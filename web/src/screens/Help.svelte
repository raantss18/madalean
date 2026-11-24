<script lang="ts">
  // Aide: the manual of docs/manual (same texts as the website), sections in order, search, anchors that match the
  // site (heading ids from index.json, never re-slugified).
  import { i18n, t } from '../lib/i18n/index.svelte';
  import { navigate, route } from '../lib/router.svelte';
  import { loadManual, searchManual, rewriteLink, imageUrl, type ManualIndex } from '../lib/manual';
  import { renderTrusted } from '../lib/md';                // KaTeX + its CSS load on the first formula (S-AP)

  let { params }: { params: Record<string, string> } = $props();
  let idx = $state<ManualIndex | null>(null);
  let err = $state('');
  let q = $state('');
  let article: HTMLElement | undefined = $state();
  $effect(() => { loadManual().then((m) => (idx = m)).catch((e) => (err = String(e))); });
  const pages = $derived(idx ? idx.pages.filter((p) => p.lang === i18n.lang) : []);
  const pageId = $derived(params['page'] || 'index');
  const page = $derived(pages.find((p) => p.id === pageId) ?? pages[0]);
  const html = $derived(page && idx ? renderTrusted(page.body, {
    headingIds: page.headings.map((h) => h.id),
    link: (h) => rewriteLink(idx!, i18n.lang, h),
    image: imageUrl,
  }) : '');
  const results = $derived(idx && q.trim() ? searchManual(idx, i18n.lang, q).slice(0, 12) : []);
  $effect(() => {
    // Scroll to the anchor of the URL once the page is rendered.
    void html;
    const hash = decodeURIComponent(location.hash.slice(1));
    queueMicrotask(() => requestAnimationFrame(() => {
      const el = hash ? document.getElementById(hash) : null;
      if (el) el.scrollIntoView({ block: 'start' });
      else window.scrollTo({ top: 0 });
    }));
  });
  void route;
</script>

<div class="help">
  <nav class="toc" aria-label={t('help.contents')}>
    <h1>{t('help.title')}</h1>
    <label class="sr-only" for="hq">{t('help.search')}</label>
    <input id="hq" class="input" type="search" placeholder={t('help.search')} bind:value={q} />
    {#if q.trim()}
      <ul class="res" aria-live="polite">
        {#each results as r (r.page.id)}
          <li><a href="/aide/{r.page.id}{r.heading ? `#${r.heading.id}` : ''}" onclick={() => (q = '')}><strong>{r.page.title}</strong>{#if r.heading}<span class="xs"> › {r.heading.text}</span>{/if}<span class="xs muted">{r.page.summary}</span></a></li>
        {:else}<li class="muted small">{t('help.none')}</li>{/each}
      </ul>
    {:else if idx}
      {#each idx.sections[i18n.lang] ?? [] as s (s.id)}
        {@const ps = pages.filter((p) => p.section === s.id)}
        {#if ps.length}
          <h2 class="sec">{s.title}</h2>
          <ul>{#each ps as p (p.id)}<li><a href="/aide/{p.id}" aria-current={page?.id === p.id ? 'page' : undefined}>{p.title}</a></li>{/each}</ul>
        {/if}
      {/each}
    {/if}
  </nav>
  <article bind:this={article} class="page" aria-live="off">
    {#if err}<p class="error-text">{t('help.error')}</p>
    {:else if !page}<p class="muted" aria-busy="true">{t('common.loading')}</p>
    {:else}
      {#if page.audience !== 'all'}<p class="chip">{t(page.audience === 'learner' ? 'help.learner' : 'help.researcher')}</p>{/if}
      <div class="md manual">{@html html}</div>
      <p class="xs muted src">{t('help.source', { src: `docs/manual/${page.source}` })} · <a href="{idx?.site_url}{page.site_path}" target="_blank" rel="noopener noreferrer">{t('help.onSite')}</a></p>
      <button class="btn small quiet" onclick={() => navigate(`/aide/${pages[(pages.indexOf(page) + 1) % pages.length]?.id ?? 'index'}`)}>{t('common.next')}</button>
    {/if}
  </article>
</div>

<style>
  .help { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--s-6); max-width: 1200px; }
  @media (max-width: 900px) { .help { grid-template-columns: minmax(0, 1fr); } .toc { order: 2; } }
  .toc { position: sticky; top: calc(var(--topbar-h) + 8px); align-self: start; max-height: calc(100dvh - var(--topbar-h) - 24px); overflow: auto; }
  @media (max-width: 900px) { .toc { position: static; max-height: none; } }
  .toc h1 { font-size: var(--fs-lg); }
  .toc ul { list-style: none; padding: 0; margin: 0 0 var(--s-2); }
  .toc a { display: block; padding: 5px 8px; border-radius: var(--r-1); text-decoration: none; color: var(--text-2); font-size: var(--fs-sm); }
  @media (pointer: coarse) { .toc a { display: flex; align-items: center; min-height: var(--touch); } }
  .toc a[aria-current='page'] { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
  .sec { font: 700 var(--fs-xs) var(--font-ui); color: var(--text-3); margin: var(--s-3) 0 4px; }
  .res a { display: grid; gap: 2px; padding: 6px 8px; }
  .page { max-width: var(--measure); min-width: 0; }
  .manual { font-size: 1.0625rem; line-height: 1.7; }
  .manual :global(h1) { font-size: var(--fs-2xl); }
  .manual :global(h2) { margin-top: var(--s-5); }
  .manual :global([id]) { scroll-margin-top: calc(var(--topbar-h) + 16px); }
  .manual :global(img) { max-width: 100%; border: 1px solid var(--line); border-radius: var(--r-2); }
  .manual :global(table) { border-collapse: collapse; display: block; overflow-x: auto; }
  .manual :global(th), .manual :global(td) { border: 1px solid var(--line); padding: 4px 8px; }
  .manual :global(pre.code) { background: var(--surface-2); padding: var(--s-3); border-radius: var(--r-2); overflow-x: auto; font-size: 0.875rem; }
  .src { margin-top: var(--s-5); }
</style>
