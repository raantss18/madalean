// Applies the saved theme before first paint (loaded synchronously in <head>; no inline script under the CSP).
(function () {
  try {
    var t = localStorage.getItem('madalean-site-theme');
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
  } catch (e) { /* storage unavailable: automatic theme */ }
})();
