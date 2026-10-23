// noodle-tc's PIP LEGEND: under the calendar, whose pip is whose -- a swatch in
// each voter's pip colour and their name (owner, 2026-10-23). /noodle-tc
// hides the roster row (the name cards), so this is where the names live.
// Loaded only by the /noodle-tc shell (deferred); on a page with no calendar
// it does nothing.
//
// It READS the roster the shared JS still renders, hidden (noodle-roster.js
// ndrRender: one button.nd-face per voter, data-name, the ink as --seal-hsl on
// its pre.nd-seal; the host's carries .host, your own .you), and redraws on
// every change to it. It never writes shared state, and builds every name
// with textContent: a name is a voter's own text.
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
    var li = document.createElement('li'), dot = document.createElement('i'), who = document.createElement('span');
    // the same colour the pips show (noodle-tc.css .nd-tc-legend i): the
    // voter's ink, filtered; no ink yet (your own seat, unsaved) is the ink
    if (ink) dot.style.setProperty('--seal-hsl', ink);
    else dot.className = 'plain';
    who.textContent = (face.classList.contains('you') ? 'You' : name) +
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
