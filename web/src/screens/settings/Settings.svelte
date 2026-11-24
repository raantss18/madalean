<script lang="ts">
  import type { Component } from 'svelte';
  import { navigate } from '../../lib/router.svelte';
  import { t, type Key } from '../../lib/i18n/index.svelte';
  import { app } from '../../lib/store/app.svelte';
  import Icon from '../../components/Icon.svelte';
  import HelpLink from '../../components/HelpLink.svelte';

  let { params }: { params: Record<string, string> } = $props();
  interface Sec { id: string; label: Key; icon: string; load: () => Promise<{ default: Component }>; help?: string; hidden?: boolean }
  const sections: Sec[] = [
    { id: 'modeles', help: 'models-keys', label: 'settings.sec.models', icon: 'cpu', load: () => import('./Models.svelte') },
    { id: 'apprentissage', help: 'proof-graph', label: 'settings.sec.lessons', icon: 'sparkle', load: () => import('./Lessons.svelte') },
    { id: 'memoire', help: 'memory', label: 'settings.sec.memory', icon: 'history', load: () => import('./Memory.svelte') },
    { id: 'fournisseurs', help: 'models-keys', label: 'settings.sec.providers', icon: 'key', load: () => import('./Providers.svelte') },
    { id: 'cles', help: 'models-keys', label: 'settings.sec.providers', icon: 'key', load: () => import('./Providers.svelte'), hidden: true },
    { id: 'appareils', help: 'pairing', label: 'settings.sec.devices', icon: 'device', load: () => import('./Devices.svelte') },
    { id: 'espaces', label: 'settings.sec.workspaces', icon: 'folder', load: () => import('./Workspaces.svelte') },
    { id: 'mises-a-jour', help: 'updates', label: 'settings.sec.updates', icon: 'refresh', load: () => import('./Updates.svelte') },
    { id: 'actualites', help: 'news', label: 'settings.sec.news', icon: 'globe', load: () => import('./NewsSettings.svelte') },
    { id: 'profil', label: 'settings.sec.profile', icon: 'heart', load: () => import('./Profile.svelte') },
    { id: 'langue', help: 'first-run', label: 'settings.sec.language', icon: 'globe', load: () => import('./Language.svelte') },
    { id: 'apparence', help: 'shortcuts', label: 'settings.sec.appearance', icon: 'sun', load: () => import('./Appearance.svelte') },
    { id: 'carnet', help: 'security', label: 'settings.sec.notebook', icon: 'notebook', load: () => import('./NotebookSettings.svelte') },
    { id: 'outils-mcp', help: 'mcp', label: 'settings.sec.mcp', icon: 'plug', load: () => import('./McpSettings.svelte') },
    { id: 'systeme', help: 'troubleshooting', label: 'settings.sec.system', icon: 'terminal', load: () => import('./System.svelte') },
    { id: 'a-propos', label: 'settings.sec.about', icon: 'info', load: () => import('./About.svelte') },
  ];
  const narrow = typeof matchMedia !== 'undefined' && matchMedia('(max-width: 767px)').matches;
  const current = $derived(sections.find((s) => s.id === params['section']) ?? (narrow ? null : sections[0]!));
  const cache = new Map<string, Promise<Component>>();
  function load(s: Sec) {
    let p = cache.get(s.id);
    if (!p) { p = s.load().then((m) => m.default); cache.set(s.id, p); }
    return p;
  }
</script>

<div class="settings">
  <nav class="secnav" class:hide-narrow={Boolean(params['section'])} aria-label={t('settings.title')}>
    <h1 class:sr-only={Boolean(params['section']) && narrow}>{t('settings.title')}</h1>
    {#if !app.m.local}<p class="remote-note small"><Icon name="lock" size={14} /> {t('settings.remoteNote')}</p>
    {:else}<a class="first-steps" href="/premiers-pas"><Icon name="sparkle" />{t('setup.fromSettings')}</a>{/if}
    <ul>
      {#each sections.filter((x) => !x.hidden) as s (s.id)}
        <li><a href="/reglages/{s.id}" aria-current={current?.id === s.id || (current?.hidden && current.label === s.label) ? 'page' : undefined}><Icon name={s.icon} />{t(s.label)}<span class="chev"><Icon name="chevronRight" size={16} /></span></a></li>
      {/each}
    </ul>
  </nav>
  {#if current}
    <section class="content" aria-labelledby="sec-h">
      <button class="btn quiet small back" onclick={() => navigate('/reglages')}><Icon name="chevronLeft" size={16} />{t('settings.title')}</button>
      <div class="row"><h2 id="sec-h" data-route-focus>{t(current.label)}</h2>{#if current.help}<HelpLink page={current.help} />{/if}</div>
      {#await load(current) then C}<C />{/await}
    </section>
  {/if}
</div>

<style>
  .settings { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: var(--s-6); max-width: 1180px; }
  .secnav ul { list-style: none; margin: 0; padding: 0; }
  .secnav a { display: flex; align-items: center; gap: 10px; min-height: var(--touch); padding: 0 var(--s-3); border-radius: var(--r-2); color: var(--text-2); text-decoration: none; font-weight: 600; }
  .secnav a:hover { background: var(--surface-2); color: var(--text); }
  .secnav a[aria-current='page'] { background: var(--accent-soft); color: var(--accent); }
  .chev { margin-left: auto; display: none; }
  .content h2 { font-size: var(--fs-xl); }
  .back { display: none; margin-bottom: var(--s-2); }
  .first-steps { display: flex; align-items: center; gap: 10px; min-height: var(--touch); padding: 0 var(--s-3); margin-bottom: var(--s-2); border: 1px dashed var(--line-strong); border-radius: var(--r-2); color: var(--accent); text-decoration: none; font-weight: 600; }
  .first-steps:hover { background: var(--accent-soft); }
  .remote-note { display: flex; gap: 6px; align-items: center; color: var(--text-2); background: var(--surface-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
  @media (max-width: 767px) {
    .settings { grid-template-columns: minmax(0, 1fr); gap: var(--s-3); }
    .hide-narrow { display: none; }
    .chev { display: inline-flex; }
    .secnav a { border-bottom: 1px solid var(--line); border-radius: 0; }
    .back { display: inline-flex; }
  }
</style>
