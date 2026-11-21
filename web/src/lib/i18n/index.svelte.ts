// Interface language. French by default, English switch. Catalogues: ./fr.ts (source) and ./en.ts (complete,
// type-checked against fr; tests/unit/i18n.test.ts checks placeholders and emptiness).
import fr from './fr';
import en from './en';

export type Lang = 'fr' | 'en';
export type Key = keyof typeof fr;
export type Params = Record<string, string | number>;

const catalogues: Record<Lang, Record<Key, string>> = { fr, en };

function initial(): Lang {
  try {
    const l = localStorage.getItem('madalean.lang');
    if (l === 'fr' || l === 'en') return l;
  } catch { /* blocked storage */ }
  if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('en')) return 'en';
  return 'fr';
}

let current = $state<Lang>(typeof window === 'undefined' ? 'fr' : initial());

export const i18n = {
  get lang(): Lang {
    return current;
  },
  set(l: Lang): void {
    if (l !== 'fr' && l !== 'en') return;
    current = l;
    try { localStorage.setItem('madalean.lang', l); } catch { /* ignore */ }
    if (typeof document !== 'undefined') document.documentElement.lang = l;
  },
};

export function format(s: string, params?: Params): string {
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m));
}

/** Translate. Plural forms: keys `x.one` / `x.other` with `n` in params → use `tn`. */
export function t(key: Key, params?: Params): string {
  return format(catalogues[current][key] ?? catalogues.fr[key] ?? key, params);
}

export function tn(base: string, n: number, params: Params = {}): string {
  const rule = new Intl.PluralRules(current).select(n) === 'one' ? 'one' : 'other';
  return t(`${base}.${rule}` as Key, { n, ...params });
}

/** For keys built at runtime (e.g. `status.${s}`); falls back to `fallback` when absent. */
export function tk(key: string, fallback = '', params?: Params): string {
  const s = (catalogues[current] as Record<string, string>)[key];
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
  return new Intl.DateTimeFormat(current, sameDay ? { hour: '2-digit', minute: '2-digit' } : { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(d);
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
  return `${n.toFixed(i ? 1 : 0)} ${(current === 'fr' ? u : ue)[i]}`;
}
