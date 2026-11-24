<script lang="ts">
  // Réglages → Fournisseurs (S-U): every online service Madalean can use, grouped by what it is for, with its free
  // tier (« vérifié le … »), where the data goes, and the key in two clicks. Facts come from GET /api/providers
  // (madalean/brain/hub.py, sources in docs/PROVIDERS.md).
  import { api, type ProviderCard, type ProvidersHub } from '../../lib/api/client';
  import { i18n, t, tk } from '../../lib/i18n/index.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import KeyForm from './KeyForm.svelte';

  let hub = $state<ProvidersHub | null>(null);
  let err = $state('');
  let busy = $state<string | null>(null);
  const lang = $derived(i18n.base === 'en' ? 'en' : 'fr');

  async function load() {
    try { hub = await api.providers(); err = ''; } catch (e) { err = errorText(e); }
  }
  void load();

  const byId = $derived(new Map((hub?.cards ?? []).map((c) => [c.id, c])));
  const starter = $derived((hub?.starter ?? []).map((id) => byId.get(id)).filter((c): c is ProviderCard => !!c));
  const starterDone = $derived(starter.filter((c) => c.key_set).length);

  function date(d: string): string {
    try { return new Date(d + 'T12:00:00').toLocaleDateString(lang === 'en' ? 'en-GB' : 'fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }); } catch { return d; }
  }
  function toggleId(c: ProviderCard): string | null {
    if (c.integrated === 'no' || c.integrated === 'retired' || c.kind === 'token') return null;
    if (c.key && c.key === c.id) return c.id;
    return c.id === 'keyless' || c.id === 'wikipedia' ? c.id : null;
  }
  function ownsKey(c: ProviderCard): boolean {
    return !!c.key && c.key === c.id && (c.kind === 'llm' || c.kind === 'search' || c.kind === 'token');
  }
  async function setEnabled(c: ProviderCard, on: boolean) {
    const id = toggleId(c);
    if (!id || !hub) return;
    busy = c.id;
    const cur = new Set(hub.cards.filter((x) => x.disabled).map((x) => toggleId(x)).filter((x): x is string => !!x));
    if (on) cur.delete(id); else cur.add(id);
    try { await api.patchSettings({ providers_disabled: [...cur] }); await load(); } catch (e) { err = errorText(e); } finally { busy = null; }
  }
  async function setWebSearch(on: boolean) {
    try { await api.patchSettings({ web_search: on }); await load(); } catch (e) { err = errorText(e); }
  }
  function priceLabel(c: ProviderCard): string { return t(`hub.price.${c.price}` as 'hub.price.free'); }
  function usageText(c: ProviderCard): string {
    const u = c.usage;
    if (!u || !u.searches) return '';
    const used = u.unit === 'usd' ? `${u.units.toFixed(3)} $` : String(Math.round(u.units));
    return u.free_month ? t('hub.usage', { used, free: u.unit === 'usd' ? `${u.free_month} $` : String(u.free_month), n: u.searches })
      : t('hub.usageN', { n: u.searches });
  }
  function stateText(c: ProviderCard): { level: string; text: string } | null {
    if (c.disabled) return { level: 'muted', text: t('hub.off') };
    if (!c.state || !c.key_set) return null;
    if (c.state.paused_until) return { level: 'warn', text: t('hub.paused', { reason: tk(`hub.reason.${c.state.reason}`, c.state.reason) }) };
    if (c.state.models) return { level: 'ok', text: t('hub.models', { n: c.state.models }) };
    return null;
  }
</script>

<p class="lead">{t('hub.lead')}</p>
{#if err}<p class="st error" role="alert">{err}</p>{/if}
{#if !hub && !err}<p class="muted">{t('hub.loading')}</p>{/if}

{#if hub}
  <section class="panel starter" aria-labelledby="hub-start">
    <h3 id="hub-start"><Icon name="sparkle" size={16} /> {t('hub.starterTitle')}</h3>
    <p class="small">{t('hub.starter', { names: starter.map((c) => c.name).join(', ') })}</p>
    <ol class="steps">
      {#each starter as c (c.id)}
        <li class:done={c.key_set}>
          {#if c.key_set}<Icon name="check" size={14} />{/if}
          <a href="#card-{c.id}">{c.name}</a> — <span class="muted">{c.good_for[lang]}</span>
        </li>
      {/each}
    </ol>
    <p class="xs muted">{t('hub.starterCount', { n: starterDone, total: starter.length })} · {t('hub.noKeyNeeded')}</p>
  </section>

  {#each hub.groups as g (g.id)}
    {@const cards = hub.cards.filter((c) => c.group === g.id)}
    <section class="group" aria-labelledby="grp-{g.id}">
      <h3 id="grp-{g.id}">{lang === 'en' ? g.en : g.fr}</h3>
      {#if g.id === 'web'}
        <label class="switch"><input type="checkbox" checked={hub.web_search} onchange={(e) => setWebSearch((e.currentTarget as HTMLInputElement).checked)} />
          <span>{t('hub.webSearchOn')}</span></label>
      {/if}
      <ul class="cards">
        {#each cards as c (c.id)}
          {@const tid = toggleId(c)}
          {@const st = stateText(c)}
          <li class="panel card" id="card-{c.id}" class:set={c.key_set && !c.disabled} class:off={c.disabled || c.integrated === 'retired'}>
            <div class="row head">
              <h4>{c.name}</h4>
              <span class="chip">{priceLabel(c)}</span>
              {#if c.integrated !== 'yes'}<span class="chip warnchip">{t(`hub.integrated.${c.integrated}` as 'hub.integrated.no')}</span>{/if}
              <span class="spacer"></span>
              {#if c.key_set}<span class="chip proved"><Icon name="check" size={12} />{t('keys.saved')}</span>{/if}
            </div>
            <p class="good">{c.good_for[lang]}</p>
            <p class="small"><strong>{t('hub.tier')}</strong> {c.free_tier[lang]} <span class="xs muted">({t('hub.checked', { date: date(c.checked) })})</span></p>
            {#if st}<p class="small st {st.level}">{st.text}</p>{/if}
            {#if usageText(c)}<p class="xs muted">{usageText(c)}</p>{/if}
            {#if ownsKey(c) && !c.disabled}
              <KeyForm p={{ id: c.id, name: c.name, url: c.key_url, prefix: c.prefix ? new RegExp(c.prefix) : null, paid: c.price === 'paid', search: c.kind === 'search' }} set={!!c.key_set} onchange={load} />
            {:else if c.key && c.key !== c.id}
              <p class="xs muted">{c.key_set ? t('hub.usesKeyOk', { name: byId.get(c.key)?.name ?? c.key }) : t('hub.usesKey', { name: byId.get(c.key)?.name ?? c.key })}</p>
            {/if}
            <div class="row foot">
              {#if tid}
                <label class="switch small"><input type="checkbox" checked={!c.disabled} disabled={busy === c.id} onchange={(e) => setEnabled(c, (e.currentTarget as HTMLInputElement).checked)} />
                  <span>{t('hub.use')}<span class="sr-only">{' ' + c.name}</span></span></label>
              {/if}
              <span class="spacer"></span>
            </div>
            {#if c.details[lang] || c.privacy[lang] || c.sources.length || c.models.length}
              <details>
                <summary class="small">{t('hub.more')}</summary>
                {#if c.details[lang]}<p class="small">{c.details[lang]}</p>{/if}
                {#if c.privacy[lang] && c.privacy[lang] !== '—'}<p class="small privacy">{c.privacy[lang]}</p>{/if}
                {#if c.models.length}<p class="xs muted">{t('hub.modelIds')} <code>{c.models.join(', ')}</code></p>{/if}
                {#if c.sources.length}
                  <p class="xs">{t('hub.sources', { date: date(c.checked) })}</p>
                  <ul class="src">{#each c.sources as u (u)}<li class="xs"><a href={u} target="_blank" rel="noopener noreferrer">{u.replace(/^https:\/\//, '')}</a></li>{/each}</ul>
                {/if}
              </details>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/each}

{/if}

<style>
  .lead { color: var(--text-2); max-width: var(--measure); }
  .starter { border-color: color-mix(in srgb, var(--accent) 40%, var(--line)); }
  .starter h3 { margin: 0 0 var(--s-2); display: flex; gap: 6px; align-items: center; }
  .steps { margin: 0 0 var(--s-2); padding-left: 1.3rem; }
  .steps li { margin: 2px 0; }
  .steps li.done a { color: var(--proved); }
  .group { margin-top: var(--s-5); }
  .group > h3 { font-size: var(--fs-lg); margin: 0 0 var(--s-2); }
  .cards { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-3); grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
  @media (max-width: 767px) { .cards { grid-template-columns: minmax(0, 1fr); } }
  .cards li.panel + li.panel { margin-top: 0; }
  .card { display: flex; flex-direction: column; gap: 4px; }
  .card.set { border-color: color-mix(in srgb, var(--proved) 40%, var(--line)); }
  .card.off { border-style: dashed; background: var(--surface-2); }
  .head h4 { margin: 0; font-size: var(--fs-md); }
  .card p { margin: 0; }
  .good { color: var(--text); }
  .privacy { color: var(--text-2); }
  .warnchip { background: var(--surface-2); color: var(--text-2); }
  details summary { cursor: pointer; min-height: 32px; display: flex; align-items: center; color: var(--accent); }
  .src { margin: 0; padding-left: 1rem; overflow-wrap: anywhere; }
  .st.ok { color: var(--proved); }
  .st.warn { color: var(--running); }
  .st.error { color: var(--failed); }
</style>
