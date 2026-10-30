// A voter's INK -- their dot colour, legend swatch and seal colour -- from a
// fixed palette (owner, 2026-10-30: a hue hashed from the key could land two
// voters on near-identical colours). The palette is CSS, --nd-ink-0..7, so
// each front end sets lightness for its own ground (noodle.css on black,
// noodle-tc.css on sand); the ink string is just `var(--nd-ink-N)`, which the
// shared code drops verbatim into a --seal-hsl style.
//
// Each key HASHES to a home colour, so a person keeps theirs across polls and
// visits; within a poll, voters claim colours in vote order, and one whose
// home is already held steps to the next free one. Only past 8 voters do
// colours repeat: the ninth starts a second ROUND (noodle-tc-legend.js gives
// each round a pip shape).
//
// Wraps the seal maker (noodle-seal.js NoodleSeal.seal) so every seal made
// carries its voter's ink, and re-inks your own (NDV.seal) once the poll --
// and so who holds which colour -- is known. Your seat before your first
// commit claims after everyone. NoodleInk.of is the hook a front end may
// replace.
var NDI_COUNT = 8;   // --nd-ink-0..7

function ndiHome(pub) {   // FNV-1a over the key: the same home for everyone, every visit
  var h = 2166136261;
  for (var i = 0; i < pub.length; i++) { h ^= pub.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) % NDI_COUNT;
}

// pub -> {slot, round}: voters claim in vote order, a key not voted yet last
function ndiPlace(pub) {
  var voters = window.NDV && NDV.poll ? NDV.poll.voters : [];
  var pubs = voters.map(function (v) { return v.pub; });
  if (pubs.indexOf(pub) < 0) pubs.push(pub);
  var held = [];
  for (var i = 0; i < pubs.length; i++) {
    var round = Math.floor(i / NDI_COUNT), slot = ndiHome(pubs[i] || '');
    held[round] = held[round] || {};
    while (held[round][slot]) slot = (slot + 1) % NDI_COUNT;
    held[round][slot] = true;
    if (pubs[i] === pub) return { slot: slot, round: round };
  }
  return { slot: 0, round: 0 };
}

function ndiOf(pub) {
  return 'var(--nd-ink-' + ndiPlace(pub).slot + ')';
}

window.NoodleInk = { of: ndiOf, place: ndiPlace, count: NDI_COUNT };

(function () {
  var S = window.NoodleSeal, R = window.NoodleRoster;
  if (!S || !R) return;
  var seal = S.seal, seals = R.seals;
  S.seal = async function (pub) { return Object.assign({}, await seal(pub), { ink: window.NoodleInk.of(pub) }); };
  R.seals = async function (voters) {
    var out = await seals(voters);
    // your own seal was made before the poll (and its order) was known
    var mine = NDV.kdf && NDV.kdf.ready() ? NDV.kdf.pub() : null;
    if (NDV.seal && mine) NDV.seal = Object.assign({}, NDV.seal, { ink: window.NoodleInk.of(mine) });
    return out;
  };
})();
