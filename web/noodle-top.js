// noodle's TOP DATES: every slot at least one GUEST picked (the host's own
// offer alone is not a result), most voters first, soonest first on a tie,
// drawn above "make another noodle". A table: one row per slot -- date
// "tue dd/mm/yyyy" (once per day, rowspan), <glyph>, then the voters' dots --
// so the dots line up in columns like the calendar's: each voter free that
// DAY owns one column (vote order, in their seal ink), a gap in the half they
// are not; nobody free that day takes a column (2026-10-31).
// The glyph is there only on a SPLIT poll: sun = midday, moon = night (Font
// Awesome U+F185 / U+F186 from noodle-seal.woff2, text glyphs, not emoji);
// they ink about two cells, so they sit in a fixed two-cell box (noodle.css).

var NDT_DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
var NDT_GLYPH = { m: '', n: '' };

// '2026-09-28' -> 'mon 28/09/2026'
function ndtDate(iso) {
  var p = iso.split('-');
  var wd = new Date(+p[0], +p[1] - 1, +p[2]).getDay();
  return NDT_DAYS[wd] + ' ' + p[2] + '/' + p[1] + '/' + p[0];
}

// cols as the calendar has them (noodle-vote.js ndvRefreshBinding): a stored
// vote's {slots}, or YOUR {self} column, which reads the live selection.
// cols[0] is always the HOST (vote order; on a fresh poll it is your own
// column, the host-to-be). -> [{slot, cols: [bool per column]}], best first.
function ndtRank(cols, sel, today, crop) {
  var count = new Map(), guests = new Set();
  cols.forEach(function (c, i) {
    (c.self ? sel : c.slots).forEach(function (s) {
      var d = s.slice(0, 10);
      if (d < today || (crop && (d < crop.from || d > crop.to))) return;
      count.set(s, (count.get(s) || 0) + 1);
      if (i > 0) guests.add(s);
    });
  });
  return Array.from(guests).sort(function (a, b) {
    return count.get(b) - count.get(a) || (a < b ? -1 : 1);   // a tie goes to the soonest
  }).map(function (s) {
    return { slot: s, cols: cols.map(function (c) { return (c.self ? sel : c.slots).has(s); }) };
  });
}

// Ranked slots -> one group per DAY, in the order of each day's best slot,
// its slots midday before night: a day's two halves sit one under the other.
function ndtByDay(rows) {
  var days = new Map();
  rows.forEach(function (r) {
    var d = r.slot.slice(0, 10);
    if (!days.has(d)) days.set(d, []);
    days.get(d).push(r);
  });
  return Array.from(days, function (e) {
    return { day: e[0], rows: e[1].sort(function (a, b) { return a.slot < b.slot ? -1 : 1; }) };
  });
}

function ndtRender(cols, sel) {
  var el = document.getElementById('nd-top');
  if (!el) return;
  var P = window.NoodleCalParts, crop = window.ndhCrop ? window.ndhCrop() : null;
  var rows = ndtRank(cols || [], sel || new Set(), P.iso(new Date()), crop);
  // the EVENT TIME (noodle-event.js): the host ticks it here; once it is
  // chosen, everyone else sees only those rows (owner, 2026-10-31)
  var pick = window.ndevPickable && window.ndevPickable();
  var event = window.ndevChosen ? window.ndevChosen() : [], chosen = new Set(event);
  if (!pick && event.length) {
    rows = event.map(function (s) {
      return { slot: s, cols: (cols || []).map(function (c) { return (c.self ? sel : c.slots).has(s); }) };
    });
  }
  var box = el.closest('.nd-top-box');
  box.hidden = !rows.length;   // the box with its label
  // which heading a front end gives it: the host's, or the host's choice
  box.classList.toggle('nd-top-host', !!pick);
  box.classList.toggle('nd-top-chosen', !pick && event.length > 0);
  el.innerHTML = ndtByDay(rows).map(function (g) {
    // only the voters free some part of THIS day get a column, as in the
    // calendar's cell (noodle-cal.js ndDotsLit): no empty columns
    var free = cols.map(function (_, i) { return g.rows.some(function (r) { return r.cols[i]; }); });
    return g.rows.map(function (r, j) {
      var k = r.slot.slice(11);
      var dots = r.cols.map(function (on, i) {
        if (!free[i]) return '';
        var ink = cols[i].ink;
        return '<i' + (on ? ' class="on"' + (ink ? ' style="--seal-hsl:' + ink + '"' : '') : '') + '></i>';
      }).join('');
      // the host's box FIRST, one per slot (the date's rowspan leaves the
      // night row's first column free for its own); the date once, spanning
      // its day's rows; the glyph only on a split poll
      return '<tr>' +
        (pick ? '<td class="nd-top-tick"><input type="checkbox" class="nd-top-pick" aria-label="event time" data-slot="' +
          r.slot + '"' + (chosen.has(r.slot) ? ' checked' : '') + '></td>' : '') +
        (j ? '' : '<th class="nd-top-date" scope="row" rowspan="' + g.rows.length + '">' + ndtDate(g.day) + '</th>') +
        (k === 'd' ? '' : '<td class="nd-top-glyph">' + NDT_GLYPH[k] + '</td>') +
        '<td><span class="nd-top-dots">' + dots + '</span></td></tr>';
    }).join('');
  }).join('');
}

window.ndtRender = ndtRender;
