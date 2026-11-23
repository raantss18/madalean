// The « Actualités » badge (session S-AV): the number of unread items of the user's domains, shared by the Home card
// and the logo menu. Quiet on purpose: a number, never a toast. Loaded once when something shows it, then kept up to
// date by the server's `news.updated` event and by what the user reads.
import { app } from './store/app.svelte';
import { news, type NewsOverview } from './api/news';

export const newsBadge = $state<{ unread: number; show: boolean; overview: NewsOverview | null; loaded: boolean }>({
  unread: 0, show: true, overview: null, loaded: false,
});

let loading: Promise<void> | null = null;
let listening = false;

export function loadNewsOverview(force = false): Promise<void> {
  if (!listening) {
    listening = true;
    app.on('news.updated', (ev) => {
      const n = (ev as unknown as { unread?: number }).unread;
      if (typeof n === 'number') newsBadge.unread = n;
      void loadNewsOverview(true);
    });
  }
  if (loading && !force) return loading;
  loading = news.overview().then((o) => {
    newsBadge.overview = o;
    newsBadge.unread = o.unread;
    newsBadge.show = o.badge;
    newsBadge.loaded = true;
  }).catch(() => { newsBadge.loaded = true; });
  return loading;
}

export function setNewsUnread(n: number): void {
  newsBadge.unread = Math.max(0, n);
  if (newsBadge.overview) newsBadge.overview.unread = newsBadge.unread;
}

/** Plain-language pieces shared by the screen, the card and the settings. */
export function sourceName(s: { fr: string; en: string } | undefined, lang: string, fallback = ''): string {
  return s ? (lang === 'en' ? s.en : s.fr) : fallback;
}
