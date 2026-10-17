#!/usr/bin/env python3
"""Verify a noodle vote page against the public source.

noodle is end-to-end encrypted: your browser holds the key (in the link's #k=
fragment) and decrypts there -- the server never sees it. The one thing a web
app cannot prove by crypto alone is that the JavaScript it served you is the
public, audited code and not a targeted swap. This checks exactly that.

noodle has NO build step, so each served file is byte-for-byte a file in the
public repo. The vote page also pins every script with Subresource Integrity
(a sha384 the browser enforces). This tool fetches the page and, for each
script, compares three hashes:

    page-pin (SRI)  ==  the file the server serves now  ==  the public repo

    python3 verify.py https://wai-lau.net/noodle/<slug>

Exit 0 only when every script is pinned and all three agree.

CAVEAT: this checks THIS fetch. A server that targets one person could serve
clean code to this tool and tampered code to them. To check YOUR OWN browser's
load, open View-Source on your vote page and compare each
integrity="sha384-..." to the "repo" hash this tool prints. Those two matching
is the targeting-resistant check -- the browser guarantees it ran the pinned
bytes.
"""
import hashlib
import re
import sys
import urllib.request
from urllib.parse import urlsplit

# web/<file> in each of these PUBLIC repos is a candidate source for a script.
# Both default to the `master` branch; `main` is tried too so a future rename
# does not silently break the check.
REPOS = ("wai-lau/noodle", "wai-lau/exec-fn")
REFS = ("master", "main")
RAW = "https://raw.githubusercontent.com/{repo}/{ref}/web/{name}"
_SCRIPT = re.compile(
    r'<script\b[^>]*\bsrc="(?P<url>/[^"?]+\.js)(?:\?[^"]*)?"'
    r'(?:[^>]*\bintegrity="sha384-(?P<pin>[A-Za-z0-9+/=]+)")?[^>]*></script>')


def _get(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "noodle-verify"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception:
        return None


def _sha384(data: bytes) -> str:
    import base64
    return base64.b64encode(hashlib.sha384(data).digest()).decode()


def _repo_hash(name: str, served_h: str | None) -> tuple[str | None, str | None]:
    """sha384 and "repo@ref" of the first public-repo copy of <name>; an exact
    match to served_h wins over the first one found."""
    repo_h = repo_src = None
    for repo in REPOS:
        for ref in REFS:
            data = _get(RAW.format(repo=repo, ref=ref, name=name))
            if data is None:
                continue
            h = _sha384(data)
            if repo_h is None:
                repo_h, repo_src = h, f"{repo}@{ref}"   # first found (fallback)
            if h == served_h:
                return h, f"{repo}@{ref}"               # an exact match wins
    return repo_h, repo_src


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].startswith("http"):
        print(__doc__)
        return 2
    page_url = argv[1].split("#", 1)[0]
    parts = urlsplit(page_url)
    origin = f"{parts.scheme}://{parts.netloc}"

    html = _get(page_url)
    if html is None:
        print(f"FAIL  could not fetch the page: {page_url}")
        return 1
    html = html.decode("utf-8", "replace")

    scripts = list(_SCRIPT.finditer(html))
    if not scripts:
        print("FAIL  no <script src> found -- is this a noodle vote page?")
        return 1

    ok = True
    for m in scripts:
        url, pin = m.group("url"), m.group("pin")
        name = url.rsplit("/", 1)[-1]
        served = _get(origin + url)
        served_h = _sha384(served) if served is not None else None
        repo_h, repo_src = _repo_hash(name, served_h)

        if pin is None:
            ok = False
            print(f"UNPINNED  {url}  (no integrity -- the browser will not enforce it)")
            continue
        agree = pin == served_h == repo_h and repo_h is not None
        if agree:
            print(f"OK        {url}  [{repo_src}]")
        else:
            ok = False
            print(f"MISMATCH  {url}")
            print(f"            page-pin : sha384-{pin}")
            print(f"            served   : {('sha384-' + served_h) if served_h else '(unreachable)'}")
            print(f"            repo     : {('sha384-' + repo_h + '  [' + repo_src + ']') if repo_h else '(not found in any public repo)'}")

    print()
    print("VERIFIED: every script is pinned and matches the public source."
          if ok else
          "NOT VERIFIED: see the lines above. If this is right after a deploy, "
          "the repo may be a commit ahead -- re-run in a minute.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
