// noodle-tc's WORDING: the same pages as /noodle, said plainly and
// professionally (owner, 2026-10-23). Loaded ONLY by the /noodle-tc shell, in
// the <head>, so it sees every node as the parser and the shared JS add them.
// It rewrites what the shared code writes rather than forking that code:
//   - a text node (or placeholder / title / aria-label) whose WHOLE trimmed text
//     is a key in NDTC_EXACT becomes its value;
//   - otherwise the first NDTC_PATTERNS entry that matches rewrites it (the
//     messages with a name, a number or a server error spliced in);
//   - NDTC_HTML replaces the inside of a few small fixed blocks outright.
// MutationObserver callbacks run before the browser paints, so the original
// wording never shows. The shared JS never reads its own words back.
//
// NEVER touched: poll CONTENT -- the title, the note, voters' names, the link
// field, the Ask box's text (NDTC_SKIP). noodle-host.js reads the title's text
// to spot the "title" placeholder; that one is restyled in noodle-tc.css.
(function () {
  var NDTC_EXACT = {
    // the page
    'noodle': 'Find a time', 'create poll': 'Create a poll',
    // [P6] says a link leaves the page -- but NOT for the encryption link,
    // whose "(opens GitHub)" the owner dropped (2026-10-23)
    'end-to-end encrypted': 'End-to-end encrypted',
    'you are': 'Responding as', 'edit': 'Change', 'change': 'Change',
    'your name': 'Your name', 'passphrase (optional)': 'Passphrase (optional)',
    'no passphrase: anyone can change your vote': 'Without a passphrase, anyone can change your response.',
    'no passphrase: anyone can change the entire poll, what a chaotic host':
      'Without a passphrase, anyone can edit this poll.',
    'next: pick times': 'Continue', 'next: offer times': 'Continue',
    // the step label above it already says what to do
    'when are you free? (everyone can see)': 'Everyone with the link can see responses.',
    'split each day into halves': 'Split each day into daytime and evening',
    'Commit': 'Save', 'Commit*': 'Save', 'committed.': 'Saved.',
    '* unsaved changes': 'Unsaved changes', 'all changes saved': 'All changes saved',
    'or ask noodle': 'Or describe your availability', 'help me': 'Fill in for me',
    'your noodle polls are end-to-end encrypted': 'Polls are end-to-end encrypted.',
    'noodle helper chatbot is not (it needs to read your requests to pick dates)':
      'The availability assistant is not: it reads your request to select dates.',
    'make another noodle': 'Create another poll', 'make your own noodle': 'Create your own poll',
    'I found a bug!': 'Report a problem (opens your email)', 'link copied to clipboard': 'Link copied',
    'host': 'Host', 'remove': 'Remove', 'you': 'You',
    // no month names here: the week column fits the longest of "october 2026"
    // / "october" / "oct" to its run (ndcPaintLabels), and expanding the short
    // one AFTER that fit overflowed a one-week run ("Novembe"); CSS capitalizes
    // placeholders, tooltips, labels
    'please help the host know who you are': 'Enter your name',
    'how shall the guests address you, host?': 'Enter your name',
    "you'll need this to change your vote": 'Needed to change your response later',
    'please enter your passphrase': 'Enter your passphrase', 'kept on this device': 'Saved on this device',
    'new name': 'New name', 'new passphrase': 'New passphrase',
    'your passphrase (same or new)': 'Passphrase (current or new)',
    'only available every in the morning on odd days\nnever tuesdays\nand also, at night on stat holidays\noh and, next monday, I\'m free all day':
      'For example: weekday mornings, not Tuesdays, all day next Monday',
    'link to this poll': 'Poll link', 'copy link': 'Copy link',
    'first week': 'First week', 'last week': 'Last week',
    'no last week yet -- drag to set one': 'No end date yet. Drag to set one.',
    'drag: first week': 'Drag to set the first week', 'drag: last week': 'Drag to set the last week',
    // reasons under the buttons
    'enter your name first': 'Enter your name to continue.',
    'that name is too long, or has characters that cannot be used':
      'Names may use letters, numbers and spaces, up to 40 characters.',
    'this browser could not make a key': 'This browser is not supported.',
    'making your key...': 'Preparing...',
    'pick at least one available time, guests can only pick from yours':
      'Select at least one time. Participants can only choose from the times you offer.',
    // errors and statuses
    'could not commit': 'Your response could not be saved.',
    'could not save the split, crop or title': 'The poll settings could not be saved.',
    'could not make the change': 'The change could not be saved.',
    'could not remove': 'The participant could not be removed.',
    'could not start a poll': 'The poll could not be created.',
    'help how? type in box pls': 'Describe your availability first.',
    'noodle could not answer': 'The assistant could not answer. Please try again.',
    'noodle could not be reached': 'The assistant is unavailable right now.',
    'this browser cannot make a key -- a current Safari, Chrome or Firefox is needed':
      'This browser is not supported. Please use a current version of Safari, Chrome or Firefox.',
    'this link is missing its key (the part after #). ask whoever sent it for the whole link.':
      'This link is incomplete. Ask the sender for the full link, including the part after #.',
  };

  var NDTC_PATTERNS = [
    [/^"(.+)" is already sealed with a different passphrase$/, 'That passphrase does not match "$1".'],
    [/^"(.+)" is already taken$/, '"$1" is already in use. Choose a different name.'],
    [/^approved by (.+)$/, 'Response saved for $1'],
    [/^too fast, wait (\d+)s =_=$/, 'Please wait $1 seconds and try again.'],
    [/^noodle read that as: (.*) -- (\d+) slots filled(?: \((\d+) unusable rule\(s\) skipped\))?\. check the calendar, then commit\.$/,
      'Understood as: $1. $2 times selected. Review the calendar, then save.'],
    [/^noodle read that as: (.*) -- nothing on this calendar matched(?: \(\d+ unusable rule\(s\) skipped\))?, so your picks are unchanged\.$/,
      'Understood as: $1. No matching times were found, so your selection is unchanged.'],
    [/^could not commit: (.+)$/, 'Your response could not be saved ($1).'],
    [/^could not make the change: (.+)$/, 'The change could not be saved ($1).'],
    [/^could not load the poll \((.+)\)$/, 'The poll could not be loaded ($1).'],
    [/^could not make a key in this browser \(.*\)\. a current Safari, Chrome or Firefox is needed\.$/,
      'This browser is not supported. Please use a current version of Safari, Chrome or Firefox.'],
    [/^something failed: (.+)$/, 'Something went wrong ($1).'],
    [/^title must be 1-(\d+) characters$/, 'The title must be 1 to $1 characters.'],
    [/^note must be at most (\d+) characters$/, 'The note can be at most $1 characters.'],
    [/^remove (.+) and their vote\?$/, 'Remove $1 and their response?'],
    [/^noodle: (.+)$/, '$1'],   // the tab title of a plain poll
    // [P10] the top-dates table (noodle-top.js ndtDate): "fri 23/10/2026"
    [/^(sun|mon|tue|wed|thu|fri|sat) (\d\d)\/(\d\d)\/\d{4}$/, function (m, wd, d, mo) {
      return NDTC_WEEKDAYS[wd] + ' ' + Number(d) + ' ' + NDTC_MONTHS[Number(mo) - 1];
    }],
  ];

  var NDTC_WEEKDAYS = { sun: 'Sunday', mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday',
    thu: 'Thursday', fri: 'Friday', sat: 'Saturday' };
  var NDTC_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];

  // the first-poll guide in the roster (noodle-roster.js NDR_HOWTO)
  var NDTC_HTML = {
    'nd-howto': '<p><b>You are the host.</b></p><p>Sign in with your name and an optional passphrase.</p>' +
      '<p>Select the times you can offer.</p><p>Save, then share the link.</p>',
  };

  // (#nd-ask / #nd-url hold their text as a VALUE, never a node: their
  // placeholder and label are reworded like any other)
  var NDTC_SKIP = '#nd-title, #nd-note, .nd-face-name, #nd-you-name, .nd-tc-legend li';
  var ATTRS = ['placeholder', 'title', 'aria-label'];

  function said(s) {
    var key = s.trim();
    if (!key) return null;
    if (Object.prototype.hasOwnProperty.call(NDTC_EXACT, key)) return NDTC_EXACT[key];
    for (var i = 0; i < NDTC_PATTERNS.length; i++) {
      if (NDTC_PATTERNS[i][0].test(key)) return key.replace(NDTC_PATTERNS[i][0], NDTC_PATTERNS[i][1]);
    }
    return null;
  }

  function skipped(el) { return !!(el && el.closest && el.closest(NDTC_SKIP)); }

  function text(node) {
    if (skipped(node.parentElement)) return;
    var v = node.nodeValue, to = said(v);
    if (to === null || to === v.trim()) return;
    // keep the spacing around it ("you are " runs into the <b>name</b> after it)
    node.nodeValue = v.match(/^\s*/)[0] + to + v.match(/\s*$/)[0];
  }

  function attrs(el) {
    if (skipped(el)) return;
    ATTRS.forEach(function (a) {
      var v = el.getAttribute(a), to = v === null ? null : said(v);
      if (to !== null && to !== v) el.setAttribute(a, to);
    });
  }

  function walk(root) {
    if (root.nodeType === 3) { text(root); return; }
    if (root.nodeType !== 1) return;
    if (root.classList) {
      for (var cls in NDTC_HTML) {
        if (root.classList.contains(cls) && root.innerHTML !== NDTC_HTML[cls]) root.innerHTML = NDTC_HTML[cls];
      }
    }
    attrs(root);
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (var n = w.nextNode(); n; n = w.nextNode()) {
      if (n.nodeType === 3) text(n); else attrs(n);
    }
  }

  new MutationObserver(function (records) {
    records.forEach(function (r) {
      if (r.type === 'childList') r.addedNodes.forEach(walk);
      else if (r.type === 'characterData') text(r.target);
      else if (r.type === 'attributes') attrs(r.target);
    });
  }).observe(document.documentElement, {
    childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS,
  });

  // what the parser had already built before this script ran (the <title>)
  walk(document.documentElement);

  // the host's "remove this guest?" prompt is a native dialog, not the DOM
  var ask = window.confirm;
  window.confirm = function (msg) { return ask.call(window, said(String(msg)) || msg); };
})();
