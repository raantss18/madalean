// Route table. Each screen is its own chunk (route-level code splitting). See docs/UI.md « Add a screen ».
import { addRoute } from './lib/router.svelte';

addRoute({ name: 'home', pattern: '/', load: () => import('./screens/Home.svelte'), nav: { label: 'nav.home', icon: 'list', order: 0, phone: true } });
addRoute({ name: 'dossier', pattern: '/d/:id/:step?', load: () => import('./screens/dossier/Dossier.svelte') });
addRoute({ name: 'activity', pattern: '/activite', load: () => import('./screens/Activity.svelte'), nav: { label: 'nav.activity', icon: 'activity', order: 1, phone: true } });
addRoute({ name: 'library', pattern: '/bibliotheque', load: () => import('./screens/Library.svelte'), nav: { label: 'nav.library', icon: 'library', order: 2, phone: true } });
addRoute({ name: 'glossary', pattern: '/glossaire', load: () => import('./screens/Glossary.svelte'), nav: { label: 'nav.glossary', icon: 'book', order: 3 } });
addRoute({ name: 'notebook', pattern: '/carnet', load: () => import('./screens/Notebook.svelte'), nav: { label: 'nav.notebook', icon: 'notebook', order: 4 } });
addRoute({ name: 'settings', pattern: '/reglages/:section?', load: () => import('./screens/settings/Settings.svelte'), nav: { label: 'nav.settings', icon: 'settings', order: 9, phone: true } });
addRoute({ name: 'pair', pattern: '/pair', load: () => import('./screens/Pair.svelte'), public: true });
addRoute({ name: 'perf', pattern: '/__perf', load: () => import('./screens/Perf.svelte') });
