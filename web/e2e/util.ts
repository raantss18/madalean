import { expect, type Page, type BrowserContext } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export const URL = () => process.env['MADALEAN_URL']!;
export const REMOTE = () => process.env['MADALEAN_REMOTE_URL']!;

/** Opens the app on the local (trusted) listener with the tour already dismissed. */
export async function open(page: Page, path = '/', opts: { tour?: boolean; mode?: 'learn' | 'research'; lang?: 'fr' | 'en' } = {}): Promise<void> {
  await page.addInitScript(([tour, mode]) => {
    try {
      if (!tour) localStorage.setItem('madalean.tour', '1');
      if (mode) localStorage.setItem('madalean.density', mode);
    } catch { /* ignore */ }
  }, [Boolean(opts.tour), opts.mode ?? ''] as const);
  await page.goto(URL() + path);
  await expect(page.locator('main')).toBeVisible();
}

export async function api<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(URL() + '/api' + path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status} ${await r.text()}`);
  return (await r.json()) as T;
}

export async function axe(page: Page, label: string): Promise<void> {
  const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).exclude('.katex-mathml').analyze();
  const v = res.violations.map((x) => `${x.id} (${x.impact}): ${x.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
  expect(v, `axe violations on ${label}`).toEqual([]);
}

export async function newContext(browser: import('@playwright/test').Browser, opts: Parameters<import('@playwright/test').Browser['newContext']>[0] = {}): Promise<BrowserContext> {
  return browser.newContext({ locale: 'fr-FR', ...opts });
}
