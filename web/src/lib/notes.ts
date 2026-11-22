// Notes: turning `[[links]]` into navigable Markdown links for the preview (the server resolves links for
// backlinks/graph; here we only need hrefs), and finding fenced Lean blocks.

export interface LinkCtx { noteIdByTitle: Map<string, string>; dossierIdByTitle: Map<string, string> }

/** `[[Title|label]]`, `[[note:ID]]`, `[[dossier:ID|…]]`, `[[@key#p12]]`, `[[passage:C]]`, `[[lib:Name]]` → Markdown. Code spans/blocks untouched. */
export function linkify(body: string, ctx: LinkCtx): string {
  const parts = body.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return parts.map((p, i) => (i % 2 === 1 ? p : p.replace(/\[\[([^\]\n]+)\]\]/g, (_m, inner: string) => {
    const [target, label] = inner.split('|') as [string, string | undefined];
    const t = target.trim();
    const text = (label ?? t).replace(/[[\]]/g, '');
    let href = '';
    if (t.startsWith('note:')) href = `/notes/${encodeURIComponent(t.slice(5))}`;
    else if (t.startsWith('dossier:')) {
      const ref = t.slice(8);
      href = `/d/${encodeURIComponent(ctx.dossierIdByTitle.get(ref.toLowerCase()) ?? ref)}`;
    } else if (t.startsWith('@')) href = `/sources?tab=library&key=${encodeURIComponent(t.slice(1).split('#')[0] ?? '')}`;
    else if (t.startsWith('passage:') || t.startsWith('lib:')) href = '';
    else {
      const id = ctx.noteIdByTitle.get(t.toLowerCase());
      href = id ? `/notes/${encodeURIComponent(id)}` : '';
    }
    return href ? `[${text}](${href})` : `**${text}**`;
  }))).join('');
}

export interface LeanBlock { index: number; code: string; startLine: number }
export function leanBlocks(body: string): LeanBlock[] {
  const out: LeanBlock[] = [];
  const lines = body.split('\n');
  let i = 0;
  let idx = 0;
  while (i < lines.length) {
    if (/^```\s*lean4?\s*$/.test(lines[i]!)) {
      const start = i;
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i]!)) code.push(lines[i++]!);
      out.push({ index: idx++, code: code.join('\n'), startLine: start + 1 });
    }
    i++;
  }
  return out;
}

/** The body with the code of Lean block `index` replaced by `code` (S-AM: « Appliquer la correction »); unchanged
 *  when there is no such block. */
export function replaceLeanBlock(body: string, index: number, code: string): string {
  const b = leanBlocks(body).find((x) => x.index === index);
  if (!b) return body;
  const lines = body.split('\n');
  const n = b.code === '' ? 0 : b.code.split('\n').length;
  lines.splice(b.startLine, n, ...code.replace(/\n+$/, '').split('\n'));
  return lines.join('\n');
}

/** Applies the user's choice for each conflict hunk to rebuild a body (server conflict format, 0-based base lines). */
export function resolveConflicts(theirsBody: string, conflicts: { mine: string; theirs: string }[], choice: ('mine' | 'theirs' | 'both')[]): string {
  let out = theirsBody;
  conflicts.forEach((c, i) => {
    const pick = choice[i] ?? 'theirs';
    if (pick === 'theirs' || !c.theirs) {
      if (pick === 'mine' && !c.theirs) out = out + (out.endsWith('\n') ? '' : '\n') + c.mine;
      return;
    }
    const rep = pick === 'mine' ? c.mine : c.theirs + c.mine;
    const at = out.indexOf(c.theirs);
    if (at >= 0) out = out.slice(0, at) + rep + out.slice(at + c.theirs.length);
  });
  return out;
}
