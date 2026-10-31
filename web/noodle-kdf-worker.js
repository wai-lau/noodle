// noodle's key worker. Runs Argon2id (hash-wasm, vendored -- web/vendor/,
// MIT) off the main thread so typing never stutters, and holds the resulting
// Ed25519 private key as a NON-EXTRACTABLE CryptoKey. The passphrase and the
// private key never leave this worker; only the public key and signatures do.
//
// Messages in:  {op:'derive', gen, kdf, pass, salt, m, t, p, len, iter}
//               {op:'use', gen, key, pub}    -- a key kept in IndexedDB (noodle-keystore.js)
//               {op:'sign', id, text}
//               {op:'key', id}               -- the CryptoKey itself, to be kept
// Messages out: {op:'derived', gen, pub, ms} | {op:'signed', id, sig} | {op:'progress', gen, done}
//               {op:'key', id, key} | {op:'error', gen|id, detail}
// The CryptoKey crosses postMessage as a structured clone and STAYS
// non-extractable: whoever holds it can sign, nobody can read it out.

// In the PINNED path (noodle-kdf.js runs this worker from a Blob with the
// vendored Argon2 prepended) hashwasm is already defined, so this unpinned
// network load is skipped -- nothing the worker runs is fetched unverified.
// In the standalone path (a raw worker url) it is not defined, so load it.
if (typeof self.hashwasm === 'undefined') {
  importScripts('/vendor/hash-wasm-argon2-4.12.0.min.js');
}

// PKCS#8 wrapper for a raw 32-byte Ed25519 seed (RFC 8410): WebCrypto has no
// "import raw private seed", but a seed inside this fixed prefix is exactly
// what 'pkcs8' import takes.
var PKCS8_PREFIX = new Uint8Array([
  0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06,
  0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20,
]);
var key = null;

function b64(buf) {
  var bytes = new Uint8Array(buf), s = '';
  for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

// hash-wasm refuses an empty password, and an empty passphrase is allowed
// (the page warns it can be impersonated): it becomes one NUL byte, which no
// text input can produce, so it collides with no typed passphrase and every
// non-empty one derives exactly as before. PBKDF2 takes the same bytes.
function secret(pass) { return pass === '' ? new Uint8Array([0]) : new TextEncoder().encode(pass); }

// m.kdf 'pbkdf2' (noodle-kdf.js NDK_PBKDF2): PBKDF2-SHA256 in WebCrypto, for a
// NEW seat in a browser with no WebAssembly; anything else is Argon2id, as it
// always was -- by hash-wasm, or, with no WebAssembly, by noble's plain-JS
// Argon2id (the same key, about a minute: Lockdown also turns off the JIT),
// reporting how far it has got as {op:'progress', gen, done 0..1}.
async function seedOf(m) {
  if (m.kdf === 'pbkdf2') {
    var base = await crypto.subtle.importKey('raw', secret(m.pass), 'PBKDF2', false, ['deriveBits']);
    return new Uint8Array(await crypto.subtle.deriveBits(
      { name: 'PBKDF2', hash: 'SHA-256', salt: m.salt, iterations: m.iter }, base, m.len * 8));
  }
  if (typeof WebAssembly === 'undefined' && self.nobleArgon2id) {
    var shown = -1;
    return self.nobleArgon2id(secret(m.pass), m.salt, { t: m.t, m: m.m, p: m.p, dkLen: m.len,
      onProgress: function (done) {
        var pct = Math.floor(done * 100);
        if (pct !== shown) { shown = pct; self.postMessage({ op: 'progress', gen: m.gen, done: done }); }
      } });
  }
  return self.hashwasm.argon2id({
    password: m.pass === '' ? secret(m.pass) : m.pass,
    salt: m.salt, parallelism: m.p, iterations: m.t,
    memorySize: m.m, hashLength: m.len, outputType: 'binary',
  });
}

async function derive(m) {
  var t0 = performance.now();
  var seed = await seedOf(m);
  var pk8 = new Uint8Array(PKCS8_PREFIX.length + seed.length);
  pk8.set(PKCS8_PREFIX); pk8.set(seed, PKCS8_PREFIX.length);
  // An extractable copy exists only long enough to read the public half out
  // of its JWK; the key actually kept for signing cannot be exported.
  var tmp = await crypto.subtle.importKey('pkcs8', pk8, { name: 'Ed25519' }, true, ['sign']);
  var jwk = await crypto.subtle.exportKey('jwk', tmp);
  key = await crypto.subtle.importKey('pkcs8', pk8, { name: 'Ed25519' }, false, ['sign']);
  seed.fill(0); pk8.fill(0);
  self.postMessage({ op: 'derived', gen: m.gen, pub: jwk.x, ms: Math.round(performance.now() - t0) });
}

async function sign(m) {
  if (!key) throw new Error('no key yet');
  var sig = await crypto.subtle.sign({ name: 'Ed25519' }, key, new TextEncoder().encode(m.text));
  self.postMessage({ op: 'signed', id: m.id, sig: b64(sig) });
}

async function use(m) {
  if (!m.key || m.key.extractable || m.key.algorithm.name !== 'Ed25519') throw new Error('not a kept key');
  key = m.key;
  self.postMessage({ op: 'derived', gen: m.gen, pub: m.pub, ms: 0 });
}

async function hand(m) {
  if (!key) throw new Error('no key yet');
  self.postMessage({ op: 'key', id: m.id, key: key });
}

self.onmessage = function (e) {
  var m = e.data;
  var job = { derive: derive, sign: sign, use: use, key: hand }[m.op];
  job = job ? job(m) : null;
  if (job) {
    job.catch(function (err) {
      self.postMessage({ op: 'error', gen: m.gen, id: m.id, detail: String(err && err.message || err) });
    });
  }
};
