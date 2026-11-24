<script lang="ts">
  // The end of the thread when nothing runs: what was tried, why it stopped, and what can be done now.
  import type { Dossier, Job } from '../../lib/api/types';
  import { failureSummary, troubleOf } from '../../lib/flow';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { app } from '../../lib/store/app.svelte';
  import { modelLabel } from '../../lib/status';
  import Icon from '../../components/Icon.svelte';
  import { run } from './actions';

  let { dossier: d, last }: { dossier: Dossier; last: Job | undefined } = $props();
  const st = $derived(d.statements[d.cur_statement]);
  const trouble = $derived(troubleOf(d, last));
  const kind = $derived(trouble || (st ? 'ready' : 'draft'));
  const f = $derived(failureSummary(d, last));
  const cause = $derived(tk(`joberr.${f.error}`, ''));
  const noted = $derived(d.statement_notes.some((n) => n.parent === d.cur_statement) || !app.m.settings?.statement_notes);
  const prove = () => run(d.id, noted ? ['proof', 'explanation'] : ['notes', 'proof', 'explanation']);
  const translate = () => run(d.id, ['understand', 'statement']);
</script>

<section class="next {kind}" id="next-{d.id}" tabindex="-1" aria-labelledby="next-h-{d.id}">
  <h3 id="next-h-{d.id}"><Icon name={trouble === 'failed' ? 'warn' : trouble ? 'stop' : 'info'} size={18} /> {t(`flow.nextTitle.${kind}`)}</h3>
  {#if trouble === 'failed'}
    <p>{cause || t('proof.failedText')}</p>
    {#if f.attempts}<p class="small">{f.models.length ? t('flow.tried', { n: f.attempts, models: f.models.map((m) => modelLabel(m).name).join(', ') }) : t('flow.triedNo', { n: f.attempts })}</p>{/if}
    {#if f.cause && f.cause !== cause}<p class="small lbl">{t('flow.lastCause')}</p><pre>{f.cause}</pre>{/if}
    <p class="small lbl">{t('flow.canDo')}</p>
  {:else if trouble === 'stopped'}<p>{t('flow.idleStopped')}</p>
  {:else}<p>{t(st ? (st.ok ? 'flow.idleReady' : 'flow.idleRejected') : 'flow.idleDraft')}</p>{/if}
  <div class="row">
    {#if st?.ok}<button class="btn primary" onclick={prove}>{trouble === 'failed' ? t('flow.retry') : trouble === 'stopped' ? t('flow.resume') : t('lean.prove')}</button>
    {:else if d.problem}<button class="btn primary" onclick={translate}>{trouble || st ? t('flow.retry') : t('enonce.translate')}</button>{/if}
    {#if st}<a class="btn" href="/d/{encodeURIComponent(d.id)}/lean">{t('flow.reviewStatement')}</a>{/if}
    {#if st && trouble}<a class="btn" href="/d/{encodeURIComponent(d.id)}/plan"><Icon name="split" size={16} />{t('flow.splitPlan')}</a>{/if}
    {#if trouble === 'failed'}<a class="btn quiet" href="/reglages/modeles">{t('flow.models')}</a>{/if}
  </div>
  {#if trouble === 'failed' && st?.ok}<p class="hint">{t('proof.failedHint')}</p>{/if}
</section>

<style>
  .next { border: 1px dashed var(--line-strong); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); background: var(--surface); scroll-margin: 180px 0 160px; }
  .next.failed { border: 1px solid var(--failed); }
  h3 { margin: 0 0 4px; display: flex; gap: 8px; align-items: center; font-family: var(--font-serif); font-size: 1.0625rem; }
  .failed h3 { color: var(--failed); }
  p { margin: 0 0 var(--s-2); }
  .lbl { font-weight: 600; margin-bottom: 2px; }
  pre { margin: 0 0 var(--s-2); background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-1); font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; }
  .hint { margin: var(--s-2) 0 0; }
</style>
