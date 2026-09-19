"""Local JSON API + static files. stdlib only; one SQLite connection per request."""
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import coach, core, db, scheduler, stats, train
from .train import Refused

STATIC = Path(__file__).with_name('static')
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8'}
MAX_BODY = 2_000_000
ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile(f'^{pattern}$'), fn))
        return fn
    return deco


def utcnow():
    return datetime.now(timezone.utc)


def _public_today(data):
    """Today is neutral: how much to train, never what it targets.

    Before the decision the player must not learn that a rep is an exploit rep, which leak it is
    about or which concept is hidden. Scheduler mode and reason appear only after the reveal; leak
    detail lives in Progress.
    """
    return {
        **{k: v for k, v in data.items() if k not in ('plan', 'leaks', 'due', 'config')},
        'reps': len(data['plan']),
        'due_count': len(data['due']),
    }


# --------------------------------------------------------------------------- training

@route('GET', '/api/today')
def get_today(conn, body):
    return _public_today(scheduler.today(conn, utcnow()))


@route('POST', '/api/sessions')
def post_session(conn, body):
    items = scheduler.plan(conn, utcnow())
    if not items:
        raise Refused('nothing to train right now')
    return {'session_id': train.start_session(conn, items), 'reps': len(items)}


@route('GET', r'/api/sessions/(\d+)/next')
def get_next(conn, body, sid):
    return train.next_item(conn, int(sid)) or {'done': True, 'today': _public_today(scheduler.today(conn, utcnow()))}


@route('GET', r'/api/cases/([a-z0-9_-]+)')
def get_case(conn, body, cid):
    c = core.get_case(conn, cid)
    if not c:
        raise Refused('unknown case')
    return {'case': core.player_view(c)}


@route('POST', '/api/attempts')
def post_attempt(conn, body):
    return {'attempt_id': train.start_attempt(conn, body.get('case_id'), body.get('session_id'), body.get('plan', {}))}


@route('POST', r'/api/attempts/(\d+)/hint')
def post_hint(conn, body, aid):
    return {'hint': train.use_hint(conn, int(aid))}


@route('POST', r'/api/attempts/(\d+)/answer')
def post_answer(conn, body, aid):
    result = train.answer(conn, int(aid), body.get('choice'), body.get('other_text', ''), body.get('reasoning', ''))
    result['coach_enabled'] = coach.config()['enabled']
    result['evidence_levels'] = db.LEVELS
    return result


@route('POST', r'/api/attempts/(\d+)/review')
def post_review(conn, body, aid):
    ratings = {k: int(v) for k, v in (body.get('ratings') or {}).items()}
    train.review(conn, int(aid), ratings, body.get('outcome') or None, body.get('error_tags', []),
                 body.get('note', ''), error_concepts=body.get('error_concepts', []))
    return {'ok': True}


@route('POST', r'/api/attempts/(\d+)/coach')
def post_coach(conn, body, aid):
    result = coach.ask(train.reveal(conn, int(aid)))
    if result['available']:
        train.save_coach(conn, int(aid), result)
    return result


@route('POST', '/api/real')
def post_real(conn, body):
    return {'attempt_id': train.log_real(conn, body.get('concepts', []), body.get('outcome') or None,
                                         body.get('note', ''), body.get('source_id'), body.get('error_tags', []),
                                         body.get('error_concepts', []))}


@route('GET', '/api/progress')
def get_progress(conn, body):
    return stats.progress(conn, utcnow())


# --------------------------------------------------------------------------- inbox

@route('GET', '/api/meta')
def get_meta(conn, body):
    return {'concepts': [dict(r) for r in conn.execute(
                "SELECT id, name, skill, definition FROM concepts WHERE status = 'active' ORDER BY id")],
            'skills': db.SKILLS, 'families': db.FAMILIES, 'levels': db.LEVELS, 'source_types': db.SOURCE_TYPES,
            'completeness': db.COMPLETENESS, 'reconstruction': db.RECONSTRUCTION, 'plan_fields': db.PLAN_FIELDS,
            'decks': [dict(r) for r in conn.execute(
                'SELECT hash, deck_id, version, source, format, date FROM deck_versions ORDER BY deck_id, version')],
            'coach': {k: v for k, v in coach.config().items() if k != 'url'}}


@route('GET', '/api/inbox')
def get_inbox(conn, body):
    return {'sources': [dict(r) for r in conn.execute(
                'SELECT id, source_type, url, matchup, created_at, substr(content, 1, 120) preview, sha256 '
                'FROM raw_sources ORDER BY id DESC')],
            'candidates': [dict(r) for r in conn.execute(
                "SELECT id, source_id, status, case_id, json_extract(data, '$.prompt') prompt, updated_at "
                'FROM candidate_cases ORDER BY id DESC')]}


@route('POST', '/api/sources')
def post_source(conn, body):
    meta = {'opponent_name': body['opponent_name']} if body.get('opponent_name') else {}
    return {'source_id': core.add_source(conn, body.get('source_type'), body.get('content', ''), body.get('url', ''),
                                         meta, body.get('deck_hash'), body.get('matchup', ''))}


@route('GET', r'/api/sources/(\d+)')
def get_source(conn, body, sid):
    s = core.get_source(conn, int(sid))
    if not s:
        raise Refused('unknown source')
    return s


@route('POST', '/api/candidates')
def post_candidate(conn, body):
    return {'candidate_id': core.create_candidate(conn, body.get('source_id'), body.get('excerpt', ''))}


@route('GET', r'/api/candidates/(\d+)')
def get_candidate(conn, body, cid):
    c = core.get_candidate(conn, int(cid))
    if not c:
        raise Refused('unknown candidate')
    return c


@route('PUT', r'/api/candidates/(\d+)')
def put_candidate(conn, body, cid):
    core.update_candidate(conn, int(cid), body['data'])
    return {'ok': True}


@route('POST', r'/api/candidates/(\d+)/promote')
def post_promote(conn, body, cid):
    case_id, errors = core.promote(conn, int(cid))
    return {'case_id': case_id, 'errors': errors}


@route('POST', '/api/concepts')
def post_concept(conn, body):
    core.add_concept(conn, body.get('id', ''), body.get('name', ''), body.get('definition', ''), body.get('skill'),
                     body.get('notes', ''))
    return {'ok': True}


@route('POST', r'/api/cases/([a-z0-9_-]+)/evidence')
def post_evidence(conn, body, cid):
    return {'errors': core.add_evidence(conn, cid, body)}


# --------------------------------------------------------------------------- plumbing

class Handler(BaseHTTPRequestHandler):
    db_path = None

    def log_message(self, *a):
        pass

    def send(self, status, payload, ctype='application/json; charset=utf-8'):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self, method):
        path = self.path.split('?')[0]
        if method == 'GET' and not path.startswith('/api/'):
            f = STATIC / ('index.html' if path == '/' else path.lstrip('/'))
            if f.resolve().parent == STATIC.resolve() and f.is_file():
                return self.send(200, f.read_bytes(), TYPES.get(f.suffix, 'application/octet-stream'))
            return self.send(404, {'error': 'not found'})
        for m, rx, fn in ROUTES:
            match = rx.match(path) if m == method else None
            if match:
                break
        else:
            return self.send(404, {'error': 'not found'})
        try:
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_BODY:
                return self.send(413, {'error': 'request too large'})
            body = json.loads(self.rfile.read(n) or b'{}') if n else {}
            conn = db.connect(self.db_path)
            try:
                return self.send(200, fn(conn, body, *match.groups()))
            finally:
                conn.close()
        except (Refused, ValueError, KeyError, TypeError) as e:
            return self.send(400, {'error': str(e)})
        except Exception as e:  # sqlite IntegrityError etc: an invariant said no
            return self.send(400 if 'Integrity' in type(e).__name__ else 500, {'error': str(e)})

    def do_GET(self):
        self.handle_any('GET')

    def do_POST(self):
        self.handle_any('POST')

    def do_PUT(self):
        self.handle_any('PUT')


def make_server(db_path, host='127.0.0.1', port=8765):
    conn = db.connect(db_path)
    core.load_seed(conn)
    conn.close()
    handler = type('BoundHandler', (Handler,), {'db_path': str(db_path)})
    return ThreadingHTTPServer((host, port), handler)
