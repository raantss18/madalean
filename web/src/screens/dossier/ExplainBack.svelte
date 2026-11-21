<script lang="ts">
  // « Explique-le avec tes mots » (explain-first / self-explanation): the learner writes first; the tutor names
  // what is right and probes the weakest part with ONE question; the learner can answer and iterate (≤ 3 rounds),
  // then is asked for a cleaner final version. Saved on this device only.
  import type { Dossier } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, i18n } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { assistantTutor } from '../../lib/learn/tutor';
  import { errorText } from '../../lib/ui/errors';
  import Md from '../../components/Md.svelte';

  let { dossier: d, target }: { dossier: Dossier; target: 'statement' | 'proof' } = $props();
  const key = $derived(`explain.${d.id}.${target}`);
  type Turn = { who: 'me' | 'tutor'; text: string };
  let turns = $state<Turn[]>([]);
  let draft = $state('');
  let busy = $state(false);
  let streaming = $state('');
  let err = $state('');
  let stopFn: (() => void) | null = null;
  $effect(() => { turns = loadJSON<Turn[]>(key, []); });
  const rounds = $derived(turns.filter((x) => x.who === 'tutor').length);
  const tutor = assistantTutor((id, fn) => app.listenAssistant(id, fn));

  async function send() {
    if (draft.trim().length < 15 || busy) return;
    const mine = draft.trim();
    turns.push({ who: 'me', text: mine });
    saveJSON(key, turns);
    draft = ''; busy = true; err = ''; streaming = '';
    try {
      const previous = turns.slice(0, -1).map((x) => `${x.who === 'me' ? 'Student' : 'Tutor'}: ${x.text}`);
      const s = await tutor.explainBack(d, mine, { target, lang: i18n.lang, previous });
      stopFn = s.stop;
      s.onToken((tk) => { streaming += tk; });
      const r = await s.done;
      if (r.finish !== 'cancelled') turns.push({ who: 'tutor', text: r.text || streaming });
      saveJSON(key, turns);
    } catch (e) { err = errorText(e); } finally { busy = false; streaming = ''; stopFn = null; }
  }
</script>

<section class="eb" aria-labelledby="eb-h-{target}">
  <h3 id="eb-h-{target}">{t('learn.explainTitle')}</h3>
  <p class="hint">{target === 'statement' ? t('learn.explainStatementPrompt') : t('learn.explainProofPrompt')}</p>
  {#if turns.length}
    <ol class="turns">
      {#each turns as x}
        <li class={x.who}><span class="who xs">{x.who === 'me' ? t('learn.you') : t('learn.tutor')}</span>{#if x.who === 'me'}<p>{x.text}</p>{:else}<Md src={x.text} />{/if}</li>
      {/each}
      {#if busy}<li class="tutor"><span class="who xs">{t('learn.tutor')}</span>{#if streaming}<Md src={streaming} />{:else}<p class="muted small">{t('learn.thinking')}</p>{/if}</li>{/if}
    </ol>
  {/if}
  {#if rounds >= 3}<p class="small cleaner">{t('learn.cleanerVersion')}</p>{/if}
  <label class="sr-only" for="eb-{target}">{t('learn.yourExplanation')}</label>
  <textarea id="eb-{target}" class="input" rows="3" bind:value={draft} placeholder={turns.length ? t('learn.answerPlaceholder') : t('learn.explainPlaceholder')} aria-describedby="eb-n-{target}"></textarea>
  <p class="xs muted" id="eb-n-{target}">{t('learn.explainNote')}</p>
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  <div class="row">
    <button class="btn" onclick={send} disabled={busy || draft.trim().length < 15}>{turns.length ? t('learn.answer') : t('learn.checkExplanation')}</button>
    {#if busy}<button class="btn quiet" onclick={() => stopFn?.()}>{t('common.stop')}</button>{/if}
    {#if turns.length && !busy}<button class="btn quiet small" onclick={() => { turns = []; saveJSON(key, []); }}>{t('learn.restart')}</button>{/if}
  </div>
</section>

<style>
  .eb { border-top: 1px solid var(--line); padding-top: var(--s-3); margin-top: var(--s-3); }
  h3 { margin-bottom: 4px; }
  .turns { list-style: none; padding: 0; margin: 0 0 var(--s-3); display: grid; gap: var(--s-2); }
  .turns li { padding: var(--s-2) var(--s-3); border-radius: var(--r-2); font-size: var(--fs-sm); }
  .turns li p { margin: 0; white-space: pre-wrap; }
  .turns .me { background: var(--accent-soft); margin-left: 12%; }
  .turns .tutor { background: var(--surface-2); margin-right: 12%; }
  .who { display: block; font-weight: 700; color: var(--text-3); }
  .cleaner { background: var(--info-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
</style>
