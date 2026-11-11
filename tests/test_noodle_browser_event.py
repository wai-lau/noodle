"""The host's EVENT TIME (noodle-event.js), in the real engine: the host ticks
a top date, Save seals it in the head, and a guest sees it under the title;
a guest gets no table. And /noodle-tc's layout around it: ONE card holding
the legend and the host's top dates, then Save, its status and any error."""
import hashlib

import pytest

pytestmark = pytest.mark.browser

UNLOCK = ("(NDV.step !== 'pick' && ndvCanNext() && ndvStep('pick'),"
          " !document.getElementById('nd-cal').classList.contains('nd-readonly'))")


def _commit(page):
    page.wait_for_function("!document.querySelector('#nd-submit').disabled", timeout=20000)
    page.evaluate("NDV.committed = 0")
    page.click("#nd-submit")
    page.wait_for_function("NDV.committed > 0", timeout=20000)


def _join(page, link, name, pw):
    page.goto(link)
    page.wait_for_function("NDV.poll", timeout=10000)
    page.fill("#nd-name", name)
    page.fill("#nd-pass", pw)
    page.wait_for_function(UNLOCK, timeout=20000)


def test_the_host_picks_an_event_time_and_everyone_sees_it(browser, base_url):
    import httpx
    from conftest import API_KEY, TURNSTILE_SECRET
    if not API_KEY or not TURNSTILE_SECRET:
        pytest.skip("API_KEY / TURNSTILE_SECRET not set")
    cookie = hashlib.sha256(f"guest:{TURNSTILE_SECRET}".encode()).hexdigest()
    slug, ctxs = None, []

    def open_():
        ctx = browser.new_context(viewport={"width": 430, "height": 932})
        ctx.add_cookies([{"name": "guest_session", "url": base_url, "value": cookie}])
        ctxs.append(ctx)
        return ctx.new_page()

    try:
        host = open_()
        host.goto(f"{base_url}/noodle-tc")
        host.click("#nd-create .nd-submit")
        host.wait_for_function("window.NDV && NDV.keyStr", timeout=10000)
        key, slug = host.evaluate("[NDV.keyStr, NDV.slug]")
        host.fill("#nd-name", "event host")
        host.fill("#nd-pass", "host pass")
        host.wait_for_function(UNLOCK, timeout=20000)
        host.evaluate("NDV.cal.setSel(new Set([...NDV.cal.openSlots('0', '9')].slice(0, 2))); ndvSaveDraft()")
        _commit(host)
        link = f"{base_url}/noodle-tc/{slug}#k={key}"
        offer = host.evaluate("NDV.poll.voters[0].slots")

        guest = open_()
        _join(guest, link, "event guest", "guest pass")
        guest.evaluate(f"NDV.cal.setSel(new Set({offer!r})); ndvSaveDraft()")
        _commit(guest)
        assert guest.locator(".nd-top-pick").count() == 0, "a guest picks no event time"
        assert guest.is_hidden("#nd-event")
        assert guest.is_hidden("#nd-top-box"), "the most popular times are the host's alone"

        # the host ticks the first top date; it shows at once, unsaved
        host.reload()
        host.wait_for_function("NDV.poll && NDV.poll.voters.length === 2", timeout=10000)
        host.wait_for_function(UNLOCK, timeout=20000)
        assert host.evaluate("document.getElementById('nd-top-box').classList.contains('nd-top-host')")
        box = host.locator(".nd-top-pick").first
        slot = box.get_attribute("data-slot")
        box.check()
        assert host.is_visible("#nd-event") and host.evaluate("ndvDirty()")
        _commit(host)
        assert host.evaluate("NDV.poll.event") == [slot]

        # /noodle-tc's order: the one card, then Save and its status
        order = host.evaluate("""() => {
          const ids = ['nd-submit', 'nd-dirty'], card = document.querySelector('.nd-tc-card');
          const y = el => el.getBoundingClientRect().top;
          return [y(card) < y(document.getElementById('nd-submit')), y(card) < y(document.getElementById('nd-dirty')),
            card.contains(document.querySelector('.nd-tc-legend')), card.contains(document.getElementById('nd-top'))]; }""")
        assert order == [True, True, True, True]

        guest.reload()
        guest.wait_for_function("NDV.poll", timeout=10000)
        guest.wait_for_selector("#nd-event:not([hidden])", timeout=10000)
        assert guest.evaluate("NDV.poll.event") == [slot]
        # the guest sees the choice under the title, no table
        assert guest.is_hidden("#nd-top-box")
        assert guest.evaluate("getComputedStyle(document.getElementById('nd-event'), '::before').content") == '"The host has chosen"'
        text = guest.inner_text("#nd-event")
        assert text.strip() and "/" not in text, "worded in full on /noodle-tc"
    finally:
        for c in ctxs:
            c.close()
        if slug:
            httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers={"Authorization": f"Bearer {API_KEY}"})


def test_the_poll_loads_only_after_every_script(browser, base_url, noodle_slug):
    """noodle-vote.js must not fetch the poll while the page is still loading
    scripts: a poll that landed before noodle-event.js lost the host's chosen
    time on reload (Chrome, 2026-10-31). Every fetch of the poll records the
    document's readyState at the moment it is made."""
    ctx = browser.new_context(viewport={"width": 430, "height": 932})
    ctx.add_init_script("""
      window.__pollFetches = [];
      const f = window.fetch;
      window.fetch = function (url, o) {
        if (String(url).indexOf('/api/noodle/') >= 0) window.__pollFetches.push(document.readyState);
        return f.apply(this, arguments);
      };""")
    page = ctx.new_page()
    try:
        page.goto(f"{base_url}/noodle-tc/{noodle_slug}")
        page.wait_for_function("window.NDV && NDV.poll", timeout=10000)
        seen = page.evaluate("window.__pollFetches")
        assert seen and "loading" not in seen, f"the poll was fetched mid-load: {seen}"
        assert page.evaluate("typeof window.ndevShow") == "function"
    finally:
        ctx.close()
