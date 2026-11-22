import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

function freePort(): Promise<number> {
  return new Promise((res, rej) => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => {
      const p = (s.address() as net.AddressInfo).port;
      s.close(() => res(p));
    });
    s.on('error', rej);
  });
}

export default async function setup(): Promise<void> {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
  const dir = mkdtempSync(join(process.env['TMPDIR'] ?? tmpdir(), 'madalean-e2e-'));
  const port = await freePort();
  let remote = await freePort();
  while (remote === port) remote = await freePort();
  // MADALEAN_E2E_STATIC: test a web build made elsewhere (`npx vite build --outDir …`) without touching madalean/static.
  const statik = process.env['MADALEAN_E2E_STATIC'] ? ['--static', process.env['MADALEAN_E2E_STATIC']] : [];
  const child = spawn(join(root, 'bin', 'madalean'), ['serve', '--demo', '--port', String(port), '--remote-port', String(remote),
    '--config-dir', join(dir, 'config'), '--cache-dir', join(dir, 'cache'), ...statik], { stdio: ['ignore', 'pipe', 'pipe'], detached: false,
    // never the real prefix (~/.local/share/madalean): an empty MADALEAN_HOME = development checkout (S-R: the article
    // editor compiles with the prefix's tectonic, whose cache must not be the user's)
    env: { ...process.env, MADALEAN_HOME: process.env['MADALEAN_E2E_HOME'] ?? join(dir, 'home') } });
  child.stdout?.on('data', () => {});
  child.stderr?.on('data', () => {});
  writeFileSync(join(dir, 'pid'), String(child.pid));
  process.env['MADALEAN_E2E_DIR'] = dir;
  process.env['MADALEAN_E2E_PID'] = String(child.pid);
  process.env['MADALEAN_URL'] = `http://127.0.0.1:${port}`;
  process.env['MADALEAN_REMOTE_URL'] = `http://127.0.0.1:${remote}`;
  const t0 = Date.now();
  for (;;) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/api/hello`);
      if (r.ok) break;
    } catch { /* not yet */ }
    if (Date.now() - t0 > 30_000) throw new Error('demo server did not start');
    await new Promise((r) => setTimeout(r, 250));
  }
}
