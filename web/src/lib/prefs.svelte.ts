// Per-device preferences (localStorage): theme, Learn/Research mode, tour seen, hint progress.
export type Theme = 'system' | 'light' | 'dark';
export type UiMode = 'learn' | 'research';

function read(key: string, fallback: string): string {
  try { return localStorage.getItem(`madalean.${key}`) ?? fallback; } catch { return fallback; }
}
function write(key: string, v: string): void {
  try { localStorage.setItem(`madalean.${key}`, v); } catch { /* ignore */ }
}

const browser = typeof window !== 'undefined';

export const prefs = $state({
  theme: (browser ? read('theme', 'system') : 'system') as Theme,
  mode: (browser ? read('density', 'learn') : 'learn') as UiMode,
  tourDone: browser ? read('tour', '') === '1' : true,
  textSize: (browser ? Number(read('textsize', '100')) : 100) || 100,
  lastProject: browser ? read('project', '') : '',
});

export function setTheme(t: Theme): void {
  prefs.theme = t;
  write('theme', t);
  if (t === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', t);
}

export function setMode(m: UiMode): void {
  prefs.mode = m;
  write('density', m);
  document.documentElement.setAttribute('data-mode', m);
}

export function setTextSize(pct: number): void {
  prefs.textSize = pct;
  write('textsize', String(pct));
  document.documentElement.style.fontSize = `${pct}%`;
}

export function setTourDone(v: boolean): void {
  prefs.tourDone = v;
  write('tour', v ? '1' : '');
}

export function setLastProject(id: string): void {
  prefs.lastProject = id;
  write('project', id);
}

export function applyPrefs(): void {
  if (prefs.theme !== 'system') document.documentElement.setAttribute('data-theme', prefs.theme);
  document.documentElement.setAttribute('data-mode', prefs.mode);
  if (prefs.textSize !== 100) document.documentElement.style.fontSize = `${prefs.textSize}%`;
}

/** Small per-device JSON store (hint ladder progress, explain-back answers, drafts). */
export function loadJSON<T>(key: string, fallback: T): T {
  try {
    const s = localStorage.getItem(`madalean.${key}`);
    return s ? (JSON.parse(s) as T) : fallback;
  } catch { return fallback; }
}
export function saveJSON(key: string, v: unknown): void {
  try { localStorage.setItem(`madalean.${key}`, JSON.stringify(v)); } catch { /* quota or blocked */ }
}
export function removeKey(key: string): void {
  try { localStorage.removeItem(`madalean.${key}`); } catch { /* ignore */ }
}
