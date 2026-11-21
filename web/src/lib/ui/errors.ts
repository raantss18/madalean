// Plain-language errors: « what happened : what to do ». Server text wins when present (already localized).
import { ApiError } from '../api/client';
import { t, tk } from '../i18n/index.svelte';

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const own = tk(`err.${e.kind}`, '');
    if (own) return own;
    if (e.serverText) return e.serverText;
    if (e.status === 0) return t('err.network');
    return t('err.generic', { code: `${e.status} ${e.kind}` });
  }
  if ((e as Error)?.name === 'AbortError') return t('err.cancelled');
  return t('err.generic', { code: String((e as Error)?.message ?? e) });
}

export function isBusy(e: unknown): boolean {
  return e instanceof ApiError && e.status === 409 && e.kind === 'busy';
}
export function isHostOnly(e: unknown): boolean {
  return e instanceof ApiError && e.status === 403 && (e.kind === 'host_only' || e.kind === 'jupyter_host_only' || (Array.isArray(e.body['details']) && (e.body['details'] as string[]).some((d) => d.startsWith('host_only'))));
}
