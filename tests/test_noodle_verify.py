"""Opt-in code verification (noodle §21m): the vote page pins every script with
Subresource Integrity, so a link holder can check what their browser actually
ran against the public repo (github.com/wai-lau/noodle). No build step -- a
served file is byte-for-byte the repo file -- so the sha384 in the page equals
sha384 of the repo file at the deployed commit.

noodle imports no app module (test_noodle_isolation), so it cannot resolve a
parent-served script (qc-holidays.js) itself: the composition root hands it a
resolver via pages.set_sri, exactly like set_nav/set_owner. noodle owns the
hashing; the resolver only returns bytes."""
import base64
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
import app_paths  # noqa: E402  (a test may import app modules; production noodle may not)
from noodle import pages  # noqa: E402

_SCRIPT = re.compile(r'<script\b[^>]*\bsrc="(?P<url>/[^"?]+\.js)(?:\?[^"]*)?"[^>]*></script>')
_INTEG = re.compile(
    r'<script\b[^>]*\bsrc="(?P<url>/[^"?]+\.js)(?:\?[^"]*)?"[^>]*'
    r'\bintegrity="sha384-(?P<h>[A-Za-z0-9+/=]+)"[^>]*></script>')


def _bytes_for(url: str) -> bytes | None:
    """What routers.py's resolver does: the served file's bytes, or None."""
    rel = url.lstrip("/")
    for d in app_paths.web_dirs():
        p = d / rel
        if p.is_file():
            return p.read_bytes()
    return None


def _sha384(data: bytes) -> str:
    return base64.b64encode(hashlib.sha384(data).digest()).decode()


def test_vote_page_scripts_carry_sri_matching_the_served_file():
    pages.set_sri(_bytes_for)
    try:
        html = pages.vote_page({"slug": "a" * 22, "e2e": True})
    finally:
        pages.set_sri(None)
    srcs = _SCRIPT.findall(html)
    assert srcs, "vote page should have external .js scripts"
    integ = {m.group("url"): m.group("h") for m in _INTEG.finditer(html)}
    for url in srcs:
        assert url in integ, f"{url} is served with no sha384 integrity"
        data = _bytes_for(url)
        assert data is not None, f"{url} does not resolve to a served file"
        assert integ[url] == _sha384(data), f"{url} integrity != the served bytes"


def test_no_sri_resolver_leaves_the_page_working_and_unpinned():
    """Isolation / standalone: with nothing injected the page still renders,
    just without integrity (never a crash)."""
    pages.set_sri(None)
    html = pages.vote_page({"slug": "a" * 22, "e2e": True})
    assert _SCRIPT.findall(html), "scripts still present"
    assert "integrity=" not in html, "no integrity without a resolver"


def test_routers_wire_the_resolver_so_production_is_not_noop():
    """The vote page in production must actually be pinned -- catch a missing
    set_sri wiring. A source check (importing routers needs app secrets): the
    composition root calls pages.set_sri beside set_nav/set_owner."""
    from conftest import HOST_ROOT
    src = (HOST_ROOT / "api" / "routers.py").read_text()
    assert "noodle_pages.set_sri(" in src, "routers.py must call noodle_pages.set_sri"


def test_verifier_expected_csp_matches_the_served_meta():
    """The GitHub-Pages verifier (docs/verify.html) checks a pasted page's CSP
    <meta> against a hard-coded EXPECTED_CSP; it must equal what the server puts
    in the <meta> (config.VOTE_CSP_META), or the verifier rejects honest pages."""
    import re as _re

    from noodle import config
    html = (Path(__file__).resolve().parent.parent / "docs" / "verify.html").read_text(encoding="utf-8")
    m = _re.search(r'const EXPECTED_CSP = "([^"]+)";', html)
    assert m, "verify.html must define EXPECTED_CSP"
    assert m.group(1) == config.VOTE_CSP_META, "verifier EXPECTED_CSP drifted from config.VOTE_CSP_META"


def test_vote_csp_admits_the_pinned_blob_worker():
    """The key worker now runs from a Blob (pinned), which a blob: worker-src and
    (because a blob worker inherits the page CSP) 'wasm-unsafe-eval' for Argon2's
    WebAssembly make possible. 'wasm-unsafe-eval' permits wasm only, not eval()."""
    from noodle import config
    assert "worker-src 'self' blob:" in config.VOTE_CSP
    assert "'wasm-unsafe-eval'" in config.VOTE_CSP
    assert "'unsafe-eval'" not in config.VOTE_CSP.replace("'wasm-unsafe-eval'", "")
