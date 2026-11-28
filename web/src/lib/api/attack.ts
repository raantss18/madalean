// « Attaque » — Left to Solve open problems (docs/ATTACK.md, DECISIONS D69 / D70). Kept apart from client.ts so the
// parallel sessions do not edit the same file. The server side (S-BJ) is built against the same contract.
import { request } from './client';

export type AttackState = 'off' | 'setup' | 'running' | 'paused' | 'budget' | 'error';
export type WorkspaceState = 'none' | 'downloading' | 'building' | 'ready' | 'error';
/** What Madalean looks for (settings `attack_kinds`). */
export type AttackKind = 'known' | 'counterexample' | 'open' | 'formalize';
export const ATTACK_KINDS: AttackKind[] = ['known', 'counterexample', 'open', 'formalize'];

export interface AttackCurrent {
  problem: string; title: string; kind: string; difficulty: number | null; dossier_id: string;
  phase: string; since: number; lease?: number | string | null;
}
export interface AttackStatus {
  state: AttackState; reason: string;
  today: { usd: number; cap: number; taken: number; proofs: number; released: number };
  workspace: { state: WorkspaceState; commit: string; size: number; progress: number };
  current: AttackCurrent[]; queue: number;
}
/** One local check: the contract leaves the shape open; a boolean, a string or `{ok, detail}` are all read. */
export type CheckValue = boolean | null | string | string[] | { ok?: boolean | null; detail?: string; text?: string; axioms?: string[] };
export interface PlanRequest { method: string; url: string; body?: Record<string, unknown> }
export interface AttackSubmission {
  id: string; problem: string; title: string; kind: 'proof' | 'disproof' | 'reduction' | 'statement';
  file: string | { path?: string; text: string };
  check: { local: CheckValue; rules: CheckValue; axioms: CheckValue };
  plan: { requests: PlanRequest[]; login?: string; repo?: string; fork?: string; branch?: string; path?: string; title?: string };
  state: 'ready' | 'sent' | 'merged' | 'rejected' | 'expired'; pr_url: string; created: number;
  dossier_id?: string;
}
export type Outcome = 'solved' | 'released' | 'reduced' | 'submitted' | 'rejected';
export interface AttackHistoryItem {
  problem: string; title: string; kind: string; outcome: Outcome; reason: string; t: number; usd: number; dossier_id: string;
}
export interface AttackSettings {
  attack_enabled?: boolean; attack_kinds?: AttackKind[]; attack_usd_per_day?: number; attack_parallel?: number;
  attack_max_difficulty_open?: number; attack_team_notes?: boolean;
}

export const attack = {
  get: () => request<AttackStatus>('GET', '/attack'),
  start: () => request<AttackStatus>('POST', '/attack/start'),
  stop: () => request<AttackStatus>('POST', '/attack/stop'),
  workspace: () => request<AttackStatus>('POST', '/attack/workspace', { accept: true }),
  submissions: () => request<AttackSubmission[]>('GET', '/attack/submissions'),
  send: (id: string) => request<AttackSubmission>('POST', `/attack/submissions/${encodeURIComponent(id)}/send`),
  discard: (id: string) => request<AttackSubmission>('POST', `/attack/submissions/${encodeURIComponent(id)}/discard`),
  history: () => request<AttackHistoryItem[]>('GET', '/attack/history'),
  settings: (patch: AttackSettings) => request<AttackSettings>('PATCH', '/attack/settings', patch),
};
