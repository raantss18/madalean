<script lang="ts">
  // The mind map: theorem on the left, lemmas to the right, sub-lemmas further right. Solid curves = the chosen
  // track; a dashed pill = another track (strategy) kept in reserve. Nodes are buttons in depth-first order, so Tab
  // follows the proof's structure; the selected one opens the detail panel.
  import type { Plan } from '../../lib/api/research';
  import { layout } from '../../lib/plan/layout';
  import { t } from '../../lib/i18n/index.svelte';
  import PlanStatus from './PlanStatus.svelte';
  import Icon from '../../components/Icon.svelte';

  let { plan, selected, onselect }: { plan: Plan; selected: string; onselect: (key: string) => void } = $props();
  const L = $derived(layout(plan));
  function plain(s: string): string { return s.replace(/\$([^$]*)\$/g, '$1').replace(/\\[a-zA-Z]+/g, (m) => m.slice(1)); }
</script>

<div class="map-scroll" role="group" aria-label={t('plan.mapLabel')}>
  <div class="map" style="width:{L.width}px;height:{L.height}px">
    <svg width={L.width} height={L.height} aria-hidden="true" focusable="false">
      {#each L.edges as e (e.to)}
        <path d={e.d} class:dashed={e.dashed} class:on={selected === e.to || selected === e.from} />
      {/each}
    </svg>
    {#each L.items as it (it.key)}
      {@const n = plan.nodes[it.node]!}
      {#if it.kind === 'node'}
        <button class="mnode ui-{n.ui}" class:root={it.key === plan.root} class:sel={selected === it.key}
          style="left:{it.x}px;top:{it.y}px;width:{it.w}px;height:{it.h}px" aria-current={selected === it.key ? 'true' : undefined}
          onclick={() => onselect(it.key)}>
          <span class="top">{#if it.key === plan.root}<span class="kind">{t('plan.theorem')}</span>{/if}<PlanStatus ui={n.ui} obvious={n.obvious} small /></span>
          <span class="ttl">{plain(n.title)}</span>
        </button>
      {:else}
        <button class="mtrack" class:abandoned={it.track?.abandoned} class:sel={selected === it.key}
          style="left:{it.x}px;top:{it.y}px;width:{it.w}px;height:{it.h}px" aria-current={selected === it.key ? 'true' : undefined}
          onclick={() => onselect(it.key)}>
          <span class="top"><Icon name={it.track?.abandoned ? 'stop' : 'split'} size={12} />{it.track?.abandoned ? t('plan.ui.abandoned') : t('plan.ui.alternative')} · {t('plan.trackLemmas', { n: it.track?.lemmas.length ?? 0 })}</span>
          <span class="ttl">{plain(it.track?.idea || '—')}</span>
        </button>
      {/if}
    {/each}
  </div>
</div>

<style>
  .map-scroll { overflow: auto; max-width: 100%; max-height: min(72dvh, 820px); border: 1px solid var(--line); border-radius: var(--r-3); background:
    radial-gradient(circle, var(--line) 1px, transparent 1.2px) 0 0 / 18px 18px, var(--bg); }
  .map { position: relative; }
  svg { position: absolute; inset: 0; }
  path { fill: none; stroke: var(--line-strong); stroke-width: 1.6; }
  path.dashed { stroke-dasharray: 5 5; }
  path.on { stroke: var(--accent); stroke-width: 2.2; }
  .mnode, .mtrack { position: absolute; display: flex; flex-direction: column; gap: 4px; text-align: left; padding: 8px 10px 8px 14px;
    border: 1.5px solid var(--line-strong); border-radius: var(--r-2); background: var(--surface); color: var(--text); font: inherit; cursor: pointer; overflow: hidden; }
  .mnode::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: var(--line-strong); }
  .mnode:hover, .mtrack:hover { box-shadow: var(--shadow-1); border-color: var(--accent); }
  .sel { outline: 3px solid var(--accent); outline-offset: 2px; }
  .top { display: flex; align-items: center; gap: 6px; min-width: 0; font-size: 0.75rem; color: var(--text-3); font-weight: 700; }
  .kind { font-family: var(--font-serif); font-style: italic; font-weight: 600; color: var(--text-2); }
  .ttl { font-size: var(--fs-sm); line-height: 1.3; font-weight: 600; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
  .root { border-width: 2px; border-color: var(--ink); }
  .root .ttl { font-family: var(--font-serif); font-size: 1rem; -webkit-line-clamp: 3; line-clamp: 3; }
  /* status: the left band + border pattern carry it, the words say it */
  .ui-proved::before { background: var(--proved); }
  .ui-proved { border-color: var(--proved); }
  .ui-failed::before { background: var(--failed); }
  .ui-failed { border-color: var(--failed); background: var(--failed-soft); }
  .ui-running::before { background: repeating-linear-gradient(135deg, var(--running-fill) 0 6px, transparent 6px 10px); }
  .ui-hole, .ui-conditional { border: 2px dashed var(--running-fill); background: var(--running-soft); }
  .ui-hole::before, .ui-conditional::before { background: var(--running-fill); }
  .ui-to_validate { border-style: dashed; }
  .ui-to_validate::before { background: var(--accent); }
  .mtrack { border: 1.5px dashed var(--line-strong); background: var(--surface-2); padding-left: 10px; }
  .mtrack .ttl { font-weight: 500; color: var(--text-2); -webkit-line-clamp: 1; line-clamp: 1; }
  .mtrack.abandoned { background: transparent; }
  @media (prefers-reduced-motion: no-preference) { .mnode, .mtrack { transition: box-shadow .15s var(--ease), border-color .15s var(--ease); } }
</style>
