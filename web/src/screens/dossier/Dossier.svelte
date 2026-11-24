<script lang="ts">
  // One dossier (D66): the header says where it stands, the thread at the centre says everything that happened in
  // order, the side pane holds the reference views (Énoncé, Lean, Preuve, Sous-lemmes, Littérature, Calculs, Versions).
  // `/d/:id/<part>` opens that tab; `?solo=1` shows that part alone in its own window.
  import { onMount, tick } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { navigate, route } from '../../lib/router.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { phaseOf } from '../../lib/status';
  import { loadJSON, prefs, saveJSON } from '../../lib/prefs.svelte';
  import { ApiError, api } from '../../lib/api/client';
  import { autoPart, deriveNow, isConditional, partOf, pendingGate, recheckState, PARTS, type Part } from '../../lib/flow';
  import { announceSolo, watchSolo } from '../../lib/ui/solo.svelte';
  import type { Dossier } from '../../lib/api/types';
  import InlineTitle from '../../components/InlineTitle.svelte';
  import StatusMark from '../../components/StatusMark.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';
  import ConductorLine from '../../components/ConductorLine.svelte';
  import { preloadKatex } from '../../lib/katex.svelte';
  import { prefetch } from '../../lib/ui/idle';
  import Thread from './Thread.svelte';
  import Pane from './Pane.svelte';
  import PartView from './PartView.svelte';
  import FlowHeader from './FlowHeader.svelte';
  import DossierMenu from './DossierMenu.svelte';

  let { params }: { params: Record<string, string> } = $props();
  const id = $derived(params['id'] ?? '');
  // S-AP: the plan is its own chunk, fetched when the browser is idle; KaTeX starts downloading with the dossier.
  preloadKatex();
  prefetch('dossier.plan', () => import('./PlanTree.svelte'));
  let loadError = $state<'' | 'not_found' | 'other'>('');
  $effect(() => {
    const did = id;
    void app.epoch;
    loadError = '';
    app.ensureDossier(did, true).catch((e) => { loadError = e instanceof ApiError && e.status === 404 ? 'not_found' : 'other'; });
  });

  const d = $derived(app.m.full[id]);
  const job = $derived(app.activeJob(id));
  const last = $derived(app.lastJob(id));
  const now = $derived(deriveNow(d, job));
  const phase = $derived(phaseOf(d?.status ?? app.m.dossiers[id]?.status ?? 'draft', job));
  const recheck = $derived(d ? recheckState(d) : '');
  const parent = $derived(d?.parent_id ? app.m.dossiers[d.parent_id] : undefined);

  // Sub-dossiers whose Lean statement waits for an approval (one card for all of them)
  const children = $derived(Object.values(app.m.dossiers).filter((c) => c.parent_id === id));
  const waiting = $derived(children.map((c) => app.m.full[c.id]).filter((c): c is Dossier => Boolean(c && pendingGate(c)?.kind === 'statement')));
  const asked = new Set<string>();
  $effect(() => {
    // summaries without `gate` (older servers): the sub-dossiers still at work on their statement are read once
    for (const c of children) {
      if (asked.has(c.id) || app.m.full[c.id] || c.proved || asked.size > 40) continue;
      if (c.gate !== undefined && c.gate?.state !== 'pending') continue;
      asked.add(c.id);
      void app.ensureDossier(c.id).catch(() => null);
    }
  });

  // --- the pane
  const solo = $derived(route.query.get('solo') === '1');
  const asked_part = $derived(partOf(params['step']));
  const part = $derived<Part>(asked_part ?? (d ? autoPart(d, now) : 'enonce'));
  interface Saved { open: boolean; w: number; split: Part | '' }
  const saved = loadJSON<Partial<Saved>>('dossier.pane', {});
  let open = $state(saved.open ?? true);
  let width = $state(Math.min(70, Math.max(28, saved.w ?? 45)));
  let split = $state<Part | ''>(saved.split && (PARTS as readonly string[]).includes(saved.split) ? saved.split : '');
  $effect(() => saveJSON('dossier.pane', { open, w: width, split } satisfies Saved));
  let narrow = $state(false);
  let wide = $state(true);
  let sheetOpen = $state(false);
  let seenPath = '';
  $effect(() => {                                           // an address naming a part opens it (sheet on phones)
    const p = route.path;
    if (p === seenPath) return;
    seenPath = p;
    peek = '';
    if (asked_part) { open = true; sheetOpen = true; } else sheetOpen = false;
  });
  onMount(() => {
    const a = window.matchMedia('(max-width: 899px)');
    const b = window.matchMedia('(min-width: 1280px)');
    const f = () => { narrow = a.matches; wide = b.matches; };
    f();
    a.addEventListener('change', f);
    b.addEventListener('change', f);
    if (!solo) watchSolo();
    return () => { a.removeEventListener('change', f); b.removeEventListener('change', f); };
  });
  $effect(() => { if (solo && id && asked_part) return announceSolo(id, asked_part); });

  let peek = $state('');
  let peekPart = $state<Part>('enonce');
  const peeked = $derived(peek ? app.m.full[peek] : undefined);
  function onpeek(cid: string) {
    void app.ensureDossier(cid).then((c) => { if (c) { peek = cid; peekPart = autoPart(c, deriveNow(c, app.activeJob(cid))); open = true; sheetOpen = true; void focusSheet(); } });
  }
  const shown = $derived(narrow ? sheetOpen : open);
  async function focusSheet() { if (narrow) { await tick(); document.getElementById('pane-close')?.focus(); } }
  function go(p: Part) { if (peek) peekPart = p; else navigate(`/d/${encodeURIComponent(id)}/${p}`, { focus: false }); }
  function show() { open = true; sheetOpen = true; void focusSheet(); }
  function hide() {
    if (narrow) { sheetOpen = false; if (asked_part) navigate(`/d/${encodeURIComponent(id)}`, { replace: true, focus: false }); } else open = false;
    peek = '';
    void tick().then(() => document.getElementById('pane-show')?.focus());
  }
  function setSplit(p: Part | '') {
    split = p;
    if (p && p === part) go(p === 'lean' ? 'preuve' : 'lean');
  }
  function onKey(e: KeyboardEvent) { if (e.key === 'Escape' && narrow && sheetOpen && !e.defaultPrevented && !document.querySelector('dialog[open], [role=menu]')) { e.preventDefault(); hide(); } }

  // --- resizing (pointer and keyboard)
  let layoutEl: HTMLDivElement | undefined = $state();
  const clamp = (x: number) => Math.min(70, Math.max(28, Math.round(x)));
  function drag(e: PointerEvent) {
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => { const r = layoutEl!.getBoundingClientRect(); width = clamp(((r.right - ev.clientX) / r.width) * 100); };
    const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
  }
  function sepKey(e: KeyboardEvent) {
    const s = e.key === 'ArrowLeft' ? 3 : e.key === 'ArrowRight' ? -3 : e.key === 'Home' ? 100 : e.key === 'End' ? -100 : 0;
    if (s) { e.preventDefault(); width = clamp(width + s); }
  }
  let fh = $state(120);
  async function jump(what: string) {
    if (narrow) sheetOpen = false;
    await tick();
    const el = document.getElementById(`${what}-${id}`);
    el?.scrollIntoView({ block: 'start' });
    el?.focus({ preventScroll: true });
  }
</script>

<svelte:window onkeydown={onKey} />

{#if loadError}
  <div class="state-msg">
    <h1>{loadError === 'not_found' ? t('dossier.notFoundTitle') : t('boot.errorTitle')}</h1>
    <p>{loadError === 'not_found' ? t('dossier.notFoundText') : t('boot.errorText')}</p>
    <a class="btn primary" href="/">{t('notfound.home')}</a>
  </div>
{:else if !d}
  <div class="loading" aria-busy="true"><span class="sr-only">{t('common.loading')}</span><div class="skel"></div></div>
{:else if solo}
  <article class="dossier solo">
    <header class="row sh">
      <StatusMark {phase} size={16} /><h1>{t(`pane.${part}`)} — {d.title || d.theorem}</h1><span class="spacer"></span>
      <button class="btn small" onclick={() => { window.close(); if (!window.closed) navigate(`/d/${encodeURIComponent(id)}/${part}`); }}><Icon name="undo" size={14} />{t('pane.back')}</button>
    </header>
    {#if job && now}<p class="small livenote" role="status">{t('flow.liveInThread')} <a href="/d/{encodeURIComponent(id)}">{t('flow.toThread')}</a></p>{/if}
    <PartView dossier={d} {job} {part} />
  </article>
{:else}
  <article class="dossier" class:research={prefs.mode === 'research'} style:--fh="{fh}px" style:--pane="{width}%">
    <div class="fixedpart" inert={narrow && shown}>
      <header class="dh">
        {#if parent}<p class="crumb small"><a href="/d/{encodeURIComponent(parent.id)}">{parent.title}</a> › {t('dossier.lemma')}</p>{/if}
        <div class="row title-row">
          <StatusMark {phase} size={18} />
          <InlineTitle id="dossier-title" value={d.title || d.theorem} label={t('dossier.titleEdit')} save={async (v) => { const r = await api.patchDossier(d.id, { title: v }); app.m.full[d.id] = r.dossier; const s = app.m.dossiers[d.id]; if (s) s.title = r.dossier.title; }} />
          <span class="spacer"></span>
          {#if isConditional(d)}<span class="chip running cond">{t('plan.conditional')}</span>{/if}
          {#if recheck === 'pending' || recheck === 'regressed'}<span class="chip {recheck === 'regressed' ? 'failed' : 'running'}">{tk(`recheck.${recheck}`, recheck)}</span>{/if}
          <div class="row tools"><HelpLink page="workflow" /><DossierMenu dossier={d} busy={Boolean(job)} />
            {#if !shown}<button id="pane-show" class="btn" aria-expanded="false" onclick={show}><Icon name="book" size={16} />{t('pane.show')}</button>{/if}</div>
        </div>
        <ConductorLine job={job ?? last} />
      </header>
    </div>
    <div class="sticky" bind:clientHeight={fh} inert={narrow && shown}><FlowHeader dossier={d} {job} {last} {now} waitingChildren={waiting.length} {jump} /></div>

    <div class="layout" class:pane={shown && !narrow} bind:this={layoutEl}>
      <div class="main" inert={narrow && shown}>
        <Thread dossier={d} {job} {last} {now} {waiting} {onpeek} />
      </div>
      {#if shown}
        {#if !narrow}
          <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (a focusable separator is the ARIA window splitter) -->
          <div class="sep" role="separator" aria-orientation="vertical" aria-label={t('pane.resize')} aria-valuenow={width} aria-valuemin={28} aria-valuemax={70} tabindex="0" onpointerdown={drag} onkeydown={sepKey}></div>
        {/if}
        {@const pd = peeked ?? d}
        <aside class="side" class:sheet={narrow} aria-label={t('pane.title')} role={narrow ? 'dialog' : undefined}>
          {#key pd.id}<Pane dossier={pd} job={peeked ? app.activeJob(pd.id) : job} part={peeked ? peekPart : part} split={wide ? split : ''} sheet={narrow} peek={Boolean(peeked)}
            ontab={go} onsplit={setSplit} onclose={hide} onpeekback={() => (peek = '')} />{/key}
        </aside>
      {/if}
    </div>
  </article>
{/if}

<style>
  .dossier { max-width: 1900px; margin: 0 auto calc(-1 * var(--s-6)); }
  .dossier.solo { margin-bottom: 0; }
  .crumb { margin: 0 0 4px; color: var(--text-2); }
  .title-row { align-items: center; gap: 10px; margin-bottom: var(--s-2); }
  .title-row :global(h1) { margin: 0; }
  .tools { gap: 4px; }
  .cond { border: 1.5px dashed var(--running); }
  .sticky { position: sticky; top: var(--topbar-h); z-index: 60; margin-bottom: var(--s-3); }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr); align-items: start; }
  .main { width: 100%; max-width: 62rem; margin: 0 auto; min-width: 0; min-height: calc(100dvh - var(--topbar-h) - var(--fh) - 170px); display: grid; }
  .layout.pane { grid-template-columns: minmax(0, 1fr) 14px minmax(0, var(--pane)); }
  .side { min-width: 0; position: sticky; top: calc(var(--topbar-h) + var(--fh) + 12px); height: calc(100dvh - var(--topbar-h) - var(--fh) - 24px); }
  .sep { align-self: stretch; cursor: col-resize; touch-action: none; position: relative; }
  .sep::after { content: ''; position: absolute; left: 6px; top: 0; bottom: 0; width: 2px; background: var(--line); border-radius: 2px; }
  .sep:hover::after, .sep:focus-visible::after { background: var(--accent); width: 3px; }
  .side.sheet { position: fixed; inset: var(--topbar-h) 0 0; height: auto; z-index: 450; background: var(--bg); }
  .solo { max-width: 1200px; }
  .sh { margin-bottom: var(--s-3); }
  .sh h1 { margin: 0; font-size: var(--fs-lg); }
  .livenote { background: var(--running-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
  @media (max-width: 767px) { .dossier:not(.solo) { margin-bottom: calc(-1 * var(--s-5)); } .title-row { gap: 6px; } .tools { width: 100%; justify-content: flex-end; } .main { min-height: 0; } .title-row :global(h1) { flex: 1 1 60%; } }
  .state-msg { max-width: 36rem; }
  .skel { height: 32px; width: 40%; background: var(--surface-2); border-radius: var(--r-2); }
</style>
