"""The two FRONT ENDS (noodle/pages.py SKINS) cannot drift apart.

/noodle and /noodle-tc wear the same templates, JS and Tarid Change structure
(noodle-tc.css); each differs ONLY by a palette sheet. Pinned here:

  - a palette declares custom properties and nothing else, under its own
    class, so a palette cannot grow a rule one front end has and the other
    lacks;
  - every palette declares exactly the --tc-* tokens the structure reads (no
    missing role, no dead one), so a colour role added to noodle-tc.css fails
    here until BOTH palettes say what it is;
  - the pages each front end serves are the same bytes but for its base, its
    palette and its theme-color (and the site nav, /noodle's alone).

The rendered side (same visible text and elements on both) is
test_noodle_browser_tc.py.
"""
import re
from pathlib import Path

import pytest

from noodle import pages

WEB = Path(__file__).resolve().parent.parent / "web"
STRUCTURE = WEB / "noodle-tc.css"

# the one non --tc-* token a palette may set: voter inks to suit its ground
# (noodle-ink.js); a palette that leaves them out keeps noodle.css's
OPTIONAL = re.compile(r"--nd-ink-[0-7]")


def _css(path: Path) -> str:
    return re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)


def _blocks(path: Path):
    """(selector, [declaration, ...]) per top-level rule."""
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _css(path)):
        decls = [d.strip() for d in body.split(";") if d.strip()]
        yield sel.strip(), decls


def _declared(path: Path) -> set[str]:
    return {d.split(":", 1)[0].strip() for _, decls in _blocks(path) for d in decls}


def _structure_reads() -> set[str]:
    """--tc-* tokens noodle-tc.css reads but neither sets itself nor gets from
    the TC scripts (the pip shapes ride in each pip's inline style)."""
    css = _css(STRUCTURE)
    read = set(re.findall(r"var\((--tc-[\w-]+)", css))
    scripts = "".join(p.read_text(encoding="utf-8") for p in WEB.glob("noodle-tc-*.js"))
    return read - set(re.findall(r"(--tc-[\w-]+)\s*:", css)) - set(re.findall(r"--tc-[\w-]+", scripts))


PALETTES = sorted({p for p, _, _ in pages.SKINS.values()})


def test_every_front_end_names_a_palette_sheet():
    assert len(PALETTES) == len(pages.SKINS), "two front ends sharing one palette is one front end"
    for name in PALETTES:
        assert (WEB / f"{name}.css").exists(), name


@pytest.mark.parametrize("name", PALETTES)
def test_a_palette_declares_tokens_and_nothing_else(name):
    path = WEB / f"{name}.css"
    assert "@" not in _css(path), f"{name}.css: no at-rules in a palette (faces go in noodle-tc.css)"
    for sel, decls in _blocks(path):
        assert f".{name}" in sel, f"{name}.css: {sel!r} is not scoped to its own class"
        for d in decls:
            assert d.startswith("--"), f"{name}.css: {sel} sets a property, not a token: {d!r}"


@pytest.mark.parametrize("name", PALETTES)
def test_a_palette_declares_exactly_the_tokens_the_structure_reads(name):
    declared = _declared(WEB / f"{name}.css")
    tc = {t for t in declared if t.startswith("--tc-")}
    reads = _structure_reads()
    assert reads, "found no --tc-* reads in noodle-tc.css: the parse is broken"
    assert not reads - tc, f"{name}.css is missing {sorted(reads - tc)}"
    # a token only a palette uses (one --tc-x built from another) is fine; one
    # that nothing reads is dead
    used = reads | {u for t in tc for u in re.findall(r"var\((--tc-[\w-]+)", _css(WEB / f"{name}.css"))}
    assert not tc - used, f"{name}.css declares tokens nothing reads: {sorted(tc - used)}"
    other = {t for t in declared - tc if not OPTIONAL.fullmatch(t)}
    assert not other, f"{name}.css sets non-palette tokens {sorted(other)}"


def test_the_palettes_declare_the_same_tokens():
    sets = {n: {t for t in _declared(WEB / f"{n}.css") if t.startswith("--tc-")} for n in PALETTES}
    first = next(iter(sets.values()))
    assert all(s == first for s in sets.values()), sets


def _as(page: str, src: str, dst: str) -> str:
    """A page rendered for front end `src`, rewritten as `dst` would serve it
    if nothing but the SKINS entry differed: its base (never the /noodle-tc
    files' names, which both load) and its palette."""
    page = re.sub(re.escape(src) + r"(?![\w.-])", dst, page)
    return page.replace(pages.SKINS[src][0], pages.SKINS[dst][0])


def _vote(base: str) -> str:
    poll = {"slug": "AAAAAAAAAAAAAAAAAAAAAA", "title": "drift", "note": "a note", "e2e": False}
    return pages.vote_page(poll, "", base)


def _strip(page: str) -> str:
    # SRI hashes follow the served files (pages._apply_sri), and only one
    # front end tints the browser bars
    return re.sub(r' integrity="[^"]*"|<meta name="theme-color"[^>]*>', "", page)


def _same(render) -> None:
    # rewrite FROM the longer base: "/noodle-tc" is never part of other text,
    # "/noodle" is part of every file name
    a, b = sorted(pages.SKINS, key=len, reverse=True)
    assert _strip(_as(render(a), a, b)) == _strip(render(b))


def test_both_front_ends_serve_the_same_vote_page():
    _same(_vote)


def test_both_front_ends_serve_the_same_start_page():
    # no request: no site nav (it belongs to /noodle alone, SKINS)
    _same(lambda base: pages.admin_page(None, base))


def test_each_page_loads_the_structure_then_its_palette():
    for base, (palette, _, _) in pages.SKINS.items():
        page = _vote(base)
        tc, pal = page.index('href="/noodle-tc.css'), page.index(f'href="/{palette}.css')
        assert tc < pal, f"{base}: the palette must come after the structure (it is the cascade)"
        assert f'class="noodle noodle-tc {palette}' in page
        assert page.index('src="/noodle-tc-copy.js') < page.index('<link rel="stylesheet" href="/chrome.css')
