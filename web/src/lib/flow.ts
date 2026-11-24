// The flow of one dossier (D64, docs/DOSSIER_FLOW.md): pure functions that turn server data into what the screen
// shows — the « now » line, the stepper and the chronological thread. No Svelte here (tests/unit/flow.test.ts).
// Old dossiers have none of the new fields (`phase`, `run`, `attempt`, `now`, `gate`): everything falls back on
// `stage`, `kind` and the job.
import type { Attempt, Dossier, DossierEvent, DossierSummary, FlowPhase, Gate, Job } from './api/types';

export type Step = 'understand' | 'translate' | 'prove' | 'verify';
export const STEPS: Step[] = ['understand', 'translate', 'prove', 'verify'];
export type StepState = 'todo' | 'active' | 'waiting' | 'done' | 'failed';
type Params = Record<string, unknown>;

export interface Now {
  phase: FlowPhase; run: string; attempt: number; activity: string; params: Params; model: string;
  started: number; waiting: '' | 'user' | 'slot' | 'quota'; side: { phase: FlowPhase; activity: string; params: Params }[];
  /** Where it comes from: the server's `now`, or derived here from the job / the gate. */
  from: 'server' | 'job' | 'gate';
}

const PHASES = new Set<string>(['understand', 'translate', 'literature', 'decompose', 'prove', 'verify', 'explain']);

/** Job stage (old vocabulary) → phase. The old stage « verify » checks the STATEMENT, so it belongs to « translate ». */
export function phaseOfStage(stage: string): FlowPhase | '' {
  switch (stage) {
    case 'understand': case 'route': return 'understand';
    case 'statement': case 'notes': case 'verify': return 'translate';
    case 'proof': case 'mathlib': case 'certificate': return 'prove';
    case 'literature': return 'literature';
    case 'explanation': case 'informal': return 'explain';
    default: return PHASES.has(stage) ? (stage as FlowPhase) : '';
  }
}

export function phaseOfEvent(ev: DossierEvent): FlowPhase | '' {
  if (ev.phase && PHASES.has(ev.phase)) return ev.phase;
  switch (ev.kind) {
    case 'understood': return 'understand';
    case 'statement': case 'notes': case 'check': return 'translate';
    case 'proof': case 'certificate': return 'prove';
    case 'literature': return 'literature';
    case 'explanation': case 'informal': return 'explain';
    case 'user': return '';
    default: return phaseOfStage(ev.stage);
  }
}

/** The step of the header a phase belongs to (« explain » comes after « verify »: every step is done by then). */
export function stepOf(p: FlowPhase | ''): Step | null {
  if (p === 'literature' || p === 'decompose') return 'prove';
  return (STEPS as string[]).includes(p) ? (p as Step) : null;
}

/** `activity` is a key, or `{key, params}` (both accepted until the server fixes one). */
function activityOf(a: unknown, params: unknown): { activity: string; params: Params } {
  const p = (params ?? {}) as Params;
  if (a && typeof a === 'object') {
    const o = a as { key?: string; params?: Params };
    return { activity: o.key ?? '', params: { ...p, ...(o.params ?? {}) } };
  }
  return { activity: String(a ?? ''), params: p };
}

/** Number of the latest attempt of a job inside its current stage (1…), 0 when there is none. */
export function attemptNumber(job: Job | null | undefined): number {
  return job ? job.attempts.filter((a) => a.stage === job.stage).length : 0;
}

export function pendingGate(d: Dossier | null | undefined): Gate | null {
  return d?.gate && d.gate.state === 'pending' ? d.gate : null;
}

export function deriveNow(d: Dossier | null | undefined, job: Job | null | undefined): Now | null {
  const gate = pendingGate(d);
  const n = d?.now;
  if (n && typeof n === 'object') {
    return {
      phase: n.phase, run: n.run ?? '', attempt: n.attempt ?? 0, ...activityOf(n.activity, n.params), model: n.model ?? '',
      started: n.started ?? 0, waiting: n.waiting ?? '', from: 'server',
      side: (n.side ?? []).map((s) => ({ phase: s.phase, ...activityOf(s.activity, s.params) })),
    };
  }
  if (job && (job.state === 'queued' || job.state === 'running')) {
    const open = [...(job.timings ?? [])].reverse().find((x) => x.stage === job.stage && x.end === null);
    const asking = Boolean((job.conductor as { ask?: unknown } | undefined)?.ask);
    const phase = phaseOfStage(job.stage) || 'understand';
    const att = attemptNumber(job);
    return {
      phase, run: job.id, attempt: phase === 'prove' || att > 1 ? att : 0, activity: job.stage ? `stage.${job.stage}` : '', params: {},
      model: '', started: open?.start ?? job.started ?? job.created, from: 'job',
      waiting: asking ? 'user' : job.state === 'queued' || job.waiting ? 'slot' : '',
      side: (job.stages ?? []).filter((s, i, a) => s !== job.stage && a.indexOf(s) === i)
        .map((s) => ({ phase: phaseOfStage(s) || 'prove', activity: `stage.${s}`, params: {} })),
    };
  }
  if (gate) {
    return { phase: gate.kind === 'meaning' ? 'understand' : 'translate', run: '', attempt: 0, activity: '', params: {}, model: '',
      started: gate.t, waiting: 'user', side: [], from: 'gate' };
  }
  return null;
}

function extraOf(d: Dossier, key: string): { verdict?: string; state?: string } {
  return (((d['extra'] as Params | undefined)?.[key] ?? d[key]) as { verdict?: string; state?: string } | undefined) ?? {};
}
export const isConditional = (d: Dossier): boolean => extraOf(d, 'conditional_proof').verdict === 'proved_modulo';
export const recheckState = (d: Dossier): string => extraOf(d, 'recheck').state ?? '';

export type Trouble = '' | 'failed' | 'stopped';
/** How the dossier stands when nothing runs and nothing waits for the user. */
export function troubleOf(d: Dossier, last: Job | null | undefined): Trouble {
  if (d.status === 'proved') return '';
  if (last?.state === 'failed' || d.status === 'failed') return 'failed';
  if (last?.state === 'cancelled' || d.status === 'stopped') return 'stopped';
  return '';
}

export function deriveSteps(d: Dossier, now: Now | null, last: Job | null | undefined): Record<Step, StepState> {
  const st = d.statements[d.cur_statement];
  const proved = d.status === 'proved';
  const out: Record<Step, StepState> = {
    understand: d.understood || d.understood_display || d.statements.length ? 'done' : 'todo',
    translate: st ? (st.ok ? 'done' : 'failed') : 'todo',
    prove: proved || isConditional(d) ? 'done' : 'todo',
    verify: proved ? (recheckState(d) === 'regressed' ? 'failed' : 'done') : 'todo',
  };
  if (now) {
    const s = stepOf(now.phase);
    if (!s) return out;                                     // explaining: everything before is as it stands
    const i = STEPS.indexOf(s);
    STEPS.forEach((x, k) => { if (k < i) out[x] = 'done'; else if (k > i) out[x] = 'todo'; });
    out[s] = now.waiting === 'user' ? 'waiting' : 'active';
    return out;
  }
  if (troubleOf(d, last) === 'failed') {
    const s = stepOf(phaseOfStage(last?.state === 'failed' ? last.stage : '')) ?? (st ? (st.ok ? 'prove' : 'translate') : 'understand');
    out[s] = 'failed';
    for (let k = STEPS.indexOf(s) + 1; k < STEPS.length; k++) out[STEPS[k]!] = 'todo';
  }
  return out;
}

// ---- The thread ----

export interface LocalReport { target: string; reason: string; text: string; t: number }
interface Base { key: string; t: number; run: string; phase: FlowPhase | ''; attempt: number }
export type EventItem = Base & { kind: 'event'; ev: DossierEvent; index: number };
export type Item =
  | EventItem
  | (Base & { kind: 'attempt'; a: Attempt; job: Job })
  | (Base & { kind: 'child'; child: DossierSummary })
  | (Base & { kind: 'gate'; gate: Gate })
  | (Base & { kind: 'report'; report: LocalReport });

export interface Block { key: string; attempt: number; items: Item[] }
export interface PhaseGroup { key: string; phase: FlowPhase | ''; t0: number; t1: number; blocks: Block[] }
export interface RunGroup { key: string; run: string; user: EventItem | null; continued: boolean; t0: number; t1: number; phases: PhaseGroup[] }

export type Filter = 'all' | 'requests' | 'results' | 'checks' | 'attempts' | 'children';
export const FILTERS: Filter[] = ['all', 'requests', 'results', 'checks', 'attempts', 'children'];
const RESULTS = new Set(['understood', 'statement', 'notes', 'proof', 'explanation', 'informal', 'certificate', 'literature']);

export function matches(it: Item, f: Filter): boolean {
  switch (f) {
    case 'requests': return it.kind === 'gate' || it.kind === 'report' || (it.kind === 'event' && (it.ev.kind === 'user' || it.ev.kind === 'report'));
    case 'results': return it.kind === 'gate' || (it.kind === 'event' && RESULTS.has(it.ev.kind));
    case 'checks': return it.kind === 'event' && (it.ev.kind === 'check' || it.ev.kind === 'error');
    case 'attempts': return it.kind === 'attempt' || it.attempt > 0;
    case 'children': return it.kind === 'child';
    default: return true;
  }
}

/** One flat list, strictly in the order things happened: events keep the server's order, the rest goes in by time. */
export function threadItems(d: Dossier, o: { jobs?: Job[]; children?: DossierSummary[]; reports?: LocalReport[] } = {}): Item[] {
  const out: Item[] = [];
  let run = '';
  let phase: FlowPhase | '' = '';
  const runOfJob = new Map<string, string>();
  for (const ev of d.events) if (ev.run && ev.job) runOfJob.set(ev.job, ev.run);
  d.events.forEach((ev, index) => {
    const own = ev.run || (ev.job ? runOfJob.get(ev.job) ?? ev.job : '');
    const user = ev.kind === 'user';
    if (user) { run = own || `u${index}`; phase = ''; } else if (own && own !== run) { phase = ''; run = own; }
    const p = user ? '' : phaseOfEvent(ev) || phase;
    phase = p;
    out.push({ kind: 'event', key: `e${index}`, t: ev.t, run, phase: p, attempt: ev.attempt ?? 0, ev, index });
  });
  const extra: Item[] = [];
  for (const job of o.jobs ?? []) {
    const n: Record<string, number> = {};
    for (const a of job.attempts) {
      const k = (n[a.stage] = (n[a.stage] ?? 0) + 1);
      if (a.status === 'generating' || a.status === 'compiling') continue;       // shown live, at the end of the thread
      extra.push({ kind: 'attempt', key: `a${job.id}.${a.index}`, t: a.t, run: runOfJob.get(job.id) ?? job.id,
        phase: phaseOfStage(a.stage), attempt: k, a, job });
    }
  }
  for (const c of o.children ?? []) extra.push({ kind: 'child', key: `c${c.id}`, t: c.created, run: '', phase: '', attempt: 0, child: c });
  if (d.gate) extra.push({ kind: 'gate', key: `g${d.gate.id}`, t: d.gate.t, run: '', phase: d.gate.kind === 'meaning' ? 'understand' : 'translate', attempt: 0, gate: d.gate });
  for (const r of o.reports ?? []) extra.push({ kind: 'report', key: `r${r.t}`, t: r.t, run: '', phase: '', attempt: 0, report: r });
  extra.sort((a, b) => a.t - b.t);
  for (const it of extra) {
    let i = out.findIndex((x) => x.t > it.t);
    if (i < 0) i = out.length;
    const prev = out[i - 1];
    if (!it.run) it.run = prev?.run ?? '';
    if (!it.phase) it.phase = it.kind === 'child' ? 'decompose' : prev?.phase ?? '';
    out.splice(i, 0, it);
  }
  return out;
}

export function groupItems(items: Item[]): RunGroup[] {
  const runs: RunGroup[] = [];
  const seen = new Set<string>();
  let prevT = 0;
  for (const it of items) {
    let r = runs[runs.length - 1];
    const user = it.kind === 'event' && it.ev.kind === 'user' ? it : null;
    const adopt = Boolean(r?.user && /^u\d+$/.test(r.run));          // an old request without an id takes the job that follows it
    if (!r || user || (it.run !== r.run && !adopt)) {
      r = { key: it.key, run: it.run, user, continued: !user && it.run !== '' && seen.has(it.run), t0: it.t, t1: it.t, phases: [] };
      runs.push(r);
    } else if (adopt && it.run) r.run = it.run;
    seen.add(r.run);
    r.t1 = Math.max(r.t1, it.t);
    if (!user) {
      let p = r.phases[r.phases.length - 1];
      if (!p || it.phase !== p.phase) {
        p = { key: `${r.key}.${it.key}`, phase: it.phase, t0: prevT && r.t0 <= prevT ? prevT : it.t, t1: it.t, blocks: [] };
        r.phases.push(p);
      }
      p.t1 = Math.max(p.t1, it.t);
      let b = p.blocks[p.blocks.length - 1];
      if (!b || b.attempt !== it.attempt) p.blocks.push((b = { key: `${p.key}.${it.key}`, attempt: it.attempt, items: [] }));
      b.items.push(it);
    }
    prevT = it.t;
  }
  return runs;
}

/** Filter, keep the last `limit` (0 = all), group. `hidden`: how many older items are not shown. */
export function buildThread(items: Item[], filter: Filter, limit: number): { runs: RunGroup[]; hidden: number; total: number } {
  const kept = filter === 'all' ? items : items.filter((i) => matches(i, filter));
  const shown = limit > 0 && kept.length > limit ? kept.slice(-limit) : kept;
  return { runs: groupItems(shown), hidden: kept.length - shown.length, total: kept.length };
}

/** What was tried, for the explanation of a failure. */
export function failureSummary(d: Dossier, last: Job | null | undefined): { attempts: number; models: string[]; cause: string; error: string } {
  const att = (last?.attempts ?? []).filter((a) => a.status !== 'cancelled');
  const bad = [...att].reverse().find((a) => a.errors_text || a.summary);
  const ev = [...d.events].reverse().find((e) => e.kind === 'error');
  return {
    attempts: att.length || d.events.reduce((n, e) => Math.max(n, e.attempt ?? 0), 0),
    models: [...new Set(att.map((a) => a.model).filter(Boolean))],
    cause: (ev?.text || bad?.errors_text || bad?.summary || '').trim().split('\n').slice(0, 6).join('\n'),
    error: last?.error ?? '',
  };
}

// ---- Parts of the side pane ----
export const PARTS = ['enonce', 'lean', 'preuve', 'plan', 'litterature', 'calculs', 'versions'] as const;
export type Part = (typeof PARTS)[number];
export function partOf(s: string | undefined): Part | null {
  if (s === 'sous-lemmes' || s === 'lemmes') return 'plan';
  return (PARTS as readonly string[]).includes(s ?? '') ? (s as Part) : null;
}
export const calcEvents = (d: Dossier): DossierEvent[] => d.events.filter((e) => e.kind === 'certificate');
export function partsOf(d: Dossier): Part[] {
  return PARTS.filter((p) => p !== 'calculs' || calcEvents(d).length > 0);
}

/** Part shown when the address names none: it follows the work. */
export function autoPart(d: Dossier, now: Now | null): Part {
  const s = now ? stepOf(now.phase) ?? 'verify' : null;
  if (s === 'understand') return 'enonce';
  if (s === 'translate') return 'lean';
  if (s) return 'preuve';
  if (d.status === 'proved' || d.proofs.length) return 'preuve';
  return d.statements.length ? 'lean' : 'enonce';
}
