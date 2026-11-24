<script lang="ts">
  // One provider in the assistant: what it is good for, its free tier, where to get the key, and the key itself
  // through Réglages' KeyForm (paste → « Enregistrer la clé » saves it on the host and tests it; never autosaved,
  // never shown again). A key already saved can be tested again with « Tester » (POST /api/models/test or
  // /api/search/test: the same tests as Réglages › Fournisseurs).
  import { api, type ProviderCard } from '../../lib/api/client';
  import { i18n, t, tk, tn } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import KeyForm from '../settings/KeyForm.svelte';

  let { c, onchange }: { c: ProviderCard; onchange: () => void } = $props();
  const lang = $derived(i18n.base === 'en' ? 'en' : 'fr');
  let test = $state<{ level: 'busy' | 'ok' | 'warn' | 'error'; text: string } | null>(null);

  async function retest() {
    test = { level: 'busy', text: t('keys.testing') };
    try {
      if (c.kind === 'search') {
        const r = await api.testSearchKey(c.id);
        test = r.ok === null ? { level: 'warn', text: t('keys.localMode') } : r.ok ? { level: 'ok', text: t('hub.searchWorks') }
          : { level: 'error', text: t('keys.refused', { reason: tk(`hub.reason.${r.reason ?? ''}`, r.reason ?? '') }) };
        return;
      }
      const r = await api.testKey(c.id);
      const reason = (r.reason ?? '').split(':')[0] ?? '';
      test = r.ok === true ? { level: 'ok', text: r.models ? tn('keys.worksN', r.models) : t('keys.works') }
        : r.ok === null ? { level: 'warn', text: reason === 'local_mode' ? t('keys.localMode') : tk(`keys.reason.${reason}`, r.reason ?? '') }
        : { level: 'error', text: t('keys.refused', { reason: tk(`keys.reason.${reason}`, r.reason ?? '') }) };
    } catch (e) { test = { level: 'error', text: errorText(e) }; }
  }
</script>

<li class="panel card" class:set={c.key_set} id="wiz-card-{c.id}">
  <div class="row head">
    <h3>{c.name}</h3>
    <span class="chip">{tk(`hub.price.${c.price}`, c.price)}</span>
    <span class="spacer"></span>
    {#if c.key_set}<span class="chip proved">{t('keys.saved')}</span>{/if}
  </div>
  <p class="small">{c.good_for[lang]}</p>
  <p class="small"><strong>{t('hub.tier')}</strong> {c.free_tier[lang]}</p>
  {#if c.key_url}<p class="xs muted">{t('setup.keys.where')} <a href={c.key_url} target="_blank" rel="noopener noreferrer">{c.key_url.replace(/^https:\/\//, '')}</a></p>{/if}
  <KeyForm p={{ id: c.id, name: c.name, url: c.key_url, prefix: c.prefix ? new RegExp(c.prefix) : null, paid: c.price === 'paid', search: c.kind === 'search' }} set={!!c.key_set} {onchange} />
  {#if c.key_set}
    <div class="row"><button class="btn small" onclick={retest} disabled={test?.level === 'busy'}>{t('setup.keys.test')}<span class="sr-only"> {c.name}</span></button></div>
    <p class="small st {test?.level ?? ''}" role="status" aria-live="polite">{test?.text ?? ''}</p>
  {/if}
</li>

<style>
  .card { display: flex; flex-direction: column; gap: 4px; list-style: none; }
  .card.set { border-color: color-mix(in srgb, var(--proved) 40%, var(--line)); }
  .card p { margin: 0; }
  .head h3 { margin: 0; font-size: var(--fs-md); }
  .st:empty { display: none; }
  a { overflow-wrap: anywhere; }
</style>
