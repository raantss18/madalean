// Produces docs/screenshots/v2/*.png at 360×780, 820×1180, 1440×900, light and dark, and checks there is no
// horizontal scroll. Run: npx playwright test --project=screens
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { open, api, REMOTE } from './util';

const OUT = new URL('../../docs/screenshots/v2/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const SIZES = [
  { name: 'phone', width: 360, height: 780 },
  { name: 'tablet', width: 820, height: 1180 },
  { name: 'desktop', width: 1440, height: 900 },
] as const;

async function provedId(): Promise<string> {
  const r = await api<{ dossiers: { id: string; status: string; parent_id: string }[] }>('GET', '/dossiers');
  return r.dossiers.find((d) => d.status === 'proved' && !d.parent_id)!.id;
}
async function noHScroll(page: Page, label: string) {
  const [sw, w] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  if (sw > w!) {
    const culprits = await page.evaluate(() => [...document.querySelectorAll('body *')].filter((el) => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map((el) => `${el.tagName}.${el.className}`));
    console.log(label, culprits);
  }
  expect(sw, `horizontal scroll on ${label}`).toBeLessThanOrEqual(w!);
}
async function shot(page: Page, name: string) {
  await page.waitForTimeout(400);
  await noHScroll(page, name);
  await page.screenshot({ path: `${OUT}${name}.png` });
}

for (const scheme of ['light', 'dark'] as const) {
  for (const s of SIZES) {
    test(`screens ${s.name} ${scheme}`, async ({ page }) => {
      await page.setViewportSize({ width: s.width, height: s.height });
      await page.emulateMedia({ colorScheme: scheme });
      const id = await provedId();
      await open(page, '/', { mode: 'learn' });
      await shot(page, `${s.name}-${scheme}-home`);
      await page.goto(`${process.env['MADALEAN_URL']}/d/${id}/lean`);
      await expect(page.locator('.cm-content').first()).toBeVisible();
      await shot(page, `${s.name}-${scheme}-lean`);
      await page.goto(`${process.env['MADALEAN_URL']}/d/${id}/preuve`);
      await expect(page.getByRole('heading', { name: /Preuve vérifiée/ })).toBeVisible();
      await shot(page, `${s.name}-${scheme}-proof-learn`);
      await page.evaluate(() => localStorage.setItem('madalean.density', 'research'));
      await page.reload();
      await expect(page.getByRole('heading', { name: /Preuve vérifiée/ })).toBeVisible();
      await shot(page, `${s.name}-${scheme}-proof-research`);
      await page.goto(`${process.env['MADALEAN_URL']}/reglages/cles`);
      await expect(page.getByRole('heading', { name: 'Anthropic (Claude)' })).toBeVisible();
      await shot(page, `${s.name}-${scheme}-settings-keys`);
      await page.goto(`${process.env['MADALEAN_URL']}/reglages/modeles`);
      await expect(page.getByText('Modèle par tâche')).toBeVisible();
      await shot(page, `${s.name}-${scheme}-settings-models`);
      if (s.name !== 'tablet') {
        await page.goto(`${REMOTE()}/`);
        await expect(page.getByRole('heading', { name: 'Relier cet appareil' })).toBeVisible();
        await shot(page, `${s.name}-${scheme}-pair`);
      }
    });
  }
}

test('screens: live parallel work and devices (desktop light)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/', { mode: 'research' });
  const a = await api<{ dossier: { id: string } }>('POST', '/dossiers', { problem: 'Montrer que la somme de deux entiers pairs est paire.' });
  await api('POST', '/dossiers', { problem: 'Pour tout réel x, x^2 + 1 > 0.' });
  await api('POST', '/dossiers', { statement: 'theorem t (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by sorry' });
  await page.goto(`${process.env['MADALEAN_URL']}/d/${a.dossier.id}`);
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: /Activité/ }).click();
  await shot(page, 'desktop-light-parallel-activity');
  await page.keyboard.press('Escape');
  await page.goto(`${process.env['MADALEAN_URL']}/d/${a.dossier.id}/preuve`);
  await page.waitForTimeout(4000);
  await shot(page, 'desktop-light-proof-streaming');
  await page.goto(`${process.env['MADALEAN_URL']}/reglages/appareils`);
  await page.getByRole('button', { name: 'Afficher un code' }).click();
  await page.getByLabel('Adresse de cet ordinateur vue des autres appareils').fill('nitro.tail1234.ts.net:10500');
  await page.getByLabel('Adresse de cet ordinateur vue des autres appareils').blur();
  await shot(page, 'desktop-light-devices-pairing');
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(`${process.env['MADALEAN_URL']}/activite`);
  await shot(page, 'phone-light-activity');
  for (const d of (await api<{ active: { dossier_id: string }[] }>('GET', '/jobs')).active) await api('POST', `/dossiers/${d.dossier_id}/stop`, {});
});

// Research screens (phase 2).
for (const [size, scheme] of [['desktop', 'light'], ['desktop', 'dark'], ['phone', 'light'], ['tablet', 'light']] as const) {
  test(`screens research ${size} ${scheme}`, async ({ page }) => {
    const s = SIZES.find((x) => x.name === size)!;
    await page.setViewportSize({ width: s.width, height: s.height });
    await page.emulateMedia({ colorScheme: scheme });
    const projects = (await api<{ projects: { id: string; title: string }[] }>('GET', '/projects')).projects;
    const research = projects.find((p) => /Recherche/.test(p.title))!.id;
    const examples = projects.find((p) => /Exemples/.test(p.title))!.id;
    const U = process.env['MADALEAN_URL'];
    await open(page, '/projet', { mode: 'research' });
    await page.evaluate((pid) => localStorage.setItem('madalean.project', pid), research);
    await page.reload();
    await shot(page, `${size}-${scheme}-research-hub`);
    await page.goto(`${U}/sources`);
    await expect(page.getByRole('link', { name: /A note on parity/ })).toBeVisible();
    await shot(page, `${size}-${scheme}-sources`);
    await page.getByRole('link', { name: /A note on parity/ }).click();
    await expect(page.locator('.chunk').first()).toBeVisible();
    await page.getByLabel('Votre question').fill('Pourquoi la somme de deux entiers pairs est-elle paire ?');
    await page.getByRole('button', { name: 'Demander' }).click();
    await expect(page.locator('.qa .answer').first()).toBeVisible({ timeout: 30_000 });
    await shot(page, `${size}-${scheme}-reader-qa`);
    if (size === 'desktop') {
      await page.getByRole('radio', { name: 'PDF' }).check({ force: true });
      await expect(page.locator('.pdf canvas').first()).toBeVisible();
      await page.waitForTimeout(1200);
      await shot(page, `${size}-${scheme}-reader-pdf`);
    }
    await page.goto(`${U}/blueprint`);
    await expect(page.getByRole('list', { name: 'Légende des états' })).toBeVisible();
    if (size !== 'phone') await page.locator('svg .gn').filter({ hasText: 'Lemma 1.2' }).first().click();
    await shot(page, `${size}-${scheme}-blueprint`);
    await page.goto(`${U}/article`);
    await expect(page.locator('.cm-editor').first()).toBeVisible();
    await shot(page, `${size}-${scheme}-article`);
    await page.evaluate((pid) => localStorage.setItem('madalean.project', pid), examples);
    await page.reload();
    const notes = (await api<{ notes: { id: string; title: string }[] }>('GET', `/notes?project=${examples}`)).notes;
    await page.goto(`${U}/notes/${notes.find((n) => /Parité/.test(n.title))!.id}`);
    await expect(page.locator('.cm-content').first()).toBeVisible();
    await shot(page, `${size}-${scheme}-notes`);
    await page.goto(`${U}/graphe`);
    await page.waitForTimeout(600);
    await shot(page, `${size}-${scheme}-graph`);
    const conj = (await api<{ conjectures: { id: string; status: string }[] }>('GET', `/conjectures?project=${examples}`)).conjectures.find((c) => c.status === 'refuted')!;
    await page.goto(`${U}/conjectures/${conj.id}`);
    await expect(page.locator('.counter')).toBeVisible();
    await shot(page, `${size}-${scheme}-conjecture`);
    const plan = (await api<{ dossiers: { id: string; title: string }[] }>('GET', '/dossiers')).dossiers.find((d) => /carré d'un entier pair/.test(d.title))!;
    await page.goto(`${U}/d/${plan.id}/plan`);
    await expect(page.getByRole('heading', { name: 'Plan de preuve' })).toBeVisible();
    await shot(page, `${size}-${scheme}-plan`);
    await page.goto(`${U}/aide/notes`);
    await expect(page.locator('.manual h1')).toBeVisible();
    await shot(page, `${size}-${scheme}-help`);
    await page.goto(`${U}/publier`);
    await shot(page, `${size}-${scheme}-publish`);
    await page.goto(`${U}/reglages/mises-a-jour`);
    await expect(page.getByRole('heading', { name: 'Madalean lui-même' })).toBeVisible();
    await shot(page, `${size}-${scheme}-settings-updates`);
  });
}
