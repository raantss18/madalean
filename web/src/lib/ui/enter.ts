// Enter / Shift+Enter in fields that send, launch or run something (session S-AK, docs/UI.md §14.3):
// Enter (or Ctrl/Cmd+Enter) sends, Shift+Enter inserts a new line, nothing happens while an IME is composing.
// Long-form editors (article, notes body, text cells…) do not use this: there Enter is a new line.

export type EnterIntent = 'submit' | 'newline' | 'none';

type KeyLike = Pick<KeyboardEvent, 'key' | 'shiftKey' | 'ctrlKey' | 'metaKey' | 'altKey' | 'isComposing'> & { keyCode?: number };

export function enterIntent(e: KeyLike): EnterIntent {
  if (e.key !== 'Enter') return 'none';
  // 229: the key event of an IME composition in browsers that do not set isComposing on it (Safari)
  if (e.isComposing || e.keyCode === 229) return 'none';
  if (e.altKey) return 'none';
  if (e.shiftKey) return 'newline';
  return 'submit';
}

/** A touch screen with no mouse or trackpad. Its on-screen keyboard has no Shift+Enter, so there Enter stays a new
 *  line and the field's button sends (the messaging-app convention); the hint is hidden there. */
export function touchOnly(): boolean {
  if (typeof matchMedia === 'undefined') return false;
  return matchMedia('(pointer: coarse)').matches && !matchMedia('(any-pointer: fine)').matches;
}

/** Svelte action for a <textarea> / <input> that sends: `use:enterSubmit={send}`. */
export function enterSubmit(node: HTMLElement, onsubmit: () => void) {
  let fn = onsubmit;
  const h = (e: KeyboardEvent) => {
    if (enterIntent(e) !== 'submit') return;
    if (touchOnly() && !e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    e.stopPropagation();
    fn();
  };
  node.addEventListener('keydown', h);
  return {
    update(f: () => void) { fn = f; },
    destroy() { node.removeEventListener('keydown', h); },
  };
}

export interface Edit { text: string; start: number; end: number }

const INDENT = '    ';

/** Shift+Enter in a code cell: a new line that keeps the current line's indentation (+1 level after « : »). */
export function newlineIndent(text: string, start: number, end: number): Edit {
  const lineStart = text.lastIndexOf('\n', start - 1) + 1;
  const line = text.slice(lineStart, start);
  let ind = /^[ \t]*/.exec(line)![0];
  if (/:\s*$/.test(line)) ind += INDENT;
  const ins = '\n' + ind;
  return { text: text.slice(0, start) + ins + text.slice(end), start: start + ins.length, end: start + ins.length };
}

/** Tab / Shift+Tab in a code cell: indent or dedent the selected lines (or insert 4 spaces at the caret). */
export function tabIndent(text: string, start: number, end: number, dedent: boolean): Edit {
  const ls = text.lastIndexOf('\n', start - 1) + 1;
  if (!dedent && start === end) {
    return { text: text.slice(0, start) + INDENT + text.slice(end), start: start + INDENT.length, end: start + INDENT.length };
  }
  const le = text.indexOf('\n', end - (end > start && text[end - 1] === '\n' ? 1 : 0));
  const stop = le === -1 ? text.length : le;
  const lines = text.slice(ls, stop).split('\n');
  let first = 0;
  let total = 0;
  const out = lines.map((l, i) => {
    if (dedent) {
      const n = /^ {0,4}/.exec(l)![0].length || (l.startsWith('\t') ? 1 : 0);
      if (i === 0) first = -n;
      total -= n;
      return l.slice(n);
    }
    if (i === 0) first = INDENT.length;
    total += INDENT.length;
    return INDENT + l;
  });
  const next = text.slice(0, ls) + out.join('\n') + text.slice(stop);
  return { text: next, start: Math.max(ls, start + first), end: Math.max(ls, end + total) };
}

/** Apply an Edit to a textarea and tell Svelte's bindings (input event). */
export function applyEdit(ta: HTMLTextAreaElement, ed: Edit): void {
  ta.value = ed.text;
  ta.setSelectionRange(ed.start, ed.end);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
}
