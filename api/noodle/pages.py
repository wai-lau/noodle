"""noodle's HTML. Its own shell (api/templates/noodle-shell.html), NOT the
site's page composer -- no Exec bubble, no CRT stack, and no import of the
app's pages module; the nav is handed in (set_nav), never built here. It links /chrome.css only for the palette + scale
tokens, which are CSS, not code."""
import base64
import hashlib
import html
import json
import re
from pathlib import Path

from noodle import config

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _tmpl(name: str) -> str:
    # read per request, like the rest of the site's templates (live edits)
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _fill(text: str, **values: str) -> str:
    # ONE pass, so a value (a poll title, say) that itself contains "{{X}}"
    # is never substituted into.
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), text)


# The LINK PREVIEW (Open Graph; what Messenger, iMessage, Discord, Slack draw
# under a pasted link): the poll's title, its note (or a default), and one
# fixed dark card -- the site icon it fell back to is white on transparent,
# which a light preview draws white on white. Scrapers cache it for weeks.
def _og(title: str, desc: str, path: str) -> str:
    tags = [("og:title", title), ("og:description", desc or config.OG_DESC),
            ("og:image", config.ORIGIN + config.OG_IMAGE), ("og:image:width", "1200"),
            ("og:image:height", "630"), ("og:url", config.ORIGIN + path),
            ("og:type", "website"), ("og:site_name", "noodle")]
    out = [f'<meta property="{k}" content="{html.escape(v, quote=True)}">' for k, v in tags]
    return "\n".join(out + ['<meta name="twitter:card" content="summary_large_image">'])


def _page(title: str, body: str, og: str = "") -> str:
    return _fill(_tmpl("noodle-shell.html"), TITLE=html.escape(title), OG=og, BODY=body)


# SUBRESOURCE INTEGRITY for the vote page (noodle ARCHITECTURE.md 21m, "code
# verification"): a sha384 on every <script src> so a link holder can check the
# code their browser ran against the public repo. noodle imports no app module,
# so it cannot resolve a parent-served script (qc-holidays.js) on its own -- the
# composition root hands it a resolver (url -> served bytes), like set_nav. The
# hash is the served FILE's; computed per render (files are small, served live).
_sri = None   # (url: str) -> bytes | None


def set_sri(fn) -> None:
    global _sri
    _sri = fn


_SRI_SRC = re.compile(r'(<script\b[^>]*\bsrc=")(/[^"?]+\.js)((?:\?[^"]*)?")([^>]*>)')


def _apply_sri(page: str) -> str:
    # No resolver (standalone / isolation): leave the page untouched -- it still
    # works, just unpinned. Never let a missing/odd file break the page.
    if _sri is None:
        return page

    def repl(m: re.Match) -> str:
        if "integrity=" in m.group(0):
            return m.group(0)
        data = _sri(m.group(2))
        if not data:
            return m.group(0)
        h = base64.b64encode(hashlib.sha384(data).digest()).decode()
        return f'{m.group(1)}{m.group(2)}{m.group(3)} integrity="sha384-{h}"{m.group(4)}'

    return _SRI_SRC.sub(repl, page)


def _kdf_attrs() -> str:
    kdf = {"m": config.KDF_M_KIB, "t": config.KDF_T, "p": config.KDF_P,
           "len": config.KDF_LEN, "debounce": config.KDF_DEBOUNCE_MS}
    return html.escape(json.dumps(kdf), quote=True)


def vote_page(poll: dict, draft: str = "") -> str:
    # an END-TO-END poll's title and note are sealed (e2e.py): the server has
    # none to write, so the page and its link preview say just "noodle" and
    # the browser fills the real ones in once it has opened them. A draft
    # still shows the placeholder the host types over.
    sealed = bool(poll.get("e2e"))
    shown = poll.get("title", "") if draft or not sealed else ""
    note = "" if sealed else poll.get("note", "")
    body = _fill(
        _tmpl("noodle-vote.html"),
        SLUG=html.escape(poll["slug"], quote=True),
        DRAFT=html.escape(draft, quote=True),
        E2E="1" if sealed else "",
        TITLE=html.escape(shown),
        NOTE=html.escape(note),
        KDF=_kdf_attrs(),
        ASK_MAX=str(config.ASK_MAX_CHARS),
    )
    og = _og("noodle" if sealed else shown, note, "/noodle/" + poll["slug"])
    page = _page("noodle" if sealed else f"noodle: {shown}", body, og)
    # Mirror the vote-page CSP (sent as a header by routes) into a <meta> in the
    # <head>, so the "no inline/eval scripts" rule is IN the bytes a link holder
    # verifies -- the browser enforces it even if a hostile server strips the
    # header, and its absence from the served HTML is itself the tell. Only the
    # vote page gets it (the /noodle admin page runs the site nav's inline script).
    # VOTE_CSP_META is a trusted constant (no < > & "); keep the quotes literal
    # so the policy reads cleanly in View-Source. Guard a stray " just in case.
    meta = f'<meta http-equiv="Content-Security-Policy" content="{config.VOTE_CSP_META.replace(chr(34), "&quot;")}">'
    page = page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + meta, 1)
    return _apply_sri(page)


# The site's nav bar, HANDED IN by the app (routers.py set_nav): noodle
# imports no app module, so it cannot build the nav itself -- the composition
# root gives it a function (request -> markup) instead. Unset, no nav.
_nav = None


def set_nav(fn) -> None:
    global _nav
    _nav = fn


# Whether a request is the OWNER's, handed in the same way (request -> bool).
# Unset, nobody is.
_is_owner = None


def set_owner(fn) -> None:
    global _is_owner
    _is_owner = fn


def admin_page(request=None) -> str:
    body = _tmpl("noodle-admin.html")
    page = _page("noodle", body, _og("noodle", "", "/noodle"))
    if _nav and request is not None:
        page = page.replace('<body class="noodle">', '<body class="noodle with-nav">', 1)
        page = page.replace("</body>", _nav(request) + "</body>", 1)
    return page


def public_poll(poll: dict) -> dict:
    """What anyone holding the link may see: window, and each voter's name,
    public key and slots. Never a budget counter, never anything secret (the
    server holds no secret -- the passphrase never arrives)."""
    # The name shown is the voter's KEY (the normalized name), not whatever
    # casing a vote stored before names were lowercased -- one identity, one
    # spelling.
    voters = sorted(poll["voters"].items(), key=lambda kv: kv[1]["order"])
    return {
        "slug": poll["slug"], "title": poll["title"], "note": poll.get("note", ""),
        # split into midday + night, or one slot a day; polls from before the
        # host could choose were all split, so a missing key means split
        "halves": poll.get("halves", True),
        # the host's crop: the first and last day anyone can pick (null: endless)
        "crop": {"from": poll["from"], "to": poll["to"]} if poll.get("from") else None,
        "voters": [{"name": key, "pub": v["pub"], "slots": v["slots"],
                    "order": v["order"]} for key, v in voters],
        # the first to commit hosts: their halves are the only ones on offer
        "host": voters[0][0] if voters else None,
    }
