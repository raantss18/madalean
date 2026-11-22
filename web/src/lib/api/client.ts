// Typed HTTP client for docs/API.md. One place for: JSON, errors, 401 handling, aborts, downloads.
import type {
  CheckResult, ConductorAsk, Device, LeanExplainAnswer, LeanExplainWhere, Dossier, DossierSummary, FollowStage, Hello, Job,
  JupyterStatus, LibEntry, Mode,
  LeaderboardRow, ModelsInfo, Rankings, Project, Settings, Stage, StateSnapshot, Strategy, SystemInfo, UpdatesStatus, UsageStatus, VersionKind,
} from './types';

export class ApiError extends Error {
  constructor(
    public status: number,
    public kind: string,
    public body: Record<string, unknown>,
  ) {
    super(`${status} ${kind}`);
  }
  /** Server-provided localized text, when any. */
  get serverText(): string {
    const m = this.body['message'] as { text?: string } | undefined;
    return typeof m?.text === 'string' ? m.text : '';
  }
}

export type Fetcher = typeof fetch;
let fetcher: Fetcher = (...a) => fetch(...a);
/** Called once on 401 (remote listener: token revoked or missing). */
let onUnauthorized: () => void = () => {
  if (typeof location !== 'undefined' && !location.pathname.startsWith('/pair')) location.assign('/pair?reason=auth');
};
export function configureClient(opts: { fetcher?: Fetcher; onUnauthorized?: () => void }): void {
  if (opts.fetcher) fetcher = opts.fetcher;
  if (opts.onUnauthorized) onUnauthorized = opts.onUnauthorized;
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE';
export interface ReqOpts { signal?: AbortSignal; allow401?: boolean }

export async function request<T>(method: Method, path: string, body?: unknown, opts: ReqOpts = {}): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin', signal: opts.signal, headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)['Content-Type'] = 'application/json';
  }
  let res: Response;
  try {
    res = await fetcher(`/api${path}`, init);
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'network', {});
  }
  let data: Record<string, unknown> = {};
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text) as Record<string, unknown>; } catch { data = { raw: text }; }
  }
  if (!res.ok) {
    const kind = typeof data['error'] === 'string' ? (data['error'] as string) : `http_${res.status}`;
    if (res.status === 401 && !opts.allow401) onUnauthorized();
    throw new ApiError(res.status, kind, data);
  }
  return data as T;
}

const enc = encodeURIComponent;

export const api = {
  hello: (o?: ReqOpts) => request<Hello>('GET', '/hello', undefined, { ...o, allow401: true }),
  state: (o?: ReqOpts) => request<StateSnapshot>('GET', '/state', undefined, o),
  pair: (code: string, device_name: string) =>
    request<{ token: string; device: Device }>('POST', '/pair', { code, device_name }, { allow401: true }),
  logout: () => request<{ ok: boolean }>('POST', '/logout', {}, { allow401: true }),
  /** Revokes this device (docs/SHELLS.md §8); falls back to /logout when the server does not have it yet. */
  forgetSelf: async () => {
    try { await request<unknown>('POST', '/devices/self/forget', {}, { allow401: true }); }
    catch (e) { if (e instanceof ApiError && (e.status === 404 || e.status === 405 || e.status === 401)) await request('POST', '/logout', {}, { allow401: true }); else throw e; }
  },
  pairingStart: () => request<{ code: string; expires: number; expires_in: number; remote_url?: string | null;
    addresses?: { host: string | null; ip: string | null; lan: string[] } }>('POST', '/pairing/start', {}),
  pairing: () => request<{ active: boolean; expires_in: number; locked_for: number }>('GET', '/pairing'),
  devices: () => request<{ devices: Device[]; apps?: Device[]; browsers?: Device[]; browser_idle_minutes?: number }>('GET', '/devices'),
  revokeDevice: (id: string) => request<{ ok: boolean }>('DELETE', `/devices/${enc(id)}`),

  patchSettings: (patch: Partial<Settings> | Record<string, unknown>) =>
    request<{ settings: Settings }>('PATCH', '/settings', patch),

  projects: () => request<{ projects: Project[] }>('GET', '/projects'),
  createProject: (p: { title: string; description?: string; workspace?: string }) =>
    request<{ project: Project }>('POST', '/projects', p),
  patchProject: (id: string, p: Partial<Project>) => request<{ project: Project }>('PATCH', `/projects/${enc(id)}`, p),
  deleteProject: (id: string) => request<{ ok: boolean; undo: string }>('DELETE', `/projects/${enc(id)}`),
  restoreProject: (id: string) => request<{ project: Project }>('POST', `/projects/${enc(id)}/restore`, {}),

  dossiers: (project?: string) =>
    request<{ dossiers: DossierSummary[] }>('GET', `/dossiers${project !== undefined ? `?project=${enc(project)}` : ''}`),
  dossier: (id: string, o?: ReqOpts) =>
    request<{ dossier: Dossier; job: Job | null; children: DossierSummary[] }>('GET', `/dossiers/${enc(id)}`, undefined, o),
  createDossier: (d: { problem?: string; statement?: string; title?: string; project_id?: string; workspace?: string;
    kind?: string; parent_id?: string; start?: boolean; mode?: Mode; strategy?: Strategy; rename?: boolean }) =>
    request<{ dossier: Dossier; job: Job | null }>('POST', '/dossiers', d),
  patchDossier: (id: string, p: Record<string, unknown>) => request<{ dossier: Dossier }>('PATCH', `/dossiers/${enc(id)}`, p),
  deleteDossier: (id: string) => request<{ ok: boolean; undo: string }>('DELETE', `/dossiers/${enc(id)}`),
  restoreDossier: (id: string) => request<{ dossier: Dossier }>('POST', `/dossiers/${enc(id)}/restore`, {}),
  message: (id: string, text: string, stage: FollowStage, extra: { mode?: Mode; strategy?: Strategy } = {}) =>
    request<{ job: Job; stage: FollowStage }>('POST', `/dossiers/${enc(id)}/message`, { text, stage, ...extra }),
  setStatement: (id: string, code: string, check = true) =>
    request<{ dossier: Dossier; check: CheckResult | null }>('POST', `/dossiers/${enc(id)}/statement`, { code, check }),
  checkDossier: (id: string, what?: 'statement' | 'proof', o?: ReqOpts) =>
    request<{ what: string; check: CheckResult }>('POST', `/dossiers/${enc(id)}/check`, what ? { what } : {}, o),
  /** « Vérifier l'énoncé » (S-K): the verdict arrives as a `check` event in the thread. */
  verify: (id: string, learn = false, extra: { mode?: Mode } = {}) =>
    request<{ job: Job }>('POST', `/dossiers/${enc(id)}/verify`, { learn, ...extra }),
  run: (id: string, plan: (Stage | { stage: Stage; request?: string; force?: boolean; learn?: boolean })[], extra: { mode?: Mode; strategy?: Strategy } = {}) =>
    request<{ job: Job }>('POST', `/dossiers/${enc(id)}/run`, { plan, ...extra }),
  stop: (id: string) => request<{ stopped: boolean }>('POST', `/dossiers/${enc(id)}/stop`, {}),
  /** Manual edit as a new user version (proof re-checked strictly by Lean). */
  saveVersion: (id: string, kind: 'proof' | 'explanation' | 'informal' | 'notes', code: string, check = true) =>
    request<{ dossier: Dossier; check: CheckResult | null }>('POST', `/dossiers/${enc(id)}/versions/${kind}`, { code, check }),
  restoreVersion: (id: string, kind: VersionKind, index: number) =>
    request<{ dossier: Dossier }>('POST', `/dossiers/${enc(id)}/versions/${kind}/${index}/restore`, {}),
  dossierJobs: (id: string, raw = false) => request<{ jobs: Job[] }>('GET', `/dossiers/${enc(id)}/jobs${raw ? '?raw' : ''}`),
  split: (id: string, body: { lemmas?: { title?: string; statement?: string; problem?: string }[]; n?: number; start?: boolean; mode?: Mode } = {}) =>
    request<{ children: Dossier[]; jobs: Job[] }>('POST', `/dossiers/${enc(id)}/split`, body),
  exportUrl: (id: string, format: ExportFormat) => `/api/dossiers/${enc(id)}/export?format=${format}`,

  jobs: () => request<{ active: Job[]; recent: Job[] }>('GET', '/jobs'),
  jobStream: (id: string, from = 0) => request<{ job_id: string; start: number; end: number; truncated: boolean; ended: boolean;
    segments: { offset: number; stage: string; attempt: number; kind: string; text: string }[] }>('GET', `/jobs/${enc(id)}/stream?from=${from}`),
  examples: () => request<{ examples: { key: string; statement: string; title: string; level: string; blurb: string;
    fr: { title: string; level: string; blurb: string }; en: { title: string; level: string; blurb: string } }[] }>('GET', '/examples'),
  declaration: (name: string, workspace?: string) => request<{ workspace: string; name: string; status: 'ok' | 'unknown' | 'indexing' | 'unavailable';
    declaration: { name: string; kind?: string; signature: string; doc: string; module: string } | null }>('GET', `/lean/declaration?name=${enc(name)}${workspace ? `&workspace=${enc(workspace)}` : ''}`),
  job: (id: string) => request<{ job: Job }>('GET', `/jobs/${enc(id)}`),
  cancelJob: (id: string) => request<{ cancelled: boolean }>('POST', `/jobs/${enc(id)}/cancel`, {}),
  /** S-AI (D41): answer « Plafond atteint : continuer avec Claude (+0,50 $) ? ». */
  answerConductor: (id: string, approve: boolean) => request<{ answered: boolean }>('POST', `/jobs/${enc(id)}/conductor`, { approve }),
  /** S-AN (D46): the same question for a request outside a job (a Calcul correction, an article compilation fix). */
  conductorAsks: () => request<{ asks: ConductorAsk[] }>('GET', '/conductor/asks'),
  answerConductorAsk: (id: string, approve: boolean) => request<{ answered: boolean }>('POST', `/conductor/asks/${enc(id)}`, { approve }),

  library: () => request<{ entries: LibEntry[] }>('GET', '/library'),
  deleteLibrary: (name: string) => request<{ removed: LibEntry }>('DELETE', `/library/${enc(name)}`),
  restoreLibrary: (entry: LibEntry) => request<{ ok: boolean }>('POST', '/library/restore', { entry }),
  libraryExportUrl: (workspace: string) => `/api/library/export?workspace=${enc(workspace)}`,

  /** S-AM (D45): « Expliquer l'erreur » (a correction is offered only once Lean accepted it) / « ligne par ligne ». */
  leanExplain: (body: LeanExplainWhere & { mode: 'error' | 'lines'; code?: string; stream?: string;
    errors?: { line: number; col: number; text: string; severity: string }[] }, o?: ReqOpts) =>
    request<LeanExplainAnswer>('POST', '/lean/explain', body, o),
  check: (code: string, opts: { workspace?: string; strict?: boolean; timeout?: number } = {}, o?: ReqOpts) =>
    request<{ check: CheckResult; workspace: string }>('POST', '/check', { code, ...opts }, o),
  importTex: (input: File | string) => {
    if (typeof input === 'string') return request<{ statements: { title: string; body: string }[] }>('POST', '/import/tex', { tex: input });
    const fd = new FormData();
    fd.append('file', input);
    return request<{ statements: { title: string; body: string }[] }>('POST', '/import/tex', fd);
  },

  models: () => request<ModelsInfo>('GET', '/models'),
  setKey: (provider: string, key: string) =>
    request<{ provider: string; set: boolean; backend: string }>('POST', '/models/keys', { provider, key }),
  deleteKey: (provider: string) => request<{ provider: string; set: boolean; existed: boolean }>('DELETE', `/models/keys/${enc(provider)}`),
  testKey: (provider: string) => request<{ provider: string; ok: boolean | null; reason?: string; model?: string; models?: number; latency_s?: number }>('POST', '/models/test', { provider }),
  refreshModels: () => request<ModelsInfo>('POST', '/models/refresh', {}),
  // providers hub + Internet search (S-U, docs/PROVIDERS.md)
  providers: () => request<ProvidersHub>('GET', '/providers'),
  searchWeb: (query: string, k = 6, lang = 'en') =>
    request<WebSearchResult>('POST', '/search/web', { query, k, lang }),
  testSearchKey: (provider: string) =>
    request<{ provider: string; ok: boolean | null; reason?: string; results?: number; latency_s?: number }>('POST', '/search/test', { provider }),
  stopLocal: () => request<unknown>('POST', '/models/local/stop', {}),
  leaderboard: () => request<{ entries: LeaderboardRow[]; tournament: Record<string, number | boolean> }>('GET', '/models/leaderboard'),
  rankings: () => request<Rankings>('GET', '/models/rankings'),
  refreshRankings: () => request<Rankings>('POST', '/models/rankings/refresh', {}),
  resetLeaderboard: () => request<{ entries: LeaderboardRow[] }>('POST', '/models/leaderboard/reset', {}),

  system: () => request<SystemInfo>('GET', '/system'),
  /** Status panel (S-AK): machine resources now, tokens and spending; polled only while the panel is open. */
  usage: (requests: string[] = []) => request<UsageStatus>('GET', `/usage${requests.length ? `?requests=${requests.map(enc).join(',')}` : ''}`),
  net: () => request<{ state: string; auth_url?: string }>('GET', '/net'),
  repair: (id: string) => request<Record<string, unknown>>('POST', `/system/repair/${enc(id)}`, {}),
  updates: () => request<UpdatesStatus>('GET', '/updates'),
  checkUpdates: () => request<{ checking: boolean }>('POST', '/updates/check', {}),
  installUpdate: (key: string) => request<UpdatesStatus>('POST', '/updates/install', { key }),
  cancelUpdate: () => request<{ cancelled: boolean }>('POST', '/updates/cancel', {}),

  assistant: (messages: { role: 'user' | 'assistant'; content: string }[], context: Record<string, unknown> = {}, mode?: Mode) =>
    request<{ request_id: string }>('POST', '/assistant', { messages, context, ...(mode ? { mode } : {}) }),
  stopAssistant: (id: string) => request<{ stopped: boolean }>('POST', `/assistant/${enc(id)}/stop`, {}),

  jupyter: () => request<JupyterStatus>('GET', '/jupyter'),
  jupyterStart: () => request<JupyterStatus>('POST', '/jupyter/start', {}),
  jupyterStop: () => request<JupyterStatus>('POST', '/jupyter/stop', {}),
  notebooks: (path = '') => request<{ notebooks: { name: string; path: string; type: string; last_modified: string }[] }>('GET', `/jupyter/notebooks?path=${enc(path)}`),
  notebook: (path: string) => request<{ path: string; cells: { index: number; cell_type: string; source: string; outputs_text: string }[]; kernel: string }>('GET', `/jupyter/notebook?path=${enc(path)}`),
  createNotebook: (path: string, kernel = 'python3') => request<{ path: string }>('POST', '/jupyter/notebook', { path, kernel }),
  appendCell: (path: string, source: string, cell_type: 'code' | 'markdown' | 'raw' = 'code') =>
    request<{ path: string; index: number }>('POST', '/jupyter/cells', { path, source, cell_type }),
};

export type ExportFormat = 'pdf' | 'tex' | 'lean' | 'md' | 'zip' | 'html';

/** The shell bridge (docs/SHELLS.md §7), looked up lazily: old Android WebViews inject it late. */
export interface ShellBridge { kind: 'desktop' | 'android'; version?: string; changeServer?: () => void; openExternal?: (url: string) => void }
export function shell(): ShellBridge | null {
  const s = (globalThis as { madaleanShell?: ShellBridge }).madaleanShell;
  return s && typeof s === 'object' ? s : null;
}

let texAvailable: Promise<boolean> | null = null;
/** Whether the host has a TeX engine (health check `tex`), cached for the session. */
export function hasTex(): Promise<boolean> {
  texAvailable ??= api.system().then((s) => s.checks?.find((c) => c.id === 'tex')?.ok !== false).catch(() => true);
  return texAvailable;
}

/**
 * Exports always use REAL server URLs answered with `Content-Disposition: attachment` (docs/SHELLS.md §6: the
 * Android shell re-downloads them with its token; no blob: URLs). PDF without a TeX engine on the host: the
 * server would answer the self-contained HTML (`X-Madalean-Fallback: html`), so we open `format=html` in a new
 * tab directly and tell the user to print it to PDF. Returns which path was taken.
 */
export async function downloadExport(id: string, format: ExportFormat): Promise<{ fallback: '' | 'html' }> {
  if (format === 'pdf' && !(await hasTex())) {
    openExternalOrTab(api.exportUrl(id, 'html'));
    return { fallback: 'html' };
  }
  clickLink(api.exportUrl(id, format), true);
  return { fallback: '' };
}

export function openExternalOrTab(url: string): void {
  const sh = shell();
  if (sh?.openExternal && /^https?:/i.test(url)) { sh.openExternal(url); return; }
  clickLink(url, false);
}

function clickLink(href: string, download: boolean): void {
  const a = document.createElement('a');
  a.href = href;
  if (download) a.download = '';
  else { a.target = '_blank'; a.rel = 'noopener'; }
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// ---- providers hub (S-U)
export interface I18nText { fr: string; en: string }
export interface ProviderCard {
  id: string; group: string; name: string; key: string | null; kind: 'llm' | 'search' | 'keyless' | 'info' | 'token';
  price: 'free' | 'free_tier' | 'credits' | 'paid'; integrated: 'yes' | 'auto' | 'no' | 'retired';
  good_for: I18nText; free_tier: I18nText; privacy: I18nText; details: I18nText; key_url: string; sources: string[];
  checked: string; prefix: string; models: string[]; key_set: boolean | null; disabled: boolean;
  state?: { models: number; ok: boolean; paused_until: number | null; reason: string };
  usage?: { units: number; searches: number; unit: string; free_month: number };
}
export interface ProvidersHub {
  checked: string; groups: { id: string; fr: string; en: string }[]; starter: string[]; cards: ProviderCard[];
  web_search: boolean; mode: string;
}
export interface WebSearchResult {
  query: string; provider: string; tried: { provider: string; error: string }[];
  results: { n: number; title: string; url: string; snippet: string; published: string; source: string }[];
}
