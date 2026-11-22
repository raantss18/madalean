// Project bar shown or hidden (session S-AK, docs/UI.md §14.2; it replaced the S-AD navigation rail, §13). Per device
// (localStorage `madalean.layout`). The article editor has its own choice (hidden by default there: its project panel
// lists the same items and the text needs the height) and its focus mode hides the bar whatever the choice.
import { loadJSON, saveJSON } from '../prefs.svelte';

interface Saved { bar: boolean; barArticle: boolean; rail?: boolean; railArticle?: boolean }
const saved = typeof window === 'undefined' ? {} : loadJSON<Partial<Saved>>('layout', {});

export const layout = $state({
  bar: saved.bar ?? saved.rail ?? true,
  barArticle: saved.barArticle ?? saved.railArticle ?? false,
  /** Screen that owns the bar choice ('' = the app-wide one). */
  scope: '' as '' | 'article',
  /** Focus mode of the current screen: the bar is hidden. */
  focus: false,
});

export function barShown(): boolean {
  if (layout.focus) return false;
  return layout.scope === 'article' ? layout.barArticle : layout.bar;
}

export function setBar(v: boolean): void {
  if (layout.scope === 'article') layout.barArticle = v;
  else layout.bar = v;
  if (v) layout.focus = false;
  saveJSON('layout', { bar: layout.bar, barArticle: layout.barArticle });
}

/** Ctrl+Shift+1 (layout-independent: `KeyboardEvent.code`), also used by the article's own shortcuts. */
export function isShortcut(e: KeyboardEvent, code: string): boolean {
  return (e.ctrlKey || e.metaKey) && e.shiftKey && !e.altKey && e.code === code;
}
