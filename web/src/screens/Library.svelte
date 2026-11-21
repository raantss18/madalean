<script lang="ts">
  // Library of proven results (reused as lemmas). Remove with undo; export one .lean per workspace.
  import type { LibEntry } from '../lib/api/types';
  import { api } from '../lib/api/client';
  import { app } from '../lib/store/app.svelte';
  import { t, fmtTime } from '../lib/i18n/index.svelte';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import Icon from '../components/Icon.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  let entries = $state<LibEntry[] | null>(null);
  let err = $state('');
  let q = $state('');
  let open = $state<string | null>(null);

  $effect(() => {
    void app.m.libraryRev;
    api.library().then((r) => { entries = r.entries; err = ''; }).catch((e) => { err = errorText(e); });
  });
  const shown = $derived((entries ?? []).filter((e) => !q.trim() || (e.name + ' ' + e.title + ' ' + e.statement).toLowerCase().includes(q.trim().toLowerCase())).sort((a, b) => b.t - a.t));
  const workspaces = $derived([...new Set((entries ?? []).map((e) => e.workspace))]);

  async function remove(e: LibEntry) {
    entries = (entries ?? []).filter((x) => x.name !== e.name);
    try {
      const r = await api.deleteLibrary(e.name);
      toast('ok', t('library.removed', { name: e.name }), { action: { label: t('common.undo'), run: async () => {
        try { await api.restoreLibrary(r.removed); } catch (x) { toast('error', errorText(x)); }
      } } });
    } catch (x) {
      entries = [...(entries ?? []), e];
      toast('error', errorText(x));
    }
  }
</script>

<div class="lib">
  <div class="row head">
    <h1>{t('library.title')}</h1>
    <span class="spacer"></span>
    {#each workspaces as w}<a class="btn small" href={api.libraryExportUrl(w)} download><Icon name="download" size={14} />{t('library.export', { w })}</a>{/each}
  </div>
  <p class="lead">{t('library.lead')}</p>
  <label class="sr-only" for="lib-q">{t('library.search')}</label>
  <input id="lib-q" class="input" type="search" placeholder={t('library.search')} bind:value={q} style="max-width: 420px; margin-bottom: var(--s-4)" />
  {#if err}<p class="error-text" role="alert">{err}</p>
  {:else if entries === null}<p aria-busy="true" class="muted">{t('common.loading')}</p>
  {:else if entries.length === 0}
    <div class="empty"><h2>{t('library.emptyTitle')}</h2><p>{t('library.emptyText')}</p><a class="btn primary" href="/">{t('library.emptyAction')}</a></div>
  {:else}
    <ul class="entries">
      {#each shown as e (e.name)}
        <li>
          <div class="row">
            <span class="mark" aria-hidden="true">∎</span>
            <div class="txt">
              <strong>{e.title || e.name}</strong>
              <span class="mono xs muted">{e.name} · {e.workspace} · {fmtTime(e.t)}</span>
            </div>
            <button class="btn small" aria-expanded={open === e.name} onclick={() => (open = open === e.name ? null : e.name)}>{open === e.name ? t('common.hide') : t('library.show')}</button>
            {#if e.dossier && app.m.dossiers[e.dossier]}<a class="btn small" href="/d/{encodeURIComponent(e.dossier)}">{t('library.openDossier')}</a>{/if}
            <button class="btn small danger" onclick={() => remove(e)} aria-label={t('library.removeOne', { name: e.name })}><Icon name="trash" size={14} /></button>
          </div>
          {#if open === e.name}<pre class="code">{e.code || e.statement}</pre>{#if e.deps.length}<p class="xs muted">{t('library.deps', { d: e.deps.join(', ') })}</p>{/if}{/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .lib { max-width: 980px; }
  .head h1 { margin: 0; }
  .lead { color: var(--text-2); }
  .entries { list-style: none; padding: 0; margin: 0; }
  .entries li { border-bottom: 1px solid var(--line); padding: var(--s-2) 0; }
  .mark { color: var(--proved); font-size: 1.1rem; }
  .txt { flex: 1; min-width: 12rem; display: grid; }
  .code { font: 0.8125rem/1.5 var(--font-mono); background: var(--surface-2); padding: var(--s-3); border-radius: var(--r-2); white-space: pre-wrap; overflow-wrap: anywhere; }
  .empty { max-width: 34rem; }
</style>
