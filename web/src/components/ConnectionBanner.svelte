<script lang="ts">
  import { app } from '../lib/store/app.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import Icon from './Icon.svelte';
  // Show nothing while connected; first connection gets a grace period to avoid a flash.
  const st = $derived(app.conn.state);
  const show = $derived(st === 'offline' || (st === 'reconnecting' && app.conn.everOpen) || (st === 'reconnecting' && app.conn.attempt > 1));
</script>

{#if show}
  <div class="banner" class:offline={st === 'offline'} role="status">
    <Icon name="wifiOff" size={16} />
    <span>{st === 'offline' ? t('conn.offline') : t('conn.lost', { s: Math.max(1, Math.round(app.conn.nextInMs / 1000)) })}</span>
    <button class="btn small" onclick={() => app.reconnect()}>{t('conn.retry')}</button>
  </div>
{/if}

<style>
  .banner { display: flex; align-items: center; gap: var(--s-2); justify-content: center; flex-wrap: wrap; padding: 6px var(--s-3); background: var(--running-soft); color: var(--running); font-size: var(--fs-sm); font-weight: 600; border-bottom: 1px solid var(--line); }
  .banner.offline { background: var(--surface-2); color: var(--text-2); }
</style>
