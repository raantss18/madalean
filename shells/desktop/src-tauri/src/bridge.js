// Injected by the Madalean desktop shell into every page of the main window.
// Remote pages get NO Tauri IPC: they reach the shell by navigating to madalean://shell/… URLs,
// which the shell's navigation handler intercepts (contract item 7 in docs/SHELLS.md).
(function () {
  if (!/^https?:$/.test(location.protocol)) return;
  var go = function (path) { location.href = 'madalean://shell/' + path; };
  // Filled in by the shell: 'desktop' (client AppImage) or 'host' (« Madalean Server », the host's own app: there is
  // no other server to change to, so no changeServer; Ctrl+Shift+K opens the server panel instead).
  var kind = '__MADALEAN_SHELL_KIND__';
  var bridge = {
    kind: kind,
    version: '__MADALEAN_SHELL_VERSION__',
    openExternal: function (url) { window.open(String(url), '_blank', 'noopener'); },
  };
  if (kind === 'desktop') bridge.changeServer = function () { go('change-server'); };
  try {
    Object.defineProperty(window, 'madaleanShell', {
      value: Object.freeze(bridge),
      writable: false, configurable: false,
    });
  } catch (e) { /* already defined */ }
  window.addEventListener('online', function () { go('check'); });
  // Ctrl+Shift+K: change server / server panel (works even if the web UI shows no button).
  window.addEventListener('keydown', function (e) {
    if (e.ctrlKey && e.shiftKey && (e.key === 'K' || e.key === 'k')) { e.preventDefault(); go('change-server'); }
  }, true);
  // Small toast used by the shell for download notifications.
  window.__madaleanToast = function (text, actionLabel, actionUrl) {
    var old = document.getElementById('__madalean_toast'); if (old) old.remove();
    var d = document.createElement('div');
    d.id = '__madalean_toast'; d.setAttribute('role', 'status');
    d.style.cssText = 'position:fixed;z-index:2147483647;left:50%;bottom:24px;transform:translateX(-50%);' +
      'background:#002b5c;color:#ffffff;font:14px/1.4 system-ui,sans-serif;padding:10px 14px;border-radius:10px;' +
      'box-shadow:0 6px 24px rgba(0,0,0,.3);display:flex;gap:12px;align-items:center;max-width:90vw';
    var s = document.createElement('span'); s.textContent = text; d.appendChild(s);
    if (actionLabel && actionUrl) {
      var b = document.createElement('button'); b.textContent = actionLabel;
      b.style.cssText = 'background:#fe7b01;color:#002b5c;border:0;border-radius:6px;padding:4px 10px;font:inherit;font-weight:600;cursor:pointer';
      b.onclick = function () { location.href = actionUrl; d.remove(); };
      d.appendChild(b);
    }
    (document.body || document.documentElement).appendChild(d);
    setTimeout(function () { d.remove(); }, 8000);
  };
})();
