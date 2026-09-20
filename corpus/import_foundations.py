#!/usr/bin/env python3
"""Import DRAGAPULT FOUNDATIONS v0.1 into a Chamber database.  Run: `python corpus/import_foundations.py`

Idempotent: concepts and cases that already exist are left alone, so re-running adds only what is new.
Nothing is ever deleted or overwritten, and the elite layer is not imported.

What is deliberately NOT imported:
  - research labels (BEST / MISTAKE / ...). They are notes about the research pass. Only FACT, COACH_GOLD and
    CONSENSUS evidence with a verdict decides an answer in the Chamber, and that is imported as evidence.
  - secondary concepts that belong to the elite layer. The foundation curriculum is exactly six concepts; a link
    to an elite concept is reported and skipped rather than quietly adding a seventh memory to schedule.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from chamber import core, db  # noqa: E402


def load():
    concepts = json.loads((HERE / 'foundations' / 'concepts.json').read_text())['concepts']
    cases = [json.loads(x) for x in (HERE / 'foundations' / 'decision_cases.jsonl').read_text().splitlines() if x.strip()]
    return concepts, cases


def source_id_for(conn, case, cache):
    """One immutable raw_source per distinct origin, reused across cases."""
    src = case['source']
    key = src.get('url') or 'constructed_from_tier0'
    if key not in cache:
        kind = 'pro_match' if src.get('type') == 'pro_match' else 'manual'
        cache[key] = core.add_source(
            conn, kind, content=json.dumps(src, ensure_ascii=False, indent=1), url=src.get('url', ''),
            metadata={'corpus': 'foundations v0.1', 'author': src.get('author', '')},
            matchup=case.get('matchup', ''))
    return cache[key]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=None, help=f'SQLite file (default {db.default_path()}, or $CHAMBER_DB)')
    p.add_argument('--dry-run', action='store_true', help='report what would change, write nothing')
    a = p.parse_args()

    conn = db.connect(a.db or db.default_path())
    core.load_seed(conn)                      # a brand-new database still needs its deck version
    concepts, cases = load()
    deck = core.current_deck(conn)
    known = {r[0] for r in conn.execute('SELECT id FROM concepts')}
    added_concepts, added_cases, skipped_links, errors = [], [], [], []

    for k in concepts:
        if k['id'] in known:
            continue
        if not a.dry_run:
            core.add_concept(conn, k['id'], k['name'], k['definition'], k['primary_skill'],
                             f"Foundation concept. {k['evidence_summary']}")
        known.add(k['id'])
        added_concepts.append(k['id'])

    cache = {}
    for c in cases:
        if conn.execute('SELECT 1 FROM decision_cases WHERE id = ?', (c['id'],)).fetchone():
            continue
        linked = [k for k in c['concepts'] if k in known]
        for k in c['concepts']:
            if k not in known:
                skipped_links.append(f"{c['id']} -> {k} (elite-layer concept, not part of the six)")
        case = {**c, 'concepts': linked, 'deck_hash': deck['hash'] if deck else None,
                'source_id': None if a.dry_run else source_id_for(conn, c, cache)}
        problems = core.validate_case(conn, case)
        if problems:
            errors.append(f"{c['id']}: {problems}")
            continue
        if not a.dry_run:
            core.insert_case(conn, case)
        added_cases.append(c['id'])

    for line in added_concepts:
        print(f'concept added   {line}')
    for line in added_cases:
        print(f'case added      {line}')
    for line in skipped_links:
        print(f'link skipped    {line}')
    for line in errors:
        print(f'REFUSED         {line}')
    print(f'{len(added_concepts)} concept(s), {len(added_cases)} case(s)'
          f'{" (dry run, nothing written)" if a.dry_run else ""}, {len(errors)} refused')
    conn.close()
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
