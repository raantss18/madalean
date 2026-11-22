<script lang="ts">
  // « Enregistré » / « Enregistrement… » / « Non enregistré — réessai » / « Modifié ailleurs » of one Autosave (S-AK).
  import type { Autosave } from '../lib/ui/autosave.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import { errorText } from '../lib/ui/errors';
  import Icon from './Icon.svelte';

  let { state: as, onreload }: { state: Autosave; onreload?: () => void } = $props();
  const label = $derived(
    as.status === 'saving' || as.status === 'dirty' ? t('save.saving')
      : as.status === 'error' ? t('save.retry')
        : as.status === 'conflict' ? t('save.conflict')
          : t('save.saved'),
  );
</script>

<span class="save-state xs" class:warn={as.status === 'error' || as.status === 'conflict'} role="status" aria-live="polite"
  title={as.lastError ? errorText(as.lastError) : undefined} data-state={as.status}>
  {#if as.status === 'saved'}<Icon name="check" size={12} />{/if}{label}
  {#if as.status === 'conflict' && onreload}<button class="btn xsmall quiet" type="button" onclick={onreload}>{t('save.reload')}</button>{/if}
</span>

<style>
  .save-state { display: inline-flex; align-items: center; gap: 4px; color: var(--text-3); white-space: nowrap; }
  .save-state.warn { color: var(--failed); font-weight: 600; white-space: normal; }
</style>
