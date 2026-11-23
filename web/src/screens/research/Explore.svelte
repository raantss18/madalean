<script lang="ts">
  // « Moteur de conjectures » (S-AW, docs/CONJECTURES.md): the guided loop Explorer → Reconnaître → Énoncer →
  // Attaquer → Journal. Steps are cards; every step shows its state, can be stopped, and what it tried stays in
  // the journal. The experiment is a cell of the project's Calcul notebook « explorations »: model-written code is
  // approved exactly as in Calcul (same endpoint, same words) and never runs before.
  import { onDestroy } from 'svelte';
  import { ApiError } from '../../lib/api/client';
  import { explore, type Candidate, type ExploreBrief, type ExploreCell, type ExploreStatus, type Exploration, type StepName } from '../../lib/api/explore';
  import { nb } from '../../lib/api/workbench';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { fmtTime, i18n } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { enterSubmit } from '../../lib/ui/enter';
  import { keepDraft } from '../../lib/ui/drafts.svelte';
  import { Autosave } from '../../lib/ui/autosave.svelte';
  import { dismiss } from '../../lib/ui/dismiss';
  import { currentProjectId } from '../../lib/project.svelte';
  import { ct } from '../../lib/calcul/strings';
  import { errText, pick, xt } from '../../lib/conjectures/strings';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import SaveState from '../../components/SaveState.svelte';
  import ExplorePlot from './explore/ExplorePlot.svelte';

  let { params }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  // only an exploration id: while the router swaps screens this component can briefly see another route's `id`
  const xid = $derived(/^x-[0-9a-f]{8}$/.test(params['id'] ?? '') ? params['id']! : '');

  let status = $state<ExploreStatus | null>(null);
  let past = $state<ExploreBrief[]>([]);
  let question = $state('');
  keepDraft(() => (pid ? `explore.${pid}` : ''), () => question, (v) => (question = v));
  let creating = $state(false);
  let x = $state<Exploration | null>(null);
  let cell = $state<ExploreCell | null>(null);
  let running = $state(false);
  let execAllowed = $state(true);
  let busy = $state('');
  let live = $state('');
  let editing = $state(false);
  let codeDraft = $state('');
  let discardFor = $state('');
  let discardWhy = $state('');
  let discardBtn = $state<HTMLElement | null>(null);
  let showDiscarded = $state(false);
  let rev = $state(0);

  const STEPS: StepName[] = ['explore', 'recognise', 'state', 'attack'];
  const lang = $derived(i18n.lang);

  function fail(e: unknown) {
    const own = e instanceof ApiError ? errText(e.kind) : '';
    toast(e instanceof ApiError && (e.kind === 'not_approved' || e.kind === 'experiments_host_only' || e.kind === 'busy') ? 'warn' : 'error', own || errorText(e));
  }
  function apply(v: { exploration: Exploration; cell?: ExploreCell | null; running: boolean; exec_allowed?: boolean }) {
    x = v.exploration; running = v.running;
    if (v.cell !== undefined) cell = v.cell;
    if (v.exec_allowed !== undefined) execAllowed = v.exec_allowed;
    if (!editing) codeDraft = v.exploration.code;
  }
  async function refresh() {
    if (!xid) return;
    try { apply(await explore.get(xid)); } catch (e) { fail(e); }
  }

  $effect(() => { void pid; if (pid) explore.status(pid).then((s) => (status = s)).catch(() => {}); });
  $effect(() => { void pid; void rev; void xid; if (pid && !xid) explore.list(pid).then((r) => (past = r.explorations)).catch((e) => fail(e)); });
  $effect(() => {
    void xid;
    x = null; cell = null; live = ''; editing = false; discardFor = '';
    if (!xid) return;
    explore.get(xid).then((v) => { apply(v); explore.warm(xid).catch(() => {}); }).catch((e) => { if (!location.pathname.startsWith('/explorer/')) return; fail(e); navigate('/explorer', { replace: true }); });
  });
  $effect(() => app.on('explore.updated', (ev) => {
    const e = ev as unknown as { exploration: Exploration; running: boolean };
    if (!x || e.exploration.id !== x.id) return;
    const was = running;
    apply(e);
    if (was && !e.running) void refresh();          // the cell's approval state and the full view, once at the end
  }));
  $effect(() => app.on('calcul.output', (ev) => {
    const e = ev as unknown as { cell_id: string; text: string };
    if (x?.cell && e.cell_id === x.cell.id) live = (live + e.text).slice(-8000);
  }));

  async function start(q = question) {
    const text = q.trim();
    if (!text || creating) { if (!text) toast('warn', xt('err.empty')); return; }
    creating = true;
    try {
      const v = await explore.create(pid, text);
      question = '';
      navigate(`/explorer/${encodeURIComponent(v.exploration.id)}`);
      apply(v);
      // what can run at once does (given terms, checked code); model code waits for the approval below
      if (v.exec_allowed && (v.exploration.origin === 'data' || v.cell?.may_run)) await run(v.exploration.id);
    } catch (e) { fail(e); } finally { creating = false; }
  }
  async function run(id = x?.id ?? '') {
    if (!id) return;
    live = '';
    try { apply(await explore.run(id)); } catch (e) { fail(e); void refresh(); }
  }
  async function approveRun() {
    if (!x || !cell) return;
    await codeSaver.flush();
    busy = 'approve';
    try {
      const c = cell;
      await nb.approve(x.project_id, c.doc, c.id, c.code_hash);
      await run(x.id);
    } catch (e) { fail(e); void refresh(); } finally { busy = ''; }
  }
  async function stop() {
    if (!x || !running) return;
    try { apply(await explore.stop(x.id)); toast('info', xt('stoppedToast')); } catch (e) { fail(e); }
  }
  function onKey(e: KeyboardEvent) {
    if (e.key !== 'Escape' || e.defaultPrevented || !running || discardFor) return;
    if (document.querySelector('dialog[open], [role="menu"]')) return;
    e.preventDefault();
    void stop();
  }

  // the experiment's code: an edit is saved by itself and becomes the user's code (no « Enregistrer » button)
  const codeSaver = new Autosave(async () => {
    if (!x || codeDraft === x.code || !codeDraft.trim()) return;
    apply(await explore.setCode(x.id, codeDraft));
  });
  onDestroy(() => codeSaver.destroy());

  async function act(name: string, c: Candidate, fn: () => Promise<void>) {
    busy = `${name}:${c.id}`;
    try { await fn(); } catch (e) { fail(e); void refresh(); } finally { busy = ''; }
  }
  const attack = (c: Candidate) => act('attack', c, async () => { apply(await explore.attack(x!.id, c.id)); });
  const keep = (c: Candidate) => act('keep', c, async () => {
    const r = await explore.keep(x!.id, c.id);
    apply(r);
    toast(r.duplicate ? 'info' : 'ok', r.duplicate ? xt('dupToast') : xt('keptToast'), { action: { label: xt('openConj'), run: () => navigate(`/conjectures/${encodeURIComponent(r.conjecture_id)}`) } });
  });
  const prove = (c: Candidate) => act('prove', c, async () => {
    const r = await explore.prove(x!.id, c.id);
    apply(r);
    toast('ok', xt('proveToast'), { action: { label: xt('openDossier'), run: () => navigate(`/d/${encodeURIComponent(r.conjecture_id)}`) } });
  });
  async function discard(c: Candidate) {
    const why = discardWhy;
    discardFor = ''; discardWhy = '';
    await act('discard', c, async () => { apply(await explore.discard(x!.id, c.id, why)); toast('info', xt('discardedToast')); });
  }
  async function exportTo(to: 'note' | 'article') {
    if (!x) return;
    busy = `export:${to}`;
    try {
      const r = await explore.exportTo(x.id, to);
      apply(r);
      if (to === 'note') toast('ok', xt('exportedNote'), { action: { label: xt('openNote'), run: () => navigate(`/notes/${encodeURIComponent(r.note_id ?? '')}`) } });
      else toast('ok', xt('exportedArticle'), { action: { label: xt('openArticle'), run: () => navigate('/article') } });
    } catch (e) { fail(e); } finally { busy = ''; }
  }
  async function remove(b: ExploreBrief) {
    try { await explore.remove(b.id); toast('info', xt('deleted')); rev++; } catch (e) { fail(e); }
  }

  const needsApproval = $derived(Boolean(cell && !cell.may_run));
  const table = $derived(x?.table ?? null);
  const shownRows = $derived(table ? table.rows.slice(0, 40) : []);
  const active = $derived((x?.candidates ?? []).filter((c) => c.status !== 'discarded'));
  const dropped = $derived((x?.candidates ?? []).filter((c) => c.status === 'discarded'));
  const keptFindings = $derived((x?.findings ?? []).filter((f) => f.status === 'kept'));
  const recogJournal = $derived((x?.journal ?? []).filter((e) => e.step === 'recognise' && e.kind === 'discarded'));
  const journal = $derived([...(x?.journal ?? [])].reverse());
  const stepChip = (s: string) => (s === 'done' ? 'proved' : s === 'failed' ? 'failed' : s === 'running' ? 'running' : '');
  function stepError(name: StepName): string {
    const s = x?.steps[name];
    if (!s?.error || s.state === 'awaiting_approval') return '';
    return (errText(s.error) || s.error) + (s.detail ? ` — ${s.detail}` : '');
  }
  const witness = (w: Record<string, unknown>) => Object.entries(w).filter(([, v]) => typeof v !== 'object').map(([k, v]) => `${k} = ${v}`).join(', ');
  const kindName = (k: string) => xt(`kind.${k}`);
</script>

<svelte:window onkeydown={onKey} />

<ProjectGate>
  {#snippet children(_pid)}
    <div class="xp">
      <div class="row head">
        <a class="btn quiet small" href="/conjectures"><Icon name="chevronLeft" size={16} />{xt('back')}</a>
        <h1>{xt('title')}</h1><HelpLink page="conjectures" />
        <span class="spacer"></span>
        {#if xid}<a class="btn small" href="/explorer"><Icon name="plus" size={14} />{xt('newOne')}</a>{/if}
      </div>

      {#if !xid}
        <p class="hint lead">{xt('lead')}</p>
        <section class="panel">
          <form onsubmit={(e) => { e.preventDefault(); void start(); }}>
            <div class="field">
              <label for="xp-q">{xt('question')}</label>
              <textarea id="xp-q" class="input q" rows="2" bind:value={question} placeholder={xt('questionPh')} use:enterSubmit={() => void start()} aria-describedby="xp-q-e"></textarea>
              <EnterHint id="xp-q-e" />
            </div>
            <div class="row">
              <button class="btn primary" type="submit" disabled={creating || !question.trim()} aria-busy={creating}><Icon name="search" size={16} />{creating ? xt('starting') : xt('start')}</button>
            </div>
          </form>
          {#if status?.examples.length}
            <h2 class="sub">{xt('examples')}</h2>
            <ul class="examples">
              {#each status.examples as ex}<li><button class="btn small ex" type="button" onclick={() => { question = pick(ex); document.getElementById('xp-q')?.focus(); }}>{pick(ex)}</button></li>{/each}
            </ul>
          {/if}
          {#if status?.oeis === 'off'}<p class="xs muted">{xt('oeis.off')}</p>{/if}
        </section>
        <section class="panel" aria-labelledby="xp-past-h">
          <h2 id="xp-past-h">{xt('past')}</h2>
          <ul class="past">
            {#each past as b (b.id)}
              <li>
                <a href="/explorer/{encodeURIComponent(b.id)}"><span class="pq">{b.question}</span>
                  <span class="xs muted">{fmtTime(b.created)}{b.summary ? ` · ${b.summary}` : ''} · {xt('candidatesN', { n: b.candidates })}{b.refuted ? ` · ${xt('refutedN', { n: b.refuted })}` : ''}</span></a>
                <button class="btn small quiet" type="button" onclick={() => remove(b)} aria-label={xt('delOf', { q: b.question.slice(0, 60) })}><Icon name="trash" size={14} /></button>
              </li>
            {:else}<li class="muted small">{xt('noPast')}</li>{/each}
          </ul>
        </section>
      {:else if x}
        <p class="theorem xq"><span class="th-head">{xt('question')}.</span> {x.question}</p>
        <div class="row bar" role="status" aria-live="polite">
          <ol class="steps" aria-label={xt('steps')}>
            {#each STEPS as s}<li class="st-{x.steps[s].state}"><a href="#xp-{s}">{xt(`step.${s}`)}</a><span class="sr-only"> : {xt(`state.${x.steps[s].state}`)}</span></li>{/each}
          </ol>
          <span class="spacer"></span>
          {#if running}
            <span class="xs muted">{xt('runningNow')} {xt('stopHint')}</span>
            <button class="btn small danger" type="button" onclick={stop}><Icon name="stop" size={14} />{xt('stop')}</button>
          {/if}
        </div>

        <!-- 1. Explorer -->
        <section class="panel card" id="xp-explore" aria-labelledby="xp-explore-h">
          <div class="row"><h2 id="xp-explore-h">1. {xt('step.explore')}</h2><span class="chip {stepChip(x.steps.explore.state)}">{xt(`state.${x.steps.explore.state}`)}</span>
            {#if x.steps.explore.seconds}<span class="xs muted">{xt('seconds', { s: x.steps.explore.seconds })}</span>{/if}</div>
          <p class="hint">{xt('stepLead.explore')}</p>
          {#if x.origin === 'data'}<p class="small">{xt('givenTerms')}</p>
          {:else if x.origin === 'model'}<p class="small">{xt('notRecognised')}</p>
          {:else if x.intent.summary && x.origin === 'catalogue'}<p class="small">{xt('recognised', { what: x.intent.summary })} <span class="xs muted">({xt('byCatalogue')})</span></p>
          {:else if x.origin === 'user'}<p class="small muted">{xt('byUser')}</p>{/if}
          {#if stepError('explore')}<p class="error-text" role="alert">{stepError('explore')}</p>{/if}
          {#if !execAllowed}<p class="banner warn" role="status">{ct('hostOnly')}</p>{/if}

          {#if x.origin !== 'data'}
            <div class="code-head row">
              <span class="label">{xt('code')}</span>
              {#if cell?.origin === 'assistant'}<span class="who xs muted">{ct('byAssistant')}{cell.model ? ` · ${cell.model}` : ''}</span>
                {#if needsApproval}<span class="badge pending">{ct('toReview')}</span>{:else if cell.approved}<span class="badge ok">{ct('approved')}</span>{/if}{/if}
              <span class="spacer"></span>
              {#if editing}<SaveState state={codeSaver} />{/if}
              <button class="btn small quiet" type="button" onclick={() => { if (editing) void codeSaver.flush(); editing = !editing; }} disabled={running} aria-expanded={editing}>{editing ? xt('closeCode') : xt('editCode')}</button>
            </div>
            {#if !x.code && !editing}<p class="small muted">{xt('noCodeYet')}</p>{/if}
            {#if editing}
              <label class="sr-only" for="xp-code">{xt('code')}</label>
              <textarea id="xp-code" class="code-in" spellcheck="false" autocapitalize="off" autocomplete="off" rows={Math.min(24, Math.max(6, codeDraft.split('\n').length + 1))}
                bind:value={codeDraft} oninput={() => codeSaver.touch()} onblur={() => codeSaver.flush()} aria-describedby="xp-code-hint"></textarea>
              <p class="xs muted" id="xp-code-hint">{xt('codeHint')}</p>
            {:else if x.code}
              <!-- svelte-ignore a11y_no_noninteractive_tabindex (a scrollable box must be reachable by keyboard) -->
              <pre class="code-view" tabindex="0" aria-label={xt('code')}>{x.code}</pre>
            {/if}
            {#if needsApproval}<p class="xs review">{ct('reviewHint')}</p>{/if}
            <div class="row actions">
              {#if needsApproval}
                <button id="xp-approve" class="btn small primary" type="button" onclick={approveRun} disabled={!execAllowed || running || busy === 'approve'}><Icon name="check" size={14} />{ct('approve')}</button>
              {:else if x.code}
                <button id="xp-run" class="btn small primary" type="button" onclick={() => run()} disabled={!execAllowed || running} aria-busy={running && x.steps.explore.state === 'running'}><Icon name="play" size={14} />{x.steps.explore.state === 'done' ? xt('rerun') : xt('run')}</button>
              {/if}
              {#if x.cell}<a class="btn small quiet" href="/calcul">{xt('inNotebook')}</a>{/if}
            </div>
            {#if live && x.steps.explore.state === 'running'}<pre class="out" role="log" aria-label={xt('output')}>{live}</pre>{/if}
          {:else if x.steps.explore.state !== 'done' && !running}
            <div class="row actions"><button class="btn small primary" type="button" onclick={() => run()}><Icon name="play" size={14} />{xt('run')}</button></div>
          {/if}

          {#if table}
            <h3 class="sub">{xt('data')}</h3>
            <div class="data">
              <!-- svelte-ignore a11y_no_noninteractive_tabindex (a scrollable box must be reachable by keyboard) -->
              <div class="tbox" tabindex="0" role="group" aria-label={xt('data')}>
                <table>
                  <thead><tr>{#each table.columns as c}<th scope="col">{c}</th>{/each}</tr></thead>
                  <tbody>{#each shownRows as r}<tr>{#each r as v}<td>{v}</td>{/each}</tr>{/each}</tbody>
                </table>
              </div>
              <ExplorePlot columns={table.columns} rows={table.rows} col={1} />
            </div>
            <p class="xs muted">{(table.total ?? table.rows.length) > shownRows.length ? xt('rowsShown', { n: shownRows.length, total: table.total ?? table.rows.length }) : xt('rowsAll', { total: table.total ?? table.rows.length })}</p>
          {/if}
        </section>

        <!-- 2. Reconnaître -->
        <section class="panel card" id="xp-recognise" aria-labelledby="xp-recognise-h">
          <div class="row"><h2 id="xp-recognise-h">2. {xt('step.recognise')}</h2><span class="chip {stepChip(x.steps.recognise.state)}">{xt(`state.${x.steps.recognise.state}`)}</span></div>
          <p class="hint">{xt('stepLead.recognise')}</p>
          {#if stepError('recognise')}<p class="error-text" role="alert">{stepError('recognise')}</p>{/if}
          {#if x.steps.recognise.state === 'done'}
            <h3 class="sub">{xt('kept')}</h3>
            {#if keptFindings.length}
              <ul class="plain">
                {#each keptFindings as f}
                  <li><Icon name="check" size={14} /> {kindName(f.kind)} <span class="xs muted">({f.columns.join(', ')})</span>
                    {#if f.detail?.sage?.agrees === true}<span class="chip proved">{xt('sageAgrees')}</span>
                    {:else if f.detail?.sage?.agrees === false}<span class="chip">{xt('sageDiffers', { g: f.detail.sage.ogf ?? '' })}</span>{/if}</li>
                {/each}
              </ul>
            {:else}<p class="small muted">{xt('noneFound')}</p>{/if}
            {#if recogJournal.length}
              <details class="disc"><summary class="small">{xt('discarded')} ({recogJournal.length})</summary>
                <ul class="plain small">{#each recogJournal as e}<li>{pick(e)}</li>{/each}</ul></details>
            {/if}
            <h3 class="sub">{xt('oeis')}</h3>
            {#each Object.entries(x.oeis) as [col, r] (col)}
              <p class="small">{xt(`oeis.${r.status}`)}</p>
              {#if r.matches.length}
                <ul class="oeis">
                  {#each r.matches as m (m.number)}
                    <li><a href={m.url} target="_blank" rel="noopener noreferrer">{m.number}<Icon name="external" size={12} /></a> <span>{m.name}</span>
                      <span class="xs muted">· {col}(n) · {xt('oeisAgrees', { n: m.matched })}{m.shift ? ` · ${xt('oeisShift', { k: m.shift })}` : ''}</span>
                      {#if m.formulas.length}<details><summary class="xs">{xt('oeisFormulas')}</summary><ul class="xs mono fl">{#each m.formulas as fm}<li>{fm}</li>{/each}</ul></details>{/if}</li>
                  {/each}
                </ul>
              {/if}
            {:else}<p class="small muted">{status?.oeis === 'off' ? xt('oeis.off') : xt('oeis.too_short')}</p>{/each}
            <p class="xs muted">{xt('lmfdb')}</p>
          {/if}
        </section>

        <!-- 3. Énoncer + 4. Attaquer -->
        <section class="panel card" id="xp-state" aria-labelledby="xp-state-h">
          <div class="row"><h2 id="xp-state-h">3. {xt('step.state')}</h2><span class="chip {stepChip(x.steps.state.state)}">{xt(`state.${x.steps.state.state}`)}</span>
            <h2 id="xp-attack" class="h2b">4. {xt('step.attack')}</h2><span class="chip {stepChip(x.steps.attack.state)}">{xt(`state.${x.steps.attack.state}`)}</span></div>
          <p class="hint">{xt('stepLead.state')} {xt('stepLead.attack')}</p>
          {#if stepError('state')}<p class="error-text" role="alert">{stepError('state')}</p>{/if}
          {#if x.steps.state.state === 'done' && !active.length}<p class="small muted">{xt('noCandidates')}</p>{/if}
          {#if active.length}<h3 class="sr-only">{xt('candidates')}</h3>{/if}
          <ul class="cands">
            {#each active as c (c.id)}
              <li class="cand cs-{c.status}" data-kind={c.kind}>
                <div class="row"><strong class="small">{kindName(c.kind)}</strong>
                  <span class="cstatus cs-{c.status}">{xt(`cstatus.${c.status}`)}</span>
                  {#if c.strength.kind === 'heuristic'}<span class="badge pending">{xt('heuristic')}</span>{/if}</div>
                <div class="theorem stmt"><Md src={pick(c.text)} cls="th-body" /></div>
                <p class="small strength"><span class="label">{xt('strength')} :</span> {pick(c.strength)}</p>
                {#if c.duplicate_of}<p class="small dup">{xt('duplicate', { title: c.duplicate_of.title })} <a href="/conjectures/{encodeURIComponent(c.duplicate_of.id)}">{xt('openConj')}</a></p>{/if}
                {#if c.lean}
                  <details class="lean"><summary class="small">{xt('lean')} — <span class="lean-{c.lean_ok === true ? 'ok' : c.lean_ok === false ? 'bad' : 'unk'}">{c.lean_ok === true ? xt('leanOk') : c.lean_ok === false ? xt('leanBad') : xt('leanUnknown')}</span></summary>
                    <pre class="out">{c.lean}</pre>{#if c.lean_error}<pre class="out err">{c.lean_error}</pre>{/if}</details>
                {:else}<p class="xs muted">{xt('leanNone')}</p>{/if}

                {#if c.counterexample}
                  <div class="counter" class:unconfirmed={!c.counterexample.verified} role="status">
                    <h4>{xt('counter')}</h4>
                    <p class="mono">{witness(c.counterexample.witness)}</p>
                    <p class="small">{xt('counterRecomputed')} {c.counterexample.sage ? '✓' : '—'} · {xt('counterLean')} {c.counterexample.lean ? '✓' : '—'}</p>
                    {#if !c.counterexample.verified}<p class="small">{xt('disputed')}</p>{/if}
                  </div>
                {:else if c.hunt}
                  <p class="small survived"><Icon name="check" size={14} /> {xt('survived', { n: c.hunt.cases, max: c.hunt.max })}</p>
                {/if}
                {#if c.hunting}<p class="small muted" aria-busy="true">{xt('attacking')}</p>{/if}
                {#if x.steps.attack.candidate === c.id && x.steps.attack.error && x.steps.attack.state !== 'awaiting_approval'}
                  <p class="small muted">{x.steps.attack.error === 'no_code' ? xt('attackSkipped', { why: xt('skip.no_code') }) : (errText(x.steps.attack.error) || x.steps.attack.error)}</p>
                {/if}

                <div class="row actions">
                  {#if c.status !== 'refuted'}
                    <button class="btn small" type="button" onclick={() => attack(c)} disabled={running || !!busy || !execAllowed}><Icon name="search" size={14} />{xt('attack')}</button>
                    <button class="btn small" type="button" onclick={() => prove(c)} disabled={running || !!busy}>{xt('prove')}</button>
                  {/if}
                  {#if c.conjecture_id}
                    <a class="btn small quiet" href="/conjectures/{encodeURIComponent(c.conjecture_id)}">{xt('openConj')}</a>
                  {:else}
                    <button class="btn small" type="button" onclick={() => keep(c)} disabled={!!busy}>{xt('keep')}</button>
                  {/if}
                  <button class="btn small quiet" type="button" onclick={(e) => { discardBtn = e.currentTarget as HTMLElement; discardFor = discardFor === c.id ? '' : c.id; discardWhy = ''; }} aria-expanded={discardFor === c.id} disabled={!!busy}>{xt('discard')}</button>
                </div>
                {#if discardFor === c.id}
                  <form class="discard row" use:dismiss={{ onclose: () => (discardFor = ''), trigger: discardBtn }} onsubmit={(e) => { e.preventDefault(); void discard(c); }}>
                    <label class="sr-only" for="xp-why-{c.id}">{xt('discardWhy')}</label>
                    <!-- svelte-ignore a11y_autofocus -->
                    <input id="xp-why-{c.id}" class="input" bind:value={discardWhy} placeholder={xt('discardWhy')} autofocus />
                    <button class="btn small danger" type="submit">{xt('discardOk')}</button>
                    <button class="btn small quiet" type="button" onclick={() => (discardFor = '')}>{xt('cancel')}</button>
                  </form>
                {/if}
              </li>
            {/each}
          </ul>
          {#if stepError('attack') && !x.steps.attack.candidate}<p class="error-text" role="alert">{stepError('attack')}</p>{/if}
          {#if dropped.length}
            <button class="btn small quiet" type="button" onclick={() => (showDiscarded = !showDiscarded)} aria-expanded={showDiscarded}>{xt('showDiscarded', { n: dropped.length })}</button>
            {#if showDiscarded}<ul class="plain small dropped">{#each dropped as c (c.id)}<li><Md inline src={pick(c.text)} /></li>{/each}</ul>{/if}
          {/if}
        </section>

        <!-- 5. Journal -->
        <section class="panel card" id="xp-journal" aria-labelledby="xp-journal-h">
          <div class="row"><h2 id="xp-journal-h">5. {xt('step.journal')}</h2><span class="spacer"></span>
            <button class="btn small" type="button" onclick={() => exportTo('note')} disabled={!!busy}>{xt('exportNote')}</button>
            <button class="btn small" type="button" onclick={() => exportTo('article')} disabled={!!busy || !active.length}>{xt('exportArticle')}</button></div>
          <p class="hint">{xt('stepLead.journal')}</p>
          <ol class="timeline" lang={lang}>
            {#each journal as e, i (i)}
              <li class="ev k-{e.kind}"><span class="xs muted">{fmtTime(e.t)} · {xt(`step.${e.step}`) === `step.${e.step}` ? e.step : xt(`step.${e.step}`)}</span>
                <div class="small"><Md inline src={pick(e)} /></div></li>
            {:else}<li class="muted small">{xt('journalEmpty')}</li>{/each}
          </ol>
        </section>
      {:else}
        <p class="muted" aria-busy="true">…</p>
      {/if}
    </div>
  {/snippet}
</ProjectGate>

<style>
  .xp { max-width: 980px; }
  .head h1 { margin: 0; }
  .lead { margin: var(--s-2) 0 var(--s-3); max-width: 46rem; }
  .q { min-height: 64px; }
  .sub { margin: var(--s-3) 0 var(--s-1); font-size: var(--fs-sm); }
  .examples { list-style: none; padding: 0; margin: 0 0 var(--s-2); display: flex; flex-wrap: wrap; gap: var(--s-2); }
  .ex { height: auto; min-height: 32px; white-space: normal; text-align: left; overflow-wrap: anywhere; padding-top: 4px; padding-bottom: 4px; }
  .past { list-style: none; padding: 0; margin: 0; display: grid; gap: 2px; }
  .past li { display: flex; align-items: center; gap: var(--s-2); }
  .past a { flex: 1; min-width: 0; display: grid; gap: 2px; padding: 8px; border-radius: var(--r-2); text-decoration: none; color: var(--text); }
  .past a:hover { background: var(--surface-2); }
  .pq { font-weight: 600; overflow-wrap: anywhere; }
  .xq { margin: var(--s-3) 0; overflow-wrap: anywhere; }
  .bar { margin-bottom: var(--s-3); }
  .steps { list-style: none; display: flex; flex-wrap: wrap; gap: 4px; padding: 0; margin: 0; font-size: var(--fs-xs); }
  .steps li { border: 1px dashed var(--line-strong); border-radius: 999px; }
  .steps a { display: inline-flex; align-items: center; min-height: 28px; padding: 0 10px; color: var(--text-2); text-decoration: none; border-radius: 999px; }
  .steps li.st-done { border-style: solid; border-color: var(--proved); } .steps li.st-done a { color: var(--proved); font-weight: 700; }
  .steps li.st-running { border-style: solid; border-color: var(--running); } .steps li.st-running a { color: var(--running); font-weight: 700; }
  .steps li.st-failed { border-style: solid; border-color: var(--failed); } .steps li.st-failed a { color: var(--failed); font-weight: 700; }
  .steps li.st-awaiting_approval { border-style: solid; border-color: var(--running); }
  .card h2, .panel h2 { margin: 0; font-size: var(--fs-lg, 1.125rem); }
  .card h2.h2b { margin-left: var(--s-3); }
  .card > .hint { margin: 2px 0 var(--s-2); }
  .code-head { margin-top: var(--s-2); }
  .code-in, .code-view { width: 100%; box-sizing: border-box; font: 0.8125rem/1.45 var(--font-mono); background: var(--surface-2); color: var(--text); border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2); margin: 4px 0; }
  .code-in { resize: vertical; }
  .code-in:focus-visible, .code-view:focus-visible, .tbox:focus-visible { outline: 2px solid var(--focus); outline-offset: 0; }
  .code-view { white-space: pre; overflow: auto; max-height: 260px; }
  .review { color: var(--running); font-weight: 600; margin: 2px 0; }
  .actions { margin-top: var(--s-2); }
  .badge { font-size: var(--fs-xs); font-weight: 600; padding: 1px 8px; border-radius: 999px; }
  .badge.pending { background: var(--running-soft); color: var(--running); }
  .badge.ok { background: var(--proved-soft); color: var(--proved); }
  .banner { border: 1px solid var(--line); border-left: 4px solid var(--running-fill); background: var(--surface); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); margin: var(--s-2) 0; }
  .out { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); max-height: 240px; overflow: auto; margin: 4px 0; }
  .out.err { color: var(--failed); }
  .data { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 360px); gap: var(--s-3); align-items: start; }
  @media (max-width: 760px) { .data { grid-template-columns: minmax(0, 1fr); } }
  .tbox { overflow: auto; max-height: 260px; border: 1px solid var(--line); border-radius: var(--r-2); }
  table { border-collapse: collapse; font: 0.8125rem/1.4 var(--font-mono); width: 100%; }
  th, td { padding: 2px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--line); }
  th { position: sticky; top: 0; background: var(--surface-2); color: var(--text); font-weight: 700; }
  .plain { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
  .plain li { overflow-wrap: anywhere; }
  .disc { margin-top: var(--s-2); }
  .disc summary, .lean summary { cursor: pointer; min-height: 28px; }
  @media (pointer: coarse) { .disc summary, .lean summary, .oeis summary { min-height: var(--touch); display: flex; align-items: center; } .steps a { min-height: var(--touch); } }
  .oeis { list-style: none; padding: 0; margin: 0 0 var(--s-2); display: grid; gap: var(--s-2); }
  .oeis a { font-weight: 700; display: inline-flex; align-items: center; gap: 2px; }
  .fl { padding-left: var(--s-4); overflow-wrap: anywhere; }
  .cands { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-3); }
  .cand { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-3); min-width: 0; }
  .cand.cs-refuted { border-color: var(--failed); }
  .cstatus { font-size: var(--fs-xs); font-weight: 700; padding: 1px 8px; border-radius: 999px; border: 1.5px solid var(--line-strong); color: var(--text-2); }
  .cstatus.cs-refuted { color: var(--failed); border-color: var(--failed); }
  .cstatus.cs-survived, .cstatus.cs-kept { color: var(--proved); border-color: var(--proved); }
  .cstatus.cs-disputed { color: var(--running); border-color: var(--running); }
  .stmt { margin: var(--s-2) 0; overflow-x: auto; }
  .strength { margin: 0 0 var(--s-1); }
  .dup { margin: 0 0 var(--s-1); }
  .lean-ok { color: var(--proved); font-weight: 700; } .lean-bad { color: var(--failed); font-weight: 700; } .lean-unk { color: var(--text-2); font-weight: 600; }
  .counter { border: 2px solid var(--failed); background: var(--failed-soft); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin: var(--s-2) 0; }
  .counter.unconfirmed { border-style: dashed; }
  .counter h4 { margin: 0; color: var(--failed); font-size: var(--fs-sm); }
  .counter p { margin: 2px 0; }
  .survived { color: var(--proved); margin: var(--s-1) 0; display: flex; gap: 4px; align-items: center; }
  .discard { margin-top: var(--s-2); }
  .discard .input { flex: 1; min-width: 180px; }
  .dropped { margin-top: var(--s-2); color: var(--text-2); }
  .timeline { list-style: none; padding: 0 0 0 var(--s-3); margin: var(--s-2) 0 0; border-left: 2px solid var(--line); display: grid; gap: var(--s-2); }
  .ev { position: relative; min-width: 0; overflow-wrap: anywhere; }
  .ev::before { content: ''; position: absolute; left: calc(-1 * var(--s-3) - 6px); top: 6px; width: 10px; height: 10px; border-radius: 50%; background: var(--line-strong); }
  .ev.k-kept::before, .ev.k-survived::before, .ev.k-kept_conjecture::before { background: var(--proved); }
  .ev.k-refuted::before, .ev.k-discarded::before { background: var(--failed); }
</style>
