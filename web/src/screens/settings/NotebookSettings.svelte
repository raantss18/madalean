<script lang="ts">
  // Host-only switches that open the machine: Jupyter from paired devices, agent code execution, LAN listener.
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { saveSettings } from './save';
  import HostLock from './HostLock.svelte';
  const s = $derived(app.m.settings);
  const locked = $derived(!app.m.local);
</script>

{#if s}
  {#if locked}<HostLock />{/if}
  <p class="small">{t('nbset.status', { s: tk(`jupyter.${app.m.jupyter?.state ?? 'stopped'}`, '') })} · <a href="/carnet">{t('nbset.open')}</a></p>
  {#each ['remote_jupyter', 'agent_exec', 'experiments_remote', 'experiments_auto', 'lan_listener'] as k}
    <div class="opt">
      <label class="switch"><input type="checkbox" checked={Boolean(s[k])} disabled={locked} aria-describedby="h-{k}" onchange={(e) => saveSettings({ [k]: (e.target as HTMLInputElement).checked })} />{tk(`nbset.${k}`, k)}</label>
      <p class="hint" id="h-{k}">{tk(`nbset.${k}.hint`, '')}</p>
    </div>
  {/each}
  {#if s.lan_listener}
    <div class="field" style="max-width: 12rem">
      <label for="lanp">{t('nbset.lanPort')}</label>
      <input id="lanp" class="input" type="number" min="1024" max="65535" value={s.lan_port} disabled={locked} onchange={(e) => saveSettings({ lan_port: Number((e.target as HTMLInputElement).value) })} />
    </div>
    <p class="hint">{t('nbset.restart')}</p>
  {/if}
{/if}

<style>.opt { margin-bottom: var(--s-3); } .opt .hint { margin-left: 52px; }</style>
