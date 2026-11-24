// Gates and « Mal compris » reports (docs/DOSSIER_FLOW.md).
import { request } from './client';
import type { Dossier, Job, ReportReason } from './types';

const enc = encodeURIComponent;
export interface FlowAnswer { dossier?: Dossier; job?: Job | null; [k: string]: unknown }
export type ReportTarget = 'meaning' | 'statement' | 'proof' | 'event';
export const REASONS: ReportReason[] = ['wrong_object', 'too_general', 'missing_hypothesis', 'wrong_claim', 'ignored_request', 'other'];

export const flow = {
  gate: (id: string, b: { gate_id: string; action: 'approve' | 'edit' | 'reject'; text?: string; candidate?: number }) =>
    request<FlowAnswer>('POST', `/dossiers/${enc(id)}/gate`, b),
  approveMany: (items: { dossier_id: string; gate_id: string }[]) => request<FlowAnswer>('POST', '/dossiers/gates/approve', { items }),
  report: (id: string, b: { target: ReportTarget; ref?: number; reason: ReportReason; text?: string }) =>
    request<FlowAnswer>('POST', `/dossiers/${enc(id)}/report`, b),
};
