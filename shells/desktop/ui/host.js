// Server panel of « Madalean Server » (host mode of the desktop shell, DECISIONS D50). Bundled page, local origin only.
'use strict';

const invoke = (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args || {});
const $ = (id) => document.getElementById(id);

const T = {
  fr: {
    intro: 'Le serveur Madalean de cet ordinateur : c’est lui qui fait tout le travail.',
    stateTitle: 'État', open: 'Ouvrir Madalean', start: 'Démarrer', stop: 'Arrêter', restart: 'Redémarrer',
    logs: 'Ouvrir les journaux', hideLogs: 'Masquer les journaux', browser: 'Ouvrir dans le navigateur',
    logsTitle: 'Journaux du serveur', refresh: 'Actualiser', other: 'English',
    foot: 'Sur les autres appareils (téléphone, autre ordinateur), utilisez l’application Madalean.',
    fixIntro: 'Pour l’installer, relancez l’installateur de Madalean (fichier « Madalean-installer.run »), ou dans un terminal :',
    phase: {
      checking: 'Recherche du serveur…', running: 'En marche', starting: 'Démarrage…', stopping: 'Arrêt…',
      stopped: 'Arrêté', failed: 'Arrêté après une erreur', not_installed: 'Service non installé',
      no_systemd: 'Pas lancé',
    },
    detail: {
      checking: () => '',
      running: (s) => `Madalean ${s.version} · ${s.url}`,
      starting: () => 'Le serveur se prépare ; Madalean s’ouvrira dans cette fenêtre dès qu’il répond.',
      stopping: () => 'Arrêt du serveur et de tous ses outils (Lean, modèles, calculs)…',
      stopped: () => 'Cliquez « Démarrer » pour le lancer.',
      failed: () => 'Regardez les journaux pour la cause, puis cliquez « Redémarrer ».',
      not_installed: (s) => `Le service « ${s.unit} » n’existe pas pour cet utilisateur.`,
      no_systemd: () => 'systemd n’est pas disponible ici : lancez le serveur à la main avec « madalean serve ».',
    },
    busy: { start: 'Démarrage demandé…', stop: 'Arrêt demandé…', restart: 'Redémarrage demandé…' },
    unmanaged: 'Ce serveur a été lancé hors du service (par exemple « madalean serve » dans un terminal) : arrêtez-le là où il a été lancé.',
    failedCmd: (e) => `La commande a échoué : ${e}`,
    noLogs: 'Aucune ligne de journal pour l’instant.',
    logsError: 'Impossible de lire les journaux (journalctl).',
    genericFix: 'cd <dossier de Madalean> && ./install.sh',
    version: (v) => `Madalean Server ${v}`,
  },
  en: {
    intro: 'This computer’s Madalean server: it does all the work.',
    stateTitle: 'Status', open: 'Open Madalean', start: 'Start', stop: 'Stop', restart: 'Restart',
    logs: 'Open the logs', hideLogs: 'Hide the logs', browser: 'Open in the browser',
    logsTitle: 'Server logs', refresh: 'Refresh', other: 'Français',
    foot: 'On other devices (phone, another computer), use the Madalean app.',
    fixIntro: 'To install it, run the Madalean installer again (the « Madalean-installer.run » file), or in a terminal:',
    phase: {
      checking: 'Looking for the server…', running: 'Running', starting: 'Starting…', stopping: 'Stopping…',
      stopped: 'Stopped', failed: 'Stopped after an error', not_installed: 'Service not installed',
      no_systemd: 'Not running',
    },
    detail: {
      checking: () => '',
      running: (s) => `Madalean ${s.version} · ${s.url}`,
      starting: () => 'The server is getting ready; Madalean opens in this window as soon as it answers.',
      stopping: () => 'Stopping the server and all its tools (Lean, models, computations)…',
      stopped: () => 'Click « Start » to launch it.',
      failed: () => 'See the logs for the cause, then click « Restart ».',
      not_installed: (s) => `There is no « ${s.unit} » service for this user.`,
      no_systemd: () => 'systemd is not available here: start the server by hand with « madalean serve ».',
    },
    busy: { start: 'Start requested…', stop: 'Stop requested…', restart: 'Restart requested…' },
    unmanaged: 'This server was started outside the service (for example « madalean serve » in a terminal): stop it where it was started.',
    failedCmd: (e) => `The command failed: ${e}`,
    noLogs: 'No log lines yet.',
    logsError: 'Cannot read the logs (journalctl).',
    genericFix: 'cd <Madalean folder> && ./install.sh',
    version: (v) => `Madalean Server ${v}`,
  },
};

let lang = 'fr';
let last = null;
const t = () => T[lang];

function applyTexts() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-t]').forEach((el) => {
    const v = t()[el.dataset.t];
    if (typeof v === 'string') el.textContent = v;
  });
  $('lang').textContent = t().other;
  $('logs-btn').textContent = $('logs').hidden ? t().logs : t().hideLogs;
  if (last) render(last);
}

function render(s) {
  last = s;
  if (s.lang && s.lang !== lang && !render.userLang) { lang = s.lang; applyTexts(); return; }
  const L = t();
  $('dot').className = `dot ${s.phase}`;
  $('phase').textContent = L.phase[s.phase] || s.phase;
  $('detail').textContent = s.busy ? L.busy[s.busy] : (L.detail[s.phase] || (() => ''))(s);
  $('detail').hidden = !$('detail').textContent;
  const unmanaged = s.phase === 'running' && !s.managed && s.service !== null;
  $('hint').hidden = !unmanaged;
  $('hint').textContent = unmanaged ? L.unmanaged : '';
  $('fix').hidden = s.phase !== 'not_installed';
  $('fix-cmd').textContent = s.install_sh ? `bash '${s.install_sh}'` : L.genericFix;
  $('error').hidden = !s.error;
  $('error').textContent = s.error ? L.failedCmd(s.error) : '';
  $('open').hidden = s.phase !== 'running';
  $('start').disabled = !s.can_start;
  $('stop').disabled = !s.can_stop;
  $('restart').disabled = !s.can_restart;
  $('browser').disabled = s.phase !== 'running';
  $('version').textContent = L.version(s.app_version);
}

async function poll() {
  try { render(await invoke('host_status')); } catch (e) { /* not in host mode / starting */ }
}

async function loadLogs() {
  $('logs-text').textContent = '…';
  try {
    const text = await invoke('host_logs', { lines: 300 });
    $('logs-text').textContent = text.trim() || t().noLogs;
    $('logs-text').scrollTop = $('logs-text').scrollHeight;
  } catch (e) {
    $('logs-text').textContent = t().logsError;
  }
}

function showLogs(show) {
  $('logs').hidden = !show;
  $('logs-btn').setAttribute('aria-expanded', String(show));
  $('logs-btn').textContent = show ? t().hideLogs : t().logs;
  if (show) { loadLogs(); $('logs').scrollIntoView({ block: 'nearest' }); }
}

function onHash() {
  // #reason=logs from the « Ouvrir les journaux » menu item; other reasons need nothing special.
  if (/reason=logs/.test(location.hash)) showLogs(true);
}

const act = (action) => async () => {
  try { await invoke('host_action', { action }); } catch (e) { /* shown by the next status */ }
  poll();
};

document.addEventListener('DOMContentLoaded', () => {
  $('start').addEventListener('click', act('start'));
  $('stop').addEventListener('click', act('stop'));
  $('restart').addEventListener('click', act('restart'));
  $('open').addEventListener('click', () => invoke('host_open', { what: 'ui' }));
  $('browser').addEventListener('click', () => invoke('host_open', { what: 'browser' }));
  $('logs-btn').addEventListener('click', () => showLogs($('logs').hidden));
  $('logs-refresh').addEventListener('click', loadLogs);
  $('lang').addEventListener('click', async () => {
    lang = lang === 'fr' ? 'en' : 'fr';
    render.userLang = true;
    try { await invoke('set_lang', { lang }); } catch (e) { /* kept for this session */ }
    applyTexts();
  });
  window.addEventListener('hashchange', onHash);
  applyTexts();
  onHash();
  poll();
  setInterval(poll, 1500);
});
