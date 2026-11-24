// Session S-AX endpoints (docs/API.md « Littérature », DECISIONS D56): literature search of a dossier, verbatim
// quotes, cited lemmas, attachments read once. Kept apart from client.ts so the parallel sessions do not edit it.
import { request } from './client';
import type { Dossier, Job } from './types';

export interface LitReference {
  id: string; title: string; authors: string[]; year: number | null; venue: string; doi: string; arxiv: string;
  url: string; kind: 'journal' | 'book' | 'proceedings' | 'preprint' | 'thesis' | 'unknown'; peer_reviewed: boolean;
  confirmed_by: string[]; providers: string[]; source_verified?: boolean;
}
export interface LitQuote { text: string; text_index: number; start: number; end: number; location: string; picked_by: string }
export interface LitText { kind: string; provider: string; text: string; locator: string; licence: string; suspect: boolean }
export interface LitLean {
  name: string; statement: string; compiled: boolean; status: 'in_mathlib' | 'proved' | 'to_prove' | 'unformalized';
  mathlib_name: string; library_name: string; model: string; note: string; child_dossier?: string;
}
export interface LitItem {
  id: string; reference: LitReference; texts: LitText[]; quotes: LitQuote[]; lean: LitLean; score: number;
  bibtex: string; key: string; origin: 'literature' | 'attachment'; label: string;
}
export interface LitResult {
  statement: string; depth: 'quick' | 'deep'; items: LitItem[]; mathlib: { name: string; signature: string }[];
  providers: Record<string, { ok: boolean; count: number; error: string }>; rejected: Record<string, number>;
  local_mode: boolean; cancelled: boolean; cached: boolean; message: string; seconds: number;
}
export interface LitConditional {
  verdict: string; source: string; admitted: string[]; code: string;
  cited: { name: string; ref: string; title: string; short: string; kind: string; peer_reviewed: boolean; quote: string; location: string }[];
}
export interface LitState {
  literature: LitResult | null; running: boolean; enabled: boolean; depth: 'quick' | 'deep'; mode: string; stale: boolean;
  conditional: LitConditional | null;
}
export interface Attachment {
  n: number; sha: string; shelf: string; source_id: string; name: string; kind: 'image' | 'pdf' | 'tex' | 'bib' | 'url';
  state: 'reading' | 'read' | 'unread' | 'error'; verified: boolean; reference: LitReference | null;
  transcription: { text: string; model: string } | null; items: LitItem[]; cell?: string; cells?: string[];
}

const base = (id: string) => `/dossiers/${encodeURIComponent(id)}`;
export const literature = {
  get: (id: string) => request<LitState>('GET', `${base(id)}/literature`),
  search: (id: string, depth?: 'quick' | 'deep', refresh = false) =>
    request<{ started: boolean }>('POST', `${base(id)}/literature`, { depth, refresh }),
  stop: (id: string) => request<{ stopped: boolean }>('POST', `${base(id)}/literature/stop`),
  addSource: (id: string, item: string) => request<{ source: { key: string }; duplicate: unknown }>('POST', `${base(id)}/literature/items/${item}/source`, {}),
  cite: (id: string, item: string) => request<{ key: string }>('POST', `${base(id)}/literature/items/${item}/cite`, {}),
  prove: (id: string, item: string) => request<{ dossier: Dossier; job: Job | null }>('POST', `${base(id)}/literature/items/${item}/prove`, {}),
  attachments: (id: string) => request<{ attachments: Attachment[] }>('GET', `${base(id)}/attachments`),
  attachFile: (id: string, file: File) => {
    const fd = new FormData();
    fd.append('file', file, file.name);
    return request<{ attachment: Attachment; read: boolean }>('POST', `${base(id)}/attachments`, fd);
  },
  attachUrl: (id: string, url: string) => request<{ attachment: Attachment; read: boolean }>('POST', `${base(id)}/attachments`, { url }),
  reread: (id: string, n: number) => request<{ started: boolean }>('POST', `${base(id)}/attachments/${n}/reread`),
};

/** D59: Calcul « Demande » cells attach to the PROJECT (Calcul cells are project notebooks, not dossiers). */
const cbase = (pid: string) => `/calcul/${encodeURIComponent(pid)}/attachments`;
export const calculAttachments = {
  list: (pid: string, cell: string) => request<{ attachments: Attachment[] }>('GET', `${cbase(pid)}?cell=${encodeURIComponent(cell)}`),
  attachFile: (pid: string, cell: string, file: File) => {
    const fd = new FormData();
    fd.append('file', file, file.name);
    fd.append('cell', cell);
    return request<{ attachment: Attachment; read: boolean }>('POST', cbase(pid), fd);
  },
  unlink: (pid: string, cell: string, n: number) =>
    request<{ attachment: Attachment }>('DELETE', `${cbase(pid)}/${n}?cell=${encodeURIComponent(cell)}`),
};

export const ATTACH_ACCEPT = 'image/png,image/jpeg,image/webp,application/pdf,.tex,.bib,.ltx,application/x-tex';
