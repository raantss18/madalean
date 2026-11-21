<script lang="ts">
  import type { Job } from '../lib/api/types';
  import { api } from '../lib/api/client';
  import { app } from '../lib/store/app.svelte';
  import { t, tk, fmtDuration } from '../lib/i18n/index.svelte';
  import { clock } from '../lib/ui/clock.svelte';
  import { jobModel, modelLabel, phaseOf, providerName } from '../lib/status';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import StatusMark from './StatusMark.svelte';
  import Icon from './Icon.svelte';

  let { job, compact = false }: { job: Job; compact?: boolean } = $props();
  let cancelling = $state(false);
  const d = $derived(app.m.dossiers[job.dossier_id]);
  const phase = $derived(phaseOf(d?.status ?? 'draft', job));
  const model = $derived(modelLabel(app.liveModel[job.id] || jobModel(job)));
  const elapsed = $derived(job.started ? clock.now - job.started : clock.now - job.created);
  const live = $derived(job.state === 'queued' || job.state === 'running');

  async function cancel() {
    cancelling = true;
    try {
      const r = await api.cancelJob(job.id);
      if (!r.cancelled) toast('info', t('activity.alreadyDone'));
    } catch (e) {
      toast('error', errorText(e));
    } finally {
      cancelling = false;
    }
  }
</script>

<li class="job" class:compact>
  <StatusMark phase={live ? phase : job.state === 'done' ? 'proved' : job.state === 'cancelled' ? 'stopped' : 'failed'} />
  <div class="main">
    <a class="title" href="/d/{encodeURIComponent(job.dossier_id)}">{d?.title || job.dossier_id}</a>
    <div class="meta xs">
      {#if live}
        <span>{tk(`stage.${job.stage}`, job.stage || t('stage.starting'))}</span>
        {#if job.waiting}<span class="wait">· {tk(`waiting.${job.waiting}`, job.waiting)}</span>{/if}
        {#if model.name}<span class="chip {model.local ? 'local' : 'online'}" title={providerName(model.provider)}>{model.name}</span>{/if}
        <span class="muted">{fmtDuration(elapsed)}</span>
      {:else}
        <span>{tk(`jobstate.${job.state}`, job.state)}</span>
        {#if job.error && job.state === 'failed'}<span class="muted">· {tk(`joberr.${job.error}`, job.error)}</span>{/if}
      {/if}
    </div>
  </div>
  {#if live}
    <button class="btn small" onclick={cancel} disabled={cancelling} aria-label={t('activity.cancelOne', { title: d?.title ?? '' })}>
      <Icon name="stop" size={14} />{cancelling ? t('activity.cancelling') : t('common.stop')}
    </button>
  {/if}
</li>

<style>
  .job { display: flex; align-items: center; gap: var(--s-3); padding: var(--s-2) 0; border-bottom: 1px solid var(--line); }
  .job:last-child { border-bottom: 0; }
  .main { flex: 1; min-width: 0; }
  .title { display: block; color: var(--text); font-weight: 600; text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .title:hover { text-decoration: underline; }
  .meta { display: flex; flex-wrap: wrap; gap: 4px 6px; align-items: center; color: var(--text-2); }
  .wait { color: var(--running); font-weight: 600; }
  .meta .chip { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
</style>
