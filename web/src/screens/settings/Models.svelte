<script lang="ts">
  import { api } from '../../lib/api/client';
  import { ROLES, type LeaderboardRow, type ModelRef } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtBytes, fmtDuration } from '../../lib/i18n/index.svelte';
  import { providerName } from '../../lib/status';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import { saveSettings } from './save';

  const s = $derived(app.m.settings);
  const m = $derived(app.m.models);
  let refreshing = $state(false);
  let openRole = $state<string | null>(null);
  $effect(() => { api.models().then((r) => { app.m.models = r; }).catch(() => {}); });
  let board = $state<LeaderboardRow[] | null>(null);
  $effect(() => { api.leaderboard().then((r) => { board = r.entries; }).catch(() => { board = []; }); });
  const boardRows = $derived((board ?? []).filter((r) => !r.domain).slice(0, 12));
  async function resetBoard() {
    if (!confirm(t('board.resetConfirm'))) return;
    try { board = (await api.resetLeaderboard()).entries; toast('ok', t('board.resetDone')); } catch (e) { toast('error', errorText(e)); }
  }
  function nameOf(key: string): string {
    for (const r of Object.values(m?.roles ?? {})) { const c = r.candidates.find((x) => x.key === key); if (c) return c.name; }
    return key.split(':').slice(1).join(':') || key;
  }

  async function refresh() {
    refreshing = true;
    try { app.m.models = await api.refreshModels(); toast('ok', t('models.refreshed')); } catch (e) { toast('error', errorText(e)); } finally { refreshing = false; }
  }
  async function unload() {
    try { await api.stopLocal(); toast('ok', t('models.unloaded')); } catch (e) { toast('error', errorText(e)); }
  }
  function choose(role: string, key: string) { void saveSettings({ prefer: { [role]: key } }); }
  function why(c: ModelRef, i: number): string {
    if (c.why) return c.why;
    const bits = [c.local ? t('models.whyLocal') : t('models.whyOnline'), c.paid ? t('models.paid') : t('models.free')];
    return `${t('models.rank', { n: i + 1 })} · ${bits.join(' · ')}`;
  }
</script>

{#if s && m}
  <div class="stack">
    <fieldset class="panel">
      <legend class="label">{t('settings.mode')}</legend>
      <div class="choices">
        {#each ['local', 'auto', 'online'] as v}
          <label class="choice" class:sel={s.mode === v}>
            <input type="radio" name="mode" value={v} checked={s.mode === v} onchange={() => saveSettings({ mode: v })} />
            <span><strong>{tk(`mode.${v}`, v)}</strong><span class="small muted">{tk(`mode.${v}.desc`, '')}</span></span>
          </label>
        {/each}
      </div>
    </fieldset>

    <fieldset class="panel">
      <legend class="label">{t('settings.strategy')}</legend>
      <div class="choices">
        {#each ['auto', 'agent', 'goedel'] as v}
          <label class="choice" class:sel={s.prove_strategy === v}>
            <input type="radio" name="strategy" value={v} checked={s.prove_strategy === v} onchange={() => saveSettings({ prove_strategy: v })} />
            <span><strong>{tk(`strategy.${v}`, v)}</strong><span class="small muted">{tk(`strategy.${v}.desc`, '')}</span></span>
          </label>
        {/each}
      </div>
    </fieldset>

    <section class="panel" aria-labelledby="roles-h">
      <h3 id="roles-h">{t('models.perRole')}</h3>
      <p class="hint">{t('models.perRoleHint')}</p>
      <ul class="roles">
        {#each ROLES as role}
          {@const r = m.roles[role]}
          {@const pref = s.prefer?.[role] ?? ''}
          <li>
            <div class="role-row">
              <label for="role-{role}"><strong>{tk(`role.${role}`, role)}</strong><span class="xs muted">{tk(`role.${role}.desc`, '')}</span></label>
              <select id="role-{role}" class="input" value={pref} onchange={(e) => choose(role, (e.target as HTMLSelectElement).value)}>
                <option value="">{t('models.auto', { first: r?.candidates[0]?.name ?? '—' })}</option>
                {#each r?.candidates ?? [] as c (c.key)}<option value={c.key}>{c.name} — {providerName(c.provider)}{c.paid ? ` (${t('models.paid')})` : ''}</option>{/each}
              </select>
              <button class="btn small quiet" aria-expanded={openRole === role} onclick={() => (openRole = openRole === role ? null : role)}>{t('models.why')}</button>
            </div>
            {#if openRole === role}
              <ol class="ranking">
                {#each (r?.candidates ?? []).slice(0, 8) as c, i (c.key)}
                  <li><span class="chip {c.local ? 'local' : 'online'}">{c.local ? t('privacy.here') : providerName(c.provider)}</span> <strong>{c.name}</strong> <span class="xs muted">{why(c, i)}</span></li>
                {:else}<li class="muted small">{t('models.noCandidate')}</li>{/each}
              </ol>
            {/if}
          </li>
        {/each}
      </ul>
    </section>

    <section class="panel" aria-labelledby="board-h">
      <div class="row"><h3 id="board-h">{t('board.title')}</h3><span class="spacer"></span>
        {#if app.m.local && board?.length}<button class="btn small quiet" onclick={resetBoard}>{t('board.reset')}</button>{/if}
      </div>
      <p class="hint">{t('board.hint')}</p>
      {#if boardRows.length}
        <div class="table-wrap">
          <table class="board">
            <caption class="sr-only">{t('board.title')}</caption>
            <thead><tr><th scope="col">{t('board.model')}</th><th scope="col">{t('board.task')}</th><th scope="col">{t('board.solved')}</th>
              <th scope="col">{t('board.score')}</th><th scope="col">{t('board.attempts')}</th><th scope="col">{t('board.time')}</th></tr></thead>
            <tbody>
              {#each boardRows as r (r.model + r.task)}
                <tr><th scope="row" class="mono xs">{nameOf(r.model)}</th><td>{tk(`board.task.${r.task}`, r.task)}</td>
                  <td>{r.solved}/{r.tasks}{#if r.pauses >= 1} <span class="xs muted">({t('board.pauses', { n: Math.round(r.pauses) })})</span>{/if}</td>
                  <td>{Math.round(r.score * 100)}</td><td>{r.mean_attempts ?? '—'}</td><td>{r.mean_seconds != null ? fmtDuration(r.mean_seconds) : '—'}</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else if board}<p class="muted small">{t('board.empty')}</p>{/if}
    </section>

    <section class="panel" aria-labelledby="local-h">
      <div class="row"><h3 id="local-h">{t('models.local')}</h3><span class="spacer"></span>
        <button class="btn small" onclick={refresh} disabled={refreshing}><Icon name="refresh" size={14} />{t('models.rescan')}</button>
        {#if m.local?.state === 'ready'}<button class="btn small" onclick={unload}>{t('models.unload')}</button>{/if}
      </div>
      <p class="small">{tk(`localstate.${m.local?.state ?? 'stopped'}`, m.local?.state ?? '')}{#if m.local?.model} — <span class="mono">{m.local.model}</span>{/if}{#if m.local?.offload} · {t('models.offload', { o: m.local.offload })}{/if}</p>
      {#if m.local_files.length}
        <ul class="files">{#each m.local_files as f}<li class="small"><span class="mono">{f.file}</span> <span class="muted xs">{f.quant ?? ''} {fmtBytes(f.size ?? 0)}</span>{#if f.error}<span class="error-text xs"> {f.error}</span>{/if}</li>{/each}</ul>
      {:else}<p class="muted small">{t('models.noLocal')}</p>{/if}
    </section>

    <details class="panel">
      <summary><strong>{t('models.advanced')}</strong></summary>
      <div class="adv">
        {#each [['prove_attempts', 1, 64], ['translate_attempts', 1, 10], ['compile_timeout_s', 10, 1800], ['agent_max_steps', 1, 200], ['agent_max_seconds', 30, 7200], ['tournament_contestants', 1, 6], ['tournament_max_rounds', 0, 10], ['tournament_max_minutes', 1, 240], ['tournament_attempts_per_model', 1, 16]] as [k, min, max]}
          <div class="field">
            <label for="adv-{k}">{tk(`adv.${k}`, String(k))}</label>
            <input id="adv-{k}" class="input" type="number" min={min} max={max} value={s[k as string] as number}
              onchange={(e) => { const v = Number((e.target as HTMLInputElement).value); if (v >= (min as number) && v <= (max as number)) void saveSettings({ [k as string]: v }); else toast('error', t('settings.range', { min: Number(min), max: Number(max) })); }} />
          </div>
        {/each}
        {#each ['tournament_enabled', 'pause_after_translation', 'statement_notes', 'informal_proof', 'autoload_model'] as k}
          <label class="switch"><input type="checkbox" checked={Boolean(s[k])} onchange={(e) => saveSettings({ [k]: (e.target as HTMLInputElement).checked })} />{tk(`adv.${k}`, k)}</label>
        {/each}
      </div>
    </details>
  </div>
{:else}
  <p class="muted" aria-busy="true">{t('common.loading')}</p>
{/if}

<style>
  fieldset.panel { margin: 0; }
  legend { padding: 0 4px; }
  .choices { display: grid; gap: var(--s-2); grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
  .choice { display: flex; gap: var(--s-2); align-items: flex-start; padding: var(--s-3); border: 1px solid var(--line); border-radius: var(--r-2); cursor: pointer; }
  .choice.sel { border-color: var(--accent); background: var(--accent-soft); }
  .choice input { margin-top: 4px; width: 18px; height: 18px; flex: none; }
  .choice span { display: grid; gap: 2px; }
  .roles { list-style: none; padding: 0; margin: 0; }
  .roles > li { border-bottom: 1px solid var(--line); padding: var(--s-2) 0; }
  .role-row { display: grid; grid-template-columns: minmax(10rem, 1fr) minmax(0, 1.6fr) auto; gap: var(--s-2); align-items: center; }
  .role-row label { display: grid; }
  @media (max-width: 767px) { .role-row { grid-template-columns: minmax(0, 1fr); } }
  .ranking { margin: var(--s-2) 0 0; padding-left: 1.4em; display: grid; gap: 4px; font-size: var(--fs-sm); }
  .files { list-style: none; padding: 0; margin: 0; }
  .table-wrap { overflow-x: auto; }
  .board { border-collapse: collapse; width: 100%; font-size: var(--fs-sm); }
  .board th, .board td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }
  .board thead th { font-weight: 600; }
  .adv { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0 var(--s-4); margin-top: var(--s-3); }
  summary { cursor: pointer; min-height: var(--touch); display: flex; align-items: center; }
</style>
