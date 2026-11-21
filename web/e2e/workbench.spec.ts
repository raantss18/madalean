import { test, expect, type Page } from '@playwright/test';
import { open, api, axe } from './util';

// Session S-M: glossary, library, Calcul, Claude spending caps (demo server: fake models, seeded Calcul sheet).

async function noHorizontalScroll(page: Page, label: string) {
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, `horizontal scroll on ${label}`).toBeLessThanOrEqual(w);
}

test('glossary: search, categories, levels, entry details, related jump, A–Z index', async ({ page }) => {
  await open(page, '/glossaire', { mode: 'research' });
  await axe(page, 'glossary');
  await page.getByRole('searchbox', { name: 'Chercher un mot' }).fill('obtain');
  const entry = page.locator('li.entry', { has: page.locator('code.key', { hasText: /^obtain$/ }) });
  await entry.locator('button.term').click();
  await expect(entry.getByText('Forme en Lean')).toBeVisible();
  await expect(entry.locator('pre.code')).toBeVisible();
  await axe(page, 'glossary entry open');
  // a related entry opens and is scrolled to, the filters are cleared if needed
  const rel = entry.locator('ul.related button').first();
  const target = (await rel.innerText()).trim();
  await rel.click();
  await expect(page.locator('li.entry.open code.key').first()).toHaveText(target);
  // category + level filters
  await page.getByRole('searchbox', { name: 'Chercher un mot' }).fill('');
  await page.getByRole('navigation', { name: 'Catégorie' }).getByRole('button', { name: /^Tactiques/ }).click();
  await page.locator('.levels label', { hasText: 'Avancé' }).click();
  await expect(page.getByRole('radio', { name: 'Avancé' })).toBeChecked();
  const n = await page.locator('li.entry').count();
  expect(n).toBeGreaterThan(0);
  for (const chip of await page.locator('li.entry .tags .chip').allInnerTexts()) expect(chip).toBe('Tactiques');
  // A–Z index: a letter moves focus to its group
  await page.locator('.levels label', { hasText: 'Tous niveaux' }).click();
  await page.getByRole('button', { name: 'Aller à la lettre S' }).click();
  await expect(page.locator('#letter-S')).toBeFocused();
  // the « in my dossiers » link finds the demo dossiers using Even
  await page.getByRole('navigation', { name: 'Catégorie' }).getByRole('button', { name: /^Toutes/ }).click();
  await page.getByRole('searchbox', { name: 'Chercher un mot' }).fill('Even');
  const ev = page.locator('li.entry', { has: page.locator('code.key', { hasText: /^Even$/ }) });
  await ev.locator('button.term').click();
  await ev.getByRole('button', { name: 'Dans mes dossiers' }).click();
  await expect(ev.locator('.uses-list a').first()).toBeVisible();
});

test('library: groups, card/table views, detail with domain and tags, export links', async ({ page }) => {
  await open(page, '/bibliotheque', { mode: 'research' });
  await expect(page.locator('.card').first()).toBeVisible();
  await axe(page, 'library cards');
  await page.getByRole('radio', { name: 'Tableau' }).check({ force: true });
  await expect(page.locator('table.tbl')).toBeVisible();
  await axe(page, 'library table');
  await page.locator('table.tbl .link-btn').first().click();
  const detail = page.locator('aside.detail');
  await expect(detail.getByRole('heading', { level: 2 })).toBeFocused();
  await detail.getByLabel('Domaine').selectOption('algebra');
  await expect.poll(async () => (await api<{ entries: { domain: string; domain_manual: boolean }[] }>('GET', '/library/catalog')).entries.some((e) => e.domain === 'algebra' && e.domain_manual)).toBe(true);
  await detail.getByLabel('Ajouter', { exact: true }).fill('parité');
  await detail.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await expect(detail.locator('ul.tags li')).toContainText('parité');
  await page.getByLabel('Ranger par').selectOption('tag');
  await expect(page.getByRole('heading', { name: /parité/ })).toBeVisible();
  await axe(page, 'library detail');
  const href = await page.getByRole('link', { name: 'Exporter (Markdown)' }).getAttribute('href');
  const md = await (await fetch(process.env['MADALEAN_URL'] + href!)).text();
  expect(md).toContain('```lean');
  await detail.getByLabel('Domaine').selectOption('');                     // back to automatic
});

test('calcul: your cells run directly, assistant cells wait for approval, results become notes', async ({ page }) => {
  // the demo's seeded worksheet belongs to the first demo project: make it the current project on this device
  const ps = (await api<{ projects: { id: string }[] }>('GET', '/projects')).projects;
  let pid = ps[0]!.id;
  for (const p of ps) if ((await api<{ sheet: { cells: unknown[] } }>('GET', `/calcul/${p.id}`)).sheet.cells.length) { pid = p.id; break; }
  await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
  await open(page, '/calcul', { mode: 'research' });
  await expect(page.getByRole('heading', { name: 'Calcul', level: 1 })).toBeVisible();
  await expect(page.locator('.tex .katex').first()).toBeVisible();            // seeded LaTeX output
  await expect(page.locator('img.plot').first()).toBeVisible();                // seeded SVG plot (served sanitised)
  await axe(page, 'calcul');
  // the seeded assistant cell: no run button, only « approve »
  const pending = page.locator('li.cell.pending').first();
  await expect(pending.getByRole('button', { name: 'Approuver ce code' })).toBeVisible();
  await expect(pending.getByRole('button', { name: 'Exécuter' })).toHaveCount(0);
  await pending.getByRole('button', { name: 'Approuver ce code' }).click();
  await expect(page.locator('li.cell.pending')).toHaveCount(0);
  // ask the assistant: a new cell to review appears
  await page.getByLabel('Calcul demandé à l’assistant').fill('les nombres premiers jumeaux');
  await page.getByRole('button', { name: 'Écrire la cellule' }).click();
  await expect(page.locator('li.cell.pending')).toHaveCount(1);
  // a result → note
  const first = page.locator('li.cell').first();
  await first.getByRole('button', { name: '→ Note' }).click();
  const dlg = page.getByRole('dialog', { name: 'Enregistrer dans une note' });
  await dlg.getByLabel('Titre (facultatif)').fill('Nombre de Fermat F5');
  await dlg.getByRole('button', { name: 'Créer la note' }).click();
  await expect(page.getByText('Note créée.')).toBeVisible();
  // a result → Lean dossier
  await first.getByRole('button', { name: '→ Dossier Lean' }).click();
  const d2 = page.getByRole('dialog', { name: 'Ouvrir un dossier Lean' });
  await d2.getByLabel('Énoncé à prouver').fill('Le nombre 2^32 + 1 n’est pas premier.');
  await d2.getByRole('button', { name: 'Créer le dossier' }).click();
  await expect(page.getByText('Dossier créé.')).toBeVisible();
  const ds = await api<{ dossiers: { title: string; problem?: string }[] }>('GET', '/dossiers');
  expect(JSON.stringify(ds)).toContain('2^32 + 1');
});

test('Claude caps: per-proof and monthly caps saved, spend shown, out-of-range refused', async ({ page }) => {
  await open(page, '/reglages/modeles', { mode: 'research' });
  const sec = page.getByRole('region', { name: 'Claude en renfort payant' });
  await expect(sec.getByRole('meter')).toBeVisible();
  await sec.getByLabel('Plafond par mois').fill('5');
  await sec.getByLabel('Plafond par mois').blur();
  await expect.poll(async () => (await api<{ settings: Record<string, number> }>('GET', '/settings')).settings['claude_cap_month_usd']).toBe(5);
  await sec.getByLabel('Plafond par preuve').fill('0.5');
  await sec.getByLabel('Plafond par preuve').blur();
  await expect.poll(async () => (await api<{ cap_proof: number }>('GET', '/models/spend')).cap_proof).toBe(0.5);
  await expect(sec).toContainText('5,00');
  await sec.getByLabel('Plafond par mois').fill('5000');
  await sec.getByLabel('Plafond par mois').blur();
  await expect(page.getByText(/Valeur entre 0 et 1000/)).toBeVisible();
  expect((await api<{ settings: Record<string, number> }>('GET', '/settings')).settings['claude_cap_month_usd']).toBe(5);
  await axe(page, 'settings claude caps');
  await api('PATCH', '/settings', { claude_cap_month_usd: 20, claude_cap_proof_usd: 1 });
});

for (const [w, h] of [[360, 780], [820, 1180]] as const) {
  test(`S-M screens at ${w}px: no horizontal scroll, axe clean`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fr-FR' });
    const page = await ctx.newPage();
    for (const path of ['/glossaire', '/bibliotheque', '/calcul', '/reglages/modeles']) {
      await open(page, path);
      await page.waitForTimeout(400);
      await noHorizontalScroll(page, `${path} ${w}`);
      await axe(page, `${path} ${w}`);
    }
    await ctx.close();
  });
}
