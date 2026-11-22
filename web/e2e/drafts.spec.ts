// S-AP: what is typed in a field that SENDS survives leaving the screen and a reload, until it is sent
// (per-device drafts, lib/ui/drafts.svelte.ts): Calcul « Demande », grounded Q&A, Lean correction, new conjecture.
import { test, expect, type Page } from '@playwright/test';
import { open, api } from './util';

const draftKeys = (page: Page, prefix: string) =>
  page.evaluate((p) => Object.keys(localStorage).filter((k) => k.startsWith(`madalean.draft.${p}`)), prefix);

test('Calcul « Demande »: kept when leaving the screen and after a reload, dropped once sent', async ({ page }) => {
  const pid = (await api<{ project: { id: string } }>('POST', '/projects', { title: 'Brouillons S-AP', description: '' })).project.id;
  await api('POST', `/calcul/${pid}/docs/calcul/cells`, { type: 'ask' });
  await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, pid);
  await open(page, '/calcul', { mode: 'research' });
  const prompt = page.getByRole('textbox', { name: 'Demande de la cellule 1' });
  await prompt.fill('factorise x^4+4 sur Z[i]');
  // leave the screen inside the app, come back
  await page.getByRole('link', { name: 'Notes' }).first().click();
  await expect(page).toHaveURL(/\/notes/);
  await page.goBack();
  await expect(page.getByRole('textbox', { name: 'Demande de la cellule 1' })).toHaveValue('factorise x^4+4 sur Z[i]');
  // reload
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Demande de la cellule 1' })).toHaveValue('factorise x^4+4 sur Z[i]');
  expect(await draftKeys(page, `calcul.${pid}.`)).toHaveLength(1);
  // send: the request becomes the cell's own (server side), the draft goes
  const asked = page.waitForResponse((r) => /\/cells\/[^/]+\/ask$/.test(r.url()) && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Écrire le code' }).first().click();
  await asked;
  await expect.poll(() => draftKeys(page, `calcul.${pid}.`)).toHaveLength(0);
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Demande de la cellule 1' })).toHaveValue('factorise x^4+4 sur Z[i]');   // the cell's prompt now
  await api('DELETE', `/projects/${pid}`);
});

test('grounded question, Lean correction and new conjecture: kept after a reload; the question is dropped once asked', async ({ page }) => {
  const projects = (await api<{ projects: { id: string; title: string }[] }>('GET', '/projects')).projects;
  const research = projects.find((p) => /Recherche/.test(p.title))!.id;
  await page.addInitScript((id) => { localStorage.setItem('madalean.project', id); }, research);

  // Q&A in the reader of a source
  await open(page, '/sources', { mode: 'research' });
  await page.getByRole('link', { name: /A note on parity/ }).click();
  await expect(page.locator('.chunk').first()).toBeVisible();
  await page.getByLabel('Votre question').fill('Pourquoi la somme de deux pairs est-elle paire ?');
  await page.reload();
  await expect(page.getByLabel('Votre question')).toHaveValue('Pourquoi la somme de deux pairs est-elle paire ?');
  await page.getByRole('button', { name: 'Demander' }).click();
  await expect(page.getByLabel('Votre question')).toHaveValue('');
  await expect.poll(() => draftKeys(page, 'qa.')).toHaveLength(0);
  await page.reload();
  await expect(page.getByLabel('Votre question')).toHaveValue('');

  // the « Corriger l'énoncé… » request: the field opens again with the text
  const dossiers = (await api<{ dossiers: { id: string; status: string; parent_id: string }[] }>('GET', '/dossiers')).dossiers;
  const proved = dossiers.find((d) => d.status === 'proved' && !d.parent_id)!.id;
  await page.goto(`${process.env['MADALEAN_URL']}/d/${proved}/lean`);
  await page.getByRole('button', { name: 'Corriger l’énoncé…' }).click();
  await page.getByLabel('Que faut-il changer ?').fill('n doit être un entier naturel');
  await page.reload();
  await expect(page.getByLabel('Que faut-il changer ?')).toHaveValue('n doit être un entier naturel');
  await page.getByLabel('Que faut-il changer ?').fill('');                 // emptied by hand: no draft left
  await expect.poll(() => draftKeys(page, `lean.correction.${proved}`)).toHaveLength(0);

  // a conjecture not yet created
  await page.goto(`${process.env['MADALEAN_URL']}/conjectures`);
  await page.getByRole('button', { name: 'Écrire une conjecture' }).click();
  const dlg = page.getByRole('dialog');
  await dlg.getByLabel('Énoncé').fill('Tout entier pair > 2 est somme de deux premiers.');
  await dlg.getByRole('button', { name: 'Annuler' }).click();
  await page.reload();
  await page.getByRole('button', { name: 'Écrire une conjecture' }).click();
  await expect(page.getByRole('dialog').getByLabel('Énoncé')).toHaveValue('Tout entier pair > 2 est somme de deux premiers.');
  await page.getByRole('dialog').getByLabel('Énoncé').fill('');
  await expect.poll(() => draftKeys(page, 'conjecture.')).toHaveLength(0);
});
