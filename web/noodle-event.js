// noodle's EVENT TIME (owner, 2026-10-31): the host ticks one or more of the
// top dates (noodle-top.js, a checkbox per row) as WHEN it happens, and
// everyone sees them under the title (#nd-event). Sealed in the head beside
// the title and note (noodle-e2e.js ndeSealHead), so only an end-to-end poll
// has one, and sent with Commit like the title (noodle-host.js
// ndhCommitSettings); unsaved, it is NDV.pendingEvent, kept in the draft.
// Same global scope as noodle-vote.js; loaded after noodle-top.js.

var NDEV_MAX = 8;   // mirrors NDE_EVENT_MAX: more than any poll needs

function ndevSaved() { return (NDV.poll && NDV.poll.event) || []; }

function ndevChosen() { return NDV.pendingEvent !== undefined ? NDV.pendingEvent : ndevSaved(); }

// the host, with their key, on a poll that can seal one
function ndevPickable() { return !!(NDV.e2e && NDV.poll && window.ndxIsHost && window.ndxIsHost()); }

function ndevToggle(slot, on) {
  var set = new Set(ndevChosen());
  if (on) set.add(slot); else set.delete(slot);
  var next = Array.from(set).sort().slice(0, NDEV_MAX);
  NDV.pendingEvent = next.join() === ndevSaved().join() ? undefined : next;
  ndevShow();
  ndvSaveDraft();   // marks it unsaved, and redraws the top dates' boxes
}

// The line under the title: each chosen slot as the top dates write it
// ("tue 03/11/2026", reworded by a front end's copy table) and, on a split
// poll, its sun or moon. Built with textContent: the slots came out of a
// sealed head anyone with the link could have written.
function ndevShow() {
  var el = ndv$('nd-event');
  if (!el) return;
  var ev = ndevChosen();
  el.hidden = !ev.length;
  el.replaceChildren.apply(el, ev.map(function (s) {
    var li = document.createElement('li'), date = document.createElement('span'), k = s.slice(11);
    date.className = 'nd-event-date';
    date.textContent = ndtDate(s.slice(0, 10));
    li.append(date);
    if (k !== 'd') {
      var g = document.createElement('span');
      g.className = 'nd-event-glyph';
      g.textContent = NDT_GLYPH[k];
      li.append(' ', g);
    }
    return li;
  }));
}

(function () {
  var top = document.getElementById('nd-top');
  if (!top) return;
  top.addEventListener('change', function (e) {
    var box = e.target.closest('input.nd-top-pick');
    if (box && ndevPickable()) ndevToggle(box.dataset.slot, box.checked);
  });
  window.ndevShow = ndevShow;
  window.ndevChosen = ndevChosen;
  window.ndevPickable = ndevPickable;
  // noodle-vote.js now waits for every script before loading the poll; this
  // catch-up is the second line of defence, should the poll ever land before
  // this file again (the time "vanished" on reload in Chrome, 2026-10-31)
  if (window.NDV && NDV.poll) {
    ndevShow();
    if (NDV.cal && NDV.cols && window.ndtRender) window.ndtRender(NDV.cols, NDV.cal.getSel());
  }
})();
