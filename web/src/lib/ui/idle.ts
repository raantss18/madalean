// Work that can wait: after the first paint, when the main thread is idle (S-AP). Prefetching is skipped when the
// device asks to save data or is on a 2G connection.

/** Runs `fn` when the browser is idle (at most `timeout` ms later). Returns a cancel function. */
export function whenIdle(fn: () => void, timeout = 3000): () => void {
  const w = globalThis as unknown as {
    requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number; cancelIdleCallback?: (h: number) => void;
  };
  if (typeof w.requestIdleCallback === 'function') {
    const h = w.requestIdleCallback(fn, { timeout });
    return () => w.cancelIdleCallback?.(h);
  }
  const h = setTimeout(fn, Math.min(timeout, 500));
  return () => clearTimeout(h);
}

/** False when prefetching would cost the user: Save-Data, or a 2G connection. */
export function canPrefetch(): boolean {
  const c = (globalThis.navigator as unknown as { connection?: { saveData?: boolean; effectiveType?: string } } | undefined)?.connection;
  if (!c) return true;
  return !c.saveData && !/(^|-)2g$/.test(c.effectiveType ?? '');
}

/** Each loader at most once, when idle, if prefetching is allowed; failures are ignored (the screen loads it later). */
const done = new Set<string>();
export function prefetch(key: string, load: () => Promise<unknown>): void {
  if (done.has(key) || !canPrefetch()) return;
  done.add(key);
  whenIdle(() => { load().catch(() => done.delete(key)); });
}
