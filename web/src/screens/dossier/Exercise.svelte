<script lang="ts">
  // Exercises built and checked by the server (docs/RESEARCH_WORKSHOP.md §4):
  // - faded proof: the last k steps removed (from the END backwards), each blank verified non-trivial; the learner
  //   fills the blanks, Lean checks the result with the strict verdict;
  // - erroneous example: a plausible wrong step that Lean really rejects; the learner first diagnoses it, then sees
  //   Lean's real error, then fixes it (checked by Lean).
  import type { Dossier, CheckResult } from '../../lib/api/types';
  import { research, type ErroneousExercise, type FadedExercise } from '../../lib/api/research';
  import { t } from '../../lib/i18n/index.svelte';
  import { learnError } from '../../lib/learn/tutor';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import CheckResultView from '../../components/CheckResultView.svelte';

  let { dossier: d }: { dossier: Dossier } = $props();
  let kind = $state<'faded' | 'erroneous'>('faded');
  let k = $state(1);
  let faded = $state<FadedExercise | null>(null);
  let fills = $state<string[]>([]);
  let wrong = $state<ErroneousExercise | null>(null);
  let diagnosis = $state('');
  let leanError = $state('');
  let fix = $state('');
  let check = $state<CheckResult | null>(null);
  let busy = $state(false);
  let err = $state('');

  async function newFaded() {
    busy = true; err = ''; check = null;
    try { faded = await research.faded(d.id, k); fills = Array(faded.blanks).fill(''); } catch (e) { err = learnError(e); } finally { busy = false; }
  }
  async function newWrong() {
    busy = true; err = ''; check = null; leanError = ''; diagnosis = '';
    try { wrong = await research.erroneous(d.id); fix = wrong.wrong_proof; } catch (e) { err = learnError(e); } finally { busy = false; }
  }
  async function submitFaded() {
    if (!faded) return;
    busy = true; err = '';
    try { check = (await research.submitExercise(d.id, faded.id, { fills })).check ?? null; } catch (e) { err = learnError(e); } finally { busy = false; }
  }
  async function submitDiagnosis() {
    if (!wrong) return;
    busy = true; err = '';
    try { const r = await research.submitExercise(d.id, wrong.id, { diagnosis }); leanError = r.lean_error ?? ''; } catch (e) { err = learnError(e); } finally { busy = false; }
  }
  async function submitFix() {
    if (!wrong) return;
    busy = true; err = '';
    try { check = (await research.submitExercise(d.id, wrong.id, { code: fix, diagnosis })).check ?? null; } catch (e) { err = learnError(e); } finally { busy = false; }
  }
</script>

<section class="ex" aria-labelledby="ex-h">
  <h3 id="ex-h">{t('exercise.title')}</h3>
  <div class="seg" role="radiogroup" aria-label={t('exercise.kind')}>
    <label><input type="radio" name="exk-{d.id}" checked={kind === 'faded'} onchange={() => { kind = 'faded'; check = null; }} />{t('exercise.faded')}</label>
    <label><input type="radio" name="exk-{d.id}" checked={kind === 'erroneous'} onchange={() => { kind = 'erroneous'; check = null; }} />{t('exercise.erroneous')}</label>
  </div>

  {#if kind === 'faded'}
    <p class="hint">{t('exercise.fadedIntro')}</p>
    <div class="row">
      <label for="ex-k" class="small">{t('exercise.level')}</label>
      <input id="ex-k" class="input" type="number" min="1" max="20" bind:value={k} style="width: 6rem" />
      <button class="btn" onclick={newFaded} disabled={busy}>{faded ? t('exercise.newOne') : t('exercise.start')}</button>
    </div>
    {#if faded}
      <CodeEditor value={faded.template} language="lean" readonly label={t('exercise.editor')} minLines={6} />
      <div class="fills">
        {#each fills as _, i}
          <div class="field"><label for="fill-{i}">{t('exercise.blank', { i: i + 1 })}</label><input id="fill-{i}" class="input mono" bind:value={fills[i]} autocomplete="off" spellcheck="false" /></div>
        {/each}
      </div>
      <button class="btn primary" onclick={submitFaded} disabled={busy || fills.some((f) => !f.trim())}>{busy ? t('lean.checking') : t('lean.checkProof')}</button>
    {/if}
  {:else}
    <p class="hint">{t('exercise.erroneousIntro')}</p>
    <button class="btn" onclick={newWrong} disabled={busy}>{wrong ? t('exercise.newOne') : t('exercise.start')}</button>
    {#if wrong}
      <CodeEditor value={wrong.wrong_proof} language="lean" readonly label={t('exercise.wrongProof')} minLines={6} />
      {#each wrong.prompts as p}<p class="small">{p}</p>{/each}
      <div class="field">
        <label for="diag">{t('exercise.diagnosis')}</label>
        <textarea id="diag" class="input" rows="2" bind:value={diagnosis} disabled={Boolean(leanError)}></textarea>
      </div>
      {#if !leanError}
        <button class="btn primary" onclick={submitDiagnosis} disabled={busy || diagnosis.trim().length < 5}>{t('exercise.showLean')}</button>
      {:else}
        <p class="small"><strong>{t('exercise.leanSays')}</strong></p>
        <pre class="lean-err">{leanError}</pre>
        <label class="label" for="fix-ed">{t('exercise.fix')}</label>
        <CodeEditor id="fix-ed" bind:value={fix} language="lean" label={t('exercise.fix')} minLines={6} onSubmit={() => { if (!busy) void submitFix(); }} describedby="fix-e" />
        <EnterHint id="fix-e" action="check" />
        <button class="btn primary" onclick={submitFix} disabled={busy}>{busy ? t('lean.checking') : t('lean.checkProof')}</button>
      {/if}
    {/if}
  {/if}
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  {#if check}<CheckResultView {check} mode="proof" />{/if}
</section>

<style>
  .ex { border-top: 1px solid var(--line); padding-top: var(--s-3); margin-top: var(--s-4); display: grid; gap: var(--s-2); }
  .fills { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0 var(--s-3); margin-top: var(--s-2); }
  .lean-err { font: 0.8125rem/1.45 var(--font-mono); white-space: pre-wrap; background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-1); }
  .seg { width: fit-content; }
</style>
