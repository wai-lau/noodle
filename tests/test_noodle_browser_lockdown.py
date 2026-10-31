"""A browser WITHOUT WebAssembly (Safari's Lockdown Mode) in the real engine:
it makes a new seat's key with PBKDF2 instead of Argon2id (noodle-kdf.js), the
seat's method is sealed in its vote, and from then on EVERY browser makes that
seat's key the same way -- so the name + passphrase work on any device, a
passphrase or name change keeps the method, and an Argon2id seat opened in
Lockdown still opens, slowly, with plain-JS Argon2id (the same key)."""
import pytest

pytestmark = pytest.mark.browser

UNLOCK = ("(NDV.step !== 'pick' && ndvCanNext() && ndvStep('pick'),"
          " !document.getElementById('nd-cal').classList.contains('nd-readonly'))")
HOST, GUEST, RENAMED = "lockdown host", "lockdown guest", "lockdown renamed"

# Lockdown Mode's missing WebAssembly, in the page AND the key worker: the
# worker runs from a Blob the page builds out of verified bytes, so the Blob
# gets one line in front. (Wrapping the Worker in a second Blob that
# importScripts the first breaks under the real CSP, which does not allow
# blob: scripts.)
NO_WASM = """
delete window.WebAssembly;
const B = window.Blob;
window.Blob = function (parts, o) {
  if (o && o.type === 'text/javascript') parts = ['self.WebAssembly = undefined;'].concat(parts);
  return new B(parts, o);
};
"""


def _ctx(browser, base_url, lockdown, cookie=None):
    ctx = browser.new_context(viewport={"width": 430, "height": 932})
    if lockdown:
        ctx.add_init_script(NO_WASM)
    if cookie:
        ctx.add_cookies([{"name": "guest_session", "url": base_url, "value": cookie}])
    return ctx, ctx.new_page()


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


def _method(page):
    return page.evaluate("NDV.kdf.method()")


def test_a_lockdown_seat_uses_pbkdf2_everywhere_and_keeps_it(browser, base_url):
    import hashlib

    import httpx
    from conftest import API_KEY, TURNSTILE_SECRET
    if not API_KEY or not TURNSTILE_SECRET:
        pytest.skip("API_KEY / TURNSTILE_SECRET not set")
    cookie = hashlib.sha256(f"guest:{TURNSTILE_SECRET}".encode()).hexdigest()
    slug, ctxs = None, []

    def open_(lockdown):
        ctx, page = _ctx(browser, base_url, lockdown, cookie)
        ctxs.append(ctx)
        return page

    try:
        # the HOST, in Lockdown: a new seat, so PBKDF2
        host = open_(True)
        host.goto(f"{base_url}/noodle")
        host.click("#nd-create button")
        host.wait_for_function("window.NDV && NDV.keyStr", timeout=10000)
        key, slug = host.evaluate("[NDV.keyStr, NDV.slug]")
        assert host.evaluate("typeof WebAssembly") == "undefined"
        host.fill("#nd-name", HOST)
        host.fill("#nd-pass", "host pass")
        host.wait_for_function(UNLOCK, timeout=20000)
        assert _method(host) == "pbkdf2"
        host.evaluate("NDV.cal.setSel(new Set([...NDV.cal.openSlots('0', '9')].slice(0, 2))); ndvSaveDraft()")
        _commit(host)
        link = f"{base_url}/noodle/{slug}#k={key}"
        assert host.evaluate("NDV.poll.voters[0].kdf") == "pbkdf2", "the method is sealed in the vote"

        # an ordinary browser opens the same seat with the same passphrase:
        # the seat says PBKDF2, so it makes the same key
        normal = open_(False)
        _join(normal, link, HOST, "host pass")
        assert _method(normal) == "pbkdf2"
        assert normal.evaluate("NDV.mine && !NDV.blocked")
        # ... and a NEW seat there is Argon2id, as always
        guest = open_(False)
        _join(guest, link, GUEST, "guest pass")
        assert _method(guest) == "argon2id"
        offer = guest.evaluate("NDV.poll.voters[0].slots")
        guest.evaluate(f"NDV.cal.setSel(new Set({offer[:1]!r})); ndvSaveDraft()")
        _commit(guest)
        assert guest.evaluate("NDV.poll.voters[1].kdf") == "argon2id"

        # the host RENAMES and changes passphrase from the ordinary browser:
        # the seat keeps PBKDF2 (a new name never re-picks the method)
        normal.evaluate("ndvStep('you')")
        normal.click("#nd-rename")
        normal.fill("#nd-name", RENAMED)
        normal.click("#nd-rekey")
        normal.fill("#nd-pass", "host pass two")
        normal.wait_for_function("NDV.kdf.ready()", timeout=20000)
        assert _method(normal) == "pbkdf2"
        normal.click("#nd-next")
        _commit(normal)
        assert normal.evaluate("NDV.poll.voters.map(v => [v.name, v.kdf])") == [[RENAMED, "pbkdf2"], [GUEST, "argon2id"]]

        # back in Lockdown: the renamed seat opens; so does the Argon2id one,
        # the slow way (noble's plain-JS Argon2id, the SAME key), with its
        # progress and the Lockdown tip on screen while it runs
        again = open_(True)
        _join(again, link, RENAMED, "host pass two")
        assert _method(again) == "pbkdf2" and again.evaluate("NDV.mine")
        guest_pub = guest.evaluate("NDV.kdf.pub()")
        locked = open_(True)
        locked.goto(link)
        locked.wait_for_function("NDV.poll", timeout=10000)
        locked.fill("#nd-name", GUEST)
        locked.fill("#nd-pass", "guest pass")
        locked.wait_for_selector("#nd-slow:not([hidden])", timeout=20000)
        assert "Lockdown Mode" in locked.inner_text("#nd-slow")
        locked.wait_for_function("NDV.kdf.ready()", timeout=180000)
        assert locked.evaluate("NDV.kdf.pub()") == guest_pub, "the same key hash-wasm made"
        assert _method(locked) == "argon2id" and locked.evaluate("NDV.mine && !NDV.keyError")
        assert locked.is_hidden("#nd-slow")
    finally:
        for c in ctxs:
            c.close()
        if slug:
            httpx.delete(f"{base_url}/api/noodle-polls/{slug}", headers={"Authorization": f"Bearer {API_KEY}"})
