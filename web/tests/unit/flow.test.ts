// S-BH (D66): grouping of the thread, « now », stepper — with the new fields and with old dossiers.
import { describe, expect, it } from 'vitest';
import { autoPart, buildThread, deriveNow, deriveSteps, failureSummary, groupItems, partOf, partsOf, pendingGate, phaseOfEvent, phaseOfStage, threadItems, troubleOf } from '../../src/lib/flow';
import { applyEvent, emptyModel, summaryOf } from '../../src/lib/store/model';
import type { Dossier, DossierEvent, DossierSummary, Gate, Job } from '../../src/lib/api/types';

const ev = (kind: DossierEvent['kind'], t: number, x: Partial<DossierEvent> = {}): DossierEvent =>
  ({ kind, text: kind, t, ref: null, stage: '', model: '', key: '', params: {}, job: '', ...x });
const dos = (x: Partial<Dossier> = {}): Dossier => ({
  id: 'd', title: 'D', problem: 'p', understood: '', understood_display: '', workspace: 'w', theorem: 'th', created: 0, updated: 0,
  events: [], statements: [], proofs: [], explanations: [], statement_notes: [], informal_proofs: [], cur_statement: -1, cur_proof: -1,
  cur_explanation: -1, lemmas_used: [], project_id: '', status: 'draft', parent_id: '', retry_parent: false, archived: false, kind: 'theorem',
  refs: [], source: null, uses: [], current: { statement: '', proof: '', explanation: '', statement_notes: '', informal_proof: '', proof_is_current: false }, ...x });
const version = (ok = true) => ({ code: 'theorem', t: 1, source: 'ai' as const, ok, parent: null, note: '', model: '', meta: {} });
const job = (x: Partial<Job> = {}): Job => ({ id: 'j1', dossier_id: 'd', plan: [], mode: 'auto', strategy: 'auto', user: true, state: 'running', stage: 'proof', waiting: '', created: 1, started: 2, ended: null, attempts: [], done_stages: [], summary: {}, error: '', ...x });
const att = (index: number, t: number, status: 'accepted' | 'rejected' | 'generating' = 'rejected') => ({ index, stage: 'proof' as const, kind: 'initial' as const, status, summary: 's', errors_text: `err ${index}`, code: '', model: `local:m${index}`, gen_seconds: 1, compile_seconds: 1, tokens: 0, finish: '', t });
const gate = (x: Partial<Gate> = {}): Gate => ({ id: 'g1', kind: 'meaning', state: 'pending', version: 0, t: 10, ...x });

describe('phases', () => {
  it('maps old stages and kinds; the old « verify » is the statement check', () => {
    expect(phaseOfStage('verify')).toBe('translate');
    expect(phaseOfStage('mathlib')).toBe('prove');
    expect(phaseOfStage('')).toBe('');
    expect(phaseOfEvent(ev('check', 1))).toBe('translate');
    expect(phaseOfEvent(ev('info', 1, { stage: 'proof' }))).toBe('prove');
    expect(phaseOfEvent(ev('info', 1, { phase: 'verify' }))).toBe('verify');
  });
});

describe('now', () => {
  it('takes the server now, with both activity shapes', () => {
    const n = deriveNow(dos({ now: { phase: 'prove', run: 'r', attempt: 2, activity: { key: 'compile', params: { n: 3 } }, model: 'local:x', started: 5, waiting: '', side: [{ phase: 'literature', activity: 'search' }] } }), undefined)!;
    expect(n).toMatchObject({ phase: 'prove', attempt: 2, activity: 'compile', params: { n: 3 }, from: 'server' });
    expect(n.side).toEqual([{ phase: 'literature', activity: 'search', params: {} }]);
  });
  it('is derived from the job on old servers', () => {
    const n = deriveNow(dos(), job({ stages: ['proof', 'literature'] as never, attempts: [att(0, 3), att(1, 4, 'generating')], timings: [{ stage: 'proof', start: 7, end: null, seconds: null }] }))!;
    expect(n).toMatchObject({ phase: 'prove', attempt: 2, activity: 'stage.proof', started: 7, waiting: '', from: 'job' });
    expect(n.side.map((s) => s.phase)).toEqual(['literature']);
    expect(deriveNow(dos(), job({ state: 'queued' }))!.waiting).toBe('slot');
    expect(deriveNow(dos(), job({ conductor: { ask: { t: 1 } } as never }))!.waiting).toBe('user');
  });
  it('waits for the user when a gate is pending and nothing runs, else is null', () => {
    expect(deriveNow(dos({ gate: gate() }), undefined)).toMatchObject({ waiting: 'user', phase: 'understand', from: 'gate' });
    expect(deriveNow(dos({ gate: gate({ kind: 'statement' }), now: null }), undefined)).toMatchObject({ waiting: 'user', phase: 'translate' });
    expect(deriveNow(dos({ gate: gate({ state: 'approved' }) }), undefined)).toBeNull();
    expect(pendingGate(dos())).toBeNull();
  });
  it('a dossier.now event updates the open dossier and its summary', () => {
    const m = emptyModel();
    const d = dos();
    m.full['d'] = d; m.dossiers['d'] = summaryOf(d);
    const now = { phase: 'prove', run: 'r', attempt: 1, activity: 'x', model: '', started: 1, waiting: '', side: [] };
    expect(applyEvent(m, { type: 'dossier.now', dossier_id: 'd', now } as never)).toBe(true);
    expect(m.full['d']!.now).toEqual(now);
    applyEvent(m, { type: 'dossier.now', dossier_id: 'd', now: null } as never);
    expect(m.dossiers['d']!.now).toBeNull();
    expect(applyEvent(m, { type: 'dossier.now', dossier_id: 'unknown', now: null } as never)).toBe(true);
  });
});

describe('stepper', () => {
  const ready = dos({ statements: [version()], cur_statement: 0, understood: 'u' });
  it('marks what is done, active, waiting, failed', () => {
    expect(deriveSteps(dos(), null, undefined)).toEqual({ understand: 'todo', translate: 'todo', prove: 'todo', verify: 'todo' });
    expect(deriveSteps(ready, deriveNow(ready, job()), undefined)).toEqual({ understand: 'done', translate: 'done', prove: 'active', verify: 'todo' });
    const g = dos({ gate: gate() });
    expect(deriveSteps(g, deriveNow(g, undefined), undefined).understand).toBe('waiting');
    expect(deriveSteps(ready, null, job({ state: 'failed', stage: 'proof' }))).toEqual({ understand: 'done', translate: 'done', prove: 'failed', verify: 'todo' });
    expect(deriveSteps(dos(), null, job({ state: 'failed', stage: 'statement' })).translate).toBe('failed');
  });
  it('is proved only after the verification; a conditional proof does not verify; retranslating resets the rest', () => {
    const proved = { ...ready, status: 'proved' as const };
    expect(deriveSteps(proved, null, undefined)).toEqual({ understand: 'done', translate: 'done', prove: 'done', verify: 'done' });
    expect(deriveSteps({ ...ready, conditional_proof: { verdict: 'proved_modulo' } }, null, undefined)).toMatchObject({ prove: 'done', verify: 'todo' });
    expect(deriveSteps({ ...proved, recheck: { state: 'regressed' } }, null, undefined).verify).toBe('failed');
    expect(deriveSteps(proved, deriveNow(proved, job({ stage: 'statement' })), undefined)).toEqual({ understand: 'done', translate: 'active', prove: 'todo', verify: 'todo' });
    expect(deriveSteps(proved, deriveNow(proved, job({ stage: 'explanation' })), undefined).verify).toBe('done');
  });
  it('trouble: stopped is not failed; an accepted proof wins', () => {
    expect(troubleOf(ready, job({ state: 'cancelled' }))).toBe('stopped');
    expect(troubleOf({ ...ready, status: 'proved' }, job({ state: 'failed' }))).toBe('');
  });
});

describe('thread', () => {
  it('groups an old dossier by request, then by phase', () => {
    const d = dos({ events: [ev('user', 1), ev('understood', 2, { job: 'a' }), ev('statement', 3, { job: 'a' }), ev('info', 4, { job: 'a' }), ev('proof', 5, { job: 'a' }), ev('user', 6, { job: 'b' }), ev('proof', 7, { job: 'b' })] });
    const { runs, hidden } = buildThread(threadItems(d), 'all', 0);
    expect(hidden).toBe(0);
    expect(runs.map((r) => [r.run, r.phases.map((p) => p.phase)])).toEqual([['a', ['understand', 'translate', 'prove']], ['b', ['prove']]]);
    expect(runs[0]!.user!.ev.kind).toBe('user');
    expect(runs[0]!.phases[0]).toMatchObject({ t0: 1, t1: 2 });
  });
  it('keeps events before any request, and says when an earlier request continues', () => {
    const d = dos({ events: [ev('statement', 1), ev('user', 2, { run: 'r1' }), ev('user', 3, { run: 'r2' }), ev('proof', 4, { run: 'r1' })] });
    const runs = groupItems(threadItems(d));
    expect(runs.map((r) => [r.run, Boolean(r.user), r.continued])).toEqual([['', false, false], ['r1', true, false], ['r2', true, false], ['r1', false, true]]);
  });
  it('folds attempts and puts job attempts, sub-dossiers, gates and reports at their time', () => {
    const child = { id: 'c1', parent_id: 'd', created: 4.5 } as DossierSummary;
    const d = dos({ gate: gate({ t: 2.5 }), events: [ev('user', 1, { run: 'r' }), ev('understood', 2, { run: 'r', phase: 'understand' }), ev('statement', 3, { run: 'r', phase: 'translate' }), ev('info', 4, { run: 'r', phase: 'prove', attempt: 1 }), ev('info', 6, { run: 'r', phase: 'prove', attempt: 2, job: 'j1' })] });
    const items = threadItems(d, { children: [child], jobs: [job({ attempts: [att(0, 4.2), att(1, 5), att(2, 7, 'generating')] })], reports: [{ target: 'event', reason: 'other', text: '', t: 8 }] });
    expect(items.map((i) => i.key)).toEqual(['e0', 'e1', 'gg1', 'e2', 'e3', 'aj1.0', 'cc1', 'aj1.1', 'e4', 'r8']);
    for (let i = 1; i < items.length; i++) expect(items[i]!.t).toBeGreaterThanOrEqual(items[i - 1]!.t);
    const prove = groupItems(items)[0]!.phases.find((p) => p.phase === 'prove')!;
    expect(prove.blocks.map((b) => [b.attempt, b.items.length])).toEqual([[1, 2]]);
    expect(items.every((i) => i.run === 'r')).toBe(true);
  });
  it('keeps the server order of events even when their clocks disagree', () => {
    const d = dos({ events: [ev('user', 5), ev('info', 3), ev('proof', 4)] });
    expect(threadItems(d).map((i) => i.key)).toEqual(['e0', 'e1', 'e2']);
  });
  it('filters and windows', () => {
    const d = dos({ events: [ev('user', 1), ...Array.from({ length: 80 }, (_, i) => ev('info', 2 + i)), ev('error', 90), ev('proof', 91)] });
    const items = threadItems(d);
    const v = buildThread(items, 'all', 60);
    expect(v.hidden).toBe(23);
    expect(v.total).toBe(83);
    expect(buildThread(items, 'requests', 60).total).toBe(1);
    expect(buildThread(items, 'checks', 60).total).toBe(1);
    expect(buildThread(items, 'results', 60).total).toBe(1);
    expect(buildThread(items, 'children', 60).runs).toEqual([]);
  });
});

describe('failure and parts', () => {
  it('sums up what was tried', () => {
    const f = failureSummary(dos({ events: [ev('error', 1, { text: 'a\nb' })] }), job({ state: 'failed', error: 'no_proof', attempts: [att(0, 1), att(1, 2)] }));
    expect(f).toEqual({ attempts: 2, models: ['local:m0', 'local:m1'], cause: 'a\nb', error: 'no_proof' });
    expect(failureSummary(dos({ events: [ev('info', 1, { attempt: 4 })] }), undefined)).toMatchObject({ attempts: 4, cause: '' });
  });
  it('parts of the pane', () => {
    expect(partOf('sous-lemmes')).toBe('plan');
    expect(partOf('x')).toBeNull();
    expect(partsOf(dos())).not.toContain('calculs');
    expect(partsOf(dos({ events: [ev('certificate', 1)] }))).toContain('calculs');
    expect(autoPart(dos(), null)).toBe('enonce');
    expect(autoPart(dos(), deriveNow(dos(), job()))).toBe('preuve');
    expect(autoPart(dos({ statements: [version()] }), null)).toBe('lean');
  });
});
