<script lang="ts">
  // « Calcul » (S-P): a Sage notebook. A document is a standard .ipynb (the same file JupyterLab opens) whose cells —
  // code, natural-language requests, text, interactive figures — share ONE kernel. Keyboard like JupyterLab
  // (Esc / Enter modes, Shift+Enter, A/B, M/Y, D D, Z). Model code runs only after approval of that exact code
  // (server-enforced). Every result connects to the research flow: conjecture, note, Lean dossier, article.
  import { tick, untrack } from 'svelte';
  import type { Component } from 'svelte';
  import { ApiError } from '../../lib/api/client';
  import { nb, wb, type NbCell, type NbDocInfo, type NbOutput, type NbView, type CalcTarget } from '../../lib/api/workbench';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { fmtTime } from '../../lib/i18n/index.svelte';
  import { ct } from '../../lib/calcul/strings';
  import { kernelProblem } from '../../lib/calcul/kernel';
  import { renderMath } from '../../lib/md';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import Menu, { type MenuItem } from '../../components/Menu.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import type { FigureSpec } from '../../lib/figure/spec';

  let { params: _p }: { params: Record<string, string> } = $props();
  const FIG = 'application/vnd.madalean.figure+json';
  let docs = $state<NbDocInfo[]>([]);
  let docId = $state('');
  let v = $state<NbView | null>(null);
  let loadedFor = $state('');
  let err = $state('');
  let drafts = $state<Record<string, string>>({});
  let prompts = $state<Record<string, string>>({});
  let sel = $state<string | null>(null);
  let mode = $state<'command' | 'edit'>('command');
  let editingMd = $state<string | null>(null);
  let running = $state<string | null>(null);
  let queue = $state(false);
  let live = $state<Record<string, string>>({});
  let writing = $state<string | null>(null);
  let approxOn = $state<Record<string, boolean>>({});
  let history = $state<string | null>(null);
  let explain = $state<Record<string, string>>({});
  let send = $state<{ cell: NbCell; target: CalcTarget; text: string; title: string } | null>(null);
  let sendOpen = $state(false);
  let newOpen = $state(false);
  let newTitle = $state('');
  let newLang = $state<'sage' | 'python'>('sage');
  let vars = $state<{ name: string; type: string; value: string }[] | null>(null);
  let side = $state<'outline' | 'variables' | null>(typeof window !== 'undefined' && window.innerWidth >= 1200 ? 'outline' : null);
  let lastDeleted: string | null = null;
  let dTimer = 0;
  let dragId = $state<string | null>(null);
  let FigureView = $state<Component<{ spec: FigureSpec; editable?: boolean; onchange?: (s: FigureSpec) => void; onsage?: (c: string) => void; label: string }> | null>(null);
  const pidNow = $derived(currentProjectId());
  const cells = $derived(v?.cells ?? []);
  const status = $derived(v?.status ?? null);
  const canExec = $derived(!!status && (status.local || status.remote_allowed));
  const kstate = $derived(status?.kernel?.state ?? 'none');

  $effect(() => { if (pidNow && pidNow !== loadedFor) void loadDocs(pidNow); });
  $effect(() => { if (cells.some((c) => c.type === 'figure' || c.outputs?.some((o) => o.data && FIG in o.data)) && !FigureView) void loadFigure(); });

  async function loadFigure() {
    const m = await import('../../components/figure/FigureView.svelte');
    FigureView = m.default as unknown as typeof FigureView;
  }
  async function loadDocs(pid: string, want = '') {
    try {
      const r = await nb.docs(pid);
      docs = r.docs; loadedFor = pid;
      const keep = want || (docs.some((d) => d.id === docId) ? docId : docs[0]?.id ?? '');
      await open(pid, keep);
    } catch (e) { err = errorText(e); }
  }
  async function open(pid: string, doc: string) {
    if (!doc) return;
    try {
      const r = await nb.get(pid, doc);
      if (docId !== doc) { drafts = {}; prompts = {}; sel = r.cells[0]?.id ?? null; }
      docId = doc; v = r; err = '';
      for (const c of r.cells) {
        if (drafts[c.id] === undefined || drafts[c.id] === c.source) drafts[c.id] = c.source;
        if (prompts[c.id] === undefined) prompts[c.id] = c.prompt ?? '';
      }
      if (side === 'variables') void loadVars();
    } catch (e) { err = errorText(e); }
  }
  let reloadT = 0;
  function reload() { clearTimeout(reloadT); reloadT = window.setTimeout(() => { if (loadedFor && docId) void open(loadedFor, docId); }, 150); }
  $effect(() => app.on('calcul.output', (ev) => {
    const e = ev as unknown as { doc?: string; cell_id: string; text: string };
    if (e.doc && e.doc !== docId) return;
    live[e.cell_id] = ((live[e.cell_id] ?? '') + e.text).slice(-20000);
  }));
  $effect(() => app.on('calcul.running', (ev) => {
    const e = ev as unknown as { doc?: string; cell_id: string };
    if (!e.doc || e.doc === docId) { running = e.cell_id; live[e.cell_id] = ''; }
  }));
  $effect(() => app.on('calcul.updated', (ev) => {
    const e = ev as unknown as { project_id: string; doc?: string };
    if (e.project_id === loadedFor && (e.doc ?? 'calcul') === docId) reload();
  }));
  $effect(() => app.on('calcul.docs', (ev) => {
    const e = ev as unknown as { project_id: string };
    if (e.project_id === loadedFor) void loadDocs(loadedFor);
  }));

  const idx = (id: string) => cells.findIndex((c) => c.id === id);
  const dirty = (c: NbCell) => (drafts[c.id] ?? c.source) !== c.source;
  const needsApproval = (c: NbCell) => c.origin === 'assistant' && !status?.auto && c.approved?.hash !== c.code_hash;
  const isCode = (c: NbCell) => c.type === 'code' || c.type === 'ask';

  async function save(c: NbCell): Promise<NbCell | null> {
    if (!dirty(c)) return c;
    try { const r = await nb.edit(loadedFor, docId, c.id, { source: drafts[c.id] }); patchCell(r.cell); return r.cell; }
    catch (e) { toast('error', errorText(e)); return null; }
  }
  function patchCell(c: NbCell) {
    if (!v) return;
    const i = idx(c.id);
    if (i >= 0) v.cells[i] = c; else v.cells = [...v.cells, c];
    if (!dirty(c) || drafts[c.id] === undefined) drafts[c.id] = c.source;
  }
  function why(r: string) { return ct(`why.${r}`) === `why.${r}` ? r : ct(`why.${r}`); }
  async function runIds(body: Parameters<typeof nb.run>[2]) {
    if (!canExec) { toast('warn', ct('hostOnly')); return; }
    for (const c of cells) if (dirty(c)) await save(c);
    queue = true;
    try {
      const r = await nb.run(loadedFor, docId, body);
      if (r.stopped && r.stopped.reason !== 'error') {
        toast('warn', ct('stopped', { n: idx(r.stopped.cell_id) + 1, why: why(r.stopped.reason) }));
        if (r.stopped.reason === 'not_approved') select(r.stopped.cell_id);
      }
      if (r.autofix) toast('info', ct('autofix'));
    } catch (e) {
      toast('error', e instanceof ApiError && e.kind === 'experiments_host_only' ? ct('hostOnly') : errorText(e));
    } finally { queue = false; running = null; live = {}; await open(loadedFor, docId); }
  }
  async function runCell(c: NbCell, advance = false) {
    if (c.type === 'markdown') { if (editingMd === c.id) { await save(c); editingMd = null; } if (advance) next(c, true); return; }
    if (!isCode(c)) { if (advance) next(c, true); return; }
    if (c.type === 'ask' && !(drafts[c.id] ?? '').trim()) { await write(c); return; }
    const saved = await save(c);
    if (!saved) return;
    if (needsApproval(saved)) { toast('warn', ct('reviewHint')); document.getElementById(`approve-${c.id}`)?.focus(); return; }
    if (advance) next(c, true);
    await runIds({ cells: [c.id] });
  }
  async function next(c: NbCell, create: boolean) {
    const i = idx(c.id);
    if (i < cells.length - 1) select(cells[i + 1]!.id);
    else if (create) await addCell('code', c.id, true);
  }
  async function approve(c: NbCell) {
    const saved = await save(c);
    if (!saved) return;
    try { const r = await nb.approve(loadedFor, docId, c.id, saved.code_hash!); patchCell(r.cell); await runIds({ cells: [c.id] }); }
    catch (e) { toast('error', errorText(e)); }
  }
  async function write(c: NbCell) {
    const p = (prompts[c.id] ?? '').trim();
    if (!p) { document.getElementById(`prompt-${c.id}`)?.focus(); return; }
    writing = c.id;
    try { const r = await nb.ask(loadedFor, docId, c.id, p); drafts[r.cell.id] = r.cell.source; patchCell(r.cell);
      await tick(); document.getElementById(r.approval_required ? `approve-${c.id}` : `run-${c.id}`)?.focus(); }
    catch (e) { toast('error', errorText(e)); } finally { writing = null; }
  }
  async function addCell(type: NbCell['type'], after: string | null, edit = true, extra: Record<string, unknown> = {}, above = false) {
    try {
      const body: Parameters<typeof nb.add>[2] = { type, ...extra };
      if (above && after) body.at = Math.max(0, idx(after)); else if (after) body.after = after;
      const r = await nb.add(loadedFor, docId, body);
      drafts[r.cell.id] = r.cell.source; prompts[r.cell.id] = r.cell.prompt ?? '';
      await open(loadedFor, docId);
      select(r.cell.id, edit && type !== 'figure');
      if (type === 'markdown' && edit) editingMd = r.cell.id;
    } catch (e) { toast('error', errorText(e)); }
  }
  async function remove(c: NbCell) {
    const i = idx(c.id);
    try {
      await nb.remove(loadedFor, docId, c.id);
      lastDeleted = c.id;
      await open(loadedFor, docId);
      const n = cells[Math.min(i, cells.length - 1)];
      if (n) select(n.id);
      toast('ok', ct('deleted'), { action: { label: 'Z', run: undo } });
    } catch (e) { toast('error', errorText(e)); }
  }
  async function undo() {
    if (!lastDeleted) return;
    try { await nb.restore(loadedFor, docId, lastDeleted); lastDeleted = null; await open(loadedFor, docId); } catch (e) { toast('error', errorText(e)); }
  }
  async function move(c: NbCell, to: number) {
    if (!v || to < 0 || to >= cells.length) return;
    const copy = [...cells]; copy.splice(idx(c.id), 1); copy.splice(to, 0, c); v.cells = copy;
    try { await nb.move(loadedFor, docId, c.id, to); await open(loadedFor, docId); } catch (e) { toast('error', errorText(e)); }
  }
  async function setType(c: NbCell, type: 'code' | 'markdown') {
    if (c.type === type || c.type === 'figure' || c.type === 'ask') return;
    try { const r = await nb.edit(loadedFor, docId, c.id, { type, source: drafts[c.id] ?? c.source }); patchCell(r.cell); } catch (e) { toast('error', errorText(e)); }
  }
  async function toggleOut(c: NbCell) {
    try { const r = await nb.edit(loadedFor, docId, c.id, { outputs_hidden: !c.outputs_hidden }); patchCell(r.cell); } catch (e) { toast('error', errorText(e)); }
  }
  async function kernel(action: 'interrupt' | 'restart' | 'shutdown' | 'clear') {
    try { await nb.kernel(loadedFor, docId, action); if (action !== 'interrupt') await open(loadedFor, docId); } catch (e) { toast('error', errorText(e)); }
  }
  async function loadVars() { try { vars = (await nb.variables(loadedFor, docId)).names; } catch { vars = []; } }
  async function createDoc(e: Event) {
    e.preventDefault();
    try { const r = await nb.createDoc(loadedFor, newTitle || ct('title'), newLang); newOpen = false; newTitle = ''; await loadDocs(loadedFor, r.doc.id); }
    catch (x) { toast('error', errorText(x)); }
  }
  // ---- figures
  let figTimers: Record<string, number> = {};
  function figChange(c: NbCell, spec: FigureSpec) {
    clearTimeout(figTimers[c.id]);
    figTimers[c.id] = window.setTimeout(async () => {
      try {
        const [{ Figure }, { toSVG }] = await Promise.all([import('../../lib/figure/geometry'), import('../../lib/figure/export')]);
        const svg = toSVG(Figure.load(spec));
        await nb.edit(loadedFor, docId, c.id, { figure: spec, svg });
      } catch (e) { toast('error', errorText(e)); }
    }, 600);
  }
  async function figPng(spec: FigureSpec): Promise<string> {
    const [{ Figure }, { toPNG }] = await Promise.all([import('../../lib/figure/geometry'), import('../../lib/figure/export')]);
    const blob = await toPNG(Figure.load(spec));
    return await new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result)); fr.readAsDataURL(blob); });
  }
  // ---- connections
  function outText(c: NbCell): string {
    return (c.outputs ?? []).map((o) => o.type === 'stream' ? o.text : o.type === 'error' ? '' : String(o.data?.['text/plain'] ?? '')).join('\n').trim();
  }
  function openSend(c: NbCell, target: CalcTarget) {
    const out = outText(c);
    const pre = c.type === 'ask' && c.prompt ? `${c.prompt} : ${out.split('\n')[0] ?? ''}` : out.split('\n').slice(0, 4).join('\n');
    send = { cell: c, target, title: '', text: target === 'conjecture' || target === 'dossier' ? pre : '' };
    sendOpen = true;
  }
  async function doSend(e: Event) {
    e.preventDefault();
    if (!send) return;
    const s = send;
    try {
      const body: Parameters<typeof nb.sendTo>[3] = { target: s.target, text: s.text, title: s.title };
      if (s.target === 'article') {
        if (s.cell.type === 'figure' && s.cell.figure) body.png = await figPng(s.cell.figure as unknown as FigureSpec);
        else { const img = (s.cell.outputs ?? []).map((o) => o.data?.['image/png'] as { asset: string } | undefined).find(Boolean); if (img && !s.text) body.asset = img.asset; }
      }
      const r = await nb.sendTo(loadedFor, docId, s.cell.id, body);
      sendOpen = false;
      const go: Record<string, () => void> = {
        conjecture: () => navigate(`/conjectures/${(r['conjecture'] as { id: string }).id}`),
        note: () => navigate(`/notes/${(r['note'] as { id: string }).id}`),
        dossier: () => navigate(`/d/${(r['dossier'] as { id: string }).id}`),
        article: () => navigate('/article'),
      };
      toast('ok', ct('sent'), { action: { label: ct('open'), run: go[s.target]! } });
    } catch (x) { toast('error', errorText(x)); }
  }
  // Phones: the notebook's secondary actions go into one « more » menu (one row of controls instead of three).
  function phoneMore(pid: string): MenuItem[] {
    const items: MenuItem[] = [
      { label: ct('restart'), icon: 'refresh', run: () => void kernel('restart'), disabled: !canExec || queue },
      { label: ct('clear'), icon: 'x', run: () => void kernel('clear'), disabled: queue },
    ];
    if (v) {
      const lab = nb.labUrl(v.doc.path), file = nb.ipynbUrl(pid, docId);
      items.push({ label: ct('openLab'), icon: 'external', run: () => { window.open(lab, '_blank', 'noopener'); } });
      items.push({ label: ct('download'), icon: 'download', run: () => { const a = document.createElement('a'); a.href = file; a.download = ''; document.body.append(a); a.click(); a.remove(); } });
    }
    return items;
  }

  function moreItems(c: NbCell): MenuItem[] {
    const items: MenuItem[] = [];
    const hasOut = isCode(c) ? (c.outputs ?? []).length > 0 : true;
    if (hasOut) for (const tg of ['conjecture', 'note', 'dossier', 'article'] as CalcTarget[]) {
      if (c.type === 'markdown' && tg === 'article') continue;
      items.push({ label: ct(`to.${tg}`), run: () => openSend(c, tg) });
    }
    if (isCode(c)) {
      items.push({ label: ct('runUntil'), run: () => runIds({ until: c.id }) });
      items.push({ label: ct('runFrom'), run: () => runIds({ from: c.id }) });
      items.push({ label: ct('explain'), run: async () => { try { explain[c.id] = (await nb.explain(loadedFor, docId, c.id)).text; } catch (e) { toast('error', errorText(e)); } } });
      if ((c.versions?.length ?? 0) > 1) items.push({ label: ct('history'), run: () => (history = history === c.id ? null : c.id) });
    }
    items.push({ label: ct('moveUp'), run: () => move(c, idx(c.id) - 1), disabled: idx(c.id) === 0 });
    items.push({ label: ct('moveDown'), run: () => move(c, idx(c.id) + 1), disabled: idx(c.id) === cells.length - 1 });
    items.push({ label: ct('del', { n: idx(c.id) + 1 }), run: () => remove(c), danger: true });
    return items;
  }
  // ---- selection & keyboard (JupyterLab-like)
  function select(id: string, edit = false) {
    sel = id; mode = edit ? 'edit' : 'command';
    void tick().then(() => {
      const c = cells.find((x) => x.id === id);
      const target = edit && c ? document.getElementById(c.type === 'ask' && !(drafts[id] ?? '').trim() ? `prompt-${id}` : `src-${id}`) : document.getElementById(`cell-${id}`);
      target?.focus();
      if (!edit) target?.scrollIntoView({ block: 'nearest' });
    });
  }
  function cellKey(c: NbCell, e: KeyboardEvent) {
    if (e.key === 'Enter' && (e.shiftKey || e.ctrlKey || e.metaKey)) { e.preventDefault(); void runCell(c, e.shiftKey); return; }
    const t = e.target as HTMLElement;
    const inField = t.matches('textarea, input, select, [contenteditable]') || !!t.closest('.figure-host');
    if (e.key === 'Escape' && inField && !t.closest('.figure-host')) { e.preventDefault(); if (c.type === 'markdown') { void save(c); editingMd = null; } select(c.id); return; }
    if (inField || t.id !== `cell-${c.id}` || e.altKey || e.ctrlKey || e.metaKey) return;
    const i = idx(c.id);
    const k = e.key;
    if (k === 'Enter') { e.preventDefault(); if (c.type === 'markdown') editingMd = c.id; select(c.id, true); }
    else if (k === 'ArrowDown' || k === 'j') { e.preventDefault(); if (i < cells.length - 1) select(cells[i + 1]!.id); }
    else if (k === 'ArrowUp' || k === 'k') { e.preventDefault(); if (i > 0) select(cells[i - 1]!.id); }
    else if (k === 'a') { e.preventDefault(); void addCell('code', c.id, false, {}, true); }
    else if (k === 'b') { e.preventDefault(); void addCell('code', c.id, false); }
    else if (k === 'm') { e.preventDefault(); void setType(c, 'markdown'); }
    else if (k === 'y') { e.preventDefault(); void setType(c, 'code'); }
    else if (k === 'z') { e.preventDefault(); void undo(); }
    else if (k === 'o') { e.preventDefault(); if (isCode(c)) void toggleOut(c); }
    else if (k === 'd') { e.preventDefault(); if (dTimer && Date.now() - dTimer < 600) { dTimer = 0; void remove(c); } else dTimer = Date.now(); }
  }
  function onDrop(c: NbCell, e: DragEvent) {
    e.preventDefault();
    const from = dragId; dragId = null;
    if (!from || from === c.id) return;
    const f = cells.find((x) => x.id === from);
    if (f) void move(f, idx(c.id));
  }
  // ---- rendering helpers
  function tex(src: string): string {
    const s = src.trim().replace(/^\$\$([\s\S]*)\$\$$/, '$1').replace(/^\\\[([\s\S]*)\\\]$/, '$1').replace(/^\$([\s\S]*)\$$/, '$1').replace(/^\\displaystyle\s*/, '');
    return renderMath(s, true);
  }
  function rows(code: string): number { return Math.min(30, Math.max(2, code.split('\n').length)); }
  const outline = $derived(cells.flatMap((c, i) => c.type === 'markdown' ? c.source.split('\n').filter((l) => /^#{1,3}\s/.test(l)).map((l) => ({ id: c.id, i, depth: l.match(/^#+/)![0].length, text: l.replace(/^#+\s*/, '') })) : []));
  function staleText(c: NbCell) { return c.stale ? ct(`stale.${c.stale_reason}`) : (c.last && !c.fresh && kstate !== 'none' ? ct('oldSession') : ''); }
  // ---- kernel that cannot start / Sage missing: a short message and one action instead of the raw server log
  type InstallJob = { phase: string; done?: number; total?: number; message?: string };
  let sageJob = $state<InstallJob | null>(null);
  function kernelName() { return v?.doc.language === 'python' ? 'Python' : 'Sage'; }
  async function restartAndRun(c: NbCell) {
    await kernel('restart');
    const fresh = cells.find((x) => x.id === c.id);
    if (fresh) await runCell(fresh);
  }
  async function installSage(retry?: NbCell) {
    if (sageJob && sageJob.phase !== 'error' && sageJob.phase !== 'done') return;
    sageJob = { phase: 'queued' };
    try { await wb.installDep('sage'); } catch (e) { sageJob = null; toast('error', errorText(e)); return; }
    toast('ok', ct('installing'));
    for (;;) {                                        // the install takes minutes: follow it, then run the cell again
      await new Promise((r) => setTimeout(r, 2000));
      let job: InstallJob | null = null;
      try { job = (((await wb.deps()).jobs ?? {})['sage'] as InstallJob | undefined) ?? null; } catch { continue; }
      if (!job) continue;
      sageJob = job;
      if (job.phase === 'error') { toast('error', ct('installFailed')); return; }
      if (job.phase === 'done') {
        sageJob = null;
        toast('ok', ct('installed'));
        await open(loadedFor, docId);
        if (retry) { const fresh = cells.find((x) => x.id === retry.id); if (fresh) await runCell(fresh); }
        return;
      }
    }
  }
  function jobText(j: InstallJob): string {
    const pct = j.total ? ` ${Math.round(((j.done ?? 0) / j.total) * 100)} %` : '';
    return ct('installingStep', { step: j.message || j.phase }) + pct;
  }
  void untrack(() => 0);
</script>

<ProjectGate>
  {#snippet children(pid: string)}
    <div class="calc">
      <header class="head">
        <div class="row title-row">
          <h1>{ct('title')}</h1>
          <HelpLink page="calcul" />
          <label class="sr-only" for="doc-pick">{ct('docs')}</label>
          <select id="doc-pick" class="input doc-pick" value={docId} onchange={(e) => open(pid, (e.target as HTMLSelectElement).value)}>
            {#each docs as d (d.id)}<option value={d.id}>{d.title} · {d.language === 'sage' ? 'Sage' : 'Python'}</option>{/each}
          </select>
          <button class="btn small quiet" onclick={() => (newOpen = true)}><Icon name="plus" size={14} />{ct('newDoc')}</button>
          <span class="spacer"></span>
          {#if v}
            <a class="btn small quiet wide-only" href={nb.labUrl(v.doc.path)} target="_blank" rel="noopener">{ct('openLab')}</a>
            <a class="btn small quiet wide-only" href={nb.ipynbUrl(pid, docId)} download>{ct('download')}</a>
          {/if}
        </div>
        <p class="lead">{ct('lead')}</p>
      </header>

      {#if err}<p class="error-text" role="alert">{err}</p>{/if}
      {#if status && !canExec}<p class="banner warn" role="status">{ct('hostOnly')}</p>{/if}
      {#if status && status.available['sage'] === false && v?.doc.language === 'sage'}
        <div class="banner" role="status"><p><strong>{ct('noSage')}</strong></p>
          {#if status.local}<button class="btn small primary" onclick={() => installSage()} disabled={!!sageJob}><Icon name="download" size={14} />{ct('installSage')}</button>{/if}</div>
      {/if}
      {#if status?.kernel?.sandboxed === false}<p class="banner warn" role="alert">{ct('notSandboxed')}</p>{/if}

      <div class="toolbar" role="toolbar" aria-label={ct('status')}>
        <button class="btn small primary" onclick={() => runIds({ all: true })} disabled={!canExec || queue}><Icon name="play" size={14} />{ct('runAll')}</button>
        {#if sel && cells.find((c) => c.id === sel && isCode(c))}<button class="btn small" onclick={() => runIds({ until: sel! })} disabled={!canExec || queue}>{ct('runUntil')}</button>{/if}
        <button class="btn small" onclick={() => kernel('interrupt')} disabled={!queue && kstate !== 'busy'}><Icon name="stop" size={14} />{ct('interrupt')}</button>
        <button class="btn small quiet wide-only" onclick={() => kernel('restart')} disabled={!canExec || queue}>{ct('restart')}</button>
        <button class="btn small quiet wide-only" onclick={() => kernel('clear')} disabled={queue}>{ct('clear')}</button>
        <span class="narrow-only"><Menu label={ct('more')} align="left" items={phoneMore(pid)} /></span>
        <span class="spacer"></span>
        <span class="chip kstate {kstate}" role="status" aria-live="polite" title={ct('idleHint', { n: status?.idle_minutes ?? 30 })}>
          <span class="dot" aria-hidden="true"></span>{queue ? ct('k.busy') : ct(`k.${['none', 'idle', 'busy', 'starting'].includes(kstate) ? kstate : 'unknown'}`)}{status?.kernel?.shared ? ` · ${ct('shared')}` : ''}
        </span>
        <button class="btn small quiet" aria-pressed={side === 'outline'} onclick={() => (side = side === 'outline' ? null : 'outline')}>{ct('outline')}</button>
        <button class="btn small quiet" aria-pressed={side === 'variables'} onclick={() => { side = side === 'variables' ? null : 'variables'; if (side) void loadVars(); }}>{ct('variables')}</button>
      </div>

      <div class="layout" class:with-side={!!side}>
        <section class="sheet" aria-label={v?.doc.title ?? ct('title')}>
          {#if v && !cells.length}<div class="empty"><p>{ct('empty')}</p></div>{/if}
          <ol class="cells">
            {#each cells as c, i (c.id)}
              {@const ap = isCode(c) && needsApproval(c)}
              {@const st = staleText(c)}
              <!-- svelte-ignore a11y_no_noninteractive_element_interactions (a focusable cell: JupyterLab's command mode) -->
              <li id="cell-{c.id}" class="cell {c.type}" class:selected={sel === c.id} class:editing={sel === c.id && mode === 'edit'} class:pending={ap}
                class:dragover={dragId && dragId !== c.id} tabindex="-1" aria-labelledby="cell-h-{c.id}"
                onfocusin={() => { sel = c.id; }} onkeydown={(e) => cellKey(c, e)} ondragover={(e) => { if (dragId) e.preventDefault(); }} ondrop={(e) => onDrop(c, e)}>
                <div class="gutter">
                  <span class="handle" draggable="true" role="img" aria-label={ct('drag', { n: i + 1 })} ondragstart={(e) => { dragId = c.id; e.dataTransfer?.setData('text/plain', c.id); }} ondragend={() => (dragId = null)}>⋮⋮</span>
                  {#if isCode(c)}<span class="num" aria-hidden="true">[{running === c.id ? '*' : (c.exec_count ?? ' ')}]</span>{/if}
                </div>
                <div class="body">
                  <div class="cell-head row">
                    <h2 class="sr-only" id="cell-h-{c.id}">{ct('cellN', { n: i + 1 })} · {ct(`type.${c.type}`)}</h2>
                    <span class="kind">{ct(`type.${c.type}`)}</span>
                    {#if isCode(c) && c.origin === 'assistant'}<span class="who">{ct('byAssistant')}{c.model ? ` · ${c.model}` : ''}</span>
                      {#if ap}<span class="badge pending">{ct('toReview')}</span>{:else if c.approved}<span class="badge ok">{ct('approved')}</span>{/if}{/if}
                    {#if st}<span class="badge stale" title={st}>{c.stale ? ct('stale') : '↺'}<span class="sr-only"> : {st}</span></span>{/if}
                    <span class="spacer"></span>
                    {#if c.type === 'markdown' && editingMd !== c.id && c.source.trim()}<button class="btn small quiet" onclick={() => { editingMd = c.id; select(c.id, true); }}>{ct('editText')}</button>{/if}
                    {#if isCode(c)}
                      {#if ap}<button id="approve-{c.id}" class="btn small primary" onclick={() => approve(c)} disabled={!canExec}><Icon name="check" size={14} />{ct('approve')}</button>
                      {:else}<button id="run-{c.id}" class="btn small primary run" onclick={() => runCell(c)} disabled={!canExec || queue} aria-busy={running === c.id} aria-label="{ct('run')} ({ct('cellN', { n: i + 1 })})"><Icon name="play" size={14} /><span class="run-label">{running === c.id ? ct('running') : ct('run')}</span></button>{/if}
                    {/if}
                    <Menu label="{ct('more')} ({ct('cellN', { n: i + 1 })})" items={moreItems(c)} />
                  </div>

                  {#if c.type === 'ask'}
                    <div class="ask-row">
                      <label class="sr-only" for="prompt-{c.id}">{ct('promptOf', { n: i + 1 })}</label>
                      <textarea id="prompt-{c.id}" class="input prompt" rows="2" bind:value={prompts[c.id]} placeholder={ct('askPh')}
                        onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) { e.preventDefault(); e.stopPropagation(); void write(c); } }}></textarea>
                      <button class="btn small" onclick={() => write(c)} disabled={writing === c.id || !(prompts[c.id] ?? '').trim()} aria-busy={writing === c.id}>
                        <Icon name="sparkle" size={14} />{writing === c.id ? ct('writing') : (c.source.trim() ? ct('rewrite') : ct('write'))}</button>
                    </div>
                    <p class="xs muted">{ap ? ct('reviewHint') : ct('askHint')}</p>
                  {/if}
                  {#if isCode(c) && (c.type === 'code' || (drafts[c.id] ?? '').trim())}
                    <label class="sr-only" for="src-{c.id}">{ct('codeOf', { n: i + 1 })}</label>
                    <textarea id="src-{c.id}" class="code-in" spellcheck="false" autocapitalize="off" autocomplete="off" rows={rows(drafts[c.id] ?? c.source)}
                      bind:value={drafts[c.id]} onfocus={() => { mode = 'edit'; }} onblur={() => save(c)}></textarea>
                  {:else if c.type === 'markdown'}
                    {#if editingMd === c.id || !c.source.trim()}
                      <label class="sr-only" for="src-{c.id}">{ct('textOf', { n: i + 1 })}</label>
                      <textarea id="src-{c.id}" class="code-in md-in" rows={rows(drafts[c.id] ?? c.source)} bind:value={drafts[c.id]}
                        onfocus={() => { mode = 'edit'; editingMd = c.id; }} onblur={async () => { await save(c); editingMd = null; }}></textarea>
                    {:else}
                      <!-- svelte-ignore a11y_no_static_element_interactions (double-click shortcut; the « Modifier le texte » button and Enter do the same) -->
                      <div class="md-view" ondblclick={() => { editingMd = c.id; select(c.id, true); }}><Md src={c.source} /></div>
                    {/if}
                  {:else if c.type === 'figure'}
                    <div class="figure-host">
                      {#if FigureView && c.figure}
                        <FigureView spec={c.figure as unknown as FigureSpec} label={ct('figureLabel', { n: i + 1 })} onchange={(s) => figChange(c, s)}
                          onsage={(code) => addCell('code', c.id, true, { source: code })} />
                      {:else if c.svg}<img class="plot" src={wb.assetUrl(c.svg.asset)} alt={ct('figureLabel', { n: i + 1 })} />{/if}
                    </div>
                  {/if}

                  {#if c.autofix && ap}<p class="xs note-fix" role="status">{ct('autofix')}</p>{/if}
                  {#if running === c.id && live[c.id]}<pre class="out live" aria-live="polite">{live[c.id]}</pre>{/if}
                  {#if isCode(c) && (c.outputs?.length ?? 0) > 0}
                    <div class="output" class:stale={c.stale} role="group" aria-label="{ct('cellN', { n: i + 1 })} : sortie">
                      <button class="btn xsmall quiet fold" aria-expanded={!c.outputs_hidden} onclick={() => toggleOut(c)}>{c.outputs_hidden ? ct('expand') : ct('collapse')}</button>
                      {#if c.last}<span class="xs muted meta">{c.last.seconds} s · {fmtTime(c.last.t)}</span>{/if}
                      {#if c.outputs_hidden}<p class="xs muted">{ct('hiddenOut')}</p>
                      {:else}
                        {#each c.outputs ?? [] as o, k (k)}
                          {@render output(c, i, o, k)}
                        {/each}
                      {/if}
                    </div>
                  {/if}
                  {#if explain[c.id]}<div class="explain"><Md src={explain[c.id]} /></div>{/if}
                  {#if history === c.id && c.versions}
                    <div class="history"><h3 class="xs">{ct('versions')}</h3>
                      <ol class="vers">{#each [...c.versions].reverse() as ver, k (k)}<li><span class="xs muted">{fmtTime(ver.t)} · {ver.origin === 'assistant' ? ct('byAssistant') : ct('byYou')}</span>
                        <pre class="out small-code">{ver.code}</pre>{#if ver.code !== (drafts[c.id] ?? c.source)}<button class="btn xsmall quiet" onclick={() => { drafts[c.id] = ver.code; void save(c); }}>{ct('useVersion')}</button>{/if}</li>{/each}</ol></div>
                  {/if}
                </div>
              </li>
            {/each}
          </ol>

          <div class="adder" role="group" aria-label={ct('addLabel')}>
            {#each ['code', 'ask', 'markdown', 'figure'] as tp (tp)}
              <button class="btn add" onclick={() => addCell(tp as NbCell['type'], cells.length ? cells[cells.length - 1]!.id : null)}><Icon name="plus" size={14} />{ct(`add.${tp}`)}</button>
            {/each}
          </div>
          <details class="keys"><summary>{ct('keys')}</summary><p class="xs">{ct('keysText')}</p></details>
        </section>

        {#if side}
          <aside class="side panel" aria-label={side === 'outline' ? ct('outline') : ct('variables')}>
            {#if side === 'outline'}
              <h2 class="side-h">{ct('outline')}</h2>
              <ul class="outline">
                {#each outline as h (h.id + h.text)}<li style="padding-left:{(h.depth - 1) * 0.75}rem"><button class="link" onclick={() => select(h.id)}>{h.text}</button></li>{/each}
                {#each cells as c, i (c.id)}{#if c.type !== 'markdown'}<li class="xs"><button class="link muted" onclick={() => select(c.id)}>{i + 1}. {ct(`type.${c.type}`)} — {(c.type === 'ask' ? c.prompt : c.type === 'figure' ? String((c.figure as { title?: string } | undefined)?.title ?? '') : c.source.split('\n')[0])?.slice(0, 40) || '…'}</button></li>{/if}{/each}
              </ul>
            {:else}
              <h2 class="side-h">{ct('variables')}</h2>
              {#if vars && vars.length}
                <table class="vars"><tbody>{#each vars as x (x.name)}<tr><th scope="row"><code>{x.name}</code></th><td class="xs muted">{x.type}</td><td class="xs"><code>{x.value}</code></td></tr>{/each}</tbody></table>
              {:else}<p class="xs muted">{ct('noVars')}</p>{/if}
            {/if}
          </aside>
        {/if}
      </div>
    </div>

    <Dialog bind:open={sendOpen} title={send ? ct(`to.${send.target}`) : ''}>
      {#if send}
        <form onsubmit={doSend}>
          <p class="small">{ct(`to.${send.target}.lead`)}</p>
          <div class="field"><label for="send-title">{ct('sendTitle')}</label><input id="send-title" class="input" bind:value={send.title} maxlength="200" /></div>
          {#if send.target !== 'note' || isCode(send.cell)}
            <div class="field"><label for="send-text">{ct('sendText')}</label>
              <textarea id="send-text" class="input" rows="4" bind:value={send.text} required={send.target === 'conjecture' || send.target === 'dossier'}></textarea></div>
          {/if}
          <div class="row"><span class="spacer"></span><button class="btn quiet" type="button" onclick={() => (sendOpen = false)}>✕</button>
            <button class="btn primary" type="submit">{ct('send')}</button></div>
        </form>
      {/if}
    </Dialog>
    <Dialog bind:open={newOpen} title={ct('newDoc')}>
      <form onsubmit={createDoc}>
        <div class="field"><label for="nd-title">{ct('newDocTitle')}</label><input id="nd-title" class="input" bind:value={newTitle} maxlength="200" /></div>
        <div class="field"><label for="nd-lang">{ct('language')}</label><select id="nd-lang" class="input" bind:value={newLang}><option value="sage">SageMath</option><option value="python">Python</option></select></div>
        <div class="row"><span class="spacer"></span><button class="btn primary" type="submit">{ct('create')}</button></div>
      </form>
    </Dialog>
  {/snippet}
</ProjectGate>

{#snippet output(c: NbCell, i: number, o: NbOutput, k: number)}
  {#if o.type === 'stream'}<pre class="out" class:err={o.name === 'stderr'}>{o.text}</pre>
  {:else if o.type === 'error' && kernelProblem(o)}
    {@const kp = kernelProblem(o)}
    <div class="out err kernel-problem" role="alert">
      <p><strong>{kp === 'nosage' ? ct('noSageLong') : kp === 'stopped' ? ct('kernelStopped', { k: kernelName() }) : ct('kernelNoStart', { k: kernelName() })}</strong></p>
      <div class="row">
        {#if kp === 'nosage'}
          {#if sageJob}<span class="small" role="status" aria-live="polite">{jobText(sageJob)}</span>
          {:else if status?.local}<button class="btn small primary" onclick={() => installSage(c)}><Icon name="download" size={14} />{ct('installSageLong')}</button>{/if}
        {:else}<button class="btn small" onclick={() => restartAndRun(c)} disabled={!canExec}><Icon name="refresh" size={14} />{ct('restartKernel')}</button>{/if}
      </div>
      <details><summary class="xs">{ct('details')}</summary><pre class="out">{o.ename}: {o.evalue}{o.traceback ? '\n' + o.traceback : ''}</pre></details>
    </div>
  {:else if o.type === 'error'}<pre class="out err" role="alert">{o.ename}: {o.evalue}{o.traceback ? '\n' + o.traceback.split('\n').slice(-8).join('\n') : ''}</pre>
  {:else}
    {@const d = o.data ?? {}}
    {@const key = `${c.id}:${k}`}
    {#if d[FIG] && FigureView}
      <div class="figure-host"><FigureView spec={d[FIG] as FigureSpec} label={ct('sageFigure', { n: i + 1 })} />
        <button class="btn xsmall quiet" onclick={() => addCell('figure', c.id, false, { figure: d[FIG] })}>+ {ct('add.figure')}</button></div>
    {:else if d['image/png'] || d['image/svg+xml']}
      {@const a = (d['image/svg+xml'] ?? d['image/png']) as { asset: string }}
      <img class="plot" src={wb.assetUrl(a.asset)} alt={String(d['text/plain'] ?? '') || ct('plot', { n: i + 1, k: k + 1 })} loading="lazy" />
    {:else if approxOn[key] && o.approx}<pre class="out">≈ {o.approx}</pre>
    {:else if typeof d['text/latex'] === 'string'}<div class="tex">{@html tex(d['text/latex'] as string)}</div>
    {:else if typeof d['text/plain'] === 'string'}<pre class="out">{d['text/plain']}</pre>{/if}
    {#if o.approx}
      <div class="seg" role="group" aria-label="{ct('exact')} / {ct('approx')}">
        <button class="btn xsmall" aria-pressed={!approxOn[key]} onclick={() => (approxOn[key] = false)}>{ct('exact')}</button>
        <button class="btn xsmall" aria-pressed={!!approxOn[key]} onclick={() => (approxOn[key] = true)}>{ct('approx')}</button>
      </div>
    {/if}
  {/if}
{/snippet}

<style>
  .calc { max-width: 1400px; }
  .head h1 { margin: 0; }
  .title-row { gap: var(--s-2); flex-wrap: wrap; align-items: center; }
  .doc-pick { width: auto; max-width: 22rem; min-height: 36px; }
  .lead { color: var(--text-2); max-width: var(--measure); margin: var(--s-1) 0 var(--s-2); }
  .banner { border: 1px solid var(--line); border-left: 4px solid var(--local); background: var(--surface); padding: var(--s-3); border-radius: var(--r-2); margin-bottom: var(--s-3); }
  .banner.warn { border-left-color: var(--running-fill); }
  .toolbar { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; position: sticky; top: 0; z-index: 3; background: var(--bg, var(--surface)); padding: var(--s-2) 0; border-bottom: 1px solid var(--line); margin-bottom: var(--s-3); }
  .chip { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-xs); padding: 2px 10px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); }
  .kernel-problem p { margin: 0 0 var(--s-1); white-space: normal; }
  .kernel-problem details pre { max-height: 14rem; overflow: auto; font-size: var(--fs-xs); }
  .kstate .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-3); }
  .kstate.idle .dot { background: var(--proved); }
  .kstate.busy .dot { background: var(--running-fill); }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-4); align-items: start; }
  .layout.with-side { grid-template-columns: minmax(0, 1fr) minmax(220px, 300px); }
  .cells { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--s-2); }
  .cell { display: grid; grid-template-columns: 3.25rem minmax(0, 1fr); border: 1px solid transparent; border-left: 3px solid transparent; border-radius: var(--r-2); background: var(--surface); }
  .cell:focus { outline: none; }
  .cell.selected { border-color: var(--line); border-left-color: var(--accent); }
  .cell.selected:focus-visible { box-shadow: 0 0 0 2px var(--focus); }
  .cell.editing { border-left-color: var(--proved); }
  .cell.pending { border-style: dashed; border-color: var(--running-fill); }
  .cell.dragover { border-top: 2px solid var(--accent); }
  .gutter { display: flex; flex-direction: column; align-items: center; gap: 4px; padding-top: var(--s-2); }
  .handle { cursor: grab; color: var(--text-3); font-size: 12px; letter-spacing: -2px; user-select: none; padding: 2px 4px; }
  .num { font: 600 var(--fs-xs) var(--font-mono); color: var(--text-3); }
  .body { padding: var(--s-2) var(--s-3) var(--s-2) 0; min-width: 0; }
  .cell-head { gap: var(--s-2); flex-wrap: wrap; align-items: center; margin-bottom: var(--s-1); }
  .kind { font-size: var(--fs-xs); font-weight: 600; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.04em; }
  .who { font-size: var(--fs-xs); color: var(--online); }
  .badge { font-size: var(--fs-xs); font-weight: 600; padding: 1px 8px; border-radius: 999px; }
  .badge.pending { background: var(--running-soft); color: var(--running); }
  .badge.ok { background: var(--proved-soft); color: var(--proved); }
  .badge.stale { background: var(--surface-2); color: var(--text-2); border: 1px dashed var(--line-strong); }
  .code-in { width: 100%; box-sizing: border-box; font: 0.875rem/1.5 var(--font-mono); background: var(--surface-2); color: var(--text);
    border: 1px solid var(--line); border-radius: var(--r-1); padding: var(--s-2); resize: vertical; tab-size: 4; }
  .md-in { font-family: var(--font-sans, inherit); }
  .code-in:focus-visible, .prompt:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
  .md-view { padding: var(--s-1) var(--s-2); border-radius: var(--r-1); cursor: text; }
  .md-view:focus-visible { outline: 2px solid var(--focus); }
  .ask-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--s-2); align-items: start; }
  .prompt { width: 100%; box-sizing: border-box; }
  .note-fix { color: var(--running); }
  .output { margin-top: var(--s-2); padding-top: var(--s-1); border-top: 1px dashed var(--line); position: relative; }
  .output.stale { opacity: 0.72; }
  .fold { float: right; }
  .meta { display: block; margin-bottom: var(--s-1); }
  .out { font: 0.8125rem/1.5 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; margin: 0 0 var(--s-2); max-height: 28rem; overflow: auto; }
  .out.err { color: var(--failed); background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-1); }
  .out.live { color: var(--text-2); }
  .small-code { font-size: var(--fs-xs); background: var(--surface-2); padding: var(--s-1) var(--s-2); }
  .tex { overflow-x: auto; padding: var(--s-1) 0; }
  .plot { max-width: 100%; height: auto; background: #fff; border-radius: var(--r-1); border: 1px solid var(--line); display: block; margin-bottom: var(--s-2); }
  .seg { display: inline-flex; gap: 2px; margin-bottom: var(--s-2); }
  .seg [aria-pressed='true'] { background: var(--accent-soft); color: var(--text); border-color: var(--accent); font-weight: 700; }
  .figure-host { margin: var(--s-1) 0; }
  .explain { margin-top: var(--s-2); padding: var(--s-2); background: var(--surface-2); border-radius: var(--r-1); }
  .vers { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-1); }
  .adder { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: var(--s-3); }
  .add { min-height: 44px; }
  .keys { margin-top: var(--s-3); color: var(--text-2); }
  .side { position: sticky; top: 3.5rem; max-height: calc(100vh - 5rem); overflow: auto; }
  .side-h { font-size: var(--fs-md, 1rem); margin: 0 0 var(--s-2); }
  .outline { list-style: none; padding: 0; margin: 0; display: grid; gap: 2px; }
  .link { background: none; border: 0; padding: 4px 0; text-align: left; color: var(--accent); cursor: pointer; font: inherit; min-height: 28px; }
  .link.muted { color: var(--text-2); }
  .vars { width: 100%; border-collapse: collapse; }
  .vars th, .vars td { text-align: left; padding: 3px 4px; border-bottom: 1px solid var(--line); vertical-align: top; overflow-wrap: anywhere; }
  .empty { padding: var(--s-4); border: 1px dashed var(--line-strong); border-radius: var(--r-2); color: var(--text-2); }
  .narrow-only { display: none; }
  @media (max-width: 1023px) {
    .layout.with-side { grid-template-columns: minmax(0, 1fr); }
    .side { position: static; max-height: none; order: -1; }
  }
  @media (max-width: 599px) {
    .cell { grid-template-columns: minmax(0, 1fr); }
    .gutter { flex-direction: row; padding: var(--s-1) var(--s-2) 0; }
    .body { padding: var(--s-1) var(--s-2) var(--s-2); }
    .run { min-height: 44px; min-width: 44px; }
    .ask-row { grid-template-columns: minmax(0, 1fr); }
    .toolbar .btn { min-height: 44px; }
    .toolbar { position: static; }
    .wide-only { display: none; }
    .toolbar .narrow-only { display: inline-flex; }
    .toolbar .narrow-only :global(.btn) { min-height: 44px; min-width: 44px; }
  }
  @media (pointer: coarse) { .doc-pick { min-height: var(--touch); } .link { min-height: var(--touch); } }
</style>
