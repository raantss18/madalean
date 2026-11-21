import { test, expect } from '@playwright/test';
import { open, api } from './util';

test('two browser contexts stay in sync live (dossier, status, settings, deletion with undo)', async ({ browser }) => {
  const a = await (await browser.newContext({ locale: 'fr-FR' })).newPage();
  const b = await (await browser.newContext({ locale: 'fr-FR', viewport: { width: 360, height: 780 } })).newPage();
  await open(a, '/', { mode: 'research' });
  await open(b, '/', { mode: 'research' });
  // A creates a dossier; B sees it appear in its list and its status change live.
  await a.getByRole('radio', { name: 'Directement en Lean' }).check();
  const ed = a.getByRole('textbox', { name: 'Énoncé Lean' }).first();
  await ed.click();
  await a.keyboard.type('theorem sync_t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry');
  await a.getByLabel('Titre du dossier').fill('Synchronisé');
  await a.getByRole('button', { name: 'Prouver cet énoncé' }).click();
  await expect(a).toHaveURL(/\/d\/.+\/preuve/);
  const id = a.url().split('/d/')[1]!.split('/')[0]!;
  await b.goto(`${process.env['MADALEAN_URL']}/d/${id}`);
  await expect(b.getByRole('heading', { level: 1, name: 'Synchronisé' })).toBeVisible();
  await expect(b.locator('.phase-txt')).toContainText('Prouvé', { timeout: 45_000 });
  await expect(a.getByRole('heading', { name: /Preuve vérifiée par Lean/ })).toBeVisible();
  // Rename on B → A's heading follows.
  await b.getByRole('button', { name: 'Autres actions' }).click();
  await b.getByRole('menuitem', { name: 'Renommer' }).click();
  await b.getByLabel('Titre').fill('Synchronisé bis');
  await b.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(a.getByRole('heading', { level: 1, name: 'Synchronisé bis' })).toBeVisible();
  // Settings change on A (mode) → B's privacy indicator follows.
  await api('PATCH', '/settings', { mode: 'local' });
  await expect(b.getByRole('button', { name: /Local uniquement/ })).toBeVisible();
  await api('PATCH', '/settings', { mode: 'auto' });
  // Delete on A (with undo) → B leaves the dossier list; undo → back.
  await a.goto(`${process.env['MADALEAN_URL']}/d/${id}`);
  await a.getByRole('button', { name: 'Autres actions' }).click();
  await a.getByRole('menuitem', { name: /Mettre à la corbeille/ }).click();
  await expect(a.getByText('« Synchronisé bis » mis à la corbeille.')).toBeVisible();
  await expect.poll(async () => (await api<{ dossiers: { id: string }[] }>('GET', '/dossiers')).dossiers.some((d) => d.id === id)).toBe(false);
  await a.getByRole('button', { name: 'Annuler' }).click();
  await expect(a.getByRole('heading', { level: 1, name: 'Synchronisé bis' })).toBeVisible();
  await a.context().close();
  await b.context().close();
});

test('reconnect: a dropped WebSocket resumes without losing events', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  const before = await page.evaluate(() => (window as unknown as { __madalean: { seqStats: { last: number } } }).__madalean.seqStats.last);
  // Go offline (closes the socket), change things on the server, come back.
  await page.context().setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await expect(page.getByText(/Hors ligne/)).toBeVisible();
  await api('POST', '/projects', { title: 'Créé pendant la coupure' });
  await page.context().setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(page.getByRole('combobox', { name: 'Projet' }).locator('option', { hasText: 'Créé pendant la coupure' })).toHaveCount(1, { timeout: 15_000 });
  const after = await page.evaluate(() => (window as unknown as { __madalean: { seqStats: { last: number } } }).__madalean.seqStats.last);
  expect(after).toBeGreaterThan(before);
});
