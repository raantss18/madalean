<script lang="ts">
  import { api } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t, fmtTime, fmtBytes } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { saveSettings } from './save';
  const u = $derived(app.m.updates);
  async function check() { try { await api.checkUpdates(); if (app.m.updates) app.m.updates.checking = true; } catch (e) { toast('error', errorText(e)); } }
  async function install(key: string) { try { app.m.updates = await api.installUpdate(key); } catch (e) { toast('error', errorText(e)); } }
  async function cancel() { try { await api.cancelUpdate(); } catch (e) { toast('error', errorText(e)); } }
</script>

{#if u}
  <div class="row">
    <button class="btn primary" onclick={check} disabled={u.checking}>{u.checking ? t('updates.checking') : t('updates.check')}</button>
    <span class="small muted">{u.t ? t('updates.last', { t: fmtTime(u.t) }) : t('updates.never')}</span>
  </div>
  <label class="switch"><input type="checkbox" checked={app.m.settings?.check_updates} onchange={(e) => saveSettings({ check_updates: (e.target as HTMLInputElement).checked })} />{t('updates.weekly')}</label>
  <p class="small">{t('updates.installed', { m: u.installed.mathlib ?? '—', models: Object.entries(u.installed.models).map(([k, v]) => `${k} ${v}`).join(', ') || '—' })}</p>
  {#if u.install}
    <section class="panel" aria-live="polite">
      <h3>{t('updates.installing', { title: u.install.title })}</h3>
      <p class="small">{u.install.step_text} {u.install.progress}</p>
      <progress max="100" value={Number.parseFloat(u.install.progress) || undefined} aria-label={t('updates.progress')}></progress>
      <button class="btn" onclick={cancel}>{t('common.cancel')}</button>
      <p class="hint">{t('updates.cancelHint')}</p>
    </section>
  {/if}
  {#if u.last_result}<p class="small {u.last_result.ok ? '' : 'error-text'}" role="status">{u.last_result.text}</p>{/if}
  {#each u.errors as e}<p class="error-text small">{e}</p>{/each}
  {#if u.candidates.length}
    <ul class="cands">
      {#each u.candidates as c (c.key)}
        <li class="panel">
          <div class="row"><strong>{c.title}</strong><span class="xs muted">{c.current} → {c.latest}</span><span class="spacer"></span>
            {#if c.installable}<button class="btn small primary" disabled={Boolean(u.install)} onclick={() => install(c.key)}>{t('updates.install')}{c.size ? ` (${fmtBytes(c.size)})` : ''}</button>
            {:else}<span class="chip">{t('updates.manual')}</span>{/if}
          </div>
          {#if c.description}<p class="small">{c.description}</p>{/if}
          {#if c.note}<p class="small mono note">{c.note}</p>{/if}
        </li>
      {/each}
    </ul>
  {:else if !u.checking}<p class="muted">{t('updates.upToDate')}</p>{/if}
{/if}

<style>
  .cands { list-style: none; padding: 0; margin: var(--s-3) 0 0; display: grid; gap: var(--s-2); }
  .cands li.panel + li.panel { margin-top: 0; }
  progress { width: 100%; height: 10px; accent-color: var(--accent); }
  .note { overflow-wrap: anywhere; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); }
</style>
