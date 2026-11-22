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

// ---------------------------------------------------------------- S-P: Calcul notebooks (docs/CALCUL.md)
export type NbCellType = 'code' | 'ask' | 'markdown' | 'figure';
export interface NbOutput { type: 'stream' | 'error' | 'result' | 'display'; name?: string; text?: string; ename?: string; evalue?: string;
  traceback?: string; data?: Record<string, unknown>; approx?: string }
export interface NbRunMeta { status: string; seconds: number; t: number; code_hash: string; upstream: string; kernel: string }
export interface NbCell { id: string; type: NbCellType; language: 'sage' | 'python'; source: string; collapsed: boolean; outputs_hidden: boolean;
  code?: string; code_hash?: string; origin?: 'user' | 'assistant'; model?: string; approved?: { hash: string; t: number; device: string } | null;
  prompt?: string; versions?: { code: string; t: number; origin: string }[]; runs?: { id: string; t: number; status: string; seconds: number }[];
  exec_count?: number | null; outputs?: NbOutput[]; last?: NbRunMeta | null; stale?: boolean; stale_reason?: string; fresh?: boolean;
  autofix?: { t: number; model: string; n?: number; max?: number; reran?: boolean } | null; uses?: string[]; figure?: Record<string, unknown>; svg?: { asset: string };
  // S-AG: what the request was recognized as, its intent key, where the code came from (catalogue | best | model | variant | fix | recipe)
  recognized?: { fr: string; en: string } | null; intent_key?: string; gen?: string }
export interface NbDocInfo { id: string; title: string; language: 'sage' | 'python'; path: string; cells?: number; updated?: number; engine?: { name: string; version: string } | null; rev?: number }
export interface NbKernel { kernel: string; state: string; shared?: boolean; name?: string; sandboxed?: boolean; connections?: number }
// S-AO (D47): the kernel prepared in advance when the document (or its project) is opened
export interface NbWarm { state: 'none' | 'off' | 'starting' | 'warming' | 'ready' | 'failed' | 'skipped'; start_s?: number; steps?: Record<string, number | 'error'>; used?: boolean; error?: string; seconds?: number }
export interface NbStatus extends CalcStatus { kernel: NbKernel; idle_minutes: number; warm?: NbWarm }
export interface NbView { doc: NbDocInfo; cells: NbCell[]; trash: { id: string; source: string }[]; status: NbStatus }
export interface NbRunResult { runs: Record<string, CalcRun & { outputs: NbOutput[] }>; stopped: { cell_id: string; reason: string } | null; autofix: NbCell | null }

export interface NbExplainError { explanation: string; fix: string; fix_valid: boolean; model: string }
export interface NbExplainLine { line: number; code: string; text: string }
// S-AJ (D42): the steps of a computation; facts computed by Sage (verified = a check passed, computed = a value)
export interface NbStepFact { key: string; text: string; status: 'verified' | 'computed' | 'failed' }
export interface NbExplainSteps { text: string; facts: NbStepFact[]; verified: boolean; reason: string; op: string; model: string; cached: boolean }

const D = (pid: string, doc: string) => `/calcul/${enc(pid)}/docs/${enc(doc)}`;
export const nb = {
  docs: (pid: string) => request<{ docs: NbDocInfo[] }>('GET', `/calcul/${enc(pid)}/docs`),
  warm: (pid: string, doc?: string) => request<{ warm: NbWarm; doc: string | null }>('POST', `/calcul/${enc(pid)}/warm`, doc ? { doc } : {}),
  createDoc: (pid: string, title: string, language: 'sage' | 'python') => request<{ doc: NbDocInfo }>('POST', `/calcul/${enc(pid)}/docs`, { title, language }),
  renameDoc: (pid: string, doc: string, title: string) => request<{ doc: NbDocInfo }>('PATCH', D(pid, doc), { title }),
  deleteDoc: (pid: string, doc: string) => request<{ removed: string }>('DELETE', D(pid, doc)),
  get: (pid: string, doc: string) => request<NbView>('GET', D(pid, doc)),
  add: (pid: string, doc: string, body: { type: NbCellType; source?: string; prompt?: string; figure?: unknown; svg?: string; after?: string; at?: number }) =>
    request<{ cell: NbCell }>('POST', `${D(pid, doc)}/cells`, body),
  edit: (pid: string, doc: string, cid: string, patch: Record<string, unknown>) => request<{ cell: NbCell }>('PATCH', `${D(pid, doc)}/cells/${enc(cid)}`, patch),
  remove: (pid: string, doc: string, cid: string) => request<{ removed: string }>('DELETE', `${D(pid, doc)}/cells/${enc(cid)}`),
  restore: (pid: string, doc: string, cid: string) => request<{ cell: NbCell }>('POST', `${D(pid, doc)}/cells/${enc(cid)}/restore`, {}),
  move: (pid: string, doc: string, cid: string, to: number) => request<{ order: string[] }>('POST', `${D(pid, doc)}/cells/${enc(cid)}/move`, { to }),
  approve: (pid: string, doc: string, cid: string, code_hash: string) => request<{ cell: NbCell }>('POST', `${D(pid, doc)}/cells/${enc(cid)}/approve`, { code_hash }),
  run: (pid: string, doc: string, body: { cells?: string[]; until?: string; from?: string; all?: boolean; timeout?: number }) =>
    request<NbRunResult>('POST', `${D(pid, doc)}/run`, body),
  ask: (pid: string, doc: string, cid: string, prompt: string, variant = false) => request<{ cell: NbCell; model: string; approval_required: boolean; origin?: string; coverage?: string; recipe?: string }>('POST', `${D(pid, doc)}/cells/${enc(cid)}/ask`, variant ? { prompt, variant: true } : { prompt }),
  kernel: (pid: string, doc: string, action: 'interrupt' | 'restart' | 'shutdown' | 'clear') => request<Record<string, unknown>>('POST', `${D(pid, doc)}/${action}`, {}),
  variables: (pid: string, doc: string) => request<{ names: { name: string; type: string; value: string }[] }>('GET', `${D(pid, doc)}/variables`),
  explain: (pid: string, doc: string, cell_id: string) => request<{ text: string; model: string }>('POST', `${D(pid, doc)}/assist`, { action: 'explain', cell_id }),
  // S-AB: code or request? · « Expliquer l'erreur » / « ligne par ligne » · apply a proposed fix (model code: approval)
  detect: (pid: string, doc: string, text: string) => request<{ kind: 'code' | 'ask'; why: string }>('POST', `${D(pid, doc)}/detect`, { text }),
  explainError: (pid: string, doc: string, cid: string) => request<NbExplainError>('POST', `${D(pid, doc)}/cells/${enc(cid)}/explain`, { mode: 'error' }),
  explainLines: (pid: string, doc: string, cid: string) => request<{ lines: NbExplainLine[]; model: string }>('POST', `${D(pid, doc)}/cells/${enc(cid)}/explain`, { mode: 'lines' }),
  explainSteps: (pid: string, doc: string, cid: string) => request<NbExplainSteps>('POST', `${D(pid, doc)}/cells/${enc(cid)}/explain`, { mode: 'steps' }),
  suggestion: (pid: string, doc: string, cid: string, code: string, model: string) => request<{ cell: NbCell; approval_required: boolean }>('POST', `${D(pid, doc)}/cells/${enc(cid)}/suggestion`, { code, model }),
  sendTo: (pid: string, doc: string, cid: string, body: { target: CalcTarget; text?: string; title?: string; png?: string; asset?: string }) =>
    request<Record<string, unknown>>('POST', `${D(pid, doc)}/cells/${enc(cid)}/to`, body),
  ipynbUrl: (pid: string, doc: string) => `/api${D(pid, doc)}/ipynb`,
  labUrl: (path: string) => `/jupyter/lab/tree/${path.split('/').map(enc).join('/')}`,
};
