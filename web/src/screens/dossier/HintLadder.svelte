<script lang="ts">
  // Progressive hint ladder (Learn mode), before the proof is revealed:
  //   diagnose (what did you try? what kind of help?) → nudge → strategy → key lemma → next step → full proof.
  // Each rung needs a short reflection on the previous hint (« what did it tell you? ») before the next one —
  // the anti « hint clicking » safeguard of the progressive-hint-ladder skill. Progress is kept per device.
  import type { Dossier } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, i18n } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { assistantTutor, HINT_LEVELS, type HintLevel } from '../../lib/learn/tutor';
  import { errorText } from '../../lib/ui/errors';
  import Md from '../../components/Md.svelte';

  let { dossier: d, onreveal }: { dossier: Dossier; onreveal: () => void } = $props();
  interface Progress { tried: string; help: string; hints: { level: HintLevel; text: string }[]; reflections: string[]; solved: boolean }
  const key = $derived(`hints.${d.id}.${d.cur_statement}`);
  let p = $state<Progress>({ tried: '', help: '', hints: [], reflections: [], solved: false });
  $effect(() => { p = loadJSON<Progress>(key, { tried: '', help: '', hints: [], reflections: [], solved: false }); });
  let reflection = $state('');
  let busy = $state(false);
  let streaming = $state('');
  let err = $state('');
  let stopFn: (() => void) | null = null;
  const tutor = assistantTutor((id, fn) => app.listenAssistant(id, fn));

  const nextLevel = $derived<HintLevel>(HINT_LEVELS[Math.min(p.hints.length, HINT_LEVELS.length - 1)]!);
  const needsReflection = $derived(p.hints.length > p.reflections.length);
  const started = $derived(p.hints.length > 0);
  function persist() { saveJSON(key, p); }

  async function ask() {
    if (busy) return;
    if (needsReflection) {
      if (reflection.trim().length < 8) { err = t('hints.reflectFirst'); return; }
      p.reflections.push(reflection.trim());
      reflection = '';
    }
    err = '';
    if (nextLevel === 'full') { p.hints.push({ level: 'full', text: '' }); persist(); onreveal(); return; }
    busy = true; streaming = '';
    persist();
    try {
      const s = await tutor.hint(d, nextLevel, { tried: p.tried, helpType: p.help ? tk(`hints.help.${p.help}`, p.help) : '', reflections: p.reflections, lang: i18n.lang });
      stopFn = s.stop;
      s.onToken((x) => { streaming += x; });
      const r = await s.done;
      if (r.finish !== 'cancelled') { p.hints.push({ level: nextLevel, text: r.text || streaming }); persist(); }
    } catch (e) { err = errorText(e); } finally { busy = false; streaming = ''; stopFn = null; }
  }
</script>

<section class="ladder" aria-labelledby="hl-h">
  <h3 id="hl-h">{t('hints.title')}</h3>
  <p class="hint">{t('hints.intro')}</p>

  <ol class="rungs" aria-label={t('hints.levels')}>
    {#each HINT_LEVELS as lv, i}
      <li class:done={i < p.hints.length} class:next={i === p.hints.length}><span class="dot" aria-hidden="true"></span>{tk(`hints.level.${lv}`, lv)}{#if i < p.hints.length}<span class="sr-only"> ({t('hints.seen')})</span>{/if}</li>
    {/each}
  </ol>

  {#if !started}
    <div class="field">
      <label for="hl-tried">{t('hints.triedLabel')}</label>
      <textarea id="hl-tried" class="input" rows="3" bind:value={p.tried} oninput={persist} placeholder={t('hints.triedPlaceholder')}></textarea>
    </div>
    <fieldset class="field help">
      <legend class="label">{t('hints.helpLabel')}</legend>
      <div class="seg">
        {#each ['concept', 'approach', 'step'] as h}
          <label><input type="radio" name="hl-help-{d.id}" value={h} bind:group={p.help} onchange={persist} />{tk(`hints.help.${h}`, h)}</label>
        {/each}
      </div>
    </fieldset>
  {/if}

  {#each p.hints.filter((h) => h.level !== 'full') as h, i}
    <div class="hintbox">
      <p class="lvl xs">{tk(`hints.level.${h.level}`, h.level)}</p>
      <Md src={h.text} />
      {#if p.reflections[i]}<p class="refl small"><strong>{t('hints.youNoted')}</strong> {p.reflections[i]}</p>{/if}
    </div>
  {/each}
  {#if busy}<div class="hintbox" aria-busy="true"><p class="lvl xs">{tk(`hints.level.${nextLevel}`, nextLevel)}</p>{#if streaming}<Md src={streaming} />{:else}<p class="muted small">{t('learn.thinking')}</p>{/if}</div>{/if}

  {#if p.hints.length < HINT_LEVELS.length}
    {#if needsReflection && !busy}
      <div class="field">
        <label for="hl-refl">{t('hints.reflectLabel')}</label>
        <textarea id="hl-refl" class="input" rows="2" bind:value={reflection} aria-describedby="hl-refl-h"></textarea>
        <p class="hint" id="hl-refl-h">{t('hints.reflectHint')}</p>
      </div>
    {/if}
    {#if err}<p class="error-text" role="alert">{err}</p>{/if}
    <div class="row">
      <button class="btn {nextLevel === 'full' ? '' : 'primary'}" onclick={ask} disabled={busy || (!started && p.tried.trim().length < 3)}>
        {p.hints.length === 0 ? t('hints.first') : nextLevel === 'full' ? t('hints.reveal') : t('hints.next', { level: tk(`hints.level.${nextLevel}`, nextLevel) })}
      </button>
      {#if busy}<button class="btn quiet" onclick={() => stopFn?.()}>{t('common.stop')}</button>{/if}
      <button class="btn quiet small" onclick={() => { p.solved = true; persist(); onreveal(); }}>{t('hints.iDidIt')}</button>
    </div>
    {#if !started}<p class="xs muted">{t('hints.whyTry')}</p>{/if}
  {/if}
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
  .refl { margin: var(--s-2) 0 0; color: var(--text-2); }
</style>
