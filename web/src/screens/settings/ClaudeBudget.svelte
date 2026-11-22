<script lang="ts">
  // Claude as paid reinforcement (S-M, user decision): Claude joins a proof only after the free models failed, within
  // a cap per proof and a cap per month. Every call is estimated before it is made (list prices) and its real cost
  // (API usage) is recorded; a call that would pass a cap is refused, and the proof says so.
  import { wb, type SpendSummary } from '../../lib/api/workbench';
  import { app } from '../../lib/store/app.svelte';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { saveSettings } from './save';

  const s = $derived(app.m.settings);
  let sp = $state<SpendSummary | null>(null);
  let failed = $state(false);
  $effect(() => { void app.m.settings?.claude_cap_month_usd; wb.spend().then((r) => { sp = r; failed = false; }).catch(() => { failed = true; }); });

  const usd = (n: number) => new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: n < 0.1 && n > 0 ? 4 : 2 }).format(n);
  const pct = $derived(sp && sp.cap_month > 0 ? Math.min(100, (sp.spent_month / sp.cap_month) * 100) : 0);
  function setCap(k: 'claude_cap_proof_usd' | 'claude_cap_month_usd' | 'conductor_cap_usd', max: number, e: Event) {
    const v = Number((e.target as HTMLInputElement).value);
    if (!Number.isFinite(v) || v < 0 || v > max) { toast('error', t('settings.range', { min: 0, max })); return; }
    void saveSettings({ [k]: Math.round(v * 100) / 100 });
  }
</script>

{#if s}
  <section class="panel" aria-labelledby="claude-h">
    <h3 id="claude-h">{t('claude.title')}</h3>
    <p class="hint">{t('claude.lead')}</p>
    {#if sp && !sp.key_set}<p class="small muted">{t('claude.noKey')} <a href="/reglages/cles">{t('claude.addKey')}</a></p>{/if}
    <label class="switch"><input type="checkbox" checked={Boolean(s['claude_reinforce'] ?? true)} onchange={(e) => saveSettings({ claude_reinforce: (e.target as HTMLInputElement).checked })} />{t('claude.enable')}</label>
    <div class="grid">
      <div class="field">
        <label for="cap-proof">{t('claude.capProof')}</label>
        <div class="money"><span aria-hidden="true">$</span><input id="cap-proof" class="input" type="number" inputmode="decimal" min="0" max="100" step="0.05" value={Number(s['claude_cap_proof_usd'] ?? 1)} onchange={(e) => setCap('claude_cap_proof_usd', 100, e)} aria-describedby="cap-proof-h" /></div>
        <p class="xs muted" id="cap-proof-h">{t('claude.capProofHint')}</p>
      </div>
      <div class="field">
        <label for="cap-month">{t('claude.capMonth')}</label>
        <div class="money"><span aria-hidden="true">$</span><input id="cap-month" class="input" type="number" inputmode="decimal" min="0" max="1000" step="1" value={Number(s['claude_cap_month_usd'] ?? 20)} onchange={(e) => setCap('claude_cap_month_usd', 1000, e)} aria-describedby="cap-month-h" /></div>
        <p class="xs muted" id="cap-month-h">{t('claude.capMonthHint')}</p>
      </div>
      <div class="field">
        <label for="claude-model">{t('claude.model')}</label>
        <select id="claude-model" class="input" value={String(s['claude_model'] ?? 'auto')} onchange={(e) => saveSettings({ claude_model: (e.target as HTMLSelectElement).value })}>
          <option value="auto">{t('claude.modelAuto')}</option>
          {#each sp?.models ?? [] as m (m.key)}<option value={m.key}>{m.name}</option>{/each}
        </select>
      </div>
    </div>
    <div class="conductor" role="group" aria-labelledby="conductor-h">
      <h4 id="conductor-h">{t('conductor.title')}</h4>
      <p class="hint">{t('conductor.lead')}</p>
      <label class="switch"><input type="checkbox" checked={Boolean(s['conductor'] ?? true)} onchange={(e) => saveSettings({ conductor: (e.target as HTMLInputElement).checked })} />{t('conductor.enable')}</label>
      <div class="field">
        <label for="cap-request">{t('conductor.cap')}</label>
        <div class="money"><span aria-hidden="true">$</span><input id="cap-request" class="input" type="number" inputmode="decimal" min="0" max="100" step="0.05" value={Number(s['conductor_cap_usd'] ?? 1)} onchange={(e) => setCap('conductor_cap_usd', 100, e)} aria-describedby="cap-request-h" /></div>
        <p class="xs muted" id="cap-request-h">{t('conductor.capHint')}</p>
      </div>
    </div>
    {#if sp}
      <div class="spend" role="group" aria-labelledby="spend-h">
        <p id="spend-h" class="label">{t('claude.spentMonth', { m: sp.month })}</p>
        <p class="big"><strong>{usd(sp.spent_month)}</strong> <span class="muted small">/ {usd(sp.cap_month)}</span></p>
        <div class="bar" role="meter" aria-valuemin="0" aria-valuemax={sp.cap_month} aria-valuenow={sp.spent_month} aria-label={t('claude.spentMonth', { m: sp.month })}>
          <span style="width: {pct}%" class:high={pct >= 80}></span></div>
        <p class="xs muted">{t('claude.calls', { n: sp.calls_month })}</p>
        {#if sp.recent.length}
          <details>
            <summary class="small">{t('claude.recent')}</summary>
            <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
            <div class="table-wrap" tabindex="0" role="region" aria-label={t('claude.recent')}><table class="tbl">
              <caption class="sr-only">{t('claude.recent')}</caption>
              <thead><tr><th scope="col">{t('claude.when')}</th><th scope="col">{t('claude.colModel')}</th><th scope="col">{t('claude.tokens')}</th><th scope="col">{t('claude.cost')}</th></tr></thead>
              <tbody>{#each sp.recent as r, i (i)}<tr><td>{fmtTime(r.ts)}</td><td class="mono xs">{r.model}</td>
                <td class="xs">{t('claude.tokensRow', { i: r.tokens_in, o: r.tokens_out, c: r.cache_read })}</td><td>{usd(r.usd)}</td></tr>{/each}</tbody>
            </table></div>
          </details>
        {/if}
      </div>
    {:else if failed}<p class="xs muted">{t('claude.spendUnavailable')}</p>{/if}
  </section>
{/if}

<style>
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0 var(--s-4); margin-top: var(--s-3); }
  .money { display: flex; align-items: center; gap: 6px; }
  .money .input { max-width: 9rem; }
  .conductor { margin-top: var(--s-3); border-top: 1px solid var(--line); padding-top: var(--s-3); }
  .conductor h4 { margin: 0 0 var(--s-1); }
  .spend { margin-top: var(--s-3); border-top: 1px solid var(--line); padding-top: var(--s-3); }
  .big { margin: 0; font-size: var(--fs-xl); font-variant-numeric: tabular-nums; }
  .bar { height: 8px; background: var(--surface-3); border-radius: 999px; overflow: hidden; max-width: 28rem; margin: var(--s-2) 0; }
  .bar span { display: block; height: 100%; background: var(--proved); }
  .bar span.high { background: var(--running-fill); }
  .table-wrap { overflow-x: auto; }
  .tbl { border-collapse: collapse; width: 100%; font-size: var(--fs-sm); }
  .tbl th, .tbl td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }
</style>
