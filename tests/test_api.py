"""HTTP API, Inbox pipeline (Gate C), coach degradation (Gate F), privacy."""
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from conftest import call  # noqa: F401

from chamber import coach

LOG = """Setup
Rival99 drew 7 cards.
Turn # 1 - me's Turn
me played Dreepy to the Bench.
Turn # 2 - Rival99's Turn
Rival99 played Boss's Orders.
Rival99's Pokémon used an attack."""


def test_rep_over_http_never_leaks_before_answer(server):
    base, _ = server
    st, s = call(base, 'POST', '/api/sessions', {})
    assert st == 200 and s['plan']
    st, n = call(base, 'GET', f"/api/sessions/{s['session_id']}/next")
    view = json.dumps(n['case'])
    assert 'evidence' not in view and 'claim' not in view and 'full_record' not in view and 'hint' not in view
    st, c = call(base, 'GET', f"/api/cases/{n['case']['id']}")
    assert 'evidence' not in c['case']
    st, e = call(base, 'POST', '/api/attempts', {'case_id': n['case']['id'], 'session_id': s['session_id'], 'plan': {}})
    if n['case']['requires']:
        assert st == 400 and 'commit your plan' in e['error']
    plan = {f: 'my plan' for f in n['case']['requires']}
    st, a = call(base, 'POST', '/api/attempts', {'case_id': n['case']['id'], 'session_id': s['session_id'], 'plan': plan})
    st, r = call(base, 'POST', f"/api/attempts/{a['attempt_id']}/answer", {'choice': n['case']['choices'][0]['key']})
    assert st == 200 and r['case']['evidence'] and r['attempt']['plan'] == plan


def test_inbox_log_to_decision_case(server):
    base, path = server
    st, s = call(base, 'POST', '/api/sources', {'source_type': 'ptcgl_log', 'content': LOG, 'opponent_name': 'Rival99',
                                                 'matchup': 'vs Gardevoir'})
    sid = s['source_id']
    st, src = call(base, 'GET', f'/api/sources/{sid}')
    assert [g['title'] for g in src['timeline']] == ['Setup', "Turn # 1 - me's Turn", "Turn # 2 - Rival99's Turn"]
    st, c = call(base, 'POST', '/api/candidates', {'source_id': sid, 'excerpt': LOG.split('\n', 5)[5]})
    cid = c['candidate_id']
    st, cand = call(base, 'GET', f'/api/candidates/{cid}')
    assert 'Rival99' not in cand['data']['full_record'] and 'OPPONENT' in cand['data']['full_record']
    assert cand['data']['reconstruction'] == 'unknown'
    st, p = call(base, 'POST', f'/api/candidates/{cid}/promote')
    assert p['case_id'] is None and p['errors']              # empty draft cannot become training data
    data = {**cand['data'], 'id': 'real-turn2-boss', 'prompt': 'Bench Dreepy or hold it?',
            'observed_state': 'Turn 1, my board: Active Budew. Hand: Dreepy, Poffin.', 'criticality': 3,
            'criticality_source': 'me after review', 'decision_family': 'bench', 'reconstruction': 'medium',
            'choices': [{'key': 'A', 'text': 'Bench it'}, {'key': 'B', 'text': 'Hold it'}], 'completeness': 'PARTIAL',
            'concepts': ['two_prize_bench_liability'],
            'evidence': [{'level': 'FACT', 'claim': 'Opponent used Boss next turn'}]}
    call(base, 'PUT', f'/api/candidates/{cid}', {'data': data})
    st, p = call(base, 'POST', f'/api/candidates/{cid}/promote')
    assert any('FACT needs exact/high' in e for e in p['errors'])       # low-confidence log cannot be FACT
    data['evidence'] = [{'level': 'HEURISTIC', 'choice': 'B', 'verdict': 'good', 'claim': 'Fewer targets.'},
                        {'level': 'UNKNOWN', 'claim': 'Opponent hand at the time.'}]
    call(base, 'PUT', f'/api/candidates/{cid}', {'data': data})
    st, p = call(base, 'POST', f'/api/candidates/{cid}/promote')
    assert p == {'case_id': 'real-turn2-boss', 'errors': []}
    st, e = call(base, 'PUT', f'/api/candidates/{cid}', {'data': data})
    assert st == 400                                                    # promoted drafts are frozen
    conn = sqlite3.connect(path)
    assert conn.execute('SELECT content FROM raw_sources WHERE id = ?', (sid,)).fetchone()[0] == LOG
    assert conn.execute("SELECT source_id FROM decision_cases WHERE id = 'real-turn2-boss'").fetchone()[0] == sid
    assert conn.execute("SELECT synthetic FROM decision_cases WHERE id = 'real-turn2-boss'").fetchone()[0] == 0


def test_source_needs_content_and_valid_type(server):
    base, _ = server
    assert call(base, 'POST', '/api/sources', {'source_type': 'ptcgl_log'})[0] == 400
    assert call(base, 'POST', '/api/sources', {'source_type': 'scrape', 'content': 'x'})[0] == 400


def test_meta_never_exposes_the_api_key(server, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-secret-123')
    monkeypatch.setenv('CHAMBER_COACH', '1')
    base, _ = server
    st, m = call(base, 'GET', '/api/meta')
    assert 'sk-secret' not in json.dumps(m) and m['coach']['enabled'] is True


def test_static_and_path_traversal(server):
    import urllib.request
    base, _ = server
    assert b'Dragapult Time Chamber' in urllib.request.urlopen(base + '/').read()
    assert call(base, 'GET', '/../chamber/db.py')[0] == 404


# ------------------------------------------------------------------ coach (Gate F)

class FakeLLM(BaseHTTPRequestHandler):
    reply = ''
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        FakeLLM.seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        body = json.dumps({'choices': [{'message': {'content': FakeLLM.reply}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_llm(monkeypatch):
    srv = HTTPServer(('127.0.0.1', 0), FakeLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv('CHAMBER_COACH', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    monkeypatch.setenv('CHAMBER_COACH_URL', f'http://127.0.0.1:{srv.server_address[1]}')
    FakeLLM.seen.clear()
    yield FakeLLM
    srv.shutdown()


GOOD = json.dumps({'main_concept': 'Phantom Dive counter math', 'explanation': 'The FACT items count the KOs.',
                   'mental_model': 'Counters needed = HP / 10.', 'socratic_question': 'Which target needs fewest?',
                   'next_focus': 'Write the count first.', 'new_claims': ['Always spread counters.']})


def answered(base):
    st, a = call(base, 'POST', '/api/attempts', {'case_id': 'demo-dive-count', 'plan': {'objective': 'max prizes'}})
    call(base, 'POST', f"/api/attempts/{a['attempt_id']}/answer", {'choice': 'A'})
    return a['attempt_id']


def test_coach_disabled_without_key(server):
    base, _ = server
    st, r = call(base, 'POST', f'/api/attempts/{answered(base)}/coach')
    assert st == 200 and r['available'] is False and 'disabled' in r['reason']


def test_coach_offline_degrades(server, monkeypatch):
    monkeypatch.setenv('CHAMBER_COACH', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'k')
    monkeypatch.setenv('CHAMBER_COACH_URL', 'http://127.0.0.1:9')
    base, _ = server
    st, r = call(base, 'POST', f'/api/attempts/{answered(base)}/coach')
    assert st == 200 and r['available'] is False and 'offline' in r['reason']


@pytest.mark.parametrize('bad', ['not json', '{"main_concept": "x"}', json.dumps({**json.loads(GOOD), 'new_claims': 'x'}), '[]'])
def test_coach_malformed_is_ignored(server, fake_llm, bad):
    fake_llm.reply = bad
    base, path = server
    aid = answered(base)
    st, r = call(base, 'POST', f'/api/attempts/{aid}/coach')
    assert r['available'] is False and 'malformed' in r['reason']
    assert sqlite3.connect(path).execute('SELECT coach FROM attempts WHERE id = ?', (aid,)).fetchone()[0] is None


def test_coach_claims_never_become_evidence(server, fake_llm):
    fake_llm.reply = '```json\n' + GOOD + '\n```'
    base, path = server
    conn = sqlite3.connect(path)
    before = conn.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]
    aid = answered(base)
    st, r = call(base, 'POST', f'/api/attempts/{aid}/coach')
    assert r['available'] and r['new_claims'] == ['Always spread counters.'] and 'not evidence' in r['trust']
    assert r['off_concept'] is False
    assert conn.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == before
    sent = fake_llm.seen[0]
    assert sent['model'] == 'z-ai/glm-5.3-flash'
    user = json.loads(sent['messages'][1]['content'])
    assert set(user) >= {'position', 'evidence', 'player_plan'} and 'full_record' not in user


def test_coach_parse_strictness():
    assert coach.parse(GOOD)['main_concept'] == 'Phantom Dive counter math'
    with pytest.raises(ValueError):
        coach.parse(json.dumps({**json.loads(GOOD), 'explanation': ''}))
