// Typed client of « Mémoire » (D62, docs/MEMORY.md): memory bundles, import preview, backups, dataset export.
import { ApiError, request } from './client';

export const MEMORY_PARTS = ['library', 'lessons', 'recipes', 'graphs', 'digests'] as const;
export type MemoryPart = (typeof MEMORY_PARTS)[number];

export interface BackupSettings {
  enabled: boolean; every_days: number; keep: number; folder: string; last: number; last_error: string;
  include_copyrighted: boolean; include_files: boolean; folder_effective?: string;
  files?: { name: string; bytes: number; t: number }[];
}
export interface MemoryStatus {
  counts: { library: number; lessons: number; recipes: number; unverified: number };
  projects: { id: string; title: string }[];
  backups: BackupSettings;
}
export interface PreviewItem { action: 'add' | 'verify' | 'validate' | 'reference' | 'unverified' | 'skip'; reason: string;
  name?: string; title?: string; id?: string; kind?: string; request?: string; workspace?: string; license?: string;
  nodes?: number; same_statements?: number; project?: string }
export interface Preview {
  bundle: { madalean: string; created: string; schema: number; workspaces: Record<string, { lean: string; mathlib: string }>; excluded: number };
  items: Partial<Record<MemoryPart, PreviewItem[]>>;
  summary: Partial<Record<MemoryPart, Record<string, number>>>;
}
export interface ImportSession { state: 'ready' | 'running' | 'done' | 'error'; progress: { stage?: string; done?: number; total?: number; name?: string };
  report: Record<string, unknown> | null; preview: Preview | null }
export interface Unverified { name: string; title: string; statement: string; workspace: string; reason: string; detail: string; t_import: number }
export interface References {
  graphs: { id: string; title: string; project: string; nodes: number; same_statements: number; imported: number }[];
  digests: { id: string; title: string; project: string; statements: number; license: string; imported: number }[];
}

export function exportUrl(parts: MemoryPart[], projects: string[] | null, copyrighted: boolean, files: boolean): string {
  const q = new URLSearchParams({ parts: parts.join(',') });
  if (projects !== null) q.set('projects', projects.join(','));
  if (copyrighted) q.set('include_copyrighted', '1');
  if (files) q.set('include_files', '1');
  return `/api/memory/export?${q.toString()}`;
}

/** Uploads a bundle (raw bytes, host only) → token + dry-run preview. Nothing is written by the server. */
async function inspect(file: Blob): Promise<{ token: string; preview: Preview }> {
  const res = await fetch('/api/memory/import', {
    method: 'POST', credentials: 'same-origin', body: file, headers: { 'Content-Type': 'application/octet-stream' },
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) throw new ApiError(res.status, typeof data['error'] === 'string' ? (data['error'] as string) : `http_${res.status}`, data);
  return data as unknown as { token: string; preview: Preview };
}

export const memoryApi = {
  status: () => request<MemoryStatus>('GET', '/memory'),
  inspect,
  apply: (token: string) => request<{ started: boolean }>('POST', `/memory/import/${encodeURIComponent(token)}`, {}),
  session: (token: string) => request<ImportSession>('GET', `/memory/import/${encodeURIComponent(token)}`),
  unverified: () => request<{ entries: Unverified[] }>('GET', '/memory/unverified'),
  reverify: () => request<{ token: string }>('POST', '/memory/unverified/verify', {}),
  forgetUnverified: (name: string) => request<{ deleted: boolean }>('DELETE', `/memory/unverified/${encodeURIComponent(name)}`),
  references: () => request<References>('GET', '/memory/references'),
  deleteReference: (kind: 'graphs' | 'digests', id: string) => request<{ deleted: boolean }>('DELETE', `/memory/references/${kind}/${encodeURIComponent(id)}`),
  backups: (patch: Partial<BackupSettings>) => request<{ backups: BackupSettings }>('PATCH', '/memory/backups', patch),
  backupNow: () => request<{ name: string; bytes: number; removed: string[] }>('POST', '/memory/backups/run', {}),
  datasetUrl: '/api/memory/dataset',
};
