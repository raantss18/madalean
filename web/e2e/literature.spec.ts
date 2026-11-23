import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

// S-AX (D56): « Littérature » in the proof step — the demo answers come from a real search about Bertrand's
// postulate recorded once (madalean/literature/demo_http); attachments are read once.

const STATEMENT = 'theorem bertrand_postulate (n : ℕ) (hn : 1 ≤ n) : ∃ p, Nat.Prime p ∧ n < p ∧ p ≤ 2 * n := by sorry';
const WORDS = 'Bertrand : pour tout entier n ≥ 1, il existe un nombre premier p tel que n < p ≤ 2n.';
const TEX = '\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\n\\begin{lemma}\nEvery prime number $p > 2$ is odd.\n\\end{lemma}\n\\end{document}\n';
type D = { dossier: { id: string } };

test('literature: quoted references with labels, Sources, bibliography, attachment read once', async ({ page }) => {
  const { dossier } = await api<D>('POST', '/dossiers', { statement: STATEMENT, problem: WORDS, title: 'Bertrand', start: false });
  await open(page, `/d/${dossier.id}/preuve`, { mode: 'research' });
  const panel = page.getByRole('region', { name: 'Littérature' });
  await expect(panel).toBeVisible({ timeout: 20_000 });
  await panel.getByRole('button', { name: 'Chercher dans la littérature' }).click();
  const ref = panel.locator('li.ref').filter({ hasText: 'Ramanujan Primes and Bertrand' });
  await expect(ref).toBeVisible({ timeout: 30_000 });
  await expect(ref).toContainText('Revue (relue par des pairs)');
  await expect(ref.locator('blockquote')).toContainText('Ramanujan prime');
  await expect(panel.getByText('Prépublication (non relue)').first()).toBeVisible();
  await axe(page, 'literature panel');
  await ref.getByRole('button', { name: 'Ajouter aux Sources' }).click();
  await expect(page.getByText('Ajouté aux Sources.')).toBeVisible();
  await ref.getByRole('button', { name: 'Ajouter à la bibliographie de l’article' }).click();
  await expect(page.getByText('Ajouté à la bibliographie.')).toBeVisible();
  // an attachment: read once, its statement quoted with its place
  await panel.locator('input[type=file]').setInputFiles({ name: 'note.tex', mimeType: 'application/x-tex', buffer: Buffer.from(TEX) });
  const att = panel.locator('.atts li').first();
  await expect(att).toContainText('note.tex');
  await expect(att.locator('.chip').first()).toHaveText('lue', { timeout: 30_000 });
  await att.locator('summary').click();
  await expect(att.locator('blockquote')).toContainText('Every prime number $p > 2$ is odd.');
  await axe(page, 'literature attachments');
  // English
  await api('PATCH', '/settings', { language: 'en' });
  try {
    await open(page, `/d/${dossier.id}/preuve`, { mode: 'research' });
    await expect(page.getByRole('region', { name: 'Literature' })).toContainText('Journal (peer reviewed)', { timeout: 20_000 });
    await expect(page.getByRole('region', { name: 'Literature' })).toContainText('Attachments');
  } finally { await api('PATCH', '/settings', { language: 'fr' }); }
});

test('literature panel fits a phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  const { dossier } = await api<D>('POST', '/dossiers', { statement: STATEMENT, problem: WORDS, title: 'Bertrand phone', start: false });
  await open(page, `/d/${dossier.id}/preuve`, { mode: 'research' });
  const panel = page.getByRole('region', { name: 'Littérature' });
  await panel.getByRole('button', { name: 'Chercher dans la littérature' }).click();
  await expect(panel.locator('li.ref').first()).toBeVisible({ timeout: 30_000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
