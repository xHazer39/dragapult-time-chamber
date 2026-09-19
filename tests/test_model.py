"""Gate A: the core model represents heterogeneous cases without hacks; provenance invariants hold."""
import json
import sqlite3

import pytest
from conftest import FIXTURES, load_fixtures

from chamber import core, db
from chamber.train import grade

BASE = {'id': 'x-case', 'observed_state': 's', 'prompt': 'p', 'criticality_source': 'me', 'decision_family': 'other',
        'completeness': 'PARTIAL', 'reconstruction': 'exact', 'criticality': 2, 'transfer_level': 'L2',
        'choices': [{'key': 'A', 'text': 'a'}], 'concepts': ['c_seq'],
        'evidence': [{'level': 'HEURISTIC', 'claim': 'x'}]}


def test_every_fixture_round_trips_deterministically(fx):
    for c in FIXTURES['cases']:
        a, b = core.get_case(fx, c['id']), core.get_case(fx, c['id'])
        assert db.dumps(a) == db.dumps(b)
        assert [k['id'] for k in a['concepts']] == sorted(c['concepts'])
        assert len(a['evidence']) == len(c['evidence'])
    shapes = {c['decision_family'] for c in FIXTURES['cases']}
    assert len(FIXTURES['cases']) >= 10 and len(shapes) >= 7


@pytest.mark.parametrize('bad', FIXTURES['invalid'], ids=lambda b: b['expect'])
def test_invalid_cases_are_rejected_with_a_reason(fx, bad):
    errors = core.validate_case(fx, {**BASE, **bad['case']})
    assert any(bad['expect'] in e for e in errors), errors


def test_valid_base_is_valid(fx):
    assert core.validate_case(fx, BASE) == []


def test_player_view_never_leaks_hindsight(fx):
    for c in FIXTURES['cases']:
        view = json.dumps(core.player_view(core.get_case(fx, c['id'])))
        assert 'HINDSIGHT_MARKER' not in view
        assert 'evidence' not in view and 'full_record' not in view and 'concepts' not in view
        assert '"verdict"' not in view


def test_grading_uses_only_grading_levels(fx):
    ev = core.get_case(fx, 'fx-pro-vs-coach')['evidence']
    assert grade(ev, 'A') is False            # COACH_GOLD bad beats PRO_LINE + HEURISTIC
    assert grade(ev, 'B') is True
    assert grade(core.get_case(fx, 'fx-log-partial')['evidence'], 'A') is None      # HEURISTIC never grades
    assert grade(core.get_case(fx, 'fx-coach-split')['evidence'], 'A') is None      # coaches disagree
    assert core.disputes(core.get_case(fx, 'fx-coach-split')['evidence']) == ['A']
    assert core.disputes(ev) == ['A']


def test_db_enforces_invariants_even_without_python_validation(fx):
    with pytest.raises(sqlite3.IntegrityError, match='FACT evidence requires'):
        fx.execute("INSERT INTO evidence (case_id, level, claim, created_at) VALUES ('fx-log-partial', 'FACT', 'x', '')")
    with pytest.raises(sqlite3.IntegrityError, match='CHECK'):
        fx.execute("INSERT INTO evidence (case_id, level, claim, choice, verdict, created_at) "
                   "VALUES ('fx-consensus', 'PRO_LINE', 'x', 'A', 'good', '')")
    with pytest.raises(sqlite3.IntegrityError, match='append-only'):
        fx.execute("UPDATE evidence SET claim = 'rewritten'")
    with pytest.raises(sqlite3.IntegrityError, match='append-only'):
        fx.execute("DELETE FROM evidence")
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        fx.execute("UPDATE raw_sources SET content = 'edited'")
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        fx.execute("DELETE FROM raw_sources")


def test_add_evidence_appends_and_keeps_disagreement(fx):
    before = core.get_case(fx, 'fx-consensus')['evidence']
    assert core.add_evidence(fx, 'fx-consensus', {'level': 'COACH_GOLD', 'choice': 'B', 'verdict': 'bad',
                                                  'reviewer': 'Coach Three', 'claim': 'disagree'}) == []
    after = core.get_case(fx, 'fx-consensus')['evidence']
    assert after[:len(before)] == before and len(after) == len(before) + 1
    assert core.disputes(after) == ['B'] and grade(after, 'B') is None
    assert core.add_evidence(fx, 'fx-log-partial', {'level': 'FACT', 'claim': 'x'})  # low reconstruction refused


def test_deck_versions_hash_and_immutability(conn):
    cards = core.parse_deck('Pokémon: 2\n3 Dragapult ex TWM 130\n57 Basic Psychic Energy SVE 5\n')
    assert cards == [[3, 'Dragapult ex', 'TWM', '130'], [57, 'Basic Psychic Energy', 'SVE', '5']]
    h1 = core.add_deck(conn, 'dragapult', cards, 'test')
    assert core.add_deck(conn, 'dragapult', list(reversed(cards)), 'test') == h1          # order-independent
    h2 = core.add_deck(conn, 'dragapult', [[2, 'Dragapult ex', 'TWM', '130'], [58, 'Basic Psychic Energy', 'SVE', '5']], 't')
    assert h2 != h1 and core.current_deck(conn)['version'] == 2
    with pytest.raises(ValueError, match='60'):
        core.add_deck(conn, 'dragapult', [[59, 'Basic Psychic Energy', 'SVE', '5']], 't')
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE deck_versions SET source = 'x'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute('DELETE FROM deck_versions')


def test_seed_loads_and_every_seed_case_is_synthetic(seeded):
    cases = seeded.execute('SELECT id, synthetic FROM decision_cases').fetchall()
    assert len(cases) >= 5 and all(r['synthetic'] for r in cases)
    assert not seeded.execute("SELECT 1 FROM evidence WHERE level IN ('COACH_GOLD', 'CONSENSUS', 'PRO_LINE')").fetchone()
    assert core.load_seed(seeded) is False    # idempotent


def test_default_db_path_is_isolated_in_tests():
    import os
    assert str(db.default_path()).startswith(os.environ['XDG_DATA_HOME']) or 'never-used' in str(db.default_path())
    assert '.local/share' not in str(db.default_path())
