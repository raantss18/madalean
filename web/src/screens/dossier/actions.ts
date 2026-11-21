// Shared dossier actions with consistent error handling (409 busy → offer to stop; undo toasts for deletions).
import { api, ApiError } from '../../lib/api/client';
import type { FollowStage, Stage } from '../../lib/api/types';
import { app } from '../../lib/store/app.svelte';
import { t } from '../../lib/i18n/index.svelte';
import { toast } from '../../lib/ui/toasts.svelte';
import { errorText, isBusy } from '../../lib/ui/errors';
import { navigate } from '../../lib/router.svelte';

export function reportError(e: unknown, dossierId?: string): void {
  if (isBusy(e) && dossierId) {
    toast('warn', t('err.busy'), { action: { label: t('dossier.stopCurrent'), run: () => void stop(dossierId) } });
    return;
  }
  toast('error', errorText(e));
}

export async function stop(id: string): Promise<void> {
  try {
    const r = await api.stop(id);
    if (!r.stopped) toast('info', t('dossier.nothingToStop'));
  } catch (e) { reportError(e); }
}

export async function run(id: string, plan: (Stage | { stage: Stage; request?: string; force?: boolean; learn?: boolean })[]): Promise<boolean> {
  try {
    const r = await api.run(id, plan);
    app.m.jobs[r.job.id] = r.job;
    return true;
  } catch (e) { reportError(e, id); return false; }
}

export async function verify(id: string, learn = false): Promise<boolean> {
  try {
    const r = await api.verify(id, learn);
    app.m.jobs[r.job.id] = r.job;
    return true;
  } catch (e) { reportError(e, id); return false; }
}

export async function follow(id: string, text: string, stage: FollowStage): Promise<boolean> {
  try {
    const r = await api.message(id, text, stage);
    app.m.jobs[r.job.id] = r.job;
    return true;
  } catch (e) { reportError(e, id); return false; }
}

export async function removeDossier(id: string): Promise<void> {
  const prev = app.m.dossiers[id];
  const full = app.m.full[id];
  // Optimistic: disappears at once, comes back if the server refuses.
  delete app.m.dossiers[id];
  navigate('/');
  try {
    await api.deleteDossier(id);
    toast('ok', t('dossier.deleted', { title: prev?.title ?? '' }), {
      action: { label: t('common.undo'), run: async () => {
        try {
          const r = await api.restoreDossier(id);
          app.m.full[r.dossier.id] = r.dossier;
          navigate(`/d/${encodeURIComponent(id)}`);
        } catch (e) { reportError(e); }
      } },
    });
  } catch (e) {
    if (prev) app.m.dossiers[id] = prev;
    if (full) app.m.full[id] = full;
    reportError(e, id);
  }
}

export async function patch(id: string, fields: Record<string, unknown>): Promise<boolean> {
  const full = app.m.full[id];
  const before: Record<string, unknown> = {};
  if (full) for (const k of Object.keys(fields)) { before[k] = full[k]; full[k] = fields[k]; }
  try {
    const r = await api.patchDossier(id, fields);
    app.m.full[id] = r.dossier;
    return true;
  } catch (e) {
    if (full) for (const k of Object.keys(before)) full[k] = before[k];
    reportError(e, id);
    return false;
  }
}

export { ApiError };
