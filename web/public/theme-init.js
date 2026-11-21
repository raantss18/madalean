// Applied before first paint (external file: the CSP forbids inline scripts).
(function () {
  try {
    var t = localStorage.getItem('madalean.theme');
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    var l = localStorage.getItem('madalean.lang');
    if (l === 'fr' || l === 'en') document.documentElement.lang = l;
    var d = localStorage.getItem('madalean.density');
    if (d === 'research') document.documentElement.setAttribute('data-mode', 'research');
  } catch (e) { /* storage blocked: defaults */ }
})();
