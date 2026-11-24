import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

test.use({ viewport: { width: 360, height: 780 }, hasTouch: true, isMobile: true });

test('phone layout: no bottom bar, no horizontal scroll, steps reachable, touch targets', async ({ page }) => {
  await open(page, '/', { mode: 'learn' });
  // S-AK: the logo menu and the project bar replace the bottom navigation
  await expect(page.locator('.bottomnav')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Sections du projet' })).toBeVisible();
  for (const path of ['/', '/activite', '/actualites', '/bibliotheque', '/reglages']) {
    await page.goto(process.env['MADALEAN_URL'] + path);
    await page.waitForTimeout(300);
    const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
    expect(sw, path).toBeLessThanOrEqual(w!);
  }
  const d = (await api<{ dossiers: { id: string; status: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved')!;
  await page.goto(`${process.env['MADALEAN_URL']}/d/${d.id}`);
  // S-BH: on a phone the reference views are a sheet
  await page.getByRole('button', { name: 'Références' }).click();
  await page.getByRole('tab', { name: 'Lean', exact: true }).click();
  await expect(page.locator('.cm-content').first()).toBeVisible();
  // Tap a Lean token → its meaning appears in the learn panel.
  await page.locator('.cm-content').first().getByText('theorem').first().click();
  await expect(page.getByText(/Déclare un théorème/)).toBeVisible();
  await axe(page, 'phone lean step');
  // Touch targets of the top bar, the project bar and the step tabs are ≥ 44 px.
  for (const el of await page.locator('[role=tab]').all()) expect((await el.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.getByRole('button', { name: 'Masquer le volet' }).click();
  for (const el of await page.locator('.topbar button, #project-bar a').all()) {
    const b = (await el.boundingBox())!;
    expect(b.height).toBeGreaterThanOrEqual(44);
    expect(b.width).toBeGreaterThanOrEqual(44);
  }
  // The dossiers are one tap away in the context switcher; picking one closes it.
  await page.locator('#context-switcher').click();
  const panel = page.getByRole('dialog', { name: 'Projets et dossiers' });
  await expect(panel).toBeVisible();
  await panel.locator('a.item').first().click();
  await expect(panel).toBeHidden();
});
