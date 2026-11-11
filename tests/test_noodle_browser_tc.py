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
        if (el.closest('.exec-nav')) continue;   // the site nav: the site's words, not noodle's
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
        # sand has no theme-color: iOS fades its bars over the ground instead
        # of a solid band
        theme = pages.PALETTES[pages.SKINS[front]]
        assert page.locator('meta[name="theme-color"]').count() == (1 if theme else 0)
        _no_leaks(page, f"{front}'s landing page")
        page.click("#nd-create .nd-submit")
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
                assert page.locator(".exec-nav").is_visible(), f"{front}: the site nav (one page, both bases)"
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


def _palette(page):
    return page.evaluate("ndpCurrent(ndpList())")


def test_the_chevrons_switch_the_palette_and_this_browser_keeps_it(browser, base_url, noodle_slug):
    """The start page's chevrons (beside Create a poll) step through every
    palette and wrap; the choice is kept in THIS browser only -- it survives a
    reload, follows to a poll page (chevrons beside the title) and to the
    other front end, and no request ever carries it."""
    ctx, page = _guest(browser, base_url)
    sent = []
    page.on("request", lambda r: sent.append(r.url) if "palette" in (r.post_data or "") + r.url and r.method != "GET" else None)
    names = list(pages.PALETTES)
    try:
        front, default = next(iter(pages.SKINS.items()))
        page.goto(f"{base_url}{front}")
        assert _palette(page) == default
        theme = 'document.querySelector(\'meta[name="theme-color"]\')?.content ?? null'
        start = names.index(default)
        for i in range(1, len(names) + 1):   # all the way round, back to the start
            page.click("#nd-create .nd-pal.next")
            now = names[(start + i) % len(names)]
            assert _palette(page) == now
            assert page.evaluate(theme) == pages.PALETTES[now], f"{now}'s browser-bar tint"
        page.click("#nd-create .nd-pal.prev")
        chosen = names[(start - 1) % len(names)]
        assert _palette(page) == chosen
        assert page.evaluate("localStorage.getItem('noodle.palette')") == chosen
        page.reload()
        assert _palette(page) == chosen, "kept across a reload"
        page.goto(f"{base_url}{front}/{noodle_slug}")
        assert _palette(page) == chosen, "and on a poll page"
        row = page.locator(".nd-title-row")
        assert row.locator(".nd-pal.prev").is_visible() and row.locator(".nd-pal.next").is_visible()
        for other in pages.SKINS:
            page.goto(f"{base_url}{other}")
            assert _palette(page) == chosen, f"and on {other}"
        assert all("palette" not in c["name"] + c["value"] for c in ctx.cookies()), "never a cookie"
        assert sent == [], f"the choice left the browser: {sent}"
    finally:
        ctx.close()
