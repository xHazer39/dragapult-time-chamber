"""Optional GLM coach via OpenRouter. Explains stored evidence; is never evidence itself.

Enabled only when CHAMBER_COACH=1 and OPENROUTER_API_KEY is set. Any failure returns
{'available': False, 'reason': ...} and the app carries on without it.
"""
import json
import os
import urllib.error
import urllib.request

KEYS = ('main_concept', 'explanation', 'mental_model', 'socratic_question', 'next_focus')
SYSTEM = """You are a Pokémon TCG coach helping one player with one Dragapult ex decision.
You receive the position the player saw, their locked plan and choice, and an evidence ledger.
Rules:
- Explain ONLY what the evidence ledger supports. Keep each evidence item's level (FACT, COACH_GOLD, CONSENSUS,
  PRO_LINE, SIMULATION, HEURISTIC, UNKNOWN). PRO_LINE means a strong player chose it, not that it is best.
- Never state a best move, a legal move, or hidden information as fact unless a FACT/COACH_GOLD/CONSENSUS item says so.
- Never fill UNKNOWN items. If evidence disagrees, say so and do not resolve it.
- Any strategic idea that is not in the ledger goes ONLY into "new_claims", as a short sentence.
Reply with one JSON object and nothing else:
{"main_concept": str, "explanation": str, "mental_model": str, "socratic_question": str, "next_focus": str,
 "new_claims": [str]}"""


def config():
    return {'enabled': os.environ.get('CHAMBER_COACH') == '1' and bool(os.environ.get('OPENROUTER_API_KEY')),
            'model': os.environ.get('CHAMBER_COACH_MODEL', 'z-ai/glm-5.3-flash'),
            'url': os.environ.get('CHAMBER_COACH_URL', 'https://openrouter.ai/api/v1').rstrip('/') + '/chat/completions'}


def context(reveal) -> dict:
    """Compact structured input. No raw logs, no full record, no opponent identifiers."""
    a, c = reveal['attempt'], reveal['case']
    return {'position': c['observed_state'][:2000], 'unknown': c['unknown_fields'], 'prompt': c['prompt'],
            'choices': c['choices'], 'choices_completeness': c['completeness'], 'player_plan': a['plan'],
            'player_choice': a['choice'] or a['other_text'][:500], 'player_reasoning': a['reasoning'][:500],
            'concepts': [{'name': k['name'], 'definition': k['definition']} for k in c['concepts']],
            'evidence': [{'level': x['level'], 'choice': x['choice'], 'verdict': x['verdict'], 'claim': x['claim']}
                         for x in a['feedback_evidence']],
            'evidence_disagrees_on': reveal['disputes']}


def parse(text: str) -> dict:
    """Strict: every key present, strings where strings belong. Raises ValueError otherwise."""
    text = text.strip()
    if text.startswith('```'):
        text = text.strip('`').removeprefix('json').strip()
    out = json.loads(text)
    if not isinstance(out, dict) or any(not isinstance(out.get(k), str) or not out[k].strip() for k in KEYS):
        raise ValueError('missing or non-string fields')
    claims = out.get('new_claims', [])
    if not isinstance(claims, list) or any(not isinstance(x, str) for x in claims):
        raise ValueError('new_claims must be a list of strings')
    return {**{k: out[k].strip() for k in KEYS}, 'new_claims': claims}


def ask(reveal, timeout=30) -> dict:
    cfg = config()
    if not cfg['enabled']:
        return {'available': False, 'reason': 'Coach disabled (set CHAMBER_COACH=1 and OPENROUTER_API_KEY).'}
    body = json.dumps({'model': cfg['model'], 'temperature': 0.2, 'response_format': {'type': 'json_object'},
                       'messages': [{'role': 'system', 'content': SYSTEM},
                                    {'role': 'user', 'content': json.dumps(context(reveal), ensure_ascii=False)}]})
    req = urllib.request.Request(cfg['url'], body.encode(), {
        'Authorization': f"Bearer {os.environ['OPENROUTER_API_KEY']}", 'Content-Type': 'application/json',
        'X-Title': 'Dragapult Time Chamber'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = json.loads(r.read())['choices'][0]['message']['content']
        result = parse(content)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {'available': False, 'reason': f'Coach offline: {type(e).__name__}'}
    except (ValueError, KeyError, IndexError, TypeError):
        return {'available': False, 'reason': 'Coach reply was malformed; ignored.'}
    names = {k['name'].lower() for k in reveal['case']['concepts']} | {k['id'] for k in reveal['case']['concepts']}
    return {'available': True, 'model': cfg['model'], **result,
            'off_concept': result['main_concept'].lower() not in names,
            'trust': 'LLM output: not evidence. new_claims are unverified HEURISTIC candidates.'}
