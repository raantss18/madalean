import { test, expect } from '@playwright/test';
import { open, api, axe, URL as BASE } from './util';

// « De l'article au plan formel » (D60): the Blueprint's « Plan formel » tab on the demo paper (a plan as a finished
// run leaves it: a definition not formalised, a lemma proved by its dossier, a theorem in Mathlib, a corollary
// formalised). Read-only: the run itself is covered by tests/test_paperplan.py with the real Lean.
type P = { id: string; title: string };

test('formal plan: statuses, progress, verbatim statement beside the Lean statement, exports', async ({ page }) => {
  const pid = (await api<{ projects: P[] }>('GET', '/projects')).projects.find((p) => /Recherche/.test(p.title))!.id;
  await page.addInitScript((p) => { try { localStorage.setItem('madalean.project', p); } catch { /* */ } }, pid);
  await open(page, '/blueprint', { mode: 'research' });
  await page.getByRole('button', { name: 'Plan formel' }).click();
  await expect(page.getByRole('button', { name: 'Plan formel' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('2 / 4 prouvés ou dans Mathlib')).toBeVisible();
  const legend = page.getByRole('list', { name: 'Légende du plan formel' });
  await expect(legend).toContainText('dans Mathlib (1)');
  await expect(legend).toContainText('prouvé (Lean) (1)');
  await expect(legend).toContainText('non formalisé (1)');
  await expect(page.locator('svg .gn.ps-in_mathlib')).toHaveCount(1);
  await axe(page, 'blueprint-plan');
  await page.getByLabel('Liste').check();
  await page.getByRole('button', { name: /Corollary 2\.2/ }).click();
  const side = page.locator('.side');
  await expect(side.locator('.stlabel')).toHaveText('énoncé formalisé');
  await expect(side.locator('pre.verbatim')).toContainText('then $n^4$ is even');
  await expect(side).toContainText('Corollary 2.2, §2, l. 57');
  await expect(side.locator('.cm-content')).toContainText('paper_cor_fourth');
  await page.getByRole('button', { name: /Theorem 2\.1/ }).click();
  await expect(side).toContainText('dans Mathlib : Even.pow');
  // the closure of a selection is counted before anything runs
  await page.getByRole('checkbox', { name: /Sélectionner Corollary 2\.2/ }).check();
  await expect(page.getByRole('button', { name: 'Formaliser la sélection (1) et ses dépendances (4)' })).toBeEnabled();
  // exports (blueprint-style LaTeX, HTML)
  const href = await page.getByRole('link', { name: 'Exporter (LaTeX)' }).getAttribute('href');
  const tex = await (await page.request.get(`${BASE()}${href}`)).text();
  expect(tex).toContain('\\lean{paper_thm_square}\n\\mathlibok');
  expect(tex).toContain('\\uses{thm:square}');
  const html = await page.request.get(`${BASE()}${await page.getByRole('link', { name: 'Exporter (HTML)' }).getAttribute('href')}`);
  expect(html.status()).toBe(200);
  expect(await html.text()).toContain('2/4');
});
