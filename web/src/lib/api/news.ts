// « Actualités » (session S-AV, docs/NEWS.md, docs/API.md): the mathematical watch kept by the server.
import { request } from './client';

export interface NewsMatch { project: string; score: number; terms: string[] }
export interface NewsItem {
  id: number; key: string; source: string; group: string;
  kind: 'paper' | 'problem' | 'question' | 'release' | 'change' | 'post';
  url: string; title: string; summary: string; authors: string[]; published: number; fetched: number;
  open: boolean; branches: string[]; cats: string[];
  extra: { arxiv?: string; primary?: string; comment?: string; oeis?: string[]; erdos?: number; state?: string; repo?: string; tag?: string;
    prize?: string; score?: number; answers?: number; licence?: string; suspect?: boolean };
  read: boolean; saved: boolean; fr: string; fr_model: string; fr_t: number; projects: NewsMatch[]; relevance: number;
}
export interface NewsFeed { id: string; url: string; title: string; enabled: boolean }
export interface NewsSettings {
  enabled: boolean; interval_hours: number; branches: string[]; sources: Record<string, boolean>; feeds: NewsFeed[];
  summaries: boolean; badge: boolean; keep_days: number; max_items: number;
}
export interface NewsSource {
  id: string; group: string; enabled: boolean; custom: boolean; items: number; unread: number;
  checked: number | null; ok: number | null; error: string; retry_at: number | null;
  fr: string; en: string; about_fr: string; about_en: string; home: string; host: string; licence: string; terms: string; url?: string;
  /** false: a © source — title, excerpt and link only, no automatic summary. */
  summaries: boolean;
}
export interface NewsNamed { id: string; fr: string; en: string }
export interface NewsSources { sources: NewsSource[]; verified: string; groups: NewsNamed[]; branches: NewsNamed[] }
export interface NewsOverview {
  unread: number; unread_all: number; items: number; saved: number; for_projects: number; open: number; newest: NewsItem[];
  last_refresh: number | null; next_refresh: number | null; mode: 'local' | 'auto' | 'online'; demo: boolean;
  enabled: boolean; badge: boolean; summaries: boolean; branches: string[]; errors: string[];
}
export interface NewsQuery {
  q?: string; branch?: string; source?: string; group?: string; open?: boolean; projects?: boolean | string;
  unread?: boolean; saved?: boolean; mine?: boolean; order?: 'date' | 'relevance'; limit?: number; offset?: number;
}
export interface NewsReport { sources?: { id: string; status: string; new?: number; error?: string }[]; new?: number; unread?: number; skipped?: string; demo?: boolean }

function qs(q: NewsQuery): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === '' || v === false) continue;
    p.set(k, v === true ? '1' : String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}
/** The same filters as a JSON body (« tout marquer comme lu »). */
function filterBody(q: NewsQuery): Record<string, unknown> {
  const { limit: _l, offset: _o, order: _r, q: _q, ...rest } = q;
  return Object.fromEntries(Object.entries(rest).filter(([, v]) => v !== undefined && v !== '' && v !== false));
}

export const news = {
  list: (q: NewsQuery = {}, signal?: AbortSignal) => request<{ items: NewsItem[]; total: number; unread: number }>('GET', `/news${qs(q)}`, undefined, { signal }),
  overview: () => request<NewsOverview>('GET', '/news/overview'),
  sources: () => request<NewsSources>('GET', '/news/sources'),
  settings: () => request<{ settings: NewsSettings }>('GET', '/news/settings'),
  patchSettings: (p: Partial<NewsSettings>) => request<{ settings: NewsSettings }>('PATCH', '/news/settings', p),
  refresh: (source?: string) => request<NewsReport>('POST', '/news/refresh', source ? { source } : {}),
  addFeed: (url: string, title = '') => request<{ settings: NewsSettings; feed: NewsFeed; tested: boolean; entries: number }>('POST', '/news/feeds', { url, title }),
  removeFeed: (id: string) => request<{ settings: NewsSettings }>('DELETE', `/news/feeds/${encodeURIComponent(id)}`),
  patchItem: (id: number, p: { read?: boolean; saved?: boolean }) => request<{ item: NewsItem; unread: number }>('PATCH', `/news/items/${id}`, p),
  readAll: (q: NewsQuery = {}) => request<{ marked: number; unread: number }>('POST', '/news/read-all', filterBody(q)),
  summarize: (id: number) => request<{ item: NewsItem }>('POST', `/news/items/${id}/summary`, {}),
};
