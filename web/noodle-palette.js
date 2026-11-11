// noodle's PALETTE SWITCH (owner, 2026-11-10): chevrons beside "Create a poll"
// on the start page and beside the title on a poll step through the palettes
// (noodle/pages.py PALETTES, handed in as the body's data-palettes: name ->
// theme-color). Every palette sheet is loaded and scoped to its body class, so
// a switch is one class swap. The choice is THIS BROWSER's (localStorage,
// never a cookie, never sent) and holds on both front ends; without one each
// front end shows its own default (pages.SKINS).
//
// Loaded FIRST in the body, before anything paints, so a chosen palette never
// flashes the default. The chevrons are wired by delegation: they need not
// exist yet.
var NDP_KEY = 'noodle.palette';

function ndpList() {
  try { return JSON.parse(document.body.dataset.palettes); } catch (e) { return {}; }
}

function ndpCurrent(list) {
  return Object.keys(list).find(function (p) { return document.body.classList.contains(p); });
}

// theme-color: a palette with none drops the tag (iOS then fades its bars
// over the page instead of painting a band)
function ndpTheme(color) {
  var tag = document.querySelector('meta[name="theme-color"]');
  if (!color) { if (tag) tag.remove(); return; }
  if (!tag) {
    tag = document.createElement('meta');
    tag.name = 'theme-color';
    document.head.append(tag);
  }
  tag.content = color;
}

function ndpUse(name) {
  var list = ndpList(), now = ndpCurrent(list);
  if (!Object.prototype.hasOwnProperty.call(list, name) || name === now) return;
  if (now) document.body.classList.remove(now);
  document.body.classList.add(name);
  ndpTheme(list[name]);
}

function ndpStep(by) {
  var list = ndpList(), names = Object.keys(list);
  var next = names[(names.indexOf(ndpCurrent(list)) + by + names.length) % names.length];
  ndpUse(next);
  try { localStorage.setItem(NDP_KEY, next); } catch (e) { /* blocked: this visit only */ }
}

(function () {
  var chosen = null;
  try { chosen = localStorage.getItem(NDP_KEY); } catch (e) { /* blocked */ }
  if (chosen) ndpUse(chosen);
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.nd-pal');
    if (b) ndpStep(b.classList.contains('prev') ? -1 : 1);
  });
})();
