<script lang="ts">
  // Collapsible outline of the plan: the main view on a phone, the « Liste » view elsewhere. Same data as the map.
  import type { Plan, PlanNode } from '../../lib/api/research';
  import { t } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';
  import PlanStatus from './PlanStatus.svelte';

  let { plan, selected, onselect }: { plan: Plan; selected: string; onselect: (key: string) => void } = $props();
  let closed = $state<Record<string, boolean>>({});
  function plain(s: string): string { return s.replace(/\$([^$]*)\$/g, '$1').replace(/\\[a-zA-Z]+/g, (m) => m.slice(1)); }
  function others(n: PlanNode) { return (n.tracks ?? []).filter((x) => x.id !== n.active_track && !x.refused && x.lemmas.length); }
</script>

<ul class="outline" aria-label={t('plan.mapLabel')}>
  {@render row(plan.nodes[plan.root]!, 0)}
</ul>

{#snippet row(n: PlanNode, depth: number)}
  {@const kids = n.children.filter((c) => plan.nodes[c])}
  {@const alts = others(n)}
  {@const open = !closed[n.id]}
  <li>
    <div class="line" style="--d:{depth}">
      {#if kids.length || alts.length}
        <button class="tog btn quiet icon" aria-expanded={open} aria-label={n.title} onclick={() => (closed[n.id] = open)}>
          <Icon name={open ? 'chevronDown' : 'chevronRight'} size={16} />
        </button>
      {:else}<span class="tog" aria-hidden="true"></span>{/if}
      <button class="item ui-{n.ui}" class:sel={selected === n.id} aria-current={selected === n.id ? 'true' : undefined} onclick={() => onselect(n.id)}>
        <span class="ttl">{#if n.id === plan.root}<span class="kind">{t('plan.theorem')}</span>{/if}{plain(n.title)}</span>
        <PlanStatus ui={n.ui} obvious={n.obvious} small />
      </button>
    </div>
    {#if open && (kids.length || alts.length)}
      <ul>
        {#each kids as c (c)}{@render row(plan.nodes[c]!, depth + 1)}{/each}
        {#each alts as tr (tr.id)}
          <li><div class="line" style="--d:{depth + 1}"><span class="tog" aria-hidden="true"></span>
            <button class="item alt" class:sel={selected === `${n.id}#${tr.id}`} aria-current={selected === `${n.id}#${tr.id}` ? 'true' : undefined} onclick={() => onselect(`${n.id}#${tr.id}`)}>
              <span class="ttl">{t('plan.trackPill', { idea: plain(tr.idea || '—') })}</span>
              <PlanStatus ui={tr.abandoned ? 'abandoned' : 'alternative'} small />
            </button>
          </div></li>
        {/each}
      </ul>
    {/if}
  </li>
{/snippet}

<style>
  .outline, .outline ul { list-style: none; margin: 0; padding: 0; }
  .line { display: flex; align-items: stretch; gap: 4px; padding-left: calc(var(--d) * 14px); margin: 4px 0; }
  .tog { flex: none; width: 32px; min-height: 32px; }
  .item { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; text-align: left; padding: 8px 10px 8px 12px; min-height: var(--touch);
    border: 1.5px solid var(--line); border-left: 5px solid var(--line-strong); border-radius: var(--r-2); background: var(--surface); color: var(--text); font: inherit; cursor: pointer; }
  .ttl { font-size: var(--fs-sm); font-weight: 600; overflow-wrap: anywhere; }
  .kind { font-family: var(--font-serif); font-style: italic; color: var(--text-2); margin-right: 0.4em; }
  .sel { outline: 3px solid var(--accent); outline-offset: 1px; }
  .ui-proved { border-left-color: var(--proved); }
  .ui-failed { border-left-color: var(--failed); background: var(--failed-soft); }
  .ui-running { border-left-color: var(--running-fill); }
  .ui-hole, .ui-conditional { border: 2px dashed var(--running-fill); border-left-width: 5px; background: var(--running-soft); }
  .ui-to_validate { border-left-color: var(--accent); border-style: dashed solid dashed solid; }
  .alt { border-style: dashed; border-left: 1.5px dashed var(--line-strong); background: var(--surface-2); }
  .alt .ttl { font-weight: 500; color: var(--text-2); }
</style>
