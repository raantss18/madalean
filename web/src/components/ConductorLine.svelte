<script lang="ts">
  // S-AI (D41): who directs this request and what it has cost so far (« Dirigé par Claude Sonnet · 0,12 $ »), the
  // plan as readable steps with the model chosen for each (expandable), and the cap question when the request's
  // budget is reached (« Continuer avec Claude (+0,50 $) ? »). The conductor's corrections appear in the thread.
  import type { Job, Conductor } from '../lib/api/types';
  import { api } from '../lib/api/client';
  import { t, tk, i18n } from '../lib/i18n/index.svelte';
  import { modelLabel } from '../lib/status';
  import { toast } from '../lib/ui/toasts.svelte';
  import Dialog from './Dialog.svelte';

  let { job }: { job: Job | null | undefined } = $props();
  const c = $derived((job?.conductor && 'state' in job.conductor ? job.conductor : null) as Conductor | null);
  // « 0,12 $ »; a few tenths of a cent are shown as « < 0,01 $ » rather than a misleading « 0,00 $ »
  const usd = (n: number) => {
    const tiny = n > 0 && n < 0.005;
    const v = (tiny ? 0.01 : n).toFixed(2);
    const s = i18n.base === 'fr' ? v.replace('.', ',') + ' $' : '$' + v;
    return tiny ? '< ' + s : s;
  };
  const name = $derived(c ? (c.name || modelLabel(c.by).name) : '');
  let open = $state(false);
  let answered = $state('');
  let dismissed = $state('');
  let sending = $state(false);
  const askKey = $derived(c?.ask ? `${job?.id}:${c.ask.t}` : '');
  $effect(() => {
    if (askKey && answered !== askKey && dismissed !== askKey) open = true;
    if (!askKey) open = false;
  });

  async function reply(approve: boolean) {
    if (!job || !c?.ask || sending) return;
    sending = true;
    answered = `${job.id}:${c.ask.t}`;
    open = false;
    try { await api.answerConductor(job.id, approve); }
    catch { toast('error', t('conductor.askTitle')); }
    finally { sending = false; }
  }
</script>

{#if c && (c.by || c.ask || ['planning', 'running', 'asking'].includes(c.state))}
  <div class="conductor small" role="status" aria-live="polite">
    <p class="line">
      {#if c.by}
        <span>{t('conductor.line', { name })}</span>
        <span class="sep" aria-hidden="true">·</span>
        <span class="cost">{c.tier === 'free' && !c.usd ? t('conductor.free') : usd(c.usd)}</span>
        {#if c.usd || c.tier !== 'free'}<span class="muted xs">{t('conductor.capOf', { cap: usd(c.cap) })}</span>{/if}
        {#if c.difficulty}<span class="chip xs">{tk(`conductor.difficulty.${c.difficulty}`, c.difficulty)}</span>{/if}
      {:else}
        <span class="muted">{t('conductor.planning')}</span>
      {/if}
    </p>
    {#if c.plan?.length}
      <details>
        <summary class="xs">{t('conductor.showPlan', { n: c.plan.length })}{#if c.summary}{' — '}{c.summary}{/if}</summary>
        <ol class="steps">
          {#each c.plan as s (s.id)}
            <li class:advisory={s.advisory}>
              <span class="kind">{tk(`conductor.step.${s.kind}`, s.kind)}</span>
              <span class="model mono xs">{s.model ? (s.model_name || modelLabel(s.model).name) : t('conductor.auto')}</span>
              {#if s.advisory}<span class="muted xs">({t('conductor.proposed')})</span>{/if}
              {#if s.why}<span class="muted xs">— {s.why}</span>{/if}
            </li>
          {/each}
        </ol>
      </details>
    {/if}
    {#if c.final}
      <p class="xs {c.final.consistent ? 'ok' : 'warn'}">{c.final.consistent ? t('conductor.finalOk') : t('conductor.finalIssues')}</p>
    {/if}
    {#if c.ask && !open}
      <div class="ask" role="group" aria-label={t('conductor.askTitle')}>
        <p>{t('conductor.askBody', { spent: usd(c.ask.spent), cap: usd(c.ask.cap), step: usd(c.ask.step) })}</p>
        <button class="btn small primary" disabled={sending} onclick={() => reply(true)}>{t('conductor.askYes', { step: usd(c.ask.step) })}</button>
        <button class="btn small" disabled={sending} onclick={() => reply(false)}>{t('conductor.askNo')}</button>
      </div>
    {/if}
  </div>
  {#if c.ask}
    <Dialog bind:open title={t('conductor.askTitle')} onclose={() => { dismissed = askKey; }}>
      <p>{t('conductor.askBody', { spent: usd(c.ask.spent), cap: usd(c.ask.cap), step: usd(c.ask.step) })}</p>
      {#snippet actions()}
        <button class="btn" disabled={sending} onclick={() => reply(false)}>{t('conductor.askNo')}</button>
        <button class="btn primary" disabled={sending} onclick={() => reply(true)}>{t('conductor.askYes', { step: usd(c.ask?.step ?? 0.5) })}</button>
      {/snippet}
    </Dialog>
  {/if}
{/if}

<style>
  .conductor { margin: var(--s-1, 4px) 0 0; }
  .line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; margin: 0; }
  .cost { font-variant-numeric: tabular-nums; font-weight: 600; }
  .steps { margin: var(--s-1, 4px) 0 0; padding-left: 1.4em; }
  .steps li { margin: 2px 0; }
  .steps .kind { margin-right: 6px; }
  .steps li.advisory .kind { font-style: italic; }
  .ask { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: var(--s-2, 8px);
    padding: var(--s-2, 8px); border: 1px solid var(--line); border-radius: 8px; }
  .ask p { margin: 0; flex-basis: 100%; }
  .ok { color: var(--proved); }
  .warn { color: var(--running-fill, inherit); }
</style>
