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

**Month boundaries went through three renderings.** Per-cell 5px bars first (`.nd-edge-b`/`.nd-edge-r`) — translucent bars that met at a corner doubled into a visibly brighter chip. Then ONE SVG path per boundary, green, 2px on the gap centre — a layer that rounds independently of the cells' own borders, so at some widths/zooms (fractional DPR, e.g. Windows at 175%) the line drifted a device pixel or two off the gap. Now 2px segments drawn INSIDE the cells (`ndcPaintBoundaries`, `<i class="nd-ml b|v|t">`), opaque cyan dimmed to read as blue, each laid out against the very box whose border it sits on, so it can't drift from it.

**The 2026-09-27 adversarial review** fixed: the crop was being re-checked OUTSIDE the vote lock (a pre-lock read could already be stale by the time the write happened); a host dropping an offered time wasn't trimming it from guests who had already picked it; a failed Commit step didn't reload the poll, so the same lost race or moved crop failed the same way forever; `fsync` was added before the poll file's rename; the passphrase field gained a 128-char cap; and an empty calendar draft could overwrite a returning voter's real, already-committed picks.

**The `noodle_slug` test fixture used to be one shared poll, `__smoke__`, found by title and reused across every run.** Whoever had hosted it, and what had been offered, carried over from the last run — so browser tests passed or failed depending on the order they'd last run in. Replaced with a fresh poll per test session, created and deleted around it.
