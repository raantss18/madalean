<script lang="ts">
  import EnterHint from '../../components/EnterHint.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  // Progressive hint ladder (Learn mode), served by POST /dossiers/{id}/hint (docs/RESEARCH_WORKSHOP.md §4):
  //   attempt first (what did you try?) → nudge → strategy → key lemma → next step → full proof (the Lean-verified
  //   proof, never model text). From level 3 the server requires a sentence on what the previous hint told you.
  // Progress comes from GET /learn/{id}/ladder, so it follows the learner's device… and is refreshed on learn.progress.
  import type { Dossier } from '../../lib/api/types';
  import { research, type HintAnswer } from '../../lib/api/research';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { keepDraft, clearDraft } from '../../lib/ui/drafts.svelte';
  import { askHint, HINT_LEVELS, LEVEL_OF_NUMBER, learnError, type HintLevel } from '../../lib/learn/tutor';
  import Md from '../../components/Md.svelte';

  let { dossier: d, onreveal }: { dossier: Dossier; onreveal: () => void } = $props();
  let hints = $state<{ level: HintLevel; text: string; redacted: boolean }[]>([]);
  let attempted = $state(false);
  let tried = $state('');
  let help = $state('');
  let reflections = $state<string[]>([]);
  let reflection = $state('');
  let busy = $state(false);
  let err = $state('');
  const rkey = $derived(`reflections.${d.id}.${d.cur_proof}`);
  // unsent text kept on this device until sent (S-AP)
  keepDraft(() => `hints.tried.${d.id}`, () => tried, (v) => (tried = v));
  keepDraft(() => `hints.reflection.${d.id}.${d.cur_proof}`, () => reflection, (v) => (reflection = v));

  async function load() {
    try {
      const l = await research.ladder(d.id);
      attempted = l.attempted;
      hints = Object.entries(l.hints).sort(([a], [b]) => +a - +b).map(([n, h]) => ({ level: LEVEL_OF_NUMBER[+n] ?? 'nudge', text: h.text, redacted: h.redacted }));
    } catch { /* not proved yet or server without learning: the ladder starts empty */ }
    reflections = loadJSON<string[]>(rkey, []);
  }
  $effect(() => { void d.id; void d.cur_proof; void load(); });
  $effect(() => app.on('learn.progress', () => void load()));

  const nextLevel = $derived<HintLevel>(HINT_LEVELS[Math.min(hints.length, HINT_LEVELS.length - 1)]!);
  const needsReflection = $derived(hints.length > 0 && hints.length > reflections.length);
  const started = $derived(hints.length > 0);

  async function ask() {
    if (busy) return;
    err = '';
    if (needsReflection) {
      if (reflection.trim().length < 8) { err = t('hints.reflectFirst'); return; }
      reflections = [...reflections, reflection.trim()];
      saveJSON(rkey, reflections);
      reflection = '';
    }
    busy = true;
    try {
      const h: HintAnswer = await askHint(d.id, nextLevel, { tried: started || attempted ? tried || '-' : tried, help, reflections });
      attempted = true;
      clearDraft(`hints.tried.${d.id}`);
      if (h.level >= 5 || nextLevel === 'full') { hints = [...hints, { level: 'full', text: '', redacted: false }]; onreveal(); return; }
      hints = [...hints, { level: LEVEL_OF_NUMBER[h.level] ?? nextLevel, text: h.text, redacted: h.redacted }];
    } catch (e) {
      err = learnError(e);
    } finally { busy = false; }
  }
</script>

<section class="ladder" aria-labelledby="hl-h">
  <h3 id="hl-h">{t('hints.title')}</h3>
  <p class="hint">{t('hints.intro')}</p>

  <ol class="rungs" aria-label={t('hints.levels')}>
    {#each HINT_LEVELS as lv, i}
      <li class:done={i < hints.length} class:next={i === hints.length}><span class="dot" aria-hidden="true"></span>{tk(`hints.level.${lv}`, lv)}{#if i < hints.length}<span class="sr-only"> ({t('hints.seen')})</span>{/if}</li>
    {/each}
  </ol>

  {#if !started && !attempted}
    <div class="field">
      <label for="hl-tried">{t('hints.triedLabel')}</label>
      <textarea id="hl-tried" class="input" rows="3" bind:value={tried} use:enterSubmit={() => void ask()} placeholder={t('hints.triedPlaceholder')} aria-describedby="hl-tried-e"></textarea>
      <EnterHint id="hl-tried-e" />
    </div>
    <fieldset class="field help">
      <legend class="label">{t('hints.helpLabel')}</legend>
      <div class="seg">
        {#each ['concept', 'approach', 'step'] as h}
          <label><input type="radio" name="hl-help-{d.id}" value={h} bind:group={help} />{tk(`hints.help.${h}`, h)}</label>
        {/each}
      </div>
    </fieldset>
  {/if}

  {#each hints.filter((h) => h.level !== 'full') as h, i}
    <div class="hintbox">
      <p class="lvl xs">{tk(`hints.level.${h.level}`, h.level)}{#if h.redacted} · <span class="redacted">{t('hints.redacted')}</span>{/if}</p>
      <Md src={h.text} />
      {#if reflections[i]}<p class="refl small"><strong>{t('hints.youNoted')}</strong> {reflections[i]}</p>{/if}
    </div>
  {/each}
  {#if busy}<div class="hintbox" aria-busy="true"><p class="lvl xs">{tk(`hints.level.${nextLevel}`, nextLevel)}</p><p class="muted small">{t('learn.thinking')}</p></div>{/if}

  {#if hints.length < HINT_LEVELS.length}
    {#if needsReflection && !busy}
      <div class="field">
        <label for="hl-refl">{t('hints.reflectLabel')}</label>
        <textarea id="hl-refl" class="input" rows="2" bind:value={reflection} use:enterSubmit={() => void ask()} aria-describedby="hl-refl-h hl-refl-e"></textarea>
        <EnterHint id="hl-refl-e" />
        <p class="hint" id="hl-refl-h">{t('hints.reflectHint')}</p>
      </div>
    {/if}
    {#if err}<p class="error-text" role="alert">{err}</p>{/if}
    <div class="row">
      <button class="btn {nextLevel === 'full' ? '' : 'primary'}" onclick={ask} disabled={busy || (!started && !attempted && tried.trim().length < 3)}>
        {hints.length === 0 ? t('hints.first') : nextLevel === 'full' ? t('hints.reveal') : t('hints.next', { level: tk(`hints.level.${nextLevel}`, nextLevel) })}
      </button>
      <button class="btn quiet small" onclick={onreveal}>{t('hints.iDidIt')}</button>
    </div>
    {#if !started && !attempted}<p class="xs muted">{t('hints.whyTry')}</p>{/if}
  {/if}
  <p class="xs muted">{t('hints.synced')}</p>
</section>

<style>
  .ladder h3 { margin-bottom: 4px; }
  .rungs { list-style: none; display: flex; flex-wrap: wrap; gap: 4px 14px; padding: 0; margin: 0 0 var(--s-3); font-size: var(--fs-xs); color: var(--text-3); }
  .rungs li { display: inline-flex; align-items: center; gap: 6px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid var(--line-strong); }
  .rungs li.done { color: var(--text); }
  .rungs li.done .dot { background: var(--accent); border-color: var(--accent); }
  .rungs li.next { color: var(--accent); font-weight: 700; }
  .rungs li.next .dot { border-color: var(--accent); }
  .help { border: 0; padding: 0; }
  .hintbox { border-left: 3px solid var(--accent); background: var(--accent-soft); padding: var(--s-2) var(--s-3); border-radius: 0 var(--r-2) var(--r-2) 0; margin-bottom: var(--s-3); }
  .lvl { margin: 0 0 2px; font-weight: 700; color: var(--accent); }
  .redacted { color: var(--running); }
  .refl { margin: var(--s-2) 0 0; color: var(--text-2); }
</style>
