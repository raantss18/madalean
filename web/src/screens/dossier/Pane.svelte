<script lang="ts">
  // D66: the side pane — reference views in tabs; any one can be put in its own window or in a column beside.
  import type { Dossier, Job } from '../../lib/api/types';
  import { partsOf, type Part } from '../../lib/flow';
  import { t } from '../../lib/i18n/index.svelte';
  import { isAway, putBack, separate } from '../../lib/ui/solo.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Icon from '../../components/Icon.svelte';
  import Menu, { type MenuItem } from '../../components/Menu.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import PartView from './PartView.svelte';

  let { dossier: d, job, part, split = '', sheet = false, peek = false, ontab, onsplit, onclose, onpeekback }: {
    dossier: Dossier; job: Job | undefined; part: Part; split?: Part | ''; sheet?: boolean; peek?: boolean;
    ontab: (p: Part) => void; onsplit: (p: Part | '') => void; onclose: () => void; onpeekback?: () => void;
  } = $props();
  const parts = $derived(partsOf(d));
  const label = (p: Part) => t(`pane.${p}`);
  const gone = $derived(isAway(d.id, part));
  const beside = $derived(!sheet && split === part);
  const HELP: Partial<Record<Part, string>> = { plan: 'proof-plans', lean: 'reading-lean' };
  function tabKey(e: KeyboardEvent, i: number) {
    const n = parts.length;
    const j = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i + n - 1) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
    if (j < 0) return;
    e.preventDefault();
    ontab(parts[j]!);
    queueMicrotask(() => document.getElementById(`tab-${parts[j]}`)?.focus());
  }
  const items = $derived<MenuItem[]>([
    { label: t('pane.window'), icon: 'external', run: () => { if (!separate(d.id, part)) toast('warn', t('pane.blocked')); } },
    ...(sheet || peek ? [] : [{ label: t('pane.column'), icon: 'split', run: () => onsplit(part) }]),
  ]);
  let tabs: HTMLDivElement | undefined = $state();
  $effect(() => { const el = tabs?.querySelector<HTMLElement>(`#tab-${part}`); if (el && tabs) tabs.scrollLeft = Math.max(0, el.offsetLeft - 60); });
</script>

<div class="pane" class:sheet>
  <div class="bar">
    {#if peek}<button class="btn small quiet" onclick={onpeekback}><Icon name="chevronLeft" size={14} />{t('pane.peekBack')}</button><span class="pk small">{t('pane.peek', { title: d.title || d.theorem })}</span>{/if}
    <span class="spacer"></span>
    <HelpLink page={HELP[part] ?? 'workflow'} />
    {#if !gone && !beside}<Menu label={t('pane.separate')} text={t('pane.separate')} icon="external" {items} />{/if}
    <button class="btn quiet icon" id="pane-close" onclick={onclose} aria-label={t('pane.hide')} title={t('pane.hide')}><Icon name="x" /></button>
  </div>
  <div class="tabs" role="tablist" aria-label={t('pane.title')} bind:this={tabs}>
    {#each parts as p, i (p)}
      <button id="tab-{p}" role="tab" class="tab" aria-selected={part === p} aria-controls="panel-{p}" tabindex={part === p ? 0 : -1} onclick={() => ontab(p)} onkeydown={(e) => tabKey(e, i)}>{label(p)}{#if isAway(d.id, p) || (!sheet && split === p)}<Icon name="external" size={12} />{/if}</button>
    {/each}
  </div>
  <div class="cols" class:two={split && !sheet && !peek}>
    <div class="body" id="panel-{part}" role="tabpanel" aria-labelledby="tab-{part}">
      {#if gone}<div class="away"><p>{t('pane.inWindow', { part: label(part) })}</p><button class="btn" onclick={() => putBack(d.id, part)}><Icon name="undo" size={16} />{t('pane.back')}</button></div>
      {:else if beside && !peek}<div class="away"><p>{t('pane.inColumn', { part: label(part) })}</p><button class="btn" onclick={() => onsplit('')}><Icon name="undo" size={16} />{t('pane.back')}</button></div>
      {:else}<PartView dossier={d} {job} {part} />{/if}
    </div>
    {#if split && !sheet && !peek}
      <section class="body col" aria-label={label(split)}>
        <div class="row ch"><h2>{label(split)}</h2><span class="spacer"></span><button class="btn small" onclick={() => onsplit('')}><Icon name="undo" size={14} />{t('pane.back')}</button></div>
        <PartView dossier={d} {job} part={split} />
      </section>
    {/if}
  </div>
</div>

<style>
  .pane { display: flex; flex-direction: column; min-height: 0; height: 100%; background: var(--bg); }
  .bar { display: flex; align-items: center; gap: 6px; min-height: 44px; }
  .pk { font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tabs { position: relative; display: flex; overflow-x: auto; border-bottom: 1px solid var(--line-strong); flex: none; scrollbar-width: thin; }
  .tab { display: inline-flex; gap: 4px; align-items: center; min-height: 44px; min-width: 44px; padding: 0 10px; border: 0; border-bottom: 3px solid transparent; background: none; color: var(--text-2); font: 600 var(--fs-sm)/1 var(--font-ui); white-space: nowrap; cursor: pointer; }
  .tab:hover { background: var(--surface-2); }
  .tab[aria-selected='true'] { color: var(--text); border-bottom-color: var(--laterite-mark); }
  .tab:focus-visible { outline-offset: -3px; }
  .cols { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr); }
  .cols.two { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-3); }
  .body { min-width: 0; overflow: auto; padding: var(--s-3) 2px var(--s-5); overscroll-behavior: contain; }
  .col { border-left: 1px solid var(--line); padding-left: var(--s-3); }
  .ch h2 { margin: 0; font-size: var(--fs-md); }
  .away { padding: var(--s-5) var(--s-3); text-align: center; color: var(--text-2); }
  .sheet .bar { padding-left: var(--s-3); }
  .sheet .body { padding: var(--s-3) var(--s-3) max(var(--s-5), env(safe-area-inset-bottom)); }
</style>
