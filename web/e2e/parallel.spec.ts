import { test, expect } from '@playwright/test';
import { open, api } from './util';

test('parallel dossiers are visible at a glance and each can be cancelled', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  const ids: string[] = [];
  for (const p of ['Pour tout entier n, n^2 + n est pair.', 'La somme de deux entiers pairs est paire.', 'Pour tout réel x, x^2 ≥ 0.']) {
    ids.push((await api<{ dossier: { id: string } }>('POST', '/dossiers', { problem: p, title: `Parallèle ${ids.length + 1}` })).dossier.id);
  }
  // S-AK: the status button counts the running jobs; its panel lists them with « Arrêter » (it replaced the drawer)
  await page.getByRole('button', { name: /\d+ en cours/ }).click();
  const panel = page.locator('#status-panel');
  await expect(panel.getByRole('link', { name: /Parallèle/ })).toHaveCount(3, { timeout: 10_000 });
  await expect(panel.getByText(/Carte graphique \d\/\d/)).toBeVisible();
  // Cancel the second one from the status panel.
  await panel.getByRole('button', { name: 'Arrêter « Parallèle 2 »' }).click();
  await expect.poll(async () => (await api<{ dossier: { status: string } }>('GET', `/dossiers/${ids[1]}`)).dossier.status, { timeout: 15_000 }).toMatch(/stopped|proved|draft/);
  for (const id of [ids[0], ids[2]]) await api('POST', `/dossiers/${id}/stop`, {});
});

test('409 busy is explained with a « stop » action', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  const { dossier } = await api<{ dossier: { id: string } }>('POST', '/dossiers', { problem: 'Montrer que 2 + 2 = 4.', title: 'Occupé' });
  await page.goto(`${process.env['MADALEAN_URL']}/d/${dossier.id}/lean`);
  // While it works, the thread offers « Arrêter » instead of sending; quick API call to provoke 409:
  const r = await page.request.post(`${process.env['MADALEAN_URL']}/api/dossiers/${dossier.id}/message`, { data: { text: 'x', stage: 'auto' } });
  expect([202, 409]).toContain(r.status());
  await expect(page.locator('aside').getByRole('button', { name: 'Arrêter' })).toBeVisible();
  await page.locator('aside').getByRole('button', { name: 'Arrêter' }).click();
  await expect.poll(async () => (await api<{ job: unknown }>('GET', `/dossiers/${dossier.id}`)).job, { timeout: 15_000 }).toBeNull();
});
