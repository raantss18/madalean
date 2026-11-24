import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

test('statement → Lean → proof → export, follow-up, version restore', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  await expect(page.getByRole('heading', { level: 1, name: 'Que voulez-vous prouver ?' })).toBeVisible();
  await axe(page, 'home');
  // (a) Énoncé: type with live maths preview.
  const editor = page.getByRole('textbox', { name: 'Énoncé' }).first();
  await editor.click();
  await page.keyboard.type('Montrer que la somme de deux entiers pairs est paire. $a+b$');
  await expect(page.locator('.preview-box .katex').first()).toBeVisible();
  await page.getByRole('button', { name: 'Traduire et prouver' }).click();
  // (b) S-BH: lands on the thread; the live output streams there, the Lean tab of the pane shows the statement.
  await expect(page).toHaveURL(/\/d\/[^/]+$/);
  await page.getByRole('tab', { name: 'Lean', exact: true }).click();
  await expect(page).toHaveURL(/\/d\/[^/]+\/lean$/);
  await expect(page.getByRole('tab', { name: 'Lean', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('.lean-step').getByText('Lean comprend le code').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('.cm-content').first()).toContainText('Even (a + b)');
  // (c) Preuve: the pipeline continues by itself; go to the proof step and wait for the verdict.
  await page.getByRole('tab', { name: /Preuve/ }).click();
  await expect(page.getByRole('heading', { name: /Preuve vérifiée par Lean/ })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/Lean v4/)).toBeVisible();
  await axe(page, 'proof step');
  const id = page.url().split('/d/')[1]!.split('/')[0]!;
  // Export: real URLs with Content-Disposition attachment.
  await page.getByRole('button', { name: 'Exporter' }).click();
  const dl = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'Lean (.lean)' }).click();
  expect((await dl).suggestedFilename()).toMatch(/\.lean$/);
  // Follow-up in the thread.
  const box = page.getByRole('textbox', { name: 'Une précision, une correction ?' });
  await box.fill('Trouve une preuve plus courte.');
  await page.getByRole('combobox', { name: 'À propos de' }).selectOption('proof');
  await page.getByRole('button', { name: 'Envoyer' }).click();
  await expect(page.locator('.ev.user').last()).toContainText('Trouve une preuve plus courte.');
  await expect.poll(async () => (await api<{ dossier: { proofs: unknown[] }; job: unknown }>('GET', `/dossiers/${id}`)).job, { timeout: 45_000 }).toBeNull();
  // Version restore with undo.
  const d = await api<{ dossier: { proofs: unknown[]; cur_proof: number } }>('GET', `/dossiers/${id}`);
  if (d.dossier.proofs.length > 1) {
    await page.getByRole('button', { name: /Versions \(\d+\)/ }).first().click();
    await page.getByRole('button', { name: 'Revenir à celle-ci' }).first().click();
    await expect(page.getByText(/Version \d+ rétablie/)).toBeVisible();
    await expect.poll(async () => (await api<{ dossier: { cur_proof: number } }>('GET', `/dossiers/${id}`)).dossier.cur_proof).not.toBe(d.dossier.cur_proof);
  }
});
