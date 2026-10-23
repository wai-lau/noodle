// noodle-tc's PIPS: their colours and shapes, and the LEGEND under the
// calendar -- whose pip is whose, a swatch in each voter's pip colour and
// shape beside their name (owner, 2026-10-23). /noodle-tc hides the roster
// row (the name cards), so this is where the names live. Loaded only by the
// /noodle-tc shell (deferred); on a page with no calendar it does nothing.
//
// The legend READS the roster the shared JS still renders, hidden (noodle-roster.js
// ndrRender: one button.nd-face per voter, data-name, the ink as --seal-hsl on
// its pre.nd-seal; the host's carries .host, your own .you), and redraws on
// every change to it. It never writes shared state, and builds every name
// with textContent: a name is a voter's own text.
//
// PIP COLOURS (owner, 2026-10-23): N voters share the hue circle EQUALLY --
// 3 voters sit at a triangle's corners, 4 at a square's -- starting from a
// hue drawn at random for the host, seeded by the poll so every viewer sees
// the same colours. All in one dark, earthy tone that sits in this palette
// with no outline. Past NDTC_HUES voters the hues would crowd, so pips also
// take a SHAPE: circle, square, triangle. Your own seat, before your first
// Save, takes the next place round the circle.
//
// It wraps the shared seal maker (noodle-seal.js NoodleSeal.seal) so every
// seal the page makes carries this ink, and re-inks your own (NDV.seal) once
// the poll is known. The shape rides IN the ink string as two more custom
// properties: the shared code drops the ink into a style attribute
// verbatim, and noodle-tc.css reads them (--tc-pip-r, --tc-pip-clip).
var NDTC_HUES = 6;
var NDTC_SHAPES = ['', ';--tc-pip-r:0', ';--tc-pip-r:0;--tc-pip-clip:polygon(50% 0,100% 100%,0 100%)'];

function ndtcSeed(slug) {   // FNV-1a: the same host hue for everyone on this poll
  var h = 2166136261;
  for (var i = 0; i < slug.length; i++) { h ^= slug.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) % 360;
}

function ndtcInk(pub) {
  var voters = window.NDV && NDV.poll ? NDV.poll.voters : [];
  var at = voters.map(function (v) { return v.pub; }).indexOf(pub);
  var n = voters.length + (at < 0 ? 1 : 0), i = at < 0 ? voters.length : at;
  var shapes = Math.min(NDTC_SHAPES.length, Math.ceil(n / NDTC_HUES)), hues = Math.ceil(n / shapes);
  var hue = Math.round(ndtcSeed(NDV.slug || '') + (i % hues) * 360 / hues) % 360;
  return hue + ' 42% 34%' + NDTC_SHAPES[Math.floor(i / hues) % NDTC_SHAPES.length];
}

(function () {
  var S = window.NoodleSeal, R = window.NoodleRoster;
  if (!S || !R || !window.NDV) return;
  var seal = S.seal, seals = R.seals;
  S.seal = async function (pub) { return Object.assign({}, await seal(pub), { ink: ndtcInk(pub) }); };
  R.seals = async function (voters) {
    var out = await seals(voters);
    // your own seal was made before the poll (and its order) was known
    var mine = NDV.kdf && NDV.kdf.ready() ? NDV.kdf.pub() : null;
    if (NDV.seal && mine) NDV.seal = Object.assign({}, NDV.seal, { ink: ndtcInk(mine) });
    return out;
  };
  // a poll that loaded before this (deferred) script ran: ink it now
  if (NDV.poll) R.seals(NDV.poll.voters).then(function (out) { NDV.seals = out; window.ndvRefreshBinding(window.ndvPub()); });
})();

(function () {
  var cal = document.getElementById('nd-cal'), roster = document.getElementById('nd-voters');
  if (!cal || !roster) return;

  var box = document.createElement('div');
  box.className = 'nd-tc-legend';
  box.setAttribute('aria-label', 'Who each dot belongs to');
  cal.after(box);

  function entry(face) {
    var name = face.dataset.name, seal = face.querySelector('.nd-seal');
    var ink = seal ? seal.style.getPropertyValue('--seal-hsl').trim() : '';
    var shape = seal ? ['--tc-pip-r', '--tc-pip-clip'] : [];
    var li = document.createElement('li'), dot = document.createElement('i'), who = document.createElement('span');
    // the same colour and shape the pips show (noodle-tc.css .nd-tc-legend i);
    // no ink yet (your own seat, unsaved) is the plain ink
    if (ink) dot.style.setProperty('--seal-hsl', ink);
    else dot.className = 'plain';
    shape.forEach(function (k) { var v = seal.style.getPropertyValue(k); if (v) dot.style.setProperty(k, v); });
    // the name as its owner typed it (the face's label), not data-name's
    // lowercased identity
    var label = face.querySelector('.nd-face-name');
    who.textContent = (face.classList.contains('you') ? 'You' : (label ? label.textContent : name)) +
      (face.classList.contains('host') ? ' (host)' : '');
    li.append(dot, who);
    return li;
  }

  function draw() {
    // a blank seat (no name yet) owns no pip
    var faces = Array.prototype.filter.call(roster.querySelectorAll('.nd-face'),
      function (f) { return f.dataset.name || f.classList.contains('you'); });
    box.replaceChildren();
    box.hidden = !faces.length;
    if (!faces.length) return;
    var intro = document.createElement('p'), list = document.createElement('ul');
    intro.textContent = 'Each dot is one person who is free then:';
    faces.forEach(function (f) { list.append(entry(f)); });
    box.append(intro, list);
  }

  new MutationObserver(draw).observe(roster, { childList: true, subtree: true, attributes: true });
  draw();
})();
