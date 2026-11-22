// S-AB: a long formula (a list of roots, a big matrix row…) must wrap on a phone instead of being clipped. KaTeX
// breaks lines only in inline mode, after relations / binary operators, never inside \left…\right: for a long
// result, drop \left / \right (the delimiters stay) and allow a break after each comma of the outer level.
export const WRAP_AT = 70;

export function breakable(src: string): string | null {
  if (src.length < WRAP_AT || /\\begin\{/.test(src)) return null;          // short, or a matrix/array: as it is
  const s = src.replace(/\\(left|right)\.\s*/g, '').replace(/\\(left|right)(?![a-zA-Z])\s*/g, '');
  let out = '', depth = 0;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i]!;
    if (ch === '\\' && i + 1 < s.length) {                                 // a command or an escaped brace: copy whole
      const m = /^\\([a-zA-Z]+|.)/.exec(s.slice(i))!;
      if (m[1] === '{') depth++;
      else if (m[1] === '}') depth--;
      out += m[0]; i += m[0].length - 1; continue;
    }
    if (ch === '(' || ch === '[' || ch === '{') depth++;
    else if (ch === ')' || ch === ']' || ch === '}') depth--;
    out += ch;
    if (ch === ',' && depth <= 1) out += '\\allowbreak ';
  }
  return out;
}
