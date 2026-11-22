// The article editor (session S-R): ONE CodeMirror 6 document per .tex file = the LaTeX source itself.
// « Visuel » mode decorates that source (rendered maths, theorem boxes, citations and references as chips, figures,
// hidden markup) and reveals the raw LaTeX where the cursor is; « Source » mode shows it plainly with highlighting.
// Switching mode only reconfigures decorations: same text, same selection, same undo history (perfect round trip
// by construction; unknown LaTeX is shown as a protected raw block and never rewritten). Lazy chunk.
import { EditorState, StateEffect, StateField, Compartment, Annotation, type Extension, type Range, type Transaction } from '@codemirror/state';
import {
  EditorView, Decoration, WidgetType, keymap, drawSelection, highlightActiveLine, lineNumbers, showTooltip,
  type DecorationSet, type Tooltip, placeholder as cmPlaceholder,
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab, undo, redo } from '@codemirror/commands';
import { StreamLanguage, HighlightStyle, syntaxHighlighting, bracketMatching, type StringStream } from '@codemirror/language';
import { tags } from '@lezer/highlight';
import { autocompletion, type CompletionContext, type CompletionResult, type Completion } from '@codemirror/autocomplete';
import { search, searchKeymap } from '@codemirror/search';
import { katexNow, loadKatex } from '../katex.svelte';
import '../../styles/article.css';
import { scan, managedRegions, parseMarker, linkedDossier, plain, MATH_ENVS, type Scan } from './latex';

// ---------------------------------------------------------------- context given by the screen
export interface EditorCtx {
  lang: 'fr' | 'en';
  path: string;
  thm: Record<string, { title: string; style: string }>;       // theorem-like environments (+ proof)
  numbers: Map<string, { num: string }>;                       // `${path}:${from}` → number
  labels: Map<string, { env: string; title: string; num: string; path: string }>;
  keys: Map<string, { title: string; author: string; year: number | null }>;
  states: Record<string, { status: string; title: string }>;   // dossier id → Lean state
  macros: Record<string, string>;                              // KaTeX macros
  figureUrl: (path: string) => string;
  title: string; authors: string;
  t: (key: string, params?: Record<string, string | number>) => string;
}
export interface SugView { id: string; from: number; to: number; at: 'replace' | 'after' | 'before'; replace: string; kind: string; origin: string; model: string }
export interface DiagView { line: number; severity: string; text: string }
export interface EditorOptions {
  parent: HTMLElement; doc: string; path: string; visual: boolean; lineNumbers: boolean; ariaLabel: string; placeholder?: string;
  ctx: () => EditorCtx;
  onChange: (path: string, doc: string) => void;
  onSelection?: (s: { from: number; to: number; text: string } | null) => void;
  onSuggestion?: (id: string, accept: boolean) => void;
  onDossier?: (id: string) => void;
  onAction?: (name: 'options' | 'title' | 'save' | 'compile' | 'forward') => void;
}

const External = Annotation.define<boolean>();
const refresh = StateEffect.define<null>();
const setSugs = StateEffect.define<SugView[]>();
const setDiags = StateEffect.define<DiagView[]>();

// ---------------------------------------------------------------- source highlighting (LaTeX StreamLanguage)
interface TexState { math: string }
const texMode = {
  name: 'latex',
  startState: (): TexState => ({ math: '' }),
  token(stream: StringStream, st: TexState): string | null {
    if (stream.match(/^%% mdl:.*/)) return 'meta';
    if (stream.match(/^%.*/)) return 'comment';
    if (st.math) {
      if (stream.match(st.math)) { st.math = ''; return 'string'; }
      if (stream.match(/^\\[A-Za-z]+/)) return 'string';
      stream.next(); return 'string';
    }
    if (stream.match('$$')) { st.math = '$$'; return 'string'; }
    if (stream.match('$')) { st.math = '$'; return 'string'; }
    if (stream.match('\\[')) { st.math = '\\]'; return 'string'; }
    if (stream.match('\\(')) { st.math = '\\)'; return 'string'; }
    if (stream.match(/^\\(begin|end)\{[^}]*\}/)) return 'keyword';
    if (stream.match(/^\\(section|subsection|subsubsection|chapter|paragraph)\*?/)) return 'heading';
    if (stream.match(/^\\[A-Za-z@]+\*?/)) return 'tagName';
    if (stream.match(/^\\./)) return 'escape';
    if (stream.match(/^[{}[\]]/)) return 'bracket';
    stream.next();
    return null;
  },
  languageData: { commentTokens: { line: '%' } },
  tokenTable: { meta: tags.meta, escape: tags.escape, heading: tags.heading },
};
const texHighlight = HighlightStyle.define([
  { tag: tags.comment, class: 'tx-com' }, { tag: tags.meta, class: 'tx-meta' }, { tag: tags.string, class: 'tx-math' },
  { tag: tags.keyword, class: 'tx-env' }, { tag: tags.tagName, class: 'tx-cmd' }, { tag: tags.heading, class: 'tx-head' },
  { tag: tags.escape, class: 'tx-esc' }, { tag: tags.bracket, class: 'tx-br' },
]);

// ---------------------------------------------------------------- widgets
// KaTeX is not in this chunk (S-AP): the editor shows the TeX source until it has loaded, then refreshes.
function renderTex(src: string, display: boolean, macros: Record<string, string>): string {
  const katex = katexNow();
  if (!katex) return '';
  try {
    return katex.renderToString(src, { displayMode: display, throwOnError: false, trust: false, strict: 'ignore',
      output: 'htmlAndMathml', maxExpand: 500, maxSize: 20, macros: { ...macros } });
  } catch { return ''; }
}

class MathWidget extends WidgetType {
  readonly ready = katexNow() !== null;
  constructor(readonly src: string, readonly display: boolean, readonly macros: Record<string, string>, readonly label: string) { super(); }
  override eq(o: MathWidget) { return o.src === this.src && o.display === this.display && o.ready === this.ready; }
  override toDOM() {
    const el = document.createElement('span');
    el.className = this.display ? 'cm-mathw cm-mathw-display' : 'cm-mathw';
    el.innerHTML = renderTex(this.src, this.display, this.macros) || '';
    if (!el.innerHTML) el.textContent = this.src;
    el.title = this.label;
    return el;
  }
  override ignoreEvent() { return false; }
}

class ChipWidget extends WidgetType {
  constructor(readonly text: string, readonly cls: string, readonly title: string) { super(); }
  override eq(o: ChipWidget) { return o.text === this.text && o.cls === this.cls && o.title === this.title; }
  override toDOM() {
    const el = document.createElement('span');
    el.className = `cm-chip ${this.cls}`;
    el.textContent = this.text;
    if (this.title) el.title = this.title;
    return el;
  }
  override ignoreEvent() { return false; }
}

class HeaderWidget extends WidgetType {
  constructor(readonly head: string, readonly opt: string, readonly badge: { id: string; status: string; label: string } | null,
    readonly onDossier: ((id: string) => void) | undefined, readonly openLabel: string) { super(); }
  override eq(o: HeaderWidget) { return o.head === this.head && o.opt === this.opt && o.badge?.status === this.badge?.status && o.badge?.id === this.badge?.id; }
  override toDOM() {
    const el = document.createElement('span');
    el.className = 'cm-thm-head';
    const b = document.createElement('strong');
    b.textContent = this.head;
    el.appendChild(b);
    if (this.opt) { const o = document.createElement('span'); o.className = 'cm-thm-opt'; o.textContent = ` (${this.opt})`; el.appendChild(o); }
    el.appendChild(document.createTextNode('.'));
    if (this.badge) {
      const a = document.createElement('button');
      a.type = 'button';
      a.className = `cm-lean cm-lean-${this.badge.status}`;
      a.textContent = this.badge.label;
      a.setAttribute('aria-label', `${this.badge.label} — ${this.openLabel}`);
      a.title = this.openLabel;
      a.addEventListener('mousedown', (e) => { e.preventDefault(); e.stopPropagation(); this.onDossier?.(this.badge!.id); });
      a.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.onDossier?.(this.badge!.id); } });
      el.appendChild(a);
    }
    return el;
  }
  override ignoreEvent(e: Event) { return e.type === 'mousedown' && (e.target as HTMLElement).classList.contains('cm-lean'); }
}

class TextWidget extends WidgetType {
  constructor(readonly text: string, readonly cls: string, readonly label = '') { super(); }
  override eq(o: TextWidget) { return o.text === this.text && o.cls === this.cls; }
  override toDOM() {
    const el = document.createElement('span');
    el.className = this.cls;
    el.textContent = this.text;
    if (this.label) el.setAttribute('aria-label', this.label);
    return el;
  }
  override ignoreEvent() { return false; }
}

class BlockWidget extends WidgetType {
  constructor(readonly html: string, readonly cls: string, readonly action: (() => void) | null, readonly actionLabel: string) { super(); }
  override eq(o: BlockWidget) { return o.html === this.html && o.cls === this.cls; }
  override toDOM() {
    const el = document.createElement('div');
    el.className = `cm-blockw ${this.cls}`;
    const span = document.createElement('div');
    span.textContent = this.html;
    el.appendChild(span);
    if (this.action) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'cm-blockw-btn'; b.textContent = this.actionLabel;
      b.addEventListener('mousedown', (e) => { e.preventDefault(); this.action!(); });
      b.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.action!(); } });
      el.appendChild(b);
    }
    return el;
  }
  override ignoreEvent() { return true; }
}

class FrontWidget extends WidgetType {
  constructor(readonly title: string, readonly authors: string, readonly edit: () => void, readonly editLabel: string, readonly empty: string) { super(); }
  override eq(o: FrontWidget) { return o.title === this.title && o.authors === this.authors; }
  override toDOM() {
    const el = document.createElement('div');
    el.className = 'cm-front';
    const h = document.createElement('div'); h.className = 'cm-front-title'; h.textContent = this.title || this.empty; el.appendChild(h);
    if (this.authors) { const a = document.createElement('div'); a.className = 'cm-front-authors'; a.textContent = this.authors; el.appendChild(a); }
    const b = document.createElement('button'); b.type = 'button'; b.className = 'cm-blockw-btn'; b.textContent = this.editLabel;
    b.addEventListener('mousedown', (e) => { e.preventDefault(); this.edit(); });
    b.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.edit(); } });
    el.appendChild(b);
    return el;
  }
  override ignoreEvent() { return true; }
}

class ImageWidget extends WidgetType {
  constructor(readonly url: string, readonly alt: string) { super(); }
  override eq(o: ImageWidget) { return o.url === this.url; }
  override toDOM() {
    const el = document.createElement('span');
    el.className = 'cm-figw';
    if (this.url.endsWith('.pdf') || /\.pdf(&|$)/.test(this.url)) { el.textContent = `▣ ${this.alt}`; return el; }
    const img = document.createElement('img');
    img.src = this.url; img.alt = this.alt; img.loading = 'lazy';
    el.appendChild(img);
    return el;
  }
  override ignoreEvent() { return false; }
}

class SugWidget extends WidgetType {
  constructor(readonly s: SugView, readonly cb: ((id: string, accept: boolean) => void) | undefined, readonly t: EditorCtx['t']) { super(); }
  override eq(o: SugWidget) { return o.s.id === this.s.id && o.s.replace === this.s.replace; }
  override toDOM() {
    const el = document.createElement('span');
    el.className = 'cm-sug';
    el.setAttribute('role', 'group');
    el.setAttribute('aria-label', this.t('ae.sug.group', { kind: this.t(`ae.sug.kind.${this.s.kind}`) || this.s.kind }));
    const ins = document.createElement('ins');
    ins.className = 'cm-sug-ins';
    ins.textContent = this.s.replace;
    el.appendChild(ins);
    for (const [ok, label, cls] of [[true, this.t('ae.sug.accept'), 'ok'], [false, this.t('ae.sug.reject'), 'no']] as const) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = `cm-sug-btn ${cls}`; b.textContent = ok ? '✓' : '✕';
      b.setAttribute('aria-label', label); b.title = label;
      b.addEventListener('mousedown', (e) => { e.preventDefault(); e.stopPropagation(); this.cb?.(this.s.id, ok); });
      b.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.cb?.(this.s.id, ok); } });
      el.appendChild(b);
    }
    return el;
  }
  override ignoreEvent() { return true; }
}

// ---------------------------------------------------------------- visual decorations
const RAW_LABEL: Record<string, string> = { tikzpicture: 'TikZ', tikzcd: 'TikZ-cd', tabular: 'ae.raw.table', table: 'ae.raw.table',
  verbatim: 'Verbatim', lstlisting: 'Code', algorithm: 'ae.raw.algo', algorithmic: 'ae.raw.algo', frame: 'ae.raw.frame' };
const SOFT_ENVS = new Set(['itemize', 'enumerate', 'description', 'figure', 'figure*', 'center', 'quote', 'quotation', 'abstract',
  'document', 'frontmatter', 'flushleft', 'flushright', 'minipage', 'table']);

function touches(sel: { from: number; to: number }, from: number, to: number): boolean {
  return sel.from <= to && sel.to >= from;
}

function lineSpan(state: EditorState, pos: number): { from: number; to: number; number: number } {
  const l = state.doc.lineAt(pos);
  return { from: l.from, to: l.to, number: l.number };
}

function buildVisual(state: EditorState, c: EditorCtx, o: EditorOptions, sc: Scan): Range<Decoration>[] {
  const text = state.doc.toString();
  const sel = state.selection.main;
  const out: Range<Decoration>[] = [];
  const hiddenLines: { from: number; to: number }[] = [];
  const isMain = c.path === 'main.tex';
  const inMath = (p: number) => sc.math.some((m) => p > m.from && p < m.to);
  const curLine = state.doc.lineAt(sel.head).number;
  // managed regions of main.tex → one block widget each
  const regions = isMain ? managedRegions(text) : [];
  const inRegion = (p: number) => regions.some((r) => p >= r.from && p <= r.to);
  for (const r of regions) {
    const w = r.name === 'front'
      ? new FrontWidget(c.title, c.authors, () => o.onAction?.('title'), c.t('ae.front.edit'), c.t('ae.front.empty'))
      : new BlockWidget(c.t(`ae.region.${r.name}`), `cm-region cm-region-${r.name}`, r.name === 'sections' ? null : () => o.onAction?.('options'),
        c.t('ae.region.open'));
    out.push(Decoration.replace({ widget: w, block: true }).range(r.from, r.to));
  }
  if (isMain) {
    const docBegin = text.indexOf('\\begin{document}');
    const pre = regions.find((r) => r.name === 'preamble');
    if (pre && docBegin > pre.to) {
      // the user's own preamble lines: protected raw block
      let p = pre.to + 1;
      let first = true;
      while (p < docBegin) {
        const l = state.doc.lineAt(p);
        out.push(Decoration.line({ class: 'cm-raw' + (first ? ' cm-raw-first' : ''), attributes: first ? { 'data-raw': c.t('ae.raw.preamble') } : {} }).range(l.from));
        first = false;
        p = l.to + 1;
      }
    }
    for (const re of [/^\\begin\{document\}\s*$/gm, /^\\end\{document\}\s*$/gm, /^\\maketitle\s*$/gm]) {
      let m: RegExpExecArray | null;
      while ((m = re.exec(text))) { const l = lineSpan(state, m.index); if (l.number !== curLine) hiddenLines.push(l); }
    }
  }
  // block markers and `% mdl:lean` link lines
  for (const mk of sc.markers) { if (!inRegion(mk.from)) hiddenLines.push(lineSpan(state, mk.from)); }
  for (const cm of sc.comments) {
    if (inRegion(cm.from)) continue;
    const s = text.slice(cm.from, cm.to);
    if (/^%\s*mdl:/.test(s)) { const l = lineSpan(state, cm.from); if (l.number !== curLine && l.from === cm.from) hiddenLines.push(l); continue; }
    if (cm.to > cm.from + 1 && !inMath(cm.from)) out.push(Decoration.mark({ class: 'cm-annot' }).range(cm.from, cm.to));
  }
  // maths
  for (const m of sc.math) {
    if (inRegion(m.from)) continue;
    if (touches(sel, m.from, m.to)) {
      out.push(Decoration.mark({ class: m.display ? 'cm-math-src cm-math-src-d' : 'cm-math-src' }).range(m.from, m.to));
      continue;
    }
    let src = text.slice(m.inner.from, m.inner.to);
    if (MATH_ENVS.has(m.env)) {
      const base = m.env.replace('*', '');
      const inner = base === 'equation' || base === 'displaymath' || base === 'math' ? src
        : `\\begin{${base === 'align' || base === 'eqnarray' || base === 'flalign' ? 'aligned' : base === 'alignat' ? 'alignedat' : base === 'multline' ? 'gathered' : 'gathered'}}${src.replace(/\\label\{[^}]*\}/g, '').replace(/\\(nonumber|notag)\b/g, '')}\\end{${base === 'align' || base === 'eqnarray' || base === 'flalign' ? 'aligned' : base === 'alignat' ? 'alignedat' : 'gathered'}}`;
      src = inner.replace(/\\label\{[^}]*\}/g, '');
    }
    const label = c.t('ae.math.label', { src: text.slice(m.inner.from, m.inner.to).slice(0, 200) });
    const startsLine = state.doc.lineAt(m.from).from === m.from && /^\s*$/.test(text.slice(state.doc.lineAt(m.from).from, m.from));
    const endsLine = state.doc.lineAt(m.to).to === m.to || /^\s*$/.test(text.slice(m.to, state.doc.lineAt(m.to).to));
    if (m.display && startsLine && endsLine) {
      const l1 = state.doc.lineAt(m.from), l2 = state.doc.lineAt(m.to);
      out.push(Decoration.replace({ widget: new MathWidget(src, true, c.macros, label), block: true }).range(l1.from, l2.to));
    } else {
      out.push(Decoration.replace({ widget: new MathWidget(src, m.display, c.macros, label) }).range(m.from, m.to));
    }
  }
  // environments
  for (const e of sc.envs) {
    if (inRegion(e.from) || inMath(e.from)) continue;
    const bLine = state.doc.lineAt(e.from), eLine = state.doc.lineAt(Math.min(e.endFrom, text.length));
    const thm = c.thm[e.name];
    if (thm || e.name === 'abstract') {
      const style = e.name === 'proof' ? 'proof' : e.name === 'abstract' ? 'abstract' : thm!.style;
      for (let ln = bLine.number; ln <= eLine.number; ln++) {
        const l = state.doc.line(ln);
        out.push(Decoration.line({ class: `cm-thm cm-thm-${style}${ln === bLine.number ? ' cm-thm-first' : ''}${ln === eLine.number ? ' cm-thm-last' : ''}` }).range(l.from));
      }
      if (!touches(sel, e.from, e.beginTo)) {
        const num = c.numbers.get(`${c.path}:${e.from}`)?.num ?? '';
        const title = e.name === 'abstract' ? c.t('ae.abstract') : thm!.title;
        const head = e.name === 'proof' ? (e.opt ? plain(e.opt) : title) : `${title}${num ? ' ' + num : ''}`;
        let badge = null;
        if (e.name !== 'proof' && e.name !== 'abstract' && thm!.style !== 'definition' && thm!.style !== 'remark') {
          const did = linkedDossier(text, e.from, e.beginTo, sc.markers);
          if (did) {
            const st = c.states[did]?.status ?? 'missing';
            badge = { id: did, status: st, label: c.t(`ae.lean.${st}`) };
          }
        }
        out.push(Decoration.replace({ widget: new HeaderWidget(head, e.name === 'proof' ? '' : plain(e.opt), badge, o.onDossier, c.t('ae.lean.open')) }).range(e.from, e.beginTo));
      }
      if (e.closed && !touches(sel, e.endFrom, e.to) && eLine.number !== curLine) {
        out.push(Decoration.replace({ widget: new TextWidget(e.name === 'proof' ? '∎' : '', e.name === 'proof' ? 'cm-qed' : 'cm-endmark', e.name === 'proof' ? c.t('ae.qed') : '') }).range(e.endFrom, e.to));
      }
      continue;
    }
    if (SOFT_ENVS.has(e.name)) {
      const cls = e.name.startsWith('figure') || e.name === 'table' ? 'cm-fig' : e.name === 'center' ? 'cm-center' : '';
      if (cls) for (let ln = bLine.number; ln <= eLine.number; ln++) out.push(Decoration.line({ class: cls }).range(state.doc.line(ln).from));
      for (const [p, end] of [[e.from, e.beginTo], [e.endFrom, e.to]] as const) {
        if (!e.closed && p === e.endFrom) continue;
        const l = state.doc.lineAt(p);
        if (l.number !== curLine && text.slice(l.from, l.to).trim() === text.slice(p, end).trim()) out.push(Decoration.line({ class: 'cm-struct' }).range(l.from));
      }
      continue;
    }
    if (e.depth > 0 && sc.envs.some((x) => x !== e && x.from < e.from && x.to > e.to && !c.thm[x.name] && !SOFT_ENVS.has(x.name))) continue;
    // unknown environment: protected raw block, shown as written
    const raw = RAW_LABEL[e.name] ?? '';
    const label = raw.startsWith('ae.') ? c.t(raw) : raw || c.t('ae.raw.env', { env: e.name });
    for (let ln = bLine.number; ln <= eLine.number; ln++) {
      out.push(Decoration.line({ class: 'cm-raw' + (ln === bLine.number ? ' cm-raw-first' : ''), attributes: ln === bLine.number ? { 'data-raw': label } : {} }).range(state.doc.line(ln).from));
    }
  }
  const rawLine = new Set<number>();
  for (const e of sc.envs) if (!c.thm[e.name] && !SOFT_ENVS.has(e.name) && e.name !== 'abstract') {
    const a = state.doc.lineAt(e.from).number, b = state.doc.lineAt(Math.min(e.endFrom, text.length)).number;
    for (let ln = a; ln <= b; ln++) rawLine.add(ln);
  }
  // commands
  for (const cmd of sc.cmds) {
    if (inRegion(cmd.from) || inMath(cmd.from) || rawLine.has(state.doc.lineAt(cmd.from).number)) continue;
    const near = touches(sel, cmd.from, cmd.to);
    const a = cmd.argSpan;
    switch (cmd.name) {
      case 'section': case 'subsection': case 'subsubsection': case 'chapter': case 'paragraph': {
        if (!a) break;
        const l = state.doc.lineAt(cmd.from);
        out.push(Decoration.line({ class: `cm-h cm-h-${cmd.name}` }).range(l.from));
        if (!near && l.number !== curLine) {
          const num = cmd.star ? '' : c.numbers.get(`${c.path}:${cmd.from}`)?.num ?? '';
          out.push(Decoration.replace({ widget: new TextWidget(num && cmd.name !== 'paragraph' ? `${num}  ` : '', 'cm-h-num') }).range(cmd.from, a.from));
          out.push(Decoration.replace({}).range(a.to, cmd.to));
        }
        break;
      }
      case 'emph': case 'textit': case 'textbf': case 'texttt': case 'textsc': case 'underline': {
        if (!a || near) break;
        const cls = { emph: 'cm-it', textit: 'cm-it', textbf: 'cm-bf', texttt: 'cm-tt', textsc: 'cm-sc', underline: 'cm-ul' }[cmd.name];
        out.push(Decoration.replace({}).range(cmd.from, a.from));
        if (a.to > a.from) out.push(Decoration.mark({ class: cls }).range(a.from, a.to));
        out.push(Decoration.replace({}).range(a.to, cmd.to));
        break;
      }
      case 'cite': case 'citep': case 'citet': case 'parencite': case 'textcite': {
        if (!a || near) break;
        const keys = cmd.arg.split(',').map((k) => k.trim()).filter(Boolean);
        const parts = keys.map((k) => { const e = c.keys.get(k); return e ? `${e.author || k}${e.year ? ' ' + e.year : ''}` : `${k} ?`; });
        const unknown = keys.some((k) => !c.keys.has(k));
        const title = keys.map((k) => c.keys.get(k)?.title || c.t('ae.cite.unknown', { key: k })).join(' ; ');
        out.push(Decoration.replace({ widget: new ChipWidget(`[${parts.join('; ')}${cmd.opt ? ', ' + plain(cmd.opt) : ''}]`, unknown ? 'cm-cite cm-bad' : 'cm-cite', title) }).range(cmd.from, cmd.to));
        break;
      }
      case 'ref': case 'cref': case 'Cref': case 'eqref': case 'autoref': {
        if (!a || near) break;
        const L = c.labels.get(cmd.arg.trim());
        const name = L ? (L.env === 'section' ? c.t('ae.ref.section') : c.thm[L.env]?.title ?? (L.env === '#eq' ? '' : L.env)) : '';
        const txt = L ? `${cmd.name === 'ref' || cmd.name === 'eqref' ? '' : name + ' '}${cmd.name === 'eqref' ? '(' + (L.num || '?') + ')' : L.num || L.title || cmd.arg}`.trim() : `${cmd.arg} ?`;
        out.push(Decoration.replace({ widget: new ChipWidget(`→ ${txt}`, L ? 'cm-ref' : 'cm-ref cm-bad', L ? `${name} ${L.title}`.trim() : c.t('ae.ref.unknown', { label: cmd.arg })) }).range(cmd.from, cmd.to));
        break;
      }
      case 'label': {
        if (!a || near) break;
        if (cmd.arg.startsWith('ml:')) out.push(Decoration.replace({}).range(cmd.from, cmd.to));      // generated dossier label
        else out.push(Decoration.replace({ widget: new ChipWidget(`#${cmd.arg}`, 'cm-label', c.t('ae.label')) }).range(cmd.from, cmd.to));
        break;
      }
      case 'footnote': {
        if (!a || near) break;
        out.push(Decoration.replace({ widget: new TextWidget('✱', 'cm-fn-mark', c.t('ae.footnote')) }).range(cmd.from, a.from));
        if (a.to > a.from) out.push(Decoration.mark({ class: 'cm-fn' }).range(a.from, a.to));
        out.push(Decoration.replace({}).range(a.to, cmd.to));
        break;
      }
      case 'includegraphics': {
        if (!a || near) break;
        const p = cmd.arg.trim();
        const url = /^figures\/[0-9a-f]{16}\.(png|jpg|pdf)$/.test(p) ? c.figureUrl(p) : '';
        out.push(Decoration.replace({ widget: url ? new ImageWidget(url, c.t('ae.figure.alt', { path: p })) : new ChipWidget(`▣ ${p}`, 'cm-bad', c.t('ae.figure.missing')) }).range(cmd.from, cmd.to));
        break;
      }
      case 'caption': {
        if (!a) break;
        out.push(Decoration.mark({ class: 'cm-caption' }).range(a.from, a.to));
        if (!near) { out.push(Decoration.replace({ widget: new TextWidget(c.t('ae.caption') + ' ', 'cm-caption-head') }).range(cmd.from, a.from)); out.push(Decoration.replace({}).range(a.to, cmd.to)); }
        break;
      }
      case 'item': {
        if (near) break;
        out.push(Decoration.replace({ widget: new TextWidget('•', 'cm-bullet') }).range(cmd.from, cmd.to));
        break;
      }
      case 'maketitle': case 'centering': case 'noindent': case 'medskip': case 'smallskip': case 'bigskip':
        if (!near) out.push(Decoration.mark({ class: 'cm-dim' }).range(cmd.from, cmd.to));
        break;
    }
  }
  // merge consecutive hidden lines into block replacements
  hiddenLines.sort((x, y) => x.from - y.from);
  let cur: { from: number; to: number } | null = null;
  const flush = () => { if (cur) out.push(Decoration.replace({ block: true }).range(cur.from, cur.to)); };
  for (const l of hiddenLines) {
    if (cur && l.from <= cur.to + 1) cur.to = Math.max(cur.to, l.to);
    else { flush(); cur = { ...l }; }
  }
  flush();
  return out;
}

// ---------------------------------------------------------------- the editor
export interface ArticleEditor {
  view: EditorView;
  open(path: string, doc: string): void;                         // switch file (keeps a state per file)
  replaceDoc(path: string, doc: string): void;                    // external update (other device, accepted suggestion)
  setVisual(v: boolean): void;
  setKeymap(k: 'default' | 'vim' | 'emacs'): Promise<void>;
  setLineNumbers(v: boolean): void;
  refresh(): void;
  setSuggestions(s: SugView[]): void;
  setDiagnostics(d: DiagView[]): void;
  applySuggestion(s: SugView): boolean;
  selection(): { from: number; to: number; text: string; line: number };
  insert(text: string, cursorOffset?: number): void;
  wrap(before: string, after: string, placeholder?: string): void;
  goto(line: number): void;
  undo(): void; redo(): void;
  focus(): void;
  destroy(): void;
}

export function createArticleEditor(o: EditorOptions): ArticleEditor {
  const visualC = new Compartment(), keymapC = new Compartment(), gutterC = new Compartment(), spellC = new Compartment();
  let visual = o.visual;
  let path = o.path;
  const states = new Map<string, EditorState>();

  const deco = StateField.define<{ set: DecorationSet; scan: Scan | null }>({
    create: (st) => compute(st),
    update(v, tr) {
      if (tr.docChanged || tr.selection || tr.effects.some((e) => e.is(refresh))) return compute(tr.state);
      return v;
    },
    provide: (f) => EditorView.decorations.from(f, (v) => v.set),
  });
  function compute(st: EditorState): { set: DecorationSet; scan: Scan | null } {
    if (!visual) return { set: Decoration.none, scan: null };
    const sc = scan(st.doc.toString());
    try { return { set: Decoration.set(buildVisual(st, { ...o.ctx(), path }, o, sc), true), scan: sc }; }
    catch (e) { console.warn('article decorations', e); return { set: Decoration.none, scan: sc }; }
  }

  // math live preview while the cursor is inside a formula
  const mathTip = StateField.define<Tooltip | null>({
    create: () => null,
    update(_v, tr) {
      if (!visual) return null;
      const st = tr.state;
      const sel = st.selection.main;
      const sc = tr.state.field(deco).scan;
      const m = sc?.math.find((x) => sel.from >= x.from && sel.to <= x.to);
      if (!m) return null;
      const src = st.doc.sliceString(m.inner.from, m.inner.to);
      return {
        pos: m.from, above: true, strictSide: false, arrow: false,
        create: () => {
          const dom = document.createElement('div');
          dom.className = 'cm-math-tip';
          dom.setAttribute('role', 'status');
          dom.innerHTML = renderTex(MATH_ENVS.has(m.env) && !/^(equation|displaymath|math)\*?$/.test(m.env) ? `\\begin{aligned}${src.replace(/\\label\{[^}]*\}/g, '').replace(/\\(nonumber|notag)\b/g, '')}\\end{aligned}` : src.replace(/\\label\{[^}]*\}/g, ''), m.display, o.ctx().macros) || '';
          return { dom };
        },
      };
    },
    provide: (f) => showTooltip.from(f),
  });

  // suggestions (track changes) and compile diagnostics, mapped through edits
  const sugField = StateField.define<{ list: SugView[]; set: DecorationSet }>({
    create: () => ({ list: [], set: Decoration.none }),
    update(v, tr) {
      let list = v.list;
      for (const e of tr.effects) if (e.is(setSugs)) list = e.value;
      if (tr.docChanged && list === v.list) list = list.map((s) => ({ ...s, from: tr.changes.mapPos(s.from, 1), to: tr.changes.mapPos(s.to, -1) }))
        .filter((s) => s.to >= s.from);
      if (list === v.list && !tr.effects.some((e) => e.is(refresh))) return v;
      const ds: Range<Decoration>[] = [];
      const t = o.ctx().t;
      for (const s of list) {
        if (s.at === 'replace' && s.to > s.from) ds.push(Decoration.mark({ class: 'cm-sug-del', attributes: { title: t('ae.sug.del') } }).range(s.from, s.to));
        const at = s.at === 'before' ? s.from : s.to;
        ds.push(Decoration.widget({ widget: new SugWidget(s, o.onSuggestion, t), side: 1 }).range(at));
      }
      return { list, set: Decoration.set(ds, true) };
    },
    provide: (f) => EditorView.decorations.from(f, (v) => v.set),
  });
  const diagField = StateField.define<DecorationSet>({
    create: () => Decoration.none,
    update(v, tr) {
      for (const e of tr.effects) if (e.is(setDiags)) {
        const ds: Range<Decoration>[] = [];
        for (const d of e.value) {
          if (d.line < 1 || d.line > tr.state.doc.lines) continue;
          ds.push(Decoration.line({ class: d.severity === 'error' ? 'cm-errline' : 'cm-warnline', attributes: { title: d.text } }).range(tr.state.doc.line(d.line).from));
        }
        return Decoration.set(ds, true);
      }
      return tr.docChanged ? v.map(tr.changes) : v;
    },
    provide: (f) => EditorView.decorations.from(f),
  });

  // managed regions of main.tex are generated from the settings: protected in both modes
  const protect = EditorState.changeFilter.of((tr: Transaction) => {
    if (tr.annotation(External) || path !== 'main.tex') return true;
    const rs = managedRegions(tr.startState.doc.toString());
    if (!rs.length) return true;
    return rs.flatMap((r) => [r.from, r.to]);
  });

  // completion: commands, environments, labels, citation keys
  const COMMANDS = ['section{}', 'subsection{}', 'emph{}', 'textbf{}', 'cite{}', 'cref{}', 'ref{}', 'eqref{}', 'label{}', 'footnote{}',
    'begin{}', 'end{}', 'frac{}{}', 'sqrt{}', 'mathbb{}', 'mathcal{}', 'operatorname{}', 'text{}', 'left(', 'right)', 'sum_{}^{}',
    'int_{}^{}', 'lim_{}', 'infty', 'leq', 'geq', 'neq', 'subseteq', 'in', 'to', 'mapsto', 'forall', 'exists', 'alpha', 'beta',
    'gamma', 'delta', 'varepsilon', 'lambda', 'mu', 'sigma', 'varphi', 'omega', 'includegraphics[width=0.7\\linewidth]{}', 'item ', 'qedhere'];
  function complete(cx: CompletionContext): CompletionResult | null {
    const line = cx.state.doc.lineAt(cx.pos);
    const before = line.text.slice(0, cx.pos - line.from);
    const c = o.ctx();
    let m = /\\(?:c|C)?ref\{([^}]*)$|\\(?:eqref|autoref|pageref)\{([^}]*)$/.exec(before);
    if (m) {
      const typed = (m[1] ?? m[2] ?? '');
      return { from: cx.pos - typed.length, validFor: /^[^}]*$/, options: [...c.labels.entries()].map(([k, v]): Completion => ({
        label: k, detail: `${c.thm[v.env]?.title ?? (v.env === 'section' ? c.t('ae.ref.section') : v.env)} ${v.num}`.trim(), info: v.title || undefined, type: 'variable' })) };
    }
    m = /\\cite[pt]?\*?(?:\[[^\]]*\])?\{(?:[^}]*,)?\s*([^},]*)$/.exec(before);
    if (m) {
      const typed = m[1] ?? '';
      return { from: cx.pos - typed.length, validFor: /^[^},]*$/, options: [...c.keys.entries()].map(([k, v]): Completion => ({
        label: k, detail: `${v.author}${v.year ? ' ' + v.year : ''}`, info: v.title || undefined, type: 'text' })) };
    }
    m = /\\begin\{([A-Za-z*]*)$/.exec(before);
    if (m) {
      const typed = m[1] ?? '';
      const envs = [...Object.keys(c.thm), 'proof', 'align', 'align*', 'equation', 'equation*', 'itemize', 'enumerate', 'figure', 'table',
        'tabular', 'center', 'tikzpicture', 'cases', 'pmatrix', 'gather*'];
      return { from: cx.pos - typed.length, options: [...new Set(envs)].map((e): Completion => ({
        label: e, detail: c.thm[e]?.title, type: 'keyword',
        apply: (view, _c, from, to) => {
          const ins = `${e}}\n\n\\end{${e}}`;
          const after = view.state.doc.sliceString(to, to + 1) === '}' ? to + 1 : to;
          view.dispatch({ changes: { from, to: after, insert: ins }, selection: { anchor: from + e.length + 2 } });
        } })) };
    }
    m = /\\([A-Za-z]*)$/.exec(before);
    if (m && (m[1]!.length > 0 || cx.explicit)) {
      const typed = m[1]!;
      const macros = Object.keys(c.macros).map((k) => k.replace(/^\\/, ''));
      const all = [...new Set([...COMMANDS, ...macros])];
      return { from: cx.pos - typed.length, validFor: /^[A-Za-z]*$/, options: all.map((x): Completion => {
        const name = x.replace(/[[{( ].*$/, '');
        return { label: name, detail: x !== name ? x.slice(name.length) : (c.macros[`\\${name}`] ?? undefined), type: 'function',
          apply: (view, _c, from, to) => {
            const brace = x.indexOf('{}');
            view.dispatch({ changes: { from, to, insert: x }, selection: { anchor: from + (brace >= 0 ? brace + 1 : x.length) } });
          } };
      }) };
    }
    return null;
  }

  const lang = () => o.ctx().lang;
  const baseExt = (): Extension[] => [
    history(), drawSelection(), EditorView.lineWrapping, highlightActiveLine(), bracketMatching(), search({ top: true }),
    StreamLanguage.define(texMode), syntaxHighlighting(texHighlight),
    deco, mathTip, sugField, diagField, protect,
    autocompletion({ override: [complete], activateOnTyping: true, icons: false }),
    keymapC.of([]),
    keymap.of([
      { key: 'Mod-s', run: () => { o.onAction?.('save'); return true; }, preventDefault: true },
      { key: 'Mod-Enter', run: () => { o.onAction?.('compile'); return true; } },
      { key: 'Mod-j', run: () => { o.onAction?.('forward'); return true; } },
      { key: 'Mod-m', run: (v) => { wrapSel(v, '$', '$', 'x'); return true; } },
      { key: 'Mod-Shift-m', run: (v) => { wrapSel(v, '\\[\n', '\n\\]', 'x'); return true; } },
      { key: 'Mod-i', run: (v) => { wrapSel(v, '\\emph{', '}', ''); return true; } },
      { key: 'Mod-b', run: (v) => { wrapSel(v, '\\textbf{', '}', ''); return true; } },
      ...searchKeymap, ...historyKeymap, ...defaultKeymap, indentWithTab,
    ]),
    visualC.of(visualExt(visual)),
    gutterC.of(o.lineNumbers && !visual ? lineNumbers() : []),
    spellC.of(EditorView.contentAttributes.of({ spellcheck: visual ? 'true' : 'false', lang: lang() })),
    EditorView.contentAttributes.of({ 'aria-label': o.ariaLabel, 'aria-multiline': 'true', autocapitalize: 'sentences' }),
    o.placeholder ? cmPlaceholder(o.placeholder) : [],
    EditorView.updateListener.of((u) => {
      if (u.docChanged && !u.transactions.every((tr) => tr.annotation(External))) o.onChange(path, u.state.doc.toString());
      if (u.selectionSet || u.docChanged) {
        const s = u.state.selection.main;
        o.onSelection?.(s.empty ? null : { from: s.from, to: s.to, text: u.state.sliceDoc(s.from, s.to) });
      }
    }),
  ];
  function visualExt(v: boolean): Extension {
    return v ? [EditorView.editorAttributes.of({ class: 'cm-visual' })] : [EditorView.editorAttributes.of({ class: 'cm-source' })];
  }
  function makeState(doc: string): EditorState { return EditorState.create({ doc, extensions: baseExt() }); }

  const view = new EditorView({ parent: o.parent, state: makeState(o.doc) });
  // formulas show their source until KaTeX is in, then render (MathWidget.eq compares `ready`)
  if (!katexNow()) void loadKatex().then(() => { if (view.dom.isConnected) view.dispatch({ effects: refresh.of(null) }); }).catch(() => { /* source stays */ });

  function wrapSel(v: EditorView, before: string, after: string, ph: string) {
    const s = v.state.selection.main;
    const inner = v.state.sliceDoc(s.from, s.to) || ph;
    v.dispatch({ changes: { from: s.from, to: s.to, insert: before + inner + after },
      selection: { anchor: s.from + before.length, head: s.from + before.length + inner.length }, userEvent: 'input' });
    v.focus();
  }

  const api: ArticleEditor = {
    view,
    open(p, doc) {
      states.set(path, view.state);
      path = p;
      const st = states.get(p);
      view.setState(st && st.doc.toString() === doc ? st : makeState(doc));
      view.dispatch({ effects: [visualC.reconfigure(visualExt(visual)), gutterC.reconfigure(o.lineNumbers && !visual ? lineNumbers() : []), refresh.of(null)] });
    },
    replaceDoc(p, doc) {
      if (p !== path) { states.delete(p); return; }
      const cur = view.state.doc.toString();
      if (cur === doc) return;
      // minimal change: common prefix/suffix (keeps the cursor and the undo history usable)
      let a = 0; while (a < cur.length && a < doc.length && cur[a] === doc[a]) a++;
      let b = 0; while (b < cur.length - a && b < doc.length - a && cur[cur.length - 1 - b] === doc[doc.length - 1 - b]) b++;
      view.dispatch({ changes: { from: a, to: cur.length - b, insert: doc.slice(a, doc.length - b) }, annotations: External.of(true) });
    },
    setVisual(v) {
      visual = v;
      view.dispatch({ effects: [visualC.reconfigure(visualExt(v)), gutterC.reconfigure(o.lineNumbers && !v ? lineNumbers() : []),
        spellC.reconfigure(EditorView.contentAttributes.of({ spellcheck: v ? 'true' : 'false', lang: lang() })), refresh.of(null)] });
      view.dispatch({ effects: EditorView.scrollIntoView(view.state.selection.main.head, { y: 'center' }) });
    },
    async setKeymap(k) {
      if (k === 'vim') { const { vim } = await import('@replit/codemirror-vim'); view.dispatch({ effects: keymapC.reconfigure(vim()) }); }
      else if (k === 'emacs') { const { emacs } = await import('@replit/codemirror-emacs'); view.dispatch({ effects: keymapC.reconfigure(emacs()) }); }
      else view.dispatch({ effects: keymapC.reconfigure([]) });
    },
    setLineNumbers(v) { o.lineNumbers = v; view.dispatch({ effects: gutterC.reconfigure(v && !visual ? lineNumbers() : []) }); },
    refresh() { view.dispatch({ effects: refresh.of(null) }); },
    setSuggestions(s) { view.dispatch({ effects: setSugs.of(s) }); },
    setDiagnostics(d) { view.dispatch({ effects: setDiags.of(d) }); },
    applySuggestion(s) {
      const doc = view.state.doc;
      if (s.from < 0 || s.to > doc.length) return false;
      const ch = s.at === 'replace' ? { from: s.from, to: s.to, insert: s.replace } : { from: s.at === 'after' ? s.to : s.from, insert: s.replace };
      view.dispatch({ changes: ch, userEvent: 'input.suggestion' });
      return true;
    },
    selection() {
      const s = view.state.selection.main;
      return { from: s.from, to: s.to, text: view.state.sliceDoc(s.from, s.to), line: view.state.doc.lineAt(s.head).number };
    },
    insert(text, cursorOffset) {
      const s = view.state.selection.main;
      const line = view.state.doc.lineAt(s.from);
      const block = text.includes('\n') && line.text.trim() !== '';
      const ins = block ? `\n${text}` : text;
      view.dispatch({ changes: { from: s.from, to: s.to, insert: ins },
        selection: { anchor: s.from + (block ? 1 : 0) + (cursorOffset ?? text.length) }, userEvent: 'input', scrollIntoView: true });
      view.focus();
    },
    wrap(before, after, ph = '') { wrapSel(view, before, after, ph); },
    goto(line) {
      const l = view.state.doc.line(Math.max(1, Math.min(line, view.state.doc.lines)));
      view.dispatch({ selection: { anchor: l.from }, effects: EditorView.scrollIntoView(l.from, { y: 'center' }) });
      view.focus();
    },
    undo() { undo(view); }, redo() { redo(view); },
    focus() { view.focus(); },
    destroy() { view.destroy(); },
  };
  return api;
}

export function markerAt(text: string, pos: number): { id: string; kind: string; dossier: string } | null {
  const sc = scan(text);
  let last = null;
  for (const m of sc.markers) { if (m.from > pos) break; last = parseMarker(m.text); }
  return last;
}
