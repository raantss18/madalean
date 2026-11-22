// S-AB: is what was typed in a new cell code (run it) or a request in words (the model writes the code)? An instant
// guess for the chip « Code / Demande »; the server confirms it with the installed Sage's preparser
// (POST …/detect). The user can always switch the chip in one click.
const NL_START = /^(trace[rz]?|dessine|calcule[rz]?|factorise[rz]?|r[ée]sou[st]|r[ée]soudre|montre|donne|trouve|cherche|d[ée]veloppe|simplifie|d[ée]rive|int[èe]gre|quel(le)?s?|combien|comment|pourquoi|est-ce|peux-tu|affiche|v[ée]rifie|compare|liste|[ée]cris|fais|construis|repr[ée]sente|d[ée]termine|cr[ée]e|plot|draw|compute|calculate|factor|solve|show|give|find|list|what|which|how|why|is|are|does|can|simplify|expand|integrate|differentiate|check|verify|write|make|build|create|determine|graph)\b(?![ \t]*[(=.[])/i;
const WORDS = /\b(le|la|les|des|du|de|un|une|sur|pour|avec|dans|et|entre|son|sa|ses|of|the|and|for|with|between|its|from|on)\b/gi;
const CODE = /[=()[\]{}]|\b(def|for|import|return|lambda|print)\b|\.\w+\(|^\s*#|\^|\*\*|:\s*$/m;

export type Guess = 'code' | 'ask';

export function guessKind(text: string): Guess {
  const t = text.trim();
  if (!t) return 'code';
  const bare = t.replace(/(['"]).*?\1/g, '');
  let nl = 0, code = 0;
  const verb = NL_START.test(t);
  if (verb) nl += 2;
  const fw = (bare.match(WORDS) ?? []).length;
  const words = (t.match(/[\p{L}]{2,}/gu) ?? []).length;
  if (fw >= 2) nl += 2; else if (fw === 1 && words >= 3) nl += 1;
  if (t.endsWith('?')) nl += 2;
  if (/[À-ÿ²³]/.test(bare)) nl += 1;
  if (CODE.test(bare)) code += 1;
  if (!verb && (/^[\w.]+\s*\(.*\)\s*$/s.test(t) || /^[\w\s+\-*/^().,[\]]+$/.test(t))) code += 1;
  return nl > code ? 'ask' : 'code';
}
