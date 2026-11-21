<script lang="ts">
  // Article (S-R, docs/ARTICLE.md): the article's LaTeX project, written in a visual editor that IS the LaTeX source
  // (rendered maths, theorem boxes, citations, figures; one click shows the raw source of the same text). Outline on
  // the left, PDF preview on the right on wide screens; advanced options in a drawer. AI help arrives only as
  // suggestions you accept or reject.
  import { onDestroy, untrack } from 'svelte';
  import { articleApi, type TexProject, type CompileResult, type Diagnostic, type AssistAction, type Suggestion as TexSug } from '../../lib/api/article';
  import { consigne, type Suggestion as QSug } from '../../lib/api/consigne';
  import { ApiError } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, i18n, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { aprefs, setAPref, WIDTHS } from '../../lib/article/prefs.svelte';
  import { headings, numberDocument, katexMacros, scan, parseMarker } from '../../lib/article/latex';
  import type { ArticleEditor, EditorCtx, SugView } from '../../lib/article/editor';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Menu from '../../components/Menu.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import PdfView from '../../components/PdfView.svelte';
  import SuggestionsReview from '../../components/SuggestionsReview.svelte';
  import ArticleOptions from './article/ArticleOptions.svelte';
  import ArticleDialogs from './article/ArticleDialogs.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());

  let proj = $state<TexProject | null>(null);
  let err = $state('');
  const texts: Record<string, string> = {};             // current text per file (not reactive: the editor owns it)
  let hashes = $state<Record<string, string>>({});
  let dirty = $state<Record<string, boolean>>({});
  let current = $state('');
  let saveState = $state<'saved' | 'saving' | 'dirty' | 'conflict' | 'error'>('saved');
  let conflict = $state<{ path: string; text: string; hash: string } | null>(null);
  let host: HTMLDivElement | undefined = $state();
  let ed: ArticleEditor | null = null;
  let ready = $state(false);
  let visual = $state(aprefs.mode !== 'source');
  let modeSel = $state<'visual' | 'source'>(aprefs.mode === 'source' ? 'source' : 'visual');
  let narrow = $state(false);
  let preview = $state(aprefs.preview !== 'off');
  let showSugs = $state(false);
  let compiling = $state(false);
  let result = $state<CompileResult | null>(null);
  let pdfNonce = $state(0);
  let target = $state<{ page: number; bbox: number[]; nonce: number } | null>(null);
  let selection = $state<{ from: number; to: number; text: string } | null>(null);
  let bubble = $state<{ x: number; y: number } | null>(null);
  let pending = $state<Record<string, string>>({});          // request id → action
  let texSugs = $state<TexSug[]>([]);
  let qSugs = $state<QSug[]>([]);
  let optionsOpen = $state(false);
  let optionsTab = $state('document');
  let dialog = $state<'' | 'title' | 'figure' | 'versions' | 'overleaf' | 'table' | 'newSection'>('');
  let headsTick = $state(0);
  let saveTimer: ReturnType<typeof setTimeout> | null = null;
  let compileTimer: ReturnType<typeof setTimeout> | null = null;
  let refreshTimer: ReturnType<typeof setTimeout> | null = null;

  // ---------------------------------------------------------------- loading
  async function load() {
    if (!pid) return;
    try {
      const r = await articleApi.project(pid);
      proj = r;
      for (const f of r.files) { texts[f.path] = f.text; hashes[f.path] = f.hash; }
      dirty = {};
      if (!current || !texts[current]) current = r.order[0] ?? 'main.tex';
      texSugs = r.suggestions;
      err = '';
      void loadQ();
      if (ed) { ed.open(current, texts[current] ?? ''); pushSugs(); ed.refresh(); }
      if (r.last?.ok && r.last.pdf && !result) result = { ok: true, pdf: articleApi.pdfUrl(pid, r.last.pdf), hash: r.last.hash, seconds: r.last.seconds, engine: r.last.engine, cached: true, diagnostics: [], packages: null as never, states: r.states };
      headsTick++;
      if (preview && !narrow && !result?.ok) void compile();
    } catch (e) { err = errorText(e); }
  }
  async function loadQ() {
    try { qSugs = (await consigne.suggestions(pid, '', 'proposed')).suggestions; } catch { qSugs = []; }
    pushSugs();
  }
  $effect(() => { void pid; untrack(() => { current = ''; result = null; void load(); }); });

  // ---------------------------------------------------------------- editor
  const thmTitles = $derived.by(() => {
    const out: Record<string, { title: string; style: string }> = {};
    const lang = proj?.settings.document.language ?? 'fr';
    for (const e of proj?.settings.theorems.envs ?? []) out[e.env] = { title: lang === 'fr' ? e.fr : e.en, style: e.style };
    out['proof'] = { title: lang === 'fr' ? 'Démonstration' : 'Proof', style: 'proof' };
    for (const [env, fr, en] of [['claim', 'Affirmation', 'Claim'], ['conjecture', 'Conjecture', 'Conjecture']] as const) out[env] ??= { title: lang === 'fr' ? fr : en, style: 'plain' };
    return out;
  });
  function ctx(): EditorCtx {
    const p = proj;
    const order = p ? ['main.tex', ...p.order] : [];
    const files = order.map((path) => ({ path, text: texts[path] ?? '' }));
    const envCounters: Record<string, string> = {};
    for (const e of p?.settings.theorems.envs ?? []) envCounters[e.env] = e.counter || '';
    const numbers = numberDocument(files, { section: 'section', envs: envCounters, within: p?.settings.theorems.numbering ?? 'section' });
    const labels = new Map<string, { env: string; title: string; num: string; path: string }>();
    for (const f of files) {
      const sc = scan(f.text);
      const owners = [...sc.envs.map((e) => ({ from: e.from, to: e.to, env: e.name, title: e.opt })),
        ...sc.math.map((m) => ({ from: m.from, to: m.to, env: '#eq', title: '' }))];
      let lastSec: { from: number; title: string } | null = null;
      const secs = sc.cmds.filter((c) => c.name === 'section' || c.name === 'subsection');
      for (const c of sc.cmds) {
        if (c.name !== 'label') continue;
        const own = owners.filter((o) => o.from < c.from && o.to > c.from && (o.env in thmTitles || o.env === '#eq' || o.env.startsWith('figure') || o.env === 'table')).pop();
        lastSec = secs.filter((s) => s.from < c.from).map((s) => ({ from: s.from, title: s.arg })).pop() ?? null;
        if (own) labels.set(c.arg, { env: own.env.startsWith('figure') ? 'figure' : own.env, title: own.title, num: numbers.get(`${f.path}:${own.from}`)?.num ?? '', path: f.path });
        else if (lastSec) labels.set(c.arg, { env: 'section', title: lastSec.title, num: numbers.get(`${f.path}:${lastSec.from}`)?.num ?? '', path: f.path });
      }
    }
    const keys = new Map((p?.keys ?? []).map((k) => [k.key, { title: k.title, author: k.author, year: k.year }]));
    const states: Record<string, { status: string; title: string }> = { ...(p?.states ?? {}) };
    for (const d of p?.dossiers ?? []) states[d.id] = { status: d.status, title: d.title };
    return {
      lang: i18n.lang, path: current, thm: thmTitles, numbers, labels, keys, states,
      macros: katexMacros(p?.settings.macros ?? {}, texts['main.tex'] ?? ''),
      figureUrl: (path: string) => articleApi.figureUrl(pid, path),
      title: p?.settings.front.title ?? '', authors: (p?.settings.front.authors ?? []).map((a) => a.name).join(', '),
      t: (k, params) => tk(k, k.startsWith('ae.sug.kind.') ? '' : k, params),
    };
  }
  $effect(() => {
    if (!host || ed || !proj) return;
    let cancelled = false;
    void import('../../lib/article/editor').then(({ createArticleEditor }) => {
      if (cancelled || !host || ed) return;
      ed = createArticleEditor({
        parent: host, doc: texts[current] ?? '', path: current, visual: visual && !narrow ? true : visual || narrow, lineNumbers: aprefs.lineNumbers,
        ariaLabel: t('ae.editorLabel'), placeholder: t('ae.placeholder'), ctx,
        onChange: (path, doc) => { texts[path] = doc; dirty[path] = true; saveState = 'dirty'; schedule(); scheduleRefresh(); },
        onSelection: (s) => { selection = s; placeBubble(); },
        onSuggestion: (id, ok) => void decide(id, ok),
        onDossier: (id) => navigate(`/d/${encodeURIComponent(id)}`),
        onAction: (a) => {
          if (a === 'options') openOptions('document');
          else if (a === 'title') dialog = 'title';
          else if (a === 'save') void saveNow();
          else if (a === 'compile') void compile();
          else if (a === 'forward') void forward();
        },
      });
      if (aprefs.keymap !== 'default') void ed.setKeymap(aprefs.keymap);
      pushSugs();
      ready = true;
    });
    return () => { cancelled = true; };
  });
  onDestroy(() => { if (saveTimer) { clearTimeout(saveTimer); void saveAll(); } ed?.destroy(); ed = null; });

  function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => { headsTick++; ed?.refresh(); }, 600);
  }
  function openFile(path: string, line = 0) {
    if (!(path in texts)) return;
    current = path;
    ed?.open(path, texts[path] ?? '');
    pushSugs();
    showDiagsInEditor();
    if (line) ed?.goto(line); else ed?.focus();
    headsTick++;
  }
  function setVisual(v: boolean) {
    visual = v;
    modeSel = v ? 'visual' : 'source';
    setAPref('mode', v ? 'visual' : 'source');
    ed?.setVisual(v);
  }

  // phone: visual mode only, one column
  $effect(() => {
    const mq = matchMedia('(max-width: 760px)');
    const f = () => { narrow = mq.matches; if (narrow && ed && !visual) { visual = true; ed.setVisual(true); } };
    f(); mq.addEventListener('change', f);
    return () => mq.removeEventListener('change', f);
  });

  // ---------------------------------------------------------------- saving
  function schedule() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => { saveTimer = null; void saveAll(); }, aprefs.autosave);
  }
  async function saveNow() { if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; } await saveAll(); if (preview) void compile(); }
  async function saveAll() {
    const paths = Object.keys(dirty).filter((p) => dirty[p]);
    if (!paths.length || conflict) return;
    saveState = 'saving';
    for (const path of paths) {
      const text = texts[path] ?? '';
      try {
        const r = await articleApi.save(pid, path, text, hashes[path] ?? '');
        hashes[path] = r.hash;
        if (texts[path] === text) dirty[path] = false;
        if (r.text != null && r.text !== text) { texts[path] = r.text; ed?.replaceDoc(path, r.text); }
      } catch (e) {
        if (e instanceof ApiError && e.kind === 'conflict') {
          conflict = (e.body['current'] as { path: string; text: string; hash: string });
          saveState = 'conflict';
          return;
        }
        saveState = 'error';
        toast('error', errorText(e));
        return;
      }
    }
    saveState = Object.values(dirty).some(Boolean) ? 'dirty' : 'saved';
    if (preview && aprefs.autoCompile) scheduleCompile();
  }
  function resolveConflict(keepMine: boolean) {
    if (!conflict) return;
    const c = conflict;
    conflict = null;
    hashes[c.path] = c.hash;
    if (keepMine) { dirty[c.path] = true; void saveAll(); }
    else { texts[c.path] = c.text; dirty[c.path] = false; ed?.replaceDoc(c.path, c.text); saveState = 'saved'; }
  }

  // ---------------------------------------------------------------- compile, preview, SyncTeX
  function scheduleCompile() {
    if (compileTimer) clearTimeout(compileTimer);
    compileTimer = setTimeout(() => void compile(), 2500);
  }
  async function compile(opts: { fetch?: boolean; force?: boolean } = {}) {
    if (compiling) { scheduleCompile(); return; }
    if (Object.values(dirty).some(Boolean)) await saveAll();
    compiling = true;
    try {
      const r = await articleApi.compile(pid, opts);
      result = r;
      if (r.ok) { pdfNonce++; if (!preview && !narrow && opts.fetch === undefined && !opts.force) toast('ok', t('ae.compiled', { s: r.seconds.toFixed(1) })); }
      showDiagsInEditor();
      if (proj && r.states) proj.states = r.states;
      ed?.refresh();
    } catch (e) { toast('error', errorText(e)); }
    finally { compiling = false; }
  }
  const pdfUrl = $derived(result?.pdf ? `${result.pdf}&n=${pdfNonce}` : '');
  const problems = $derived((result?.diagnostics ?? []).filter((d) => d.severity !== 'info' || d.fix));
  const errors = $derived(problems.filter((d) => d.severity === 'error').length);
  function showDiagsInEditor() {
    ed?.setDiagnostics((result?.diagnostics ?? []).filter((d) => d.path === current && d.line > 0 && d.severity !== 'info')
      .map((d) => ({ line: d.line, severity: d.severity, text: d.plain.text })));
  }
  async function forward() {
    if (!ed) return;
    if (!preview) { preview = true; setAPref('preview', aprefs.preview === 'off' ? 'right' : aprefs.preview); }
    try {
      const r = (await articleApi.forward(pid, current, ed.selection().line)).result;
      if (r) target = { page: r.page, bbox: [r.x - 4, r.y - 4, r.x + r.w + 4, r.y + r.h + 4], nonce: Date.now() };
      else toast('info', t('ae.sync.none'));
    } catch (e) { toast('error', errorText(e)); }
  }
  async function inverse(page: number, x: number, y: number) {
    try {
      const r = (await articleApi.inverse(pid, page, x, y)).result;
      if (r && r.path in texts) openFile(r.path, r.line);
    } catch { /* no SyncTeX data yet */ }
  }
  async function fix(d: Diagnostic) {
    const f = d.fix;
    if (!f || !proj) return;
    try {
      if (f.kind === 'add_package' && f.name) {
        await patchSettings({ packages: { ...proj.settings.packages, extra: [...new Set([...proj.settings.packages.extra, f.name])], removed: proj.settings.packages.removed.filter((x) => x !== f.name) } });
      } else if (f.kind === 'remove_package' && f.name) {
        const inSettings = proj.settings.packages.base.includes(f.name) || proj.settings.packages.extra.includes(f.name);
        if (inSettings) await patchSettings({ packages: { ...proj.settings.packages, extra: proj.settings.packages.extra.filter((x) => x !== f.name), removed: [...new Set([...proj.settings.packages.removed, f.name])] } });
        else openFile(d.path, d.line);
      } else if (f.kind === 'fetch') {
        toast('info', t('ae.fetching'));
        await compile({ fetch: true });
        return;
      } else if (f.kind === 'replace' && f.find && f.replace) {
        openFile(d.path, d.line);
        const text = texts[d.path] ?? '';
        const lines = text.split('\n');
        const ln = lines[d.line - 1] ?? '';
        if (ln.includes(f.find)) {
          const start = lines.slice(0, d.line - 1).join('\n').length + (d.line > 1 ? 1 : 0) + ln.indexOf(f.find);
          ed?.applySuggestion({ id: 'fix', from: start, to: start + f.find.length, at: 'replace', replace: f.replace, kind: 'fix', origin: 'user', model: '' });
        }
        return;
      } else if (f.kind === 'add_macro') { openOptions('macros', f.name); return; }
      else if (f.kind === 'add_theorem' && f.env) {
        const name = f.env.charAt(0).toUpperCase() + f.env.slice(1);
        await patchSettings({ theorems: { ...proj.settings.theorems, envs: [...proj.settings.theorems.envs, { env: f.env, fr: name, en: name, style: 'plain', counter: 'theorem' }] } });
      } else if (f.kind === 'open_sources') { navigate('/sources'); return; }
      else if (f.kind === 'repair') { navigate('/settings/system'); return; }
      void compile();
    } catch (e) { toast('error', errorText(e)); }
  }
  async function patchSettings(patch: Parameters<typeof articleApi.settings>[1]) {
    if (!proj) return;
    await saveAll();
    const r = await articleApi.settings(pid, patch);
    proj.settings = r.settings;
    for (const f of r.files) { texts[f.path] = f.text; hashes[f.path] = f.hash; dirty[f.path] = false; ed?.replaceDoc(f.path, f.text); }
    ed?.refresh();
  }

  // ---------------------------------------------------------------- suggestions (track changes)
  function qAnchor(s: QSug): { path: string; from: number; to: number } | null {
    if (s.target?.mode !== 'replace_excerpt' && s.target?.mode !== 'insert_after') return null;
    const needle = s.target.mode === 'insert_after' ? (s.target.near || s.before) : s.before;
    if (!needle) return null;
    for (const path of [current, ...Object.keys(texts)]) {
      const text = texts[path] ?? '';
      let lo = 0, hi = text.length;
      if (s.target.block_id) {
        const sc = scan(text);
        const i = sc.markers.findIndex((m) => parseMarker(m.text)?.id === s.target.block_id);
        if (i < 0) continue;
        lo = sc.markers[i]!.to; hi = sc.markers[i + 1]?.from ?? text.length;
      }
      const at = text.indexOf(needle, lo);
      if (at >= 0 && at + needle.length <= hi) return { path, from: at, to: at + needle.length };
    }
    return null;
  }
  function pushSugs() {
    if (!ed) return;
    const views: SugView[] = [];
    for (const s of texSugs) if (s.state === 'pending' && s.anchor && s.anchor.path === current) views.push({ id: s.id, from: s.anchor.from, to: s.anchor.to, at: s.at, replace: s.replace, kind: s.kind, origin: s.origin, model: s.model });
    for (const s of qSugs) {
      const a = qAnchor(s);
      if (a && a.path === current) views.push({ id: `q:${s.id}`, from: a.from, to: a.to, at: s.target.mode === 'insert_after' ? 'after' : 'replace', replace: s.target.mode === 'insert_after' ? '\n' + s.after : s.after, kind: s.type, origin: 'research', model: s.model });
    }
    ed.setSuggestions(views);
  }
  async function reloadSugs() {
    try { texSugs = (await articleApi.suggestions(pid)).suggestions; } catch { /* */ }
    pushSugs();
  }
  async function decide(id: string, ok: boolean) {
    try {
      if (id.startsWith('q:')) {
        await saveAll();
        const sid = id.slice(2);
        if (ok) await consigne.accept(pid, sid); else await consigne.reject(pid, sid);
        await refetchFiles();
        await loadQ();
      } else {
        const s = texSugs.find((x) => x.id === id);
        if (!s) return;
        if (ok && s.anchor && s.anchor.path === current && ed) {
          ed.applySuggestion({ id, from: s.anchor.from, to: s.anchor.to, at: s.at, replace: s.replace, kind: s.kind, origin: s.origin, model: s.model });
          await articleApi.accept(pid, id, true);
        } else if (ok) {
          await saveAll();
          const r = await articleApi.accept(pid, id, false);
          for (const f of r.files) { texts[f.path] = f.text; hashes[f.path] = f.hash; ed?.replaceDoc(f.path, f.text); }
        } else await articleApi.reject(pid, id);
        texSugs = texSugs.filter((x) => x.id !== id);
        await reloadSugs();
      }
      toast('ok', ok ? t('ae.sug.accepted') : t('ae.sug.rejected'));
    } catch (e) { toast('error', errorText(e)); await reloadSugs(); }
  }
  async function refetchFiles() {
    const r = await articleApi.project(pid);
    proj = r;
    for (const f of r.files) {
      hashes[f.path] = f.hash;
      if (!dirty[f.path] && texts[f.path] !== f.text) { texts[f.path] = f.text; ed?.replaceDoc(f.path, f.text); }
      else texts[f.path] ??= f.text;
    }
    texSugs = r.suggestions;
    headsTick++;
  }

  // ---------------------------------------------------------------- assistant (selection → suggestion)
  function placeBubble() {
    if (!selection || !ed || !host) { bubble = null; return; }
    const c = ed.view.coordsAtPos(selection.from);
    const box = host.getBoundingClientRect();
    bubble = c ? { x: Math.max(8, Math.min(c.left - box.left, box.width - 330)), y: c.top - box.top + host.scrollTop - 48 } : null;
  }
  async function assist(action: AssistAction) {
    if (!selection || !ed) return;
    await saveAll();
    try {
      const r = await articleApi.assist(pid, { action, path: current, from: selection.from, text: selection.text });
      pending[r.request_id] = action;
      toast('info', t(action === 'sage' ? 'ae.assist.sageRunning' : 'ae.assist.running', { mode: tk(`ae.mode.${r.mode}`, r.mode) }));
    } catch (e) { toast('error', errorText(e)); }
  }
  async function lean() {
    if (!selection) return;
    await saveAll();
    try {
      const r = await articleApi.lean(pid, { path: current, text: selection.text });
      toast('ok', t(r.linked ? 'ae.lean.created' : 'ae.lean.createdNoLink', { title: r.dossier.title }), { action: { label: t('ae.lean.openDossier'), run: () => navigate(`/d/${encodeURIComponent(r.dossier.id)}`) } });
      await refetchFiles();
    } catch (e) { toast('error', errorText(e)); }
  }
  $effect(() => app.on('article.assist.done', (ev) => {
    const e = ev as unknown as { project: string; request_id: string; action: string; cell?: { id: string } };
    if (e.project !== pid || !(e.request_id in pending)) return;
    delete pending[e.request_id];
    if (e.cell) toast('ok', t('ae.assist.sageDone'), { action: { label: t('ae.assist.openCalcul'), run: () => navigate('/calcul') } });
    else { toast('ok', t('ae.assist.done')); void reloadSugs(); }
  }));
  $effect(() => app.on('article.assist.error', (ev) => {
    const e = ev as unknown as { project: string; request_id: string; error: string; text?: string };
    if (e.project !== pid || !(e.request_id in pending)) return;
    delete pending[e.request_id];
    toast('error', e.text || tk(`err.${e.error}`, t('ae.assist.failed')));
  }));
  $effect(() => app.on('article.suggestion', (ev) => { const e = ev as unknown as { project: string }; if (e.project === pid) void reloadSugs(); }));
  $effect(() => app.on('research.suggestion', (ev) => { const e = ev as unknown as { project_id: string }; if (e.project_id === pid) void loadQ(); }));
  $effect(() => app.on('texproject.file', (ev) => {
    const e = ev as unknown as { project: string; path: string; hash: string };
    if (e.project !== pid || hashes[e.path] === e.hash) return;
    if (dirty[e.path]) { void articleApi.project(pid).then((r) => { const f = r.files.find((x) => x.path === e.path); if (f && f.hash !== hashes[e.path]) { conflict = f; saveState = 'conflict'; } }); }
    else void refetchFiles();
  }));

  // ---------------------------------------------------------------- insertions
  function insertEnv(env: string) {
    if (!ed) return;
    const label = env === 'proof' ? '' : `\\label{${({ theorem: 'thm', lemma: 'lem', definition: 'def' } as Record<string, string>)[env] ?? env.slice(0, 3)}:}`;
    const snippet = `\\begin{${env}}${label}\n\n\\end{${env}}\n`;
    ed.insert(snippet, `\\begin{${env}}${label}\n`.length);
  }
  const insertItems = $derived([
    { label: t('ae.ins.theorem'), icon: 'check', run: () => insertEnv('theorem') },
    { label: t('ae.ins.lemma'), run: () => insertEnv('lemma') },
    { label: t('ae.ins.definition'), run: () => insertEnv('definition') },
    { label: t('ae.ins.proof'), run: () => insertEnv('proof') },
    { label: t('ae.ins.math'), hint: 'Ctrl+M', run: () => ed?.wrap('$', '$', 'x') },
    { label: t('ae.ins.display'), hint: 'Ctrl+Maj+M', run: () => ed?.insert('\\begin{equation}\\label{eq:}\n\n\\end{equation}\n', '\\begin{equation}\\label{eq:}\n'.length) },
    { label: t('ae.ins.align'), run: () => ed?.insert('\\begin{align}\n  a &= b \\\\\n  &= c\n\\end{align}\n', 16) },
    { label: t('ae.ins.figure'), icon: 'eye', run: () => (dialog = 'figure') },
    { label: t('ae.ins.table'), run: () => ed?.insert('\\begin{table}[ht]\n\\centering\n\\begin{tabular}{cc}\n\\hline\n$x$ & $y$ \\\\\n\\hline\n\\end{tabular}\n\\caption{}\n\\end{table}\n', 72) },
    { label: t('ae.ins.list'), run: () => ed?.insert('\\begin{itemize}\n  \\item \n\\end{itemize}\n', 24) },
    { label: t('ae.ins.footnote'), run: () => ed?.wrap('\\footnote{', '}', '') },
    { label: t('ae.ins.cite'), run: () => ed?.wrap('\\cite{', '}', '') },
    { label: t('ae.ins.ref'), run: () => ed?.wrap('\\cref{', '}', '') },
    { label: t('ae.ins.comment'), run: () => ed?.insert(`% ${t('ae.ins.commentText')} `) },
    { label: t('ae.ins.section'), icon: 'plus', run: () => (dialog = 'newSection') },
  ]);
  const moreItems = $derived([
    { label: t('ae.more.options'), icon: 'settings', run: () => openOptions('document') },
    { label: t('ae.more.versions'), icon: 'history', run: () => (dialog = 'versions') },
    { label: t('ae.more.overleaf'), icon: 'external', run: () => (dialog = 'overleaf') },
    { label: t('ae.more.pdf'), icon: 'download', run: () => { const a = document.createElement('a'); a.href = articleApi.exportUrl(pid, 'pdf'); a.download = ''; document.body.appendChild(a); a.click(); a.remove(); } },
    { label: t('ae.more.undo'), icon: 'undo', hint: 'Ctrl+Z', run: () => ed?.undo() },
    { label: t('ae.more.redo'), hint: 'Ctrl+Maj+Z', run: () => ed?.redo() },
  ]);
  function openOptions(tab: string, macro?: string) { optionsTab = tab; optionsOpen = true; pendingMacro = macro ?? ''; }
  let pendingMacro = $state('');

  // ---------------------------------------------------------------- outline
  const outline = $derived.by(() => {
    void headsTick;
    if (!proj) return [];
    return proj.order.map((path) => {
      const hs = headings(texts[path] ?? '');
      const top = hs.find((h) => h.level <= 1);
      return { path, title: top?.title || path.replace(/^sections\/\d*-?/, '').replace(/\.tex$/, ''), subs: hs.filter((h) => h !== top && h.level <= 2) };
    });
  });
  async function addSection(title: string) {
    try {
      await saveAll();
      const r = await articleApi.addSection(pid, title, current.startsWith('sections/') ? current : '');
      texts[r.path] = r.text; hashes[r.path] = r.hash;
      if (proj) proj.order = r.order;
      await refetchFiles();
      openFile(r.path, 2);
    } catch (e) { toast('error', errorText(e)); }
  }
  async function moveSection(path: string, d: -1 | 1) {
    if (!proj) return;
    const o = [...proj.order]; const i = o.indexOf(path); const j = i + d;
    if (j < 0 || j >= o.length) return;
    [o[i], o[j]] = [o[j]!, o[i]!];
    try { await saveAll(); await articleApi.order(pid, o); proj.order = o; await refetchFiles(); } catch (e) { toast('error', errorText(e)); }
  }
  async function deleteSection(path: string) {
    try {
      await saveAll();
      await articleApi.deleteSection(pid, path);
      delete texts[path];
      if (current === path) current = '';
      await load();
      toast('ok', t('ae.section.deleted'), { action: { label: t('ae.more.versions'), run: () => { dialog = 'versions'; } } });
    } catch (e) { toast('error', errorText(e)); }
  }

  const statusText = $derived(saveState === 'saving' ? t('ae.status.saving') : saveState === 'dirty' ? t('ae.status.dirty')
    : saveState === 'conflict' ? t('ae.status.conflict') : saveState === 'error' ? t('ae.status.error') : t('ae.status.saved'));
  const pendingCount = $derived(texSugs.filter((s) => s.state === 'pending').length + qSugs.length);
  const busyAssist = $derived(Object.keys(pending).length > 0);
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="ae" class:narrow class:with-preview={preview && !narrow} class:below={aprefs.preview === 'below'}
      style:--ae-scale={aprefs.fontSize / 100} style:--ae-measure={WIDTHS[aprefs.width]}>
      <header class="bar">
        <h1 class="atitle" title={proj?.settings.front.title}>{proj?.settings.front.title || t('ae.untitled')}</h1>
        <HelpLink page="articles" />
        <span class="status xs" class:warn={saveState === 'conflict' || saveState === 'error'} role="status" aria-live="polite">{statusText}</span>
        <span class="spacer"></span>
        {#if !narrow}
          <div class="seg" role="radiogroup" aria-label={t('ae.modeLabel')}>
            <label><input type="radio" name="ae-mode" value="visual" bind:group={modeSel} onchange={() => setVisual(true)} />{t('ae.mode.visual')}</label>
            <label><input type="radio" name="ae-mode" value="source" bind:group={modeSel} onchange={() => setVisual(false)} />{t('ae.mode.source')}</label>
          </div>
        {/if}
        <Menu label={t('ae.insert')} icon="plus" text={narrow ? '' : t('ae.insert')} items={insertItems} />
        <button class="btn small" onclick={() => (showSugs = !showSugs)} aria-pressed={showSugs}>
          <Icon name="sparkle" size={16} /><span class:sr-only={narrow}>{t('ae.suggestions')}</span>{#if pendingCount}<span class="count">{pendingCount}</span>{/if}
        </button>
        {#if !narrow}
          <button class="btn small" onclick={() => { preview = !preview; setAPref('preview', preview ? (aprefs.preview === 'off' ? 'right' : aprefs.preview) : 'off'); if (preview && !result) void compile(); }} aria-pressed={preview}>
            <Icon name="eye" size={16} />{t('ae.preview')}
          </button>
        {/if}
        <button class="btn small primary" onclick={() => compile({ force: false })} disabled={compiling} aria-busy={compiling}>
          <Icon name="play" size={16} />{compiling ? t('ae.compiling') : t('ae.compile')}
        </button>
        <Menu label={t('ae.more')} items={moreItems} />
      </header>

      {#if conflict}
        <div class="banner warn row" role="alert">
          <span>{t('ae.conflict', { path: conflict.path })}</span>
          <button class="btn small" onclick={() => resolveConflict(true)}>{t('ae.conflict.mine')}</button>
          <button class="btn small" onclick={() => resolveConflict(false)}>{t('ae.conflict.theirs')}</button>
        </div>
      {/if}
      {#if err}<p class="error-text">{err}</p>{/if}

      <div class="body">
        {#if !narrow}
          <nav class="outline" aria-label={t('ae.outline')}>
            <ol>
              <li><button class="node" class:cur={current === 'main.tex'} onclick={() => openFile('main.tex')}><Icon name="file" size={14} />{t('ae.front.node')}</button></li>
              {#each outline as s, i (s.path)}
                <li>
                  <div class="row node-row">
                    <button class="node" class:cur={current === s.path} onclick={() => openFile(s.path)} title={s.path}><span class="num">{i + 1}</span>{s.title}</button>
                    <span class="tools">
                      <button class="btn quiet icon tiny" onclick={() => moveSection(s.path, -1)} disabled={i === 0} aria-label={t('ae.section.up', { title: s.title })}><Icon name="chevronUp" size={14} /></button>
                      <button class="btn quiet icon tiny" onclick={() => moveSection(s.path, 1)} disabled={i === outline.length - 1} aria-label={t('ae.section.down', { title: s.title })}><Icon name="chevronDown" size={14} /></button>
                      <button class="btn quiet icon tiny" onclick={() => deleteSection(s.path)} aria-label={t('ae.section.delete', { title: s.title })}><Icon name="trash" size={14} /></button>
                    </span>
                  </div>
                  {#if s.subs.length && current === s.path}
                    <ol class="subs">{#each s.subs as h}<li><button class="sub" onclick={() => openFile(s.path, h.line)}>{h.title}</button></li>{/each}</ol>
                  {/if}
                </li>
              {/each}
            </ol>
            <button class="btn small quiet add" onclick={() => (dialog = 'newSection')}><Icon name="plus" size={14} />{t('ae.section.add')}</button>
            {#if proj}
              <p class="xs muted meta">{tk(`ae.tpl.${proj.settings.document.template}`, proj.settings.document.class)} · {proj.settings.document.language === 'fr' ? 'Français' : 'English'}
                <button class="linkish" onclick={() => openOptions('document')}>{t('ae.change')}</button></p>
            {/if}
          </nav>
        {:else if proj}
          <label class="sr-only" for="ae-file">{t('ae.outline')}</label>
          <select id="ae-file" class="input phone-nav" value={current} onchange={(e) => openFile((e.target as HTMLSelectElement).value)}>
            <option value="main.tex">{t('ae.front.node')}</option>
            {#each outline as s, i (s.path)}<option value={s.path}>{i + 1}. {s.title}</option>{/each}
          </select>
        {/if}

        <div class="writing" class:ae-paper={aprefs.paper === 'paper'}>
          {#if !proj && !err}<p class="muted pad" aria-busy="true">{t('common.loading')}</p>{/if}
          <div class="host" bind:this={host} hidden={!ready}></div>
          {#if selection && bubble && selection.text.trim().length > 1}
            <div class="bubble" style:left="{bubble.x}px" style:top="{Math.max(0, bubble.y)}px" role="toolbar" aria-label={t('ae.assist.label')}>
              <Icon name="sparkle" size={14} />
              <button class="btn quiet small" onclick={() => assist('rewrite')} disabled={busyAssist}>{t('ae.assist.rewrite')}</button>
              <button class="btn quiet small" onclick={() => assist('shorten')} disabled={busyAssist}>{t('ae.assist.shorten')}</button>
              <Menu label={t('ae.assist.more')} icon="more" items={[
                { label: t('ae.assist.formalise'), run: () => assist('formalise') },
                { label: t('ae.assist.translate_fr'), run: () => assist('translate_fr') },
                { label: t('ae.assist.translate_en'), run: () => assist('translate_en') },
                { label: t('ae.assist.proof_sketch'), run: () => assist('proof_sketch') },
                { label: t('ae.assist.lean'), icon: 'check', run: () => lean() },
                { label: t('ae.assist.sage'), icon: 'notebook', run: () => assist('sage') },
              ]} />
            </div>
          {/if}
        </div>

        {#if preview && !narrow}
          <aside class="preview" aria-label={t('ae.preview')}>
            {#if problems.length}
              <details class="diags" open={errors > 0}>
                <summary>{errors ? t('ae.diag.errors', { n: errors }) : t('ae.diag.notes', { n: problems.length })}</summary>
                <ul>
                  {#each problems as d}
                    <li class="diag {d.severity}">
                      <button class="linkish" onclick={() => openFile(d.path, d.line)} disabled={!d.line}>{d.path.replace('sections/', '')}{d.line ? `:${d.line}` : ''}</button>
                      <span>{d.plain.text}</span>
                      {#if d.fix && d.fix.kind !== 'replace' || d.fix?.kind === 'replace'}<button class="btn small" onclick={() => fix(d)}>{tk(`ae.fix.${d.fix?.kind}`, t('ae.fix.go'), { name: d.fix?.name ?? '', replace: d.fix?.replace ?? '' })}</button>{/if}
                    </li>
                  {/each}
                </ul>
              </details>
            {/if}
            {#if pdfUrl}
              <PdfView url={pdfUrl} label={t('ae.pdfLabel')} target={target} onpoint={inverse} />
              <p class="xs muted">{t('ae.pdfHint')} {#if result}· {t('ae.engine', { engine: result.engine, s: result.seconds.toFixed(1) })}{/if}</p>
            {:else}
              <div class="empty">
                <p>{compiling ? t('ae.compiling') : result && !result.ok ? t('ae.noPdf') : t('ae.previewEmpty')}</p>
                {#if !compiling && !result}<button class="btn small" onclick={() => compile()}>{t('ae.compileNow')}</button>{/if}
              </div>
            {/if}
          </aside>
        {/if}
      </div>

      {#if narrow && problems.length}
        <details class="diags phone">
          <summary>{errors ? t('ae.diag.errors', { n: errors }) : t('ae.diag.notes', { n: problems.length })}</summary>
          <ul>{#each problems as d}<li class="diag {d.severity}"><button class="linkish" onclick={() => openFile(d.path, d.line)}>{d.path.replace('sections/', '')}:{d.line}</button> {d.plain.text}</li>{/each}</ul>
        </details>
      {/if}
      {#if narrow && result?.pdf}
        <p class="pad"><a class="btn small" href={pdfUrl} target="_blank" rel="noopener">{t('ae.openPdf')}</a></p>
      {/if}

      {#if showSugs}
        <section class="sugs" aria-label={t('ae.suggestions')}>
          <div class="row"><h2 class="h3">{t('ae.suggestions')}</h2><span class="spacer"></span><button class="btn quiet icon small" onclick={() => (showSugs = false)} aria-label={t('common.close')}><Icon name="x" size={16} /></button></div>
          {#if texSugs.filter((s) => s.state === 'pending').length}
            <ul class="mine">
              {#each texSugs.filter((s) => s.state === 'pending') as s (s.id)}
                <li><span class="chip">{tk(`ae.sug.kind.${s.kind}`, s.kind)}</span> <del>{s.find.slice(0, 160)}</del> <ins>{s.replace.slice(0, 240)}</ins>
                  <span class="row"><button class="btn small" onclick={() => { if (s.anchor) openFile(s.anchor.path); void decide(s.id, true); }}>{t('ae.sug.accept')}</button>
                  <button class="btn small quiet" onclick={() => decide(s.id, false)}>{t('ae.sug.reject')}</button>
                  {#if s.anchor}<button class="linkish xs" onclick={() => openFile(s.anchor!.path)}>{s.anchor.path}</button>{/if}</span></li>
              {/each}
            </ul>
          {:else}<p class="xs muted">{t('ae.sug.none')}</p>{/if}
          <SuggestionsReview {pid} />
        </section>
      {/if}
    </div>

    {#if proj}
      <ArticleOptions {pid} bind:open={optionsOpen} bind:tab={optionsTab} settings={proj.settings} templates={proj.templates} fonts={proj.fonts}
        macro={pendingMacro} onsettings={(s, files) => { if (proj) proj.settings = s; for (const f of files) { texts[f.path] = f.text; hashes[f.path] = f.hash; dirty[f.path] = false; ed?.replaceDoc(f.path, f.text); } ed?.refresh(); }}
        onprefs={(k) => { if (k === 'keymap') void ed?.setKeymap(aprefs.keymap); if (k === 'lineNumbers') ed?.setLineNumbers(aprefs.lineNumbers); }}
        beforeChange={saveAll} />
      <ArticleDialogs {pid} bind:dialog settings={proj.settings}
        onfigure={(path, caption) => ed?.insert(path ? `\\begin{figure}[ht]\n\\centering\n\\includegraphics[width=0.7\\linewidth]{${path}}\n\\caption{${caption}}\\label{fig:${path.slice(8, 14)}}\n\\end{figure}\n`
          : '\\begin{figure}[ht]\n\\centering\n\\begin{tikzpicture}\n  \\draw[->] (0,0) -- (2,0) node[right] {$x$};\n  \\draw[->] (0,0) -- (0,2) node[above] {$y$};\n\\end{tikzpicture}\n\\caption{}\n\\end{figure}\n')}
        onsection={addSection}
        onrestored={() => load()}
        onsettings={(s, files) => { if (proj) proj.settings = s; for (const f of files) { texts[f.path] = f.text; hashes[f.path] = f.hash; ed?.replaceDoc(f.path, f.text); } ed?.refresh(); }}
        onimported={() => load()} beforeChange={saveAll} />
    {/if}
  {/snippet}
</ProjectGate>

<style>
  .ae { display: flex; flex-direction: column; min-height: calc(100dvh - var(--topbar-h) - 32px); margin: calc(-1 * var(--s-3)) calc(-1 * var(--s-4)) 0; }
  .bar { display: flex; align-items: center; gap: var(--s-2); flex-wrap: wrap; padding: var(--s-2) var(--s-4); border-bottom: 1px solid var(--line); background: var(--surface); position: sticky; top: var(--topbar-h); z-index: 4; }
  .atitle { font: 700 var(--fs-md) var(--font-serif); margin: 0; max-width: 22ch; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .status { color: var(--text-3); }
  .status.warn { color: var(--failed); font-weight: 600; }
  .count { background: var(--accent); color: var(--on-ink); border-radius: 999px; font: 700 11px var(--font-ui); padding: 1px 6px; margin-left: 2px; }
  .banner { padding: var(--s-2) var(--s-4); background: var(--running-soft); color: var(--text); border-bottom: 1px solid var(--line); }
  .body { flex: 1; display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: 0; }
  .with-preview .body { grid-template-columns: 180px minmax(0, 1fr) minmax(320px, 40%); }
  .with-preview.below .body { grid-template-columns: 200px minmax(0, 1fr); }
  .with-preview.below .preview { grid-column: 1 / -1; }
  .narrow .body { grid-template-columns: 1fr; }
  .outline { border-right: 1px solid var(--line); padding: var(--s-3) var(--s-2); font-size: var(--fs-sm); overflow-y: auto; max-height: calc(100dvh - var(--topbar-h) - 90px); position: sticky; top: calc(var(--topbar-h) + 56px); }
  .outline ol { list-style: none; margin: 0; padding: 0; }
  .node { display: flex; gap: 6px; align-items: baseline; width: 100%; text-align: left; background: none; border: none; color: var(--text); padding: 6px 6px; border-radius: var(--r-1); cursor: pointer; font: inherit; min-height: 32px; }
  .node:hover { background: var(--surface-2); }
  .node.cur { background: var(--accent-soft); color: var(--text); font-weight: 600; box-shadow: inset 2px 0 0 var(--accent); }
  .node .num { color: var(--text-3); font-variant-numeric: tabular-nums; min-width: 1.2em; }
  .node-row { gap: 0; flex-wrap: nowrap; }
  .node-row .tools { display: none; }
  .node-row:hover .tools, .node-row:focus-within .tools { display: inline-flex; }
  .tiny { width: 26px !important; min-height: 26px !important; }
  .subs { padding-left: 1.6em !important; }
  .sub { background: none; border: none; color: var(--text-2); font: var(--fs-xs) var(--font-ui); text-align: left; padding: 3px 4px; cursor: pointer; min-height: 24px; }
  .sub:hover { color: var(--text); }
  .add { margin-top: var(--s-2); }
  .meta { margin-top: var(--s-4); padding: 0 6px; }
  .linkish { background: none; border: none; color: var(--accent); cursor: pointer; padding: 0 2px; font: inherit; text-decoration: underline; min-height: 24px; }
  .writing { position: relative; min-width: 0; background: var(--bg); }
  .writing.ae-paper { background: var(--surface-2); }
  .host { min-height: 70vh; }
  .pad { padding: var(--s-4); }
  .phone-nav { margin: var(--s-2) var(--s-3); width: calc(100% - 2 * var(--s-3)); }
  .bubble { position: absolute; z-index: 6; display: flex; align-items: center; gap: 2px; background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--r-2); box-shadow: var(--shadow-2); padding: 2px 4px 2px 8px; color: var(--online); }
  .preview { border-left: 1px solid var(--line); padding: var(--s-2) var(--s-3); background: var(--surface-3); min-width: 0; position: sticky; top: calc(var(--topbar-h) + 56px); align-self: start; max-height: calc(100dvh - var(--topbar-h) - 70px); overflow: auto; }
  .preview .empty { display: grid; place-items: center; gap: var(--s-2); min-height: 40vh; text-align: center; color: var(--text-2); }
  .diags { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin-bottom: var(--s-2); font-size: var(--fs-sm); }
  .diags.phone { margin: var(--s-2) var(--s-3); }
  .diags summary { cursor: pointer; font-weight: 600; min-height: 28px; }
  .diags ul { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-2); }
  .diag { display: flex; flex-wrap: wrap; gap: 6px; align-items: baseline; padding-left: 8px; border-left: 3px solid var(--line-strong); }
  .diag.error { border-left-color: var(--failed); } .diag.warning { border-left-color: var(--running); }
  .sugs { position: fixed; right: var(--s-3); bottom: var(--s-3); width: min(440px, calc(100vw - 24px)); max-height: 70vh; overflow: auto; background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--r-3); box-shadow: var(--shadow-2); padding: var(--s-3); z-index: 8; }
  .sugs .mine { list-style: none; padding: 0; display: grid; gap: var(--s-2); }
  .sugs del { color: var(--failed); } .sugs ins { color: var(--proved); text-decoration: none; }
  .h3 { font-size: var(--fs-md); margin: 0; }
  @media (max-width: 767px) {
    .ae { margin: calc(-1 * var(--s-3)) calc(-1 * var(--s-3)) 0; }
    .bar { padding: var(--s-2) var(--s-3); }
    .sugs { left: var(--s-2); right: var(--s-2); width: auto; bottom: calc(var(--bottomnav-h) + var(--s-2) + env(safe-area-inset-bottom)); max-height: 60dvh; z-index: 520; }
    :global(html[data-kb='open']) .sugs { bottom: var(--s-2); }
  }
  @media (pointer: coarse) {
    .node, .linkish { min-height: var(--touch); }
    .sub { min-height: 40px; }
    .tiny { width: 40px !important; min-height: 40px !important; }
    .node-row .tools { display: inline-flex; }
  }
  @media (max-width: 1100px) { .with-preview .body { grid-template-columns: 0 minmax(0, 1fr) minmax(320px, 46%); } .with-preview .outline { display: none; } }
</style>
