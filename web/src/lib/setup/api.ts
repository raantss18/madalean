// Typed client of the setup endpoints (S-AL GET /api/setup; S-AQ wizard progress, reuse, local models). Host only.
import { request } from '../api/client';
import type { ModelFile, NextStep, WizardInfo } from './wizard';

export interface Component { component: string; title: string; need: string; version: string; pinned: string; path: string;
  source: string; ok: boolean; state: 'ok' | 'on_demand' | 'dev' | 'missing' | 'outdated' | string; repair: string }
export interface ReuseInfo {
  sage: { preference: string; used: string; ok: boolean; system: { found?: boolean | null; version?: string | null; kernelspec?: string | null; compatible?: boolean | null } };
  tex: { preference: string; used: string; ok: boolean; engines: number; system: { found?: boolean | null; year?: number | null; fontspec?: boolean | null; compatible?: boolean | null } };
}
export interface RecItem { id: string; recommended: string; why: string; detected: string; title: string;
  options: { value: string; label: string; available: boolean }[] }
export interface FetchJob { running?: boolean; phase?: string; keys?: string[]; index?: number; done_gb?: number; total_gb?: number; message?: string; ok?: boolean | null }
export interface SetupStatus {
  schema: string;
  setup: { plan?: Record<string, string>; source?: string } | null;
  detected: { hardware?: { ram_bytes?: number; gpus?: { name: string; vram_mib: number }[]; disk?: { free_bytes?: number } };
    tools?: Record<string, { found?: boolean; version?: string }>; madalean?: { sage_own?: boolean } };
  prefs: { sage_source: string; tex_engine: string; mode: string; wizard_done: boolean };
  components: Component[];
  reuse: ReuseInfo;
  keys: string[];
  devices: number;
  next_steps: NextStep[];
  recommended: { plan: Record<string, string>; items: RecItem[]; advice: { id: string; text: string; command: string }[];
    disk: { needed_bytes: number; free_bytes: number } } | null;
  models: { dir: string; files: ModelFile[]; download_bytes: Record<string, number>; choice: string; fetch: FetchJob };
  wizard: WizardInfo;
}

export const setupApi = {
  status: (refresh = false) => request<SetupStatus>('GET', `/setup${refresh ? '?refresh=1' : ''}`),
  wizard: () => request<WizardInfo>('GET', '/setup/wizard'),
  saveWizard: (p: Partial<Pick<WizardInfo, 'step' | 'visited' | 'models' | 'done' | 'completed' | 'reminder'>>) =>
    request<WizardInfo>('PATCH', '/setup/wizard', p),
  reuse: (p: { sage_source?: string; tex_engine?: string }) =>
    request<{ prefs: SetupStatus['prefs']; reuse: ReuseInfo }>('POST', '/setup/reuse', p),
  fetchModels: (models: 'prover' | 'all') =>
    request<{ started: boolean; models: SetupStatus['models'] }>('POST', '/setup/models', { models }),
  cancelModels: () => request<{ cancelled: boolean }>('POST', '/setup/models/cancel', {}),
  /** A component of the prefix (§18), installed or repaired in the background: progress = `deps.progress` events. */
  installComponent: (name: string) => request<{ component: string; started: boolean }>('POST', `/deps/${encodeURIComponent(name)}/install`, {}),
  componentJobs: () => request<{ jobs?: Record<string, FetchJob & { done?: number; total?: number }> }>('GET', '/deps'),
};
