<script lang="ts">
  // The discreet « Entrée pour envoyer · Maj+Entrée pour aller à la ligne » under a sending field (S-AK, §14.3).
  // `inline`: a span for a row of buttons (no layout shift when it shows).
  import { t } from '../lib/i18n/index.svelte';
  let { id = '', action = 'send', inline = false }: { id?: string; action?: 'send' | 'run' | 'check'; inline?: boolean } = $props();
</script>

{#if inline}<span class="enter-hint xs" {id}>{t(`enter.${action}`)}</span>
{:else}<p class="enter-hint xs" {id}>{t(`enter.${action}`)}</p>{/if}

<style>
  .enter-hint { margin: 2px 0 0; color: var(--text-3); }
  span.enter-hint { margin: 0; }
  @media (pointer: coarse) { .enter-hint { display: none; } }
</style>
