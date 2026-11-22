// « Premiers pas » (S-AQ, D49): opens by itself at the first start on the host only, every step skippable,
// « Plus tard » + resume from the Home card / the logo menu, each step's controls, « Terminer ».
// global-setup.ts marks the assistant finished for the other specs; each test here reopens it and puts it back.
import { test, expect, type Page } from '@playwright/test';
import { api, axe, open, REMOTE, URL } from './util';

type Wiz = { step: string; visited: string[]; models: string; done: boolean; completed: boolean; reminder: boolean; auto: boolean };
type S = { settings: Record<string, unknown> };

async function firstStart(): Promise<void> {
  await api('PATCH', '/setup/wizard', { done: false, completed: false, step: 'welcome', reminder: true });
}
async function restore(): Promise<void> {
  await api('PATCH', '/setup/wizard', { completed: true });
  await api('PATCH', '/settings', { mode: 'auto', sage_source: 'auto', tex_engine: 'auto', conductor_cap_usd: 1, parallel_stages: true });
}
const heading = (page: Page) => page.getByRole('heading', { level: 1 });

test.afterEach(restore);

test('first start on the host opens the assistant; a paired device never sees it', async ({ page, browser }) => {
  await firstStart();
  await open(page, '/');
  await expect(page).toHaveURL(/\/premiers-pas\/welcome$/);
  await expect(heading(page)).toHaveText('Bienvenue dans Madalean');
  await expect(page.getByRole('navigation', { name: 'Étapes' }).getByRole('link')).toHaveCount(10);
  await expect(page.getByRole('link', { name: /Aide/ })).toHaveAttribute('href', '/aide/first-config#lassistant-premiers-pas');
  await expect(page.locator('.topbar')).toHaveCount(0);                                    // full screen
  await axe(page, 'wizard welcome');
  // a deep link is respected even at the first start
  await page.goto(URL() + '/reglages/modeles');
  await expect(page).toHaveURL(/\/reglages\/modeles$/);
  // a paired browser on the remote listener: no assistant, no menu entry, the page says why
  const ctx = await browser.newContext({ locale: 'fr-FR' });
  const remote = await ctx.newPage();
  const { code } = await api<{ code: string }>('POST', '/pairing/start', {});
  await remote.goto(REMOTE() + '/pair');
  await remote.getByLabel('Code à 6 chiffres').fill(code);
  await remote.getByLabel('Nom de cet appareil').fill('Téléphone premiers pas');
  await remote.getByRole('button', { name: 'Relier' }).click();
  await expect(remote.getByRole('heading', { level: 1, name: 'Que voulez-vous prouver ?' })).toBeVisible();
  await expect(remote).toHaveURL(/\/$/);
  await expect(remote.getByText('Premiers pas', { exact: true })).toHaveCount(0);           // no Home card
  await remote.locator('.logo-btn').click();
  await expect(remote.getByRole('menuitem', { name: 'Premiers pas' })).toHaveCount(0);
  await remote.goto(REMOTE() + '/premiers-pas');
  await expect(remote.getByText(/seulement sur l’ordinateur hôte/)).toBeVisible();
  const r = await remote.request.get(REMOTE() + '/api/setup/wizard');
  expect(r.status()).toBeGreaterThanOrEqual(401);
  const devs = await api<{ browsers: { id: string; name: string }[]; devices: { id: string; name: string }[] }>('GET', '/devices');
  for (const d of [...devs.browsers, ...devs.devices].filter((x) => x.name === 'Téléphone premiers pas')) await api('DELETE', `/devices/${d.id}`);
  await ctx.close();
});

test('skip, « Plus tard », Home card, resume from the card and the logo menu', async ({ page }) => {
  await firstStart();
  await open(page, '/premiers-pas');
  await expect(page).toHaveURL(/\/premiers-pas\/welcome$/);
  await page.getByRole('button', { name: 'Commencer' }).click();
  await expect(heading(page)).toHaveText('Les outils de Madalean');
  await page.getByRole('button', { name: 'Passer cette étape' }).click();
  await expect(heading(page)).toHaveText('Un modèle sur cet ordinateur ?');
  await expect.poll(async () => (await api<Wiz>('GET', '/setup/wizard')).step).toBe('local');
  expect((await api<Wiz>('GET', '/setup/wizard')).visited).toEqual(['welcome', 'tools']);
  // the stepper shows where we have been (✓) and lets the keyboard jump to any step
  await expect(page.getByRole('link', { name: /Outils.*déjà vue/ })).toBeVisible();
  await page.getByRole('button', { name: 'Plus tard' }).click();
  await expect(page).toHaveURL(URL() + '/');
  const w = await api<Wiz>('GET', '/setup/wizard');
  expect(w.done && !w.completed && !w.auto).toBe(true);
  // the Home card stays and does not reopen the assistant by itself
  const card = page.getByRole('complementary', { name: 'Premiers pas' });
  await expect(card).toContainText('« Modèle local » (étape 3 sur 10)');
  await page.reload();
  await expect(page).toHaveURL(URL() + '/');
  await axe(page, 'home with the reminder card');
  await card.getByRole('link', { name: 'Reprendre' }).click();
  await expect(heading(page)).toHaveText('Un modèle sur cet ordinateur ?');
  await page.getByRole('button', { name: 'Précédent' }).click();
  await expect(heading(page)).toHaveText('Les outils de Madalean');
  // the logo menu (outside the assistant) opens it where we stopped
  await page.goto(URL() + '/aide');
  await page.locator('.logo-btn').click();
  await page.getByRole('menuitem', { name: 'Premiers pas' }).click();
  await expect(heading(page)).toHaveText('Les outils de Madalean');
  // from Réglages too
  await page.goto(URL() + '/reglages');
  await page.getByRole('link', { name: /Premiers pas : l’assistant/ }).click();
  await expect(heading(page)).toHaveText('Les outils de Madalean');
  // « Ne plus afficher » hides the card
  await page.goto(URL() + '/');
  await card.getByRole('button', { name: 'Ne plus afficher' }).click();
  await expect(card).toHaveCount(0);
  expect((await api<Wiz>('GET', '/setup/wizard')).reminder).toBe(false);
});

test('each step: reuse choice, local model, key test, Claude caps, mode, behaviours, finish', async ({ page }) => {
  await firstStart();
  await open(page, '/premiers-pas/tools');
  // ---- tools: the components and the reuse choices, saved and checked by the server
  await expect(page.getByRole('heading', { name: 'Composants' })).toBeVisible();
  const sage = page.getByRole('group', { name: 'Quel SageMath utiliser ?' });
  await sage.getByRole('radio', { name: /^La copie de Madalean/ }).check();
  await expect(sage.getByRole('status')).toHaveText('Choix enregistré.');
  expect((await api<S>('GET', '/settings')).settings['sage_source']).toBe('own');
  await page.reload();
  await expect(sage.getByRole('radio', { name: /^La copie de Madalean/ })).toBeChecked();
  await axe(page, 'wizard tools');
  // ---- local model: the choice is remembered; the demo never downloads
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(heading(page)).toHaveText('Un modèle sur cet ordinateur ?');
  const models = page.getByRole('group', { name: 'Quels modèles installer sur cet ordinateur ?' });
  await models.getByRole('radio', { name: /Le modèle de preuve/ }).check();
  await expect.poll(async () => (await api<Wiz>('GET', '/setup/wizard')).models).toBe('prover');
  await models.getByRole('radio', { name: /Les trois modèles/ }).check();
  await expect.poll(async () => (await api<Wiz>('GET', '/setup/wizard')).models).toBe('all');
  await page.reload();
  await expect(models.getByRole('radio', { name: /Les trois modèles/ })).toBeChecked();
  // the models dir is the machine's (~/models): « Télécharger » only when a file is missing there
  const dl = page.getByRole('button', { name: /^Télécharger/ });
  if (await dl.count()) {
    await dl.click();
    await expect(page.getByText('Mode démo : rien n’est téléchargé.')).toBeVisible();
  } else await expect(models.getByText('Déjà sur cet ordinateur.').last()).toBeVisible();
  await axe(page, 'wizard local');
  // ---- keys: paste, explicit save (tested at once), then « Tester » again
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(heading(page)).toHaveText('Des clés gratuites pour les modèles en ligne');
  const groq = page.locator('#wiz-card-groq');
  await groq.getByLabel('Clé Groq').fill('gsk_' + 'x'.repeat(40));
  await expect.poll(async () => (await api<{ keys: Record<string, boolean> }>('GET', '/models')).keys['groq'] ?? false).toBe(false);   // never autosaved
  await groq.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(groq.getByText('clé enregistrée', { exact: true })).toBeVisible();
  await groq.getByRole('button', { name: /^Tester/ }).click();
  await expect(groq.getByRole('status').last()).not.toHaveText(/Je teste/);
  await expect(groq.getByRole('status').last()).not.toBeEmpty();
  await axe(page, 'wizard keys');
  await groq.getByRole('button', { name: 'Retirer la clé' }).click();
  await groq.getByRole('button', { name: 'Retirer la clé' }).click();
  // ---- Hugging Face, then Claude's caps (saved as they change)
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(heading(page)).toHaveText('Hugging Face : le meilleur prouveur Lean ouvert');
  await expect(page.locator('#wiz-card-huggingface')).toBeVisible();
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(heading(page)).toHaveText('Claude, chef d’orchestre et renfort payant');
  await page.getByLabel('Plafond par demande').fill('2');
  await page.getByLabel('Plafond par demande').blur();
  await expect.poll(async () => (await api<S>('GET', '/settings')).settings['conductor_cap_usd']).toBe(2);
  await axe(page, 'wizard claude');
  // ---- modes: where the models work (server) and Learn / Research (this device)
  await page.getByRole('button', { name: 'Suivant' }).click();
  await page.getByRole('radio', { name: /^En ligne/ }).check();
  await expect.poll(async () => (await api<S>('GET', '/settings')).settings['mode']).toBe('online');
  await page.getByRole('radio', { name: /Recherche/ }).check();
  expect(await page.evaluate(() => localStorage.getItem('madalean.density'))).toBe('research');
  await page.getByRole('radio', { name: /Apprendre/ }).check();
  // ---- automatic or manual
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(page.getByLabel('Lancer les expériences sans approbation')).not.toBeChecked();
  await page.getByLabel('Faire avancer les étapes en même temps').uncheck();
  await expect.poll(async () => (await api<S>('GET', '/settings')).settings['parallel_stages']).toBe(false);
  await axe(page, 'wizard auto');
  // ---- devices (the pairing flow of Réglages), then the checklist and « Terminer »
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(page.getByRole('button', { name: 'Afficher un code' })).toBeVisible();
  await page.getByRole('button', { name: 'Suivant' }).click();
  await expect(heading(page)).toHaveText('C’est prêt');
  await expect(page.getByRole('heading', { name: 'Liste de vérification' })).toBeVisible();
  await expect(page.getByText('En ligne', { exact: true })).toBeVisible();                 // summary of the choices
  await axe(page, 'wizard done');
  await page.getByRole('button', { name: 'Terminer' }).click();
  await expect(page).toHaveURL(URL() + '/');
  await expect(page.getByRole('complementary', { name: 'Premiers pas' })).toHaveCount(0);
  const w = await api<Wiz>('GET', '/setup/wizard');
  expect(w.completed && w.done && !w.auto).toBe(true);
  await page.reload();
  await expect(page).toHaveURL(URL() + '/');
});

test('phone and dark theme: no horizontal scroll, axe clean, Enter in the key field saves explicitly', async ({ page }) => {
  await firstStart();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark' });
  for (const s of ['welcome', 'tools', 'local', 'keys', 'claude', 'auto', 'done']) {
    await open(page, `/premiers-pas/${s}`);
    await expect(heading(page)).toBeVisible();
    await page.waitForTimeout(300);
    const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    expect(sw, s).toBeLessThanOrEqual(w!);
    if (s === 'welcome' || s === 'keys') await axe(page, `wizard ${s} phone dark`);
  }
  await open(page, '/premiers-pas/keys');
  const card = page.locator('#wiz-card-gemini');
  await card.getByLabel(/Clé Google Gemini|Clé Gemini/).fill('AIza' + 'y'.repeat(35));
  await card.getByLabel(/Clé Google Gemini|Clé Gemini/).press('Enter');                     // the form's own submit
  await expect(card.getByText('clé enregistrée', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Retirer la clé' }).click();
  await card.getByRole('button', { name: 'Retirer la clé' }).click();
  await expect(card.getByRole('status').first()).toContainText('Clé retirée');
});
