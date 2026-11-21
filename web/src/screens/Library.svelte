<script lang="ts">
  // Library of proven results (S-M): organised by domain (auto-classified, editable), project or tag; card and table
  // views; each result with its statement (words + Lean), status (verified by Lean / conditional on admitted lemmas),
  // who proved it, what it uses and what uses it, export. Results are reused as lemmas by later proofs.
  import { api } from '../lib/api/client';
  import { wb, type CatalogEntry } from '../lib/api/workbench';
  import { app } from '../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../lib/i18n/index.svelte';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import { providerName } from '../lib/status';
  import Icon from '../components/Icon.svelte';
  import Md from '../components/Md.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  type GroupBy = 'domain' | 'project' | 'tag' | 'none';
  let entries = $state<CatalogEntry[] | null>(null);
  let domains = $state<string[]>([]);
  let err = $state('');
  let q = $state('');
  let groupBy = $state<GroupBy>(readPref('groupBy', 'domain') as GroupBy);
  let view = $state<'cards' | 'table'>(readPref('view', 'cards') as 'cards' | 'table');
  let status = $state<'' | 'verified' | 'conditional'>('');
  let selected = $state<string | null>(null);
  let tagDraft = $state('');

  function readPref(k: string, d: string): string { try { return localStorage.getItem(`madalean.library.${k}`) ?? d; } catch { return d; } }
  function writePref(k: string, v: string) { try { localStorage.setItem(`madalean.library.${k}`, v); } catch { /* ignore */ } }
  $effect(() => writePref('groupBy', groupBy));
  $effect(() => writePref('view', view));

  $effect(() => {
    void app.m.libraryRev;
    wb.catalog().then((r) => { entries = r.entries; domains = r.domains; err = ''; }).catch((e) => { err = errorText(e); });
  });
  const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const shown = $derived.by(() => {
    const needle = fold(q.trim());
    return (entries ?? []).filter((e) => (!status || e.status === status) &&
      (!needle || fold(`${e.name} ${e.title} ${e.statement} ${e.nl} ${e.tags.join(' ')} ${e.project} ${tk(`domain.${e.domain}`, e.domain)}`).includes(needle)))
      .sort((a, b) => b.t - a.t);
  });
  const groups = $derived.by(() => {
    const g = new Map<string, CatalogEntry[]>();
    const add = (k: string, e: CatalogEntry) => { if (!g.has(k)) g.set(k, []); g.get(k)!.push(e); };
    for (const e of shown) {
      if (groupBy === 'domain') add(e.domain, e);
      else if (groupBy === 'project') add(e.project_id || '', e);
      else if (groupBy === 'tag') { if (e.tags.length) for (const tg of e.tags) add(tg, e); else add('', e); }
      else add('*', e);
    }
    return [...g.entries()].sort(([a, x], [b, y]) => (a === '' ? 1 : b === '' ? -1 : y.length - x.length || a.localeCompare(b)));
  });
  function groupLabel(k: string): string {
    if (groupBy === 'domain') return tk(`domain.${k}`, k);
    if (groupBy === 'project') return k ? (app.m.projects[k]?.title ?? (entries ?? []).find((e) => e.project_id === k)?.project ?? k) : t('library.noProject');
    if (groupBy === 'tag') return k || t('library.noTag');
    return t('library.allResults');
  }
  const sel = $derived((entries ?? []).find((e) => e.name === selected) ?? null);
  const byName = $derived(new Map((entries ?? []).map((e) => [e.name, e])));
  const counts = $derived({ verified: (entries ?? []).filter((e) => e.status === 'verified').length, conditional: (entries ?? []).filter((e) => e.status === 'conditional').length });

  function modelLabel(e: CatalogEntry): string {
    if (e.by_user) return t('library.byYou');
    if (!e.model) return '—';
    const [p, ...rest] = e.model.split(':');
    return `${rest.join(':') || e.model} (${providerName(p ?? '')})`;
  }
  async function setDomain(e: CatalogEntry, d: string) {
    const before = e.domain;
    e.domain = d || e.domain_auto; e.domain_manual = !!d;
    try { await wb.libraryMeta(e.name, { domain: d }); toast('ok', t('library.classified', { d: tk(`domain.${e.domain}`, e.domain) })); }
    catch (x) { e.domain = before; toast('error', errorText(x)); }
  }
  async function setTags(e: CatalogEntry, tags: string[]) {
    const before = e.tags;
    e.tags = [...new Set(tags.map((x) => x.trim()).filter(Boolean))].sort();
    try { await wb.libraryMeta(e.name, { tags: e.tags }); } catch (x) { e.tags = before; toast('error', errorText(x)); }
  }
  function addTag(e: CatalogEntry, ev: Event) {
    ev.preventDefault();
    const v = tagDraft.trim();
    tagDraft = '';
    if (v) void setTags(e, [...e.tags, v]);
  }
  async function remove(e: CatalogEntry) {
    entries = (entries ?? []).filter((x) => x.name !== e.name);
    selected = null;
    try {
      const r = await api.deleteLibrary(e.name);
      toast('ok', t('library.removed', { name: e.name }), { action: { label: t('common.undo'), run: async () => {
        try { await api.restoreLibrary(r.removed); } catch (x) { toast('error', errorText(x)); }
      } } });
    } catch (x) { entries = [...(entries ?? []), e]; toast('error', errorText(x)); }
  }
  function openDetail(name: string) {
    selected = name;
    queueMicrotask(() => document.getElementById('lib-detail-h')?.focus());
  }
</script>

<div class="lib">
  <header class="row head">
    <h1>{t('library.title')}</h1>
    <span class="spacer"></span>
    <a class="btn small" href={wb.catalogExportUrl('md')} download><Icon name="download" size={14} />{t('library.exportMd')}</a>
    <a class="btn small" href={wb.catalogExportUrl('json')} download><Icon name="download" size={14} />JSON</a>
  </header>
  <p class="lead">{t('library.lead2')}</p>

  {#if err}<p class="error-text" role="alert">{err}</p>
  {:else if entries === null}<p aria-busy="true" class="muted">{t('common.loading')}</p>
  {:else if entries.length === 0}
    <div class="empty"><h2>{t('library.emptyTitle')}</h2><p>{t('library.emptyText')}</p><a class="btn primary" href="/">{t('library.emptyAction')}</a></div>
  {:else}
    <div class="tools" role="search">
      <label class="sr-only" for="lib-q">{t('library.search')}</label>
      <input id="lib-q" class="input" type="search" placeholder={t('library.searchAll')} bind:value={q} />
      <label class="field-inline"><span>{t('library.groupBy')}</span>
        <select class="input" bind:value={groupBy}>
          {#each ['domain', 'project', 'tag', 'none'] as g}<option value={g}>{tk(`library.group.${g}`, g)}</option>{/each}
        </select></label>
      <label class="field-inline"><span>{t('library.status')}</span>
        <select class="input" bind:value={status}>
          <option value="">{t('library.statusAll', { n: entries.length })}</option>
          <option value="verified">{t('library.statusVerified', { n: counts.verified })}</option>
          <option value="conditional">{t('library.statusConditional', { n: counts.conditional })}</option>
        </select></label>
      <div class="seg views" role="radiogroup" aria-label={t('library.view')}>
        <label class:sel={view === 'cards'}><input type="radio" name="lib-view" value="cards" bind:group={view} />{t('library.viewCards')}</label>
        <label class:sel={view === 'table'}><input type="radio" name="lib-view" value="table" bind:group={view} />{t('library.viewTable')}</label>
      </div>
    </div>
    <p class="small muted" role="status" aria-live="polite">{t('library.count', { n: shown.length })}</p>

    <div class="layout" class:with-detail={!!sel}>
      <div class="results">
        {#each groups as [k, list] (k)}
          <section class="group" aria-labelledby="lg-{k || 'none'}">
            {#if groupBy !== 'none'}<h2 id="lg-{k || 'none'}" class="group-h">{groupLabel(k)} <span class="n">{list.length}</span></h2>{/if}
            {#if view === 'cards'}
              <ul class="cards">
                {#each list as e (e.name + k)}
                  <li class="card" class:conditional={e.status === 'conditional'} class:current={selected === e.name}>
                    <button class="card-btn" onclick={() => openDetail(e.name)} aria-current={selected === e.name}>
                      <span class="card-top">
                        <span class="badge {e.status}">{e.status === 'verified' ? '∎' : '◐'} {tk(`library.st.${e.status}`, e.status)}</span>
                        <span class="xs muted">{fmtTime(e.t)}</span>
                      </span>
                      <strong class="card-title">{e.title || e.name}</strong>
                      {#if e.nl}<span class="nl small"><Md inline src={e.nl.length > 220 ? e.nl.slice(0, 220) + '…' : e.nl} /></span>{/if}
                      <code class="lean xs">{e.statement}</code>
                      <span class="card-foot xs muted">
                        <span>{modelLabel(e)}</span>
                        {#if e.uses.length || e.used_by.length}<span>{t('library.links', { u: e.uses.length, b: e.used_by.length })}</span>{/if}
                      </span>
                    </button>
                  </li>
                {/each}
              </ul>
            {:else}
              <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
              <div class="table-wrap" tabindex="0" role="region" aria-label={groupLabel(k)}>
                <table class="tbl">
                  <caption class="sr-only">{groupLabel(k)}</caption>
                  <thead><tr><th scope="col">{t('library.colResult')}</th><th scope="col">{t('library.colStatus')}</th><th scope="col">{t('library.colDomain')}</th>
                    <th scope="col">{t('library.colProject')}</th><th scope="col">{t('library.colBy')}</th><th scope="col">{t('library.colLinks')}</th><th scope="col">{t('library.colDate')}</th></tr></thead>
                  <tbody>
                    {#each list as e (e.name + k)}
                      <tr class:current={selected === e.name}>
                        <th scope="row"><button class="link-btn" onclick={() => openDetail(e.name)}>{e.title || e.name}</button><br /><code class="xs muted">{e.name}</code></th>
                        <td><span class="badge {e.status}">{tk(`library.st.${e.status}`, e.status)}</span></td>
                        <td>{tk(`domain.${e.domain}`, e.domain)}</td>
                        <td>{e.project || '—'}</td>
                        <td class="small">{modelLabel(e)}</td>
                        <td class="num">{e.uses.length} / {e.used_by.length}</td>
                        <td class="small">{fmtTime(e.t)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </section>
        {:else}<p class="muted">{t('library.noMatch')}</p>{/each}
      </div>

      {#if sel}
        <aside class="detail panel" aria-labelledby="lib-detail-h">
          <div class="row">
            <h2 id="lib-detail-h" tabindex="-1">{sel.title || sel.name}</h2><span class="spacer"></span>
            <button class="btn small quiet" onclick={() => (selected = null)} aria-label={t('common.close')}><Icon name="x" size={16} /></button>
          </div>
          <p><span class="badge {sel.status}">{sel.status === 'verified' ? '∎' : '◐'} {tk(`library.st.${sel.status}`, sel.status)}</span>
            {#if sel.status === 'conditional'}<span class="small"> {t('library.admitted', { a: sel.admitted.join(', ') || '—' })}</span>{/if}</p>
          {#if sel.nl}<div class="theorem"><Md src={sel.nl} /></div>{/if}
          <pre class="code">{sel.statement}</pre>
          <dl class="facts">
            <div><dt>{t('library.colBy')}</dt><dd>{modelLabel(sel)}</dd></div>
            <div><dt>{t('library.colProject')}</dt><dd>{sel.project || '—'}</dd></div>
            <div><dt>{t('library.workspace')}</dt><dd class="mono xs">{sel.workspace}</dd></div>
            {#if sel.axioms?.length}<div><dt>{t('library.axioms')}</dt><dd class="mono xs">{sel.axioms.join(', ')}</dd></div>{/if}
          </dl>

          <div class="field">
            <label for="lib-dom">{t('library.colDomain')}</label>
            <select id="lib-dom" class="input" value={sel.domain_manual ? sel.domain : ''} onchange={(ev) => setDomain(sel, (ev.target as HTMLSelectElement).value)}>
              <option value="">{t('library.domainAuto', { d: tk(`domain.${sel.domain_auto}`, sel.domain_auto) })}</option>
              {#each domains as d}<option value={d}>{tk(`domain.${d}`, d)}</option>{/each}
            </select>
          </div>
          <div class="field">
            <span class="label" id="lib-tags-l">{t('library.tags')}</span>
            <ul class="tags" aria-labelledby="lib-tags-l">
              {#each sel.tags as tg}<li class="chip">{tg} <button class="x" onclick={() => setTags(sel, sel.tags.filter((x) => x !== tg))} aria-label={t('library.removeTag', { t: tg })}><Icon name="x" size={12} /></button></li>{/each}
            </ul>
            <form class="row" onsubmit={(ev) => addTag(sel, ev)}>
              <label class="sr-only" for="lib-tag-new">{t('library.addTag')}</label>
              <input id="lib-tag-new" class="input" maxlength="40" placeholder={t('library.addTagPh')} bind:value={tagDraft} />
              <button class="btn small" type="submit" disabled={!tagDraft.trim()}>{t('library.addTag')}</button>
            </form>
          </div>

          <section aria-labelledby="lib-graph-h">
            <h3 id="lib-graph-h">{t('library.graph')}</h3>
            <div class="mini-graph">
              <div class="col"><p class="xs muted">{t('library.uses')}</p>
                {#each sel.uses as u}<button class="node" onclick={() => openDetail(u)} disabled={!byName.has(u)}>{byName.get(u)?.title || u}</button>{:else}<p class="xs muted">—</p>{/each}</div>
              <div class="col mid" aria-hidden="true"><span class="arrow">→</span><span class="node self">{sel.title || sel.name}</span><span class="arrow">→</span></div>
              <div class="col"><p class="xs muted">{t('library.usedBy')}</p>
                {#each sel.used_by as u}<button class="node" onclick={() => openDetail(u)} disabled={!byName.has(u)}>{byName.get(u)?.title || u}</button>{:else}<p class="xs muted">—</p>{/each}</div>
            </div>
          </section>

          <div class="row actions">
            {#if sel.dossier && app.m.dossiers[sel.dossier]}<a class="btn small" href="/d/{encodeURIComponent(sel.dossier)}">{t('library.openDossier')}</a>{/if}
            {#if sel.status === 'verified'}<a class="btn small" href={wb.catalogExportUrl('lean', sel.name)} download><Icon name="download" size={14} />{t('library.exportLean')}</a>{/if}
            {#if sel.code}<button class="btn small" onclick={() => navigator.clipboard?.writeText(sel.code).then(() => toast('ok', t('library.copied')))}><Icon name="copy" size={14} />{t('library.copyCode')}</button>{/if}
            <span class="spacer"></span>
            {#if sel.status === 'verified' && sel.code}<button class="btn small danger" onclick={() => remove(sel)} aria-label={t('library.removeOne', { name: sel.name })}><Icon name="trash" size={14} /></button>{/if}
          </div>
        </aside>
      {/if}
    </div>
  {/if}
</div>

<style>
  .lib { max-width: 1280px; }
  .head h1 { margin: 0; }
  .lead { color: var(--text-2); max-width: var(--measure); }
  .tools { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: end; margin-bottom: var(--s-2); }
  .tools input[type='search'] { flex: 1 1 18rem; max-width: 30rem; }
  .field-inline { display: grid; gap: 2px; font-size: var(--fs-xs); color: var(--text-3); }
  .field-inline .input { width: auto; color: var(--text); font-size: var(--fs-sm); }
  .views { display: inline-flex; border: 1px solid var(--line-strong); border-radius: var(--r-2); overflow: hidden; }
  .views label { padding: 6px 12px; cursor: pointer; font-size: var(--fs-sm); min-height: 36px; display: flex; align-items: center; }
  .views label + label { border-left: 1px solid var(--line); }
  .views label.sel { background: var(--ink); color: var(--on-ink); }
  .views input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .views label:has(input:focus-visible) { outline: 2px solid var(--focus); outline-offset: -2px; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s-4); align-items: start; }
  .layout.with-detail { grid-template-columns: minmax(0, 1fr) minmax(320px, 400px); }
  .group-h { font-family: var(--font-serif); font-size: var(--fs-lg); margin: var(--s-4) 0 var(--s-2); display: flex; gap: var(--s-2); align-items: baseline; }
  .group-h .n { font: 600 var(--fs-xs) var(--font-ui); color: var(--text-3); }
  .cards { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-3); grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  .card { border: 1px solid var(--line); border-top: 3px solid var(--proved); border-radius: var(--r-2); background: var(--surface); }
  .card.conditional { border-top-color: var(--running-fill); border-top-style: dashed; }
  .card.current { outline: 2px solid var(--accent); }
  .card-btn { all: unset; box-sizing: border-box; display: grid; gap: var(--s-1); padding: var(--s-3); width: 100%; height: 100%; cursor: pointer; align-content: start; }
  .card-btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: var(--r-2); }
  .card-top { display: flex; justify-content: space-between; align-items: center; gap: var(--s-2); }
  .card-title { font-family: var(--font-serif); font-size: var(--fs-md); line-height: 1.3; }
  .nl { color: var(--text-2); }
  .lean { font-family: var(--font-mono); color: var(--text-2); background: var(--surface-2); padding: 4px 6px; border-radius: var(--r-1);
    display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
  .card-foot { display: flex; justify-content: space-between; gap: var(--s-2); flex-wrap: wrap; }
  .badge { font-size: var(--fs-xs); font-weight: 600; padding: 1px 8px; border-radius: 999px; white-space: nowrap; }
  .badge.verified { background: var(--proved-soft); color: var(--proved); }
  .badge.conditional { background: var(--running-soft); color: var(--running); }
  .table-wrap { overflow-x: auto; }
  .tbl { border-collapse: collapse; width: 100%; font-size: var(--fs-sm); }
  .tbl th, .tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  .tbl thead th { font-weight: 600; font-size: var(--fs-xs); color: var(--text-3); }
  .tbl tr.current { background: var(--accent-soft); }
  .tbl .num { font-variant-numeric: tabular-nums; }
  .link-btn { all: unset; color: var(--accent); cursor: pointer; font-weight: 600; text-decoration: underline; text-underline-offset: 2px; }
  .link-btn:focus-visible { outline: 2px solid var(--focus); }
  .detail { position: sticky; top: var(--s-2); max-height: calc(100vh - 2 * var(--s-3) - var(--topbar-h)); overflow: auto; }
  .detail h2 { margin: 0; font-family: var(--font-serif); font-size: var(--fs-lg); }
  .code { font: 0.8125rem/1.5 var(--font-mono); background: var(--surface-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); white-space: pre-wrap; overflow-wrap: anywhere; }
  .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-2); margin: var(--s-2) 0; }
  .facts dt { font-size: var(--fs-xs); color: var(--text-3); }
  .facts dd { margin: 0; font-size: var(--fs-sm); overflow-wrap: anywhere; }
  .tags { list-style: none; padding: 0; margin: 0 0 var(--s-2); display: flex; flex-wrap: wrap; gap: 4px; }
  .tags .x { all: unset; cursor: pointer; display: inline-flex; padding: 2px; border-radius: 50%; }
  .tags .x:focus-visible { outline: 2px solid var(--focus); }
  .mini-graph { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: var(--s-2); align-items: center; }
  .mini-graph .col { display: grid; gap: 4px; }
  .mini-graph .mid { display: flex; align-items: center; gap: 4px; }
  .node { font-size: var(--fs-xs); border: 1px solid var(--line-strong); background: var(--surface); color: var(--text); border-radius: var(--r-1); padding: 4px 6px; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
  .node.self { background: var(--ink); color: var(--on-ink); border-color: var(--ink); max-width: 9rem; }
  .arrow { color: var(--text-3); }
  .actions { margin-top: var(--s-3); flex-wrap: wrap; }
  .empty { max-width: 34rem; }
  @media (max-width: 1023px) {
    .layout.with-detail { grid-template-columns: minmax(0, 1fr); }
    .detail { position: static; max-height: none; order: -1; }
  }
  @media (max-width: 599px) {
    .tools input[type='search'] { flex-basis: 100%; max-width: none; }
    .mini-graph { grid-template-columns: minmax(0, 1fr); }
    .mini-graph .mid { justify-content: center; }
  }
</style>
