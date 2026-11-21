// CodeMirror 6 setup for Lean and for natural language/LaTeX. Loaded lazily (own chunk).
import { EditorState, StateEffect, StateField, type Extension, Compartment, RangeSetBuilder } from '@codemirror/state';
import {
  EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, hoverTooltip,
  Decoration, type DecorationSet, placeholder as cmPlaceholder,
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { StreamLanguage, HighlightStyle, syntaxHighlighting, bracketMatching, type StringStream } from '@codemirror/language';
import { tags } from '@lezer/highlight';
import { abbreviationAt, insideDollarMath } from './abbrev';
import { lookupGloss, tokenAt, type GlossEntry } from './glossary';

const KEYWORDS = new Set('theorem lemma example def by have show from fun let in with match at calc import open namespace end section variable set_option noncomputable instance structure class where if then else do return universe abbrev'.split(' '));
const TACTICS = new Set('intro intros exact apply rw rwa simp simp_all norm_num linarith nlinarith ring ring_nf field_simp omega decide constructor cases rcases obtain induction use refine positivity gcongr aesop tauto exfalso contradiction unfold specialize push_cast norm_cast exact_mod_cast trivial rfl left right by_contra by_cases interval_cases nth_rewrite conv congr ext funext split_ifs subst symm trans exists existsi assumption clear rename_i next all_goals any_goals first try repeat'.split(' '));

interface LeanState { comment: number }
const leanMode = {
  name: 'lean',
  startState: (): LeanState => ({ comment: 0 }),
  token(stream: StringStream, st: LeanState): string | null {
    if (st.comment > 0) {
      while (!stream.eol()) {
        if (stream.match('/-')) st.comment++;
        else if (stream.match('-/')) { st.comment--; if (st.comment === 0) break; }
        else stream.next();
      }
      return 'comment';
    }
    if (stream.eatSpace()) return null;
    if (stream.match('--')) { stream.skipToEnd(); return 'comment'; }
    if (stream.match('/-')) { st.comment = 1; return 'comment'; }
    if (stream.match(/^"(?:[^"\\]|\\.)*"?/)) return 'string';
    if (stream.match(/^\d+(\.\d+)?/)) return 'number';
    if (stream.match('sorry')) return 'invalid';
    const id = stream.match(/^[\p{L}_][\p{L}\p{N}_.'!?₀-₉ᵢₙ]*/u) as RegExpMatchArray | null;
    if (id) {
      const w = id[0];
      if (KEYWORDS.has(w)) return 'keyword';
      if (TACTICS.has(w)) return 'tactic';
      if (/^[A-Z]/.test(w) || /^[ℕℤℚℝℂ]$/.test(w)) return 'typeName';
      return 'variableName';
    }
    if (stream.match(/^(:=|→|↔|←|∀|∃|λ|∧|∨|¬|≤|≥|≠|∣|∈|∉|⊆|⊂|∩|∪|∑|∏|⟨|⟩|×|·|∘|⁻¹|=|<|>|\+|-|\*|\/|\^|%|\|)/)) return 'operator';
    stream.next();
    return null;
  },
  languageData: { commentTokens: { line: '--', block: { open: '/-', close: '-/' } } },
  tokenTable: { tactic: tags.controlKeyword, typeName: tags.typeName, invalid: tags.invalid },
};

const leanHighlight = HighlightStyle.define([
  { tag: tags.keyword, class: 'tk-kw' },
  { tag: tags.controlKeyword, class: 'tk-tac' },
  { tag: tags.typeName, class: 'tk-type' },
  { tag: tags.comment, class: 'tk-com' },
  { tag: tags.string, class: 'tk-str' },
  { tag: tags.number, class: 'tk-num' },
  { tag: tags.operator, class: 'tk-op' },
  { tag: tags.invalid, class: 'tk-sorry' },
]);

/** Space/Tab after `\le` → ≤. In natural-language mode, not inside $…$ (keep LaTeX). */
function abbreviations(natural: boolean): Extension {
  const expand = (view: EditorView): boolean => {
    const sel = view.state.selection.main;
    if (!sel.empty) return false;
    const line = view.state.doc.lineAt(sel.head);
    const before = line.text.slice(0, sel.head - line.from);
    if (natural && insideDollarMath(before)) return false;
    const hit = abbreviationAt(before);
    if (!hit) return false;
    const [len, sym] = hit;
    view.dispatch({ changes: { from: sel.head - len, to: sel.head, insert: sym }, selection: { anchor: sel.head - len + sym.length }, userEvent: 'input.abbrev' });
    return true;
  };
  return [
    keymap.of([{ key: 'Tab', run: (v) => expand(v) }]),
    EditorView.inputHandler.of((view, _from, _to, text) => {
      if (text !== ' ') return false;
      if (!expand(view)) return false;
      const head = view.state.selection.main.head;
      view.dispatch({ changes: { from: head, insert: ' ' }, selection: { anchor: head + 1 } });
      return true;
    }),
  ];
}

// Error lines (from Lean messages)
const setErrors = StateEffect.define<{ line: number; text: string; severity: string }[]>();
const errorField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(deco, tr) {
    deco = deco.map(tr.changes);
    for (const e of tr.effects) {
      if (!e.is(setErrors)) continue;
      const b = new RangeSetBuilder<Decoration>();
      const lines = [...new Set(e.value.filter((x) => x.line >= 1 && x.line <= tr.state.doc.lines).map((x) => x.line))].sort((a, c) => a - c);
      for (const ln of lines) {
        const sev = e.value.find((x) => x.line === ln)?.severity ?? 'error';
        const l = tr.state.doc.line(ln);
        b.add(l.from, l.from, Decoration.line({ class: sev === 'error' ? 'cm-errline' : 'cm-warnline' }));
      }
      deco = b.finish();
    }
    return deco;
  },
  provide: (f) => EditorView.decorations.from(f),
});

export interface GlossLookup {
  (token: string): Promise<{ title: string; body: string } | null>;
}

export interface EditorOptions {
  parent: HTMLElement;
  doc: string;
  language: 'lean' | 'natural';
  readOnly?: boolean;
  ariaLabel: string;
  placeholder?: string;
  lineNumbers?: boolean;
  lang: () => 'fr' | 'en';
  onChange?: (doc: string) => void;
  /** Hover / tap explanations of Lean tokens (Learn mode). */
  gloss?: boolean;
  declLookup?: GlossLookup;
  onTokenTap?: (token: string, entry: GlossEntry | null) => void;
  onSubmit?: () => void;
}

export interface EditorHandle {
  view: EditorView;
  set(doc: string): void;
  get(): string;
  setErrors(errs: { line: number; text: string; severity: string }[]): void;
  setReadOnly(ro: boolean): void;
  focus(): void;
  destroy(): void;
}

export function createEditor(o: EditorOptions): EditorHandle {
  const ro = new Compartment();
  const ext: Extension[] = [
    history(),
    drawSelection(),
    EditorView.lineWrapping,
    keymap.of([
      ...(o.onSubmit ? [{ key: 'Mod-Enter', run: () => { o.onSubmit!(); return true; } }] : []),
      ...historyKeymap, ...defaultKeymap, indentWithTab,
    ]),
    abbreviations(o.language === 'natural'),
    ro.of([EditorState.readOnly.of(Boolean(o.readOnly)), EditorView.editable.of(!o.readOnly)]),
    EditorView.contentAttributes.of({ 'aria-label': o.ariaLabel, 'aria-multiline': 'true', spellcheck: o.language === 'natural' ? 'true' : 'false', autocapitalize: 'off', autocorrect: 'off' }),
    EditorView.updateListener.of((u) => { if (u.docChanged) o.onChange?.(u.state.doc.toString()); }),
  ];
  if (o.placeholder) ext.push(cmPlaceholder(o.placeholder));
  if (o.language === 'lean') {
    ext.push(StreamLanguage.define(leanMode), syntaxHighlighting(leanHighlight), bracketMatching(), errorField);
    if (o.lineNumbers !== false) ext.push(lineNumbers(), highlightActiveLineGutter());
    if (!o.readOnly) ext.push(highlightActiveLine());
  }
  if (o.gloss && o.language === 'lean') {
    ext.push(hoverTooltip(async (view, pos) => {
      const line = view.state.doc.lineAt(pos);
      const tok = tokenAt(line.text, pos - line.from);
      if (!tok) return null;
      const g = lookupGloss(tok.text);
      let title = tok.text;
      let body = g ? g.entry[o.lang()] : '';
      if (!g && o.declLookup && /[\p{L}]/u.test(tok.text)) {
        const r = await o.declLookup(tok.text).catch(() => null);
        if (r) { title = r.title; body = r.body; }
      }
      if (!body) return null;
      return {
        pos: line.from + tok.from, end: line.from + tok.to, above: true,
        create: () => {
          const dom = document.createElement('div');
          dom.className = 'cm-gloss';
          const h = document.createElement('strong');
          h.textContent = title;
          const p = document.createElement('p');
          p.textContent = body;
          dom.append(h, p);
          return { dom };
        },
      };
    }, { hoverTime: 350 }));
    if (o.onTokenTap) {
      ext.push(EditorView.domEventHandlers({
        click: (_e, view) => {
          const pos = view.state.selection.main.head;
          const line = view.state.doc.lineAt(pos);
          const tok = tokenAt(line.text, pos - line.from);
          if (tok) o.onTokenTap!(tok.text, lookupGloss(tok.text)?.entry ?? null);
          return false;
        },
      }));
    }
  }
  const view = new EditorView({ parent: o.parent, state: EditorState.create({ doc: o.doc, extensions: ext }) });
  return {
    view,
    set(doc: string) {
      if (doc === view.state.doc.toString()) return;
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: doc } });
    },
    get: () => view.state.doc.toString(),
    setErrors(errs) { view.dispatch({ effects: setErrors.of(errs) }); },
    setReadOnly(r) { view.dispatch({ effects: ro.reconfigure([EditorState.readOnly.of(r), EditorView.editable.of(!r)]) }); },
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
