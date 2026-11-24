<script lang="ts">
  // D64/D66: the question asked before anything is translated (meaning) or proved (statement). Nothing here may let
  // « Lean comprend le code » be read as « fidèle » or « prouvé ».
  import type { Dossier, Gate } from '../../lib/api/types';
  import { flow } from '../../lib/api/flow';
  import { t, tk, fmtTime } from '../../lib/i18n/index.svelte';
  import { modelLabel } from '../../lib/status';
  import { app } from '../../lib/store/app.svelte';
  import { toast } from '../../lib/ui/toasts.svelte';
  import { enterSubmit } from '../../lib/ui/enter';
  import { keepDraft } from '../../lib/ui/drafts.svelte';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import EnterHint from '../../components/EnterHint.svelte';
  import { applyAnswer, flowError } from './flowtext';
  import type { ReportTarget } from '../../lib/api/flow';

  let { dossier: d, gate, onreport, onabout }: {
    dossier: Dossier; gate: Gate; onreport?: (target: ReportTarget, ref?: number) => void; onabout?: (stage: 'auto' | 'statement') => void;
  } = $props();
  const m = $derived(gate.meaning ?? {});
  const s = $derived(gate.statement ?? {});
  const cands = $derived(s.candidates ?? []);
  const pending = $derived(gate.state === 'pending');
  let picked = $state<number | null>(null);
  const chosen = $derived(picked ?? s.chosen ?? cands[0]?.version ?? 0);
  let asking = $state<'' | 'edit' | 'reject'>('');
  let text = $state('');
  let busy = $state('');
  const uid = $derived(`gate-${d.id}-${gate.id}`);
  keepDraft(() => `gate.${d.id}.${gate.id}`, () => text, (v) => { text = v; if (v && !asking) asking = 'edit'; });

  async function act(action: 'approve' | 'edit' | 'reject') {
    if (busy || (action === 'edit' && !text.trim())) return;
    busy = action;
    try {
      const r = await flow.gate(d.id, { gate_id: gate.id, action, ...(action !== 'approve' && text.trim() ? { text: text.trim() } : {}),
        ...(gate.kind === 'statement' ? { candidate: chosen } : {}) });
      text = ''; asking = '';
      if (action === 'approve') toast('ok', t('gate.approved'));
      await applyAnswer(d.id, r);
    } catch (e) { await flowError(e, d.id); } finally { busy = ''; }
  }
  const src = (x: unknown) => (typeof x === 'string' ? x : (x as { title?: string } | undefined)?.title ?? '');
  const okOf = (v: number) => d.statements[v]?.ok ?? true;
</script>

{#snippet meaning()}
  {#if m.known_status && m.known_status !== 'unknown'}
    <div class="status {m.known_status}">
      <p class="sthead"><Icon name={m.known_status === 'known' ? 'book' : 'warn'} size={16} /> <strong>{t(`gate.status.${m.known_status}`)}</strong>
        <span class="chip {m.status_confidence === 'cited' ? '' : 'running'}">{m.status_confidence === 'cited' ? t('gate.cited') : t('gate.modelOnly')}</span></p>
      {#each m.status_sources ?? [] as q}
        <figure><blockquote><Md src={q.quote} /></blockquote>
          <figcaption class="xs">{#if /^https?:/.test(q.url)}<a href={q.url} target="_blank" rel="noopener noreferrer">{q.title || q.url}</a>{:else}{q.title}{/if}</figcaption></figure>
      {/each}
    </div>
  {/if}
  {#if m.restated}<h4>{t('gate.restated')}</h4><div class="said"><Md src={m.restated} /></div>{/if}
  <dl>
    {#if m.objects?.length}<div><dt>{t('gate.objects')}</dt><dd><ul>{#each m.objects as o}<li><strong>{o.name}</strong> : <Md src={o.meaning} cls="inl" /></li>{/each}</ul></dd></div>{/if}
    {#if m.hypotheses}<div><dt>{t('gate.hypotheses')}</dt><dd>{#if m.hypotheses.length}<ul>{#each m.hypotheses as h}<li><Md src={h} cls="inl" /></li>{/each}</ul>{:else}{t('gate.noHypotheses')}{/if}</dd></div>{/if}
    {#if m.claim}<div><dt>{t('gate.claim')}</dt><dd><Md src={m.claim} cls="inl" /></dd></div>{/if}
  </dl>
  {#if m.known_results?.length}
    <h4>{t('gate.known')}</h4><p class="hint">{t('gate.knownHint')}</p>
    <ul class="known">{#each m.known_results as k (k.id)}
      <li><strong>{k.title}</strong>{#if k.statement}{' — '}<Md src={k.statement} cls="inl" />{/if}
        {#if src(k.source)}<span class="xs muted">({src(k.source)})</span>{/if}
        {#if k.dossier_id}<a class="xs" href="/d/{encodeURIComponent(k.dossier_id)}">{t('flow.childGo')}{#if app.m.dossiers[k.dossier_id]}<span class="sr-only"> : {k.title}</span>{/if}</a>{/if}</li>
    {/each}</ul>
  {/if}
  {#if m.questions?.length}<h4>{t('gate.questions')}</h4><ul>{#each m.questions as q}<li><Md src={q} cls="inl" /></li>{/each}</ul>{/if}
{/snippet}

{#snippet statement()}
  <p class="note small"><Icon name="info" size={14} /> {t('gate.statementNote')}</p>
  {#if s.agreement}<p class="small agree {s.agreement}">{#if s.agreement === 'different'}<Icon name="warn" size={14} /> {/if}{t(`gate.agreement.${s.agreement}`)}</p>{/if}
  <div class="cands" class:two={cands.length > 1}>
    {#each cands as c (c.version)}
      <article class="cand" class:on={chosen === c.version && cands.length > 1} aria-label={t('gate.candidate', { n: c.version + 1 })}>
        <div class="row">
          <strong>{t('gate.candidate', { n: c.version + 1 })}</strong>
          {#if c.model}<span class="chip {modelLabel(c.model).local ? 'local' : 'online'}">{modelLabel(c.model).name}</span>{/if}
          <span class="chip {okOf(c.version) ? '' : 'failed'}">{okOf(c.version) ? t('gate.understands') : t('gate.doesNot')}</span>
          <span class="chip {c.verdict === 'false' ? 'failed' : c.verdict === 'doubtful' ? 'running' : ''}">{tk(`gate.verdict.${c.verdict || 'unknown'}`, t('gate.verdict.unknown'))}</span>
          <span class="chip">{t('gate.notProved')}</span>
        </div>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex (a scrollable region must be reachable by keyboard) -->
        <pre class="code" tabindex="0">{c.code}</pre>
        <h4>{t('gate.back')} <span class="xs muted">({t('gate.backHint')})</span></h4>
        {#if c.back_translation}<div class="said"><Md src={c.back_translation} /></div>{:else}<p class="small muted">{t('gate.noBack')}</p>{/if}
        {#if c.objects_missing?.length}<p class="small miss"><Icon name="warn" size={14} /> {t('gate.missing', { list: c.objects_missing.join(', ') })}</p>{/if}
        {#if c.reasons?.length}<ul class="small">{#each c.reasons as r}<li><Md src={r} cls="inl" /></li>{/each}</ul>{/if}
        {#if pending && cands.length > 1}<label class="pick"><input type="radio" name="{uid}-c" checked={chosen === c.version} onchange={() => (picked = c.version)} />{t('gate.choose')}</label>{/if}
      </article>
    {/each}
  </div>
{/snippet}

<section class="gate {gate.kind} {gate.state}" id={pending ? `gate-${d.id}` : undefined} tabindex="-1" aria-labelledby="{uid}-h">
  <div class="row head">
    <h3 id="{uid}-h"><Icon name={pending ? 'info' : gate.state === 'approved' ? 'check' : 'x'} size={18} /> {t(gate.kind === 'meaning' ? 'gate.meaningTitle' : 'gate.statementTitle')}</h3>
    <span class="chip {pending ? 'running' : gate.state === 'rejected' ? 'failed' : ''}">{t(`gate.state.${gate.state}`)}</span>
    <span class="xs muted">{fmtTime(gate.t)}</span>
  </div>
  {#if pending}
    {#if gate.kind === 'meaning'}{@render meaning()}<p class="hint">{t('gate.meaningNote')}</p>{:else}{@render statement()}{/if}
    <div class="row acts">
      <button class="btn primary" disabled={Boolean(busy)} onclick={() => act('approve')}><Icon name="check" size={16} />{t('gate.approve')}</button>
      <button class="btn" aria-expanded={asking === 'edit'} disabled={Boolean(busy)} onclick={() => (asking = asking === 'edit' ? '' : 'edit')}><Icon name="edit" size={16} />{t('gate.correct')}</button>
      <button class="btn" aria-expanded={asking === 'reject'} disabled={Boolean(busy)} onclick={() => (asking = asking === 'reject' ? '' : 'reject')}><Icon name="x" size={16} />{t('gate.reject')}</button>
      <span class="spacer"></span>
      {#if onabout}<button class="btn small quiet" onclick={() => onabout?.(gate.kind === 'statement' ? 'statement' : 'auto')}>{t('flow.about')}</button>{/if}
      {#if onreport}<button class="btn small quiet" onclick={() => onreport?.(gate.kind, gate.kind === 'statement' ? chosen : undefined)}><Icon name="warn" size={14} />{t('report.button')}</button>{/if}
    </div>
    {#if asking}
      <div class="field">
        <label for="{uid}-t">{t(asking === 'edit' ? 'gate.correctLabel' : 'gate.rejectLabel')}</label>
        <textarea id="{uid}-t" class="input" rows="2" bind:value={text} use:enterSubmit={() => void act(asking || 'edit')} aria-describedby="{uid}-e"></textarea>
        <EnterHint id="{uid}-e" />
        <div class="row"><button class="btn {asking === 'reject' ? 'danger' : 'primary'}" disabled={Boolean(busy) || (asking === 'edit' && !text.trim())} onclick={() => act(asking || 'edit')}>{t(asking === 'edit' ? 'gate.sendCorrect' : 'gate.sendReject')}</button></div>
      </div>
    {/if}
  {:else}
    <details><summary class="small">{t('thread.details')}</summary>{#if gate.kind === 'meaning'}{@render meaning()}{:else}{@render statement()}{/if}</details>
  {/if}
</section>

<style>
  .gate { border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--s-4); background: var(--surface); scroll-margin: 180px 0 160px; container: gate / inline-size; }
  .gate.pending { border: 2px solid var(--running); }
  .gate:focus-visible { outline: 2px solid var(--focus); }
  h3 { margin: 0; display: flex; gap: 8px; align-items: center; font-size: 1.0625rem; font-family: var(--font-serif); }
  h4 { margin: var(--s-3) 0 4px; font-size: var(--fs-sm); color: var(--text-2); }
  .status { margin-top: var(--s-3); border-left: 4px solid var(--line-strong); background: var(--surface-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); }
  .status.open, .status.false, .status.unclear { border-left-color: var(--running); background: var(--running-soft); }
  .status.false { border-left-color: var(--failed); background: var(--failed-soft); }
  .sthead { margin: 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  figure { margin: var(--s-2) 0 0; }
  blockquote { margin: 0; padding-left: var(--s-3); border-left: 2px solid var(--line-strong); font-family: var(--font-serif); font-style: italic; }
  figcaption { margin-top: 2px; }
  .said { font-family: var(--font-serif); font-size: 1.0625rem; line-height: 1.55; }
  .said :global(p), .status :global(.md p) { margin: 0; }
  dl { margin: var(--s-2) 0 0; display: grid; gap: 4px; }
  dl > div { display: grid; grid-template-columns: 7.5rem minmax(0, 1fr); gap: var(--s-2); }
  dt { font-weight: 600; font-size: var(--fs-sm); color: var(--text-2); }
  dd { margin: 0; }
  ul { margin: 0; padding-left: 1.2em; }
  .gate :global(.md.inl), .gate :global(.md.inl p) { display: inline; }
  .known li { margin-bottom: 4px; }
  .note { margin: var(--s-3) 0 var(--s-2); padding: var(--s-2) var(--s-3); border-radius: var(--r-2); background: var(--info-soft); }
  .agree { margin: 0 0 var(--s-2); }
  .agree.different, .miss { color: var(--running); font-weight: 600; }
  .cands { display: grid; gap: var(--s-3); }
  .cand { border: 1px solid var(--line); border-radius: var(--r-2); padding: var(--s-3); min-width: 0; }
  .cand.on { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
  .code { margin: var(--s-2) 0 0; background: var(--surface-2); border-radius: var(--r-2); padding: var(--s-2) var(--s-3); font: 0.8125rem/1.5 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 260px; overflow: auto; }
  .pick { display: flex; gap: 8px; align-items: center; min-height: var(--touch); font-weight: 600; cursor: pointer; }
  .acts { margin-top: var(--s-4); }
  .field { margin: var(--s-3) 0 0; }
  textarea.input { min-height: 64px; }
  @container gate (min-width: 640px) { .cands.two { grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); } }
  @media (max-width: 767px) { .gate { padding: var(--s-3); } dl > div { grid-template-columns: minmax(0, 1fr); gap: 0; } .acts .btn { flex: 1 1 auto; } }
</style>
