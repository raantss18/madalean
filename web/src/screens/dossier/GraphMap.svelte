<script lang="ts">
  // The problem graph drawn (S-BA, D59): an optional view beside the list, never instead of it. Layered DAG (the goal
  // on top, a lemma below every lemma that uses it; a shared sub-lemma is drawn ONCE with several arrows). Status =
  // colour + shape + words: verified = square box, conditional = dashed box, open = pill, refuted = double border,
  // abandoned = dotted and struck through; each box spells its state. Nodes are buttons in the LIST order, so Tab
  // follows the list; Enter opens the same detail panel. Pan: drag or the arrow buttons; zoom: wheel / + / −.
  import type { Graph } from '../../lib/api/graph';
  import { STATE_ICON } from '../../lib/api/graph';
  import { dagLayout, zoomAt } from '../../lib/graph/dag';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';

  let { graph, order, selected, onselect }: {
    graph: Graph; order: string[]; selected: string; onselect: (id: string) => void;
  } = $props();
  const L = $derived(dagLayout(graph));
  const box = $derived(Object.fromEntries(L.boxes.map((b) => [b.id, b])));
  const ids = $derived([...order.filter((id) => box[id]), ...L.boxes.map((b) => b.id).filter((id) => !order.includes(id))]);
  let view = $state({ x: 0, y: 0, k: 1 });
  let drag: { x: number; y: number; vx: number; vy: number } | null = null;
  let frame: HTMLDivElement | undefined = $state();

  function wheel(e: WheelEvent) {
    if (!frame) return;
    e.preventDefault();
    const r = frame.getBoundingClientRect();
    view = zoomAt(view, e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
  }
  function down(e: PointerEvent) {
    if ((e.target as HTMLElement).closest('button')) return;
    drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (drag) view = { ...view, x: drag.vx + e.clientX - drag.x, y: drag.vy + e.clientY - drag.y };
  }
  const up = () => { drag = null; };
  const zoom = (f: number) => { const r = frame?.getBoundingClientRect(); view = zoomAt(view, f, (r?.width ?? 0) / 2, (r?.height ?? 0) / 2); };
  const pan = (dx: number, dy: number) => { view = { ...view, x: view.x + dx, y: view.y + dy }; };
  /** keep the focused node in sight (keyboard users never need to pan by hand) */
  function seen(id: string) {
    const b = box[id];
    const r = frame?.getBoundingClientRect();
    if (!b || !r) return;
    const x = b.x * view.k + view.x, y = b.y * view.k + view.y;
    if (x < 0 || y < 0 || x + b.w * view.k > r.width || y + b.h * view.k > r.height)
      view = { ...view, x: r.width / 2 - (b.x + b.w / 2) * view.k, y: r.height / 3 - (b.y + b.h / 2) * view.k };
  }
  const stateLabel = (s: string, composed = false) => (s === 'verified' && composed ? t('pg.state.composed') : tk(`pg.state.${s}`, s));
</script>

<div class="gm">
  <div class="tools" role="toolbar" aria-label={t('pg.map.tools')}>
    <button class="btn quiet icon small" aria-label={t('pg.map.zoomIn')} onclick={() => zoom(1.2)}><Icon name="plus" size={14} /></button>
    <button class="btn quiet icon small" aria-label={t('pg.map.zoomOut')} onclick={() => zoom(1 / 1.2)}><span aria-hidden="true">−</span></button>
    <button class="btn quiet small" onclick={() => (view = { x: 0, y: 0, k: 1 })}>{t('pg.map.reset')}</button>
    <button class="btn quiet icon small" aria-label={t('pg.map.left')} onclick={() => pan(80, 0)}><span aria-hidden="true">←</span></button>
    <button class="btn quiet icon small" aria-label={t('pg.map.right')} onclick={() => pan(-80, 0)}><span aria-hidden="true">→</span></button>
    <button class="btn quiet icon small" aria-label={t('pg.map.up')} onclick={() => pan(0, 80)}><span aria-hidden="true">↑</span></button>
    <button class="btn quiet icon small" aria-label={t('pg.map.down')} onclick={() => pan(0, -80)}><span aria-hidden="true">↓</span></button>
  </div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="frame" bind:this={frame} role="group" aria-label={t('pg.map.label')}
    onwheel={wheel} onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up}>
    <div class="plane" style="width:{L.width}px;height:{L.height}px;transform:translate({view.x}px,{view.y}px) scale({view.k})">
      <svg width={L.width} height={L.height} aria-hidden="true" focusable="false">
        <defs><marker id="pg-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="head" /></marker></defs>
        {#each L.edges as e, i (i)}
          <path d={e.d} class="k-{e.kind}" class:on={selected === e.to || selected === e.from} marker-end="url(#pg-arrow)" />
        {/each}
      </svg>
      {#each ids as id (id)}
        {@const b = box[id]!}
        {@const n = graph.nodes[id]!}
        <button class="nb st-{n.state}" class:root={id === graph.root} style="left:{b.x}px;top:{b.y}px;width:{b.w}px;height:{b.h}px"
          aria-current={selected === id ? 'true' : undefined} onclick={() => onselect(id)} onfocus={() => seen(id)}>
          <span class="m"><Icon name={STATE_ICON[n.state] ?? 'info'} size={12} />{stateLabel(n.state, n.composed)}{#if id === graph.root} · {t('pg.target')}{/if}</span>
          <span class="tt">{n.title}</span>
        </button>
      {/each}
    </div>
  </div>
  <p class="xs muted">{t('pg.map.hint')}</p>
</div>

<style>
  .gm { display: grid; gap: 6px; }
  .tools { display: flex; flex-wrap: wrap; gap: 4px; }
  .frame { position: relative; overflow: hidden; height: min(64dvh, 640px); border: 1px solid var(--line); border-radius: var(--r-3);
    background: radial-gradient(circle, var(--line) 1px, transparent 1.2px) 0 0 / 18px 18px, var(--bg); touch-action: none; cursor: grab; }
  .plane { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
  svg { position: absolute; inset: 0; overflow: visible; }
  path { fill: none; stroke: var(--line-strong); stroke-width: 1.6; }
  path.k-refutes { stroke: var(--failed); stroke-dasharray: 2 4; }
  path.k-generalises, path.k-special_case { stroke-dasharray: 6 4; }
  path.on { stroke: var(--accent); stroke-width: 2.4; }
  .head { fill: var(--line-strong); stroke: none; }
  .nb { position: absolute; display: flex; flex-direction: column; gap: 2px; text-align: left; padding: 6px 10px; overflow: hidden;
    border: 1.5px solid var(--line-strong); background: var(--surface); color: var(--text); font: inherit; cursor: pointer; border-radius: 4px; }
  .nb[aria-current='true'] { outline: 3px solid var(--focus); outline-offset: 2px; }
  .nb:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
  .m { display: inline-flex; align-items: center; gap: 4px; font-size: 0.72rem; font-weight: 700; color: var(--text-2); }
  .tt { font-size: var(--fs-sm); font-weight: 600; line-height: 1.25; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
  .root { border-width: 2.5px; border-color: var(--ink); }
  /* shape + colour + words */
  .st-verified { border: 2px solid var(--proved); border-radius: 2px; }
  .st-verified .m { color: var(--proved); }
  .st-conditional { border: 2px dashed var(--running-fill); background: var(--running-soft); }
  .st-conditional .m { color: var(--running); }
  .st-open { border-radius: 999px; padding-left: 16px; padding-right: 16px; }
  .st-refuted { border: 4px double var(--failed); background: var(--failed-soft); }
  .st-refuted .m { color: var(--failed); }
  .st-abandoned { border: 2px dotted var(--text-3); background: transparent; }
  .st-abandoned .tt { text-decoration: line-through; text-decoration-color: var(--text-3); }
</style>
