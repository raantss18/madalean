<script lang="ts">
  // Sources (Zotero-like library + NotebookLM-like questions): shelves, filters, add by identifier / file / paste /
  // Zotero export, literature search with merged results, grounded questions over the whole shelf.
  import { research, type Citation, type LitResult, type Shelf, type SourceSummary } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { navigate, route } from '../../lib/router.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import QaPanel from '../../components/QaPanel.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  let shelves = $state<Shelf[]>([]);
  let shelf = $state('');
  let list = $state<SourceSummary[] | null>(null);
  let err = $state('');
  let q = $state(route.query.get('key') ?? '');
  let tag = $state('');
  let status = $state('');
  let tab = $state<'library' | 'search' | 'ask'>((route.query.get('tab') as 'library') ?? 'library');
  let adding = $state(false);
  let addMode = $state<'id' | 'file' | 'paste'>('id');
  let identifier = $state('');
  let pasted = $state('');
  let addBusy = $state(false);
  let addErr = $state('');
  let fileInput: HTMLInputElement | undefined = $state();
  // literature search
  let lq = $state('');
  let lit = $state<{ results: LitResult[]; providers: Record<string, { ok: boolean; count: number; error?: string }> } | null>(null);
  let litBusy = $state(false);
  let addedIds = $state<Record<string, string>>({});

  async function loadShelves(pid: string) {
    try {
      shelves = (await research.shelves()).shelves;
      if (!shelf || !shelves.some((s) => s.id === shelf)) shelf = shelves.find((s) => s.id === pid)?.id ?? pid;
    } catch (e) { err = errorText(e); }
  }
  async function load() {
    if (!shelf) return;
    try { list = (await research.sources(shelf, { q, tag, status })).sources; err = ''; } catch (e) { err = errorText(e); list = []; }
  }
  const pidNow = $derived(currentProjectId());
  $effect(() => { if (pidNow) void loadShelves(pidNow); });
  let rev = $state(0);
  $effect(() => app.on('sources.updated', () => { rev++; }));
  $effect(() => { void shelf; void q; void tag; void status; void rev; const h = setTimeout(load, 150); return () => clearTimeout(h); });
  const ro = $derived(shelves.find((s) => s.id === shelf)?.readonly ?? false);
  const tags = $derived([...new Set((list ?? []).flatMap((s) => s.tags))].sort());

  async function addId(force = false) {
    if (!identifier.trim()) return;
    addBusy = true; addErr = '';
    try {
      const r = await research.addByIdentifier(shelf, identifier.trim(), force);
      if (r.duplicate && !force) { addErr = t('sources.duplicate', { reason: tk(`sources.dup.${r.duplicate.reason}`, r.duplicate.reason) }); return; }
      toast('ok', t('sources.added', { title: r.source.csl.title }));
      adding = false; identifier = ''; rev++;
    } catch (e) { addErr = errorText(e); } finally { addBusy = false; }
  }
  async function addPaste() {
    addBusy = true; addErr = '';
    try {
      const r = await research.addText(shelf, pasted);
      toast('ok', t('sources.imported', { n: r.added.length, d: r.duplicates.length }));
      if (r.errors.length) addErr = r.errors.join(' · '); else { adding = false; pasted = ''; }
      rev++;
    } catch (e) { addErr = errorText(e); } finally { addBusy = false; }
  }
  async function addFile(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (!f) return;
    addBusy = true; addErr = '';
    try {
      const r = await research.addFile(shelf, f);
      toast('ok', r.source ? t('sources.added', { title: r.source.csl.title }) : t('sources.imported', { n: r.added?.length ?? 0, d: r.duplicates?.length ?? 0 }));
      adding = false; rev++;
    } catch (x) { addErr = errorText(x); } finally { addBusy = false; if (fileInput) fileInput.value = ''; }
  }
  async function litSearch(e: Event) {
    e.preventDefault();
    if (!lq.trim()) return;
    litBusy = true;
    try { lit = await research.litsearch(lq.trim()); } catch (x) { toast('error', errorText(x)); } finally { litBusy = false; }
  }
  async function addResult(r: LitResult) {
    try {
      const a = await research.addCsl(shelf, r.csl);
      addedIds[r.id] = a.source.id;
      toast('ok', a.duplicate ? t('sources.alreadyThere') : t('sources.added', { title: r.title }));
      rev++;
    } catch (x) { toast('error', errorText(x)); }
  }
  async function remove(s: SourceSummary) {
    try {
      await research.deleteSource(shelf, s.id);
      rev++;
      toast('ok', t('sources.removed', { title: s.title }), { action: { label: t('common.undo'), run: async () => { await research.restoreSource(shelf, s.id); rev++; } } });
    } catch (e) { toast('error', errorText(e)); }
  }
  function cite(c: Citation) { navigate(`/sources/${encodeURIComponent(c.shelf)}/${encodeURIComponent(c.source_id)}?chunk=${encodeURIComponent(c.chunk_id)}${c.page ? `&page=${c.page}` : ''}`); }
</script>

<ProjectGate>
  {#snippet children(pid)}
    <div class="sources">
      <div class="row head">
        <h1>{t('sources.title')}</h1>
        <HelpLink page="sources" />
        <span class="spacer"></span>
        <label class="sr-only" for="shelf">{t('sources.shelf')}</label>
        <select id="shelf" class="input shelf" bind:value={shelf}>
          {#each shelves as s (s.id)}<option value={s.id}>{s.title} ({s.count}){s.readonly ? ` — ${t('sources.readonly')}` : ''}</option>{/each}
        </select>
        {#if !ro}<button class="btn primary" onclick={() => (adding = true)}><Icon name="plus" size={16} />{t('sources.add')}</button>{/if}
      </div>
      <p class="lead">{t('sources.lead')}</p>

      <div class="seg tabs" role="radiogroup" aria-label={t('sources.view')}>
        <label><input type="radio" name="src-tab" checked={tab === 'library'} onchange={() => (tab = 'library')} />{t('sources.tab.library')}</label>
        <label><input type="radio" name="src-tab" checked={tab === 'search'} onchange={() => (tab = 'search')} />{t('sources.tab.search')}</label>
        <label><input type="radio" name="src-tab" checked={tab === 'ask'} onchange={() => (tab = 'ask')} />{t('sources.tab.ask')}</label>
      </div>

      {#if tab === 'library'}
        <div class="row filters">
          <label class="sr-only" for="src-q">{t('sources.filter')}</label>
          <input id="src-q" class="input" type="search" placeholder={t('sources.filter')} bind:value={q} />
          <label class="sr-only" for="src-tag">{t('sources.tag')}</label>
          <select id="src-tag" class="input" bind:value={tag}><option value="">{t('sources.allTags')}</option>{#each tags as tg}<option value={tg}>#{tg}</option>{/each}</select>
          <label class="sr-only" for="src-st">{t('sources.status')}</label>
          <select id="src-st" class="input" bind:value={status}>
            <option value="">{t('sources.allStatus')}</option>
            {#each ['to_read', 'unread', 'reading', 'skimmed', 'read'] as s}<option value={s}>{tk(`readstatus.${s}`, s)}</option>{/each}
          </select>
          <a class="btn small" href={research.exportUrl(shelf, 'bib')} download><Icon name="download" size={14} />BibTeX</a>
        </div>
        {#if err}<p class="error-text" role="alert">{err}</p>
        {:else if list === null}<p class="muted" aria-busy="true">{t('common.loading')}</p>
        {:else if list.length === 0}
          <div class="empty"><h2>{t('sources.emptyTitle')}</h2><p>{t('sources.emptyText')}</p>{#if !ro}<button class="btn primary" onclick={() => (adding = true)}>{t('sources.add')}</button>{/if}</div>
        {:else}
          <ul class="items">
            {#each list as s (s.id)}
              <li>
                <a class="item" href="/sources/{encodeURIComponent(shelf)}/{encodeURIComponent(s.id)}">
                  <span class="t">{s.title}</span>
                  <span class="m small">{s.authors}{s.year ? ` · ${s.year}` : ''}{s.venue ? ` · ${s.venue}` : ''}</span>
                  <span class="b row">
                    <span class="chip">{tk(`readstatus.${s.status}`, s.status)}</span>
                    <code class="xs">@{s.key}</code>
                    {#if s.has_pdf}<span class="chip">PDF</span>{/if}{#if s.has_tex}<span class="chip">TeX</span>{/if}
                    {#if s.fulltext === 'ok'}<span class="chip proved">{t('sources.indexed')}</span>{:else if s.fulltext !== 'none'}<span class="chip running">{tk(`fulltext.${s.fulltext}`, s.fulltext)}</span>{/if}
                    {#if !s.verified}<span class="chip running">{t('sources.unverified')}</span>{/if}
                    {#if s.annotations}<span class="xs muted">{t('sources.annotations', { n: s.annotations })}</span>{/if}
                    {#each s.tags as tg}<span class="xs muted">#{tg}</span>{/each}
                  </span>
                </a>
                {#if !s.readonly && !ro}<button class="btn small quiet icon" onclick={() => remove(s)} aria-label={t('sources.removeOne', { title: s.title })}><Icon name="trash" size={16} /></button>{/if}
              </li>
            {/each}
          </ul>
        {/if}
      {:else if tab === 'search'}
        <form class="row lit" onsubmit={litSearch}>
          <label class="sr-only" for="lit-q">{t('lit.query')}</label>
          <input id="lit-q" class="input" bind:value={lq} placeholder={t('lit.placeholder')} />
          <button class="btn primary" type="submit" disabled={litBusy}>{litBusy ? t('lit.searching') : t('lit.search')}</button>
        </form>
        <p class="hint">{t('lit.privacy')}</p>
        {#if lit}
          <p class="small providers">{#each Object.entries(lit.providers) as [name, p]}<span class="chip {p.ok ? '' : 'failed'}">{name}: {p.ok ? p.count : t('lit.providerFailed')}</span>{/each}</p>
          <ul class="items">
            {#each lit.results as r (r.id)}
              <li class="lit-item">
                <div class="grow">
                  <span class="t">{r.title}</span>
                  <span class="m small">{r.authors}{r.year ? ` · ${r.year}` : ''}{r.venue ? ` · ${r.venue}` : ''}</span>
                  <span class="b row">{#each r.providers as pv}<span class="chip">{pv}</span>{/each}{#if r.oa?.is_oa}<span class="chip proved">{t('lit.openAccess')}</span>{/if}{#if r.doi}<code class="xs">{r.doi}</code>{/if}{#if r.arxiv}<code class="xs">arXiv:{r.arxiv}</code>{/if}</span>
                  {#if r.abstract}<details><summary class="xs">{t('lit.abstract')}</summary><p class="small">{r.abstract}</p></details>{/if}
                </div>
                {#if addedIds[r.id]}<a class="btn small" href="/sources/{encodeURIComponent(shelf)}/{encodeURIComponent(addedIds[r.id]!)}">{t('lit.open')}</a>
                {:else}<button class="btn small primary" onclick={() => addResult(r)} disabled={ro}>{t('lit.add')}</button>{/if}
              </li>
            {:else}<li class="muted">{t('lit.none')}</li>{/each}
          </ul>
        {/if}
      {:else}
        <div class="ask"><QaPanel project={pid} scope={{ shelves: [shelf] }} oncite={cite} /></div>
      {/if}
    </div>

    <Dialog bind:open={adding} title={t('sources.addTitle')} wide>
      <div class="seg" role="radiogroup" aria-label={t('sources.addHow')}>
        <label><input type="radio" name="add-mode" checked={addMode === 'id'} onchange={() => (addMode = 'id')} />{t('sources.addId')}</label>
        <label><input type="radio" name="add-mode" checked={addMode === 'file'} onchange={() => (addMode = 'file')} />{t('sources.addFile')}</label>
        <label><input type="radio" name="add-mode" checked={addMode === 'paste'} onchange={() => (addMode = 'paste')} />{t('sources.addPaste')}</label>
      </div>
      <div class="addbody">
        {#if addMode === 'id'}
          <form onsubmit={(e) => { e.preventDefault(); void addId(); }}>
            <div class="field"><label for="add-id">{t('sources.idLabel')}</label><input id="add-id" class="input" bind:value={identifier} placeholder="10.1007/… · 2411.02513 · Zbl 0965.11001" />
              <p class="hint">{t('sources.idHint')}</p></div>
          </form>
        {:else if addMode === 'file'}
          <p class="small">{t('sources.fileHint')}</p>
          <input bind:this={fileInput} id="add-file" type="file" accept=".pdf,.tex,.zip,.gz,.tgz,.tar,.bib,.ris,.json,.rdf,.epub" onchange={addFile} class="input" aria-label={t('sources.addFile')} />
        {:else}
          <div class="field"><label for="add-paste">{t('sources.pasteLabel')}</label><textarea id="add-paste" class="input mono" rows="8" bind:value={pasted}></textarea><p class="hint">{t('sources.pasteHint')}</p></div>
        {/if}
        {#if addBusy}<p class="muted small" aria-busy="true">{t('sources.adding')}</p>{/if}
        {#if addErr}<p class="error-text" role="alert">{addErr}{#if addErr.startsWith(t('sources.duplicate', { reason: '' }).slice(0, 8))} <button class="btn small" onclick={() => addId(true)}>{t('sources.addAnyway')}</button>{/if}</p>{/if}
      </div>
      {#snippet actions()}
        <button class="btn quiet" onclick={() => (adding = false)}>{t('common.cancel')}</button>
        {#if addMode === 'id'}<button class="btn primary" onclick={() => addId()} disabled={addBusy || !identifier.trim()}>{t('sources.add')}</button>{/if}
        {#if addMode === 'paste'}<button class="btn primary" onclick={addPaste} disabled={addBusy || !pasted.trim()}>{t('sources.import')}</button>{/if}
      {/snippet}
    </Dialog>
  {/snippet}
</ProjectGate>

<style>
  .sources { max-width: 1100px; }
  .head h1 { margin: 0; }
  .shelf { width: auto; max-width: 320px; }
  .lead { color: var(--text-2); max-width: var(--measure); }
  .tabs { margin-bottom: var(--s-4); }
  .filters { margin-bottom: var(--s-3); }
  .filters .input[type='search'] { flex: 1; min-width: 12rem; }
  .filters select { width: auto; }
  .items { list-style: none; padding: 0; margin: 0; }
  .items > li { display: flex; align-items: center; gap: var(--s-2); border-bottom: 1px solid var(--line); }
  .item, .lit-item .grow { flex: 1; display: grid; gap: 2px; padding: var(--s-2) var(--s-2); color: var(--text); text-decoration: none; min-width: 0; }
  .item:hover { background: var(--surface-2); }
  .lit-item { padding-right: var(--s-2); }
  .t { font-family: var(--font-serif); font-weight: 600; font-size: 1.0625rem; }
  .m { color: var(--text-2); }
  .b { gap: 6px; }
  .lit .input { flex: 1; min-width: 12rem; }
  .providers { display: flex; flex-wrap: wrap; gap: 6px; }
  .empty { max-width: 34rem; }
  .ask { max-width: 760px; }
  .addbody { margin-top: var(--s-3); }
</style>
