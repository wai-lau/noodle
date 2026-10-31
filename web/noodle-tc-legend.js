// noodle-tc's PIPS: their colours and shapes, and the LEGEND (in one card with
// the most popular times) -- whose pip is whose, a swatch in each voter's pip colour and
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
// PIP COLOURS: the shared palette (noodle-ink.js; this skin's dark
// --nd-ink-* in noodle-tc.css). Past its length colours repeat, so each
// ROUND of 8 voters takes a SHAPE: circle, square, triangle. The shape rides IN the ink
// string as two more custom properties: the shared code drops the ink into a
// style attribute verbatim, and noodle-tc.css reads them (--tc-pip-r,
// --tc-pip-clip). A poll that loaded before this (deferred) script ran is
// re-inked here.
var NDTC_SHAPES = ['', ';--tc-pip-r:0', ';--tc-pip-r:0;--tc-pip-clip:polygon(50% 0,100% 100%,0 100%)'];

(function () {
  var I = window.NoodleInk, R = window.NoodleRoster;
  if (!I || !R || !window.NDV) return;
  var of = I.of;
  I.of = function (pub) {
    return of(pub) + NDTC_SHAPES[I.place(pub).round % NDTC_SHAPES.length];
  };
  if (NDV.poll) R.seals(NDV.poll.voters).then(function (out) { NDV.seals = out; window.ndvRefreshBinding(window.ndvPub()); });
})();

(function () {
  var cal = document.getElementById('nd-cal'), roster = document.getElementById('nd-voters');
  if (!cal || !roster) return;

  var box = document.createElement('div');
  box.className = 'nd-tc-legend';
  box.setAttribute('aria-label', 'Who each dot belongs to');

  // ONE card (owner, 2026-10-31): the legend and the host's top dates,
  // merged. On the pick step it sits right under the calendar, with Save,
  // its status and any error (the banner, otherwise at the top of the page)
  // under it; on the name step (the pick hidden) under Continue, the banner
  // between them.
  var root = document.getElementById('noodle'), banner = document.getElementById('nd-banner');
  var card = document.createElement('section'), top = document.getElementById('nd-top-box');
  card.className = 'nd-tc-card';
  card.append(box);
  if (top) card.append(top);
  function place() {
    var pick = root.classList.contains('nd-step-pick');
    var cal = document.getElementById('nd-cal'), dirty = document.getElementById('nd-dirty');
    var you = document.getElementById('nd-you');
    if (pick && cal.nextSibling !== card) cal.after(card);
    if (pick && dirty.nextSibling !== banner) dirty.after(banner);
    if (!pick && (you.nextSibling !== banner || banner.nextSibling !== card)) you.after(banner, card);
  }
  new MutationObserver(place).observe(root, { attributes: true, attributeFilter: ['class'] });
  place();

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
    // no intro line (owner, 2026-10-30): the pips beside names say it
    var list = document.createElement('ul');
    faces.forEach(function (f) { list.append(entry(f)); });
    box.append(list);
  }

  new MutationObserver(draw).observe(roster, { childList: true, subtree: true, attributes: true });
  draw();
})();
