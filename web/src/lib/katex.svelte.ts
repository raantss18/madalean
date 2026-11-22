// KaTeX off the critical path (S-AP, docs/PERFORMANCE.md « Interface sur téléphone »): the library and its CSS
// (~270 kB minified) load on the first formula to show, not with every screen. Until it is in, formulas are shown
// as their TeX source (`.math-pending`); `katexVersion()` is reactive, so a `$derived` / template that rendered a
// placeholder renders again once KaTeX has loaded.
import type katexT from 'katex';

type Katex = typeof katexT;
let mod: Katex | null = null;
let pending: Promise<Katex> | null = null;
let version = $state(0);

/** Loads KaTeX (once). Safe to call many times; failures are retried on the next call. */
export function loadKatex(): Promise<Katex> {
  if (mod) return Promise.resolve(mod);
  pending ??= Promise.all([import('katex'), import('katex/dist/katex.min.css')]).then(([m]) => {
    mod = (m as unknown as { default: Katex }).default ?? (m as unknown as Katex);
    version++;
    return mod;
  }).catch((e) => { pending = null; throw e; });
  return pending;
}

/** The loaded library, or null. Reading it inside a reactive context subscribes to its arrival. */
export function katexNow(): Katex | null {
  void version;
  return mod;
}

export function katexVersion(): number {
  return version;
}

/** For tests and screens that know they will show maths at once (Calcul): start the download early. */
export function preloadKatex(): void {
  void loadKatex().catch(() => { /* shown as source; retried on the next formula */ });
}
