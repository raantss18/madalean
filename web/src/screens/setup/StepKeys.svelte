<script lang="ts">
  // Step 4: free keys of online providers (GET /api/providers: the same facts as Réglages › Fournisseurs). The three
  // « bon départ » providers first, the others folded; Hugging Face and Anthropic have their own steps.
  import { api, type ProvidersHub } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import type { SetupStatus } from '../../lib/setup/api';
  import Icon from '../../components/Icon.svelte';
  import ProviderKey from './ProviderKey.svelte';

  let { reload }: { status: SetupStatus | null; reload: (refresh?: boolean) => Promise<void> } = $props();
  let hub = $state<ProvidersHub | null>(null);
  let err = $state('');
  async function load() { try { hub = await api.providers(); err = ''; } catch (e) { err = errorText(e); } }
  void load();
  function changed() { void load(); void reload(); }
  const OWN_STEP = new Set(['huggingface', 'anthropic', 'github']);
  const owns = (c: ProvidersHub['cards'][number]) => !!c.key && c.key === c.id && (c.kind === 'llm' || c.kind === 'search')
    && c.integrated !== 'no' && c.integrated !== 'retired' && !OWN_STEP.has(c.id);
  const starter = $derived((hub?.starter ?? []).map((id) => hub!.cards.find((c) => c.id === id)).filter((c) => !!c && owns(c)));
  const others = $derived((hub?.cards ?? []).filter((c) => owns(c) && !(hub?.starter ?? []).includes(c.id)));
  const done = $derived(starter.filter((c) => c!.key_set).length);
</script>

<div class="stack">
  <p class="small note"><Icon name="lock" size={14} /> {t('setup.keys.privacy')}</p>
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  {#if !hub && !err}<p class="muted" aria-busy="true">{t('setup.loading')}</p>{/if}
  {#if hub}
    <section aria-labelledby="k-start">
      <h2 id="k-start">{t('setup.keys.starter')}</h2>
      <p class="hint">{t('setup.keys.starterHint', { n: done, total: starter.length })}</p>
      <ul class="cards">{#each starter as c (c!.id)}<ProviderKey c={c!} onchange={changed} />{/each}</ul>
    </section>
    <details class="panel">
      <summary><strong>{t('setup.keys.others', { n: others.length })}</strong></summary>
      <ul class="cards more">{#each others as c (c.id)}<ProviderKey {c} onchange={changed} />{/each}</ul>
      <p class="xs muted"><a href="/reglages/fournisseurs">{t('setup.keys.allInSettings')}</a></p>
    </details>
  {/if}
</div>

<style>
  h2 { font-size: var(--fs-lg); margin: 0 0 var(--s-1); }
  .note { display: flex; gap: 6px; align-items: flex-start; color: var(--text-2); background: var(--surface-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); margin: 0; }
  .cards { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-3); grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
  .cards :global(li.panel + li.panel) { margin-top: 0; }
  .more { margin-top: var(--s-3); }
  summary { cursor: pointer; min-height: var(--touch); display: flex; align-items: center; }
  @media (max-width: 767px) { .cards { grid-template-columns: minmax(0, 1fr); } }
</style>
