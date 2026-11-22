<script lang="ts">
  // The current project's sections, one row under the top bar on project screens (session S-AK, docs/UI.md §14.2).
  // Scrolls sideways on phones (the current section is brought into view). Ctrl+Shift+1 hides / shows it.
  import { route, routes } from '../lib/router.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import Icon from './Icon.svelte';

  let nav: HTMLElement | undefined = $state();
  const items = $derived([
    { name: 'home', href: '/', label: t('nav.dossiers'), icon: 'list' },
    ...routes.filter((r) => r.nav?.group === 'project').sort((a, b) => a.nav!.order - b.nav!.order)
      .map((r) => ({ name: r.name, href: r.pattern.replace(/\/:[^/]+\??/g, ''), label: t(r.nav!.label), icon: r.nav!.icon })),
  ]);
  const current = (name: string) => route.name === name || (name === 'home' && route.name === 'dossier') || (name === 'sources' && route.name === 'reader');
  $effect(() => {
    void route.name;
    queueMicrotask(() => nav?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  });
</script>

<nav bind:this={nav} id="project-bar" class="pbar" aria-label={t('bar.label')}>
  <ul>
    {#each items as it (it.name)}
      <li><a href={it.href} aria-current={current(it.name) ? 'page' : undefined}><Icon name={it.icon} size={16} />{it.label}</a></li>
    {/each}
  </ul>
</nav>

<style>
  .pbar { border-bottom: 1px solid var(--line); background: var(--surface); overflow-x: auto; scrollbar-width: thin; padding: 0 max(var(--s-3), env(safe-area-inset-right)) 0 max(var(--s-3), env(safe-area-inset-left)); }
  ul { list-style: none; margin: 0; padding: 0; display: flex; gap: 2px; min-width: max-content; }
  a { position: relative; display: inline-flex; align-items: center; gap: 6px; min-height: 40px; padding: 0 12px; color: var(--text-2); text-decoration: none; font-size: var(--fs-sm); font-weight: 600; white-space: nowrap; }
  @media (pointer: coarse) { a { min-height: 44px; } }
  a:hover { color: var(--text); background: var(--surface-2); }
  a[aria-current='page'] { color: var(--text); }
  a[aria-current='page']::after { content: ''; position: absolute; left: 10px; right: 10px; bottom: 0; height: 3px; border-radius: 3px 3px 0 0; background: var(--laterite-mark); }
  a[aria-current='page'] :global(.ico) { color: var(--accent); }
</style>
