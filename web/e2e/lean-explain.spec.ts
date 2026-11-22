import { test, expect, type Page } from '@playwright/test';
import { open, api, axe } from './util';

// S-AM (D45): « Expliquer » for Lean — statement, proof (and a manual draft), notes' Lean blocks. The demo's Lean
// refuses code naming `no_such_lemma`; the demo model explains it and proposes `Nat.le_refl`, which that Lean accepts.

type D = { dossier: { id: string; theorem: string; statements: { source: string; code: string }[]; proofs: { source: string; ok: boolean }[]; status: string; current: { statement: string } } };

async function explainMenu(page: Page, scope: ReturnType<Page['locator']>, item: string) {
  await scope.getByRole('button', { name: 'Expliquer' }).click();
  await page.getByRole('menuitem', { name: item }).click();
}

test('statement: explain the error, a fix accepted by Lean, apply it as a new version; line by line', async ({ page }) => {
  const { dossier } = await api<D>('POST', '/dossiers', { statement: 'theorem lx_demo (n : ℕ) (h : no_such_lemma n) : n ≤ n := by sorry', title: 'Expliquer Lean', start: false });
  await open(page, `/d/${dossier.id}/lean`, { mode: 'research' });
  await page.getByRole('button', { name: 'Vérifier avec Lean' }).first().click();
  await expect(page.locator('.check.bad')).toBeVisible({ timeout: 20_000 });
  const panel = page.locator('section.panel').filter({ has: page.getByRole('heading', { name: 'Énoncé Lean' }) });
  // the menu: outside click and Escape close it (S-AK)
  await panel.getByRole('button', { name: 'Expliquer' }).click();
  await expect(page.getByRole('menuitem', { name: 'Expliquer l’erreur' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menuitem')).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Expliquer' })).toBeFocused();
  await explainMenu(page, panel, 'Expliquer l’erreur');
  const out = page.getByRole('region', { name: 'L’erreur, expliquée' });
  await expect(out).toContainText('Lean ne connaît pas le nom', { timeout: 20_000 });
  await expect(out).toContainText('Correction acceptée par Lean');
  await expect(out.locator('pre.fix')).toContainText('Nat.le_refl');
  await axe(page, 'lean explain error');
  const before = (await api<D>('GET', `/dossiers/${dossier.id}`)).dossier.statements.length;
  await out.getByRole('button', { name: 'Appliquer la correction' }).click();
  await expect(page.getByText('Correction appliquée : nouvelle version.')).toBeVisible();
  await expect(out).toHaveCount(0);
  const after = (await api<D>('GET', `/dossiers/${dossier.id}`)).dossier;
  expect(after.statements.length).toBe(before + 1);
  expect(after.statements[after.statements.length - 1]!.source).toBe('user');
  expect(after.current.statement).toContain('Nat.le_refl');
  // line by line: header lines glossed without a model, the theorem explained
  await explainMenu(page, panel, 'Expliquer ligne par ligne');
  const lines = page.getByRole('region', { name: 'Explication ligne par ligne' });
  await expect(lines).toContainText('Charge Mathlib', { timeout: 20_000 });
  await expect(lines).toContainText('Cette ligne');
  await lines.getByRole('button', { name: 'Fermer' }).click();
  await expect(lines).toHaveCount(0);
});

test('proof: lines of the verified proof; a refused manual proof explained and fixed (strict check)', async ({ page }) => {
  const { dossier } = await api<D>('POST', '/dossiers', { statement: 'theorem lx_proof (n : ℕ) : n ≤ n := by sorry', title: 'Preuve à expliquer', start: false });
  const name = dossier.theorem;
  await api('POST', `/dossiers/${dossier.id}/versions/proof`, { code: `theorem ${name} (n : ℕ) : n ≤ n := by\n  exact Nat.le_refl n` });
  // a draft in progress on this device (ManualEdit keeps it), refused by Lean
  await page.addInitScript(([id, n]) => {
    try { localStorage.setItem(`madalean.editing.${id}.proof`, JSON.stringify({ base: '', text: `theorem ${n} (n : ℕ) : n ≤ n := by\n  exact no_such_lemma n` })); } catch { /* */ }
  }, [dossier.id, name] as const);
  await open(page, `/d/${dossier.id}/preuve`, { mode: 'research' });
  const result = page.locator('section.result');
  await expect(result.getByRole('heading', { name: /Preuve vérifiée par Lean/ })).toBeVisible({ timeout: 20_000 });
  // lines of the verified proof
  await explainMenu(page, result.locator('.tools'), 'Expliquer ligne par ligne');
  await expect(page.getByRole('region', { name: 'Explication ligne par ligne' })).toContainText('Cette ligne', { timeout: 20_000 });
  await page.getByRole('region', { name: 'Explication ligne par ligne' }).getByRole('button', { name: 'Fermer' }).click();
  // the draft: check → refused (no longer the current proof) → explain → apply = a new version, checked strictly
  const edit = page.locator('.edit');
  if (!(await edit.isVisible())) await page.getByRole('button', { name: 'Modifier la preuve' }).click();
  await edit.getByRole('button', { name: /Vérifier/ }).first().click();
  const refused = page.locator('.last-bad');
  await expect(refused).toContainText('refusée par Lean', { timeout: 20_000 });
  await expect(refused.locator('pre')).toContainText('no_such_lemma');
  await explainMenu(page, refused, 'Expliquer l’erreur');
  const out = page.getByRole('region', { name: 'L’erreur, expliquée' });
  await expect(out.locator('pre.fix')).toContainText('Nat.le_refl', { timeout: 20_000 });
  const n0 = (await api<D>('GET', `/dossiers/${dossier.id}`)).dossier.proofs.length;
  await out.getByRole('button', { name: 'Appliquer la correction' }).click();
  await expect.poll(async () => (await api<D>('GET', `/dossiers/${dossier.id}`)).dossier.proofs.length).toBe(n0 + 1);
  const d = (await api<D>('GET', `/dossiers/${dossier.id}`)).dossier;
  expect(d.proofs[d.proofs.length - 1]!.source).toBe('user');
  expect(d.proofs[d.proofs.length - 1]!.ok).toBe(true);
});

test('notes: a Lean block explained and fixed in place; phone width, dark theme, axe', async ({ page }) => {
  const pid = (await api<{ projects: { id: string; title: string }[] }>('GET', '/projects')).projects[0]!.id;
  const { note } = await api<{ note: { id: string } }>('POST', '/notes', { project_id: pid, title: 'Bloc à expliquer', body: 'Un bloc :\n\n```lean\ntheorem nb (n : ℕ) : n ≤ n := by\n  exact no_such_lemma n\n```\n' });
  await page.addInitScript((p) => { try { localStorage.setItem('madalean.project', p); } catch { /* */ } }, pid);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark' });
  await open(page, `/notes/${note.id}`, { mode: 'research' });
  const lb = page.locator('.lb').first();
  await lb.getByRole('button', { name: 'Vérifier avec Lean' }).click();
  await expect(lb.locator('.chip.failed')).toBeVisible({ timeout: 20_000 });
  await lb.getByRole('button', { name: 'Expliquer' }).click();
  await expect(page.locator('.sheet-scrim')).toBeVisible();               // a bottom sheet on phones
  await axe(page, 'lean explain menu (phone, dark)');
  await page.getByRole('menuitem', { name: 'Expliquer l’erreur' }).click();
  const out = lb.getByRole('region', { name: 'L’erreur, expliquée' });
  await expect(out.locator('pre.fix')).toContainText('Nat.le_refl', { timeout: 20_000 });
  const w = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(w).toBeLessThanOrEqual(390);
  await axe(page, 'lean explain answer (phone, dark)');
  await out.getByRole('button', { name: 'Appliquer la correction' }).click();
  await expect.poll(async () => (await api<{ note: { body: string } }>('GET', `/notes/${note.id}`)).note.body, { timeout: 15_000 }).toContain('exact Nat.le_refl n');
  await expect(lb.locator('.chip.proved')).toBeVisible({ timeout: 20_000 });
});
