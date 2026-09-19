"""Competitive-performance evidence per concept. Counts with denominators, never a mastery score."""
import json
from statistics import median

from .train import memory

TIER = {'L0': 'seen', 'L1': 'seen', 'L2': 'unseen', 'L3': 'unseen', 'L4': 'real'}
MIN_UNSEEN, MIN_REAL, MIN_LATER = 3, 2, 3   # below these, say "insufficient evidence"


def opportunities(conn):
    """Answered attempts per concept, oldest first."""
    rows = conn.execute(
        'SELECT ac.concept_id, a.id, a.created_at, a.transfer_level, a.outcome, a.latency_ms, a.retries, a.case_id '
        'FROM attempts a JOIN attempt_concepts ac ON ac.attempt_id = a.id '
        'WHERE a.answered_at IS NOT NULL ORDER BY a.created_at, a.id').fetchall()
    out = {}
    for r in rows:
        out.setdefault(r['concept_id'], []).append(dict(r))
    return out


def concept_stats(conn, when):
    opps = opportunities(conn)
    result = []
    for c in conn.execute("SELECT * FROM concepts WHERE status = 'active' ORDER BY id"):
        ops = opps.get(c['id'], [])
        tiers = {t: {'ok': 0, 'error': 0, 'undefined': 0} for t in ('seen', 'unseen', 'real')}
        for o in ops:
            tiers[TIER[o['transfer_level']]][o['outcome'] or 'undefined'] += 1
        defined = [o for o in ops if o['outcome'] and o['retries'] == 0]   # a retry after the reveal proves nothing
        first_err = next((i for i, o in enumerate(defined) if o['outcome'] == 'error'), None)
        repeat = {t: {'later': 0, 'errors': 0} for t in tiers}
        if first_err is not None:
            for o in defined[first_err + 1:]:
                r = repeat[TIER[o['transfer_level']]]
                r['later'] += 1
                r['errors'] += o['outcome'] == 'error'
        recent = defined[-5:]
        lat = [o['latency_ms'] for o in ops if o['latency_ms'] is not None and o['retries'] == 0]
        s = {'id': c['id'], 'name': c['name'], 'skill': c['skill'], 'definition': c['definition'],
             'memory': memory(c['fsrs_card'], when), 'tiers': tiers, 'repeat': repeat,
             'recent': {'n': len(recent), 'errors': sum(o['outcome'] == 'error' for o in recent)},
             'latency': {'median_s': round(median(lat) / 1000, 1) if lat else None, 'n': len(lat)},
             'last_at': ops[-1]['created_at'] if ops else None, 'opportunities': len(ops)}
        s['status'] = status(s)
        result.append(s)
    return result


def status(s):
    """One honest label. Memory (FSRS) and performance are judged separately."""
    t, rep, mem = s['tiers'], s['repeat'], s['memory']
    unseen_n = t['unseen']['ok'] + t['unseen']['error']
    real_n = t['real']['ok'] + t['real']['error']
    if rep['real']['errors']:
        return 'repeat error in real games'
    if s['recent']['errors']:
        return 'active leak'
    if unseen_n < MIN_UNSEEN and real_n < MIN_REAL:
        if mem['reviewed'] and (mem['retrievability'] or 0) >= 0.8 and t['seen']['ok']:
            return 'known, not yet shown on unseen positions'
        return 'insufficient evidence'
    if t['unseen']['ok'] / max(unseen_n, 1) < 0.7:
        return 'known, not transferring to unseen positions'
    if real_n < MIN_REAL:
        return 'transfers in drills; needs real-game evidence'
    return 'no current evidence of a leak'


def progress(conn, when):
    stats = concept_stats(conn, when)
    total = {t: {'ok': sum(s['tiers'][t]['ok'] for s in stats), 'error': sum(s['tiers'][t]['error'] for s in stats),
                 'undefined': sum(s['tiers'][t]['undefined'] for s in stats)} for t in ('seen', 'unseen', 'real')}
    # Tags from real games and drills; the recurrence of a tag is the plainest repeat-error signal.
    tags = {}
    for (raw,) in conn.execute("SELECT error_tags FROM attempts WHERE error_tags <> '[]' ORDER BY created_at"):
        for t in json.loads(raw):
            tags[t] = tags.get(t, 0) + 1
    return {'concepts': stats, 'totals': total, 'error_tags': sorted(tags.items(), key=lambda kv: -kv[1]),
            'thresholds': {'unseen': MIN_UNSEEN, 'real': MIN_REAL, 'later': MIN_LATER}}
