// Article editor (S-R, docs/ARTICLE.md): visual mode = the LaTeX source decorated; one click to the source of the
// same text; autosave to the .tex files; insertion; compile to a real PDF; assistant suggestions accepted inline;
// options drawer; versions; Overleaf dialog; phone layout; axe. Also writes docs/screenshots/v2/article-*.png.
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, api, axe } from './util';

const OUT = new URL('../../docs/screenshots/v2/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
type P = { id: string; title: string };
type Proj = { files: { path: string; text: string; hash: string }[]; order: string[] };

async function project(title: RegExp): Promise<string> {
  const r = await api<{ projects: P[] }>('GET', '/projects');
  return r.projects.find((p) => title.test(p.title))!.id;
}
async function openArticle(page: Page, pid: string, prefs: Record<string, unknown> = {}) {
  await page.addInitScript(([p, pr]) => {
    try { localStorage.setItem('madalean.project', p as string); localStorage.setItem('madalean.article.prefs', JSON.stringify(pr)); } catch { /* */ }
  }, [pid, prefs] as const);
  await open(page, '/article', { mode: 'research' });
  await expect(page.locator('.cm-editor')).toBeVisible({ timeout: 30_000 });
}
const file = async (pid: string, path: string) => (await api<Proj>('GET', `/research/projects/${pid}/texproject`)).files.find((f) => f.path === path)!.text;

test('visual editing is the LaTeX source: maths, theorem boxes, chips, source switch, autosave', async ({ page }) => {
  const pid = await project(/Recherche/);
  await openArticle(page, pid, { preview: 'off' });
  const ed = page.locator('.cm-editor');
  // rendered maths (KaTeX), theorem heads with the Lean state, citation chips
  await expect(ed.locator('.cm-mathw .katex').first()).toBeVisible();
  await expect(ed.locator('.cm-thm-head').filter({ hasText: /Lemme/ }).first()).toBeVisible();
  await expect(ed.locator('.cm-lean-verified').first()).toBeVisible();
  await expect(ed.locator('.cm-lean-unverified').first()).toBeVisible();
  await expect(ed.locator('.cm-cite').first()).toBeVisible();
  await expect(ed.getByText('%% mdl:block')).toHaveCount(0);                     // markers hidden
  await axe(page, 'article visual');
  await page.screenshot({ path: `${OUT}article-visual-light.png` });
  // type in the visual mode → saved into the section file
  await ed.locator('.cm-line').filter({ hasText: 'Cet article' }).first().click();
  await expect(ed.locator('.cm-content')).toBeFocused();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nNouvelle phrase écrite en mode visuel avec $x^2$.');
  await expect(page.getByRole('status').filter({ hasText: 'Enregistré' })).toBeVisible({ timeout: 15_000 });
  await expect.poll(async () => file(pid, 'sections/01-introduction.tex'), { timeout: 15_000 }).toContain('Nouvelle phrase écrite en mode visuel avec $x^2$.');
  // switch to the source: same text, raw LaTeX visible
  await page.getByRole('radio', { name: 'Source LaTeX' }).check({ force: true });
  await expect(page.locator('.cm-editor.cm-source')).toBeVisible();
  await expect(ed.getByText('%% mdl:block b-').first()).toBeVisible();
  await expect(ed).toContainText('\\begin{lemma}');
  await page.screenshot({ path: `${OUT}article-source-light.png` });
  await page.getByRole('radio', { name: 'Visuel' }).check({ force: true });
  await expect(page.locator('.cm-editor.cm-visual')).toBeVisible();
  // insert a theorem from the menu
  await page.getByRole('button', { name: 'Insérer' }).click();
  await page.getByRole('menuitem', { name: 'Théorème' }).click();
  await page.keyboard.type('Tout entier est pair ou impair.');
  await expect.poll(async () => file(pid, 'sections/01-introduction.tex'), { timeout: 15_000 }).toMatch(/\\begin\{theorem\}\\label\{thm:\}\nTout entier est pair ou impair\./);
});

test('compile to PDF, diagnostics with a fix, options drawer, versions, Overleaf', async ({ page }) => {
  const pid = await project(/Recherche/);
  await openArticle(page, pid, { preview: 'right', autoCompile: false });
  await page.getByRole('button', { name: 'Compiler', exact: true }).first().click();
  await expect(page.locator('.preview canvas, .diag.error').first()).toBeVisible({ timeout: 120_000 });
  const diag = await page.locator('.diag.error').allInnerTexts();
  const proj = await api<Proj>('GET', `/research/projects/${pid}/texproject`);
  expect(diag, JSON.stringify(proj.files.map((f) => f.path))).toEqual([]);
  await expect(page.locator('.preview canvas').first()).toBeVisible({ timeout: 120_000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}article-preview-light.png` });
  await axe(page, 'article preview');
  // an unknown command → plain diagnostic with a one-click fix
  const path = 'sections/01-introduction.tex';
  const p = await api<Proj>('GET', `/research/projects/${pid}/texproject`);
  const f = p.files.find((x) => x.path === path)!;
  await api('POST', `/research/projects/${pid}/texproject/file`, { path, text: f.text + '\nVoir \\textcolr{red}{ceci}.\n', base: f.hash });
  await page.reload();
  await expect(page.locator('.cm-editor')).toBeVisible();
  await page.getByRole('button', { name: 'Compiler', exact: true }).first().click();
  await expect(page.getByText(/Vouliez-vous écrire \\textcolor/)).toBeVisible({ timeout: 120_000 });
  await page.getByRole('button', { name: /Remplacer par \\textcolor/ }).click();
  await expect.poll(async () => file(pid, path), { timeout: 15_000 }).toContain('\\textcolor{red}{ceci}');
  // advanced options: add a macro → preamble regenerated
  await page.getByRole('button', { name: 'Plus d’actions' }).click();
  await page.getByRole('menuitem', { name: 'Options avancées' }).click();
  await expect(page.getByRole('heading', { name: 'Options avancées' })).toBeVisible();
  await page.screenshot({ path: `${OUT}article-options-light.png` });
  await axe(page, 'article options');
  await page.getByRole('tab', { name: 'Macros' }).click();
  await page.getByLabel('Nom', { exact: true }).fill('eps');
  await page.getByLabel('Définition', { exact: true }).fill('\\varepsilon');
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await expect.poll(async () => file(pid, 'main.tex'), { timeout: 15_000 }).toContain('\\providecommand{\\eps}{\\varepsilon}');
  await page.getByRole('tab', { name: 'Paquets' }).click();
  await expect(page.getByText(/Fichiers TeX utilisés/)).toBeVisible();
  await page.getByRole('tab', { name: 'Personnalisation' }).click();
  await page.getByLabel('Taille du texte').selectOption('112');
  await page.keyboard.press('Escape');
  // versions
  await page.getByRole('button', { name: 'Plus d’actions' }).click();
  await page.getByRole('menuitem', { name: 'Versions' }).click();
  await page.getByLabel('Nom de la version').fill('avant relecture');
  await page.getByRole('button', { name: 'Créer une version' }).click();
  await expect(page.getByText('avant relecture')).toBeVisible();
  await axe(page, 'article versions');
  await page.keyboard.press('Escape');
  // Overleaf: export link and import field, detection is read-only
  await page.getByRole('button', { name: 'Plus d’actions' }).click();
  await page.getByRole('menuitem', { name: 'Overleaf…' }).click();
  await expect(page.getByRole('link', { name: 'Télécharger le projet (.zip)' })).toHaveAttribute('href', /export\?format=overleaf/);
  await axe(page, 'article overleaf');
  await page.screenshot({ path: `${OUT}article-overleaf-light.png` });
});

test('assistant: a selection becomes a suggestion, accepted inline; never a silent edit', async ({ page }) => {
  const pid = await project(/Recherche/);
  const path = 'sections/01-introduction.tex';
  const before = await file(pid, path);
  await openArticle(page, pid, { preview: 'off', mode: 'source' });
  const target = 'Cet article distingue';
  await page.locator('.cm-line', { hasText: target }).first().click();
  await page.evaluate((txt) => {
    const walker = document.createTreeWalker(document.querySelector('.cm-content')!, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const i = (n.textContent ?? '').indexOf(txt);
      if (i >= 0) { getSelection()!.setBaseAndExtent(n, i, n, i + txt.length); return; }
    }
  }, target);
  await page.getByRole('toolbar', { name: 'Assistant sur la sélection' }).getByRole('button', { name: 'Raccourcir' }).click();
  await expect(page.locator('.cm-sug').first()).toBeVisible({ timeout: 30_000 });
  expect(await file(pid, path)).toBe(before);                                           // suggestion only
  await page.screenshot({ path: `${OUT}article-suggestion-light.png` });
  await page.locator('.cm-sug-btn.ok').first().click();
  await expect(page.locator('.cm-sug')).toHaveCount(0);
  await expect.poll(async () => file(pid, path), { timeout: 15_000 }).not.toBe(before);
  const sugs = await api<{ suggestions: { state: string }[] }>('GET', `/research/projects/${pid}/texproject/suggestions?state=accepted`);
  expect(sugs.suggestions.length).toBeGreaterThan(0);
});

test('phone: visual mode only, one column, no horizontal scroll; dark theme', async ({ page }) => {
  const pid = await project(/Recherche/);
  await page.setViewportSize({ width: 360, height: 780 });
  await openArticle(page, pid, { preview: 'right' });
  await expect(page.getByRole('radio', { name: 'Source LaTeX' })).toHaveCount(0);
  await expect(page.locator('.preview')).toHaveCount(0);
  await expect(page.getByLabel('Plan de l’article')).toBeVisible();
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
  expect(sw).toBeLessThanOrEqual(w!);
  await axe(page, 'article phone');
  await page.screenshot({ path: `${OUT}article-phone-light.png` });
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload();
  await expect(page.locator('.cm-editor.cm-visual')).toBeVisible();
  await page.waitForTimeout(800);
  await axe(page, 'article dark');
  await page.screenshot({ path: `${OUT}article-visual-dark.png` });
});
