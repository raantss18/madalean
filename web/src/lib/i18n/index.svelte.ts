// Interface language. French by default, English switch. Catalogues: ./fr.ts (source) and ./en.ts (complete,
// type-checked against fr; tests/unit/i18n.test.ts checks placeholders and emptiness).
// S-AP: only French (the source and the fallback) is in the first chunk; English is its own chunk, loaded before the
// app mounts when it is the device's language (main.ts awaits `i18n.ready()`), or when the user switches to it.
import fr from './fr';

// S-BE (D63): Malagasy is a partial catalogue; a missing key is shown in French, never in English.
export type Lang = 'fr' | 'en' | 'mg';
/** Languages of what is written in full (manual, glossary, examples, server contents). */
export type BaseLang = 'fr' | 'en';
export const LANGS: readonly [Lang, string][] = [['fr', 'Français'], ['en', 'English'], ['mg', 'Malagasy']];
export const isLang = (l: unknown): l is Lang => l === 'fr' || l === 'en' || l === 'mg';
export type Key = keyof typeof fr;
export type Params = Record<string, string | number>;

type Catalogue = Partial<Record<Key, string>>;
const catalogues: Partial<Record<Lang, Catalogue>> & { fr: Catalogue } = { fr };
const loaders: Record<Lang, () => Promise<Catalogue>> = {
  fr: async () => fr,
  en: () => import('./en').then((m) => m.default),
  mg: () => import('./mg').then((m) => m.default),
};
const loading = new Map<Lang, Promise<Catalogue>>();

/** Loads a catalogue once (retried after a failure). */
export function loadCatalogue(l: Lang): Promise<Catalogue> {
  const have = catalogues[l];
  if (have) return Promise.resolve(have);
  let p = loading.get(l);
  if (!p) {
    p = loaders[l]().then((c) => { catalogues[l] = c; return c; });
    p.catch(() => loading.delete(l));
    loading.set(l, p);
  }
  return p;
}

function initial(): Lang {
  try {
    const l = localStorage.getItem('madalean.lang');
    if (isLang(l)) return l;
  } catch { /* blocked storage */ }
  if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('en')) return 'en';
  if (typeof navigator !== 'undefined' && /^mg\b/i.test(navigator.language ?? '')) return 'mg';
  return 'fr';
}

// The language shown: always one whose catalogue is loaded. `wanted` is the last one asked for (a switch back while
// the English chunk is still downloading wins).
const asked: Lang = typeof window === 'undefined' ? 'fr' : initial();
let current = $state<Lang>(catalogues[asked] ? asked : 'fr');
let wanted: Lang = asked;

function apply(l: Lang): void {
  current = l;
  if (typeof document !== 'undefined') document.documentElement.lang = l;
}

export const i18n = {
  get lang(): Lang {
    return current;
  },
  /** The language of contents that exist in French and English only (mg reads French); also the one given to Intl. */
  get base(): BaseLang {
    return current === 'en' ? 'en' : 'fr';
  },
  /** Switches the language (at once when its catalogue is loaded, else as soon as it is). */
  set(l: Lang): Promise<void> {
    if (!isLang(l)) return Promise.resolve();
    wanted = l;
    try { localStorage.setItem('madalean.lang', l); } catch { /* ignore */ }
    if (catalogues[l]) { apply(l); return Promise.resolve(); }
    return loadCatalogue(l).then(() => { if (wanted === l) apply(l); }, () => { /* offline: stay in the current language */ });
  },
  /** Before mounting: the catalogue of the device's language is loaded and shown. */
  ready(): Promise<void> {
    return wanted === current ? Promise.resolve() : i18n.set(wanted);
  },
};

export function format(s: string, params?: Params): string {
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m));
}

/** Translate. Plural forms: keys `x.one` / `x.other` with `n` in params → use `tn`. */
export function t(key: Key, params?: Params): string {
  return format(catalogues[current]?.[key] ?? catalogues.fr[key] ?? key, params);
}

export function tn(base: string, n: number, params: Params = {}): string {
  const rule = new Intl.PluralRules(i18n.base).select(n) === 'one' ? 'one' : 'other';
  return t(`${base}.${rule}` as Key, { n, ...params });
}

/** For keys built at runtime (e.g. `status.${s}`); falls back to `fallback` when absent. */
export function tk(key: string, fallback = '', params?: Params): string {
  const s = (catalogues[current] as Record<string, string> | undefined)?.[key] ?? (catalogues.fr as Record<string, string>)[key];
  return s === undefined ? fallback : format(s, params);
}

export function hasKey(key: string): boolean {
  return key in catalogues.fr;
}

export function fmtTime(t: number | null | undefined): string {
  if (!t) return '';
  const d = new Date(t * 1000);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return new Intl.DateTimeFormat(i18n.base, sameDay ? { hour: '2-digit', minute: '2-digit' } : { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(d);
}

export function fmtDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '';
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m < 60 ? `${m} min ${s.toString().padStart(2, '0')}` : `${Math.floor(m / 60)} h ${(m % 60).toString().padStart(2, '0')}`;
}

export function fmtBytes(n: number): string {
  if (!n) return '';
  const u = ['o', 'Ko', 'Mo', 'Go', 'To'];
  const ue = ['B', 'kB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < 4) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${(current === 'en' ? ue : u)[i]}`;
}
