// Main-thread side of noodle's key derivation.
//
// Passphrase -> Argon2id (in noodle-kdf-worker.js) -> Ed25519 seed. The salt
// is SHA-256(poll slug + NUL + normalized name), so the same name and
// passphrase give the same key on any device, and the same passphrase gives a
// different key in every poll.
//
// Debounced: a derive starts KDF_DEBOUNCE ms after typing stops. Never more
// than one runs -- a change mid-derive TERMINATES the worker (Argon2 cannot be
// interrupted from outside) and a generation counter drops anything stale.

// Must match noodle/slots.py normalize_name() exactly (it salts the KDF):
// ASCII letters, digits and spaces only, lowercased.
function noodleNormName(raw) {
  var s = String(raw || '').normalize('NFKC');
  if (/[\p{Cc}\p{Cf}]/u.test(s)) return null;
  s = s.split(/\s+/).filter(Boolean).join(' ').toLowerCase();
  if (!s || Array.from(s).length > 40 || !/^[a-z0-9 ]+$/.test(s)) return null;
  return s;
}

function ndHex(bytes) {
  return Array.from(bytes, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
}

async function noodleSalt(slug, norm) {
  var d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(slug + '\u0000' + norm));
  return new Uint8Array(d).slice(0, 16);
}

// ── pinning the key worker (noodle ARCHITECTURE.md 21m) ──────────────────────
// new Worker()/importScripts cannot be pinned with Subresource Integrity, so
// the key worker and the Argon2 it runs would otherwise be the one unverified
// thing on the page. noodle-kdf.js IS pinned (a <script src> on the vote page),
// so it fetches both, checks them against the sha384 below, and runs them from a
// Blob whose bytes ARE the bytes it verified -- no second-request gap like
// view-source has. A tampered worker could leak a PASSPHRASE (never your names
// or times, which stay out of it); a hash MISMATCH fails the derive closed.
// Kept honest by tests/test_noodle_kdf_pin.py (recomputes these from the files).
var NDK_WORKER_SRC = '/noodle-kdf-worker.js';
var NDK_VENDOR_SRC = '/vendor/hash-wasm-argon2-4.12.0.min.js';
var NDK_PIN = {};
NDK_PIN[NDK_WORKER_SRC] = 'sha384-YRCDPHEZMQ0+0Jw/Kk87bGslN9UUusLoFtXGRO+u812cRQtjssHhKKVg/Rd+2c9p';
NDK_PIN[NDK_VENDOR_SRC] = 'sha384-tP0Wy54CKmng7i9EoTlPySD0hBx6Octj0VS6MfwlnUu111MPa+JLm0CCbep6XJ1W';

function ndkB64(buf) {
  var b = new Uint8Array(buf), s = '';
  for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return btoa(s);
}

// Fetch a file (cache-revalidated, so a deploy's fresh bytes always win) and
// verify its sha384 against pinKey. A bad hash NEVER retries -- that is the
// tamper signal, and the caller fails the derive closed; two quick retries only
// absorb a transient fetch blip.
async function ndkFetchPinned(url, pinKey) {
  var want = NDK_PIN[pinKey], lastErr;
  for (var i = 0; i < 3; i++) {
    try {
      var r = await fetch(url, { cache: 'no-cache' });
      if (!r.ok) throw new Error('http ' + r.status + ' for ' + pinKey);
      var buf = await r.arrayBuffer();
      var got = 'sha384-' + ndkB64(await crypto.subtle.digest('SHA-384', buf));
      if (got !== want) throw new Error('integrity mismatch for ' + pinKey);
      return buf;
    } catch (e) {
      lastErr = e;
      if (/integrity mismatch/.test(String(e && e.message))) break;
    }
  }
  throw lastErr || new Error('could not verify ' + pinKey);
}

// A Blob worker whose bytes are the verified vendor + worker. Vendor FIRST, so
// the worker's guarded importScripts finds hashwasm defined and skips its
// (unpinned) network load. Needs CSP worker-src blob: and, because a blob
// worker inherits the page CSP, script-src 'wasm-unsafe-eval' for Argon2's wasm
// (noodle/config.py VOTE_CSP).
async function ndkPinnedUrl(workerUrl) {
  var vendor = await ndkFetchPinned(NDK_VENDOR_SRC, NDK_VENDOR_SRC);
  var work = await ndkFetchPinned(workerUrl, NDK_WORKER_SRC);
  return URL.createObjectURL(new Blob([vendor, '\n;\n', work], { type: 'text/javascript' }));
}

// opts: {slug, kdf:{m,t,p,len,debounce}, workerUrl, onStart(info), onDerived(info), onError(msg)}
function NoodleKdf(opts) {
  var worker = null, timer = null, gen = 0, busy = false, signId = 0;
  var pendingSigns = {};
  var current = null; // {norm, pub} of the key the worker holds now
  var workerUrl = opts.workerUrl;   // replaced by a pinned blob url when opts.pin
  var urlP = null;

  function spawn() {
    worker = new Worker(workerUrl);
    worker.onmessage = onMessage;
    worker.onerror = function () { busy = false; opts.onError('key worker failed to start'); };
  }

  // Resolve workerUrl to the pinned blob (opts.pin) once, before the first
  // spawn. A verification FAILURE rejects, so the caller fails the derive
  // closed -- never silently running an unverified worker.
  function readyUrl() {
    if (!urlP) {
      urlP = (opts.pin ? ndkPinnedUrl(opts.workerUrl) : Promise.resolve(null))
        .then(function (u) { if (u) workerUrl = u; });
    }
    return urlP;
  }

  function onMessage(e) {
    var m = e.data;
    if (m.op === 'derived' && m.gen === gen) {
      busy = false;
      current = { norm: current && current.pendingNorm, pub: m.pub };
      opts.onDerived({ pub: m.pub, ms: m.ms });
    } else if ((m.op === 'signed' || m.op === 'key') && pendingSigns[m.id]) {
      pendingSigns[m.id].resolve(m.op === 'key' ? m.key : m.sig); delete pendingSigns[m.id];
    } else if (m.op === 'error') {
      if (m.id && pendingSigns[m.id]) { pendingSigns[m.id].reject(new Error(m.detail)); delete pendingSigns[m.id]; }
      if (m.gen === gen) { busy = false; opts.onError(m.detail); }
    }
  }

  async function run(name, pass, myGen) {
    var norm = noodleNormName(name);
    var salt = await noodleSalt(opts.slug, norm);
    try { await readyUrl(); } catch (e) { if (myGen === gen) opts.onError('could not verify the key helper -- reload the page'); return; }
    if (myGen !== gen) return;
    if (!worker) spawn();
    if (busy) { worker.terminate(); spawn(); } // cancel the in-flight derive
    busy = true;
    current = { pendingNorm: norm, pub: null };
    opts.onStart({ salt: ndHex(salt), norm: norm });
    worker.postMessage({ op: 'derive', gen: myGen, pass: pass, salt: salt,
      m: opts.kdf.m, t: opts.kdf.t, p: opts.kdf.p, len: opts.kdf.len });
  }

  // Call on every keystroke in either field.
  function input(name, pass) {
    gen++;
    current = null;
    clearTimeout(timer);
    // an empty passphrase is allowed -- the name alone then decides the key,
    // so anyone typing the name gets it (the page says so)
    if (!noodleNormName(name)) { opts.onStart(null); return; }
    var myGen = gen;
    timer = setTimeout(function () { run(name, pass, myGen); }, opts.kdf.debounce);
  }

  function ask(msg) {
    var id = ++signId;
    return new Promise(function (resolve, reject) {
      if (!worker) { reject(new Error('no key worker')); return; }
      pendingSigns[id] = { resolve: resolve, reject: reject };
      worker.postMessage(Object.assign({ id: id }, msg));
    });
  }

  function sign(text) { return ask({ op: 'sign', text: text }); }

  // The worker's current CryptoKey (non-extractable), to keep in IndexedDB.
  function key() { return ask({ op: 'key' }); }

  // Sign as a KEPT key (noodle-keystore.js) instead of deriving one: no
  // passphrase, no Argon2 -- the worker just takes the key it is handed.
  function use(name, kept) {
    gen++;
    clearTimeout(timer);
    var myGen = gen, norm = noodleNormName(name);
    readyUrl().then(function () {
      if (myGen !== gen) return;
      if (!worker) spawn();
      if (busy) { worker.terminate(); spawn(); }
      busy = true;
      current = { pendingNorm: norm, pub: null };
      opts.onStart({ salt: '', norm: norm });
      worker.postMessage({ op: 'use', gen: myGen, key: kept.key, pub: kept.pub });
    }, function () { if (myGen === gen) opts.onError('could not verify the key helper -- reload the page'); });
  }

  return {
    input: input, sign: sign, key: key, use: use,
    stop: function () { gen++; clearTimeout(timer); if (worker) worker.terminate(); },
    ready: function () { return !!(current && current.pub) && !busy; },
    pub: function () { return current && current.pub; },
  };
}

if (typeof window !== 'undefined') {
  window.NoodleKdf = NoodleKdf;
  window.noodleNormName = noodleNormName;
  window.noodleSalt = noodleSalt;
}
