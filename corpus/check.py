#!/usr/bin/env python3
"""Integrity check over the corpus files.  Run: `python corpus/check.py`

Boring and explicit on purpose. It reads the corpus, resolves every reference it can resolve
mechanically, and prints one line per problem. Exit code 1 if anything failed.

It reuses the Chamber's own vocabularies and evidence rules (chamber.db / chamber.core) so the
corpus cannot declare something the application would refuse on import.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('CORPUS_DIR') or HERE)   # CORPUS_DIR: check a copy (used by the tests)
sys.path.insert(0, str(HERE.parent))

from chamber.core import evidence_errors  # noqa: E402
from chamber.db import COMPLETENESS, FAMILIES, PLAN_FIELDS, RECONSTRUCTION, SKILLS  # noqa: E402

# A corpus grade_status is about the research pass, never about the application.
GRADE_STATUSES = ('UNGRADED', 'GRADED_RESEARCH')
# Research labels are notes about the research, never application grades.
RESEARCH_LABELS = ('BEST', 'EXCELLENT', 'GOOD', 'INACCURACY', 'MISTAKE', 'UNGRADED')
# A FACT verdict in the corpus must name why it is deterministic.
FACT_BASES = ('RULE', 'LEGALITY', 'EXACT_DAMAGE', 'PRIZE_ARITHMETIC', 'RESOURCE_ARITHMETIC',
              'FORCED_LINE', 'STRICT_DOMINANCE')

problems = []


def fail(where, msg):
    problems.append(f'{where}: {msg}')


# --------------------------------------------------------------------------- loading

def load_json(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        fail(rel, f'malformed JSON at line {e.lineno} column {e.colno}: {e.msg}')
        return None


def load_jsonl(rel):
    p = ROOT / rel
    if not p.exists():
        return []
    rows = []
    for n, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            fail(f'{rel}:{n}', f'malformed JSON: {e.msg}')
    return rows


def unique_ids(rel, rows, key='id'):
    seen = set()
    for n, r in enumerate(rows, 1):
        i = r.get(key)
        if not i:
            fail(f'{rel}:{n}', f'missing {key}')
        elif i in seen:
            fail(f'{rel}:{n}', f'duplicate {key} {i!r}')
        seen.add(i)
    return seen


# --------------------------------------------------------------------------- references

def source_key(url):
    """A YouTube video is one source whatever the &t= is; anything else is its path."""
    u = urlsplit(url or '')
    if 'youtu' in u.netloc:
        return parse_qs(u.query).get('v', [u.path.lstrip('/')])[0]
    return f'{u.netloc}{u.path}'.rstrip('/')


def check_source_ref(where, src, known_sources, fact_ids):
    """A corpus object points either at a registered source or at Tier-0 facts."""
    if not isinstance(src, dict):
        return fail(where, 'source must be an object')
    refs = src.get('fact_refs') or []
    for r in refs:
        if r not in fact_ids:
            fail(where, f'source fact_refs names unknown fact {r!r}')
    url = src.get('url')
    if url and not any(source_key(url).startswith(k) for k in known_sources):
        fail(where, f'source url {url!r} is not in sources/source_registry.jsonl or sources/pro_matches.jsonl')
    if not url and not refs:
        fail(where, 'source names neither a url nor fact_refs')


def check_deck_ref(where, obj, decks):
    ref = obj.get('deck_reference')
    if ref and not (HERE.parent / ref).exists():
        fail(where, f'deck_reference {ref!r} does not exist')
    h = obj.get('deck_hash_name_count')
    if h and not any(full.startswith(h) for full in decks.values()):
        fail(where, f'deck hash {h!r} matches no deck in corpus/decks/')


# --------------------------------------------------------------------------- cases

def check_case(where, c, concept_ids, known_sources, fact_ids, decks):
    for f in ('observed_state', 'prompt', 'criticality_source'):
        if not str(c.get(f, '')).strip():
            fail(where, f'{f} is required')
    if c.get('decision_family') not in FAMILIES:
        fail(where, f"decision_family {c.get('decision_family')!r} invalid")
    if c.get('completeness') not in COMPLETENESS:
        fail(where, f"completeness {c.get('completeness')!r} invalid")
    if c.get('reconstruction') not in RECONSTRUCTION:
        fail(where, f"reconstruction {c.get('reconstruction')!r} invalid")
    if not (isinstance(c.get('criticality'), int) and 0 <= c['criticality'] <= 4):
        fail(where, 'criticality must be an int 0-4')
    if c.get('transfer_level') not in ('L0', 'L1', 'L2', 'L3'):
        fail(where, 'transfer_level must be L0-L3 (L4 is a real game, not a case)')
    for f in c.get('requires', []):
        if f not in PLAN_FIELDS:
            fail(where, f'requires names unknown plan field {f!r}')

    keys = [ch.get('key') for ch in c.get('choices', [])]
    if len(keys) != len(set(keys)):
        fail(where, 'choice keys must be unique')
    if c.get('completeness') == 'EXHAUSTIVE' and not keys:
        fail(where, 'EXHAUSTIVE completeness needs choices')

    for k in c.get('concepts', []):
        if k not in concept_ids:
            fail(where, f'unknown concept {k!r}')
    if not c.get('concepts'):
        fail(where, 'link at least one concept')

    if not c.get('evidence'):
        fail(where, 'add at least one evidence item (use level UNKNOWN if nothing is established)')
    for i, x in enumerate(c.get('evidence', []), 1):
        for m in evidence_errors(x, keys, c.get('reconstruction')):
            fail(f'{where} evidence {i}', m)
        if x.get('level') == 'FACT' and x.get('fact_basis') not in FACT_BASES:
            fail(f'{where} evidence {i}',
                 f'FACT needs a deterministic fact_basis from {FACT_BASES}, got {x.get("fact_basis")!r}')

    check_source_ref(where, c.get('source', {}), known_sources, fact_ids)
    check_deck_ref(where, c, decks)
    check_research_label(where, c)


def check_research_label(where, c):
    """A research label is a note about the research, never an application grade.

    What decides an answer in the Chamber is FACT/COACH_GOLD/CONSENSUS evidence carrying a verdict,
    and nothing else. So a case that carries a label such as BEST or MISTAKE must say, in writing,
    that the label is research only -- otherwise it could be imported as truth by mistake.
    """
    rl = c.get('research_label')
    if not rl:
        return
    label, status = rl.get('label'), rl.get('grade_status')
    if label not in RESEARCH_LABELS:
        fail(where, f'research_label.label {label!r} is not one of {RESEARCH_LABELS}')
    if status not in GRADE_STATUSES:
        fail(where, f'research_label.grade_status {status!r} is not one of {GRADE_STATUSES}')
    if (label == 'UNGRADED') != (status == 'UNGRADED'):
        fail(where, f'label {label!r} and grade_status {status!r} disagree')
    if status == 'GRADED_RESEARCH' and 'RESEARCH LABEL ONLY' not in (rl.get('note') or ''):
        fail(where, 'a research grade must carry the "RESEARCH LABEL ONLY" note')
    if not rl.get('why'):
        fail(where, 'research_label needs a why')


# --------------------------------------------------------------------------- declared counts

def check_declared(rel, table):
    text = (ROOT / rel).read_text()
    for pattern, actual, label in table:
        m = re.search(pattern, text)
        if not m:
            fail(rel, f'declared count for {label} not found (pattern {pattern!r})')
        elif int(m[1]) != actual:
            fail(rel, f'declares {m[1]} {label}, found {actual}')


# --------------------------------------------------------------------------- main

def main():
    concepts = (load_json('extracted/concepts.json') or {}).get('concepts', [])
    claims = load_jsonl('extracted/claims.jsonl')
    candidates = load_jsonl('extracted/candidate_cases.jsonl')
    cases = load_jsonl('validated/decision_cases.jsonl')
    registry = load_jsonl('sources/source_registry.jsonl')
    matches = load_jsonl('sources/pro_matches.jsonl')
    rules = load_jsonl('facts/rules.jsonl')
    cards = load_jsonl('facts/cards.jsonl')
    ledger = load_jsonl('validated/validation_ledger.jsonl')
    f_concepts = (load_json('foundations/concepts.json') or {}).get('concepts', [])
    f_cases = load_jsonl('foundations/decision_cases.jsonl')

    claim_ids = unique_ids('extracted/claims.jsonl', claims)
    concept_ids = unique_ids('extracted/concepts.json', concepts)
    f_concept_ids = unique_ids('foundations/concepts.json', f_concepts)
    unique_ids('extracted/candidate_cases.jsonl', candidates)
    unique_ids('validated/decision_cases.jsonl', cases)
    unique_ids('foundations/decision_cases.jsonl', f_cases)
    unique_ids('sources/source_registry.jsonl', registry)
    unique_ids('sources/pro_matches.jsonl', matches)
    rule_ids = unique_ids('facts/rules.jsonl', rules)
    card_ids = unique_ids('facts/cards.jsonl', cards)
    fact_ids = rule_ids | card_ids
    for dup in concept_ids & f_concept_ids:
        fail('foundations/concepts.json', f'concept {dup!r} duplicates the elite corpus')

    # Chamber seed concepts are canonical too: a foundation case may target one of them.
    seed = json.loads((HERE.parent / 'chamber' / 'seed.json').read_text())
    all_concepts = concept_ids | f_concept_ids | {k['id'] for k in seed['concepts']}

    known_sources = {source_key(s.get('url')) for s in registry + matches if s.get('url')}
    decks = {p.name: json.loads(p.read_text()).get('hash_sha256_name_count', '')
             for p in sorted((ROOT / 'decks').glob('*.json'))}

    for c in concepts:
        if c.get('primary_skill') not in SKILLS:
            fail(f"concept {c['id']}", f"primary_skill {c.get('primary_skill')!r} is not a Chamber skill")
        for cl in c.get('supporting_claim_ids', []):
            if cl not in claim_ids:
                fail(f"concept {c['id']}", f'supporting claim {cl!r} does not exist')
        if not c.get('supporting_claim_ids'):
            fail(f"concept {c['id']}", 'no supporting claim')

    for c in claims:
        check_source_ref(f"claim {c['id']}", c.get('source', {}), known_sources, fact_ids)

    for c in candidates:
        # candidate_concepts are proposals from extraction, not validated ids: not checked here.
        check_source_ref(f"candidate {c['id']}", c.get('source', {}), known_sources, fact_ids)

    for c in cases:
        check_case(f"case {c['id']}", c, all_concepts, known_sources, fact_ids, decks)

    case_ids = {c['id'] for c in cases} | {c['id'] for c in candidates}
    for e in ledger:
        if e.get('case') not in case_ids:
            fail('validation_ledger', f"entry for unknown case/candidate {e.get('case')!r}")

    # ---- foundations layer: 6 concepts, 2 cases each, exactly one primary concept per case
    for c in f_cases:
        where = f"foundation case {c['id']}"
        check_case(where, c, all_concepts, known_sources, fact_ids, decks)
        primary = c.get('primary_concept')
        if primary not in all_concepts:
            fail(where, f'primary_concept {primary!r} is unknown')
        elif primary not in c.get('concepts', []):
            fail(where, 'primary_concept is not among the case concepts')
        if c.get('layer') != 'foundation':
            fail(where, "layer must be 'foundation'")
    if f_concepts:
        if len(f_concepts) != 6:
            fail('foundations/concepts.json', f'expected 6 foundation concepts, found {len(f_concepts)}')
        for k in f_concepts:
            n = sum(c.get('primary_concept') == k['id'] for c in f_cases)
            if n != 2:
                fail('foundations', f"concept {k['id']} has {n} case(s) as primary concept, expected 2")
        for k in f_concepts:
            if k.get('primary_skill') not in SKILLS:
                fail(f"foundation concept {k['id']}", f"primary_skill {k.get('primary_skill')!r} is not a Chamber skill")

    check_declared('CORPUS_REPORT.md', [
        (r'Concepts: \*\*(\d+)\*\*', len(concepts), 'concepts'),
        (r'Claims: \*\*(\d+)\*\*', len(claims), 'claims'),
        (r'Candidate positions: \*\*(\d+)\*\*', len(candidates), 'candidate positions'),
        (r'Chamber-ready DecisionCases: \*\*(\d+)\*\*', len(cases), 'decision cases'),
        (r'Rules facts: \*\*(\d+)\*\*', len(rules), 'rules facts'),
        (r'Card facts: \*\*(\d+)\*\*', len(cards), 'card facts'),
        (r'Pro matches: \*\*(\d+)\*\*', len(matches), 'pro matches'),
        (r'Registered sources: \*\*(\d+)\*\*', len(registry), 'registered sources'),
        (r'Playbook principles: \*\*(\d+)\*\*',
         len(re.findall(r'(?m)^\d+\. \*\*', (ROOT / 'validated/PLAYBOOK_v0.1.md').read_text())), 'playbook principles'),
    ])
    check_declared('validated/PLAYBOOK_v0.1.md', [
        (r'\*\*(\d+)\*\* principles',
         len(re.findall(r'(?m)^\d+\. \*\*', (ROOT / 'validated/PLAYBOOK_v0.1.md').read_text())), 'principles'),
    ])

    for p in problems:
        print(p)
    n_objects = sum(map(len, (concepts, claims, candidates, cases, registry, matches, rules, cards,
                              f_concepts, f_cases)))
    print(f'{len(problems)} problem(s) over {n_objects} corpus objects')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
