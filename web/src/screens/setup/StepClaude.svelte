<script lang="ts">
  // Step 6: Claude (Anthropic key, paid per use) as conductor and paid reinforcement, and its caps: per request
  // (`conductor_cap_usd`, 1 $; reached → Madalean asks before going on, +0.50 $), per proof (`claude_cap_proof_usd`)
  // and per month (`claude_cap_month_usd`, every paid call: Claude and Goedel 32B). Caps are saved as they change.
  import { api, type ProvidersHub } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { toast } from '../../lib/ui/toasts.svelte';
  import type { SetupStatus } from '../../lib/setup/api';
  import { saveSettings } from '../settings/save';
  import ProviderKey from './ProviderKey.svelte';

  let { reload }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  let hub = $state<ProvidersHub | null>(null);
  let err = $state('');
  async function load() { try { hub = await api.providers(); err = ''; } catch (e) { err = errorText(e); } }
  void load();
  const card = $derived(hub?.cards.find((c) => c.id === 'anthropic'));
  const s = $derived(app.m.settings);
  type Cap = 'conductor_cap_usd' | 'claude_cap_proof_usd' | 'claude_cap_month_usd';
  const CAPS: { k: Cap; label: 'conductor.cap' | 'claude.capProof' | 'claude.capMonth'; hint: 'setup.claude.capRequestHint' | 'claude.capProofHint' | 'claude.capMonthHint'; max: number; step: number; def: number }[] = [
    { k: 'conductor_cap_usd', label: 'conductor.cap', hint: 'setup.claude.capRequestHint', max: 100, step: 0.05, def: 1 },
    { k: 'claude_cap_proof_usd', label: 'claude.capProof', hint: 'claude.capProofHint', max: 100, step: 0.05, def: 1 },
    { k: 'claude_cap_month_usd', label: 'claude.capMonth', hint: 'claude.capMonthHint', max: 1000, step: 1, def: 20 },
  ];
  function setCap(k: Cap, max: number, e: Event) {
    const v = Number((e.target as HTMLInputElement).value);
    if (!Number.isFinite(v) || v < 0 || v > max) { toast('error', t('settings.range', { min: 0, max })); return; }
    void saveSettings({ [k]: Math.round(v * 100) / 100 }, true);
  }
</script>

<div class="stack">
  <ul class="explain small">
    <li>{t('setup.claude.conductor')}</li>
    <li>{t('setup.claude.reinforce')}</li>
    <li>{t('setup.claude.paid')}</li>
  </ul>
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  {#if card}<ul class="one"><ProviderKey c={card} onchange={() => { void load(); void reload(); }} /></ul>{/if}
  {#if s}
    <section class="panel" aria-labelledby="c-caps">
      <h2 id="c-caps">{t('setup.claude.caps')}</h2>
      <div class="caps">
        {#each CAPS as c (c.k)}
          <div class="field">
            <label for="wiz-{c.k}">{t(c.label)}</label>
            <div class="money"><span aria-hidden="true">$</span><input id="wiz-{c.k}" class="input" type="number" inputmode="decimal" min="0" max={c.max} step={c.step}
              value={Number(s[c.k] ?? c.def)} onchange={(e) => setCap(c.k, c.max, e)} aria-describedby="wiz-{c.k}-h" /></div>
            <p class="xs muted" id="wiz-{c.k}-h">{t(c.hint)}</p>
          </div>
        {/each}
      </div>
      <label class="switch"><input type="checkbox" checked={Boolean(s['claude_reinforce'] ?? true)} onchange={(e) => saveSettings({ claude_reinforce: (e.currentTarget as HTMLInputElement).checked }, true)} />{t('claude.enable')}</label>
      <p class="hint">{t('setup.claude.noKeyNoCost')}</p>
    </section>
  {/if}
  <p class="xs muted">{t('setup.optional')}</p>
</div>

<style>
  .explain { margin: 0; padding-left: 1.2rem; display: grid; gap: 4px; }
  .one { list-style: none; padding: 0; margin: 0; max-width: 560px; }
  .caps { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0 var(--s-4); }
  .money { display: flex; align-items: center; gap: 6px; }
  .money .input { max-width: 9rem; }
</style>
