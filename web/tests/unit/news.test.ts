// « Actualités » (session S-AV): the API client builds the list's query and the « tout marquer comme lu » body from
// the same filters; every branch, group and error kind the server can send has its strings in both languages.
import { describe, it, expect, beforeEach } from 'vitest';
import { configureClient } from '../../src/lib/api/client';
import { news } from '../../src/lib/api/news';
import fr from '../../src/lib/i18n/fr';
import en from '../../src/lib/i18n/en';

let calls: { url: string; method: string; body: unknown }[] = [];
beforeEach(() => {
  calls = [];
  configureClient({
    fetcher: (async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return new Response(JSON.stringify({ items: [], total: 0, unread: 0, marked: 0 }), { status: 200 });
    }) as typeof fetch,
  });
});

describe('news API client', () => {
  it('sends only the filters that are set', async () => {
    await news.list({ q: 'théorème de Fermat', branch: 'number-theory', open: true, unread: false, saved: undefined, projects: true, limit: 30, offset: 0 });
    const u = new URL(calls[0]!.url, 'http://x');
    expect(u.pathname).toBe('/api/news');
    expect(Object.fromEntries(u.searchParams)).toEqual({ q: 'théorème de Fermat', branch: 'number-theory', open: '1', projects: '1', limit: '30', offset: '0' });
    await news.list();
    expect(calls[1]!.url).toBe('/api/news');
    await news.list({ projects: 'p-1', group: 'lean', order: 'relevance' });
    expect(calls[2]!.url).toBe('/api/news?projects=p-1&group=lean&order=relevance');
  });
  it('« mark all as read » carries the filters, not the page or the search text', async () => {
    await news.readAll({ q: 'x', group: 'lean', unread: true, saved: false, limit: 30, offset: 60, order: 'date', mine: true });
    expect(calls[0]).toEqual({ url: '/api/news/read-all', method: 'POST', body: { group: 'lean', unread: true, mine: true } });
  });
  it('item and feed calls', async () => {
    await news.patchItem(7, { saved: true });
    await news.summarize(7);
    await news.addFeed('https://a.example.org/feed', 'A');
    await news.removeFeed('feed-1 2');
    await news.refresh('ams');
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['PATCH /api/news/items/7', 'POST /api/news/items/7/summary', 'POST /api/news/feeds',
      'DELETE /api/news/feeds/feed-1%202', 'POST /api/news/refresh']);
    expect(calls[2]!.body).toEqual({ url: 'https://a.example.org/feed', title: 'A' });
    expect(calls[4]!.body).toEqual({ source: 'ams' });
  });
});

describe('news strings', () => {
  it('every error kind of the server has a plain sentence in both languages', () => {
    for (const k of ['local_mode', 'rights', 'short', 'suspect', 'no_model', 'failed']) {
      expect(fr[`news.err.${k}` as keyof typeof fr], k).toBeTruthy();
      expect(en[`news.err.${k}` as keyof typeof en], k).toBeTruthy();
    }
    for (const k of ['bad_url', 'duplicate', 'unreachable', 'not_a_feed', 'bad_value']) {
      expect(fr[`news.set.err.${k}` as keyof typeof fr], k).toBeTruthy();
      expect(en[`news.set.err.${k}` as keyof typeof en], k).toBeTruthy();
    }
  });
  it('no jargon in the French strings shown to the user', () => {
    const texts = Object.entries(fr).filter(([k]) => k.startsWith('news.')).map(([, v]) => v).join('\n');
    for (const word of ['ETag', 'backoff', 'endpoint', 'API', 'fetch', 'parser', 'FTS', 'SQLite', 'prompt', 'token', 'injection', 'cache', 'cookie'])
      expect(texts, word).not.toMatch(new RegExp(`\\b${word}\\b`, 'i'));
  });
});
