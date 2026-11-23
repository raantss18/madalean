// Session S-AT endpoints (docs/API.md « Certificats »): Sage computes a witness, Lean checks it. Kept apart from
// client.ts so the parallel sessions do not edit the same file.
import { request } from './client';
import type { Dossier } from './types';

export interface ApiMsg { key: string; params: Record<string, unknown>; text: string }
export type CertStatus = 'verified' | 'refuted' | 'rejected' | 'no_witness' | 'unavailable' | 'none';
export interface CertOutcome {
  status: CertStatus; kind: string; title: ApiMsg | null; code: string; witness: ApiMsg[]; checker: string;
  axioms: string[] | null; reason: string; errors: string; sage_seconds: number; lean_seconds: number; seconds: number;
  lines: number; statement?: string; workspace?: string; dossier?: Dossier | null;
}
export interface CertKind { id: string; title: ApiMsg; sage: boolean; checker: string }

export const certificates = {
  info: () => request<{ enabled: boolean; sage: boolean; kinds: CertKind[] }>('GET', '/certificates'),
  check: (statement: string, workspace?: string) => request<CertOutcome>('POST', '/certificates/check', { statement, workspace }),
  fromCell: (project_id: string, doc: string, cell_id: string) =>
    request<CertOutcome>('POST', '/certificates/dossier', { project_id, doc, cell_id }),
};

/** Cells whose result Madalean knows how to state in Lean (the server decides; this only hides the action elsewhere). */
export function certifiable(code: string): boolean {
  const last = code.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).pop() ?? '';
  return /^(print\s*\()?\s*(factor|is_prime|is_pseudoprime|gcd|lcm|xgcd|power_mod|inverse_mod|factorial|binomial|next_prime)\s*\(/.test(last)
    || /^[-+*^()\d\s]*[-+*^][-+*^()\d\s]*$/.test(last);
}
