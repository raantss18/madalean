<script lang="ts">
  // Global activity centre: every running/queued job of every dossier, cancel each; resource slots; recent jobs.
  import { app } from '../lib/store/app.svelte';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { TERMINAL } from '../lib/store/model';
  import JobRow from './JobRow.svelte';

  let { headingLevel = 2 }: { headingLevel?: 2 | 3 } = $props();
  const active = $derived(app.activeJobs);
  const recent = $derived(Object.values(app.m.jobs).filter((j) => TERMINAL.has(j.state)).sort((a, b) => (b.ended ?? 0) - (a.ended ?? 0)).slice(0, 8));
  const slots = $derived(app.m.system?.slots);
</script>

<section class="activity" aria-labelledby="act-h">
  <svelte:element this={`h${headingLevel}`} id="act-h">{t('activity.title')}</svelte:element>
  {#if slots}
    <ul class="slots" aria-label={t('activity.resources')}>
      {#each (['gpu', 'online', 'lean'] as const) as k}
        {@const s = slots[k]}
        <li class:full={s.used >= s.capacity}>
          <span class="name">{tk(`slot.${k}`, k)}</span>
          <span class="meter" aria-hidden="true">{#each Array(s.capacity) as _, i}<i class:on={i < s.used}></i>{/each}</span>
          <span class="nums">{t('activity.slotUse', { used: s.used, cap: s.capacity })}{#if s.waiting} · {t('activity.slotWaiting', { n: s.waiting })}{/if}</span>
        </li>
      {/each}
    </ul>
  {/if}
  {#if active.length}
    <ul class="jobs">{#each active as job (job.id)}<JobRow {job} />{/each}</ul>
  {:else}
    <p class="muted empty">{t('activity.none')}</p>
  {/if}
  {#if recent.length}
    <h3>{t('activity.recent')}</h3>
    <ul class="jobs">{#each recent as job (job.id)}<JobRow {job} compact />{/each}</ul>
  {/if}
</section>

<style>
  .activity h2, .activity h3 { margin-top: 0; }
  .activity h3 { margin-top: var(--s-4); font-size: var(--fs-sm); color: var(--text-2); }
  ul { list-style: none; margin: 0; padding: 0; }
  .slots { display: grid; gap: 6px; margin-bottom: var(--s-3); padding: var(--s-3); background: var(--surface-2); border-radius: var(--r-2); }
  .slots li { display: grid; grid-template-columns: 7.5rem auto 1fr; gap: var(--s-2); align-items: center; font-size: var(--fs-sm); }
  .name { font-weight: 600; }
  .meter { display: inline-flex; gap: 3px; }
  .meter i { width: 12px; height: 12px; border-radius: 2px; border: 1.5px solid var(--line-strong); }
  .meter i.on { background: var(--running-fill); border-color: var(--running-fill); }
  .nums { color: var(--text-2); font-size: var(--fs-xs); }
  .empty { margin: var(--s-2) 0; }
</style>
