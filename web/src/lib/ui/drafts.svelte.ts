// Unsent text kept on this device (S-AP): what is typed in a field that SENDS (a question, a request, an answer to
// check…) survives leaving the screen, a reload or a closed tab, until it is sent — sending empties the field, which
// removes the draft. Per device (localStorage `madalean.draft.*`, the same store as the new-problem and follow-up
// drafts of S-AK): unsent text is not server data. Saved text (notes, cells, titles…) uses Autosave instead.
import { untrack } from 'svelte';
import { loadJSON, saveJSON, removeKey } from '../prefs.svelte';

export function loadDraft(key: string): string {
  const v = loadJSON<unknown>(`draft.${key}`, '');
  return typeof v === 'string' ? v : '';
}

/** Whitespace-only text is no draft: the key is removed. */
export function saveDraft(key: string, text: string): void {
  if (text.trim()) saveJSON(`draft.${key}`, text);
  else removeKey(`draft.${key}`);
}

export function clearDraft(key: string): void {
  removeKey(`draft.${key}`);
}

/**
 * Binds a field to its draft, during a component's initialisation: restores the draft of `key()` (now and whenever
 * the key changes, e.g. another dossier in the same screen), then saves every change. `key()` returning '' turns it
 * off (nothing loaded or saved).
 */
export function keepDraft(key: () => string, get: () => string, set: (v: string) => void): void {
  let loaded: string | null = null;
  $effect.pre(() => {
    const k = key();
    if (k === loaded) return;
    const first = loaded === null;
    loaded = k;
    if (!k) return;
    const v = loadDraft(k);
    untrack(() => { if (v || !first) set(v); });       // first load: a non-empty draft only (keeps a preset text)
  });
  $effect(() => {
    const v = get();
    const k = key();
    if (k && k === loaded) saveDraft(k, v);
  });
}
