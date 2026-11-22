<script lang="ts">
  import type { Component } from 'svelte';
  import { onMount } from 'svelte';
  import { app } from './lib/store/app.svelte';
  import { route, routes, navigate, type RouteDef } from './lib/router.svelte';
  import { t } from './lib/i18n/index.svelte';
  import { prefs, setMode } from './lib/prefs.svelte';
  import { railShown, setRail, isShortcut } from './lib/ui/layout.svelte';
  import Icon from './components/Icon.svelte';
  import Toasts from './components/Toasts.svelte';
  import DossierList from './components/DossierList.svelte';
  import ProjectSwitcher from './components/ProjectSwitcher.svelte';
  import PrivacyIndicator from './components/PrivacyIndicator.svelte';
  import ConnectionBanner from './components/ConnectionBanner.svelte';
  import ActivityPanel from './components/ActivityPanel.svelte';
  import CommandPalette from './components/CommandPalette.svelte';
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
  let drawer = $state(false);
  let activityOpen = $state(false);
  let palette = $state(false);
  // From 1024 px the rail is permanent but can be hidden (☰, Ctrl+Shift+1); below, the same button opens it as a drawer.
  let wide = $state(typeof window !== 'undefined' && matchMedia('(min-width: 1024px)').matches);
  $effect(() => {
    const mq = matchMedia('(min-width: 1024px)');
    const f = () => { wide = mq.matches; };
    mq.addEventListener('change', f);
    return () => mq.removeEventListener('change', f);
  });
  const railOpen = $derived(wide ? railShown() : drawer);
  function toggleRail() { if (wide) setRail(!railShown()); else drawer = !drawer; }

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

  const navItems = $derived(routes.filter((r) => r.nav).sort((a, b) => a.nav!.order - b.nav!.order));
  const activeCount = $derived(app.activeJobs.length);

  function onKey(e: KeyboardEvent) {
    const mod = e.ctrlKey || e.metaKey;
    if (isShortcut(e, 'Digit1')) { e.preventDefault(); toggleRail(); return; }
    if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); palette = !palette; return; }
    const tgt = e.target as HTMLElement;
    const typing = tgt?.closest?.('input, textarea, select, [contenteditable="true"], .cm-editor');
    if (typing || mod || e.altKey) return;
    if (e.key === '/') { e.preventDefault(); palette = true; }
    else if (e.key === 'n' && prefs.mode === 'research') { e.preventDefault(); navigate('/'); }
    else if (e.key === 'Escape') { drawer = false; activityOpen = false; }
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
  <div class="shell" class:drawer-open={drawer} class:rail-hidden={!railShown()}>
    <header class="topbar">
      <button class="btn quiet icon menu-btn" aria-label={t('nav.dossiers')} aria-expanded={railOpen} aria-controls="rail" aria-keyshortcuts="Control+Shift+1"
        title={`${railOpen ? t('layout.rail.hide') : t('layout.rail.show')} (${t('layout.key', { k: '1' })})`} onclick={toggleRail}><Icon name="menu" /></button>
      <a class="brand" href="/" aria-label={t('nav.homeLabel')}>
        <img src="/brand/icon.svg" alt="" width="28" height="28" />
        <span class="word">Madalean</span>
      </a>
      <ProjectSwitcher />
      <div class="spacer"></div>
      <button class="btn quiet search-btn" onclick={() => (palette = true)} aria-keyshortcuts="Control+K" title={t('cmd.open')}>
        <Icon name="search" /><span class="lbl">{t('cmd.short')}</span><kbd class="kbd" aria-hidden="true">Ctrl K</kbd>
      </button>
      <PrivacyIndicator />
      <button class="btn quiet act-btn" aria-label={t('activity.openN', { n: activeCount })} aria-expanded={activityOpen} aria-controls="activity-drawer" onclick={() => (activityOpen = !activityOpen)}>
        <Icon name="activity" />{#if activeCount}<span class="count" aria-hidden="true">{activeCount}</span>{/if}
      </button>
      <div class="mode seg" role="radiogroup" aria-label={t('mode.label')}>
        <label title={t('mode.learnHint')}><input type="radio" name="uimode" value="learn" checked={prefs.mode === 'learn'} onchange={() => setMode('learn')} /><Icon name="graduate" size={16} /><span class="mlbl">{t('mode.learn')}</span></label>
        <label title={t('mode.researchHint')}><input type="radio" name="uimode" value="research" checked={prefs.mode === 'research'} onchange={() => setMode('research')} /><Icon name="microscope" size={16} /><span class="mlbl">{t('mode.research')}</span></label>
      </div>
      <a class="btn quiet icon settings-btn" href="/reglages" aria-label={t('nav.settings')}><Icon name="settings" /></a>
    </header>
    <ConnectionBanner />
    {#if app.m.demo}<p class="demo-band" role="note">{t('demo.band')}</p>{/if}
    <div class="body">
      <nav id="rail" class="rail" aria-label={t('nav.dossiers')}>
        <div class="rail-mode seg" role="radiogroup" aria-label={t('mode.label')}>
          <label><input type="radio" name="uimode-rail" value="learn" checked={prefs.mode === 'learn'} onchange={() => setMode('learn')} /><Icon name="graduate" size={16} />{t('mode.learn')}</label>
          <label><input type="radio" name="uimode-rail" value="research" checked={prefs.mode === 'research'} onchange={() => setMode('research')} /><Icon name="microscope" size={16} />{t('mode.research')}</label>
        </div>
        <ul class="projnav" aria-label={t('nav.project')}>
          <li><a href="/" aria-current={route.name === 'home' || route.name === 'dossier' ? 'page' : undefined} onclick={() => (drawer = false)}><Icon name="list" size={16} />{t('nav.dossiers')}</a></li>
          {#each navItems.filter((r) => r.nav?.group === 'project') as r (r.name)}
            <li><a href={r.pattern.replace(/\/:[^/]+\??/g, '')} aria-current={route.name === r.name || (r.name === 'sources' && route.name === 'reader') ? 'page' : undefined} onclick={() => (drawer = false)}><Icon name={r.nav!.icon} size={16} />{t(r.nav!.label)}</a></li>
          {/each}
        </ul>
        <DossierList onpick={() => (drawer = false)} />
        <ul class="secondary">
          {#each navItems.filter((r) => r.name !== 'home' && r.name !== 'project' && r.nav?.group !== 'project') as r (r.name)}
            <li><a href={r.pattern.replace(/\/:[^/]+\??/g, '')} aria-current={route.name === r.name ? 'page' : undefined} onclick={() => (drawer = false)}><Icon name={r.nav!.icon} />{t(r.nav!.label)}</a></li>
          {/each}
        </ul>
      </nav>
      {#if drawer}<button class="scrim" aria-label={t('common.close')} onclick={() => (drawer = false)}></button>{/if}
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
    <nav class="bottomnav kb-hide" aria-label={t('nav.main')}>
      {#each navItems.filter((r) => r.nav?.phone) as r (r.name)}
        <a href={r.pattern.replace(/\/:[^/]+\??/g, '')} aria-current={route.name === r.name ? 'page' : undefined}>
          <Icon name={r.nav!.icon} size={22} /><span>{t(r.nav!.label)}</span>
          {#if r.name === 'activity' && activeCount}<span class="badge" aria-label={t('activity.runningN', { n: activeCount })}>{activeCount}</span>{/if}
        </a>
      {/each}
    </nav>
    {#if activityOpen}
      <aside id="activity-drawer" class="activity-drawer" aria-label={t('activity.title')}>
        <button class="btn quiet icon close" aria-label={t('common.close')} onclick={() => (activityOpen = false)}><Icon name="x" /></button>
        <ActivityPanel />
      </aside>
    {/if}
  </div>
  <CommandPalette bind:open={palette} />
{/if}
<Toasts />

<style>
  .shell { min-height: 100dvh; display: flex; flex-direction: column; }
  .topbar { position: sticky; top: 0; z-index: 500; display: flex; align-items: center; gap: var(--s-2); height: var(--topbar-h); padding: 0 max(var(--s-3), env(safe-area-inset-right)) 0 max(var(--s-3), env(safe-area-inset-left)); background: color-mix(in srgb, var(--surface) 92%, transparent); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }
  .brand { flex: none; display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-width: var(--touch); color: var(--text); text-decoration: none; margin-right: var(--s-2); min-height: var(--touch); }
  .brand img { flex: none; border-radius: 6px; }
  .topbar :global(.switch-select) { flex: 0 1 auto; min-width: 0; }
  .topbar :global(.privacy) { flex: 0 1 auto; min-width: 0; }
  .word { font-family: var(--font-serif); font-weight: 600; font-size: 1.25rem; letter-spacing: 0.01em; border-bottom: 2px solid var(--laterite-mark); line-height: 1.1; }
  .spacer { flex: 1; }
  .search-btn .kbd { margin-left: 4px; }
  .act-btn { position: relative; }
  .count { min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: var(--running-fill); color: #1a1200; font-size: 12px; font-weight: 700; display: inline-grid; place-items: center; }
  .mode { flex: none; }
  .mode label { gap: 6px; min-height: 36px; padding: 0 10px; }
  @media (pointer: coarse) { .mode label { min-height: 44px; } }
  .demo-band { margin: 0; padding: 4px var(--s-3); background: var(--info-soft); color: var(--accent); font-size: var(--fs-xs); font-weight: 600; text-align: center; }
  .body { flex: 1; display: grid; grid-template-columns: var(--rail-w) minmax(0, 1fr); min-height: 0; }
  .rail { position: sticky; top: var(--topbar-h); height: calc(100dvh - var(--topbar-h)); overflow: hidden; border-right: 1px solid var(--line); background: var(--surface); display: flex; flex-direction: column; }
  .rail > :global(.dl) { flex: 1; min-height: 0; overflow: auto; }
  .projnav { list-style: none; margin: 0; padding: var(--s-2) var(--s-2) var(--s-1); display: grid; grid-template-columns: 1fr 1fr; gap: 2px; border-bottom: 1px solid var(--line); }
  .projnav a { display: flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 var(--s-2); border-radius: var(--r-1); color: var(--text-2); text-decoration: none; font-size: var(--fs-sm); font-weight: 600; }
  @media (pointer: coarse) { .projnav a { min-height: 44px; } }
  .projnav a:hover { background: var(--surface-2); color: var(--text); }
  .projnav a[aria-current='page'] { background: var(--accent-soft); color: var(--accent); }
  .secondary { list-style: none; margin: auto 0 0; padding: var(--s-1) 0; border-top: 1px solid var(--line); display: grid; grid-template-columns: 1fr 1fr; }
  .secondary a { display: flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 var(--s-3); color: var(--text-2); text-decoration: none; font-size: var(--fs-sm); font-weight: 600; }
  .secondary a:hover { background: var(--surface-2); color: var(--text); }
  .secondary a[aria-current='page'] { color: var(--accent); }
  main { min-width: 0; padding: var(--s-5) max(var(--s-6), env(safe-area-inset-right)) var(--s-7) var(--s-6); }
  main:focus { outline: none; }
  @media (min-width: 1024px) {
    .rail-hidden .body { grid-template-columns: minmax(0, 1fr); }
    .rail-hidden .rail { display: none; }
  }
  .rail-mode { display: none; margin: var(--s-3) var(--s-3) 0; }
  .rail-mode label { flex: 1; justify-content: center; gap: 6px; }
  .bottomnav { display: none; }
  .scrim { display: none; }
  .activity-drawer { position: fixed; z-index: 700; top: calc(var(--topbar-h) + 6px); right: 8px; width: min(440px, calc(100vw - 16px)); max-height: calc(100dvh - var(--topbar-h) - 16px); overflow: auto; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); box-shadow: var(--shadow-2); padding: var(--s-4); }
  .activity-drawer .close { position: absolute; top: 8px; right: 8px; }
  .loading { padding: var(--s-5) 0; }
  .skel { height: 28px; width: 50%; background: var(--surface-2); border-radius: var(--r-2); margin-bottom: var(--s-3); }
  .skel.short { width: 30%; }
  .boot-error { max-width: 36rem; padding: var(--s-6) 0; }

  @media (max-width: 1279px) {
    .search-btn .kbd { display: none; }
    .search-btn .lbl, .mlbl { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  }
  @media (max-width: 1023px) {
    .menu-btn { display: inline-flex; }
    .word { display: none; }
    .body { grid-template-columns: minmax(0, 1fr); }
    .rail { position: fixed; z-index: 650; left: 0; top: var(--topbar-h); bottom: 0; height: auto; width: min(340px, 88vw); transform: translateX(-105%); transition: transform 180ms var(--ease); box-shadow: var(--shadow-2); visibility: hidden; }
    .drawer-open .rail { transform: none; visibility: visible; }
    .scrim { display: block; position: fixed; inset: var(--topbar-h) 0 0 0; z-index: 640; background: rgba(10, 14, 24, 0.35); border: 0; }
    main { padding: var(--s-4) max(var(--s-4), env(safe-area-inset-right)) var(--s-7) max(var(--s-4), env(safe-area-inset-left)); }
    .rail { padding-left: env(safe-area-inset-left); padding-bottom: env(safe-area-inset-bottom); }
  }
  @media (min-width: 768px) and (max-width: 1023px) {
    .topbar :global(.switch-select) { max-width: 200px; }
    .topbar :global(.pill) { max-width: 180px; }
  }
  @media (max-width: 767px) {
    .topbar { gap: 2px; padding: 0 var(--s-1); }
    .word { display: none; }
    .brand { margin-right: 0; }
    .search-btn, .settings-btn { display: none; }
    .topbar .mode { display: none; }
    .rail-mode { display: flex; }
    .topbar :global(.switch-select) { flex: 1 1 0; width: 0; min-width: 0; max-width: none; }
    .act-btn { display: none; }
    main { padding: var(--s-3) max(var(--s-3), env(safe-area-inset-right)) calc(var(--bottomnav-h) + var(--s-5) + env(safe-area-inset-bottom)) max(var(--s-3), env(safe-area-inset-left)); }
    :global(html[data-kb='open']) main { padding-bottom: var(--s-5); }
    .bottomnav { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; position: fixed; z-index: 500; left: 0; right: 0; bottom: 0; height: calc(var(--bottomnav-h) + env(safe-area-inset-bottom)); padding: 0 env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); background: var(--surface); border-top: 1px solid var(--line); }
    .bottomnav a { position: relative; display: grid; place-items: center; align-content: center; gap: 2px; color: var(--text-2); text-decoration: none; font-size: 12px; font-weight: 600; min-height: 48px; }
    .bottomnav a[aria-current='page'] { color: var(--accent); }
    .bottomnav a[aria-current='page']::before { content: ''; position: absolute; top: 0; left: 25%; right: 25%; height: 3px; border-radius: 0 0 3px 3px; background: var(--accent); }
    .badge { position: absolute; top: 4px; left: calc(50% + 6px); min-width: 18px; height: 18px; border-radius: 9px; background: var(--running-fill); color: #1a1200; font-size: 11px; font-weight: 700; display: grid; place-items: center; padding: 0 4px; }
  }
  @media (prefers-reduced-motion: reduce) { .rail { transition: none; } }
</style>
