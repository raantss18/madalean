import { test, expect } from '@playwright/test';
import { open, api, axe } from './util';

test('keys: paste → saved and tested, never shown again → remove with confirmation', async ({ page }) => {
  await open(page, '/reglages/cles', { mode: 'research' });
  await axe(page, 'settings keys');
  const card = page.locator('li', { has: page.getByRole('heading', { name: 'Groq' }) });
  // Malformed key: refused before sending, with the reason.
  await card.getByLabel('Clé Groq').fill('not a key');
  await card.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(card.getByRole('status')).toContainText('ne ressemble pas');
  // Well-formed key → saved; the field is emptied; the card says « clé enregistrée ».
  await card.getByLabel('Clé Groq').fill('gsk_' + 'x'.repeat(40));
  await card.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(card.getByText('clé enregistrée', { exact: true })).toBeVisible();
  await expect(card.getByRole('status')).toContainText(/Clé enregistrée|Ça marche/);
  expect(await page.content()).not.toContain('x'.repeat(40));
  const models = await api<{ keys: Record<string, boolean> }>('GET', '/models');
  expect(models.keys['groq']).toBe(true);
  await card.getByRole('button', { name: 'Retirer la clé' }).click();
  await card.getByRole('button', { name: 'Retirer la clé' }).click();
  await expect(card.getByRole('status')).toContainText('Clé retirée');
  expect((await api<{ keys: Record<string, boolean> }>('GET', '/models')).keys['groq']).toBeFalsy();
});

test('models: mode and per-role choice are saved and shared', async ({ page }) => {
  await open(page, '/reglages/modeles', { mode: 'research' });
  await axe(page, 'settings models');
  await page.getByRole('radio', { name: /^Local/ }).check();
  await expect.poll(async () => (await api<{ settings: { mode: string } }>('GET', '/settings')).settings.mode).toBe('local');
  await page.getByRole('radio', { name: /^Automatique/ }).first().check();
  await expect.poll(async () => (await api<{ settings: { mode: string } }>('GET', '/settings')).settings.mode).toBe('auto');
  const sel = page.getByLabel(/^Prouver/);
  const opt = await sel.locator('option').nth(1).getAttribute('value');
  await sel.selectOption(opt!);
  await expect.poll(async () => (await api<{ settings: { prefer: Record<string, string> } }>('GET', '/settings')).settings.prefer['prove']).toBe(opt);
  await sel.selectOption('');
  // An out-of-range value is refused with a plain message and nothing changes.
  await page.getByText('Réglages avancés').click();
  await page.getByLabel('Essais de preuve').fill('999');
  await page.getByLabel('Essais de preuve').blur();
  await expect(page.getByText('Valeur entre 1 et 64.')).toBeVisible();
});

test('language switch: the whole interface goes English and back', async ({ page }) => {
  await open(page, '/reglages/langue', { mode: 'learn' });
  await page.getByRole('radio', { name: 'English' }).check();
  await expect(page.getByRole('heading', { name: 'Language' })).toBeVisible();
  await page.goto(`${process.env['MADALEAN_URL']}/`);
  await expect(page.getByRole('heading', { level: 1, name: 'What do you want to prove?' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await axe(page, 'home in English');
  await page.goto(`${process.env['MADALEAN_URL']}/reglages/langue`);
  await page.getByRole('radio', { name: 'Français' }).check();
  await expect(page.getByRole('heading', { name: 'Langue' })).toBeVisible();
});

test('devices (host): pairing code with countdown and QR, device list', async ({ page }) => {
  await open(page, '/reglages/appareils', { mode: 'research' });
  await page.getByRole('button', { name: 'Afficher un code' }).click();
  await expect(page.getByText(/Expire dans \d min/)).toBeVisible();
  await page.getByLabel('Adresse de cet ordinateur vue des autres appareils').fill('host.example.ts.net:10500');
  await expect(page.getByRole('img', { name: /QR code de liaison/ })).toBeVisible();
  await expect(page.getByText(/madalean:\/\/pair\?host=host\.example\.ts\.net:10500&code=\d{6}/)).toBeVisible();
  await axe(page, 'devices');
});
