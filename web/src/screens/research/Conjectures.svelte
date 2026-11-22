<script lang="ts">
  // Conjecture workshop: propose from the project's context, test before believing (Lean small cases, Sage/Python
  // experiments that run only after you approve that exact code), counter-examples re-verified by the server,
  // an append-only evidence log, and promotion to a theorem only through a Lean proof.
  import { ApiError } from '../../lib/api/client';
  import { research, type Conjecture, type Experiment, type Proposal } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';
  import Md from '../../components/Md.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import type { CheckResult } from '../../lib/api/types';
  import { onDestroy } from 'svelte';
  import { Autosave } from '../../lib/ui/autosave.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  import SaveState from '../../components/SaveState.svelte';
  import EnterHint from '../../components/EnterHint.svelte';

  let { params }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  const cid = $derived(params['id'] ?? '');
  let list = $state<Conjecture[]>([]);
  let c = $state<Conjecture | null>(null);
  let proposing = $state(false);
  let proposals = $state<Proposal[] | null>(null);
  let filtered = $state<Proposal[]>([]);
  let propBusy = $state(false);
  let writing = $state(false);
  let newStmt = $state('');
  let newMotiv = $state('');
  let lean = $state('');
  let leanCheck = $state<CheckResult | null>(null);
  let busy = $state('');
  let output = $state<Record<string, string>>({});
  let codeEdit = $state<Record<string, string>>({});
  let expStatus = $state<{ available: { sage: boolean; python: boolean }; sandbox: string; auto: boolean; remote_allowed: boolean } | null>(null);
  let rev = $state(0);

  $effect(() => { void pid; void rev; if (pid) research.conjectures(pid).then((r) => (list = r.conjectures)).catch((e) => toast('error', errorText(e))); });
  $effect(() => { void cid; if (cid) research.conjecture(cid).then((r) => { c = r.conjecture; lean = r.conjecture.lean_statement; }).catch((e) => toast('error', errorText(e))); else c = null; });
  $effect(() => { research.experimentsStatus().then((s) => (expStatus = s)).catch(() => {}); });
  $effect(() => app.on('conjecture.updated', (ev) => {
    const x = (ev as unknown as { conjecture: Conjecture }).conjecture;
    if (c && x.id === c.id) { c = x; if (!lean) lean = x.lean_statement; }
    rev++;
  }));
  $effect(() => app.on('experiment.output', (ev) => {
    const e = ev as unknown as { conjecture_id: string; experiment_id: string; stream: string; text: string };
    output[e.experiment_id] = (output[e.experiment_id] ?? '') + (e.stream === 'stderr' ? e.text : e.text);
  }));
  const STEPS = ['proposed', 'tested-n-cases', 'lean-statement', 'proved'] as const;

  async function propose() {
    propBusy = true; proposals = null;
    try {
      const notes = (await research.notes(pid)).notes.slice(0, 20).map((n) => n.id);
      const r = await research.generateConjectures(pid, { note_ids: notes, library: true, n: 5 });
      proposals = r.proposals; filtered = r.filtered;
    } catch (e) { toast('error', errorText(e)); } finally { propBusy = false; }
  }
  async function accept(p: Proposal) {
    try { const r = await research.createConjecture({ project_id: pid, statement: p.statement, motivation: p.motivation, lean: p.lean || undefined, origin: p.origin }); proposing = false; rev++; navigate(`/conjectures/${encodeURIComponent(r.conjecture.id)}`); }
    catch (e) { toast('error', errorText(e)); }
  }
  async function write(e: Event) {
    e.preventDefault();
    if (!newStmt.trim()) return;
    try { const r = await research.createConjecture({ project_id: pid, statement: newStmt.trim(), motivation: newMotiv.trim() }); writing = false; newStmt = ''; newMotiv = ''; rev++; navigate(`/conjectures/${encodeURIComponent(r.conjecture.id)}`); }
    catch (x) { toast('error', errorText(x)); }
  }
  async function act<T>(name: string, fn: () => Promise<T>, ok?: string): Promise<T | undefined> {
    busy = name;
    try { const r = await fn(); if (ok) toast('ok', ok); return r; }
    catch (e) {
      if (e instanceof ApiError && e.kind === 'experiments_host_only') toast('warn', t('conj.hostOnly'));
      else toast('error', errorText(e));
    } finally { busy = ''; }
    return undefined;
  }
  async function saveLean() {
    if (!c) return;
    const r = await act('lean', () => research.conjLean(c!.id, lean));
    if (r) { c = r.conjecture; leanCheck = r.check; }
  }
  async function cases() { if (c) { const r = await act('cases', () => research.conjCases(c!.id)); if (r) c = r.conjecture; } }
  async function newExp(language: 'sage' | 'python', kind: 'counterexample' | 'test') {
    if (!c) return;
    const r = await act('exp', () => research.newExperiment(c!.id, { kind, language }));
    if (r) { const x = await research.conjecture(c.id); c = x.conjecture; }
  }
  // S-AK: edited experiment code is saved automatically; a saved edit drops the approval (the server's rule), so the
  // run button asks again with the new code.
  const codeSaver = new Autosave(async () => {
    if (!c) return;
    const cid = c.id;
    let changed = false;
    for (const [eid, code] of Object.entries(codeEdit)) {
      const x = c.experiments.find((e) => e.id === eid);
      if (!x || code === x.code) continue;
      await research.editExperiment(cid, eid, code);
      changed = true;
    }
    if (!changed) return;
    const r = await research.conjecture(cid);
    if (c?.id !== cid) return;
    c = r.conjecture;
    for (const x of c.experiments) if (codeEdit[x.id] === x.code) delete codeEdit[x.id];
  });
  onDestroy(() => codeSaver.destroy());
  async function approveRun(x: Experiment) {
    if (!c) return;
    if (codeEdit[x.id] !== undefined && codeEdit[x.id] !== x.code) {
      await codeSaver.flush();
      toast('info', t('conj.codeChanged'));
      return;
    }
    output[x.id] = '';
    const ok = await act('run', async () => { await research.approveExperiment(c!.id, x.id, x.code_hash); return research.runExperiment(c!.id, x.id); });
    if (ok) toast('info', t('conj.running'));
  }
  async function promote() { if (c) { const r = await act('promote', () => research.promote(c!.id), t('conj.promoted')); if (r) c = r.conjecture; } }
  const exps = $derived(c?.experiments ?? []);
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="cj" class:has-item={Boolean(cid)}>
      <aside class="clist" aria-label={t('conj.list')}>
        <div class="row"><h1>{t('conj.title')}</h1><HelpLink page="conjectures" /></div>
        <div class="row">
          <button class="btn small primary" onclick={() => { proposing = true; void propose(); }}><Icon name="bulb" size={14} />{t('conj.propose')}</button>
          <button class="btn small" onclick={() => (writing = true)}><Icon name="edit" size={14} />{t('conj.write')}</button>
        </div>
        <ul>
          {#each list as x (x.id)}
            <li><a href="/conjectures/{encodeURIComponent(x.id)}" aria-current={x.id === cid ? 'page' : undefined}>
              <span class="ct">{x.title}</span>
              <span class="cstatus st-{x.status}">{tk(`conj.status.${x.status}`, x.status)}{x.status === 'tested-n-cases' ? ` (${x.cases_tested})` : ''}</span>
            </a></li>
          {:else}<li class="muted small">{t('conj.empty')}</li>{/each}
        </ul>
      </aside>

      <section class="detail" aria-label={t('conj.detail')}>
        {#if !c}
          <div class="empty"><h2>{t('conj.pick')}</h2><p>{t('conj.pickText')}</p></div>
        {:else}
          <a class="btn quiet small back-list" href="/conjectures"><Icon name="chevronLeft" size={16} />{t('conj.title')}</a>
          <div class="row"><h2 class="ctitle">{c.title}</h2><span class="cstatus big st-{c.status}">{tk(`conj.status.${c.status}`, c.status)}</span></div>
          <ol class="steps" aria-label={t('conj.progress')}>
            {#each STEPS as s, i}
              <li class:done={c.status !== 'refuted' && STEPS.indexOf(c.status as typeof STEPS[number]) >= i}>{tk(`conj.status.${s}`, s)}</li>
            {/each}
            {#if c.status === 'refuted'}<li class="refuted">{t('conj.status.refuted')}</li>{/if}
          </ol>
          <div class="theorem stmt"><span class="th-head">{t('conj.word')}.</span> <Md src={c.statement_nl} cls="th-body" /></div>
          {#if c.motivation}<p class="small muted">{t('conj.motivation')} : <Md inline src={c.motivation} /></p>{/if}

          {#if c.counterexample}
            <div class="counter" role="status">
              <h3>{t('conj.counterTitle')}</h3>
              <p class="mono">{Object.entries(c.counterexample.witness).map(([k, v]) => `${k} = ${v}`).join(', ')}</p>
              <p class="small">{c.counterexample.verified ? t('conj.counterVerified') : t('conj.counterUnverified')}
                · Sage/Python {c.counterexample.sage ? '✓' : '—'} · Lean {c.counterexample.lean ? '✓' : '—'}</p>
            </div>
          {/if}

          <section class="panel">
            <h3>{t('lean.leanStatement')}</h3>
            <CodeEditor bind:value={lean} language="lean" label={t('lean.leanStatement')} minLines={3} workspace="" />
            <div class="row">
              <button class="btn" onclick={saveLean} disabled={busy === 'lean' || !lean.trim()}>{busy === 'lean' ? t('lean.checking') : t('conj.saveLean')}</button>
              <button class="btn" onclick={() => act('formalize', () => research.conjFormalize(c!.id), t('conj.formalizing'))} disabled={!!busy}>{t('conj.formalize')}</button>
              <button class="btn" onclick={cases} disabled={!!busy || !c.statement_ok}>{busy === 'cases' ? t('lean.checking') : t('conj.cases')}</button>
              <button class="btn" onclick={() => act('prove', () => research.conjProve(c!.id), t('conj.proving'))} disabled={!!busy || !c.statement_ok || c.status === 'refuted'}>{t('conj.prove')}</button>
              <button class="btn" onclick={() => navigate(`/d/${encodeURIComponent(c!.id)}`)}>{t('conj.openDossier')}</button>
            </div>
            {#if leanCheck}<CheckResultView check={leanCheck} />{/if}
          </section>

          <section class="panel">
            <div class="row"><h3>{t('conj.experiments')}</h3><span class="spacer"></span>
              </div>
            <p class="hint">{t('conj.expLead')}</p>
            {#if !app.m.local && !expStatus?.remote_allowed}<p class="small lock"><Icon name="lock" size={14} /> {t('conj.hostOnly')}</p>{/if}
            <div class="row">
              <button class="btn small" onclick={() => newExp('sage', 'counterexample')} disabled={!!busy || !expStatus?.available.sage}>{t('conj.newCounter', { lang: 'Sage' })}</button>
              <button class="btn small" onclick={() => newExp('python', 'counterexample')} disabled={!!busy || !expStatus?.available.python}>{t('conj.newCounter', { lang: 'Python' })}</button>
              <button class="btn small" onclick={() => newExp('python', 'test')} disabled={!!busy}>{t('conj.newTest')}</button>
            </div>
            {#each exps as x (x.id)}
              <article class="exp">
                <div class="row"><strong class="small">{tk(`conj.expKind.${x.kind}`, x.kind)} · {x.language}</strong>
                  <span class="chip {x.status === 'done' ? 'proved' : x.status === 'failed' || x.status === 'rejected' ? 'failed' : x.status === 'running' ? 'running' : ''}">{tk(`conj.expStatus.${x.status}`, x.status)}</span>
                  <span class="xs muted">{x.source === 'ai' ? t('conj.byAi') : t('versions.byYou')}</span></div>
                <label class="label" for="code-{x.id}">{t('conj.code')}</label>
                <textarea id="code-{x.id}" class="input mono code" rows="9" value={codeEdit[x.id] ?? x.code} oninput={(e) => { codeEdit[x.id] = (e.target as HTMLTextAreaElement).value; codeSaver.touch(); }} onblur={() => codeSaver.flush()} spellcheck="false"></textarea>
                <p class="xs muted">{t('conj.approveNote')} {#if codeEdit[x.id] !== undefined}<SaveState state={codeSaver} />{/if}</p>
                <div class="row">
                  {#if x.status !== 'running'}
                    <button class="btn small primary" onclick={() => approveRun(x)} disabled={!!busy}>{codeEdit[x.id] !== undefined && codeEdit[x.id] !== x.code ? t('conj.saveCode') : t('conj.approveRun')}</button>
                    <button class="btn small quiet" onclick={() => act('reject', () => research.rejectExperiment(c!.id, x.id))}>{t('conj.rejectExp')}</button>
                  {/if}
                </div>
                {#if output[x.id]}<pre class="out" role="log" aria-label={t('conj.output')}>{output[x.id]}</pre>{/if}
                {#if x.runs.length}<p class="xs muted">{x.runs.map((r) => `${fmtTime(r.t)} — ${r.verdict || r.status} (${r.seconds.toFixed(1)} s)`).join(' · ')}</p>{/if}
              </article>
            {/each}
          </section>

          <section class="panel">
            <div class="row"><h3>{t('conj.evidence')}</h3><span class="chip {c.chain_ok ? 'proved' : 'failed'}">{c.chain_ok ? t('conj.chainOk') : t('conj.chainBroken')}</span>
              <span class="spacer"></span><button class="btn small" onclick={() => act('lit', () => research.conjLiterature(c!.id), t('conj.litDone'))}>{t('conj.literature')}</button></div>
            <ol class="timeline">
              {#each [...c.evidence].reverse() as e (e.id)}
                <li class="ev v-{e.verdict}">
                  <span class="xs muted">{fmtTime(e.t)} · {tk(`conj.evKind.${e.kind}`, e.kind)}{e.model ? ` · ${e.model}` : ''}</span>
                  <p class="small">{e.summary.text}</p>
                  {#if e.code || e.output}<details><summary class="xs">{t('conj.details')}</summary>{#if e.code}<pre class="out">{e.code}</pre>{/if}{#if e.output}<pre class="out">{e.output}</pre>{/if}</details>{/if}
                </li>
              {/each}
            </ol>
          </section>
          <div class="row">
            <button class="btn primary" onclick={promote} disabled={!c.proved || !!busy}>{t('conj.promote')}</button>
            {#if !c.proved}<span class="hint">{t('conj.promoteHint')}</span>{/if}
          </div>
        {/if}
      </section>
    </div>

    <Dialog bind:open={proposing} title={t('conj.proposeTitle')} wide>
      <p class="small">{t('conj.proposeLead')}</p>
      {#if propBusy}<p class="muted" aria-busy="true">{t('conj.thinking')}</p>
      {:else if proposals}
        <ul class="props">
          {#each proposals as p, i (i)}
            <li class="panel"><Md src={p.statement} />{#if p.motivation}<p class="small muted">{p.motivation}</p>{/if}{#if p.lean}<pre class="out">{p.lean}</pre>{/if}
              <button class="btn small primary" onclick={() => accept(p)}>{t('conj.accept')}</button></li>
          {:else}<li class="muted">{t('conj.noProposal')}</li>{/each}
        </ul>
        {#if filtered.length}<details><summary class="small">{t('conj.filtered', { n: filtered.length })}</summary><ul class="small">{#each filtered as f}<li>{f.statement} — <em>{tk(`conj.filter.${f.reason}`, f.reason ?? '')}</em></li>{/each}</ul></details>{/if}
      {/if}
    </Dialog>
    <Dialog bind:open={writing} title={t('conj.write')}>
      <form id="cjw" onsubmit={write}>
        <div class="field"><label for="cjs">{t('conj.statement')}</label><textarea id="cjs" class="input" rows="3" bind:value={newStmt} use:enterSubmit={() => (document.getElementById('cjw') as HTMLFormElement | null)?.requestSubmit()} aria-describedby="cjs-e"></textarea><EnterHint id="cjs-e" /></div>
        <div class="field"><label for="cjm">{t('conj.motivation')}</label><input id="cjm" class="input" bind:value={newMotiv} /></div>
      </form>
      {#snippet actions()}<button class="btn quiet" onclick={() => (writing = false)}>{t('common.cancel')}</button><button class="btn primary" type="submit" form="cjw">{t('conj.create')}</button>{/snippet}
    </Dialog>
  {/snippet}
</ProjectGate>

<style>
  .cj { display: grid; grid-template-columns: 290px minmax(0, 1fr); gap: var(--s-4); max-width: 1400px; }
  @media (max-width: 900px) { .cj { grid-template-columns: minmax(0, 1fr); } }
  /* Narrow screens: list → detail, one at a time, with a way back. */
  .back-list { display: none; margin-bottom: var(--s-2); }
  @media (max-width: 900px) {
    .has-item .clist { display: none; }
    .cj:not(.has-item) .detail { display: none; }
    .back-list { display: inline-flex; }
  }
  @media (pointer: coarse) { .clist a { min-height: var(--touch); } }
  .clist h1 { margin: 0; }
  .clist ul { list-style: none; padding: 0; margin: var(--s-2) 0 0; }
  .clist a { display: grid; gap: 2px; padding: 8px; border-radius: var(--r-2); text-decoration: none; color: var(--text); }
  .clist a:hover { background: var(--surface-2); }
  .clist a[aria-current='page'] { background: var(--accent-soft); }
  .ct { font-weight: 600; }
  .cstatus { font-size: var(--fs-xs); font-weight: 700; width: fit-content; padding: 1px 8px; border-radius: 999px; border: 1.5px solid var(--line-strong); color: var(--text-2); }
  .cstatus.big { font-size: var(--fs-sm); }
  .st-proved { color: var(--proved); border-color: var(--proved); }
  .st-refuted { color: var(--failed); border-color: var(--failed); }
  .st-lean-statement { color: var(--accent); border-color: var(--accent); }
  .st-tested-n-cases { color: var(--running); border-color: var(--running); }
  .ctitle { margin: 0; font-size: var(--fs-xl); }
  .steps { list-style: none; display: flex; flex-wrap: wrap; gap: 4px; padding: 0; margin: var(--s-2) 0 var(--s-3); font-size: var(--fs-xs); }
  .steps li { padding: 3px 10px; border: 1px dashed var(--line-strong); border-radius: 999px; color: var(--text-3); }
  .steps li.done { border-style: solid; border-color: var(--proved); color: var(--proved); font-weight: 700; }
  .steps li.refuted { border: 1.5px solid var(--failed); color: var(--failed); font-weight: 700; }
  .stmt { margin-bottom: var(--s-3); }
  .stmt :global(.md), .stmt :global(.md p) { display: inline; }
  .counter { border: 2px solid var(--failed); background: var(--failed-soft); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin-bottom: var(--s-3); }
  .counter h3 { margin: 0; color: var(--failed); }
  .detail .panel { margin-top: var(--s-3); }
  .detail h3 { margin: 0 0 var(--s-2); }
  .exp { border-top: 1px solid var(--line); padding-top: var(--s-2); margin-top: var(--s-3); }
  .code { font-size: 0.8125rem; }
  .out { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); max-height: 260px; overflow: auto; }
  .lock { display: flex; gap: 6px; align-items: center; color: var(--text-2); }
  .timeline { list-style: none; padding: 0 0 0 var(--s-3); margin: 0; border-left: 2px solid var(--line); display: grid; gap: var(--s-2); }
  .ev { position: relative; }
  .ev::before { content: ''; position: absolute; left: calc(-1 * var(--s-3) - 6px); top: 6px; width: 10px; height: 10px; border-radius: 50%; background: var(--line-strong); }
  .ev.v-holds::before { background: var(--proved); } .ev.v-refuted::before, .ev.v-counterexample::before { background: var(--failed); }
  .ev p { margin: 0; }
  .props { list-style: none; padding: 0; display: grid; gap: var(--s-2); }
  .empty { max-width: 34rem; }
</style>
