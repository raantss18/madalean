<script lang="ts">
  // One dossier = one fluid flow: Énoncé → Traduction Lean → Preuve (each step re-openable, state always shown),
  // with the thread (follow-up requests) beside it on wide screens and below it otherwise.
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { phaseOf, modelLabel, jobModel, providerName } from '../../lib/status';
  import { prefs } from '../../lib/prefs.svelte';
  import { ApiError } from '../../lib/api/client';
  import StatusMark from '../../components/StatusMark.svelte';
  import Icon from '../../components/Icon.svelte';
  import StepStatement from './StepStatement.svelte';
  import StepLean from './StepLean.svelte';
  import StepProof from './StepProof.svelte';
  import PlanTree from './PlanTree.svelte';
  import Thread from './Thread.svelte';
  import DossierMenu from './DossierMenu.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import { stop } from './actions';

  let { params }: { params: Record<string, string> } = $props();
  const id = $derived(params['id'] ?? '');
  let loadError = $state<'' | 'not_found' | 'other'>('');

  $effect(() => {
    const did = id;
    void app.epoch;
    loadError = '';
    app.ensureDossier(did, true).catch((e) => { loadError = e instanceof ApiError && e.status === 404 ? 'not_found' : 'other'; });
  });

  const d = $derived(app.m.full[id]);
  const job = $derived(app.activeJob(id));
  const last = $derived(app.lastJob(id));
  const phase = $derived(phaseOf(d?.status ?? app.m.dossiers[id]?.status ?? 'draft', job));
  const conditional = $derived((d?.['extra'] as { conditional_proof?: { verdict?: string } } | undefined)?.conditional_proof?.verdict === 'proved_modulo' || (d?.['conditional_proof'] as { verdict?: string } | undefined)?.verdict === 'proved_modulo');
  const recheck = $derived(((d?.['extra'] as { recheck?: { state?: string } } | undefined)?.recheck ?? (d?.['recheck'] as { state?: string } | undefined))?.state ?? '');
  const LEAN_STAGES = ['understand', 'route', 'statement', 'notes'];
  const PROOF_STAGES = ['proof', 'explanation', 'informal'];

  type StepKey = 'enonce' | 'lean' | 'preuve' | 'plan';
  const steps: StepKey[] = ['enonce', 'lean', 'preuve', 'plan'];
  const stepState = $derived.by<Record<StepKey, 'todo' | 'running' | 'queued' | 'done' | 'failed' | 'conditional'>>(() => {
    const st = job?.stage ?? '';
    const queued = job && (job.state === 'queued' || job.waiting);
    const r = (k: string[]) => (job && k.includes(st) ? (queued ? 'queued' : 'running') : null);
    const hasStatement = (d?.statements.length ?? 0) > 0;
    const statementOk = hasStatement && d!.statements[d!.cur_statement]?.ok !== false;
    return {
      enonce: d?.problem || hasStatement ? 'done' : 'todo',
      lean: r(LEAN_STAGES) ?? (statementOk ? 'done' : hasStatement ? 'failed' : last?.state === 'failed' && !hasStatement ? 'failed' : 'todo'),
      preuve: r(PROOF_STAGES) ?? (d?.status === 'proved' ? 'done' : d?.status === 'failed' && hasStatement ? 'failed' : 'todo'),
      plan: conditional ? 'conditional' : d?.status === 'proved' && (d?.uses?.length ?? 0) > 0 ? 'done' : 'todo',
    };
  });
  const autoStep = $derived.by<StepKey>(() => {
    if (job && LEAN_STAGES.includes(job.stage)) return 'lean';
    if (job && PROOF_STAGES.includes(job.stage)) return 'preuve';
    if (!d) return 'lean';
    if (d.status === 'proved' || d.proofs.length) return 'preuve';
    if (d.statements.length) return d.status === 'failed' || d.status === 'proving' ? 'preuve' : 'lean';
    return d.problem ? 'lean' : 'enonce';
  });
  const step = $derived<StepKey>((steps as string[]).includes(params['step'] ?? '') ? (params['step'] as StepKey) : autoStep);
  const model = $derived(modelLabel((job && (app.liveModel[job.id] || jobModel(job))) || ''));

  function go(s: StepKey) { navigate(`/d/${encodeURIComponent(id)}/${s}`, { focus: false }); }
  function tabKey(e: KeyboardEvent, i: number) {
    let j = -1;
    const n = steps.length;
    if (e.key === 'ArrowRight') j = (i + 1) % n;
    else if (e.key === 'ArrowLeft') j = (i + n - 1) % n;
    else if (e.key === 'Home') j = 0;
    else if (e.key === 'End') j = n - 1;
    if (j >= 0) { e.preventDefault(); go(steps[j]!); queueMicrotask(() => document.getElementById(`tab-${steps[j]}`)?.focus()); }
  }
  const parent = $derived(d?.parent_id ? app.m.dossiers[d.parent_id] : undefined);
</script>

{#if loadError}
  <div class="state-msg">
    <h1>{loadError === 'not_found' ? t('dossier.notFoundTitle') : t('boot.errorTitle')}</h1>
    <p>{loadError === 'not_found' ? t('dossier.notFoundText') : t('boot.errorText')}</p>
    <a class="btn primary" href="/">{t('notfound.home')}</a>
  </div>
{:else if !d}
  <div class="loading" aria-busy="true"><span class="sr-only">{t('common.loading')}</span><div class="skel"></div></div>
{:else}
  <article class="dossier" class:research={prefs.mode === 'research'}>
    <header class="dh">
      {#if parent}<p class="crumb small"><a href="/d/{encodeURIComponent(parent.id)}">{parent.title}</a> › {t('dossier.lemma')}</p>{/if}
      <div class="row title-row">
        <StatusMark {phase} size={18} />
        <h1>{d.title || d.theorem}</h1>
      </div>
      <div class="row meta small">
        <span class="phase-txt">{tk(`phase.${phase}`, phase)}{#if job}&nbsp;— {tk(`stage.${job.stage}`, t('stage.starting'))}{#if job.waiting} · <span class="wait">{tk(`waiting.${job.waiting}`, '')}</span>{/if}{/if}</span>
        {#if model.name}<span class="chip {model.local ? 'local' : 'online'}" title={providerName(model.provider)}><Icon name={model.local ? 'cpu' : 'cloud'} size={12} />{model.name}</span>{/if}
        {#if conditional}<span class="chip running cond">{t('plan.conditional')}</span>{/if}
        {#if recheck === 'pending' || recheck === 'regressed'}<span class="chip {recheck === 'regressed' ? 'failed' : 'running'}">{tk(`recheck.${recheck}`, recheck)}</span>{/if}
        <span class="mono xs muted theorem-name" title={t('dossier.theoremName')}>{d.theorem}</span>
        <span class="spacer"></span>
        {#if job}<button class="btn small danger" onclick={() => stop(id)}><Icon name="stop" size={14} />{t('common.stop')}</button>{/if}
        <HelpLink page={step === 'plan' ? 'proof-plans' : step === 'lean' ? 'reading-lean' : 'workflow'} />
        <DossierMenu dossier={d} busy={Boolean(job)} />
      </div>
    </header>

    <div class="tabs" role="tablist" aria-label={t('dossier.steps')}>
      {#each steps as s, i (s)}
        {@const st = stepState[s]}
        <button id="tab-{s}" role="tab" class="tab {st}" aria-selected={step === s} aria-controls="panel-{s}" tabindex={step === s ? 0 : -1}
          onclick={() => go(s)} onkeydown={(e) => tabKey(e, i)}>
          <span class="num" aria-hidden="true">{i + 1}</span>
          <span class="tl">{t(`step.${s}`)}</span>
          <span class="ts xs">{t(`stepstate.${st}`)}</span>
        </button>
      {/each}
    </div>

    <div class="layout" class:solo={step === 'plan'}>
      <div id="panel-{step}" class="panel-step" role="tabpanel" aria-labelledby="tab-{step}">
        {#if step === 'enonce'}<StepStatement dossier={d} {job} />
        {:else if step === 'lean'}<StepLean dossier={d} {job} />
        {:else if step === 'preuve'}<StepProof dossier={d} {job} />
        {:else}<PlanTree dossier={d} />{/if}
      </div>
      <aside class="side" aria-label={t('thread.title')}>
        <Thread dossier={d} {job} />
      </aside>
    </div>
  </article>
{/if}

<style>
  .dossier { max-width: 1500px; }
  .crumb { margin: 0 0 4px; color: var(--text-2); }
  .title-row { flex-wrap: nowrap; align-items: baseline; gap: 10px; }
  .title-row h1 { margin: 0; overflow-wrap: anywhere; }
  .meta { margin: 6px 0 var(--s-4); color: var(--text-2); }
  .wait { color: var(--running); font-weight: 600; }
  .theorem-name { max-width: 40ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip :global(.ico) { margin-right: 2px; }
  .tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; border-bottom: 1px solid var(--line); margin-bottom: var(--s-4); position: sticky; top: var(--topbar-h); z-index: 50; background: var(--bg); }
  .tab { display: grid; grid-template-columns: auto 1fr; grid-template-rows: auto auto; column-gap: 10px; align-items: center; text-align: left; min-height: 56px; padding: 8px 12px; border: 0; border-bottom: 3px solid transparent; background: none; color: var(--text-2); cursor: pointer; font: inherit; }
  .tab:hover { background: var(--surface-2); }
  .tab[aria-selected='true'] { color: var(--text); border-bottom-color: var(--laterite-mark); }
  .num { grid-row: span 2; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; border: 1.5px solid var(--line-strong); font-weight: 700; font-size: var(--fs-sm); }
  .tab.done .num { background: var(--proved); border-color: var(--proved); color: var(--surface); }
  .tab.running .num { border-color: var(--running-fill); background: var(--running-soft); color: var(--running); }
  .tab.queued .num { border-style: dashed; }
  .tab.failed .num { border-color: var(--failed); color: var(--failed); }
  .tab.conditional .num { border: 2px dashed var(--running-fill); color: var(--running); }
  .tab.conditional .ts { color: var(--running); font-weight: 600; }
  .cond { border: 1.5px dashed var(--running); }
  .tl { font-weight: 700; font-family: var(--font-serif); font-size: 1.0625rem; }
  .ts { color: var(--text-3); }
  .tab.running .ts { color: var(--running); font-weight: 600; }
  .tab.failed .ts { color: var(--failed); font-weight: 600; }
  .tab.done .ts { color: var(--proved); }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) var(--inspector-w); gap: var(--s-5); align-items: start; }
  .side { position: sticky; top: calc(var(--topbar-h) + 72px); max-height: calc(100dvh - var(--topbar-h) - 88px); overflow: auto; }
  @media (max-width: 1279px) { .layout { grid-template-columns: minmax(0, 1fr); } .side { position: static; max-height: none; } }
  /* the plan's mind map needs the width: the thread goes below it */
  .layout.solo { grid-template-columns: minmax(0, 1fr); }
  .layout.solo .side { position: static; max-height: none; }
  @media (max-width: 767px) {
    .tab { grid-template-columns: 1fr; justify-items: center; text-align: center; padding: 6px 4px; min-height: 60px; }
    .num { grid-row: auto; }
    .tl { font-size: var(--fs-sm); }
    .ts { display: none; }
    .theorem-name { display: none; }
  }
  .state-msg { max-width: 36rem; }
  .skel { height: 32px; width: 40%; background: var(--surface-2); border-radius: var(--r-2); }
</style>
