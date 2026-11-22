// Project items shown beside the article (session S-AD, docs/ARTICLE.md §9): one description per kind (icon of its
// own shape + text label + colour token, so colour is never the only cue) and the LaTeX each kind inserts. Pure: unit
// tested in tests/unit/article-items.test.ts.

export type ItemKind = 'proof' | 'calc' | 'cell' | 'note' | 'conj' | 'source' | 'figure' | 'version';

export interface KindInfo { icon: string; color: string; label: string /* i18n key */; group: string /* i18n key */ }

export const KINDS: Record<ItemKind, KindInfo> = {
  proof: { icon: 'proof', color: 'var(--k-proof)', label: 'ae.items.kind.proof', group: 'ae.items.group.proof' },
  calc: { icon: 'plot', color: 'var(--k-calc)', label: 'ae.items.kind.calc', group: 'ae.items.group.calc' },
  cell: { icon: 'cell', color: 'var(--k-cell)', label: 'ae.items.kind.cell', group: 'ae.items.group.calc' },
  note: { icon: 'note', color: 'var(--k-note)', label: 'ae.items.kind.note', group: 'ae.items.group.note' },
  conj: { icon: 'conjecture', color: 'var(--k-conj)', label: 'ae.items.kind.conj', group: 'ae.items.group.conj' },
  source: { icon: 'source', color: 'var(--k-source)', label: 'ae.items.kind.source', group: 'ae.items.group.source' },
  figure: { icon: 'image', color: 'var(--k-figure)', label: 'ae.items.kind.figure', group: 'ae.items.group.figure' },
  version: { icon: 'clock', color: 'var(--k-version)', label: 'ae.items.kind.version', group: 'ae.items.group.version' },
};

/** Order of the groups in the panel. Calcul cells are listed inside their notebook. */
export const GROUPS: ItemKind[] = ['proof', 'calc', 'note', 'conj', 'source', 'figure', 'version'];

/** Text placed inside a LaTeX argument or environment: no braces, backslashes or comment signs from titles. */
export function texSafe(s: string, n = 200): string {
  return s.replace(/[\\{}%#&$^_~]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);
}

/** Label of a dossier region in the article (`ml:` + id without separators, as texproject writes it). */
export function dossierLabel(id: string): string {
  return 'ml:' + id.replace(/[^A-Za-z0-9]/g, '');
}

/**
 * A dossier (Lean proof) inserted in the article: a reference when the article already states it, otherwise its
 * statement in a theorem-like environment linked by `% mdl:lean <id>` (the build typesets it as « non vérifié »
 * unless Lean verified the proof — docs/ARTICLE.md §1).
 */
export function dossierSnippet(d: { id: string; title: string; theorem: string; lemma: boolean }, labels: Set<string>): { text: string; cursor?: number } {
  const label = dossierLabel(d.id);
  if (labels.has(label)) return { text: `\\cref{${label}}` };
  const env = d.lemma ? 'lemma' : 'theorem';
  const title = texSafe(d.title, 120);
  const head = `\\begin{${env}}${title ? `[${title}]` : ''}\\label{${label}}\n% mdl:lean ${d.id}\n`;
  const body = (d.theorem || '').trim().slice(0, 4000);
  return { text: `${head}${body}\n\\end{${env}}\n`, cursor: head.length + body.length };
}

export function conjectureSnippet(c: { title: string; statement_nl: string }): { text: string; cursor: number } {
  const title = texSafe(c.title, 120);
  const head = `\\begin{conjecture}${title ? `[${title}]` : ''}\n`;
  const body = (c.statement_nl || '').trim().slice(0, 4000);
  return { text: `${head}${body}\n\\end{conjecture}\n`, cursor: head.length + body.length };
}

export function citeSnippet(key: string): { text: string } {
  return { text: `\\cite{${key.replace(/[{}\\,\s]/g, '')}}` };
}

export function figureSnippet(path: string, caption = ''): { text: string } {
  const tag = path.replace(/^figures\//, '').replace(/\.[a-z]+$/i, '').slice(0, 6);
  return { text: `\\begin{figure}[ht]\n\\centering\n\\includegraphics[width=0.7\\linewidth]{${path}}\n\\caption{${texSafe(caption, 200)}}\\label{fig:${tag}}\n\\end{figure}\n` };
}

/** First displayable line of a Calcul cell (code or Markdown). */
export function cellTitle(source: string): string {
  const line = source.split('\n').map((l) => l.trim()).find((l) => l && !/^#+\s*$/.test(l)) ?? '';
  return line.replace(/^#+\s*/, '').replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1').slice(0, 80);
}

/** PNG assets (32 hex ids) anywhere in a Calcul cell's outputs — what the « Figure » dialog offers too. */
export function cellAssets(o: unknown, out: string[] = []): string[] {
  if (!o || typeof o !== 'object') return out;
  if (Array.isArray(o)) { for (const x of o) cellAssets(x, out); return out; }
  const r = o as Record<string, unknown>;
  if (typeof r['asset'] === 'string' && /^[0-9a-f]{32}$/.test(r['asset']) && (!r['mime'] || r['mime'] === 'image/png') && !out.includes(r['asset'])) out.push(r['asset']);
  for (const v of Object.values(r)) cellAssets(v, out);
  return out;
}

/** A LaTeX result of a Calcul cell (`text/latex` output), as display maths. */
export function cellLatex(outputs: { data?: Record<string, unknown> }[] | undefined): string {
  for (const o of outputs ?? []) {
    const v = o.data?.['text/latex'];
    if (typeof v === 'string' && v.trim()) {
      const s = v.trim().replace(/^\$\$?|\$\$?$/g, '').replace(/^\\\[|\\\]$/g, '').trim();
      if (s) return s;
    }
  }
  return '';
}

/** Items matching a search (accent- and case-insensitive). */
export function fold(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}
export function matches(q: string, ...fields: (string | undefined | null)[]): boolean {
  const n = fold(q.trim());
  return !n || fields.some((f) => f && fold(f).includes(n));
}

// ---------------------------------------------------------------- file tree of the LaTeX project
export interface TreeNode { path: string; name: string; kind: 'tex' | 'main' | 'bib' | 'toml' | 'lock' | 'image' | 'folder';
  note?: string /* i18n key */; children?: TreeNode[]; orphan?: boolean }

/**
 * The article's directory as the author would see it in a file manager: main.tex, sections/ (in document order,
 * then files not included by main.tex), figures/, and the generated or settings files.
 */
export function fileTree(files: string[], order: string[], figures: string[]): TreeNode[] {
  const secs = files.filter((p) => p.startsWith('sections/'));
  const ordered = [...order.filter((p) => secs.includes(p)), ...secs.filter((p) => !order.includes(p)).sort()];
  const name = (p: string) => p.slice(p.lastIndexOf('/') + 1);
  return [
    { path: 'main.tex', name: 'main.tex', kind: 'main', note: 'ae.files.main' },
    { path: 'sections/', name: 'sections', kind: 'folder', children: ordered.map((p) => ({ path: p, name: name(p), kind: 'tex', orphan: !order.includes(p) })) },
    { path: 'figures/', name: 'figures', kind: 'folder', children: figures.map((p) => ({ path: p, name: name(p), kind: 'image' })) },
    { path: 'refs.bib', name: 'refs.bib', kind: 'bib', note: 'ae.files.bib' },
    { path: 'madalean.toml', name: 'madalean.toml', kind: 'toml', note: 'ae.files.toml' },
    { path: 'madalean.lock', name: 'madalean.lock', kind: 'lock', note: 'ae.files.lock' },
  ];
}
