# Verifying noodle

noodle encrypts each poll end-to-end with a key that lives only in the link's
`#` fragment — the **same scheme Excalidraw uses**, explained here:
<https://blog.excalidraw.com/end-to-end-encryption/>. Read that first; the rest
of this page assumes it and only covers what's specific to noodle.

## The link

```
https://wai-lau.net/noodle/<slug>?t=<token>#k=<key>
```

- **`<slug>`** — the poll's public id. The server uses it to find the stored
  ciphertext. Not a secret.
- **`<token>`** — a capability that lets the link open and edit the poll. In the
  query string, so the server does see it; it is not what keeps the poll private.
- **`<key>`** — the encryption key. It sits after the `#`, the one part of a URL
  a browser never sends to the server. This is the whole secret: anyone with the
  full link can read the poll, and no one without it can — not even the server.

## Auditing the code

Encryption can't prove one thing: that the **page the server handed your
browser** is the public, audited code and not a tampered copy that copies
`<key>`. Three facts make that checkable here:

- **No build step.** Each script the server serves (e.g. `/noodle-e2e.js`) is
  byte-for-byte a file in this repo. The sealing/opening code is one short file:
  [`web/noodle-e2e.js`](web/noodle-e2e.js) (AES-256-GCM via the browser's
  built-in `crypto.subtle`).
- **Every script is pinned** with [Subresource Integrity](https://developer.mozilla.org/docs/Web/Security/Subresource_Integrity):
  a `sha384` the **browser itself enforces**, refusing to run a script whose
  bytes don't match. So a pin that equals the repo's hash means the browser ran
  the repo's code — you don't even have to re-download the script.
- **A strict policy is in the page.** The vote page carries a
  `<meta http-equiv="Content-Security-Policy">` that forbids inline scripts,
  `eval`, and any request leaving the site. It's right there in the HTML, so you
  can see it's present; the browser enforces it even if the server strips the
  matching HTTP header, and its absence would be plain in the page.

Together those cover everything that can run: if every script is pinned to the
repo and the strict policy is in force, no other code — inline or external — can
touch your key.

### Check it (the verifier — no install)

Open **<https://wai-lau.github.io/noodle/verify.html>**. It runs on GitHub, which
the noodle server can't touch, and compares the page you paste against this public
repo — checking the scripts' pins, the policy, and that there's no inline script.

Paste the page your browser **actually received**, not `view-source:`:

1. On your vote page, press **F12** → **Network** → reload.
2. Click the **top request** (the document) → **Response** → select all, copy.
3. Paste into the verifier → **Check**.

(Why the Network response and not `view-source:`? `view-source:` re-fetches the
page — a hostile server could answer that second request differently from the one
that ran. The Network response is the bytes that ran.)

### Or by hand

In the same Response, confirm the `<meta … Content-Security-Policy …>` is present
and that every `<script>` has an `integrity="sha384-…"` matching the repo — no
script without one, and no inline `<script>`. Hash a repo file to compare:

```
curl -s https://raw.githubusercontent.com/wai-lau/noodle/master/web/noodle-e2e.js \
  | openssl dgst -sha384 -binary | openssl base64
```

## What you're guaranteed

Verify the page that actually ran and **that visit cannot read your poll** — the
browser will not run a script that isn't the public code, and the policy lets
nothing else run or phone out. There's nothing left to trust but the public code
itself. Do it each visit (a server can't fool a check you actually run; it can
only hope you skip it), and — because "matches the repo" only means the server
served the repo's code — trust that the code is honest by reading the handful of
files that touch your key (`web/noodle-e2e.js`, `noodle-vote.js`,
`noodle-claim.js`, `noodle-commit.js`, `noodle-keystore.js`) and re-reading them
when they change.
