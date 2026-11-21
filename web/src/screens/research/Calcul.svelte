<script lang="ts">
  // « Calcul » (S-M): Sage / Python cells of the current project, run in Madalean's sandboxed offline kernel.
  // Your own cells run when you ask; code written by the assistant runs only after you approve that exact code
  // (server-enforced). Outputs: text, formulas (KaTeX), plots (PNG / sanitised SVG). One click turns a result into a
  // conjecture, a note, a Lean dossier or an article block.
  import { ApiError } from '../../lib/api/client';
  import { wb, type CalcCell, type CalcRun, type CalcStatus, type CalcTarget } from '../../lib/api/workbench';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { renderMath } from '../../lib/md';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  let cells = $state<CalcCell[]>([]);
  let status = $state<CalcStatus | null>(null);
  let trash = $state<{ id: string; code: string }[]>([]);
  let loadedFor = $state('');
  let err = $state('');
  let drafts = $state<Record<string, string>>({});
  let running = $state<string | null>(null);
  let live = $state<Record<string, string>>({});
  let busy = $state('');
  let newCode = $state('');
  let newLang = $state<'sage' | 'python'>('sage');
  let ask = $state('');
  let answers = $state<{ id: string; text: string; model: string; cell?: string }[]>([]);
  let history = $state<string | null>(null);
  let send = $state<{ cell: CalcCell; target: CalcTarget; text: string; title: string } | null>(null);
  let sendOpen = $state(false);
  let deps = $state<{ state: string; job?: { running?: boolean; phase?: string; done?: number; total?: number; message?: string } } | null>(null);
  let panelOpen = $state(typeof window === 'undefined' || window.innerWidth >= 1024);
  const pidNow = $derived(currentProjectId());
  $effect(() => { if (pidNow && pidNow !== loadedFor) void load(pidNow); });

  async function load(pid: string) {
    try {
      const r = await wb.calc(pid);
      cells = r.sheet.cells; status = r.status; trash = r.trash; loadedFor = pid; err = '';
      for (const c of cells) if (drafts[c.id] === undefined) drafts[c.id] = c.code;
      if (status.available && !status.available['sage']) void loadDeps();
    } catch (e) { err = errorText(e); }
  }
  async function loadDeps() {
    try {
      const r = await wb.deps();
      const c = (r.components ?? []).find((x) => x.component === 'sage');
      deps = c ? { state: String(c.state ?? ''), job: r.jobs?.['sage'] } : null;
    } catch { deps = null; }
  }
  $effect(() => app.on('calcul.output', (ev) => {
    const e = ev as unknown as { cell_id: string; text: string };
    live[e.cell_id] = ((live[e.cell_id] ?? '') + e.text).slice(-20000);
  }));
  $effect(() => app.on('calcul.updated', (ev) => {
    const e = ev as unknown as { project_id: string; cell?: CalcCell; cell_id?: string; run?: CalcRun };
    if (e.project_id !== loadedFor) return;
    if (e.cell) {
      const i = cells.findIndex((c) => c.id === e.cell!.id);
      if (i >= 0) { const local = drafts[e.cell.id] !== cells[i]!.code; cells[i] = e.cell; if (!local) drafts[e.cell.id] = e.cell.code; }
      else { cells = [...cells, e.cell]; drafts[e.cell.id] = e.cell.code; }
    } else if (e.run && e.cell_id) {
      const c = cells.find((x) => x.id === e.cell_id);
      if (c && !c.runs.some((r) => r.id === e.run!.id)) c.runs = [...c.runs, e.run];
    }
  }));
  $effect(() => app.on('deps.progress', (ev) => {
    const e = ev as unknown as { component: string; phase: string; done: number; total: number; message: string };
    if (e.component !== 'sage') return;
    deps = { state: e.phase === 'done' ? 'ok' : 'installing', job: { running: e.phase !== 'done', ...e } };
    if (e.phase === 'done' && loadedFor) void load(loadedFor);
  }));

  const dirty = (c: CalcCell) => (drafts[c.id] ?? c.code) !== c.code;
  const needsApproval = (c: CalcCell) => c.origin === 'assistant' && !status?.auto && c.approved?.hash !== c.code_hash;
  const lastRun = (c: CalcCell) => c.runs[c.runs.length - 1];
  const canExec = $derived(!!status && (status.local || status.remote_allowed));

  async function save(pid: string, c: CalcCell): Promise<CalcCell | null> {
    if (!dirty(c)) return c;
    try { const r = await wb.editCell(pid, c.id, { code: drafts[c.id] ?? c.code }); Object.assign(c, r.cell); return c; }
    catch (e) { toast('error', errorText(e)); return null; }
  }
  async function run(pid: string, c: CalcCell) {
    const saved = await save(pid, c);
    if (!saved || running) return;
    if (needsApproval(saved)) { toast('warn', t('calc.approveFirst')); document.getElementById(`approve-${c.id}`)?.focus(); return; }
    running = c.id; live[c.id] = '';
    try {
      const r = await wb.runCell(pid, c.id, saved.language === 'sage' ? 300 : 60);
      if (!c.runs.some((x) => x.id === r.run.id)) c.runs = [...c.runs, r.run];
    } catch (e) {
      toast('error', e instanceof ApiError && e.kind === 'experiments_host_only' ? t('calc.hostOnly') : errorText(e));
    } finally { running = null; live[c.id] = ''; }
  }
  async function stop(pid: string) { try { await wb.interrupt(pid); } catch (e) { toast('error', errorText(e)); } }
  async function approve(pid: string, c: CalcCell) {
    const saved = await save(pid, c);
    if (!saved) return;
    try { const r = await wb.approveCell(pid, c.id, saved.code_hash); Object.assign(c, r.cell); toast('ok', t('calc.approved')); }
    catch (e) { toast('error', e instanceof ApiError && e.status === 409 ? t('calc.stale') : errorText(e)); }
  }
  async function add(pid: string, runIt: boolean) {
    const code = newCode.trim();
    if (!code) return;
    try {
      const r = await wb.addCell(pid, code, newLang);
      cells = [...cells.filter((x) => x.id !== r.cell.id), r.cell]; drafts[r.cell.id] = r.cell.code; newCode = '';
      if (runIt) await run(pid, cells[cells.length - 1]!);
    } catch (e) { toast('error', errorText(e)); }
  }
  async function remove(pid: string, c: CalcCell) {
    cells = cells.filter((x) => x.id !== c.id);
    try {
      await wb.deleteCell(pid, c.id);
      toast('ok', t('calc.deleted'), { action: { label: t('common.undo'), run: async () => {
        try { const r = await wb.restoreCell(pid, c.id); cells = [...cells, r.cell]; drafts[r.cell.id] = r.cell.code; } catch (x) { toast('error', errorText(x)); }
      } } });
    } catch (e) { cells = [...cells, c]; toast('error', errorText(e)); }
  }
  async function move(pid: string, c: CalcCell, d: -1 | 1) {
    const i = cells.indexOf(c);
    const j = i + d;
    if (j < 0 || j >= cells.length) return;
    const copy = [...cells]; copy.splice(i, 1); copy.splice(j, 0, c); cells = copy;
    try { await wb.moveCell(pid, c.id, j); } catch (e) { toast('error', errorText(e)); void load(pid); }
    queueMicrotask(() => document.getElementById(`mv-${d < 0 ? 'up' : 'down'}-${c.id}`)?.focus());
  }
  async function assist(pid: string, action: 'write' | 'fix' | 'explain', c?: CalcCell) {
    busy = action + (c?.id ?? '');
    try {
      if (c) await save(pid, c);
      const r = await wb.assist(pid, { action, cell_id: c?.id, prompt: action === 'write' ? ask : '', language: newLang });
      if (r.text) answers = [{ id: crypto.randomUUID?.() ?? String(Date.now()), text: r.text, model: r.model, cell: c?.id }, ...answers].slice(0, 12);
      if (r.cell) {
        const i = cells.findIndex((x) => x.id === r.cell!.id);
        if (i >= 0) cells[i] = r.cell; else cells = [...cells, r.cell];
        drafts[r.cell.id] = r.cell.code;
        if (action === 'write') ask = '';
        toast('ok', r.approval_required ? t('calc.reviewNew') : t('calc.written'));
        queueMicrotask(() => document.getElementById(`code-${r.cell!.id}`)?.focus());
      }
    } catch (e) { toast('error', errorText(e)); } finally { busy = ''; }
  }
  function openSend(c: CalcCell, target: CalcTarget) {
    const r = lastRun(c);
    const out = r ? [r.stdout, r.result].join('\n').trim() : '';
    send = { cell: c, target, title: '', text: target === 'article' ? '' : target === 'note' ? '' : out.split('\n').slice(0, 6).join('\n') };
    sendOpen = true;
  }
  async function doSend(pid: string, e: Event) {
    e.preventDefault();
    if (!send) return;
    const s = send;
    try {
      const r = await wb.sendTo(pid, s.cell.id, s.target, s.text, s.title);
      sendOpen = false;
      if (s.target === 'conjecture') { const cj = r['conjecture'] as { id: string }; toast('ok', t('calc.sent.conjecture'), { action: { label: t('calc.open'), run: () => navigate(`/conjectures/${cj.id}`) } }); }
      else if (s.target === 'note') { const n = r['note'] as { id: string }; toast('ok', t('calc.sent.note'), { action: { label: t('calc.open'), run: () => navigate(`/notes/${n.id}`) } }); }
      else if (s.target === 'dossier') { const d = r['dossier'] as { id: string }; toast('ok', t('calc.sent.dossier'), { action: { label: t('calc.open'), run: () => navigate(`/d/${d.id}`) } }); }
      else toast('ok', t('calc.sent.article'), { action: { label: t('calc.open'), run: () => navigate('/article') } });
    } catch (x) { toast('error', errorText(x)); }
  }
  async function installSage() {
    try { await wb.installDep('sage'); deps = { state: 'installing', job: { running: true, phase: 'start' } }; }
    catch (e) { toast('error', e instanceof ApiError && e.status === 403 ? t('calc.installHostOnly') : errorText(e)); }
  }
  function keydown(pid: string, c: CalcCell, e: KeyboardEvent) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || e.shiftKey)) { e.preventDefault(); void run(pid, c); }
  }
  function latex(src: string): string {
    const s = src.trim().replace(/^\$\$([\s\S]*)\$\$$/, '$1').replace(/^\\\[([\s\S]*)\\\]$/, '$1').replace(/^\$([\s\S]*)\$$/, '$1');
    return renderMath(s, true);
  }
  function rows(code: string): number { return Math.min(24, Math.max(3, code.split('\n').length + 1)); }
</script>

<ProjectGate>
  {#snippet children(pid: string)}
    <div class="calc">
      <header class="head">
        <div class="row">
          <h1>{t('calc.title')}</h1>
          <HelpLink page="calcul" />
          <span class="spacer"></span>
          {#if status}
            <span class="chip local" title={t('calc.sandboxHint')}><Icon name="lock" size={12} />{tk(`calc.sandbox.${status.sandbox}`, status.sandbox)}</span>
            {#if running}<button class="btn small" onclick={() => stop(pid)}><Icon name="stop" size={14} />{t('calc.interrupt')}</button>{/if}
          {/if}
        </div>
        <p class="lead">{t('calc.lead')}</p>
      </header>

      {#if err}<p class="error-text" role="alert">{err}</p>{/if}
      {#if status && !canExec}<p class="banner warn" role="status">{t('calc.remoteOff')}</p>{/if}
      {#if status && status.available['sage'] === false}
        <div class="banner" role="status">
          <p><strong>{t('calc.noSage')}</strong> {t('calc.noSageText')}</p>
          {#if deps?.job?.running || deps?.state === 'installing'}
            <p class="small" aria-live="polite">{t('calc.installing')} {deps?.job?.message ?? ''}</p>
            {#if deps?.job?.total}<progress max={deps.job.total} value={deps.job.done ?? 0} aria-label={t('calc.installing')}></progress>{:else}<progress aria-label={t('calc.installing')}></progress>{/if}
          {:else if status.local}<button class="btn small primary" onclick={installSage}><Icon name="download" size={14} />{t('calc.installSage')}</button>
          {:else}<p class="small muted">{t('calc.installHostOnly')}</p>{/if}
        </div>
      {/if}

      <div class="layout">
        <section class="sheet" aria-label={t('calc.sheet')}>
          {#if !cells.length && loadedFor === pid}
            <div class="empty"><p>{t('calc.empty')}</p></div>
          {/if}
          <ol class="cells">
            {#each cells as c, i (c.id)}
              {@const r = lastRun(c)}
              {@const ap = needsApproval(c)}
              <li class="cell" class:assistant={c.origin === 'assistant'} class:pending={ap} aria-labelledby="cell-h-{c.id}">
                <div class="gutter">
                  <span class="num" aria-hidden="true">[{i + 1}]</span>
                </div>
                <div class="body">
                  <div class="cell-head row">
                    <h2 class="sr-only" id="cell-h-{c.id}">{t('calc.cellN', { n: i + 1 })}</h2>
                    <span class="who {c.origin}">{c.origin === 'assistant' ? t('calc.byAssistant') : t('calc.byYou')}</span>
                    {#if c.origin === 'assistant'}<span class="xs muted">{c.model}</span>{/if}
                    {#if c.origin === 'assistant'}
                      {#if ap}<span class="badge pending">{t('calc.toReview')}</span>{:else if c.approved}<span class="badge ok">{t('calc.approvedShort')}</span>{/if}
                    {/if}
                    <span class="spacer"></span>
                    <label class="sr-only" for="lang-{c.id}">{t('calc.language')}</label>
                    <select id="lang-{c.id}" class="input lang" value={c.language} onchange={async (e) => { try { const x = await wb.editCell(pid, c.id, { language: (e.target as HTMLSelectElement).value }); Object.assign(c, x.cell); } catch (x) { toast('error', errorText(x)); } }}>
                      <option value="sage">Sage</option><option value="python">Python</option>
                    </select>
                    <button id="mv-up-{c.id}" class="btn small quiet icon" onclick={() => move(pid, c, -1)} disabled={i === 0} aria-label={t('calc.moveUp')}>↑</button>
                    <button id="mv-down-{c.id}" class="btn small quiet icon" onclick={() => move(pid, c, 1)} disabled={i === cells.length - 1} aria-label={t('calc.moveDown')}>↓</button>
                    <button class="btn small quiet icon" onclick={() => remove(pid, c)} aria-label={t('calc.delete', { n: i + 1 })}><Icon name="trash" size={14} /></button>
                  </div>
                  {#if c.note && c.origin === 'assistant'}<p class="xs muted ask">« {c.note} »</p>{/if}
                  <label class="sr-only" for="code-{c.id}">{t('calc.codeOf', { n: i + 1 })}</label>
                  <textarea id="code-{c.id}" class="code-in" spellcheck="false" autocapitalize="off" rows={rows(drafts[c.id] ?? c.code)}
                    bind:value={drafts[c.id]} onkeydown={(e) => keydown(pid, c, e)} onblur={() => save(pid, c)} aria-describedby="hint-{c.id}"></textarea>
                  <p class="xs muted" id="hint-{c.id}">{ap ? t('calc.reviewHint') : t('calc.runHint')}{dirty(c) ? ' ' + t('calc.unsaved') : ''}</p>
                  <div class="row actions">
                    {#if ap}
                      <button id="approve-{c.id}" class="btn small primary" onclick={() => approve(pid, c)} disabled={!canExec}><Icon name="check" size={14} />{t('calc.approve')}</button>
                    {:else}
                      <button class="btn small primary" onclick={() => run(pid, c)} disabled={!canExec || !!running} aria-busy={running === c.id}><Icon name="play" size={14} />{running === c.id ? t('calc.running') : t('calc.run')}</button>
                    {/if}
                    {#if r && (r.status !== 'ok' || r.error)}<button class="btn small" onclick={() => assist(pid, 'fix', c)} disabled={!!busy}><Icon name="sparkle" size={14} />{t('calc.fix')}</button>{/if}
                    <button class="btn small quiet" onclick={() => assist(pid, 'explain', c)} disabled={!!busy}>{t('calc.explain')}</button>
                    {#if c.versions.length > 1 || c.runs.length > 1}<button class="btn small quiet" aria-expanded={history === c.id} onclick={() => (history = history === c.id ? null : c.id)}><Icon name="history" size={14} />{t('calc.history')}</button>{/if}
                  </div>
                  {#if running === c.id && live[c.id]}<pre class="out live" aria-live="polite">{live[c.id]}</pre>{/if}
                  {#if r}
                    <div class="output" class:failed={r.status !== 'ok'} aria-label={t('calc.outputOf', { n: i + 1 })} role="group">
                      <p class="xs muted meta">{tk(`calc.status.${r.status}`, r.status)} · {r.seconds} s · {fmtTime(r.t)}{r.code_hash !== c.code_hash ? ' · ' + t('calc.oldCode') : ''}</p>
                      {#if r.stdout}<pre class="out">{r.stdout}</pre>{/if}
                      {#each r.rich as x, k (k)}
                        {#if x.mime === 'text/latex' && x.data}<div class="tex">{@html latex(x.data)}</div>
                        {:else if x.asset}<img class="plot" src={wb.assetUrl(x.asset)} alt={t('calc.plotAlt', { n: i + 1, k: k + 1 })} loading="lazy" />{/if}
                      {/each}
                      {#if r.result && !r.rich.some((x) => x.mime === 'text/latex')}<pre class="out">{r.result}</pre>{/if}
                      {#if r.error || r.stderr}<pre class="out err">{r.error || r.stderr}</pre>{/if}
                      {#if r.status === 'ok'}
                        <div class="row send" role="group" aria-label={t('calc.sendLabel')}>
                          <span class="xs muted">{t('calc.sendLabel')}</span>
                          {#each ['conjecture', 'note', 'dossier', 'article'] as tg}
                            <button class="btn small quiet" onclick={() => openSend(c, tg as CalcTarget)}>{tk(`calc.to.${tg}`, tg)}</button>
                          {/each}
                        </div>
                      {/if}
                    </div>
                  {/if}
                  {#if history === c.id}
                    <div class="history panel">
                      <h3 class="xs">{t('calc.versions')}</h3>
                      <ol class="vers">{#each [...c.versions].reverse() as v, k (k)}<li><span class="xs muted">{fmtTime(v.t)} · {v.origin === 'assistant' ? t('calc.byAssistant') : t('calc.byYou')}</span>
                        <pre class="out small-code">{v.code}</pre>{#if v.code !== (drafts[c.id] ?? c.code)}<button class="btn small quiet" onclick={() => (drafts[c.id] = v.code)}>{t('calc.useVersion')}</button>{/if}</li>{/each}</ol>
                      <h3 class="xs">{t('calc.runs')}</h3>
                      <ul class="vers">{#each [...c.runs].reverse() as x (x.id)}<li class="xs">{fmtTime(x.t)} · {tk(`calc.status.${x.status}`, x.status)} · {x.seconds} s</li>{/each}</ul>
                    </div>
                  {/if}
                </div>
              </li>
            {/each}
          </ol>

          <form class="new panel" onsubmit={(e) => { e.preventDefault(); void add(pid, true); }}>
            <div class="row">
              <label for="new-code" class="label">{t('calc.newCell')}</label><span class="spacer"></span>
              <label class="sr-only" for="new-lang">{t('calc.language')}</label>
              <select id="new-lang" class="input lang" bind:value={newLang}><option value="sage">Sage</option><option value="python">Python</option></select>
            </div>
            <textarea id="new-code" class="code-in" rows="4" spellcheck="false" autocapitalize="off" placeholder={newLang === 'sage' ? 'factor(2^32 + 1)' : 'sum(range(10))'}
              bind:value={newCode} onkeydown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || e.shiftKey)) { e.preventDefault(); void add(pid, true); } }}></textarea>
            <div class="row">
              <button class="btn small primary" type="submit" disabled={!newCode.trim() || !canExec}><Icon name="play" size={14} />{t('calc.addRun')}</button>
              <button class="btn small" type="button" onclick={() => add(pid, false)} disabled={!newCode.trim()}><Icon name="plus" size={14} />{t('calc.add')}</button>
              {#if trash.length}<span class="xs muted">{t('calc.trashN', { n: trash.length })}</span>{/if}
            </div>
          </form>
        </section>

        <aside class="asst panel" aria-labelledby="asst-h">
          <div class="row"><h2 id="asst-h">{t('calc.assistant')}</h2><span class="spacer"></span>
            <button class="btn small quiet panel-toggle" aria-expanded={panelOpen} onclick={() => (panelOpen = !panelOpen)}>{panelOpen ? t('common.hide') : t('common.show')}</button></div>
          {#if panelOpen}
            <p class="small muted">{t('calc.assistantLead')}</p>
            <form onsubmit={(e) => { e.preventDefault(); void assist(pid, 'write'); }}>
              <label for="asst-q" class="sr-only">{t('calc.askLabel')}</label>
              <textarea id="asst-q" class="input" rows="3" bind:value={ask} placeholder={t('calc.askPh')}></textarea>
              <button class="btn small primary" type="submit" disabled={!ask.trim() || !!busy} aria-busy={busy === 'write'}><Icon name="sparkle" size={14} />{busy === 'write' ? t('calc.thinking') : t('calc.write')}</button>
            </form>
            <p class="xs muted">{t('calc.approvalRule')}</p>
            {#if busy && busy !== 'write'}<p class="small muted" aria-busy="true">{t('calc.thinking')}</p>{/if}
            <ul class="answers" aria-live="polite">
              {#each answers as a (a.id)}<li><Md src={a.text} /><p class="xs muted">{a.model}</p></li>{/each}
            </ul>
          {/if}
        </aside>
      </div>
    </div>

    <Dialog bind:open={sendOpen} title={send ? tk(`calc.to.${send.target}.title`, send.target) : ''}>
      {#if send}
        <form id="send-f" onsubmit={(e) => doSend(pid, e)}>
          <p class="small">{tk(`calc.to.${send.target}.lead`, '')}</p>
          <div class="field"><label for="send-title">{t('calc.sendTitle')}</label><input id="send-title" class="input" bind:value={send.title} maxlength="200" /></div>
          <div class="field"><label for="send-text">{tk(`calc.to.${send.target}.text`, t('calc.sendText'))}</label>
            <textarea id="send-text" class="input" rows="5" bind:value={send.text} required={send.target === 'conjecture' || send.target === 'dossier'}></textarea></div>
          <div class="row"><span class="spacer"></span><button class="btn quiet" type="button" onclick={() => (sendOpen = false)}>{t('common.cancel')}</button>
            <button class="btn primary" type="submit">{tk(`calc.to.${send.target}.go`, t('calc.send'))}</button></div>
        </form>
      {/if}
    </Dialog>
  {/snippet}
</ProjectGate>

<style>
  .calc { max-width: 1320px; }
  .head h1 { margin: 0; }
  .lead { color: var(--text-2); max-width: var(--measure); margin-top: var(--s-1); }
  .banner { border: 1px solid var(--line); border-left: 4px solid var(--local); background: var(--surface); padding: var(--s-3); border-radius: var(--r-2); margin-bottom: var(--s-3); }
  .banner.warn { border-left-color: var(--running-fill); }
  .banner p { margin: 0 0 var(--s-2); }
  progress { width: 100%; max-width: 28rem; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 360px); gap: var(--s-4); align-items: start; }
  .cells { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--s-3); }
  .cell { display: grid; grid-template-columns: 3rem minmax(0, 1fr); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); }
  .cell.assistant { border-color: color-mix(in srgb, var(--online) 35%, var(--line)); }
  .cell.pending { border-style: dashed; border-color: var(--running-fill); }
  .gutter { border-right: 1px solid var(--line); padding: var(--s-3) 0; text-align: center; background: var(--surface-2); border-radius: var(--r-2) 0 0 var(--r-2); }
  .cell.assistant .gutter { background: var(--online-soft); }
  .num { font: 600 var(--fs-xs) var(--font-mono); color: var(--text-3); }
  .body { padding: var(--s-2) var(--s-3) var(--s-3); min-width: 0; }
  .cell-head { gap: var(--s-2); flex-wrap: wrap; }
  .who { font-size: var(--fs-xs); font-weight: 600; }
  .who.assistant { color: var(--online); }
  .badge { font-size: var(--fs-xs); font-weight: 600; padding: 1px 8px; border-radius: 999px; }
  .badge.pending { background: var(--running-soft); color: var(--running); }
  .badge.ok { background: var(--proved-soft); color: var(--proved); }
  .lang { width: auto; min-height: 32px; padding: 2px 6px; font-size: var(--fs-sm); }
  .icon { min-width: 32px; justify-content: center; }
  .ask { margin: 0 0 var(--s-1); font-style: italic; }
  .code-in { width: 100%; box-sizing: border-box; font: 0.875rem/1.5 var(--font-mono); background: var(--surface-2); color: var(--text);
    border: 1px solid var(--line-strong); border-radius: var(--r-1); padding: var(--s-2); resize: vertical; tab-size: 4; }
  .code-in:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
  .actions { gap: var(--s-2); flex-wrap: wrap; margin-top: var(--s-1); }
  .output { margin-top: var(--s-2); border-top: 1px dashed var(--line); padding-top: var(--s-2); }
  .output .meta { margin: 0 0 var(--s-1); }
  .out { font: 0.8125rem/1.5 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; margin: 0 0 var(--s-2); max-height: 28rem; overflow: auto; }
  .out.err { color: var(--failed); background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-1); }
  .out.live { color: var(--text-2); }
  .small-code { font-size: var(--fs-xs); background: var(--surface-2); padding: var(--s-1) var(--s-2); }
  .tex { overflow-x: auto; padding: var(--s-1) 0; }
  .plot { max-width: 100%; height: auto; background: #fff; border-radius: var(--r-1); border: 1px solid var(--line); }
  .send { gap: var(--s-1); flex-wrap: wrap; align-items: center; }
  .history { margin-top: var(--s-2); }
  .vers { list-style: none; padding: 0; margin: 0 0 var(--s-2); display: grid; gap: var(--s-1); }
  .new { margin-top: var(--s-3); display: grid; gap: var(--s-2); }
  .asst { position: sticky; top: var(--s-2); }
  .asst h2 { margin: 0; font-size: var(--fs-lg); }
  .asst textarea { width: 100%; box-sizing: border-box; margin-bottom: var(--s-2); }
  .answers { list-style: none; padding: 0; margin: var(--s-3) 0 0; display: grid; gap: var(--s-3); }
  .answers li { border-top: 1px solid var(--line); padding-top: var(--s-2); }
  .panel-toggle { display: none; }
  .empty { padding: var(--s-4); border: 1px dashed var(--line-strong); border-radius: var(--r-2); color: var(--text-2); }
  @media (max-width: 1023px) {
    .layout { grid-template-columns: minmax(0, 1fr); }
    .asst { position: static; order: -1; }
    .panel-toggle { display: inline-flex; }
  }
  @media (max-width: 599px) {
    .cell { grid-template-columns: minmax(0, 1fr); }
    .gutter { display: none; }
  }
</style>
