# noodle

Standalone Doodle-style scheduling poll at `wai-lau.net/noodle` (start one,
guest tier) and `wai-lau.net/noodle/<slug>` (vote, public by unguessable link).
Full design, crypto and every trap: **ARCHITECTURE.md** (this repo, §21a–m);
incidents: **ARCHAEOLOGY.md**.

---

## RULES — READ FIRST

**A git SUBMODULE of exec-fn at `apps/noodle`** (repo `wai-lau/noodle`, since
2026-10-14). It MIRRORS exec-fn's layout, so the parent finds each piece the
way it finds its own (exec-fn ARCHITECTURE.md §1e):

| Here | Served / loaded as |
|------|--------------------|
| `api/noodle/` (package) | on exec-fn's `sys.path` (`api/app_paths.py`); mounted by exec-fn's `routers.py` |
| `api/templates/noodle-*.html` | read by `noodle/pages.py` (its own loader, `../templates`) |
| `web/noodle-*.{js,css}`, `noodle-card.jpg`, `fonts/noodle-seal.woff2`, `vendor/hash-wasm-*` | flat at `/` (`/noodle-vote.js`, `/fonts/…`, `/vendor/…`) |
| `tests/` | collected by exec-fn's pytest (fixtures: exec-fn's root `conftest.py`) |

**Commit HERE** (`git -C apps/noodle commit …` from exec-fn). exec-fn's push
hook pushes this repo first, then bumps + pushes exec-fn's pointer. Pre-commit
is exec-fn's shared hook (symlinked in): lints, caps, the tests.

**noodle IMPORTS NO OTHER APP MODULE** — not exec-fn's, not another app's.
Pinned by `tests/test_noodle_isolation.py` (the module list is DERIVED from
exec-fn's `api/` + every other `apps/*/api`). The owner tier, nav and owner
detection are INJECTED by exec-fn's `routers.py` (`set_nav`, `set_owner`).
What it does use from exec-fn is by URL only: `/chrome.css` tokens,
`/fonts/iosevka-500.woff2`, `/qc-holidays.js` (shared with /rd), `/favicon.png`.

**`?v=` needs no bumping**: exec-fn fills every `?v=` in an HTML response with
the served file's content hash (`asset_version.py`, exec-fn §13c).

**State is encrypted at rest, keyed by the link** (`data/noodle/polls/` in
exec-fn's `api/data`): HKDF(slug) names the file and is the AES-GCM key; the
server stores no links. **Polls started since 2026-10-09 are end-to-end** (key
in the `#k=` fragment, never sent). §21d, §21m.

**The `<link>`/`<script>` ORDER in the noodle templates is the cascade and the
init order** (`noodle-vote.js` runs `ndvInit` as it loads). One CSS/JS file per
page part.

**Owner key reset** (the package now lives in the submodule, so run it there):
`docker compose exec -w /app/apps/noodle/api api python -m noodle.reset <slug> "<name>"`.

**Every non-ASCII glyph is single-width** via `web/fonts/noodle-seal.woff2`
(cut from exec-fn's full Iosevka; `tests/test_noodle_glyphs.py`).

**Docs rule**: this file is an INDEX; measurements, traps and stories go in
ARCHITECTURE.md / ARCHAEOLOGY.md.
