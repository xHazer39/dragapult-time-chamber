import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Before anything imports chamber: every default path points into a throwaway directory.
_TMP = tempfile.mkdtemp(prefix='chamber-tests-')
os.environ['CHAMBER_DB'] = os.path.join(_TMP, 'never-used.db')
os.environ['XDG_DATA_HOME'] = _TMP
os.environ.pop('OPENROUTER_API_KEY', None)
os.environ.pop('CHAMBER_COACH', None)
sys.path.insert(0, str(Path(__file__).parent.parent))

from chamber import core, db  # noqa: E402

FIXTURES = json.loads((Path(__file__).parent / 'fixtures' / 'cases.json').read_text())


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / 'test.db')
    yield c
    c.close()


@pytest.fixture
def seeded(conn):
    core.load_seed(conn)
    return conn


def load_fixtures(conn):
    for k in FIXTURES['concepts']:
        core.add_concept(conn, k['id'], k['name'], k['definition'], k['skill'])
    src = {key: core.add_source(conn, s['source_type'], s.get('content', ''), s.get('url', ''), s.get('metadata'))
           for key, s in FIXTURES['sources'].items()}
    for c in FIXTURES['cases']:
        c = {**c, 'source_id': src.get(c.get('source'))}
        errors = core.validate_case(conn, c)
        assert not errors, (c['id'], errors)
        core.insert_case(conn, c)
    return src


@pytest.fixture
def fx(conn):
    load_fixtures(conn)
    return conn


@pytest.fixture
def server(tmp_path):
    """A live app on a random port with its own DB. Yields (base_url, db_path)."""
    import threading
    from chamber.server import make_server
    path = tmp_path / 'app.db'
    srv = make_server(path, port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{srv.server_address[1]}', path
    srv.shutdown()
    srv.server_close()


def call(base, method, path, body=None):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(base + path, json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


from test_api import fake_llm  # noqa: E402,F401  (shared by the browser tests)
