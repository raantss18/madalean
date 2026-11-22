// Phone/tablet display fixes (session S-AA, docs/UI.md §12): the first-run tour never hides the statement field or
// the send button, menus sit directly on the on-screen keyboard, and menus switch to bottom sheets below 768 px
// (S-AK: there is no bottom bar any more; sheets sit on the screen's bottom edge). Set SHOTS_DIR to also save a
// screenshot of every case.
import { test, expect, type Page } from '@playwright/test';
import { open } from './util';

const WIDTHS = [360, 412, 600, 700, 768, 1024] as const;
const HEIGHT: Record<number, number> = { 360: 780, 412: 915, 600: 960, 700: 1000, 768: 1024, 1024: 1366 };
const SCHEMES = ['light', 'dark'] as const;

async function shot(page: Page, name: string): Promise<void> {
  const dir = process.env['SHOTS_DIR'];
  if (dir) await page.screenshot({ path: `${dir}/${name}.png` });
}

type Box = { x: number; y: number; width: number; height: number };
const overlaps = (a: Box, b: Box) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

for (const w of WIDTHS) {
  for (const scheme of SCHEMES) {
    test.describe(`${w}px ${scheme}`, () => {
      test.use({ viewport: { width: w, height: HEIGHT[w]! }, hasTouch: w < 1024, isMobile: w < 768, colorScheme: scheme });

      test('tour leaves the statement field and the send button visible and usable', async ({ page }) => {
        await open(page, '/', { tour: true, mode: 'learn' });
        const tour = page.locator('section.tour');
        await expect(tour).toBeVisible();
        await page.waitForTimeout(250);
        const tb = (await tour.boundingBox())!;
        const field = page.locator('.compose .cm-editor').first();
        const send = page.locator('.compose .btn.primary.big');
        for (const el of [field, send]) {
          await el.scrollIntoViewIfNeeded();
          const b = (await el.boundingBox())!;
          const t2 = (await tour.boundingBox())!;
          expect(overlaps(b, t2), `tour over ${await el.getAttribute('class')} at ${w}px`).toBe(false);
        }
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(100);
        // On first view (no scrolling) the statement field is not under the card either.
        const fb = (await field.boundingBox())!;
        expect(overlaps(fb, (await tour.boundingBox())!)).toBe(false);
        expect(tb.width).toBeGreaterThan(200);
        await shot(page, `home-tour-${w}-${scheme}`);
        // Still dismissable.
        await tour.getByRole('button', { name: 'Passer' }).click();
        await expect(tour).toBeHidden();
      });

      test('menu: bottom sheet below 768 px, popover from 768 px', async ({ page }) => {
        await open(page, '/article', { mode: 'research' });
        const more = page.getByRole('button', { name: /Plus d.actions/ }).first();
        await expect(more).toBeVisible();
        await more.click();
        const menu = page.getByRole('menu');
        await expect(menu).toBeVisible();
        const mb = (await menu.boundingBox())!;
        if (w < 768) {
          // Sheet: anchored 8 px above the bottom edge, nearly full width (capped on wide phones), entirely on screen.
          expect(Math.abs(mb.y + mb.height + 8 - HEIGHT[w]!)).toBeLessThanOrEqual(2);
          expect(mb.width).toBeGreaterThanOrEqual(Math.min(w - 16, 560) - 2);
          await expect(page.locator('.sheet-scrim')).toBeVisible();
        } else {
          const bb = (await more.boundingBox())!;
          expect(mb.y).toBeGreaterThanOrEqual(bb.y + bb.height);
          expect(mb.width).toBeLessThan(400);
          await expect(page.locator('.sheet-scrim')).toBeHidden();
        }
        expect(mb.x).toBeGreaterThanOrEqual(0);
        expect(mb.x + mb.width).toBeLessThanOrEqual(w);
        expect(mb.y + mb.height).toBeLessThanOrEqual(HEIGHT[w]!);
        await shot(page, `menu-${w}-${scheme}`);
        await page.keyboard.press('Escape');
        await expect(menu).toBeHidden();
      });
    });
  }
}

for (const w of [360, 412, 600, 700] as const) {
  for (const scheme of SCHEMES) {
    test.describe(`keyboard ${w}px ${scheme}`, () => {
      test.use({ viewport: { width: w, height: HEIGHT[w]! }, hasTouch: true, isMobile: true, colorScheme: scheme });

      test('menu opened while the keyboard is up sits directly on the keyboard, then on the bottom edge', async ({ page }) => {
        await open(page, '/article', { mode: 'research' });
        const editor = page.locator('.cm-content').first();
        await expect(editor).toBeVisible();
        await editor.click();
        // Simulated keyboard: the web view shrinks by 45 % while the field is focused (interactive-widget=resizes-content).
        const kbTop = Math.round(HEIGHT[w]! * 0.55);
        await page.setViewportSize({ width: w, height: kbTop });
        await expect(page.locator('html')).toHaveAttribute('data-kb', 'open');
        await page.getByRole('button', { name: /Plus d.actions/ }).first().click();
        const menu = page.getByRole('menu');
        await expect(menu).toBeVisible();
        await page.waitForTimeout(200);
        // Focus left the editor for the menu but the keyboard is still up: no gap.
        await expect(page.locator('html')).toHaveAttribute('data-kb', 'open');
        let mb = (await menu.boundingBox())!;
        expect(Math.abs(kbTop - (mb.y + mb.height))).toBeLessThanOrEqual(10);
        expect(mb.y).toBeGreaterThanOrEqual(0);
        await shot(page, `menu-keyboard-${w}-${scheme}`);
        // Keyboard goes down: the sheet moves back to the bottom edge.
        await page.setViewportSize({ width: w, height: HEIGHT[w]! });
        await expect(page.locator('html')).not.toHaveAttribute('data-kb', 'open');
        await page.waitForTimeout(200);
        mb = (await menu.boundingBox())!;
        expect(Math.abs(mb.y + mb.height + 8 - HEIGHT[w]!)).toBeLessThanOrEqual(2);
      });
    });
  }
}
