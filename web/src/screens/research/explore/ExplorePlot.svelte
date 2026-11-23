<script lang="ts">
  // Small inline plot of one column of an exploration's table against its index (no library; colours from the
  // theme's variables, so light and dark both work). The text alternative says what the picture shows.
  import { buildPlot, shortValue } from '../../../lib/conjectures/plot';
  import { xt } from '../../../lib/conjectures/strings';

  let { columns, rows, col = 1 }: { columns: string[]; rows: string[][]; col?: number } = $props();
  const plot = $derived(buildPlot(rows, col, 0));
  const alt = $derived(plot ? xt('plotAlt', {
    col: columns[col] ?? '', x: columns[0] ?? '', n: plot.points.length, min: shortValue(rows[0]?.[col]),
    max: shortValue(rows[rows.length - 1]?.[col]), log: plot.log ? xt('plotLog') : '',
  }) : '');
</script>

{#if plot}
  <figure class="xplot">
    <svg viewBox="0 0 {plot.width} {plot.height}" role="img" aria-label={alt} preserveAspectRatio="xMidYMid meet">
      <line class="axis" x1="12" y1={plot.height - 12} x2={plot.width - 12} y2={plot.height - 12} />
      <line class="axis" x1="12" y1="12" x2="12" y2={plot.height - 12} />
      {#if plot.points.length <= 400}<path class="curve" d={plot.path} />{/if}
      {#each plot.points.slice(0, 400) as p}<circle class="dot" cx={p.cx} cy={p.cy} r="2" />{/each}
    </svg>
    <figcaption class="xs muted">{columns[col]} / {columns[0]}{plot.log ? xt('plotLog') : ''}</figcaption>
  </figure>
{:else}
  <p class="xs muted">{xt('noPlot')}</p>
{/if}

<style>
  .xplot { margin: 0; max-width: 360px; width: 100%; }
  svg { width: 100%; height: auto; display: block; background: var(--surface-2); border-radius: var(--r-2); }
  .axis { stroke: var(--line-strong); stroke-width: 1; }
  .curve { fill: none; stroke: var(--accent); stroke-width: 1.5; opacity: 0.55; }
  .dot { fill: var(--accent); }
  figcaption { margin-top: 2px; }
</style>
