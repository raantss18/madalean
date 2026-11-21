// The project the research screens work on: the one chosen in the top-bar switcher, else the most recently updated.
import { app } from './store/app.svelte';
import { prefs, setLastProject } from './prefs.svelte';

export function currentProjectId(): string {
  if (prefs.lastProject && app.m.projects[prefs.lastProject]) return prefs.lastProject;
  const ps = Object.values(app.m.projects).filter((p) => !p.archived).sort((a, b) => b.updated - a.updated);
  return ps[0]?.id ?? '';
}

export function useProject(id: string): void {
  if (id && id !== prefs.lastProject) setLastProject(id);
}

/** Research screens of a project, in the order shown in the rail and the project hub. */
export const PROJECT_SECTIONS = [
  { path: '/', label: 'nav.dossiers', icon: 'list', name: 'home' },
  { path: '/sources', label: 'nav.sources', icon: 'book', name: 'sources' },
  { path: '/notes', label: 'nav.notes', icon: 'edit', name: 'notes' },
  { path: '/graphe', label: 'nav.graph', icon: 'link', name: 'graph' },
  { path: '/blueprint', label: 'nav.blueprint', icon: 'tree', name: 'blueprint' },
  { path: '/article', label: 'nav.article', icon: 'file', name: 'article' },
  { path: '/conjectures', label: 'nav.conjectures', icon: 'bulb', name: 'conjectures' },
  { path: '/publier', label: 'nav.publish', icon: 'globe', name: 'publish' },
] as const;
