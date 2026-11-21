import { test, expect } from '@playwright/test';
import { open, api } from './util';

async function proved(): Promise<string> {
  const { dossier } = await api<{ dossier: { id: string } }>('POST', '/dossiers', { statement: 'theorem learn_t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry', title: 'Apprendre' });
  await expect.poll(async () => (await api<{ dossier: { status: string } }>('GET', `/dossiers/${dossier.id}`)).dossier.status, { timeout: 45_000 }).toBe('proved');
  return dossier.id;
}

test('Learn mode: hint ladder before the proof (reflection required), explain-back, faded exercise checked by Lean', async ({ page }) => {
  const id = await proved();
  await open(page, `/d/${id}/preuve`, { mode: 'learn' });
  await expect(page.getByRole('heading', { name: 'Indices, avant la preuve' })).toBeVisible();
  await expect(page.locator('.cm-content')).toHaveCount(0);            // proof hidden
  await page.getByLabel('Qu’avez-vous essayé, ou quelle est votre idée ?').fill('Écrire a = 2k et b = 2l.');
  await page.getByRole('radio', { name: 'Trouver l’approche' }).check();
  await page.getByRole('button', { name: 'Un premier indice' }).click();
  await expect(page.locator('.hintbox').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel('Qu’est-ce que cet indice vous a appris ?')).toBeVisible({ timeout: 30_000 });
  // Next hint is refused until the reflection is written.
  await page.getByRole('button', { name: /Indice suivant/ }).click();
  await expect(page.getByText('Écrivez d’abord ce que l’indice précédent vous a appris')).toBeVisible();
  await page.getByLabel('Qu’est-ce que cet indice vous a appris ?').fill('Il faut utiliser la définition de pair.');
  await page.getByRole('button', { name: /Indice suivant/ }).click();
  await expect(page.locator('.hintbox')).toHaveCount(2, { timeout: 30_000 });
  await page.getByRole('button', { name: 'J’ai trouvé, montrer la preuve' }).click();
  await expect(page.locator('.cm-content').first()).toContainText('theorem');
  // Explain it back.
  await page.getByLabel('Votre explication').last().fill('On écrit a = 2k, b = 2l donc a + b = 2(k + l), qui est pair.');
  await page.getByRole('button', { name: 'Faire relire mon explication' }).last().click();
  await expect(page.locator('.turns .tutor').last()).not.toBeEmpty({ timeout: 30_000 });
  // Faded exercise: the last step is removed; the original line makes Lean accept it.
  await expect(page.getByRole('heading', { name: 'Exercice : terminez la preuve' })).toBeVisible();
  const d = await api<{ dossier: { current: { proof: string } } }>('GET', `/dossiers/${id}`);
  const exercise = page.getByRole('textbox', { name: 'Preuve à compléter' });
  await exercise.click();
  await page.keyboard.press('Control+a');
  await page.keyboard.insertText(d.dossier.current.proof);
  await page.getByRole('button', { name: 'Vérifier la preuve avec Lean' }).click();
  await expect(page.getByText('Lean accepte la preuve.')).toBeVisible({ timeout: 30_000 });
});

test('Research mode: proof shown at once, no hint ladder; split into lemmas shows the tree', async ({ page }) => {
  const id = await proved();
  await open(page, `/d/${id}/preuve`, { mode: 'research' });
  await expect(page.locator('.cm-content').first()).toContainText('theorem');
  await expect(page.getByRole('heading', { name: 'Indices, avant la preuve' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Découper en lemmes' }).first().click();
  await page.getByRole('radio', { name: 'Les écrire moi-même' }).check();
  await page.getByLabel('Lemmes (un par paragraphe, en mots ou en Lean)').fill('La somme de deux pairs est paire.\n\nZéro est pair.');
  await page.getByRole('button', { name: 'Découper et lancer' }).click();
  await expect(page.getByRole('heading', { name: /Lemmes : \d+ prouvés sur 2/ })).toBeVisible({ timeout: 20_000 });
  for (const j of (await api<{ active: { dossier_id: string }[] }>('GET', '/jobs')).active) await api('POST', `/dossiers/${j.dossier_id}/stop`, {});
});
