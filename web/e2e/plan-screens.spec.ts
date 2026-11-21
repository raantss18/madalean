// Proof plan mind map (S-L): docs/screenshots/v2/plan-*.png at 360×780, 820×1180, 1440×900, light and dark — no
// horizontal page scroll, no overlap between map nodes, axe 0 violations (map, panel, outline), FR and EN.
// Run: npx playwright test --project=screens plan-screens
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, api, axe } from './util';

const OUT = new URL('../../docs/screenshots/v2/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const SIZES = [
  { name: 'phone', width: 360, height: 780 },
  { name: 'tablet', width: 820, height: 1180 },
  { name: 'desktop', width: 1440, height: 900 },
] as const;

async function noHScroll(page: Page, label: string) {
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, `horizontal scroll on ${label}`).toBeLessThanOrEqual(w!);
}
async function noOverlap(page: Page) {
  const boxes = await page.locator('.map .mnode, .map .mtrack').evaluateAll((els) => els.map((e) => {
    const s = (e as HTMLElement).style; return { x: parseFloat(s.left), y: parseFloat(s.top), w: parseFloat(s.width), h: parseFloat(s.height) };
  }));
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i]!, b = boxes[j]!;
    expect(a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h, `nodes ${i}/${j} overlap`).toBe(false);
  }
}
async function shot(page: Page, name: string) {
  await page.waitForTimeout(350);
  await noHScroll(page, name);
  await page.screenshot({ path: `${OUT}${name}.png` });
}

for (const scheme of ['light', 'dark'] as const) {
  for (const s of SIZES) {
    test(`plan mind map ${s.name} ${scheme}`, async ({ page }) => {
      await page.setViewportSize({ width: s.width, height: s.height });
      await page.emulateMedia({ colorScheme: scheme });
      const d = (await api<{ dossiers: { id: string; title: string; project_id: string }[] }>('GET', '/dossiers')).dossiers.find((x) => /carré d'un entier pair/.test(x.title))!;
      const lang = s.name === 'tablet' && scheme === 'dark' ? 'en' : 'fr';
      await page.addInitScript(([p, l]) => { try { localStorage.setItem('madalean.project', p!); localStorage.removeItem('madalean.planView'); localStorage.setItem('madalean.lang', l!); } catch { /* */ } }, [d.project_id, lang]);
      if (lang === 'en') await api('PATCH', '/settings', { language: 'en' });
      try {
      await open(page, `/d/${d.id}/plan`, { mode: 'research', lang });
      await expect(page.locator('.plan h2').first()).toBeVisible();
      if (s.name === 'phone') {
        await expect(page.locator('.outline')).toBeVisible();          // the outline is the main view on a phone
        await axe(page, `plan-outline-${s.name}-${scheme}`);
        await shot(page, `plan-${s.name}-${scheme}-outline`);
        await page.locator('.plan .seg label').first().click();              // map, secondary
      }
      await expect(page.locator('.map')).toBeVisible();
      await noOverlap(page);
      await axe(page, `plan-map-${s.name}-${scheme}`);
      await shot(page, `plan-${s.name}-${scheme}-map`);
      await page.locator('.map .mnode').nth(2).click();
      await expect(page.locator('.panel-node h3')).toBeVisible();
      await page.locator('.panel-node').scrollIntoViewIfNeeded();
      await axe(page, `plan-panel-${s.name}-${scheme}`);
      await shot(page, `plan-${s.name}-${scheme}-node`);
      } finally { if (lang === 'en') await api('PATCH', '/settings', { language: 'fr' }); }
    });
  }
}
