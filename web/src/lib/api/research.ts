// Typed client of the research layer: docs/RESEARCH_SOURCES.md (S-E) and docs/RESEARCH_WORKSHOP.md (S-G).
import { request, type ReqOpts } from './client';
import type { CheckResult, Dossier, Job, Message, UpdatesStatus } from './types';

const enc = encodeURIComponent;

// ---------------------------------------------------------------- sources
export type Name = { family?: string; given?: string; literal?: string };
export interface Csl {
  type: string; title: string; author?: Name[]; editor?: Name[]; issued?: { 'date-parts': number[][] };
  'container-title'?: string; volume?: string; issue?: string; page?: string; DOI?: string; URL?: string; ISBN?: string;
  publisher?: string; abstract?: string; note?: string; arxiv?: string; zbl?: string; msc?: string[]; [k: string]: unknown;
}
export type ReadStatus = 'unread' | 'reading' | 'read' | 'to_read' | 'skimmed';
export interface Annotation { id: string; page?: number | null; quads?: number[][]; range?: { chunk: string; start: number; end: number } | null;
  text: string; note: string; color: string; created: number; updated: number }
export interface SourceFile { sha256: string; name: string; kind: 'pdf' | 'tex' | 'archive' | 'epub'; size: number; role: string; added: number }
export interface Source {
  id: string; key: string; csl: Csl; files: SourceFile[]; tags: string[]; collections: string[]; status: ReadStatus; notes: string;
  annotations: Annotation[]; verified: boolean; proposed: Csl | null; origin: { via: string; at: number };
  oa: { is_oa?: boolean; status?: string; url?: string; landing?: string };
  fulltext: { state: 'none' | 'ok' | 'no_text_layer' | 'ocr' | 'error'; method?: string; chunks?: number; pages?: number; warnings: string[]; at: number };
  warnings?: string[]; added: number; updated: number; readonly?: boolean;
}
export interface SourceSummary {
  id: string; key: string; title: string; authors: string; year: number | null; type: string; venue: string; doi: string; arxiv: string;
  tags: string[]; collections: string[]; status: ReadStatus; verified: boolean; has_pdf: boolean; has_tex: boolean; fulltext: string;
  oa: { is_oa?: boolean }; annotations: number; updated: number; readonly: boolean;
}
export interface Chunk { id: string; source_id: string; ord: number; kind: string; text: string; page: number | null;
  bbox: [number, number, number, number] | null; section: string; label: string; locator: string; meta: Record<string, unknown> }
export interface Shelf { id: string; title: string; count: number; readonly: boolean; project?: boolean }
export interface LitResult { id: string; title: string; authors: string; year: number | null; venue: string; doi: string; arxiv: string;
  zbl: string; openalex: string; msc: string[]; abstract: string; oa: { is_oa?: boolean; url?: string }; providers: string[]; score: number; csl: Csl; why?: string }
export interface Citation { passage: string; chunk_id: string; source_id: string; source_key: string; shelf: string; page: number | null;
  bbox: number[] | null; locator: string; quote: string; span: [number, number]; match: number }
export interface QaResult {
  kind: 'ask' | 'summary' | 'compare'; question: string; status: 'ok' | 'no_passages' | 'not_in_sources' | 'unsupported'; model: string; dropped: number;
  passages: { passage: string; chunk_id: string; source_id: string; source_key: string; shelf: string; page: number | null; locator: string; kind: string; text: string; score: number }[];
  sentences: { text: string; supported: boolean; general: boolean; notice?: boolean; citations: Citation[] }[];
  general: { text: string; supported: false; general: true; citations: [] }[]; general_model?: string;
}

// ---------------------------------------------------------------- blueprint / article
export interface BpNode { id: string; kind: string; name: string; number: string; label: string; title: string; text: string; tex: string;
  proof: string; section: string; locator: string; page?: number; cites: string[];
  uses: { to: string; via: string; proposed: boolean; accepted?: boolean; rejected?: boolean }[]; quality: string; dossier_id: string }
export interface Blueprint { source_id: string; paper_key: string; method: string; title: string; nodes: BpNode[]; warnings: string[]; shelf: string; created: number; updated: number }
export type NodeStateName = 'not_created' | 'stated' | 'statement' | 'proved' | 'defined' | 'verified' | 'blocked' | 'failed';
export interface NodeState { node_id: string; source_id: string; dossier_id: string; state: NodeStateName; verified: boolean;
  missing_definitions: string[]; unverified_uses: string[] }
export interface Block { id: string; kind: string; title: string; source: 'ai' | 'user' | 'dossier'; text: string; dossier_id: string;
  versions: { text: string; source: string; t: number; model: string; note: string; title: string; removed_citations?: string[] }[]; updated: number }
export interface Article { title: string; authors: { name: string; affiliation?: string; email?: string }[]; abstract: Block; blocks: Block[];
  options: { lean_appendix: boolean; verification_table: boolean; lang: 'fr' | 'en'; numbering: 'section' | 'global' }; created: number; updated: number }

// ---------------------------------------------------------------- notes
export interface NoteSummary { id: string; project_id: string; title: string; tags: string[]; kind: 'note' | 'daily'; rev: number;
  created: number; updated: number; deleted: number | null; size: number; excerpt: string }
export interface LeanBlockResult { ok: boolean; statement_ok: boolean; has_sorry: boolean; summary: string; seconds: number;
  errors: { line: number; note_line: number; col: number; text: string; severity: string }[]; timed_out: boolean; infra_error: string;
  workspace: string; t: number; hash: string; index: number; reasons?: string[] }
export interface Note extends NoteSummary { body: string; user_tags: string[]; device: string;
  lean_blocks: { index: number; hash: string; start_line: number; result: LeanBlockResult | null }[];
  links: { kind: 'note' | 'dossier' | 'source' | 'lib' | 'passage'; ref: string; label: string; locator: string }[] }
export interface NoteConflict { error: 'conflict'; base_rev: number; current: Note; conflicts: { base_start: number; base_end: number; base: string; mine: string; theirs: string }[]; fields: string[] }
export interface GraphNode { id: string; kind: 'note' | 'dossier' | 'source'; ref: string; title: string; missing?: boolean; tags?: string[];
  status?: string; dossier_kind?: string; proved?: boolean }
export interface GraphEdge { source: string; target: string; kind: 'link' | 'uses' | 'cites'; label?: string; locator?: string }

// ---------------------------------------------------------------- conjectures / plans
export interface Experiment { id: string; kind: 'counterexample' | 'test'; language: 'sage' | 'python'; code: string; predicate: string;
  code_hash: string; source: 'ai' | 'user'; model: string; status: 'awaiting_approval' | 'approved' | 'running' | 'done' | 'failed' | 'rejected';
  approved: { hash: string; t: number; device: string } | null; runs: { t: number; status: string; verdict: string; seconds: number }[] }
export interface Evidence { id: string; t: number; kind: string; summary: Message; verdict: string; code: string; language: string; output: string;
  data: Record<string, unknown>; model: string; device: string; prev: string; hash: string }
export type ConjStatus = 'proposed' | 'tested-n-cases' | 'lean-statement' | 'proved' | 'refuted';
export interface Conjecture { id: string; title: string; project_id: string; kind: string; status: ConjStatus; cases_tested: number;
  statement_nl: string; motivation: string; origin: Record<string, unknown>; lean_statement: string; statement_ok: boolean; proved: boolean;
  counterexample: { witness: Record<string, unknown>; verified: boolean; sage: boolean; lean: boolean } | null; promoted: unknown;
  evidence: Evidence[]; experiments: Experiment[]; chain_ok: boolean; dossier_status?: string; updated?: number }
export interface Proposal { statement: string; motivation: string; lean: string; test: string; origin?: object; reason?: string; match?: string }
export type PlanUi = 'to_validate' | 'validated' | 'running' | 'proved' | 'failed' | 'abandoned' | 'alternative' | 'hole' | 'conditional';
export interface PlanCheck { state: 'ok' | 'failed' | 'unchecked'; why: string; t: number }
export interface PlanTrack { id: string; idea: string; lemmas: string[]; combination: string; check: PlanCheck; abandoned: boolean; refused: string; name?: string }
export interface PlanNode { id: string; parent: string | null; children: string[]; title: string; statement_nl: string; why: string; lean: string;
  status: string; state: string; dossier_id: string; admitted: boolean; edited: boolean; cancelled: boolean; proved: boolean;
  conditional: Record<string, unknown> | null; dossier_status: string;
  // S-L: decomposition as a mind map
  ui: PlanUi; off: '' | 'alternative' | 'abandoned'; depth: number; track: string; tracks: PlanTrack[]; active_track: string;
  uses: string[]; lean_ok: boolean | null; lean_error: string; obvious: boolean; obvious_proof: string; name?: string;
  combine: { state?: string; why?: string; t?: number; holes?: number } | null;
  refused_tracks?: { idea: string; reason: string; lemmas: string[] }[] }
export interface PlanSummary { lemmas: number; proved: number; running: number; failed: number; holes: number; to_validate: number;
  conditional: number; depth: number; max_depth: number; nodes: number; max_nodes: number;
  next: 'split' | 'validate' | 'prove' | 'wait' | 'fix' | 'conditional' | 'done' | 'stopped'; attention: string[];
  run: { started: number; deadline: number; mode: string; stopped: string; finished?: number } | null; analysing: string }
export interface Plan { rev: number; t: number; source: 'ai' | 'user' | 'sketch' | 'auto'; model: string; root: string; nodes: Record<string, PlanNode>;
  root_state: string; queued: string[]; limit: number; validated?: number;
  verdict: { state: 'open' | 'proved_modulo' | 'proved'; verified: boolean; admitted: number; admitted_names?: string[] };
  summary: PlanSummary; limits: { depth: number; lemmas: number; alternatives: number; nodes: number; budget_minutes: number };
  versions: { rev: number; t: number; source: string; model: string; device: string; note: string }[] }

// ---------------------------------------------------------------- learn / updates
export interface HintAnswer { level: number; level_name: string; text: string; model: string; source: 'ai' | 'lean'; redacted: boolean; name?: string }
export interface ExplainAnswer { text: string; criteria: { criterion: string; met: boolean; evidence: string }[]; met: number; total: number;
  gap: string; question: string; redacted: boolean; graded_against: string }
export interface FadedExercise { id: string; template: string; blanks: number; k: number; verified: Record<string, unknown> }
export interface ErroneousExercise { id: string; wrong_proof: string; mutation: string; block: number; prompts: string[] }
export interface SelfUpdate { version: string; installed: string; previous: string | null; available: { version: string; notes_url?: string } | null;
  last: Record<string, unknown> | null; busy: boolean; pending_restart: boolean; versions: string[]; managed_install: boolean; public_key: string; [k: string]: unknown }
export interface RecheckReport { workspace: string; reason: string; started: number; ended: number | null; total: number; ok: number;
  regressed: { name: string; dossier: string; kind: string; summary: string; errors: string }[] }

// ---------------------------------------------------------------- publish (docs/RESEARCH_SOURCES.md §12)
export interface PublishManifest {
  id: string; project: string; created: number; workspace: string; toolchain: string; mathlib: string;
  items: { path: string; kind: string; size: number; sha256: string; origin: string; note: string }[];
  excluded: { what: string; why: string; license?: string }[]; warnings: string[];
  statuses: Record<string, string>; counts: Record<string, number>; not_included: string[];
}
export interface PublishState { repo: string; branch: string; commit: string; changed: boolean; created: boolean; pages: boolean; pages_url: string; pushed_at: number; login?: string; pages_error?: { error: string; message?: string; permission?: string; scope?: string; settings?: string }; pages_settings?: string }
export interface GithubCheckItem { id: string; ok: boolean | null; code: string; params: Record<string, string> }
export interface GithubCheck { ok: boolean; login?: string; name?: string; token_kind: string; source: string; scopes?: string[] | null; expires?: string; checks: GithubCheckItem[] }

const sh = (shelf: string) => `/research/shelves/${enc(shelf)}`;
const src = (shelf: string, id: string) => `${sh(shelf)}/sources/${enc(id)}`;
const proj = (pid: string) => `/research/projects/${enc(pid)}`;

export const research = {
  // sources
  shelves: () => request<{ shelves: Shelf[] }>('GET', '/research/shelves'),
  sources: (shelf: string, q: { q?: string; tag?: string; collection?: string; status?: string } = {}) => {
    const p = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
    return request<{ shelf: string; sources: SourceSummary[]; total: number }>('GET', `${sh(shelf)}/sources?${p}`);
  },
  addByIdentifier: (shelf: string, identifier: string, force = false) =>
    request<{ source: Source; duplicate: { of: string; reason: string } | null }>('POST', `${sh(shelf)}/sources`, { identifier, files: true, force }),
  addCsl: (shelf: string, csl: Csl, force = false) => request<{ source: Source; duplicate: unknown }>('POST', `${sh(shelf)}/sources`, { csl, force }),
  addText: (shelf: string, text: string, format?: string) =>
    request<{ added: { id: string; key: string }[]; duplicates: { id: string; key: string }[]; errors: string[] }>('POST', `${sh(shelf)}/sources`, { text, ...(format ? { format } : {}) }),
  addFile: (shelf: string, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ source?: Source; added?: { id: string; key: string }[]; duplicates?: unknown[]; errors?: string[] }>('POST', `${sh(shelf)}/sources`, fd);
  },
  source: (shelf: string, id: string) => request<{ source: Source }>('GET', src(shelf, id)),
  patchSource: (shelf: string, id: string, p: Partial<Pick<Source, 'tags' | 'collections' | 'status' | 'notes' | 'csl' | 'key'>> & { verified?: true }) =>
    request<{ source: Source }>('PATCH', src(shelf, id), p),
  deleteSource: (shelf: string, id: string) => request<{ ok: boolean; undo: string }>('DELETE', src(shelf, id)),
  restoreSource: (shelf: string, id: string) => request<{ source: Source }>('POST', `${src(shelf, id)}/restore`, {}),
  copySource: (shelf: string, id: string, to: string) => request<{ source: Source }>('POST', `${src(shelf, id)}/copy`, { to }),
  attachFile: (shelf: string, id: string, file: File) => { const fd = new FormData(); fd.append('file', file); return request<{ source: Source }>('POST', `${src(shelf, id)}/files`, fd); },
  fileUrl: (shelf: string, id: string, sha: string, download = false) => `/api${src(shelf, id)}/files/${sha}${download ? '?download' : ''}`,
  chunks: (shelf: string, id: string, page?: number) => request<{ chunks: Chunk[] }>('GET', `${src(shelf, id)}/chunks${page ? `?page=${page}` : ''}`),
  addAnnotation: (shelf: string, id: string, a: Partial<Annotation>) => request<{ source: Source; annotation: Annotation }>('POST', `${src(shelf, id)}/annotations`, a),
  patchAnnotation: (shelf: string, id: string, aid: string, a: Partial<Annotation>) => request<{ source: Source }>('PATCH', `${src(shelf, id)}/annotations/${enc(aid)}`, a),
  deleteAnnotation: (shelf: string, id: string, aid: string) => request<{ source: Source }>('DELETE', `${src(shelf, id)}/annotations/${enc(aid)}`),
  propose: (shelf: string, id: string) => request<unknown>('POST', `${src(shelf, id)}/propose`, {}),
  exportUrl: (shelf: string, format: 'bib' | 'ris' | 'csljson') => `/api${sh(shelf)}/export?format=${format}`,
  search: (shelf: string, query: string, k = 12) => request<{ hits: (Chunk & { score: number; shelf: string; source_key: string })[] }>('POST', `${sh(shelf)}/search`, { query, k }),
  resolve: (id: string) => request<{ csl: Csl; via: string; oa: unknown }>('GET', `/research/resolve?id=${enc(id)}`),
  litsearch: (query: string, n = 10) => request<{ results: LitResult[]; providers: Record<string, { ok: boolean; count: number; error?: string }> }>('POST', '/research/litsearch', { query, n }),
  related: (id: string, how: 'related' | 'cited_by' | 'references') => request<{ results: LitResult[] }>('POST', '/research/litsearch/related', { id, how }),
  readingList: (question: string) => request<{ request_id: string }>('POST', '/research/litsearch/reading-list', { question }),
  ask: (question: string, project: string, scope?: { shelves?: string[]; sources?: string[] }, general = false) =>
    request<{ request_id: string }>('POST', '/research/ask', { question, project, ...(scope ? { scope } : {}), general }),
  summarize: (shelf: string, source: string) => request<{ request_id: string }>('POST', '/research/summarize', { shelf, source }),
  compare: (sources: { shelf: string; id: string }[]) => request<{ request_id: string }>('POST', '/research/compare', { sources }),
  stopRequest: (rid: string) => request<unknown>('POST', `/research/requests/${enc(rid)}/stop`, {}),
  keys: (pid: string) => request<{ keys: { key: string; title: string; label: string; authors: string; year: number | null }[] }>('GET', `${proj(pid)}/keys`),
  bibliographyUrl: (pid: string) => `/api${proj(pid)}/bibliography`,
  // blueprint
  blueprints: (pid: string) => request<{ blueprints: { source_id: string; paper_key: string; method: string; nodes: number; created: number; warnings: string[] }[] }>('GET', `${proj(pid)}/blueprints`),
  blueprint: (pid: string, sid: string) => request<{ blueprint: Blueprint; status: Record<string, NodeState> }>('GET', `${proj(pid)}/blueprints/${enc(sid)}`),
  createBlueprint: (pid: string, source_id: string, shelf?: string, model_pass = false) =>
    request<{ blueprint: Blueprint; request_id: string }>('POST', `${proj(pid)}/blueprints`, { source_id, ...(shelf ? { shelf } : {}), model_pass }),
  deleteBlueprint: (pid: string, sid: string) => request<{ ok: boolean }>('DELETE', `${proj(pid)}/blueprints/${enc(sid)}`),
  restoreBlueprint: (pid: string, sid: string) => request<unknown>('POST', `${proj(pid)}/blueprints/${enc(sid)}/restore`, {}),
  edge: (pid: string, sid: string, from: string, to: string, action: 'add' | 'remove' | 'accept' | 'reject') =>
    request<{ blueprint: Blueprint }>('POST', `${proj(pid)}/blueprints/${enc(sid)}/edges`, { from, to, action }),
  nodeDossiers: (pid: string, sid: string, nodes?: string[]) => request<{ dossiers: Dossier[]; blueprint: Blueprint }>('POST', `${proj(pid)}/blueprints/${enc(sid)}/dossiers`, nodes ? { nodes } : {}),
  formalise: (pid: string, dossier_ids: string[], use_paper_proof = true) =>
    request<{ jobs: Job[]; busy: string[]; skipped: string[] }>('POST', `${proj(pid)}/formalise`, { dossier_ids, use_paper_proof }),
  blueprintStatus: (pid: string) => request<{ nodes: NodeState[]; counts: Record<string, number> }>('GET', `${proj(pid)}/blueprint-status`),
  // article
  article: (pid: string) => request<{ article: Article; generating: string[] }>('GET', `${proj(pid)}/article`),
  patchArticle: (pid: string, p: Partial<Pick<Article, 'title' | 'authors' | 'options'>> & { order?: string[] }) => request<{ article: Article }>('PATCH', `${proj(pid)}/article`, p),
  syncArticle: (pid: string) => request<{ article: Article; added: number }>('POST', `${proj(pid)}/article/sync`, {}),
  addBlock: (pid: string, b: { kind: string; title?: string; text?: string; dossier_id?: string; after?: string }) => request<{ article: Article; block: Block }>('POST', `${proj(pid)}/article/blocks`, b),
  patchBlock: (pid: string, bid: string, p: { text?: string; title?: string }) => request<{ article: Article; block: Block }>('PATCH', `${proj(pid)}/article/blocks/${enc(bid)}`, p),
  deleteBlock: (pid: string, bid: string) => request<unknown>('DELETE', `${proj(pid)}/article/blocks/${enc(bid)}`),
  restoreBlock: (pid: string, bid: string) => request<unknown>('POST', `${proj(pid)}/article/blocks/${enc(bid)}/restore`, {}),
  generateBlock: (pid: string, bid: string, force = false, instructions = '') => request<{ request_id: string }>('POST', `${proj(pid)}/article/blocks/${enc(bid)}/generate`, { force, ...(instructions ? { instructions } : {}) }),
  restoreBlockVersion: (pid: string, bid: string, i: number) => request<{ article: Article }>('POST', `${proj(pid)}/article/blocks/${enc(bid)}/versions/${i}/restore`, {}),
  articleExportUrl: (pid: string, format: 'pdf' | 'tex' | 'zip' | 'md') => `/api${proj(pid)}/article/export?format=${format}`,

  // notes
  notes: (project: string, opts: { tag?: string; trash?: boolean } = {}) =>
    request<{ notes: NoteSummary[] }>('GET', `/notes?project=${enc(project)}${opts.tag ? `&tag=${enc(opts.tag)}` : ''}${opts.trash ? '&trash=1' : ''}`),
  createNote: (project_id: string, title: string, body = '', tags: string[] = []) => request<{ note: Note }>('POST', '/notes', { project_id, title, body, tags }),
  note: (id: string, o?: ReqOpts) => request<{ note: Note; backlinks: { id: string; title: string; label: string; context: string }[]; attachments: unknown[] }>('GET', `/notes/${enc(id)}`, undefined, o),
  patchNote: (id: string, base_rev: number, p: { title?: string; body?: string; tags?: string[] }) =>
    request<{ note: Note; merged: boolean; renamed_links_in: string[] }>('PATCH', `/notes/${enc(id)}`, { base_rev, ...p }),
  deleteNote: (id: string) => request<{ ok: boolean }>('DELETE', `/notes/${enc(id)}`),
  restoreNote: (id: string) => request<{ note: Note }>('POST', `/notes/${enc(id)}/restore`, {}),
  noteVersions: (id: string) => request<{ versions: { rev: number; title: string; size: number; t: number; device: string; reason: string }[]; rev: number }>('GET', `/notes/${enc(id)}/versions`),
  noteVersion: (id: string, rev: number) => request<{ version: { rev: number; title: string; body: string; tags: string[]; t: number } }>('GET', `/notes/${enc(id)}/versions/${rev}`),
  noteDiff: (id: string, from: number, to: number) => request<{ diff: string; title_changed: boolean }>('GET', `/notes/${enc(id)}/diff?from=${from}&to=${to}`),
  restoreNoteVersion: (id: string, rev: number, base_rev?: number) => request<{ note: Note }>('POST', `/notes/${enc(id)}/versions/${rev}/restore`, base_rev ? { base_rev } : {}),
  searchNotes: (q: string, project?: string) => request<{ results: (NoteSummary & { snippet: string; score: number })[] }>('GET', `/notes/search?q=${enc(q)}${project ? `&project=${enc(project)}` : ''}`),
  graph: (pid: string, q: { kinds?: string; edges?: string; tag?: string; orphans?: boolean } = {}) =>
    request<{ nodes: GraphNode[]; edges: GraphEdge[] }>('GET', `/projects/${enc(pid)}/graph?${new URLSearchParams({ ...(q.kinds ? { kinds: q.kinds } : {}), ...(q.edges ? { edges: q.edges } : {}), ...(q.tag ? { tag: q.tag } : {}), orphans: q.orphans === false ? '0' : '1' })}`),
  tags: (pid: string) => request<{ tags: { tag: string; count: number }[] }>('GET', `/projects/${enc(pid)}/tags`),
  dailyNote: (pid: string) => request<{ note: Note }>('POST', `/projects/${enc(pid)}/notes/daily`, {}),
  leanCheckNote: (id: string, block?: number) => request<{ results: LeanBlockResult[]; note: Note }>('POST', `/notes/${enc(id)}/lean-check`, block === undefined ? {} : { block }),
  noteToDossier: (id: string, p: { block?: number; paragraph?: number; text?: string; kind?: string; title?: string; start?: boolean }) =>
    request<{ dossier: Dossier; job: Job | null; note: Note }>('POST', `/notes/${enc(id)}/to-dossier`, p),
  noteExportUrl: (id: string, format: 'md' | 'html' | 'pdf') => `/api/notes/${enc(id)}/export?format=${format}`,
  addAttachment: (id: string, file: File) => { const fd = new FormData(); fd.append('file', file); return request<{ attachment: { id: string; url: string; markdown: string } }>('POST', `/notes/${enc(id)}/attachments`, fd); },

  // conjectures
  conjectures: (project: string) => request<{ conjectures: Conjecture[] }>('GET', `/conjectures?project=${enc(project)}`),
  conjecture: (id: string) => request<{ conjecture: Conjecture }>('GET', `/conjectures/${enc(id)}`),
  generateConjectures: (pid: string, p: { note_ids?: string[]; dossier_ids?: string[]; library?: boolean; source_keys?: string[]; n?: number }) =>
    request<{ proposals: Proposal[]; filtered: Proposal[]; model: string }>('POST', `/projects/${enc(pid)}/conjectures/generate`, p),
  createConjecture: (p: { project_id: string; statement: string; motivation?: string; lean?: string; title?: string; origin?: object; model?: string }) =>
    request<{ conjecture: Conjecture }>('POST', '/conjectures', p),
  conjLean: (id: string, code: string) => request<{ conjecture: Conjecture; check: CheckResult }>('POST', `/conjectures/${enc(id)}/lean`, { code }),
  conjFormalize: (id: string) => request<{ job: Job }>('POST', `/conjectures/${enc(id)}/formalize`, {}),
  conjProve: (id: string) => request<{ job: Job }>('POST', `/conjectures/${enc(id)}/prove`, {}),
  conjCases: (id: string, p: { cases?: Record<string, unknown>[]; bounded?: number } = {}) => request<{ entry: Evidence; conjecture: Conjecture }>('POST', `/conjectures/${enc(id)}/lean-cases`, p),
  conjRefuteLean: (id: string, witness: string) => request<{ ok: boolean; code: string; check: CheckResult }>('POST', `/conjectures/${enc(id)}/refute-lean`, { witness }),
  newExperiment: (id: string, p: { kind: 'counterexample' | 'test'; language: 'sage' | 'python'; code?: string }) =>
    request<{ experiment: Experiment; approval_required: boolean }>('POST', `/conjectures/${enc(id)}/experiments`, p),
  editExperiment: (id: string, eid: string, code: string) => request<{ experiment: Experiment }>('PATCH', `/conjectures/${enc(id)}/experiments/${enc(eid)}`, { code }),
  approveExperiment: (id: string, eid: string, code_hash: string) => request<unknown>('POST', `/conjectures/${enc(id)}/experiments/${enc(eid)}/approve`, { code_hash }),
  rejectExperiment: (id: string, eid: string) => request<unknown>('POST', `/conjectures/${enc(id)}/experiments/${enc(eid)}/reject`, {}),
  runExperiment: (id: string, eid: string, timeout = 60) => request<{ started: boolean }>('POST', `/conjectures/${enc(id)}/experiments/${enc(eid)}/run`, { timeout }),
  experimentsStatus: () => request<{ available: { sage: boolean; python: boolean }; sandbox: string; auto: boolean; remote_allowed: boolean }>('GET', '/experiments/status'),
  conjLiterature: (id: string) => request<{ result: Record<string, unknown> }>('POST', `/conjectures/${enc(id)}/literature`, {}),
  promote: (id: string) => request<{ conjecture: Conjecture }>('POST', `/conjectures/${enc(id)}/promote`, {}),

  // proof plans
  plan: (did: string) => request<{ plan: Plan }>('GET', `/dossiers/${enc(did)}/plan`),
  newPlan: (did: string) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan`, {}),
  draftPlan: (did: string, p: { hint?: string; sketch?: string; force?: boolean } = {}) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/draft`, p),
  addPlanNode: (did: string, p: { base_rev: number; parent: string; index?: number; title: string; statement_nl?: string; why?: string; lean?: string }) =>
    request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes`, p),
  patchPlanNode: (did: string, nid: string, p: { base_rev: number; title?: string; statement_nl?: string; why?: string; lean?: string; combination?: string }) =>
    request<{ plan: Plan }>('PATCH', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}`, p),
  deletePlanNode: (did: string, nid: string, base_rev: number) => request<{ plan: Plan }>('DELETE', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}?base_rev=${base_rev}`),
  movePlanNode: (did: string, nid: string, p: { base_rev: number; parent: string; index?: number }) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}/move`, p),
  acceptPlan: (did: string, base_rev: number, nodes: string[]) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/accept`, { base_rev, nodes }),
  rejectPlan: (did: string, base_rev: number, nodes: string[]) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/reject`, { base_rev, nodes }),
  submitPlan: (did: string, base_rev: number, nodes?: string[]) => request<{ plan: Plan; submitted: string[] }>('POST', `/dossiers/${enc(did)}/plan/submit`, { base_rev, ...(nodes ? { nodes } : {}) }),
  cancelPlanNode: (did: string, nid: string) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}/cancel`, {}),
  replanNode: (did: string, nid: string, base_rev: number, hint = '') => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}/replan`, { base_rev, hint }),
  admitNode: (did: string, nid: string, base_rev: number, undo = false) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}/${undo ? 'unadmit' : 'admit'}`, { base_rev }),
  proveModulo: (did: string, node?: string) => request<{ ok: boolean; conditional: boolean; plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/prove-modulo`, node ? { node } : {}),
  analysePlan: (did: string, p: { node?: string; hint?: string; base_rev?: number; force?: boolean } = {}) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/analyse`, p),
  validatePlan: (did: string, base_rev: number) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/validate`, { base_rev }),
  provePlan: (did: string, base_rev: number) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/prove`, { base_rev }),
  switchTrack: (did: string, nid: string, base_rev: number, track?: string) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}/track`, { base_rev, ...(track ? { track } : {}) }),
  recheckNode: (did: string, nid: string, base_rev: number) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/nodes/${enc(nid)}/recheck`, { base_rev }),
  restorePlanVersion: (did: string, rev: number) => request<{ plan: Plan }>('POST', `/dossiers/${enc(did)}/plan/versions/${rev}/restore`, {}),

  // learn
  hint: (did: string, p: { level: string; tried?: string; help?: string; reflections?: string[]; confidence?: number }) => request<HintAnswer>('POST', `/dossiers/${enc(did)}/hint`, p),
  explainBack: (did: string, p: { target: 'statement' | 'proof'; text: string; previous?: string[] }) => request<ExplainAnswer>('POST', `/dossiers/${enc(did)}/explain-back`, p),
  ladder: (did: string) => request<{ attempted: boolean; revealed: number[]; hints: Record<string, HintAnswer>; next: number; levels: Record<string, string> }>('GET', `/learn/${enc(did)}/ladder`),
  faded: (did: string, k: number) => request<FadedExercise>('POST', `/learn/${enc(did)}/exercises/faded`, { k }),
  erroneous: (did: string) => request<ErroneousExercise>('POST', `/learn/${enc(did)}/exercises/erroneous`, {}),
  submitExercise: (did: string, eid: string, p: { fills?: string[]; diagnosis?: string; code?: string }) =>
    request<{ checked: boolean; ok?: boolean; check?: CheckResult; lean_error?: string; wrong_block?: number }>('POST', `/learn/${enc(did)}/exercises/${enc(eid)}/submit`, p),
  learnToken: (name: string, workspace?: string) => request<{ known?: boolean; text?: string; signature?: string; doc?: string; module?: string; suggestions?: string[]; [k: string]: unknown }>('GET', `/learn/token?name=${enc(name)}${workspace ? `&workspace=${enc(workspace)}` : ''}`),
  learnProgress: (dossier?: string) => request<{ device: string; entries: { t: number; dossier: string; kind: string; [k: string]: unknown }[] }>('GET', `/learn/progress${dossier ? `?dossier=${enc(dossier)}` : ''}`),

  // updates (S-G additions)
  recheck: () => request<{ running: boolean; report: RecheckReport | null }>('GET', '/updates/recheck'),
  startRecheck: (workspace?: string) => request<unknown>('POST', '/updates/recheck', workspace ? { workspace } : {}),
  systemTerminal: (comp: string) => request<{ opened: boolean; command: string; terminal: string }>('POST', `/updates/system/${enc(comp)}/terminal`, {}),
  selfupdate: () => request<SelfUpdate>('GET', '/selfupdate'),
  selfupdateCheck: () => request<SelfUpdate>('POST', '/selfupdate/check', {}),
  selfupdateInstall: () => request<SelfUpdate>('POST', '/selfupdate/install', {}),
  selfupdateRollback: () => request<SelfUpdate>('POST', '/selfupdate/rollback', {}),
  selfupdateRestart: () => request<unknown>('POST', '/selfupdate/restart', {}),
  workspacePackages: (key: string) => request<{ workspace: string; readonly: boolean; packages: { name: string; url: string; rev: string; direct: boolean }[] }>('GET', `/workspaces/${enc(key)}/packages`),
  addLibrary: (key: string, p: { name: string; url: string; rev: string }) => request<UpdatesStatus>('POST', `/workspaces/${enc(key)}/libraries`, p),

  // publish
  publishState: (pid: string) => request<{ manifest: PublishManifest | null; state: PublishState | null; preview: boolean; running: boolean }>('GET', `/research/publish/${enc(pid)}`),
  publishPlan: (pid: string, p: { dossiers?: string[]; notes?: string[]; include_pdf?: boolean; computations?: boolean | string[]; license?: string; title?: string; lang?: string }) =>
    request<{ manifest: PublishManifest }>('POST', `/research/publish/${enc(pid)}/plan`, p),
  publishPreview: (pid: string, manifest_id: string) => request<{ pages: number; url: string }>('POST', `/research/publish/${enc(pid)}/preview`, { manifest_id }),
  publishPush: (pid: string, p: { manifest_id: string; repo: string; create?: boolean; private?: boolean; branch?: string }) =>
    request<{ request_id: string }>('POST', `/research/publish/${enc(pid)}/push`, p),
  githubCheck: (repo = '', priv = false) => request<GithubCheck>('GET', `/research/github/check?repo=${encodeURIComponent(repo)}${priv ? '&private=1' : ''}`),
};

/** Plain list of authors from CSL names. */
export function authorsOf(c: Csl | undefined): string {
  return (c?.author ?? []).map((n) => n.literal ?? [n.given, n.family].filter(Boolean).join(' ')).join(', ');
}
export function yearOf(c: Csl | undefined): number | null {
  return c?.issued?.['date-parts']?.[0]?.[0] ?? null;
}
