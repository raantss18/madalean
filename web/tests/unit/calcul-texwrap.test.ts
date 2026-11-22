import { beforeAll, describe, expect, it } from 'vitest';
import { breakable } from '../../src/lib/calcul/texwrap';
import { renderMath } from '../../src/lib/md';
import { loadKatex } from '../../src/lib/katex.svelte';

beforeAll(async () => { await loadKatex(); });          // KaTeX is lazy (S-AP): load it as a formula on screen would

const ROOTS = '\\left[\\left(1, 1\\right), \\left(a^{3} + 1, 1\\right), \\left(a^{3} + a + 1, 1\\right), \\left(a^{3} + a^{2} + 1, 1\\right), \\left(a^{2} + a + 1, 1\\right)\\right]';

describe('calcul: long formulas wrap (S-AB)', () => {
  it('keeps short formulas and matrices as they are', () => {
    expect(breakable('\\sqrt{2} \\pi')).toBeNull();
    expect(breakable('\\left(\\begin{array}{rr}1 & 2\\end{array}\\right)' + ' '.repeat(80))).toBeNull();
  });
  it('allows a break after each outer comma, never inside a pair', () => {
    const b = breakable(ROOTS)!;
    expect(b).not.toContain('\\left');
    expect(b.replace(/\s+/g, '').startsWith('[(1,1),\\allowbreak(a^{3}+1,1),\\allowbreak')).toBe(true);
    expect(b).not.toContain('1,\\allowbreak 1');
    expect(renderMath(b, false)).not.toContain('katex-error');
  });
});
