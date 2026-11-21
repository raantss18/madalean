// Meaning of a Lean name from the server: GET /learn/token (curated tactic table + the workspace's declaration index;
// unknown names are reported unknown, never invented). Cached per session.
import { research } from '../api/research';

export interface TokenInfo { title: string; body: string; module?: string }
const cache = new Map<string, Promise<TokenInfo | null>>();

export function lookupToken(name: string, workspace?: string): Promise<TokenInfo | null> {
  const k = `${workspace ?? ''}|${name}`;
  let p = cache.get(k);
  if (!p) {
    p = research.learnToken(name, workspace).then((r) => {
      if (r.known === false) return null;
      const body = [r.signature as string | undefined, (r.doc as string | undefined) || (r.text as string | undefined)].filter(Boolean).join('\n\n');
      return body ? { title: String((r['name'] as string) ?? name), body, module: r.module as string | undefined } : null;
    }).catch(() => null);
    cache.set(k, p);
  }
  return p;
}
