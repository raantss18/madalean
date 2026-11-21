// Session S-R endpoints (docs/ARTICLE.md §5): the article's LaTeX project. Kept apart from client.ts / research.ts
// so the parallel sessions do not edit the same file.
import { request } from './client';

const enc = encodeURIComponent;
const base = (pid: string) => `/research/projects/${enc(pid)}/texproject`;

export interface TexFile { path: string; text: string; hash: string }
export interface ThmEnv { env: string; fr: string; en: string; style: 'plain' | 'definition' | 'remark'; counter: string }
export interface TexSettings {
  document: { template: string; class: string; options: string[]; language: 'fr' | 'en' };
  front: { title: string; authors: { name: string; affiliation?: string; email?: string }[]; date: string };
  packages: { base: string[]; extra: string[]; removed: string[] };
  macros: Record<string, string>;
  theorems: { numbering: 'section' | 'global' | 'none'; envs: ThmEnv[] };
  bibliography: { style: string };
  layout: { paper: 'a4' | 'letter'; margin: string; font: string; linespread: number };
  madalean: { lean_appendix: boolean; verification_table: boolean; preamble: 'managed' | 'manual' };
}
export type DossierState = 'verified' | 'conditional' | 'unverified' | 'missing';
export interface Diagnostic { severity: 'error' | 'warning' | 'info'; path: string; line: number; message: string;
  plain: { key: string; params: Record<string, string | number>; text: string };
  fix: null | { kind: 'add_package' | 'remove_package' | 'fetch' | 'replace' | 'add_macro' | 'add_theorem' | 'open_sources' | 'repair';
    name?: string; files?: string[]; find?: string; replace?: string; env?: string } }
export interface PackageInfo { name: string; file: string; kind: string; state: 'cached' | 'bundle' | 'missing' | 'system'; where: { path: string; line: number }[] }
export interface Packages { class: string; packages: PackageInfo[]; needed: { name: string; why: string; path: string; line: number; state: string }[];
  redundant: { name: string; reason: string; path: string; line: number }[]; refused: { name: string; instead: string; path: string; line: number }[];
  engine: 'tectonic' | 'system' | 'none'; digest: string }
export interface CompileResult { ok: boolean; pdf: string | null; hash: string; seconds: number; engine: string; cached: boolean;
  diagnostics: Diagnostic[]; packages: Packages; states: Record<string, { status: DossierState; title: string }> }
export interface Suggestion { id: string; block_id: string; path: string; find: string; occurrence: number; at: 'replace' | 'after' | 'before';
  replace: string; kind: string; origin: 'assistant' | 'research' | 'user'; rationale: string; model: string; created: number;
  state: 'pending' | 'accepted' | 'rejected' | 'stale'; anchor?: { path: string; from: number; to: number } }
export interface CiteKey { key: string; title: string; author: string; year: number | null }
export interface LabelRef { label: string; path: string; line: number; env: string; title: string }
export interface TexProject {
  settings: TexSettings; files: TexFile[]; order: string[]; outline: { path: string; line: number; level: string; title: string }[];
  labels: LabelRef[]; cites: string[]; keys: CiteKey[]; links: { dossier: string; path: string; line: number }[];
  states: Record<string, { status: DossierState; title: string }>; dossiers: { id: string; title: string; status: DossierState }[];
  figures: string[]; templates: { id: string; fr: string; en: string; class: string }[]; fonts: string[];
  lock: Record<string, unknown>; last: { ok: boolean; hash: string; pdf: string | null; t: number; engine: string; seconds: number } | null;
  suggestions: Suggestion[]; created?: boolean;
}
export interface Version { id: string; t: number; label: string; auto: boolean; by: string; files: string[] }
export type AssistAction = 'rewrite' | 'shorten' | 'formalise' | 'translate_fr' | 'translate_en' | 'proof_sketch' | 'sage';
export interface Overleaf { found: boolean; url: string; container: string; image: string; source: string; alive: boolean; local: boolean }

type DeepPartial<T> = { [K in keyof T]?: T[K] extends object ? (T[K] extends unknown[] ? T[K] : DeepPartial<T[K]>) : T[K] };

export const articleApi = {
  project: (pid: string) => request<TexProject>('GET', base(pid)),
  save: (pid: string, path: string, text: string, baseHash: string) =>
    request<{ path: string; hash: string; unchanged?: boolean; text?: string | null }>('POST', `${base(pid)}/file`, { path, text, base: baseHash }),
  addSection: (pid: string, title: string, after = '') => request<{ path: string; text: string; hash: string; order: string[] }>('POST', `${base(pid)}/sections`, { title, after }),
  deleteSection: (pid: string, path: string) => request<{ order: string[] }>('DELETE', `${base(pid)}/file?path=${enc(path)}`),
  order: (pid: string, sections: string[]) => request<{ order: string[] }>('POST', `${base(pid)}/order`, { sections }),
  settings: (pid: string, patch: DeepPartial<TexSettings>) => request<{ settings: TexSettings; files: TexFile[] }>('PATCH', `${base(pid)}/settings`, patch),
  template: (pid: string, template: string) => request<{ settings: TexSettings; files: TexFile[] }>('POST', `${base(pid)}/template`, { template }),
  compile: (pid: string, opts: { force?: boolean; fetch?: boolean } = {}, signal?: AbortSignal) =>
    request<CompileResult>('POST', `${base(pid)}/compile`, opts, { signal }),
  pdfUrl: (pid: string, h: string) => `/api${base(pid)}/pdf?h=${enc(h)}`,
  forward: (pid: string, path: string, line: number) =>
    request<{ result: { page: number; x: number; y: number; w: number; h: number; line: number } | null }>('GET', `${base(pid)}/synctex?path=${enc(path)}&line=${line}`),
  inverse: (pid: string, page: number, x: number, y: number) =>
    request<{ result: { path: string; line: number } | null }>('GET', `${base(pid)}/synctex?page=${page}&x=${x.toFixed(1)}&y=${y.toFixed(1)}`),
  packages: (pid: string) => request<Packages>('GET', `${base(pid)}/packages`),
  versions: (pid: string) => request<{ versions: Version[] }>('GET', `${base(pid)}/versions`),
  makeVersion: (pid: string, label: string) => request<{ version: Version | null }>('POST', `${base(pid)}/versions`, { label }),
  versionFile: (pid: string, vid: string, path: string) => request<{ text: string }>('GET', `${base(pid)}/versions/${enc(vid)}?path=${enc(path)}`),
  restoreVersion: (pid: string, vid: string) => request<{ changed: string[] }>('POST', `${base(pid)}/versions/${enc(vid)}/restore`, {}),
  suggestions: (pid: string, state = 'pending') => request<{ suggestions: Suggestion[] }>('GET', `${base(pid)}/suggestions?state=${enc(state)}`),
  accept: (pid: string, sid: string, applied: boolean) => request<{ suggestion: Suggestion; files: TexFile[] }>('POST', `${base(pid)}/suggestions/${enc(sid)}/accept`, { applied }),
  reject: (pid: string, sid: string) => request<{ suggestion: Suggestion }>('POST', `${base(pid)}/suggestions/${enc(sid)}/reject`, {}),
  assist: (pid: string, body: { action: AssistAction; path: string; from: number; text: string }) =>
    request<{ request_id: string; mode: string }>('POST', `${base(pid)}/assist`, body),
  lean: (pid: string, body: { path: string; text: string; title?: string }) =>
    request<{ dossier: { id: string; title: string }; linked: boolean }>('POST', `${base(pid)}/lean`, body),
  figureFromCalcul: (pid: string, asset: string) => request<{ path: string }>('POST', `${base(pid)}/figures`, { calcul_asset: asset }),
  figureUpload: (pid: string, file: File) => { const fd = new FormData(); fd.append('file', file); return request<{ path: string }>('POST', `${base(pid)}/figures`, fd); },
  figureUrl: (pid: string, path: string) => `/api${base(pid)}/figure?path=${enc(path)}`,
  overleaf: (pid: string, refresh = false) => request<Overleaf>('GET', `${base(pid)}/overleaf${refresh ? '?refresh=1' : ''}`),
  exportUrl: (pid: string, format: 'overleaf' | 'pdf') => `/api${base(pid)}/export?format=${format}`,
  importZip: (pid: string, file: File) => {
    const fd = new FormData(); fd.append('file', file);
    return request<{ changed: string[]; skipped: { name: string; why: string }[]; refs_bib: boolean; new_keys: string[]; preamble_manual: boolean }>('POST', `${base(pid)}/import`, fd);
  },
};
