// S-H review: Markdown / KaTeX rendering of untrusted text (model output, notes, sources, titles).
import { beforeAll, describe, expect, it } from 'vitest';
import { renderMarkdown, renderInline } from '../../src/lib/md';
import { loadKatex } from '../../src/lib/katex.svelte';

beforeAll(async () => { await loadKatex(); });          // KaTeX is lazy (S-AP): load it as a formula on screen would

describe('untrusted Markdown', () => {
  it('neutralises script URLs and off-site protocol-relative links', () => {
    for (const href of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,x', 'vbscript:x', '//evil.example/x',
      '/\\evil.example/x', ' javascript:alert(1)']) {
      const html = renderMarkdown(`[x](${href})`);
      expect(html).not.toMatch(/href="(?:javascript|data|vbscript|\/\/|\/\\)/i);
    }
    expect(renderMarkdown('[ok](/d/abc)')).toContain('href="/d/abc"');
    expect(renderMarkdown('[ok](https://arxiv.org/abs/1)')).toContain('rel="noopener noreferrer"');
  });
  it('never emits raw HTML, images or KaTeX links/classes', () => {
    const html = renderMarkdown('<img src=x onerror=alert(1)> <script>alert(1)</script> ![a](http://x/y.png) ' +
      '$\\href{javascript:alert(1)}{x}$ $\\htmlClass{x}{y}$ $\\url{javascript:alert(1)}$');
    expect(html).not.toMatch(/<img|<script|<[^>]+\son\w+=|href="javascript/i);
    expect(html).not.toContain('class="x"');
    expect(renderInline('<svg onload=alert(1)>')).not.toContain('<svg');
  });
  it('a formula may start with a digit; prices stay text (S-BH)', () => {
    expect(renderMarkdown('vaut $6$ et $5 \\le x$')).not.toContain('$');
    expect(renderMarkdown('from $5 to $10')).toContain('$5 to $10');
    expect(renderMarkdown('$5 and $6')).toContain('$5 and $6');
  });
});
