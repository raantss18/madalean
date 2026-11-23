<script lang="ts">
  // « Actualités » (session S-AV, docs/NEWS.md, docs/UI.md §17): what is new in mathematics — papers by domain, open
  // problems, Lean / Mathlib, AI for maths, announcements — read from the server's local store (so it works offline).
  // Everything shown here came from the web: titles and abstracts go through the safe Markdown renderer (no HTML, no
  // images), links open outside, and an item is only ever sent to a project by an explicit action of the user.
  import { app } from '../../lib/store/app.svelte';
  import { api, ApiError } from '../../lib/api/client';
  import { research } from '../../lib/api/research';
  import { news, type NewsItem, type NewsQuery, type NewsSources, type NewsSource } from '../../lib/api/news';
  import { newsBadge, loadNewsOverview, setNewsUnread, sourceName } from '../../lib/news.svelte';
  import { currentProjectId } from '../../lib/project.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, tn, tk, i18n, fmtTime } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';
  import Md from '../../components/LazyMd.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();

  interface Filters { q: string; branch: string; source: string; unread: boolean; saved: boolean; open: boolean; projects: boolean; mine: boolean }
  const saved0 = loadJSON<Partial<Filters>>('news.filters', {});
  let f = $state<Filters>({ branch: '', source: '', unread: false, saved: false, open: false, projects: false, mine: false, ...saved0, q: '' });
  const PAGE = 30;
  let items = $state<NewsItem[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let failed = $state('');
  let meta = $state<NewsSources | null>(null);
  let opened = $state<Record<number, boolean>>({});
  let busy = $state<Record<string, boolean>>({});
  let refreshing = $state(false);
  let live = $state('');

  const lang = $derived(i18n.lang);
  const byId = $derived(new Map((meta?.sources ?? []).map((s) => [s.id, s] as const)));
  const branchName = (id: string) => { const b = meta?.branches.find((x) => x.id === id); return b ? (lang === 'en' ? b.en : b.fr) : id; };
  const groups = $derived((meta?.groups ?? []).map((g) => ({ ...g, sources: (meta?.sources ?? []).filter((s) => s.group === g.id && s.enabled) })).filter((g) => g.sources.length));
  const project = $derived(app.m.projects[currentProjectId()]);
  const ov = $derived(newsBadge.overview);
  const local = $derived((ov?.mode ?? app.m.settings?.mode) === 'local' && !ov?.demo);
  const anyFilter = $derived(Boolean(f.q || f.branch || f.source || f.unread || f.saved || f.open || f.projects || f.mine));

  function query(offset = 0): NewsQuery {
    const src = f.source.startsWith('g:') ? { group: f.source.slice(2) } : f.source ? { source: f.source } : {};
    return { q: f.q.trim(), branch: f.branch, ...src, unread: f.unread, saved: f.saved, open: f.open, projects: f.projects, mine: f.mine,
      order: f.projects && !f.q.trim() ? 'relevance' : 'date', limit: PAGE, offset };
  }

  let ctl: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  async function load(more = false) {
    ctl?.abort();
    ctl = new AbortController();
    loading = true; failed = '';
    try {
      const r = await news.list(query(more ? items.length : 0), ctl.signal);
      items = more ? [...items, ...r.items.filter((x) => !items.some((y) => y.id === x.id))] : r.items;
      total = r.total;
      setNewsUnread(r.unread);
      live = tn('news.count', r.total);
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      failed = errorText(e);
    } finally { loading = false; }
  }
  // Filters are live: a change reloads (the search waits for a pause in typing).
  $effect(() => {
    const { q: _q, ...rest } = f;
    saveJSON('news.filters', rest);
    void JSON.stringify(f);
    clearTimeout(timer);
    timer = setTimeout(() => void load(), 180);
    return () => clearTimeout(timer);
  });
  $effect(() => {
    void loadNewsOverview(true);
    news.sources().then((m) => { meta = m; }).catch(() => {});
    return app.on('news.updated', () => { if (!Object.values(opened).some(Boolean)) void load(); });
  });

  function ago(ts: number): string {
    const s = Date.now() / 1000 - ts;
    if (s < 0 || s > 6 * 86400) return new Intl.DateTimeFormat(lang, { day: 'numeric', month: 'short', year: s > 300 * 86400 ? 'numeric' : undefined }).format(new Date(ts * 1000));
    const rtf = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' });
    if (s < 3600) return rtf.format(-Math.max(1, Math.round(s / 60)), 'minute');
    if (s < 86400) return rtf.format(-Math.round(s / 3600), 'hour');
    return rtf.format(-Math.round(s / 86400), 'day');
  }
  function authors(it: NewsItem): string {
    if (!it.authors.length) return '';
    return it.authors.length <= 4 ? it.authors.join(', ') : t('news.authorsMore', { first: it.authors.slice(0, 3).join(', '), n: it.authors.length - 3 });
  }
  const srcTitle = (it: NewsItem) => sourceName(byId.get(it.source), lang, it.source);
  const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; } };
  const projTitle = (pid: string) => app.m.projects[pid]?.title ?? '';

  function patchLocal(it: NewsItem) { items = items.map((x) => (x.id === it.id ? it : x)); }
  async function flag(it: NewsItem, p: { read?: boolean; saved?: boolean }) {
    patchLocal({ ...it, ...p });                                    // optimistic
    try { const r = await news.patchItem(it.id, p); patchLocal(r.item); setNewsUnread(r.unread); }
    catch (e) { patchLocal(it); toast('error', errorText(e)); }
  }
  function toggle(it: NewsItem) {
    opened[it.id] = !opened[it.id];
    if (opened[it.id] && !it.read) void flag(it, { read: true });
  }
  async function refresh() {
    refreshing = true;
    try {
      const r = await news.refresh();
      const bad = (r.sources ?? []).filter((s) => s.status === 'error').length;
      toast(bad ? 'info' : 'ok', bad ? t('news.refreshedSome', { n: r.new ?? 0, bad }) : tn('news.refreshed', r.new ?? 0));
      await Promise.all([load(), loadNewsOverview(true), news.sources().then((m) => { meta = m; })]);
    } catch (e) {
      toast('error', e instanceof ApiError && e.kind === 'local_mode' ? t('news.localNote') : errorText(e));
    } finally { refreshing = false; }
  }
  async function readAll() {
    try {
      const r = await news.readAll(query());
      setNewsUnread(r.unread);
      toast('ok', tn('news.marked', r.marked));
      await load();
    } catch (e) { toast('error', errorText(e)); }
  }
  async function summarize(it: NewsItem) {
    busy[`s${it.id}`] = true;
    try { patchLocal((await news.summarize(it.id)).item); }
    catch (e) { toast('error', e instanceof ApiError ? tk(`news.err.${e.kind}`, errorText(e)) : errorText(e)); }
    finally { busy[`s${it.id}`] = false; }
  }

  // ---- send to the project (explicit actions; the text becomes the user's own material there)
  const excerpt = (it: NewsItem, n = 1500) => (it.summary.length > n ? `${it.summary.slice(0, n - 1)}…` : it.summary);
  const cite = (it: NewsItem) => `${srcTitle(it)} — ${it.url}`;
  async function act(it: NewsItem, kind: 'source' | 'conjecture' | 'dossier' | 'note') {
    const pid = currentProjectId();
    const k = `${kind}${it.id}`;
    busy[k] = true;
    try {
      if (kind === 'source') {
        const r = await research.addByIdentifier(pid, `arXiv:${it.extra.arxiv}`);
        toast('ok', r.duplicate ? t('news.did.sourceDup') : t('news.did.source', { project: project?.title ?? '' }),
          { action: { label: t('news.open'), run: () => navigate('/sources') } });
      } else if (kind === 'conjecture') {
        const r = await research.createConjecture({ project_id: pid, statement: `${it.title}\n\n${excerpt(it)}`.trim(), motivation: cite(it),
          title: it.title.slice(0, 80), origin: { kind: 'news', key: it.key, url: it.url } });
        toast('ok', t('news.did.conjecture'), { action: { label: t('news.open'), run: () => navigate(`/conjectures/${encodeURIComponent(r.conjecture.id)}`) } });
      } else if (kind === 'dossier') {
        const r = await api.createDossier({ problem: `${it.title}\n\n${excerpt(it)}\n\n(${cite(it)})`.trim(), title: it.title.slice(0, 80), project_id: pid || undefined, start: false });
        app.m.full[r.dossier.id] = r.dossier;
        toast('ok', t('news.did.dossier'), { action: { label: t('news.open'), run: () => navigate(`/d/${encodeURIComponent(r.dossier.id)}/enonce`) } });
      } else {
        const body = [`> ${excerpt(it, 3000).replace(/\n+/g, '\n> ')}`, '', `— ${[authors(it), `[${srcTitle(it)}](${it.url})`, new Intl.DateTimeFormat(lang, { dateStyle: 'long' }).format(new Date(it.published * 1000))].filter(Boolean).join(', ')}`,
          ...(it.fr ? ['', `**${t('news.autoSummary')}** ${it.fr}`] : [])].join('\n');
        const r = await research.createNote(pid, it.title.slice(0, 120), body, ['actualités']);
        toast('ok', t('news.did.note'), { action: { label: t('news.open'), run: () => navigate(`/notes/${encodeURIComponent(r.note.id)}`) } });
      }
      if (!it.saved) void flag(it, { saved: true });
    } catch (e) {
      toast('error', e instanceof ApiError && e.kind === 'local_mode' ? t('news.err.sourceLocal') : errorText(e));
    } finally { busy[k] = false; }
  }
  function clearFilters() { f = { q: '', branch: '', source: '', unread: false, saved: false, open: false, projects: false, mine: false }; }
  const status = (s: NewsSource | undefined) => (s?.error ? t('news.sourceError') : '');
</script>

<div class="news">
  <header class="head">
    <div class="row"><h1 id="news-h">{t('news.title')}</h1><HelpLink page="news" /></div>
    <p class="lead">{t('news.lead')}</p>
    <div class="row bar">
      <p class="when small muted" aria-live="off">
        {#if ov?.demo}{t('news.demoNote')}
        {:else if local}<Icon name="wifiOff" size={14} /> {t('news.localNote')}
        {:else if ov && !ov.enabled}{t('news.offNote')}
        {:else if ov?.last_refresh}{t('news.updatedAt', { when: fmtTime(ov.last_refresh) })}{#if ov.next_refresh} · {t('news.nextAt', { when: fmtTime(Math.max(ov.next_refresh, Date.now() / 1000)) })}{/if}
        {:else if ov}{t('news.never')}{/if}
      </p>
      <span class="spacer"></span>
      <button class="btn small" onclick={refresh} disabled={refreshing || local} title={local ? t('news.localNote') : undefined}>
        <Icon name="refresh" size={14} />{refreshing ? t('news.refreshing') : t('news.refresh')}
      </button>
      <a class="btn small quiet" href="/reglages/actualites"><Icon name="sliders" size={14} />{t('news.settings')}</a>
    </div>
  </header>

  <section class="filters" aria-label={t('news.filters')}>
    <div class="search">
      <label class="sr-only" for="news-q">{t('news.search')}</label>
      <Icon name="search" size={16} />
      <input id="news-q" class="input" type="search" bind:value={f.q} placeholder={t('news.searchPh')} autocomplete="off" />
    </div>
    <div class="selects">
      <label class="sr-only" for="news-branch">{t('news.branch')}</label>
      <select id="news-branch" class="input" bind:value={f.branch}>
        <option value="">{t('news.allBranches')}</option>
        {#each meta?.branches ?? [] as b (b.id)}<option value={b.id}>{lang === 'en' ? b.en : b.fr}</option>{/each}
      </select>
      <label class="sr-only" for="news-source">{t('news.source')}</label>
      <select id="news-source" class="input" bind:value={f.source}>
        <option value="">{t('news.allSources')}</option>
        {#each groups as g (g.id)}
          <optgroup label={lang === 'en' ? g.en : g.fr}>
            {#if g.sources.length > 1}<option value={`g:${g.id}`}>{t('news.allOf', { group: lang === 'en' ? g.en : g.fr })}</option>{/if}
            {#each g.sources as s (s.id)}<option value={s.id}>{sourceName(s, lang)}</option>{/each}
          </optgroup>
        {/each}
      </select>
    </div>
    <div class="toggles" role="group" aria-label={t('news.show')}>
      <button class="tog" aria-pressed={f.unread} onclick={() => (f.unread = !f.unread)}>{t('news.f.unread')}{#if newsBadge.unread}<span class="n">{newsBadge.unread}</span>{/if}</button>
      <button class="tog" aria-pressed={f.mine} onclick={() => (f.mine = !f.mine)} disabled={!ov?.branches.length} title={!ov?.branches.length ? t('news.f.mineNone') : undefined}>{t('news.f.mine')}</button>
      <button class="tog" aria-pressed={f.open} onclick={() => (f.open = !f.open)}>{t('news.f.open')}</button>
      <button class="tog" aria-pressed={f.projects} onclick={() => (f.projects = !f.projects)}>{t('news.f.projects')}</button>
      <button class="tog" aria-pressed={f.saved} onclick={() => (f.saved = !f.saved)}><Icon name="bookmark" size={14} />{t('news.f.saved')}</button>
    </div>
  </section>

  <p class="sr-only" role="status" aria-live="polite">{live}</p>
  <div class="row count">
    <p class="small muted">{loading && !items.length ? t('common.loading') : tn('news.count', total)}</p>
    <span class="spacer"></span>
    {#if anyFilter}<button class="btn small quiet" onclick={clearFilters}><Icon name="x" size={14} />{t('news.clear')}</button>{/if}
    {#if items.some((x) => !x.read)}<button class="btn small quiet" onclick={readAll}><Icon name="check" size={14} />{t('news.readAll')}</button>{/if}
  </div>

  {#if failed}<p class="error-text" role="alert">{failed}</p>{/if}

  {#if !loading && !items.length && !failed}
    <div class="empty panel">
      {#if anyFilter}<p>{t('news.emptyFiltered')}</p><button class="btn small" onclick={clearFilters}>{t('news.clear')}</button>
      {:else if local}<p>{t('news.emptyLocal')}</p>
      {:else}<p>{t('news.empty')}</p><button class="btn small primary" onclick={refresh} disabled={refreshing}><Icon name="refresh" size={14} />{t('news.refresh')}</button>{/if}
    </div>
  {/if}

  <ul class="list" aria-labelledby="news-h">
    {#each items as it (it.id)}
      {@const isOpen = Boolean(opened[it.id])}
      <li class="item" class:unread={!it.read} class:open={isOpen}>
        <article aria-labelledby="nt-{it.id}">
          <h2 class="title" id="nt-{it.id}">
            <button class="disc" aria-expanded={isOpen} aria-controls="nb-{it.id}" onclick={() => toggle(it)}>
              {#if !it.read}<span class="dot" aria-hidden="true"></span><span class="sr-only">{t('news.unreadMark')} </span>{/if}
              <span class="tt"><Md inline src={it.title} /></span>
              <span class="chev"><Icon name={isOpen ? 'chevronUp' : 'chevronDown'} size={16} /></span>
            </button>
          </h2>
          <p class="meta small">
            <span class="src" title={status(byId.get(it.source))}>{srcTitle(it)}</span>
            <span aria-hidden="true">·</span> <time datetime={new Date(it.published * 1000).toISOString()}>{ago(it.published)}</time>
            {#if it.authors.length}<span aria-hidden="true">·</span> <span class="auth">{authors(it)}</span>{/if}
          </p>
          <p class="tags">
            {#if it.open}<span class="chip running">{t('news.openProblem')}</span>{/if}
            {#each it.branches as b (b)}<button class="chip br" onclick={() => (f.branch = f.branch === b ? '' : b)} aria-pressed={f.branch === b} title={t('news.filterBranch', { branch: branchName(b) })}>{branchName(b)}</button>{/each}
            {#each it.projects.slice(0, 2) as m (m.project)}{#if projTitle(m.project)}<span class="chip proved" title={t('news.why', { terms: m.terms.join(', ') })}>{t('news.forProject', { project: projTitle(m.project) })}</span>{/if}{/each}
            {#if it.saved}<span class="chip"><Icon name="bookmark" size={12} />{t('news.savedMark')}</span>{/if}
            {#if it.fr && !isOpen}<span class="chip">{t('news.hasSummary')}</span>{/if}
          </p>
          {#if !isOpen && it.summary}<p class="peek small">{it.fr || it.summary}</p>{/if}

          {#if isOpen}
            <div class="body" id="nb-{it.id}">
              {#if it.extra.suspect}<p class="warn small"><Icon name="warn" size={14} /> {t('news.suspect')}</p>{/if}
              {#if it.fr}
                <div class="fr">
                  <p class="lbl xs">{t('news.autoSummary')} <span class="muted">— {t('news.autoSummaryBy', { model: it.fr_model === 'demo' ? t('news.demoModel') : it.fr_model })}</span></p>
                  <Md src={it.fr} />
                </div>
                <p class="lbl xs">{t('news.original')}</p>
              {/if}
              {#if it.summary}<div class="abs"><Md src={it.summary} /></div>{:else}<p class="muted small">{t('news.noAbstract')}</p>{/if}
              {#if it.projects.length}
                <p class="small muted why">{#each it.projects as m (m.project)}{#if projTitle(m.project)}<span>{t('news.whyProject', { project: projTitle(m.project), terms: m.terms.join(', ') })}</span> {/if}{/each}</p>
              {/if}
              {#if it.cats.length || it.extra.comment}<p class="xs muted cats">{[...it.cats.slice(0, 8), it.extra.comment ?? ''].filter(Boolean).join(' · ')}</p>{/if}
              <div class="actions">
                <a class="btn small primary" href={/^https?:\/\//.test(it.url) ? it.url : '#'} target="_blank" rel="noopener noreferrer external"><Icon name="external" size={14} />{t('news.openOn', { host: host(it.url) })}</a>
                {#if !it.fr && it.summary.length >= 200 && !it.extra.suspect && byId.get(it.source)?.summaries !== false}
                  <button class="btn small" onclick={() => summarize(it)} disabled={busy[`s${it.id}`] || local || ov?.demo} title={local ? t('news.err.local_mode') : undefined}>
                    <Icon name="sparkle" size={14} />{busy[`s${it.id}`] ? t('news.summarizing') : t('news.summarize')}
                  </button>
                {/if}
                <button class="btn small" aria-pressed={it.saved} onclick={() => flag(it, { saved: !it.saved })}><Icon name="bookmark" size={14} />{it.saved ? t('news.unsave') : t('news.save')}</button>
                <button class="btn small quiet" onclick={() => { opened[it.id] = false; void flag(it, { read: false }); }}>{t('news.markUnread')}</button>
              </div>
              <div class="send" role="group" aria-labelledby="ns-{it.id}">
                <p class="lbl xs" id="ns-{it.id}">{project ? t('news.sendTo', { project: project.title }) : t('news.sendNoProject')}</p>
                <div class="actions">
                  {#if it.extra.arxiv}<button class="btn small" onclick={() => act(it, 'source')} disabled={!project || busy[`source${it.id}`]}><Icon name="book" size={14} />{t('news.act.source')}</button>{/if}
                  <button class="btn small" onclick={() => act(it, 'conjecture')} disabled={!project || busy[`conjecture${it.id}`]}><Icon name="bulb" size={14} />{t('news.act.conjecture')}</button>
                  <button class="btn small" onclick={() => act(it, 'dossier')} disabled={busy[`dossier${it.id}`]}><Icon name="folder" size={14} />{t('news.act.dossier')}</button>
                  <button class="btn small" onclick={() => act(it, 'note')} disabled={!project || busy[`note${it.id}`]}><Icon name="edit" size={14} />{t('news.act.note')}</button>
                </div>
              </div>
            </div>
          {/if}
        </article>
      </li>
    {/each}
  </ul>

  {#if items.length < total}
    <div class="more"><button class="btn" onclick={() => load(true)} disabled={loading}>{loading ? t('common.loading') : t('news.more', { n: total - items.length })}</button></div>
  {/if}
  {#if meta && items.length}<p class="foot xs muted">{t('news.foot')} <a href="/aide/news">{t('news.footLink')}</a></p>{/if}
</div>

<style>
  .news { max-width: 980px; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-4); }
  .lead { color: var(--text-2); max-width: var(--measure); margin: 0 0 var(--s-2); }
  .bar { gap: var(--s-2); flex-wrap: wrap; }
  .when { margin: 0; display: inline-flex; align-items: center; gap: 6px; }
  .filters { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: var(--s-3); padding: var(--s-3); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); }
  .search { position: relative; min-width: 0; }
  .search :global(.ico) { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--text-3); pointer-events: none; }
  .search .input { padding-left: 36px; }
  .selects { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--s-2); min-width: 0; }
  .toggles { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: var(--s-2); }
  .tog { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 var(--s-3); border: 1px solid var(--line-strong); border-radius: 999px; background: var(--surface); color: var(--text-2); font: inherit; font-size: var(--fs-sm); font-weight: 600; cursor: pointer; }
  .tog:hover:not(:disabled) { border-color: var(--accent); color: var(--text); }
  .tog[aria-pressed='true'] { background: var(--ink); border-color: var(--ink); color: var(--on-ink); }
  .tog:disabled { opacity: 0.55; cursor: not-allowed; }
  .tog .n { min-width: 20px; padding: 0 6px; border-radius: 10px; background: var(--accent-soft); color: var(--accent); font-size: var(--fs-xs); line-height: 20px; text-align: center; }
  .tog[aria-pressed='true'] .n { background: var(--on-ink); color: var(--ink); }
  .count { gap: var(--s-2); flex-wrap: wrap; min-height: 32px; }
  .count p { margin: 0; }
  .empty { text-align: center; color: var(--text-2); display: grid; gap: var(--s-3); justify-items: center; padding: var(--s-6) var(--s-4); }
  .empty p { margin: 0; max-width: var(--measure); }
  .list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--s-2); }
  .item { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-3) var(--s-4); min-width: 0; }
  .item.unread { border-left: 3px solid var(--accent); padding-left: calc(var(--s-4) - 2px); }
  .item.open { border-color: var(--line-strong); }
  .title { margin: 0; font-size: var(--fs-md); line-height: 1.35; }
  .disc { display: flex; align-items: flex-start; gap: var(--s-2); width: 100%; padding: 4px 0; border: 0; background: none; color: var(--text); font: inherit; font-family: var(--font-serif); font-weight: 600; text-align: left; cursor: pointer; border-radius: var(--r-1); }
  .disc:hover .tt { color: var(--accent); }
  .item:not(.unread) .disc { font-weight: 500; }
  .tt { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .tt :global(.md), .tt :global(.md p) { display: inline; margin: 0; }
  .chev { flex: none; color: var(--text-3); padding-top: 3px; }
  .dot { flex: none; width: 8px; height: 8px; margin-top: 8px; border-radius: 50%; background: var(--accent); }
  .meta { margin: 2px 0 0; color: var(--text-2); overflow-wrap: anywhere; }
  .src { font-weight: 600; color: var(--text); }
  .tags { display: flex; flex-wrap: wrap; gap: 6px; margin: var(--s-2) 0 0; }
  .tags:empty { display: none; }
  .chip.br { border: 0; font: inherit; font-size: var(--fs-xs); font-weight: 600; cursor: pointer; min-height: 24px; }
  .chip.br:hover, .chip.br[aria-pressed='true'] { background: var(--accent-soft); color: var(--accent); }
  .chip { white-space: normal; }
  .peek { margin: var(--s-2) 0 0; color: var(--text-2); display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
  .body { margin-top: var(--s-3); padding-top: var(--s-3); border-top: 1px solid var(--line); display: grid; gap: var(--s-2); min-width: 0; }
  .body :global(.md) { overflow-wrap: anywhere; max-width: var(--measure); }
  .lbl { margin: 0; font-weight: 700; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.04em; }
  .lbl .muted { text-transform: none; letter-spacing: 0; font-weight: 500; }
  .fr { padding: var(--s-2) var(--s-3); border-radius: var(--r-2); background: var(--surface-2); display: grid; gap: 4px; }
  .fr :global(.md p) { margin: 0; }
  .warn { margin: 0; display: flex; gap: 6px; align-items: flex-start; padding: var(--s-2) var(--s-3); border-radius: var(--r-2); background: var(--running-soft); color: var(--text); }
  .why, .cats { margin: 0; overflow-wrap: anywhere; }
  .why span { display: block; }
  .actions { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
  .send { margin-top: var(--s-2); padding-top: var(--s-2); border-top: 1px dashed var(--line); display: grid; gap: var(--s-2); }
  .more { display: flex; justify-content: center; }
  .foot { margin: 0; text-align: center; }
  @media (pointer: coarse) { .tog { min-height: var(--touch); } .disc { min-height: var(--touch); } .chip.br { min-height: 32px; padding: 4px 12px; } }
  @media (max-width: 767px) {
    .lead { display: none; }
    .filters { grid-template-columns: minmax(0, 1fr); padding: var(--s-2); }
    .item { padding: var(--s-3); }
    .item.unread { padding-left: calc(var(--s-3) - 2px); }
    .actions .btn { flex: 1 1 auto; justify-content: center; }
  }
  @media (max-width: 420px) { .selects { grid-template-columns: minmax(0, 1fr); } }
</style>
