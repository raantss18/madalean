<script lang="ts">
  // Notes (Obsidian-like, inside Madalean): Markdown + KaTeX + Lean blocks checked by Lean, [[links]] with completion
  // to notes / dossiers / sources, backlinks, tags, versions with diff and restore, live multi-device editing with
  // server-side merge and a conflict view when two devices changed the same lines.
  import { onDestroy } from 'svelte';
  import { ApiError } from '../../lib/api/client';
  import { research, type Note, type NoteConflict, type NoteSummary, type LeanBlockResult } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { linkify, leanBlocks } from '../../lib/notes';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import ConflictView from './ConflictView.svelte';

  let { params }: { params: Record<string, string> } = $props();
  const nid = $derived(params['id'] ?? '');
  let list = $state<NoteSummary[]>([]);
  let q = $state('');
  let hits = $state<(NoteSummary & { snippet: string })[] | null>(null);
  let tagFilter = $state('');
  let note = $state<Note | null>(null);
  let backlinks = $state<{ id: string; title: string; context: string }[]>([]);
  let title = $state('');
  let body = $state('');
  let baseRev = 0;
  let dirty = $state(false);
  let saving = $state(false);
  let savedAt = $state(0);
  let conflict = $state<NoteConflict | null>(null);
  let view = $state<'edit' | 'preview' | 'split'>('split');
  let versionsOpen = $state(false);
  let versions = $state<{ rev: number; title: string; t: number; device: string; reason: string }[]>([]);
  let diff = $state<{ rev: number; text: string } | null>(null);
  let creating = $state(false);
  let newTitle = $state('');
  let checking = $state(-1);
  let pid = '';
  const pidNow = $derived(currentProjectId());
  $effect(() => { if (pidNow) void loadList(pidNow); });
  let timer: ReturnType<typeof setTimeout> | null = null;

  async function loadList(p: string) {
    pid = p;
    try { list = (await research.notes(p, tagFilter ? { tag: tagFilter } : {})).notes; } catch (e) { toast('error', errorText(e)); }
  }
  async function open(id: string) {
    if (!id) { note = null; return; }
    try {
      const r = await research.note(id);
      setNote(r.note);
      backlinks = r.backlinks;
    } catch (e) { toast('error', errorText(e)); note = null; }
  }
  let synced = { body: '', title: '' };
  function setNote(n: Note) {
    note = n; title = n.title; body = n.body; baseRev = n.rev; dirty = false; synced = { body: n.body, title: n.title };
  }
  // Any change typed in the editor or the title → autosave (debounced).
  $effect(() => { if (note && (body !== synced.body || title !== synced.title)) edited(); });
  $effect(() => { void nid; void open(nid); });
  $effect(() => app.on('note.updated', (ev) => {
    const e = ev as unknown as { note: Note; device: string; merged?: boolean; reason?: string };
    if (pid && e.note.project_id === pid) void loadList(pid);
    if (!note || e.note.id !== note.id || e.note.rev <= baseRev) return;
    if (!dirty) { setNote(e.note); toast('info', t('notes.updatedElsewhere')); }
    // else: keep the local text; the next save sends our old base_rev and the server merges.
  }));
  $effect(() => app.on('note.deleted', (ev) => { if (pid) void loadList(pid); if (note && (ev as unknown as { id: string }).id === note.id) { note = null; navigate('/notes'); } }));
  $effect(() => {
    const s = q.trim();
    if (!s) { hits = null; return; }
    const h = setTimeout(() => research.searchNotes(s, pid).then((r) => (hits = r.results)).catch(() => {}), 200);
    return () => clearTimeout(h);
  });

  function edited() {
    dirty = true;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => void save(), 1200);
  }
  async function save(override?: { body: string; base: number; title?: string }) {
    if (!note || saving) return;
    if (timer) { clearTimeout(timer); timer = null; }
    saving = true;
    const sentBody = override?.body ?? body;
    const sentTitle = override?.title ?? title;
    try {
      const r = await research.patchNote(note.id, override?.base ?? baseRev, { title: sentTitle.trim() || note.title, body: sentBody });
      const localChangedMeanwhile = body !== sentBody;
      note = r.note; baseRev = r.note.rev;
      synced = { body: r.note.body, title: r.note.title };
      if (!localChangedMeanwhile) { body = r.note.body; title = r.note.title; dirty = false; }
      else synced = { body: sentBody, title: sentTitle };
      if (r.merged) toast('info', t('notes.merged'));
      savedAt = Date.now() / 1000;
      conflict = null;
      void loadList(pid);
    } catch (e) {
      if (e instanceof ApiError && e.kind === 'conflict') conflict = e.body as unknown as NoteConflict;
      else toast('error', errorText(e));
    } finally { saving = false; }
  }
  function resolved(merged: string, t2: string) {
    if (!conflict) return;
    const base = conflict.current.rev;
    body = merged; title = t2;
    void save({ body: merged, base, title: t2 });
  }
  async function create(e: Event) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      const r = await research.createNote(pid, newTitle.trim(), `# ${newTitle.trim()}\n\n`);
      creating = false; newTitle = '';
      await loadList(pid);
      navigate(`/notes/${encodeURIComponent(r.note.id)}`);
    } catch (x) { toast('error', errorText(x)); }
  }
  async function daily() {
    try { const r = await research.dailyNote(pid); await loadList(pid); navigate(`/notes/${encodeURIComponent(r.note.id)}`); } catch (x) { toast('error', errorText(x)); }
  }
  async function remove() {
    if (!note) return;
    const n = note;
    try {
      await research.deleteNote(n.id);
      navigate('/notes');
      toast('ok', t('notes.deleted', { title: n.title }), { action: { label: t('common.undo'), run: async () => { const r = await research.restoreNote(n.id); navigate(`/notes/${encodeURIComponent(r.note.id)}`); } } });
    } catch (x) { toast('error', errorText(x)); }
  }
  async function openVersions() {
    if (!note) return;
    try { versions = (await research.noteVersions(note.id)).versions; versionsOpen = true; diff = null; } catch (x) { toast('error', errorText(x)); }
  }
  async function showDiff(rev: number) {
    if (!note) return;
    try { diff = { rev, text: (await research.noteDiff(note.id, rev, note.rev)).diff }; } catch (x) { toast('error', errorText(x)); }
  }
  async function restoreRev(rev: number) {
    if (!note) return;
    try { const r = await research.restoreNoteVersion(note.id, rev, note.rev); setNote(r.note); versionsOpen = false; toast('ok', t('notes.restored', { rev })); }
    catch (x) { toast('error', errorText(x)); }
  }
  async function checkLean(block?: number) {
    if (!note) return;
    if (dirty) await save();
    checking = block ?? 999;
    try { const r = await research.leanCheckNote(note.id, block); note = r.note; } catch (x) { toast('error', errorText(x)); } finally { checking = -1; }
  }
  async function toDossier(block: number) {
    if (!note) return;
    try {
      const r = await research.noteToDossier(note.id, { block });
      setNote(r.note);
      toast('ok', t('notes.dossierCreated'), { action: { label: t('notes.openDossier'), run: () => navigate(`/d/${encodeURIComponent(r.dossier.id)}`) } });
    } catch (x) { toast('error', errorText(x)); }
  }
  async function complete(typed: string) {
    const s = typed.toLowerCase();
    const opts: { label: string; apply: string; detail?: string }[] = [];
    for (const n of list) if (n.title.toLowerCase().includes(s) && n.id !== note?.id) opts.push({ label: n.title, apply: n.title, detail: t('notes.kindNote') });
    for (const d of Object.values(app.m.dossiers)) if (d.project_id === pid && (d.title.toLowerCase().includes(s) || d.id.includes(s))) opts.push({ label: d.title, apply: `dossier:${d.id}|${d.title}`, detail: t('notes.kindDossier') });
    try {
      const keys = (await research.keys(pid)).keys;
      for (const k of keys) if ((`@${k.key} ${k.title}`).toLowerCase().includes(s.replace(/^@/, ''))) opts.push({ label: `@${k.key}`, apply: `@${k.key}`, detail: k.title });
    } catch { /* sources layer absent */ }
    return opts.slice(0, 30);
  }
  const ctx = $derived({
    noteIdByTitle: new Map(list.map((n) => [n.title.toLowerCase(), n.id])),
    dossierIdByTitle: new Map(Object.values(app.m.dossiers).map((d) => [d.title.toLowerCase(), d.id])),
  });
  const blocks = $derived(leanBlocks(body));
  const resultOf = (i: number): LeanBlockResult | null => note?.lean_blocks.find((b) => b.index === i)?.result ?? null;
  const tags = $derived([...new Set(list.flatMap((n) => n.tags))].sort());
  onDestroy(() => { if (timer) { clearTimeout(timer); if (dirty) void save(); } });
</script>

<ProjectGate>
  {#snippet children(_p)}
    <div class="notes">
      <aside class="nlist" aria-label={t('notes.list')}>
        <div class="row"><h1>{t('notes.title')}</h1><HelpLink page="notes" /></div>
        <div class="row">
          <button class="btn small primary" onclick={() => (creating = true)}><Icon name="plus" size={14} />{t('notes.new')}</button>
          <button class="btn small" onclick={daily}>{t('notes.daily')}</button>
          <a class="btn small" href="/graphe"><Icon name="link" size={14} />{t('nav.graph')}</a>
        </div>
        <label class="sr-only" for="nq">{t('notes.search')}</label>
        <input id="nq" class="input" type="search" placeholder={t('notes.search')} bind:value={q} />
        {#if tags.length}
          <label class="sr-only" for="ntag">{t('sources.tag')}</label>
          <select id="ntag" class="input" bind:value={tagFilter} onchange={() => loadList(pid)}><option value="">{t('sources.allTags')}</option>{#each tags as tg}<option value={tg}>#{tg}</option>{/each}</select>
        {/if}
        <ul>
          {#each hits ?? list as n (n.id)}
            <li><a href="/notes/{encodeURIComponent(n.id)}" aria-current={n.id === nid ? 'page' : undefined}>
              <span class="nt">{n.title}</span>
              {#if 'snippet' in n}<span class="xs muted">{@html String((n as { snippet: string }).snippet).replace(/[<>&]/g, '').replace(/\[/g, '<mark>').replace(/\]/g, '</mark>')}</span>
              {:else}<span class="xs muted">{fmtTime(n.updated)}{#each n.tags as tg} · #{tg}{/each}</span>{/if}
            </a></li>
          {:else}<li class="muted small">{q ? t('list.noMatch') : t('notes.empty')}</li>{/each}
        </ul>
      </aside>

      <section class="editor" aria-label={t('notes.editor')}>
        {#if !note}
          <div class="empty"><h2>{t('notes.pick')}</h2><p>{t('notes.pickText')}</p></div>
        {:else}
          <div class="row ebar">
            <label class="sr-only" for="ntitle">{t('notes.titleLabel')}</label>
            <input id="ntitle" class="input ntitle" bind:value={title} />
            <span class="status xs" role="status">{saving ? t('notes.saving') : dirty ? t('notes.unsaved') : savedAt ? t('notes.saved') : t('notes.rev', { rev: note.rev })}</span>
            <div class="seg" role="radiogroup" aria-label={t('notes.viewMode')}>
              {#each [['edit', 'draft.edit'], ['split', 'notes.split'], ['preview', 'draft.preview']] as [v, k]}
                <label><input type="radio" name="nview" checked={view === v} onchange={() => (view = v as 'edit')} />{t(k as 'draft.edit')}</label>
              {/each}
            </div>
            <button class="btn small" onclick={openVersions}><Icon name="history" size={14} />{t('notes.versions')}</button>
            <a class="btn small" href={research.noteExportUrl(note.id, 'md')} download><Icon name="download" size={14} />.md</a>
            <button class="btn small quiet icon" onclick={remove} aria-label={t('notes.delete')}><Icon name="trash" size={16} /></button>
          </div>
          {#if conflict}<ConflictView {conflict} mineBody={body} mineTitle={title} onresolve={resolved} oncancel={() => { if (conflict) setNote(conflict.current); conflict = null; }} />{/if}
          <div class="panes {view}">
            {#if view !== 'preview'}
              <div class="pane"><CodeEditor bind:value={body} language="natural" label={t('notes.body')} minLines={18} linkComplete={complete} onSubmit={() => save()} />
                <p class="hint">{t('notes.syntax')}</p></div>
            {/if}
            {#if view !== 'edit'}
              <div class="pane preview"><Md src={linkify(body, ctx)} /></div>
            {/if}
          </div>
          {#if blocks.length}
            <section class="lean" aria-labelledby="nlean-h">
              <div class="row"><h2 id="nlean-h">{t('notes.leanBlocks', { n: blocks.length })}</h2><span class="spacer"></span>
                <button class="btn small" onclick={() => checkLean()} disabled={checking >= 0}>{checking === 999 ? t('lean.checking') : t('notes.checkAll')}</button></div>
              {#each blocks as b (b.index)}
                {@const r = resultOf(b.index)}
                <div class="lb">
                  <div class="row"><strong class="small">{t('notes.block', { i: b.index + 1, line: b.startLine })}</strong>
                    {#if r}<span class="chip {r.ok ? 'proved' : 'failed'}">{r.ok ? t('notes.leanOk') : t('notes.leanNo')}</span>{:else}<span class="chip">{t('notes.notChecked')}</span>{/if}
                    <span class="spacer"></span>
                    <button class="btn small" onclick={() => checkLean(b.index)} disabled={checking >= 0}>{checking === b.index ? t('lean.checking') : t('lean.check')}</button>
                    <button class="btn small" onclick={() => toDossier(b.index)}>{t('notes.toDossier')}</button>
                  </div>
                  {#if r && !r.ok}<CheckResultView check={{ ...r, axioms: null, reasons: r.reasons ?? [], cancelled: false }} />{/if}
                </div>
              {/each}
            </section>
          {/if}
          <section class="back" aria-labelledby="bl-h">
            <h2 id="bl-h">{t('notes.backlinks', { n: backlinks.length })}</h2>
            {#if backlinks.length}
              <ul>{#each backlinks as b (b.id)}<li><a href="/notes/{encodeURIComponent(b.id)}">{b.title}</a> <span class="small muted">… {b.context} …</span></li>{/each}</ul>
            {:else}<p class="small muted">{t('notes.noBacklinks')}</p>{/if}
          </section>
        {/if}
      </section>
    </div>

    <Dialog bind:open={creating} title={t('notes.new')}>
      <form id="newnote" onsubmit={create}><div class="field"><label for="nn">{t('notes.titleLabel')}</label><input id="nn" class="input" bind:value={newTitle} /></div></form>
      {#snippet actions()}<button class="btn quiet" onclick={() => (creating = false)}>{t('common.cancel')}</button><button class="btn primary" type="submit" form="newnote">{t('notes.create')}</button>{/snippet}
    </Dialog>
    <Dialog bind:open={versionsOpen} title={t('notes.versions')} wide>
      <ol class="vers" reversed>
        {#each versions as v (v.rev)}
          <li><strong>{t('notes.rev', { rev: v.rev })}</strong> <span class="xs muted">{fmtTime(v.t)} · {v.device || '—'}{v.reason ? ` · ${v.reason}` : ''}</span>
            <button class="btn small" onclick={() => showDiff(v.rev)}>{t('notes.diff')}</button>
            {#if v.rev !== note?.rev}<button class="btn small primary" onclick={() => restoreRev(v.rev)}>{t('versions.restore')}</button>{/if}
            {#if diff?.rev === v.rev}<pre class="diff">{#each diff.text.split('\n') as line}<span class={line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : ''}>{line}{'\n'}</span>{/each}</pre>{/if}
          </li>
        {/each}
      </ol>
      <p class="hint">{t('notes.versionsHint')}</p>
    </Dialog>
  {/snippet}
</ProjectGate>

<style>
  .notes { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--s-4); max-width: 1500px; }
  @media (max-width: 900px) { .notes { grid-template-columns: minmax(0, 1fr); } }
  .nlist { display: grid; gap: var(--s-2); align-content: start; }
  .nlist h1 { margin: 0; }
  .nlist ul { list-style: none; padding: 0; margin: 0; max-height: 60vh; overflow: auto; }
  .nlist li a { display: grid; padding: 6px 8px; border-radius: var(--r-2); color: var(--text); text-decoration: none; min-height: 40px; }
  .nlist li a:hover { background: var(--surface-2); }
  .nlist li a[aria-current='page'] { background: var(--accent-soft); }
  .nt { font-weight: 600; }
  .nlist :global(mark) { background: color-mix(in srgb, var(--running-fill) 40%, transparent); color: inherit; }
  .ebar { margin-bottom: var(--s-2); }
  .ntitle { flex: 1; min-width: 12rem; font: 600 1.25rem var(--font-serif); }
  .status { color: var(--text-3); min-width: 7rem; }
  .panes { display: grid; gap: var(--s-3); }
  .panes.split { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  @media (max-width: 1100px) { .panes.split { grid-template-columns: minmax(0, 1fr); } }
  .pane { min-width: 0; }
  .preview { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-3) var(--s-4); font-family: var(--font-serif); line-height: 1.65; max-height: 75vh; overflow: auto; }
  .lean, .back { margin-top: var(--s-4); }
  .lean h2, .back h2 { font-size: var(--fs-md); margin: 0; }
  .lb { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin-top: var(--s-2); background: var(--surface); }
  .back ul { padding-left: 1.2em; }
  .empty { max-width: 34rem; }
  .vers { list-style: none; padding: 0; display: grid; gap: var(--s-2); }
  .diff { font: 0.8125rem/1.45 var(--font-mono); background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 300px; overflow: auto; }
  .diff .add { color: var(--proved); } .diff .del { color: var(--failed); }
</style>
