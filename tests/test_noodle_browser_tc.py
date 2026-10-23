"""/noodle-tc, the second front end (pages.SKINS), in the real engine: it says
things in ITS words (noodle-tc-copy.js) and shows no seal art (noodle-tc.css).
The flows themselves are the same JS as /noodle, smoked on both front ends by
test_noodle_browser_smoke.py; this guards what only the skin adds.

A failure here usually means a new or changed string in the shared JS that
the wording table has no line for yet."""
import hashlib

import httpx
import pytest

from test_noodle_browser_smoke import _sign_in, _tap

pytestmark = pytest.mark.browser

# noodle's own voice: none of it may reach a /noodle-tc page
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
        out.push(n.nodeValue.trim());
      }
      // a hidden element's label is out of the accessibility tree too
      document.querySelectorAll('[placeholder], [aria-label]').forEach(e => {
        if (e.checkVisibility()) out.push(e.getAttribute('placeholder') || e.getAttribute('aria-label'));
      });
      return out.filter(Boolean);
    }""")


def _no_leaks(page, where):
    for text in _shown(page):
        hit = [w for w in LEAKS if w in text.lower()]
        assert not hit, f"{where}: noodle's own wording {hit!r} in {text!r}"


def test_the_tc_pages_speak_in_their_own_words(browser, base_url, admin_headers):
    ctx, page = _guest(browser, base_url)
    slug = None
    try:
        page.goto(f"{base_url}/noodle-tc")
        # no theme-color: iOS fades its bars over the ground instead of a solid band
        assert page.locator('meta[name="theme-color"]').count() == 0
        _no_leaks(page, "the landing page")
        page.click("#nd-create button")
        page.wait_for_function("window.NDV && NDV.keyStr", timeout=20000)
        slug = page.evaluate("NDV.slug")
        _sign_in(page, "tc host", "tc pass")
        _tap(page, 2)
        _no_leaks(page, "the host's pick step")
        assert page.inner_text("#nd-submit") == "Save"   # sentence case, never spaced capitals
        assert not page.locator(".nd-seal").first.is_visible(), "no seal art on /noodle-tc"
    finally:
        ctx.close()
        if slug:
            httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers={"Authorization": admin_headers["Authorization"]})
