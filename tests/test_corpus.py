"""The corpus integrity checker: it passes on the real corpus, and it is not vacuous."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / 'corpus' / 'check.py'


def run(corpus_dir=None):
    env = {'PATH': '/usr/bin:/bin', 'CORPUS_DIR': str(corpus_dir)} if corpus_dir else None
    return subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True, env=env)


def test_real_corpus_is_clean():
    r = run()
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_broken_reference_is_reported(tmp_path):
    copy = tmp_path / 'corpus'
    shutil.copytree(ROOT / 'corpus', copy)
    f = copy / 'extracted' / 'claims.jsonl'
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    rows[0]['id'] = 'claim_renamed_by_test'                       # a concept still points at the old id
    f.write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in rows) + '\n')
    (copy / 'facts' / 'rules.jsonl').write_text('{"id": "broken"\n')
    r = run(copy)
    assert r.returncode == 1
    assert 'does not exist' in r.stdout and 'malformed JSON' in r.stdout
