// S-AP (docs/PERFORMANCE.md « Interface sur téléphone »): socket events batched per frame, lazy KaTeX and English
// catalogue, idle prefetch, per-device drafts of unsent text.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { FrameBatcher, frameOrTimeout } from '../../src/lib/store/coalesce';
import { StreamStore } from '../../src/lib/store/streams';
import { whenIdle, canPrefetch, prefetch } from '../../src/lib/ui/idle';
import { loadDraft, saveDraft, clearDraft } from '../../src/lib/ui/drafts.svelte';

describe('FrameBatcher (socket events coalesced per frame)', () => {
  it('delivers a burst once, in arrival order, at the next frame', () => {
    const frames: (() => void)[] = [];
    const got: number[][] = [];
    const b = new FrameBatcher<number>((xs) => got.push(xs), (cb) => frames.push(cb));
    for (let i = 1; i <= 50; i++) b.push(i);
    expect(got).toEqual([]);                       // nothing applied before the frame
    expect(frames).toHaveLength(1);                // one frame asked for the whole burst
    frames.shift()!();
    expect(got).toEqual([Array.from({ length: 50 }, (_, i) => i + 1)]);
    expect(b.stats).toEqual({ batches: 1, items: 50, largest: 50 });
  });
  it('a later event waits for the following frame; flush() delivers at once', () => {
    const frames: (() => void)[] = [];
    const got: string[][] = [];
    const b = new FrameBatcher<string>((xs) => got.push(xs), (cb) => frames.push(cb));
    b.push('a');
    frames.shift()!();
    b.push('b'); b.push('c');
    expect(b.pending).toBe(2);
    b.flush();
    expect(got).toEqual([['a'], ['b', 'c']]);
    frames.shift()!();                             // the frame asked for b/c finds nothing left
    expect(got).toHaveLength(2);
  });
  it('without frames (hidden tab) the timer delivers, and only once', () => {
    vi.useFakeTimers();
    try {
      const got: number[][] = [];
      const b = new FrameBatcher<number>((xs) => got.push(xs), frameOrTimeout(100));
      b.push(1); b.push(2);
      vi.advanceTimersByTime(99);
      expect(got).toEqual([]);
      vi.advanceTimersByTime(2);
      expect(got).toEqual([[1, 2]]);
    } finally { vi.useRealTimers(); }
  });
  it('the stream store can notify inside the batch (no extra frame)', () => {
    const frames: (() => void)[] = [];
    const s = new StreamStore((cb) => frames.push(cb));
    let n = 0;
    s.subscribe('j', () => n++);
    s.token('j', 'proof', 0, 'text', 'a');
    s.token('j', 'proof', 0, 'text', 'b');
    s.flush();
    expect(n).toBe(1);
    frames.shift()!();                             // the scheduled frame has nothing left to say
    expect(n).toBe(1);
    expect(s.get('j').parts[0]!.text).toBe('ab');
  });
});

describe('job index (one pass per change instead of rows × jobs)', () => {
  it('gives the same active / last job per dossier and the same running list as the reducer helpers', async () => {
    const { app } = await import('../../src/lib/store/app.svelte');
    const { activeJobFor, lastJobFor } = await import('../../src/lib/store/model');
    const mk = (id: string, dossier_id: string, state: string, created: number) => ({ id, dossier_id, state, created, stage: '', attempts: [] });
    const jobs = [mk('a', 'd1', 'done', 1), mk('b', 'd1', 'running', 2), mk('c', 'd1', 'queued', 3), mk('d', 'd2', 'failed', 5),
      mk('e', 'd2', 'done', 4), mk('f', 'd3', 'running', 0)];
    app.m.jobs = Object.fromEntries(jobs.map((j) => [j.id, j])) as never;
    for (const d of ['d1', 'd2', 'd3', 'd4']) {
      expect(app.activeJob(d)?.id).toBe(activeJobFor(app.m, d)?.id);
      expect(app.lastJob(d)?.id).toBe(lastJobFor(app.m, d)?.id);
    }
    expect(app.activeJobs.map((j) => j.id)).toEqual(['f', 'b', 'c']);
    app.m.jobs['b'] = mk('b', 'd1', 'done', 2) as never;          // a job event: the index follows
    expect(app.activeJobs.map((j) => j.id)).toEqual(['f', 'c']);
    expect(app.activeJob('d1')?.id).toBe('c');
  });
});

describe('lazy KaTeX', () => {
  it('shows the escaped TeX source until KaTeX is in, then renders it', async () => {
    vi.resetModules();
    const md = await import('../../src/lib/md');
    const k = await import('../../src/lib/katex.svelte');
    expect(k.katexNow()).toBeNull();
    const before = md.renderMarkdown('Soit $a<b$ et $$x^2$$');
    expect(before).toContain('<span class="math-pending">a&lt;b</span>');
    expect(before).not.toContain('class="katex"');
    expect(k.katexVersion()).toBe(0);
    await k.loadKatex();                           // renderMath already started it: the same promise
    expect(k.katexVersion()).toBe(1);
    const after = md.renderMarkdown('Soit $a<b$');
    expect(after).toContain('class="katex"');
    expect(after).not.toContain('math-pending');
  });
  it('loads once however many formulas ask for it', async () => {
    vi.resetModules();
    const k = await import('../../src/lib/katex.svelte');
    const [a, b] = await Promise.all([k.loadKatex(), k.loadKatex()]);
    expect(a).toBe(b);
    expect(k.katexVersion()).toBe(1);
  });
});

describe('lazy English catalogue', () => {
  beforeEach(() => { vi.resetModules(); });
  it('French is there at once; English after its chunk; a switch back while it loads wins', async () => {
    const i = await import('../../src/lib/i18n/index.svelte');
    expect(i.i18n.lang).toBe('fr');
    expect(i.t('common.loading')).not.toBe('common.loading');
    const fr = i.t('common.loading');
    const toEn = i.i18n.set('en');
    expect(i.i18n.lang).toBe('fr');                // not loaded yet: still French, never a key
    await toEn;
    expect(i.i18n.lang).toBe('en');
    expect(i.t('common.loading')).not.toBe(fr);
    await i.i18n.set('fr');
    expect(i.i18n.lang).toBe('fr');
  });
  it('fr → en → fr quickly ends in French', async () => {
    const i = await import('../../src/lib/i18n/index.svelte');
    const p = i.i18n.set('en');
    await i.i18n.set('fr');
    await p;
    expect(i.i18n.lang).toBe('fr');
  });
});

describe('idle work and prefetch', () => {
  const nav = globalThis.navigator;
  afterEach(() => { Object.defineProperty(globalThis, 'navigator', { value: nav, configurable: true }); });
  it('whenIdle runs later and can be cancelled', () => {
    vi.useFakeTimers();
    try {
      const f = vi.fn();
      whenIdle(f, 3000);
      expect(f).not.toHaveBeenCalled();
      vi.advanceTimersByTime(600);
      expect(f).toHaveBeenCalledOnce();
      const g = vi.fn();
      whenIdle(g)();
      vi.advanceTimersByTime(5000);
      expect(g).not.toHaveBeenCalled();
    } finally { vi.useRealTimers(); }
  });
  it('no prefetch on Save-Data or 2G', () => {
    Object.defineProperty(globalThis, 'navigator', { value: { connection: { saveData: true } }, configurable: true });
    expect(canPrefetch()).toBe(false);
    Object.defineProperty(globalThis, 'navigator', { value: { connection: { effectiveType: 'slow-2g' } }, configurable: true });
    expect(canPrefetch()).toBe(false);
    Object.defineProperty(globalThis, 'navigator', { value: { connection: { effectiveType: '4g' } }, configurable: true });
    expect(canPrefetch()).toBe(true);
  });
  it('each loader at most once, retried after a failure', async () => {
    vi.useFakeTimers();
    try {
      const ok = vi.fn(() => Promise.resolve());
      prefetch('t.ok', ok); prefetch('t.ok', ok);
      vi.advanceTimersByTime(600);
      expect(ok).toHaveBeenCalledOnce();
      const bad = vi.fn(() => Promise.reject(new Error('offline')));
      prefetch('t.bad', bad);
      vi.advanceTimersByTime(600);
      await Promise.resolve(); await Promise.resolve();
      prefetch('t.bad', bad);
      vi.advanceTimersByTime(600);
      expect(bad).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });
});

describe('drafts of unsent text', () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
      getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k),
    } });
  });
  it('saves, reads back, and removes empty or whitespace-only text', () => {
    saveDraft('qa.p1.all', 'Pourquoi ?');
    expect(store.get('madalean.draft.qa.p1.all')).toBe('"Pourquoi ?"');
    expect(loadDraft('qa.p1.all')).toBe('Pourquoi ?');
    saveDraft('qa.p1.all', '   \n');
    expect(store.has('madalean.draft.qa.p1.all')).toBe(false);
    saveDraft('x', 'a'); clearDraft('x');
    expect(loadDraft('x')).toBe('');
  });
  it('reads the S-AK follow-up drafts (same store) and ignores anything that is not text', () => {
    store.set('madalean.draft.thread.d1', JSON.stringify('suite'));
    expect(loadDraft('thread.d1')).toBe('suite');
    store.set('madalean.draft.bad', JSON.stringify({ text: 1 }));
    expect(loadDraft('bad')).toBe('');
    store.set('madalean.draft.broken', '{');
    expect(loadDraft('broken')).toBe('');
  });
});
