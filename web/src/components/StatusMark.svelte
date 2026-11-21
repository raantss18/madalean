<script lang="ts">
  // The status glyph family, after the end-of-proof mark ∎: filled = proved, drawing = running,
  // dotted = queued, struck = failed, open = draft, half = stopped. Text label always present (not colour alone).
  import type { Phase } from '../lib/status';
  import { tk } from '../lib/i18n/index.svelte';
  let { phase, size = 14, showLabel = false }: { phase: Phase; size?: number; showLabel?: boolean } = $props();
  const label = $derived(tk(`phase.${phase}`, phase));
</script>

<span class="mark {phase}" title={showLabel ? undefined : label}>
  <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
    {#if phase === 'proved'}
      <rect x="2" y="2" width="12" height="12" rx="1" fill="currentColor" />
    {:else if phase === 'failed'}
      <rect x="2.75" y="2.75" width="10.5" height="10.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" />
      <path d="M3.5 12.5l9-9" stroke="currentColor" stroke-width="1.5" />
    {:else if phase === 'running'}
      <rect class="draw" x="2.75" y="2.75" width="10.5" height="10.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" pathLength="40" />
      <rect class="fill" x="5" y="5" width="6" height="6" fill="currentColor" />
    {:else if phase === 'queued'}
      <rect x="2.75" y="2.75" width="10.5" height="10.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 2" />
    {:else if phase === 'stopped'}
      <rect x="2.75" y="2.75" width="10.5" height="10.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" />
      <rect x="3" y="8" width="10" height="5" fill="currentColor" opacity="0.55" />
    {:else}
      <rect x="2.75" y="2.75" width="10.5" height="10.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" />
    {/if}
  </svg>
  {#if showLabel}<span class="lbl">{label}</span>{:else}<span class="sr-only">{label}</span>{/if}
</span>

<style>
  .mark { display: inline-flex; align-items: center; gap: 6px; flex: none; line-height: 1; }
  .lbl { font-size: var(--fs-xs); font-weight: 650; }
  .proved { color: var(--proved); }
  .failed { color: var(--failed); }
  .running { color: var(--running); }
  .queued, .draft, .stopped { color: var(--queued); }
  .draw { stroke-dasharray: 30 10; animation: draw 1.6s linear infinite; }
  .fill { animation: pulse 1.6s ease-in-out infinite; transform-origin: 8px 8px; }
  @keyframes draw { to { stroke-dashoffset: -40; } }
  @keyframes pulse { 0%, 100% { opacity: 0.35; transform: scale(0.7); } 50% { opacity: 1; transform: scale(1); } }
  @media (prefers-reduced-motion: reduce) { .draw, .fill { animation: none; } }
</style>
