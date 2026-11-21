import { describe, it, expect } from 'vitest';
import { emptyModel, applyEvent, loadSnapshot, activeJobFor, MAX_FINISHED_JOBS } from '../../src/lib/store/model';
import type { Dossier, Job, SeqEvent, StateSnapshot } from '../../src/lib/api/types';

const job = (id: string, state: Job['state'], dossier = 'd1', created = 1): Job => ({
  id, dossier_id: dossier, plan: [], mode: 'auto', strategy: 'auto', user: true, state, stage: 'proof', waiting: '',
  created, started: created, ended: state === 'running' ? null : created + 1, attempts: [], done_stages: [], summary: {}, error: '',
});
const e = (o: Record<string, unknown>) => ({ seq: 1, ts: 0, ...o }) as unknown as SeqEvent;
const dossier = (id: string, status: Dossier['status']): Dossier => ({
  id, title: 'T', problem: '', understood: '', understood_display: '', workspace: 'w', theorem: 't', created: 1, updated: 2,
  events: [], statements: [{ code: 'x', t: 1, source: 'ai', ok: true, parent: null, note: '', model: '', meta: {} }], proofs: [],
  explanations: [], statement_notes: [], informal_proofs: [], cur_statement: 0, cur_proof: -1, cur_explanation: -1, lemmas_used: [],
  project_id: 'p', status, parent_id: '', retry_parent: false, archived: false, kind: 'theorem', refs: [], source: null, uses: [],
  current: { statement: 'x', proof: '', explanation: '', statement_notes: '', informal_proof: '', proof_is_current: false },
});

describe('model reducer', () => {
  it('loads a snapshot and applies job / dossier / settings events', () => {
    const m = emptyModel();
    loadSnapshot(m, { local: true, demo: true, brain: 'fake', version: 'v', host_name: 'h', device: null, settings: { language: 'fr' } as never,
      host_only_settings: ['lan_listener'], projects: [], dossiers: [], jobs: { active: [job('j1', 'running')], recent: [] }, models: null as never,
      system: null as never, library: { count: 2 }, updates: null as never, jupyter: null as never, lang: 'fr', seq: 1, boot: 1, migration: {} } as unknown as StateSnapshot);
    expect(m.loaded).toBe(true);
    expect(activeJobFor(m, 'd1')?.id).toBe('j1');
    applyEvent(m, e({ type: 'job.updated', job: job('j1', 'done') }));
    expect(activeJobFor(m, 'd1')).toBeUndefined();
    applyEvent(m, e({ type: 'dossier.updated', dossier: dossier('d1', 'proved') }));
    expect(m.dossiers['d1']!.proved).toBe(true);
    expect(m.full['d1']!.status).toBe('proved');
    applyEvent(m, e({ type: 'dossier.deleted', id: 'd1' }));
    expect(m.dossiers['d1']).toBeUndefined();
    applyEvent(m, e({ type: 'library.updated', added: 'x' }));
    expect(m.libraryCount).toBe(3);
    expect(applyEvent(m, e({ type: 'plugin.thing' }))).toBe(false);
  });
  it('keeps at most MAX_FINISHED_JOBS finished jobs', () => {
    const m = emptyModel();
    for (let i = 0; i < MAX_FINISHED_JOBS + 30; i++) applyEvent(m, e({ type: 'job.updated', job: job(`j${i}`, 'done', 'd', i) }));
    applyEvent(m, e({ type: 'job.updated', job: job('live', 'running') }));
    expect(Object.keys(m.jobs).length).toBe(MAX_FINISHED_JOBS + 1);
    expect(m.jobs['j0']).toBeUndefined();
  });
});
