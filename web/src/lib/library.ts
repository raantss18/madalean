// Library of proven results (S-M, finished by S-W): filters and grouping, kept out of the screen so they are tested.
// Filters (domain, project, tag, status, text) combine with the grouping (« Ranger par »).
import type { CatalogEntry } from './api/workbench';

export type GroupBy = 'domain' | 'project' | 'tag' | 'none';
export interface LibFilter {
  q?: string; // folded text search
  status?: '' | 'verified' | 'conditional';
  domain?: string; // '' = all
  project?: string | null; // null = all, '' = results without a project
  tag?: string | null; // null = all, '' = results without a tag
  label?: (e: CatalogEntry) => string; // extra searchable text (translated domain name…)
}

export const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

export function filterResults(entries: CatalogEntry[], f: LibFilter): CatalogEntry[] {
  const needle = fold((f.q ?? '').trim());
  return entries
    .filter((e) => (!f.status || e.status === f.status) &&
      (!f.domain || e.domain === f.domain) &&
      (f.project == null || (e.project_id || '') === f.project) &&
      (f.tag == null || (f.tag === '' ? e.tags.length === 0 : e.tags.includes(f.tag))) &&
      (!needle || fold(`${e.name} ${e.title} ${e.statement} ${e.nl} ${e.tags.join(' ')} ${e.project} ${f.label?.(e) ?? e.domain}`).includes(needle)))
    .sort((a, b) => b.t - a.t);
}

/** Groups in display order: biggest first, « none » ('') last. A result with several tags appears under each tag,
 * except when one tag is chosen in the filter (then only under it). */
export function groupResults(list: CatalogEntry[], by: GroupBy, tag: string | null = null): [string, CatalogEntry[]][] {
  const g = new Map<string, CatalogEntry[]>();
  const add = (k: string, e: CatalogEntry) => { if (!g.has(k)) g.set(k, []); g.get(k)!.push(e); };
  for (const e of list) {
    if (by === 'domain') add(e.domain, e);
    else if (by === 'project') add(e.project_id || '', e);
    else if (by === 'tag') { if (tag !== null) add(tag, e); else if (e.tags.length) for (const tg of e.tags) add(tg, e); else add('', e); }
    else add('*', e);
  }
  return [...g.entries()].sort(([a, x], [b, y]) => (a === '' ? 1 : b === '' ? -1 : y.length - x.length || a.localeCompare(b)));
}

/** The values that exist, with their counts, for the filter menus (no empty choice is offered). */
export function facets(entries: CatalogEntry[]) {
  const dom = new Map<string, number>(), proj = new Map<string, number>(), tag = new Map<string, number>();
  let untagged = 0;
  for (const e of entries) {
    dom.set(e.domain, (dom.get(e.domain) ?? 0) + 1);
    proj.set(e.project_id || '', (proj.get(e.project_id || '') ?? 0) + 1);
    if (e.tags.length) for (const tg of new Set(e.tags)) tag.set(tg, (tag.get(tg) ?? 0) + 1); else untagged++;
  }
  const byCount = (m: Map<string, number>) => [...m.entries()].sort(([a, x], [b, y]) => y - x || a.localeCompare(b));
  return { domains: byCount(dom), projects: byCount(proj), tags: byCount(tag), untagged };
}
