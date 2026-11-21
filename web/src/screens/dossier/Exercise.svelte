<script lang="ts">
  // Faded worked example: the proven proof with its last k steps removed (fading from the END backwards);
  // the learner completes it and Lean checks it (strict mode). Success → next level removes one more step.
  import type { Dossier, CheckResult } from '../../lib/api/types';
  import { api } from '../../lib/api/client';
  import { t } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { fadeProof } from '../../lib/learn/tutor';
  import { errorText } from '../../lib/ui/errors';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';

  let { dossier: d }: { dossier: Dossier } = $props();
  const key = $derived(`exercise.${d.id}.${d.cur_proof}`);
  let level = $state(1);
  let code = $state('');
  let check = $state<CheckResult | null>(null);
  let busy = $state(false);
  let err = $state('');
  let why = $state('');
  let ctl: AbortController | null = null;
  const fade = $derived(fadeProof(d.current.proof, level));
  $effect(() => {
    const saved = loadJSON<{ level: number; why: string }>(key, { level: 1, why: '' });
    level = saved.level; why = saved.why;
  });
  $effect(() => { if (fade) { code = fade.exercise; check = null; } });

  async function verify() {
    busy = true; err = ''; check = null;
    ctl = new AbortController();
    try {
      const r = await api.check(code, { workspace: d.workspace, strict: true }, { signal: ctl.signal });
      check = r.check;
    } catch (e) { if ((e as Error).name !== 'AbortError') err = errorText(e); } finally { busy = false; ctl = null; }
  }
  function next() { level = Math.min((fade?.total ?? 1), level + 1); saveJSON(key, { level, why }); }
</script>

{#if fade}
  <section class="ex" aria-labelledby="ex-h">
    <h3 id="ex-h">{t('exercise.title')}</h3>
    <p class="hint">{t('exercise.intro', { k: Math.min(level, fade.total), n: fade.total })}</p>
    <div class="row lv">
      <label for="ex-level" class="small">{t('exercise.level')}</label>
      <select id="ex-level" class="input" style="width:auto" bind:value={level} onchange={() => saveJSON(key, { level, why })}>
        {#each Array(fade.total) as _, i}<option value={i + 1}>{i + 1 === fade.total ? t('exercise.levelAll') : t('exercise.levelK', { k: i + 1 })}</option>{/each}
      </select>
    </div>
    <CodeEditor bind:value={code} language="lean" label={t('exercise.editor')} minLines={6} onSubmit={verify} />
    <div class="row" style="margin-top: var(--s-2)">
      <button class="btn primary" onclick={verify} disabled={busy}>{busy ? t('lean.checking') : t('lean.checkProof')}</button>
      {#if busy}<button class="btn quiet" onclick={() => ctl?.abort()}>{t('common.cancel')}</button>{/if}
      <button class="btn quiet" onclick={() => fade && (code = fade.exercise)}>{t('exercise.reset')}</button>
    </div>
    {#if err}<p class="error-text" role="alert">{err}</p>{/if}
    {#if check}
      <CheckResultView {check} mode="proof" />
      {#if check.ok}
        <div class="field why">
          <label for="ex-why">{t('exercise.whyLabel')}</label>
          <textarea id="ex-why" class="input" rows="2" bind:value={why} onchange={() => saveJSON(key, { level, why })}></textarea>
        </div>
        {#if level < fade.total}<button class="btn" onclick={next}>{t('exercise.harder')}</button>{/if}
      {/if}
    {/if}
  </section>
{/if}

<style>
  .ex { border-top: 1px solid var(--line); padding-top: var(--s-3); margin-top: var(--s-4); }
  .lv { margin-bottom: var(--s-2); }
  .why { margin-top: var(--s-3); }
</style>
