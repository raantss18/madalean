import { rmSync } from 'node:fs';
export default async function teardown(): Promise<void> {
  const pid = Number(process.env['MADALEAN_E2E_PID']);
  if (pid) {
    try { process.kill(pid, 'SIGTERM'); } catch { /* already gone */ }
    for (let i = 0; i < 40; i++) {
      try { process.kill(pid, 0); } catch { break; }
      await new Promise((r) => setTimeout(r, 100));
    }
    try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
  }
  const dir = process.env['MADALEAN_E2E_DIR'];
  if (dir && dir.includes('madalean-e2e-')) rmSync(dir, { recursive: true, force: true });
}
