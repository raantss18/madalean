// S-BH (D64, D66): the dossier as one chronological thread with a separable pane. The server side of the contract is
// another session's work: the new fields are mocked on top of real demo dossiers (GET /dossiers/:id), the POSTs are
// answered here and their bodies checked.
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, api, axe } from './util';

type D = Record<string, unknown> & { id: string };
type One = { dossier: D; job: unknown; children: unknown[] };
const now0 = 1_764_000_000;
const ev = (kind: string, t: number, text: string, x: Record<string, unknown> = {}) =>
  ({ kind, text, t: now0 + t, ref: null, stage: '', model: 'anthropic:claude-sonnet', key: '', params: {}, job: 'j-mock', run: 'r1', phase: '', attempt: 0, ...x });
const version = (code: string, x: Record<string, unknown> = {}) => ({ code, t: now0, source: 'ai', ok: true, parent: null, note: '', model: 'anthropic:claude-sonnet', meta: {}, ...x });
const CHI = 'theorem chromatic_number_plane : chromaticNumber unitDistancePlane = 6 := by sorry';
const current = (statement: string) => ({ statement, proof: '', explanation: '', statement_notes: '', informal_proof: '', proof_is_current: false });
const MEANING = { id: 'g-m', kind: 'meaning', state: 'pending', version: 0, t: now0 + 60, meaning: {
  restated: 'Le plus petit nombre de couleurs pour colorier $\\mathbb{R}^2$ sans que deux points à distance $1$ aient la même couleur vaut $6$.',
  objects: [{ name: 'plan', meaning: 'le plan euclidien $\\mathbb{R}^2$' }, { name: 'nombre chromatique', meaning: 'celui du graphe des distances unité' }],
  hypotheses: [], claim: '$\\chi(\\mathbb{R}^2) = 6$', known_status: 'open', status_confidence: 'cited',
  status_sources: [{ title: 'de Grey, The chromatic number of the plane is at least 5', url: 'https://arxiv.org/abs/1804.02385', quote: 'We present a family of finite unit-distance graphs in the plane that are not 4-colourable.' }],
  known_results: [{ id: 'k1', title: 'Au moins 5 couleurs', statement: '$\\chi \\ge 5$', source: 'de Grey 2018' }, { id: 'k2', title: 'Au plus 7 couleurs', statement: '$\\chi \\le 7$', source: 'Isbell' }],
  questions: ['Voulez-vous les bornes connues $5 \\le \\chi \\le 7$ plutôt que l’égalité ?'] } };
const statementGate = (id: string, code: string, extra: object[] = []) => ({ id, kind: 'statement', state: 'pending', version: 0, t: now0 + 90, statement: { chosen: 0, agreement: extra.length ? 'different' : 'single',
  candidates: [{ version: 0, code, back_translation: 'Le graphe des distances unité du plan a pour nombre chromatique 6.', model: 'anthropic:claude-sonnet', objects_missing: [], verdict: 'doubtful', reasons: ['Égalité non démontrée à ce jour.'] }, ...extra] } });

async function create(title: string, x: Record<string, unknown> = {}): Promise<string> {
  return (await api<{ dossier: { id: string } }>('POST', '/dossiers', { problem: 'Le nombre chromatique du plan est 6', title, start: false, ...x })).dossier.id;
}
/** GET /dossiers/:id answers the real dossier with `patch` on top; `job` replaces the running job. */
async function mock(page: Page, id: string, patch: () => Record<string, unknown>, job: () => unknown = () => null): Promise<void> {
  const real = await api<One>('GET', `/dossiers/${id}`);
  await page.route((u) => u.pathname === `/api/dossiers/${id}`, (r) => r.request().method() !== 'GET' ? r.continue()
    : r.fulfill({ json: { ...real, dossier: { ...real.dossier, ...patch() }, job: job() } }));
  await page.route(/\/api\/jobs\/j-mock/, (r) => r.fulfill({ json: { segments: [], seq: 0 } }));
}
const mockJob = (id: string, x: Record<string, unknown> = {}) => ({ id: 'j-mock', dossier_id: id, plan: [], mode: 'auto', strategy: 'auto', user: true, state: 'running', stage: 'proof', waiting: '', created: now0, started: now0, ended: null, attempts: [], done_stages: [], summary: {}, error: '', ...x });
const longEvents = () => [ev('user', 0, 'Le nombre chromatique du plan est 6', { model: '' }), ev('understood', 10, 'Compris ainsi\n$\\chi(\\mathbb{R}^2)=6$', { phase: 'understand' }),
  ev('statement', 20, 'Traduit en Lean.', { phase: 'translate', ref: 0 }),
  ...Array.from({ length: 70 }, (_, i) => ev(i % 7 === 6 ? 'error' : 'info', 30 + i * 12, `Événement ${i + 1}`, { phase: 'prove', attempt: Math.floor(i / 7) + 1 }))];
const SHOTS = process.env['ONE_THREAD_SHOTS'];
async function shot(page: Page, name: string) { if (SHOTS) { mkdirSync(SHOTS, { recursive: true }); await page.screenshot({ path: `${SHOTS}/${name}.png` }); } }
const steps = (page: Page) => page.getByRole('region', { name: 'Avancement du dossier' });
async function noHScroll(page: Page) { expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0); }

test('chromatic case: meaning gate → correction → statement gate → approval of several known results', async ({ page }) => {
  const id = await create('Nombre chromatique du plan');
  const kids = [await create('Au moins 5 couleurs', { parent_id: id }), await create('Au plus 7 couleurs', { parent_id: id })];
  let gate: Record<string, unknown> = MEANING;
  const kidGate: Record<string, unknown> = { [kids[0]!]: statementGate('k-0', 'theorem chi_ge : 5 ≤ χ := by sorry'), [kids[1]!]: statementGate('k-1', 'theorem chi_le : χ ≤ 7 := by sorry') };
  const base = { events: [ev('user', 0, 'Le nombre chromatique du plan est 6', { model: '' }), ev('understood', 50, 'Compris ainsi\nχ = 6', { phase: 'understand' })], now: null };
  await mock(page, id, () => ({ ...base, gate, ...(gate['kind'] === 'statement' ? { statements: [version(CHI), version(CHI)], cur_statement: 0, current: current(CHI) } : {}) }));
  for (const k of kids) await mock(page, k, () => ({ gate: kidGate[k], now: null }));
  // the summaries say it too (the real server's children have no gate: only their full dossiers are mocked above)
  await page.route((u) => u.pathname === '/api/state', async (r) => {
    const res = await r.fetch();
    const j = await res.json() as { dossiers: { id: string; gate?: unknown }[] };
    for (const c of j.dossiers) if (kidGate[c.id]) c.gate = kidGate[c.id];
    await r.fulfill({ json: j });
  });
  const bodies: { url: string; body: Record<string, unknown> }[] = [];
  await page.route(/\/api\/dossiers\/[^/]+\/(gate|report)$|\/api\/dossiers\/gates\/approve$/, (r) => {
    bodies.push({ url: new URL(r.request().url()).pathname, body: r.request().postDataJSON() as Record<string, unknown> });
    if (r.request().url().endsWith('/gates/approve')) for (const k of kids) kidGate[k] = { ...(kidGate[k] as object), state: 'approved' };
    return r.fulfill({ json: { ok: true } });
  });
  await open(page, `/d/${id}`, { mode: 'research' });

  // the header says whose turn it is, and jumps there
  await expect(steps(page).getByRole('listitem').first()).toContainText('vous attend');
  await expect(steps(page)).toContainText('Madalean attend votre réponse : est-ce bien ce que vous voulez dire ?');
  const card = page.getByRole('region', { name: 'Est-ce bien ce que vous voulez dire ?' });
  await steps(page).getByRole('button', { name: 'Répondre' }).click();
  await expect(card).toBeFocused();
  await expect(card).toContainText('Problème ouvert');
  await expect(card.locator('blockquote')).toContainText('not 4-colourable');
  await expect(card).toContainText('avec une référence citée');
  await expect(card.getByText('Au plus 7 couleurs')).toBeVisible();
  await expect(page.getByText('Prouvé', { exact: true })).toHaveCount(0);
  await axe(page, 'meaning gate');
  await shot(page, 'desktop-meaning');
  await card.getByRole('button', { name: 'Corriger' }).click();
  await card.getByLabel('Que faut-il corriger ?').fill('Je veux les bornes connues');
  gate = { ...statementGate('g-s', CHI, [{ version: 1, code: CHI.replace('= 6', '≤ 6'), back_translation: 'Six couleurs suffisent.', model: 'mistral:m', objects_missing: ['égalité'], verdict: 'unknown', reasons: [] }]), t: now0 + 120 };
  await card.getByRole('button', { name: 'Envoyer la correction' }).click();
  await expect.poll(() => bodies[0]).toEqual({ url: `/api/dossiers/${id}/gate`, body: { gate_id: 'g-m', action: 'edit', text: 'Je veux les bornes connues' } });

  // statement: two candidates side by side, « Lean comprend le code » is neither faithful nor proved
  const st = page.getByRole('region', { name: 'L’énoncé Lean dit-il bien la même chose ?' });
  await expect(st.getByRole('article')).toHaveCount(2);
  await expect(st).toContainText('pas qu’il dit la même chose que vous, ni qu’il est prouvé');
  await expect(st).toContainText('Objets de votre texte absents du code : égalité');
  await expect(st.getByText('Lean comprend le code', { exact: true })).toHaveCount(2);
  await expect(st.getByText('pas encore prouvé')).toHaveCount(2);
  await expect(st).toContainText('Les traductions ne disent pas la même chose');
  await axe(page, 'statement gate');
  await shot(page, 'desktop-statement');
  // nothing can be proved from the pane meanwhile
  await page.getByRole('tab', { name: 'Lean', exact: true }).click();
  await expect(page.getByText('La question est posée dans le fil : répondez-y avant de prouver.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Prouver cet énoncé' })).toHaveCount(0);

  // « Mal compris » on the statement
  await st.getByRole('button', { name: 'Mal compris' }).click();
  const dlg = page.getByRole('dialog', { name: 'Signaler une mauvaise interprétation' });
  await expect(dlg.getByRole('button', { name: 'Signaler' })).toBeDisabled();
  await dlg.getByRole('radio', { name: 'Ce n’est pas ce que j’affirme' }).check();
  await dlg.getByLabel('Expliquez (facultatif)').fill('égalité, pas inégalité');
  await axe(page, 'report dialog');
  await dlg.getByRole('button', { name: 'Signaler' }).click();
  await expect.poll(() => bodies[1]).toEqual({ url: `/api/dossiers/${id}/report`, body: { target: 'statement', ref: 0, reason: 'wrong_claim', text: 'égalité, pas inégalité' } });
  await expect(page.locator('.rep')).toContainText('Ce n’est pas ce que j’affirme');

  // approve with the second candidate
  await st.getByRole('radio', { name: 'Prendre cette version' }).nth(1).check();
  gate = { ...gate, state: 'approved' };
  await st.getByRole('button', { name: 'Approuver' }).click();
  await expect.poll(() => bodies[2]?.body).toEqual({ gate_id: 'g-s', action: 'approve', candidate: 1 });
  await expect(st.getByRole('button', { name: 'Approuver' })).toHaveCount(0);

  // sub-dossiers: in the thread with their state; one card approves both
  await expect(page.getByRole('article', { name: 'Sous-dossier : Au plus 7 couleurs' })).toContainText('attend votre accord');
  const batch = page.getByRole('region', { name: 'Approuver plusieurs énoncés' });
  await expect(batch.getByRole('checkbox')).toHaveCount(2);
  await shot(page, 'desktop-batch');
  await batch.getByRole('button', { name: 'Approuver les 2 énoncés cochés' }).click();
  await expect.poll(() => (bodies[3]?.body['items'] as unknown[] | undefined)?.length).toBe(2);
  await expect(batch).toHaveCount(0);
});

test('a stale question shows the current one', async ({ page }) => {
  const id = await create('Question périmée');
  let gate = MEANING;
  await mock(page, id, () => ({ gate, now: null }));
  await page.route(/\/gate$/, (r) => { gate = { ...MEANING, id: 'g-new', t: now0 + 99 }; return r.fulfill({ status: 409, json: { error: 'stale_gate' } }); });
  await open(page, `/d/${id}`, { mode: 'research' });
  await page.getByRole('button', { name: 'Approuver' }).click();
  await expect(page.getByText('Cette question a changé entre-temps')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approuver' })).toBeEnabled();
});

test('long thread while proving: one now line, live output in place, filters, window, jump to latest', async ({ page }) => {
  const id = await create('Long travail');
  const nowv = { phase: 'prove', run: 'r1', attempt: 11, activity: 'stage.proof', model: 'mistral:codestral', started: Date.now() / 1000 - 75, waiting: '', side: [{ phase: 'literature', activity: 'stage.literature' }] };
  await mock(page, id, () => ({ events: longEvents(), statements: [version(CHI)], cur_statement: 0, current: current(CHI), status: 'proving', now: nowv, gate: null }), () => mockJob(id));
  await open(page, `/d/${id}`, { mode: 'research' });
  const head = steps(page);
  await expect(head.getByRole('listitem').nth(2)).toContainText('en cours');
  await expect(head.getByRole('listitem').nth(3)).toContainText('pas commencé');
  await expect(head.locator('.phase-txt')).toHaveCount(1);
  await expect(head).toContainText('Recherche de preuve');
  await expect(head).toContainText('essai 11');
  await expect(head).toContainText('codestral');
  await expect(head).toContainText(/depuis 1 min/);
  await expect(head).toContainText('en même temps : recherche dans la littérature');
  await expect(head.getByRole('button', { name: 'Arrêter' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Arrêter' })).toHaveCount(1);
  // live output: once, at the end of the thread
  await page.evaluate(() => (window as unknown as { __madalean: { streams: { token: (...a: unknown[]) => void } } }).__madalean.streams.token('j-mock', 'proof', 0, 'text', 'nlinarith [sq_nonneg x]'));
  await expect(page.getByRole('log')).toHaveCount(1);
  await expect(page.getByRole('log')).toContainText('nlinarith');
  // opened on the latest; 60 items shown, the rest on demand
  await expect(page.locator('.it', { hasText: 'Événement 70' })).toBeVisible();
  await expect(page.locator('.first', { hasText: /^Événement 2$/ })).toHaveCount(0);
  await expect(page.locator('details.attempt')).not.toHaveCount(0);
  await axe(page, 'long thread');
  await shot(page, 'desktop-live');
  await page.getByRole('button', { name: /Afficher 13 événements plus anciens/ }).click();
  await expect(page.locator('.it', { hasText: 'Traduit en Lean.' })).toBeVisible();
  // reading above: new items do not steal the scroll, the button brings back
  await page.evaluate(() => window.scrollTo(0, 0));
  const y = await page.evaluate(() => window.scrollY);
  await page.evaluate((did) => { const a = (window as unknown as { __madalean: { m: { full: Record<string, { events: unknown[] }> } } }).__madalean; a.m.full[did]!.events.push({ ...(a.m.full[did]!.events.at(-1) as object), kind: 'info', attempt: 0, text: 'Tout nouveau', t: Date.now() / 1000 }); }, id);
  const latest = page.getByRole('button', { name: /Aller au plus récent/ });
  await expect(latest).toContainText('1 nouveau');
  expect(await page.evaluate(() => window.scrollY)).toBe(y);
  await latest.click();
  await expect(page.locator('.it', { hasText: 'Tout nouveau' }).last()).toBeInViewport();
  await expect(latest).toHaveCount(0);
  // filters
  await page.getByRole('group', { name: 'Filtrer le fil' }).getByRole('button', { name: /Vos demandes/ }).click();
  await expect(page.locator('.ev.user')).toHaveCount(1);
  await expect(page.locator('.thread .it')).toHaveCount(0);
  await page.getByRole('button', { name: /Contrôles et erreurs/ }).click();
  await expect(page.locator('.card.error')).toHaveCount(10);
});

test('failure: what was tried, the last cause and what can be done', async ({ page }) => {
  const id = await create('Échec expliqué');
  const a = (i: number) => ({ index: i, stage: 'proof', kind: 'initial', status: 'rejected', summary: '', errors_text: `unsolved goals ${i}`, code: 'x', raw: '', model: `mistral:m${i}`, gen_seconds: 2, compile_seconds: 1, tokens: 1, finish: '', t: now0 + 30 + i });
  await mock(page, id, () => ({ events: longEvents().slice(0, 3), statements: [version(CHI)], cur_statement: 0, current: current(CHI), status: 'failed' }), () => mockJob(id, { state: 'failed', error: 'no_proof', attempts: [a(0), a(1)] }));
  await open(page, `/d/${id}`, { mode: 'research' });
  await expect(steps(page).getByRole('listitem').nth(2)).toContainText('échec');
  await steps(page).getByRole('button', { name: 'Pourquoi, et que faire' }).click();
  const next = page.getByRole('region', { name: 'Pas de preuve pour l’instant' });
  await expect(next).toBeFocused();
  await expect(next).toContainText('2 essai(s) avec m0, m1');
  await expect(next).toContainText('unsolved goals 1');
  await expect(next.getByRole('button', { name: 'Réessayer' })).toBeVisible();
  await expect(page.locator('details.attempt')).toHaveCount(2);
  await axe(page, 'failure');
  await shot(page, 'desktop-failure');
});

test('the pane: old addresses, keyboard resize, hide, split column and own window (synced), put back', async ({ page, context }) => {
  const id = await create('Volet');
  for (const [p, tab] of [['enonce', 'Énoncé'], ['lean', 'Lean'], ['preuve', 'Preuve'], ['plan', 'Sous-lemmes'], ['litterature', 'Littérature'], ['versions', 'Versions']] as const) {
    await open(page, `/d/${id}/${p}`, { mode: 'research' });
    await expect(page.getByRole('tab', { name: tab, exact: true })).toHaveAttribute('aria-selected', 'true');
  }
  const sep = page.getByRole('separator', { name: 'Largeur du volet' });
  const w = Number(await sep.getAttribute('aria-valuenow'));
  await sep.focus();
  await page.keyboard.press('ArrowLeft');
  await expect(sep).toHaveAttribute('aria-valuenow', String(w + 3));
  // column
  await page.getByRole('tab', { name: 'Énoncé', exact: true }).click();
  await page.getByRole('button', { name: 'Séparer' }).click();
  await page.getByRole('menuitem', { name: 'Dans une colonne' }).click();
  await expect(page.getByRole('region', { name: 'Énoncé', exact: true })).toContainText('Le nombre chromatique du plan est 6');
  await expect(page.getByRole('tab', { name: 'Lean', exact: true })).toHaveAttribute('aria-selected', 'true');
  await axe(page, 'split column');
  await page.getByRole('region', { name: 'Énoncé', exact: true }).getByRole('button', { name: 'Remettre' }).click();
  await expect(page.getByRole('region', { name: 'Énoncé', exact: true })).toHaveCount(0);
  // window
  await page.getByRole('tab', { name: 'Énoncé', exact: true }).click();
  const popup = context.waitForEvent('page');
  await page.getByRole('button', { name: 'Séparer' }).click();
  await page.getByRole('menuitem', { name: 'Dans sa fenêtre' }).click();
  const win = await popup;
  await expect(win).toHaveURL(new RegExp(`/d/${id}/enonce\\?solo=1`));
  await expect(win.getByRole('heading', { level: 1 })).toContainText('Énoncé — Volet');
  await expect(win.locator('.topbar')).toHaveCount(0);
  await expect(page.getByText('« Énoncé » est ouvert dans sa propre fenêtre.')).toBeVisible();
  await axe(win, 'solo window');
  await api('PATCH', `/dossiers/${id}`, { problem: 'Texte changé ailleurs' });                // the WebSocket keeps it in sync
  await expect(win.getByText('Texte changé ailleurs')).toBeVisible();
  const closed = win.waitForEvent('close');
  await page.getByRole('button', { name: 'Remettre' }).click();
  await closed;
  await expect(page.locator('.theorem').first()).toContainText('Texte changé ailleurs');
  // hidden, remembered after a reload
  await page.getByRole('button', { name: 'Masquer le volet' }).click();
  await expect(page.locator('#pane-show')).toBeFocused();
  await page.goto(`${process.env['MADALEAN_URL']}/d/${id}`);
  await expect(page.locator('#pane-show')).toBeVisible();
  await expect(page.getByRole('tablist')).toHaveCount(0);
  await page.locator('#pane-show').click();
  await expect(page.getByRole('tablist')).toBeVisible();
});

test('a sub-dossier opens in place and in the pane; « En parler » sets what the request is about', async ({ page }) => {
  const id = await create('Parent');
  const kid = await create('Enfant', { parent_id: id, problem: 'Borne inférieure' });
  await mock(page, id, () => ({ events: longEvents().slice(0, 3), statements: [version(CHI)], cur_statement: 0, current: current(CHI) }));
  await open(page, `/d/${id}`, { mode: 'research' });
  const card = page.getByRole('article', { name: 'Sous-dossier : Enfant' });
  await card.getByRole('button', { name: 'Ouvrir ici' }).click();
  await expect(card).toContainText('Borne inférieure');
  await card.getByRole('button', { name: 'Dans le volet' }).click();
  const pane = page.getByRole('complementary', { name: 'Références du dossier' });
  await expect(pane).toContainText('Sous-dossier : Enfant');
  await expect(pane).toContainText('Borne inférieure');
  await pane.getByRole('button', { name: 'Revenir au dossier' }).click();
  await expect(pane).not.toContainText('Sous-dossier : Enfant');
  await expect(card.getByRole('link', { name: 'Ouvrir ce dossier' })).toHaveAttribute('href', `/d/${kid}`);
  await page.getByRole('button', { name: 'En parler : Traduit en Lean.' }).click();
  await expect(page.getByLabel('À propos de')).toHaveValue('statement');
  await expect(page.getByRole('textbox', { name: 'Une précision, une correction ?' })).toBeFocused();
});

test('an old dossier (no new fields) shows as one thread', async ({ page }) => {
  const d = (await api<{ dossiers: { id: string; title: string; status: string }[] }>('GET', '/dossiers')).dossiers.find((x) => x.status === 'proved' && /somme de deux entiers pairs/i.test(x.title))!;
  await open(page, `/d/${d.id}`, { mode: 'research' });
  await expect(steps(page).getByRole('listitem').nth(3)).toContainText('fait');
  await expect(steps(page)).toContainText('Lean a vérifié la preuve');
  await expect(page.locator('.ev.user').first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Traduire en Lean' }).first()).toBeVisible();
  await shot(page, 'desktop-old');
});

for (const scheme of ['light', 'dark'] as const) {
  test(`phone (${scheme}): thread full width, pane as a sheet, axe`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, colorScheme: scheme, locale: 'fr-FR', reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    const id = await create(`Téléphone ${scheme}`);
    await mock(page, id, () => ({ events: longEvents().slice(0, 12), gate: MEANING, now: null }));
    await open(page, `/d/${id}`, { mode: 'research' });
    await expect(page.getByRole('region', { name: 'Est-ce bien ce que vous voulez dire ?' })).toBeVisible();
    await noHScroll(page);
    await axe(page, `phone thread ${scheme}`);
    await shot(page, `phone-${scheme}`);
    await page.locator('#pane-show').click();
    const sheet = page.getByRole('dialog', { name: 'Références du dossier' });
    await expect(sheet).toBeVisible();
    await expect(page.locator('#pane-close')).toBeFocused();
    await noHScroll(page);
    await axe(page, `phone sheet ${scheme}`);
    await shot(page, `phone-sheet-${scheme}`);
    await page.keyboard.press('Escape');
    await expect(sheet).toHaveCount(0);
    // an old address opens its tab as a sheet
    await page.goto(`${process.env['MADALEAN_URL']}/d/${id}/lean`);
    await expect(sheet.getByRole('tab', { name: 'Lean', exact: true })).toHaveAttribute('aria-selected', 'true');
    await ctx.close();
  });
}

test('dark desktop: statement gate, axe', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  const id = await create('Sombre');
  await mock(page, id, () => ({ events: longEvents().slice(0, 3), statements: [version(CHI)], cur_statement: 0, current: current(CHI), gate: statementGate('g-d', CHI), now: null }));
  await open(page, `/d/${id}`, { mode: 'research' });
  await expect(page.getByRole('region', { name: 'L’énoncé Lean dit-il bien la même chose ?' })).toBeVisible();
  await axe(page, 'statement gate dark');
  await shot(page, 'desktop-dark');
});
