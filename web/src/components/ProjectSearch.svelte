<script lang="ts">
  // One search across the project: dossiers, notes, Calcul cells and figures, source passages, suggestions. Every
  // result opens where it lives, and can be sent to the article or to « Publier » (your explicit action).
  import { consigne, type SearchResult } from '../lib/api/consigne';
  import { t, tk } from '../lib/i18n/index.svelte';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import Icon from './Icon.svelte';

  let { pid }: { pid: string } = $props();
  let q = $state('');
  let results = $state<SearchResult[] | null>(null);
  let busy = $state(false);

  async function run(e?: Event) {
    e?.preventDefault();
    if (!q.trim()) return;
    busy = true;
    try { results = (await consigne.search(pid, q.trim())).results; } catch (err) { toast('error', errorText(err)); } finally { busy = false; }
  }
  function href(r: SearchResult): string {
    switch (r.kind) {
      case 'dossier': return `/d/${encodeURIComponent(r.id)}`;
      case 'note': return `/notes/${encodeURIComponent(r.id)}`;
      case 'calcul': case 'figure': return '/calcul';
      case 'passage': return `/sources/${encodeURIComponent(pid)}/${encodeURIComponent(r.source_id ?? '')}${r.page ? `#p${r.page}` : ''}`;
      default: return '/article#suggestions';
    }
  }
  async function toArticle(r: SearchResult) {
    try {
      await consigne.toArticle(pid, r.kind === 'passage' ? { kind: 'passage', id: r.id, source_key: r.source_key ?? '', text: r.snippet, locator: r.title.replace(r.source_key ?? '', '').trim() } : { kind: r.kind, id: r.id, title: r.title });
      toast('ok', t('psearch.addedArticle'));
    } catch (e) { toast('error', errorText(e)); }
  }
  async function toPublish(r: SearchResult) {
    try { await consigne.toBasket(pid, r.kind, r.id); toast('ok', t('psearch.addedPublish')); } catch (e) { toast('error', errorText(e)); }
  }
  const canArticle = (r: SearchResult) => ['dossier', 'note', 'calcul', 'figure', 'passage'].includes(r.kind);
  const canPublish = (r: SearchResult) => ['dossier', 'note', 'calcul', 'figure'].includes(r.kind);
</script>

<section class="panel" aria-labelledby="ps-h">
  <h2 id="ps-h">{t('psearch.title')}</h2>
  <form class="row" role="search" onsubmit={run}>
    <label class="sr-only" for="ps-q">{t('psearch.label')}</label>
    <input id="ps-q" class="input grow" type="search" bind:value={q} placeholder={t('psearch.placeholder')} />
    <button class="btn" type="submit" disabled={busy || !q.trim()}><Icon name="search" size={14} />{t('psearch.go')}</button>
  </form>
  {#if results}
    <p class="xs muted" role="status">{t('psearch.count', { n: results.length })}</p>
    <ul class="res">
      {#each results as r (r.kind + r.id)}
        <li>
          <div class="row"><span class="chip">{tk(`psearch.kind.${r.kind}`, r.kind)}</span><a href={href(r)} class="small">{r.title || r.id}</a>
            <span class="spacer"></span>
            {#if canArticle(r)}<button class="btn small quiet" onclick={() => toArticle(r)} aria-label={t('psearch.toArticleOf', { t: r.title || r.id })}>{t('psearch.toArticle')}</button>{/if}
            {#if canPublish(r)}<button class="btn small quiet" onclick={() => toPublish(r)} aria-label={t('psearch.toPublishOf', { t: r.title || r.id })}>{t('psearch.toPublish')}</button>{/if}
          </div>
          {#if r.snippet}<p class="xs muted snip">{r.snippet}</p>{/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .grow { flex: 1; min-width: 10rem; }
  .res { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--s-2); }
  .res li { border-top: 1px solid var(--line); padding-top: 6px; }
  .snip { margin: 2px 0 0; overflow-wrap: anywhere; }
</style>
