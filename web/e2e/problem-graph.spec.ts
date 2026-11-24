// Problem graph (S-AY, D57): the « Graphe » view of the Plan tab — target, legend, node detail (« Pourquoi cette
// piste ? »), « Expliquer la démonstration », the lessons screen; axe 0 violations, light desktop and dark phone,
// no horizontal scroll, FR and EN.
import { test, expect, type Page } from '@playwright/test';
import { open, api, axe } from './util';

async function noHScroll(page: Page, label: string) {
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, `horizontal scroll on ${label}`).toBeLessThanOrEqual(w!);
}

for (const v of [{ name: 'desktop', width: 1440, height: 900, scheme: 'light', lang: 'fr' }, { name: 'phone', width: 390, height: 844, scheme: 'dark', lang: 'en' }] as const) {
  test(`problem graph ${v.name} ${v.scheme} ${v.lang}`, async ({ page }) => {
    await page.setViewportSize({ width: v.width, height: v.height });
    await page.emulateMedia({ colorScheme: v.scheme });
    const d = (await api<{ dossiers: { id: string; title: string; project_id: string }[] }>('GET', '/dossiers')).dossiers.find((x) => /carré d'un entier pair/.test(x.title))!;
    await page.addInitScript(([p]) => { try { localStorage.setItem('madalean.project', p!); localStorage.setItem('madalean.planView', 'graph'); } catch { /* */ } }, [d.project_id]);
    await open(page, `/d/${d.id}/plan`, { mode: 'research', lang: v.lang });
    await expect(page.locator('.pg h3')).toBeVisible();
    await expect(page.locator('.pg .target')).toBeVisible();
    await expect(page.locator('.pg .legend li')).toHaveCount(5);
    await noHScroll(page, `graph ${v.name}`);
    await axe(page, `graph-${v.name}`);
    const first = page.locator('.pg .nodes .nd').first();
    if (await first.count()) {
      await first.click();
      await expect(page.locator('.pg .panel h4')).toBeVisible();
      await axe(page, `graph-panel-${v.name}`);
    }
    await page.locator('.pg .head .btn').click();                      // « Expliquer la démonstration »
    await expect(page.locator('dialog[open] .md, dialog[open] p').first()).toBeVisible();
    await axe(page, `graph-explain-${v.name}`);
    await page.keyboard.press('Escape');
    await expect(page.locator('dialog[open]')).toHaveCount(0);
    // D59: the drawn view (desktop only; phones keep the list), lazy-loaded, nodes as buttons in the list order
    if (v.name === 'phone') {
      await expect(page.locator('.pg .views')).toHaveCount(0);
    } else {
      await page.locator('.pg .views button').nth(1).click();
      await expect(page.locator('.pg .gm .nb').first()).toBeVisible();
      await expect(page.locator('.pg .nodes')).toHaveCount(0);
      await noHScroll(page, 'graph drawn');
      await axe(page, 'graph-drawn');
      await page.locator('.pg .gm .nb').first().focus();
      await page.keyboard.press('Enter');
      await expect(page.locator('.pg .panel h4')).toBeVisible();
      await page.locator('.pg .views button').first().click();
      await expect(page.locator('.pg .nodes')).toBeVisible();
    }
  });
}

test('lessons screen', async ({ page }) => {
  await open(page, '/reglages/apprentissage', { mode: 'research' });
  await expect(page.locator('.ls .lead')).toBeVisible();
  await axe(page, 'lessons');
});
