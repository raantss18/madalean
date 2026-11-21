// Settings are applied immediately (like L Katta): optimistic, rolled back with a plain message if refused.
import { api, ApiError } from '../../lib/api/client';
import type { Settings } from '../../lib/api/types';
import { app } from '../../lib/store/app.svelte';
import { optimistic } from '../../lib/store/optimistic';
import { t, tk } from '../../lib/i18n/index.svelte';
import { toast } from '../../lib/ui/toasts.svelte';
import { errorText } from '../../lib/ui/errors';

export async function saveSettings(patch: Partial<Settings> | Record<string, unknown>, quiet = false): Promise<boolean> {
  const s = app.m.settings;
  if (!s) return false;
  const r = await optimistic(
    () => {
      const before = JSON.parse(JSON.stringify(s)) as Settings;
      for (const [k, v] of Object.entries(patch)) {
        if (k === 'server' || k === 'sampling' || k === 'prefer') (s as Record<string, unknown>)[k] = { ...(s[k] as object), ...(v as object) };
        else (s as Record<string, unknown>)[k] = v;
      }
      return () => { app.m.settings = before; };
    },
    () => api.patchSettings(patch),
    {
      onSuccess: (v) => { app.m.settings = v.settings; if (!quiet) toast('ok', t('settings.saved')); },
      onError: (e) => {
        if (e instanceof ApiError && Array.isArray(e.body['details'])) {
          const d = (e.body['details'] as string[]).map((x) => tk(`settings.err.${x.split(':')[0]}`, x, { key: x.split(':')[1] ?? '' }));
          toast('error', d.join(' · '));
        } else toast('error', errorText(e));
      },
    },
  );
  return r.ok;
}
