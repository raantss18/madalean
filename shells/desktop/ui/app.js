// Connect screen of the Madalean desktop shell (bundled, local origin only).
'use strict';

const invoke = (cmd, args) => window.__TAURI_INTERNALS__.invoke(cmd, args || {});
const $ = (id) => document.getElementById(id);

const T = {
  fr: {
    title: 'Connectez-vous à votre Madalean',
    intro: 'L’ordinateur hôte fait tout le travail ; cette fenêtre affiche son interface.',
    retry: 'Réessayer', saved: 'Serveurs enregistrés', newServer: 'Nouveau serveur',
    address: 'Adresse du serveur', placeholder: 'nom-du-pc.votre-tailnet.ts.net',
    addressHelp: 'Nom Tailscale complet (port 10500 par défaut), ou collez ici un lien madalean://pair.',
    code: 'Code d’appairage', device: 'Nom de cet appareil',
    codeHelp: 'Les 6 chiffres affichés sur l’ordinateur hôte (Réglages → Appareils), valables 5 minutes.',
    pairBtn: 'Appairer et ouvrir', openBtn: 'Ouvrir', forgetBtn: 'Oublier', other: 'English',
    localHint: 'Sur l’ordinateur hôte, l’interface s’ouvre directement, sans code.',
    updTitle: 'Mises à jour', updAuto: 'Mises à jour automatiques', updCheck: 'Vérifier maintenant', updRestart: 'Redémarrer',
    updHelp: 'Vérifie deux fois par jour, télécharge et contrôle la signature, puis installe au prochain démarrage.',
    upd: {
      idle: (u) => `Version ${u.current}.`, checking: () => 'Vérification…',
      downloading: (u) => `Téléchargement de la version ${u.version}… ${u.progress} %`,
      ready: (u) => `Version ${u.version} installée : elle s’ouvrira au prochain démarrage.`,
      available: (u) => u.installable ? `Version ${u.version} disponible.` : `Version ${u.version} disponible : téléchargez la nouvelle AppImage (ce programme n’est pas lancé comme AppImage).`,
      up_to_date: (u) => `Version ${u.current} : à jour.`,
    },
    updErr: {
      no_key: 'Mises à jour désactivées dans cette version de développement (pas de clé).',
      unsigned: 'Mise à jour refusée : manifeste non signé.', bad_signature: 'Mise à jour refusée : signature invalide.',
      bad_channel: 'Mise à jour refusée : manifeste d’un autre canal.', bad_manifest: 'Mise à jour refusée : manifeste incorrect.',
      no_file: 'Aucune AppImage dans cette version.', network: 'Serveur de mises à jour injoignable : nouvel essai plus tard.',
      size: 'Mise à jour refusée : taille incorrecte.', checksum: 'Mise à jour refusée : empreinte SHA-256 incorrecte.',
      not_writable: 'Impossible de remplacer l’AppImage (dossier en lecture seule).',
      too_old: 'Cette version est trop ancienne pour la mise à jour automatique : téléchargez la nouvelle AppImage depuis la page de téléchargement.',
    },
    thisComputer: 'Cet ordinateur (hôte)', lastUsed: 'utilisé le', paired: 'appairé', notPaired: 'à appairer',
    checkingLocal: 'Recherche d’un serveur Madalean sur cet ordinateur…',
    opening: (h) => `Ouverture de ${h}…`, pairing: 'Appairage…',
    forgetConfirm: (h) => `Oublier ${h} ? Il faudra appairer cet appareil à nouveau.`,
    linkFilled: 'Lien d’appairage reçu : vérifiez puis cliquez « Appairer et ouvrir ».',
    reason: {
      manual: '', link: '',
      unreachable: 'Le serveur ne répond plus. Vérifiez que l’ordinateur hôte est allumé et que Tailscale est connecté.',
      revoked: 'Cet appareil n’est plus autorisé par l’hôte. Appairez-le à nouveau avec un nouveau code.',
      session_failed: 'Impossible d’ouvrir une session sur le serveur. Réessayez ou appairez à nouveau.',
    },
    err: {
      address: { empty: 'Indiquez l’adresse du serveur.', invalid: 'Adresse invalide.',
        cleartext_forbidden: 'Seules les adresses https:// sont acceptées (http seulement vers cet ordinateur).',
        need_full_name: 'Utilisez le nom complet, par ex. mon-pc.mon-tailnet.ts.net (le certificat HTTPS est émis pour ce nom).' },
      unreachable: 'Serveur injoignable. L’ordinateur hôte est-il allumé, Madalean lancé et Tailscale connecté sur les deux appareils ?',
      tls: 'Connexion sécurisée impossible (certificat). Utilisez le nom complet *.ts.net et vérifiez que HTTPS est activé dans Tailscale.',
      not_madalean: 'Cette adresse ne répond pas comme un serveur Madalean.',
      bad_code: 'Code incorrect ou expiré. Affichez un nouveau code sur l’hôte.',
      locked: (s) => `Trop d’essais : appairage bloqué${s ? ` (réessayez dans ${Math.ceil(s / 60)} min)` : ''}.`,
      revoked: 'Cet appareil n’est plus autorisé. Appairez-le à nouveau.',
      need_pairing: 'Cet appareil n’est pas encore appairé avec ce serveur : saisissez le code affiché sur l’hôte.',
      server: (s) => `Erreur du serveur (${s}).`, storage: 'Impossible d’enregistrer le jeton sur cet ordinateur.',
      internal: 'Erreur interne.', code_format: 'Le code comporte 6 chiffres.',
    },
  },
  en: {
    title: 'Connect to your Madalean',
    intro: 'The host computer does all the work; this window shows its interface.',
    retry: 'Retry', saved: 'Saved servers', newServer: 'New server',
    address: 'Server address', placeholder: 'your-pc.your-tailnet.ts.net',
    addressHelp: 'Full Tailscale name (port 10500 by default), or paste a madalean://pair link here.',
    code: 'Pairing code', device: 'Name of this device',
    codeHelp: 'The 6 digits shown on the host computer (Settings → Devices), valid for 5 minutes.',
    pairBtn: 'Pair and open', openBtn: 'Open', forgetBtn: 'Forget', other: 'Français',
    localHint: 'On the host computer itself, the interface opens directly, no code needed.',
    updTitle: 'Updates', updAuto: 'Automatic updates', updCheck: 'Check now', updRestart: 'Restart',
    updHelp: 'Checks twice a day, downloads and verifies the signature, then installs at the next start.',
    upd: {
      idle: (u) => `Version ${u.current}.`, checking: () => 'Checking…',
      downloading: (u) => `Downloading version ${u.version}… ${u.progress} %`,
      ready: (u) => `Version ${u.version} installed: it opens at the next start.`,
      available: (u) => u.installable ? `Version ${u.version} available.` : `Version ${u.version} available: download the new AppImage (this program is not running as an AppImage).`,
      up_to_date: (u) => `Version ${u.current}: up to date.`,
    },
    updErr: {
      no_key: 'Updates disabled in this development build (no key).',
      unsigned: 'Update refused: unsigned manifest.', bad_signature: 'Update refused: invalid signature.',
      bad_channel: 'Update refused: manifest of another channel.', bad_manifest: 'Update refused: malformed manifest.',
      no_file: 'No AppImage in this release.', network: 'Update server unreachable: will retry later.',
      size: 'Update refused: wrong size.', checksum: 'Update refused: SHA-256 mismatch.',
      not_writable: 'Cannot replace the AppImage (read-only folder).',
      too_old: 'This version is too old to update automatically: download the new AppImage from the download page.',
    },
    thisComputer: 'This computer (host)', lastUsed: 'used on', paired: 'paired', notPaired: 'needs pairing',
    checkingLocal: 'Looking for a Madalean server on this computer…',
    opening: (h) => `Opening ${h}…`, pairing: 'Pairing…',
    forgetConfirm: (h) => `Forget ${h}? This device will have to be paired again.`,
    linkFilled: 'Pairing link received: check it, then click “Pair and open”.',
    reason: {
      manual: '', link: '',
      unreachable: 'The server stopped answering. Check that the host computer is on and Tailscale is connected.',
      revoked: 'This device is no longer authorised by the host. Pair it again with a new code.',
      session_failed: 'Could not open a session on the server. Retry or pair again.',
    },
    err: {
      address: { empty: 'Enter the server address.', invalid: 'Invalid address.',
        cleartext_forbidden: 'Only https:// addresses are accepted (http only to this computer).',
        need_full_name: 'Use the full name, e.g. my-pc.my-tailnet.ts.net (the HTTPS certificate is issued for that name).' },
      unreachable: 'Server unreachable. Is the host computer on, Madalean running and Tailscale connected on both devices?',
      tls: 'Secure connection failed (certificate). Use the full *.ts.net name and check that HTTPS is enabled in Tailscale.',
      not_madalean: 'This address does not answer like a Madalean server.',
      bad_code: 'Wrong or expired code. Show a new code on the host.',
      locked: (s) => `Too many attempts: pairing locked${s ? ` (retry in ${Math.ceil(s / 60)} min)` : ''}.`,
      revoked: 'This device is no longer authorised. Pair it again.',
      need_pairing: 'This device is not paired with this server yet: enter the code shown on the host.',
      server: (s) => `Server error (${s}).`, storage: 'Could not store the token on this computer.',
      internal: 'Internal error.', code_format: 'The code has 6 digits.',
    },
  },
};

let lang = 'fr';
let state = null;
let lastAction = null;
const t = () => T[lang];

function errorText(e) {
  if (!e || typeof e !== 'object') return t().err.internal;
  const m = t().err;
  switch (e.code) {
    case 'address': return m.address[e.reason] || m.address.invalid;
    case 'locked': return m.locked(e.retry_after);
    case 'server': return m.server(e.status);
    default: return typeof m[e.code] === 'string' ? m[e.code] : m.internal;
  }
}

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-t]').forEach((el) => {
    const v = t()[el.dataset.t];
    if (typeof v === 'string') el.textContent = v;
  });
  $('lang').textContent = t().other;
  $('address').placeholder = t().placeholder;
  renderServers();
}

function setStatus(text, kind, retry) {
  const s = $('status');
  if (!text) { s.hidden = true; return; }
  s.hidden = false;
  s.className = 'status' + (kind === 'error' ? ' error' : '');
  $('status-text').textContent = text;
  lastAction = retry || null;
  $('retry').hidden = !retry;
}

function setFormError(text) {
  const e = $('form-error');
  e.hidden = !text;
  e.textContent = text || '';
}

function busy(on) {
  $('submit').disabled = on;
  document.querySelectorAll('.servers button').forEach((b) => { b.disabled = on; });
}

function renderServers() {
  if (!state) return;
  const ul = $('servers');
  ul.textContent = '';
  const list = state.servers;
  $('saved').hidden = list.length === 0;
  for (const s of list) {
    const li = document.createElement('li');
    const name = document.createElement('div');
    name.className = 'name';
    const b = document.createElement('b');
    b.textContent = s.host_name || s.display;
    const small = document.createElement('small');
    const when = s.last_used ? new Date(s.last_used * 1000).toLocaleDateString(lang) : '';
    small.textContent = `${s.display} · ${s.has_token ? t().paired : t().notPaired}${when ? ` · ${t().lastUsed} ${when}` : ''}`;
    name.append(b, small);
    const open = document.createElement('button');
    open.className = 'btn small';
    open.textContent = t().openBtn;
    open.onclick = () => connect(s.origin, s.host_name || s.display);
    const forget = document.createElement('button');
    forget.className = 'link';
    forget.textContent = t().forgetBtn;
    forget.onclick = async () => {
      if (!window.confirm(t().forgetConfirm(s.display))) return;
      await invoke('forget', { origin: s.origin }).catch(() => {});
      state = await invoke('init_state');
      renderServers();
    };
    li.append(name, open, forget);
    ul.append(li);
  }
  const dl = $('suggestions');
  dl.textContent = '';
  for (const s of list) {
    const o = document.createElement('option');
    o.value = s.display;
    dl.append(o);
  }
}

async function connect(origin, label) {
  setFormError('');
  setStatus(t().opening(label), 'info');
  busy(true);
  try {
    await invoke('connect', { origin });
    // The shell navigates this window away on success.
  } catch (e) {
    busy(false);
    if (e && (e.code === 'need_pairing' || e.code === 'revoked')) {
      $('address').value = (state.servers.find((s) => s.origin === origin) || {}).display || origin;
      setStatus(errorText(e), 'error');
      $('code').focus();
    } else {
      setStatus(errorText(e), 'error', () => connect(origin, label));
    }
    state = await invoke('init_state');
    renderServers();
  }
}

async function fillFromLink(text) {
  const r = await invoke('parse_link', { text });
  if (!r) return false;
  const [link] = r;
  $('address').value = link.host;
  if (link.code) $('code').value = link.code;
  return true;
}

async function onSubmit(ev) {
  ev.preventDefault();
  setFormError('');
  const address = $('address').value.trim();
  const code = $('code').value.replace(/\s+/g, '');
  if (/madalean:\/\/pair/i.test(address)) { await fillFromLink(address); return onSubmit(ev); }
  if (!/^[0-9]{6}$/.test(code)) {
    // Maybe already paired: try to connect without a code.
    if (!code && address) {
      try { busy(true); await invoke('connect', { origin: address }); return; } catch (e) {
        busy(false);
        if (e && e.code !== 'need_pairing') { setFormError(errorText(e)); return; }
      }
    }
    setFormError(t().err.code_format); $('code').focus(); return;
  }
  busy(true);
  setStatus(t().pairing, 'info');
  try {
    await invoke('pair', { address, code, deviceName: $('device').value });
  } catch (e) {
    busy(false);
    setStatus('');
    setFormError(errorText(e));
    if (e && e.code === 'bad_code') { $('code').select(); }
  }
}

async function refreshUpdate() {
  const u = await invoke('update_status').catch(() => null);
  if (!u) return;
  $('auto-upd').checked = u.auto;
  const text = u.state === 'error'
    ? (t().updErr[u.error] || t().updErr.bad_manifest)
    : (t().upd[u.state] || t().upd.idle)(u);
  $('upd-status').textContent = text;
  $('upd-restart').hidden = !u.pending_restart;
  $('upd-check').disabled = u.state === 'checking' || u.state === 'downloading';
}

async function main() {
  state = await invoke('init_state');
  lang = state.lang === 'en' ? 'en' : 'fr';
  $('version').textContent = `Madalean ${state.version}`;
  $('device').value = state.device_name;
  applyLang();

  $('lang').onclick = async () => { lang = lang === 'fr' ? 'en' : 'fr'; applyLang(); refreshUpdate(); await invoke('set_lang', { lang }); };
  $('auto-upd').onchange = () => invoke('set_auto_update', { on: $('auto-upd').checked });
  $('upd-check').onclick = async () => { await invoke('check_updates_now'); refreshUpdate(); };
  $('upd-restart').onclick = () => invoke('restart_now');
  refreshUpdate();
  setInterval(refreshUpdate, 1000);
  $('retry').onclick = () => lastAction && lastAction();
  $('pair').addEventListener('submit', onSubmit);
  $('address').addEventListener('paste', (e) => {
    const text = (e.clipboardData || window.clipboardData).getData('text');
    if (/madalean:\/\/pair/i.test(text)) { e.preventDefault(); fillFromLink(text); }
  });
  $('code').addEventListener('input', () => { $('code').value = $('code').value.replace(/\D/g, '').slice(0, 6); });

  const reason = new URLSearchParams(location.hash.slice(1)).get('reason') || '';
  const reasonText = t().reason[reason];
  if (reasonText) setStatus(reasonText, 'error', state.servers.length ? () => connect(state.servers[0].origin, state.servers[0].display) : null);

  if (state.pending_link) {
    $('address').value = state.pending_link.host;
    if (state.pending_link.code) $('code').value = state.pending_link.code;
    setStatus(t().linkFilled, 'info');
    if (state.autosubmit) $('pair').requestSubmit();  // test hook (MADALEAN_SHELL_TEST_AUTOSUBMIT=1)
    else $('submit').focus();
    return;
  }
  if (reason) return;  // came back on purpose (change server) or after an error: let the user choose

  // Automatic start: the host itself first, then the last server used.
  setStatus(t().checkingLocal, 'info');
  const local = await invoke('probe_local').catch(() => null);
  if (local) { await connect(state.local_url, t().thisComputer); return; }
  setStatus('');
  const last = state.servers.find((s) => s.has_token);
  if (last) { await connect(last.origin, last.host_name || last.display); return; }
  $('address').focus();
}

main().catch((e) => setStatus(String(e), 'error'));
