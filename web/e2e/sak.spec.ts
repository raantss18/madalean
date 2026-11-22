// S-AK (docs/UI.md §14, DECISIONS D43): the logo menu, the context switcher, the status panel, the project bar,
// outside click / Escape on every panel kind, Enter / Shift+Enter, autosave with reload persistence, axe.
import { test, expect, type Page } from '@playwright/test';
import { open, api, axe, URL as BASE } from './util';

interface DossierRow { id: string; title: string; status: string; project_id: string }
const dossiers = async () => (await api<{ dossiers: DossierRow[] }>('GET', '/dossiers')).dossiers;
const projects = async () => (await api<{ projects: { id: string; title: string; description: string }[] }>('GET', '/projects')).projects;

async function calculProject(): Promise<string> {
  for (const p of await projects()) if ((await api<{ cells: unknown[] }>('GET', `/calcul/${p.id}/docs/calcul`)).cells.length) return p.id;
  return (await projects())[0]!.id;
}

const logo = (page: Page) => page.getByRole('button', { name: 'Menu Madalean' });

test('logo menu: Accueil first, every destination, mode, second click goes home, Escape returns focus', async ({ page }) => {
  await open(page, '/glossaire', { mode: 'learn' });
  await expect(page.locator('.bottomnav, #rail, .menu-btn')).toHaveCount(0);             // no bottom bar, rail or ☰
  await logo(page).click();
  const menu = page.getByRole('menu', { name: 'Menu Madalean' });
  await expect(menu).toBeVisible();
  await expect(logo(page)).toHaveAttribute('aria-expanded', 'true');
  const items = menu.getByRole('menuitem');
  await expect(items.first()).toHaveText('Accueil');
  await expect(items.first()).toBeFocused();
  for (const name of ['Activité', 'Bibliothèque', 'Glossaire', 'Carnet', 'Aide', 'Réglages']) await expect(menu.getByRole('menuitem', { name, exact: true })).toBeVisible();
  // on a global screen the project bar is not shown: the menu holds the project's sections
  for (const name of ['Sources', 'Notes', 'Calcul', 'Publier']) await expect(menu.getByRole('menuitem', { name, exact: true })).toBeVisible();
  await expect(menu.getByRole('menuitemradio', { name: 'Recherche' })).toHaveAttribute('aria-checked', 'false');
  await axe(page, 'logo menu open');
  // arrows move, Escape closes and gives the focus back to the logo
  await page.keyboard.press('ArrowDown');
  await expect(items.nth(1)).toBeFocused();
  await page.keyboard.press('End');
  await expect(menu.getByRole('menuitemcheckbox')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await expect(logo(page)).toBeFocused();
  // mode switch from the menu
  await logo(page).click();
  await menu.getByRole('menuitemradio', { name: 'Recherche' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-mode', 'research');
  await menu.getByRole('menuitemradio', { name: 'Apprendre' }).click();
  // a destination
  await menu.getByRole('menuitem', { name: 'Bibliothèque' }).click();
  await expect(page).toHaveURL(/\/bibliotheque$/);
  await expect(menu).toBeHidden();
  // a second click on the logo (menu open) goes home
  await logo(page).click();
  await logo(page).click();
  await expect(page).toHaveURL(BASE() + '/');
  await expect(menu).toBeHidden();
  // on a project screen the bar is there and the menu no longer repeats the sections
  await expect(page.getByRole('navigation', { name: 'Sections du projet' })).toBeVisible();
  await logo(page).click();
  await expect(menu.getByRole('menuitem', { name: 'Sources', exact: true })).toHaveCount(0);
  // Ctrl+Shift+1 hides the bar (remembered) → the sections come back in the menu
  await page.keyboard.press('Escape');
  await page.keyboard.press('Control+Shift+Digit1');
  await expect(page.getByRole('navigation', { name: 'Sections du projet' })).toHaveCount(0);
  await logo(page).click();
  await expect(menu.getByRole('menuitem', { name: 'Sources', exact: true })).toBeVisible();
  await menu.getByRole('menuitemcheckbox', { name: /Barre du projet/ }).click();
  await expect(page.getByRole('navigation', { name: 'Sections du projet' })).toBeVisible();
});

test('outside click closes every panel kind and keeps the page usable', async ({ page }) => {
  const d = (await dossiers()).find((x) => x.status === 'proved')!;
  await open(page, `/d/${d.id}/preuve`, { mode: 'research' });
  const outside = async () => { await page.mouse.click(5, 600); };
  // logo menu
  await logo(page).click();
  await expect(page.getByRole('menu', { name: 'Menu Madalean' })).toBeVisible();
  await outside();
  await expect(page.getByRole('menu', { name: 'Menu Madalean' })).toBeHidden();
  // context switcher
  await page.locator('#context-switcher').click();
  await expect(page.getByRole('dialog', { name: 'Projets et dossiers' })).toBeVisible();
  await outside();
  await expect(page.getByRole('dialog', { name: 'Projets et dossiers' })).toBeHidden();
  // status panel
  await page.locator('#status-btn').click();
  await expect(page.locator('#status-panel')).toBeVisible();
  await outside();
  await expect(page.locator('#status-panel')).toBeHidden();
  // a « ⋯ » menu of the dossier
  await page.getByRole('button', { name: 'Autres actions' }).click();
  await expect(page.getByRole('menu')).toBeVisible();
  await outside();
  await expect(page.getByRole('menu')).toHaveCount(0);
  // Escape on each, focus back on its button
  await page.locator('#status-btn').click();
  await page.locator('#status-panel').getByRole('link').first().focus();
  await page.keyboard.press('Escape');
  await expect(page.locator('#status-panel')).toBeHidden();
  await expect(page.locator('#status-btn')).toBeFocused();
  // a click on the button itself toggles (not « outside »)
  await page.locator('#context-switcher').click();
  await page.locator('#context-switcher').click();
  await expect(page.getByRole('dialog', { name: 'Projets et dossiers' })).toBeHidden();
});

test('context switcher: full names, projects beside their dossiers, opens a dossier', async ({ page }) => {
  const all = await dossiers();
  const ps = await projects();
  const p = ps.find((x) => all.some((d) => d.project_id === x.id))!;
  const target = all.find((d) => d.project_id === p.id)!;
  await open(page, '/', { mode: 'research' });
  const btn = page.locator('#context-switcher');
  await btn.click();
  const panel = page.getByRole('dialog', { name: 'Projets et dossiers' });
  for (const x of ps) await expect(panel.getByRole('button', { name: x.title, exact: true })).toBeVisible();
  await panel.getByRole('button', { name: p.title, exact: true }).click();
  await expect(panel.getByRole('heading', { name: `Dossiers de « ${p.title} »` })).toBeVisible();
  await expect(btn).toContainText(p.title);
  await axe(page, 'context switcher open');
  await panel.getByRole('link', { name: new RegExp(target.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).first().click();
  await expect(page).toHaveURL(new RegExp(`/d/${target.id}`));
  await expect(panel).toBeHidden();
  // in a dossier the button reads « Projet › Dossier » in full, with the whole text as tooltip
  await expect(btn).toContainText(target.title);
  await expect(btn).toHaveAttribute('title', `${p.title} › ${target.title}`);
});

test('status panel: mode, resources, tokens and cost; polled only while open', async ({ page }) => {
  const calls: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/usage')) calls.push(r.url()); });
  await open(page, '/', { mode: 'research' });
  await page.waitForTimeout(3500);
  expect(calls, 'nothing polled while closed').toHaveLength(0);
  await page.locator('#status-btn').click();
  const panel = page.locator('#status-panel');
  await expect(panel.getByRole('heading', { name: 'Qui reçoit quoi' })).toBeVisible();
  await expect(panel.getByRole('heading', { name: 'Ordinateur hôte' })).toBeVisible();
  await expect(panel.getByText('Processeur')).toBeVisible();
  await expect(panel.getByText('Mémoire', { exact: true })).toBeVisible();
  await expect(panel.getByRole('row', { name: /Aujourd’hui/ })).toBeVisible();
  await expect(panel.getByRole('row', { name: /Ce mois-ci/ })).toBeVisible();
  await expect(panel.getByRole('link', { name: 'Changer de modèles ou de mode' })).toHaveAttribute('href', '/reglages/modeles');
  await page.waitForTimeout(3300);
  expect(calls.length).toBeGreaterThanOrEqual(2);                                       // sampled while open
  await axe(page, 'status panel open');
  await page.keyboard.press('Escape');
  const n = calls.length;
  await page.waitForTimeout(3500);
  expect(calls.length, 'polling stops when closed').toBe(n);
});

test('Enter sends, Shift+Enter is a new line: new problem, follow-up request', async ({ page }) => {
  await open(page, '/', { mode: 'research' });
  const ed = page.locator('#statement-input');
  await ed.click();
  await page.keyboard.type('Ligne un');
  await page.keyboard.press('Shift+Enter');
  await page.keyboard.type('ligne deux : pour tout entier $n$, $n+n$ est pair.');
  await expect(page.locator('.cm-line')).toHaveCount(2);
  await expect(page.getByText('Entrée pour envoyer · Maj+Entrée pour aller à la ligne').first()).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/d\/[^/]+\/lean/);
  const id = new URL(page.url()).pathname.split('/')[2]!;
  // follow-up request in the thread: Shift+Enter keeps writing, Enter sends
  const box = page.locator(`#follow-${id}`);
  await box.click();
  await box.pressSequentially('Première ligne');
  await page.keyboard.press('Shift+Enter');
  await box.pressSequentially('seconde ligne');
  await expect(box).toHaveValue('Première ligne\nseconde ligne');
  const sent = page.waitForRequest((r) => r.url().includes(`/api/dossiers/${id}/`) && r.method() === 'POST');
  await page.keyboard.press('Enter');
  await sent;
  await expect(box).toHaveValue('');
});

test('Calcul code cell: Enter runs, Shift+Enter new line with indentation, Tab indents; autosaved and kept after reload', async ({ page }) => {
  const pid = await calculProject();
  await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
  await open(page, '/calcul', { mode: 'research' });
  await page.getByRole('button', { name: 'Ajouter une cellule' }).click();
  const cell = page.locator('li.cell').last();
  const box = cell.getByRole('textbox', { name: /Code de la cellule/ });
  await box.click();
  await box.pressSequentially('for i in range(3):');
  await page.keyboard.press('Shift+Enter');
  await box.pressSequentially('x = i');
  await expect(box).toHaveValue('for i in range(3):\n    x = i');
  await page.keyboard.press('Shift+Enter');
  await page.keyboard.press('Shift+Tab');
  await box.pressSequentially('y = 2');
  await expect(box).toHaveValue('for i in range(3):\n    x = i\ny = 2');
  await expect(cell.getByText('Entrée pour exécuter · Maj+Entrée pour aller à la ligne · Tab pour indenter')).toBeVisible();
  // autosave while typing (no blur), then a reload shows the same code
  await expect(page.locator('.save-state[data-state="saved"]').first()).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(1500);
  await page.reload();
  await expect(page.locator('li.cell').last().getByRole('textbox', { name: /Code de la cellule/ })).toHaveValue('for i in range(3):\n    x = i\ny = 2');
  // Enter runs the cell
  const box2 = page.locator('li.cell').last().getByRole('textbox', { name: /Code de la cellule/ });
  await box2.click();
  const run = page.waitForRequest((r) => /\/calcul\/.*\/run$/.test(r.url()) && r.method() === 'POST');
  await page.keyboard.press('End');
  await page.keyboard.press('Enter');
  await run;
});

test('autosave: dossier title and statement, project description, profile — kept after reload', async ({ page }) => {
  const d = (await dossiers()).find((x) => x.status !== 'proved')!;
  await open(page, `/d/${d.id}/enonce`, { mode: 'research' });
  // title in place: no dialog, no « Enregistrer »
  await page.getByRole('heading', { level: 1 }).getByRole('button').click();
  const ti = page.locator('#dossier-title');
  await ti.fill('Titre changé automatiquement');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Titre changé automatiquement');
  // statement: edited, saved while typing; « Retraduire » is an action, « Terminer » closes
  await page.getByRole('button', { name: 'Modifier' }).first().click();
  const st = page.locator('.cm-content').first();
  await st.click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type(' Ajout sauvé.');
  await expect(page.locator('.save-state[data-state="saved"]').first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('button', { name: 'Enregistrer seulement' })).toHaveCount(0);
  await page.waitForTimeout(1500);
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Titre changé automatiquement');
  await expect(page.locator('.theorem').first()).toContainText('Ajout sauvé.');
  const after = (await api<{ dossier: { title: string; problem: string } }>('GET', `/dossiers/${d.id}`)).dossier;
  expect(after.title).toBe('Titre changé automatiquement');
  expect(after.problem).toContain('Ajout sauvé.');
  // project description on the project page
  await page.goto(BASE() + '/projet');
  const desc = page.getByRole('textbox', { name: 'Description' });
  await desc.fill('Description écrite sans bouton.');
  await expect(page.locator('.save-state').first()).toHaveAttribute('data-state', /saving|dirty|saved/);
  await page.waitForTimeout(2000);
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Description' })).toHaveValue('Description écrite sans bouton.');
  // profile setting: no « Enregistrer » button any more
  await page.goto(BASE() + '/reglages/profil');
  const prof = page.getByRole('textbox', { name: 'Votre profil' }).first();
  await prof.fill('Je prépare l’agrégation.');
  await expect(page.getByRole('button', { name: 'Enregistrer' })).toHaveCount(0);
  await page.waitForTimeout(2000);
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Votre profil' }).first()).toHaveValue('Je prépare l’agrégation.');
});

test('autosave: a failing save says so and retries; nothing is lost', async ({ page }) => {
  await open(page, '/projet', { mode: 'research' });
  let fail = true;
  await page.route('**/api/projects/*', async (route) => {
    if (route.request().method() === 'PATCH' && fail) { await route.abort('failed'); return; }
    await route.continue();
  });
  const desc = page.getByRole('textbox', { name: 'Description' });
  await desc.fill('Texte qui doit survivre à une panne.');
  await expect(page.locator('.save-state[data-state="error"]')).toContainText('Non enregistré — réessai', { timeout: 10_000 });
  fail = false;
  await expect(page.locator('.save-state[data-state="error"]')).toHaveCount(0, { timeout: 15_000 });
  const p = (await projects()).find((x) => x.description === 'Texte qui doit survivre à une panne.');
  expect(p).toBeTruthy();
});

for (const scheme of ['light', 'dark'] as const) {
  test(`axe with each top-bar panel open, desktop and tablet (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    const d = (await dossiers()).find((x) => x.status === 'proved')!;
    for (const width of [1440, 820]) {
      await page.setViewportSize({ width, height: 1000 });
      await open(page, `/d/${d.id}/preuve`, { mode: 'learn' });
      await axe(page, `dossier ${width} ${scheme}`);
      await logo(page).click();
      await axe(page, `logo menu ${width} ${scheme}`);
      await page.keyboard.press('Escape');
      await page.locator('#context-switcher').click();
      await axe(page, `switcher ${width} ${scheme}`);
      await page.keyboard.press('Escape');
      await page.locator('#status-btn').click();
      await expect(page.locator('#status-panel').getByText('Processeur')).toBeVisible();
      await axe(page, `status ${width} ${scheme}`);
      await page.keyboard.press('Escape');
      await page.goto(BASE() + '/projet');
      await axe(page, `project page ${width} ${scheme}`);
    }
  });

  test(`phone (${scheme}): no bottom bar, logo menu as a sheet, project bar scrolls, axe`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, colorScheme: scheme, locale: 'fr-FR' });
    const page = await ctx.newPage();
    await open(page, '/', { mode: 'learn' });
    await expect(page.locator('.bottomnav')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.getByRole('button', { name: /^Chercher/ })).toBeVisible();          // search reachable on phones
    await axe(page, `phone home ${scheme}`);
    await logo(page).click();
    const sheet = page.getByRole('menu', { name: 'Menu Madalean' });
    const box = (await sheet.boundingBox())!;
    expect(box.height).toBeGreaterThan(500);                                                // a full-height sheet
    for (const el of await sheet.getByRole('menuitem').all()) expect((await el.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await axe(page, `phone logo menu ${scheme}`);
    await page.mouse.click(380, 700);                                                       // the scrim
    await expect(sheet).toBeHidden();
    await page.locator('#status-btn').click();
    await expect(page.locator('#status-panel')).toBeVisible();
    await axe(page, `phone status panel ${scheme}`);
    await page.keyboard.press('Escape');
    await page.locator('#context-switcher').click();
    await axe(page, `phone context switcher ${scheme}`);
    await ctx.close();
  });
}
