<script lang="ts">
  // Research screens need a project. Shows the current one (with a way to change it), or helps create the first.
  import type { Snippet } from 'svelte';
  import { app } from '../lib/store/app.svelte';
  import { api } from '../lib/api/client';
  import { t } from '../lib/i18n/index.svelte';
  import { currentProjectId } from '../lib/project.svelte';
  import { setLastProject } from '../lib/prefs.svelte';
  import { errorText } from '../lib/ui/errors';
  let { children }: { children: Snippet<[string]> } = $props();
  const pid = $derived(currentProjectId());
  let title = $state('');
  let err = $state('');
  async function create(e: Event) {
    e.preventDefault();
    if (!title.trim()) { err = t('project.titleRequired'); return; }
    try { const r = await api.createProject({ title: title.trim() }); app.m.projects[r.project.id] = r.project; setLastProject(r.project.id); }
    catch (x) { err = errorText(x); }
  }
</script>

{#if pid}
  {@render children(pid)}
{:else}
  <div class="gate">
    <h1>{t('gate.title')}</h1>
    <p>{t('gate.text')}</p>
    <form onsubmit={create} class="row">
      <label class="sr-only" for="gate-title">{t('project.titleLabel')}</label>
      <input id="gate-title" class="input" bind:value={title} placeholder={t('project.titleHint')} style="max-width: 360px" />
      <button class="btn primary" type="submit">{t('project.create')}</button>
    </form>
    {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  </div>
{/if}

<style>.gate { max-width: 40rem; }</style>
