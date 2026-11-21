<script lang="ts">
  // Article (Lean → paper): blocks the AI drafts and you edit. AI drafts and your text are marked; regenerating a
  // block you edited asks first and keeps your text in its versions (never overwritten). Dossier blocks are typeset
  // as theorems only when Lean verified them, otherwise as « Affirmation » with a not-verified mark.
  import { ApiError, downloadExport } from '../../lib/api/client';
  import { research, type Article, type Block } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { errorText } from '../../lib/ui/errors';
  import { currentProjectId } from '../../lib/project.svelte';
  import { modelLabel } from '../../lib/status';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import Md from '../../components/Md.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import Menu from '../../components/Menu.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  void downloadExport;

  let { params: _p }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  let art = $state<Article | null>(null);
  let generating = $state<Record<string, string>>({});
  let editing = $state<Record<string, string>>({});
  let err = $state('');
  let preview = $state(false);
  let keys = $state<{ key: string; title: string }[]>([]);
  let confirm = $state<{ bid: string } | null>(null);
  let versionsOf = $state<Block | null>(null);

  async function load() {
    if (!pid) return;
    try {
      const r = await research.article(pid);
      art = r.article;
      for (const b of r.generating) generating[b] ??= '';
      err = '';
    } catch (e) { err = errorText(e); }
    research.keys(pid).then((r) => (keys = r.keys)).catch(() => {});
  }
  $effect(() => { void pid; void load(); });
  $effect(() => app.on('article.updated', (ev) => { const e = ev as unknown as { project: string; article: Article }; if (e.project === pid) art = e.article; }));
  $effect(() => app.on('article.token', (ev) => { const e = ev as unknown as { project: string; block_id: string; text: string }; if (e.project === pid) generating[e.block_id] = (generating[e.block_id] ?? '') + e.text; }));
  $effect(() => app.on('article.done', (ev) => {
    const e = ev as unknown as { project: string; block_id: string; removed_citations?: string[] };
    if (e.project !== pid) return;
    delete generating[e.block_id];
    if (e.removed_citations?.length) toast('warn', t('article.removedCites', { keys: e.removed_citations.join(', ') }));
  }));
  $effect(() => app.on('article.error', (ev) => { const e = ev as unknown as { project: string; block_id: string; text: string }; if (e.project === pid) { delete generating[e.block_id]; toast('error', e.text || t('err.generic', { code: 'article' })); } }));

  const blocks = $derived(art ? [art.abstract, ...art.blocks] : []);
  async function save(b: Block) {
    try { art = (await research.patchBlock(pid, b.id, { text: editing[b.id] ?? b.text })).article; delete editing[b.id]; toast('ok', t('article.saved')); }
    catch (e) { toast('error', errorText(e)); }
  }
  async function generate(bid: string, force = false) {
    try { await research.generateBlock(pid, bid, force); generating[bid] = ''; confirm = null; }
    catch (e) {
      if (e instanceof ApiError && e.kind === 'user_edited') confirm = { bid };
      else toast('error', errorText(e));
    }
  }
  async function move(b: Block, d: -1 | 1) {
    if (!art) return;
    const ids = art.blocks.map((x) => x.id);
    const i = ids.indexOf(b.id); const j = i + d;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j]!, ids[i]!];
    const before = art.blocks;
    art.blocks = ids.map((id) => before.find((x) => x.id === id)!);
    try { art = (await research.patchArticle(pid, { order: ids })).article; } catch (e) { art.blocks = before; toast('error', errorText(e)); }
  }
  async function remove(b: Block) {
    try {
      await research.deleteBlock(pid, b.id);
      await load();
      toast('ok', t('article.blockDeleted'), { action: { label: t('common.undo'), run: async () => { await research.restoreBlock(pid, b.id); await load(); } } });
    } catch (e) { toast('error', errorText(e)); }
  }
  async function add(after: string) {
    try { const r = await research.addBlock(pid, { kind: 'prose', text: '', after }); art = r.article; editing[r.block.id] = ''; } catch (e) { toast('error', errorText(e)); }
  }
  async function sync() {
    try { const r = await research.syncArticle(pid); art = r.article; toast('ok', t('article.synced', { n: r.added })); } catch (e) { toast('error', errorText(e)); }
  }
  async function patchArt(p: Parameters<typeof research.patchArticle>[1]) {
    try { art = (await research.patchArticle(pid, p)).article; } catch (e) { toast('error', errorText(e)); }
  }
  async function restoreVersion(b: Block, i: number) {
    try { art = (await research.restoreBlockVersion(pid, b.id, i)).article; versionsOf = null; toast('ok', t('versions.restored', { n: i + 1 })); } catch (e) { toast('error', errorText(e)); }
  }
  function dossierInfo(b: Block) {
    const d = app.m.dossiers[b.dossier_id];
    return d ? { title: d.title, proved: d.proved, kind: d.kind } : null;
  }
  const exportItems = $derived((['pdf', 'tex', 'zip', 'md'] as const).map((f) => ({ label: tk(`export.${f}`, f.toUpperCase()), icon: 'file', run: () => {
    const a = document.createElement('a'); a.href = research.articleExportUrl(pid, f); a.download = ''; document.body.appendChild(a); a.click(); a.remove();
    if (f === 'pdf') toast('info', t('export.building'));
  } })));
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="article">
      <div class="row head">
        <h1>{t('article.title')}</h1><HelpLink page="articles" />
        <span class="spacer"></span>
        <label class="switch small"><input type="checkbox" bind:checked={preview} />{t('article.preview')}</label>
        <button class="btn small" onclick={sync}><Icon name="refresh" size={14} />{t('article.sync')}</button>
        <Menu label={t('export.title')} icon="download" text={t('export.short')} items={exportItems} />
      </div>
      {#if err}<p class="error-text">{err}</p>{:else if !art}<p class="muted" aria-busy="true">{t('common.loading')}</p>{:else}
        <div class="meta panel">
          <div class="field"><label for="at">{t('article.paperTitle')}</label><input id="at" class="input" value={art.title} onchange={(e) => patchArt({ title: (e.target as HTMLInputElement).value })} /></div>
          <div class="field"><label for="aa">{t('article.authors')}</label><input id="aa" class="input" value={art.authors.map((a) => a.name).join(', ')} onchange={(e) => patchArt({ authors: (e.target as HTMLInputElement).value.split(',').map((s) => ({ name: s.trim() })).filter((a) => a.name) })} /></div>
          <div class="row">
            <label class="switch small"><input type="checkbox" checked={art.options.lean_appendix} onchange={(e) => patchArt({ options: { ...art!.options, lean_appendix: (e.target as HTMLInputElement).checked } })} />{t('article.leanAppendix')}</label>
            <label class="switch small"><input type="checkbox" checked={art.options.verification_table} onchange={(e) => patchArt({ options: { ...art!.options, verification_table: (e.target as HTMLInputElement).checked } })} />{t('article.verifTable')}</label>
            <label for="alang" class="small">{t('article.lang')}</label>
            <select id="alang" class="input" style="width:auto" value={art.options.lang} onchange={(e) => patchArt({ options: { ...art!.options, lang: (e.target as HTMLSelectElement).value as 'fr' } })}><option value="fr">Français</option><option value="en">English</option></select>
          </div>
        </div>
        <p class="hint">{t('article.lead')}</p>
        {#if preview}
          <div class="paper">
            <h2 class="ptitle">{art.title}</h2>
            <p class="pauth">{art.authors.map((a) => a.name).join(', ')}</p>
            {#each blocks as b (b.id)}
              {@const di = dossierInfo(b)}
              {#if b.kind === 'dossier' && di}
                <div class="theorem pblock"><span class="th-head">{di.proved ? tk(`article.kind.${di.kind}`, t('article.kind.theorem')) : t('article.claim')}.</span> {#if !di.proved}<span class="nv">{t('article.notVerified')}</span>{/if} <Md src={b.text || di.title} cls="th-body" /></div>
              {:else}
                {#if b.title}<h3>{b.title}</h3>{/if}<Md src={b.text} />
              {/if}
            {/each}
          </div>
        {:else}
          <ol class="blocks">
            {#each blocks as b, i (b.id)}
              {@const di = dossierInfo(b)}
              {@const isAbstract = b.id === art.abstract.id}
              <li class="block {b.source}">
                <div class="row bh">
                  <span class="chip">{isAbstract ? t('article.abstract') : tk(`article.blockKind.${b.kind}`, b.kind)}</span>
                  {#if b.source === 'ai'}<span class="chip online" title={t('article.aiTitle')}>{t('article.aiDraft')}{b.versions.at(-1)?.model ? ` · ${modelLabel(b.versions.at(-1)!.model).name}` : ''}</span>
                  {:else if b.source === 'user'}<span class="chip local">{t('article.yours')}</span>
                  {:else if di}<span class="chip {di.proved ? 'proved' : 'running'}">{di.proved ? t('article.verified') : t('article.notVerified')}</span>{/if}
                  {#if b.title}<strong class="small">{b.title}</strong>{/if}
                  <span class="spacer"></span>
                  {#if !isAbstract}
                    <button class="btn small quiet icon" onclick={() => move(b, -1)} disabled={i <= 1} aria-label={t('article.moveUp')}><Icon name="chevronUp" size={14} /></button>
                    <button class="btn small quiet icon" onclick={() => move(b, 1)} disabled={i === blocks.length - 1} aria-label={t('article.moveDown')}><Icon name="chevronDown" size={14} /></button>
                  {/if}
                  {#if b.kind !== 'dossier'}
                    <button class="btn small" onclick={() => generate(b.id)} disabled={b.id in generating}>{b.id in generating ? t('article.generating') : t('article.regenerate')}</button>
                    <button class="btn small" onclick={() => (editing[b.id] = editing[b.id] ?? b.text)} disabled={b.id in editing}>{t('common.edit')}</button>
                  {/if}
                  {#if b.versions.length > 1}<button class="btn small quiet" onclick={() => (versionsOf = b)}>{t('versions.button', { n: b.versions.length })}</button>{/if}
                  {#if !isAbstract}<button class="btn small quiet icon" onclick={() => remove(b)} aria-label={t('article.delete')}><Icon name="trash" size={14} /></button>{/if}
                </div>
                {#if b.id in generating}
                  <div class="gen" aria-live="polite"><p class="xs muted">{t('article.generating')}</p><Md src={generating[b.id] ?? ''} /></div>
                {:else if b.id in editing}
                  <CodeEditor bind:value={editing[b.id]} language="natural" label={t('article.blockText')} minLines={6} onSubmit={() => save(b)} />
                  <div class="row">
                    <button class="btn small primary" onclick={() => save(b)}>{t('common.save')}</button>
                    <button class="btn small quiet" onclick={() => delete editing[b.id]}>{t('common.cancel')}</button>
                    {#if keys.length}
                      <label class="sr-only" for="cite-{b.id}">{t('article.cite')}</label>
                      <select id="cite-{b.id}" class="input" style="width:auto" onchange={(e) => { const k = (e.target as HTMLSelectElement).value; if (k) editing[b.id] = `${editing[b.id] ?? ''} [@${k}]`; (e.target as HTMLSelectElement).value = ''; }}>
                        <option value="">{t('article.cite')}</option>{#each keys as k (k.key)}<option value={k.key}>@{k.key} — {k.title}</option>{/each}
                      </select>
                    {/if}
                  </div>
                {:else if b.kind === 'dossier' && di}
                  <p class="small"><a href="/d/{encodeURIComponent(b.dossier_id)}">{di.title}</a></p>
                  {#if b.text}<Md src={b.text} />{/if}
                {:else if b.text}<Md src={b.text} />
                {:else}<p class="muted small">{t('article.emptyBlock')}</p>{/if}
                {#if !isAbstract}<button class="btn small quiet addafter" onclick={() => add(b.id)}><Icon name="plus" size={14} />{t('article.addAfter')}</button>{/if}
              </li>
            {/each}
          </ol>
        {/if}
      {/if}
    </div>
    <Dialog open={Boolean(confirm)} title={t('article.overwriteTitle')} onclose={() => (confirm = null)}>
      <p>{t('article.overwriteText')}</p>
      {#snippet actions()}
        <button class="btn quiet" onclick={() => (confirm = null)}>{t('article.keepMine')}</button>
        <button class="btn primary" onclick={() => confirm && generate(confirm.bid, true)}>{t('article.regenerateAnyway')}</button>
      {/snippet}
    </Dialog>
    <Dialog open={Boolean(versionsOf)} title={t('article.versions')} wide onclose={() => (versionsOf = null)}>
      {#if versionsOf}
        <ol class="vers">
          {#each versionsOf.versions as v, i}
            <li><strong>{t('versions.n', { n: i + 1 })}</strong> <span class="chip {v.source === 'user' ? 'local' : 'online'}">{v.source === 'user' ? t('versions.byYou') : modelLabel(v.model).name || t('versions.byAi')}</span> <span class="xs muted">{fmtTime(v.t)}</span>
              <button class="btn small" onclick={() => restoreVersion(versionsOf!, i)}>{t('versions.restore')}</button>
              <div class="vtext"><Md src={v.text} /></div></li>
          {/each}
        </ol>
      {/if}
    </Dialog>
  {/snippet}
</ProjectGate>

<style>
  .article { max-width: 980px; }
  .head h1 { margin: 0; }
  .meta { margin: var(--s-3) 0; }
  .blocks { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--s-3); }
  .block { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--line-strong); border-radius: var(--r-2); padding: var(--s-3) var(--s-4); }
  .block.ai { border-left-color: var(--online); }
  .block.user { border-left-color: var(--local); }
  .block.dossier { border-left-color: var(--proved); }
  .bh { margin-bottom: var(--s-2); }
  .block :global(.md) { font-family: var(--font-serif); line-height: 1.65; }
  .gen { background: var(--online-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
  .addafter { margin-top: var(--s-2); }
  .paper { background: var(--surface); border: 1px solid var(--line); padding: var(--s-6); border-radius: var(--r-2); font-family: var(--font-serif); line-height: 1.7; }
  .ptitle { text-align: center; font-size: var(--fs-xl); }
  .pauth { text-align: center; color: var(--text-2); }
  .pblock { margin: var(--s-3) 0; }
  .nv { color: var(--failed); font: 700 var(--fs-xs) var(--font-ui); border: 1.5px solid var(--failed); border-radius: 999px; padding: 0 6px; }
  .vers { list-style: none; padding: 0; display: grid; gap: var(--s-3); }
  .vtext { background: var(--surface-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); margin-top: 4px; }
</style>
