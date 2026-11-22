// S-AD: project items beside the article (kinds, inserted LaTeX) and the file tree of the LaTeX project.
import { describe, it, expect } from 'vitest';
import fr from '../../src/lib/i18n/fr';
import { ICONS } from '../../src/components/Icon.svelte';
import { KINDS, GROUPS, dossierSnippet, dossierLabel, conjectureSnippet, citeSnippet, figureSnippet, cellTitle, cellAssets, cellLatex, matches, texSafe, fileTree } from '../../src/lib/article/items';

describe('item kinds', () => {
  it('each kind has its own icon, a label, a group and a colour token', () => {
    const icons = new Set<string>();
    for (const [k, v] of Object.entries(KINDS)) {
      expect(ICONS[v.icon], k).toBeTruthy();
      expect(v.label in fr, v.label).toBe(true);
      expect(v.group in fr, v.group).toBe(true);
      expect(v.color).toMatch(/^var\(--k-/);
      icons.add(v.icon);
    }
    expect(icons.size).toBe(Object.keys(KINDS).length);       // never two kinds with the same picture
    for (const g of GROUPS) expect(`ae.items.empty.${g}` in fr, g).toBe(true);
  });
});

describe('inserted LaTeX', () => {
  it('a dossier becomes a theorem linked to Lean, or a reference when the article already states it', () => {
    const d = { id: 'd-20261121-ab12cd', title: 'Somme {paire}', theorem: 'La somme de deux pairs est paire.', lemma: false };
    expect(dossierLabel(d.id)).toBe('ml:d20261121ab12cd');
    const s = dossierSnippet(d, new Set());
    expect(s.text).toBe('\\begin{theorem}[Somme paire]\\label{ml:d20261121ab12cd}\n% mdl:lean d-20261121-ab12cd\nLa somme de deux pairs est paire.\n\\end{theorem}\n');
    expect(s.text.slice(0, s.cursor)).toMatch(/est paire\.$/);
    expect(dossierSnippet({ ...d, lemma: true }, new Set()).text).toMatch(/^\\begin\{lemma\}/);
    expect(dossierSnippet(d, new Set(['ml:d20261121ab12cd'])).text).toBe('\\cref{ml:d20261121ab12cd}');
  });
  it('conjecture, citation, figure', () => {
    expect(conjectureSnippet({ title: 'Goldbach', statement_nl: 'Tout pair > 2 est somme de deux premiers.' }).text)
      .toBe('\\begin{conjecture}[Goldbach]\nTout pair > 2 est somme de deux premiers.\n\\end{conjecture}\n');
    expect(citeSnippet('knuth1984').text).toBe('\\cite{knuth1984}');
    expect(citeSnippet('a}b\\c').text).toBe('\\cite{abc}');
    expect(figureSnippet('figures/0123456789abcdef.png', 'Graphe de $f$').text)
      .toContain('\\includegraphics[width=0.7\\linewidth]{figures/0123456789abcdef.png}\n\\caption{Graphe de f}\\label{fig:012345}');
    expect(texSafe('a\\b{c}%d')).toBe('a b c d');
  });
  it('Calcul cells: title, PNG assets, LaTeX result', () => {
    expect(cellTitle('\n# Courbe de f\nplot(sin)')).toBe('Courbe de f');
    expect(cellTitle('')).toBe('');
    const a = 'a'.repeat(32), b = 'b'.repeat(32);
    expect(cellAssets([{ data: { 'image/png': { asset: a, mime: 'image/png' } } }, { asset: b, mime: 'image/svg+xml' }, { x: { asset: a } }])).toEqual([a]);
    expect(cellLatex([{ data: { 'text/plain': '2' } }, { data: { 'text/latex': '$$\\frac{1}{2}$$' } }])).toBe('\\frac{1}{2}');
    expect(cellLatex(undefined)).toBe('');
  });
  it('search ignores accents and case', () => {
    expect(matches('ETE', 'Été indien')).toBe(true);
    expect(matches('', 'x')).toBe(true);
    expect(matches('zzz', 'abc', undefined)).toBe(false);
  });
});

describe('file tree', () => {
  it('main.tex, sections in document order then not-included ones, figures, generated files', () => {
    const t = fileTree(['main.tex', 'sections/02-b.tex', 'sections/01-a.tex', 'sections/09-old.tex'], ['sections/01-a.tex', 'sections/02-b.tex'], ['figures/x.png']);
    expect(t.map((n) => n.name)).toEqual(['main.tex', 'sections', 'figures', 'refs.bib', 'madalean.toml', 'madalean.lock']);
    expect(t[1]!.children!.map((n) => [n.name, Boolean(n.orphan)])).toEqual([['01-a.tex', false], ['02-b.tex', false], ['09-old.tex', true]]);
    expect(t[2]!.children!.map((n) => n.kind)).toEqual(['image']);
    for (const n of t) if (n.note) expect(n.note in fr, n.note).toBe(true);
  });
});
