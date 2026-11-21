// Safe Markdown + maths renderer for UNTRUSTED model output.
// - markdown-it with html:false (raw HTML is shown as text), no images (alt text only), links open outside
//   with rel=noopener noreferrer; javascript:/data: links are refused by markdown-it's validateLink;
// - maths: $…$, $$…$$, \(…\), \[…\] through KaTeX (trust:false, errors rendered as text);
// - the final HTML goes through DOMPurify (defence in depth).
import MarkdownIt, { type StateInline, type StateBlock } from 'markdown-it';
import katex from 'katex';
import DOMPurify from 'dompurify';
import 'katex/dist/katex.min.css';

export function renderMath(src: string, display: boolean): string {
  return katex.renderToString(src, { displayMode: display, throwOnError: false, trust: false, strict: 'ignore', output: 'htmlAndMathml', maxExpand: 500, maxSize: 20 });
}

function mathInline(state: StateInline, silent: boolean): boolean {
  const src = state.src;
  const start = state.pos;
  let open = '';
  let close = '';
  if (src.startsWith('$$', start)) { open = '$$'; close = '$$'; }
  else if (src[start] === '$') { open = '$'; close = '$'; }
  else if (src.startsWith('\\(', start)) { open = '\\('; close = '\\)'; }
  else if (src.startsWith('\\[', start)) { open = '\\['; close = '\\]'; }
  else return false;
  if (open === '$' && /[\s\d]/.test(src[start + 1] ?? ' ')) return false;   // "$ 5" / "$5" are not maths
  let pos = start + open.length;
  let end = -1;
  while (pos < state.posMax) {
    const i = src.indexOf(close, pos);
    if (i < 0) break;
    if (src[i - 1] !== '\\') { end = i; break; }
    pos = i + 1;
  }
  if (end < 0 || end === start + open.length) return false;
  if (open === '$' && /\s/.test(src[end - 1] ?? '')) return false;
  if (!silent) {
    const tok = state.push('math', 'math', 0);
    tok.content = src.slice(start + open.length, end);
    tok.markup = open;
    tok.meta = { display: open === '$$' || open === '\\[' };
  }
  state.pos = end + close.length;
  return true;
}

function mathBlock(state: StateBlock, startLine: number, endLine: number, silent: boolean): boolean {
  let pos = state.bMarks[startLine]! + state.tShift[startLine]!;
  let max = state.eMarks[startLine]!;
  const line = state.src.slice(pos, max);
  const open = line.startsWith('$$') ? '$$' : line.startsWith('\\[') ? '\\[' : '';
  if (!open) return false;
  const close = open === '$$' ? '$$' : '\\]';
  let content = line.slice(open.length);
  let next = startLine;
  let found = false;
  if (content.trimEnd().endsWith(close) && content.trim().length >= close.length) {
    content = content.trimEnd().slice(0, -close.length);
    found = true;
  }
  while (!found) {
    next++;
    if (next >= endLine) return false;
    pos = state.bMarks[next]! + state.tShift[next]!;
    max = state.eMarks[next]!;
    const l = state.src.slice(pos, max);
    if (l.trimEnd().endsWith(close)) {
      content += '\n' + l.trimEnd().slice(0, -close.length);
      found = true;
    } else content += '\n' + l;
  }
  if (silent) return true;
  state.line = next + 1;
  const tok = state.push('math_block', 'math', 0);
  tok.block = true;
  tok.content = content;
  tok.map = [startLine, state.line];
  return true;
}

const md = MarkdownIt({ html: false, linkify: false, typographer: false, breaks: false });
md.inline.ruler.after('escape', 'math', mathInline);
md.block.ruler.after('blockquote', 'math_block', mathBlock, { alt: ['paragraph', 'reference', 'blockquote', 'list'] });
md.renderer.rules['math'] = (tokens, idx) => renderMath(tokens[idx]!.content, Boolean((tokens[idx]!.meta as { display?: boolean })?.display));
md.renderer.rules['math_block'] = (tokens, idx) => `<div class="math-block">${renderMath(tokens[idx]!.content, true)}</div>`;
md.renderer.rules.image = (tokens, idx) => {
  const alt = tokens[idx]!.content;
  return alt ? `<span class="img-alt">[${md.utils.escapeHtml(alt)}]</span>` : '';
};
const defaultLinkOpen = md.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const tok = tokens[idx]!;
  const href = String(tok.attrGet('href') ?? '');
  if (!/^(https?:|mailto:|\/(?!\/)|#)/i.test(href)) tok.attrSet('href', '#');
  if (/^https?:/i.test(href)) {
    tok.attrSet('target', '_blank');
    tok.attrSet('rel', 'noopener noreferrer');
  }
  return defaultLinkOpen(tokens, idx, options, env, self);
};

let hooked = false;
function purify(html: string): string {
  if (typeof window === 'undefined') return html;
  if (!hooked) {
    hooked = true;
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
      if (node.tagName === 'A' && node.getAttribute('target') === '_blank') node.setAttribute('rel', 'noopener noreferrer');
    });
  }
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ['target'],
    FORBID_TAGS: ['img', 'style', 'iframe', 'form', 'input', 'video', 'audio', 'object', 'embed'],
    USE_PROFILES: { html: true, mathMl: true },
  });
}

export function renderMarkdown(src: string): string {
  return purify(md.render(src ?? ''));
}

export function renderInline(src: string): string {
  return purify(md.renderInline(src ?? ''));
}
