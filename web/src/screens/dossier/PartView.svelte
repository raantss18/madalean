<script lang="ts">
  // One reference view of the dossier (a tab of the pane, a split column, or a separate window).
  import type { Dossier, Job } from '../../lib/api/types';
  import { calcEvents, type Part } from '../../lib/flow';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { phaseOf } from '../../lib/status';
  import StatusMark from '../../components/StatusMark.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import StepStatement from './StepStatement.svelte';
  import StepLean from './StepLean.svelte';
  import StepProof from './StepProof.svelte';
  import SplitDialog from './SplitDialog.svelte';

  let { dossier: d, job, part }: { dossier: Dossier; job: Job | undefined; part: Part } = $props();
  // S-AP: the plan and the literature are their own chunks
  const loadPlan = () => import('./PlanTree.svelte').then((m) => m.default);
  const loadLit = () => import('./LiteraturePanel.svelte').then((m) => m.default);
  const loadVersions = () => import('./VersionsPanel.svelte').then((m) => m.default);
  let splitting = $state(false);
  const kids = (id: string) => Object.values(app.m.dossiers).filter((c) => c.parent_id === id).sort((a, b) => a.created - b.created);
  const children = $derived(kids(d.id));
</script>

{#snippet loading()}<div class="loading" aria-busy="true"><span class="sr-only">{t('common.loading')}</span></div>{/snippet}
{#snippet tree(id: string, depth: number)}
  <ul class="tree">
    {#each kids(id) as c (c.id)}
      {@const cj = app.activeJob(c.id)}
      <li><a href="/d/{encodeURIComponent(c.id)}"><StatusMark phase={phaseOf(c.status, cj)} showLabel /><span>{c.title || c.theorem}</span>{#if cj}<span class="xs muted">{tk(`stage.${cj.stage}`, '')}{#if cj.waiting} · {tk(`waiting.${cj.waiting}`, '')}{/if}</span>{/if}</a>
        {#if depth < 6 && kids(c.id).length}{@render tree(c.id, depth + 1)}{/if}</li>
    {/each}
  </ul>
{/snippet}

<div class="part">
  {#if part === 'enonce'}<StepStatement dossier={d} {job} />
  {:else if part === 'lean'}<StepLean dossier={d} {job} />
  {:else if part === 'preuve'}<StepProof dossier={d} {job} />
  {:else if part === 'plan'}
    {#if children.length}
      <section class="panel lemmas" aria-labelledby="lem-h-{d.id}">
        <h2 id="lem-h-{d.id}">{t('proof.lemmas', { done: children.filter((c) => c.proved).length, n: children.length })}</h2>
        {#if d.retry_parent}<p class="hint">{t('proof.retryParent')}</p>{/if}
        {@render tree(d.id, 0)}
      </section>
    {/if}
    {#if d.statements.length && !job}<p><button class="btn small" onclick={() => (splitting = true)}><Icon name="split" size={14} />{t('dossier.split')}</button></p>{/if}
    {#await loadPlan()}{@render loading()}{:then PlanTree}<PlanTree dossier={d} />{/await}
    <SplitDialog dossier={d} bind:open={splitting} />
  {:else if part === 'litterature'}{#await loadLit()}{@render loading()}{:then LiteraturePanel}<LiteraturePanel dossier={d} />{/await}
  {:else if part === 'calculs'}
    {#each calcEvents(d) as e, i (i)}
      <section class="panel"><p class="xs muted">Sage + Lean · {fmtTime(e.t)}</p><p>{e.text.split('\n')[0]}</p><Md src={e.text.split('\n').slice(1).join('\n')} /></section>
    {:else}<p class="muted">{t('flow.filterEmpty')}</p>{/each}
  {:else}{#await loadVersions()}{@render loading()}{:then V}<V dossier={d} busy={Boolean(job)} />{/await}{/if}
</div>

<style>
  @media (min-width: 900px) { .part { container: part / inline-size; } }
  .tree { list-style: none; padding: 0; margin: var(--s-2) 0 0; }
  .tree .tree, .tree :global(.tree) { padding-left: var(--s-4); margin: 0; }
  .tree a { display: flex; align-items: center; gap: var(--s-3); min-height: var(--touch); color: var(--text); text-decoration: none; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  .tree a:hover { background: var(--surface-2); }
  .lemmas { margin-bottom: var(--s-3); }
</style>
