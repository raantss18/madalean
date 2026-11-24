import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

// S-BC (D61): « Préparer pour Mathlib » from a dossier's verified proof and from the library. The demo's Lean accepts
// the file (no real Mathlib search, no #lint: those checks show « non vérifié »); no GitHub key in the demo, so only
// « Copier » / « Télécharger le fichier » are offered.

type D = { dossier: { id: string; theorem: string } };

test('dossier: prepare, steps, checklist, file, PR text; copy/download only without a GitHub key', async ({ page }) => {
  const { dossier } = await api<D>('POST', '/dossiers', { statement: 'theorem ml_demo (a b : ℕ) (h : a ≤ b) : a ≤ b + 0 := by sorry', title: 'Pour Mathlib', start: false });
  await api('POST', `/dossiers/${dossier.id}/versions/proof`, { code: `theorem ${dossier.theorem} (a b : ℕ) (h : a ≤ b) : a ≤ b + 0 := by\n  simpa using h` });
  await open(page, `/d/${dossier.id}/preuve`, { mode: 'research' });
  const btn = page.getByRole('button', { name: 'Préparer pour Mathlib' });
  await expect(btn).toBeVisible({ timeout: 20_000 });
  await btn.click();
  const panel = page.getByRole('region', { name: 'Préparer une contribution à Mathlib' });
  await expect(panel.getByLabel('Votre nom (ligne de copyright)')).not.toHaveValue('');
  await panel.getByLabel('Votre nom (ligne de copyright)').fill('Ada Lovelace');
  await panel.getByRole('button', { name: 'Lancer la préparation' }).click();
  await expect(panel.getByRole('list', { name: 'Étapes' })).toBeVisible();
  await expect(panel.getByRole('heading', { name: 'Liste de contrôle' })).toBeVisible({ timeout: 60_000 });
  await expect(panel.getByRole('cell').first()).toBeVisible();
  await expect(panel.getByRole('rowheader', { name: 'En-tête de copyright' })).toBeVisible();
  await expect(panel.locator('pre.file')).toContainText('Authors: Ada Lovelace');
  await expect(panel.locator('code.name')).toHaveText('Nat.le_add_zero_of_le');
  await expect(panel.getByText(/feat\(/)).toBeVisible();
  await expect(panel.getByText('enregistrez une clé GitHub dans Réglages → Clés', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: /Créer une branche/ })).toHaveCount(0);
  const href = await panel.getByRole('link', { name: 'Télécharger le fichier' }).getAttribute('href');
  const file = await (await fetch(process.env['MADALEAN_URL'] + href!)).text();
  expect(file).toContain('theorem le_add_zero_of_le');
  await axe(page, 'mathlib contribution panel');
  await panel.getByRole('button', { name: 'Fermer' }).click();
  await expect(panel).toHaveCount(0);
  // reopened: the package is kept
  await btn.click();
  await expect(page.getByRole('region', { name: 'Préparer une contribution à Mathlib' }).locator('pre.file')).toContainText('Ada Lovelace');
});

test('library: the verified result offers « Préparer pour Mathlib »', async ({ page }) => {
  const { dossier } = await api<D>('POST', '/dossiers', { statement: 'theorem ml_lib (n : ℕ) : n ≤ n + 1 := by sorry', title: 'Résultat de bibliothèque', start: false });
  await api('POST', `/dossiers/${dossier.id}/versions/proof`, { code: `theorem ${dossier.theorem} (n : ℕ) : n ≤ n + 1 := by\n  omega` });
  await open(page, '/bibliotheque', { mode: 'research' });
  await page.getByRole('radio', { name: 'Tableau' }).check({ force: true });
  await page.locator('table.tbl .link-btn', { hasText: 'Résultat de bibliothèque' }).first().click();
  const detail = page.locator('aside.detail');
  await detail.getByRole('button', { name: 'Préparer pour Mathlib' }).click();
  const panel = page.getByRole('region', { name: 'Préparer une contribution à Mathlib' });
  await expect(panel.getByRole('button', { name: /Lancer la préparation|Recommencer/ })).toBeVisible();
  await axe(page, 'mathlib contribution panel (library)');
});
