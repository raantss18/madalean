// Plain words of the flow (D66): the server sends keys (`activity`, reasons, verdicts), the interface translates them;
// an unknown key falls back on the phase, never on the raw key.
import { tk, t } from '../../lib/i18n/index.svelte';
import type { FlowPhase } from '../../lib/api/types';
import { app } from '../../lib/store/app.svelte';
import { reportError } from './actions';
import type { FlowAnswer } from '../../lib/api/flow';
import { ApiError } from '../../lib/api/client';
import { toast } from '../../lib/ui/toasts.svelte';

export function phaseText(p: FlowPhase | ''): string {
  return tk(`flow.phase.${p || 'other'}`, t('flow.phase.other'));
}

export function activityText(x: { phase: FlowPhase; activity: string; params: Record<string, unknown> }): string {
  const p: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(x.params)) p[k] = typeof v === 'number' ? v : String(v ?? '');
  const a = x.activity;
  return (a && (tk(`activity.${a}`, '', p) || tk(a, '', p) || tk(`stage.${a}`, '', p) || tk(`flow.phase.${a}`, '', p))) || phaseText(x.phase);
}

/** Every flow call may answer with the dossier and / or the job it started. */
export async function applyAnswer(id: string, r: FlowAnswer): Promise<void> {
  if (r.job) app.m.jobs[r.job.id] = r.job;
  if (r.dossier?.id) app.m.full[r.dossier.id] = r.dossier;
  else await app.ensureDossier(id, true).catch(() => null);
}

export async function flowError(e: unknown, id: string): Promise<void> {
  if (e instanceof ApiError && e.status === 409 && e.kind === 'stale_gate') {
    toast('warn', t('gate.stale'));
    await app.ensureDossier(id, true).catch(() => null);
    return;
  }
  reportError(e, id);
}
