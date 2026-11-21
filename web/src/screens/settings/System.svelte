<script lang="ts">
  // System health with one-click repairs (host only for repairs), GPU and disk.
  import { api } from '../../lib/api/client';
  import type { HealthCheck, SystemInfo } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText, isHostOnly } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import HostLock from './HostLock.svelte';

  let sys = $state<SystemInfo | null>(null);
  let busy = $state('');
  let locked = $state(!app.m.local);
  async function load() { try { sys = await api.system(); } catch (e) { toast('error', errorText(e)); } }
  $effect(() => { void load(); });
  const monitor = $derived(app.m.system?.monitor ?? sys?.monitor);
  async function repair(c: HealthCheck) {
    busy = c.id;
    try { const r = await api.repair(c.repair); toast('ok', t('system.repaired', { what: tk(`check.${c.id}`, c.id) }) + (r['names'] ? ` (${r['names']})` : '')); await load(); }
    catch (e) { if (isHostOnly(e)) locked = true; toast('error', errorText(e)); } finally { busy = ''; }
  }
</script>

{#if locked}<HostLock text={t('system.repairHost')} />{/if}
{#if monitor}
  <section class="panel">
    <h3>{t('system.machine')}</h3>
    {#if monitor.gpu}
      <p class="small">{t('system.gpu', { name: monitor.gpu.name, used: (monitor.gpu.used / 1024).toFixed(1), total: (monitor.gpu.total / 1024).toFixed(1), temp: monitor.gpu.temp, util: monitor.gpu.util })}</p>
      <meter min="0" max={monitor.gpu.total} value={monitor.gpu.used} aria-label={t('system.vram')}></meter>
    {:else}<p class="small muted">{monitor.gpu_error || t('system.noGpu')}</p>{/if}
    {#each monitor.disk as d}<p class="small">{t('system.disk', { path: d.path, free: d.free_gb.toFixed(0), total: d.total_gb.toFixed(0) })}</p>{/each}
  </section>
{/if}
<section class="panel">
  <div class="row"><h3>{t('system.health')}</h3><span class="spacer"></span><button class="btn small" onclick={load}><Icon name="refresh" size={14} />{t('system.recheck')}</button></div>
  {#if !sys}<p class="muted">{t('common.loading')}</p>
  {:else}
    <ul class="checks">
      {#each sys.checks ?? [] as c (c.id)}
        <li class:ok={c.ok} class:warn={!c.ok}>
          <Icon name={c.ok ? 'check' : 'warn'} size={16} label={c.ok ? t('system.ok') : t('system.problem')} />
          <span class="txt"><strong>{tk(`check.${c.id}`, c.id)}</strong><span class="small">{c.message?.text}</span></span>
          {#if !c.ok && c.repair}<button class="btn small primary" disabled={busy === c.id || locked} onclick={() => repair(c)}>{busy === c.id ? t('system.repairing') : t('system.repair')}</button>{/if}
        </li>
      {/each}
    </ul>
    {#if sys.brain === 'fake'}<p class="small">{t('system.fakeBrain')}</p>{/if}
  {/if}
</section>

<style>
  h3 { margin: 0 0 var(--s-2); }
  meter { width: 100%; height: 10px; }
  .checks { list-style: none; padding: 0; margin: 0; }
  .checks li { display: flex; gap: var(--s-3); align-items: center; padding: var(--s-2) 0; border-bottom: 1px solid var(--line); }
  .checks li.ok > :global(.ico) { color: var(--proved); }
  .checks li.warn > :global(.ico) { color: var(--running); }
  .txt { flex: 1; display: grid; min-width: 0; overflow-wrap: anywhere; }
</style>
