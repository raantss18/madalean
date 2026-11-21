<script lang="ts">
  // « Découper en lemmes »: let the model propose lemmas (or write them), they run in parallel as sub-dossiers.
  import type { Dossier } from '../../lib/api/types';
  import { api } from '../../lib/api/client';
  import { app } from '../../lib/store/app.svelte';
  import { t } from '../../lib/i18n/index.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import Dialog from '../../components/Dialog.svelte';
  import { reportError } from './actions';

  let { dossier, open = $bindable(false) }: { dossier: Dossier; open?: boolean } = $props();
  let how = $state<'auto' | 'manual'>('auto');
  let n = $state(3);
  let manual = $state('');
  let busy = $state(false);

  async function go() {
    busy = true;
    try {
      const lemmas = how === 'manual' ? manual.split(/\n\s*\n|\n(?=theorem|lemma)/).map((s) => s.trim()).filter(Boolean).map((s) => (/^(theorem|lemma)\b/.test(s) ? { statement: s } : { problem: s })) : undefined;
      const r = await api.split(dossier.id, { ...(lemmas ? { lemmas } : { n }), start: true });
      for (const j of r.jobs) app.m.jobs[j.id] = j;
      toast('ok', t('split.started', { n: r.children.length }));
      open = false;
    } catch (e) { reportError(e, dossier.id); } finally { busy = false; }
  }
</script>

<Dialog bind:open title={t('split.title')}>
  <p class="small">{t('split.intro')}</p>
  <fieldset class="field" style="border:0;padding:0">
    <legend class="label">{t('split.how')}</legend>
    <label class="switch"><input type="radio" name="split-how" value="auto" bind:group={how} style="appearance:auto;width:18px;height:18px" />{t('split.auto')}</label>
    <label class="switch"><input type="radio" name="split-how" value="manual" bind:group={how} style="appearance:auto;width:18px;height:18px" />{t('split.manual')}</label>
  </fieldset>
  {#if how === 'auto'}
    <div class="field"><label for="split-n">{t('split.n')}</label><input id="split-n" class="input" type="number" min="1" max="8" bind:value={n} style="max-width:8rem" /></div>
  {:else}
    <div class="field"><label for="split-m">{t('split.manualLabel')}</label><textarea id="split-m" class="input mono" rows="6" bind:value={manual}></textarea><p class="hint">{t('split.manualHint')}</p></div>
  {/if}
  {#snippet actions()}
    <button class="btn quiet" onclick={() => (open = false)}>{t('common.cancel')}</button>
    <button class="btn primary" onclick={go} disabled={busy || (how === 'manual' && !manual.trim())}>{busy ? t('split.working') : t('split.go')}</button>
  {/snippet}
</Dialog>
