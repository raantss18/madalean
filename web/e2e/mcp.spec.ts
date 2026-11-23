import { test, expect } from '@playwright/test';
import { open, api, axe, URL, REMOTE } from './util';

// Réglages › Outils (MCP) (session S-AZ, DECISIONS D58): off by default, the connection snippet appears once the
// server is allowed, external servers start disabled, a refused address says why; host-only; axe clean (both themes).
test('MCP settings: server switch, snippet, external server, axe', async ({ page }) => {
  await open(page, '/reglages/outils-mcp');
  await expect(page.getByRole('heading', { name: 'Madalean comme serveur MCP' })).toBeVisible();
  const allow = page.getByRole('checkbox', { name: 'Autoriser les applications de cet ordinateur' });
  await expect(allow).not.toBeChecked();
  await expect(page.getByText('claude mcp add madalean')).toHaveCount(0);
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await axe(page, `mcp off ${scheme}`);
  }
  await allow.check();
  await expect(page.getByText(/claude mcp add madalean -- .*bin\/madalean mcp serve/)).toBeVisible();
  await expect(page.getByText('"mcpServers"')).toBeVisible();
  expect((await api<{ server: { enabled: boolean } }>('GET', '/mcp')).server.enabled).toBe(true);

  // an external server: a plain-http address elsewhere is refused with a sentence, nothing is added
  await page.getByRole('radio', { name: 'Adresse (HTTP)' }).check();
  await page.getByLabel('Adresse', { exact: true }).fill('http://example.org/mcp');
  await page.getByLabel('Adresse', { exact: true }).press('Enter');
  await expect(page.locator('p.err[role=alert]')).toContainText('http seulement pour cet ordinateur');
  // Madalean itself, by its own local address: added, tested, still off, nothing allowed
  await page.getByRole('checkbox', { name: 'Aussi par une adresse locale (HTTP)' }).check();
  await page.getByLabel('Nom').fill('Madalean local');
  await page.getByLabel('Adresse', { exact: true }).fill(`${URL()}/api/mcp/http`);
  await page.getByRole('button', { name: 'Ajouter et tester' }).click();
  await expect(page.getByText(/Testé .* : \d+ outils/)).toBeVisible();
  const srv = (await api<{ servers: { enabled: boolean; allowed: string[]; tools: unknown[] }[] }>('GET', '/mcp')).servers[0]!;
  expect(srv.enabled).toBe(false);
  expect(srv.allowed).toEqual([]);
  expect(srv.tools.length).toBeGreaterThan(3);
  await page.getByRole('checkbox', { name: /check_lean/ }).check();
  await expect.poll(async () => (await api<{ servers: { allowed: string[] }[] }>('GET', '/mcp')).servers[0]!.allowed).toEqual(['check_lean']);
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await axe(page, `mcp on ${scheme}`);
  }
  await page.getByRole('button', { name: 'Retirer', exact: true }).click();
  await page.getByRole('button', { name: 'Retirer ce serveur' }).click();
  await expect(page.getByText('Aucun serveur externe.')).toBeVisible();
  await page.getByRole('checkbox', { name: 'Aussi par une adresse locale (HTTP)' }).uncheck();
  await allow.uncheck();
  await expect.poll(async () => (await api<{ server: { enabled: boolean } }>('GET', '/mcp')).server.enabled).toBe(false);
});

test('MCP API is host-only', async () => {
  const r = await fetch(`${REMOTE()}/api/mcp`);
  expect([401, 403]).toContain(r.status);
});
