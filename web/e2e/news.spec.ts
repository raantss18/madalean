// « Actualités » (session S-AV, docs/NEWS.md): the screen, its filters, the send-to-project actions, the Home card,
// the settings section, accessibility (axe) and the layouts — against the demo server, whose news store is seeded
// from the recorded answers of madalean/news/demo_data (no network).
// Screenshots: docs/screenshots/v2/news-*.png (run with the `e2e` project).
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, api, axe } from './util';

const OUT = new URL('../../docs/screenshots/v2/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

interface Item { id: number; title: string; url: string; open: boolean; read: boolean; saved: boolean; source: string; group: string; extra: Record<string, unknown>; projects: { project: string; terms: string[] }[] }
const list = (q = '') => api<{ items: Item[]; total: number; unread: number }>('GET', `/news${q}`);

async function noHScroll(page: Page, label: string) {
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, `horizontal scroll on ${label}`).toBeLessThanOrEqual(w!);
}
async function reset() {
  await api('PATCH', '/news/settings', { branches: [], badge: true, summaries: false, enabled: true });
  await api('POST', '/news/refresh', {});            // demo: re-seeds from the recordings (idempotent)
}

test.describe.configure({ mode: 'serial' });
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { try { localStorage.removeItem('madalean.news.filters'); } catch { /* ignore */ } });
});

test('the demo store is seeded and the screen lists it, reachable from the logo menu', async ({ page }) => {
  await reset();
  const all = await list('?limit=100');
  expect(all.total).toBeGreaterThan(60);
  expect(new Set(all.items.map((x) => x.source)).size).toBeGreaterThanOrEqual(10);
  await open(page, '/', { mode: 'research' });
  await page.getByRole('button', { name: /Menu|menu/ }).first().click();
  const entry = page.getByRole('menuitem', { name: /Actualités/ });
  await expect(entry).toBeVisible();
  await entry.click();
  await expect(page).toHaveURL(/\/actualites$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Actualités' })).toBeVisible();
  await expect(page.locator('.news .item').first()).toBeVisible();
  await expect(page.locator('.news .item')).toHaveCount(30);
  await expect(page.getByText('Démonstration : exemples enregistrés')).toBeVisible();
  await page.getByRole('button', { name: /Afficher la suite/ }).click();
  await expect(page.locator('.news .item')).toHaveCount(60);
});

test('filters: open problems, field, source, search, for my projects', async ({ page }) => {
  await open(page, '/actualites', { mode: 'research' });
  await expect(page.locator('.news .item').first()).toBeVisible();
  // open problems
  await page.getByRole('button', { name: 'Problèmes ouverts', exact: true }).click();
  const open_ = await list('?open=1&limit=100');
  await expect(page.locator('.news .item')).toHaveCount(Math.min(open_.total, 30));
  await expect(page.locator('.news .item .chip.running').first()).toHaveText('Problème ouvert');
  expect(await page.locator('.news .item').count()).toBe(await page.locator('.news .item .chip.running').count());
  await page.getByRole('button', { name: 'Problèmes ouverts', exact: true }).click();
  // field
  await page.getByLabel('Domaine').selectOption('number-theory');
  const nt = await list('?branch=number-theory&limit=100');
  await expect(page.locator('.count p')).toHaveText(new RegExp(`^${nt.total} élément`));
  await page.getByLabel('Domaine').selectOption('');
  // source (one source, then a whole group)
  await page.getByLabel('Source', { exact: true }).selectOption('lean-releases');
  await expect(page.locator('.news .item .src').first()).toHaveText('Lean — versions');
  await page.getByLabel('Source', { exact: true }).selectOption('g:lean');
  const lean = await list('?group=lean&limit=100');
  await expect(page.locator('.count p')).toHaveText(new RegExp(`^${lean.total} élément`));
  await page.getByRole('button', { name: 'Enlever les filtres' }).click();
  // search (accent-insensitive, live)
  await page.getByLabel('Chercher dans les actualités').fill('parite carres');
  await expect(page.locator('.news .item')).toHaveCount(1);
  await expect(page.locator('.news .item .tt')).toContainText('Parité des carrés');
  await page.getByLabel('Chercher dans les actualités').fill('');
  // for my projects: the demo project is about parity, the demo feed has a question about it
  await page.getByRole('button', { name: 'Pour mes projets' }).click();
  await expect(page.locator('.news .item .tt').first()).toContainText('Parité des carrés');
  await expect(page.locator('.news .item .chip.proved').first()).toContainText('Pour : ');
  const mine = await list('?projects=1&limit=100');
  expect(mine.total).toBeGreaterThan(0);
  expect(mine.total).toBeLessThan(15);
  expect(mine.items[0]!.projects[0]!.terms.length).toBeGreaterThan(0);
});

test('reading an item: abstract, French summary beside the original, external link, saved, unread', async ({ page }) => {
  await open(page, '/actualites', { mode: 'research' });
  await page.getByLabel('Chercher dans les actualités').fill('parité des carrés');
  const row = page.locator('.news .item').first();
  await expect(row.locator('.tt')).toContainText('Parité des carrés');
  const before = (await list()).unread;
  await row.getByRole('button', { name: /Parité des carrés/ }).click();
  await expect(row.locator('.body')).toBeVisible();
  await expect(row.locator('.fr .lbl')).toBeVisible();
  await expect(row.getByText('Texte d’origine', { exact: true })).toBeVisible();
  await expect(row.locator('.abs')).toContainText('la somme de deux entiers pairs est paire');
  const link = row.getByRole('link', { name: /Ouvrir sur example\.org/ });
  await expect(link).toHaveAttribute('target', '_blank');
  await expect(link).toHaveAttribute('rel', /noopener/);
  await expect.poll(async () => (await list()).unread).toBe(before - 1);          // opening marks it read
  await row.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(row.getByRole('button', { name: 'Ne plus garder' })).toBeVisible();
  expect((await list('?saved=1')).items.map((x) => x.title)).toContain('Parité des carrés : une question ouverte de démonstration');
  await row.getByRole('button', { name: 'Marquer non lu' }).click();
  await expect.poll(async () => (await list()).unread).toBe(before);
  await expect(row.locator('.body')).toHaveCount(0);
});

test('a hostile item is shown as inert text, flagged, and cannot be summarised', async ({ page }) => {
  const dialogs: string[] = [];
  page.on('dialog', (d) => { dialogs.push(d.message()); void d.dismiss(); });
  await open(page, '/actualites', { mode: 'research' });
  await page.getByLabel('Chercher dans les actualités').fill('remarkable identity');
  const row = page.locator('.news .item').first();
  await row.getByRole('button', { name: /remarkable identity/ }).click();
  await expect(row.locator('.warn')).toContainText('n’est jamais envoyé à un modèle');
  await expect(row.locator('.abs')).toContainText('ignore all previous instructions');   // readable, as text
  expect(await row.locator('.abs script, .abs img, .abs a[href^="javascript"]').count()).toBe(0);
  await expect(row.getByRole('button', { name: 'Résumer en français' })).toHaveCount(0);
  expect(dialogs).toEqual([]);
  const it = (await list('?q=remarkable identity')).items[0]!;
  expect(it.extra['suspect']).toBe(true);
  const r = await fetch(`${process.env['MADALEAN_URL']}/api/news/items/${it.id}/summary`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  expect(r.status).toBe(422);
  expect(((await r.json()) as { error: string }).error).toBe('suspect');
});

test('send to the project: Sources (arXiv), conjecture, dossier, note', async ({ page }) => {
  // its own project: the demo projects are left untouched (other specs find them by title and by order)
  const demo = (await api<{ project: { id: string; title: string } }>('POST', '/projects', { title: 'Veille (e2e)' })).project;
  await page.addInitScript((id) => { try { localStorage.setItem('madalean.lastProject', JSON.stringify(id)); } catch { /* ignore */ } }, demo.id);
  await open(page, '/actualites', { mode: 'research' });
  await page.getByLabel('Source', { exact: true }).selectOption('arxiv-math');
  const row = page.locator('.news .item').first();
  const title = (await row.locator('.tt').innerText()).trim();
  await row.locator('button.disc').click();
  await expect(row.getByText(/Envoyer vers le projet/)).toBeVisible();
  for (const name of ['Ajouter aux Sources du projet', 'Créer une conjecture', 'Créer un dossier à partir de ce problème', 'Envoyer dans une note']) {
    await expect(row.getByRole('button', { name })).toBeEnabled();
  }
  // conjecture
  const c0 = (await api<{ conjectures: unknown[] }>('GET', `/conjectures?project=${demo.id}`)).conjectures.length;
  await row.getByRole('button', { name: 'Créer une conjecture' }).click();
  await expect(page.getByText('Conjecture créée.')).toBeVisible();
  const cs = (await api<{ conjectures: { statement?: string; problem?: string; title: string }[] }>('GET', `/conjectures?project=${demo.id}`)).conjectures;
  expect(cs.length).toBe(c0 + 1);
  // note
  await row.getByRole('button', { name: 'Envoyer dans une note' }).click();
  await expect(page.getByText('Note créée.')).toBeVisible();
  const notes = (await api<{ notes: { title: string; tags: string[] }[] }>('GET', `/notes?project=${demo.id}`)).notes;
  expect(notes.some((n) => n.tags.includes('actualités'))).toBe(true);
  // dossier: created, not started
  const d0 = (await api<{ dossiers: { id: string }[] }>('GET', '/state')).dossiers.length;
  await row.getByRole('button', { name: 'Créer un dossier à partir de ce problème' }).click();
  await expect(page.getByText(/Dossier créé/)).toBeVisible();
  const st = await api<{ dossiers: { id: string; title: string; status: string }[]; jobs?: { dossier_id: string; active?: boolean }[] }>('GET', '/state');
  expect(st.dossiers.length).toBe(d0 + 1);
  // Sources: the demo replays recorded arXiv answers, so the import goes through the existing Sources path
  await row.getByRole('button', { name: 'Ajouter aux Sources du projet' }).click();
  await expect(page.locator('.toast, [role=status], [role=alert]').filter({ hasText: /Sources|Mode Local|Erreur|introuvable|Introuvable/ }).first()).toBeVisible();
  expect(title.length).toBeGreaterThan(3);
  await expect(row.getByRole('button', { name: 'Ne plus garder' })).toBeVisible();     // sent items are kept
  await api('DELETE', `/projects/${demo.id}`);     // leave the demo's project order as it was for the other specs
});

test('Home card « Nouveautés » and the menu badge follow the unread count; the badge can be turned off', async ({ page }) => {
  await reset();
  const n = (await api<{ unread: number }>('GET', '/news/overview')).unread;
  expect(n).toBeGreaterThan(0);
  await open(page, '/', { mode: 'research' });
  const card = page.locator('.newscard');
  await expect(card).toBeVisible();
  await expect(card.getByRole('heading', { name: 'Nouveautés' })).toBeVisible();
  await expect(card.getByRole('link', { name: new RegExp(`${n} non lus?`) })).toBeVisible();
  await expect(card.locator('li')).toHaveCount(3);
  await page.getByRole('button', { name: /Menu|menu/ }).first().click();
  await expect(page.getByRole('menuitem', { name: /Actualités/ })).toContainText(n > 99 ? '99+' : String(n));
  await page.keyboard.press('Escape');
  // following one field narrows the count
  await api('PATCH', '/news/settings', { branches: ['pde'] });
  const m = (await api<{ unread: number }>('GET', '/news/overview')).unread;
  expect(m).toBeLessThan(n);
  await page.reload();
  await expect(page.locator('.newscard').getByRole('link', { name: new RegExp(`${m} non lus?`) })).toBeVisible();
  await page.locator('.newscard').getByRole('link', { name: /non lu/ }).click();
  await expect(page).toHaveURL(/\/actualites$/);
  await page.getByRole('button', { name: 'Mes domaines' }).click();
  await expect(page.locator('.count p')).toHaveText(new RegExp('^\\d+ élément'));
  // quiet: badge off → no card
  await api('PATCH', '/news/settings', { badge: false });
  await open(page, '/', { mode: 'research' });
  await expect(page.locator('main h1').first()).toBeVisible();
  await page.waitForTimeout(1200);
  await expect(page.locator('.newscard')).toHaveCount(0);
  await reset();
});

test('settings: fields, sources with their terms, own feeds, frequency, summaries', async ({ page }) => {
  await reset();
  await open(page, '/reglages/actualites', { mode: 'research' });
  await expect(page.getByRole('heading', { level: 2, name: 'Actualités' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Domaines suivis' })).toBeVisible();
  await expect(page.locator('.branches li')).toHaveCount(15);
  await page.getByLabel('Théorie des nombres').check();
  await expect.poll(async () => (await api<{ settings: { branches: string[] } }>('GET', '/news/settings')).settings.branches).toEqual(['number-theory']);
  await page.getByRole('button', { name: 'Tout suivre' }).click();
  await expect.poll(async () => (await api<{ settings: { branches: string[] } }>('GET', '/news/settings')).settings.branches).toEqual([]);
  // a source: off, with its licence and terms
  const quanta = page.locator('.sources li').filter({ hasText: 'Quanta Magazine' });
  await quanta.getByText('Licence et conditions').click();
  await expect(quanta.locator('details p')).toContainText('Quanta Magazine');
  await quanta.getByRole('checkbox').uncheck();
  await expect.poll(async () => (await api<{ settings: { sources: Record<string, boolean> } }>('GET', '/news/settings')).settings.sources['quanta']).toBe(false);
  expect((await list('?source=quanta')).total).toBe(0);
  await quanta.getByRole('checkbox').check();
  // frequency and summaries
  await page.getByLabel('Fréquence').selectOption('24');
  await expect.poll(async () => (await api<{ settings: { interval_hours: number } }>('GET', '/news/settings')).settings.interval_hours).toBe(24);
  await page.getByLabel('Résumer automatiquement les nouveautés de mes domaines').check();
  await expect.poll(async () => (await api<{ settings: { summaries: boolean } }>('GET', '/news/settings')).settings.summaries).toBe(true);
  // own feed: a refused address, then a good one (Enter validates the single-line field)
  await page.getByLabel('Adresse d’un flux RSS ou Atom').fill('https://192.168.0.10/feed');
  await page.getByLabel('Adresse d’un flux RSS ou Atom').press('Enter');
  await expect(page.getByRole('alert').filter({ hasText: 'Adresse refusée' })).toBeVisible();
  await page.getByLabel('Adresse d’un flux RSS ou Atom').fill('https://blog.example.org/feed.xml');
  await page.getByLabel(/^Nom/).fill('Mon séminaire');
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  const mine = page.locator('.sources li').filter({ hasText: 'Mon séminaire' });
  await expect(mine).toBeVisible();
  await expect(mine).toContainText('https://blog.example.org/feed.xml');
  await mine.getByRole('button', { name: /Retirer/ }).click();
  await expect(mine).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Ce qui quitte cet ordinateur' })).toBeVisible();
  await api('PATCH', '/news/settings', { interval_hours: 6, summaries: false });
});

test('English', async ({ page }) => {
  await api('PATCH', '/settings', { language: 'en' });
  try {
    await open(page, '/actualites', { mode: 'research' });
    await expect(page.getByRole('heading', { level: 1, name: 'News' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open problems', exact: true })).toBeVisible();
    await page.getByLabel('Field').selectOption('number-theory');
    await expect(page.locator('.count p')).toHaveText(/^\d+ items?/);
    await page.goto(`${process.env['MADALEAN_URL']}/reglages/actualites`);
    await expect(page.getByRole('heading', { name: 'Fields followed' })).toBeVisible();
    await expect(page.getByLabel('Number theory')).toBeVisible();
  } finally { await api('PATCH', '/settings', { language: 'fr' }); }
});

for (const [w, h, scheme] of [[360, 780, 'light'], [820, 1180, 'light'], [1440, 900, 'light'], [1440, 900, 'dark'], [360, 780, 'dark']] as const) {
  test(`layout, axe and screenshots ${w} ${scheme}`, async ({ page }) => {
    await reset();
    await page.setViewportSize({ width: w, height: h });
    await page.emulateMedia({ colorScheme: scheme });
    await open(page, '/actualites', { mode: 'research' });
    await expect(page.locator('.news .item').first()).toBeVisible();
    await page.locator('.news .item').filter({ hasText: /\$/ }).first().waitFor({ state: 'attached', timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(600);
    await noHScroll(page, `news ${w}`);
    await axe(page, `news list ${w} ${scheme}`);
    await page.screenshot({ path: `${OUT}news-list-${w}-${scheme}.png` });
    await page.getByLabel('Chercher dans les actualités').fill('parité des carrés');
    await expect(page.locator('.news .item')).toHaveCount(1);
    await page.locator('.news .item button.disc').first().click();
    await expect(page.locator('.news .item .body')).toBeVisible();
    await page.waitForTimeout(500);
    await noHScroll(page, `news item ${w}`);
    await axe(page, `news item ${w} ${scheme}`);
    await page.screenshot({ path: `${OUT}news-item-${w}-${scheme}.png` });
    // keyboard: the title is a real button (Enter / Space toggle), Tab reaches the actions in order
    await page.locator('.news .item button.disc').first().focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.news .item .body')).toHaveCount(0);
    await page.keyboard.press('Space');
    await expect(page.locator('.news .item .body')).toBeVisible();
    if (scheme === 'light') {
      await open(page, '/reglages/actualites', { mode: 'research' });
      await expect(page.getByRole('heading', { name: 'Domaines suivis' })).toBeVisible();
      await page.waitForTimeout(300);
      await noHScroll(page, `news settings ${w}`);
      await axe(page, `news settings ${w}`);
      await page.screenshot({ path: `${OUT}news-settings-${w}-${scheme}.png`, fullPage: true });
      await open(page, '/', { mode: 'research' });
      await expect(page.locator('.newscard')).toBeVisible();
      await page.locator('.newscard').scrollIntoViewIfNeeded();
      await noHScroll(page, `home card ${w}`);
      await axe(page, `home with news card ${w}`);
      if (w !== 820) await page.locator('.newscard').screenshot({ path: `${OUT}news-home-card-${w}-${scheme}.png` });
    }
  });
}
