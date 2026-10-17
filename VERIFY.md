# Verifying noodle

Your noodle polls are **end-to-end encrypted**. The key that unlocks a poll is
made in your browser and lives only in the link's `#k=…` fragment, which a
browser never sends to the server. The server stores ciphertext it has no key
for, so a leaked disk, a backup, or the running server itself cannot read your
names or your picks.

There is one thing encryption alone cannot prove: that the **JavaScript the
server handed your browser** is this public code, and not a tampered copy that
quietly copies your key. Every web app shares this limit, because the page
decrypts with code it fetches from the same server each visit.

noodle lets you check it, if you want.

## Why it's checkable here

noodle has **no build step**. The file served at `/noodle-e2e.js` is
byte-for-byte [`web/noodle-e2e.js`](web/noodle-e2e.js) in this repo. The vote
page also pins every script with [Subresource Integrity](https://developer.mozilla.org/docs/Web/Security/Subresource_Integrity):
a `sha384` hash the **browser itself enforces**, refusing to run a script whose
bytes don't match. So "is the code genuine?" becomes "does the hash on the page
equal the hash of the file in this public repo?"

## The one-command check

```
python3 scripts/verify.py https://wai-lau.net/noodle/<your-poll-slug>
```

Python 3, no install. It fetches the vote page and, for each script, confirms
the pinned hash, the file the server serves now, and the file in the public repo
all agree. It exits `0` only when every script checks out.

## The by-hand check

Open **View-Source** on your own vote page. Each script tag carries
`integrity="sha384-…"`. Compare those to the hashes of the files in this repo
(`verify.py` prints the repo hash for each, or compute it yourself:
`cat web/noodle-e2e.js | openssl dgst -sha384 -binary | openssl base64`).

## The honest limit

A server that wants to target **one** person could serve clean code to a checker
and tampered code to the victim. No web page can fully close that — only a
pinned client that stops re-fetching its code from the server (a browser
extension, a native app) can. What this gets you: the attack must be targeted
and timed, and **any one person who checks their own page can expose it**. The
by-hand check above is the targeting-resistant one, because it reads the hashes
*your* browser was handed.
