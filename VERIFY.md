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

Encryption can't prove one thing: that the **JavaScript the server handed your
browser** is the public, audited code and not a tampered copy that copies
`<key>`. Two facts make that checkable here:

- **No build step.** Each file the server serves (e.g. `/noodle-e2e.js`) is
  byte-for-byte a file in this repo. The sealing/opening code is one short file:
  [`web/noodle-e2e.js`](web/noodle-e2e.js) (AES-256-GCM via the browser's
  built-in `crypto.subtle`).
- **Every script is pinned** with [Subresource Integrity](https://developer.mozilla.org/docs/Web/Security/Subresource_Integrity):
  a `sha384` the **browser itself enforces**, refusing to run a script whose
  bytes don't match.

So the only question is: *does the hash pinned on the page equal the hash of the
file in this public repo?*

### The real check: View-Source (no install, targeting-resistant)

Open **View-Source** on your own vote page (`view-source:` prefix, or right-click
→ View Page Source). Every `<script>` carries `integrity="sha384-…"`. If each one
equals the matching repo file's hash — and none is missing — then every script
your browser ran was the public code. This is the trustworthy check: the browser
enforced those exact hashes, and View-Source shows them as served, outside any
script the page could run.

Hash a repo file to compare:

```
curl -s https://raw.githubusercontent.com/wai-lau/noodle/master/web/noodle-e2e.js \
  | openssl dgst -sha384 -binary | openssl base64
```

## The honest limit

A server that wants to target **one** person could serve clean code to a checker
and tampered code to the victim. No web page fully closes that — only a pinned
client that stops re-fetching its code (a browser extension, a native app) can.
What this gets you: the attack must be targeted and timed, and **any one person
who View-Sources their own page can expose it.**
