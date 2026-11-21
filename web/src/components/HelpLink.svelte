<script lang="ts">
  // Contextual help: opens the matching page of the manual (docs/manual, rendered by the Aide screen).
  import { t } from '../lib/i18n/index.svelte';
  import Icon from './Icon.svelte';
  let { page, anchor = '' }: { page: string; anchor?: string } = $props();
</script>

<a class="help" href="/aide/{page}{anchor ? `#${anchor}` : ''}" title={t('help.open')}>
  <Icon name="info" size={16} /><span>{t('help.short')}</span>
</a>

<style>
  .help { display: inline-flex; align-items: center; gap: 4px; min-height: 32px; padding: 0 8px; border-radius: 999px; color: var(--text-2); text-decoration: none; font-size: var(--fs-xs); font-weight: 600; border: 1px solid var(--line); }
  .help:hover { color: var(--accent); border-color: var(--accent); }
  @media (pointer: coarse) { .help { min-height: 44px; } }
</style>
