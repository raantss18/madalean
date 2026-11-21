import { describe, it, expect } from 'vitest';
import { scan, matchBrace, managedRegions, parseMarker, linkedDossier, numberDocument, katexMacros, headings } from '../../src/lib/article/latex';

const DOC = String.raw`%% mdl:block b-12345678 section
\section{Introduction}\label{sec:intro}
Soit $f(x)=\frac{1}{x}$ et % commentaire $ {
\[ \int_0^1 x\,dx \]
\begin{theorem}[Cauchy]\label{thm:c}
Énoncé \emph{important} \cite[Thm.~1]{knuth}.
\end{theorem}
\begin{proof}Voir \cref{thm:c}.\end{proof}
\begin{align}
a &= b \label{eq:a}\\
\end{align}
\begin{tikzpicture}\draw (0,0) -- (1,1);\end{tikzpicture}
\verb|$not math$|`;

describe('LaTeX scanner of the article editor', () => {
  const s = scan(DOC);
  it('finds maths (inline, display, environments) and ignores comments and \\verb', () => {
    expect(s.math.map((m) => m.env)).toEqual(['$', '\\[', 'align']);
    expect(DOC.slice(s.math[0]!.inner.from, s.math[0]!.inner.to)).toBe('f(x)=\\frac{1}{x}');
    expect(s.comments.length).toBe(1);
    expect(s.markers[0]!.text).toBe('%% mdl:block b-12345678 section');
  });
  it('finds environments with optional argument and their end', () => {
    const th = s.envs.find((e) => e.name === 'theorem')!;
    expect(th.opt).toBe('Cauchy');
    expect(DOC.slice(th.endFrom, th.to)).toBe('\\end{theorem}');
    expect(s.envs.map((e) => e.name)).toEqual(['theorem', 'proof', 'tikzpicture']);
  });
  it('finds commands with their arguments, nested inside other arguments', () => {
    const names = s.cmds.map((c) => c.name);
    expect(names).toEqual(expect.arrayContaining(['section', 'label', 'emph', 'cite', 'cref']));
    const cite = s.cmds.find((c) => c.name === 'cite')!;
    expect(cite.opt).toBe('Thm.~1');
    expect(cite.arg).toBe('knuth');
  });
  it('matches braces with escapes', () => {
    expect(matchBrace('{a\\}b{c}}x', 0)).toBe(8);
    expect(matchBrace('{a', 0)).toBe(-1);
  });
  it('never throws on broken input', () => {
    expect(() => scan('\\begin{theorem} $x \\section{')).not.toThrow();
    expect(scan('$ unclosed\n\nnext $x$').math.length).toBe(1);
  });
  it('managed regions, markers and the dossier link', () => {
    const main = '%% mdl:preamble begin\n\\documentclass{amsart}\n%% mdl:preamble end\n\\begin{document}\n%% mdl:front begin\n\\title{x}\n%% mdl:front end\n';
    expect(managedRegions(main).map((r) => r.name)).toEqual(['preamble', 'front']);
    expect(parseMarker('%% mdl:block b-0000abcd dossier dossier=d-1')).toEqual({ id: 'b-0000abcd', kind: 'dossier', dossier: 'd-1' });
    const t = '%% mdl:block b-0000abcd dossier dossier=d-1\n\\begin{theorem}\nx\n\\end{theorem}\n\\begin{lemma}\n% mdl:lean d-2\ny\\end{lemma}';
    const sc = scan(t);
    expect(linkedDossier(t, sc.envs[0]!.from, sc.envs[0]!.beginTo, sc.markers)).toBe('d-1');
    expect(linkedDossier(t, sc.envs[1]!.from, sc.envs[1]!.beginTo, sc.markers)).toBe('d-2');
  });
  it('numbers sections and theorems like amsthm (shared counter within section)', () => {
    const n = numberDocument([{ path: 'a.tex', text: '\\section{A}\n\\begin{theorem}x\\end{theorem}\n\\begin{lemma}y\\end{lemma}\n\\section{B}\n\\begin{lemma}z\\end{lemma}' }],
      { section: 'section', envs: { theorem: '', lemma: 'theorem' }, within: 'section' });
    expect([...n.values()].map((v) => v.num)).toEqual(['1', '1.1', '1.2', '2', '2.1']);
  });
  it('KaTeX macros from settings and \\newcommand, headings', () => {
    expect(katexMacros({ R: '\\mathbb{R}' }, '\\newcommand{\\abs}[1]{\\left|#1\\right|}')).toEqual({ '\\R': '\\mathbb{R}', '\\abs': '\\left|#1\\right|' });
    expect(headings(DOC)[0]).toMatchObject({ level: 1, title: 'Introduction', line: 2 });
  });
});
