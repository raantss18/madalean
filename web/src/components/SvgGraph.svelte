<script lang="ts" module>
  export interface GNode { id: string; label: string; kind: string; cls?: string; title?: string; pattern?: string }
  export interface GEdge { source: string; target: string; kind?: string; dashed?: boolean; label?: string }
</script>

<script lang="ts">
  // Pan/zoom SVG graph: hundreds of nodes stay readable (labels only near the pointer/selection or when zoomed in),
  // keyboard: Tab through nodes, Enter opens; arrows pan, +/- zoom. Positions are computed by the caller.
  import type { Pos } from '../lib/graph/layout';
  import { t } from '../lib/i18n/index.svelte';

  let { nodes, edges, pos, selected = '', onselect, onopen, label, arrows = false, height = '70vh', nodeW = 0, minFit = 0.1 }: {
    nodes: GNode[]; edges: GEdge[]; pos: Pos; selected?: string; onselect?: (id: string) => void; onopen?: (id: string) => void;
    label: string; arrows?: boolean; height?: string; nodeW?: number; minFit?: number;
  } = $props();

  let svg: SVGSVGElement | undefined = $state();
  let view = $state({ x: 0, y: 0, k: 1 });
  let hover = $state('');
  let drag: { x: number; y: number; vx: number; vy: number } | null = null;
  const bounds = $derived.by(() => {
    const ps = Object.values(pos);
    if (!ps.length) return { x0: 0, y0: 0, x1: 100, y1: 100 };
    return { x0: Math.min(...ps.map((p) => p.x)) - 80, y0: Math.min(...ps.map((p) => p.y)) - 40, x1: Math.max(...ps.map((p) => p.x)) + 80 + nodeW, y1: Math.max(...ps.map((p) => p.y)) + 40 };
  });
  function fit() {
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const k = Math.max(minFit, Math.min(r.width / (bounds.x1 - bounds.x0), r.height / (bounds.y1 - bounds.y0), 1.6));
    const w = (bounds.x1 - bounds.x0) * k;
    view = { k, x: w > r.width ? -bounds.x0 * k : -bounds.x0 * k + (r.width - w) / 2, y: -bounds.y0 * k + (r.height - (bounds.y1 - bounds.y0) * k) / 2 };
  }
  $effect(() => { void pos; if (svg) queueMicrotask(fit); });
  const neighbours = $derived.by(() => {
    const focus = hover || selected;
    const s = new Set<string>();
    if (!focus) return s;
    s.add(focus);
    for (const e of edges) { if (e.source === focus) s.add(e.target); if (e.target === focus) s.add(e.source); }
    return s;
  });
  const showAll = $derived(view.k > 0.9 || nodes.length <= 40);

  function wheel(e: WheelEvent) {
    e.preventDefault();
    const r = svg!.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }
  function zoomAt(px: number, py: number, f: number) {
    const k = Math.min(4, Math.max(0.1, view.k * f));
    view = { k, x: px - ((px - view.x) * k) / view.k, y: py - ((py - view.y) * k) / view.k };
  }
  function down(e: PointerEvent) {
    if ((e.target as Element).closest('.gn')) return;
    drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) { if (drag) view = { ...view, x: drag.vx + e.clientX - drag.x, y: drag.vy + e.clientY - drag.y }; }
  function up() { drag = null; }
  function key(e: KeyboardEvent) {
    const step = 60;
    if (e.key === 'ArrowLeft') view = { ...view, x: view.x + step };
    else if (e.key === 'ArrowRight') view = { ...view, x: view.x - step };
    else if (e.key === 'ArrowUp') view = { ...view, y: view.y + step };
    else if (e.key === 'ArrowDown') view = { ...view, y: view.y - step };
    else if (e.key === '+' || e.key === '=') zoomCenter(1.25);
    else if (e.key === '-') zoomCenter(0.8);
    else return;
    e.preventDefault();
  }
  function zoomCenter(f: number) { const r = svg!.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, f); }
  const short = (s: string) => (nodeW ? (s.length > 26 ? s.slice(0, 25) + '…' : s) : s.length > 32 ? s.slice(0, 31) + '…' : s);
  function edgePath(e: GEdge): string {
    const a = pos[e.source], b = pos[e.target];
    if (!a || !b) return '';
    if (nodeW) { const x1 = a.x, y1 = a.y, x2 = b.x + nodeW, y2 = b.y; const mx = (x1 + x2) / 2; return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`; }
    return `M${a.x},${a.y} L${b.x},${b.y}`;
  }
</script>

<div class="graph">
  <div class="tools row">
    <button class="btn small" onclick={() => zoomCenter(1.25)} aria-label={t('graph.zoomIn')}>+</button>
    <button class="btn small" onclick={() => zoomCenter(0.8)} aria-label={t('graph.zoomOut')}>−</button>
    <button class="btn small" onclick={fit}>{t('graph.fit')}</button>
    <span class="xs muted">{t('graph.count', { n: nodes.length, e: edges.length })} · {t('graph.keys')}</span>
  </div>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (the canvas pans and zooms with the keyboard; nodes are buttons) -->
  <svg bind:this={svg} role="group" aria-label={label} tabindex="0" style:height onwheel={wheel} onpointerdown={down} onpointermove={move} onpointerup={up} onkeydown={key}>
    <defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--line-strong)" /></marker></defs>
    <g transform="translate({view.x},{view.y}) scale({view.k})">
      {#each edges as e, i (i)}
        <path class="ge {e.kind ?? ''}" class:dim={neighbours.size > 0 && !(neighbours.has(e.source) && neighbours.has(e.target))} class:dashed={e.dashed}
          d={edgePath(e)} marker-end={arrows ? 'url(#arr)' : undefined} />
      {/each}
      {#each nodes as n (n.id)}
        {@const p = pos[n.id]}
        {#if p}
          <g class="gn {n.kind} {n.cls ?? ''}" class:sel={selected === n.id} class:dim={neighbours.size > 0 && !neighbours.has(n.id)} transform="translate({p.x},{p.y})"
            role="button" tabindex="0" aria-label={`${short(n.label)}${short(n.label) !== n.label ? ' (' + n.label + ')' : ''}${n.title ? ' — ' + n.title : ''}`}
            onclick={() => onselect?.(n.id)} ondblclick={() => onopen?.(n.id)} onkeydown={(e) => { if (e.key === 'Enter') { onselect?.(n.id); onopen?.(n.id); } else if (e.key === ' ') { e.preventDefault(); onselect?.(n.id); } }}
            onpointerenter={() => (hover = n.id)} onpointerleave={() => (hover = '')} onfocus={() => (hover = n.id)} onblur={() => (hover = '')}>
            {#if nodeW}
              <rect x="0" y="-18" width={nodeW} height="36" rx="6" class="box" stroke-dasharray={n.pattern === 'dashed' ? '5 3' : n.pattern === 'dotted' ? '2 3' : undefined} />
              <text x="10" y="5" class="lbl">{short(n.label)}</text>
            {:else}
              <circle r={(n.kind === 'note' ? 7 : 9) / Math.sqrt(Math.min(1, view.k))} class="dot" />
              {#if showAll || neighbours.has(n.id) || selected === n.id}<text x={12 / Math.min(1, view.k)} y={4 / Math.min(1, view.k)} class="lbl" style:font-size="{12 / Math.min(1, view.k)}px" style:stroke-width="{3 / Math.min(1, view.k)}px">{short(n.label)}</text>{/if}
            {/if}
            <title>{n.title ?? n.label}</title>
          </g>
        {/if}
      {/each}
    </g>
  </svg>
</div>

<style>
  .graph { display: grid; gap: 4px; }
  svg { width: 100%; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); touch-action: none; cursor: grab; display: block; }
  svg:focus-visible { outline: 2px solid var(--focus); }
  .ge { fill: none; stroke: var(--line-strong); stroke-width: 1.2; }
  .ge.uses { stroke: var(--accent); }
  .ge.cites { stroke: var(--online); stroke-dasharray: 3 3; }
  .ge.dashed { stroke-dasharray: 6 4; }
  .ge.dim, .gn.dim { opacity: 0.18; }
  .gn { cursor: pointer; }
  .gn:focus-visible { outline: none; }
  .gn:focus-visible .dot, .gn:focus-visible .box { stroke: var(--focus); stroke-width: 3; }
  .dot { fill: var(--surface); stroke-width: 2.5; stroke: var(--text-2); }
  .note .dot { fill: var(--accent-soft); stroke: var(--accent); }
  .dossier .dot { fill: var(--surface-2); stroke: var(--text-2); }
  .dossier.proved .dot { fill: var(--proved); stroke: var(--proved); }
  .source .dot { fill: var(--online-soft); stroke: var(--online); }
  .missing .dot { stroke-dasharray: 2 2; fill: none; }
  .sel .dot, .sel .box { stroke: var(--laterite-mark); stroke-width: 3.5; }
  .lbl { font: 600 12px var(--font-ui); fill: var(--text); paint-order: stroke; stroke: var(--surface); stroke-width: 3px; pointer-events: none; }
  .box { fill: var(--surface); stroke: var(--line-strong); stroke-width: 1.5; }
  .st-verified .box { fill: var(--proved-soft); stroke: var(--proved); stroke-width: 2.5; }
  .st-proved .box { fill: var(--proved-soft); stroke: var(--proved); }
  .st-defined .box { fill: var(--local-soft); stroke: var(--local); }
  .st-statement .box { fill: var(--accent-soft); stroke: var(--accent); }
  .st-stated .box, .st-not_created .box { fill: var(--surface); stroke: var(--line-strong); }
  .st-blocked .box { fill: var(--running-soft); stroke: var(--running); }
  .st-failed .box { fill: var(--failed-soft); stroke: var(--failed); }
  .st-conditional .box { fill: var(--running-soft); stroke: var(--running); }
  .box + .lbl { stroke: none; font-size: 13px; }
</style>
