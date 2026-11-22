// App navigation rail shown or hidden from 1024 px (session S-AD, docs/UI.md §13). Per device (localStorage
// `madalean.layout`). The article editor has its own choice (hidden by default: its project panel lists the same
// items and the text needs the width) and its focus mode hides the rail whatever the choice.
import { loadJSON, saveJSON } from '../prefs.svelte';

interface Saved { rail: boolean; railArticle: boolean }
const saved = typeof window === 'undefined' ? {} : loadJSON<Partial<Saved>>('layout', {});

export const layout = $state({
  rail: saved.rail ?? true,
  railArticle: saved.railArticle ?? false,
  /** Screen that owns the rail choice ('' = the app-wide one). */
  scope: '' as '' | 'article',
  /** Focus mode of the current screen: the rail is hidden. */
  focus: false,
});

export function railShown(): boolean {
  if (layout.focus) return false;
  return layout.scope === 'article' ? layout.railArticle : layout.rail;
}

export function setRail(v: boolean): void {
  if (layout.scope === 'article') layout.railArticle = v;
  else layout.rail = v;
  if (v) layout.focus = false;
  saveJSON('layout', { rail: layout.rail, railArticle: layout.railArticle });
}

/** Ctrl+Shift+1 (layout-independent: `KeyboardEvent.code`), also used by the article's own shortcuts. */
export function isShortcut(e: KeyboardEvent, code: string): boolean {
  return (e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.code === code;
}
