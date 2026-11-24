<script lang="ts">
  // Réglages › Actualités (session S-AV, docs/NEWS.md): the domains followed, the sources (each with what it is, its
  // licence and its state), the user's own RSS / Atom feeds, the frequency, the French summaries, the badge.
  // Every change is saved at once (docs/UI.md §14.5); nothing here needs a « Save » button.
  import { news, type NewsSettings, type NewsSources, type NewsSource } from '../../lib/api/news';
  import { loadNewsOverview, sourceName } from '../../lib/news.svelte';
  import { app } from '../../lib/store/app.svelte';
  import { ApiError } from '../../lib/api/client';
  import { t, tk, tn, i18n, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  let s = $state<NewsSettings | null>(null);
  let meta = $state<NewsSources | null>(null);
  let url = $state('');
  let title = $state('');
  let adding = $state(false);
  let addErr = $state('');
  const lang = $derived(i18n.base);
  const local = $derived(app.m.settings?.mode === 'local');

  async function load() {
    try { [s, meta] = [(await news.settings()).settings, await news.sources()]; } catch (e) { toast('error', errorText(e)); }
  }
  $effect(() => { void load(); });

  async function save(patch: Partial<NewsSettings>) {
    if (!s) return;
    const before = s;
    s = { ...s, ...patch };                                          // optimistic
    try {
      s = (await news.patchSettings(patch)).settings;
      meta = await news.sources();
      void loadNewsOverview(true);
    } catch (e) { s = before; toast('error', errorText(e)); }
  }
  function toggleBranch(id: string, on: boolean) {
    if (!s) return;
    void save({ branches: on ? [...s.branches, id] : s.branches.filter((b) => b !== id) });
  }
  function toggleSource(src: NewsSource, on: boolean) {
    if (!s) return;
    if (src.custom) void save({ feeds: s.feeds.map((f) => (f.id === src.id ? { ...f, enabled: on } : f)) });
    else void save({ sources: { [src.id]: on } });
  }
  async function addFeed() {
    const u = url.trim();
    if (!u || adding) return;
    adding = true; addErr = '';
    try {
      const r = await news.addFeed(u, title.trim());
      s = r.settings;
      meta = await news.sources();
      url = ''; title = '';
      toast('ok', r.tested ? tn('news.set.feedAdded', r.entries) : t('news.set.feedSaved'));
    } catch (e) {
      addErr = e instanceof ApiError ? tk(`news.set.err.${e.kind}`, errorText(e)) : errorText(e);
    } finally { adding = false; }
  }
  async function removeFeed(id: string) {
    try { s = (await news.removeFeed(id)).settings; meta = await news.sources(); void loadNewsOverview(true); }
    catch (e) { toast('error', errorText(e)); }
  }
  function stateText(src: NewsSource): string {
    if (!src.enabled) return t('news.set.off');
    if (src.error) return t('news.set.stateError', { when: src.retry_at ? fmtTime(src.retry_at) : '…' });
    if (src.ok) return t('news.set.stateOk', { when: fmtTime(src.ok), n: src.items });
    return t('news.set.stateNever');
  }
  const groups = $derived((meta?.groups ?? []).map((g) => ({ ...g, sources: (meta?.sources ?? []).filter((x) => x.group === g.id) })).filter((g) => g.sources.length || g.id === 'custom'));
</script>

{#if s && meta}
  <section class="panel" aria-labelledby="ns-auto">
    <h3 id="ns-auto">{t('news.set.auto')}</h3>
    <label class="switch"><input type="checkbox" checked={s.enabled} onchange={(e) => save({ enabled: e.currentTarget.checked })} /><span>{t('news.set.enabled')}</span></label>
    <p class="hint">{local ? t('news.set.localHint') : t('news.set.enabledHint')}</p>
    <div class="grid">
      <div class="field">
        <label for="ns-freq">{t('news.set.frequency')}</label>
        <select id="ns-freq" class="input" value={String(s.interval_hours)} onchange={(e) => save({ interval_hours: Number(e.currentTarget.value) })} disabled={!s.enabled}>
          {#each [6, 12, 24, 48] as h (h)}<option value={String(h)}>{h < 24 ? t('news.set.everyH', { h }) : h === 24 ? t('news.set.daily') : t('news.set.every2d')}</option>{/each}
          {#if ![6, 12, 24, 48].includes(s.interval_hours)}<option value={String(s.interval_hours)}>{t('news.set.everyH', { h: s.interval_hours })}</option>{/if}
        </select>
      </div>
      <div class="field">
        <label for="ns-keep">{t('news.set.keep')}</label>
        <select id="ns-keep" class="input" value={String(s.keep_days)} onchange={(e) => save({ keep_days: Number(e.currentTarget.value) })}>
          {#each [7, 14, 30, 60, 90] as d (d)}<option value={String(d)}>{t('news.set.days', { d })}</option>{/each}
          {#if ![7, 14, 30, 60, 90].includes(s.keep_days)}<option value={String(s.keep_days)}>{t('news.set.days', { d: s.keep_days })}</option>{/if}
        </select>
      </div>
    </div>
    <p class="hint">{t('news.set.keepHint')}</p>
    <label class="switch"><input type="checkbox" checked={s.badge} onchange={(e) => save({ badge: e.currentTarget.checked })} /><span>{t('news.set.badge')}</span></label>
    <p class="hint">{t('news.set.badgeHint')}</p>
  </section>

  <section class="panel" aria-labelledby="ns-dom">
    <h3 id="ns-dom">{t('news.set.domains')}</h3>
    <p class="hint">{s.branches.length ? tn('news.set.domainsN', s.branches.length) : t('news.set.domainsAll')}</p>
    <ul class="branches">
      {#each meta.branches as b (b.id)}
        <li><label class="check"><input type="checkbox" checked={s.branches.includes(b.id)} onchange={(e) => toggleBranch(b.id, e.currentTarget.checked)} /><span>{lang === 'en' ? b.en : b.fr}</span></label></li>
      {/each}
    </ul>
    {#if s.branches.length}<button class="btn small quiet" onclick={() => save({ branches: [] })}>{t('news.set.domainsClear')}</button>{/if}
  </section>

  <section class="panel" aria-labelledby="ns-src">
    <h3 id="ns-src">{t('news.set.sources')}</h3>
    <p class="hint">{t('news.set.sourcesHint', { date: meta.verified })}</p>
    {#each groups as g (g.id)}
      <h4>{lang === 'en' ? g.en : g.fr}</h4>
      <ul class="sources">
        {#each g.sources as src (src.id)}
          <li>
            <label class="switch"><input type="checkbox" checked={src.enabled} onchange={(e) => toggleSource(src, e.currentTarget.checked)} /><span class="nm">{sourceName(src, lang)}</span></label>
            <div class="desc">
              {#if src.custom}<p class="small url">{src.url}</p>{:else}<p class="small">{lang === 'en' ? src.about_en : src.about_fr}</p>{/if}
              <p class="xs muted">
                {#if !src.custom}<a href={src.home} target="_blank" rel="noopener noreferrer external">{src.host}<Icon name="external" size={12} /></a> · {/if}{stateText(src)}
              </p>
              {#if src.licence}
                <details><summary class="xs">{t('news.set.terms')}</summary><p class="xs muted" lang="en">{src.licence}. {src.terms}</p></details>
              {/if}
            </div>
            {#if src.custom}<button class="btn small quiet danger" onclick={() => removeFeed(src.id)} aria-label={t('news.set.feedRemoveOf', { title: sourceName(src, lang) })}><Icon name="trash" size={14} />{t('news.set.feedRemove')}</button>{/if}
          </li>
        {/each}
      </ul>
      {#if g.id === 'custom'}
        <form class="add" onsubmit={(e) => { e.preventDefault(); void addFeed(); }}>
          <div class="field"><label for="ns-url">{t('news.set.feedUrl')}</label><input id="ns-url" class="input" type="url" inputmode="url" bind:value={url} placeholder="https://exemple.org/feed.xml" autocomplete="off" aria-describedby="ns-url-h" /></div>
          <div class="field"><label for="ns-title">{t('news.set.feedTitle')} <span class="muted">({t('common.optional')})</span></label><input id="ns-title" class="input" bind:value={title} maxlength="80" /></div>
          <button class="btn" type="submit" disabled={!url.trim() || adding}><Icon name="plus" size={16} />{adding ? t('news.set.feedAdding') : t('news.set.feedAdd')}</button>
        </form>
        <p class="hint" id="ns-url-h">{t('news.set.feedHint')}</p>
        {#if addErr}<p class="error-text" role="alert">{addErr}</p>{/if}
      {/if}
    {/each}
  </section>

  <section class="panel" aria-labelledby="ns-sum">
    <h3 id="ns-sum">{t('news.set.summaries')}</h3>
    <label class="switch"><input type="checkbox" checked={s.summaries} onchange={(e) => save({ summaries: e.currentTarget.checked })} /><span>{t('news.set.summariesOn')}</span></label>
    <p class="hint">{t('news.set.summariesHint')}</p>
  </section>

  <section class="panel privacy" aria-labelledby="ns-priv">
    <h3 id="ns-priv"><Icon name="lock" size={16} />{t('news.set.privacy')}</h3>
    <p class="small">{t('news.set.privacyText')}</p>
  </section>
{:else}
  <p class="muted">{t('common.loading')}</p>
{/if}

<style>
  h3 { margin: 0 0 var(--s-2); display: flex; align-items: center; gap: 8px; }
  h4 { margin: var(--s-4) 0 var(--s-2); font-size: var(--fs-sm); color: var(--text-2); text-transform: uppercase; letter-spacing: 0.04em; }
  .hint { margin-bottom: var(--s-3); max-width: var(--measure); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 280px)); gap: 0 var(--s-4); }
  .branches { list-style: none; margin: 0 0 var(--s-2); padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0 var(--s-3); }
  .check { display: flex; align-items: center; gap: 10px; min-height: var(--touch); cursor: pointer; }
  .check input { width: 18px; height: 18px; flex: none; accent-color: var(--accent); }
  .sources { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--s-2); }
  .sources li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0 var(--s-3); align-items: start; padding: var(--s-2) 0; border-top: 1px solid var(--line); }
  .sources .switch { grid-column: 1; }
  .nm { font-weight: 600; }
  .desc { grid-column: 1; padding-left: 52px; min-width: 0; }
  .desc p { margin: 0 0 2px; overflow-wrap: anywhere; }
  .desc a { display: inline-flex; align-items: center; gap: 3px; }
  .url { font-family: var(--font-mono); }
  .sources li > .btn { grid-column: 2; grid-row: 1; }
  details summary { cursor: pointer; color: var(--text-2); padding: 4px 0; width: fit-content; }
  .add { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) auto; gap: var(--s-3); align-items: end; margin-top: var(--s-3); }
  .add .field { margin: 0; }
  .privacy p { margin: 0; max-width: var(--measure); }
  @media (max-width: 767px) {
    .add { grid-template-columns: minmax(0, 1fr); }
    .desc { padding-left: 0; }
    .sources li { grid-template-columns: minmax(0, 1fr); }
    .sources li > .btn { grid-column: 1; grid-row: auto; justify-self: start; }
  }
  @media (pointer: coarse) { details summary { min-height: var(--touch); display: flex; align-items: center; } }
</style>
