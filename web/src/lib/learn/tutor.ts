// Learn mode, wired to the server's learning endpoints (docs/RESEARCH_WORKSHOP.md §4): the server builds the prompts
// from the dossier, enforces the gates (attempt first, in order, reflect first), redacts leaks, returns the
// Lean-verified proof at level 5, grades explain-back against the verified proof, and checks exercises with Lean.
// No prompt lives in the client any more.
import { ApiError } from '../api/client';
import { research, type ExplainAnswer, type HintAnswer } from '../api/research';
import { t, tk } from '../i18n/index.svelte';

export const HINT_LEVELS = ['nudge', 'strategy', 'lemma', 'step', 'full'] as const;
export type HintLevel = (typeof HINT_LEVELS)[number];
/** Server level numbers (1..5) → our level names. */
export const LEVEL_OF_NUMBER: Record<number, HintLevel> = { 1: 'nudge', 2: 'strategy', 3: 'lemma', 4: 'step', 5: 'full' };

export async function askHint(did: string, level: HintLevel, ctx: { tried: string; help: string; reflections: string[] }): Promise<HintAnswer> {
  return research.hint(did, { level, tried: ctx.tried, help: ctx.help, reflections: ctx.reflections });
}

export async function askExplainBack(did: string, target: 'statement' | 'proof', text: string, previous: string[]): Promise<ExplainAnswer> {
  return research.explainBack(did, { target, text, previous });
}

/** Plain-language reason for the server's learning gates. */
export function learnError(e: unknown): string {
  if (e instanceof ApiError) {
    const own = tk(`learnerr.${e.kind}`, '');
    if (own) return own;
    if (e.serverText) return e.serverText;
  }
  return t('err.generic', { code: e instanceof ApiError ? `${e.status} ${e.kind}` : String(e) });
}
