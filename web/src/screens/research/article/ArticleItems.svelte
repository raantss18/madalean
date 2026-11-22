<script lang="ts">
  // « Éléments du projet » beside the article (S-AD): proofs (dossiers), Calcul notebooks and their cells, notes,
  // conjectures, sources, figures and versions — each kind with its own icon, a text label and a colour accent.
  // « Insérer » (or a drag onto the text) puts the matching LaTeX at the cursor; the title opens the item.
  import { app } from '../../../lib/store/app.svelte';
  import { t, fmtTime, tk, type Key } from '../../../lib/i18n/index.svelte';
  import { navigate } from '../../../lib/router.svelte';
  import { research } from '../../../lib/api/research';
  import { nb, type NbDocInfo, type NbCell } from '../../../lib/api/workbench';
  import { articleApi, type TexProject, type Version } from '../../../lib/api/article';
  import { phaseOf } from '../../../lib/status';
  import { aprefs, setAPref } from '../../../lib/article/prefs.svelte';
  import { KINDS, GROUPS, type ItemKind, dossierSnippet, conjectureSnippet, citeSnippet, figureSnippet, cellTitle, cellAssets, cellLatex, matches } from '../../../lib/article/items';
  import { toast } from '../../../lib/ui/toasts.svelte';
  import { errorText } from '../../../lib/ui/errors';
  import Icon from '../../../components/Icon.svelte';

  type Snip = { text: string; cursor?: number };
  let { pid, proj, active, oninsert, onversions, onpick }: {
    pid: string; proj: TexProject; active: boolean;
    oninsert: (s: Snip) => void; onversions: () => void; onpick?: () => void;
  } = $props();

  interface Row { id: string; kind: ItemKind; title: string; meta: string; open?: () => void; href?: string;
    snippet?: Snip; insert?: () => Promise<void>; thumb?: string; doc?: string; count?: number }

  let q = $state('');
  let notes = $state<Row[]>([]);
  let conjs = $state<Row[]>([]);
  let sources = $state<Row[]>([]);
  let docs = $state<NbDocInfo[]>([]);
  let versions = $state<Version[]>([]);
  let cells = $state<Record<string, Row[] | 'loading' | 'error'>>({});
  let openDocs = $state<Record<string, boolean>>({});
  let loaded = $state('');
  let loading = $state(false);

  async function load() {
    loading = true;
    await Promise.all([
      research.notes(pid).then((r) => { notes = r.notes.filter((n) => !n.deleted).sort((a, b) => b.updated - a.updated).map((n) => ({ id: n.id, kind: 'note', title: n.title || t('ae.items.untitled'), meta: fmtTime(n.updated), open: () => navigate(`/notes/${encodeURIComponent(n.id)}`) })); }).catch(() => { notes = []; }),
      research.conjectures(pid).then((r) => { conjs = r.conjectures.map((c) => ({ id: c.id, kind: 'conj', title: c.title || c.statement_nl.slice(0, 80), meta: tk(`conj.status.${c.status}`, c.status),
        open: () => navigate(`/conjectures/${encodeURIComponent(c.id)}`), snippet: conjectureSnippet(c) })); }).catch(() => { conjs = []; }),
      research.sources(pid).then((r) => { sources = r.sources.map((s) => ({ id: s.id, kind: 'source', title: s.title || s.key, meta: [s.authors, s.year].filter(Boolean).join(' · ') || s.key,
        open: () => navigate(`/sources/${encodeURIComponent(pid)}/${encodeURIComponent(s.id)}`), snippet: s.key ? citeSnippet(s.key) : undefined })); }).catch(() => { sources = []; }),
      nb.docs(pid).then((r) => { docs = r.docs; }).catch(() => { docs = []; }),
      articleApi.versions(pid).then((r) => { versions = r.versions.slice().reverse(); }).catch(() => { versions = []; }),
    ]);
    loading = false;
    loaded = pid;
  }
  $effect(() => { if (active && loaded !== pid && !loading) void load(); });

  async function loadCells(doc: string) {
    cells[doc] = 'loading';
    try {
      const v = await nb.get(pid, doc);
      cells[doc] = v.cells.filter((c) => c.type !== 'ask' || c.source).map((c) => cellRow(doc, c));
    } catch { cells[doc] = 'error'; }
  }
  function cellRow(doc: string, c: NbCell): Row {
    const assets = cellAssets(c.outputs);
    const tex = cellLatex(c.outputs);
    const kindText = c.type === 'markdown' ? t('ae.items.cell.text') : c.type === 'figure' ? t('ae.items.cell.figure') : c.language === 'python' ? 'Python' : 'Sage';
    const row: Row = { id: c.id, kind: 'cell', title: cellTitle(c.source || c.prompt || '') || t('ae.items.cell.empty'),
      meta: [kindText, assets.length ? t('ae.items.cell.hasFigure') : tex ? t('ae.items.cell.hasFormula') : ''].filter(Boolean).join(' · '), doc,
      open: () => navigate('/calcul') };
    if (assets.length) {
      const asset = assets[assets.length - 1]!;
      row.thumb = `/api/calcul/assets/${asset}`;
      row.insert = async () => { const r = await articleApi.figureFromCalcul(pid, asset); oninsert(figureSnippet(r.path, row.title)); };
    } else if (tex) row.snippet = { text: `\\[\n${tex}\n\\]\n` };
    return row;
  }
  function toggleDoc(id: string) {
    openDocs[id] = !openDocs[id];
    if (openDocs[id] && !Array.isArray(cells[id])) void loadCells(id);
  }

  const labels = $derived(new Set(proj.labels.map((l) => l.label)));
  const proofs = $derived.by<Row[]>(() => Object.values(app.m.dossiers)
    .filter((d) => d.project_id === pid && !d.archived)
    .sort((a, b) => b.updated - a.updated)
    .map((d) => {
      const lemma = Boolean(d.parent_id);
      const snip = dossierSnippet({ id: d.id, title: d.title, theorem: d.theorem, lemma }, labels);
      return { id: d.id, kind: 'proof' as const, title: d.title || d.theorem, meta: `${lemma ? t('ae.items.lemma') + ' · ' : ''}${tk(`phase.${phaseOf(d.status, app.activeJob(d.id))}`, d.status)}${snip.text.startsWith('\\cref') ? ' · ' + t('ae.items.inArticle') : ''}`,
        open: () => navigate(`/d/${encodeURIComponent(d.id)}`), snippet: snip };
    }));
  const figures = $derived<Row[]>(proj.figures.map((p) => ({ id: p, kind: 'figure', title: p.replace(/^figures\//, ''), meta: '', href: articleApi.figureUrl(pid, p), thumb: articleApi.figureUrl(pid, p), snippet: figureSnippet(p) })));
  const calcRows = $derived<Row[]>(docs.map((d) => ({ id: d.id, kind: 'calc', title: d.title, meta: [d.language === 'python' ? 'Python' : 'Sage', d.cells != null ? t('ae.items.cells', { n: d.cells }) : ''].filter(Boolean).join(' · '), open: () => navigate('/calcul'), count: d.cells })));
  const versionRows = $derived<Row[]>(versions.map((v) => ({ id: v.id, kind: 'version', title: versionLabel(v), meta: fmtTime(v.t), open: onversions })));

  const groups = $derived.by(() => {
    const all: Record<string, Row[]> = { proof: proofs, calc: calcRows, note: notes, conj: conjs, source: sources, figure: figures, version: versionRows };
    return GROUPS.map((k) => ({ kind: k, rows: all[k]!.filter((r) => matches(q, r.title, r.meta)) }));
  });
  const total = $derived(groups.reduce((n, g) => n + g.rows.length, 0));

  function toggleGroup(k: string) {
    const c = aprefs.closedGroups.includes(k) ? aprefs.closedGroups.filter((x) => x !== k) : [...aprefs.closedGroups, k];
    setAPref('closedGroups', c);
  }
  async function insert(r: Row) {
    try {
      if (r.insert) await r.insert();
      else if (r.snippet) oninsert(r.snippet);
      else return;
      onpick?.();
    } catch (e) { toast('error', errorText(e)); }
  }
  function drag(e: DragEvent, r: Row) {
    if (!r.snippet || !e.dataTransfer) return;
    e.dataTransfer.setData('text/plain', r.snippet.text);
    e.dataTransfer.effectAllowed = 'copy';
  }
  const versionLabel = (v: Version) => (!v.label || v.label === 'autosave' || v.label === 'view' || v.label === 'settings' ? t('ae.v.auto')
    : v.label === 'creation' ? t('ae.v.creation') : v.label === 'before-restore' ? t('ae.v.beforeRestore')
    : v.label === 'before-overleaf-import' ? t('ae.v.beforeImport') : v.label.startsWith('suggestion') ? t('ae.v.suggestion')
    : v.label.startsWith('template:') ? t('ae.v.template', { tpl: v.label.slice(9) }) : v.label);
  const kl = (k: ItemKind) => t(KINDS[k].label as Key);
</script>

<div class="items">
  <div class="search">
    <label class="sr-only" for="ae-items-q">{t('ae.items.search')}</label>
    <input id="ae-items-q" class="input" type="search" placeholder={t('ae.items.search')} bind:value={q} autocomplete="off" />
  </div>
  <p class="xs muted hint">{t('ae.items.hint')}</p>
  {#if loading && !loaded}<p class="muted xs" aria-busy="true">{t('common.loading')}</p>{/if}
  {#each groups as g (g.kind)}
    {@const info = KINDS[g.kind]}
    {@const open = !aprefs.closedGroups.includes(g.kind) || q.trim() !== ''}
    <section class="group" style:--k={info.color} aria-labelledby="ae-g-{g.kind}">
      <h3 class="gh">
        <button id="ae-g-{g.kind}" class="gbtn" aria-expanded={open} aria-controls="ae-gl-{g.kind}" onclick={() => toggleGroup(g.kind)}>
          <Icon name={open ? 'chevronDown' : 'chevronRight'} size={14} />
          <span class="kicon"><Icon name={info.icon} size={16} /></span>
          <span class="gt">{t(info.group as Key)}</span>
          <span class="n">{g.rows.length}</span>
        </button>
      </h3>
      <ul id="ae-gl-{g.kind}" hidden={!open}>
        {#each g.rows as r (r.id)}
          <li class="item" data-kind={r.kind} draggable={r.snippet ? 'true' : undefined} ondragstart={(e) => drag(e, r)}>
            <span class="kicon" aria-hidden="true">{#if r.thumb}<img src={r.thumb} alt="" loading="lazy" />{:else}<Icon name={KINDS[r.kind].icon} size={18} />{/if}</span>
            <span class="txt">
              {#if r.href}<a class="ttl" href={r.href} target="_blank" rel="noopener">{r.title}</a>
              {:else}<button class="ttl" onclick={() => { r.open?.(); onpick?.(); }}>{r.title}</button>{/if}
              <span class="meta xs"><span class="kl">{kl(r.kind)}</span>{#if r.meta} · {r.meta}{/if}</span>
            </span>
            {#if r.kind === 'calc'}
              <button class="btn quiet icon small" aria-expanded={!!openDocs[r.id]} aria-controls="ae-cells-{r.id}" aria-label={t('ae.items.showCells', { title: r.title })} onclick={() => toggleDoc(r.id)}><Icon name={openDocs[r.id] ? 'chevronUp' : 'chevronDown'} size={16} /></button>
            {:else if r.snippet || r.insert}
              <button class="btn small ins" onclick={() => insert(r)} aria-label={t('ae.items.insertNamed', { kind: kl(r.kind), title: r.title })}><Icon name="plus" size={14} /><span aria-hidden="true">{t('ae.items.insert')}</span></button>
            {/if}
          </li>
          {#if r.kind === 'calc' && openDocs[r.id]}
            {@const cs = cells[r.id]}
            <li class="cells" id="ae-cells-{r.id}">
              {#if cs === 'loading' || cs === undefined}<p class="xs muted" aria-busy="true">{t('common.loading')}</p>
              {:else if cs === 'error'}<p class="xs muted">{t('ae.items.cellsError')}</p>
              {:else if !cs.length}<p class="xs muted">{t('ae.items.noCells')}</p>
              {:else}
                <ul aria-label={t('ae.items.cellsOf', { title: r.title })}>
                  {#each cs as c (c.id)}
                    <li class="item sub" data-kind="cell" style:--k={KINDS.cell.color} draggable={c.snippet ? 'true' : undefined} ondragstart={(e) => drag(e, c)}>
                      <span class="kicon" aria-hidden="true">{#if c.thumb}<img src={c.thumb} alt="" loading="lazy" />{:else}<Icon name="cell" size={16} />{/if}</span>
                      <span class="txt">
                        <button class="ttl mono" onclick={() => { c.open?.(); onpick?.(); }}>{c.title}</button>
                        <span class="meta xs"><span class="kl">{kl('cell')}</span>{#if c.meta} · {c.meta}{/if}</span>
                      </span>
                      {#if c.snippet || c.insert}
                        <button class="btn small ins" onclick={() => insert(c)} aria-label={t('ae.items.insertNamed', { kind: kl('cell'), title: c.title })}><Icon name="plus" size={14} /><span aria-hidden="true">{t('ae.items.insert')}</span></button>
                      {/if}
                    </li>
                  {/each}
                </ul>
              {/if}
            </li>
          {/if}
        {:else}
          <li class="xs muted empty">{q ? t('ae.items.noMatch') : t(`ae.items.empty.${g.kind}` as Key)}</li>
        {/each}
      </ul>
    </section>
  {/each}
  {#if loaded && !total && q}<p class="xs muted">{t('ae.items.noMatch')}</p>{/if}
  <button class="btn small quiet refresh" onclick={() => load()} disabled={loading}><Icon name="refresh" size={14} />{t('ae.items.refresh')}</button>
</div>

<style>
  .items { display: grid; gap: var(--s-1); }
  .search .input { min-height: 36px; width: 100%; }
  .hint { margin: 0 2px var(--s-1); }
  .group { border-top: 1px solid var(--line); padding-top: 2px; }
  .gh { margin: 0; font-size: var(--fs-sm); }
  .gbtn { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 36px; padding: 0 4px; background: none; border: 0; color: var(--text); font: 600 var(--fs-sm) var(--font-ui); cursor: pointer; border-radius: var(--r-1); text-align: left; }
  .gbtn:hover { background: var(--surface-2); }
  .gt { flex: 1; }
  .n { color: var(--text-3); font-variant-numeric: tabular-nums; font-weight: 600; }
  .kicon { flex: none; display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 6px; color: var(--k); background: color-mix(in srgb, var(--k) 13%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--k) 35%, transparent); overflow: hidden; }
  .gbtn .kicon { width: 22px; height: 22px; }
  .kicon img { width: 100%; height: 100%; object-fit: cover; background: #fff; }
  ul { list-style: none; margin: 0; padding: 0; }
  .item { display: flex; align-items: center; gap: 8px; padding: 4px 4px 4px 6px; border-left: 3px solid var(--k, var(--line)); margin: 2px 0; border-radius: 0 var(--r-1) var(--r-1) 0; }
  .item[draggable='true'] { cursor: grab; }
  .item:hover { background: var(--surface-2); }
  .item.sub { margin-left: 10px; }
  .item[data-kind='proof'] { --k: var(--k-proof); } .item[data-kind='calc'] { --k: var(--k-calc); } .item[data-kind='note'] { --k: var(--k-note); }
  .item[data-kind='conj'] { --k: var(--k-conj); } .item[data-kind='source'] { --k: var(--k-source); } .item[data-kind='figure'] { --k: var(--k-figure); }
  .item[data-kind='version'] { --k: var(--k-version); }
  .txt { flex: 1; min-width: 0; display: grid; }
  .ttl { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden; background: none; border: 0; padding: 2px 0; color: var(--text); font: 600 var(--fs-sm)/1.3 var(--font-ui); text-align: left; cursor: pointer; text-decoration: none; min-height: 24px; overflow-wrap: anywhere; }
  .ttl:hover { text-decoration: underline; }
  .ttl.mono { font: 500 var(--fs-xs) var(--font-mono); }
  .meta { color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kl { font-weight: 700; color: var(--text); }
  .ins { flex: none; gap: 2px; padding: 0 8px; }
  .cells { padding: 0 0 4px; }
  .cells > p { margin: 4px 0 4px 16px; }
  .empty { padding: 4px 8px 6px; }
  .refresh { justify-self: start; margin-top: var(--s-2); }
  @media (pointer: coarse) {
    .gbtn { min-height: var(--touch); }
    .ttl { min-height: var(--touch); padding: 4px 0; }
    .ins { min-height: var(--touch); }
  }
</style>
