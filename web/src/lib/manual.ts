// In-app help from docs/manual/index.json (schema madalean-manual/1, docs/SITE.md §2): the same texts as the site,
// never a second copy. Loaded lazily (its own chunk), pages filtered by interface language.
export interface ManualPage {
  id: string; lang: 'fr' | 'en'; title: string; order: number | string; section: string; audience: 'learner' | 'researcher' | 'all';
  summary: string; source: string; site_path: string; headings: { level: number; text: string; id: string }[];
  images: { src: string; exists: boolean }[]; verify: string[]; body: string; text: string;
}
export interface ManualIndex {
  schema: string; source: string; site_url: string; languages: string[];
  sections: Record<string, { id: string; title: string }[]>; site_links: Record<string, string>; pages: ManualPage[];
}

let cache: Promise<ManualIndex> | null = null;
export function loadManual(): Promise<ManualIndex> {
  cache ??= import('../../../docs/manual/index.json').then((m) => (m.default ?? m) as unknown as ManualIndex);
  return cache;
}

export function fold(s: string): string {
  return s.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
}

/** Search over title, headings, summary and text (accent-folded); returns pages with the best heading hit. */
export function searchManual(idx: ManualIndex, lang: string, q: string): { page: ManualPage; heading?: { text: string; id: string }; score: number }[] {
  const words = fold(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const out = [];
  for (const p of idx.pages.filter((x) => x.lang === lang)) {
    const title = fold(p.title), summary = fold(p.summary), text = fold(p.text);
    let score = 0;
    let heading: { text: string; id: string } | undefined;
    for (const w of words) {
      const s = (title.includes(w) ? 6 : 0) + (summary.includes(w) ? 3 : 0) + (text.includes(w) ? 1 : 0);
      const h = p.headings.find((x) => fold(x.text).includes(w));
      if (h) { heading ??= h; }
      if (!s && !h) { score = 0; break; }
      score += s + (h ? 4 : 0);
    }
    if (score) out.push({ page: p, heading, score });
  }
  return out.sort((a, b) => b.score - a.score);
}

/** Rewrites a manual link: `<id>.md#a` → help route; `site:<name>#a` → site URL (or the Updates screen); http → external. */
export function rewriteLink(idx: ManualIndex, lang: string, href: string): { href: string; external: boolean } {
  const md = /^([a-z0-9-]+)\.md(#.*)?$/.exec(href);
  if (md) return { href: `/aide/${md[1]}${md[2] ?? ''}`, external: false };
  const site = /^site:([a-z0-9-]+)(#.*)?$/.exec(href);
  if (site) {
    if (site[1] === 'updates' || site[1] === 'install') return { href: '/reglages/mises-a-jour', external: false };
    const path = idx.site_links[site[1]!] ?? '';
    return { href: `${idx.site_url}${lang}/${path}${site[2] ?? ''}`, external: true };
  }
  if (href.startsWith('#')) return { href, external: false };
  if (/^https?:\/\//.test(href)) return { href, external: true };
  return { href: '#', external: false };
}

export function imageUrl(src: string): string {
  const m = /(?:^|\/)img\/([A-Za-z0-9._-]+)$/.exec(src);
  return m ? `/help/img/${m[1]}` : '';
}
