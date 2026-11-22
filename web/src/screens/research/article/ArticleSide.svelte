<script lang="ts">
  // Project panel of the article editor (S-AD): tab « Plan » (sections = files, sub-headings, and the file tree of
  // the LaTeX project, shown or hidden) and tab « Éléments » (proofs, Calcul, notes, conjectures, sources, figures,
  // versions). Inline column on wide screens, drawer on tablets, bottom sheet on phones (Article.svelte decides).
  import { t, tk } from '../../../lib/i18n/index.svelte';
  import type { TexProject } from '../../../lib/api/article';
  import { aprefs, setAPref } from '../../../lib/article/prefs.svelte';
  import Icon from '../../../components/Icon.svelte';
  import ArticleItems from './ArticleItems.svelte';
  import ArticleFiles from './ArticleFiles.svelte';

  type Snip = { text: string; cursor?: number };
  let { pid, proj, outline, current, dirty, mode, onclose, onopen, onmove, ondelete, onnewsection, onoptions, oninsert, onversions }: {
    pid: string; proj: TexProject; outline: { path: string; title: string; subs: { title: string; line: number }[] }[];
    current: string; dirty: Record<string, boolean>; mode: 'inline' | 'overlay' | 'sheet'; onclose: () => void;
    onopen: (path: string, line?: number) => void; onmove: (path: string, d: -1 | 1) => void; ondelete: (path: string) => void;
    onnewsection: () => void; onoptions: (tab: string) => void; oninsert: (s: Snip) => void; onversions: () => void;
  } = $props();

  const tabs = ['outline', 'items'] as const;
  function key(e: KeyboardEvent) {
    const i = tabs.indexOf(aprefs.sideTab);
    let j = -1;
    if (e.key === 'ArrowRight') j = (i + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') j = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') j = 0;
    else if (e.key === 'End') j = tabs.length - 1;
    if (j < 0) return;
    e.preventDefault();
    setAPref('sideTab', tabs[j]!);
    queueMicrotask(() => document.getElementById(`ae-tab-${tabs[j]}`)?.focus());
  }
  // In a drawer or a sheet, picking something closes it (the text is what you wanted to see).
  const pick = () => { if (mode !== 'inline') onclose(); };
</script>

<div class="side-in">
  <div class="head">
    <div class="tabs" role="tablist" aria-label={t('ae.side.label')} tabindex="-1" onkeydown={key}>
      {#each tabs as k (k)}
        <button role="tab" id="ae-tab-{k}" aria-selected={aprefs.sideTab === k} aria-controls="ae-tabpanel" tabindex={aprefs.sideTab === k ? 0 : -1}
          onclick={() => setAPref('sideTab', k)}><Icon name={k === 'outline' ? 'list' : 'folder'} size={15} />{t(k === 'outline' ? 'ae.side.outline' : 'ae.side.items')}</button>
      {/each}
    </div>
    <button class="btn quiet icon small close" onclick={onclose} aria-label={t('ae.side.hide')}><Icon name={mode === 'inline' ? 'chevronLeft' : 'x'} size={16} /></button>
  </div>

  <div id="ae-tabpanel" role="tabpanel" aria-labelledby="ae-tab-{aprefs.sideTab}" class="tp">
    {#if aprefs.sideTab === 'outline'}
      <nav class="outline" aria-label={t('ae.outline')}>
        <ol>
          <li><button class="node" class:cur={current === 'main.tex'} aria-current={current === 'main.tex' ? 'true' : undefined} onclick={() => { onopen('main.tex'); pick(); }}><Icon name="file" size={14} />{t('ae.front.node')}</button></li>
          {#each outline as s, i (s.path)}
            <li>
              <div class="row node-row">
                <button class="node" class:cur={current === s.path} aria-current={current === s.path ? 'true' : undefined} onclick={() => { onopen(s.path); pick(); }} title={s.path}><span class="num">{i + 1}</span>{s.title}</button>
                <span class="tools">
                  <button class="btn quiet icon tiny" onclick={() => onmove(s.path, -1)} disabled={i === 0} aria-label={t('ae.section.up', { title: s.title })}><Icon name="chevronUp" size={14} /></button>
                  <button class="btn quiet icon tiny" onclick={() => onmove(s.path, 1)} disabled={i === outline.length - 1} aria-label={t('ae.section.down', { title: s.title })}><Icon name="chevronDown" size={14} /></button>
                  <button class="btn quiet icon tiny" onclick={() => ondelete(s.path)} aria-label={t('ae.section.delete', { title: s.title })}><Icon name="trash" size={14} /></button>
                </span>
              </div>
              {#if s.subs.length && current === s.path}
                <ol class="subs">{#each s.subs as h}<li><button class="sub" onclick={() => { onopen(s.path, h.line); pick(); }}>{h.title}</button></li>{/each}</ol>
              {/if}
            </li>
          {/each}
        </ol>
        <button class="btn small quiet add" onclick={onnewsection}><Icon name="plus" size={14} />{t('ae.section.add')}</button>
      </nav>

      <section class="files" aria-labelledby="ae-files-h">
        <h3 class="fh">
          <button id="ae-files-h" class="fbtn" aria-expanded={aprefs.fileTree} aria-controls="ae-files" onclick={() => setAPref('fileTree', !aprefs.fileTree)}>
            <Icon name={aprefs.fileTree ? 'chevronDown' : 'chevronRight'} size={14} /><Icon name="folderOpen" size={16} />{t('ae.files.title')}
          </button>
        </h3>
        <div id="ae-files" hidden={!aprefs.fileTree}>
          {#if aprefs.fileTree}
            <ArticleFiles {pid} {proj} {current} {dirty} onopen={(p) => onopen(p)} {onoptions} {oninsert} {onnewsection} onpick={pick} />
          {/if}
        </div>
      </section>
      <p class="xs muted meta">{tk(`ae.tpl.${proj.settings.document.template}`, proj.settings.document.class)} · {proj.settings.document.language === 'fr' ? 'Français' : 'English'}
        <button class="linkish" onclick={() => onoptions('document')}>{t('ae.change')}</button></p>
    {:else}
      <ArticleItems {pid} {proj} active={aprefs.sideTab === 'items'} {oninsert} onversions={() => { onversions(); pick(); }} onpick={pick} />
    {/if}
  </div>
</div>

<style>
  .side-in { display: flex; flex-direction: column; min-height: 0; height: 100%; }
  .head { display: flex; align-items: center; gap: 4px; padding: var(--s-2) var(--s-2) 0; border-bottom: 1px solid var(--line); }
  .tabs { display: flex; flex: 1; gap: 2px; min-width: 0; }
  .tabs button { display: inline-flex; align-items: center; gap: 6px; flex: 1; justify-content: center; min-height: 36px; padding: 0 8px; border: 0; border-bottom: 2px solid transparent; background: none; color: var(--text-2); font: 600 var(--fs-sm) var(--font-ui); cursor: pointer; white-space: nowrap; }
  .tabs button[aria-selected='true'] { color: var(--text); border-bottom-color: var(--accent); }
  .tabs button:hover { color: var(--text); }
  .close { flex: none; }
  .tp { flex: 1; min-height: 0; overflow-y: auto; padding: var(--s-2); font-size: var(--fs-sm); overscroll-behavior: contain; }
  .outline ol { list-style: none; margin: 0; padding: 0; }
  .node { display: flex; gap: 6px; align-items: baseline; width: 100%; text-align: left; background: none; border: none; color: var(--text); padding: 6px; border-radius: var(--r-1); cursor: pointer; font: inherit; min-height: 32px; }
  .node:hover { background: var(--surface-2); }
  .node.cur { background: var(--accent-soft); color: var(--text); font-weight: 600; box-shadow: inset 2px 0 0 var(--accent); }
  .node .num { color: var(--text-3); font-variant-numeric: tabular-nums; min-width: 1.2em; }
  .node-row { gap: 0; flex-wrap: nowrap; }
  .node-row .tools { display: none; }
  .node-row:hover .tools, .node-row:focus-within .tools { display: inline-flex; }
  .tiny { width: 26px !important; min-height: 26px !important; }
  .subs { padding-left: 1.6em !important; }
  .sub { background: none; border: none; color: var(--text-2); font: var(--fs-xs) var(--font-ui); text-align: left; padding: 3px 4px; cursor: pointer; min-height: 24px; }
  .sub:hover { color: var(--text); }
  .add { margin-top: var(--s-1); }
  .files { margin-top: var(--s-3); border-top: 1px solid var(--line); padding-top: var(--s-1); }
  .fh { margin: 0; font-size: var(--fs-sm); }
  .fbtn { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 36px; padding: 0 4px; background: none; border: 0; color: var(--text); font: 600 var(--fs-sm) var(--font-ui); cursor: pointer; border-radius: var(--r-1); text-align: left; }
  .fbtn:hover { background: var(--surface-2); }
  .meta { margin-top: var(--s-4); padding: 0 6px; }
  .linkish { background: none; border: none; color: var(--accent); cursor: pointer; padding: 0 2px; font: inherit; text-decoration: underline; min-height: 24px; }
  @media (pointer: coarse) {
    .node, .linkish, .fbtn, .tabs button { min-height: var(--touch); }
    .sub { min-height: 40px; }
    .tiny { width: 40px !important; min-height: 40px !important; }
    .node-row .tools { display: inline-flex; }
  }
</style>
