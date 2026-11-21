// Learn mode: hint ladder, explain-it-back feedback and faded exercises.
// The server has no dedicated endpoints yet (docs/UI.md « Requests to the server »): this module defines the
// client-side interface `Tutor` and implements it on top of POST /api/assistant (streamed answer on the WS).
import { api } from '../api/client';
import type { Dossier } from '../api/types';

export const HINT_LEVELS = ['nudge', 'strategy', 'lemma', 'step', 'full'] as const;
export type HintLevel = (typeof HINT_LEVELS)[number];

export interface TutorStream {
  onToken(fn: (text: string) => void): void;
  done: Promise<{ text: string; model: string; finish: string }>;
  stop(): void;
}

export interface Tutor {
  /** A hint at `level` (never the full proof before `full`), given what the learner tried and wrote. */
  hint(d: Dossier, level: HintLevel, ctx: { tried: string; helpType: string; reflections: string[]; lang: 'fr' | 'en' }): Promise<TutorStream>;
  /** Feedback on the learner's own explanation: names what is right, probes the weakest part with ONE question. */
  explainBack(d: Dossier, explanation: string, ctx: { target: 'statement' | 'proof'; lang: 'fr' | 'en'; previous: string[] }): Promise<TutorStream>;
}

type Listen = (requestId: string, fn: (ev: { type: string; text: string; model?: string; finish?: string; error?: string }) => void) => () => void;

const PROMPTS = {
  fr: {
    role: 'Tu es un tuteur de mathématiques et de Lean 4 pour un étudiant. Réponds en français, en 2 à 5 phrases, avec $…$ pour les formules. Ne donne JAMAIS la preuve Lean complète.',
    levels: {
      nudge: 'Niveau 1 (coup de pouce) : pose UNE question qui oriente vers l’idée clé, sans la nommer.',
      strategy: 'Niveau 2 (stratégie) : décris la stratégie générale (par exemple récurrence, contraposée, calcul direct, découpage en cas) et pourquoi elle convient, sans tactique ni lemme précis.',
      lemma: 'Niveau 3 (lemme clé) : nomme le résultat ou la définition clé (nom Mathlib si tu le connais avec certitude, sinon l’énoncé mathématique) et demande comment l’utiliser.',
      step: 'Niveau 4 (étape suivante) : indique la prochaine étape concrète (une tactique Lean ou un calcul), sans écrire la suite.',
      full: '',
    } as Record<HintLevel, string>,
    tried: 'Ce que l’étudiant a essayé ou pense :',
    help: 'Type d’aide demandée :',
    refl: 'Ce que l’étudiant a retenu des indices précédents :',
    explain: 'L’étudiant explique avec ses mots {target}. 1) Dis précisément ce qui est juste. 2) Repère la partie la plus faible (vague, circulaire, ou fausse) et pose UNE question pour la creuser. Ne réécris pas l’explication à sa place, ne donne pas la preuve.',
    targetStatement: 'ce que dit l’énoncé Lean',
    targetProof: 'pourquoi la preuve marche',
    prev: 'Échanges précédents :',
  },
  en: {
    role: 'You are a mathematics and Lean 4 tutor for a student. Answer in English, in 2 to 5 sentences, with $…$ for formulas. NEVER give the complete Lean proof.',
    levels: {
      nudge: 'Level 1 (nudge): ask ONE question that points towards the key idea, without naming it.',
      strategy: 'Level 2 (strategy): describe the overall strategy (e.g. induction, contrapositive, direct computation, case split) and why it fits, without a specific tactic or lemma.',
      lemma: 'Level 3 (key lemma): name the key result or definition (its Mathlib name only if you are certain, otherwise the mathematical statement) and ask how to use it.',
      step: 'Level 4 (next step): give the next concrete step (one Lean tactic or one computation), without writing the rest.',
      full: '',
    } as Record<HintLevel, string>,
    tried: 'What the student tried or thinks:',
    help: 'Kind of help requested:',
    refl: 'What the student took from previous hints:',
    explain: 'The student explains in their own words {target}. 1) Say precisely what is right. 2) Find the weakest part (vague, circular or wrong) and ask ONE question to probe it. Do not rewrite the explanation for them, do not give the proof.',
    targetStatement: 'what the Lean statement says',
    targetProof: 'why the proof works',
    prev: 'Previous exchanges:',
  },
};

export function hintPrompt(d: Dossier, level: HintLevel, ctx: { tried: string; helpType: string; reflections: string[]; lang: 'fr' | 'en' }): string {
  const p = PROMPTS[ctx.lang];
  const parts = [p.role, p.levels[level], '', `Problem: ${d.understood_display || d.problem}`, 'Lean statement:', '```lean', d.current.statement, '```'];
  if (ctx.tried.trim()) parts.push(p.tried, ctx.tried.trim());
  if (ctx.helpType) parts.push(`${p.help} ${ctx.helpType}`);
  if (ctx.reflections.length) parts.push(p.refl, ...ctx.reflections.map((r, i) => `${i + 1}. ${r}`));
  return parts.join('\n');
}

export function explainPrompt(d: Dossier, explanation: string, ctx: { target: 'statement' | 'proof'; lang: 'fr' | 'en'; previous: string[] }): string {
  const p = PROMPTS[ctx.lang];
  const parts = [p.role, p.explain.replace('{target}', ctx.target === 'statement' ? p.targetStatement : p.targetProof), '',
    'Lean:', '```lean', ctx.target === 'statement' ? d.current.statement : d.current.proof || d.current.statement, '```'];
  if (ctx.previous.length) parts.push(p.prev, ...ctx.previous);
  parts.push('---', explanation.trim());
  return parts.join('\n');
}

export function assistantTutor(listen: Listen): Tutor {
  async function ask(prompt: string): Promise<TutorStream> {
    // `dossier_id` is NOT sent as context for hints: the server would put the current proof in the model's
    // context. The statement (or, for explain-back of a proof, the proof) is in the prompt itself.
    const { request_id } = await api.assistant([{ role: 'user', content: prompt }], {});
    let tokenFn: (t: string) => void = () => {};
    let acc = '';
    const done = new Promise<{ text: string; model: string; finish: string }>((resolve, reject) => {
      const off = listen(request_id, (ev) => {
        if (ev.type === 'assistant.token') { acc += ev.text; tokenFn(ev.text); }
        else if (ev.type === 'assistant.done') { off(); resolve({ text: ev.text || acc, model: ev.model ?? '', finish: ev.finish ?? '' }); }
        else if (ev.type === 'assistant.error') { off(); reject(new Error(ev.text || ev.error || 'assistant')); }
      });
    });
    return { onToken: (fn) => { tokenFn = fn; }, done, stop: () => void api.stopAssistant(request_id).catch(() => {}) };
  }
  return {
    hint: (d, level, ctx) => ask(hintPrompt(d, level, ctx)),
    explainBack: (d, explanation, ctx) => ask(explainPrompt(d, explanation, ctx)),
  };
}

// ---- Faded proofs (worked example → completion problems): steps are removed from the END backwards.

/** Splits a Lean proof into header (up to and including `:= by`) and tactic lines. */
export function splitProof(code: string): { header: string; tactics: string[] } | null {
  const i = code.search(/:=\s*by\b/);
  if (i < 0) return null;
  const m = /:=\s*by\b[ \t]*/.exec(code.slice(i))!;
  const end = i + m[0].length;
  const header = code.slice(0, end);
  const body = code.slice(end).replace(/^\n/, '');
  const tactics = body.split('\n').filter((l) => l.trim() !== '');
  if (header.trimEnd().endsWith('by') && tactics.length === 0) return null;
  return { header, tactics };
}

/** Fading level k (1 = last step removed, …, n = whole proof removed). Returns the exercise text and the hidden lines. */
export function fadeProof(code: string, k: number): { exercise: string; hidden: string[]; total: number } | null {
  const sp = splitProof(code);
  if (!sp || sp.tactics.length === 0) return null;
  const n = sp.tactics.length;
  const kk = Math.max(1, Math.min(n, k));
  const shown = sp.tactics.slice(0, n - kk);
  const hidden = sp.tactics.slice(n - kk);
  const indent = /^\s*/.exec(hidden[0] ?? '  ')?.[0] || '  ';
  const exercise = `${sp.header}\n${[...shown, `${indent}sorry -- ${'…'}`].join('\n')}\n`;
  return { exercise, hidden, total: n };
}
