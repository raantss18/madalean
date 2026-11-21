// « Consigne de recherche », suggestions, one search across a project (session S-Q; server:
// madalean/server/plugins/research_agent.py).
import { request } from './client';

const enc = encodeURIComponent;

export type SuggestionType = 'correction' | 'exemple' | 'figure' | 'generalisation' | 'verification';
export const SUGGESTION_TYPES: SuggestionType[] = ['correction', 'exemple', 'figure', 'generalisation', 'verification'];

export interface ConsigneStep { id: string; kind: string; status: 'todo' | 'running' | 'done' | 'failed'; targets: { kind: string; number: string }[]; result: Record<string, unknown>; started: number; ended: number }
export interface ConsigneRun {
  id: string; project_id: string; instruction: string;
  source: { shelf: string; id: string; key: string; title: string };
  limits: { max_steps: number; max_minutes: number; max_cost_usd: number; max_targets: number; max_suggestions: number };
  mode: string; steps: ConsigneStep[];
  status: 'planned' | 'running' | 'paused' | 'done' | 'stopped' | 'cancelled' | 'failed';
  stopped_by?: string; paused_reason?: string; error?: string;
  spent: { seconds: number; cost_usd: number; model_calls: number; steps: number };
  journal_note: string; suggestions: string[]; jobs: string[]; dossiers: string[]; conjectures: string[]; cells: string[];
  created: number; updated: number;
}
export interface LeanEvidence { dossier_id: string; title?: string; kind?: string; statement_ok?: boolean; proved?: boolean; running?: boolean; vacuous?: boolean; lean?: string }
export interface CalcEvidence { cell_id: string; code?: string; approved?: boolean; run?: { ok: boolean; text: string; error: string; assets: string[] } | null }
export interface Citation { key?: string; locator?: string; title?: string; url?: string; year?: string | number; quote?: string }
export interface Suggestion {
  id: string; run_id: string; project_id: string; type: SuggestionType; title: string;
  before: string; after: string; rationale: string; touches_math: boolean;
  target: { mode: 'replace_excerpt' | 'insert_after' | 'add_dossier'; block_id?: string; dossier_id?: string; near?: string };
  evidence: { lean?: LeanEvidence[]; calcul?: CalcEvidence[]; citations?: Citation[] };
  status: 'proposed' | 'accepted' | 'rejected' | 'stale'; created: number; decided: number; model: string;
  conjecture?: boolean; proved?: boolean; after_if_proved?: string;
}
export interface SearchResult { kind: 'dossier' | 'note' | 'calcul' | 'figure' | 'passage' | 'suggestion'; id: string; title: string; snippet: string; status?: string; type?: string; source_id?: string; source_key?: string; page?: number | null; assets?: string[] }
export interface Basket { dossiers: string[]; notes: string[]; calcul: string[] }

const base = (pid: string) => `/research/projects/${enc(pid)}`;

export const consigne = {
  plan: (pid: string, p: { source: { shelf?: string; id: string }; instruction: string; limits?: Partial<ConsigneRun['limits']> }) =>
    request<{ run: ConsigneRun }>('POST', `${base(pid)}/consignes`, { ...p, dry_run: true }),
  start: (pid: string, p: { source: { shelf?: string; id: string }; instruction: string; limits?: Partial<ConsigneRun['limits']> }) =>
    request<{ run: ConsigneRun }>('POST', `${base(pid)}/consignes`, p),
  runs: (pid: string) => request<{ runs: ConsigneRun[] }>('GET', `${base(pid)}/consignes`),
  cancel: (pid: string, rid: string) => request<{ run: ConsigneRun }>('POST', `${base(pid)}/consignes/${enc(rid)}/cancel`, {}),
  resume: (pid: string, rid: string, limits?: Partial<ConsigneRun['limits']>) => request<{ run: ConsigneRun }>('POST', `${base(pid)}/consignes/${enc(rid)}/resume`, limits ? { limits } : {}),
  suggestions: (pid: string, type = '', status = '') =>
    request<{ suggestions: Suggestion[]; counts: Record<string, number> }>('GET', `${base(pid)}/suggestions?type=${enc(type)}&status=${enc(status)}`),
  accept: (pid: string, sid: string, after?: string) => request<{ suggestion: Suggestion }>('POST', `${base(pid)}/suggestions/${enc(sid)}/accept`, after !== undefined ? { after } : {}),
  reject: (pid: string, sid: string) => request<{ suggestion: Suggestion }>('POST', `${base(pid)}/suggestions/${enc(sid)}/reject`, {}),
  search: (pid: string, q: string) => request<{ results: SearchResult[] }>('GET', `${base(pid)}/search?q=${enc(q)}`),
  toArticle: (pid: string, p: { kind: string; id: string; source_key?: string; text?: string; locator?: string; title?: string }) =>
    request<{ block: unknown }>('POST', `${base(pid)}/to-article`, p),
  basket: (pid: string) => request<{ basket: Basket }>('GET', `${base(pid)}/basket`),
  toBasket: (pid: string, kind: string, id: string, remove = false) => request<{ basket: Basket }>('POST', `${base(pid)}/basket`, { kind, id, remove }),
};
