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


def test_foundations_import_is_idempotent_and_grades_only_the_fact_cases(tmp_path):
    import sys as _sys
    _sys.path.insert(0, str(ROOT / 'corpus'))
    import import_foundations
    from chamber import core, db, train

    path = tmp_path / 'import.db'
    for _ in range(2):                                    # twice: the second run must add nothing
        _sys.argv = ['import_foundations', '--db', str(path)]
        assert import_foundations.main() == 0
    conn = db.connect(path)
    cases = [json.loads(x) for x in (ROOT / 'corpus' / 'foundations' / 'decision_cases.jsonl').read_text().splitlines()]
    assert len(cases) == 12
    for c in cases:
        got = core.get_case(conn, c['id'])
        assert got, c['id']
        assert c['primary_concept'] in [k['id'] for k in got['concepts']]
        graded = {ch['key']: train.grade(got['evidence'], ch['key']) for ch in got['choices']}
        if got['synthetic']:
            assert all(v is not None for v in graded.values()), c['id']          # constructed: FACT decides
        else:
            assert all(v is None for v in graded.values()), c['id']              # pro line: never grades
    # no duplicate cases, and the six foundation concepts are all there
    assert conn.execute("SELECT COUNT(*) FROM decision_cases WHERE id LIKE 'found-%'").fetchone()[0] == 12
    conn.close()
