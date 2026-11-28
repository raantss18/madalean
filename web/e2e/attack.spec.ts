import { test, expect, type Page, type Route } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, axe } from './util';

// S-BK (D70): « Problèmes ouverts ». The server side (S-BJ, docs/ATTACK.md) is built in parallel: every /api/attack
// route is mocked here on top of the demo server; live events are handed to the app's store as the socket would.
// ATTACK_SHOTS=<dir> saves screenshots.

type J = Record<string, unknown>;
const now = () => Date.now() / 1000;
const SHOTS = process.env['ATTACK_SHOTS'];
async function shot(page: Page, name: string) { if (SHOTS) { mkdirSync(SHOTS, { recursive: true }); await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); } }
async function noHScroll(page: Page) { expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0); }

const status = (x: J = {}): J => ({
  state: 'off', reason: '', today: { usd: 0, cap: 5, taken: 0, proofs: 0, released: 0 },
  workspace: { state: 'ready', commit: 'f00dcafe', size: 8e9, progress: 1 }, current: [], queue: 0, ...x,
});
const CURRENT = [
  { problem: 'erdos-123', title: 'Erdős 123 : sommes de puissances', kind: 'known', difficulty: 25, dossier_id: 'd-atk-1', phase: 'proving', since: now() - 12 * 60, lease: 'L1' },
  { problem: 'oeis-a000045', title: 'Un contre-exemple pour n ≤ 30', kind: 'counterexample', difficulty: 35, dossier_id: 'd-atk-2', phase: 'searching', since: now() - 30, lease: 'L2' },
];
const FILE = 'import FormalConjectures.Util.ProblemImports\n\ntheorem erdos_123 : ∀ n : ℕ, n ≤ n + 1 := by\n  intro n\n  omega\n';
const READY: J = {
  id: 'sub-1', problem: 'erdos-123', title: 'Erdős 123 : sommes de puissances', kind: 'proof', file: { path: 'FormalConjectures/ErdosProblems/123.lean', text: FILE },
  check: { local: true, rules: { ok: true }, axioms: ['propext', 'Classical.choice'] },
  plan: { id: 'pl-1', login: 'ada-l', requests: [
    { method: 'POST', url: 'https://api.github.com/repos/google-deepmind/formal-conjectures/forks' },
    { method: 'POST', url: 'https://api.github.com/repos/ada-l/formal-conjectures/git/refs', body: { ref: 'refs/heads/madalean/erdos-123' } },
    { method: 'PUT', url: 'https://api.github.com/repos/ada-l/formal-conjectures/contents/FormalConjectures/ErdosProblems/123.lean', body: { message: 'Erdős 123', branch: 'madalean/erdos-123' } },
    { method: 'POST', url: 'https://api.github.com/repos/google-deepmind/formal-conjectures/pulls', body: { title: 'Erdős 123', body: 'Lease: L1\nAgent: madalean\nModel: claude' } },
  ] }, state: 'ready', pr_url: '', created: now() - 600, dossier_id: 'd-atk-1',
};
const FAILING: J = { ...READY, id: 'sub-2', problem: 'erdos-9', title: 'Erdős 9', check: { local: true, rules: 'mot interdit : sorry', axioms: null }, created: now() - 900 };
const HISTORY = [
  { problem: 'erdos-7', title: 'Erdős 7', kind: 'known', outcome: 'solved', reason: '', t: now() - 86400, usd: 1.2, dossier_id: 'd-h1' },
  { problem: 'open-3', title: 'Cas n = 3 d’un problème ouvert', kind: 'open', outcome: 'reduced', reason: '', t: now() - 7200, usd: 0.8, dossier_id: 'd-h2' },
  { problem: 'open-4', title: 'Problème difficile', kind: 'open', outcome: 'released', reason: 'stuck', t: now() - 3600, usd: 0.45, dossier_id: '' },
];

interface Mock { st: J; subs: J[]; hist: J[]; calls: string[]; bodies: J[] }
async function mock(page: Page, init: Partial<Mock> = {}): Promise<Mock> {
  const m: Mock = { st: status(), subs: [], hist: [], calls: [], bodies: [], ...init };
  await page.route((u) => u.pathname.startsWith('/api/attack'), async (r: Route) => {
    const req = r.request();
    const path = new URL(req.url()).pathname;
    const key = `${req.method()} ${path}`;
    m.calls.push(key);
    if (req.method() !== 'GET') m.bodies.push((req.postDataJSON() as J) ?? {});
    if (key === 'GET /api/attack') return r.fulfill({ json: m.st });
    if (key === 'POST /api/attack/workspace') { m.st = status({ state: 'setup', workspace: { state: 'downloading', commit: 'f00dcafe', size: 8e9, progress: 0.4 } }); return r.fulfill({ json: m.st }); }
    if (key === 'POST /api/attack/start') { if (m.st['state'] !== 'setup') m.st = { ...m.st, state: 'running' }; return r.fulfill({ json: m.st }); }
    if (key === 'POST /api/attack/stop') { m.st = { ...m.st, state: 'off', current: [] }; return r.fulfill({ json: m.st }); }
    if (key === 'GET /api/attack/submissions') return r.fulfill({ json: m.subs });
    if (key === 'GET /api/attack/history') return r.fulfill({ json: m.hist });
    if (key === 'PATCH /api/attack/settings') return r.fulfill({ json: req.postDataJSON() });
    const sm = /^POST \/api\/attack\/submissions\/([^/]+)\/(send|discard)$/.exec(key);
    if (sm) {
      const s = m.subs.find((x) => x['id'] === sm[1]);
      if (!s) return r.fulfill({ status: 404, json: { error: 'not_found' } });
      if (sm[2] === 'send') {
        if ((req.postDataJSON() as { plan?: string })?.plan !== (s['plan'] as { id?: string })?.id) return r.fulfill({ status: 409, json: { error: 'plan_changed' } });
        Object.assign(s, { state: 'sent', pr_url: 'https://github.com/google-deepmind/formal-conjectures/pull/4242' });
      } else m.subs = m.subs.filter((x) => x !== s);
      return r.fulfill({ json: { submission: s } });
    }
    return r.fulfill({ status: 404, json: { error: 'not_found' } });
  });
  return m;
}
const stateLine = (page: Page) => page.locator('.head p.state > span:last-child');
/** Hands an event to the store as the WebSocket would (after sequencing). */
async function emit(page: Page, ev: J) {
  await page.evaluate((e) => (window as unknown as { __madalean: { deliver: (x: unknown) => void } }).__madalean.deliver({ seq: 0, ts: Date.now() / 1000, ...e }), ev);
}

test('off → first start explains everything, then downloads with the size in words', async ({ page }) => {
  const m = await mock(page, { st: status({ workspace: { state: 'none', commit: '', size: 9.6e9, progress: 0 } }) });
  await open(page, '/attaque');
  await expect(page.getByRole('heading', { level: 1, name: 'Problèmes ouverts' })).toBeVisible();
  await expect(stateLine(page)).toHaveText('Madalean ne travaille pas sur les problèmes ouverts.');
  await expect(page.getByText('Rien à envoyer pour l’instant.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Démarrer' }).click();
  const dlg = page.getByRole('dialog', { name: 'Avant de commencer' });
  await expect(dlg).toBeVisible();
  await expect(dlg).toContainText('en continu');
  await expect(dlg).toContainText('au plus 5,00 $ par jour');
  await expect(dlg).toContainText('environ 9,6 Go');
  await expect(dlg).toContainText('après votre clic sur « Envoyer »');
  await expect(dlg).toContainText('Keep my email addresses private');
  await expect(dlg.getByRole('link', { name: 'Ouvrir ce réglage sur GitHub' })).toHaveAttribute('href', 'https://github.com/settings/emails');
  await axe(page, 'attack agreement dialog');
  await shot(page, 'attaque-accord');
  // cancel: nothing was asked of the server
  await dlg.getByRole('button', { name: 'Annuler' }).click();
  await expect(dlg).toHaveCount(0);
  expect(m.calls.filter((c) => c.startsWith('POST'))).toEqual([]);
  await page.getByRole('button', { name: 'Démarrer' }).click();
  await page.getByRole('button', { name: 'J’accepte : télécharger et démarrer' }).click();
  await expect(stateLine(page)).toHaveText('Préparation : téléchargement de Lean et Mathlib, 3,2 / 8 Go');
  expect(m.calls.filter((c) => c.startsWith('POST'))).toEqual(['POST /api/attack/workspace', 'POST /api/attack/start']);
  expect(m.bodies[0]).toEqual({ accept: true });
  await expect(page.getByRole('progressbar', { name: 'Téléchargement de Lean et Mathlib' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Arrêter' })).toBeVisible();
  // live: the download progresses, then Lean builds
  await emit(page, { type: 'attack.state', attack: status({ state: 'setup', workspace: { state: 'downloading', commit: 'f00dcafe', size: 8e9, progress: 0.75 } }) });
  await expect(stateLine(page)).toHaveText('Préparation : téléchargement de Lean et Mathlib, 6 / 8 Go');
  await emit(page, { type: 'attack.state', attack: status({ state: 'setup', workspace: { state: 'building', commit: 'f00dcafe', size: 8e9, progress: 1 } }) });
  await expect(stateLine(page)).toHaveText('Préparation : Lean vérifie l’espace de travail (une seule fois)');
});

test('running: header in words, one card per problem, live budget pause, stop', async ({ page }) => {
  const today = { usd: 3.1, cap: 5, taken: 4, proofs: 1, released: 2 };
  const m = await mock(page, { st: status({ state: 'running', today, current: CURRENT, queue: 3 }), hist: HISTORY });
  await open(page, '/attaque');
  await expect(stateLine(page)).toHaveText('Madalean travaille sur 2 problèmes');
  await expect(page.getByText('3 problèmes en attente')).toBeVisible();
  await expect(page.getByText('3,10 $ sur 5,00 $')).toBeVisible();
  const counts = page.getByRole('definition');
  await expect(counts).toHaveText(['4', '1', '2']);
  const now = page.getByRole('region', { name: 'En ce moment' });
  const cards = now.getByRole('listitem');
  await expect(cards).toHaveCount(2);
  await expect(cards.first()).toContainText('Résultat connu · difficulté 25 / 100');
  await expect(cards.first()).toContainText('cherche une preuve · depuis 12 min');
  await expect(cards.nth(1)).toContainText('cherche un contre-exemple avec Sage · depuis < 1 min');
  await expect(now.getByRole('link', { name: 'Erdős 123 : sommes de puissances' })).toHaveAttribute('href', '/d/d-atk-1');
  await axe(page, 'attack running');
  await shot(page, 'attaque-en-cours');
  // keyboard: the first card's link is reachable by Tab
  await now.getByRole('link').first().focus();
  await expect(now.getByRole('link').first()).toBeFocused();
  await emit(page, { type: 'attack.state', attack: status({ state: 'budget', today: { ...today, usd: 5 }, current: [] }) });
  await expect(stateLine(page)).toHaveText('En pause : budget du jour atteint (5,00 $)');
  await expect(page.getByRole('status').filter({ hasText: 'En pause : budget du jour atteint (5,00 $)' })).toHaveCount(1);
  await expect(now.getByText('Aucun problème en cours.')).toBeVisible();
  await emit(page, { type: 'attack.state', ...status({ state: 'paused', reason: 'user_jobs', current: [] }) });
  await expect(stateLine(page)).toHaveText('En pause : vos propres dossiers passent d’abord');
  await page.getByRole('button', { name: 'Arrêter' }).click();
  await expect(stateLine(page)).toHaveText('Madalean ne travaille pas sur les problèmes ouverts.');
  expect(m.calls).toContain('POST /api/attack/stop');
});

test('ready → plan → send needs a confirmation → sent with the PR link; discard; a failing check cannot send', async ({ page }) => {
  const m = await mock(page, { st: status({ state: 'running' }), subs: [{ ...READY }, { ...FAILING }] });
  await open(page, '/attaque');
  const sub = page.getByRole('article', { name: 'Erdős 123 : sommes de puissances' });
  await expect(sub).toContainText('Prête, pas encore envoyée');
  await expect(sub).toContainText('FormalConjectures/ErdosProblems/123.lean');
  await expect(sub.getByRole('textbox', { name: /Fichier Lean de/ })).toBeVisible();
  await expect(sub.locator('.cm-content')).toContainText('omega');
  const checks = sub.getByRole('list', { name: 'Vérifications sur cet ordinateur' }).getByRole('listitem');
  await expect(checks).toHaveCount(3);
  await expect(checks.nth(0)).toContainText('Lean strict, vérification neuve : réussi');
  await expect(checks.nth(1)).toContainText('Règles du site : réussi');
  await expect(checks.nth(2)).toContainText('propext, Classical.choice');
  const plan = sub.getByRole('region', { name: 'Ce qui sera envoyé' });
  await expect(plan).toContainText('compte ada-l');
  await expect(plan).toContainText('Faire une copie du dépôt google-deepmind/formal-conjectures sur votre compte');
  await expect(plan).toContainText('Ajouter le fichier FormalConjectures/ErdosProblems/123.lean dans ada-l/formal-conjectures');
  await expect(plan).toContainText('Ouvrir une demande publique sur google-deepmind/formal-conjectures');
  await expect(page.getByRole('article', { name: 'Erdős 9' }).getByRole('region', { name: 'Ce qui sera envoyé' })).toHaveCount(0);
  await expect(plan.getByRole('listitem')).toHaveCount(4);
  await expect(plan).toContainText('PUT https://api.github.com/repos/ada-l/formal-conjectures/contents/');
  // the failing one: explained and not sendable
  const bad = page.getByRole('article', { name: 'Erdős 9' });
  await expect(bad).toContainText('Règles du site : échoué');
  await expect(bad).toContainText('mot interdit : sorry');
  await expect(bad).toContainText('Axiomes (seulement les trois habituels) : pas encore vérifié');
  await expect(bad.getByRole('button', { name: 'Envoyer…' })).toBeDisabled();
  await axe(page, 'attack submissions');
  await shot(page, 'attaque-pretes');
  // « Envoyer… » asks first; « Annuler » sends nothing
  await sub.getByRole('button', { name: 'Envoyer…' }).click();
  const dlg = page.getByRole('dialog', { name: 'Envoyer à GitHub ?' });
  await expect(dlg).toContainText('avec le compte GitHub ada-l');
  await expect(dlg).toContainText('tout le monde pourra la lire');
  await page.keyboard.press('Escape');
  await expect(dlg).toHaveCount(0);
  await expect(sub.getByRole('button', { name: 'Envoyer…' })).toBeFocused();
  expect(m.calls.filter((c) => c.includes('/send'))).toEqual([]);
  await sub.getByRole('button', { name: 'Envoyer…' }).click();
  await dlg.getByRole('button', { name: 'Confirmer l’envoi' }).click();
  await expect(page.getByText('Envoyé. La demande est ouverte sur GitHub.')).toBeVisible();
  expect(m.calls.filter((c) => c.includes('/send'))).toEqual(['POST /api/attack/submissions/sub-1/send']);
  await expect(sub).toContainText('Envoyée, en attente de relecture');
  await expect(sub.getByRole('link', { name: 'Voir la demande sur GitHub' })).toHaveAttribute('href', /pull\/4242$/);
  await expect(sub.getByRole('button', { name: 'Envoyer…' })).toHaveCount(0);
  // live: the site merged it
  await emit(page, { type: 'attack.submission', submission: { ...m.subs[0], state: 'merged' } });
  await expect(sub).toContainText('Acceptée par le site');
  // discard the failing one
  await bad.getByRole('button', { name: 'Écarter…' }).click();
  await page.getByRole('dialog', { name: 'Écarter cette preuve ?' }).getByRole('button', { name: 'Écarter' }).click();
  await expect(bad).toHaveCount(0);
  expect(m.calls).toContain('POST /api/attack/submissions/sub-2/discard');
});

test('history: outcomes with reasons, spend per problem, filter by kind', async ({ page }) => {
  await mock(page, { st: status(), hist: HISTORY });
  await open(page, '/attaque');
  const h = page.getByRole('region', { name: 'Historique' });
  await expect(h.getByRole('listitem')).toHaveCount(3);
  await expect(h.getByRole('listitem').first()).toContainText('Rendu');
  await expect(h.getByRole('listitem').first()).toContainText('0,45 $ dépensés');
  await expect(h.getByRole('listitem').first()).toContainText('Pourquoi : stuck');
  await expect(h).toContainText('Cas particulier prouvé');
  await expect(h).toContainText('Total de cette liste : 2,45 $');
  await h.getByLabel('Type de problème').selectOption({ label: 'Problème ouvert facile' });
  await expect(h.getByRole('listitem')).toHaveCount(2);
  await expect(h).toContainText('Total de cette liste : 1,25 $');
  await expect(h.getByRole('link', { name: 'Erdős 7' })).toHaveCount(0);
});

test('settings: kinds, budget, parallel, difficulty, team notes off by default', async ({ page }) => {
  const m = await mock(page);
  await open(page, '/reglages/problemes-ouverts');
  await expect(page.getByRole('heading', { name: 'Problèmes ouverts', level: 2 })).toBeVisible();
  const kinds = page.getByRole('group', { name: 'Types de problèmes' });
  await expect(kinds.getByRole('checkbox')).toHaveCount(4);
  // the server's default: the three kinds its engine produces (statements to formalise come later, D69)
  await expect(kinds.getByRole('checkbox', { name: /Énoncé à formaliser/ })).not.toBeChecked();
  await kinds.getByRole('checkbox', { name: /Contre-exemple/ }).uncheck();
  await expect.poll(() => m.bodies.at(-1)).toEqual({ attack_kinds: ['known', 'open'] });
  await page.getByLabel('Budget par jour (dollars)').fill('2.5');
  await page.getByLabel('Budget par jour (dollars)').press('Tab');
  await expect.poll(() => m.bodies.at(-1)).toEqual({ attack_usd_per_day: 2.5 });
  await page.getByLabel('Problèmes en même temps').fill('1');
  await page.getByLabel('Problèmes en même temps').press('Tab');
  await expect.poll(() => m.bodies.at(-1)).toEqual({ attack_parallel: 1 });
  const notes = page.getByRole('checkbox', { name: 'Publier des notes pour l’équipe' });
  await expect(notes).not.toBeChecked();
  await expect(page.getByText('Désactivé par défaut.', { exact: false })).toBeVisible();
  await notes.check();
  await expect.poll(() => m.bodies.at(-1)).toEqual({ attack_post_notes: true });
  await axe(page, 'attack settings');
});

test('menu entry and Home card while it runs', async ({ page }) => {
  await mock(page, { st: status({ state: 'running', current: CURRENT, today: { usd: 1, cap: 5, taken: 2, proofs: 0, released: 0 } }) });
  await page.route((u) => u.pathname === '/api/state', async (r) => {
    const j = await (await r.fetch()).json() as { settings: J };
    j.settings = { ...j.settings, attack_enabled: true };
    await r.fulfill({ json: j });
  });
  await open(page, '/');
  const card = page.getByRole('region', { name: 'Problèmes ouverts' });
  await expect(card).toContainText('Madalean travaille sur 2 problèmes');
  await expect(card).toContainText('1,00 $ sur 5,00 $');
  await page.getByRole('button', { name: /menu/i }).first().click();
  const item = page.getByRole('menuitem', { name: 'Problèmes ouverts' });
  await expect(item).toBeVisible();
  await item.click();
  await expect(page).toHaveURL(/\/attaque$/);
});

test('phone and dark: cards stack, no sideways scroll, accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await mock(page, { st: status({ state: 'running', current: CURRENT, today: { usd: 2, cap: 5, taken: 3, proofs: 1, released: 1 } }), subs: [{ ...READY }], hist: HISTORY });
  await open(page, '/attaque');
  await expect(stateLine(page)).toHaveText('Madalean travaille sur 2 problèmes');
  const cards = page.getByRole('region', { name: 'En ce moment' }).getByRole('listitem');
  const [a, b] = [await cards.nth(0).boundingBox(), await cards.nth(1).boundingBox()];
  expect(b!.y).toBeGreaterThan(a!.y + a!.height - 1);         // stacked, not side by side
  await noHScroll(page);
  await axe(page, 'attack phone dark');
  await shot(page, 'attaque-telephone-sombre');
  await page.getByRole('article', { name: 'Erdős 123 : sommes de puissances' }).getByRole('button', { name: 'Envoyer…' }).click();
  await expect(page.getByRole('dialog', { name: 'Envoyer à GitHub ?' })).toBeVisible();
  await noHScroll(page);
});
