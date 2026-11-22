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

test('calcul notebook: ordered cells, exact/approx, NL cell to review, keyboard, connections', async ({ page }) => {
  // the demo's seeded notebook belongs to the first demo project: make it the current project on this device
  const ps = (await api<{ projects: { id: string }[] }>('GET', '/projects')).projects;
  let pid = ps[0]!.id;
  for (const p of ps) if ((await api<{ cells: unknown[] }>('GET', `/calcul/${p.id}/docs/calcul`)).cells.length) { pid = p.id; break; }
  await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
  await open(page, '/calcul', { mode: 'research' });
  await expect(page.getByRole('heading', { name: 'Calcul', level: 1 })).toBeVisible();
  await expect(page.locator('.tex .katex').first()).toBeVisible();            // seeded LaTeX output
  await expect(page.locator('img.plot').first()).toBeVisible();                // seeded SVG plot (served sanitised)
  await expect(page.locator('li.cell.figure svg').first()).toBeVisible();      // interactive figure cell
  await expect(page.getByRole('link', { name: 'Ouvrir dans JupyterLab' })).toHaveAttribute('href', /\/jupyter\/lab\/tree\/calcul\//);
  await axe(page, 'calcul notebook');
  await page.screenshot({ path: '../docs/screenshots/v2/calcul-notebook.png', fullPage: true });
  // exact ↔ approximate
  const approx = page.getByRole('group', { name: 'Exact / Approché' }).first();
  await approx.getByRole('button', { name: 'Approché' }).click();
  await expect(page.getByText('≈ 4.44288293815837')).toBeVisible();
  await approx.getByRole('button', { name: 'Exact' }).click();
  // the seeded model cell: approve only, no run button
  const pending = page.locator('li.cell.pending').first();
  await expect(pending.getByRole('button', { name: 'Approuver et exécuter' })).toBeVisible();
  await expect(pending.getByRole('button', { name: /^Exécuter/ })).toHaveCount(0);
  // S-AB: one « + » under the last cell; the new cell recognises a request in words (chip « Code / Demande »)
  const before = await page.locator('li.cell').count();
  await expect(page.getByRole('button', { name: 'Ajouter une cellule' })).toHaveCount(1);
  await page.getByRole('button', { name: 'Ajouter une cellule' }).click();
  await expect(page.locator('li.cell')).toHaveCount(before + 1);
  let ask = page.locator('li.cell').last();
  await ask.getByRole('textbox', { name: /Code de la cellule/ }).fill('graphe de Petersen et son nombre chromatique');
  const chip = ask.getByRole('group', { name: 'Ce que vous avez tapé' });
  await expect(chip.getByRole('button', { name: 'Demande' })).toHaveAttribute('aria-pressed', 'true');
  await chip.getByRole('button', { name: 'Code' }).click();                 // a wrong guess is fixed in one click…
  await expect(ask.getByRole('button', { name: /^Exécuter/ })).toBeVisible();
  await chip.getByRole('button', { name: 'Demande' }).click();              // …and back
  await ask.getByRole('button', { name: 'Écrire le code' }).click();
  ask = page.locator('li.cell.ask').last();
  await expect(ask.getByRole('textbox', { name: /Code de la cellule/ })).toHaveValue(/PetersenGraph/);
  await expect(ask).toHaveClass(/pending/);
  // « Réécrire » right below the request, « Approuver et exécuter » right below the code; nothing else in the head
  await expect(ask.getByRole('button', { name: 'Réécrire' })).toBeVisible();
  await expect(ask.locator('.cell-head').getByRole('button')).toHaveCount(1);           // only « ⋯ »
  const rw = ask.getByRole('button', { name: 'Réécrire' });
  await rw.click();
  await rw.click();                                                         // rewriting again at once: never « busy »
  await expect(page.getByText(/travaille/)).toHaveCount(0);
  await expect(ask.getByRole('textbox', { name: /Code de la cellule/ })).toHaveValue(/PetersenGraph/);
  await axe(page, 'calcul ask cell');
  // « Expliquer ligne par ligne » from the cell menu
  const firstCode = page.locator('li.cell.code').first();
  await firstCode.getByRole('button', { name: /Plus d’actions/ }).click();
  await page.getByRole('menuitem', { name: 'Expliquer ligne par ligne' }).click();
  await expect(firstCode.getByRole('region', { name: 'Explication ligne par ligne' }).locator('li').first()).toContainText('Cette ligne calcule');
  await axe(page, 'calcul line explanations');
  await firstCode.getByRole('button', { name: 'Fermer' }).click();
  // S-AJ: « Expliquer les étapes du calcul » — facts marked « vérifié par Sage », the derivation ends on the result
  await firstCode.getByRole('button', { name: /Plus d’actions/ }).click();
  await page.getByRole('menuitem', { name: 'Expliquer les étapes du calcul' }).click();
  const steps = firstCode.getByRole('region', { name: 'Étapes du calcul' });
  await expect(steps.locator('li.fact')).toHaveCount(4);
  await expect(steps.locator('.mark.verified')).toHaveCount(3);
  await expect(steps.locator('.mark.verified').first()).toContainText('vérifié par Sage');
  await expect(steps.locator('.steps-md ol li')).toHaveCount(4);
  await expect(steps.locator('.steps-md .katex').first()).toBeVisible();
  await expect(steps.getByRole('note')).toHaveCount(0);                     // verified: no « sans vérification »
  await axe(page, 'calcul steps explanation');
  await page.setViewportSize({ width: 375, height: 800 });
  await noHorizontalScroll(page, 'calcul steps (phone)');
  await page.setViewportSize({ width: 1440, height: 900 });
  await steps.getByRole('button', { name: 'Replier les étapes' }).click();
  await expect(steps.locator('li.fact')).toHaveCount(0);
  await steps.getByRole('button', { name: 'Insérer dans l’article' }).click();
  const artDlg = page.getByRole('dialog', { name: 'Insérer dans l’article' });
  await expect(artDlg.getByLabel('Énoncé')).toHaveValue(/641 \\cdot 6700417/);
  await artDlg.getByRole('button', { name: '✕' }).click();
  await steps.getByRole('button', { name: 'Fermer' }).click();
  // a cell without a successful result has no such entry (the model's pending cell)
  await page.locator('li.cell.pending').first().getByRole('button', { name: /Plus d’actions/ }).click();
  await expect(page.getByRole('menuitem', { name: 'Expliquer les étapes du calcul' })).toHaveCount(0);
  await page.keyboard.press('Escape');
  // keyboard: Esc (command mode), B inserts below, D D deletes
  await ask.getByRole('textbox', { name: /Code de la cellule/ }).press('Escape');
  await expect(ask).toBeFocused();
  await page.keyboard.press('b');
  await expect(page.locator('li.cell')).toHaveCount(before + 2);
  const added = page.locator('li.cell').last();
  await added.focus();
  await page.keyboard.press('d');
  await page.keyboard.press('d');
  await expect(page.locator('li.cell')).toHaveCount(before + 1);
  // a result → note, → Lean dossier (statement prefilled from the result)
  const first = page.locator('li.cell.code').first();
  await first.getByRole('button', { name: /Plus d’actions/ }).click();
  await page.getByRole('menuitem', { name: 'Ajouter à une note' }).click();
  let dlg = page.getByRole('dialog', { name: 'Ajouter à une note' });
  await dlg.getByLabel('Titre (facultatif)').fill('Nombre de Fermat F5');
  await dlg.getByRole('button', { name: 'Envoyer' }).click();
  await expect(page.getByText('C’est fait.').first()).toBeVisible();
  await first.getByRole('button', { name: /Plus d’actions/ }).click();
  await page.getByRole('menuitem', { name: 'Créer un dossier Lean' }).click();
  dlg = page.getByRole('dialog', { name: 'Créer un dossier Lean' });
  await expect(dlg.getByLabel('Énoncé')).toHaveValue(/641/);
  await dlg.getByLabel('Énoncé').fill('Le nombre 2^32 + 1 n’est pas premier.');
  await dlg.getByRole('button', { name: 'Envoyer' }).click();
  await expect.poll(async () => JSON.stringify(await api('GET', '/dossiers'))).toContain('2^32 + 1');
});

test('calcul: a request is recognized, « Réécrire » gives the same code, « Autre version » in the menu (S-AG)', async ({ page }) => {
  const ps = (await api<{ projects: { id: string }[] }>('GET', '/projects')).projects;
  let pid = ps[0]!.id;
  for (const p of ps) if ((await api<{ cells: unknown[] }>('GET', `/calcul/${p.id}/docs/calcul`)).cells.length) { pid = p.id; break; }
  await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
  await open(page, '/calcul', { mode: 'research' });
  await expect(page.getByRole('heading', { name: 'Calcul', level: 1 })).toBeVisible();
  await expect(page.locator('li.cell').first()).toBeVisible();
  const n0 = await page.locator('li.cell').count();
  await page.getByRole('button', { name: 'Ajouter une cellule' }).click();
  await expect(page.locator('li.cell')).toHaveCount(n0 + 1);
  let ask = page.locator('li.cell').nth(n0);
  await ask.getByRole('textbox', { name: /Code de la cellule/ }).fill('factorise x^5+4x-1 dans F_{5^3}[x]');
  await expect(ask.getByRole('group', { name: 'Ce que vous avez tapé' }).getByRole('button', { name: 'Demande' })).toHaveAttribute('aria-pressed', 'true');
  await ask.getByRole('button', { name: 'Écrire le code' }).click();
  ask = page.locator('li.cell.ask').last();
  const code = ask.getByRole('textbox', { name: /Code de la cellule/ });
  await expect(code).toHaveValue('F125.<a> = GF(5^3)\nR.<x> = PolynomialRing(F125)\nf = x^5 + 4*x - 1\nf.factor()');
  await expect(ask.getByText('Reconnu : corps fini F₁₂₅ = F_{5³}', { exact: false })).toBeVisible();
  await expect(ask.getByText(/construction vérifiée/)).toBeVisible();
  // the same request written another way, « Réécrire »: byte-identical code
  await ask.getByRole('textbox', { name: /Demande de la cellule/ }).fill('factorise x^5 + 4x - 1 dans GF(125)[x]');
  await ask.getByRole('button', { name: 'Réécrire' }).click();
  await expect(code).toHaveValue('F125.<a> = GF(5^3)\nR.<x> = PolynomialRing(F125)\nf = x^5 + 4*x - 1\nf.factor()');
  // « Autre version » is a small item of the cell's menu, not a new button
  await expect(ask.locator('.cell-head').getByRole('button')).toHaveCount(1);
  await ask.getByRole('button', { name: /Plus d’actions/ }).click();
  await expect(page.getByRole('menuitem', { name: 'Autre version' })).toBeVisible();
  await page.keyboard.press('Escape');
  await axe(page, 'calcul recognized request');
  // a field that does not exist: said under the request, no code
  const n = await page.locator('li.cell').count();
  await page.getByRole('button', { name: 'Ajouter une cellule' }).click();
  await expect(page.locator('li.cell')).toHaveCount(n + 1);
  let bad = page.locator('li.cell').nth(n);
  await bad.getByRole('textbox', { name: /Code de la cellule/ }).fill('factorise x^2+1 dans F_12[x]');
  await bad.getByRole('button', { name: 'Écrire le code' }).click();
  bad = page.locator('li.cell.ask').last();
  await expect(bad.getByRole('alert')).toContainText("puissance d'un nombre premier");
  await expect(bad.getByRole('textbox', { name: /Code de la cellule/ })).toHaveCount(0);
});

test('calcul notebook on a phone and in dark mode: single column, big run buttons, axe clean', async ({ browser }) => {
  const ps = (await api<{ projects: { id: string }[] }>('GET', '/projects')).projects;
  let pid = ps[0]!.id;
  for (const p of ps) if ((await api<{ cells: unknown[] }>('GET', `/calcul/${p.id}/docs/calcul`)).cells.length) { pid = p.id; break; }
  for (const [w, h, scheme] of [[360, 780, 'light'], [360, 780, 'dark'], [412, 915, 'light'], [768, 1024, 'light'], [768, 1024, 'dark'],
    [1440, 900, 'light'], [1440, 900, 'dark']] as const) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, locale: 'fr-FR' });
    const page = await ctx.newPage();
    await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
    await open(page, '/calcul', { mode: 'research' });
    await expect(page.locator('.tex .katex').first()).toBeVisible();
    await expect(page.locator('li.cell.figure svg').first()).toBeVisible();
    const [sw, iw] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    expect(sw).toBeLessThanOrEqual(iw);
    if (w < 600) {
      const box = await page.locator('li.cell.code').first().getByRole('button', { name: /^Exécuter/ }).boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    await axe(page, `calcul ${w}px ${scheme}`);
    // long formulas scroll inside their box, never clipped (S-AB: the LaTeX result cut on a phone)
    const clipped = await page.evaluate(() => [...document.querySelectorAll('.output .tex')].filter((el) => {
      const cs = getComputedStyle(el);
      return el.scrollWidth > el.clientWidth + 1 && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll';
    }).length);
    expect(clipped).toBe(0);
    await page.screenshot({ path: `../docs/screenshots/v2/calcul-${w}-${scheme}.png`, fullPage: true });
    await ctx.close();
  }
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
