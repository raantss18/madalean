// Minimal history router with route-level code splitting. To add a screen: see docs/UI.md « Add a screen ».
import type { Component } from 'svelte';
import type { Key } from './i18n/index.svelte';

export interface RouteDef {
  name: string;
  /** Path pattern: literal segments and `:param` (optional with `?`, last segment only). */
  pattern: string;
  load: () => Promise<{ default: Component<{ params: Record<string, string> }> }>;
  /** Shown in the navigation: the project bar (`group: 'project'`) or the logo menu, and the command palette. */
  nav?: { label: Key; icon: string; order: number; shortcut?: string; group?: 'project' };
  /** Visible without a paired session (pairing screen). */
  public?: boolean;
}

export const routes: RouteDef[] = [];

export function addRoute(r: RouteDef): void {
  routes.push(r);
}

export const route = $state<{ name: string; params: Record<string, string>; path: string; query: URLSearchParams }>({
  name: '', params: {}, path: '/', query: new URLSearchParams(),
});

export function match(path: string): { def: RouteDef; params: Record<string, string> } | null {
  const segs = path.replace(/\/+$/, '').split('/').filter(Boolean);
  for (const def of routes) {
    const ps = def.pattern.split('/').filter(Boolean);
    const params: Record<string, string> = {};
    let ok = true;
    const required = ps.filter((p) => !p.endsWith('?')).length;
    if (segs.length < required || segs.length > ps.length) continue;
    for (let i = 0; i < ps.length; i++) {
      const p = ps[i]!;
      const s = segs[i];
      if (p.startsWith(':')) {
        if (s === undefined) {
          if (!p.endsWith('?')) ok = false;
          continue;
        }
        params[p.slice(1).replace('?', '')] = decodeURIComponent(s);
      } else if (p !== s) {
        ok = false;
        break;
      }
    }
    if (ok) return { def, params };
  }
  return null;
}

function sync(): void {
  const m = match(location.pathname);
  route.path = location.pathname;
  route.query = new URLSearchParams(location.search);
  route.name = m?.def.name ?? 'notfound';
  route.params = m?.params ?? {};
}

// Called before every in-app navigation (links, back / forward): autosave flushes what is pending (S-AK).
const leaving = new Set<() => void>();
export function beforeNavigate(fn: () => void): () => void {
  leaving.add(fn);
  return () => leaving.delete(fn);
}
function runLeaving(): void {
  for (const fn of [...leaving]) {
    try { fn(); } catch { /* a failing hook never blocks navigation */ }
  }
}

export function navigate(path: string, opts: { replace?: boolean; focus?: boolean } = {}): void {
  if (path === location.pathname + location.search) return;
  runLeaving();
  if (opts.replace) history.replaceState(null, '', path);
  else history.pushState(null, '', path);
  sync();
  if (opts.focus === false) return;
  // Focus management for screen readers: move focus to the main heading after a route change.
  queueMicrotask(() => requestAnimationFrame(() => {
    const h = document.querySelector<HTMLElement>('main h1, main [data-route-focus]');
    if (h) {
      if (!h.hasAttribute('tabindex')) h.setAttribute('tabindex', '-1');
      h.focus({ preventScroll: false });
    }
  }));
}

export function startRouter(): void {
  sync();
  window.addEventListener('popstate', () => { runLeaving(); sync(); });
  // Intercept same-origin links (not downloads, not new tabs, not /api or /jupyter).
  document.addEventListener('click', (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as Element | null)?.closest?.('a');
    if (!a) return;
    // In the app shells, off-origin links go to the system browser through the bridge (docs/SHELLS.md §7).
    const ext = a.getAttribute('href') ?? '';
    const bridge = (globalThis as { madaleanShell?: { openExternal?: (u: string) => void } }).madaleanShell;
    if (/^https?:\/\//i.test(ext) && !ext.startsWith(location.origin) && typeof bridge?.openExternal === 'function') {
      e.preventDefault();
      bridge.openExternal(ext);
      return;
    }
    if (a.target || a.hasAttribute('download')) return;
    const href = a.getAttribute('href');
    if (!href || !href.startsWith('/') || href.startsWith('//') || href.startsWith('/api') || href.startsWith('/jupyter')) return;
    e.preventDefault();
    navigate(href);
  });
}
