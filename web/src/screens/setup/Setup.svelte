<script lang="ts">
  // « Premiers pas » (S-AQ, DECISIONS D49): the first-run assistant, full screen, on the host only. One step per
  // address (/premiers-pas/<step>), every step skippable, progress saved on the server (GET/PATCH /api/setup/wizard)
  // so it resumes where the user stopped. Settings are saved as soon as they change (D43), keys only by their own
  // « Enregistrer la clé » (checked and tested, never autosaved). « Plus tard » = Settings.wizard_done; the Home card
  // offers it again until « Terminer ».
  import type { Component } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { i18n, t, tk } from '../../lib/i18n/index.svelte';
  import { setupApi, type SetupStatus } from '../../lib/setup/api';
  import { setup, saveWizard } from '../../lib/setup/state.svelte';
  import { HELP, STEPS, isStep, next, prev, progress, indexOf, resumeStep, visitedAfterMove, type StepId } from '../../lib/setup/wizard';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import Wordmark from '../../components/Wordmark.svelte';

  let { params }: { params: Record<string, string> } = $props();

  const loaders: Record<StepId, () => Promise<{ default: Component<{ status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> }> }>> = {
    welcome: () => import('./StepWelcome.svelte'),
    tools: () => import('./StepTools.svelte'),
    local: () => import('./StepLocal.svelte'),
    keys: () => import('./StepKeys.svelte'),
    hf: () => import('./StepHf.svelte'),
    claude: () => import('./StepClaude.svelte'),
    modes: () => import('./StepModes.svelte'),
    auto: () => import('./StepAuto.svelte'),
    pair: () => import('./StepPair.svelte'),
    done: () => import('./StepDone.svelte'),
  };

  const step = $derived<StepId>(isStep(params['step']) ? params['step'] : resumeStep(undefined, setup.info));
  let status = $state<SetupStatus | null>(null);
  let err = $state('');
  let leaving = $state(false);

  async function reload(refresh = false) {
    try { status = await setupApi.status(refresh); setup.info = status.wizard; err = ''; } catch (e) { err = errorText(e); }
  }
  $effect(() => { if (app.m.local) void reload(); });
  // Opened without a step (logo menu, Réglages, first start): resume where the user stopped.
  $effect(() => {
    if (!isStep(params['step']) && setup.info) navigate(`/premiers-pas/${resumeStep(undefined, setup.info)}`, { replace: true, focus: false });
  });
  // Reached by the browser's back / forward or a link: remember this step too.
  $effect(() => {
    const s = params['step'];
    if (isStep(s) && setup.info && !setup.info.completed && setup.info.step !== s) void saveWizard({ step: s });
  });
  // Phones and tablets: the stepper is one scrolling row; keep the current step in view.
  $effect(() => {
    void step;
    queueMicrotask(() => document.querySelector('.steps [aria-current="step"]')?.scrollIntoView({ block: 'nearest', inline: 'center' }));
  });

  function go(to: StepId | null) {
    if (!to) return;
    const visited = visitedAfterMove(setup.info?.visited ?? [], step);
    if (setup.info) setup.info = { ...setup.info, step: to, visited };
    void saveWizard({ step: to, visited });
    navigate(`/premiers-pas/${to}`);
  }
  async function later() {
    leaving = true;
    await saveWizard({ done: true, step });
    navigate('/');
  }
  async function finish() {
    leaving = true;
    await saveWizard({ completed: true, step: 'done', visited: [...STEPS] });
    navigate('/');
  }
  const lang = $derived(i18n.lang === 'en' ? 'en' : 'fr');
  const help = $derived(HELP[step]);
  const visited = $derived(new Set(setup.info?.visited ?? []));
</script>

{#if !app.m.local}
  <main id="main" class="wiz-remote">
    <h1>{t('setup.title')}</h1>
    <p>{t('setup.hostOnly')}</p>
    <a class="btn primary" href="/">{t('notfound.home')}</a>
  </main>
{:else}
  <div class="wiz">
    <header class="wiz-top">
      <span class="brand"><Wordmark height={26} alt="Madalean" /></span>
      <span class="where small"><strong>{t('setup.title')}</strong> · {t('setup.stepOf', { i: indexOf(step) + 1, n: STEPS.length })}</span>
      <span class="spacer"></span>
      <button class="btn quiet" onclick={later} disabled={leaving} title={t('setup.laterHint')}>{t('setup.later')}</button>
    </header>
    <div class="bar" role="progressbar" aria-label={t('setup.progress')} aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress(step)}><span style="width: {progress(step)}%"></span></div>

    <div class="wiz-body">
      <nav class="steps" aria-label={t('setup.steps')}>
        <ol>
          {#each STEPS as s, i (s)}
            <li>
              <a href="/premiers-pas/{s}" aria-current={s === step ? 'step' : undefined} class:seen={visited.has(s) && s !== step}
                onclick={(e) => { e.preventDefault(); go(s); }}>
                <span class="num" aria-hidden="true">{#if visited.has(s) && s !== step}<Icon name="check" size={14} />{:else}{i + 1}{/if}</span>
                <span class="lbl">{tk(`setup.step.${s}`, s)}</span>
                {#if visited.has(s) && s !== step}<span class="sr-only">({t('setup.seen')})</span>{/if}
              </a>
            </li>
          {/each}
        </ol>
      </nav>

      <main id="main" class="wiz-main">
        <div class="head">
          <h1 data-route-focus>{tk(`setup.step.${step}.title`, step)}</h1>
          <HelpLink page={help.page} anchor={help.anchor ? help.anchor[lang] : ''} />
        </div>
        <p class="lead">{tk(`setup.step.${step}.lead`, '')}</p>
        {#if err}<p class="error-text" role="alert">{err} <button class="btn small" onclick={() => reload()}>{t('setup.retry')}</button></p>{/if}
        {#key step}
          {#await loaders[step]() then m}
            <m.default {status} {reload} />
          {/await}
        {/key}

        <div class="wiz-nav">
          {#if prev(step)}<button class="btn" onclick={() => go(prev(step))}><Icon name="chevronLeft" size={16} />{t('setup.prev')}</button>{/if}
          <span class="spacer"></span>
          {#if step === 'done'}
            <button class="btn primary" onclick={finish} disabled={leaving}><Icon name="check" size={16} />{t('setup.finish')}</button>
          {:else}
            {#if step !== 'welcome'}<button class="btn quiet" onclick={() => go(next(step))}>{t('setup.skip')}</button>{/if}
            <button class="btn primary" onclick={() => go(next(step))}>{step === 'welcome' ? t('setup.start') : t('setup.next')}<Icon name="chevronRight" size={16} /></button>
          {/if}
        </div>
        <p class="xs muted later-note">{t('setup.laterNote')}</p>
      </main>
    </div>
  </div>
{/if}

<style>
  .wiz { min-height: 100dvh; display: flex; flex-direction: column; background: var(--bg); }
  .wiz-top { position: sticky; top: 0; z-index: 50; display: flex; align-items: center; gap: var(--s-3); min-height: var(--topbar-h); padding: 0 max(var(--s-4), env(safe-area-inset-right)) 0 max(var(--s-4), env(safe-area-inset-left)); background: var(--surface); border-bottom: 1px solid var(--line); }
  .brand { display: inline-flex; flex: none; }
  .where { color: var(--text-2); }
  .spacer { flex: 1; }
  .bar { height: 3px; background: var(--surface-3); }
  .bar span { display: block; height: 100%; background: var(--laterite-mark); transition: width 200ms var(--ease); }   /* brand: one orange touch */
  .wiz-body { flex: 1; display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: var(--s-6); width: 100%; max-width: 1180px; margin: 0 auto; padding: var(--s-5) max(var(--s-5), env(safe-area-inset-right)) var(--s-7) max(var(--s-5), env(safe-area-inset-left)); }
  .steps { min-width: 0; }
  .steps ol { list-style: none; margin: 0; padding: 0; position: sticky; top: calc(var(--topbar-h) + var(--s-4)); }
  .steps a { display: flex; align-items: center; gap: 10px; min-height: 40px; padding: 0 var(--s-2); border-radius: var(--r-2); color: var(--text-2); text-decoration: none; font-weight: 600; font-size: var(--fs-sm); }
  .steps a:hover { background: var(--surface-2); color: var(--text); }
  .steps a[aria-current='step'] { background: var(--accent-soft); color: var(--accent); }
  .num { flex: none; display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--line-strong); font-size: var(--fs-xs); }
  .steps a[aria-current='step'] .num { background: var(--accent); border-color: var(--accent); color: var(--surface); }
  .steps a.seen .num { border-color: var(--proved); color: var(--proved); }
  .wiz-main { min-width: 0; max-width: 820px; }
  .head { display: flex; align-items: center; gap: var(--s-3); flex-wrap: wrap; }
  .head h1 { margin: 0; font-size: var(--fs-2xl); }
  .head h1:focus { outline: none; }
  .lead { color: var(--text-2); max-width: var(--measure); font-size: var(--fs-md); }
  .wiz-nav { display: flex; align-items: center; gap: var(--s-2); flex-wrap: wrap; margin-top: var(--s-6); padding-top: var(--s-4); border-top: 1px solid var(--line); }
  .later-note { margin-top: var(--s-2); }
  .wiz-remote { max-width: 36rem; margin: 0 auto; padding: var(--s-7) var(--s-4); }

  /* Shared by the steps (one place, every step looks the same). */
  .wiz-main :global(fieldset.panel) { margin: 0; min-width: 0; }
  .wiz-main :global(fieldset.panel > legend) { font-weight: 700; font-size: var(--fs-lg); padding: 0 4px; }
  .wiz-main :global(.choices) { display: grid; gap: var(--s-2); grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
  .wiz-main :global(.choice) { display: flex; gap: var(--s-2); align-items: flex-start; padding: var(--s-3); border: 1px solid var(--line); border-radius: var(--r-2); background: var(--surface); cursor: pointer; }
  .wiz-main :global(.choice.sel) { border-color: var(--accent); background: var(--accent-soft); }
  .wiz-main :global(.choice.off) { cursor: not-allowed; background: var(--surface-2); }
  .wiz-main :global(.choice input) { margin-top: 4px; width: 18px; height: 18px; flex: none; }
  .wiz-main :global(.choice > span) { display: grid; gap: 2px; min-width: 0; }
  .wiz-main :global(.rec) { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border-radius: 999px; font-size: var(--fs-xs); font-weight: 700; color: var(--proved); background: var(--proved-soft); width: fit-content; }
  .wiz-main :global(.why) { margin: var(--s-2) 0 0; padding: var(--s-2) var(--s-3); border-left: 3px solid var(--laterite-mark); background: var(--surface); border-radius: 0 var(--r-2) var(--r-2) 0; font-size: var(--fs-sm); color: var(--text-2); }
  .wiz-main :global(.st.ok) { color: var(--proved); }
  .wiz-main :global(.st.warn) { color: var(--running); }
  .wiz-main :global(.st.error) { color: var(--failed); }
  .wiz-main :global(.opt) { margin-bottom: var(--s-3); }
  .wiz-main :global(.opt .hint) { margin-left: 52px; }
  .wiz-main :global(.meter) { height: 8px; background: var(--surface-3); border-radius: 999px; overflow: hidden; max-width: 28rem; margin: var(--s-2) 0; }
  .wiz-main :global(.meter span) { display: block; height: 100%; background: var(--accent); }
  .wiz-main :global(section.panel h2) { font-size: var(--fs-lg); margin: 0 0 var(--s-2); }
  .wiz-main :global(code.cmd) { display: inline-block; padding: 2px 6px; background: var(--surface-2); border-radius: var(--r-1); overflow-wrap: anywhere; }

  @media (max-width: 1023px) {
    .wiz-body { grid-template-columns: minmax(0, 1fr); gap: var(--s-4); padding-top: var(--s-3); }
    .steps ol { position: static; display: flex; gap: 4px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin; }
    .steps a { white-space: nowrap; position: relative; }   /* keeps the hidden labels inside the scrolling row */
    .steps a:not([aria-current='step']) .lbl { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    .steps a { min-width: var(--touch); min-height: var(--touch); justify-content: center; }
  }
  @media (max-width: 767px) {
    .where { display: none; }
    .wiz-body { padding: var(--s-3) max(var(--s-3), env(safe-area-inset-right)) calc(var(--s-6) + env(safe-area-inset-bottom)) max(var(--s-3), env(safe-area-inset-left)); }
    .head h1 { font-size: var(--fs-xl); }
    .wiz-nav .btn { min-height: 44px; }
  }
  @media (pointer: coarse) { .steps a { min-height: 44px; } }
  @media (prefers-reduced-motion: reduce) { .bar span { transition: none; } }
</style>
