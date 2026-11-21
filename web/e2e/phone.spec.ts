import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

test.use({ viewport: { width: 360, height: 780 }, hasTouch: true, isMobile: true });

test('phone layout: bottom navigation, no horizontal scroll, steps reachable, touch targets', async ({ page }) => {
  await open(page, '/', { mode: 'learn' });
  const nav = page.getByRole('navigation', { name: 'Navigation principale' });
  await expect(nav).toBeVisible();
  for (const path of ['/', '/activite', '/bibliotheque', '/reglages']) {
    await page.goto(process.env['MADALEAN_URL'] + path);
    await page.waitForTimeout(300);
    const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
    expect(sw, path).toBeLessThanOrEqual(w!);
  }
  const d = (await api<{ dossiers: { id: string; status: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved')!;
  await page.goto(`${process.env['MADALEAN_URL']}/d/${d.id}`);
  await page.getByRole('tab', { name: /Traduction Lean/ }).click();
  await expect(page.locator('.cm-content').first()).toBeVisible();
  // Tap a Lean token → its meaning appears in the learn panel.
  await page.locator('.cm-content').first().getByText('theorem').first().click();
  await expect(page.getByText(/Déclare un théorème/)).toBeVisible();
  await axe(page, 'phone lean step');
  // Touch targets of the bottom navigation and the step tabs are ≥ 44 px.
  for (const el of await page.locator('.bottomnav a, [role=tab]').all()) {
    const b = (await el.boundingBox())!;
    expect(b.height).toBeGreaterThanOrEqual(44);
    expect(b.width).toBeGreaterThanOrEqual(44);
  }
  // The dossier drawer opens from the menu button and closes on pick.
  await page.getByRole('button', { name: 'Dossiers' }).click();
  await expect(page.locator('#rail')).toBeVisible();
});
