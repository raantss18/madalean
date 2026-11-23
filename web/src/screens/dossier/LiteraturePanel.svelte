<script lang="ts">
  // « Littérature » (S-AX, D56): references found for the statement (retrieved records only), the passage quoted word
  // for word with its place, the Lean statement and its status; and the dossier's attachments, each read once.
  // A result that is not proved in Lean is never shown as such: « à prouver » / « preuve conditionnelle ».
  import type { Dossier } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { literature, ATTACH_ACCEPT, type LitState, type LitItem, type Attachment } from '../../lib/api/literature';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { navigate } from '../../lib/router.svelte';
  import { reportError } from './actions';
  import Icon from '../../components/Icon.svelte';

  let { dossier: d }: { dossier: Dossier } = $props();
  let st = $state<LitState | null>(null);
  let atts = $state<Attachment[]>([]);
  let busy = $state('');
  let url = $state('');
  let fileInput = $state<HTMLInputElement | null>(null);
  let rev = $state(0);

  async function load(id: string) {
    try {
      const [a, b] = await Promise.all([literature.get(id), literature.attachments(id)]);
      if (id === d.id) { st = a; atts = b.attachments; }
    } catch (e) { reportError(e, id); }
  }
  $effect(() => { void rev; void load(d.id); });
  $effect(() => app.on('literature.updated', (ev) => { if ((ev as { dossier_id?: string }).dossier_id === d.id) rev++; }));

  const res = $derived(st?.literature ?? null);
  const items = $derived((res?.items ?? []).filter((i) => i.quotes.length));

  async function act(key: string, fn: () => Promise<unknown>, ok?: string) {
    busy = key;
    try { await fn(); if (ok) toast('ok', ok); rev++; } catch (e) { reportError(e, d.id); } finally { busy = ''; }
  }
  const search = (refresh = false) => act('search', () => literature.search(d.id, st?.depth, refresh));
  async function prove(it: LitItem) {
    busy = 'prove' + it.id;
    try { const r = await literature.prove(d.id, it.id); navigate(`/d/${encodeURIComponent(r.dossier.id)}`); }
    catch (e) { reportError(e, d.id); } finally { busy = ''; }
  }
  async function attach(files: FileList | null) {
    for (const f of Array.from(files ?? [])) {
      await act('attach', () => literature.attachFile(d.id, f), t('lit.attached', { name: f.name }));
    }
    if (fileInput) fileInput.value = '';
  }
  async function attachUrl() {
    const u = url.trim();
    if (!u) return;
    await act('attach', () => literature.attachUrl(d.id, u), t('lit.attached', { name: u }));
    url = '';
  }
  function who(it: LitItem): string {
    const a = it.reference.authors;
    return a.slice(0, 3).join(', ') + (a.length > 3 ? ' et al.' : '');
  }
</script>

<section class="panel lit" aria-labelledby="lit-h">
  <h2 id="lit-h"><Icon name="book" size={16} /> {t('lit.title')}</h2>
  <p class="hint small">{t('lit.intro')}</p>

  {#if st?.conditional?.verdict === 'proved_modulo'}
    <div class="cond" role="status">
      <strong>{t('lit.conditional')}</strong>
      <span class="small">{t('lit.conditionalText', { refs: st.conditional.cited.map((c) => c.short).join(', ') })}</span>
    </div>
  {/if}

  <div class="row actions">
    {#if st?.running}
      <span class="chip running" role="status">{t('lit.running')}</span>
      <button class="btn small" onclick={() => act('stop', () => literature.stop(d.id))}>{t('common.stop')}</button>
    {:else}
      <button class="btn small primary" disabled={busy === 'search' || st?.mode === 'local' || !d.statements.length} onclick={() => search(Boolean(res))}>
        {res ? t('lit.again') : t('lit.searchStatement')}
      </button>
    {/if}
    {#if st?.mode === 'local'}<span class="xs muted">{t('lit.local')}</span>{/if}
  </div>

  {#if res}
    <p class="small muted">
      {#if res.message === 'found'}{t('lit.found', { n: items.length })}{:else if res.message === 'cancelled'}{t('lit.cancelled')}{:else if res.local_mode}{t('lit.local')}{:else}{t('lit.nothing')}{/if}
      {#if res.cached} · {t('lit.cached')}{/if}{#if st?.stale} · {t('lit.stale')}{/if}
    </p>
    <ol class="refs">
      {#each items as it (it.id)}
        {@const r = it.reference}
        {@const q = it.quotes[0]!}
        <li class="ref">
          <div class="head">
            <a class="title" href={r.url || undefined} target="_blank" rel="noopener noreferrer">{r.title}</a>
            <span class="chip {r.peer_reviewed ? 'proved' : r.kind === 'preprint' ? 'running' : ''}">{tk(`lit.kind.${r.kind}`, r.kind)}</span>
          </div>
          <p class="xs muted">{who(it)} ({r.year ?? '—'}){#if r.venue} · <em>{r.venue}</em>{/if} · {t('lit.via', { list: r.confirmed_by.join(', ') })}</p>
          <blockquote class="quote"><p>« {q.text} »</p><footer class="xs muted">{q.location}{#if q.picked_by.startsWith('model')} · {t('lit.pickedByModel')}{/if}</footer></blockquote>
          <div class="lean">
            <span class="chip st-{it.lean.status}">{tk(`lit.status.${it.lean.status}`, it.lean.status)}</span>
            {#if it.lean.mathlib_name}<code class="xs">{it.lean.mathlib_name}</code>{/if}
            {#if it.lean.statement}
              <details><summary class="xs">{t('lit.leanStatement')}</summary><pre class="code">{it.lean.statement}</pre><p class="xs muted">{t('lit.translated')}</p></details>
            {/if}
          </div>
          <div class="row btns">
            <button class="btn small" disabled={busy !== ''} onclick={() => act('src' + it.id, () => literature.addSource(d.id, it.id), t('lit.addedSource'))}>{t('lit.addSource')}</button>
            <button class="btn small" disabled={busy !== ''} onclick={() => act('cite' + it.id, () => literature.cite(d.id, it.id), t('lit.addedBib'))}>{t('lit.addBib')}</button>
            {#if it.lean.status === 'to_prove'}
              {#if it.lean.child_dossier}<a class="btn small" href="/d/{encodeURIComponent(it.lean.child_dossier)}">{t('lit.openLemma')}</a>
              {:else}<button class="btn small" disabled={busy !== ''} onclick={() => prove(it)}>{t('lit.prove')}</button>{/if}
            {/if}
            {#if it.bibtex}<details class="bib"><summary class="xs">BibTeX</summary><pre class="code">{it.bibtex}</pre></details>{/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  <h3 id="att-h">{t('lit.attachments')}</h3>
  <p class="hint small">{t('lit.attachIntro')}</p>
  <div class="row attach">
    <input bind:this={fileInput} id="lit-file" class="sr-only" type="file" accept={ATTACH_ACCEPT} multiple onchange={(e) => attach((e.target as HTMLInputElement).files)} />
    <label for="lit-file" class="btn small"><Icon name="paperclip" size={14} /> {t('lit.attachFile')}</label>
    <form class="urlform" onsubmit={(e) => { e.preventDefault(); void attachUrl(); }}>
      <label class="sr-only" for="lit-url">{t('lit.attachUrl')}</label>
      <input id="lit-url" class="input" type="url" placeholder="https://…" bind:value={url} />
      <button class="btn small" disabled={!url.trim() || busy === 'attach'}>{t('lit.attachUrl')}</button>
    </form>
  </div>
  {#if atts.length}
    <ul class="atts" aria-labelledby="att-h">
      {#each atts as a (a.n)}
        <li>
          <details>
            <summary>
              <span class="xs muted">{t('lit.attachmentN', { n: a.n })}</span> <span class="name">{a.name}</span>
              <span class="chip {a.state === 'read' ? 'proved' : a.state === 'reading' ? 'running' : 'failed'}">{tk(`lit.att.${a.state}`, a.state)}</span>
              {#if a.verified}<span class="chip proved">{t('lit.att.verified')}</span>{:else if a.state === 'read'}<span class="chip">{t('lit.att.unverified')}</span>{/if}
            </summary>
            {#if a.transcription}<p class="xs muted">{t('lit.transcription', { model: a.transcription.model })}</p><pre class="code">{a.transcription.text}</pre>{/if}
            {#each a.items as it (it.id)}
              {@const q = it.quotes[0]}
              {#if q}
                <blockquote class="quote"><p>« {q.text} »</p><footer class="xs muted">{q.location}</footer></blockquote>
                <span class="chip st-{it.lean.status}">{tk(`lit.status.${it.lean.status}`, it.lean.status)}</span>
                {#if it.lean.statement}<pre class="code">{it.lean.statement}</pre>{/if}
              {/if}
            {:else}<p class="xs muted">{a.state === 'reading' ? t('lit.att.reading') : t('lit.att.none')}</p>{/each}
            <button class="btn small quiet" onclick={() => act('reread', () => literature.reread(d.id, a.n))}>{t('lit.reread')}</button>
          </details>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .lit h2 { margin: 0; display: flex; align-items: center; gap: 8px; }
  .lit h3 { margin: var(--s-4) 0 var(--s-1); font-size: 1rem; }
  .actions, .btns, .attach { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; margin: var(--s-2) 0; }
  .refs, .atts { list-style: none; padding: 0; margin: var(--s-2) 0 0; display: grid; gap: var(--s-3); }
  .ref { border-top: 1px solid var(--line); padding-top: var(--s-2); }
  .head { display: flex; gap: var(--s-2); align-items: baseline; flex-wrap: wrap; }
  .title { font-weight: 600; color: var(--text); }
  .quote { margin: var(--s-2) 0; padding: var(--s-2) var(--s-3); border-left: 3px solid var(--line-strong); background: var(--surface-2); border-radius: var(--r-1); }
  .quote p { margin: 0; font-family: var(--font-serif); overflow-wrap: anywhere; }
  .quote footer { margin-top: 4px; }
  .code { font: 0.75rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); max-height: 220px; overflow: auto; }
  .lean { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
  .lean details { flex-basis: 100%; }
  .st-to_prove { border: 1.5px dashed var(--running); color: var(--running); }
  .st-in_mathlib, .st-proved { color: var(--proved); }
  .cond { border: 2px dashed var(--running-fill); background: var(--running-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); display: grid; gap: 4px; margin: var(--s-2) 0; }
  .cond strong { color: var(--running); }
  .urlform { display: flex; gap: var(--s-2); flex: 1 1 16rem; min-width: 0; }
  .urlform .input { flex: 1; min-width: 0; }
  .atts summary { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-height: var(--touch); cursor: pointer; }
  .atts .name { overflow-wrap: anywhere; }
  .bib { flex-basis: 100%; }
</style>
