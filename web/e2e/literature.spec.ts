import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

// S-AX (D56): the « Littérature » tab of the pane — the demo answers come from a real search about Bertrand's
// postulate recorded once (madalean/literature/demo_http); attachments are read once.

const STATEMENT = 'theorem bertrand_postulate (n : ℕ) (hn : 1 ≤ n) : ∃ p, Nat.Prime p ∧ n < p ∧ p ≤ 2 * n := by sorry';
const WORDS = 'Bertrand : pour tout entier n ≥ 1, il existe un nombre premier p tel que n < p ≤ 2n.';
const TEX = '\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\n\\begin{lemma}\nEvery prime number $p > 2$ is odd.\n\\end{lemma}\n\\end{document}\n';
type D = { dossier: { id: string } };

test('literature: quoted references with labels, Sources, bibliography, attachment read once', async ({ page }) => {
  const { dossier } = await api<D>('POST', '/dossiers', { statement: STATEMENT, problem: WORDS, title: 'Bertrand', start: false });
  await open(page, `/d/${dossier.id}/litterature`, { mode: 'research' });
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
    await open(page, `/d/${dossier.id}/litterature`, { mode: 'research' });
    await expect(page.getByRole('region', { name: 'Literature', exact: true })).toContainText('Journal (peer reviewed)', { timeout: 20_000 });
    await expect(page.getByRole('region', { name: 'Literature', exact: true })).toContainText('Attachments');
  } finally { await api('PATCH', '/settings', { language: 'fr' }); }
});

test('literature panel fits a phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  const { dossier } = await api<D>('POST', '/dossiers', { statement: STATEMENT, problem: WORDS, title: 'Bertrand phone', start: false });
  await open(page, `/d/${dossier.id}/litterature`, { mode: 'research' });
  const panel = page.getByRole('region', { name: 'Littérature' });
  await panel.getByRole('button', { name: 'Chercher dans la littérature' }).click();
  await expect(panel.locator('li.ref').first()).toBeVisible({ timeout: 30_000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('a file joined to a new problem is attached before the work starts', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  await page.locator('#home-files').setInputFiles({ name: 'given.tex', mimeType: 'application/x-tex', buffer: Buffer.from(TEX) });
  await expect(page.getByRole('list', { name: 'Joindre un fichier' }).getByText('given.tex')).toBeVisible();
  await page.locator('#statement-input').click();
  await page.keyboard.type('Tout nombre premier p > 2 est impair.');
  await page.getByRole('button', { name: 'Traduire et prouver' }).click();
  await expect(page).toHaveURL(/\/d\/[^/]+$/);
  const id = decodeURIComponent(new URL(page.url()).pathname.split('/')[2] ?? '');
  const r = await api<{ attachments: { name?: string; n: number }[] }>('GET', `/dossiers/${encodeURIComponent(id)}/attachments`);
  expect(r.attachments.length).toBe(1);
  await axe(page, 'dossier after a new problem with a file');
});
