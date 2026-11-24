<script lang="ts">
  // D66: where the dossier stands. The stepper (Comprendre → Traduire → Prouver → Vérifier) and ONE « En ce moment »
  // line, always visible: what happens, for how long, with which model, what runs beside, and « Arrêter »; when it is
  // the user's turn it says so and jumps there. The elapsed time is not announced to screen readers.
  import type { Dossier, Job } from '../../lib/api/types';
  import { STEPS, deriveSteps, isConditional, pendingGate, recheckState, troubleOf, failureSummary, type Now } from '../../lib/flow';
  import { t, tk, fmtDuration } from '../../lib/i18n/index.svelte';
  import { app } from '../../lib/store/app.svelte';
  import { clock } from '../../lib/ui/clock.svelte';
  import { jobModel, modelLabel, providerName } from '../../lib/status';
  import Icon from '../../components/Icon.svelte';
  import { activityText } from './flowtext';
  import { stop } from './actions';

  let { dossier: d, job, last, now, waitingChildren = 0, jump }: {
    dossier: Dossier; job: Job | undefined; last: Job | undefined; now: Now | null; waitingChildren?: number; jump: (id: string) => void;
  } = $props();
  const steps = $derived(deriveSteps(d, now, last));
  const ICON = { todo: 'x', active: 'activity', waiting: 'info', done: 'check', failed: 'warn' } as const;
  const gate = $derived(pendingGate(d));
  const trouble = $derived(now ? '' : troubleOf(d, last));
  const model = $derived(modelLabel(now?.model || (job ? app.liveModel[job.id] || jobModel(job) : '')));
  const fs = $derived(trouble === 'failed' ? failureSummary(d, last) : null);

  const text = $derived.by(() => {
    if (now?.waiting === 'user') return gate ? t(gate.kind === 'meaning' ? 'flow.waitMeaning' : 'flow.waitStatement') : t('flow.waitUser');
    if (now) return activityText(now);
    if (trouble === 'failed') return t('flow.idleFailed', { cause: tk(`joberr.${fs?.error ?? ''}`, '') || fs?.cause.split('\n')[0] || t('flow.idleFailedShort') });
    if (trouble === 'stopped') return t('flow.idleStopped');
    if (d.status === 'proved') return recheckState(d) === 'regressed' ? t('flow.idleRegressed') : t('flow.idleProved');
    if (isConditional(d)) return t('flow.idleConditional');
    const st = d.statements[d.cur_statement];
    return st ? t(st.ok ? 'flow.idleReady' : 'flow.idleRejected') : t('flow.idleDraft');
  });
  const mood = $derived(now ? (now.waiting === 'user' ? 'user' : 'run') : trouble || (d.status === 'proved' ? 'proved' : 'idle'));
  const elapsed = $derived(now && now.started && now.waiting !== 'user' ? fmtDuration(clock.now - now.started) : '');
</script>

<section class="flow {mood}" aria-label={t('flow.steps')}>
  <ol class="steps">
    {#each STEPS as s (s)}
      <li class={steps[s]} aria-current={steps[s] === 'active' || steps[s] === 'waiting' ? 'step' : undefined}>
        <span class="dot" aria-hidden="true">{#if steps[s] === 'todo'}<span class="o"></span>{:else}<Icon name={ICON[steps[s]]} size={14} />{/if}</span>
        <span class="nm">{t(`flow.step.${s}`)}</span>
        <span class="st xs">{t(`flow.state.${steps[s]}`)}</span>
      </li>
    {/each}
  </ol>
  <div class="nowline">
    <p class="txt"><strong class="lead">{t('flow.now')}{' : '}</strong><span class="phase-txt">{text}</span>
      {#if now && now.waiting !== 'user'}
        {#if now.attempt > 0}<span class="bit">· {t('flow.attemptOf', { n: now.attempt })}</span>{/if}
        {#if now.waiting}<span class="bit wait">· {now.waiting === 'quota' ? t('flow.waitQuota') : job?.waiting ? tk(`waiting.${job.waiting}`, t('flow.waitSlot')) : t('flow.waitSlot')}</span>{/if}
        {#if elapsed}<span class="bit">· {t('flow.since', { d: elapsed })}</span>{/if}
        {#if now.side.length}<span class="bit">· {t('flow.also', { list: now.side.map((x) => activityText(x).toLowerCase()).join(', ') })}</span>{/if}
      {/if}
      {#if model.name && now && now.waiting !== 'user'}<span class="chip {model.local ? 'local' : 'online'}" title={providerName(model.provider)}><Icon name={model.local ? 'cpu' : 'cloud'} size={12} />{model.name}</span>{/if}
    </p>
    <div class="acts">
      {#if now?.waiting === 'user' && gate}<button class="btn small primary" onclick={() => jump('gate')}><Icon name="chevronDown" size={14} />{t('flow.answer')}</button>
      {:else if trouble}<button class="btn small" onclick={() => jump('next')}><Icon name="info" size={14} />{t('flow.why')}</button>{/if}
      {#if !gate && waitingChildren}<button class="btn small primary" onclick={() => jump('batch')}>{t('flow.waitChildren', { n: waitingChildren })}</button>{/if}
      {#if job}<button class="btn small danger" onclick={() => stop(d.id)}><Icon name="stop" size={14} />{t('common.stop')}</button>{/if}
    </div>
  </div>
  <p class="sr-only" role="status" aria-live="polite">{t('flow.now')}{' : '}{text}{#if now && now.attempt > 0}, {t('flow.attemptOf', { n: now.attempt })}{/if}</p>
</section>

<style>
  .flow { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); overflow: hidden; box-shadow: 0 4px 10px -8px rgba(10, 20, 40, .45); }
  .steps { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .steps li { position: relative; display: grid; grid-template-columns: auto 1fr; column-gap: 8px; align-items: center; padding: 8px 14px; color: var(--text-2); border-bottom: 3px solid var(--line); }
  .steps li + li { border-left: 1px solid var(--line); }
  .dot { grid-row: span 2; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; border: 1.5px solid var(--line-strong); }
  .o { width: 6px; height: 6px; border-radius: 50%; background: var(--line-strong); }
  .nm { font-family: var(--font-serif); font-weight: 700; line-height: 1.2; overflow-wrap: anywhere; }
  .st { color: var(--text-3); line-height: 1.2; }
  li.done .dot { background: var(--proved); border-color: var(--proved); color: var(--surface); }
  li.done .st { color: var(--proved); }
  li.done { border-bottom-color: var(--proved); }
  li.active { background: var(--running-soft); border-bottom-color: var(--running-fill); color: var(--text); }
  li.active .dot { border: 2px solid var(--running); color: var(--running); background: var(--surface); }
  li.active .st, li.waiting .st { color: var(--running); font-weight: 700; }
  li.waiting { background: var(--running-soft); border-bottom: 3px dashed var(--running); color: var(--text); }
  li.waiting .dot { border: 2px dashed var(--running); color: var(--running); background: var(--surface); }
  li.failed { border-bottom-color: var(--failed); }
  li.failed .dot { border-color: var(--failed); color: var(--failed); border-width: 2px; }
  li.failed .st { color: var(--failed); font-weight: 700; }
  .nowline { display: flex; align-items: center; gap: var(--s-3); padding: 6px 14px; min-height: 48px; }
  .txt { margin: 0; flex: 1; min-width: 0; line-height: 1.45; }
  .flow.user .nowline { background: var(--running-soft); }
  .flow.failed .phase-txt { color: var(--failed); font-weight: 600; }
  .flow.proved .phase-txt { color: var(--proved); font-weight: 600; }
  .flow.user .phase-txt, .wait { color: var(--running); font-weight: 600; }
  .bit { color: var(--text-2); font-variant-numeric: tabular-nums; }
  .chip { vertical-align: middle; margin-left: 4px; max-width: 24ch; overflow: hidden; text-overflow: ellipsis; }
  .acts { display: flex; gap: var(--s-2); flex-wrap: wrap; justify-content: flex-end; }
  @media (max-width: 767px) {
    .steps li { grid-template-columns: 1fr; justify-items: center; text-align: center; padding: 5px 2px; }
    .dot { grid-row: auto; width: 22px; height: 22px; }
    .nm { font-size: 0.8125rem; }
    .steps .st { font-size: 0.6875rem; }
    .nowline { padding: 4px 10px; gap: var(--s-2); font-size: var(--fs-sm); }
    .lead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .flow:not(.user) .phase-txt { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  }
</style>
