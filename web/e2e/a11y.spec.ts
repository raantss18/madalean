import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

for (const scheme of ['light', 'dark'] as const) {
  test(`axe WCAG 2.1 AA on main screens (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    const d = (await api<{ dossiers: { id: string; status: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved')!;
    await open(page, '/', { mode: 'learn' });
    await axe(page, `home ${scheme}`);
    for (const path of [`/d/${d.id}/enonce`, `/d/${d.id}/lean`, `/d/${d.id}/preuve`, '/activite', '/actualites', '/bibliotheque', '/glossaire', '/carnet',
      '/reglages/modeles', '/reglages/appareils', '/reglages/systeme', '/reglages/apparence', '/reglages/mises-a-jour',
      '/projet', '/sources', '/notes', '/graphe', '/blueprint', '/article', '/conjectures', '/explorer', '/calcul', '/publier', '/aide', '/aide/pairing', `/d/${d.id}`, `/d/${d.id}/plan`, `/d/${d.id}/litterature`, `/d/${d.id}/versions`, `/d/${d.id}/lean?solo=1`]) {
      await page.goto(process.env['MADALEAN_URL'] + path);
      await page.waitForTimeout(500);
      await axe(page, `${path} ${scheme}`);
    }
    await page.evaluate(() => localStorage.setItem('madalean.density', 'research'));
    await page.goto(`${process.env['MADALEAN_URL']}/d/${d.id}/preuve`);
    await page.waitForTimeout(500);
    await axe(page, `proof research ${scheme}`);
  });
}

test('keyboard: skip link, command palette, pane tabs with arrows, Escape closes', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Aller au contenu' })).toBeFocused();
  await page.keyboard.press('Control+k');
  const q = page.getByRole('combobox', { name: 'Aller à… ou faire…' });
  await expect(q).toBeFocused();
  await q.fill('somme de deux');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/d\//);
  const tab = page.getByRole('tab', { selected: true });
  await tab.focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('tab', { selected: true })).toBeFocused();
  await page.keyboard.press('Control+k');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('combobox', { name: 'Aller à… ou faire…' })).toHaveCount(0);
});
