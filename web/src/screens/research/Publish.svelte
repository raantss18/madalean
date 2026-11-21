<script lang="ts">
  // « Publier » (ARCHITECTURE §17 role 1, docs/RESEARCH_SOURCES.md §12): choose what goes on the public site,
  // build the exact list of files (nothing is sent), preview the site locally, then push — the push carries the id
  // of the list you reviewed, so nothing else can leave. Statuses are recomputed from Lean's facts by the template.
  import { ApiError } from '../../lib/api/client';
  import { research, type NoteSummary, type PublishManifest, type PublishState } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtBytes, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import Icon from '../../components/Icon.svelte';
  import GithubCheck from '../../components/GithubCheck.svelte';
  import { consigne } from '../../lib/api/consigne';

  let { params: _p }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  let available = $state(true);
  let manifest = $state<PublishManifest | null>(null);
  let last = $state<PublishState | null>(null);
  let notes = $state<NoteSummary[]>([]);
  let dossiers = $state<string[]>([]);
  let noteIds = $state<string[]>([]);
  let includePdf = $state(false);
  let license = $state('CC-BY-4.0');
  let repo = $state('');
  let create = $state(false);
  let priv = $state(false);
  let previewUrl = $state('');
  let hasPreview = $state(false);
  let busy = $state('');
  let progress = $state<string[]>([]);
  let confirm = $state(false);
  let err = $state('');

  const projectDossiers = $derived(Object.values(app.m.dossiers).filter((d) => d.project_id === pid && !d.archived).sort((a, b) => a.created - b.created));
  async function load() {
    if (!pid) return;
    try {
      const r = await research.publishState(pid);
      available = true; manifest = r.manifest; last = r.state; hasPreview = r.preview;
      if (last?.repo) repo = last.repo;
    } catch (e) { if (e instanceof ApiError && (e.status === 404 || e.status === 405)) available = false; else err = errorText(e); }
    research.notes(pid).then((r) => (notes = r.notes)).catch(() => {});
  }
  $effect(() => { void pid; void load(); });
  let preselected = '';
  $effect(() => { if (preselected !== pid && projectDossiers.length) { preselected = pid; dossiers = projectDossiers.filter((d) => d.proved).map((d) => d.id);
    // what was sent here from the project search (« → Publier ») is preselected too
    consigne.basket(pid).then((r) => { dossiers = [...new Set([...dossiers, ...r.basket.dossiers.filter((id) => projectDossiers.some((d) => d.id === id))])]; noteIds = [...new Set([...noteIds, ...r.basket.notes])]; }).catch(() => {}); } });

  async function plan() {
    busy = 'plan'; err = ''; previewUrl = ''; hasPreview = false;
    try { manifest = (await research.publishPlan(pid, { dossiers, notes: noteIds, include_pdf: includePdf, license })).manifest; }
    catch (e) { err = errorText(e); } finally { busy = ''; }
  }
  async function preview() {
    if (!manifest) return;
    busy = 'preview'; err = '';
    try { previewUrl = (await research.publishPreview(pid, manifest.id)).url; hasPreview = true; }
    catch (e) { err = e instanceof ApiError && e.kind === 'manifest_changed' ? t('publish.changed') : errorText(e); } finally { busy = ''; }
  }
  async function push() {
    if (!manifest) return;
    confirm = false; busy = 'push'; progress = []; err = '';
    try {
      // the site sent is the local preview: build it first when it was not (the push used to stop on « no preview »)
      if (!hasPreview) { progress = [t('publish.building')]; previewUrl = (await research.publishPreview(pid, manifest.id)).url; hasPreview = true; }
      const r = await research.publishPush(pid, { manifest_id: manifest.id, repo: repo.trim(), create, private: priv });
      await new Promise<void>((resolve) => {
        app.listenRequest(r.request_id, (ev) => {
          if (ev.type === 'publish.progress') progress = [...progress, tk(`publish.step.${String(ev['step'])}`, String(ev['step']))];
          else if (ev.type === 'publish.done') { last = ev['state'] as PublishState; toast('ok', last.changed ? t('publish.pushed', { url: last.pages_url || last.repo }) : t('publish.upToDate')); resolve(); }
          else if (ev.type === 'publish.error') { err = (ev['message'] as { text?: string } | undefined)?.text || tk(`publish.err.${String(ev['error'])}`, t('publish.err.unknown', { code: String(ev['error']) })); resolve(); }
        });
      });
    } catch (e) { err = e instanceof ApiError && e.kind === 'manifest_changed' ? t('publish.changed') : errorText(e); } finally { busy = ''; }
  }
  const totalSize = $derived((manifest?.items ?? []).reduce((n, i) => n + i.size, 0));
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="pub">
      <div class="row"><h1>{t('publish.title')}</h1><HelpLink page="publish" /></div>
      <p class="lead">{t('publish.lead')}</p>
      {#if !available}<p class="notice small" role="note"><Icon name="info" size={14} /> {t('publish.notYet')}</p>{/if}
      {#if last?.pushed_at}<p class="small">{t('publish.last', { repo: last.repo, t: fmtTime(last.pushed_at) })} {#if last.pages_url}<a href={last.pages_url} target="_blank" rel="noopener noreferrer">{last.pages_url}</a>{/if}</p>{/if}

      <section class="panel" aria-labelledby="pub-choose">
        <h2 id="pub-choose">{t('publish.choose')}</h2>
        <fieldset class="list"><legend class="label">{t('publish.results')}</legend>
          {#each projectDossiers as d (d.id)}
            <label class="switch small"><input type="checkbox" value={d.id} bind:group={dossiers} />
              <span>{d.title} <span class="chip {d.proved ? 'proved' : 'running'}">{d.proved ? t('publish.verifiedLean') : t('publish.claimOnly')}</span></span></label>
          {:else}<p class="muted small">{t('publish.noDossier')}</p>{/each}
        </fieldset>
        {#if notes.length}
          <fieldset class="list"><legend class="label">{t('publish.notes')}</legend>
            {#each notes as n (n.id)}<label class="switch small"><input type="checkbox" value={n.id} bind:group={noteIds} />{n.title}</label>{/each}
            <p class="hint">{t('publish.notesHint')}</p>
          </fieldset>
        {/if}
        <label class="switch small"><input type="checkbox" bind:checked={includePdf} />{t('publish.includePdf')}</label>
        <div class="field" style="max-width: 16rem"><label for="lic">{t('publish.license')}</label><input id="lic" class="input" bind:value={license} /></div>
        <button class="btn primary" onclick={plan} disabled={!available || !!busy || !dossiers.length}>{busy === 'plan' ? t('publish.planning') : t('publish.makeList')}</button>
        <p class="hint">{t('publish.nothingSent')}</p>
      </section>

      {#if manifest}
        <section class="panel leaves" aria-labelledby="pub-leaves">
          <h2 id="pub-leaves">{t('publish.leaves')}</h2>
          <p class="small">{t('publish.summary', { n: manifest.items.length, size: fmtBytes(totalSize), lean: manifest.toolchain, mathlib: manifest.mathlib.slice(0, 10) })}</p>
          {#if Object.keys(manifest.statuses).length}
            <p class="small">{#each Object.entries(manifest.counts) as [k, n]}<span class="chip">{tk(`bp.state.${k}`, k)} : {n}</span> {/each}</p>
          {/if}
          {#each manifest.warnings as w}<p class="small warn">{tk(`publish.warn.${w.split(':')[0]}`, w, { id: w.split(':')[1] ?? '' })}</p>{/each}
          <details open><summary class="small">{t('publish.files', { n: manifest.items.length })}</summary>
            <table class="tbl">
              <caption class="sr-only">{t('publish.leaves')}</caption>
              <thead><tr><th scope="col">{t('publish.file')}</th><th scope="col">{t('publish.kindCol')}</th><th scope="col">{t('publish.originCol')}</th><th scope="col">{t('publish.sizeCol')}</th></tr></thead>
              <tbody>{#each manifest.items as it (it.path)}<tr><td class="mono xs">{it.path}</td><td class="small">{tk(`publish.kind.${it.kind}`, it.kind)}</td><td class="small">{it.origin}</td><td class="small">{fmtBytes(it.size)}</td></tr>{/each}</tbody>
            </table>
          </details>
          {#if manifest.excluded.length}
            <h3>{t('publish.excluded')}</h3>
            <ul class="small">{#each manifest.excluded as x}<li>{x.what} — {tk(`publish.why.${x.why}`, x.why)}{x.license ? ` (${x.license})` : ''}</li>{/each}</ul>
          {/if}
          <h3>{t('publish.neverTitle')}</h3>
          <ul class="small">{#each manifest.not_included as x}<li>{x}</li>{/each}</ul>
          <div class="row">
            <button class="btn" onclick={preview} disabled={!!busy}>{busy === 'preview' ? t('publish.building') : t('publish.preview')}</button>
            {#if previewUrl}<a class="btn" href={previewUrl} target="_blank" rel="noopener">{t('publish.openPreview')}</a>{/if}
          </div>
        </section>

        <section class="panel" aria-labelledby="pub-push">
          <h2 id="pub-push">{t('publish.pushTitle')}</h2>
          <div class="field"><label for="repo">{t('publish.repo')}</label><input id="repo" class="input" bind:value={repo} placeholder="compte/nom-du-depot" /><p class="hint">{t('publish.repoHint')}</p></div>
          <label class="switch small"><input type="checkbox" bind:checked={create} />{t('publish.create')}</label>
          {#if create}<label class="switch small"><input type="checkbox" bind:checked={priv} />{t('publish.privateRepo')}</label>{/if}
          <p class="hint">{t('publish.tokenHint')} <a href="/reglages/cles">{t('settings.sec.keys')}</a></p>
          <button class="btn primary" onclick={() => (confirm = true)} disabled={!!busy || !/^[\w.-]+\/[\w.-]+$/.test(repo.trim()) || !app.m.local}>{t('publish.push')}</button>
          {#if !app.m.local}<p class="small muted">{t('publish.hostOnly')}</p>{/if}
          <details class="ghbox"><summary class="small">{t('gh.testTitle')}</summary><GithubCheck {repo} {priv} /></details>
          {#if progress.length}<ol class="small steps" aria-live="polite">{#each progress as p}<li>{p}</li>{/each}</ol>{/if}
          {#if last?.pages_error}
            <p class="small warn" role="note">{t('publish.pagesFailed')} {last.pages_error.message || tk(`gh.code.${last.pages_error.error}`, '', last.pages_error as Record<string, string>)}
              {#if last.pages_settings}<a href={last.pages_settings} target="_blank" rel="noopener noreferrer">{t('publish.pagesManual')}</a>{/if}</p>
          {/if}
          {#if confirm}
            <div class="confirm" role="group" aria-labelledby="pc-h">
              <h3 id="pc-h">{t('publish.confirmTitle', { n: manifest.items.length, repo })}</h3>
              <p class="small">{t('publish.confirmText')}</p>
              <div class="row"><button class="btn primary" onclick={push}>{t('publish.confirmPush')}</button><button class="btn quiet" onclick={() => (confirm = false)}>{t('common.cancel')}</button></div>
            </div>
          {/if}
        </section>
      {/if}
      {#if err}<p class="error-text" role="alert">{err}</p>{/if}
    </div>
  {/snippet}
</ProjectGate>

<style>
  .pub { max-width: 920px; }
  .lead { color: var(--text-2); }
  .notice { background: var(--info-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); display: flex; gap: 6px; align-items: center; }
  .list { border: 0; padding: 0; margin: 0 0 var(--s-3); display: grid; gap: 2px; min-width: 0; }
  .list .chip { white-space: normal; }
  .list .switch { align-items: flex-start; }
  .list .switch { min-height: 36px; }
  .warn { color: var(--running); }
  .tbl { width: 100%; border-collapse: collapse; table-layout: fixed; overflow-wrap: anywhere; }
  .tbl th, .tbl td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--line); }
  .leaves h3 { font-size: var(--fs-sm); margin: var(--s-3) 0 4px; }
  .confirm { border: 2px solid var(--running-fill); background: var(--running-soft); border-radius: var(--r-2); padding: var(--s-3); margin-top: var(--s-3); }
  .confirm h3 { font-size: var(--fs-md); margin: 0; }
  .steps { padding-left: 1.2em; }
  .ghbox { margin: var(--s-2) 0; }
</style>
