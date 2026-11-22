<script lang="ts">
  // The discreet « Entrée pour envoyer · Maj+Entrée pour aller à la ligne » under a sending field (S-AK, §14.3).
  import { t } from '../lib/i18n/index.svelte';
  let { id = '', action = 'send' }: { id?: string; action?: 'send' | 'run' | 'check' } = $props();
</script>

<p class="enter-hint xs" {id}>{t(`enter.${action}`)}</p>

<style>
  .enter-hint { margin: 2px 0 0; color: var(--text-3); }
  @media (pointer: coarse) { .enter-hint { display: none; } }
</style>
