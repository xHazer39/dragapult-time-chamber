"""Decks, raw sources, candidate cases, decision cases, evidence. Provenance lives here."""
import hashlib
import json
import re
from pathlib import Path

from .db import (COMPLETENESS, FAMILIES, LEVELS, PLAN_FIELDS, RECONSTRUCTION, SKILLS, SOURCE_TYPES,
                 dumps, now, row)

SEED = Path(__file__).with_name('seed.json')
JSON_FIELDS = ('unknown_fields', 'requires', 'choices', 'symptom_tags', 'root_cause_tags')
CASE_COLUMNS = ('id', 'source_id', 'deck_hash', 'format', 'date', 'matchup', 'observed_state', 'full_record',
                'unknown_fields', 'prompt', 'requires', 'hint', 'decision_family', 'criticality',
                'criticality_source', 'choices', 'completeness', 'symptom_tags', 'root_cause_tags', 'difficulty',
                'transfer_level', 'variant_of', 'reconstruction', 'synthetic')
# The only case fields a player may see before answering. Everything else is reveal-only.
PLAYER_FIELDS = ('id', 'version', 'format', 'matchup', 'observed_state', 'unknown_fields', 'prompt', 'requires',
                 'decision_family', 'choices', 'completeness', 'transfer_level', 'synthetic', 'deck_label')


# --------------------------------------------------------------------------- decks

def parse_deck(text: str) -> list:
    """PTCGL export lines like '3 Dragapult ex TWM 130'. Headers and blanks are ignored."""
    cards = []
    for line in text.splitlines():
        m = re.match(r'\s*(\d+)\s+(.+?)(?:\s+([A-Z0-9]{2,5})\s+(\d+[a-z]?))?\s*$', line)
        if m:
            cards.append([int(m[1]), m[2], m[3] or '', m[4] or ''])
    return cards


def deck_hash(cards: list) -> str:
    canon = '\n'.join(f'{q} {n} {s} {num}' for q, n, s, num in sorted(cards, key=lambda c: c[1:]))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def add_deck(conn, deck_id: str, cards: list, source: str, format: str = '', date: str = '') -> str:
    total = sum(c[0] for c in cards)
    if total != 60:
        raise ValueError(f'deck must have exactly 60 cards, got {total}')
    h = deck_hash(cards)
    if conn.execute('SELECT 1 FROM deck_versions WHERE hash = ?', (h,)).fetchone():
        return h
    version = conn.execute('SELECT COALESCE(MAX(version), 0) + 1 FROM deck_versions WHERE deck_id = ?',
                           (deck_id,)).fetchone()[0]
    conn.execute('INSERT INTO deck_versions VALUES (?,?,?,?,?,?,?,?)',
                 (h, deck_id, version, dumps(sorted(cards, key=lambda c: c[1:])), source, format, date, now()))
    conn.commit()
    return h


def current_deck(conn, deck_id='dragapult'):
    return row(conn.execute('SELECT * FROM deck_versions WHERE deck_id = ? ORDER BY version DESC LIMIT 1',
                            (deck_id,)).fetchone())


def deck_label(conn, h):
    d = conn.execute('SELECT deck_id, version FROM deck_versions WHERE hash = ?', (h,)).fetchone() if h else None
    return f'{d[0]} v{d[1]} ({h})' if d else 'unspecified'


# --------------------------------------------------------------------------- raw sources

def add_source(conn, source_type, content='', url='', metadata=None, deck_hash=None, matchup='') -> int:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f'unknown source type {source_type!r}')
    if not (content.strip() or url.strip()):
        raise ValueError('a source needs content or a URL')
    sha = hashlib.sha256(f'{source_type}\n{url}\n{content}'.encode()).hexdigest()
    cur = conn.execute('INSERT INTO raw_sources (source_type, content, url, sha256, metadata, deck_hash, matchup, '
                       'created_at) VALUES (?,?,?,?,?,?,?,?)',
                       (source_type, content, url, sha, dumps(metadata or {}), deck_hash or None, matchup, now()))
    conn.commit()
    return cur.lastrowid


def get_source(conn, source_id):
    s = row(conn.execute('SELECT * FROM raw_sources WHERE id = ?', (source_id,)).fetchone())
    if s:
        s['metadata'] = json.loads(s['metadata'])
        s['timeline'] = timeline(s['content']) if s['source_type'] == 'ptcgl_log' else []
    return s


def timeline(text: str) -> list:
    """Best-effort grouping of a PTCGL log by 'Turn # N' headers. Never interprets game actions."""
    groups = [{'title': 'Setup', 'lines': []}]
    for n, line in enumerate(text.splitlines(), 1):
        if re.match(r'\s*Turn\s*#\s*\d+', line):
            groups.append({'title': line.strip(), 'lines': []})
        elif line.strip():
            groups[-1]['lines'].append({'n': n, 'text': line})
    return [g for g in groups if g['lines'] or g['title'] != 'Setup']


def anonymize(text: str, names) -> str:
    for name in names or []:
        if name.strip():
            text = re.sub(re.escape(name.strip()), 'OPPONENT', text, flags=re.IGNORECASE)
    return text


# --------------------------------------------------------------------------- candidates

def create_candidate(conn, source_id, excerpt=''):
    src = get_source(conn, source_id)
    if not src:
        raise ValueError('unknown source')
    data = {'full_record': anonymize(excerpt, [src['metadata'].get('opponent_name', '')]),
            'matchup': src['matchup'], 'deck_hash': src['deck_hash'], 'observed_state': '', 'prompt': '',
            'unknown_fields': [], 'requires': ['objective'], 'hint': '', 'decision_family': 'other',
            'criticality': 2, 'criticality_source': '', 'choices': [], 'completeness': 'UNKNOWN',
            'symptom_tags': [], 'root_cause_tags': [], 'difficulty': 2, 'transfer_level': 'L2',
            'reconstruction': 'unknown', 'synthetic': False, 'concepts': [], 'evidence': [],
            'format': '', 'date': src['created_at'][:10]}
    t = now()
    cur = conn.execute('INSERT INTO candidate_cases (source_id, data, created_at, updated_at) VALUES (?,?,?,?)',
                       (source_id, dumps(data), t, t))
    conn.commit()
    return cur.lastrowid


def get_candidate(conn, cid):
    c = row(conn.execute('SELECT * FROM candidate_cases WHERE id = ?', (cid,)).fetchone())
    if c:
        c['data'] = json.loads(c['data'])
    return c


def update_candidate(conn, cid, data):
    if conn.execute("UPDATE candidate_cases SET data = ?, updated_at = ? WHERE id = ? AND status = 'draft'",
                    (dumps(data), now(), cid)).rowcount != 1:
        raise ValueError('only draft candidates can be edited')
    conn.commit()


def promote(conn, cid):
    """Human-validated candidate -> DecisionCase. Returns (case_id, errors)."""
    c = get_candidate(conn, cid)
    if not c or c['status'] != 'draft':
        return None, ['candidate not found or not a draft']
    case = {**c['data'], 'source_id': c['source_id']}
    case.setdefault('id', '')
    case['id'] = case['id'] or f"case-{c['source_id']}-{cid}"
    errors = validate_case(conn, case)
    if errors:
        return None, errors
    insert_case(conn, case, commit=False)
    conn.execute("UPDATE candidate_cases SET status = 'promoted', case_id = ?, updated_at = ? WHERE id = ?",
                 (case['id'], now(), cid))
    conn.commit()
    return case['id'], []


# --------------------------------------------------------------------------- decision cases

def validate_case(conn, c) -> list:
    """Readable errors for a human. The DB CHECKs/triggers are the backstop for the same rules."""
    e = []
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', str(c.get('id', ''))):
        e.append('id: lowercase letters, digits, - and _ only')
    elif conn.execute('SELECT 1 FROM decision_cases WHERE id = ?', (c['id'],)).fetchone():
        e.append(f"id {c['id']!r} already exists")
    for f in ('observed_state', 'prompt', 'criticality_source'):
        if not str(c.get(f, '')).strip():
            e.append(f'{f} is required')
    if c.get('decision_family') not in FAMILIES:
        e.append('decision_family invalid')
    if c.get('completeness') not in COMPLETENESS:
        e.append('completeness invalid')
    if c.get('reconstruction') not in RECONSTRUCTION:
        e.append('reconstruction invalid')
    if not (isinstance(c.get('criticality'), int) and 0 <= c['criticality'] <= 4):
        e.append('criticality must be 0-4')
    if c.get('transfer_level', 'L2') not in ('L0', 'L1', 'L2', 'L3'):
        e.append('transfer_level must be L0-L3 (L4 is a real game, not a case)')
    if any(f not in PLAN_FIELDS for f in c.get('requires', [])):
        e.append(f'requires must be a subset of {PLAN_FIELDS}')
    keys = [ch.get('key') for ch in c.get('choices', [])]
    if len(keys) != len(set(keys)) or any(not k or not ch.get('text') for k, ch in zip(keys, c.get('choices', []))):
        e.append('choices need unique keys and text')
    if c.get('completeness') == 'EXHAUSTIVE' and not keys:
        e.append('EXHAUSTIVE completeness needs choices')
    concepts = c.get('concepts', [])
    if not concepts:
        e.append('link at least one concept')
    for k in concepts:
        if not conn.execute("SELECT 1 FROM concepts WHERE id = ?", (k,)).fetchone():
            e.append(f'unknown concept {k!r}')
    if c.get('deck_hash') and not conn.execute('SELECT 1 FROM deck_versions WHERE hash = ?',
                                                (c['deck_hash'],)).fetchone():
        e.append('unknown deck version')
    if c.get('variant_of') and not conn.execute('SELECT 1 FROM decision_cases WHERE id = ?',
                                                 (c['variant_of'],)).fetchone():
        e.append('variant_of refers to an unknown case')
    ev = c.get('evidence', [])
    if not ev:
        e.append('add at least one evidence item (use level UNKNOWN if nothing is established)')
    for i, x in enumerate(ev):
        e += [f'evidence {i + 1}: {m}' for m in evidence_errors(x, keys, c.get('reconstruction'))]
    return e


def evidence_errors(x, choice_keys, reconstruction) -> list:
    e = []
    if x.get('level') not in LEVELS:
        e.append('level invalid')
    if not str(x.get('claim', '')).strip():
        e.append('claim is required')
    if x.get('choice') and x['choice'] not in choice_keys:
        e.append(f"choice {x['choice']!r} is not one of the case choices")
    if x.get('verdict') not in (None, '', 'good', 'bad'):
        e.append('verdict must be good, bad or empty')
    if x.get('verdict') and not x.get('choice'):
        e.append('a verdict must name the choice it judges')
    if x.get('verdict') and x.get('level') in ('PRO_LINE', 'SIMULATION', 'UNKNOWN'):
        e.append(f"{x['level']} cannot carry a verdict (a pro line or simulation is not a best move)")
    if x.get('level') == 'COACH_GOLD' and not str(x.get('reviewer', '')).strip():
        e.append('COACH_GOLD needs an identified reviewer')
    if x.get('level') == 'CONSENSUS' and not str(x.get('source_ref', '')).strip():
        e.append('CONSENSUS needs source references')
    if x.get('level') == 'FACT' and reconstruction not in ('exact', 'high'):
        e.append('FACT needs exact/high reconstruction; use HEURISTIC or UNKNOWN for an uncertain log')
    return e


def insert_case(conn, c, commit=True):
    vals = {k: c.get(k) for k in CASE_COLUMNS}
    for k in JSON_FIELDS:
        vals[k] = dumps(c.get(k) or [])
    for k, default in (('format', ''), ('date', ''), ('matchup', ''), ('full_record', ''), ('hint', ''),
                       ('difficulty', 2), ('transfer_level', 'L2')):
        vals[k] = vals[k] if vals[k] not in (None, '') else default
    vals['synthetic'] = int(bool(c.get('synthetic')))
    vals['deck_hash'] = vals['deck_hash'] or None
    vals['variant_of'] = vals['variant_of'] or None
    conn.execute(f"INSERT INTO decision_cases ({','.join(vals)}, created_at) VALUES "
                 f"({','.join('?' * len(vals))}, ?)", (*vals.values(), now()))
    for k in c['concepts']:
        conn.execute('INSERT INTO case_concepts VALUES (?, ?)', (c['id'], k))
    for x in c['evidence']:
        insert_evidence(conn, c['id'], x)
    if commit:
        conn.commit()


def insert_evidence(conn, case_id, x):
    conn.execute('INSERT INTO evidence (case_id, level, claim, choice, verdict, source_ref, reviewer, created_at) '
                 'VALUES (?,?,?,?,?,?,?,?)',
                 (case_id, x['level'], x['claim'].strip(), x.get('choice') or None, x.get('verdict') or None,
                  x.get('source_ref', ''), x.get('reviewer', ''), now()))


def add_evidence(conn, case_id, x) -> list:
    """Later evidence (e.g. a coach review). Appended, never replacing what is there."""
    c = get_case(conn, case_id)
    if not c:
        return ['unknown case']
    errors = evidence_errors(x, [ch['key'] for ch in c['choices']], c['reconstruction'])
    if not errors:
        insert_evidence(conn, case_id, x)
        conn.commit()
    return errors


def get_case(conn, case_id):
    c = row(conn.execute('SELECT * FROM decision_cases WHERE id = ?', (case_id,)).fetchone())
    if not c:
        return None
    for k in JSON_FIELDS:
        c[k] = json.loads(c[k])
    c['synthetic'] = bool(c['synthetic'])
    c['deck_label'] = deck_label(conn, c['deck_hash'])
    c['concepts'] = [row(r) for r in conn.execute(
        'SELECT c.id, c.name, c.definition, c.skill FROM case_concepts cc JOIN concepts c ON c.id = cc.concept_id '
        'WHERE cc.case_id = ? ORDER BY c.id', (case_id,))]
    c['evidence'] = [row(r) for r in conn.execute('SELECT * FROM evidence WHERE case_id = ? ORDER BY id',
                                                  (case_id,))]
    return c


def player_view(case: dict) -> dict:
    """What the player sees before committing: no evidence, no concepts, no full record, no hint."""
    return {k: case[k] for k in PLAYER_FIELDS}


def disputes(evidence) -> list:
    """Choices on which evidence items give opposite verdicts. Shown, never auto-resolved."""
    by_choice = {}
    for x in evidence:
        if x['verdict']:
            by_choice.setdefault(x['choice'], set()).add(x['verdict'])
    return sorted(k for k, v in by_choice.items() if len(v) > 1)


def add_concept(conn, cid, name, definition, skill, notes=''):
    if skill not in SKILLS:
        raise ValueError(f'skill must be one of {SKILLS}')
    if not re.fullmatch(r'[a-z0-9_]+', cid or ''):
        raise ValueError('concept id: lowercase letters, digits and _ only')
    conn.execute('INSERT INTO concepts (id, name, definition, skill, notes, created_at) VALUES (?,?,?,?,?,?)',
                 (cid, name, definition, skill, notes, now()))
    conn.commit()


def load_seed(conn, path=SEED):
    """Demo content on an empty DB only. Every seed case is synthetic and says so."""
    if conn.execute('SELECT 1 FROM concepts').fetchone():
        return False
    seed = json.loads(Path(path).read_text())
    d = seed['deck']
    h = add_deck(conn, d['deck_id'], d['cards'], d['source'], d['format'], d['date'])
    for k in seed['concepts']:
        add_concept(conn, k['id'], k['name'], k['definition'], k['skill'], k.get('notes', ''))
    for c in seed['cases']:
        c = {**c, 'deck_hash': h}
        errors = validate_case(conn, c)
        if errors:
            raise ValueError(f"seed case {c['id']}: {errors}")
        insert_case(conn, c)
    return True
