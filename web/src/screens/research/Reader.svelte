<script lang="ts">
  // Reader: the paper (PDF with highlights, or its TeX-derived structure) side by side with grounded questions about
  // it. A citation jumps to its passage (page + box in the PDF, or the passage in the structure view).
  import { research, authorsOf, yearOf, type Chunk, type Citation, type Source } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { navigate, route } from '../../lib/router.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import Md from '../../components/Md.svelte';
  import QaPanel from '../../components/QaPanel.svelte';
  import PdfView from '../../components/PdfView.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params }: { params: Record<string, string> } = $props();
  const shelf = $derived(params['shelf'] ?? '');
  const id = $derived(params['id'] ?? '');
  let src = $state<Source | null>(null);
  let chunks = $state<Chunk[]>([]);
  let err = $state('');
  let view = $state<'pdf' | 'structure'>('structure');
  let target = $state<{ page: number; bbox?: number[] | null; nonce: number } | null>(null);
  let focusChunk = $state('');
  let tagInput = $state('');
  let compareWith = $state<string[]>([]);
  let others = $state<{ id: string; title: string }[]>([]);
  let bpBusy = $state(false);

  async function load() {
    try {
      src = (await research.source(shelf, id)).source;
      chunks = (await research.chunks(shelf, id)).chunks;
      others = (await research.sources(shelf)).sources.filter((s) => s.id !== id).map((s) => ({ id: s.id, title: s.title }));
      const pdf = src.files.find((f) => f.kind === 'pdf');
      view = pdf && !chunks.some((c) => c.page === null && c.kind !== 'abstract') ? 'pdf' : 'structure';
      err = '';
      const qc = route.query.get('chunk');
      if (qc) jump({ chunk_id: qc, page: Number(route.query.get('page')) || null, bbox: null } as unknown as Citation);
    } catch (e) { err = errorText(e); }
  }
  $effect(() => { void shelf; void id; void load(); });
  $effect(() => app.on('sources.updated', (ev) => {
    const s = (ev as unknown as { source?: Source }).source;
    if (s && s.id === id) src = s;
  }));
  const pdfFile = $derived(src?.files.find((f) => f.kind === 'pdf'));
  const sections = $derived.by(() => {
    const m = new Map<string, Chunk[]>();
    for (const c of chunks) { const k = c.section || ''; m.set(k, [...(m.get(k) ?? []), c]); }
    return [...m.entries()];
  });

  function jump(c: Pick<Citation, 'chunk_id' | 'page' | 'bbox'> & Partial<Citation>) {
    const ch = chunks.find((x) => x.id === c.chunk_id);
    const page = c.page ?? ch?.page ?? null;
    if (c.source_id && c.source_id !== id) { navigate(`/sources/${encodeURIComponent(c.shelf ?? shelf)}/${encodeURIComponent(c.source_id)}?chunk=${encodeURIComponent(c.chunk_id)}${page ? `&page=${page}` : ''}`); return; }
    if (page && pdfFile) { view = 'pdf'; target = { page, bbox: c.bbox ?? ch?.bbox ?? null, nonce: Date.now() }; }
    else {
      view = 'structure';
      focusChunk = c.chunk_id;
      queueMicrotask(() => requestAnimationFrame(() => {
        const el = document.getElementById(`chunk-${c.chunk_id}`);
        el?.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
        el?.focus({ preventScroll: true });
      }));
    }
  }
  async function patch(p: Parameters<typeof research.patchSource>[2]) {
    try { src = (await research.patchSource(shelf, id, p)).source; } catch (e) { toast('error', errorText(e)); }
  }
  async function highlightPdf(page: number, quads: number[][], text: string) {
    try { src = (await research.addAnnotation(shelf, id, { page, quads, text, color: 'yellow', note: '' })).source; toast('ok', t('reader.highlighted')); }
    catch (e) { toast('error', errorText(e)); }
  }
  async function highlightChunk(c: Chunk) {
    try { src = (await research.addAnnotation(shelf, id, { range: { chunk: c.id, start: 0, end: c.text.length }, text: c.text.slice(0, 500), color: 'yellow', note: '' })).source; toast('ok', t('reader.highlighted')); }
    catch (e) { toast('error', errorText(e)); }
  }
  async function editNote(aid: string, note: string) {
    try { src = (await research.patchAnnotation(shelf, id, aid, { note })).source; } catch (e) { toast('error', errorText(e)); }
  }
  async function deleteAnn(aid: string) {
    try {
      src = (await research.deleteAnnotation(shelf, id, aid)).source;
      toast('ok', t('reader.annDeleted'));
    } catch (e) { toast('error', errorText(e)); }
  }
  async function copyLink(c: Chunk) {
    const link = `[[passage:${c.id}]]`;
    try { await navigator.clipboard.writeText(link); toast('ok', t('reader.linkCopied', { link })); } catch { toast('info', link); }
  }
  async function blueprint() {
    bpBusy = true;
    try {
      await research.createBlueprint(currentProjectId(), id, shelf === currentProjectId() ? undefined : shelf);
      toast('ok', t('reader.blueprintMade'));
      navigate(`/blueprint?source=${encodeURIComponent(id)}`);
    } catch (e) { toast('error', errorText(e)); } finally { bpBusy = false; }
  }
  const chunkAnn = $derived((cid: string) => (src?.annotations ?? []).filter((a) => a.range?.chunk === cid));
</script>

{#if err}
  <div><h1>{t('reader.notFound')}</h1><p class="error-text">{err}</p><a class="btn" href="/sources">{t('nav.sources')}</a></div>
{:else if !src}
  <p class="muted" aria-busy="true">{t('common.loading')}</p>
{:else}
  <article class="reader">
    <header class="rh">
      <p class="crumb small"><a href="/sources">{t('nav.sources')}</a> › <code>@{src.key}</code></p>
      <div class="row"><h1>{src.csl.title}</h1><HelpLink page="sources" /></div>
      <p class="small meta">{authorsOf(src.csl)}{yearOf(src.csl) ? ` · ${yearOf(src.csl)}` : ''}{src.csl['container-title'] ? ` · ${src.csl['container-title']}` : ''}
        {#if src.csl.DOI} · <a href="https://doi.org/{src.csl.DOI}" target="_blank" rel="noopener noreferrer">DOI</a>{/if}
        {#if src.csl.arxiv} · <a href="https://arxiv.org/abs/{src.csl.arxiv}" target="_blank" rel="noopener noreferrer">arXiv</a>{/if}</p>
      {#if !src.verified}
        <p class="warn small" role="note">{t('reader.unverified')}
          {#if src.proposed}<button class="btn small" onclick={() => patch({ verified: true })}>{t('reader.acceptProposed', { title: src.proposed.title })}</button>{/if}
          <button class="btn small" onclick={() => patch({ verified: true })}>{t('reader.confirm')}</button></p>
      {/if}
      <div class="row ctl">
        <label for="rs" class="small">{t('sources.status')}</label>
        <select id="rs" class="input" style="width:auto" value={src.status} onchange={(e) => patch({ status: (e.target as HTMLSelectElement).value as Source['status'] })}>
          {#each ['to_read', 'unread', 'reading', 'skimmed', 'read'] as s}<option value={s}>{tk(`readstatus.${s}`, s)}</option>{/each}
        </select>
        {#each src.tags as tg}<button class="chip tagchip" onclick={() => patch({ tags: src!.tags.filter((x) => x !== tg) })} aria-label={t('reader.removeTag', { tag: tg })}>#{tg} ×</button>{/each}
        <form onsubmit={(e) => { e.preventDefault(); if (tagInput.trim()) { void patch({ tags: [...src!.tags, tagInput.trim().replace(/^#/, '')] }); tagInput = ''; } }}>
          <label class="sr-only" for="tagin">{t('reader.addTag')}</label>
          <input id="tagin" class="input tagin" bind:value={tagInput} placeholder={t('reader.addTag')} />
        </form>
        <span class="spacer"></span>
        {#if pdfFile}<a class="btn small" href={research.fileUrl(shelf, id, pdfFile.sha256, true)} download><Icon name="download" size={14} />PDF</a>{/if}
        <button class="btn small" onclick={blueprint} disabled={bpBusy || src.fulltext.state === 'none'}><Icon name="tree" size={14} />{t('reader.makeBlueprint')}</button>
      </div>
      {#if src.fulltext.state !== 'ok'}<p class="small muted">{tk(`fulltext.${src.fulltext.state}`, src.fulltext.state)}</p>{/if}
    </header>

    <div class="split">
      <section class="doc" aria-label={t('reader.document')}>
        <div class="seg" role="radiogroup" aria-label={t('reader.view')}>
          <label><input type="radio" name="rview" checked={view === 'structure'} onchange={() => (view = 'structure')} disabled={!chunks.length} />{t('reader.structure')}</label>
          <label><input type="radio" name="rview" checked={view === 'pdf'} onchange={() => (view = 'pdf')} disabled={!pdfFile} />PDF</label>
        </div>
        {#if view === 'pdf' && pdfFile}
          <PdfView url={research.fileUrl(shelf, id, pdfFile.sha256)} annotations={src.annotations} {target} onhighlight={src.readonly ? undefined : highlightPdf} label={src.csl.title} />
        {:else if chunks.length}
          <div class="structure">
            {#each sections as [sec, cs] (sec)}
              {#if sec}<h2 class="sec">{sec}</h2>{/if}
              {#each cs as c (c.id)}
                <div id="chunk-{c.id}" class="chunk {c.kind}" class:focus={focusChunk === c.id} class:annotated={chunkAnn(c.id).length > 0} tabindex="-1">
                  {#if c.locator && c.kind !== 'paragraph'}<p class="loc xs">{c.locator}</p>{/if}
                  <Md src={c.text} cls={['theorem', 'lemma', 'proposition', 'corollary', 'conjecture', 'claim'].includes(c.kind) ? 'th-body' : ''} />
                  <div class="ctools row">
                    {#if c.page}<button class="btn small quiet" onclick={() => jump({ chunk_id: c.id, page: c.page, bbox: c.bbox })} disabled={!pdfFile}>{t('reader.inPdf', { p: c.page })}</button>{/if}
                    {#if !src.readonly}<button class="btn small quiet" onclick={() => highlightChunk(c)}>{t('reader.highlight')}</button>{/if}
                    <button class="btn small quiet" onclick={() => copyLink(c)}>{t('reader.copyLink')}</button>
                  </div>
                </div>
              {/each}
            {/each}
          </div>
        {:else}
          <p class="muted">{t('reader.noText')}</p>
        {/if}
        {#if src.annotations.length}
          <details class="anns" open>
            <summary>{t('reader.annotationsN', { n: src.annotations.length })}</summary>
            <ul>
              {#each src.annotations as a (a.id)}
                <li>
                  <button class="linkish" onclick={() => a.range ? jump({ chunk_id: a.range.chunk, page: null, bbox: null }) : (view = 'pdf', target = { page: a.page ?? 1, bbox: a.quads?.[0] ? [a.quads[0][0]!, a.quads[0][1]!, a.quads[0][2]!, a.quads[0][5] ?? a.quads[0][3]!] : null, nonce: Date.now() })}>
                    {a.page ? t('reader.page', { n: a.page }) : t('reader.passage')}</button>
                  <q class="small">{a.text.slice(0, 200)}</q>
                  <label class="sr-only" for="an-{a.id}">{t('reader.annNote')}</label>
                  <input id="an-{a.id}" class="input small" value={a.note} placeholder={t('reader.annNote')} onchange={(e) => editNote(a.id, (e.target as HTMLInputElement).value)} disabled={src.readonly} />
                  {#if !src.readonly}<button class="btn small quiet icon" onclick={() => deleteAnn(a.id)} aria-label={t('reader.annDelete')}><Icon name="trash" size={14} /></button>{/if}
                </li>
              {/each}
            </ul>
          </details>
        {/if}
      </section>
      <aside class="side">
        <QaPanel project={currentProjectId()} scope={{ sources: [id] }} oncite={jump} title={t('reader.askThis')}
          summary={{ shelf, source: id }} compare={compareWith.length ? [{ shelf, id }, ...compareWith.map((x) => ({ shelf, id: x }))] : null} />
        {#if others.length}
          <details class="cmp"><summary class="small">{t('reader.compareWith')}</summary>
            {#each others as o (o.id)}<label class="switch small"><input type="checkbox" value={o.id} bind:group={compareWith} />{o.title}</label>{/each}
          </details>
        {/if}
      </aside>
    </div>
  </article>
{/if}

<style>
  .reader { max-width: 1500px; }
  .crumb { margin: 0; color: var(--text-2); }
  .rh h1 { margin: 0; }
  .meta { color: var(--text-2); margin: 4px 0; }
  .warn { background: var(--running-soft); color: var(--running); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .ctl { margin: var(--s-2) 0 var(--s-3); }
  .tagchip { border: 0; cursor: pointer; }
  .tagin { width: 9rem; min-height: 32px; }
  .split { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(320px, 1fr); gap: var(--s-4); align-items: start; }
  @media (max-width: 1100px) { .split { grid-template-columns: minmax(0, 1fr); } }
  .side { position: sticky; top: calc(var(--topbar-h) + 8px); max-height: calc(100dvh - var(--topbar-h) - 24px); overflow: auto; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-4); }
  @media (max-width: 1100px) { .side { position: static; max-height: none; } }
  .structure { max-height: calc(100dvh - var(--topbar-h) - 170px); overflow: auto; padding-right: var(--s-2); }
  @media (max-width: 1100px) { .structure { max-height: none; } }
  .sec { font-size: var(--fs-lg); margin-top: var(--s-4); }
  .chunk { padding: var(--s-2) var(--s-3); border-left: 3px solid transparent; border-radius: 0 var(--r-2) var(--r-2) 0; margin-bottom: var(--s-2); font-family: var(--font-serif); line-height: 1.6; }
  .chunk.theorem, .chunk.lemma, .chunk.proposition, .chunk.corollary, .chunk.definition, .chunk.conjecture { background: var(--surface); border-left-color: var(--line-strong); }
  .chunk.annotated { border-left-color: #e0b000; }
  .chunk.focus { outline: 3px solid var(--laterite-mark); outline-offset: 2px; }
  .chunk:focus { outline: 3px solid var(--laterite-mark); }
  .loc { margin: 0; font-family: var(--font-ui); font-weight: 700; color: var(--text-2); }
  .ctools { gap: 2px; font-family: var(--font-ui); }
  .ctools .btn { min-height: 28px; }
  @media (pointer: coarse) { .ctools .btn { min-height: 44px; } }
  .anns { margin-top: var(--s-3); }
  .anns ul { list-style: none; padding: 0; display: grid; gap: var(--s-2); }
  .anns li { display: grid; grid-template-columns: auto 1fr; gap: 4px 8px; align-items: center; }
  .anns q { grid-column: 1 / -1; color: var(--text-2); }
  .linkish { background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; }
  .cmp { margin-top: var(--s-3); }
</style>
