"""UI v4 interactions in a real browser: command palette, action bar, deep focus, reveal story, next step."""
import pytest

from test_e2e import do_rep, page  # noqa: F401  (shared browser fixture: fails on any console error)

pytest.importorskip('playwright.sync_api')
LEAKY = ('exploit', 'coverage', 'probe', 'phantom dive counter math', 'leak')


def bar(page):
    return page.inner_text('#actionbar')


def until(page, check, what):
    """Poll from Python: the app's CSP forbids the eval that wait_for_function needs."""
    for _ in range(40):
        if check():
            return
        page.wait_for_timeout(50)
    raise AssertionError(what)


def wait_bar(page, text):
    until(page, lambda: text in bar(page), f'action bar never showed {text!r}: {bar(page)!r}')


def test_palette_opens_filters_navigates_and_restores_focus(page):
    page.goto(page.base + '/#today')
    page.wait_for_selector('#plan')
    page.focus('#start')
    page.keyboard.press('Control+k')
    page.wait_for_selector('#palette[open]')
    assert page.evaluate('document.activeElement.id') == 'palette-input'
    page.keyboard.press('Escape')                                  # closes, focus back on the invoker
    page.wait_for_selector('#palette:not([open])', state='attached')
    assert page.evaluate('document.activeElement.id') == 'start'
    page.keyboard.press('Control+k')
    page.keyboard.type('progr')
    assert page.locator('#palette-list [role=option]').first.inner_text().startswith('Progress')
    page.keyboard.press('Control+k')                               # toggles closed
    page.keyboard.press('Control+k')
    page.keyboard.press('ArrowDown')
    assert page.get_attribute('#palette-list [role=option]:nth-child(2)', 'aria-selected') == 'true'
    assert page.get_attribute('#palette-input', 'aria-activedescendant') == 'pal-1'
    page.keyboard.press('ArrowUp')
    page.keyboard.type('inbox')
    page.keyboard.press('Enter')
    page.wait_for_selector('#save-source')
    assert page.url.endswith('#inbox') and not page.locator('#palette[open]').count()


def test_palette_offers_only_possible_commands(page):
    page.goto(page.base + '/#today')
    page.wait_for_selector('#plan')
    page.keyboard.press('Control+k')
    items = page.inner_text('#palette-list')
    assert 'Start session' in items and 'Lock plan' not in items and 'Submit decision' not in items
    page.keyboard.press('Escape')
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    page.keyboard.press('Control+k')
    items = page.inner_text('#palette-list')
    assert 'Lock plan' in items and 'Submit decision' not in items and 'Start session' not in items
    for word in LEAKY[:3]:
        assert word not in items.lower()


def test_action_bar_follows_the_phase_and_never_leaks(page):
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    wait_bar(page, 'Lock plan')
    assert 'Submit' not in bar(page)
    assert page.evaluate("document.body.classList.contains('deep-focus')")
    for ta in page.locator('textarea[id^="plan-"]').all():
        ta.fill('Take prizes')
    page.keyboard.press('Control+Enter')
    page.wait_for_selector('#locked-plan')
    wait_bar(page, 'Choose')
    text = bar(page)
    assert 'Submit decision' in text and 'Hint' in text and 'Lock plan' not in text
    for word in LEAKY:                                           # nothing about the target before the decision
        assert word not in text.lower() and word not in page.inner_text('main').lower()
    page.keyboard.press('b')
    page.keyboard.press('Control+Enter')
    page.wait_for_selector('#ledger')
    wait_bar(page, 'Rate recall')
    assert 'Retry' not in bar(page)                               # retry exists only after the review is saved
    assert not page.evaluate("document.body.classList.contains('deep-focus')")
    assert page.evaluate('document.activeElement.id') == 'story-title'
    page.locator('input[name^="recall-"]').nth(2).check()
    page.click('#save-review')
    page.wait_for_selector('#after:not([hidden])')
    wait_bar(page, 'Retry')
    assert page.evaluate('document.activeElement.id') == 'next'


def test_deep_focus_keeps_navigation_reachable(page):
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    link = page.locator('.nav a[href="#progress"]')
    assert link.is_visible() and float(page.evaluate("getComputedStyle(document.querySelector('.nav')).opacity")) > 0.2
    link.focus()                                                  # keyboard focus brings the chrome back
    until(page, lambda: page.evaluate("getComputedStyle(document.querySelector('.nav')).opacity") == '1', 'nav stayed dim on focus')
    link.click()
    page.wait_for_selector('#next-step')
    assert not page.evaluate("document.body.classList.contains('deep-focus')")


def test_reveal_story_keeps_graded_and_ungraded_apart(page):
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=1)
    assert 'is-dim' not in page.get_attribute('#reveal', 'class')
    assert page.locator('#reveal .verdict-step .node.solid').count() == 1
    assert 'Matches the graded evidence' in page.inner_text('#verdict')
    page.goto(page.base + '/?fresh#case/demo-dive-setup')
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=0, outcome='ok')
    assert 'is-dim' in page.get_attribute('#reveal', 'class')
    assert page.locator('#reveal .verdict-step .node.dashed').count() == 1
    assert 'Not graded' in page.inner_text('#verdict') and 'unresolved' in page.inner_text('#reveal').lower()
    for label in ('Your plan', 'Your decision', 'Why', 'Principle', 'Recall', 'Next'):
        assert label.lower() in page.inner_text('main').lower(), label


def test_progress_leads_with_an_honest_next_step(page):
    page.goto(page.base + '/#progress')
    page.wait_for_selector('#next-step')
    assert 'Insufficient evidence' in page.inner_text('#next-step')
    assert 'is-dim' in page.get_attribute('#next-step', 'class')
    page.goto(page.base + '/#case/demo-dive-count')
    page.wait_for_selector('#lock')
    do_rep(page, choice_index=0, recall='Again')                  # a verified error
    page.goto(page.base + '/#progress')
    page.wait_for_selector('#next-step')
    step = page.inner_text('#next-step')
    assert 'Train this concept' in step and 'Phantom Dive counter math' in step
    assert 'is-dim' not in page.get_attribute('#next-step', 'class')


@pytest.mark.parametrize('width', [360, 393, 430])
def test_phone_has_no_overflow_and_no_second_bar(page, width):
    page.set_viewport_size({'width': width, 'height': 800})
    for hash_, sel in (('#today', '#plan'), ('#case/demo-dive-count', '#lock'), ('#progress', '#next-step'), ('#inbox', '#save-source')):
        page.goto(page.base + '/' + hash_)
        page.wait_for_selector(sel)
        assert page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth') <= 0, hash_
        assert not page.locator('#actionbar').is_visible()
