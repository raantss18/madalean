// Light LaTeX scanner for the article editor (session S-R, docs/ARTICLE.md). Pure functions, no DOM: the visual
// mode decorates the source text with what this finds; nothing here ever rewrites the text (perfect round trip by
// construction: the document IS the LaTeX source).

export interface Span { from: number; to: number }
export interface MathSpan extends Span { display: boolean; inner: Span; env: string }
export interface EnvSpan {
  name: string; from: number; to: number;          // from = start of \begin, to = end of \end{…} (or doc end)
  beginTo: number;                                  // end of the \begin{…}[opt] header
  endFrom: number;                                  // start of \end{…} (= to when unclosed)
  opt: string; optSpan: Span | null; depth: number; closed: boolean;
}
export interface Cmd { name: string; from: number; to: number; star: boolean; opt: string; optSpan: Span | null; arg: string; argSpan: Span | null }
export interface Scan { math: MathSpan[]; envs: EnvSpan[]; cmds: Cmd[]; comments: Span[]; markers: { from: number; to: number; text: string }[] }

export const MATH_ENVS = new Set(['equation', 'equation*', 'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
  'eqnarray', 'eqnarray*', 'flalign', 'flalign*', 'alignat', 'alignat*', 'displaymath', 'math']);
export const ARG_CMDS = new Set(['section', 'subsection', 'subsubsection', 'chapter', 'paragraph', 'emph', 'textit', 'textbf',
  'texttt', 'textsc', 'underline', 'cite', 'citep', 'citet', 'parencite', 'textcite', 'ref', 'cref', 'Cref', 'eqref', 'autoref',
  'label', 'footnote', 'includegraphics', 'caption', 'url', 'href', 'title', 'author']);
const NO_ARG = new Set(['item', 'maketitle', 'qed', 'newline', 'par', 'noindent', 'centering', 'medskip', 'smallskip', 'bigskip']);

/** Index of the brace closing the one opened at `open` (text[open] === '{'), or -1. Escapes and nesting handled. */
export function matchBrace(text: string, open: number, max = 20000): number {
  let depth = 0;
  const end = Math.min(text.length, open + max);
  for (let i = open; i < end; i++) {
    const c = text[i];
    if (c === '\\') { i++; continue; }
    if (c === '%') { const nl = text.indexOf('\n', i); if (nl < 0) return -1; i = nl; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return i; }
  }
  return -1;
}

function matchBracket(text: string, open: number): number {
  let depth = 0;
  for (let i = open; i < Math.min(text.length, open + 2000); i++) {
    const c = text[i];
    if (c === '\\') { i++; continue; }
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === ']' && depth === 0) return i;
    else if (c === '\n' && text[i + 1] === '\n') return -1;
  }
  return -1;
}

/** Scan the whole document (linear). Unclosed constructs never throw: they simply end at the document end. */
export function scan(text: string): Scan {
  const math: MathSpan[] = [];
  const envs: EnvSpan[] = [];
  const cmds: Cmd[] = [];
  const comments: Span[] = [];
  const markers: { from: number; to: number; text: string }[] = [];
  const stack: EnvSpan[] = [];
  const n = text.length;
  let i = 0;
  let lineStart = true;
  while (i < n) {
    const c = text[i]!;
    if (lineStart && text.startsWith('%% mdl:', i)) {
      const nl = text.indexOf('\n', i);
      const to = nl < 0 ? n : nl;
      markers.push({ from: i, to, text: text.slice(i, to) });
      i = to; continue;
    }
    lineStart = c === '\n';
    if (c === '%') {
      const nl = text.indexOf('\n', i);
      const to = nl < 0 ? n : nl;
      comments.push({ from: i, to });
      i = to; continue;
    }
    if (c === '$') {
      const display = text[i + 1] === '$';
      const open = display ? 2 : 1;
      let j = i + open;
      let end = -1;
      while (j < n) {
        const d = text[j];
        if (d === '\\') { j += 2; continue; }
        if (d === '$') {
          if (display) { if (text[j + 1] === '$') { end = j; break; } } else { end = j; break; }
        }
        if (!display && d === '\n' && text[j + 1] === '\n') break;       // a blank line ends a broken $
        j++;
      }
      if (end < 0) { i += open; continue; }
      math.push({ from: i, to: end + open, display, inner: { from: i + open, to: end }, env: display ? '$$' : '$' });
      i = end + open; continue;
    }
    if (c === '\\') {
      const nx = text[i + 1];
      if (nx === '(' || nx === '[') {
        const close = nx === '(' ? '\\)' : '\\]';
        const end = text.indexOf(close, i + 2);
        if (end >= 0) {
          math.push({ from: i, to: end + 2, display: nx === '[', inner: { from: i + 2, to: end }, env: nx === '(' ? '\\(' : '\\[' });
          i = end + 2; continue;
        }
        i += 2; continue;
      }
      const m = /^[A-Za-z]+/.exec(text.slice(i + 1, i + 40));
      if (!m) { i += 2; continue; }
      const name = m[0];
      let j = i + 1 + name.length;
      if (name === 'verb') {                                                 // \verb|…|
        const delim = text[j];
        const end = delim ? text.indexOf(delim, j + 1) : -1;
        i = end >= 0 ? end + 1 : j; continue;
      }
      if (name === 'begin' || name === 'end') {
        const b = /^\{([A-Za-z*@]+)\}/.exec(text.slice(j, j + 60));
        if (!b) { i = j; continue; }
        const env = b[1]!;
        let k = j + b[0].length;
        if (name === 'begin') {
          if (MATH_ENVS.has(env)) {
            const endTag = `\\end{${env}}`;
            const e = text.indexOf(endTag, k);
            const to = e >= 0 ? e + endTag.length : n;
            math.push({ from: i, to, display: true, inner: { from: k, to: e >= 0 ? e : n }, env });
            i = to; continue;
          }
          let opt = '', optSpan: Span | null = null;
          if (text[k] === '[') {
            const cl = matchBracket(text, k);
            if (cl > 0) { opt = text.slice(k + 1, cl); optSpan = { from: k + 1, to: cl }; k = cl + 1; }
          }
          const sp: EnvSpan = { name: env, from: i, to: n, beginTo: k, endFrom: n, opt, optSpan, depth: stack.length, closed: false };
          stack.push(sp); envs.push(sp);
          i = k; continue;
        }
        // \end{env}: close the nearest matching open environment
        for (let s = stack.length - 1; s >= 0; s--) {
          if (stack[s]!.name === env) {
            const sp = stack[s]!;
            sp.endFrom = i; sp.to = k; sp.closed = true;
            stack.length = s;
            break;
          }
        }
        i = k; continue;
      }
      let star = false;
      if (text[j] === '*') { star = true; j++; }
      if (ARG_CMDS.has(name)) {
        let opt = '', optSpan: Span | null = null;
        let k = j;
        while (text[k] === ' ') k++;
        if (text[k] === '[') {
          const cl = matchBracket(text, k);
          if (cl > 0) { opt = text.slice(k + 1, cl); optSpan = { from: k + 1, to: cl }; k = cl + 1; }
        }
        if (text[k] === '{') {
          const cl = matchBrace(text, k);
          if (cl > 0) {
            cmds.push({ name, from: i, to: cl + 1, star, opt, optSpan, arg: text.slice(k + 1, cl), argSpan: { from: k + 1, to: cl } });
            i = k + 1; continue;           // continue INSIDE the argument (nested math, commands)
          }
        }
        cmds.push({ name, from: i, to: j, star, opt, optSpan, arg: '', argSpan: null });
        i = j; continue;
      }
      if (NO_ARG.has(name)) cmds.push({ name, from: i, to: j, star, opt: '', optSpan: null, arg: '', argSpan: null });
      i = j; continue;
    }
    i++;
  }
  return { math, envs, cmds, comments, markers };
}

/** Labels defined in a text with the environment or heading they belong to (for \ref completion and chips). */
export interface LabelInfo { label: string; env: string; title: string; number: string; path: string; line: number }

export interface Numbering { section: string; envs: Record<string, string> /* env → counter name ('' = own) */; within: 'section' | 'global' | 'none' }

/** Numbers of sections and theorem-like environments across the files in order (amsthm semantics, approximate). */
export function numberDocument(files: { path: string; text: string }[], num: Numbering): Map<string, { num: string }>
{
  const out = new Map<string, { num: string }>();           // key `${path}:${from}` → number
  let sec = 0;
  const counters: Record<string, number> = {};
  for (const f of files) {
    const s = scan(f.text);
    const items: { pos: number; kind: 'sec' | 'env'; name: string; star: boolean }[] = [];
    for (const c of s.cmds) if (c.name === 'section' || c.name === 'chapter') items.push({ pos: c.from, kind: 'sec', name: c.name, star: c.star });
    for (const e of s.envs) if (e.name in num.envs) items.push({ pos: e.from, kind: 'env', name: e.name, star: false });
    for (const m of s.math) if (/^(equation|align|gather|multline)$/.test(m.env)) items.push({ pos: m.from, kind: 'env', name: '#eq', star: false });
    items.sort((a, b) => a.pos - b.pos);
    for (const it of items) {
      if (it.kind === 'sec') {
        if (it.star) continue;
        sec++;
        if (num.within === 'section') for (const k of Object.keys(counters)) counters[k] = 0;
        out.set(`${f.path}:${it.pos}`, { num: String(sec) });
        continue;
      }
      const counter = it.name === '#eq' ? '#eq' : (num.envs[it.name] || it.name);
      counters[counter] = (counters[counter] ?? 0) + 1;
      const n = counters[counter]!;
      out.set(`${f.path}:${it.pos}`, { num: num.within === 'section' && sec > 0 ? `${sec}.${n}` : String(n) });
    }
  }
  return out;
}

/** Markers of the managed regions of main.tex: name → span of the whole region (begin line … end line). */
export function managedRegions(text: string): { name: string; from: number; to: number }[] {
  const out: { name: string; from: number; to: number }[] = [];
  const re = /^%% mdl:(preamble|front|sections|backmatter) begin$/gm;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const endTag = `%% mdl:${m[1]} end`;
    const e = text.indexOf(endTag, m.index);
    if (e < 0) continue;
    out.push({ name: m[1]!, from: m.index, to: e + endTag.length });
  }
  return out;
}

/** Block marker → {id, kind, dossier}. */
export function parseMarker(line: string): { id: string; kind: string; dossier: string } | null {
  const m = /^%% mdl:block (abstract|b-[0-9a-f]{8}) ([a-z]+)(?: dossier=(\S+))?\s*$/.exec(line);
  return m ? { id: m[1]!, kind: m[2]!, dossier: m[3] ?? '' } : null;
}

/** Dossier linked to the theorem environment that starts at `envFrom`: the enclosing dossier region, or a
 *  `% mdl:lean <id>` line right after the \begin line. */
export function linkedDossier(text: string, envFrom: number, beginTo: number, markers: Scan['markers']): string {
  const after = text.slice(beginTo, beginTo + 200);
  const m = /^[^\n]*\n\s*%\s*mdl:lean\s+([A-Za-z0-9][A-Za-z0-9._-]*)/.exec(after);
  if (m) return m[1]!;
  let last: { dossier: string } | null = null;
  for (const mk of markers) { if (mk.from > envFrom) break; const p = parseMarker(mk.text); if (p) last = p; }
  return last?.dossier ?? '';
}

/** Plain text of a short LaTeX fragment (titles in the outline, chips). */
export function plain(s: string): string {
  return s.replace(/\\(?:emph|textit|textbf|texttt|textsc)\{([^{}]*)\}/g, '$1').replace(/\\label\{[^}]*\}/g, '')
    .replace(/\\[A-Za-z]+\*?/g, '').replace(/[{}]/g, '').replace(/~/g, ' ').trim();
}

export interface Heading { level: number; title: string; from: number; line: number }
export function headings(text: string): Heading[] {
  const out: Heading[] = [];
  const lv: Record<string, number> = { chapter: 0, section: 1, subsection: 2, subsubsection: 3 };
  for (const c of scan(text).cmds) {
    if (c.name in lv && c.argSpan) out.push({ level: lv[c.name]!, title: plain(c.arg), from: c.from, line: text.slice(0, c.from).split('\n').length });
  }
  return out;
}

/** KaTeX macros from the article's settings and simple \newcommand / \DeclareMathOperator definitions. */
export function katexMacros(settingsMacros: Record<string, string>, ...texts: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(settingsMacros)) out[`\\${k}`] = v;
  for (const t of texts) {
    for (const m of t.matchAll(/\\(?:newcommand|renewcommand|providecommand)\*?\{?\\([A-Za-z]+)\}?(?:\[(\d)\])?\{/g)) {
      const open = (m.index ?? 0) + m[0].length - 1;
      const close = matchBrace(t, open);
      if (close > 0 && close - open < 400) out[`\\${m[1]}`] = t.slice(open + 1, close);
    }
    for (const m of t.matchAll(/\\DeclareMathOperator\*?\{\\([A-Za-z]+)\}\{([^{}]*)\}/g)) out[`\\${m[1]}`] = `\\operatorname{${m[2]}}`;
  }
  return out;
}
