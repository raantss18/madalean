<script lang="ts">
  // Dossiers of the current project with live status. Lemmas (parent_id) are nested under their parent.
  import type { DossierSummary } from '../lib/api/types';
  import { app } from '../lib/store/app.svelte';
  import { prefs } from '../lib/prefs.svelte';
  import { route } from '../lib/router.svelte';
  import { t, tk, fmtTime } from '../lib/i18n/index.svelte';
  import { jobModel, modelLabel, phaseOf } from '../lib/status';
  import StatusMark from './StatusMark.svelte';

  let { onpick }: { onpick?: () => void } = $props();
  let q = $state('');
  let showArchived = $state(false);

  const all = $derived(Object.values(app.m.dossiers).filter((d) => (prefs.lastProject ? d.project_id === prefs.lastProject : true) && (showArchived || !d.archived)));
  const filtered = $derived(q.trim() ? all.filter((d) => (d.title + ' ' + d.theorem).toLowerCase().includes(q.trim().toLowerCase())) : all);
  const tree = $derived.by(() => {
    const ids = new Set(filtered.map((d) => d.id));
    const kids = new Map<string, DossierSummary[]>();
    const roots: DossierSummary[] = [];
    for (const d of filtered) {
      if (d.parent_id && ids.has(d.parent_id)) {
        const l = kids.get(d.parent_id) ?? [];
        l.push(d);
        kids.set(d.parent_id, l);
      } else roots.push(d);
    }
    roots.sort((a, b) => b.updated - a.updated);
    return { roots, kids };
  });
  const current = $derived(route.name === 'dossier' ? route.params['id'] : '');
</script>

<div class="dl">
  <div class="search">
    <label class="sr-only" for="dl-q">{t('list.search')}</label>
    <input id="dl-q" class="input" type="search" placeholder={t('list.search')} bind:value={q} autocomplete="off" />
  </div>
  {#if tree.roots.length === 0}
    <div class="empty">
      {#if q}<p class="muted small">{t('list.noMatch')}</p>
      {:else}<p class="small">{t('list.empty')}</p><a class="btn small primary" href="/" onclick={() => onpick?.()}>{t('list.startOne')}</a>{/if}
    </div>
  {:else}
    <ul role="list" aria-label={t('list.label')}>
      {#each tree.roots as d (d.id)}
        {@render row(d, 0)}
      {/each}
    </ul>
  {/if}
  <label class="switch xs arch"><input type="checkbox" bind:checked={showArchived} />{t('list.showArchived')}</label>
</div>

{#snippet row(d: DossierSummary, depth: number)}
  {@const job = app.activeJob(d.id)}
  {@const phase = phaseOf(d.status, job)}
  {@const kids = tree.kids.get(d.id) ?? []}
  <li>
    <a class="item" class:current={current === d.id} href="/d/{encodeURIComponent(d.id)}" aria-current={current === d.id ? 'page' : undefined} style:padding-left="{12 + depth * 18}px" onclick={() => onpick?.()}>
      <StatusMark {phase} />
      <span class="txt">
        <span class="title">{d.title || d.theorem}</span>
        <span class="sub xs">
          {#if job}
            {tk(`stage.${job.stage}`, t('stage.starting'))}{#if job.waiting} · <span class="wait">{tk(`waiting.${job.waiting}`, '')}</span>{/if}
            {#if jobModel(job) || app.liveModel[job.id]}{@const ml = modelLabel(app.liveModel[job.id] || jobModel(job))} · {ml.name}{/if}
          {:else}
            {tk(`phase.${phase}`, phase)} · {fmtTime(d.updated)}
          {/if}
        </span>
      </span>
      {#if kids.length}<span class="chip">{kids.filter((k) => k.proved).length}/{kids.length}</span>{/if}
    </a>
    {#if kids.length}
      <ul role="list" aria-label={t('list.lemmasOf', { title: d.title })}>
        {#each kids.sort((a, b) => a.created - b.created) as k (k.id)}{@render row(k, depth + 1)}{/each}
      </ul>
    {/if}
  </li>
{/snippet}

<style>
  .dl { display: flex; flex-direction: column; min-height: 0; }
  .search { padding: var(--s-2) var(--s-3); }
  .search .input { min-height: 36px; }
  ul { list-style: none; margin: 0; padding: 0; }
  .item { display: flex; align-items: center; gap: 10px; min-height: var(--touch); padding: 6px 12px; color: var(--text); text-decoration: none; border-left: 3px solid transparent; }
  .item:hover { background: var(--surface-2); }
  .item.current { background: var(--accent-soft); border-left-color: var(--accent); }
  .txt { display: grid; min-width: 0; flex: 1; }
  .title { font-weight: 600; font-size: var(--fs-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sub { color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .wait { color: var(--running); font-weight: 600; }
  .empty { padding: var(--s-4); }
  .arch { padding: var(--s-2) var(--s-3); color: var(--text-3); }
  .arch input { transform: scale(0.8); }
</style>
