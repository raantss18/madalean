// « Premiers pas » (S-AQ, D49): docs/screenshots/v2/wizard-*.png — every step at 1440×900 light, the main ones on a
// phone (390×844) and in the dark theme, and the Home reminder card. Run: npx playwright test --project=screens
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { api, open } from './util';

const OUT = new URL('../../docs/screenshots/v2/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const STEPS = ['welcome', 'tools', 'local', 'keys', 'hf', 'claude', 'modes', 'auto', 'pair', 'done'];

async function shot(page: Page, name: string) {
  await page.waitForTimeout(500);
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, `horizontal scroll on ${name}`).toBeLessThanOrEqual(w!);
  await page.screenshot({ path: `${OUT}${name}.png` });
}

test.beforeEach(async () => { await api('PATCH', '/setup/wizard', { done: false, completed: false, step: 'welcome', reminder: true }); });
test.afterAll(async () => { await api('PATCH', '/setup/wizard', { completed: true }); });

const SETS = [
  { size: 'desktop', width: 1440, height: 900, scheme: 'light' as const, steps: STEPS },
  { size: 'desktop', width: 1440, height: 900, scheme: 'dark' as const, steps: ['welcome', 'tools', 'keys', 'claude', 'done'] },
  { size: 'phone', width: 390, height: 844, scheme: 'light' as const, steps: ['welcome', 'tools', 'local', 'keys', 'done'] },
];
for (const set of SETS) {
  test(`wizard screens ${set.size} ${set.scheme}`, async ({ page }) => {
    await page.setViewportSize({ width: set.width, height: set.height });
    await page.emulateMedia({ colorScheme: set.scheme });
    for (const s of set.steps) {
      await open(page, `/premiers-pas/${s}`, { mode: 'learn' });
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
      await shot(page, `wizard-${s}-${set.size}-${set.scheme}`);
    }
  });
}

test('wizard Home reminder card', async ({ page }) => {
  await api('PATCH', '/setup/wizard', { done: true, step: 'keys' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ colorScheme: 'light' });
  await open(page, '/', { mode: 'learn' });
  await expect(page.getByRole('complementary', { name: 'Premiers pas' })).toBeVisible();
  await shot(page, 'wizard-home-card-desktop-light');
});
