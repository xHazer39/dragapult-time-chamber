"""Sessions, attempts, grading and FSRS concept-memory reviews.

FSRS schedules CONCEPT MEMORY only. It never measures Pokémon skill.

Rating mapping (V1, deliberately simple, adjust here):
  - the player self-rates recall of each linked concept after the reveal: 1 Again, 2 Hard, 3 Good, 4 Easy;
  - a hint caps the rating at Hard;
  - latency, decision correctness and retries never change the rating (they are stored separately);
  - a retry (same case again within 12 hours) never updates FSRS.
"""
import json
from datetime import datetime, timedelta

from fsrs import Card, Rating, Scheduler

from .core import disputes, get_case, player_view
from .db import GRADING_LEVELS, PLAN_FIELDS, dumps, now, row

# Default FSRS parameters. No optimizer until real review history exists (see concept_reviews.log).
# Fuzzing off so scheduling is reproducible.
FSRS = Scheduler(enable_fuzzing=False)


class Refused(ValueError):
    """A request that would break a training invariant."""


def rating_for(recall: int, hint_used: bool) -> int:
    return min(recall, 2) if hint_used else recall


def grade(evidence, choice):
    """True/False only when GRADING_LEVELS evidence judges this choice unanimously. Else None."""
    verdicts = {x['verdict'] for x in evidence
                if x['level'] in GRADING_LEVELS and x['verdict'] and x['choice'] == choice}
    return verdicts.pop() == 'good' if len(verdicts) == 1 else None


# --------------------------------------------------------------------------- sessions

def start_session(conn, plan) -> int:
    cur = conn.execute('INSERT INTO sessions (started_at, plan) VALUES (?, ?)', (now(), dumps(plan)))
    conn.commit()
    return cur.lastrowid


def next_item(conn, session_id):
    s = row(conn.execute('SELECT * FROM sessions WHERE id = ?', (session_id,)).fetchone())
    if not s:
        raise Refused('unknown session')
    done = {r[0] for r in conn.execute('SELECT case_id FROM attempts WHERE session_id = ? AND answered_at IS NOT NULL',
                                       (session_id,))}
    for item in json.loads(s['plan']):
        if item['case_id'] not in done:
            case = get_case(conn, item['case_id'])
            if case and case['status'] != 'retired':
                # the concept stays server-side until the reveal: naming it would be a hint
                return {'item': {k: item[k] for k in ('case_id', 'mode', 'reason')}, 'case': player_view(case)}
    if not s['ended_at']:
        summary = row(conn.execute(
            "SELECT COUNT(*) reps, SUM(outcome = 'error') errors, SUM(outcome = 'ok') ok, "
            "SUM(outcome IS NULL) undefined FROM attempts WHERE session_id = ? AND answered_at IS NOT NULL",
            (session_id,)).fetchone())
        conn.execute('UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?', (now(), dumps(summary), session_id))
        conn.commit()
    return None


# --------------------------------------------------------------------------- attempts

def start_attempt(conn, case_id, session_id, plan) -> int:
    """Locks the declared plan. There is no endpoint to change it afterwards."""
    case = get_case(conn, case_id)
    if not case or case['status'] == 'retired':
        raise Refused('case not available')
    plan = {k: str(plan.get(k, '')).strip() for k in PLAN_FIELDS if str(plan.get(k, '')).strip()}
    missing = [f for f in case['requires'] if f not in plan]
    if missing:
        raise Refused(f'commit your plan first: {", ".join(missing)}')
    seen = conn.execute('SELECT COUNT(*) FROM attempts WHERE case_id = ? AND answered_at IS NOT NULL',
                        (case_id,)).fetchone()[0]
    t = now()
    # A retry = the same case again within 12 hours (in or out of a session). Retries never update FSRS.
    since = (datetime.fromisoformat(t) - timedelta(hours=12)).isoformat()
    retries = conn.execute('SELECT COUNT(*) FROM attempts WHERE case_id = ? AND answered_at >= ?',
                           (case_id, since)).fetchone()[0]
    cur = conn.execute(
        'INSERT INTO attempts (case_id, case_version, session_id, created_at, plan, plan_locked_at, retries, '
        'seen_before, transfer_level, difficulty, criticality) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (case_id, case['version'], session_id, t, dumps(plan), t, retries, int(seen > 0),
         'L0' if seen else case['transfer_level'], case['difficulty'], case['criticality']))
    for k in case['concepts']:
        conn.execute('INSERT INTO attempt_concepts (attempt_id, concept_id) VALUES (?, ?)', (cur.lastrowid, k['id']))
    conn.commit()
    return cur.lastrowid


def _attempt(conn, aid):
    a = row(conn.execute('SELECT * FROM attempts WHERE id = ?', (aid,)).fetchone())
    if not a or a['case_id'] is None:
        raise Refused('unknown attempt')
    return a


def use_hint(conn, aid) -> str:
    a = _attempt(conn, aid)
    if a['answered_at']:
        raise Refused('already answered')
    conn.execute('UPDATE attempts SET hint_used = 1 WHERE id = ?', (aid,))
    conn.commit()
    return get_case(conn, a['case_id'])['hint'] or 'No hint for this case.'


def answer(conn, aid, choice=None, other_text='', reasoning=''):
    a = _attempt(conn, aid)
    if a['answered_at']:
        raise Refused('already answered: an answer cannot be changed after the reveal')
    case = get_case(conn, a['case_id'])
    keys = [c['key'] for c in case['choices']]
    if choice and choice not in keys:
        raise Refused('unknown choice')
    if not choice and not other_text.strip():
        raise Refused('pick a choice or describe your line')
    correct = grade(case['evidence'], choice) if choice else None
    t = now()
    latency = int((datetime.fromisoformat(t) - datetime.fromisoformat(a['plan_locked_at'])).total_seconds() * 1000)
    conn.execute(
        'UPDATE attempts SET answered_at = ?, choice = ?, other_text = ?, reasoning = ?, latency_ms = ?, correct = ?, '
        'outcome = ?, outcome_source = ?, feedback_evidence = ? WHERE id = ?',
        (t, choice or None, other_text.strip(), reasoning.strip(), latency,
         None if correct is None else int(correct),
         None if correct is None else ('ok' if correct else 'error'),
         None if correct is None else 'evidence', dumps(case['evidence']), aid))
    conn.commit()
    return reveal(conn, aid)


def reveal(conn, aid):
    a = _attempt(conn, aid)
    if not a['answered_at']:
        raise Refused('answer first')
    case = get_case(conn, a['case_id'])
    for k in ('plan', 'error_tags', 'feedback_evidence'):
        a[k] = json.loads(a[k])
    a['coach'] = json.loads(a['coach']) if a['coach'] else None
    a['recall'] = {r[0]: r[1] for r in conn.execute(
        'SELECT concept_id, recall FROM attempt_concepts WHERE attempt_id = ?', (aid,))}
    return {'attempt': a, 'case': case, 'disputes': disputes(case['evidence']),
            'graded': a['correct'] is not None}


def review(conn, aid, ratings: dict, self_outcome=None, error_tags=(), note='', when=None, error_concepts=()):
    """Concept recall -> FSRS. Self outcomes are stored, but remain weak evidence.

    Error attribution is deliberately conservative: on multi-concept cases, only concepts
    explicitly selected as causal receive the error signal. Leaving attribution blank means
    "unsure" rather than blaming every linked concept.
    """
    a = _attempt(conn, aid)
    if not a['answered_at']:
        raise Refused('answer first')
    concepts = [r[0] for r in conn.execute('SELECT concept_id FROM attempt_concepts WHERE attempt_id = ?', (aid,))]
    if conn.execute('SELECT 1 FROM attempt_concepts WHERE attempt_id = ? AND recall IS NOT NULL', (aid,)).fetchone():
        raise Refused('already reviewed')
    if sorted(ratings) != sorted(concepts) or any(r not in (1, 2, 3, 4) for r in ratings.values()):
        raise Refused('rate recall 1-4 for every linked concept')
    if self_outcome not in (None, 'ok', 'error'):
        raise Refused('outcome must be ok, error or empty')
    selected = set(error_concepts or ())
    if not selected.issubset(set(concepts)):
        raise Refused('error_concepts must be linked to this case')

    if a['outcome_source'] != 'evidence' and self_outcome:
        conn.execute("UPDATE attempts SET outcome = ?, outcome_source = 'self' WHERE id = ?", (self_outcome, aid))
        final_outcome = self_outcome
    else:
        final_outcome = a['outcome']

    # Root-cause attribution. A single-concept error is unambiguous enough to attribute;
    # multi-concept errors require an explicit selection, otherwise remain unattributed.
    if final_outcome == 'error':
        if len(concepts) == 1:
            selected = {concepts[0]}
        if selected:
            for cid in concepts:
                conn.execute('UPDATE attempt_concepts SET error_relevant = ? WHERE attempt_id = ? AND concept_id = ?',
                             (int(cid in selected), aid, cid))
    elif final_outcome == 'ok':
        conn.execute('UPDATE attempt_concepts SET error_relevant = 0 WHERE attempt_id = ?', (aid,))

    conn.execute('UPDATE attempts SET error_tags = ?, note = ? WHERE id = ?', (dumps(sorted(set(error_tags))), note, aid))
    for k, recall in ratings.items():
        conn.execute('UPDATE attempt_concepts SET recall = ? WHERE attempt_id = ? AND concept_id = ?', (recall, aid, k))
        if a['retries'] == 0:
            fsrs_review(conn, k, rating_for(recall, bool(a['hint_used'])), aid, when)
    conn.commit()


def fsrs_review(conn, concept_id, rating, attempt_id=None, when=None):
    when = when or datetime.fromisoformat(now())
    stored = conn.execute('SELECT fsrs_card FROM concepts WHERE id = ?', (concept_id,)).fetchone()[0]
    card = Card.from_json(stored) if stored else Card(card_id=0)
    card, log = FSRS.review_card(card, Rating(rating), review_datetime=when)
    conn.execute('UPDATE concepts SET fsrs_card = ? WHERE id = ?', (card.to_json(), concept_id))
    conn.execute('INSERT INTO concept_reviews (concept_id, attempt_id, rating, reviewed_at, log) VALUES (?,?,?,?,?)',
                 (concept_id, attempt_id, rating, when.isoformat(), log.to_json()))


def memory(stored, when):
    """FSRS memory state for display. Retrievability is recall probability, NOT playing skill."""
    if not stored:
        return {'reviewed': False, 'due': True, 'due_at': None, 'retrievability': None}
    card = Card.from_json(stored)
    return {'reviewed': True, 'due': card.due <= when, 'due_at': card.due.isoformat(),
            'retrievability': round(FSRS.get_card_retrievability(card, when), 2)}


def log_real(conn, concept_ids, outcome=None, note='', source_id=None, error_tags=(), error_concepts=()):
    """Log an L4 real-match opportunity.

    Real-game outcomes are self-reported and therefore remain weak evidence in analytics.
    Multi-concept errors are attributed only to explicitly selected root-cause concepts.
    """
    if not concept_ids:
        raise Refused('name at least one concept')
    if outcome not in (None, 'ok', 'error'):
        raise Refused('outcome must be ok, error or empty')
    concepts = list(dict.fromkeys(concept_ids))
    selected = set(error_concepts or ())
    if not selected.issubset(set(concepts)):
        raise Refused('error_concepts must be among the logged concepts')
    t = now()
    cur = conn.execute(
        "INSERT INTO attempts (created_at, answered_at, transfer_level, outcome, outcome_source, error_tags, note, "
        "real_source_id) VALUES (?, ?, 'L4', ?, ?, ?, ?, ?)",
        (t, t, outcome, 'self' if outcome else None, dumps(sorted(set(error_tags))), note, source_id or None))
    if outcome == 'error' and len(concepts) == 1:
        selected = {concepts[0]}
    for k in concepts:
        relevant = None
        if outcome == 'ok':
            relevant = 0
        elif outcome == 'error' and selected:
            relevant = int(k in selected)
        conn.execute('INSERT INTO attempt_concepts (attempt_id, concept_id, error_relevant) VALUES (?, ?, ?)',
                     (cur.lastrowid, k, relevant))
    conn.commit()
    return cur.lastrowid


def save_coach(conn, aid, result):
    conn.execute('UPDATE attempts SET coach = ? WHERE id = ?', (dumps(result), aid))
    conn.commit()
