<script lang="ts">
  // Project switcher: a native <select> (accessible everywhere, phone pickers) + « new project » dialog.
  import { app } from '../lib/store/app.svelte';
  import { api } from '../lib/api/client';
  import { t } from '../lib/i18n/index.svelte';
  import { prefs, setLastProject } from '../lib/prefs.svelte';
  import { toast } from '../lib/ui/toasts.svelte';
  import { errorText } from '../lib/ui/errors';
  import Dialog from './Dialog.svelte';

  const projects = $derived(Object.values(app.m.projects).filter((p) => !p.archived).sort((a, b) => b.updated - a.updated));
  let creating = $state(false);
  let title = $state('');
  let description = $state('');
  let busy = $state(false);
  let err = $state('');

  function change(e: Event) {
    const v = (e.target as HTMLSelectElement).value;
    if (v === '__new') { creating = true; (e.target as HTMLSelectElement).value = prefs.lastProject; return; }
    setLastProject(v);
  }
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
    } catch (e) { err = errorText(e); } finally { busy = false; }
  }
</script>

<label class="sr-only" for="project-select">{t('project.label')}</label>
<select id="project-select" class="switch-select" value={prefs.lastProject} onchange={change}>
  <option value="">{t('project.all')}</option>
  {#each projects as p (p.id)}<option value={p.id}>{p.title}</option>{/each}
  <option value="__new">{t('project.new')}</option>
</select>

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
  .switch-select { min-height: 36px; max-width: 240px; padding: 0 28px 0 10px; border: 1px solid var(--line-strong); border-radius: var(--r-2); background: var(--surface); color: var(--text); font: 600 var(--fs-sm) var(--font-ui); text-overflow: ellipsis; }
  @media (pointer: coarse) { .switch-select { min-height: 44px; } }

</style>
