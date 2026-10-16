# noodle — ARCHAEOLOGY

Moved out of exec-fn's ARCHAEOLOGY.md (§21) on 2026-10-14, when noodle became its
own repo (`wai-lau/noodle`), consumed by exec-fn as the submodule
`apps/noodle`. A bare `§N` below (other than §21's own subsections) means a
section of **exec-fn's** ARCHAEOLOGY.md; how the parent serves this app is
exec-fn §1e.

## 21. noodle

Current design: [ARCHITECTURE.md §21](ARCHITECTURE.md).

**The 2026-09-29 split.** `noodle.css` had grown to 630 lines of rules appended in request order; it split into `noodle.css` + `noodle-identity.css`/`-actions.css`/`-roster.css`/`-split.css`/`-admin.css`/`-foot.css` (verified by a computed-style snapshot of every element, identical but for the random seal/stamp frame). The same day, `noodle-vote.js` (428 lines: identity fields, Commit, the core all in one) split into `noodle-vote.js` (state/binding/calendar/load/init), `noodle-identity.js`, `noodle-commit.js`, `noodle-roster.js` (absorbing `noodle-seats.js`, which had held the roster LOGIC while `noodle-roster.js` held only its renderer — grepping "roster" used to miss half of it), `noodle-storage.js` (renamed from `noodle-local.js`, which read as dev tooling), and `noodle-esc.js` (the HTML escape, previously written twice). Every function moved verbatim, checked by diffing each body; 33 browser tests passed unchanged. Also that day: the shared signed-action envelope (name+ts shape, skew window, signature check) moved from a private `host._check` to `votes.check_action` — `rekey.py` had been importing a helper from a module named for host-ONLY actions, so an edit meant for the host could quietly change rekey's validation too; `ndhConvert` (the JS twin of `slots.convert`) was pinned against it through node and turned out to drop slots already in the target form, which `convert` keeps — invisible because the page never mixed forms; and the split got the same "re-check inside the lock" fix the crop already had, plus `NoodleCal().destroy()` now disconnects the calendar's observers before a rebuild.

**Ask noodle used to ask the model for dates, not rules.** First as `{date, block}` objects per day (blew `max_tokens` on anything long), then as per-date verdict lines — either way, ~50 small arithmetic problems per answer, and some always slipped: on a phone, "friday nights, days that are prime and fibonacci all day, day if stat holiday" lit the 9th/15th/25th/27th and missed the 8th and 11th. Rewritten so the model lists rule conditions ONCE (`{"day": [2,3,5,13]}`) and code applies them exactly to every date — 2-3s per ask against 5-9s, and the grid is now exact for whatever the rules say.

**The blank "you" seat's placeholder seed used to be 16 bytes.** An early version of `noodle.blankSeal.<slug>` stored a 16-byte hex string; the seal renderer reads 32 fingerprint bytes and read past the end. Fixed by validating for exactly 64 hex characters and regenerating anything else.

**Month boundaries went through three renderings.** Per-cell 5px bars first (`.nd-edge-b`/`.nd-edge-r`) — translucent bars that met at a corner doubled into a visibly brighter chip. Then ONE SVG path per boundary, green, 2px on the gap centre — a layer that rounds independently of the cells' own borders, so at some widths/zooms (fractional DPR, e.g. Windows at 175%) the line drifted a device pixel or two off the gap. Then 2px segments drawn INSIDE the cells (`ndcPaintBoundaries`, `<i class="nd-ml b|v|t">`), opaque cyan dimmed to read as blue, each laid out against the very box whose border it sits on, so it can't drift from it. All of it is gone since: months are now a vertical name in the week column plus an alternating cell shade, no divider line (ARCHITECTURE.md 21e).

**The 2026-09-27 adversarial review** fixed: the crop was being re-checked OUTSIDE the vote lock (a pre-lock read could already be stale by the time the write happened); a host dropping an offered time wasn't trimming it from guests who had already picked it; a failed Commit step didn't reload the poll, so the same lost race or moved crop failed the same way forever; `fsync` was added before the poll file's rename; the passphrase field gained a 128-char cap; and an empty calendar draft could overwrite a returning voter's real, already-committed picks.

**The `noodle_slug` test fixture used to be one shared poll, `__smoke__`, found by title and reused across every run.** Whoever had hosted it, and what had been offered, carried over from the last run — so browser tests passed or failed depending on the order they'd last run in. Replaced with a fresh poll per test session, created and deleted around it.

**The first vote used to decide the host, and the draft token was visible.** From 2026-10-09 end-to-end drafts were handed out as a bare HMAC over `e2e\0`+slug. That token appears in the server, its nginx access log and anyone watching either, and the FIRST vote on a poll becomes host (order 0, with the head/remove powers) — so an observer could vote first and take the seat (fixed 2026-10-12, `eab07af`: the creator's CLAIM key, ARCHITECTURE.md 21m). The bare-HMAC plain drafts (before 2026-10-09) stayed accepted until 2026-10-14 for the same reason, then were retired too; polls already made from either are untouched.

**The 2026-10-14 security audit** (`eb126ad`, `924baef`, `594fea8`, `9b8a8dc`, `858258f`, `4e6a0af`): a slug alone could add junk seats without end, each write re-sealing the whole file under the one lock (1,500 seats = a 12 MB file, 327 ms holds) → `MAX_VOTERS`, `POLL_FILE_MAX`, write rate limits, reads that skip the lock; Ask accepted any made-up slug and a fresh one per call dodged the per-poll window (~$12/day per IP) → a stored poll or its own draft token, plus a global ceiling; degenerate small-order Ed25519 keys verified for any message, a removed/rekeyed key's body could be replayed inside the skew window, and a lone surrogate in signed text was a 500 → `sig.valid_pub`, `poll["gone"]` tombstones, `surrogatepass`; a server that also held an e2e poll's key could re-seal anyone's vote → signatures kept and checked by the PAGE (`ndeTrusted`); the passphrase sat in localStorage in plain text → only the non-extractable KEY is kept, in IndexedDB. The same day the fixes were made non-breaking: every poll carries a rules stamp `"v": 2` and older polls keep the old rules as special cases (21d, `tests/test_noodle_legacy.py`).

**The 2026-10-03 simplification.** The CRT stack came off noodle (feedback: the site's one plain page), the autoplaying demo video under `/noodle`'s button was dropped ("just have the thing in the middle"), the argon2id recipe box went, and the page became one section at a time (`you` then `pick`). On 2026-10-13 `/noodle`'s poll list went too, and with it the browser-side `noodle.polls` entry that held every opened poll's link, `#k=` key included; a per-day creation chart replaced it. Drafts were re-keyed per poll + NAME (not passphrase) on 2026-09-27 (`cba52e6`) after a stale draft under an earlier key beat a freshly saved vote.

### 21b. Identity and the vote page

**Name normalization.** Names are lowercased as typed and stored normalized; identity was already case-blind, so this changed no key, it only stopped first-typed casing making one person look like two. The page strips non-ASCII letters/digits/spaces as typed, over the known Unicode divergence points (lookalike scripts stay unmerged).

**KDF cost.** Measured ~360ms in node on the droplet, ~560-680ms in headless WebKit at m=64 MiB t=2; the config comment targets 50-250ms on a mid-range phone.

**One section edits at a time (feedback 2026-10-03).** `ndvStep`/`ndvPaintStep` split the page into YOU then PICK. The host's title/note became editable on either step (Wai: naming the poll goes with naming yourself). The title placeholder is "title" (not "untitled noodle") and the field is labelled "your name", because it was unclear which name was the group's and which the voter's. `noodle-identity.js` loads BEFORE `NDV` exists, so an IIFE there throws; `ndvStepInit` is called from `ndvInit`. Browser tests advance with `ndvCanNext() && ndvStep('pick')` inside their unlock waits.

**UI audit 2026-10-03** (all applied): the argon2id recipe box went — the seal + caption sit centred under the fields (`.nd-seal-row`, hidden until a name is typed); `#nd-next-why` gives the reason "next" is grey (a key still deriving does not hold it); the host's not-yet-offered days are dim green and NOT struck (only past / out-of-crop days are); the crop grips sit at `left: 20px` in the week column, off the dates; the foot links are plain dim underlined links, not buttons that out-shout Commit; the note has no dashed line of its own; "help me" is its label's height; one passphrase hint for both roles; the pick note reads "when are you free? (everyone can see)".

**Lines are 2px** in noodle (borders, crop lines, split diagonal) — set when 1px hairlines broke up under the CRT scanlines then on the page. The CRT stack came off 2026-10-03.

### 21d. Storage and abuse bounds

**Old polls keep the old rules** (owner, 2026-10-14: "don't break old polls, keep them as special cases"). The cost, accepted: an old poll's slug is still enough to flood that one poll.

**Abuse bounds (2026-10-14).** A security audit showed a slug alone could add junk seats without end, each write re-sealing the whole file under the one lock: 1,500 seats = a 12 MB file, 327 ms lock holds. Hence `MAX_VOTERS`, `POLL_FILE_MAX`, the write limiter, and reads that never take the lock.

**Encryption at rest (2026-10-08).** Only `store.py` changed for it; everything above still gets a dict. `store.migrate_all()` was run on the droplet 2026-10-08: 8 polls.

**Two races found the hard way.** The **crop** (a pre-lock read can be a copy a concurrent narrowing already made stale) and the **split** (a host flipping `halves` between a vote's pre-lock shape-check and its write would convert every stored slot mid-flight; `_admit` now re-checks the slot codes inside the lock and 409s instead of writing a vote in the wrong shape).

**Calendar observers.** `NoodleCal().destroy()` disconnects the `ResizeObserver`/`IntersectionObserver` before `ndvEnsureCal` builds a fresh grid — every split flip or crop drag used to leave the OLD observers, and the detached grid they watched, alive for the page's life.

### 21e. The calendar

The `.nd-cal-wrap` / banner z-index layering was built to rise over the CRT stack, which noodle no longer has (2026-10-03); it stays because the sticky/crop z-indices are tuned to it.

**Dots are 6px** — 4px read as specks over a picked half (feedback 2026-10-03).

**Months: weeks loaded later once put their black week cells over "october"**, and a crop box before the names left them undimmed — hence the DOM-order rule (rows -> names -> `.nd-cropbox`). Names were measured in the narrower fallback font ("september 2026" overran into the header) until re-fit on `document.fonts.ready`. The even-month `.alt` shade is the rules' own green 0.12 (0.06 was too close to black to tell months apart); it replaced a blurred month-number watermark and a stepped month divider line.

### 21g. Storage

**Passphrase in localStorage (until 2026-10-14).** Pages before the security audit kept the passphrase in plain text in `noodle.pass.<slug>.<name>` (plus a cross-poll `noodle.lastpass.<name>` fallback), readable by any script that ever ran on the origin, and people reuse passphrases. Replaced by the non-extractable KEY in IndexedDB. A stale draft under an earlier key once beat the freshly-saved vote once that seal matched again, hence "a successful Commit clears EVERY draft".

**`noodle.polls` (gone 2026-10-13)** held every opened poll's link, `#k=` key included, for `/noodle`'s poll list; the vote page now removes it on load.

### 21h. Ask noodle

**Relative days are resolved in the prompt.** The model once read "next monday" as the 29th — a Tuesday — and re-added a day a "never tuesdays" rule had removed; named out, it copies instead of counts.

**Answering from a stored crop/split/offer** (the old design) could be older than the screen and filled greyed days while missing shown ones; hence "works on the PAGE's state".

**Ask abuse (2026-10-14).** A made-up slug used to pass the shape check, and a fresh one per call slipped past the per-poll window — ~$12/day per IP with no ceiling. Fixed with the stored-poll-or-draft-token rule and the global ceiling (`ASK_GLOBAL_RATE`, <= ~$1/h at most).

**Decision 2026-10-12 (owner):** Ask noodle stays non-e2e, with a grey note under the box, no redesign.

### 21i. `/noodle` and the chart

**Poll list removed 2026-10-13** (Wai: "no need for host noodle to show poll lists"): the owner's table of sealed ids, the browser-side id mapping (`ndmIdOf`) and the `noodle.polls` localStorage it read are gone. Replaced by the per-day creation chart, backfilled once from the nginx access logs (14 days kept): a draft page (`?t=`) followed by a first successful commit, plus the owner's `POST /api/noodle-polls` — polls first seen before 2026-09-29 have no date and are not drawn; days before 2026-10-13 are backfilled. `created_at` is inside each poll's encryption and a file's mtime is its last write, hence counting as it happens.

**Demo video** autoplayed under the button until 2026-10-03; Wai dropped it ("just have the thing in the middle"); the last two copies are in exec-fn's `.archaeology/media/`. `/noodle` blurb added 2026-10-13.

**OG card:** the site's own icon falls back to white-on-transparent, which a light-mode preview draws white on white, hence the fixed dark `noodle-card.jpg`.

### 21k. Tests

The `noodle_slug` fixture is a fresh poll per session (see the top of this file for why the shared `__smoke__` poll went).

### 21m. End-to-end polls

**Claim timeline.** From 2026-10-09 e2e drafts were a bare HMAC over `e2e\0`+slug; the claim key (2026-10-12) closed the observer-votes-first hole. The drafts minted 2026-10-09..12 (no claim) are refused outright, and an e2e poll stored with NO claim and NO voters (that window's shape, if any was abandoned) refuses its first vote — none existed when this landed (per the owner at the time; not re-verifiable from the code). Plain bare-HMAC drafts (before 2026-10-09) were retired 2026-10-14.

**Page-side signature checks (2026-10-14 audit).** A server that ALSO holds the poll key — its operator invited to the poll, say — could re-seal anyone's vote or the head, and pages took it. Records from before 2026-10-14 carry no signature and still show. Link holders now see each vote's ts. `ndvLoadPoll` used to hold the raw blobs on `NDV.poll` for a moment.

**CSP (2026-10-14).** The page holds the poll key and, once typed, the voter's key, so any future XSS should find nothing to run. Playwright's `wait_for_function` compiles its predicate in the page on every poll; WebKit's `bypass_csp` covers only the first evaluation.

**Hardening audit 2026-10-14.** Plain orders were `len()` (repeated one after a removal) and now `max+1`; dates in crops/slots were accepted by `date.fromisoformat` in forms like `20261013` and `2026-W42-1`, stored as sent and never equal to any slot.

**Accepted-limits dating:** the Ask note was the owner's call 2026-10-12.

### Rate limits and the test suite

A busy hour of pre-commit runs from this box spent noodle's 20-per-hour draft limit and failed `test_noodle_drafts_need_their_token` on 2026-10-01; tests from this machine must never fail because of a rate limit (owner).
