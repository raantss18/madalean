<script lang="ts">
  // The project page (S-AK, docs/UI.md §14): the project's title and description edited in place (autosaved), what it
  // contains (counts, links to its sections), search across it, and the conductor's instruction. Switching project is
  // done in the top bar's context switcher only.
  import { onDestroy, untrack } from 'svelte';
  import { app } from '../../lib/store/app.svelte';
  import { api } from '../../lib/api/client';
  import { routes } from '../../lib/router.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { research } from '../../lib/api/research';
  import { nb } from '../../lib/api/workbench';
  import { currentProjectId } from '../../lib/project.svelte';
  import { Autosave } from '../../lib/ui/autosave.svelte';
  import ProjectGate from '../../components/ProjectGate.svelte';
  import SaveState from '../../components/SaveState.svelte';
  import InlineTitle from '../../components/InlineTitle.svelte';
  import Icon from '../../components/Icon.svelte';
  import ConsignePanel from '../../components/ConsignePanel.svelte';
  import ProjectSearch from '../../components/ProjectSearch.svelte';

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
  // S-AO (D47): a project with Calcul documents gets its kernel ready in advance (setting; nothing is created)
  $effect(() => {
    const p = pid;
    if (p) untrack(() => { if (app.m.settings?.calcul_warm !== false) nb.warm(p).catch(() => {}); });
  });
  const sections = $derived([{ name: 'home', pattern: '/', nav: { label: 'nav.dossiers' as const, icon: 'list' } }, ...routes.filter((r) => r.nav?.group === 'project'), ...routes.filter((r) => r.name === 'library')]);

  // Title (InlineTitle) and description: edited in place, saved automatically (PATCH /projects/{id}).
  let description = $state('');
  let loadedFor = '';
  $effect(() => {
    if (project && project.id !== loadedFor) { loadedFor = project.id; description = project.description ?? ''; }
  });
  const saver = new Autosave(async () => {
    const id = loadedFor;
    if (!id) return;
    const r = await api.patchProject(id, { description: description.trim() });
    app.m.projects[r.project.id] = r.project;
  });
  onDestroy(() => saver.destroy());
</script>

<ProjectGate>
  {#snippet children(_pid)}
    <div class="hub">
      <div class="row head">
        <InlineTitle id="hub-title" value={project?.title ?? ''} label={t('hub.title')} save={async (v) => { const r = await api.patchProject(pid, { title: v }); app.m.projects[r.project.id] = r.project; }} />
        {#if saver.status !== 'saved'}<SaveState state={saver} />{/if}
      </div>
      <label class="sr-only" for="hub-desc">{t('hub.desc')}</label>
      <textarea id="hub-desc" class="desc" rows="2" placeholder={t('hub.descPh')} bind:value={description} oninput={() => saver.touch()} onblur={() => saver.flush()}></textarea>

      <h2 class="h3">{t('hub.sections')}</h2>
      <ul class="cards">
        {#each sections as s (s.name)}
          <li><a href={s.pattern.replace(/\/:[^/]+\??/g, '') || '/'}>
            <Icon name={s.nav!.icon} size={18} />
            <span class="ct">{t(s.nav!.label)}</span>
            {#if counts[s.name]}<span class="cc xs">{counts[s.name]}</span>{/if}
          </a></li>
        {/each}
      </ul>
      <ProjectSearch {pid} />
      <ConsignePanel {pid} />
    </div>
  {/snippet}
</ProjectGate>

<style>
  .hub { max-width: 980px; }
  .head { align-items: center; gap: var(--s-3); flex-wrap: nowrap; }
  .desc { display: block; width: 100%; margin: var(--s-2) 0 var(--s-4) -7px; padding: 4px 6px; font: inherit; color: var(--text-2); background: transparent; border: 1px solid transparent; border-radius: var(--r-2); resize: vertical; }
  .desc:hover { border-color: var(--line); }
  .desc:focus { border-color: var(--line-strong); background: var(--surface); color: var(--text); }
  .cards { list-style: none; padding: 0; margin: var(--s-2) 0 var(--s-5); display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--s-2); }
  .cards a { display: flex; align-items: center; gap: 10px; min-height: 48px; padding: 0 var(--s-3); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-2); text-decoration: none; color: var(--text); }
  .cards a:hover { border-color: var(--accent); }
  .ct { font-weight: 600; }
  .cc { margin-left: auto; color: var(--accent); font-weight: 700; }
</style>
