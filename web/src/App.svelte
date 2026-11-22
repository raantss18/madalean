<script lang="ts">
  import type { Component } from 'svelte';
  import { onMount } from 'svelte';
  import { app } from './lib/store/app.svelte';
  import { route, routes, navigate, type RouteDef } from './lib/router.svelte';
  import { t } from './lib/i18n/index.svelte';
  import { prefs } from './lib/prefs.svelte';
  import { barShown, setBar, isShortcut } from './lib/ui/layout.svelte';
  import Icon from './components/Icon.svelte';
  import Toasts from './components/Toasts.svelte';
  import AppMenu from './components/AppMenu.svelte';
  import ContextSwitcher from './components/ContextSwitcher.svelte';
  import StatusPanel from './components/StatusPanel.svelte';
  import ProjectBar from './components/ProjectBar.svelte';
  import ConnectionBanner from './components/ConnectionBanner.svelte';
  import CommandPalette from './components/CommandPalette.svelte';
  import ConductorAsk from './components/ConductorAsk.svelte';
  import Tour from './components/Tour.svelte';

  type Screen = Component<{ params: Record<string, string> }>;
  const cache = new Map<string, Promise<Screen>>();
  function load(def: RouteDef): Promise<Screen> {
    let p = cache.get(def.name);
    if (!p) {
      p = def.load().then((m) => m.default);
      p.catch(() => cache.delete(def.name));
      cache.set(def.name, p);
    }
    return p;
  }

  const def = $derived(routes.find((r) => r.name === route.name));
  const isPublic = $derived(Boolean(def?.public));
  let gate = $state<'checking' | 'ready' | 'unpaired'>('checking');
  let palette = $state(false);

  // S-AK (docs/UI.md §14.2): one top bar (logo menu · context switcher · search · status) and, on the screens of a
  // project, the project bar. No rail, no drawer, no bottom bar.
  const PROJECT_SCREENS = new Set(['home', 'dossier', 'project', 'sources', 'reader', 'notes', 'graph', 'blueprint', 'article', 'conjectures', 'calcul', 'publish']);
  const projectScreen = $derived(PROJECT_SCREENS.has(route.name));
  const barOnScreen = $derived(projectScreen && barShown());

  onMount(async () => {
    if (route.name === 'pair') { gate = 'unpaired'; return; }
    // One round trip: GET /state directly (an unpaired remote browser gets 401 → the client opens /pair).
    gate = 'ready';
    await app.boot();
  });

  $effect(() => {
    // Leaving the pairing page after a successful pairing.
    if (gate === 'unpaired' && route.name !== 'pair') { gate = 'ready'; void app.boot(); }
  });

  function onKey(e: KeyboardEvent) {
    const mod = e.ctrlKey || e.metaKey;
    if (isShortcut(e, 'Digit1')) { e.preventDefault(); setBar(!barShown()); return; }
    if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); palette = !palette; return; }
    const tgt = e.target as HTMLElement;
    const typing = tgt?.closest?.('input, textarea, select, [contenteditable="true"], .cm-editor');
    if (typing || mod || e.altKey) return;
    if (e.key === '/') { e.preventDefault(); palette = true; }
    else if (e.key === 'n' && prefs.mode === 'research') { e.preventDefault(); navigate('/'); }
  }
</script>

<svelte:window onkeydown={onKey} />
<svelte:head><title>{route.name === 'dossier' && app.m.full[route.params['id'] ?? ''] ? `${app.m.full[route.params['id'] ?? '']!.title} — Madalean` : 'Madalean'}</title></svelte:head>

{#if isPublic || gate === 'unpaired'}
  {#if def}
    {#await load(def) then Screen}<Screen params={route.params} />{/await}
  {/if}
{:else}
  <a class="skip-link" href="#main">{t('a11y.skip')}</a>
  <div class="shell">
    <header class="topbar">
      <AppMenu {barOnScreen} />
      <ContextSwitcher />
      <div class="spacer"></div>
      <button class="btn quiet search-btn" onclick={() => (palette = true)} aria-keyshortcuts="Control+K" title={t('cmd.open')}>
        <Icon name="search" /><span class="lbl">{t('cmd.short')}</span><kbd class="kbd" aria-hidden="true">Ctrl K</kbd>
      </button>
      <StatusPanel />
    </header>
    <ConnectionBanner />
    {#if app.m.demo}<p class="demo-band" role="note">{t('demo.band')}</p>{/if}
    {#if barOnScreen}<ProjectBar />{/if}
    <main id="main">
      {#if app.bootError && !app.m.loaded}
        <div class="boot-error">
          <h1>{app.bootError === 'network' ? t('boot.offlineTitle') : t('boot.errorTitle')}</h1>
          <p>{app.bootError === 'network' ? t('boot.offlineText') : t('boot.errorText')}</p>
          <button class="btn primary" onclick={() => app.boot()}>{t('conn.retry')}</button>
        </div>
      {:else if !app.m.loaded}
        <div class="loading" aria-busy="true"><span class="sr-only">{t('common.loading')}</span><div class="skel"></div><div class="skel short"></div></div>
      {:else if def}
        <!-- First-run tour: in the page flow below 1024 px (above the statement, never over it), floating card above. -->
        {#if !prefs.tourDone && prefs.mode === 'learn' && route.name === 'home'}<Tour />{/if}
        {#await load(def)}
          <div class="loading" aria-busy="true"><span class="sr-only">{t('common.loading')}</span></div>
        {:then Screen}
          {#key route.name}<Screen params={route.params} />{/key}
        {:catch}
          <div class="boot-error"><h1>{t('boot.chunkTitle')}</h1><p>{t('boot.chunkText')}</p><button class="btn primary" onclick={() => location.reload()}>{t('boot.reload')}</button></div>
        {/await}
      {:else}
        <div class="boot-error"><h1>{t('notfound.title')}</h1><p>{t('notfound.text')}</p><a class="btn primary" href="/">{t('notfound.home')}</a></div>
      {/if}
    </main>
  </div>
  <CommandPalette bind:open={palette} />
  <ConductorAsk />
{/if}
<Toasts />

<style>
  .shell { min-height: 100dvh; display: flex; flex-direction: column; }
  .topbar { position: sticky; top: 0; z-index: 500; display: flex; align-items: center; gap: var(--s-2); height: var(--topbar-h); padding: 0 max(var(--s-3), env(safe-area-inset-right)) 0 max(var(--s-3), env(safe-area-inset-left)); background: var(--surface); border-bottom: 1px solid var(--line); }   /* no backdrop-filter: it would make the top bar the containing block of the fixed sheets inside it */
  .spacer { flex: 1 0 var(--s-2); }
  .search-btn { flex: none; }
  .search-btn .kbd { margin-left: 4px; }
  .demo-band { margin: 0; padding: 4px var(--s-3); background: var(--info-soft); color: var(--accent); font-size: var(--fs-xs); font-weight: 600; text-align: center; }
  main { flex: 1; min-width: 0; padding: var(--s-5) max(var(--s-6), env(safe-area-inset-right)) var(--s-7) max(var(--s-6), env(safe-area-inset-left)); }
  main:focus { outline: none; }
  .loading { padding: var(--s-5) 0; }
  .skel { height: 28px; width: 50%; background: var(--surface-2); border-radius: var(--r-2); margin-bottom: var(--s-3); }
  .skel.short { width: 30%; }
  .boot-error { max-width: 36rem; padding: var(--s-6) 0; }

  @media (max-width: 1279px) {
    .search-btn .kbd { display: none; }
    .search-btn .lbl { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  }
  @media (max-width: 1023px) {
    main { padding: var(--s-4) max(var(--s-4), env(safe-area-inset-right)) var(--s-7) max(var(--s-4), env(safe-area-inset-left)); }
  }
  @media (max-width: 767px) {
    .topbar { gap: 4px; padding: 0 max(var(--s-1), env(safe-area-inset-right)) 0 max(var(--s-1), env(safe-area-inset-left)); }
    .spacer { display: none; }
    .search-btn { min-width: 44px; padding: 0; justify-content: center; }
    main { padding: var(--s-3) max(var(--s-3), env(safe-area-inset-right)) calc(var(--s-6) + env(safe-area-inset-bottom)) max(var(--s-3), env(safe-area-inset-left)); }
  }
</style>
