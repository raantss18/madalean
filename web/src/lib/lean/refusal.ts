// DECISIONS D28: the server refuses, before compiling, Lean code that could run programs on the host (#eval, IO,
// macros, initialize, native code, non-Mathlib imports). The refusal arrives as a failed check whose summary starts
// with « Refusé avant compilation » / « Refused before compiling » and whose `reasons` name the constructs.
import { t, tk } from '../i18n/index.svelte';

interface Checkish { summary?: string; reasons?: string[]; errors?: unknown[] }

const LABELS: [RegExp, string][] = [
  [/#eval|commande exécutée/i, 'd28.eval'],
  [/initialize|au chargement/i, 'd28.initialize'],
  [/méta-programmation|meta-programming|macro|syntax/i, 'd28.meta'],
  [/attribut|attribute/i, 'd28.attribute'],
  [/IO|unsafe|système|system/i, 'd28.io'],
  [/native/i, 'd28.native'],
  [/import/i, 'd28.import'],
];

export function isRefusal(c: Checkish | null | undefined): boolean {
  return Boolean(c && /^(Refusé avant compilation|Refused before compil)/i.test(c.summary ?? ''));
}

/** Plain-language list of what was refused, or null when the check is not a D28 refusal. */
export function refusalOf(c: Checkish | null | undefined): string[] | null {
  if (!isRefusal(c)) return null;
  const raw = c!.reasons?.length ? c!.reasons : [(c!.summary ?? '').replace(/^[^:]*:\s*/, '')];
  return raw.map((r) => {
    const hit = LABELS.find(([re]) => re.test(r));
    return hit ? tk(hit[1], r) : r;
  }).filter((v, i, a) => a.indexOf(v) === i).concat([]).map((s) => s || t('d28.unknown'));
}
