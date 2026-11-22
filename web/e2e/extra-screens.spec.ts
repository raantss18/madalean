// The screenshots no other spec produced (S-AP regenerated every docs/screenshots/v2 image with the current UI):
// glossary, library and Claude caps at 360 / 820 / 1440 px; the Calcul notebook at 820 px, in dark mode and on a
// 390 px phone; the hint ladder; the richest proof plan of the DEMO data (a proved one first — the demo has none
// fully proved), since the original plan-real-compact-proved image showed the user's own dossier « Fonction continue
// sur un compact », which a test server does not have. Run: npx playwright test --project=screens extra-screens
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, api } from './util';

const OUT = new URL('../../docs/screenshots/v2/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const H: Record<number, number> = { 360: 780, 390: 844, 820: 1180, 1280: 900, 1440: 900 };

async function shot(page: Page, name: string, fullPage = false) {
  await page.waitForTimeout(500);
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, `horizontal scroll on ${name}`).toBeLessThanOrEqual(w!);
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage });
}
async function calculProject(): Promise<string> {
  const ps = (await api<{ projects: { id: string }[] }>('GET', '/projects')).projects;
  for (const p of ps) if ((await api<{ cells: unknown[] }>('GET', `/calcul/${p.id}/docs/calcul`)).cells.length) return p.id;
  return ps[0]!.id;
}

for (const [w, scheme] of [[360, 'light'], [360, 'dark'], [820, 'light'], [1440, 'light'], [1440, 'dark']] as const) {
  test(`glossary, library, Claude caps ${w} ${scheme}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: H[w]! });
    await page.emulateMedia({ colorScheme: scheme });
    await open(page, '/glossaire', { mode: 'research' });
    await expect(page.locator('main h1')).toBeVisible();
    await shot(page, `glossary-${w}-${scheme}`);
    await page.goto(`${process.env['MADALEAN_URL']}/bibliotheque`);
    await expect(page.locator('main h1')).toBeVisible();
    await shot(page, `library-${w}-${scheme}`);
    await page.goto(`${process.env['MADALEAN_URL']}/reglages/modeles`);
    const h = page.getByRole('heading', { name: 'Claude en renfort payant' });
    await h.scrollIntoViewIfNeeded();
    await page.evaluate(() => {
      const e = [...document.querySelectorAll('h2, h3')].find((x) => x.textContent?.includes('Claude en renfort payant'));
      if (e) window.scrollBy(0, e.getBoundingClientRect().top - 120);
    });
    await shot(page, `settings-claude-${w}-${scheme}`);
  });
}

test('Calcul at 820 px, dark at 1280 px (full page), on a 390 px phone', async ({ browser }) => {
  const pid = await calculProject();
  for (const [name, w, scheme, full] of [['calcul-820-light', 820, 'light', false], ['calcul-dark', 1280, 'dark', true], ['calcul-phone', 390, 'light', false]] as const) {
    const ctx = await browser.newContext({ viewport: { width: w, height: H[w]! }, colorScheme: scheme, locale: 'fr-FR' });
    const page = await ctx.newPage();
    await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
    await open(page, '/calcul', { mode: 'research' });
    await expect(page.locator('.tex .katex').first()).toBeVisible();
    await expect(page.locator('li.cell.figure svg').first()).toBeVisible();
    await shot(page, name, full);
    await ctx.close();
  }
});

test('hint ladder (Learn mode, desktop light)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const d = (await api<{ dossiers: { id: string; status: string; parent_id: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved' && !x.parent_id)!;
  await open(page, `/d/${d.id}/preuve`, { mode: 'learn' });
  await expect(page.getByRole('heading', { name: 'Indices, avant la preuve' })).toBeVisible();
  await shot(page, 'desktop-light-hint-ladder');
});

test('the richest proof plan of the demo data (desktop light)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const ds = (await api<{ dossiers: { id: string; status: string; parent_id: string }[] }>('GET', '/dossiers')).dossiers.filter((d) => !d.parent_id);
  let best = { id: '', score: -1 };
  for (const d of ds) {
    try {
      const p = (await api<{ plan: { nodes?: unknown[] | Record<string, unknown> } }>('GET', `/dossiers/${d.id}/plan`)).plan;
      const n = Array.isArray(p.nodes) ? p.nodes.length : Object.keys(p.nodes ?? {}).length;
      const score = (d.status === 'proved' ? 1000 : 0) + n;           // a proved plan first, then the most nodes
      if (n > 0 && score > best.score) best = { id: d.id, score };
    } catch { /* no plan */ }
  }
  expect(best.id, 'a demo dossier with a plan').not.toBe('');
  await open(page, `/d/${best.id}/plan`, { mode: 'research' });
  await expect(page.getByRole('heading', { name: 'Plan de preuve' })).toBeVisible();
  await shot(page, 'plan-real-compact-proved-desktop-light');
});
