import { test, expect, type Page } from '@playwright/test';
import { open, api, axe, URL as BASE } from './util';

type P = { id: string; title: string };
async function project(title: RegExp): Promise<string> {
  const r = await api<{ projects: P[] }>('GET', '/projects');
  return r.projects.find((p) => title.test(p.title))!.id;
}
async function openIn(page: Page, path: string, pid: string, mode: 'learn' | 'research' = 'research') {
  await page.addInitScript((p) => { try { localStorage.setItem('madalean.project', p); } catch { /* */ } }, pid);
  await open(page, path, { mode });
}

test('sources: library, add by paste, literature search, grounded answer with citations that open the passage, highlight', async ({ page }) => {
  const pid = await project(/Recherche/);
  await openIn(page, '/sources', pid);
  await expect(page.getByRole('link', { name: /A note on parity/ })).toBeVisible();
  await axe(page, 'sources');
  // Add by paste (BibTeX).
  await page.getByRole('button', { name: 'Ajouter' }).first().click();
  await page.getByRole('radio', { name: 'Coller' }).check({ force: true });
  await page.getByLabel('BibTeX, RIS, CSL-JSON ou RDF Zotero').fill('@book{euclid300, title={Elements}, author={Euclid}, year={300}}');
  await page.getByRole('button', { name: 'Importer' }).click();
  await expect(page.getByRole('link', { name: /Elements/ })).toBeVisible();
  // Literature search (recorded answers in demo mode).
  await page.getByRole('radio', { name: 'Recherche bibliographique' }).check({ force: true });
  await page.getByLabel('Termes à chercher').fill('parity of integers');
  await page.locator('form.lit').getByRole('button', { name: 'Chercher' }).click();
  await expect(page.locator('.providers .chip').first()).toBeVisible({ timeout: 30_000 });
  // Reader + grounded question.
  await page.goto(`${BASE()}/sources?tab=library`);
  await page.getByRole('link', { name: /A note on parity/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'A note on parity' })).toBeVisible();
  await expect(page.locator('.chunk.definition')).toBeVisible();
  await axe(page, 'reader');
  await page.getByLabel('Votre question').fill('Why is the sum of two even integers even?');
  await page.getByRole('button', { name: 'Demander' }).click();
  // Wait for the answer, then open a cited passage (a sentence citation, else one of the consulted passages).
  await expect(page.locator('.qa .answer').first()).toBeVisible({ timeout: 30_000 });
  if (await page.locator('.cite').count()) await page.locator('.cite').first().click();
  else { await page.locator('.qa details summary').first().click(); await page.locator('.qa .passages button').filter({ hasText: 'Definition 1.1' }).first().click(); }
  await expect(page.locator('.chunk.focus')).toBeVisible();
  // Highlight a passage → annotation count grows.
  const sid = new URL(page.url()).pathname.split('/').pop()!;
  const before = (await api<{ source: { annotations: unknown[] } }>('GET', `/research/shelves/${pid}/sources/${sid}`)).source.annotations.length;
  await page.locator('.chunk.definition').getByRole('button', { name: 'Surligner' }).click();
  await expect.poll(async () => (await api<{ source: { annotations: unknown[] } }>('GET', `/research/shelves/${pid}/sources/${sid}`)).source.annotations.length).toBe(before + 1);
  // The PDF view renders pages with pdf.js.
  await page.getByRole('radio', { name: 'PDF' }).check({ force: true });
  await expect(page.locator('.pdf canvas').first()).toBeVisible();
  await expect.poll(async () => page.locator('.pdf canvas').first().evaluate((c) => (c as HTMLCanvasElement).width)).toBeGreaterThan(100);
});

test('notes: edit with autosave, [[ completion, Lean block check, versions, live conflict merge view', async ({ page }) => {
  const pid = await project(/Exemples/);
  const notes = await api<{ notes: { id: string; title: string; rev: number }[] }>('GET', `/notes?project=${pid}`);
  const n = notes.notes.find((x) => x.title === 'Somme et produit')!;
  await openIn(page, `/notes/${n.id}`, pid);
  await expect(page.getByLabel('Titre', { exact: true })).toHaveValue('Somme et produit');
  await axe(page, 'notes');
  const editor = page.getByRole('textbox', { name: 'Texte de la note' });
  await editor.click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nVoir aussi [[Pol');
  await expect(page.locator('.cm-tooltip-autocomplete')).toContainText('Polynôme d');
  await page.keyboard.press('Enter');
  await expect.poll(async () => (await api<{ note: { body: string } }>('GET', `/notes/${n.id}`)).note.body, { timeout: 10_000 }).toContain("[[Polynôme d'Euler]]");
  // Versions + diff.
  await page.getByRole('button', { name: 'Versions' }).click();
  await page.getByRole('button', { name: 'Différences' }).first().click();
  await expect(page.locator('.diff')).toBeVisible();
  await page.keyboard.press('Escape');
  // Conflict: another device rewrites the same line while we edit it.
  const cur = (await api<{ note: { rev: number; body: string } }>('GET', `/notes/${n.id}`)).note;
  await page.waitForTimeout(300);
  await api('PATCH', `/notes/${n.id}`, { base_rev: cur.rev, body: 'Texte écrit sur la tablette.\n' });
  await editor.click();
  await page.keyboard.press('Control+a');
  await page.keyboard.type('Texte écrit sur le PC.');
  await expect(page.getByRole('heading', { name: 'Modifié ailleurs en même temps' })).toBeVisible({ timeout: 10_000 });
  await axe(page, 'conflict view');
  await page.getByRole('button', { name: 'Enregistrer ce résultat' }).click();
  await expect.poll(async () => (await api<{ note: { body: string } }>('GET', `/notes/${n.id}`)).note.body).toContain('Texte écrit sur le PC.');
  // A note with a Lean block: check it.
  const lean = notes.notes.find((x) => /Parité/.test(x.title))!;
  await page.goto(`${BASE()}/notes/${lean.id}`);
  await page.getByRole('button', { name: 'Vérifier avec Lean' }).first().click();
  await expect(page.locator('.lb .chip').first()).toHaveText(/Lean accepte|Lean refuse/, { timeout: 20_000 });
});

test('graph and blueprint: nodes, list views, node panel with paper text beside Lean, formalise selected', async ({ page }) => {
  const pid = await project(/Recherche/);
  await openIn(page, '/graphe', pid);
  await expect(page.locator('svg .gn').first()).toBeVisible();
  await axe(page, 'graph');
  await page.getByLabel('Liste').check();
  await expect(page.locator('table.tbl tbody tr').first()).toBeVisible();
  await page.goto(`${BASE()}/blueprint`);
  await expect(page.getByRole('list', { name: 'Légende des états' })).toContainText('vérifié');
  await axe(page, 'blueprint');
  await page.getByLabel('Liste').check();
  await page.getByRole('button', { name: /Lemma 1\.2/ }).click();
  await expect(page.locator('.side')).toContainText('If');
  await expect(page.locator('.side .cm-content')).toContainText('theorem');
  await page.getByRole('checkbox', { name: /Sélectionner Theorem 2\.1/ }).check();
  await page.getByRole('button', { name: /Formaliser la sélection \(1\)/ }).click();
  await expect(page.getByText(/formalisation\(s\) lancée\(s\)/)).toBeVisible();
  for (const j of (await api<{ active: { dossier_id: string }[] }>('GET', '/jobs')).active) await api('POST', `/dossiers/${j.dossier_id}/stop`, {});
});

// The article editor (LaTeX project, visual/source modes, suggestions) is tested in e2e/article.spec.ts (S-R).

test('conjectures: counter-example and evidence log, write one, experiment needs explicit approval', async ({ page }) => {
  const pid = await project(/Exemples/);
  const list = await api<{ conjectures: { id: string; title: string; status: string }[] }>('GET', `/conjectures?project=${pid}`);
  const refuted = list.conjectures.find((c) => c.status === 'refuted')!;
  await openIn(page, `/conjectures/${refuted.id}`, pid);
  await expect(page.getByRole('heading', { name: 'Contre-exemple' })).toBeVisible();
  await expect(page.locator('.counter')).toContainText('n = 40');
  await expect(page.locator('.timeline li').first()).toBeVisible();
  await axe(page, 'conjecture');
  await page.getByRole('button', { name: 'Écrire une conjecture' }).click();
  await page.getByLabel('Énoncé', { exact: true }).fill('Pour tout entier n, n^3 - n est divisible par 6.');
  await page.getByRole('button', { name: 'Créer' }).click();
  await expect(page.getByRole('heading', { level: 2, name: /n\^3 - n|divisible/ })).toBeVisible();
  await page.getByRole('button', { name: /Chercher un contre-exemple \(Python\)/ }).click();
  await expect(page.getByRole('button', { name: 'J’ai lu ce code : approuver et lancer' })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Rien ne s’exécute sans votre approbation/)).toBeVisible();
});

test('proof plan mind map: select, validate, leave a hole → never verified; outline view', async ({ page }) => {
  const d = (await api<{ dossiers: { id: string; title: string; project_id: string }[] }>('GET', '/dossiers')).dossiers.find((x) => /carré d'un entier pair/.test(x.title))!;
  await openIn(page, `/d/${d.id}/plan`, d.project_id);
  await expect(page.getByRole('heading', { name: 'Plan de preuve' })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Carte mentale du plan de preuve' })).toBeVisible();
  await axe(page, 'plan-map');
  await page.getByRole('button', { name: /Carré d’un double|Carré d'un double/ }).first().click();
  const panel = page.locator('.panel-node');
  await expect(panel.getByRole('heading', { level: 3 })).toHaveText(/Carré d.un double/);
  await expect(panel.getByRole('navigation', { name: 'Chemin depuis le théorème' })).toBeVisible();
  await axe(page, 'plan-panel');
  await page.getByRole('button', { name: 'Valider le plan' }).click();
  await expect(page.getByRole('button', { name: 'Valider le plan' })).toHaveCount(0);
  await page.getByRole('button', { name: /Carré de 2k/ }).first().click();
  await panel.getByRole('button', { name: 'Laisser un trou (sorry)' }).click();
  await expect(panel.locator('.pst').first()).toContainText('trou (admis)');
  await expect(page.getByText('Prouvé et vérifié par Lean')).toHaveCount(0);
  await page.getByText('Liste', { exact: true }).click();
  await expect(page.locator('.outline')).toBeVisible();
  await axe(page, 'plan-outline');
  await page.getByText('Carte', { exact: true }).click();
});

test('learn mode through the server: ladder gates, explain-back criteria, faded and erroneous exercises', async ({ page }) => {
  const d = (await api<{ dossiers: { id: string; title: string; project_id: string; status: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved' && /somme de deux entiers pairs/.test(x.title))!;
  await openIn(page, `/d/${d.id}/preuve`, d.project_id, 'learn');
  await expect(page.getByRole('heading', { name: 'Indices, avant la preuve' })).toBeVisible();
  const next = page.getByRole('button', { name: /indice|Indice/ }).first();
  await expect(next).toBeVisible();
  if (await page.getByLabel('Qu’avez-vous essayé, ou quelle est votre idée ?').count()) await page.getByLabel('Qu’avez-vous essayé, ou quelle est votre idée ?').fill('Écrire a = 2k.');
  if (await page.getByLabel('Qu’est-ce que cet indice vous a appris ?').count()) await page.getByLabel('Qu’est-ce que cet indice vous a appris ?').fill('Il faut utiliser la définition.');
  await next.click();
  await expect(page.locator('.hintbox').last()).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: 'J’ai trouvé, montrer la preuve' }).click();
  await page.getByLabel('Votre explication').last().fill('On écrit a = 2k et b = 2l, donc a + b = 2(k + l).');
  await page.getByRole('button', { name: 'Faire relire mon explication' }).last().click();
  await expect(page.locator('.crit li').first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: 'Créer l’exercice' }).click();
  // Either blanks to fill, or the server's honest « every step is automatic: no useful exercise ».
  const blank = page.getByLabel('Trou 1');
  const trivial = page.locator('.ex').getByRole('alert');
  await expect(blank.or(trivial)).toBeVisible({ timeout: 30_000 });
  if (await blank.count()) {
    await blank.fill('exact Even.add ha hb');
    await page.getByRole('button', { name: 'Vérifier la preuve avec Lean' }).last().click();
    await expect(page.locator('.check').last()).toBeVisible({ timeout: 30_000 });
  }
  await page.getByRole('radio', { name: 'Trouver l’erreur' }).check({ force: true });
  await page.getByRole('button', { name: 'Créer l’exercice' }).click();
  const diag = page.getByLabel('Quelle étape est fausse, et pourquoi ?');
  await expect(diag.or(page.locator('.ex').getByRole('alert'))).toBeVisible({ timeout: 30_000 });
  if (await diag.count()) {
    await diag.fill('La dernière étape, le lemme ne s’applique pas.');
    await page.getByRole('button', { name: 'Voir ce que dit Lean' }).click();
    await expect(page.getByText('Message de Lean :')).toBeVisible({ timeout: 30_000 });
  }
});

test('manual proof edit becomes a version checked by Lean; D28 refusal is shown clearly', async ({ page }) => {
  const d = (await api<{ dossiers: { id: string; title: string; project_id: string; status: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved' && /somme de deux entiers pairs/.test(x.title))!;
  const before = (await api<{ dossier: { proofs: unknown[]; current: { proof: string } } }>('GET', `/dossiers/${d.id}`)).dossier;
  await openIn(page, `/d/${d.id}/preuve`, d.project_id);
  await page.getByRole('button', { name: 'Modifier la preuve' }).click();
  await page.getByRole('textbox', { name: 'Preuve modifiée' }).click();
  await page.keyboard.press('Control+End');
  await page.keyboard.press('Shift+Enter');                                  // S-AK: Shift+Enter = new line, Enter = check
  await page.keyboard.type('  -- relu à la main');
  await page.getByRole('button', { name: 'Vérifier et enregistrer' }).click();
  await expect.poll(async () => (await api<{ dossier: { proofs: unknown[] } }>('GET', `/dossiers/${d.id}`)).dossier.proofs.length, { timeout: 20_000 }).toBe(before.proofs.length + 1);
  // D28: the server refuses code that could run on the host; the UI says so plainly (refusal simulated here).
  await page.route('**/api/dossiers/*/check', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ what: 'statement', check: {
    ok: false, statement_ok: false, summary: 'Refusé avant compilation : commande exécutée à la compilation (#eval…).', errors: [], axioms: null, has_sorry: false,
    reasons: ['commande exécutée à la compilation (#eval…)'], seconds: 0, timed_out: false, cancelled: false, infra_error: '' } }) }));
  await page.goto(`${BASE()}/d/${d.id}/lean`);
  await page.getByRole('button', { name: 'Vérifier avec Lean' }).click();
  await expect(page.getByText('Lean n’a pas été lancé : code refusé par sécurité')).toBeVisible();
  await expect(page.getByText(/une commande exécutée à la compilation/)).toBeVisible();
});

test('help, publish, updates, global search', async ({ page }) => {
  const pid = await project(/Recherche/);
  await openIn(page, '/reglages/cles', pid);
  await page.locator('main a.help').first().click();
  await expect(page).toHaveURL(/\/aide\/models-keys/);
  await expect(page.locator('.manual h1')).toBeVisible();
  await axe(page, 'help');
  await page.getByLabel('Chercher dans le manuel').fill('appairer');
  await expect(page.locator('.res li').first()).toBeVisible();
  await page.goto(`${BASE()}/aide/pairing`);
  await expect(page.locator('.manual h2[id]').first()).toBeAttached();
  const ids = await page.locator('.manual h2[id]').evaluateAll((hs) => hs.map((h) => h.id));
  expect(ids.length).toBeGreaterThan(0);
  await page.goto(`${BASE()}/publier`);
  await expect(page.getByRole('heading', { name: 'Ce que vous publiez' })).toBeVisible();
  await axe(page, 'publish');
  // The demo workspace has no pinned Mathlib: the server refuses to build the list and the UI says why, in words.
  await page.getByRole('button', { name: 'Préparer la liste exacte' }).click();
  await expect(page.getByRole('heading', { name: 'Ce qui quittera cet ordinateur' }).or(page.locator('.pub [role=alert]'))).toBeVisible({ timeout: 20_000 });
  await page.goto(`${BASE()}/reglages/mises-a-jour`);
  await expect(page.getByLabel('Installer automatiquement quand rien ne tourne')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Madalean lui-même' })).toBeVisible();
  await axe(page, 'updates');
  await page.keyboard.press('Control+k');
  await page.getByRole('combobox', { name: 'Aller à… ou faire…' }).fill('parity');
  await expect(page.getByRole('option', { name: /A note on parity/ })).toBeVisible({ timeout: 10_000 });
});
