// « Moteur de conjectures » (S-AW): the guided flow Explorer → Reconnaître → Énoncer → Attaquer → Journal on the demo
// server (no kernel: recognised sequences are computed by the catalogue, Lean is the demo stand-in, OEIS answers
// from the recorded fixture).
import { test, expect, type Page } from '@playwright/test';
import { open, api, axe } from './util';

type P = { id: string; title: string };
async function project(): Promise<string> {
  const r = await api<{ projects: P[] }>('GET', '/projects');
  return (r.projects.find((p) => /Exemples/.test(p.title)) ?? r.projects[0]!).id;
}
async function openIn(page: Page, path: string, pid: string) {
  await page.addInitScript((p) => { try { localStorage.setItem('madalean.project', p); } catch { /* */ } }, pid);
  await open(page, path, { mode: 'research' });
}
async function ask(page: Page, text: string) {
  await page.getByLabel('Votre question').fill(text);
  await page.getByRole('button', { name: 'Explorer', exact: true }).click();
  await expect(page).toHaveURL(/\/explorer\/x-[0-9a-f]{8}/);
}
const done = (page: Page) => expect(page.locator('#xp-state .chip').first()).toHaveText('fait', { timeout: 60_000 });

test('explore: sum of the first n odd numbers → table, a(n) = n², Lean accepted, kept as a conjecture', async ({ page }) => {
  const pid = await project();
  await openIn(page, '/conjectures', pid);
  await page.getByRole('link', { name: 'Explorer', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Explorer' })).toBeVisible();
  await page.getByRole('button', { name: 'la somme des n premiers nombres impairs' }).click();
  await expect(page.getByLabel('Votre question')).toHaveValue('la somme des n premiers nombres impairs');
  await page.getByLabel('Votre question').press('Enter');                       // Enter sends (D43)
  await expect(page).toHaveURL(/\/explorer\/x-/);
  await expect(page.getByText(/Reconnu : a\(n\) = somme des n premiers nombres impairs/)).toBeVisible();
  await done(page);
  await expect(page.locator('#xp-explore table tbody tr').nth(3)).toContainText('9');
  await expect(page.locator('#xp-explore svg[role=img]')).toHaveAttribute('aria-label', /Graphique de a/);
  const cand = page.locator('.cand[data-kind=polynomial]');
  await expect(cand).toContainText('vérifié jusqu\'à n = 59');
  await expect(cand).toContainText('accepté par Lean');
  await expect(cand.locator('.katex').first()).toBeVisible();
  await expect(page.locator('#xp-recognise')).toContainText('LMFDB');
  await cand.getByRole('button', { name: 'Garder comme conjecture ouverte' }).click();
  await expect(cand.getByRole('link', { name: 'Ouvrir la conjecture' })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#xp-journal')).toContainText('Gardée comme conjecture du projet');
  await cand.getByRole('link', { name: 'Ouvrir la conjecture' }).click();
  await expect(page).toHaveURL(/\/conjectures\/.+/);
  await expect(page.locator('.clist')).toContainText('Formule close — la somme des n premiers nombres impairs');
  await expect(page.locator('.timeline')).toContainText('exploration');
});

test('explore: given Catalan terms → OEIS A000108 (recorded answer) and candidates', async ({ page }) => {
  const pid = await project();
  await openIn(page, '/explorer', pid);
  await ask(page, '1, 1, 2, 5, 14, 42, 132, 429, 1430, 4862, 16796, 58786, 208012, 742900');
  await done(page);
  const link = page.getByRole('link', { name: /A000108/ });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('href', 'https://oeis.org/A000108');
  await expect(link).toHaveAttribute('rel', /noopener/);
  await expect(page.locator('#xp-recognise')).toContainText('14 termes identiques');
  await expect(page.locator('.cand[data-kind=holonomic]')).toContainText('pas démontré');
  await expect(page.locator('.cand[data-kind=oeis]').first()).toContainText('coïncide avec A000108 sur 14 termes');
  await expect(page.locator('.cand[data-kind=growth]')).toContainText('heuristique');
  // given terms: nothing to hunt with — said plainly, nothing breaks
  await page.locator('.cand[data-kind=holonomic]').getByRole('button', { name: 'Chercher un contre-exemple' }).click();
  await expect(page.locator('.cand[data-kind=holonomic]')).toContainText('Recherche impossible', { timeout: 30_000 });
});

test('explore: n² + n + 41 → « toujours premier » refuted by n = 40, kept with its counter-example', async ({ page }) => {
  const pid = await project();
  await openIn(page, '/explorer', pid);
  await ask(page, 'n^2 + n + 41 jusqu\'à 30');
  await done(page);
  const cand = page.locator('.cand[data-kind=all_prime]');
  await expect(cand).toContainText('vérifié jusqu\'à n = 30');
  await cand.getByRole('button', { name: 'Chercher un contre-exemple' }).click();
  await expect(cand.locator('.counter')).toContainText('n = 40', { timeout: 60_000 });
  await expect(cand.locator('.cstatus')).toHaveText('réfutée');
  await expect(cand.locator('.counter')).toContainText('recalculé dans un noyau neuf ✓');
  await expect(cand.getByRole('button', { name: 'Tenter la preuve' })).toHaveCount(0);
  await expect(page.locator('#xp-journal')).toContainText('Réfutée');
  const list = await api<{ conjectures: { title: string; status: string }[] }>('GET', `/conjectures?project=${pid}`);
  // the demo project already holds « Polynôme d'Euler » with the same Lean statement: the engine reuses it (duplicate)
  expect(list.conjectures.some((c) => /Toujours premier|Polynôme d'Euler/.test(c.title) && c.status === 'refuted')).toBe(true);
});

test('explore: an unrecognised question shows Calcul’s approval prompt and nothing runs', async ({ page }) => {
  const pid = await project();
  await openIn(page, '/explorer', pid);
  await ask(page, 'le nombre de carrés parfaits inférieurs à n');
  await expect(page.getByText(/Non reconnu : un modèle a écrit le code/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('button', { name: 'Approuver et exécuter' })).toBeVisible();
  await expect(page.getByText('Code écrit par le modèle : relisez-le, il ne s’exécute qu’après votre accord.')).toBeVisible();
  await expect(page.locator('#xp-explore .code-view')).toContainText('cj_rows_for');
  await expect(page.locator('#xp-explore .chip').first()).toHaveText('à approuver');
  await expect(page.locator('#xp-explore table')).toHaveCount(0);
  const id = page.url().split('/').pop()!;
  const v = await api<{ exploration: { table: unknown; steps: Record<string, { state: string }> }; cell: { may_run: boolean; origin: string } }>('GET', `/explorations/${id}`);
  expect(v.exploration.table).toBeNull();
  expect(v.cell.origin).toBe('assistant');
  expect(v.cell.may_run).toBe(false);
  // the server refuses to run it too
  const r = await fetch(`${process.env['MADALEAN_URL']}/api/explorations/${id}/run`, { method: 'POST' });
  expect(r.status).toBe(403);
});

for (const scheme of ['light', 'dark'] as const) {
  for (const width of [1280, 375] as const) {
    test(`explore: axe, no horizontal scroll (${scheme}, ${width}px)`, async ({ browser }) => {
      const ctx = await browser.newContext({ locale: 'fr-FR', colorScheme: scheme, viewport: { width, height: 800 }, hasTouch: width < 768, isMobile: width < 768 });
      const page = await ctx.newPage();
      const pid = await project();
      await openIn(page, '/explorer', pid);
      await axe(page, `explore start ${scheme} ${width}`);
      await ask(page, 'la somme des n premiers nombres impairs');
      await done(page);
      await expect(page.locator('.cand').first()).toBeVisible();
      await page.waitForTimeout(400);
      await axe(page, `explore results ${scheme} ${width}`);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over).toBeLessThanOrEqual(1);
      if (width < 768) {
        for (const el of await page.locator('.xp button:visible, .xp a.btn:visible').all()) {
          const b = await el.boundingBox();
          if (b) expect(b.height, await el.innerText()).toBeGreaterThanOrEqual(40);
        }
      }
      await ctx.close();
    });
  }
}
