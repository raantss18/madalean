// Session S-BC endpoints (docs/API.md « Préparer pour Mathlib », DECISIONS D61). Kept apart from client.ts so the
// parallel sessions do not edit the same file.
import { request } from './client';

export type MlSource = { kind: 'library' | 'dossier'; id: string };
export type MlStepState = 'pending' | 'running' | 'ok' | 'warn' | 'fail';
export interface MlStep { id: 'port' | 'mathlib' | 'name' | 'imports' | 'final' | 'lint'; state: MlStepState; params: Record<string, unknown> }
export interface MlCheck { id: string; ok: boolean | null; severity: 'ok' | 'unknown' | 'warning' | 'error'; params: Record<string, unknown> }
export interface MlPackage {
  key: string; state: 'running' | 'ready' | 'in_mathlib' | 'port_failed' | 'failed' | 'stopped'; t: number; error: string;
  source: { kind: string; id: string; title: string; workspace: string; main: string; dossier: string };
  author: string; steps: MlStep[];
  port: { from: string; to: string; renames: { old: string; new: string }[]; syntax: string[]; ok: boolean; errors: string;
    lean: { lean: string; mathlib: string } } | null;
  in_mathlib: { lemma: string; tactic: string; used: string } | null;
  name: { name: string; namespace: string; full: string; original: string; free: boolean | null; taken?: string;
    fallback: boolean; rules: string[]; words: { token: string; word: string; part: string }[] } | null;
  checks: MlCheck[]; imports: string[];
  file: { path: string; text: string } | null;
  target: { closest: string; closest_path: string; module: string; path: string } | null;
  pr: { title: string; body: string; explain: { fr: string; en: string } } | null;
  links: { id: string; url: string }[];
  github?: { branch?: { fork: string; branch: string; branch_url: string; compare_url: string }; pr?: { number: number; url: string } };
}
export interface MlState { package: MlPackage | null; running: boolean; github: { configured: boolean; host: boolean }; default_author: string }
export interface MlPlan {
  id: string; kind: 'branch' | 'pr'; login: string; fork: string; branch: string; path?: string; content?: string;
  requests: { method: string; url: string; body?: Record<string, unknown> }[];
}

const q = (s: MlSource) => `kind=${encodeURIComponent(s.kind)}&id=${encodeURIComponent(s.id)}`;

export const mathlib = {
  get: (s: MlSource) => request<MlState>('GET', `/mathlib/contrib?${q(s)}`),
  start: (s: MlSource, author: string) => request<MlState>('POST', '/mathlib/contrib', { ...s, author }),
  fileUrl: (s: MlSource) => `/api/mathlib/contrib/file?${q(s)}`,
  reprove: (s: MlSource) => request<{ dossier: string; job: string }>('POST', '/mathlib/contrib/reprove', s),
  plan: (s: MlSource, step: 'branch' | 'pr') => request<{ plan: MlPlan }>('POST', '/mathlib/contrib/github/plan', { ...s, step }),
  send: (s: MlSource, plan: string) =>
    request<{ result: Record<string, unknown>; package: MlPackage }>('POST', '/mathlib/contrib/github/send', { ...s, plan }),
};
