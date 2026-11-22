<script lang="ts">
  import EnterHint from '../../components/EnterHint.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  // « Explique-le avec tes mots » — POST /dossiers/{id}/explain-back: the learner writes first; the server grades the
  // explanation against criteria taken from the Lean-verified proof (or the Lean statement), names the gap and asks
  // ONE question. Up to three rounds, then a cleaner final version is asked for.
  import type { Dossier } from '../../lib/api/types';
  import type { ExplainAnswer } from '../../lib/api/research';
  import { t } from '../../lib/i18n/index.svelte';
  import { loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { keepDraft } from '../../lib/ui/drafts.svelte';
  import { askExplainBack, learnError } from '../../lib/learn/tutor';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';

  let { dossier: d, target }: { dossier: Dossier; target: 'statement' | 'proof' } = $props();
  const key = $derived(`explain.${d.id}.${target}`);
  type Turn = { who: 'me' | 'tutor'; text: string; answer?: ExplainAnswer };
  let turns = $state<Turn[]>([]);
  let draft = $state('');
  let busy = $state(false);
  let err = $state('');
  $effect(() => { turns = loadJSON<Turn[]>(key, []); });
  keepDraft(() => key, () => draft, (v) => (draft = v));       // unsent explanation kept until sent (S-AP)
  const rounds = $derived(turns.filter((x) => x.who === 'tutor').length);

  async function send() {
    if (draft.trim().length < 15 || busy) return;
    const mine = draft.trim();
    const previous = turns.map((x) => `${x.who === 'me' ? 'Student' : 'Tutor'}: ${x.text}`);
    turns = [...turns, { who: 'me', text: mine }];
    saveJSON(key, turns);
    draft = ''; busy = true; err = '';
    try {
      const a = await askExplainBack(d.id, target, mine, previous);
      turns = [...turns, { who: 'tutor', text: a.text || [a.gap, a.question].filter(Boolean).join('\n\n'), answer: a }];
      saveJSON(key, turns);
    } catch (e) { err = learnError(e); } finally { busy = false; }
  }
</script>

<section class="eb" aria-labelledby="eb-h-{target}">
  <h3 id="eb-h-{target}">{t('learn.explainTitle')}</h3>
  <p class="hint">{target === 'statement' ? t('learn.explainStatementPrompt') : t('learn.explainProofPrompt')}</p>
  {#if turns.length}
    <ol class="turns">
      {#each turns as x}
        <li class={x.who}>
          <span class="who xs">{x.who === 'me' ? t('learn.you') : t('learn.tutor')}</span>
          {#if x.who === 'me'}<p>{x.text}</p>{:else}
            {#if x.answer?.total}
              <p class="score xs">{t('learn.criteriaMet', { met: x.answer.met, total: x.answer.total })}</p>
              <ul class="crit">
                {#each x.answer.criteria as c}<li class:met={c.met}><Icon name={c.met ? 'check' : 'x'} size={14} label={c.met ? t('learn.met') : t('learn.notMet')} /> <Md inline src={c.criterion} /></li>{/each}
              </ul>
            {/if}
            <Md src={x.text} />
          {/if}
        </li>
      {/each}
      {#if busy}<li class="tutor"><span class="who xs">{t('learn.tutor')}</span><p class="muted small">{t('learn.thinking')}</p></li>{/if}
    </ol>
  {/if}
  {#if rounds >= 3}<p class="small cleaner">{t('learn.cleanerVersion')}</p>{/if}
  <label class="sr-only" for="eb-{target}">{t('learn.yourExplanation')}</label>
  <textarea id="eb-{target}" class="input" rows="3" bind:value={draft} use:enterSubmit={() => void send()} placeholder={turns.length ? t('learn.answerPlaceholder') : t('learn.explainPlaceholder')} aria-describedby="eb-n-{target} eb-e-{target}"></textarea>
  <EnterHint id="eb-e-{target}" />
  <p class="xs muted" id="eb-n-{target}">{t('learn.explainNote')}</p>
  {#if err}<p class="error-text" role="alert">{err}</p>{/if}
  <div class="row">
    <button class="btn" onclick={send} disabled={busy || draft.trim().length < 15}>{turns.length ? t('learn.answer') : t('learn.checkExplanation')}</button>
    {#if turns.length && !busy}<button class="btn quiet small" onclick={() => { turns = []; saveJSON(key, []); }}>{t('learn.restart')}</button>{/if}
  </div>
</section>

<style>
  .eb { border-top: 1px solid var(--line); padding-top: var(--s-3); margin-top: var(--s-3); }
  h3 { margin-bottom: 4px; }
  .turns { list-style: none; padding: 0; margin: 0 0 var(--s-3); display: grid; gap: var(--s-2); }
  .turns > li { padding: var(--s-2) var(--s-3); border-radius: var(--r-2); font-size: var(--fs-sm); }
  .turns li p { margin: 0; white-space: pre-wrap; }
  .turns .me { background: var(--accent-soft); margin-left: 12%; }
  .turns .tutor { background: var(--surface-2); margin-right: 12%; }
  .who { display: block; font-weight: 700; color: var(--text-3); }
  .score { color: var(--text-2); font-weight: 600; margin-bottom: 4px !important; }
  .crit { list-style: none; padding: 0; margin: 0 0 var(--s-2); display: grid; gap: 2px; }
  .crit li { display: flex; gap: 6px; align-items: baseline; color: var(--failed); }
  .crit li.met { color: var(--proved); }
  .cleaner { background: var(--info-soft); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
</style>
