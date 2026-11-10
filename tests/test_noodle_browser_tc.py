"""The Tarid Change front ends (pages.SKINS: /noodle and /noodle-tc) in the
real engine: they say things in the TC words (noodle-tc-copy.js), show no seal
art (noodle-tc.css), and -- the DRIFT guard -- show the same words and the
same elements as each other, palette aside (the source side of that is
test_noodle_skins.py). The flows themselves are smoked on both by
test_noodle_browser_smoke.py.

A wording failure usually means a new or changed string in the shared JS that
the wording table has no line for yet."""
import hashlib

import httpx
import pytest

from noodle import pages

from test_noodle_browser_smoke import _sign_in, _tap

pytestmark = pytest.mark.browser

# noodle's own voice: none of it may reach either front end
LEAKS = ("noodle", "commit", "seal", "pick times", "help me", "pls", "--")


def _guest(browser, base_url):
    from conftest import TURNSTILE_SECRET
    if not TURNSTILE_SECRET:
        pytest.skip("TURNSTILE_SECRET not set")
    ctx = browser.new_context(viewport={"width": 430, "height": 932})
    ctx.add_cookies([{"name": "guest_session", "url": base_url,
                      "value": hashlib.sha256(f"guest:{TURNSTILE_SECRET}".encode()).hexdigest()}])
    return ctx, ctx.new_page()


def _shown(page):
    """Every visible word on the page, plus placeholders and labels."""
    return page.evaluate("""() => {
      const out = [document.title];
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = w.nextNode(); n; n = w.nextNode()) {
        const el = n.parentElement;
        if (!n.nodeValue.trim() || !el.checkVisibility()) continue;
        if (el.closest('#nd-title, #nd-note, .nd-face-name, #nd-you-name, .nd-top-date')) continue;  // poll content
        if (el.closest('.exec-nav')) continue;   // the site nav, /noodle's alone
        out.push(n.nodeValue.trim());
      }
      // a hidden element's label is out of the accessibility tree too
      document.querySelectorAll('[placeholder], [aria-label]').forEach(e => {
        if (e.checkVisibility() && !e.closest('.exec-nav')) out.push(e.getAttribute('placeholder') || e.getAttribute('aria-label'));
      });
      return out.filter(Boolean);
    }""")


def _no_leaks(page, where):
    for text in _shown(page):
        hit = [w for w in LEAKS if w in text.lower()]
        assert not hit, f"{where}: noodle's own wording {hit!r} in {text!r}"


@pytest.mark.parametrize("front", list(pages.SKINS))
def test_the_tc_pages_speak_in_their_own_words(browser, base_url, admin_headers, front):
    ctx, page = _guest(browser, base_url)
    slug = None
    try:
        page.goto(f"{base_url}{front}")
        # /noodle-tc has no theme-color: iOS fades its bars over the ground
        # instead of a solid band
        theme = pages.SKINS[front][1]
        assert page.locator('meta[name="theme-color"]').count() == (1 if theme else 0)
        _no_leaks(page, f"{front}'s landing page")
        page.click("#nd-create button")
        page.wait_for_function("window.NDV && NDV.keyStr", timeout=20000)
        slug = page.evaluate("NDV.slug")
        _sign_in(page, "tc host", "tc pass")
        _tap(page, 2)
        _no_leaks(page, f"{front}'s host pick step")
        assert page.inner_text("#nd-submit") == "Save"   # sentence case, never spaced capitals
        assert not page.locator(".nd-seal").first.is_visible(), f"no seal art on {front}"
    finally:
        ctx.close()
        if slug:
            httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers={"Authorization": admin_headers["Authorization"]})


def _visible_ids(page):
    """Every element on screen that has an id, outside the site nav."""
    return page.evaluate("""() => [...document.querySelectorAll('body [id]')]
      .filter(e => e.checkVisibility() && !e.closest('.exec-nav')).map(e => e.id).sort()""")


def test_the_front_ends_show_the_same_page(browser, base_url, admin_headers):
    """The same poll on each front end: the same words and the same elements
    on screen, on the start page and on each step of a vote. Only the colours
    and faces may differ."""
    auth = {"Authorization": admin_headers["Authorization"]}
    slug = httpx.post(f"{base_url}/api/noodle-polls", headers=auth, json={"title": "__smoke_drift__"}).json()["slug"]
    seen = {}
    try:
        for front in pages.SKINS:
            ctx, page = _guest(browser, base_url)
            try:
                page.goto(f"{base_url}{front}")
                start = (_shown(page), _visible_ids(page))
                page.goto(f"{base_url}{front}/{slug}")
                page.wait_for_function("NDV.poll && NDV.keysLoaded", timeout=20000)
                you = (_shown(page), _visible_ids(page))
                _sign_in(page, "drift host", "drift pass")
                pick = (_shown(page), _visible_ids(page))
                seen[front] = {"start": start, "you": you, "pick": pick}
            finally:
                ctx.close()
    finally:
        httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers=auth)
    a, b = seen.values()
    for step in a:
        assert a[step] == b[step], f"the front ends drifted on the {step} page"
