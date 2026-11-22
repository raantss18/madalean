<script lang="ts">
  // File tree of the article's LaTeX project (S-AD): what is on disk in `article/` (docs/ARTICLE.md §1). Read-only
  // except what the editor already does safely: a .tex file opens in the editor, a figure opens (or is inserted),
  // the settings file opens « Options avancées », refs.bib (made at compile time from the sources) opens Sources.
  import { t, type Key } from '../../../lib/i18n/index.svelte';
  import { articleApi, type TexProject } from '../../../lib/api/article';
  import { aprefs, setAPref } from '../../../lib/article/prefs.svelte';
  import { fileTree, figureSnippet, type TreeNode } from '../../../lib/article/items';
  import { navigate } from '../../../lib/router.svelte';
  import Icon from '../../../components/Icon.svelte';

  let { pid, proj, current, dirty, onopen, onoptions, oninsert, onnewsection, onpick }: {
    pid: string; proj: TexProject; current: string; dirty: Record<string, boolean>;
    onopen: (path: string) => void; onoptions: (tab: string) => void; oninsert: (s: { text: string }) => void;
    onnewsection: () => void; onpick?: () => void;
  } = $props();

  const tree = $derived(fileTree(proj.files.map((f) => f.path), proj.order, proj.figures));
  const ICON: Record<TreeNode['kind'], string> = { main: 'texfile', tex: 'texfile', bib: 'bookmark', toml: 'sliders', lock: 'sliders', image: 'image', folder: 'folder' };

  function toggle(path: string) {
    const o = aprefs.openFolders.includes(path) ? aprefs.openFolders.filter((x) => x !== path) : [...aprefs.openFolders, path];
    setAPref('openFolders', o);
  }
  function act(n: TreeNode) {
    if (n.kind === 'main' || n.kind === 'tex') onopen(n.path);
    else if (n.kind === 'toml') onoptions('document');
    else if (n.kind === 'lock') onoptions('packages');
    else if (n.kind === 'bib') navigate('/sources');
    onpick?.();
  }
</script>

<ul class="tree" aria-label={t('ae.files.label')}>
  <li class="root xs muted"><Icon name="folderOpen" size={14} /> article/</li>
  {#each tree as n (n.path)}
    {@render node(n, 1)}
  {/each}
</ul>

{#snippet node(n: TreeNode, depth: number)}
  {#if n.kind === 'folder'}
    {@const open = aprefs.openFolders.includes(n.path)}
    <li>
      <button class="row-btn folder" style:padding-left="{depth * 12}px" aria-expanded={open} aria-controls="ae-tree-{n.name}" onclick={() => toggle(n.path)}>
        <Icon name={open ? 'chevronDown' : 'chevronRight'} size={12} /><Icon name={open ? 'folderOpen' : 'folder'} size={16} />
        <span class="nm">{n.name}/</span><span class="xs muted">{n.children?.length ?? 0}</span>
      </button>
      <ul id="ae-tree-{n.name}" hidden={!open}>
        {#each n.children ?? [] as c (c.path)}{@render node(c, depth + 1)}{/each}
        {#if n.name === 'sections'}
          <li><button class="row-btn add xs" style:padding-left="{(depth + 1) * 12 + 14}px" onclick={() => { onnewsection(); onpick?.(); }}><Icon name="plus" size={12} />{t('ae.section.add')}</button></li>
        {:else if !n.children?.length}
          <li class="xs muted empty" style:padding-left="{(depth + 1) * 12 + 14}px">{t('ae.files.noFigures')}</li>
        {/if}
      </ul>
    </li>
  {:else if n.kind === 'image'}
    <li class="leaf">
      <a class="row-btn" style:padding-left="{depth * 12 + 14}px" href={articleApi.figureUrl(pid, n.path)} target="_blank" rel="noopener" title={n.path}>
        <span class="fi" data-kind="image"><Icon name="image" size={16} /></span><span class="nm mono">{n.name}</span>
      </a>
      <button class="btn quiet icon tiny" onclick={() => { oninsert(figureSnippet(n.path)); onpick?.(); }} aria-label={t('ae.files.insertFigure', { name: n.name })}><Icon name="plus" size={14} /></button>
    </li>
  {:else}
    <li class="leaf">
      <button class="row-btn" class:cur={current === n.path} aria-current={current === n.path ? 'true' : undefined} style:padding-left="{depth * 12 + 14}px" onclick={() => act(n)} title={n.path}>
        <span class="fi" data-kind={n.kind}><Icon name={ICON[n.kind]} size={16} /></span>
        <span class="nm mono">{n.name}</span>
        {#if dirty[n.path]}<span class="xs dot" title={t('ae.status.dirty')}>●<span class="sr-only">{t('ae.status.dirty')}</span></span>{/if}
        {#if n.note}<span class="xs muted note">{t(n.note as Key)}</span>{/if}
        {#if n.orphan}<span class="xs warn">{t('ae.files.orphan')}</span>{/if}
      </button>
    </li>
  {/if}
{/snippet}

<style>
  .tree, .tree ul { list-style: none; margin: 0; padding: 0; }
  .root { display: flex; align-items: center; gap: 4px; padding: 2px 4px 4px; font-family: var(--font-mono); }
  .leaf { display: flex; align-items: center; }
  .row-btn { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; min-height: 30px; padding-right: 4px; background: none; border: 0; border-radius: var(--r-1); color: var(--text); font: var(--fs-sm) var(--font-ui); text-align: left; cursor: pointer; text-decoration: none; }
  .row-btn:hover { background: var(--surface-2); }
  .row-btn.cur { background: var(--accent-soft); font-weight: 600; box-shadow: inset 2px 0 0 var(--accent); }
  .folder { width: 100%; font-weight: 600; color: var(--text-2); }
  .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mono { font-family: var(--font-mono); font-size: var(--fs-xs); }
  .note { margin-left: auto; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .warn { color: var(--running); font-weight: 600; margin-left: auto; }
  .dot { color: var(--running); }
  .fi { display: inline-grid; place-items: center; color: var(--k-file); }
  .fi[data-kind='image'] { color: var(--k-figure); }
  .fi[data-kind='bib'] { color: var(--k-source); }
  .add { color: var(--accent); }
  .empty { padding: 2px 0 4px; }
  .tiny { width: 28px !important; min-height: 28px !important; }
  @media (pointer: coarse) { .row-btn { min-height: var(--touch); } .tiny { width: 40px !important; min-height: 40px !important; } }
</style>
