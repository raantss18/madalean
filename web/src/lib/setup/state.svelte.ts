// Where the first-run assistant stands (GET /api/setup/wizard), shared by App (opens it by itself), the logo menu,
// Réglages and the Home reminder card. Read once at the start of the web app, on the host only.
import { app } from '../store/app.svelte';
import { navigate, route } from '../router.svelte';
import { setupApi } from './api';
import { shouldAutoOpen, type WizardInfo } from './wizard';

export const setup = $state<{ info: WizardInfo | null }>({ info: null });

let started = false;
/** After app.boot(): on the host, learn where the assistant stands; open it when this is the first start. */
export async function setupBoot(): Promise<void> {
  if (started || !app.m.loaded || !app.m.local) return;
  started = true;
  app.on('setup.wizard', (ev) => { setup.info = (ev as unknown as { wizard: WizardInfo }).wizard; });
  try { setup.info = await setupApi.wizard(); } catch { return; }      // an older server: no assistant
  if (shouldAutoOpen(app.m.local, route.name, app.m.settings?.wizard_done, setup.info)) navigate('/premiers-pas', { replace: true });
}

export async function saveWizard(p: Parameters<typeof setupApi.saveWizard>[0]): Promise<WizardInfo | null> {
  try { setup.info = await setupApi.saveWizard(p); return setup.info; } catch { return null; }
}
