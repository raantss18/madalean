import '@fontsource-variable/source-sans-3/wght.css';
import '@fontsource-variable/source-serif-4/wght.css';
import '@fontsource-variable/source-serif-4/wght-italic.css';
import '@fontsource/dejavu-mono/400.css';
import '@fontsource/dejavu-mono/700.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/editor.css';
import { mount } from 'svelte';
import App from './App.svelte';
import './routes';
import { applyPrefs } from './lib/prefs.svelte';
import { startRouter } from './lib/router.svelte';
import { watchKeyboard } from './lib/ui/keyboard';
import { i18n } from './lib/i18n/index.svelte';

applyPrefs();
startRouter();
watchKeyboard();
// The English catalogue is its own chunk (S-AP): an English device waits for it (one request) rather than flashing
// French; a French device mounts at once.
void i18n.ready().finally(() => mount(App, { target: document.getElementById('app')! }));
