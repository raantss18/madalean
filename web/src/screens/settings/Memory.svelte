<script lang="ts">
  // « Mémoire » (D62, docs/MEMORY.md): one portable bundle of what Madalean learned — export with choices, import
  // with a dry-run preview (host only; every Lean proof re-checked here before it enters the library), automatic
  // local backups, and the training-dataset export (verified pairs only; no training happens in Madalean).
  import { memoryApi, exportUrl, MEMORY_PARTS, type MemoryPart, type MemoryStatus, type Preview, type ImportSession,
    type Unverified, type References, type BackupSettings } from '../../lib/api/memory';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime, fmtBytes } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import Icon from '../../components/Icon.svelte';

  let st = $state<MemoryStatus | null>(null);
  let parts = $state<Record<MemoryPart, boolean>>({ library: true, lessons: true, recipes: true, graphs: true, digests: true });
  let allProjects = $state(true);
  let chosen = $state<Record<string, boolean>>({});
  let copyrighted = $state(false);
  let files = $state(false);
  let file: HTMLInputElement | undefined = $state();
  let preview = $state<Preview | null>(null);
  let token = $state('');
  let session = $state<ImportSession | null>(null);
  let busy = $state(false);
  let unverified = $state<Unverified[]>([]);
  let refs = $state<References | null>(null);
  let folder = $state('');

  async function load() {
    try {
      st = await memoryApi.status();
      folder = st.backups.folder;
      const [u, r] = await Promise.all([memoryApi.unverified(), memoryApi.references()]);
      unverified = u.entries; refs = r;
    } catch (e) { toast('error', errorText(e)); }
  }
  $effect(() => { void load(); });

  function download(href: string) {
    const a = document.createElement('a');
    a.href = href; a.download = '';
    document.body.appendChild(a); a.click(); a.remove();
  }
  function doExport() {
    const ps = MEMORY_PARTS.filter((p) => parts[p]);
    if (!ps.length) { toast('error', t('memory.export.none')); return; }
    const projects = allProjects ? null : [...(st?.projects ?? []).filter((p) => chosen[p.id]).map((p) => p.id), ...(chosen['global'] ? ['global'] : [])];
    download(exportUrl(ps, projects, copyrighted, files));
  }

  async function pick(ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (!f) return;
    busy = true; preview = null; session = null;
    try { const r = await memoryApi.inspect(f); preview = r.preview; token = r.token; }
    catch (e) { toast('error', tk(`memory.err.${(e as { kind?: string }).kind ?? ''}`, errorText(e))); }
    finally { busy = false; if (file) file.value = ''; }
  }
  async function follow(tok: string) {
    for (;;) {
      session = await memoryApi.session(tok);
      if (session.state === 'done' || session.state === 'error') break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    await load();
  }
  async function apply() {
    busy = true;
    try { await memoryApi.apply(token); await follow(token); toast('ok', t('memory.import.done')); }
    catch (e) { toast('error', errorText(e)); } finally { busy = false; }
  }
  async function reverify() {
    busy = true;
    try { const r = await memoryApi.reverify(); await follow(r.token); } catch (e) { toast('error', errorText(e)); } finally { busy = false; }
  }
  async function forget(u: Unverified) {
    try { await memoryApi.forgetUnverified(u.name); unverified = unverified.filter((x) => x.name !== u.name); } catch (e) { toast('error', errorText(e)); }
  }
  async function dropRef(kind: 'graphs' | 'digests', id: string) {
    try { await memoryApi.deleteReference(kind, id); refs = await memoryApi.references(); } catch (e) { toast('error', errorText(e)); }
  }
  async function saveBackups(patch: Partial<BackupSettings>) {
    if (!st) return;
    try { const r = await memoryApi.backups(patch); st = { ...st, backups: { ...st.backups, ...r.backups } }; toast('ok', t('settings.saved')); }
    catch (e) { toast('error', tk(`memory.err.${(e as { kind?: string }).kind ?? ''}`, errorText(e))); await load(); }
  }
  async function backupNow() {
    busy = true;
    try { const r = await memoryApi.backupNow(); toast('ok', t('memory.backup.written', { name: r.name })); await load(); }
    catch (e) { toast('error', errorText(e)); } finally { busy = false; }
  }
  function summary(p: MemoryPart): string {
    const s = preview?.summary[p];
    if (!s || !Object.keys(s).length) return t('memory.preview.nothing');
    return Object.entries(s).map(([a, n]) => `${n} ${tk(`memory.action.${a}`, a)}`).join(' · ');
  }
  function itemLabel(it: { name?: string; title?: string; request?: string; id?: string; kind?: string }): string {
    return it.title || it.name || it.request || (it.kind ? `${tk(`lessons.kind.${it.kind}`, it.kind)} ${it.id ?? ''}` : it.id ?? '');
  }
</script>

<div class="mem">
  <p class="lead">{t('memory.lead')}</p>
  {#if st}
    <p class="xs muted">{t('memory.counts', { library: st.counts.library, lessons: st.counts.lessons, recipes: st.counts.recipes })}</p>
  {/if}

  <section aria-labelledby="mem-export">
    <h3 id="mem-export">{t('memory.export.title')}</h3>
    <fieldset>
      <legend class="small">{t('memory.export.parts')}</legend>
      {#each MEMORY_PARTS as p (p)}
        <label class="ck"><input type="checkbox" bind:checked={parts[p]} />{tk(`memory.part.${p}`, p)}</label>
      {/each}
    </fieldset>
    <fieldset>
      <legend class="small">{t('memory.export.projects')}</legend>
      <label class="ck"><input type="checkbox" bind:checked={allProjects} />{t('memory.export.allProjects')}</label>
      {#if !allProjects}
        {#each st?.projects ?? [] as p (p.id)}
          <label class="ck"><input type="checkbox" bind:checked={chosen[p.id]} />{p.title}</label>
        {/each}
        <label class="ck"><input type="checkbox" bind:checked={chosen['global']} />{t('memory.export.noProject')}</label>
      {/if}
    </fieldset>
    <label class="ck"><input type="checkbox" bind:checked={copyrighted} />{t('memory.export.copyrighted')}</label>
    <p class="xs muted note">{t('memory.export.copyrightedNote')}</p>
    <label class="ck"><input type="checkbox" bind:checked={files} />{t('memory.export.files')}</label>
    <div class="row acts"><button class="btn small primary" onclick={doExport}><Icon name="download" size={14} />{t('memory.export.go')}</button></div>
  </section>

  <section aria-labelledby="mem-import">
    <h3 id="mem-import">{t('memory.import.title')}</h3>
    {#if app.m.local}
      <p class="small muted">{t('memory.import.lead')}</p>
      <div class="row acts">
        <label class="btn small"><Icon name="file" size={14} />{t('memory.import.pick')}<input bind:this={file} class="sr-only" type="file" accept=".madalean-memory,application/zip" onchange={pick} disabled={busy} /></label>
      </div>
      {#if preview}
        <div class="preview" role="region" aria-label={t('memory.preview.title')}>
          <p class="small">{t('memory.preview.bundle', { version: preview.bundle.madalean, created: preview.bundle.created })}
            {#if preview.bundle.excluded} · {t('memory.preview.excluded', { n: preview.bundle.excluded })}{/if}</p>
          <ul class="list">
            {#each MEMORY_PARTS.filter((p) => preview?.items[p]?.length) as p (p)}
              <li>
                <details>
                  <summary><b>{tk(`memory.part.${p}`, p)}</b> — {summary(p)}</summary>
                  <ul class="items">
                    {#each (preview.items[p] ?? []).slice(0, 200) as it, i (i)}
                      <li class="xs"><span class="act {it.action}">{tk(`memory.action.${it.action}`, it.action)}</span> {itemLabel(it)} <span class="muted">— {tk(`memory.reason.${it.reason}`, it.reason)}{#if it.same_statements} · {t('memory.preview.same', { n: it.same_statements })}{/if}</span></li>
                    {/each}
                  </ul>
                </details>
              </li>
            {/each}
          </ul>
          {#if session?.state !== 'done'}
            <div class="row acts">
              <button class="btn small primary" onclick={apply} disabled={busy}><Icon name="check" size={14} />{t('memory.import.apply')}</button>
              <button class="btn small quiet" onclick={() => { preview = null; token = ''; }} disabled={busy}>{t('common.cancel')}</button>
            </div>
          {/if}
        </div>
      {/if}
      {#if session}
        <p class="small" role="status">
          {#if session.state === 'running'}{t('memory.import.running', { done: session.progress.done ?? 0, total: session.progress.total ?? 0 })}
          {:else if session.state === 'done'}{t('memory.import.done')}
          {:else if session.state === 'error'}{t('memory.import.failed')}{/if}
        </p>
      {/if}
    {:else}
      <p class="small muted"><Icon name="lock" size={14} /> {t('memory.hostOnly')}</p>
    {/if}
    {#if unverified.length}
      <h4>{t('memory.unverified.title', { n: unverified.length })}</h4>
      <p class="xs muted">{t('memory.unverified.lead')}</p>
      <ul class="list">
        {#each unverified as u (u.name + u.workspace)}
          <li>
            <div class="txt"><code class="small">{u.name}</code><span class="xs muted">{tk(`memory.reason.${u.reason}`, u.reason)}{#if u.detail} — {u.detail}{/if} · {u.workspace}</span></div>
            {#if app.m.local}<button class="btn quiet icon small" aria-label={t('memory.unverified.forget', { name: u.name })} onclick={() => forget(u)}><Icon name="trash" size={14} /></button>{/if}
          </li>
        {/each}
      </ul>
      {#if app.m.local}<div class="row acts"><button class="btn small" onclick={reverify} disabled={busy}><Icon name="refresh" size={14} />{t('memory.unverified.retry')}</button></div>{/if}
    {/if}
    {#if refs && (refs.graphs.length || refs.digests.length)}
      <h4>{t('memory.refs.title')}</h4>
      <p class="xs muted">{t('memory.refs.lead')}</p>
      <ul class="list">
        {#each refs.graphs as g (g.id)}
          <li><div class="txt"><span class="small">{g.title}</span><span class="xs muted">{t('memory.refs.graph', { nodes: g.nodes, same: g.same_statements })}{#if g.project} · {g.project}{/if}</span></div>
            {#if app.m.local}<button class="btn quiet icon small" aria-label={t('memory.refs.delete', { name: g.title })} onclick={() => dropRef('graphs', g.id)}><Icon name="trash" size={14} /></button>{/if}</li>
        {/each}
        {#each refs.digests as d (d.id)}
          <li><div class="txt"><span class="small">{d.title}</span><span class="xs muted">{t('memory.refs.digest', { n: d.statements })}{#if d.license} · {d.license}{/if}</span></div>
            {#if app.m.local}<button class="btn quiet icon small" aria-label={t('memory.refs.delete', { name: d.title })} onclick={() => dropRef('digests', d.id)}><Icon name="trash" size={14} /></button>{/if}</li>
        {/each}
      </ul>
    {/if}
  </section>

  <section aria-labelledby="mem-backups">
    <h3 id="mem-backups">{t('memory.backup.title')}</h3>
    <p class="small muted">{t('memory.backup.lead')}</p>
    {#if st}
      {#if app.m.local}
        <label class="ck"><input type="checkbox" checked={st.backups.enabled} onchange={(e) => saveBackups({ enabled: (e.target as HTMLInputElement).checked })} />{t('memory.backup.enabled')}</label>
        <div class="grid">
          <label>{t('memory.backup.every')}
            <select value={String(st.backups.every_days)} onchange={(e) => saveBackups({ every_days: Number((e.target as HTMLSelectElement).value) })}>
              <option value="1">{t('memory.backup.daily')}</option><option value="7">{t('memory.backup.weekly')}</option><option value="30">{t('memory.backup.monthly')}</option>
            </select></label>
          <label>{t('memory.backup.keep')}
            <input type="number" min="1" max="100" value={st.backups.keep} onchange={(e) => saveBackups({ keep: Number((e.target as HTMLInputElement).value) })} /></label>
          <label class="wide">{t('memory.backup.folder')}
            <input type="text" bind:value={folder} placeholder={st.backups.folder_effective} spellcheck="false"
              onchange={() => saveBackups({ folder })} onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void saveBackups({ folder }); } }} /></label>
        </div>
        <label class="ck"><input type="checkbox" checked={st.backups.include_copyrighted} onchange={(e) => saveBackups({ include_copyrighted: (e.target as HTMLInputElement).checked })} />{t('memory.export.copyrighted')}</label>
        <div class="row acts"><button class="btn small" onclick={backupNow} disabled={busy}><Icon name="history" size={14} />{t('memory.backup.now')}</button></div>
      {/if}
      <p class="xs muted">{t('memory.backup.where', { folder: st.backups.folder_effective ?? '' })}{#if st.backups.last} · {t('memory.backup.last', { when: fmtTime(st.backups.last) })}{/if}</p>
      {#if st.backups.last_error}<p class="xs err" role="alert">{t('memory.backup.error', { why: st.backups.last_error })}</p>{/if}
      {#if st.backups.files?.length}
        <ul class="list">
          {#each st.backups.files as f (f.name)}<li class="xs"><code>{f.name}</code> · {fmtBytes(f.bytes)}</li>{/each}
        </ul>
      {/if}
    {/if}
  </section>

  <section aria-labelledby="mem-dataset">
    <h3 id="mem-dataset">{t('memory.dataset.title')}</h3>
    <p class="small muted">{t('memory.dataset.lead')}</p>
    <div class="row acts"><button class="btn small" onclick={() => download(memoryApi.datasetUrl)}><Icon name="download" size={14} />{t('memory.dataset.go')}</button></div>
  </section>
</div>

<style>
  .mem { display: grid; gap: var(--s-4); max-width: 760px; }
  .lead { margin: 0; color: var(--text-2); }
  section { display: grid; gap: var(--s-2); }
  h3 { margin: 0; font-size: var(--fs-lg); }
  h4 { margin: var(--s-2) 0 0; font-size: var(--fs-md, 1rem); }
  fieldset { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); display: flex; flex-wrap: wrap; gap: var(--s-1) var(--s-3); margin: 0; }
  legend { font-weight: 600; }
  .ck { display: inline-flex; gap: 6px; align-items: center; min-height: 32px; }
  .note { margin: -4px 0 0 26px; }
  .acts { gap: var(--s-2); flex-wrap: wrap; }
  .list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  .list > li { display: flex; gap: var(--s-2); align-items: flex-start; border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-2); background: var(--surface); }
  .list > li > details { flex: 1; min-width: 0; }
  .items { margin: var(--s-1) 0 0; padding-left: var(--s-3); display: grid; gap: 2px; overflow-wrap: anywhere; }
  .txt { display: grid; gap: 2px; min-width: 0; flex: 1; overflow-wrap: anywhere; }
  .act { font-weight: 700; }
  .act.skip, .act.unverified { color: var(--text-2); }
  .preview { display: grid; gap: var(--s-2); border: 1px dashed var(--line-strong); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--s-2); }
  .grid label { display: grid; gap: 4px; font-size: var(--fs-sm, 0.9rem); }
  .grid .wide { grid-column: 1 / -1; }
  .err { color: var(--failed); }
</style>
