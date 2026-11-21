<script lang="ts">
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { api } from '../../lib/api/client';
  import { saveSettings } from './save';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText, isHostOnly } from '../../lib/ui/errors';
  import HostLock from './HostLock.svelte';
  const ws = $derived(app.m.system?.workspaces ?? []);
  const cur = $derived(app.m.settings?.workspace ?? '');
  let rescanning = $state(false);
  let locked = $state(false);
  async function rescan() {
    rescanning = true;
    try { await api.repair('workspaces'); const s = await api.system(); app.m.system = s; toast('ok', t('workspaces.rescanned')); }
    catch (e) { if (isHostOnly(e)) locked = true; else toast('error', errorText(e)); } finally { rescanning = false; }
  }
</script>

<p class="lead">{t('workspaces.lead')}</p>
{#if locked || !app.m.local}<HostLock text={t('workspaces.rescanHost')} />{/if}
<fieldset class="list">
  <legend class="label">{t('workspaces.default')}</legend>
  {#each ws as w (w.key)}
    <label class="ws" class:sel={cur === w.key}>
      <input type="radio" name="ws" value={w.key} checked={cur === w.key} disabled={!w.ready} onchange={() => saveSettings({ workspace: w.key })} />
      <span>
        <strong>{w.label}</strong> <span class="chip {w.ready ? 'proved' : 'failed'}">{w.ready ? t('workspaces.ready') : t('workspaces.notReady')}</span>
        <span class="xs muted mono">{w.toolchain} · {w.path}</span>
        {#if w.description}<span class="small">{w.description}</span>{/if}
        {#each w.problems as p}<span class="error-text small">{p}</span>{/each}
      </span>
    </label>
  {:else}<p class="muted">{t('workspaces.none')}</p>{/each}
</fieldset>
{#if app.m.local}<button class="btn" onclick={rescan} disabled={rescanning}>{t('workspaces.rescan')}</button>{/if}

<style>
  .lead { color: var(--text-2); }
  .list { border: 0; padding: 0; margin: 0 0 var(--s-4); display: grid; gap: var(--s-2); }
  .ws { display: flex; gap: var(--s-3); padding: var(--s-3); border: 1px solid var(--line); border-radius: var(--r-2); cursor: pointer; }
  .ws.sel { border-color: var(--accent); background: var(--accent-soft); }
  .ws input { width: 18px; height: 18px; margin-top: 4px; flex: none; }
  .ws > span { display: grid; gap: 2px; min-width: 0; }
  .mono { overflow-wrap: anywhere; }
</style>
