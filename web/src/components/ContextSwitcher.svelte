<script lang="ts">
  // « Projet › Dossier » in the top bar (session S-AK, docs/UI.md §14.2): the single place to switch project or
  // dossier. Full names (two lines when needed, tooltip with the whole text); the panel lists the projects beside the
  // dossiers of the highlighted project. Outside click / Escape close it (focus back on the button).
  import { app } from '../lib/store/app.svelte';
  import { api } from '../lib/api/client';
  import { route, navigate } from '../lib/router.svelte';
  import { t } from '../lib/i18n/index.svelte';
  import { prefs, setLastProject } from '../lib/prefs.svelte';
  import { currentProjectId } from '../lib/project.svelte';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import { dismiss } from '../lib/ui/dismiss';
  import Dialog from './Dialog.svelte';
  import DossierList from './DossierList.svelte';
  import Icon from './Icon.svelte';

  let open = $state(false);
  let btn: HTMLButtonElement | undefined = $state();
  let panel: HTMLDivElement | undefined = $state();
  /** Project whose dossiers are listed in the panel ('' = all projects). */
  let browse = $state('');

  const projects = $derived(Object.values(app.m.projects).filter((p) => !p.archived).sort((a, b) => b.updated - a.updated));
  const dossier = $derived(route.name === 'dossier' ? app.m.dossiers[route.params['id'] ?? ''] ?? app.m.full[route.params['id'] ?? ''] : undefined);
  // the project the screen shows: the dossier's; on a project section the current one (it falls back to the most
  // recent project when « Tous les projets » is chosen); else the choice ("" = all projects, the Dossiers page)
  const SECTION_SCREENS = new Set(['project', 'sources', 'reader', 'notes', 'graph', 'blueprint', 'article', 'conjectures', 'calcul', 'publish']);
  const projectId = $derived(dossier?.project_id ?? (SECTION_SCREENS.has(route.name) ? currentProjectId() : prefs.lastProject));
  const projectTitle = $derived(projectId ? app.m.projects[projectId]?.title ?? t('project.all') : t('project.all'));
  const dossierTitle = $derived(dossier ? dossier.title || dossier.theorem : '');
  // S-AY (D57b): a sub-dossier is a dossier with a parent — « Projet › Dossier › Lemme » (bounded, cycle-safe)
  const parents = $derived.by(() => {
    const out: { id: string; title: string }[] = [];
    const seen = new Set<string>();
    let p = dossier?.parent_id ? app.m.dossiers[dossier.parent_id] : undefined;
    while (p && !seen.has(p.id) && out.length < 6) {
      seen.add(p.id);
      out.unshift({ id: p.id, title: p.title || p.theorem });
      p = p.parent_id ? app.m.dossiers[p.parent_id] : undefined;
    }
    return out;
  });
  const full = $derived(dossierTitle ? [projectTitle, ...parents.map((p) => p.title), dossierTitle].join(' › ') : projectTitle);

  function toggle() {
    open = !open;
    if (open) {
      browse = projectId ?? '';
      queueMicrotask(() => panel?.querySelector<HTMLElement>('[aria-current="true"], .proj')?.focus());
    }
  }
  function close(refocus = false) { open = false; if (refocus) btn?.focus(); }
  function pick(id: string) {
    browse = id;
    setLastProject(id);
  }

  // « Nouveau projet » (the dialog lives outside the panel: it survives the panel closing)
  let creating = $state(false);
  let title = $state('');
  let description = $state('');
  let busy = $state(false);
  let err = $state('');
  async function create() {
    if (!title.trim()) { err = t('project.titleRequired'); return; }
    busy = true;
    try {
      const r = await api.createProject({ title: title.trim(), description: description.trim() });
      app.m.projects[r.project.id] = r.project;
      setLastProject(r.project.id);
      creating = false;
      title = ''; description = ''; err = '';
      toast('ok', t('project.created', { title: r.project.title }));
      navigate('/projet');
    } catch (e) { err = errorText(e); } finally { busy = false; }
  }
</script>

<div class="ctx">
  <button bind:this={btn} id="context-switcher" class="ctx-btn" class:two={Boolean(dossierTitle)} aria-expanded={open} aria-controls="ctx-panel"
    title={full} onclick={toggle}>
    <Icon name="folder" size={16} />
    <span class="names">
      <span class="proj-name">{projectTitle}</span>
      {#if dossierTitle}{#each parents as p (p.id)}<span class="sep" aria-hidden="true">›</span><span class="par-name">{p.title}</span>{/each}<span class="sep" aria-hidden="true">›</span><span class="dos-name">{dossierTitle}</span>{/if}
    </span>
    <span class="sr-only">{t('ctx.change')}</span>
    <Icon name="chevronDown" size={14} />
  </button>
  {#if open}
    <div bind:this={panel} id="ctx-panel" class="panel" role="dialog" aria-modal="false" aria-label={t('ctx.title')}
      use:dismiss={{ onclose: () => close(), trigger: btn }}>
      <section class="col projects" aria-labelledby="ctx-ph">
        <h2 id="ctx-ph" class="h">{t('ctx.projects')}</h2>
        <ul>
          <li><button class="proj" aria-current={browse === '' ? 'true' : undefined} onclick={() => pick('')}>{t('project.all')}</button></li>
          {#each projects as p (p.id)}
            <li><button class="proj" aria-current={browse === p.id ? 'true' : undefined} onclick={() => pick(p.id)}>{p.title}</button></li>
          {/each}
        </ul>
        <div class="acts">
          {#if browse}<a class="btn small" href="/projet" onclick={() => close()}><Icon name="folder" size={14} />{t('menu.overview')}</a>{/if}
          <button class="btn small quiet" onclick={() => { close(); creating = true; }}><Icon name="plus" size={14} />{t('ctx.newProject')}</button>
        </div>
      </section>
      <section class="col dossiers" aria-labelledby="ctx-dh">
        <h2 id="ctx-dh" class="h">{browse ? t('ctx.dossiersOf', { title: app.m.projects[browse]?.title ?? '' }) : t('ctx.allDossiers')}</h2>
        <DossierList uid="ctx" project={browse} onpick={() => close()} />
      </section>
    </div>
  {/if}
</div>

<Dialog bind:open={creating} title={t('project.newTitle')}>
  <form onsubmit={(e) => { e.preventDefault(); void create(); }} id="new-project">
    <div class="field">
      <label for="np-title">{t('project.titleLabel')}</label>
      <input id="np-title" class="input" bind:value={title} aria-invalid={err ? 'true' : undefined} aria-describedby={err ? 'np-err' : 'np-hint'} />
      <p class="hint" id="np-hint">{t('project.titleHint')}</p>
      {#if err}<p class="error-text" id="np-err">{err}</p>{/if}
    </div>
    <div class="field">
      <label for="np-desc">{t('project.descLabel')}</label>
      <textarea id="np-desc" class="input" rows="3" bind:value={description}></textarea>
    </div>
  </form>
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (creating = false)}>{t('common.cancel')}</button>
    <button class="btn primary" type="submit" form="new-project" disabled={busy}>{t('project.create')}</button>
  {/snippet}
</Dialog>

<style>
  .ctx { position: relative; min-width: 0; flex: 0 1 auto; }
  .ctx-btn { display: inline-flex; align-items: center; gap: 8px; max-width: 100%; min-height: 40px; padding: 2px 10px; border: 1px solid var(--line-strong); border-radius: var(--r-2); background: var(--surface); color: var(--text); font: 600 var(--fs-sm) / 1.2 var(--font-ui); text-align: left; cursor: pointer; }
  .ctx-btn:hover, .ctx-btn[aria-expanded='true'] { border-color: var(--accent); }
  @media (pointer: coarse) { .ctx-btn { min-height: 44px; } }
  .ctx-btn > :global(.ico) { flex: none; color: var(--text-2); }
  /* Full names: wrap on two lines rather than cut; only beyond two lines the end is clipped (tooltip has it all). */
  .names { min-width: 0; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden; overflow-wrap: anywhere; }
  .sep { color: var(--text-3); margin: 0 4px; }
  .proj-name { color: var(--text-2); }
  .two .dos-name { color: var(--text); }
  .panel { position: absolute; z-index: 800; top: calc(100% + 6px); left: 0; width: min(760px, calc(100vw - 24px)); max-height: calc(100dvh - var(--topbar-h) - 16px); display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); box-shadow: var(--shadow-2); overflow: hidden; }
  .col { min-height: 0; overflow: auto; display: flex; flex-direction: column; }
  .projects { border-right: 1px solid var(--line); padding: var(--s-2); }
  .dossiers { padding-top: var(--s-2); }
  .h { margin: 4px 10px 6px; font: 700 var(--fs-xs) var(--font-ui); color: var(--text-3); text-transform: uppercase; letter-spacing: 0.04em; overflow-wrap: anywhere; }
  .dossiers .h { margin-left: var(--s-3); }
  ul { list-style: none; margin: 0; padding: 0; }
  .proj { display: block; width: 100%; min-height: 40px; padding: 8px 10px; border: 0; border-left: 3px solid transparent; border-radius: var(--r-1); background: none; color: var(--text); font: 600 var(--fs-sm) / 1.3 var(--font-ui); text-align: left; overflow-wrap: anywhere; cursor: pointer; }
  .proj:hover { background: var(--surface-2); }
  .proj[aria-current='true'] { background: var(--accent-soft); color: var(--accent); border-left-color: var(--accent); }
  @media (pointer: coarse) { .proj { min-height: 44px; } }
  .acts { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: auto; padding: var(--s-3) 4px 4px; }
  /* Tablets: the panel may need the whole width. Phones: a sheet under the top bar, projects above the dossiers. */
  @media (max-width: 1023px) { .panel { position: fixed; left: 12px; right: 12px; top: calc(var(--topbar-h) + 4px); width: auto; } }
  @media (max-width: 767px) {
    .ctx { flex: 1 1 0; }
    .ctx-btn { width: 100%; }
    .names { display: grid; -webkit-line-clamp: unset; line-clamp: none; }
    .two .names { font-size: var(--fs-xs); }
    .two .proj-name, .two .dos-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .two .sep { display: none; }
    .two .dos-name { font-size: var(--fs-sm); }
    .panel { left: 0; right: 0; top: var(--topbar-h); border-radius: 0 0 var(--r-3) var(--r-3); grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); max-height: calc(100dvh - var(--topbar-h)); }
    .projects { border-right: 0; border-bottom: 1px solid var(--line); max-height: 38dvh; }
  }
</style>
