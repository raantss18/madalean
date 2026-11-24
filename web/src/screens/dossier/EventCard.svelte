<script lang="ts">
  // One event of the thread. The long contents (Lean proof, explanations) stay in the pane; here: what happened, who,
  // when, the statement code folded, and the ways on (see it, discuss it, « Mal compris »).
  import type { Dossier, DossierEvent, FollowStage, Job } from '../../lib/api/types';
  import type { ReportTarget } from '../../lib/api/flow';
  import type { Part } from '../../lib/flow';
  import { t, fmtTime } from '../../lib/i18n/index.svelte';
  import { modelLabel } from '../../lib/status';
  import Md from '../../components/Md.svelte';
  import Icon from '../../components/Icon.svelte';
  import StatementVerdict from './StatementVerdict.svelte';

  let { dossier: d, ev, index, job, latest = false, onreport, onabout }: {
    dossier: Dossier; ev: DossierEvent; index: number; job: Job | undefined; latest?: boolean;
    onreport: (target: ReportTarget, ref?: number) => void; onabout: (stage: FollowStage) => void;
  } = $props();
  const first = $derived(ev.text.split('\n')[0] ?? '');
  // the server's older wording: « Lean accepte l'énoncé » reads as a verdict on the meaning
  const plain = (x: string) => x.replace(/Lean accepte l['’]énoncé/, 'Lean comprend le code').replace(/Lean accepts the statement/, 'Lean understands the code');
  const rest = $derived(ev.text.split('\n').slice(1).join('\n').trim());
  const PART: Partial<Record<string, Part>> = { understood: 'enonce', statement: 'lean', notes: 'lean', check: 'lean', literature: 'litterature', proof: 'preuve', explanation: 'preuve', informal: 'preuve', certificate: 'calculs' };
  const part = $derived(PART[ev.kind]);
  const about = $derived<FollowStage>(part === 'lean' || part === 'enonce' ? 'statement' : ev.kind === 'explanation' || ev.kind === 'informal' ? 'explanation' : part === 'preuve' ? 'proof' : 'auto');
  const target = $derived<ReportTarget>(ev.kind === 'understood' ? 'meaning' : part === 'lean' ? 'statement' : part === 'preuve' ? 'proof' : 'event');
  const who = $derived(ev.kind === 'certificate' ? 'Sage + Lean' : ev.kind === 'literature' ? t('lit.title') : ev.model ? modelLabel(ev.model).name : ev.kind === 'info' || ev.kind === 'error' || ev.kind === 'report' ? 'Madalean' : 'Lean');
  const version = $derived(ev.kind === 'statement' && ev.ref !== null ? d.statements[ev.ref] : undefined);
  const gated = $derived(d.gate?.kind === 'meaning' && d.gate.state === 'pending');
</script>

<article class="card {ev.kind}">
  <p class="meta xs">{#if ev.kind === 'error'}<Icon name="warn" size={12} />{/if}<span>{who}</span><span>· {fmtTime(ev.t)}</span>
    {#if version}<span class="chip {version.ok ? '' : 'failed'}">{version.ok ? t('gate.understands') : t('gate.doesNot')}</span>{#if d.status !== 'proved' || ev.ref !== d.cur_statement}<span class="chip">{t('gate.notProved')}</span>{/if}{/if}
    {#if ev.kind === 'proof' && ev.ref !== null && d.proofs[ev.ref]?.ok}<span class="chip proved"><Icon name="check" size={12} />{t('proof.verified')}</span>{/if}
    <span class="acts">
      {#if part}<a class="lk" href="/d/{encodeURIComponent(d.id)}/{part}">{t(`flow.seeIn.${part}` as 'flow.seeIn.lean')}</a>{/if}
      <button class="lk" onclick={() => onabout(about)}>{t('flow.about')}<span class="sr-only"> : {first.slice(0, 60)}</span></button>
      <button class="lk" onclick={() => onreport(target, target === 'event' ? index : ev.ref ?? undefined)}>{t('report.button')}<span class="sr-only"> : {first.slice(0, 60)}</span></button>
    </span>
  </p>
  <p class="first">{plain(first)}</p>
  {#if version}<details><summary class="xs">{t('flow.leanCode', { n: (ev.ref ?? 0) + 1 })}</summary><pre>{version.code}</pre></details>{/if}
  {#if ev.kind === 'check'}
    <StatementVerdict id={d.id} params={ev.params} busy={Boolean(job)} actions={latest && ev.ref === d.cur_statement && !d.proofs.some((p) => p.parent === d.cur_statement && p.ok)} />
  {:else if rest}
    {#if ev.kind === 'understood' && latest && !gated}<div class="said"><Md src={rest} /></div>
    {:else}<details><summary class="xs">{t('thread.details')}</summary><Md src={rest} /></details>{/if}
  {/if}
</article>

<style>
  .card { padding: 2px var(--s-3) var(--s-2); border-radius: var(--r-2); background: var(--surface); border: 1px solid var(--line); }
  .card p { margin: 0; }
  .meta { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; color: var(--text-3); font-weight: 600; }
  .first { white-space: pre-wrap; overflow-wrap: anywhere; }
  .card.error { background: var(--failed-soft); }
  .card.proof, .card.certificate { border-left: 3px solid var(--proved); }
  .card.statement, .card.check { border-left: 3px solid var(--accent); }
  .card.info { background: transparent; border-style: dashed; color: var(--text-2); }
  .said { font-family: var(--font-serif); border-left: 3px solid var(--line-strong); padding-left: var(--s-3); margin-top: 4px; }
  .said :global(p) { margin: 0; }
  summary { cursor: pointer; color: var(--text-2); }
  pre { margin: 4px 0; background: var(--surface-2); padding: var(--s-2); border-radius: var(--r-1); font: 0.8125rem/1.5 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; }
  .acts { margin-left: auto; display: flex; flex-wrap: wrap; gap: 0 var(--s-3); }
  .lk { background: none; border: 0; padding: 0; font: 400 var(--fs-xs)/1 var(--font-ui); color: var(--accent); text-decoration: underline; cursor: pointer; min-height: 28px; display: inline-flex; align-items: center; }
  @media (pointer: coarse) { .lk { min-height: var(--touch); } }
</style>
