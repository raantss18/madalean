// Per-device personalisation of the article editor (localStorage `madalean.article.prefs`).
import { loadJSON, saveJSON } from '../prefs.svelte';

export interface ArticlePrefs {
  fontSize: number;            // % of the base size
  width: 'narrow' | 'normal' | 'wide';
  paper: 'paper' | 'plain';    // the writing surface looks like a page, or blends with the app
  keymap: 'default' | 'vim' | 'emacs';
  autosave: number;            // ms of idle before saving
  preview: 'right' | 'below' | 'off';
  autoCompile: boolean;        // compile after saving while the preview is open
  lineNumbers: boolean;        // source mode
  mode: 'visual' | 'source';
}

const DEFAULTS: ArticlePrefs = { fontSize: 100, width: 'normal', paper: 'paper', keymap: 'default', autosave: 1500, preview: 'right',
  autoCompile: true, lineNumbers: true, mode: 'visual' };

export const aprefs = $state<ArticlePrefs>({ ...DEFAULTS, ...loadJSON<Partial<ArticlePrefs>>('article.prefs', {}) });

export function setAPref<K extends keyof ArticlePrefs>(k: K, v: ArticlePrefs[K]): void {
  aprefs[k] = v;
  saveJSON('article.prefs', { ...aprefs });
}

export function resetAPrefs(): void {
  Object.assign(aprefs, DEFAULTS);
  saveJSON('article.prefs', { ...aprefs });
}

export const WIDTHS: Record<ArticlePrefs['width'], string> = { narrow: '62ch', normal: '72ch', wide: '92ch' };
