// A `Line` of lib/attack.ts in the user's language; a server reason is translated when known, else shown as given.
import type { Line } from '../../lib/attack';
import { t, tk, tn } from '../../lib/i18n/index.svelte';

export function say(l: Line): string {
  const p = { ...l.params };
  if ('reason' in p) p['reason'] = tk(`attack.reason.${p['reason']}`, String(p['reason'] || '')) || t('attack.reason.unknown');
  return l.plural !== undefined ? tn(l.key, l.plural, p) : tk(l.key, l.key, p);
}
