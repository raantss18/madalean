<script lang="ts">
  import { t } from '../../lib/i18n/index.svelte';
  import Icon from '../../components/Icon.svelte';
  let { text = '' }: { text?: string } = $props();
</script>

<p class="lock small" role="note"><Icon name="lock" size={16} /><span>{text || t('settings.hostOnly')}</span></p>

<style>
  .lock { display: flex; gap: 8px; align-items: flex-start; background: var(--surface-2); border: 1px solid var(--line); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); color: var(--text-2); }
</style>
