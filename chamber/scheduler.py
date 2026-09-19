"""Chamber scheduler: what is most worth training now. Small, deterministic, explainable.

FSRS says when a concept's memory is due. Performance signals (recent errors, repeat errors in real games,
missing unseen/real evidence) say where the leaks are. Three modes keep it out of a filter bubble:
  exploit  - known recurring leaks
  coverage - important concepts/skills outside the current leaks, memory-due first
  probe    - never-attempted positions, to find leaks nobody has recorded yet
The defaults below are a starting point, not a tuned optimum.
"""
import hashlib
from datetime import datetime, timedelta

from .core import current_deck
from .stats import concept_stats

CONFIG = {
    'reps': 6,
    'mix': {'exploit': 0.5, 'coverage': 0.3, 'probe': 0.2},
    'min_criticality': 2,           # 0-1 cases are ignored
    'seed': 0,                      # tie-break rotation for probe; same seed + same data = same plan
    'real_game_days': 14,
    'play_after_unseen': (5, 0.8),  # >= 5 recent unseen results and >= 80% ok -> recommend real games
}
EVIDENCE_RANK = {'FACT': 2, 'COACH_GOLD': 2, 'CONSENSUS': 2, 'PRO_LINE': 1, 'SIMULATION': 1}


def _h(seed, s):
    return hashlib.sha256(f'{seed}:{s}'.encode()).hexdigest()


def mode_sequence(n, mix):
    """Deterministic interleave: at each rep choose the mode furthest below its target share."""
    counts, seq = {m: 0 for m in mix}, []
    for i in range(n):
        m = max(mix, key=lambda k: (mix[k] * (i + 1) - counts[k], -list(mix).index(k)))
        counts[m] += 1
        seq.append(m)
    return seq


def servable_cases(conn, cfg):
    rows = conn.execute(
        "SELECT dc.id, dc.criticality, cc.concept_id, "
        "(SELECT COUNT(*) FROM attempts a WHERE a.case_id = dc.id AND a.answered_at IS NOT NULL) seen, "
        "(SELECT MAX(created_at) FROM attempts a WHERE a.case_id = dc.id) last_at, "
        "(SELECT GROUP_CONCAT(level) FROM evidence e WHERE e.case_id = dc.id) levels "
        "FROM decision_cases dc JOIN case_concepts cc ON cc.case_id = dc.id "
        "JOIN concepts k ON k.id = cc.concept_id AND k.status = 'active' "
        "WHERE dc.status = 'active' AND dc.criticality >= ?", (cfg['min_criticality'],)).fetchall()
    by_concept = {}
    for r in rows:
        r = dict(r)
        r['evidence_rank'] = max((EVIDENCE_RANK.get(x, 0) for x in (r['levels'] or '').split(',')), default=0)
        by_concept.setdefault(r['concept_id'], []).append(r)
    return by_concept


def case_key(cfg):
    # unseen first (transfer), then criticality, then defensible evidence, then least recent, then stable hash
    return lambda r: (r['seen'] > 0, -r['criticality'], -r['evidence_rank'], r['last_at'] or '', _h(cfg['seed'], r['id']))


def plan(conn, when: datetime, cfg=CONFIG):
    stats = {s['id']: s for s in concept_stats(conn, when)}
    cases = servable_cases(conn, cfg)
    used_cases, used_concepts, used_skills, items = set(), set(), set(), []

    def pick_case(cid):
        free = [r for r in cases.get(cid, []) if r['id'] not in used_cases]
        return min(free, key=case_key(cfg)) if free else None

    def exploit():
        leaks = []
        for cid, s in stats.items():
            if not s['recent']['errors'] or cid not in cases or cid in used_concepts:
                continue
            score = (2 * s['recent']['errors'] / s['recent']['n'] + 2 * bool(s['repeat']['real']['errors'])
                     + s['memory']['due'] + max(r['criticality'] for r in cases[cid]) / 4)
            leaks.append((-score, cid))
        for _, cid in sorted(leaks):
            case = pick_case(cid)
            if case:
                s = stats[cid]
                why = f"{s['recent']['errors']}/{s['recent']['n']} recent results were errors"
                if s['repeat']['real']['errors']:
                    why += f"; repeated in {s['repeat']['real']['errors']} real game(s)"
                return case, cid, why + ('; memory due' if s['memory']['due'] else '')
        return None

    def coverage():
        cands = []
        for cid, s in stats.items():
            if s['recent']['errors'] or cid not in cases or cid in used_concepts:
                continue
            m = s['memory']
            score = (m['due'] + (1 - m['retrievability'] if m['reviewed'] else 1)
                     + max(r['criticality'] for r in cases[cid]) / 4 + 0.5 * (s['skill'] not in used_skills))
            cands.append((-score, cid))
        for _, cid in sorted(cands):
            case = pick_case(cid)
            if case:
                m = stats[cid]['memory']
                why = ('concept never reviewed' if not m['reviewed'] else
                       f"memory due (recall probability {m['retrievability']})" if m['due'] else
                       'keeps an important skill in rotation')
                return case, cid, why
        return None

    def probe():
        cands = []
        for cid, rows in cases.items():
            if cid not in stats:
                continue
            unseen_results = stats[cid]['tiers']['unseen']['ok'] + stats[cid]['tiers']['unseen']['error']
            for r in rows:
                if r['seen'] == 0 and r['id'] not in used_cases:
                    cands.append(((unseen_results, _h(cfg['seed'], r['id'])), r, cid, unseen_results))
        if not cands:
            return None
        _, r, cid, n = min(cands, key=lambda c: c[0])
        return r, cid, f'never-attempted position; {n} unseen result(s) recorded for this concept'

    pickers = {'exploit': exploit, 'coverage': coverage, 'probe': probe}
    for mode in mode_sequence(cfg['reps'], cfg['mix']):
        order = [mode] + [m for m in ('coverage', 'probe', 'exploit') if m != mode]
        for m in order:
            got = pickers[m]()
            if got:
                case, cid, why = got
                if m != mode:
                    why = f'{why} (no {mode} candidate)'
                items.append({'case_id': case['id'], 'concept_id': cid, 'mode': m, 'reason': why})
                used_cases.add(case['id'])
                used_concepts.add(cid)
                used_skills.add(stats[cid]['skill'])
                break
        else:
            break
    return items


def play_recommendation(conn, when, cfg=CONFIG, items=None):
    since = (when - timedelta(days=cfg['real_game_days'])).isoformat()
    recent_real = conn.execute("SELECT COUNT(*) FROM attempts WHERE transfer_level = 'L4' AND created_at >= ?",
                               (since,)).fetchone()[0]
    unseen = conn.execute("SELECT outcome FROM attempts WHERE transfer_level IN ('L2', 'L3') AND outcome IS NOT NULL "
                          "ORDER BY created_at DESC, id DESC LIMIT 10").fetchall()
    n, ok = len(unseen), sum(r[0] == 'ok' for r in unseen)
    need_n, need_rate = cfg['play_after_unseen']
    if items is not None and not items:
        return {'play': True, 'reason': 'Nothing worth drilling right now. Go play competitive matches and log '
                                         'the key decisions in the Inbox.'}
    if recent_real == 0 and n >= need_n and ok / n >= need_rate:
        return {'play': True, 'reason': f"Drills: {ok}/{n} recent unseen cases ok, but no real-match opportunity "
                                         f"logged in {cfg['real_game_days']} days. Go play competitive matches, "
                                         'then log what happened.'}
    if recent_real == 0:
        return {'play': False, 'reason': f"No real-match opportunity logged in {cfg['real_game_days']} days: "
                                          'drill results alone cannot show transfer.'}
    return {'play': False, 'reason': f'{recent_real} real-match opportunity(ies) logged recently.'}


def today(conn, when, cfg=CONFIG):
    items = plan(conn, when, cfg)
    stats = concept_stats(conn, when)
    deck = current_deck(conn)
    stale = conn.execute("SELECT COUNT(*) FROM decision_cases WHERE status = 'active' AND deck_hash IS NOT NULL "
                         'AND deck_hash <> ?', (deck['hash'] if deck else '',)).fetchone()[0] if deck else 0
    return {
        'plan': items,
        'leaks': [{'id': s['id'], 'name': s['name'], 'recent': s['recent'], 'status': s['status']}
                  for s in stats if s['recent']['errors'] or s['repeat']['real']['errors']],
        'due': [{'id': s['id'], 'name': s['name']} for s in stats if s['memory']['due']],
        'play': play_recommendation(conn, when, cfg, items),
        'deck': {'label': f"{deck['deck_id']} v{deck['version']} ({deck['hash']})" if deck else 'no deck version',
                 'cases_for_older_versions': stale},
        'config': cfg,
    }
