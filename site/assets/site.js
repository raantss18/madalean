// Progressive enhancement only: theme toggle and the manual's search page. Every page works without it.
(function () {
  'use strict';
  var root = document.documentElement;

  // ---------------------------------------------------------------- theme: auto -> light -> dark -> auto
  var btn = document.getElementById('theme-toggle');
  if (btn) {
    var label = function () {
      var t = root.getAttribute('data-theme') || 'auto';
      var text = btn.getAttribute('data-' + t) || '';
      btn.setAttribute('aria-label', text);
      btn.setAttribute('title', text);
    };
    btn.hidden = false;
    label();
    btn.addEventListener('click', function () {
      var t = root.getAttribute('data-theme');
      var next = t === 'light' ? 'dark' : t === 'dark' ? null : 'light';
      if (next) root.setAttribute('data-theme', next); else root.removeAttribute('data-theme');
      try { if (next) localStorage.setItem('madalean-site-theme', next); else localStorage.removeItem('madalean-site-theme'); } catch (e) { /* ignore */ }
      label();
    });
  }

  // ---------------------------------------------------------------- search (prebuilt index, no server)
  var box = document.getElementById('search');
  if (!box) return;
  var input = document.getElementById('q');
  var status = document.getElementById('search-status');
  var list = document.getElementById('search-results');
  var fold = function (s) {
    return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  };
  var entries = null;
  fetch(box.getAttribute('data-index'), { credentials: 'same-origin' })
    .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then(function (data) {
      entries = data.map(function (e) {
        return { e: e, t: fold(e.t), h: fold(e.h || ''), x: fold((e.s || '') + ' ' + e.x) };
      });
      input.disabled = false;
      status.textContent = box.getAttribute('data-hint');
      var q0 = new URLSearchParams(location.search).get('q');
      if (q0) { input.value = q0; run(); }
      input.focus();
    })
    .catch(function () { status.textContent = box.getAttribute('data-none'); });

  function snippet(text, words) {
    var low = fold(text);
    var i = -1;
    for (var k = 0; k < words.length && i < 0; k++) i = low.indexOf(words[k]);
    var start = Math.max(0, i - 60);
    return (start > 0 ? '…' : '') + text.slice(start, start + 180) + (text.length > start + 180 ? '…' : '');
  }

  function run() {
    var q = fold(input.value.trim());
    while (list.firstChild) list.removeChild(list.firstChild);
    if (q.length < 2 || !entries) { status.textContent = box.getAttribute('data-hint'); return; }
    var words = q.split(/\s+/).filter(Boolean);
    var hits = [];
    entries.forEach(function (it) {
      var score = 0;
      for (var k = 0; k < words.length; k++) {
        var w = words[k];
        var s = (it.t.indexOf(w) >= 0 ? 6 : 0) + (it.h.indexOf(w) >= 0 ? 4 : 0) + (it.x.indexOf(w) >= 0 ? 1 : 0);
        if (!s) return;
        score += s;
      }
      hits.push([score, it]);
    });
    hits.sort(function (a, b) { return b[0] - a[0]; });
    hits.slice(0, 25).forEach(function (h) {
      var e = h[1].e;
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = e.u;
      a.textContent = e.h ? e.t + ' › ' + e.h : e.t;
      var p = document.createElement('p');
      p.textContent = snippet((e.s ? e.s + ' ' : '') + e.x, words);
      li.appendChild(a);
      li.appendChild(p);
      list.appendChild(li);
    });
    status.textContent = hits.length ? hits.length + ' ' + box.getAttribute('data-results') : box.getAttribute('data-none');
  }
  var timer = null;
  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 120); });
})();
