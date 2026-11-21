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

applyPrefs();
startRouter();
mount(App, { target: document.getElementById('app')! });
