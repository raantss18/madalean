import { test, expect } from '@playwright/test';
import { api, REMOTE, axe } from './util';

test('pairing on the remote listener: wrong code, then good code, then logout', async ({ browser }) => {
  const ctx = await browser.newContext({ locale: 'fr-FR' });
  const page = await ctx.newPage();
  await page.goto(REMOTE() + '/');
  // Unpaired: the app sends us to the pairing screen.
  await expect(page).toHaveURL(/\/pair/);
  await expect(page.getByRole('heading', { name: 'Relier cet appareil' })).toBeVisible();
  await axe(page, 'pairing');
  // No active code yet → plain message.
  await page.getByLabel('Code à 6 chiffres').fill('123456');
  await page.getByLabel('Nom de cet appareil').fill('Téléphone de test');
  await page.getByRole('button', { name: 'Relier' }).click();
  await expect(page.locator('#pair-err')).toContainText(/Aucun code en cours|Code incorrect/);
  // Host starts pairing; a wrong code is refused with a clear reason.
  const { code } = await api<{ code: string }>('POST', '/pairing/start', {});
  const wrong = code === '000000' ? '111111' : '000000';
  await page.getByLabel('Code à 6 chiffres').fill(wrong);
  await page.getByRole('button', { name: 'Relier' }).click();
  await expect(page.locator('#pair-err')).toContainText('Code incorrect');
  // Good code → the app opens, on the remote listener, with host-only settings locked.
  await page.getByLabel('Code à 6 chiffres').fill(code);
  await page.getByRole('button', { name: 'Relier' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Que voulez-vous prouver ?' })).toBeVisible();
  const devices = await api<{ devices: { name: string; id: string }[] }>('GET', '/devices');
  expect(devices.devices.some((d) => d.name === 'Téléphone de test')).toBe(true);
  await page.goto(REMOTE() + '/reglages/carnet');
  await expect(page.getByText(/modifiable seulement depuis l’ordinateur hôte/)).toBeVisible();
  await expect(page.getByLabel('Ouvrir le carnet aux appareils reliés')).toBeDisabled();
  // Unlink this device → back to pairing; the API now refuses it.
  await page.goto(REMOTE() + '/reglages/appareils');
  await page.getByRole('button', { name: 'Délier cet appareil' }).click();
  await expect(page).toHaveURL(/\/pair/);
  const r = await page.request.get(REMOTE() + '/api/state');
  expect(r.status()).toBe(401);
  await ctx.close();
});

test('revoking a device from the host sends the remote browser back to pairing', async ({ browser }) => {
  const ctx = await browser.newContext({ locale: 'fr-FR' });
  const page = await ctx.newPage();
  const { code } = await api<{ code: string }>('POST', '/pairing/start', {});
  await page.goto(REMOTE() + '/pair');
  await page.getByLabel('Code à 6 chiffres').fill(code);
  await page.getByLabel('Nom de cet appareil').fill('Tablette révoquée');
  await page.getByRole('button', { name: 'Relier' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Que voulez-vous prouver ?' })).toBeVisible();
  const devices = await api<{ devices: { name: string; id: string }[] }>('GET', '/devices');
  const dev = devices.devices.find((d) => d.name === 'Tablette révoquée')!;
  await api('DELETE', `/devices/${dev.id}`);
  // Next API call (navigation to settings triggers fetches) → 401 → pairing screen.
  await page.goto(REMOTE() + '/bibliotheque');
  await expect(page).toHaveURL(/\/pair/, { timeout: 15_000 });
  await ctx.close();
});
