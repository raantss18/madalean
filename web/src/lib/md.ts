// Safe Markdown + maths renderer for UNTRUSTED model output.
// - markdown-it with html:false (raw HTML is shown as text), no images (alt text only), links open outside
//   with rel=noopener noreferrer; javascript:/data: links are refused by markdown-it's validateLink;
// - maths: $…$, $$…$$, \(…\), \[…\] through KaTeX (trust:false, errors rendered as text). KaTeX is loaded on the
//   first formula (lib/katex.svelte.ts, S-AP): until then the TeX source is shown in a `.math-pending` span, and
//   reactive callers (Md.svelte's $derived, templates) render again when it arrives;
// - the final HTML goes through DOMPurify (defence in depth).
import MarkdownIt, { type StateInline, type StateBlock } from 'markdown-it';
import DOMPurify from 'dompurify';
import { katexNow, preloadKatex } from './katex.svelte';

const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function renderMath(src: string, display: boolean): string {
  const katex = katexNow();
  if (!katex) {
    preloadKatex();
    return `<span class="math-pending${display ? ' display' : ''}">${src.replace(/[&<>"']/g, (c) => ESC[c]!)}</span>`;
  }
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
  if (open === '$' && /\s/.test(src[start + 1] ?? ' ')) return false;   // "$ 5" is not maths
  let pos = start + open.length;
  let end = -1;
  while (pos < state.posMax) {
    const i = src.indexOf(close, pos);
    if (i < 0) break;
    if (src[i - 1] !== '\\') { end = i; break; }
    pos = i + 1;
  }
  if (end < 0 || end === start + open.length) return false;
  // prices (« $5 and $6 »): the closing $ follows a space or precedes a digit; « $6$ » and « $5 \le x$ » are maths
  if (open === '$' && (/\s/.test(src[end - 1] ?? '') || /\d/.test(src[end + 1] ?? ''))) return false;
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
  if (!/^(https?:|mailto:|\/(?![\/\\])|#)/i.test(href)) tok.attrSet('href', '#');
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

// ---------------------------------------------------------------- trusted content (the manual, docs/SITE.md §2)
const KW = /\b(theorem|lemma|example|def|by|have|show|from|fun|let|in|with|match|at|calc|import|open|namespace|end|section|variable|where|if|then|else)\b/g;
const TAC = /\b(intro|intros|exact|apply|rw|simp|norm_num|linarith|nlinarith|ring|ring_nf|field_simp|omega|decide|constructor|cases|rcases|obtain|induction|use|refine|positivity|gcongr|aesop|tauto|exfalso|contradiction|unfold|specialize|push_cast|norm_cast|trivial|rfl|left|right|by_contra|sorry)\b/g;
function leanHighlight(code: string): string {
  const esc = md.utils.escapeHtml(code);
  return esc.split('\n').map((line) => {
    const c = line.indexOf('--');
    const head = c >= 0 ? line.slice(0, c) : line;
    const tail = c >= 0 ? `<span class="tk-com">${line.slice(c)}</span>` : '';
    return head.replace(KW, '<span class="tk-kw">$1</span>').replace(TAC, '<span class="tk-tac">$1</span>') + tail;
  }).join('\n');
}

export interface TrustedOpts {
  headingIds: string[];                        // ids in document order (from index.json headings[])
  link: (href: string) => { href: string; external: boolean };
  image: (src: string) => string;
}

const trusted = new MarkdownIt({ html: false, linkify: false, typographer: false });
trusted.inline.ruler.after('escape', 'math', mathInline);
trusted.block.ruler.after('blockquote', 'math_block', mathBlock, { alt: ['paragraph', 'reference', 'blockquote', 'list'] });
trusted.renderer.rules['math'] = md.renderer.rules['math']!;
trusted.renderer.rules['math_block'] = md.renderer.rules['math_block']!;
trusted.renderer.rules.fence = (tokens, idx) => {
  const tok = tokens[idx]!;
  const lang = tok.info.trim().split(/\s+/)[0] ?? '';
  const body = /^lean4?$/.test(lang) ? leanHighlight(tok.content) : md.utils.escapeHtml(tok.content);
  return `<pre class="code lang-${md.utils.escapeHtml(lang)}"><code>${body}</code></pre>`;
};

export function renderTrusted(src: string, o: TrustedOpts): string {
  const env = { h: 0 };
  const tokens = trusted.parse(src, env);
  for (const tok of tokens) {
    if (tok.type === 'heading_open') { const id = o.headingIds[env.h++]; if (id) tok.attrSet('id', id); }
    if (tok.type === 'inline') for (const ch of tok.children ?? []) {
      if (ch.type === 'link_open') {
        const r = o.link(String(ch.attrGet('href') ?? ''));
        ch.attrSet('href', r.href);
        if (r.external) { ch.attrSet('target', '_blank'); ch.attrSet('rel', 'noopener noreferrer'); }
      } else if (ch.type === 'image') ch.attrSet('src', o.image(String(ch.attrGet('src') ?? '')));
    }
  }
  const html = trusted.renderer.render(tokens, trusted.options, env);
  if (typeof window === 'undefined') return html;
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'], USE_PROFILES: { html: true, mathMl: true }, FORBID_TAGS: ['style', 'iframe', 'form', 'input'] });
}
