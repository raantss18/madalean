// Madalean install wizard (served by packaging/installer/server.py on 127.0.0.1 only). No framework, no external
// request: the machine check and the plan come from the server (shared engine madalean/deps/assistant.py).
(function () {
  'use strict';
  var token = new URLSearchParams(location.search).get('t') || '';
  // keep the token out of the address bar and the history once read
  try { history.replaceState(null, '', location.pathname); } catch (e) { /* ignore */ }
  var root = document.documentElement;
  var lang = (navigator.language || 'fr').toLowerCase().indexOf('fr') === 0 ? 'fr' : 'en';
  try { lang = localStorage.getItem('madalean-installer-lang') || lang; } catch (e) { /* ignore */ }

  var S = {
    fr: {
      skip: 'Aller au contenu', installer: 'Installation', theme: 'Thème', steps: 'Étapes',
      s_welcome: 'Bienvenue', s_machine: 'Votre machine', s_plan: "Plan d'installation", s_install: 'Installation',
      s_config: 'Première configuration', s_done: 'Terminé',
      eyebrow: 'Assistant de démonstration pour Lean 4 et Mathlib',
      welcome_h: 'Installons Madalean sur cet ordinateur',
      welcome_p: "Cet ordinateur deviendra l'hôte : il fera tout le calcul. Vos autres appareils s'y relieront ensuite.",
      welcome_1: "Tout s'installe dans un seul dossier de votre compte, sans mot de passe administrateur.",
      welcome_2: "L'assistant regarde ce qui est déjà installé et vous conseille ; vous gardez le dernier mot.",
      welcome_3: 'Chaque fichier téléchargé est vérifié (empreinte SHA-256).',
      start: 'Commencer', back: 'Retour', next: 'Continuer', machine_h: 'Votre machine',
      machine_p: "Voici ce que l'assistant a trouvé.", detecting: 'Vérification en cours…',
      plan_h: 'Le plan conseillé', plan_p: 'Chaque élément est réglé pour cette machine. Changez ce que vous voulez.',
      reset: 'Revenir au plan conseillé', install_btn: 'Installer', install_h: 'Installation',
      progress: "Progression de l'installation", error_h: "L'installation s'est arrêtée",
      error_p: "Rien n'est perdu : l'installation reprend là où elle s'est arrêtée. Les dernières lignes ci-dessous indiquent la cause.",
      retry: 'Réessayer', details: 'Voir le détail', config_h: 'Première configuration',
      config_p: 'Madalean est installé et démarré. Il reste quelques réglages, faits dans Madalean lui-même :',
      cfg1_t: 'Une clé de modèle en ligne', cfg1: 'gratuite (par exemple Google Gemini ou Mistral) : Réglages › Modèles et clés.',
      cfg2_t: 'Le mode de travail', cfg2: 'en ligne, automatique ou local ; Apprendre ou Recherche.',
      cfg3_t: 'Ce qui part tout seul', cfg3: "exécution du code proposé par les modèles (après votre accord par défaut), mises à jour, chef d'orchestre.",
      cfg4_t: 'Vos appareils', cfg4: 'téléphone, tablette, autre ordinateur : Réglages › Appareils.',
      open_app: 'Ouvrir Madalean', guide: 'Guide de configuration', done_h: "C'est prêt",
      done_p: "Madalean démarre avec l'ordinateur. Adresse sur cet ordinateur :",
      done_p2: 'Vos choix sont enregistrés ; vous pourrez les changer dans les réglages de Madalean.',
      finish: "Fermer l'assistant", closed: 'Vous pouvez fermer cet onglet.',
      foot: 'Madalean — logiciel libre (Apache-2.0) · RANIRIAMANJAKA Antsa',
      cpu: 'Processeur', ram: 'Mémoire', disk: 'Disque libre', gpu: 'Carte graphique', none_gpu: 'Aucune carte NVIDIA',
      gb: 'Go', threads: 'fils', found: 'Présent', missing: 'Absent', compatible: 'Compatible', incompatible: 'Non compatible',
      recommended: 'conseillé', unavailable: 'non disponible ici', seen: 'Trouvé : ', copy: 'Copier', copied: 'Copié',
      run_yourself: 'À lancer vous-même dans un terminal (Madalean n’utilise jamais sudo) :',
      need: 'Place nécessaire ≈ {n} Go · libre : {f} Go', step: 'Étape {n} sur {t}', starting: 'Démarrage…',
      finished: 'Installation terminée.', failed: "L'installation a échoué (code {rc}).", other: 'English',
      lost: 'L’assistant ne répond plus. Relancez l’installateur.', python: 'Python', elan: 'Lean (elan)',
      ollama: 'Ollama', tailscale: 'Tailscale', bwrap: 'Bac à sable (bubblewrap)', tex: 'TeX Live', sage: 'SageMath',
      os: 'Système', busy: 'Une installation est déjà en cours.'
    },
    en: {
      skip: 'Skip to content', installer: 'Setup', theme: 'Theme', steps: 'Steps',
      s_welcome: 'Welcome', s_machine: 'Your machine', s_plan: 'Install plan', s_install: 'Installation',
      s_config: 'First configuration', s_done: 'Done',
      eyebrow: 'Proof assistant companion for Lean 4 and Mathlib',
      welcome_h: "Let's install Madalean on this computer",
      welcome_p: 'This computer becomes the host: it does all the computing. Your other devices link to it afterwards.',
      welcome_1: 'Everything goes into one folder of your account, no administrator password.',
      welcome_2: 'The assistant looks at what is already installed and advises you; you have the last word.',
      welcome_3: 'Every downloaded file is verified (SHA-256 fingerprint).',
      start: 'Start', back: 'Back', next: 'Continue', machine_h: 'Your machine',
      machine_p: 'Here is what the assistant found.', detecting: 'Checking…',
      plan_h: 'The recommended plan', plan_p: 'Every item is set for this machine. Change what you like.',
      reset: 'Back to the recommended plan', install_btn: 'Install', install_h: 'Installation',
      progress: 'Installation progress', error_h: 'The installation stopped',
      error_p: 'Nothing is lost: the installation resumes where it stopped. The last lines below show the cause.',
      retry: 'Try again', details: 'Show details', config_h: 'First configuration',
      config_p: 'Madalean is installed and running. A few settings remain, made in Madalean itself:',
      cfg1_t: 'An online model key', cfg1: 'free (for example Google Gemini or Mistral): Settings › Models and keys.',
      cfg2_t: 'The working mode', cfg2: 'online, automatic or local; Learn or Research.',
      cfg3_t: 'What runs on its own', cfg3: 'running the code models propose (after your approval by default), updates, conductor.',
      cfg4_t: 'Your devices', cfg4: 'phone, tablet, another computer: Settings › Devices.',
      open_app: 'Open Madalean', guide: 'Configuration guide', done_h: 'All set',
      done_p: 'Madalean starts with the computer. Address on this computer:',
      done_p2: 'Your choices are saved; you can change them in Madalean’s settings.',
      finish: 'Close the assistant', closed: 'You can close this tab.',
      foot: 'Madalean — free software (Apache-2.0) · RANIRIAMANJAKA Antsa',
      cpu: 'Processor', ram: 'Memory', disk: 'Free disk', gpu: 'Graphics card', none_gpu: 'No NVIDIA card',
      gb: 'GB', threads: 'threads', found: 'Present', missing: 'Missing', compatible: 'Compatible', incompatible: 'Not compatible',
      recommended: 'recommended', unavailable: 'not available here', seen: 'Found: ', copy: 'Copy', copied: 'Copied',
      run_yourself: 'Run it yourself in a terminal (Madalean never uses sudo):',
      need: 'Space needed ≈ {n} GB · free: {f} GB', step: 'Step {n} of {t}', starting: 'Starting…',
      finished: 'Installation finished.', failed: 'The installation failed (code {rc}).', other: 'Français',
      lost: 'The assistant no longer answers. Start the installer again.', python: 'Python', elan: 'Lean (elan)',
      ollama: 'Ollama', tailscale: 'Tailscale', bwrap: 'Sandbox (bubblewrap)', tex: 'TeX Live', sage: 'SageMath',
      os: 'System', busy: 'An installation is already running.'
    }
  };
  function t(k, p) {
    var s = (S[lang] && S[lang][k]) || S.fr[k] || k;
    if (p) Object.keys(p).forEach(function (n) { s = s.replace('{' + n + '}', p[n]); });
    return s;
  }
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function gb(b) { return Math.round((b || 0) / 1073741824); }

  // ------------------------------------------------------------ API
  function api(path, body) {
    var opt = { headers: { 'X-Install-Token': token }, credentials: 'same-origin', cache: 'no-store' };
    if (body !== undefined) {
      opt.method = 'POST';
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body);
    }
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (d) { d.__status = r.status; return d; });
    });
  }

  // ------------------------------------------------------------ language, theme
  function applyLang() {
    root.lang = lang;
    document.title = lang === 'fr' ? 'Installer Madalean' : 'Install Madalean';
    document.querySelectorAll('[data-i18n]').forEach(function (n) { n.textContent = t(n.getAttribute('data-i18n')); });
    document.querySelectorAll('[data-i18n-label]').forEach(function (n) { n.setAttribute('aria-label', t(n.getAttribute('data-i18n-label'))); });
    var b = $('lang');
    b.textContent = lang === 'fr' ? 'EN' : 'FR';
    b.setAttribute('aria-label', t('other'));
    b.setAttribute('lang', lang === 'fr' ? 'en' : 'fr');
    $('guide-link').href = state.site ? state.site + lang + '/first-config.html' : '#';
    if (state.detected) { renderMachine(); renderPlan(false); }
    if (cur === 'install') renderProgress(lastProgress);
  }
  $('lang').addEventListener('click', function () {
    lang = lang === 'fr' ? 'en' : 'fr';
    try { localStorage.setItem('madalean-installer-lang', lang); } catch (e) { /* ignore */ }
    applyLang();
  });
  try { var th = localStorage.getItem('madalean-installer-theme'); if (th) root.setAttribute('data-theme', th); } catch (e) { /* ignore */ }
  $('theme').addEventListener('click', function () {
    var c = root.getAttribute('data-theme');
    var n = c === 'light' ? 'dark' : c === 'dark' ? null : 'light';
    if (n) root.setAttribute('data-theme', n); else root.removeAttribute('data-theme');
    try { if (n) localStorage.setItem('madalean-installer-theme', n); else localStorage.removeItem('madalean-installer-theme'); } catch (e) { /* ignore */ }
  });

  // ------------------------------------------------------------ navigation
  var order = ['welcome', 'machine', 'plan', 'install', 'config', 'done'];
  var cur = 'welcome';
  function show(name) {
    cur = name;
    order.forEach(function (n) { $('p-' + n).hidden = n !== name; });
    var i = order.indexOf(name);
    document.querySelectorAll('#steps li').forEach(function (li) {
      var k = order.indexOf(li.getAttribute('data-for'));
      li.className = k === i ? 'current' : k < i ? 'past' : '';
      if (k === i) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
    var h = $('h-' + name);
    if (h) { h.setAttribute('tabindex', '-1'); h.focus(); }
  }
  document.querySelectorAll('[data-back]').forEach(function (b) {
    b.addEventListener('click', function () { show(b.getAttribute('data-back')); });
  });

  // ------------------------------------------------------------ state
  var state = {};
  var plan = null;
  function rec() { return state.recommendation ? state.recommendation[lang] : null; }
  function load() {
    return api('/api/state').then(function (d) {
      if (d.__status !== 200) throw new Error('state');
      state = d;
      $('guide-link').href = d.site + lang + '/first-config.html';
      $('app-url').textContent = d.madalean_url;
      $('app-url').href = d.madalean_url;
      if (d.state === 'detecting') { setTimeout(load, 700); return; }
      $('detecting').hidden = true;
      $('go-plan').disabled = false;
      if (!plan) plan = Object.assign({}, rec().plan);
      renderMachine();
      renderPlan(false);
      if (d.state === 'running' || d.state === 'failed' || d.state === 'done') { show('install'); poll(); }
    }).catch(function () { $('detecting').textContent = t('lost'); });
  }

  function cell(title, value, sub, pill) {
    var c = el('div', 'cell');
    c.appendChild(el('h3', null, title));
    c.appendChild(el('p', null, value));
    if (sub) c.appendChild(el('small', null, sub));
    if (pill) c.appendChild(el('span', 'pill ' + pill[0], pill[1]));
    return c;
  }
  function renderMachine() {
    var g = $('machine-grid');
    while (g.firstChild) g.removeChild(g.firstChild);
    var d = state.detected || {};
    var hw = d.hardware || {}, tl = d.tools || {};
    var gpus = hw.gpus || [];
    var gpu = gpus.reduce(function (a, b) { return !a || b.vram_mib > a.vram_mib ? b : a; }, null);
    g.appendChild(cell(t('os'), (d.os || {}).name || '?', (d.os || {}).arch || '', (d.os || {}).supported === false ? ['warn', t('incompatible')] : null));
    g.appendChild(cell(t('cpu'), ((hw.cpu || {}).model || '?'), ((hw.cpu || {}).threads || '?') + ' ' + t('threads')));
    g.appendChild(cell(t('ram'), gb(hw.ram_bytes) + ' ' + t('gb')));
    g.appendChild(cell(t('disk'), gb((hw.disk || {}).free_bytes) + ' ' + t('gb'), (hw.disk || {}).path || ''));
    g.appendChild(cell(t('gpu'), gpu ? gpu.name : t('none_gpu'), gpu ? Math.round(gpu.vram_mib / 1024) + ' ' + t('gb') + (hw.cuda ? ' · CUDA ' + hw.cuda : '') : ''));
    function tool(key, label, sub, compat) {
      var x = tl[key] || {};
      var pill = !x.found ? ['no', t('missing')] : compat === undefined ? ['ok', t('found')] : compat ? ['ok', t('compatible')] : ['warn', t('incompatible')];
      g.appendChild(cell(label, x.found ? (sub || t('found')) : t('missing'), x.found ? (x.path || x.xelatex || '') : '', pill));
    }
    tool('sage', t('sage'), tl.sage && tl.sage.version ? 'SageMath ' + tl.sage.version : '', tl.sage ? !!tl.sage.compatible : undefined);
    tool('tex', t('tex'), tl.tex && tl.tex.year ? 'TeX Live ' + tl.tex.year : '', tl.tex ? !!tl.tex.compatible : undefined);
    var py = (tl.python || []).map(function (p) { return p.version; }).filter(Boolean).join(', ');
    g.appendChild(cell(t('python'), py || t('missing'), '', py ? ['ok', t('found')] : ['no', t('missing')]));
    tool('elan', t('elan'), tl.elan && tl.elan.toolchains && tl.elan.toolchains.length ? tl.elan.toolchains.slice(-2).join(', ') : '');
    tool('ollama', t('ollama'), tl.ollama && tl.ollama.version ? 'Ollama ' + tl.ollama.version : '');
    tool('tailscale', t('tailscale'), tl.tailscale && tl.tailscale.version ? 'Tailscale ' + tl.tailscale.version : '');
    tool('bwrap', t('bwrap'));
  }

  function renderPlan(reset) {
    var r = rec();
    if (!r) return;
    if (reset || !plan) plan = Object.assign({}, r.plan);
    var adv = $('advice');
    while (adv.firstChild) adv.removeChild(adv.firstChild);
    (r.advice || []).forEach(function (a) {
      var box = el('div', 'advice');
      box.appendChild(el('p', null, a.text));
      if (a.command) {
        var row = el('div', 'copy-row');
        row.appendChild(el('code', null, a.command));
        var b = el('button', 'btn', t('copy'));
        b.type = 'button';
        b.addEventListener('click', function () {
          (navigator.clipboard ? navigator.clipboard.writeText(a.command) : Promise.reject()).then(function () { b.textContent = t('copied'); }, function () {});
        });
        row.appendChild(b);
        box.appendChild(row);
      }
      adv.appendChild(box);
    });
    var f = $('plan-form');
    while (f.firstChild) f.removeChild(f.firstChild);
    r.items.forEach(function (it) {
      var fs = el('fieldset', 'item');
      fs.appendChild(el('legend', null, it.title));
      fs.appendChild(el('p', 'why', it.why));
      if (it.detected) fs.appendChild(el('p', 'seen', t('seen') + it.detected));
      it.options.forEach(function (o) {
        var lab = el('label', 'opt' + (o.available ? '' : ' disabled'));
        var inp = document.createElement('input');
        inp.type = 'radio'; inp.name = it.id; inp.value = o.value;
        inp.checked = plan[it.id] === o.value; inp.disabled = !o.available;
        inp.addEventListener('change', function () { plan[it.id] = o.value; updateDisk(); });
        lab.appendChild(inp);
        var span = el('span', null, o.label);
        if (o.value === it.recommended) span.appendChild(el('span', 'rec', t('recommended')));
        if (!o.available) span.appendChild(el('span', 'muted', ' (' + t('unavailable') + ')'));
        lab.appendChild(span);
        fs.appendChild(lab);
      });
      f.appendChild(fs);
    });
    updateDisk();
  }
  function updateDisk() {
    // same estimate as the engine (assistant.disk_needed): base + models + Sage now + workspace build
    var d = state.detected || {}, have = ((d.madalean || {}).models) || {};
    var sets = { all: ['Q4_K_M', 'formalizer', 'explainer'], prover: ['Q4_K_M'], none: [] };
    var n = 6e9;
    (sets[plan.models] || []).forEach(function (m) { if (!have[m]) n += 5e9; });
    if (plan.sage === 'now' && !(d.madalean || {}).sage_own) n += 6.5e9;
    if (plan.workspace === 'build') n += 5e9;
    $('disk').textContent = t('need', { n: gb(n), f: gb(((d.hardware || {}).disk || {}).free_bytes) });
  }
  $('reset-plan').addEventListener('click', function () { renderPlan(true); });

  // ------------------------------------------------------------ install + progress
  var since = 0, lastProgress = null, timer = null;
  function renderProgress(p) {
    if (!p) return;
    var fill = $('bar-fill');
    fill.style.width = p.percent + '%';
    $('bar').setAttribute('aria-valuenow', String(p.percent));
    $('install-title').textContent = p.state === 'done' ? t('finished') : p.state === 'failed' ? t('failed', { rc: p.rc }) : (p.title || t('starting'));
    $('install-step').textContent = p.step ? t('step', { n: p.step, t: p.total }) : '';
    $('install-error').hidden = p.state !== 'failed';
    $('go-config').hidden = p.state !== 'done';
  }
  function poll() {
    clearTimeout(timer);
    api('/api/progress?since=' + since).then(function (p) {
      lastProgress = p;
      var log = $('log');
      if (p.lines && p.lines.length) {
        log.appendChild(document.createTextNode(p.lines.join('\n') + '\n'));
        log.scrollTop = log.scrollHeight;
      }
      since = p.next;
      renderProgress(p);
      if (p.state === 'failed') {
        var all = log.textContent.trimEnd().split('\n');
        $('error-tail').textContent = all.slice(-15).join('\n');
      }
      if (p.state === 'running') timer = setTimeout(poll, 800);
      if (p.state === 'done') $('go-config').focus();
    }).catch(function () { $('install-title').textContent = t('lost'); });
  }
  function startInstall() {
    $('log').textContent = '';
    since = 0;
    show('install');
    renderProgress({ state: 'running', percent: 0, step: 0, total: 9, title: t('starting') });
    api('/api/install', { plan: plan }).then(function (d) {
      if (d.__status === 409 && d.error === 'busy') { poll(); return; }
      if (d.__status >= 400) { $('install-title').textContent = d.detail || d.error; return; }
      poll();
    });
  }
  $('go-machine').addEventListener('click', function () { show('machine'); });
  $('go-plan').addEventListener('click', function () { show('plan'); });
  $('go-install').addEventListener('click', startInstall);
  $('retry').addEventListener('click', startInstall);
  $('go-config').addEventListener('click', function () { show('config'); });
  $('open-app').addEventListener('click', function () { api('/api/open', {}); });
  $('go-done').addEventListener('click', function () { show('done'); });
  $('finish').addEventListener('click', function () {
    api('/api/quit', {}).finally(function () { $('finish').disabled = true; $('closed').hidden = false; });
  });

  applyLang();
  show('welcome');
  load();
})();
