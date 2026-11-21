<script lang="ts">
  // Step 3 « Preuve »: attempts streaming live, Lean's verdict, the verified proof, the natural-language proof
  // and the tactic-by-tactic explanation, quick actions, lemmas, versions, Learn-mode hint ladder and exercise.
  import type { Dossier, Job, Attempt } from '../../lib/api/types';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime, fmtDuration } from '../../lib/i18n/index.svelte';
  import { prefs, loadJSON, saveJSON } from '../../lib/prefs.svelte';
  import { modelLabel, phaseOf, providerName } from '../../lib/status';
  import CodeEditor from '../../components/CodeEditor.svelte';
  import Md from '../../components/Md.svelte';
  import StreamView from '../../components/StreamView.svelte';
  import StatusMark from '../../components/StatusMark.svelte';
  import Icon from '../../components/Icon.svelte';
  import Versions from './Versions.svelte';
  import HintLadder from './HintLadder.svelte';
  import ExplainBack from './ExplainBack.svelte';
  import Exercise from './Exercise.svelte';
  import ManualEdit from './ManualEdit.svelte';
  import SplitDialog from './SplitDialog.svelte';
  import { follow, run } from './actions';
  import { navigate } from '../../lib/router.svelte';

  let { dossier: d, job }: { dossier: Dossier; job: Job | undefined } = $props();
  const proving = $derived(job && ['proof', 'explanation', 'informal'].includes(job.stage));
  const proofV = $derived(d.proofs[d.cur_proof]);
  const hasProof = $derived(Boolean(d.current.proof) && d.current.proof_is_current);
  const proved = $derived(d.status === 'proved' && hasProof);
  const attempts = $derived<Attempt[]>((job ?? app.lastJob(d.id))?.attempts.filter((a) => a.stage === 'proof') ?? []);
  const lastAttempt = $derived(attempts[attempts.length - 1]);
  const revealKey = $derived(`revealed.${d.id}.${d.cur_proof}`);
  let revealed = $state(false);
  $effect(() => { revealed = loadJSON<boolean>(revealKey, false); });
  const hideProof = $derived(prefs.mode === 'learn' && proved && !revealed);
  function reveal() { revealed = true; saveJSON(revealKey, true); }
  let editProof = $state(false);
  let editInformal = $state(false);
  let editExpl = $state(false);
  let splitting = $state(false);
  let textTab = $state<'informal' | 'explanation'>('informal');
  const extra = $derived((d['extra'] as Record<string, unknown> | undefined) ?? {});
  const cond = $derived((extra['conditional_proof'] ?? d['conditional_proof']) as { verdict?: string; admitted?: string[]; code?: string } | undefined);
  const recheck = $derived(((extra['recheck'] ?? d['recheck']) as { state?: string } | undefined)?.state ?? '');
  const children = $derived(Object.values(app.m.dossiers).filter((c) => c.parent_id === d.id).sort((a, b) => a.created - b.created));
  const explV = $derived(d.explanations[d.cur_explanation]);
  const informalV = $derived(d.informal_proofs.find((v) => v.parent === d.cur_proof) ?? d.informal_proofs[d.informal_proofs.length - 1]);

  const quick = $derived([
    { label: t('quick.simpler'), run: () => follow(d.id, t('quick.simplerReq'), 'proof') },
    { label: t('quick.other'), run: () => follow(d.id, t('quick.otherReq'), 'proof') },
    { label: t('quick.detail'), run: () => follow(d.id, t('quick.detailReq'), 'explanation') },
  ]);
</script>

<div class="proof-step stack">
  {#if proving && job}
    <section class="panel live" aria-labelledby="live-h">
      <div class="row"><h2 id="live-h">{job.stage === 'proof' ? t('proof.searching') : tk(`stage.${job.stage}`, '')}</h2>
        {#if job.waiting}<span class="chip running">{tk(`waiting.${job.waiting}`, '')}</span>{/if}
      </div>
      {#if job.stage === 'proof'}
        {#if job.tournament && 'names' in job.tournament && job.tournament.names.length}
          <p class="small" role="status">{t('proof.tournament', { k: job.tournament.round, models: job.tournament.names.join(', ') })}</p>
        {/if}
        <ol class="attempts">
          {#each attempts as a (a.index)}
            <li class={a.status}>
              <details open={a === lastAttempt && a.status === 'generating'}>
                <summary>
                  <StatusMark phase={a.status === 'accepted' ? 'proved' : a.status === 'rejected' || a.status === 'error' ? 'failed' : a.status === 'cancelled' ? 'stopped' : 'running'} />
                  <span>{t('proof.attempt', { n: a.index + 1 })} · {tk(`attempt.kind.${a.kind}`, a.kind)} · {tk(`attempt.status.${a.status}`, a.status)}</span>
                  {#if a.model}<span class="chip {modelLabel(a.model).local ? 'local' : 'online'}">{modelLabel(a.model).name}</span>{/if}
                  {#if a.gen_seconds}<span class="xs muted">{fmtDuration(a.gen_seconds + a.compile_seconds)}</span>{/if}
                </summary>
                {#if a.status === 'generating'}<StreamView jobId={job.id} stage="proof" attempt={a.index} maxHeight="360px" />
                {:else}
                  {#if a.summary}<p class="small">{a.summary}</p>{/if}
                  {#if a.errors_text}<pre class="errs">{a.errors_text}</pre>{/if}
                {/if}
              </details>
            </li>
          {:else}
            <li><StreamView jobId={job.id} stage="proof" maxHeight="320px" /></li>
          {/each}
        </ol>
      {:else}
        <StreamView jobId={job.id} stage={job.stage} maxHeight="320px" />
      {/if}
    </section>
  {/if}

  {#if cond?.verdict === 'proved_modulo'}
    <section class="panel conditional" role="status" aria-labelledby="cond-h">
      <h2 id="cond-h"><Icon name="warn" size={16} /> {t('plan.conditional')}</h2>
      <p class="small">{t('plan.conditionalText', { n: cond.admitted?.length ?? 0, names: (cond.admitted ?? []).join(', ') })}</p>
      {#if cond.code}<details><summary class="small">{t('plan.conditionalCode')}</summary><pre class="errs neutral">{cond.code}</pre></details>{/if}
      <a class="btn small" href="/d/{encodeURIComponent(d.id)}/plan">{t('plan.openPlan')}</a>
    </section>
  {/if}
  {#if hasProof}
    {#if recheck === 'pending' || recheck === 'regressed'}
      <p class="recheck {recheck}" role="status"><Icon name="warn" size={14} /> {tk(`recheck.${recheck}.long`, recheck)}</p>
    {/if}
    <section class="panel result" class:proved aria-labelledby="res-h">
      <div class="row">
        <h2 id="res-h"><StatusMark phase={proved ? 'proved' : phaseOf(d.status)} size={16} /> {proved ? t('proof.verified') : t('proof.notVerified')}</h2>
        <span class="spacer"></span>
        <Versions dossier={d} kind="proof" busy={Boolean(job)} />
      </div>
      {#if proofV && proved}
        <p class="stamp small">
          {t('proof.stamp', { lean: proofV.meta.lean ?? '?', mathlib: proofV.meta.mathlib ?? '?' })}
          {#if proofV.meta.seconds} · {fmtDuration(proofV.meta.seconds)}{/if}
          {#if proofV.meta.attempts} · {t('proof.attempts', { n: proofV.meta.attempts })}{/if}
          · {fmtTime(proofV.t)}
          {#if proofV.model}· <span class="chip {modelLabel(proofV.model).local ? 'local' : 'online'}" title={providerName(modelLabel(proofV.model).provider)}>{modelLabel(proofV.model).name}</span>{/if}
          {#if proofV.meta.axioms}<br /><span class="xs">{t('proof.axioms', { a: proofV.meta.axioms.join(', ') || '—' })}</span>{/if}
        </p>
      {/if}

      {#if hideProof}
        <HintLadder dossier={d} onreveal={reveal} />
        <p class="xs"><button class="linkish" onclick={reveal}>{t('hints.skipToProof')}</button></p>
      {:else}
        <h3>{t('proof.lean')}</h3>
        <CodeEditor value={d.current.proof} language="lean" readonly label={t('proof.lean')} gloss={prefs.mode === 'learn'} workspace={d.workspace} minLines={6} />
        <div class="row tools">
          <button class="btn small" aria-expanded={editProof} onclick={() => (editProof = !editProof)}><Icon name="edit" size={14} />{t('proof.editByHand')}</button>
        </div>
        <ManualEdit dossier={d} kind="proof" server={d.current.proof} bind:open={editProof} />
      {/if}
    </section>

    {#if !hideProof}
      <section class="panel texts" aria-labelledby="txt-h">
        <h2 id="txt-h" class="sr-only">{t('proof.texts')}</h2>
        <div class="seg" role="radiogroup" aria-label={t('proof.texts')}>
          <label><input type="radio" name="txt-{d.id}" checked={textTab === 'informal'} onchange={() => (textTab = 'informal')} />{t('proof.informal')}</label>
          <label><input type="radio" name="txt-{d.id}" checked={textTab === 'explanation'} onchange={() => (textTab = 'explanation')} />{t('proof.explanation')}</label>
        </div>
        {#if textTab === 'informal'}
          {#if d.current.informal_proof}
            <div class="prose"><Md src={d.current.informal_proof} /></div>
            {#if informalV?.model}<p class="xs muted">{t('common.by', { model: modelLabel(informalV.model).name })} · {t('proof.leanIsTruth')}</p>{/if}
            <button class="btn small" aria-expanded={editInformal} onclick={() => (editInformal = !editInformal)}><Icon name="edit" size={14} />{t('common.edit')}</button>
            <ManualEdit dossier={d} kind="informal" server={d.current.informal_proof} bind:open={editInformal} />
          {:else}
            <p class="muted small">{t('proof.noInformal')}</p>
            {#if !job}<button class="btn small" onclick={() => run(d.id, ['informal'])}>{t('proof.makeInformal')}</button>{/if}
          {/if}
        {:else}
          {#if d.current.explanation}
            <div class="prose"><Md src={d.current.explanation} /></div>
            <div class="row">
              {#if explV?.model}<span class="xs muted">{t('common.by', { model: modelLabel(explV.model).name })}</span>{/if}
              <span class="spacer"></span>
              <Versions dossier={d} kind="explanation" busy={Boolean(job)} />
              <button class="btn small" aria-expanded={editExpl} onclick={() => (editExpl = !editExpl)}><Icon name="edit" size={14} />{t('common.edit')}</button>
            </div>
            <ManualEdit dossier={d} kind="explanation" server={d.current.explanation} bind:open={editExpl} />
          {:else}
            <p class="muted small">{t('proof.noExplanation')}</p>
            {#if !job}<button class="btn small" onclick={() => run(d.id, ['explanation'])}>{t('proof.makeExplanation')}</button>{/if}
          {/if}
        {/if}
      </section>
    {/if}

    {#if !job}
      <section class="quick" aria-label={t('quick.title')}>
        {#each quick as q}<button class="btn" onclick={q.run}>{q.label}</button>{/each}
        <button class="btn" onclick={() => (splitting = true)}><Icon name="split" size={16} />{t('dossier.split')}</button>
      </section>
    {/if}

    {#if prefs.mode === 'learn' && proved && !hideProof}
      <section class="panel" aria-label={t('learn.title')}>
        <ExplainBack dossier={d} target="proof" />
        <Exercise dossier={d} />
      </section>
    {/if}
  {:else if !proving}
    <section class="panel empty-proof">
      {#if d.status === 'failed' || (app.lastJob(d.id)?.state === 'failed' && d.statements.length)}
        <h2>{t('proof.failedTitle')}</h2>
        <p>{tk(`joberr.${app.lastJob(d.id)?.error ?? ''}`, t('proof.failedText'))}</p>
        <div class="row">
          <button class="btn primary" onclick={() => run(d.id, ['proof', 'explanation'])}>{t('proof.retry')}</button>
          <a class="btn" href="/d/{encodeURIComponent(d.id)}/plan"><Icon name="split" size={16} />{t('plan.split')}</a>
          <button class="btn" onclick={() => navigate(`/d/${encodeURIComponent(d.id)}/lean`)}>{t('proof.reviewStatement')}</button>
        </div>
        <p class="hint">{t('proof.failedHint')}</p>
      {:else if d.statements.length}
        <h2>{t('proof.notStarted')}</h2>
        <p>{t('proof.notStartedText')}</p>
        <button class="btn primary" onclick={() => run(d.id, ['proof', 'explanation'])}>{t('lean.prove')}</button>
      {:else}
        <h2>{t('proof.needStatement')}</h2>
        <a class="btn primary" href="/d/{encodeURIComponent(d.id)}/lean">{t('proof.toStatement')}</a>
      {/if}
    </section>
  {/if}

  {#if children.length}
    <section class="panel" aria-labelledby="lem-h">
      <h2 id="lem-h">{t('proof.lemmas', { done: children.filter((c) => c.proved).length, n: children.length })}</h2>
      {#if d.retry_parent}<p class="hint">{t('proof.retryParent')}</p>{/if}
      <ul class="tree">
        {#each children as c (c.id)}
          {@const cj = app.activeJob(c.id)}
          <li><a href="/d/{encodeURIComponent(c.id)}"><StatusMark phase={phaseOf(c.status, cj)} showLabel /><span>{c.title || c.theorem}</span>{#if cj}<span class="xs muted">{tk(`stage.${cj.stage}`, '')}{#if cj.waiting} · {tk(`waiting.${cj.waiting}`, '')}{/if}</span>{/if}</a></li>
        {/each}
      </ul>
    </section>
  {/if}
</div>
<SplitDialog dossier={d} bind:open={splitting} />

<style>
  h2 { margin: 0; display: flex; align-items: center; gap: 8px; }
  h3 { margin: var(--s-3) 0 var(--s-2); }
  .attempts { list-style: none; padding: 0; margin: var(--s-3) 0 0; display: grid; gap: var(--s-2); }
  .attempts summary { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-height: var(--touch); cursor: pointer; font-size: var(--fs-sm); }
  .errs { font: 0.75rem/1.45 var(--font-mono); white-space: pre-wrap; background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-1); max-height: 180px; overflow: auto; }
  .conditional { border: 2px dashed var(--running-fill); background: var(--running-soft); }
  .conditional h2 { color: var(--running); }
  .errs.neutral { background: var(--surface-2); }
  .recheck { margin: 0; padding: var(--s-2) var(--s-3); border-radius: var(--r-2); background: var(--running-soft); color: var(--running); font-weight: 600; font-size: var(--fs-sm); display: flex; gap: 6px; align-items: center; }
  .recheck.regressed { background: var(--failed-soft); color: var(--failed); }
  .result.proved { border-color: color-mix(in srgb, var(--proved) 50%, var(--line)); border-left: 4px solid var(--proved); }
  .stamp { color: var(--text-2); margin: var(--s-2) 0; }
  .tools { margin-top: var(--s-2); }
  .prose { max-width: var(--measure); margin: var(--s-3) 0; font-family: var(--font-serif); font-size: 1.0625rem; line-height: 1.65; }
  .quick { display: flex; flex-wrap: wrap; gap: var(--s-2); }
  .tree { list-style: none; padding: 0; margin: var(--s-2) 0 0; }
  .tree a { display: flex; align-items: center; gap: var(--s-3); min-height: var(--touch); color: var(--text); text-decoration: none; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  .tree a:hover { background: var(--surface-2); }
  .linkish { background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; font: inherit; min-height: 24px; }
</style>
