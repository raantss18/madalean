<script lang="ts">
  // Dialogs of the article editor: title and authors, figure insertion (Calcul / image / TikZ), versions, Overleaf
  // round trip, new section.
  import { articleApi, type TexSettings, type TexFile, type Version, type Overleaf } from '../../../lib/api/article';
  import { request } from '../../../lib/api/client';
  import { t, fmtTime } from '../../../lib/i18n/index.svelte';
  import { toast } from '../../../lib/ui/toasts.svelte';
  import { errorText } from '../../../lib/ui/errors';
  import Dialog from '../../../components/Dialog.svelte';

  let { pid, dialog = $bindable(''), settings, onfigure, onsection, onrestored, onsettings, onimported, beforeChange }: {
    pid: string; dialog?: string; settings: TexSettings; onfigure: (path: string, caption: string) => void; onsection: (title: string) => void;
    onrestored: () => void; onsettings: (s: TexSettings, files: TexFile[]) => void; onimported: () => void; beforeChange: () => Promise<void>;
  } = $props();

  // ---- title & authors
  let title = $state('');
  let authors = $state<{ name: string; affiliation?: string; email?: string }[]>([]);
  let date = $state('');
  $effect(() => { if (dialog === 'title') { title = settings.front.title; authors = settings.front.authors.map((a) => ({ ...a })); date = settings.front.date; if (!authors.length) authors = [{ name: '' }]; } });
  async function saveTitle() {
    try {
      await beforeChange();
      const r = await articleApi.settings(pid, { front: { title, authors: authors.filter((a) => a.name.trim()), date } });
      onsettings(r.settings, r.files);
      dialog = '';
    } catch (e) { toast('error', errorText(e)); }
  }

  // ---- figures
  let figTab = $state<'calcul' | 'image' | 'tikz'>('calcul');
  let assets = $state<string[]>([]);
  let caption = $state('');
  let chosen = $state('');
  let file = $state<File | null>(null);
  let loadingAssets = $state(false);
  function collect(o: unknown, out: Set<string>) {
    if (!o || typeof o !== 'object') return;
    if (Array.isArray(o)) { for (const x of o) collect(x, out); return; }
    const r = o as Record<string, unknown>;
    if (typeof r['asset'] === 'string' && /^[0-9a-f]{32}$/.test(r['asset']) && (!r['mime'] || r['mime'] === 'image/png')) out.add(r['asset']);
    for (const v of Object.values(r)) collect(v, out);
  }
  $effect(() => {
    if (dialog !== 'figure') return;
    caption = ''; chosen = ''; file = null; loadingAssets = true;
    request<unknown>('GET', `/calcul/${encodeURIComponent(pid)}`).then((r) => { const s = new Set<string>(); collect(r, s); assets = [...s].reverse().slice(0, 40); })
      .catch(() => (assets = [])).finally(() => (loadingAssets = false));
  });
  async function insertFigure() {
    try {
      if (figTab === 'tikz') {
        onfigure('', '');
        dialog = '';
        return;
      }
      const r = figTab === 'calcul' ? await articleApi.figureFromCalcul(pid, chosen) : await articleApi.figureUpload(pid, file!);
      onfigure(r.path, caption.replace(/[{}\\]/g, ''));
      dialog = '';
    } catch (e) { toast('error', errorText(e)); }
  }

  // ---- versions
  let versions = $state<Version[]>([]);
  let vlabel = $state('');
  let confirmV = $state('');
  async function loadVersions() { try { versions = (await articleApi.versions(pid)).versions; } catch (e) { toast('error', errorText(e)); } }
  $effect(() => { if (dialog === 'versions') { confirmV = ''; void loadVersions(); } });
  async function makeVersion(e: Event) {
    e.preventDefault();
    try { await beforeChange(); await articleApi.makeVersion(pid, vlabel.trim() || t('ae.v.manual')); vlabel = ''; await loadVersions(); toast('ok', t('ae.v.made')); }
    catch (x) { toast('error', errorText(x)); }
  }
  async function restore(v: Version) {
    try { await beforeChange(); const r = await articleApi.restoreVersion(pid, v.id); toast('ok', t('ae.v.restored', { n: r.changed.length })); dialog = ''; onrestored(); }
    catch (e) { toast('error', errorText(e)); }
  }
  const labelOf = (v: Version) => (v.label === 'autosave' || v.label === 'view' || v.label === 'settings' ? t('ae.v.auto')
    : v.label === 'creation' ? t('ae.v.creation') : v.label === 'before-restore' ? t('ae.v.beforeRestore')
    : v.label === 'before-overleaf-import' ? t('ae.v.beforeImport') : v.label.startsWith('suggestion') ? t('ae.v.suggestion')
    : v.label.startsWith('template:') ? t('ae.v.template', { tpl: v.label.slice(9) }) : v.label);

  // ---- Overleaf
  let ol = $state<Overleaf | null>(null);
  let zip = $state<File | null>(null);
  let importRes = $state<{ changed: string[]; skipped: { name: string; why: string }[]; new_keys: string[]; preamble_manual: boolean } | null>(null);
  $effect(() => { if (dialog === 'overleaf') { importRes = null; zip = null; articleApi.overleaf(pid).then((r) => (ol = r)).catch(() => (ol = null)); } });
  async function doImport() {
    if (!zip) return;
    try { await beforeChange(); importRes = await articleApi.importZip(pid, zip); onimported(); toast('ok', t('ae.ol.imported', { n: importRes.changed.length })); }
    catch (e) { toast('error', errorText(e)); }
  }

  // ---- new section
  let secTitle = $state('');
  $effect(() => { if (dialog === 'newSection') secTitle = ''; });
</script>

<Dialog open={dialog === 'title'} title={t('ae.front.dialog')} onclose={() => (dialog = '')}>
  <div class="field"><label for="ad-title">{t('ae.front.title')}</label><input id="ad-title" class="input" bind:value={title} /></div>
  <fieldset class="authors">
    <legend>{t('ae.front.authors')}</legend>
    {#each authors as a, i}
      <div class="author">
        <input class="input" aria-label={t('ae.front.name', { n: i + 1 })} placeholder={t('ae.front.namePh')} bind:value={a.name} autocomplete="name" />
        <input class="input" aria-label={t('ae.front.affiliation', { n: i + 1 })} placeholder={t('ae.front.affPh')} bind:value={a.affiliation} autocomplete="organization" />
        <input class="input" aria-label={t('ae.front.email', { n: i + 1 })} placeholder="nom@exemple.org" bind:value={a.email} type="email" autocomplete="email" />
        <button class="btn small quiet" onclick={() => (authors = authors.filter((_x, k) => k !== i))}>{t('ae.front.remove')}</button>
      </div>
    {/each}
    <button class="btn small" onclick={() => (authors = [...authors, { name: '' }])}>{t('ae.front.addAuthor')}</button>
  </fieldset>
  <div class="field"><label for="ad-date">{t('ae.front.date')}</label><input id="ad-date" class="input" bind:value={date} placeholder={t('ae.front.datePh')} /></div>
  {#snippet actions()}<button class="btn quiet" onclick={() => (dialog = '')}>{t('common.cancel')}</button><button class="btn primary" onclick={saveTitle}>{t('common.save')}</button>{/snippet}
</Dialog>

<Dialog open={dialog === 'figure'} title={t('ae.fig.title')} wide onclose={() => (dialog = '')}>
  <div class="seg" role="radiogroup" aria-label={t('ae.fig.source')}>
    <label><input type="radio" name="fig-src" checked={figTab === 'calcul'} onchange={() => (figTab = 'calcul')} />{t('ae.fig.calcul')}</label>
    <label><input type="radio" name="fig-src" checked={figTab === 'image'} onchange={() => (figTab = 'image')} />{t('ae.fig.image')}</label>
    <label><input type="radio" name="fig-src" checked={figTab === 'tikz'} onchange={() => (figTab = 'tikz')} />TikZ</label>
  </div>
  {#if figTab === 'calcul'}
    {#if loadingAssets}<p class="muted" aria-busy="true">{t('common.loading')}</p>
    {:else if !assets.length}<p class="muted">{t('ae.fig.noCalcul')}</p>
    {:else}
      <div class="assets" role="radiogroup" aria-label={t('ae.fig.pick')}>
        {#each assets as a}
          <label class="asset" class:on={chosen === a}><input type="radio" name="fig-asset" value={a} bind:group={chosen} class="sr-only" /><img src={`/api/calcul/assets/${a}`} alt={t('ae.fig.calculAlt')} loading="lazy" /></label>
        {/each}
      </div>
    {/if}
    <p class="xs muted">{t('ae.fig.svgNote')}</p>
  {:else if figTab === 'image'}
    <div class="field"><label for="ad-file">{t('ae.fig.file')}</label><input id="ad-file" type="file" accept="image/png,image/jpeg,application/pdf" onchange={(e) => (file = (e.target as HTMLInputElement).files?.[0] ?? null)} /></div>
  {:else}
    <p>{t('ae.fig.tikzText')}</p>
  {/if}
  {#if figTab !== 'tikz'}<div class="field"><label for="ad-cap">{t('ae.fig.caption')}</label><input id="ad-cap" class="input" bind:value={caption} /></div>{/if}
  {#snippet actions()}<button class="btn quiet" onclick={() => (dialog = '')}>{t('common.cancel')}</button>
    <button class="btn primary" onclick={insertFigure} disabled={(figTab === 'calcul' && !chosen) || (figTab === 'image' && !file)}>{t('ae.fig.insert')}</button>{/snippet}
</Dialog>

<Dialog open={dialog === 'versions'} title={t('ae.v.title')} wide onclose={() => (dialog = '')}>
  <form class="row" onsubmit={makeVersion}>
    <label class="sr-only" for="ad-vl">{t('ae.v.label')}</label>
    <input id="ad-vl" class="input" bind:value={vlabel} placeholder={t('ae.v.labelPh')} style="max-width: 320px" />
    <button class="btn small primary">{t('ae.v.make')}</button>
  </form>
  <p class="xs muted">{t('ae.v.lead')}</p>
  <ol class="vers">
    {#each versions as v (v.id)}
      <li class:auto={v.auto}>
        <span class="vl">{labelOf(v)}</span> <span class="xs muted">{fmtTime(v.t)} · {t('ae.v.files', { n: v.files.length })}</span>
        <span class="spacer"></span>
        {#if confirmV === v.id}
          <button class="btn small primary" onclick={() => restore(v)}>{t('ae.v.confirm')}</button><button class="btn small quiet" onclick={() => (confirmV = '')}>{t('common.cancel')}</button>
        {:else}<button class="btn small" onclick={() => (confirmV = v.id)}>{t('ae.v.restore')}</button>{/if}
      </li>
    {/each}
  </ol>
</Dialog>

<Dialog open={dialog === 'overleaf'} title={t('ae.ol.title')} wide onclose={() => (dialog = '')}>
  <p>{t('ae.ol.lead')}</p>
  {#if ol}
    <p class="small">{ol.found ? (ol.alive ? t('ae.ol.found', { url: ol.url }) : t('ae.ol.foundDown', { url: ol.url })) : t('ae.ol.notFound')}</p>
  {/if}
  <h3>{t('ae.ol.send')}</h3>
  <ol class="steps">
    <li><a class="btn small" href={articleApi.exportUrl(pid, 'overleaf')} download>{t('ae.ol.download')}</a></li>
    <li>{#if ol?.found && ol.local}<a class="btn small" href={`${ol.url}/project`} target="_blank" rel="noopener noreferrer">{t('ae.ol.open')}</a>{:else}{t('ae.ol.openManual')}{/if}</li>
    <li>{t('ae.ol.upload')}</li>
  </ol>
  <h3>{t('ae.ol.back')}</h3>
  <p class="small">{t('ae.ol.backLead')}</p>
  <div class="row">
    <label class="sr-only" for="ad-zip">{t('ae.ol.zip')}</label>
    <input id="ad-zip" type="file" accept=".zip,application/zip" onchange={(e) => (zip = (e.target as HTMLInputElement).files?.[0] ?? null)} />
    <button class="btn small primary" onclick={doImport} disabled={!zip}>{t('ae.ol.import')}</button>
  </div>
  {#if importRes}
    <div class="res" role="status">
      <p>{t('ae.ol.changed', { n: importRes.changed.length })}</p>
      {#if importRes.skipped.length}<p class="xs">{t('ae.ol.skipped', { files: importRes.skipped.map((s) => s.name).join(', ') })}</p>{/if}
      {#if importRes.new_keys.length}<p class="xs">{t('ae.ol.newKeys', { keys: importRes.new_keys.join(', ') })}</p>{/if}
      {#if importRes.preamble_manual}<p class="xs">{t('ae.ol.manualPreamble')}</p>{/if}
    </div>
  {/if}
  <p class="xs muted">{t('ae.ol.note')}</p>
</Dialog>

<Dialog open={dialog === 'newSection'} title={t('ae.section.add')} onclose={() => (dialog = '')}>
  <form onsubmit={(e) => { e.preventDefault(); if (secTitle.trim()) { onsection(secTitle.trim()); dialog = ''; } }}>
    <div class="field"><label for="ad-sec">{t('ae.section.title')}</label><input id="ad-sec" class="input" bind:value={secTitle} /></div>
    <button class="btn primary" disabled={!secTitle.trim()}>{t('ae.section.create')}</button>
  </form>
</Dialog>

<style>
  .authors { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin: var(--s-2) 0; display: grid; gap: var(--s-2); }
  .author { display: grid; grid-template-columns: 1.2fr 1.4fr 1.2fr auto; gap: 6px; }
  @media (max-width: 640px) { .author { grid-template-columns: 1fr; } }
  .assets { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--s-2); margin: var(--s-3) 0; }
  .asset { border: 2px solid var(--line); border-radius: var(--r-2); padding: 4px; cursor: pointer; background: #fff; }
  .asset.on { border-color: var(--accent); }
  .asset:has(input:focus-visible) { outline: 2px solid var(--focus); }
  .asset img { width: 100%; height: 110px; object-fit: contain; display: block; }
  .vers { list-style: none; padding: 0; display: grid; gap: 4px; max-height: 50vh; overflow: auto; }
  .vers li { display: flex; align-items: center; gap: var(--s-2); padding: 4px 6px; border-bottom: 1px solid var(--line); }
  .vers li.auto .vl { color: var(--text-2); }
  .steps { display: grid; gap: var(--s-2); }
  h3 { font-size: var(--fs-md); margin: var(--s-4) 0 var(--s-2); }
  .res { background: var(--surface-2); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); margin-top: var(--s-2); }
</style>
