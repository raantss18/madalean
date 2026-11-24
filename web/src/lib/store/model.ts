// The client-side model of the server state and its reducer. Pure TypeScript (no Svelte): the reactive store
// wraps one instance in $state, unit tests use plain objects.
import type {
  Device, Dossier, DossierSummary, Job, JupyterStatus, ModelsInfo, Project, SeqEvent, Settings, StateSnapshot,
  SystemInfo, UpdatesStatus,
} from '../api/types';

export interface Model {
  loaded: boolean;
  local: boolean;
  demo: boolean;
  brain: string;
  version: string;
  host_name: string;
  device: Device | null;
  settings: Settings | null;
  hostOnly: string[];
  projects: Record<string, Project>;
  dossiers: Record<string, DossierSummary>;
  /** Full dossiers fetched by an open screen (kept fresh by `dossier.updated`). */
  full: Record<string, Dossier>;
  jobs: Record<string, Job>;
  models: ModelsInfo | null;
  system: SystemInfo | null;
  libraryCount: number;
  libraryRev: number;
  updates: UpdatesStatus | null;
  jupyter: JupyterStatus | null;
  devices: Device[] | null;
  browsers: Device[] | null;          // browser sessions of the remote/LAN listeners (host view)
}

export function emptyModel(): Model {
  return {
    loaded: false, local: true, demo: false, brain: '', version: '', host_name: '', device: null, settings: null,
    hostOnly: [], projects: {}, dossiers: {}, full: {}, jobs: {}, models: null, system: null, libraryCount: 0,
    libraryRev: 0, updates: null, jupyter: null, devices: null, browsers: null,
  };
}

export const MAX_FINISHED_JOBS = 200;

export function loadSnapshot(m: Model, s: StateSnapshot): void {
  m.loaded = true;
  m.local = s.local;
  m.demo = s.demo;
  m.brain = s.brain;
  m.version = s.version;
  m.host_name = s.host_name;
  m.device = s.device;
  m.settings = s.settings;
  m.hostOnly = s.host_only_settings ?? [];
  m.projects = Object.fromEntries(s.projects.map((p) => [p.id, p]));
  m.dossiers = Object.fromEntries(s.dossiers.map((d) => [d.id, d]));
  m.jobs = Object.fromEntries([...s.jobs.recent, ...s.jobs.active].map((j) => [j.id, j]));
  m.models = s.models;
  m.system = s.system;
  m.libraryCount = s.library?.count ?? 0;
  m.libraryRev++;
  m.updates = s.updates;
  m.jupyter = s.jupyter;
  // Full dossiers may be stale after a resync: drop them, open screens refetch (see store.ensureDossier).
  for (const id of Object.keys(m.full)) if (!m.dossiers[id]) delete m.full[id];
}

export function summaryOf(d: Dossier): DossierSummary {
  return {
    id: d.id, title: d.title, project_id: d.project_id, status: d.status, parent_id: d.parent_id, kind: d.kind,
    theorem: d.theorem, workspace: d.workspace, created: d.created, updated: d.updated, archived: d.archived,
    has_statement: d.statements.length > 0, proved: d.status === 'proved',
    ...(d.gate !== undefined ? { gate: d.gate } : {}), ...(d.now !== undefined ? { now: d.now } : {}),
  };
}

export const TERMINAL = new Set(['done', 'failed', 'cancelled']);

function pruneJobs(m: Model): void {
  const finished = Object.values(m.jobs).filter((j) => TERMINAL.has(j.state));
  if (finished.length <= MAX_FINISHED_JOBS) return;
  finished.sort((a, b) => (a.ended ?? a.created) - (b.ended ?? b.created));
  for (const j of finished.slice(0, finished.length - MAX_FINISHED_JOBS)) delete m.jobs[j.id];
}

/** Applies one sequenced server event. Returns false for types this reducer does not handle. */
export function applyEvent(m: Model, ev: SeqEvent): boolean {
  const e = ev as unknown as Record<string, unknown> & { type: string };
  switch (e.type) {
    case 'job.updated': {
      const job = e['job'] as Job;
      m.jobs[job.id] = job;
      if (TERMINAL.has(job.state)) pruneJobs(m);
      return true;
    }
    case 'dossier.updated': {
      const d = e['dossier'] as Dossier;
      m.dossiers[d.id] = summaryOf(d);
      m.full[d.id] = d;
      return true;
    }
    case 'dossier.now': {                                    // D64: what happens right now, without the whole dossier
      const id = e['dossier_id'] as string;
      const now = (e['now'] as Dossier['now']) ?? null;
      if (m.full[id]) m.full[id]!.now = now;
      if (m.dossiers[id]) m.dossiers[id]!.now = now;
      return true;
    }
    case 'dossier.deleted': {
      const id = e['id'] as string;
      delete m.dossiers[id];
      delete m.full[id];
      return true;
    }
    case 'project.updated': {
      const p = e['project'] as Project;
      m.projects[p.id] = p;
      return true;
    }
    case 'project.deleted':
      delete m.projects[e['id'] as string];
      return true;
    case 'library.updated':
      if (e['added']) m.libraryCount++;
      if (e['removed']) m.libraryCount = Math.max(0, m.libraryCount - 1);
      m.libraryRev++;
      return true;
    case 'system.status': {
      const s = e['system'] as SystemInfo;
      m.system = { ...(m.system ?? { workspaces: [] }), ...s } as SystemInfo;
      return true;
    }
    case 'models.status': {
      if (!m.models) return true;
      if (e['local']) m.models.local = e['local'] as ModelsInfo['local'];
      if (e['keys']) m.models.keys = e['keys'] as Record<string, boolean>;
      return true;
    }
    case 'settings.updated':
      m.settings = e['settings'] as Settings;
      return true;
    case 'devices.updated':
      m.devices = e['devices'] as Device[];
      m.browsers = (e['browsers'] as Device[] | undefined) ?? m.browsers;
      return true;
    case 'updates.status':
      m.updates = e['updates'] as UpdatesStatus;
      return true;
    case 'jupyter.status':
      m.jupyter = e['jupyter'] as JupyterStatus;
      return true;
    default:
      return false;
  }
}

export function activeJobFor(m: Model, dossierId: string): Job | undefined {
  let best: Job | undefined;
  for (const j of Object.values(m.jobs)) {
    if (j.dossier_id !== dossierId || TERMINAL.has(j.state)) continue;
    if (!best || j.created > best.created) best = j;
  }
  return best;
}

export function lastJobFor(m: Model, dossierId: string): Job | undefined {
  let best: Job | undefined;
  for (const j of Object.values(m.jobs)) if (j.dossier_id === dossierId && (!best || j.created > best.created)) best = j;
  return best;
}
