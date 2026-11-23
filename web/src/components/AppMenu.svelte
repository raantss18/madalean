<script lang="ts">
  // The logo is the main menu (session S-AK, docs/UI.md §14.2): one click opens it (« Accueil » first and focused),
  // a second click on the logo while it is open goes home. ARIA menu button: arrows / Home / End move, Escape and an
  // outside click close it, the focus returns to the logo. Shows the project's sections only when the project bar is
  // not on screen (the menu holds what the screen does not show).
  import { app } from '../lib/store/app.svelte';
  import { route, routes, navigate } from '../lib/router.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import { prefs, setMode, type UiMode } from '../lib/prefs.svelte';
  import { barShown, setBar } from '../lib/ui/layout.svelte';
  import { dismiss } from '../lib/ui/dismiss';
  import { currentProjectId } from '../lib/project.svelte';
  import { newsBadge, loadNewsOverview } from '../lib/news.svelte';
  import Icon from './Icon.svelte';
  import Wordmark from './Wordmark.svelte';

  let { barOnScreen }: { barOnScreen: boolean } = $props();
  let open = $state(false);
  let btn: HTMLButtonElement | undefined = $state();
  let list: HTMLDivElement | undefined = $state();

  const href = (pattern: string) => pattern.replace(/\/:[^/]+\??/g, '') || '/';
  const sections = $derived(routes.filter((r) => r.nav?.group === 'project').sort((a, b) => a.nav!.order - b.nav!.order));
  const tools = $derived(routes.filter((r) => r.nav && !r.nav.group && !['home', 'project', 'help', 'settings'].includes(r.name)).sort((a, b) => a.nav!.order - b.nav!.order));
  const project = $derived(app.m.projects[currentProjectId()]);
  const active = $derived(app.activeJobs.length);

  function items(): HTMLElement[] { return [...(list?.querySelectorAll<HTMLElement>('[role^=menuitem]') ?? [])]; }
  function show() {
    open = true;
    void loadNewsOverview();                           // S-AV: the unread count of « Actualités », asked when the menu opens
    queueMicrotask(() => items()[0]?.focus());
  }
  function close(refocus = false) { open = false; if (refocus) btn?.focus(); }
  function onLogo() {
    if (open) { close(); navigate('/'); return; }      // second click: home
    show();
  }
  function onBtnKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); show(); if (e.key === 'ArrowUp') queueMicrotask(() => items().at(-1)?.focus()); }
  }
  function key(e: KeyboardEvent) {
    const els = items();
    const i = els.indexOf(document.activeElement as HTMLElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); els[(i + 1) % els.length]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); els[(i - 1 + els.length) % els.length]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); els[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); els.at(-1)?.focus(); }
    else if (e.key === 'Tab') close();
    else if (e.key === ' ' && (document.activeElement as HTMLElement)?.tagName === 'A') { e.preventDefault(); (document.activeElement as HTMLElement).click(); }
  }
  function pickMode(m: UiMode) { setMode(m); }
  const cur = (name: string) => route.name === name || (name === 'sources' && route.name === 'reader') || (name === 'home' && route.name === 'dossier');
</script>

<div class="appmenu">
  <button bind:this={btn} class="logo-btn" aria-haspopup="menu" aria-expanded={open} aria-controls="app-menu"
    aria-label={t('menu.label')} title={t('menu.title')} onclick={onLogo} onkeydown={onBtnKey}>
    <img class="brand-icon" src="/brand/icon.svg" alt="" width="32" height="32" />
    <span class="word"><Wordmark height={28} alt="" /></span>
    <Icon name="chevronDown" size={14} />
  </button>
  {#if open}
    <div class="scrim" aria-hidden="true"></div>
    <div bind:this={list} id="app-menu" class="panel" role="menu" aria-label={t('menu.label')} tabindex="-1" onkeydown={key}
      use:dismiss={{ onclose: () => close(), trigger: btn }}>
      <a role="menuitem" href="/" aria-current={route.name === 'home' ? 'page' : undefined} onclick={() => close()}><Icon name="home" size={18} />{t('nav.home')}</a>
      {#if !barOnScreen}
        <div role="separator"></div>
        <div role="group" aria-label={project ? t('menu.projectOf', { title: project.title }) : t('nav.project')}>
          <p class="grp xs" aria-hidden="true">{project ? project.title : t('nav.project')}</p>
          <a role="menuitem" href="/projet" aria-current={route.name === 'project' ? 'page' : undefined} onclick={() => close()}><Icon name="folder" size={18} />{t('menu.overview')}</a>
          {#each sections as r (r.name)}
            <a role="menuitem" href={href(r.pattern)} aria-current={cur(r.name) ? 'page' : undefined} onclick={() => close()}><Icon name={r.nav!.icon} size={18} />{t(r.nav!.label)}</a>
          {/each}
        </div>
      {/if}
      <div role="separator"></div>
      <div role="group" aria-label={t('menu.tools')}>
        {#each tools as r (r.name)}
          <a role="menuitem" href={href(r.pattern)} aria-current={cur(r.name) ? 'page' : undefined} onclick={() => close()}>
            <Icon name={r.nav!.icon} size={18} />{t(r.nav!.label)}{#if r.name === 'activity' && active}<span class="count" aria-hidden="true">{active}</span><span class="sr-only">({t('activity.runningN', { n: active })})</span>{/if}{#if r.name === 'news' && newsBadge.show && newsBadge.unread}<span class="count quiet" aria-hidden="true">{newsBadge.unread > 99 ? '99+' : newsBadge.unread}</span><span class="sr-only">({t('news.unreadN', { n: newsBadge.unread })})</span>{/if}
          </a>
        {/each}
      </div>
      <div role="separator"></div>
      <a role="menuitem" href="/aide" aria-current={cur('help') ? 'page' : undefined} onclick={() => close()}><Icon name="info" size={18} />{t('nav.help')}</a>
      {#if app.m.local}<a role="menuitem" href="/premiers-pas" onclick={() => close()}><Icon name="sparkle" size={18} />{t('setup.title')}</a>{/if}
      <a role="menuitem" href="/reglages" aria-current={cur('settings') ? 'page' : undefined} onclick={() => close()}><Icon name="settings" size={18} />{t('nav.settings')}</a>
      <div role="separator"></div>
      <div role="group" aria-label={t('mode.label')}>
        <p class="grp xs" aria-hidden="true">{t('mode.label')}</p>
        <button role="menuitemradio" aria-checked={prefs.mode === 'learn'} title={t('mode.learnHint')} onclick={() => pickMode('learn')}><Icon name="graduate" size={18} />{t('mode.learn')}<span class="tick" aria-hidden="true">{prefs.mode === 'learn' ? '✓' : ''}</span></button>
        <button role="menuitemradio" aria-checked={prefs.mode === 'research'} title={t('mode.researchHint')} onclick={() => pickMode('research')}><Icon name="microscope" size={18} />{t('mode.research')}<span class="tick" aria-hidden="true">{prefs.mode === 'research' ? '✓' : ''}</span></button>
      </div>
      <button role="menuitemcheckbox" aria-checked={barShown()} aria-keyshortcuts="Control+Shift+1" onclick={() => setBar(!barShown())}>
        <Icon name="list" size={18} />{t('menu.bar')}<span class="kbd-h xs">{t('layout.key', { k: '1' })}</span><span class="tick" aria-hidden="true">{barShown() ? '✓' : ''}</span>
      </button>
    </div>
  {/if}
</div>

<style>
  .appmenu { position: relative; flex: none; }
  .logo-btn { display: inline-flex; align-items: center; gap: 6px; min-height: var(--touch); min-width: var(--touch); padding: 0 6px; border: 1px solid transparent; border-radius: var(--r-2); background: none; color: var(--text-2); cursor: pointer; }
  .logo-btn:hover, .logo-btn[aria-expanded='true'] { background: var(--surface-2); border-color: var(--line); }
  .brand-icon { flex: none; border-radius: 7px; display: none; }
  .word { display: inline-flex; }
  .panel { position: absolute; z-index: 800; top: calc(100% + 6px); left: 0; width: 290px; max-height: calc(100dvh - var(--topbar-h) - 16px); overflow: auto; padding: 6px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); box-shadow: var(--shadow-2); }
  .panel a, .panel button { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 40px; padding: 0 10px; border: 0; border-radius: var(--r-1); background: none; color: var(--text); font: inherit; font-size: var(--fs-sm); font-weight: 600; text-align: left; text-decoration: none; cursor: pointer; }
  .panel a:hover, .panel button:hover, .panel a:focus-visible, .panel button:focus-visible { background: var(--surface-2); outline-offset: -2px; }
  .panel a[aria-current='page'] { color: var(--accent); background: var(--accent-soft); }
  .panel :global(.ico) { color: var(--text-2); flex: none; }
  .panel a[aria-current='page'] :global(.ico) { color: var(--accent); }
  [role='separator'] { height: 1px; margin: 6px 4px; background: var(--line); }
  .grp { margin: 4px 10px 2px; color: var(--text-3); font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; overflow-wrap: anywhere; }
  .tick { margin-left: auto; color: var(--accent); font-weight: 700; }
  .kbd-h { margin-left: auto; color: var(--text-3); font-weight: 500; }
  .kbd-h + .tick { margin-left: 8px; }
  .count { margin-left: auto; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: var(--running-fill); color: #1a1200; font-size: 12px; font-weight: 700; display: inline-grid; place-items: center; }
  .count.quiet { background: var(--accent-soft); color: var(--accent); }
  .scrim { display: none; }
  @media (pointer: coarse) { .panel a, .panel button { min-height: 44px; } }
  @media (max-width: 1023px) {
    .word { display: none; }
    .brand-icon { display: block; }
  }
  /* Phones: a sheet from the left edge, the full height under the top bar. */
  @media (max-width: 767px) {
    .scrim { display: block; position: fixed; inset: var(--topbar-h) 0 0 0; z-index: 790; background: rgba(10, 14, 24, 0.4); }
    .panel { position: fixed; top: var(--topbar-h); left: 0; bottom: 0; width: min(320px, 86vw); max-height: none; border-radius: 0 var(--r-3) var(--r-3) 0; padding: 8px 8px calc(8px + env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left)); }
    .kbd-h { display: none; }
    .panel a, .panel button { min-height: 48px; }
  }
  @media (prefers-reduced-motion: no-preference) { .panel { animation: am-in 120ms var(--ease); } }
  @keyframes am-in { from { transform: translateY(-4px); } to { transform: none; } }   /* no opacity: contrast stays exact */
</style>
