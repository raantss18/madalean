import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

// Verified exercises (S-BE, DECISIONS D63) and the Malagasy interface; the demo's Lean is a stand-in (no_such = refused).
test.afterEach(async () => { await api('PATCH', '/settings', { language: 'fr' }); });

test('exercises in French: filters, answer, hints, solution, teacher tools, axe', async ({ page }) => {
  test.setTimeout(180_000);
  await open(page, '/', { mode: 'learn' });
  await page.getByRole('button', { name: 'Menu Madalean' }).click();
  await page.getByRole('menuitem', { name: 'Exercices' }).click();
  await expect(page.getByRole('heading', { name: 'Exercices', level: 1 })).toBeVisible();
  const all = await page.locator('ul.list > li').count();
  expect(all).toBeGreaterThanOrEqual(20);
  await page.getByLabel('Niveau').first().selectOption('olympiade');
  await expect.poll(() => page.locator('ul.list > li').count()).toBeLessThan(all);
  await page.getByLabel('Niveau').first().selectOption('lycee');
  for (const colorScheme of ['light', 'dark'] as const) { await page.emulateMedia({ colorScheme }); await axe(page, `exercises ${colorScheme}`); }
  await page.getByRole('link', { name: /Somme de deux nombres pairs/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Somme de deux nombres pairs');
  await expect(page.getByText('La solution se montre après tous les indices')).toBeVisible();

  await page.getByRole('radio', { name: 'En Lean' }).check();
  const ed = page.locator('.cm-content').first();
  await ed.click();
  await page.keyboard.type('exact no_such');
  await page.getByRole('button', { name: 'Vérifier', exact: true }).click();
  await expect(page.getByText('Lean refuse cette preuve.')).toBeVisible();
  for (const n of [1, 2, 3]) await page.getByRole('button', { name: `Indice suivant (${n} sur 3)` }).click();
  await expect(page.locator('ol.hints > li')).toHaveCount(3);
  await page.getByRole('button', { name: 'Voir la solution' }).click();
  await expect(page.getByText('Solution acceptée par Lean.')).toBeVisible();
  await expect(page.locator('pre', { hasText: 'obtain' })).toBeVisible();
  await ed.click();
  await page.keyboard.press('ControlOrMeta+a');
  await page.keyboard.type('exact ha.add hb');
  await page.getByRole('button', { name: 'Vérifier', exact: true }).click();
  await expect(page.getByText('Lean accepte votre preuve.')).toBeVisible();
  for (const colorScheme of ['light', 'dark'] as const) { await page.emulateMedia({ colorScheme }); await axe(page, `exercise ${colorScheme}`); }
  await page.reload();
  await expect(page.locator('ol.hints > li')).toHaveCount(3);          // progress and draft are kept
  await expect(page.locator('.cm-content').first()).toContainText('ha.add hb');

  await page.getByRole('link', { name: 'Tous les exercices' }).click();
  await expect(page.getByText(/^1 résolu/)).toBeVisible();
  await expect(page.getByText('Résolu après la solution').last()).toBeVisible();
  await page.getByText('Outils de l’enseignant').click();
  await page.getByRole('checkbox', { name: /Somme de deux nombres pairs/ }).check();
  const href = await page.getByRole('link', { name: 'LaTeX' }).getAttribute('href');
  const tex = await page.evaluate(async (u) => (await fetch(u!)).text(), href);
  expect(tex).toContain('\\begin{document}');
  expect(tex).toContain('Montrer que');
  await page.getByLabel('Importer un fichier').setInputFiles({ name: 'b.json', mimeType: 'application/json', buffer: Buffer.from('{"format":"x"}') });
  await expect(page.getByText('n’est pas une banque d’exercices')).toBeVisible();
  await axe(page, 'teacher tools');
});

test('the Malagasy interface: picker, exercises on a phone, French fallback, axe', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await open(page, '/reglages/langue', { mode: 'learn' });
  await page.getByRole('radio', { name: 'Malagasy' }).check();
  await expect(page.locator('html')).toHaveAttribute('lang', 'mg');
  await expect.poll(async () => (await api<{ settings: { language: string } }>('GET', '/settings')).settings.language).toBe('mg');
  await axe(page, 'language mg');
  await page.goto(new URL('/exercices', page.url()).href);
  await expect(page.getByRole('heading', { name: 'Fanazaran-tena', level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, 'exercises mg');
  await page.getByRole('link', { name: /Azo zaraina amin'ny 6/ }).click();
  await expect(page.locator('.theorem')).toContainText('Porofoy fa');
  await page.getByLabel('Alohan’ny toro-hevitra voalohany').fill('n^3 - n');
  await page.getByRole('button', { name: /Toro-hevitra manaraka/ }).click();
  await expect(page.locator('ol.hints')).toContainText('Soraty ho vokatra');
  await axe(page, 'exercise mg');
  // a screen that is not translated yet: French, never English
  await page.goto(new URL('/', page.url()).href);
  await expect(page.getByRole('heading', { level: 1 }).first()).toContainText('Inona no tianao hoporofoina');
  await page.goto(new URL('/aide', page.url()).href);
  await expect(page.locator('main')).toContainText('Madalean');
});
