<script lang="ts">
  // Step 5: Hugging Face token → Goedel-Prover-V2-32B served online leads each proof (setting `hf_goedel`), paid per
  // token with Hugging Face credits, within the monthly cap of the next step.
  import { api, type ProvidersHub } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import type { SetupStatus } from '../../lib/setup/api';
  import { saveSettings } from '../settings/save';
  import ProviderKey from './ProviderKey.svelte';

  let { reload }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  let hub = $state<ProvidersHub | null>(null);
  let err = $state('');
  async function load() { try { hub = await api.providers(); err = ''; } catch (e) { err = errorText(e); } }
  void load();
  const card = $derived(hub?.cards.find((c) => c.id === 'huggingface'));
  const s = $derived(app.m.settings);
</script>

<div class="stack">
  <ul class="explain small">
    <li>{t('setup.hf.what')}</li>
    <li>{t('setup.hf.cost')}</li>
    <li>{t('setup.hf.token')}</li>
  </ul>
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  {#if card}<ul class="one"><ProviderKey c={card} onchange={() => { void load(); void reload(); }} /></ul>{/if}
  {#if s}
    <div class="opt">
      <label class="switch"><input type="checkbox" checked={Boolean(s['hf_goedel'] ?? true)} aria-describedby="h-hf" onchange={(e) => saveSettings({ hf_goedel: (e.currentTarget as HTMLInputElement).checked }, true)} />{t('adv.hf_goedel')}</label>
      <p class="hint" id="h-hf">{t('setup.hf.switchHint')}</p>
    </div>
  {/if}
  <p class="xs muted">{t('setup.optional')}</p>
</div>

<style>
  .explain { margin: 0; padding-left: 1.2rem; display: grid; gap: 4px; }
  .one { list-style: none; padding: 0; margin: 0; max-width: 560px; }
</style>
