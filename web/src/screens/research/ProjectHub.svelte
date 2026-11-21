<script lang="ts">
  // The current project at a glance: one door to its dossiers, sources, notes, graph, blueprint, article,
  // conjectures and publication (the phone's « Projet » tab).
  import { app } from '../../lib/store/app.svelte';
  import { routes } from '../../lib/router.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { research } from '../../lib/api/research';
  import { currentProjectId } from '../../lib/project.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import ProjectSwitcher from '../../components/ProjectSwitcher.svelte';
  import Icon from '../../components/Icon.svelte';

  let { params: _p }: { params: Record<string, string> } = $props();
  const pid = $derived(currentProjectId());
  const project = $derived(app.m.projects[pid]);
  let counts = $state<Record<string, string>>({});
  $effect(() => {
    if (!pid) return;
    const ds = Object.values(app.m.dossiers).filter((d) => d.project_id === pid && !d.archived);
    counts = { home: t('hub.dossiers', { n: ds.length, p: ds.filter((d) => d.proved).length }) };
    research.shelves().then((r) => { const s = r.shelves.find((x) => x.id === pid); if (s) counts = { ...counts, sources: t('hub.count', { n: s.count }) }; }).catch(() => {});
    research.notes(pid).then((r) => (counts = { ...counts, notes: t('hub.count', { n: r.notes.length }) })).catch(() => {});
    research.conjectures(pid).then((r) => (counts = { ...counts, conjectures: t('hub.count', { n: r.conjectures.length }) })).catch(() => {});
    research.blueprints(pid).then((r) => (counts = { ...counts, blueprint: t('hub.count', { n: r.blueprints.length }) })).catch(() => {});
  });
  const sections = $derived([{ name: 'home', pattern: '/', nav: { label: 'nav.dossiers' as const, icon: 'list' } }, ...routes.filter((r) => r.nav?.group === 'project'), ...routes.filter((r) => r.name === 'library')]);
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="hub">
      <h1>{project?.title ?? t('nav.project')}</h1>
      {#if project?.description}<p class="lead">{project.description}</p>{/if}
      <div class="row"><span class="small">{t('hub.change')}</span><ProjectSwitcher /></div>
      <ul class="cards">
        {#each sections as s (s.name)}
          <li><a href={s.pattern.replace(/\/:[^/]+\??/g, '') || '/'}>
            <Icon name={s.nav!.icon} size={22} />
            <span class="ct">{t(s.nav!.label)}</span>
            <span class="cd xs">{t(`hub.desc.${s.name}` as 'hub.desc.home')}</span>
            {#if counts[s.name]}<span class="cc xs">{counts[s.name]}</span>{/if}
          </a></li>
        {/each}
      </ul>
    </div>
  {/snippet}
</ProjectGate>

<style>
  .hub { max-width: 980px; }
  .lead { color: var(--text-2); }
  .cards { list-style: none; padding: 0; margin: var(--s-4) 0 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--s-3); }
  .cards a { display: grid; gap: 4px; padding: var(--s-3) var(--s-4); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); text-decoration: none; color: var(--text); min-height: 100%; }
  .cards a:hover { border-color: var(--accent); }
  .ct { font: 600 1.0625rem var(--font-serif); }
  .cd { color: var(--text-2); }
  .cc { color: var(--accent); font-weight: 700; }
</style>
