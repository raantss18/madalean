<script lang="ts">
  import { toasts, dismiss, hold, release } from '../lib/ui/toasts.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import Icon from './Icon.svelte';
</script>

<!-- Two live regions: polite for info/ok, assertive for errors (WCAG 4.1.3). -->
<div class="toasts" aria-live="polite" role="status">
  {#each toasts.list.filter((x) => x.level !== 'error') as x (x.id)}
    {@render item(x)}
  {/each}
</div>
<div class="toasts err" aria-live="assertive" role="alert">
  {#each toasts.list.filter((x) => x.level === 'error') as x (x.id)}
    {@render item(x)}
  {/each}
</div>

{#snippet item(x: (typeof toasts.list)[number])}
  <div class="toast {x.level}" onmouseenter={() => hold(x.id)} onmouseleave={() => release(x.id)} onfocusin={() => hold(x.id)} onfocusout={() => release(x.id)} role="group" aria-label={x.text}>
    <span class="txt">{x.text}</span>
    {#if x.action}
      <button class="btn small" onclick={async () => { const a = x.action!; dismiss(x.id); await a.run(); }}>{x.action.label}</button>
    {/if}
    <button class="btn small quiet icon close" onclick={() => dismiss(x.id)} aria-label={t('common.close')}><Icon name="x" size={16} /></button>
  </div>
{/snippet}

<style>
  .toasts { position: fixed; z-index: 900; right: var(--s-4); bottom: var(--s-4); display: grid; gap: var(--s-2); width: min(420px, calc(100vw - 2 * var(--s-4))); pointer-events: none; }
  .toasts.err { bottom: auto; top: calc(var(--topbar-h) + var(--s-2)); }
  @media (max-width: 767px) { .toasts { bottom: calc(var(--bottomnav-h) + var(--s-2) + env(safe-area-inset-bottom)); right: var(--s-3); } }
  .toast { pointer-events: auto; display: flex; align-items: center; gap: var(--s-2); padding: var(--s-2) var(--s-2) var(--s-2) var(--s-4); background: var(--surface); color: var(--text); border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: var(--r-2); box-shadow: var(--shadow-2); font-size: var(--fs-sm); animation: in 180ms var(--ease); }
  .toast.ok { border-left-color: var(--proved); }
  .toast.warn { border-left-color: var(--running-fill); }
  .toast.error { border-left-color: var(--failed); }
  .txt { flex: 1; overflow-wrap: anywhere; }
  .close { min-height: 36px; width: 36px; }
  @keyframes in { from { transform: translateY(6px); opacity: 0; } }
</style>
