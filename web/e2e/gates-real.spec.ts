import { test, expect } from '@playwright/test';
import { api, axe, open } from './util';

// The gates of D64 against the real (demo) server, nothing mocked: meaning → approve → statement → approve → proof.
type Full = { dossier: { status: string; gate: { kind: string; state: string } | null; proofs: unknown[]; now: unknown } };
const read = (id: string) => api<Full>('GET', `/dossiers/${id}`);

test('a person validates the meaning, then the Lean statement, before any proof', async ({ page }) => {
  await api('PATCH', '/settings', { validate_before_proof: true });
  try {
    const { dossier } = await api<Full & { dossier: { id: string } }>('POST', '/dossiers', { problem: 'Montrer que 2 + 2 = 4.', title: 'Portes' });
    await open(page, `/d/${dossier.id}`);
    for (const [kind, title] of [['meaning', 'Est-ce bien ce que vous voulez dire'], ['statement', 'dit-il bien la même chose']] as const) {
      await expect.poll(async () => { const g = (await read(dossier.id)).dossier.gate; return g?.state === 'pending' ? g.kind : ''; }, { timeout: 40_000 }).toBe(kind);
      expect((await read(dossier.id)).dossier.proofs).toHaveLength(0);
      await expect(page.getByText(title).first()).toBeVisible();
      await axe(page, `gate ${kind}`);
      await page.getByRole('button', { name: 'Approuver', exact: true }).first().click();
    }
    await expect.poll(async () => (await read(dossier.id)).dossier.proofs.length, { timeout: 60_000 }).toBeGreaterThan(0);
  } finally { await api('PATCH', '/settings', { validate_before_proof: false }); }
});
