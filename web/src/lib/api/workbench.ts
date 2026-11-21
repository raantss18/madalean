// Session S-M endpoints (docs/API.md « Calcul, library catalogue, glossary, spending »): kept apart from client.ts so
// the parallel sessions do not edit the same file.
import { request } from './client';

const enc = encodeURIComponent;

export interface RichOut { mime: 'text/latex' | 'image/png' | 'image/svg+xml'; data?: string; asset?: string }
export interface CalcRun { id: string; t: number; status: string; seconds: number; stdout: string; stderr: string; result: string;
  error: string; rich: RichOut[]; device: string; code_hash: string; sandbox: string; language: string }
export interface CalcCell { id: string; language: 'sage' | 'python'; code: string; code_hash: string; origin: 'user' | 'assistant';
  approved: { hash: string; t: number; device: string } | null; created: number; updated: number; model: string; note: string;
  versions: { code: string; t: number; origin: string }[]; runs: CalcRun[] }
export interface CalcStatus { available: Record<string, boolean>; sandbox: string; auto: boolean; remote_allowed: boolean; local: boolean; running: boolean }
export interface CalcSheet { sheet: { project_id: string; cells: CalcCell[]; rev: number }; trash: { id: string; code: string }[]; status: CalcStatus }
export type CalcTarget = 'conjecture' | 'note' | 'dossier' | 'article';

export interface CatalogEntry { name: string; title: string; statement: string; nl: string; code: string; workspace: string;
  dossier: string; t: number; project_id: string; project: string; domain: string; domain_auto: string; domain_manual: boolean;
  tags: string[]; status: 'verified' | 'conditional'; admitted: string[]; model: string; by_user: boolean; axioms: string[] | null;
  uses: string[]; used_by: string[] }

export interface SpendSummary { month: string; spent_month: number; cap_month: number; cap_proof: number; calls_month: number;
  by_model: Record<string, number>; recent: { ts: number; model: string; scope: string; tokens_in: number; tokens_out: number;
    cache_read: number; cache_write: number; usd: number }[];
  prices: Record<string, { input: number; output: number; cache_read: number; cache_write: number }>;
  enabled: boolean; key_set: boolean; model: string; models: { key: string; name: string }[] }

export interface DepsComponent { component: string; title?: string; state?: string; installed?: boolean; version?: string; [k: string]: unknown }

export const wb = {
  calc: (pid: string) => request<CalcSheet>('GET', `/calcul/${enc(pid)}`),
  addCell: (pid: string, code: string, language: string, after = '') =>
    request<{ cell: CalcCell }>('POST', `/calcul/${enc(pid)}/cells`, { code, language, after }),
  editCell: (pid: string, cid: string, patch: { code?: string; language?: string; note?: string }) =>
    request<{ cell: CalcCell }>('PATCH', `/calcul/${enc(pid)}/cells/${enc(cid)}`, patch),
  deleteCell: (pid: string, cid: string) => request<{ removed: string }>('DELETE', `/calcul/${enc(pid)}/cells/${enc(cid)}`),
  restoreCell: (pid: string, cid: string) => request<{ cell: CalcCell }>('POST', `/calcul/${enc(pid)}/cells/${enc(cid)}/restore`, {}),
  moveCell: (pid: string, cid: string, to: number) => request<{ order: string[] }>('POST', `/calcul/${enc(pid)}/cells/${enc(cid)}/move`, { to }),
  approveCell: (pid: string, cid: string, code_hash: string) =>
    request<{ cell: CalcCell }>('POST', `/calcul/${enc(pid)}/cells/${enc(cid)}/approve`, { code_hash }),
  runCell: (pid: string, cid: string, timeout = 60) => request<{ run: CalcRun }>('POST', `/calcul/${enc(pid)}/cells/${enc(cid)}/run`, { timeout }),
  interrupt: (pid: string) => request<{ interrupted: boolean }>('POST', `/calcul/${enc(pid)}/interrupt`, {}),
  assist: (pid: string, body: { action: 'write' | 'fix' | 'explain'; cell_id?: string; prompt?: string; language?: string; after?: string }) =>
    request<{ cell?: CalcCell; text?: string; model: string; approval_required?: boolean }>('POST', `/calcul/${enc(pid)}/assist`, body),
  sendTo: (pid: string, cid: string, target: CalcTarget, text = '', title = '') =>
    request<Record<string, unknown>>('POST', `/calcul/${enc(pid)}/cells/${enc(cid)}/to`, { target, text, title }),
  assetUrl: (aid: string) => `/api/calcul/assets/${enc(aid)}`,

  catalog: () => request<{ entries: CatalogEntry[]; domains: string[] }>('GET', '/library/catalog'),
  libraryMeta: (name: string, patch: { domain?: string; tags?: string[] }) =>
    request<{ name: string; meta: { domain?: string; tags?: string[] } }>('PATCH', `/library/meta/${enc(name)}`, patch),
  catalogExportUrl: (format: 'md' | 'json' | 'lean', name = '') => `/api/library/catalog/export?format=${format}${name ? `&name=${enc(name)}` : ''}`,

  glossaryUses: (term: string) => request<{ term: string; dossiers: { id: string; title: string; project_id: string; status: string; in: string }[] }>(
    'GET', `/glossary/uses?term=${enc(term)}`),

  spend: () => request<SpendSummary>('GET', '/models/spend'),
  deps: () => request<{ components?: DepsComponent[]; jobs?: Record<string, { running?: boolean; phase?: string; done?: number; total?: number; message?: string }> }>('GET', '/deps'),
  installDep: (name: string) => request<{ component: string; started: boolean }>('POST', `/deps/${enc(name)}/install`, {}),
};
