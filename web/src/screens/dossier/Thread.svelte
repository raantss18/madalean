<script lang="ts">
  // D66: the dossier's thread — everything that happened, in order, at the centre of the screen: grouped by request,
  // then by phase; attempts are folded (the active one is open and streams in place); sub-dossiers and questions appear
  // where they happened. Long threads show the last items first; the phases off screen are not laid out.
  import type { Dossier, FollowStage, Job } from '../../lib/api/types';
  import type { ReportTarget } from '../../lib/api/flow';
  import { FILTERS, buildThread, threadItems, pendingGate, troubleOf, attemptNumber, type Filter, type Item, type LocalReport, type Now } from '../../lib/flow';
  import { app } from '../../lib/store/app.svelte';
  import { t, tk, fmtTime, fmtDuration } from '../../lib/i18n/index.svelte';
  import { modelLabel, sideStages } from '../../lib/status';
  import { tick, untrack } from 'svelte';
  import Icon from '../../components/Icon.svelte';
  import StatusMark from '../../components/StatusMark.svelte';
  import StreamView from '../../components/StreamView.svelte';
  import Composer from './Composer.svelte';
  import EventCard from './EventCard.svelte';
  import GateCard from './GateCard.svelte';
  import BatchGates from './BatchGates.svelte';
  import ChildCard from './ChildCard.svelte';
  import NextCard from './NextCard.svelte';
  import ReportDialog from './ReportDialog.svelte';
  import { phaseText } from './flowtext';

  let { dossier: d, job, last, now, waiting = [], onpeek }: {
    dossier: Dossier; job: Job | undefined; last: Job | undefined; now: Now | null; waiting?: Dossier[]; onpeek?: (id: string) => void;
  } = $props();
  const LIMIT = 60;
  let filter = $state<Filter>('all');
  let limit = $state(LIMIT);
  let stage = $state<FollowStage>('auto');
  let reports = $state<(LocalReport & { id: string })[]>([]);
  const jobs = $derived(Object.values(app.m.jobs).filter((j) => j.dossier_id === d.id && j.attempts.length));
  const children = $derived(Object.values(app.m.dossiers).filter((c) => c.parent_id === d.id));
  // a report the server already wrote in the thread is not shown a second time
  const mine = $derived(reports.filter((r) => r.id === d.id && !d.events.some((e) => e.t >= r.t - 5 && (e.kind === 'report' || /report/.test(e.key)))));
  const items = $derived(threadItems(d, { jobs, children, reports: mine }));
  const view = $derived(buildThread(items, filter, limit));
  const counts = $derived(Object.fromEntries(FILTERS.map((f) => [f, buildThread(items, f, 0).total])) as Record<Filter, number>);
  const lastOf = $derived.by(() => {
    const m: Record<string, number> = {};
    d.events.forEach((e, i) => { m[e.kind] = i; });
    return m;
  });
  const showNext = $derived(!now && !waiting.length && !pendingGate(d) && d.status !== 'proved' && (d.status !== 'draft' || Boolean(d.problem || d.statements.length)) && (troubleOf(d, last) !== '' || !d.proofs.some((p) => p.ok && p.parent === d.cur_statement)));
  const attempts = $derived((job?.attempts ?? []).filter((a) => a.stage === job?.stage));
  const cur = $derived(attempts[attempts.length - 1]);
  const liveAttempt = $derived(cur && (cur.status === 'generating' || cur.status === 'compiling') ? cur : undefined);

  // --- « Mal compris » and « En parler »
  let reporting = $state(false);
  let rTarget = $state<ReportTarget>('event');
  let rRef = $state<number | undefined>(undefined);
  function report(target: ReportTarget, ref?: number) { rTarget = target; rRef = ref; reporting = true; }
  function about(s: FollowStage) { stage = s; document.getElementById(`follow-${d.id}`)?.focus(); }

  // --- scrolling: the page scrolls; the end is followed only when the reader is already there
  let atEnd = $state(true);
  let seen = $state(0);
  let endMark: HTMLDivElement | undefined = $state();
  const gap = () => document.documentElement.scrollHeight - window.innerHeight - window.scrollY;
  function onScroll() { atEnd = gap() < 90; if (atEnd) seen = items.length; }
  function toEnd(smooth = true) {
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: smooth && !calm ? 'smooth' : 'auto' });
    atEnd = true; seen = items.length;
  }
  let opened = '';
  $effect(() => {
    const id = d.id;
    if (opened === id) return;
    opened = id;
    untrack(() => { filter = 'all'; limit = LIMIT; seen = items.length; });
    // opening a dossier shows its latest state (after the router moved the focus to the title)
    const h = setTimeout(() => {
      const g = pendingGate(untrack(() => d)) ? document.getElementById(`gate-${id}`) : null;       // a question first, else the end
      if (g) { g.scrollIntoView({ block: 'start' }); onScroll(); } else toEnd(false);
    }, 80);
    return () => clearTimeout(h);
  });
  $effect(() => {
    void items.length; void now?.phase; void now?.waiting;
    if (untrack(() => atEnd && !pendingGate(d))) void tick().then(() => { if (opened === d.id && endMark) toEnd(false); });
  });
  const fresh = $derived(Math.max(0, items.length - seen));
  const spoken = $derived.by(() => {                        // announced politely: only new results, not streamed text
    const e = d.events[d.events.length - 1];
    return e && e.kind !== 'user' ? (e.text.split('\n')[0] ?? '').slice(0, 160) : '';
  });
  const dur = (a: number, b: number) => (b - a >= 1 ? fmtDuration(b - a) : '');
</script>

<svelte:window onscroll={onScroll} onresize={onScroll} />

{#snippet item(it: Item)}
  <div class="it" data-kind={it.kind}>
    {#if it.kind === 'event'}<EventCard dossier={d} ev={it.ev} index={it.index} {job} latest={lastOf[it.ev.kind] === it.index} onreport={report} onabout={about} />
    {:else if it.kind === 'gate'}<GateCard dossier={d} gate={it.gate} onreport={report} onabout={about} />
    {:else if it.kind === 'child'}<ChildCard child={it.child} {onpeek} />
    {:else if it.kind === 'report'}<p class="rep"><Icon name="warn" size={14} /> {t('report.item', { what: t(`report.target.${it.report.target}` as 'report.target.event'), reason: t(`report.reason.${it.report.reason}` as 'report.reason.other') })}{#if it.report.text} « {it.report.text} »{/if} <span class="xs muted">{fmtTime(it.t)}</span></p>
    {:else}
      {@const a = it.a}
      <div class="att">
        {#if a.summary}<p class="small">{a.summary}</p>{/if}
        {#if a.errors_text}<pre class="errs">{a.errors_text}</pre>{/if}
        {#if !a.summary && !a.errors_text}<p class="small muted">{tk(`attempt.status.${a.status}`, a.status)}</p>{/if}
      </div>
    {/if}
  </div>
{/snippet}

<section class="thread" aria-labelledby="th-h">
  <h2 id="th-h" class="sr-only">{t('thread.title')}</h2>
  <div class="chips" role="group" aria-label={t('flow.filters')}>
    {#each FILTERS.filter((f) => f === 'all' || counts[f]) as f (f)}<button class="fchip" aria-pressed={filter === f} onclick={() => { filter = f; limit = LIMIT; }}>{t(`flow.filter.${f}`)}{#if f !== 'all'} <span class="n">{counts[f]}</span>{/if}</button>{/each}
  </div>
  {#if view.hidden}<button class="btn small quiet" onclick={() => (limit += 200)}><Icon name="chevronUp" size={14} />{t('thread.earlier', { n: view.hidden })}</button>{/if}
  {#if !items.length}<p class="muted">{t('flow.empty')}</p>{:else if !view.total}<p class="muted">{t('flow.filterEmpty')}</p>{/if}

  <ol class="runs" aria-label={t('thread.events')}>
    {#each view.runs as r (r.key)}
      <li class="run">
        {#if r.user}
          <div class="ev user"><p class="meta xs">{t('thread.you')}{#if r.user.ev.stage && r.user.ev.stage !== 'auto'} · {t('thread.aboutLabel').toLowerCase()} : {tk(`follow.${r.user.ev.stage}`, r.user.ev.stage).toLowerCase()}{/if} · {fmtTime(r.user.ev.t)}</p><p class="say">{r.user.ev.text}</p></div>
        {:else}<p class="cont xs">{r.continued ? t('flow.continued') : t('flow.start')} · {fmtTime(r.t0)}</p>{/if}
        {#each r.phases as p (p.key)}
          <section class="phase" aria-label={phaseText(p.phase)}>
            <h3><span class="pin" aria-hidden="true"></span>{phaseText(p.phase)} <span class="when xs">{fmtTime(p.t1)}{#if p.blocks.some((b) => b.items.some((x) => x.kind === 'event' || x.kind === 'attempt')) && dur(p.t0, p.t1)} · {dur(p.t0, p.t1)}{/if}</span></h3>
            {#each p.blocks as b (b.key)}
              {#if b.attempt > 0}
                {@const a = b.items.find((x) => x.kind === 'attempt')}
                <details class="attempt" open={filter === 'attempts' ? undefined : !liveAttempt && !showNext && b === p.blocks[p.blocks.length - 1] && p === r.phases[r.phases.length - 1] && r === view.runs[view.runs.length - 1] && b.items.some((x) => x.kind !== 'attempt')}>
                  <summary>
                    {#if a?.kind === 'attempt'}<StatusMark phase={a.a.status === 'accepted' ? 'proved' : a.a.status === 'cancelled' ? 'stopped' : 'failed'} />{/if}
                    <span>{t('flow.attempt', { n: b.attempt })}{#if a?.kind === 'attempt'} · {tk(`attempt.kind.${a.a.kind}`, a.a.kind)} · {tk(`attempt.status.${a.a.status}`, a.a.status)}{/if}</span>
                    {#if a?.kind === 'attempt' && a.a.model}<span class="chip {modelLabel(a.a.model).local ? 'local' : 'online'}">{modelLabel(a.a.model).name}</span>{/if}
                    <span class="xs muted">{fmtTime(b.items[b.items.length - 1]!.t)}{#if a?.kind === 'attempt' && a.a.gen_seconds} · {fmtDuration(a.a.gen_seconds + a.a.compile_seconds)}{/if}</span>
                  </summary>
                  {#each b.items as it (it.key)}{@render item(it)}{/each}
                </details>
              {:else}{#each b.items as it (it.key)}{@render item(it)}{/each}{/if}
            {/each}
          </section>
        {/each}
      </li>
    {/each}
    {#if job && now && filter === 'all'}
      <li class="run">
        <section class="phase on" aria-label="{t('flow.live')} : {phaseText(now.phase)}">
          <h3><span class="pin" aria-hidden="true"></span>{phaseText(now.phase)} <span class="chip running">{t('flow.live')}</span>{#if attemptNumber(job) && now.phase === 'prove'}<span class="when xs">{t('flow.attempt', { n: attemptNumber(job) })}</span>{/if}</h3>
          {#if job.tournament && 'names' in job.tournament && job.tournament.names.length && job.stage === 'proof'}<p class="small">{t('proof.tournament', { k: job.tournament.round, models: job.tournament.names.join(', ') })}</p>{/if}
          <StreamView jobId={job.id} stage={job.stage} attempt={liveAttempt && job.stage === 'proof' ? liveAttempt.index : null} maxHeight="340px" />
          {#each sideStages(job) as s (s)}<details class="attempt"><summary><StatusMark phase="running" /><span>{tk(`stage.${s}`, s)}</span></summary><StreamView jobId={job.id} stage={s} maxHeight="220px" /></details>{/each}
        </section>
      </li>
    {/if}
  </ol>
  {#if waiting.length}<BatchGates dossier={d} {waiting} />{/if}
  {#if showNext}<NextCard dossier={d} {last} />{/if}
  <div bind:this={endMark}></div>

  <div class="dock">
    {#if !atEnd}<button class="btn small latest" onclick={() => toEnd()}><Icon name="chevronDown" size={14} />{t('flow.latest')}{#if fresh} · {t('flow.newItems', { n: fresh })}{/if}</button>{/if}
    <Composer dossier={d} {job} bind:stage />
  </div>
  <p class="sr-only" aria-live="polite">{spoken}</p>
</section>
<ReportDialog dossier={d} target={rTarget} ref={rRef} bind:open={reporting} onsent={(r) => { reports = [...reports, { ...r, id: d.id }]; }} />

<style>
  .thread { min-width: 0; display: flex; flex-direction: column; gap: var(--s-3); }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .fchip { min-height: 32px; padding: 0 12px; border-radius: 999px; border: 1px solid var(--line-strong); background: var(--surface); color: var(--text-2); font: 600 var(--fs-xs)/1 var(--font-ui); cursor: pointer; }
  .fchip[aria-pressed='true'] { background: var(--ink); color: var(--on-ink); border-color: var(--ink); }
  .fchip .n { font-weight: 400; }
  .runs { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--s-4); grid-template-columns: minmax(0, 1fr); }
  .run { display: grid; gap: var(--s-3); grid-template-columns: minmax(0, 1fr); }
  .ev.user { justify-self: end; max-width: min(88%, 46rem); background: var(--accent-soft); border-radius: var(--r-3) var(--r-3) 4px var(--r-3); padding: var(--s-2) var(--s-3); }
  .ev.user p { margin: 0; }
  .say { white-space: pre-wrap; overflow-wrap: anywhere; }
  .meta { color: var(--text-2); font-weight: 600; }
  .cont { margin: 0; color: var(--text-3); text-align: center; }
  .phase { position: relative; padding-left: 22px; display: grid; gap: var(--s-2); grid-template-columns: minmax(0, 1fr); content-visibility: auto; contain-intrinsic-size: auto 180px; }
  .phase::before { content: ''; position: absolute; left: 6px; top: 12px; bottom: -14px; width: 2px; background: var(--line); }
  .run:last-child .phase:last-child::before { bottom: 0; }
  .pin { position: absolute; left: 0; top: 5px; width: 14px; height: 14px; border-radius: 50%; background: var(--bg); border: 3px solid var(--line-strong); }
  .phase.on .pin { border-color: var(--running-fill); background: var(--running-soft); }
  h3 { margin: 0; font-size: var(--fs-sm); color: var(--text-2); font-weight: 700; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  .when { color: var(--text-3); font-weight: 400; font-variant-numeric: tabular-nums; }
  .it + .it { margin-top: var(--s-2); }
  .attempt { border: 1px solid var(--line); border-radius: var(--r-2); background: var(--surface); padding: 0 var(--s-3); }
  .attempt[open] { padding-bottom: var(--s-3); }
  .attempt summary { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 38px; cursor: pointer; font-size: var(--fs-sm); }
  .att p { margin: 0 0 4px; }
  .errs { margin: 0; font: 0.75rem/1.45 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; background: var(--failed-soft); padding: var(--s-2); border-radius: var(--r-1); max-height: 180px; overflow: auto; }
  .rep { margin: 0; padding: var(--s-2) var(--s-3); border-radius: var(--r-2); background: var(--running-soft); }
  .dock { position: sticky; bottom: 0; z-index: 40; padding: var(--s-2) 0 max(var(--s-2), env(safe-area-inset-bottom)); background: linear-gradient(to bottom, transparent, var(--bg) 14px); margin-top: auto; }
  .latest { display: flex; margin: 0 auto var(--s-2); box-shadow: var(--shadow-2); }
  @media (pointer: coarse) { .fchip { min-height: var(--touch); } }
  @media (max-width: 767px) { .chips { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 2px; } .fchip { white-space: nowrap; flex: none; } .phase { padding-left: 18px; } .ev.user { max-width: 94%; } }
</style>
