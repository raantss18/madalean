// Route table. Each screen is its own chunk (route-level code splitting). See docs/UI.md « Add a screen ».
// nav.group: 'project' = sections of the current project (project bar), else global destinations (logo menu).
import { addRoute } from './lib/router.svelte';

addRoute({ name: 'home', pattern: '/', load: () => import('./screens/Home.svelte'), nav: { label: 'nav.home', icon: 'list', order: 0 } });
addRoute({ name: 'dossier', pattern: '/d/:id/:step?', load: () => import('./screens/dossier/Dossier.svelte') });
addRoute({ name: 'project', pattern: '/projet', load: () => import('./screens/research/ProjectHub.svelte'), nav: { label: 'nav.project', icon: 'folder', order: 1 } });
addRoute({ name: 'sources', pattern: '/sources', load: () => import('./screens/research/Sources.svelte'), nav: { label: 'nav.sources', icon: 'book', order: 10, group: 'project' } });
addRoute({ name: 'reader', pattern: '/sources/:shelf/:id', load: () => import('./screens/research/Reader.svelte') });
addRoute({ name: 'notes', pattern: '/notes/:id?', load: () => import('./screens/research/Notes.svelte'), nav: { label: 'nav.notes', icon: 'edit', order: 11, group: 'project' } });
addRoute({ name: 'graph', pattern: '/graphe', load: () => import('./screens/research/Graph.svelte'), nav: { label: 'nav.graph', icon: 'link', order: 12, group: 'project' } });
addRoute({ name: 'blueprint', pattern: '/blueprint', load: () => import('./screens/research/Blueprint.svelte'), nav: { label: 'nav.blueprint', icon: 'tree', order: 13, group: 'project' } });
addRoute({ name: 'article', pattern: '/article', load: () => import('./screens/research/Article.svelte'), nav: { label: 'nav.article', icon: 'file', order: 14, group: 'project' } });
addRoute({ name: 'conjectures', pattern: '/conjectures/:id?', load: () => import('./screens/research/Conjectures.svelte'), nav: { label: 'nav.conjectures', icon: 'bulb', order: 15, group: 'project' } });
// S-AW: the guided « Explorer » flow of the conjecture engine, its own chunk, reached from Conjectures (no nav entry)
addRoute({ name: 'explore', pattern: '/explorer/:id?', load: () => import('./screens/research/Explore.svelte') });
addRoute({ name: 'calcul', pattern: '/calcul', load: () => import('./screens/research/Calcul.svelte'), nav: { label: 'nav.calcul', icon: 'terminal', order: 15.5, group: 'project' } });
addRoute({ name: 'publish', pattern: '/publier', load: () => import('./screens/research/Publish.svelte'), nav: { label: 'nav.publish', icon: 'globe', order: 16, group: 'project' } });
addRoute({ name: 'activity', pattern: '/activite', load: () => import('./screens/Activity.svelte'), nav: { label: 'nav.activity', icon: 'activity', order: 20 } });
addRoute({ name: 'library', pattern: '/bibliotheque', load: () => import('./screens/Library.svelte'), nav: { label: 'nav.library', icon: 'library', order: 21 } });
addRoute({ name: 'glossary', pattern: '/glossaire', load: () => import('./screens/Glossary.svelte'), nav: { label: 'nav.glossary', icon: 'book', order: 22 } });
addRoute({ name: 'notebook', pattern: '/carnet', load: () => import('./screens/Notebook.svelte'), nav: { label: 'nav.notebook', icon: 'notebook', order: 23 } });
addRoute({ name: 'help', pattern: '/aide/:page?', load: () => import('./screens/Help.svelte'), nav: { label: 'nav.help', icon: 'info', order: 24 } });
addRoute({ name: 'settings', pattern: '/reglages/:section?', load: () => import('./screens/settings/Settings.svelte'), nav: { label: 'nav.settings', icon: 'settings', order: 29 } });
// S-AQ (D49): the first-run assistant « Premiers pas », full screen on the host (App renders it without the top bar)
addRoute({ name: 'setup', pattern: '/premiers-pas/:step?', load: () => import('./screens/setup/Setup.svelte') });
addRoute({ name: 'pair', pattern: '/pair', load: () => import('./screens/Pair.svelte'), public: true });
addRoute({ name: 'perf', pattern: '/__perf', load: () => import('./screens/Perf.svelte') });
