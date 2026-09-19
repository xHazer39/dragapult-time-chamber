"""Competitive-performance evidence per concept.

Verified outcomes and self-reports are deliberately separated. A self-reported error is a
useful weak signal for discovering a leak; a self-reported success is not allowed to certify
transfer or close a leak.
"""
import json
from statistics import median

from .train import memory

TIER = {'L0': 'seen', 'L1': 'seen', 'L2': 'unseen', 'L3': 'unseen', 'L4': 'real'}
MIN_UNSEEN, MIN_REAL, MIN_LATER = 3, 2, 3


def opportunities(conn):
    """Answered attempts per concept, oldest first, with per-concept error attribution."""
    rows = conn.execute(
        'SELECT ac.concept_id, ac.error_relevant, a.id, a.created_at, a.transfer_level, a.outcome, '
        'a.outcome_source, a.latency_ms, a.retries, a.case_id '
        'FROM attempts a JOIN attempt_concepts ac ON ac.attempt_id = a.id '
        'WHERE a.answered_at IS NOT NULL ORDER BY a.created_at, a.id').fetchall()
    out = {}
    for r in rows:
        d = dict(r)
        d['effective'] = effective_outcome(d)
        out.setdefault(r['concept_id'], []).append(d)
    return out


def effective_outcome(o):
    """Return verified ok/error, weak self_ok/self_error, or None for this concept.

    An error on a multi-concept case is ignored for concepts that were not explicitly
    attributed as causal. This avoids poisoning several concept histories with one mistake.
    """
    if not o['outcome']:
        return None
    if o['outcome'] == 'error' and o['error_relevant'] != 1:
        return None
    if o['outcome_source'] == 'evidence':
        return o['outcome']
    if o['outcome_source'] == 'self':
        return f"self_{o['outcome']}"
    return None


def _repeat(defined):
    first_err = next((i for i, o in enumerate(defined) if o['effective'] == 'error'), None)
    repeat = {t: {'later': 0, 'errors': 0} for t in ('seen', 'unseen', 'real')}
    if first_err is not None:
        for o in defined[first_err + 1:]:
            r = repeat[TIER[o['transfer_level']]]
            r['later'] += 1
            r['errors'] += o['effective'] == 'error'
    return repeat


def concept_stats(conn, when):
    opps = opportunities(conn)
    result = []
    for c in conn.execute("SELECT * FROM concepts WHERE status = 'active' ORDER BY id"):
        ops = opps.get(c['id'], [])
        tiers = {t: {'ok': 0, 'error': 0, 'self_ok': 0, 'self_error': 0, 'undefined': 0}
                 for t in ('seen', 'unseen', 'real')}
        for o in ops:
            tiers[TIER[o['transfer_level']]][o['effective'] or 'undefined'] += 1

        verified = [o for o in ops if o['effective'] in ('ok', 'error') and o['retries'] == 0]
        self_reported = [o for o in ops if o['effective'] in ('self_ok', 'self_error') and o['retries'] == 0]
        repeat = _repeat(verified)
        recent_verified = verified[-5:]
        recent_self = self_reported[-5:]
        lat = [o['latency_ms'] for o in ops if o['latency_ms'] is not None and o['retries'] == 0]
        s = {
            'id': c['id'], 'name': c['name'], 'skill': c['skill'], 'definition': c['definition'],
            'memory': memory(c['fsrs_card'], when), 'tiers': tiers, 'repeat': repeat,
            'recent': {
                'n': len(recent_verified),
                'errors': sum(o['effective'] == 'error' for o in recent_verified),
                'self_n': len(recent_self),
                'self_errors': sum(o['effective'] == 'self_error' for o in recent_self),
            },
            'latency': {'median_s': round(median(lat) / 1000, 1) if lat else None, 'n': len(lat)},
            'last_at': ops[-1]['created_at'] if ops else None,
            'opportunities': len(ops),
        }
        s['status'] = status(s)
        result.append(s)
    return result


def status(s):
    """One honest label. Self-report can flag a possible leak, never certify transfer."""
    t, rep, mem = s['tiers'], s['repeat'], s['memory']
    unseen_n = t['unseen']['ok'] + t['unseen']['error']
    real_n = t['real']['ok'] + t['real']['error']
    if rep['real']['errors']:
        return 'repeat error in real games (verified)'
    if s['recent']['errors']:
        return 'active leak (verified)'
    if s['recent']['self_errors'] or t['real']['self_error']:
        return 'possible leak (self-reported)'
    if unseen_n < MIN_UNSEEN and real_n < MIN_REAL:
        if mem['reviewed'] and (mem['retrievability'] or 0) >= 0.8 and t['seen']['ok']:
            return 'known, not yet shown on unseen positions'
        return 'insufficient verified evidence'
    if t['unseen']['ok'] / max(unseen_n, 1) < 0.7:
        return 'known, not transferring to unseen positions'
    if real_n < MIN_REAL:
        return 'transfers in drills; needs verified real-game evidence'
    return 'no current verified evidence of a leak'


def progress(conn, when):
    stats = concept_stats(conn, when)
    keys = ('ok', 'error', 'self_ok', 'self_error', 'undefined')
    total = {t: {k: sum(s['tiers'][t][k] for s in stats) for k in keys} for t in ('seen', 'unseen', 'real')}
    tags = {}
    for (raw,) in conn.execute("SELECT error_tags FROM attempts WHERE error_tags <> '[]' ORDER BY created_at"):
        for t in json.loads(raw):
            tags[t] = tags.get(t, 0) + 1
    return {
        'concepts': stats,
        'totals': total,
        'error_tags': sorted(tags.items(), key=lambda kv: -kv[1]),
        'thresholds': {'unseen': MIN_UNSEEN, 'real': MIN_REAL, 'later': MIN_LATER},
    }
