// « Premiers pas » (S-AQ, DECISIONS D49): the first-run assistant's pure logic — steps, navigation, when it opens by
// itself, what the final checklist says. No Svelte, no fetch: unit-tested in tests/unit/setup-wizard.test.ts.

export const STEPS = ['welcome', 'tools', 'local', 'keys', 'hf', 'claude', 'modes', 'auto', 'pair', 'done'] as const;
export type StepId = (typeof STEPS)[number];

/** The manual page (docs/manual/<lang>/<page>.md, opened in the Aide screen) that explains each step, and the
 * heading to scroll to (ids of docs/manual/index.json, one per language). */
export const HELP: Record<StepId, { page: string; anchor?: { fr: string; en: string } }> = {
  welcome: { page: 'first-config', anchor: { fr: 'lassistant-premiers-pas', en: 'the-first-steps-assistant' } },
  tools: { page: 'components' },
  local: { page: 'components', anchor: { fr: 'modeles-locaux', en: 'local-models' } },
  keys: { page: 'first-config', anchor: { fr: 'cles-des-fournisseurs-en-ligne', en: 'keys-of-online-providers' } },
  hf: { page: 'first-config', anchor: { fr: 'jeton-hugging-face-goedel-prover-32b-en-ligne', en: 'hugging-face-token-goedel-prover-32b-online' } },
  claude: { page: 'first-config', anchor: { fr: 'claude-chef-dorchestre-et-renfort-payant', en: 'claude-conductor-and-paid-reinforcement' } },
  modes: { page: 'first-config', anchor: { fr: 'ou-travaillent-les-modeles', en: 'where-the-models-work' } },
  auto: { page: 'first-config', anchor: { fr: 'comportements-automatiques-et-manuels', en: 'automatic-and-manual-behaviours' } },
  pair: { page: 'pairing' },
  done: { page: 'first-config', anchor: { fr: 'liste-de-verification', en: 'checklist' } },
};

export interface WizardInfo {
  schema: string; steps: string[]; step: string; visited: string[]; models: '' | 'all' | 'prover' | 'none';
  done: boolean; completed: boolean; reminder: boolean; auto: boolean;
}

export function isStep(s: string | undefined | null): s is StepId {
  return !!s && (STEPS as readonly string[]).includes(s);
}
export function indexOf(s: StepId): number { return STEPS.indexOf(s); }
export function next(s: StepId): StepId | null { const i = indexOf(s); return i < STEPS.length - 1 ? STEPS[i + 1]! : null; }
export function prev(s: StepId): StepId | null { const i = indexOf(s); return i > 0 ? STEPS[i - 1]! : null; }

/** Step to show: the one in the address when valid, else where the user stopped (server), else the first. */
export function resumeStep(urlStep: string | undefined, info: Pick<WizardInfo, 'step' | 'completed'> | null): StepId {
  if (isStep(urlStep)) return urlStep;
  if (info && !info.completed && isStep(info.step)) return info.step;
  return STEPS[0];
}

/** 0–100, for the progress bar: steps behind the current one. */
export function progress(s: StepId): number { return Math.round((indexOf(s) / (STEPS.length - 1)) * 100); }

/** Opens by itself only on the host, at the start of the web app on the home screen, while it is neither finished
 * nor put off, and never on a server that already held the user's work (`auto` is computed by the server). */
export function shouldAutoOpen(local: boolean, routeName: string, wizardDone: boolean | undefined, info: Pick<WizardInfo, 'auto'> | null): boolean {
  return local && routeName === 'home' && wizardDone === false && !!info?.auto;
}

/** The Home reminder card: on the host, while the assistant is not finished and the user did not hide the card. */
export function showReminder(local: boolean, info: Pick<WizardInfo, 'completed' | 'reminder'> | null): boolean {
  return local && !!info && !info.completed && info.reminder;
}

/** Steps the user went through (for the stepper's ticks), the current one excluded. */
export function visitedAfterMove(visited: readonly string[], from: StepId): StepId[] {
  const seen = new Set([...visited, from]);
  return STEPS.filter((s) => seen.has(s));
}

// ---- local models: which set, and how much it downloads
export type ModelSet = 'all' | 'prover' | 'none';
export interface ModelFile { key: string; file: string; present: boolean; bytes: number; download_bytes: number }

/** The choice to show selected: what the user picked before, else the server's recommendation, else « none ». */
export function modelChoice(saved: string, recommended: string | undefined): ModelSet {
  for (const v of [saved, recommended]) if (v === 'all' || v === 'prover' || v === 'none') return v;
  return 'none';
}
export function modelsMissing(files: ModelFile[], set: ModelSet): ModelFile[] {
  const keys = set === 'all' ? ['Q4_K_M', 'formalizer', 'explainer'] : set === 'prover' ? ['Q4_K_M'] : [];
  return files.filter((f) => keys.includes(f.key) && !f.present);
}

// ---- reuse of system tools
export type SageSource = 'auto' | 'own' | 'system';
export type TexEngine = 'auto' | 'tectonic' | 'system';
/** Recommended copy of SageMath: the system's when it is compatible (version ≥ 10.0 and its Jupyter kernel), else
 * Madalean's own one; the 2.0.0 behaviour (`auto`) when the machine check is not known. */
export function recommendedSage(system: { found?: boolean | null; compatible?: boolean | null } | undefined, ownInstalled: boolean): SageSource {
  if (ownInstalled) return 'auto';
  if (system?.compatible) return 'system';
  return system?.found === undefined || system?.found === null ? 'auto' : 'own';
}
/** tectonic always (same PDF everywhere, offline), the TeX Live as the automatic fallback = `auto`. */
export function recommendedTex(): TexEngine { return 'auto'; }

// ---- the final checklist
export interface NextStep { id: string; done: boolean; title: { fr: string; en: string }; help: string }
export interface ChecklistRow { id: string; done: boolean; title: string; help: string; optional: boolean }
const OPTIONAL = new Set(['pair', 'sage', 'tex']);
export function checklist(steps: NextStep[], lang: 'fr' | 'en'): ChecklistRow[] {
  return steps.map((s) => ({ id: s.id, done: s.done, title: s.title[lang] ?? s.title.fr, help: s.help, optional: OPTIONAL.has(s.id) }));
}
export function checklistSummary(rows: ChecklistRow[]): { done: number; total: number; essentialLeft: number } {
  return { done: rows.filter((r) => r.done).length, total: rows.length, essentialLeft: rows.filter((r) => !r.done && !r.optional).length };
}
