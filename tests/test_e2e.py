"""Gate B/H: real browser end to end. No console errors allowed."""
import json

import pytest

pw = pytest.importorskip('playwright.sync_api')

LOG = "Setup\nRival99 drew 7 cards.\nTurn # 1 - me's Turn\nme played Dreepy to the Bench.\nTurn # 2 - Rival99's Turn\nRival99 played Boss's Orders."


@pytest.fixture
def page(server):
    base, _ = server
    with pw.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        errors = []
        pg.on('console', lambda m: m.type == 'error' and errors.append(m.text))
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.base = base
        yield pg
        browser.close()
        assert errors == [], errors


def do_rep(page, choice_index=0, recall='Good', outcome=None):
    """Plan -> lock -> answer -> reveal -> review, on whatever case is shown."""
    for ta in page.locator('textarea[id^="plan-"]').all():
        ta.fill('Take prizes without exposing my bench')
    page.click('#lock')
    page.wait_for_selector('#locked-plan')
    radios = page.locator('input[name="choice"]')
    if radios.count():
        radios.nth(choice_index).check()
    else:
        page.fill('#other', 'My own line')
    page.click('#submit')
    page.wait_for_selector('#ledger')
    for group in page.locator('[name^="recall-"]').evaluate_all('els => [...new Set(els.map(e => e.name))]'):
        page.locator(f'input[name="{group}"]').nth(['Again', 'Hard', 'Good', 'Easy'].index(recall)).check()
    if outcome and page.locator('input[name="self-outcome"]').count():
        page.check(f'input[name="self-outcome"][value="{outcome}"]')
    page.click('#save-review')
    page.wait_for_selector('#after:not([hidden])')


def test_demo_session_full_rep_and_next(page):
    page.goto(page.base + '/#today')
    page.wait_for_selector('#plan')
    assert 'SYNTHETIC' not in page.inner_text('#plan')
    page.click('#start')
    page.wait_for_selector('#position')
    assert 'SYNTHETIC DEMO' in page.inner_text('main')
    # plan must be locked before any reveal element exists
    assert page.locator('#ledger').count() == 0 and page.locator('input[name="choice"]').count() == 0
    first_prompt = page.inner_text('#prompt')
    do_rep(page)
    assert page.locator('#verdict').count() == 1
    assert 'Coach disabled' in page.inner_text('#coach-off')
    page.click('#next')
    page.wait_for_selector('#lock')
    assert page.inner_text('#prompt') != first_prompt


def test_error_becomes_a_leak_and_is_scheduled(page):
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=0, recall='Again')            # A is wrong per FACT
    assert 'Contradicted by graded evidence' in page.inner_text('#verdict')
    page.goto(page.base + '/#today')
    page.wait_for_selector('#plan')
    main = page.inner_text('main').lower()
    # Today must not prime: no mode, no leak, no concept, no scheduler reason.
    for word in ('exploit', 'coverage', 'probe', 'leak', 'phantom_dive', 'phantom dive counter math'):
        assert word not in main, word
    assert 'reps' in page.inner_text('#plan')
    page.click('#start')
    page.wait_for_selector('#position')
    assert 'Knocks Out the most Benched' in page.inner_text('#prompt')   # demo-dive-count-2: unseen, same concept


def test_conflicting_and_unknown_evidence_is_shown_not_resolved(page):
    page.goto(page.base + '/#case/demo-dive-setup')
    page.wait_for_selector('#lock')
    page.click('#lock')                                      # missing required plan fields
    assert 'commit your plan' in page.inner_text('[role=alert]')
    do_rep(page, choice_index=0, outcome='ok')
    assert 'Not graded' in page.inner_text('#verdict')
    assert 'disagrees on choice A' in page.inner_text('#disputes')
    ledger = page.inner_text('#ledger')
    assert 'UNKNOWN' in ledger and 'HEURISTIC' in ledger


def test_retry_is_seen_and_progress_separates_tiers_and_real_games(page):
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=1)                             # B correct, unseen L2
    page.click('#retry')
    do_rep(page, choice_index=1)
    assert 'retry #1' in page.inner_text('#reveal')
    page.goto(page.base + '/#progress')
    page.wait_for_selector('#progress')
    row = page.locator('#progress tr', has_text='Phantom Dive counter math').inner_text()
    assert '1/1 verified ok' in row and 'insufficient verified evidence' in row
    page.check('input[name="real-concept"][value="two_prize_bench_liability"]')
    page.check('input[name="real-outcome"][value="error"]')
    page.fill('#real-tags', 'benched_liability')
    page.click('#log-real-btn')
    page.wait_for_selector('#progress tr:has-text("Two-Prize bench liability") >> text=self-reported ok')
    assert 'benched_liability: 1' in page.inner_text('main')


def test_inbox_log_to_validated_case_then_practise(page):
    page.goto(page.base + '/#inbox')
    page.wait_for_selector('#save-source')
    page.fill('#src-content', LOG + '\n<img src=x onerror=alert(1)>')
    page.fill('#src-opp', 'Rival99')
    page.click('#save-source')
    page.wait_for_selector('#timeline')
    assert page.locator('#timeline img').count() == 0            # rendered as text, not HTML
    page.locator('input[name="logline"]').nth(3).check()
    page.click('#make-candidate')
    page.wait_for_selector('#promote')
    assert 'Rival99' not in page.input_value('#c-full')
    page.click('#promote')
    page.wait_for_selector('[role=alert]:has-text("observed_state is required")')
    page.fill('#c-id', 'real-bench-t2')
    page.fill('#c-prompt', 'Bench Dreepy now?')
    page.fill('#c-observed', 'Turn 1. Active Budew. Hand: Dreepy, Poffin, Crispin.')
    page.fill('#c-choices', 'A: Bench it\nB: Hold it')
    page.select_option('#c-family', 'bench')
    page.select_option('#c-crit', '3')
    page.fill('#c-crit-src', 'my review')
    page.select_option('#c-recon', 'medium')
    page.check('input[name="c-concept"][value="two_prize_bench_liability"]')
    page.click('#add-ev')
    page.select_option('#ev0-level', 'FACT')
    page.fill('#ev0-claim', 'Opponent had Boss next turn')
    page.click('#promote')
    page.wait_for_selector('[role=alert]:has-text("FACT needs exact/high")')
    page.select_option('#ev0-level', 'HEURISTIC')
    page.fill('#ev0-choice', 'B')
    page.select_option('#ev0-verdict', 'good')
    page.click('#promote')
    page.wait_for_selector('#promoted')
    page.click('#promoted a')
    page.wait_for_selector('#lock')
    assert 'Bench Dreepy now?' in page.inner_text('#prompt')
    assert 'Boss' not in page.inner_text('main')                 # hindsight excerpt stays hidden
    do_rep(page, choice_index=1, outcome='ok')
    assert 'Boss' in page.inner_text('main')                     # full record shown after answering


def test_coach_mocked_enabled(page, fake_llm):
    from test_api import GOOD
    fake_llm.reply = GOOD
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=0)
    page.click('#coach-btn')
    page.wait_for_selector('#coach-out >> text=Main concept')
    out = page.inner_text('#coach-out')
    assert 'not evidence' in out and 'Unverified claims' in out and 'Always spread counters.' in out


def test_mode_hidden_before_reveal_and_keyboard_shortcuts(page):
    page.goto(page.base + '/#case/demo-dive-count')        # leave a leak so the session has an exploit rep
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=0, recall='Again')
    page.goto(page.base + '/#today')
    page.click('#start')
    page.wait_for_selector('#position')
    for mode in ('exploit', 'coverage', 'probe'):          # no training-mode hint before the decision
        assert mode not in page.inner_text('main').lower()
    for ta in page.locator('textarea[id^="plan-"]').all():
        ta.fill('a plan with the letters a b 1 2')          # typing never triggers shortcuts
    page.keyboard.press('Control+Enter')                     # lock
    page.wait_for_selector('#locked-plan')
    page.fill('#other', 'a')
    assert page.locator('input[name="choice"]:checked').count() == 0
    page.locator('#other').blur()
    page.keyboard.press('a')
    assert page.locator('input[name="choice"][value="A"]').is_checked()
    assert 'exploit' not in page.inner_text('main').lower()
    page.keyboard.press('Control+Enter')                     # submit
    page.wait_for_selector('#ledger')
    page.locator('body').click(position={'x': 2, 'y': 2})
    page.keyboard.press('2')
    assert page.locator('input[name^="recall-"][value="2"]:checked').count() == 1
    assert page.locator('.focusbar .badge').inner_text() in ('exploit', 'coverage', 'probe')   # shown after reveal
