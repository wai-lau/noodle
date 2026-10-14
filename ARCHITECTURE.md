# noodle — ARCHITECTURE

Moved out of exec-fn's ARCHITECTURE.md (§21) on 2026-10-14, when noodle became its
own repo (`wai-lau/noodle`), consumed by exec-fn as the submodule
`apps/noodle`. A bare `§N` below (other than §21's own subsections) means a
section of **exec-fn's** ARCHITECTURE.md; how the parent serves this app is
exec-fn §1e.

## 21. noodle — an isolated scheduling poll

A Doodle-style poll at `/noodle/<slug>`: slots are `(date, midday|night)`, or
on an unsplit poll `(date, whole day)` — no clock times. **Fully
standalone**: `api/noodle/` imports stdlib, fastapi, pydantic, `anthropic`
and `cryptography` only, never another app module (pinned by
`tests/test_noodle_isolation.py`). Its own state directory, its own HTML
shell (no Exec bubble, no voice; the site nav only on `/noodle`, handed in
by `routers.py` via `pages.set_nav`), its own routes; it links
`/chrome.css` for palette + scale tokens only. Three bare routers carry it —
`routers.py` mounts `routes.router` on `public`, `routes.guest_router` on
the guest tier, `routes.owner_router` on `protected`; noodle itself holds no
auth. The browser derives an Ed25519 key from the passphrase
(`noodle-kdf-worker.js`) and sends only `{name, pub, slots, ts, sig}`.

### File map

**Server** (`api/noodle/`), wired in by exec-fn's `api/routers.py`:

| File | What |
|---|---|
| `routes.py` | 3 routers: `router` (public — poll page/JSON, vote/settings/remove/rekey/ask), `guest_router` (`/noodle` + `POST /api/noodle-polls/new`), `owner_router` (list/create/delete + the per-day counts). |
| `pages.py` | HTML shell, Open Graph, KDF config as `data-*`, demo-video markup, `set_nav`/`set_owner` injection points. |
| `store.py` | One JSON file per poll under `DATA_DIR/polls/`; the one lock; atomic writes. |
| `drafts.py` | A poll that doesn't exist yet: HMAC token, `ensure()` (-> whether it created one). |
| `stats.py` | Polls created per day, `DATA_DIR/created.json` = `{"YYYY-MM-DD": n}`, for the owner's chart (21i). |
| `votes.py` | `VoteError`, `now_ms`, `check_action` (shared signed-action envelope), `host_of`, `_admit`, `submit`. |
| `host.py` | Host-only: `settings` (split/crop/title/note), `remove`. |
| `rekey.py` | Passphrase/name change: old key signs the new one. |
| `e2e.py` | END-TO-END polls (21m): sealed vote/head/remove/rekey + `public()`; the server never holds their key. |
| `sig.py` | Ed25519 verify, `canonical()` / `canonical_action()`. |
| `slots.py` | `normalize_name`, `codes`, `parse_window`, `clean_slots`, `convert`. |
| `rules.py` | Ask noodle's rule language + `apply()`. |
| `ask.py` | Rate limits, prompt assembly, `ask()`. |
| `llm.py` | Haiku client + `SLOT_TOOL` schema. |
| `holidays.py` | Quebec holidays — Python mirror of exec-fn's `web/qc-holidays.js`. |
| `config.py` | Every knob (KDF params, caps, rate limits). |
| `reset.py` | Owner CLI: `python -m noodle.reset <slug> "<name>"`. |

**CSS** (`web/`), loaded in this order by `noodle-shell.html` — **the load
order is the cascade**: `noodle.css` (font-face, shell, title/note,
host/guest wording) → `noodle-identity.css` (fields, seal, you -> pick step) →
`noodle-actions.css` (Ask, banner, Commit, lock states, share) →
`noodle-roster.css` (voter faces) → `noodle-split.css` (split checkbox) →
`noodle-admin.css` (`/noodle` page) → `noodle-created.css` (the owner's chart) → `noodle-foot.css` (top dates + foot
links) → `noodle-cal.css` (grid).

**JS** (`web/`), loaded in this order by `noodle-vote.html` — **order
matters**: `noodle-vote.js` runs `ndvInit()` as it loads, so everything it
calls must already be loaded: `qc-holidays` → `noodle-toggle` →
`noodle-seal` → `noodle-cal` → `noodle-cal-view` → `noodle-kdf` (+
`noodle-kdf-worker`) → `noodle-esc` → `noodle-roster` → `noodle-crop` →
`noodle-keystore` → `noodle-storage` → `noodle-identity` → `noodle-claim` → `noodle-e2e` → `noodle-commit` → `noodle-vote` →
`noodle-ask` → `noodle-host` → `noodle-rekey` → `noodle-top` →
`noodle-share`. `/noodle` (`noodle-admin.html`) loads only `noodle-claim` +
`noodle-admin` + `noodle-created`.

**Templates** (`api/templates/`): `noodle-shell.html` (shared shell —
`.page-scroll` wrapper, OG slot; **no CRT stack**, removed 2026-10-03 on
user feedback: noodle is the site's one plain page),
`noodle-vote.html` (poll body + scripts), `noodle-admin.html` (`/noodle`
body + its 2 scripts).

**Tests** (`tests/test_noodle_*.py`): unit — isolation, crypt (at rest), votes,
host, rekey, drafts, ask, rules, holidays, names, convert, toggle, glyphs,
limits, stats, legacy, hardening, e2e, e2e_view. Browser (WebKit/Playwright) —
`test_noodle_browser.py` (sign/vote), `_page` (ask/storage/share/top-dates/
pick-note), `_host` (host tools), `_keys` (kept keys), `_created` (owner chart),
`_e2e`, `_signed`, `_csp`, `_journey`; shared helpers in
`tests/noodle_helpers.py`. exec-fn's side: the `noodle_slug` fixture (root
`conftest.py`), smoke rows in exec-fn's `tests/test_smoke.py`.

### 21a. Access tiers & routes

Nothing in `api/noodle/` imports `auth.py` — tier enforcement lives
entirely outside the package (exec-fn's `tests/test_admin_only.py` enumerates
`owner_router` like any other admin route). Holding the link is the only
access control for **voting**: the slug is `secrets.token_urlsafe(16)` (22
chars, `[A-Za-z0-9_-]`), validated to that exact shape (`store._SLUG_RE`)
before it becomes a path component. `GET /noodle/{slug}/results` 301s to
the vote page — there is no separate results page (21f).

Starting a poll is guest-tier: any guest behind Turnstile may create a
draft. Owner-only, API-only (no page shows them since 2026-10-13): the
poll list, creating one directly with a title (`POST /api/noodle-polls`),
and deleting. The owner's OWN `/noodle` page
doesn't use that titled endpoint either — `ndmCreate` calls the same
`.../new` a guest would, so the owner's poll also starts as an untitled
draft; the titled endpoint is direct-API/script only.

Every body is capped and checked on both declared `Content-Length` and
actual bytes read: `BODY_MAX_CREATE` 1024, `BODY_MAX_VOTE` 8192,
`BODY_MAX_ASK` 1024 bytes. Every vote page sends `X-Robots-Tag: noindex` +
`Referrer-Policy: no-referrer`, so a slug never leaks via Referer (`/noodle`
sends `no-store` + its framing CSP only, 21m).

### 21b. Identity: passphrase -> key -> seal

`noodle-kdf.js` debounces `KDF_DEBOUNCE_MS` (1000ms) after typing stops,
then a Worker runs Argon2id (hash-wasm 4.12.0, vendored under
`web/vendor/`, MIT) to a 32-byte seed, wrapped in the fixed RFC 8410 PKCS#8
prefix (WebCrypto has no raw-seed import) and imported as Ed25519. The
signing key is **non-extractable**; an extractable copy exists only long
enough to read the public half out of its JWK. Salt =
`SHA-256(slug + NUL + normalized name)[:16]` — same name+passphrase, same
key on any device; different key per poll. Only one derive ever runs: a
change mid-derive **terminates the worker** (Argon2 can't be interrupted)
and a generation counter drops stale results. KDF params (`config.KDF_*`:
m=65536 KiB, t=2, p=1, len=32) reach the page as `data-kdf` so page and
config can't disagree — measured ~360ms in node on the droplet, ~560-680ms
in headless WebKit; retune `KDF_T` after measuring on a phone.

**Name normalization must match byte for byte** between `slots.normalize_name`
and `noodleNormName` (the browser salts the KDF with it, the server binds
by it): NFKC, reject `Cc`/`Cf`, collapse whitespace, lowercase, then ASCII
letters/digits/spaces only — the page strips anything else as typed, over
the known Unicode divergence points (`tests/test_noodle_names.py`; lookalike
scripts stay unmerged). Names are lowercased as typed and stored normalized
— identity was already case-blind, so this changed no key; it only stopped
first-typed casing making one person look like two.

**The seal** (`noodle-seal.js`, ONE implementation for a voter's own seal
and every roster seal): everything — the 18 border-punctuation cells, the
eye pair, the mouth, and the HSL ink — is picked deterministically from
`fp = SHA-256(raw pubkey)`, byte by byte (no modulo bias: 256 divides
evenly into each choice set). Ink hue is unconstrained but lightness has a
floor (62-82%) so every seal reads on black regardless of hue; it reaches
CSS as the page-local `--seal-hsl` token (exec-fn's `scripts/lint-colors.py`
`LOCAL_ACCENTS`) and also colours that voter's calendar dots.

**One section edits at a time** (`ndvStep`/`ndvPaintStep` in
`noodle-identity.js`, feedback 2026-10-03): `#nd-you` (name + passphrase +
seal) then `#nd-pick` (calendar, Ask, Commit). The host's title/note are
editable on EITHER step (Wai, 2026-10-03: naming the poll goes with naming
yourself) -- still sent only with Commit. `NDV.step` is
`'you'|'pick'`; `.nd-step-pick` on `#noodle` folds YOU to one line ("you
are <name> [edit]", in the seal's ink). On the you step the pick is a grey
read-only preview (`ndvSyncLock`'s `open` requires the pick step) and
Commit/why/dirty/split are hidden; `#nd-next` (or Enter in either field)
advances once a name is typed. A saved identity that unlocks skips straight
to the pick (`NDV.autoStep`); a name that turns out sealed by another key
falls back to YOU; tapping a roster face returns to YOU. Rekey: `change` is
on YOU, Commit (on the pick) carries it. The step init (`ndvStepInit`) is
called from `ndvInit` -- `noodle-identity.js` loads BEFORE `NDV` exists, so
an IIFE there throws. Browser tests advance with
`ndvCanNext() && ndvStep('pick')` inside their unlock waits. The title has the
placeholder "title" (not "untitled noodle") and the field is labelled "your
name" -- which was the group's name and which the voter's was unclear. The
Ask box's text is `--fs-2xs`, under iOS's 16px focus-zoom line, so the
noodle shell's viewport carries `maximum-scale=1` (iOS still pinch-zooms;
Android does not on noodle pages -- accepted).

**UI audit 2026-10-03** (all applied): the argon2id recipe box is GONE --
the seal + caption sit centred under the fields (`.nd-seal-row`, hidden
until a name is typed); `#nd-next-why` above "next" gives the reason it is
grey (`ndvNextWhy`, the identity half of `ndvWhyNot`; a key still deriving
does not hold it); the host's not-yet-offered days are dim green and NOT
struck (only past / out-of-crop days are); the crop grips sit at `left:
20px` in the week column, off the dates; the foot links are plain dim
underlined links, not buttons that out-shout Commit; the note has no dashed
line of its own; "help me" is its label's height; one passphrase hint for
both roles; the pick note reads "when are you free? (everyone can see)".

**A name sealed by another key locks the page** (`ndvSyncLock`): calendar,
Ask and Commit go grey + `inert` (`.nd-locked`), the caption reads
`NOT <name>'s seal of approval`; only identity fields and voter faces stay
live.

### 21c. Votes, the host, rekey, drafts

**Votes.** `votes.submit()` runs every stateless check (name/ts shape,
`TS_SKEW_MS`=120s window, Ed25519 over `sig.canonical(poll,name,slots,ts)`)
before the store lock; only binding + replay need the file. Signed bytes:
`json.dumps({name,poll,slots,ts}, sort_keys=True, separators=(",",":"),
ensure_ascii=False)` — `ndvSubmit` reproduces this by inserting keys in
sorted order before `JSON.stringify`. `ts` must be inside the skew window
AND strictly newer than the last accepted one for that key (a replay
inside the window still fails); the page reads the server's clock off the
`Date` header (`NDV.skew`). First submission for `(poll, name)` binds a
pubkey; every later one must verify under the same key (an empty stored
`pub` means the owner reset it). `votes.host_of()`: vote order 0 is host,
their picked slots ARE the offer — enforced server-side (`_admit`) and
client-side (`setAllowed`); `_trim_guests` trims every guest's slots to a
new host offer in the same write, so a time the host drops disappears from
every guest's dots too.

Recovery is owner-only and forgets the key, not the vote:
`docker compose exec -w /app/apps/noodle/api api python -m noodle.reset <slug> "<name>"`
blanks `pub`/`ts`; slots and dot-column `order` are kept, and the next
signed submission re-binds whatever key signs it.

**The host & host actions.** Whoever acts FIRST on a fresh poll — a vote,
or `host.settings` — becomes host (order 0). Every host action shares
`votes.check_action()`: name+ts shape, the skew window, and
`sig.canonical_action()`, whose mandatory `kind` field stops a vote from
ever being replayed as a host action or vice versa. `host.settings()` sets
split/crop/title/note in one signed request; on a poll with no voters yet
it plants the caller as order 0. Flipping `halves` re-expresses every
voter's slots via `slots.convert()`; narrowing the crop drops out-of-crop
slots from every voter at once. `host.remove()` (`_as_host`) deletes a
guest's whole record; a host can never remove themself. The client mirrors
the envelope exactly (`ndhSend`/`ndhCanon`): sorted-key signature, `kind`
stripped before sending (the server supplies it).

**Rekey.** A name is bound to the key its first vote signed with, derived
from name AND passphrase together, so changing either is a re-bind only
the CURRENT key may make: `canonical_action(kind="rekey", name, newname,
newpub, poll, ts)` signed by the OLD key (`rekey.rekey`). The server checks
the old key against the bound record, requires a strictly newer `ts`,
refuses a `newname` someone else holds (409), then moves the whole record
(slots, order, host role) to the new key+name. Client (`NDR` state,
`noodle-rekey.js`): tapping `change` keeps the old name+passphrase in
memory, spawns a **second** KDF worker (`NDR.keeper`) to re-derive the old
key so it can still sign, and turns the button into `undo` — **Commit
carries the change**, no separate confirm. `ndrAs(pub)` answers "which key
does the server think I am" everywhere on the page; `ndrCommit(ts)` sends
the rekey first, then pending settings, then the vote, each strictly
newer. **Mid-change the OLD key stays live and keeps acting**: `ndhSend()`
signs with `NDR.keeper`/`NDR.oldPub` whenever `NDR.active`, so a host
partway through a passphrase change can still remove a guest or save
settings, signed by the key the server still recognises as theirs.

**Drafts.** `POST /api/noodle-polls/new` (guest tier, `NEW_RATE`=20/
`NEW_WINDOW_S`=3600 per IP) stores nothing: a fresh slug + an HMAC token
(`drafts.token`, `NOODLE_SECRET` or a generated `DATA_DIR/secret.key`,
0600) bound to the body's `{claim}` (400 without one -- 21m), and the page
opens at `/noodle/<slug>?t=<token>#k=<key>` with an empty poll standing in. The host's first commit carries the token as an unsigned
`draft` field; `drafts.ensure()` writes the poll (idempotent
`store.try_create`) inside that request, then the page drops `?t=`. Without
the exact token for that slug nothing is ever created, so an abandoned
"create" leaves nothing and nobody can mint a poll on a slug of their
choosing.

### 21d. Concurrency & storage

**Old polls keep the old rules** (owner, 2026-10-14: "don't break old polls, keep them as special cases"). Every poll created since carries a rules stamp `"v": 2` (`store.RULES`); one without it is OLD (`store.legacy`), and wherever a new rule could refuse or hide something an honest voter does, an old poll is exempt: no seat cap, no file-size cap, no write rate limit (`routes._throttled` skips it), an end-to-end poll with no claim seats its first voter as host as it always did, and `e2e.public` marks it `legacy` so its pages show unsigned records and never go strict or cap the seats they open. Rules that only ever stop an attacker apply to every poll (tombstones, small-order keys, surrogate-safe signing, signature checks on records that HAVE one, log masking, headers, CSP, kept keys). Pinned by `tests/test_noodle_legacy.py`. The cost, accepted: an old poll's slug is still enough to flood that one poll.

**Abuse bounds on writes** (2026-10-14, after a security audit showed a slug
alone could add junk seats without end, each write re-sealing the whole file
under the one lock -- 1,500 seats = a 12 MB file, 327 ms lock holds): a poll
seats at most `MAX_VOTERS` = 200 keys (a NEW key past it gets 409 "this poll
is full"; a seat already there always re-votes), its sealed file never
passes `POLL_FILE_MAX` = 2 MB (`store.TooBig` -> 413), and every signed write
(vote / settings / remove / rekey) is rate-limited per IP (60 / 10 min) and
per poll (300 / h) by `noodle/limits.py` (429 + `Retry-After`; the test
suite's exemption skips it). **Reads never take the lock**: `store._migrate`
checks for a pre-encryption file before locking, so a load cannot queue
behind another poll's write. The page opens at most 250 seats
(`NDE_MAX_SEATS`), so a flooded poll cannot freeze it.

**Encrypted at rest, keyed by the link** (since 2026-10-08). The slug (128
random bits, already the only access control) goes through HKDF-SHA256
(salt = 32 zero bytes) twice: info `noodle poll file v1` -> the FILE id
(`polls/<64 hex>.json`), info `noodle poll key v1` -> an AES-256-GCM key.
Neither is stored; the id gives back neither slug nor key. A file is
`{"v":1,"nonce","ct"}`, fresh nonce per write, the file id as associated
data (a blob moved under another poll's name fails to open). The server
can open a poll only while a request carrying its link is in flight; a copy
of `data/noodle/` (backup, leaked disk, root browsing) is noise. On its
own this is NOT end-to-end -- a compromised RUNNING server sees each slug
as it arrives -- which is why every poll started since 2026-10-09 is ALSO
end-to-end (21m), sealed inside this layer. Only `store.py` changed for it
-- everything above it still gets a dict.
Changing either HKDF label orphans every poll.
Pre-encryption `<slug>.json` files are sealed on first touch
(`store._migrate`) or all at once by `store.migrate_all()` (run on the
droplet 2026-10-08: 8 polls).

One file per poll under `DATA_DIR/polls/`. **One
process-wide `threading.RLock`** (`store._LOCK`) guards every
read-modify-write; `store.edit()` is load → yield → write, raising inside
skips the save. Every write is `mkstemp` + `fsync` + `os.replace` — fsync
before the rename, so a crash mid-write can't corrupt it. The slug is
checked against its exact generated shape before ever touching the
filesystem.

**Checks that depend on current poll state are re-run INSIDE the lock, not
just before it** (`votes._admit`) — two races found the hard way: the
**crop** (a pre-lock read can be a copy a concurrent narrowing already made
stale), and the **split** (a host flipping `halves` between a vote's
pre-lock shape-check and its write would otherwise convert every stored
slot mid-flight; `_admit` re-checks the slot codes inside the lock and
409s — "the poll's days were just split or joined" — instead of writing a
vote in the wrong shape).

Client-side, `NoodleCal().destroy()` disconnects the calendar's
`ResizeObserver`/`IntersectionObserver` before `ndvEnsureCal` builds a
fresh grid — every split flip or crop drag used to leave the OLD
observers, and the detached grid they watched, alive for the page's life.
One process-wide lock across every poll is a known trade-off: no
correctness issue, just no cross-poll write parallelism.

### 21e. The calendar

`noodle-cal.js` (pure geometry — `ndIso`/`ndHalf`/`ndAddDays`/`ndRowHtml`/
`ndDotsHtml`/etc, as `window.NoodleCalParts`) + `noodle-cal-view.js`
(`NoodleCal()`, the stateful controller), styled by `noodle-cal.css`. ONE
continuous vertical scroller of Sunday-first weeks, /rd's visual language
(5px rules, bold dates, cyan weekends). `.nd-cal-wrap` sits at `--z-top`:
on a poll page `.page-scroll` goes static (the document scrolls, its
scrollbar hidden) and the card's z-index goes auto, and the banner +
"approved by" stamp go to `--z-max` so the calendar never covers them. That
layering was built to rise over the CRT stack, which noodle no longer has
(2026-10-03); it stays because the sticky/crop z-indices are tuned to it.

**Endless unless bounded by a crop.** Opens on `NDC_FIRST`=12 weeks, appends
`NDC_MORE`=8 as a sentinel scrolls into view — via both a `scroll` listener
AND an `IntersectionObserver` (the observer alone stalls: it fires only on
a visibility CHANGE, so a batch landing while the sentinel is still
visible never triggers again) — caps at `NDC_MAX`=160 weeks (~3 years,
`SLOT_YEARS_AHEAD`). The HOST's calendar is always endless (crop handles
need room to drag anywhere); a GUEST's renders only the host's offered
span, no scroll inside the page (`ndcCapHeight` caps only an endless
calendar to `NDC_VISIBLE`=6 weeks, measured from a real row).

Each cell's background splits on a 30° line through its centre (`ndHalf`,
top-left=midday, bottom-right=night) on the **host's** grid, hit-tested the
same way a tap lands. A **guest's** cell instead draws two right-angle
triangles (`.nd-tri`, CSS `clip-path`) for the halves actually offered,
since the split line alone can't show that; guest taps hit-test the same
diagonal.

**Dots**: every voter — you included — owns ONE fixed column by vote order
(top dot midday, bottom night, a gap where not free), so one person reads
as one vertical line down the grid. Dots are **6px** (`ND_DOT` in
noodle-cal.js mirrors `.nd-dots` in noodle-cal.css -- change both); 4px read
as specks over a picked half (feedback 2026-10-03). Your own column is a `self` entry
showing your LIVE selection, not your last-saved vote. Overflow gets /rd's
hollow ring; your own column is never the one cut.

**Months: a name and a shade, no divider line.** Each month's name runs
vertically in the week column, right of the fill/erase buttons
(`ndcPaintLabels`, `.nd-mlabel`; the column is 56px = 40px of buttons + 16px
of name), spanning its own run of weeks (a week belongs to its Wednesday's
month): the longest of `october 2026` / `october` / `oct` that fits the run
with `NDC_LABEL_SLACK`=16px to spare, re-fitted once `document.fonts.ready`
(measured in the narrower fallback font, "september 2026" overran into the
header). Names share the week column's z and the crop box's, so DOM ORDER
decides, and every repaint keeps it rows -> names -> `.nd-cropbox` (append
the names, then move the box last): weeks loaded later once put their black
week cells over "october", and a box before the names left them undimmed.
**Past days are unavailable**: `NoodleCal.setSel` drops any slot before
today and `ndvPresent` drops them from the saved copy (so a stored past pick
is no unsaved change); the next Commit clears them from the stored vote. Even months' cells
carry `.alt` (`noodle-cal.js`): a `::after` of the rules' own green 0.12 laid
twice, behind the cell's fill -- brighter than the rules so they still show,
no new colour step (0.06 was too close to black to tell months apart). This
replaced a blurred month-number watermark behind the cells and a stepped
month divider line.

Quebec statutory holidays tint like
weekends (`.hol`, from exec-fn's `qc-holidays.js`, shared with /rd; `noodle/holidays.py` mirrors
it).

**Toggles** (`noodle-toggle.js`, pure, node-tested): a weekday column or
week row is a MODE button — pencil (fill) or eraser (clear) — never a
reading of current cell state; the grid's corner flips every button at
once, and row/column buttons start OFF (hidden until the corner is tapped
once). Every toggle/mode/copy glyph exists ONLY in
`web/fonts/noodle-seal.woff2` under family `'Noodle Glyphs'`, named FIRST
in the stack — with the mono font alone the icons render as nothing (21j).

The **split** checkbox (host-only) sits on the calendar's first row (the
always-past week above today), placed INSIDE the grid so it scrolls with
it, and is detached before every rebuild or the rebuild destroys it.

**The crop** (`noodle-crop.js`, `NDX`): host-only, no button — two
draggable grip lines (`.nd-crop-h`) on the endless calendar's top/bottom
edges. The top line can't be dragged above THIS week (`ndxTopMin`); a crop
line resolves to a real calendar DATE (`ndxRowOf`), not a "last loaded
row", so it never runs away as weeks load. Cropped-off weeks are shaded
(`.nd-shade`, `backdrop-filter: grayscale(1) brightness(0.55)` — headless
WebKit won't composite `backdrop-filter` into screenshots, verify in
Chromium). A truly fresh poll auto-sets a pending crop of this week plus
`NDX_SPAN`=2 more, saved with the host's first Commit. A dropped crop line
sends nothing itself; Commit sends it with the split via `POST /settings`,
then the vote, each strictly newer.

### 21f. The vote page

**Read-only until the key is yours.** `.nd-off` (grey, calendar still
SCROLLS, no `inert`) applies with no name, a key still deriving, or a
voter's name with no passphrase entered yet; `.nd-locked` (grey AND
`inert`) applies once the typed name is sealed by someone ELSE's key
(`ndvSyncLock`).

Commit is disabled with the reason ALWAYS shown underneath (`ndvWhyNot`: no/
bad/taken/sealed name, no key yet, or — for a host — nothing picked) — a
disabled button with no stated reason reads as broken. It reads `Commit*`
whenever the calendar or any pending split/crop/title/note/rekey differs
from what the server holds for the current key (`ndvDirty`).

**Every error goes to ONE fixed banner** (`#nd-banner`, `ndvBanner`) rather
than a line beside whatever raised it, off-screen as often as not; it
persists until replaced and its text is selectable for a bug report.
Non-error status ("committed.") is a separate line above the calendar,
cleared on every reload.

The poll's link (`noodle-share.js`) appears once the host has offered
something, as read-only text under Commit with a copy button (falls back
to select-for-manual-copy). The HOST's Commit also copies the link,
started inside the tap itself (Safari revokes clipboard permission after
an `await`), capped to 800ms so a stuck write can't hold up the "approved"
popup.

**Top dates** (`noodle-top.js`): every slot at least one NON-host voter
picked (the host's own offer alone isn't a "result"), ranked by vote count
then soonest, read live off the calendar's own dot columns. One row per
slot — a glyph (sun/moon, split polls only) + date, then a fixed
one-column-per-voter dot row matching the calendar's column order.

Foot: "make another noodle" (host) / "make your own noodle" (guest), then
a `mailto:` bug-report link — driven by one class, `.nd-as-host`
(`ndhTitleMarks`), never per-string branching. Both stay LINKS but are drawn
as smaller Commit buttons (`noodle-foot.css .nd-another a`, `--fs-2xs`).

### 21g. Browser storage

`localStorage` and IndexedDB, **deliberately never a cookie** — a cookie
rides on every request. **The passphrase is never stored at all** (since
2026-10-14, security audit: it sat in localStorage in plain text, readable by
any script that ever ran on this origin, and people reuse passphrases). What
is kept is the KEY it made: the worker's non-extractable Ed25519 `CryptoKey`,
structured-cloned out (`NoodleKdf.key()`) into IndexedDB `noodle`/`keys`,
id `<slug>\0<name>` -> `{key, pub}` (`web/noodle-keystore.js`). A script on
the origin could USE it here but never read it out. It is kept once PROVEN
(the derived key matches the voter's seat, `ndvOnDerived` -> `ndvRememberKey`,
or a commit lands). Next visit: an EMPTY passphrase field over a name with a
kept key signs as that key (`NoodleKdf.use`, no Argon2), the field shows
"kept on this device", locked like a right passphrase. The name restores at
once; the kept keys load a moment later and re-check the identity unless the
voter has typed (`NDV.touched`). Renaming over a kept key opens the
passphrase field too ("your passphrase (same or new)" -- the page never
knew it); a passphrase change signs with the kept key (`NDR.keeper.use`); a
committed change keeps the new key and drops the old name's.

| Key | Holds |
|---|---|
| `noodle.identity` | last-used NAME only (travels between polls), no passphrase |
| IndexedDB `noodle`/`keys` `<slug>\0<name>` | that name's KEPT signing key on this poll (above) -- never a passphrase |
| ~~`noodle.pass.<slug>.<name>`~~ | written by pages before 2026-10-14: that name's passphrase in plain text. Still fills the field ONCE on this poll; when its key proves to be the seat it becomes a kept key and the entry is deleted |
| ~~`noodle.lastpass.<name>`~~ | the cross-poll passphrase fallback: gone, every entry deleted on load |
| `noodle.draft.<slug>.<name>` | unsaved calendar picks + a host's unsaved title/note |
| `noodle.ask.<slug>.<name>` | the Ask textarea text (a Commit leaves it alone) |
| ~~`noodle.polls`~~ | Gone 2026-10-13 with `/noodle`'s poll list (21i): it held every opened poll's link, `#k=` key included; `noodle-storage.js` now removes it on load |
| `noodle.blankSeal.<slug>` | 32 random bytes made once per browser per poll, so the empty "you" seat wears the same placeholder seal every visit |

A draft outranks the submitted vote on reopen (it's the newer of the two);
a successful Commit clears EVERY draft the poll holds — any identity's —
since a stale draft under an earlier key used to beat the freshly-saved
vote once that seal matched again.

### 21h. Ask noodle

**Works on the PAGE's state, never the server's.** `ask.ask()` takes the
dates the caller says are pickable right now plus whether the poll is
split, and never reads or writes a poll (pinned by a test that patches
every `store` function to raise) — a stored crop/split/offer can be older
than the screen, and answering from it used to fill greyed days and miss
shown ones. The page clamps the answer to its own current offer again.

One `claude-haiku-4-5` call (`llm.py`) with a FORCED tool (`select_slots`):
the model returns a one-sentence `reading` plus an ORDERED RULE LIST —
never dates. `rules.py` applies rules to every date in the window in code
(`every`/`weekday`/`day`/`month`/`date`/`holiday`/`holiday_within` n/
`holiday_since` n/`all`/`any`/`not`, depth ≤8, ≤40 rules); an invalid rule
is dropped and counted, never guessed at. Relative days ("next monday")
are resolved in the PROMPT, not left to the model — it once miscounted
after a same-week removal rule ran first.

`split` is set true when the wording distinguishes day-parts, OR —
regardless what the model says — when the applied rules picked only one
half of some day; a HOST's page then ticks split; a GUEST's page can't
split, so halves fold back into whole days. A `crop` in the answer is also
a LIMIT on the slots returned, not just a suggested view.

**Rate limits are ROLLING windows, never lifetime caps** (in-memory:
`ASK_POLL_RATE`=60/hr per poll, `ASK_IP_RATE`=60/hr per IP, and a ceiling on
ALL asks together, `ASK_GLOBAL_RATE`=120/hr -- each is a paid Haiku call;
checked+recorded under one lock BEFORE the model call); a refused ask is
never recorded, so the window refills on schedule. **Only a stored poll, or a
draft carrying its own token, may ask** (2026-10-14): a made-up slug used to
pass the shape check, and a fresh one per call slipped past the per-poll
window -- ~$12/day per IP with no ceiling (security audit). No per-voter limit — asking needs no name
and a key is free to mint. `ASK_MAX_CHARS`=280, `ASK_MAX_TOKENS`=1024 (a
truncated tool call raises `Truncated` → 422). An answer REPLACES the grid
outright unless it matches nothing, in which case existing picks are left
alone and the page says so.

### 21i. `/noodle` and link previews

**Everyone, owner included**: the title and one `create poll` button
(no title -- the draft starts `title`, a placeholder, until the host
retitles by tapping it), centred in the screen above the nav
(`#noodle-admin`), with Wai's blurb under the button (`.nd-create-note`, 2026-10-13):
"end-to-end encrypted" / `https://wai-lau.net/noodle/<slug>?t=<token>#k=<K>` / "<K> is a
secret key composed on your device" / "data after the # is not sent to the
server" / "only people you send the full URL can access the poll", then a link to
Excalidraw's "End-to-End Encryption in the Browser" post (the same scheme). Deliberately NOT "Signal Protocol" -- one static key per poll, no
ratchet, no forward secrecy (21m). **No poll list since 2026-10-13** (Wai: "no need for
host noodle to show poll lists"): the owner's table of sealed ids, the
browser-side id mapping (`ndmIdOf`) and the `noodle.polls` localStorage
it read are gone -- the vote page now REMOVES any `noodle.polls` it finds,
since it held every opened poll's link with its key. The owner API stays:
`GET /api/noodle-polls` lists file ids + mtimes only (the server holds no
links, 21d), `DELETE /api/noodle-polls/{ref}` takes a slug or a file id
and every vote with it.

**The owner's chart** (2026-10-13): "polls created per day", one column a
day from the first counted day to today (90 at most; older days fold into
an "earlier" count), tooltip on hover/focus/tap, the peak's count on its
cap, an "as a table" fallback (`web/noodle-created.{js,css}`). Shown only
when `GET /api/noodle-polls/created` (owner-only) answers. The sealed polls
cannot say when they were made -- `created_at` is inside each poll's
encryption and a file's mtime is its last write -- so `stats.py` COUNTS
creations as they happen (`store.try_create` / `drafts.ensure` report
whether they wrote one; the routes record it), skipping the test suite's
rate-exempt requests. Days before 2026-10-13 were backfilled once from the
nginx access logs (14 days kept): a draft page (`?t=`) followed by a first
successful commit, plus the owner's `POST /api/noodle-polls` -- polls first
seen before 2026-09-29 have no date and are not drawn. There was an autoplaying demo
video under the button until 2026-10-03; Wai dropped it ("just have the
thing in the middle"), the last two copies are in exec-fn's `.archaeology/media/`.
The title (`.nd-brand`) is big, glowing, set in **Courier New** —
a system font everywhere — not the site's own mono face.

Open Graph on every noodle page (`pages._og`): title, description (the
poll's note or a default), one fixed dark card image
(`web/noodle-card.jpg`, 1200×630 — the site's own icon falls back to
white-on-transparent, which a light-mode preview draws white on white),
absolute URLs (`config.ORIGIN`). `theme-color` is `#000`, deliberately NOT
noodle green — the same tag paints an installed PWA's title bar. Meta
caches a preview for weeks (re-scrape via Facebook's Sharing Debugger);
Discord has no re-scrape tool (append `?1`).

The shell carries no CRT stack (dropped 2026-10-03, top of 21). Lines are 2px
in noodle (borders, crop lines, the split diagonal) — set when 1px hairlines
broke up under the CRT scanlines that were then on the page.

### 21j. Glyph font

`web/fonts/noodle-seal.woff2` (4.9KB) is a hand-cut subset of the Mayukai
TTF carrying every non-ASCII glyph noodle draws — seal parts, the teaching
box's arrow and bullet, the toggle/mode/copy icons — under family
`'Noodle Glyphs'` with a matching `unicode-range`; the site's own woff2 is
a 126-glyph ASCII subset with none of them. `tests/test_noodle_glyphs.py`
scans every noodle source for literal and `\uXXXX`-escaped glyphs, fails on
one missing from the font, one whose advance isn't `M`'s, any emoji or
variation selector, or a drifted `unicode-range` — then measures the
RENDERED width of each in real WebKit.

### 21k. Tests

**End to end, as people use it** -- `tests/test_noodle_browser_journey.py`: a real plain poll (owner API) and a real end-to-end poll (made from `/noodle`), a host and three guests each in their OWN browser context voting different parts of the host's offer; then a fresh visitor sees every vote exactly as cast, a later host edit reaches everyone, a voter on a NEW device gets their own vote back with their passphrase, and on the e2e poll the server's JSON and HTML hold no name, title, note or slot while a link without its key opens nothing.

The unit isolation test is an AST import-graph audit that noodle imports no
app module, plus a runtime audit wrapping `open`/`replace`/`mkdir`/
`scandir`/`mkstemp` over a full create→vote→edit→ask→reset cycle. The rest
(file map) cover their module 1:1 — signature/replay edge cases, host
actions, rekey, drafts, Ask's caps/clamp/schema-discard (model faked), the
rule language, the holiday mirror, name-normalization parity, `ndhConvert`
pinned against `slots.convert` through node, and the toggle/hit-test rules
through node. Browser tests are split by topic (file map); helpers
(`can_commit`/`offer_one`) are shared via `tests/noodle_helpers.py`.

exec-fn's root `conftest.py`'s `noodle_slug` fixture creates a **fresh poll per test
session** (titled `__smoke__`, deleted after) — it used to be one
long-lived poll found by title and reused forever, so who had hosted it and
what had been offered carried over between runs, and tests passed or
failed by the order they last ran in.

### 21l. Known & accepted risks

- An owner key-reset of the HOST's own name lets the next signer claim
  host — deliberate, since the reset is owner-only already.
- One process-wide `store._LOCK` serializes every poll's writes — no
  correctness issue, just no cross-poll parallelism.
- The passphrase is shown in the clear in its own field — deliberate: it's
  the voter's own screen, meant to be proofread, and never leaves the
  browser regardless.
- No in-app password recovery by design: a forgotten passphrase is a
  forgotten key. Only the owner's `python -m noodle.reset` CLI re-opens a
  name for a fresh bind -- on a PLAIN poll. On an end-to-end one the host
  removes the forgotten seat and the voter commits again (21m).

### 21m. End-to-end polls

**Every poll started since 2026-10-09 is end-to-end; older polls are
untouched** (owner: existing links must keep working, and only new noodles
change). Plain = `votes.py`/`host.py`/`rekey.py`, server reads the poll;
end-to-end = `e2e.py`, server cannot. The two never mix: `routes.py`
dispatches every write by the STORED poll's `e2e` flag (`e2e.is_e2e`), and
each e2e signature carries an `e2e-*` kind, so nothing signed for one path
or action verifies as another.

**The key** is 32 random bytes made by the creator's BROWSER on `/noodle`
(`noodle-claim.js noodleNewPollKey`), before the draft is even minted, and
carried in the link's fragment (`/noodle/<slug>#k=<43 b64url>`) -- the part
a browser never sends, so the server never holds it, not even in flight.
Every draft token is `<claim>.<mac>` (`drafts.kind`, below): the bare HMAC
over the slug (plain drafts handed out before 2026-10-09) was RETIRED
2026-10-14 -- the access log keeps those tokens, and committing one first
made you host. Polls already made from either old kind are unaffected. The owner's titled
`POST /api/noodle-polls` stays plain (the server is handed the title).

**The creator's claim** (since 2026-10-12): the FIRST vote decides the host,
and the draft token is seen by the server, its nginx access log, and
anyone watching either -- so a token alone used to let an observer vote
first and take the host's seat (and the host's head/remove powers with
it). Now `/noodle` derives an Ed25519 **claim key** from the poll key
(HKDF-SHA256, zero salt, info `noodle e2e claim v1`, seed -> PKCS#8) and
sends only its public half to `/new`; the token is `<claim>.<HMAC over
e2e-claim\0 + slug + \0 + claim>`, `store.create_at` keeps it as the
poll's `claim`, and `e2e._claim` refuses (403) any vote on a poll still
holding one unless it carries `claim` = the claim key's signature over
`canonical_action(kind="e2e-claim", poll, voter=<pub>)`; the first good one
spends it. The page attaches it whenever nothing is sealed on the poll yet
(`ndeSendVote`), which also covers a draft whose first vote failed after
the poll was written. The end-to-end drafts minted 2026-10-09..12 (bare
HMAC over `e2e\0`+slug, no claim) are refused outright, and an end-to-end
poll stored with NO claim and NO voters (the same window's shape, if any was
created and abandoned) refuses its first vote (403) -- the slug alone would
otherwise seat a stranger as host. None existed when this landed (an empty
unclaimed poll seals to exactly 235 bytes; no stored file was). Every place that hands a link on carries the key:
`ndeLink()` (share box, the host's clipboard copy, the post-draft
`replaceState`). A link without the key
shows a banner and locks; a key that opens nothing says so too.

**Sealed** (AES-256-GCM, WebCrypto, `iv(12)||ct` base64; AAD =
`noodle e2e v1|<slug>|<kind>|<pub>`, so the server cannot move a vote to
another voter or pass one off as the settings): `head` = `{title, note,
halves, from, to}`, sealed WHOLE each time (no server copy to merge into);
each voter = `{name, slots}`, keyed by their pub. **The server still sees
and enforces**, by key alone: public keys, vote order, timestamps; only you
change your seat; the FIRST key to vote -- the creator's, by the claim --
is the host (order 0, so the host's
first Commit sends the VOTE before the head -- reversed from plain polls,
where a split must convert stored votes first); only the host seals the
head or removes a guest (`target` = pub); only your old key moves your seat
to a new key (`e2e-rekey`, the vote re-sealed to the new pub, order kept);
replay (strictly newer ts per key) and the skew window.

**The page checks signatures itself** (2026-10-14, security audit: a server that ALSO holds the poll key -- its operator invited to the poll, say -- could re-seal anyone's vote or the head, and pages took it). The server now KEEPS each vote's signature with the ts it covers (`vts`: a voter's `ts` moves on with every later host action) and the head's signature + signer, and serves them (`e2e.public`, `_signed`); `noodle-e2e.js ndeTrusted` verifies each with WebCrypto Ed25519 against `ndeCanon({ct, kind, poll, ts})` -- the exact bytes the browser signed -- and DROPS a record whose signature fails. The head counts only if signed by the host seat (order 0); a host's passphrase change re-seals and re-signs the head with the new key in the same Commit (`ndvSubmit` sets `pendingTitle`). Records from before 2026-10-14 (and a seat just handed to a new key, until that key votes -- which the same Commit does) carry no signature and still show, so existing polls work; once a browser has seen a poll FULLY signed it remembers (`localStorage noodle.signed.<slug>`) and from then on drops unsigned records there too -- a stripped signature is the only way one could appear. Not covered: a malicious server can still withhold, roll back or REORDER records (order 0 is the host), and a first-time visitor cannot tell stripped from old. Link holders now see each vote's ts. `ndvLoadPoll` builds the opened view BEFORE assigning `NDV.poll` (it used to hold the raw blobs for a moment). Pinned by `tests/test_noodle_browser_signed.py` (a route tampers the poll JSON: forged -> dropped, stripped -> dropped once seen signed, shown to a fresh browser; host rekey re-signs the head).

**What moved into the browser** (`ndeView`, mirroring the server rules
byte for byte -- `tests/test_noodle_e2e_view.py` runs it in node against
`slots.convert`): the split conversion, the crop filter, the host's offer
(guests' dots only within it), one seat per name (the FIRST key to claim a
name keeps it; a later seat with the same name is not drawn, and its
owner's page locks as "sealed with a different passphrase", as before).
Every opened field is shape-checked: anyone holding the link holds the
key. Title/note/`document.title` are filled in after opening
(`ndeShowTexts`); the server's HTML and link preview say only "noodle".

**Content-Security-Policy on the vote page** (2026-10-14): `script-src 'self'` (no inline script, no eval), `frame-ancestors 'none'`, `connect-src`/`worker-src`/`img-src`/`font-src 'self'`, `object-src 'none'`, `base-uri 'none'`; styles may be inline (seal inks are `style="--seal-hsl:…"` strings). The page holds the poll key and, once typed, the voter's key, so any future XSS should find nothing to run. `/noodle` carries the site nav (an inline script), so it gets `frame-ancestors 'none'` only. **Testing it**: Playwright's `wait_for_function` compiles its string predicate in the page on every poll, which the policy refuses (WebKit's `bypass_csp` covers only the first evaluation) -- so exec-fn's root `conftest.py`'s browser wrapper strips the CSP header off page documents for the general suites, and `tests/test_noodle_browser_csp.py` keeps it (`bypass_csp=False`), polls from Python, and walks a plain vote plus an e2e create -> commit with zero violations.

**Hardening from the 2026-10-14 audit** (`tests/test_noodle_hardening.py`):
a key that LEFT a poll -- moved to a new passphrase, or removed by the host --
is tombstoned in `poll["gone"]` with the ts it left at (`e2e._bury`; entries
older than the skew window are dropped), so a body it signed before then,
replayed within the window, gets 409; a genuinely newer vote may still rejoin.
`sig.valid_pub` refuses Ed25519 keys of small order (identity + 7 torsion
points: with A = identity, R = identity and S = 0 verify for ANY message, and
OpenSSL checks nothing) -- `verify` and both rekey paths use it; the check is
pure integer math (decode, double thrice, compare with the identity). Signed
text is encoded `surrogatepass`, so a lone surrogate is a failed signature,
not a 500. Plain orders are `max+1` (len() repeated one after a removal);
dates in crops and slots are `YYYY-MM-DD` only (`slots._day`).

**KDF salt** on an e2e poll is `SHA-256(slug + NUL + key + NUL + name)`
(`ndeScope()` passed as NoodleKdf's slug), so the server -- which knows the
slug -- cannot test guessed names (or name + passphrase) against stored
public keys.

**Accepted limits**: Ask noodle still sends its text + the pickable dates
through the server to Haiku (never stored) -- owner's call 2026-10-12: a
grey note right under the Ask box says so (`.nd-ask-note`: "your noodle polls
are end-to-end encrypted" -- shown only on e2e polls, `.nd-e2e-only` -- then
"the noodle helper is not end-to-end encrypted"), no redesign; anyone with the SLUG (no key
needed) can post seats whose sealed contents are junk (dropped when drawn,
up to the seat cap, 21d), and a link holder can claim a name first; the claim
key derives from the poll key, so anyone the creator hands the raw draft
address to before their first Commit can host instead; a malicious server
can still withhold, roll back or reorder records (it cannot read them, and
pages drop what it forges -- above),
and -- as with any web page -- a compromised server could serve JS that
reads the fragment; no owner reset (above). Tests:
`tests/test_noodle_e2e.py` (server, incl. the slug + token alone failing
to take the host's seat), `test_noodle_drafts.py`,
`test_noodle_e2e_view.py` (node), `test_noodle_browser_e2e.py` (WebKit,
`/noodle` -> draft -> host -> guest -> rekey -> keyless link -> remove,
asserting the token carries the claim Python derives from the key and the
server never serves a name, title or note).

### Rate limits never fail the test suite

The per-IP limiters (tarot chat + warm, mtg chat, noodle draft starts, ask
and signed writes) are SKIPPED for requests carrying `x-ratelimit-exempt:
sha256("ratelimit-exempt:" + API_KEY)` (exec-fn's `auth.RATE_EXEMPT_TOKEN` /
`auth.rate_exempt`; noodle derives the same token from the env itself, since it
imports no app module, and never exempts when `API_KEY` is unset). The suite
sends it from exec-fn's root `conftest.py`: every `httpx.Client` gets it as a default
header, and every browser context adds it ONLY for requests to the app's own
origin (a context route), never to CDNs. Why: a busy hour of pre-commit runs
from this box spent noodle's 20-per-hour draft limit and failed
`test_noodle_drafts_need_their_token` on 2026-10-01; tests from this machine
must never fail because of a rate limit (owner).
