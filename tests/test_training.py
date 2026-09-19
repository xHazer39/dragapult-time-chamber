"""Gates B, D, E: one rep end to end, FSRS state, scheduler determinism, honest metrics."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from conftest import load_fixtures

from chamber import core, scheduler, stats, train
from chamber.train import Refused

NOW = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)


def rep(conn, case_id, choice=None, recall=3, outcome=None, session=None, other='', plan=None):
    case = core.get_case(conn, case_id)
    plan = plan or {f: 'x' for f in case['requires']}
    aid = train.start_attempt(conn, case_id, session, plan)
    r = train.answer(conn, aid, choice, other)
    train.review(conn, aid, {k['id']: recall for k in case['concepts']}, outcome, when=NOW)
    return aid, r


def test_plan_must_be_committed_and_is_locked(seeded):
    with pytest.raises(Refused, match='commit your plan'):
        train.start_attempt(seeded, 'demo-dive-setup', None, {'objective': 'win'})
    aid = train.start_attempt(seeded, 'demo-dive-setup', None, {'objective': 'o', 'prize_map': 'p', 'opponent_plan': 'q'})
    with pytest.raises(Refused, match='answer first'):
        train.reveal(seeded, aid)
    train.answer(seeded, aid, 'A')
    with pytest.raises(Refused, match='cannot be changed'):
        train.answer(seeded, aid, 'B')


def test_graded_fact_case_and_fsrs_update(seeded):
    aid, r = rep(seeded, 'demo-dive-count', 'A', recall=1)
    assert r['graded'] and r['attempt']['correct'] == 0 and r['attempt']['outcome'] == 'error'
    card = seeded.execute("SELECT fsrs_card FROM concepts WHERE id = 'phantom_dive_counter_math'").fetchone()[0]
    assert json.loads(card)['last_review'] is not None
    log = seeded.execute('SELECT rating, log FROM concept_reviews').fetchone()
    assert log['rating'] == 1 and json.loads(log['log'])['rating'] == 1
    with pytest.raises(Refused, match='already reviewed'):
        train.review(seeded, aid, {'phantom_dive_counter_math': 3})


def test_heuristic_case_is_never_graded_but_self_outcome_is_recorded(seeded):
    _, r = rep(seeded, 'demo-ultra-discard', 'D', outcome='error')
    assert r['graded'] is False and r['attempt']['correct'] is None
    a = seeded.execute('SELECT outcome, outcome_source FROM attempts').fetchone()
    assert tuple(a) == ('error', 'self')


def test_self_outcome_never_overrides_graded_evidence(seeded):
    rep(seeded, 'demo-dive-count', 'B', outcome='error')
    assert tuple(seeded.execute('SELECT outcome, outcome_source FROM attempts').fetchone()) == ('ok', 'evidence')


def test_hint_caps_rating_and_retries_do_not_touch_fsrs(seeded):
    sid = train.start_session(seeded, [{'case_id': 'demo-dive-count'}])
    aid = train.start_attempt(seeded, 'demo-dive-count', sid, {'objective': 'x'})
    train.use_hint(seeded, aid)
    train.answer(seeded, aid, 'B')
    train.review(seeded, aid, {'phantom_dive_counter_math': 4}, when=NOW)
    assert seeded.execute('SELECT rating FROM concept_reviews').fetchone()[0] == 2
    aid2 = train.start_attempt(seeded, 'demo-dive-count', sid, {'objective': 'x'})
    a2 = seeded.execute('SELECT retries, transfer_level, seen_before FROM attempts WHERE id = ?', (aid2,)).fetchone()
    assert tuple(a2) == (1, 'L0', 1)
    train.answer(seeded, aid2, 'B')
    train.review(seeded, aid2, {'phantom_dive_counter_math': 4}, when=NOW)
    assert seeded.execute('SELECT COUNT(*) FROM concept_reviews').fetchone()[0] == 1


def test_fsrs_card_round_trip_and_memory_is_not_skill(seeded):
    train.fsrs_review(seeded, 'resource_preservation', 3, when=NOW)
    m = train.memory(seeded.execute("SELECT fsrs_card FROM concepts WHERE id = 'resource_preservation'").fetchone()[0],
                     NOW + timedelta(days=1))
    assert m['reviewed'] and 0 < m['retrievability'] <= 1 and set(m) == {'reviewed', 'due', 'due_at', 'retrievability'}


def test_session_walks_plan_then_ends(seeded):
    items = scheduler.plan(seeded, NOW)
    sid = train.start_session(seeded, items)
    seen = []
    while (n := train.next_item(seeded, sid)):
        seen.append(n['case']['id'])
        assert 'concept_id' not in n['item']
        assert 'evidence' not in n['case'] and 'full_record' not in n['case'] and 'hint' not in n['case']
        rep(seeded, n['case']['id'], (n['case']['choices'] or [{'key': None}])[0]['key'], session=sid)
    assert seen == [i['case_id'] for i in items]
    assert json.loads(seeded.execute('SELECT summary FROM sessions').fetchone()[0])['reps'] == len(items)


# ------------------------------------------------------------------ scheduler (Gate D)

def test_mode_sequence_is_deterministic_and_proportional():
    seq = scheduler.mode_sequence(10, {'exploit': .5, 'coverage': .3, 'probe': .2})
    assert seq == scheduler.mode_sequence(10, {'exploit': .5, 'coverage': .3, 'probe': .2})
    assert (seq.count('exploit'), seq.count('coverage'), seq.count('probe')) == (5, 3, 2)


def test_plan_is_reproducible_and_explained(fx):
    a, b = scheduler.plan(fx, NOW), scheduler.plan(fx, NOW)
    assert a == b and a and all(i['reason'] and i['mode'] in ('exploit', 'coverage', 'probe') for i in a)
    assert 'fx-manual-setup' not in [i['case_id'] for i in a]          # criticality 1 is ignored
    assert len({i['case_id'] for i in a}) == len(a)


def test_seed_changes_probe_order_only_via_config(fx):
    cfg = {**scheduler.CONFIG, 'mix': {'probe': 1.0}, 'reps': 3}
    assert scheduler.plan(fx, NOW, cfg) == scheduler.plan(fx, NOW, cfg)
    assert all(i['mode'] == 'probe' for i in scheduler.plan(fx, NOW, cfg))


def test_exploit_targets_a_recorded_leak_and_prefers_unseen_cases(seeded):
    rep(seeded, 'demo-dive-count', 'A')      # error on phantom_dive_counter_math
    items = scheduler.plan(seeded, NOW)
    first = items[0]
    assert first['mode'] == 'exploit' and first['concept_id'] == 'phantom_dive_counter_math'
    assert first['case_id'] == 'demo-dive-count-2' and 'errors' in first['reason']
    assert {'coverage', 'probe'} & {i['mode'] for i in items}          # not only the leak: no filter bubble


def test_go_play_recommendation_when_drills_strong_and_no_real_games(seeded):
    assert scheduler.today(seeded, NOW)['play']['play'] is False
    for _ in range(5):
        seeded.execute("INSERT INTO attempts (created_at, answered_at, transfer_level, outcome, outcome_source) "
                       "VALUES (?, ?, 'L2', 'ok', 'evidence')", (NOW.isoformat(), NOW.isoformat()))
    rec = scheduler.today(seeded, NOW)['play']
    assert rec['play'] is True and '5/5' in rec['reason']
    train.log_real(seeded, ['resource_preservation'], 'ok')
    assert scheduler.play_recommendation(seeded, datetime.now(timezone.utc))['play'] is False


def test_retired_and_low_criticality_cases_are_never_scheduled(fx):
    fx.execute("UPDATE decision_cases SET status = 'retired' WHERE id = 'fx-consensus'")
    ids = [i['case_id'] for i in scheduler.plan(fx, NOW, {**scheduler.CONFIG, 'reps': 20})]
    assert 'fx-consensus' not in ids and 'fx-manual-setup' not in ids


# ------------------------------------------------------------------ progress (Gate E)

def test_progress_separates_seen_unseen_real_and_repeat_errors(seeded):
    rep(seeded, 'demo-dive-count', 'A')                          # unseen error (first error)
    rep(seeded, 'demo-dive-count', 'B')                          # same case again: L0 seen, ok
    rep(seeded, 'demo-dive-count-2', 'A')                        # unseen, repeat error
    train.log_real(seeded, ['phantom_dive_counter_math'], 'error', error_tags=['no_explicit_count'])
    s = {x['id']: x for x in stats.concept_stats(seeded, NOW)}['phantom_dive_counter_math']
    assert s['tiers']['unseen'] == {'ok': 0, 'error': 2, 'undefined': 0}
    assert s['tiers']['seen'] == {'ok': 1, 'error': 0, 'undefined': 0}
    assert s['tiers']['real'] == {'ok': 0, 'error': 1, 'undefined': 0}
    assert s['repeat']['unseen'] == {'later': 1, 'errors': 1} and s['repeat']['real'] == {'later': 1, 'errors': 1}
    assert s['status'] == 'repeat error in real games'
    p = stats.progress(seeded, NOW)
    assert ('no_explicit_count', 1) in p['error_tags']
    assert 'mastery' not in json.dumps(p).lower() and '%' not in json.dumps(p)


def test_no_data_means_insufficient_evidence(seeded):
    assert {s['status'] for s in stats.concept_stats(seeded, NOW)} == {'insufficient evidence'}


def test_memory_alone_never_claims_transfer(seeded):
    for _ in range(3):
        train.fsrs_review(seeded, 'phantom_dive_counter_math', 4, when=NOW)
    rep(seeded, 'demo-dive-count', 'B')
    rep(seeded, 'demo-dive-count', 'B')           # L0 success again
    s = {x['id']: x for x in stats.concept_stats(seeded, NOW)}['phantom_dive_counter_math']
    assert s['status'] in ('insufficient evidence', 'known, not yet shown on unseen positions')
