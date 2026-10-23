"""noodle SMOKE (WebKit = iOS): make a poll and use it the way a person does --
typed names, real taps on the calendar, the Commit button -- then check a
stranger with the link sees it all. No JS shortcuts (setSel, ndvStep) on the
voting path: the journey suite (test_noodle_browser_journey.py) covers the
data from every side, this one covers "can a human still get a vote in".

The first run also SAVES the poll's link (key included) and what it holds to
SAVED, never deleted, so every later run reopens that same, ever-older poll
on the current code: a change that leaves new polls working but strands old
ones fails here. Delete the file to start a fresh one (the next run saves it).

LEGACY holds hand-picked REAL polls from older eras, found in the nginx logs
from before slugs were masked (2026-10-14), opened READ-ONLY (they are other
people's polls: nothing is signed or written). The plain (non-e2e) ones are
SPECIAL exceptions, not a contract: keeping them working is no reason to keep
plain-poll support, and a security change that drops it deletes the entry
here rather than bending for it. Neither file is in git: a slug IS the poll's
key, and this repo is public.
"""
import hashlib
import json
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.browser

WAIT = 20000
# exec-fn's api/data: gitignored and outlives deploys (the link carries the key)
SAVED = Path(__file__).resolve().parents[3] / "api" / "data" / "noodle-smoke-poll.json"
LEGACY = SAVED.with_name("noodle-smoke-legacy.json")
HOST, GUEST = ("smoke host", "smoke host pass"), ("smoke guest", "smoke guest pass")


def _guest_cookie():
    from conftest import TURNSTILE_SECRET
    if not TURNSTILE_SECRET:
        pytest.skip("TURNSTILE_SECRET not set")
    return {"name": "guest_session", "value": hashlib.sha256(f"guest:{TURNSTILE_SECRET}".encode()).hexdigest()}


def _device(browser, base_url, cookie=None):
    ctx = browser.new_context(viewport={"width": 430, "height": 932})
    if cookie:
        ctx.add_cookies([{**cookie, "url": base_url}])
    return ctx, ctx.new_page()


def _opened(page):
    """The card is on screen (past the boot veil) with no error banner."""
    page.wait_for_selector("#noodle:not(.nd-booting)", timeout=WAIT)
    page.wait_for_function("NDV.poll && NDV.keysLoaded", timeout=WAIT)
    assert page.is_hidden("#nd-banner"), page.inner_text("#nd-banner")


def _sign_in(page, name, pw):
    """Type a name + passphrase and press next, as a person would."""
    _opened(page)
    if page.is_visible("#nd-you-edit"):   # a remembered identity opened on PICK
        page.click("#nd-you-edit")
    page.fill("#nd-name", name)
    page.fill("#nd-pass", pw)
    page.wait_for_function("NDV.kdf.ready()", timeout=WAIT)
    page.click("#nd-next")
    page.wait_for_function("!document.getElementById('nd-cal').classList.contains('nd-readonly')", timeout=WAIT)


def _tap(page, n):
    """Tap the first `n` pickable days, each one more pick than before."""
    cells = page.locator(".nd-d:not(.out):not(.shut)")
    assert cells.count() >= n, "nothing to pick"
    for i in range(n):
        before = page.evaluate("NDV.cal.getSel().size")
        cell = cells.nth(i)
        cell.scroll_into_view_if_needed()
        box = cell.bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.15)
        assert page.evaluate("NDV.cal.getSel().size") == before + 1, f"tap {i} picked nothing"


def _commit(page):
    page.wait_for_function("!document.querySelector('#nd-submit').disabled", timeout=WAIT)
    page.evaluate("NDV.committed = 0")
    page.click("#nd-submit")
    page.wait_for_function("NDV.committed > 0", timeout=WAIT)
    assert page.is_hidden("#nd-banner"), page.inner_text("#nd-banner")


def _view(page, n):
    """What a page shows once all `n` voters are in: {title, voters: {name: slots}}."""
    page.wait_for_function(f"NDV.poll.voters.length === {n} && NDV.poll.voters.every(v => v.name)", timeout=WAIT)
    return page.evaluate("({title: NDV.poll.title,"
                         " voters: Object.fromEntries(NDV.poll.voters.map(v => [v.name, [...v.slots].sort()]))})")


# every FRONT END (noodle pages.SKINS): one backend, so the same flow on each
@pytest.mark.parametrize("front", ["/noodle", "/noodle-tc"])
def test_a_new_poll_takes_votes_from_real_taps(browser, base_url, admin_headers, front):
    cookie = _guest_cookie()
    hctx, host = _device(browser, base_url, cookie)
    slug, keep = None, False
    try:
        host.goto(f"{base_url}{front}")
        host.click("#nd-create button")
        host.wait_for_function("window.NDV && NDV.keyStr", timeout=WAIT)
        slug, key = host.evaluate("[NDV.slug, NDV.keyStr]")
        assert host.url.startswith(f"{base_url}{front}/{slug}"), "a poll opens in the front end it was made in"
        path = f"{front}/{slug}#k={key}"   # saved without the origin: any SMOKE_BASE_URL
        link = base_url + path
        _sign_in(host, *HOST)
        _tap(host, 3)
        _commit(host)
        assert host.evaluate("ndeLink()") == link, "the share link stays in this front end"

        gctx, guest = _device(browser, base_url)
        try:
            guest.goto(link)
            _sign_in(guest, *GUEST)
            _tap(guest, 2)   # a guest picks from the host's offer
            _commit(guest)
        finally:
            gctx.close()

        vctx, visitor = _device(browser, base_url)   # the link, nothing remembered
        try:
            visitor.goto(link)
            _opened(visitor)
            seen = _view(visitor, 2)
        finally:
            vctx.close()
        assert list(seen["voters"]) == [HOST[0], GUEST[0]], "the host's seat comes first"
        assert len(seen["voters"][HOST[0]]) == 3 and len(seen["voters"][GUEST[0]]) == 2
        assert set(seen["voters"][GUEST[0]]) <= set(seen["voters"][HOST[0]]), "a guest picks only what was offered"

        if front == "/noodle" and not SAVED.exists():   # the first one becomes the old poll for every later run
            SAVED.write_text(json.dumps({"path": path, "slug": slug, "made": host.evaluate("new Date().toISOString()"),
                                         "title": seen["title"], "voters": seen["voters"]}, indent=2))
            keep = True
    finally:
        hctx.close()
        if slug and not keep:
            httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers={"Authorization": admin_headers["Authorization"]})


def test_the_saved_old_poll_still_works(browser, base_url):
    if not SAVED.exists():
        pytest.skip(f"no saved poll yet ({SAVED.name}): the new-poll smoke saves one on its next run")
    saved = json.loads(SAVED.read_text())
    link = base_url + saved["path"]
    ctx, page = _device(browser, base_url)
    try:
        page.goto(link)
        _opened(page)
        seen = _view(page, len(saved["voters"]))
        assert seen == {"title": saved["title"], "voters": saved["voters"]}, \
            f"the poll saved {saved['made']} no longer reads back as it was"
    finally:
        ctx.close()
    # its guest, on a new device, still unlocks their own seat with the passphrase
    ctx, page = _device(browser, base_url)
    try:
        page.goto(link)
        _sign_in(page, *GUEST)
        page.wait_for_function("NDV.mine", timeout=WAIT)
        assert not page.evaluate("NDV.blocked"), "the old passphrase no longer opens the old seat"
    finally:
        ctx.close()


def _legacy():
    return json.loads(LEGACY.read_text())["polls"] if LEGACY.exists() else []


@pytest.mark.parametrize("old", _legacy() or [None], ids=lambda o: o["era"].split(":")[0] if o else "none")
def test_an_old_era_poll_still_opens(browser, base_url, old):
    if old is None:
        pytest.skip(f"no saved old-era polls ({LEGACY.name})")
    ctx, page = _device(browser, base_url)
    try:
        page.goto(base_url + old["path"])
        _opened(page)
        page.wait_for_function("NDV.poll.voters.length > 0", timeout=WAIT)
        poll = page.evaluate("({title: NDV.poll.title, voters: NDV.poll.voters.map(v => [v.name, v.slots.length])})")
        assert poll["title"], f"{old['era']}: no title"
        assert len(poll["voters"]) >= old["voters"], f"{old['era']}: voters went missing"
        assert all(name for name, _ in poll["voters"]), f"{old['era']}: a voter lost their name"
        assert page.locator("#nd-voters .nd-face[data-name]:not([data-name=\"\"])").count() == len(poll["voters"]), "every voter has a face"
    finally:
        ctx.close()


def test_a_name_keeps_its_capitals_for_everyone(browser, base_url, admin_headers):
    """A name is shown as its owner typed it -- capitals and all -- to every
    viewer of an end-to-end poll, while the seat stays case-blind (the
    identity is the lowercased name)."""
    cookie = _guest_cookie()
    hctx, host = _device(browser, base_url, cookie)
    slug = None
    try:
        host.goto(f"{base_url}/noodle")
        host.click("#nd-create button")
        host.wait_for_function("window.NDV && NDV.keyStr", timeout=WAIT)
        slug, key = host.evaluate("[NDV.slug, NDV.keyStr]")
        _sign_in(host, "Smoke Capital Host", "cap pass")
        assert host.input_value("#nd-name") == "Smoke Capital Host", "capitals kept as typed"
        _tap(host, 1)
        _commit(host)
        vctx, visitor = _device(browser, base_url)
        try:
            visitor.goto(f"{base_url}/noodle/{slug}#k={key}")
            _opened(visitor)
            visitor.wait_for_function("NDV.poll.voters.length === 1", timeout=WAIT)
            seat = visitor.evaluate("NDV.poll.voters[0]")
            assert seat["name"] == "smoke capital host", "the identity is the lowercased name"
            assert seat["display"] == "Smoke Capital Host"
            assert visitor.inner_text("#nd-voters .nd-face-name") == "Smoke Capital Host"
        finally:
            vctx.close()
    finally:
        hctx.close()
        if slug:
            httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers={"Authorization": admin_headers["Authorization"]})
