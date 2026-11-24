import { test, expect } from '@playwright/test';
import { open, api } from './util';

async function proved(): Promise<string> {
  const { dossier } = await api<{ dossier: { id: string } }>('POST', '/dossiers', { statement: 'theorem learn_t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry', title: 'Apprendre' });
  await expect.poll(async () => (await api<{ dossier: { status: string } }>('GET', `/dossiers/${dossier.id}`)).dossier.status, { timeout: 45_000 }).toBe('proved');
  return dossier.id;
}

// Learn mode (hint ladder, explain-back, exercises) is covered against the server's learning endpoints in research.spec.ts.

test('Research mode: proof shown at once, no hint ladder; split into lemmas shows the tree', async ({ page }) => {
  const id = await proved();
  await open(page, `/d/${id}/preuve`, { mode: 'research' });
  await expect(page.locator('.cm-content').first()).toContainText('theorem');
  await expect(page.getByRole('heading', { name: 'Indices, avant la preuve' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Découper en lemmes' }).first().click();
  await page.getByRole('radio', { name: 'Les écrire moi-même' }).check();
  await page.getByLabel('Lemmes (un par paragraphe, en mots ou en Lean)').fill('La somme de deux pairs est paire.\n\nZéro est pair.');
  await page.getByRole('button', { name: 'Découper et lancer' }).click();
  // S-BH: a card per sub-dossier in the thread, the tree in the « Sous-lemmes » tab
  await expect(page.getByRole('article', { name: /^Sous-dossier/ })).toHaveCount(2, { timeout: 20_000 });
  await page.getByRole('tab', { name: 'Sous-lemmes' }).click();
  await expect(page.getByRole('heading', { name: /Lemmes : \d+ prouvés sur 2/ })).toBeVisible({ timeout: 20_000 });
  for (const j of (await api<{ active: { dossier_id: string }[] }>('GET', '/jobs')).active) await api('POST', `/dossiers/${j.dossier_id}/stop`, {});
});
