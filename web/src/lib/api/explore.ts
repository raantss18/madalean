// Typed client of the « Moteur de conjectures » (docs/CONJECTURES.md, docs/API.md §Conjecture engine; session S-AW).
// Approving model-written code uses Calcul's own endpoint (lib/api/workbench.ts `nb.approve`): the experiment is a
// cell of the project's « explorations » notebook, so the approval rule is literally the same.
import { request } from './client';
import type { Job } from './types';

const enc = encodeURIComponent;

export type StepName = 'explore' | 'recognise' | 'state' | 'attack';
export type StepState = 'todo' | 'running' | 'awaiting_approval' | 'done' | 'failed' | 'stopped';
export interface Step { state: StepState; error: string; seconds: number; detail?: string; candidate?: string }
export interface Bilingual { fr: string; en: string }

export interface Finding {
  kind: string; status: 'kept' | 'discarded'; columns: string[]; params: Record<string, unknown>;
  tested: { from?: number; to?: number; cases?: number; fit?: number; held_out?: number };
  reason: string; detail: Record<string, unknown> & { sage?: { ogf?: string; agrees?: boolean | null; error?: string } }; heuristic: boolean;
}
export interface Strength extends Bilingual { kind: 'tested' | 'heuristic' | 'oeis'; from: number; to: number; cases: number }
export interface Counterexample {
  witness: Record<string, unknown>; detail: Record<string, unknown>; sage: boolean; lean: boolean | null; verified: boolean; t: number;
  lean_check: { ok: boolean; code?: string; errors?: string[]; unsupported?: boolean } | null;
}
export type CandidateStatus = 'candidate' | 'kept' | 'survived' | 'refuted' | 'disputed' | 'discarded';
export interface Candidate {
  id: string; kind: string; columns: string[]; finding: Finding; text: Bilingual; lean: string | null; lean_ok: boolean | null;
  lean_error: string; strength: Strength; status: CandidateStatus; conjecture_id: string;
  duplicate_of: { id: string; title: string } | null; counterexample: Counterexample | null;
  hunt: { cases: number; to: number; max: number; sparse: boolean; seconds: number } | null; hunting?: boolean;
}
export interface OeisMatch { number: string; name: string; offset: number; keywords: string[]; formulas: string[]; url: string; data: string[]; matched: number; shift?: number; differs_at?: number }
export interface OeisResult { status: 'ok' | 'none' | 'off' | 'too_short' | 'error' | 'unrecorded'; matches: OeisMatch[]; rejected: OeisMatch[]; url: string; cached: boolean; error: string }
export interface JournalEntry extends Bilingual { t: number; step: string; kind: string; data: Record<string, unknown> }
export interface ExploreTable { columns: string[]; rows: string[][]; total?: number; labels?: boolean }
export interface Exploration {
  id: string; project_id: string; question: string; created: number; updated: number; language: 'sage' | 'python' | '';
  origin: 'catalogue' | 'model' | 'data' | 'user' | '';
  intent: { kind?: string; recognised?: boolean; summary?: string; family?: string; sequences?: { name: string; latex: string; fr: string; en: string }[] };
  cell: { doc: string; id: string; code_hash: string; origin: string } | null; code: string; model: string;
  steps: Record<StepName, Step>; table: ExploreTable | null; oeis: Record<string, OeisResult>; findings: Finding[];
  candidates: Candidate[]; journal: JournalEntry[]; lmfdb: string;
}
export interface ExploreBrief {
  id: string; project_id: string; question: string; created: number; updated: number; origin: string;
  steps: Record<StepName, StepState>; candidates: number; refuted: number; summary: string;
}
export interface ExploreCell { doc: string; id: string; code: string; code_hash: string; origin: 'user' | 'assistant'; model: string; approved: boolean; may_run: boolean; language: string }
export interface ExploreView { exploration: Exploration; cell: ExploreCell | null; running: boolean; exec_allowed: boolean }
export interface ExploreStatus {
  available: { sage?: boolean; python?: boolean }; auto: boolean; remote_allowed: boolean; demo: boolean; oeis: 'on' | 'off';
  lmfdb: string; mode: string; examples: Bilingual[]; local: boolean;
}

const X = (xid: string) => `/explorations/${enc(xid)}`;
const C = (xid: string, cid: string) => `${X(xid)}/candidates/${enc(cid)}`;

export const explore = {
  status: (pid: string) => request<ExploreStatus>('GET', `/explore/status?project=${enc(pid)}`),
  list: (pid: string) => request<{ explorations: ExploreBrief[] }>('GET', `/projects/${enc(pid)}/explorations`),
  create: (pid: string, question: string, language = '') => request<ExploreView>('POST', `/projects/${enc(pid)}/explorations`, { question, language }),
  get: (xid: string) => request<ExploreView>('GET', X(xid)),
  setCode: (xid: string, code: string) => request<ExploreView>('PATCH', X(xid), { code }),
  remove: (xid: string) => request<{ deleted: boolean }>('DELETE', X(xid)),
  run: (xid: string) => request<ExploreView & { started: boolean }>('POST', `${X(xid)}/run`, {}),
  stop: (xid: string) => request<ExploreView>('POST', `${X(xid)}/stop`, {}),
  warm: (xid: string) => request<{ warm: unknown }>('POST', `${X(xid)}/warm`, {}),
  exportTo: (xid: string, to: 'note' | 'article') => request<ExploreView & { note_id?: string; article?: boolean }>('POST', `${X(xid)}/export`, { to }),
  keep: (xid: string, cid: string) => request<ExploreView & { conjecture_id: string; duplicate: boolean }>('POST', `${C(xid, cid)}/keep`, {}),
  discard: (xid: string, cid: string, reason = '') => request<ExploreView>('POST', `${C(xid, cid)}/discard`, { reason }),
  attack: (xid: string, cid: string) => request<ExploreView & { started: boolean }>('POST', `${C(xid, cid)}/attack`, {}),
  prove: (xid: string, cid: string) => request<ExploreView & { job: Job; conjecture_id: string }>('POST', `${C(xid, cid)}/prove`, {}),
};
