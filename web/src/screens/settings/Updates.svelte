<script lang="ts">
  // Updates (ARCHITECTURE §16): automatic installs at a quiet moment (or « ask first »), the list with progress,
  // Madalean's own signed self-update with rollback, the re-verification of proven results after a library update
  // (« à revérifier » / regressed), and system components with « open a terminal with the command » (host only).
  import { api } from '../../lib/api/client';
  import { research, type RecheckReport, type SelfUpdate } from '../../lib/api/research';
  import type { UpdateCandidate } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime, fmtBytes } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText, isHostOnly } from '../../lib/ui/errors';
  import { saveSettings } from './save';
  import HostLock from './HostLock.svelte';
  import Icon from '../../components/Icon.svelte';

  const u = $derived(app.m.updates);
  const local = $derived(app.m.local);
  let self = $state<SelfUpdate | null>(null);
  let recheck = $state<{ running: boolean; report: RecheckReport | null } | null>(null);
  let copied = $state('');
  async function loadSelf() { try { self = await research.selfupdate(); } catch { /* older server */ } }
  async function loadRecheck() { try { recheck = await research.recheck(); } catch { /* older server */ } }
  $effect(() => { void loadSelf(); void loadRecheck(); });
  $effect(() => app.on('selfupdate.status', (ev) => { self = (ev as unknown as { selfupdate: SelfUpdate }).selfupdate; }));
  $effect(() => app.on('updates.recheck', () => void loadRecheck()));
  $effect(() => app.on('updates.auto', (ev) => { const e = ev as unknown as { key: string; latest: string; error?: string }; if (e.error) toast('error', t('updates.autoFailed', { key: e.key, e: e.error })); }));

  async function check() { try { await api.checkUpdates(); if (app.m.updates) app.m.updates.checking = true; } catch (e) { toast('error', errorText(e)); } }
  async function install(key: string) { try { app.m.updates = await api.installUpdate(key); } catch (e) { toast('error', errorText(e)); } }
  async function cancel() { try { await api.cancelUpdate(); } catch (e) { toast('error', errorText(e)); } }
  async function selfAction(fn: () => Promise<SelfUpdate | unknown>, ok: string) {
    try { const r = await fn(); if (r && typeof r === 'object' && 'version' in r) self = r as SelfUpdate; toast('ok', ok); }
    catch (e) { toast(isHostOnly(e) ? 'warn' : 'error', isHostOnly(e) ? t('settings.hostOnly') : errorText(e)); }
  }
  async function terminal(c: UpdateCandidate) {
    const comp = c.key.replace(/^system:/, '');
    try { const r = await research.systemTerminal(comp); toast('ok', t('updates.terminalOpened', { term: r.terminal })); }
    catch (e) {
      const cmd = (c.spec as { command?: string }).command ?? '';
      toast('warn', `${errorText(e)}${cmd ? ' — ' + t('updates.copyInstead') : ''}`);
    }
  }
  async function copy(cmd: string) { try { await navigator.clipboard.writeText(cmd); copied = cmd; } catch { toast('info', cmd); } }
  const system = $derived((u?.candidates ?? []).filter((c) => c.kind === 'system'));
  const others = $derived((u?.candidates ?? []).filter((c) => c.kind !== 'system'));
</script>

{#if u}
  <section class="panel">
    <h3>{t('updates.autoTitle')}</h3>
    {#if !local}<HostLock />{/if}
    <label class="switch"><input type="checkbox" checked={Boolean(app.m.settings?.['updates_auto'] ?? true)} disabled={!local}
      onchange={(e) => saveSettings({ updates_auto: (e.target as HTMLInputElement).checked })} />{t('updates.auto')}</label>
    <p class="hint">{t('updates.autoHint')}</p>
    <label class="switch"><input type="checkbox" checked={app.m.settings?.check_updates} onchange={(e) => saveSettings({ check_updates: (e.target as HTMLInputElement).checked })} />{t('updates.weekly')}</label>
    <div class="row">
      <button class="btn primary" onclick={check} disabled={u.checking}>{u.checking ? t('updates.checking') : t('updates.check')}</button>
      <span class="small muted">{u.t ? t('updates.last', { t: fmtTime(u.t) }) : t('updates.never')}</span>
    </div>
    <p class="small">{t('updates.installed', { m: u.installed.mathlib ?? '—', models: Object.entries(u.installed.models).map(([k, v]) => `${k} ${v}`).join(', ') || '—' })}</p>
  </section>

  {#if u.tracked}
    {@const tr = u.tracked}
    <section class="panel" aria-labelledby="tr-h">
      <h3 id="tr-h">{t('tracked.title')}</h3>
      <p class="hint">{t('tracked.hint', { d: tr.every_days })}</p>
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <div class="table-wrap" tabindex="0" role="region" aria-labelledby="tr-h">
        <table class="tracked">
          <thead><tr><th scope="col">{t('tracked.component')}</th><th scope="col">{t('tracked.current')}</th><th scope="col">{t('tracked.latest')}</th><th scope="col">{t('tracked.policy')}</th></tr></thead>
          <tbody>
            {#each tr.components as c (c.id)}
              <tr><th scope="row">{tk(`tracked.${c.id}`, c.id)}</th>
                <td class="mono xs">{c.current || (c.state === 'on_demand' ? t('tracked.onDemand') : '—')}</td>
                <td class="xs">{#if c.pending}<span class="chip">{c.latest}</span>{:else}{t('tracked.upToDate')}{/if}</td>
                <td class="xs muted">{tk(`tracked.policy.${c.policy}`, c.policy)}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="xs muted">{tr.last_check ? t('updates.last', { t: fmtTime(tr.last_check) }) : t('updates.never')}{#if tr.next_check} · {t('tracked.next', { t: fmtTime(tr.next_check) })}{/if}</p>
    </section>
  {/if}

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

  <section class="panel">
    <h3>{t('updates.listTitle')}</h3>
    {#if others.length}
      <ul class="cands">
        {#each others as c (c.key)}
          <li>
            <div class="row"><strong>{c.title}</strong><span class="xs muted">{c.current || '—'} → {c.latest}</span><span class="spacer"></span>
              {#if c.installable}<button class="btn small primary" disabled={Boolean(u.install) || !local} onclick={() => install(c.key)}>{t('updates.install')}{c.size ? ` (${fmtBytes(c.size)})` : ''}</button>
              {:else}<span class="chip">{t('updates.notifyOnly')}</span>{/if}
            </div>
            {#if c.description}<p class="small">{c.description}</p>{/if}
            {#if c.note}<p class="small muted">{c.note}</p>{/if}
            {#if (c.spec as { release_notes?: string }).release_notes}<a class="small" href={(c.spec as { release_notes: string }).release_notes} target="_blank" rel="noopener noreferrer">{t('updates.notes')}</a>{/if}
            {#if (c.spec as { rebuild?: string[] }).rebuild?.length}<p class="xs muted">{t('updates.rebuild', { p: (c.spec as { rebuild: string[] }).rebuild.join(', ') })}</p>{/if}
          </li>
        {/each}
      </ul>
    {:else if !u.checking}<p class="muted small">{t('updates.upToDate')}</p>{/if}
  </section>

  {#if recheck?.report && typeof recheck.report.total === 'number'}
    {@const r = { ...recheck.report, regressed: recheck.report.regressed ?? [] }}
    <section class="panel" aria-labelledby="rc-h">
      <h3 id="rc-h">{t('updates.recheckTitle')}</h3>
      <p class="small">{recheck.running ? t('updates.recheckRunning', { ok: r.ok, total: r.total }) : t('updates.recheckDone', { ok: r.ok, total: r.total, ws: r.workspace })}</p>
      {#if r.regressed.length}
        <ul class="regressed">
          {#each r.regressed as x}<li><span class="chip failed">{t('recheck.regressed')}</span> <a href="/d/{encodeURIComponent(x.dossier)}">{x.name}</a> <span class="small muted">{x.summary}</span></li>{/each}
        </ul>
      {/if}
      <button class="btn small" onclick={() => research.startRecheck().then(() => toast('info', t('updates.recheckStarted'))).catch((e) => toast('error', errorText(e)))} disabled={recheck.running}>{t('updates.recheckNow')}</button>
    </section>
  {/if}

  <section class="panel" aria-labelledby="su-h">
    <h3 id="su-h">{t('updates.selfTitle')}</h3>
    {#if self}
      <p class="small">{t('updates.selfVersion', { v: self.version })}{self.available ? ` · ${t('updates.selfAvailable', { v: self.available.version })}` : ''}</p>
      {#if !self.managed_install}<p class="small muted">{t('updates.selfUnmanaged')}</p>{/if}
      {#if self.pending_restart}<p class="small notice">{t('updates.selfPending')}</p>{/if}
      <div class="row">
        <button class="btn small" onclick={() => selfAction(research.selfupdateCheck, t('updates.selfChecked'))} disabled={!local || self.busy}>{t('updates.check')}</button>
        {#if self.available}<button class="btn small primary" onclick={() => selfAction(research.selfupdateInstall, t('updates.selfInstalling'))} disabled={!local || self.busy || !self.managed_install}>{t('updates.selfInstall', { v: self.available.version })}</button>{/if}
        {#if self.pending_restart}<button class="btn small primary" onclick={() => selfAction(research.selfupdateRestart, t('updates.selfRestarting'))} disabled={!local}>{t('updates.selfRestart')}</button>{/if}
        {#if self.previous}<button class="btn small" onclick={() => selfAction(research.selfupdateRollback, t('updates.selfRolledBack'))} disabled={!local || self.busy}>{t('updates.selfRollback', { v: self.previous })}</button>{/if}
      </div>
      <p class="xs muted">{t('updates.selfSigned')}</p>
    {:else}<p class="muted small">{t('updates.selfUnavailable')}</p>{/if}
  </section>

  {#if system.length}
    <section class="panel" aria-labelledby="sys-h">
      <h3 id="sys-h">{t('updates.systemTitle')}</h3>
      <p class="hint">{t('updates.systemLead')}</p>
      <ul class="cands">
        {#each system as c (c.key)}
          {@const cmd = (c.spec as { command?: string }).command ?? ''}
          <li>
            <div class="row"><strong>{c.title}</strong><span class="xs muted">{c.current || '—'} → {c.latest}</span></div>
            {#if cmd}<pre class="cmd">{cmd}</pre>{/if}
            <div class="row">
              {#if local}<button class="btn small" onclick={() => terminal(c)}><Icon name="terminal" size={14} />{t('updates.openTerminal')}</button>{/if}
              {#if cmd}<button class="btn small quiet" onclick={() => copy(cmd)}>{copied === cmd ? t('draft.copied') : t('draft.copy')}</button>{/if}
            </div>
          </li>
        {/each}
      </ul>
      {#if !local}<HostLock text={t('updates.terminalHost')} />{/if}
    </section>
  {/if}
{/if}

<style>
  .panel h3 { margin: 0 0 var(--s-2); }
  .cands { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-2); }
  .cands > li { border-top: 1px solid var(--line); padding-top: var(--s-2); }
  .cands > li:first-child { border-top: 0; padding-top: 0; }
  progress { width: 100%; height: 10px; accent-color: var(--accent); }
  .cmd { font: 0.8125rem/1.45 var(--font-mono); background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); white-space: pre-wrap; overflow-wrap: anywhere; }
  .regressed { padding-left: 1.2em; }
  .table-wrap { overflow-x: auto; }
  .tracked { border-collapse: collapse; width: 100%; font-size: var(--fs-sm); }
  .tracked th, .tracked td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }
  .notice { background: var(--running-soft); color: var(--running); padding: 4px 8px; border-radius: var(--r-1); }
</style>
