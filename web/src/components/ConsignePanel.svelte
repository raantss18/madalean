<script lang="ts">
  import EnterHint from './EnterHint.svelte';
  import { enterSubmit } from '../lib/ui/enter';
  // « Consigne de recherche »: a source + an instruction in your words → Madalean plans bounded steps with the
  // existing tools (blueprint, Lean, Calcul, conjectures, literature) and PROPOSES changes; you accept each one in
  // Article → Suggestions. The plan is shown before anything runs; every step goes to the research journal (a note).
  import { research, type SourceSummary } from '../lib/api/research';
  import { consigne, type ConsigneRun } from '../lib/api/consigne';
  import { app } from '../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import Icon from './Icon.svelte';

  let { pid }: { pid: string } = $props();
  let sources = $state<SourceSummary[]>([]);
  let sourceId = $state('');
  let instruction = $state('');
  let limits = $state({ max_steps: 12, max_minutes: 30, max_cost_usd: 0.5 });
  let preview = $state<ConsigneRun | null>(null);
  let runs = $state<ConsigneRun[]>([]);
  let busy = $state('');
  let err = $state('');

  async function load() {
    if (!pid) return;
    research.sources(pid).then((r) => { sources = r.sources; if (!sourceId && sources.length) sourceId = sources[0]!.id; }).catch(() => {});
    consigne.runs(pid).then((r) => (runs = r.runs)).catch(() => {});
  }
  $effect(() => { void pid; void load(); });
  $effect(() => app.on('research.run', (ev) => {
    const e = ev as unknown as { project_id: string; run: ConsigneRun };
    if (e.project_id !== pid) return;
    const i = runs.findIndex((r) => r.id === e.run.id);
    runs = i >= 0 ? runs.map((r, j) => (j === i ? e.run : r)) : [e.run, ...runs];
  }));

  const payload = () => ({ source: { id: sourceId }, instruction: instruction.trim(), limits });
  async function plan() {
    busy = 'plan'; err = '';
    try { preview = (await consigne.plan(pid, payload())).run; } catch (e) { err = errorText(e); preview = null; } finally { busy = ''; }
  }
  async function start() {
    busy = 'start'; err = '';
    try { const r = (await consigne.start(pid, payload())).run; runs = [r, ...runs.filter((x) => x.id !== r.id)]; preview = null; }
    catch (e) { err = errorText(e); } finally { busy = ''; }
  }
  async function act(r: ConsigneRun, what: 'cancel' | 'resume') {
    // a run stopped by a limit gets a little more of it (time +20 min, cost +0.5 $, steps +6) when resumed
    const more = r.stopped_by === 'time' ? { max_minutes: r.limits.max_minutes + 20 } : r.stopped_by === 'cost' ? { max_cost_usd: r.limits.max_cost_usd + 0.5 } : r.stopped_by === 'steps' ? { max_steps: r.limits.max_steps + 6 } : undefined;
    try { const n = (what === 'cancel' ? await consigne.cancel(pid, r.id) : await consigne.resume(pid, r.id, more)).run; runs = runs.map((x) => (x.id === n.id ? n : x)); } catch (e) { err = errorText(e); }
  }
  const stepMark = (s: string) => (s === 'done' ? '✓' : s === 'failed' ? '✗' : s === 'running' ? '…' : '·');
  const targets = (ts: { kind: string; number: string }[]) => ts.map((x) => `${tk(`consigne.kind.${x.kind}`, x.kind)} ${x.number}`).join(', ');
</script>

<section class="panel consigne" aria-labelledby="cs-h">
  <h2 id="cs-h">{t('consigne.title')}</h2>
  <p class="hint">{t('consigne.lead')}</p>
  {#if !sources.length}
    <p class="small muted">{t('consigne.noSource')} <a href="/sources">{t('nav.sources')}</a></p>
  {:else}
    <div class="field"><label for="cs-src">{t('consigne.source')}</label>
      <select id="cs-src" class="input" bind:value={sourceId}>{#each sources as s (s.id)}<option value={s.id}>@{s.key} — {s.title}</option>{/each}</select></div>
    <div class="field"><label for="cs-txt">{t('consigne.instruction')}</label>
      <textarea id="cs-txt" class="input" rows="3" bind:value={instruction} use:enterSubmit={() => { if (!busy && instruction.trim() && sourceId) void plan(); }} placeholder={t('consigne.placeholder')} aria-describedby="cs-hint cs-e"></textarea>
      <EnterHint id="cs-e" />
      <p class="hint" id="cs-hint">{t('consigne.understands')}</p></div>
    <details class="lim"><summary class="small">{t('consigne.limits')}</summary>
      <div class="row">
        <div class="field"><label for="cs-st">{t('consigne.maxSteps')}</label><input id="cs-st" class="input" type="number" min="1" max="40" bind:value={limits.max_steps} /></div>
        <div class="field"><label for="cs-mn">{t('consigne.maxMinutes')}</label><input id="cs-mn" class="input" type="number" min="1" max="240" bind:value={limits.max_minutes} /></div>
        <div class="field"><label for="cs-co">{t('consigne.maxCost')}</label><input id="cs-co" class="input" type="number" min="0" max="20" step="0.1" bind:value={limits.max_cost_usd} /></div>
      </div>
      <p class="hint">{t('consigne.limitsHint')}</p>
    </details>
    <div class="row">
      <button class="btn" onclick={plan} disabled={!!busy || !instruction.trim() || !sourceId}>{busy === 'plan' ? t('consigne.planning') : t('consigne.seePlan')}</button>
      {#if preview}<button class="btn primary" onclick={start} disabled={!!busy}>{busy === 'start' ? t('consigne.starting') : t('consigne.start')}</button>{/if}
    </div>
    {#if preview}
      <div class="planbox" aria-live="polite">
        <h3>{t('consigne.planTitle')}</h3>
        <ol class="small">{#each preview.steps as s (s.id)}<li>{tk(`consigne.step.${s.kind}`, s.kind)}{#if s.targets.length} — {targets(s.targets)}{/if}</li>{/each}</ol>
        <p class="hint">{t('consigne.planHint')}</p>
      </div>
    {/if}
  {/if}
  {#if err}<p class="error-text small" role="alert">{err}</p>{/if}

  {#if runs.length}
    <h3>{t('consigne.runs')}</h3>
    <ul class="runs">
      {#each runs.slice(0, 6) as r (r.id)}
        <li>
          <div class="row">
            <span class="chip {r.status === 'done' ? 'proved' : r.status === 'running' ? 'running' : r.status === 'failed' ? 'failed' : ''}">{tk(`consigne.status.${r.status}`, r.status)}</span>
            <span class="small instr">« {r.instruction.slice(0, 140)} »</span>
            <span class="spacer"></span>
            {#if r.status === 'running'}<button class="btn small" onclick={() => act(r, 'cancel')}>{t('consigne.stop')}</button>{/if}
            {#if ['paused', 'stopped', 'cancelled', 'failed'].includes(r.status)}<button class="btn small" onclick={() => act(r, 'resume')}>{t('consigne.resume')}</button>{/if}
          </div>
          <ol class="steps xs">{#each r.steps as s (s.id)}<li class={s.status}><span aria-hidden="true">{stepMark(s.status)}</span> {tk(`consigne.step.${s.kind}`, s.kind)}<span class="sr-only"> — {tk(`consigne.sstatus.${s.status}`, s.status)}</span>{#if s.result?.['error']} <span class="muted">({tk(`consigne.err.${String(s.result['error'])}`, String(s.result['error']))})</span>{/if}</li>{/each}</ol>
          <p class="xs muted">{t('consigne.spent', { min: Math.round(r.spent.seconds / 60), cost: r.spent.cost_usd.toFixed(2), calls: r.spent.model_calls })}
            · {fmtTime(r.created)}{#if r.stopped_by} · {t('consigne.stoppedBy', { why: tk(`consigne.why.${r.stopped_by}`, r.stopped_by) })}{/if}</p>
          <p class="xs links">
            {#if r.suggestions.length}<a href="/article#suggestions"><Icon name="edit" size={12} />{t('consigne.toReview', { n: r.suggestions.length })}</a>{/if}
            {#if r.journal_note}<a href="/notes/{encodeURIComponent(r.journal_note)}"><Icon name="book" size={12} />{t('consigne.journal')}</a>{/if}
            {#if r.cells.length}<a href="/calcul"><Icon name="terminal" size={12} />{t('consigne.cells', { n: r.cells.length })}</a>{/if}
          </p>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .consigne textarea { width: 100%; resize: vertical; }
  .lim .row { gap: var(--s-3); flex-wrap: wrap; }
  .lim .field { max-width: 11rem; }
  .planbox { border-left: 3px solid var(--accent); padding: var(--s-2) var(--s-3); margin-top: var(--s-2); background: var(--surface-2, var(--surface)); }
  .planbox h3 { margin: 0 0 4px; font-size: var(--fs-sm); }
  .runs { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-3); }
  .runs > li { border-top: 1px solid var(--line); padding-top: var(--s-2); }
  .instr { overflow-wrap: anywhere; }
  .steps { list-style: none; padding: 0; margin: 4px 0; display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .steps .done { color: var(--proved); }
  .steps .failed { color: var(--failed); }
  .steps .running { color: var(--running); font-weight: 600; }
  .links { display: flex; gap: var(--s-3); flex-wrap: wrap; }
  .links a { display: inline-flex; gap: 4px; align-items: center; }
</style>
