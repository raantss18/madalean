// « Mémoire » (S-BD, D62): export choices, import with a dry-run preview then the report, backups autosaved,
// dataset link; axe 0 violations (French desktop, English phone).
import { test, expect } from '@playwright/test';
import { open, api, axe, URL } from './util';

test('memory: export, import preview → apply, backups, dataset', async ({ page }) => {
  await open(page, '/reglages/memoire', { mode: 'research' });
  await expect(page.getByRole('heading', { name: 'Exporter' })).toBeVisible();
  await axe(page, 'memory');
  // the bundle of this server, imported back: the preview says « déjà présent » and nothing is re-added
  const res = await fetch(URL() + '/api/memory/export?parts=library,lessons,recipes');
  expect(res.status).toBe(200);
  const buf = Buffer.from(await res.arrayBuffer());
  await page.locator('input[type=file]').setInputFiles({ name: 'm.madalean-memory', mimeType: 'application/zip', buffer: buf });
  const prev = page.getByRole('region', { name: 'Aperçu de l’import' });
  await expect(prev).toBeVisible();
  await expect(prev).toContainText('Bibliothèque');
  await axe(page, 'memory preview');
  await prev.getByRole('button', { name: 'Importer' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Import terminé.' }).first()).toBeVisible();
  // a file that is not a bundle: refused with a plain message
  await page.locator('input[type=file]').setInputFiles({ name: 'x.madalean-memory', mimeType: 'application/zip', buffer: Buffer.from('nope') });
  await expect(page.getByText('Ce fichier n’est pas une mémoire Madalean.').first()).toBeVisible();
  // backups: autosaved on change
  await page.getByLabel('Sauvegarder automatiquement').check();
  await expect.poll(async () => (await api<{ backups: { enabled: boolean } }>('GET', '/memory')).backups.enabled).toBe(true);
  await page.getByLabel('Copies gardées').fill('3');
  await page.getByLabel('Copies gardées').blur();
  await expect.poll(async () => (await api<{ backups: { keep: number } }>('GET', '/memory')).backups.keep).toBe(3);
  await page.getByRole('button', { name: 'Sauvegarder maintenant' }).click();
  await expect(page.locator('.mem code', { hasText: /^madalean-memory-\d{8}-\d{6}\.madalean-memory$/ })).toBeVisible();
  await page.getByLabel('Sauvegarder automatiquement').uncheck();
  await expect.poll(async () => (await api<{ backups: { enabled: boolean } }>('GET', '/memory')).backups.enabled).toBe(false);
  const ds = await fetch(URL() + '/api/memory/dataset');
  expect(ds.status).toBe(200);
  for (const line of (await ds.text()).split('\n').filter(Boolean)) expect(JSON.parse(line).verified).toMatch(/^lean-strict/);
});

test('memory in English on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.emulateMedia({ colorScheme: 'dark' });
  await open(page, '/reglages/langue', { mode: 'research' });
  await page.getByRole('radio', { name: 'English' }).check();
  await page.goto(URL() + '/reglages/memoire');
  await expect(page.getByRole('heading', { name: 'Automatic backups' })).toBeVisible();
  await axe(page, 'memory en phone');
  await page.goto(URL() + '/reglages/langue');
  await page.getByRole('radio', { name: 'Français' }).check();
  await expect(page.getByRole('heading', { name: 'Langue' })).toBeVisible();
});
