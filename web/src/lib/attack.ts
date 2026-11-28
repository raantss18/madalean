// Pure helpers of the « Attaque » screen (docs/ATTACK.md, D70): the state said in words, money and sizes in the
// user's language, check results read whatever their shape, live event merging, history filter. No DOM, no i18n
// import: the screen turns the returned keys into text (tests/unit/attack.test.ts).
import type { AttackHistoryItem, AttackStatus, AttackSubmission, CheckValue } from './api/attack';
import type { Phase } from './status';

type Lang = 'fr' | 'en';

/** « 5,00 $ » in French, « $5.00 » in English (the budget is in US dollars). */
export function money(n: number, lang: Lang): string {
  const v = Number.isFinite(n) ? n : 0;
  const s = v.toFixed(2);
  return lang === 'fr' ? `${s.replace('.', ',')} $` : `$${s}`;
}

/** Bytes → gigabytes as people count them on a download (10^9), one decimal at most: « 3,2 », « 8 ». */
export function gb(bytes: number, lang: Lang): string {
  const v = Math.round((Number.isFinite(bytes) ? bytes : 0) / 1e8) / 10;
  const s = Number.isInteger(v) ? String(v) : v.toFixed(1);
  return lang === 'fr' ? s.replace('.', ',') : s;
}

/** Downloaded / total bytes. `progress` is a fraction (≤ 1) or, if larger, a byte count. */
export function downloaded(ws: AttackStatus['workspace']): { done: number; total: number; ratio: number } {
  const total = Math.max(0, ws.size || 0);
  const p = Math.max(0, ws.progress || 0);
  const done = p <= 1 ? p * total : Math.min(p, total || p);
  return { done, total, ratio: total > 0 ? Math.min(1, done / total) : Math.min(1, p <= 1 ? p : 0) };
}

export interface Line { key: string; params: Record<string, string | number>; plural?: number }

/** The state of the attack in one sentence (the header and the Home card). */
export function headline(s: AttackStatus, lang: Lang): Line {
  switch (s.state) {
    case 'off': return { key: 'attack.state.off', params: {} };
    case 'setup': {
      const ws = s.workspace;
      if (ws.state === 'downloading') {
        const d = downloaded(ws);
        return d.total > 0
          ? { key: 'attack.state.downloading', params: { done: gb(d.done, lang), total: gb(d.total, lang) } }
          : { key: 'attack.state.downloadingNoSize', params: {} };
      }
      if (ws.state === 'building') return { key: 'attack.state.building', params: {} };
      return { key: 'attack.state.setup', params: {} };
    }
    case 'running': {
      const n = s.current.length;
      return n ? { key: 'attack.state.running', params: {}, plural: n } : { key: 'attack.state.looking', params: {} };
    }
    case 'budget': return { key: 'attack.state.budget', params: { cap: money(s.today.cap, lang) } };
    case 'paused': return { key: 'attack.state.paused', params: { reason: s.reason } };
    case 'error': return { key: 'attack.state.error', params: { reason: s.reason } };
  }
  return { key: 'attack.state.off', params: {} };
}

/** Whether Madalean is working or about to (the button then says « Arrêter »). */
export function isOn(s: AttackStatus | null): boolean {
  return Boolean(s && s.state !== 'off' && s.state !== 'error');
}

/** The first start needs the user's agreement to the download (D69): nothing is downloaded before. */
export function needsAgreement(s: AttackStatus | null): boolean {
  return Boolean(s && (s.workspace.state === 'none'));
}

export interface CheckRead { ok: boolean | null; detail: string }
/** A check result read whatever its shape: `true`, `"ok"`, `{ok, detail}`, a list of axioms… `null` = not run. */
export function readCheck(v: CheckValue | undefined, kind: 'local' | 'rules' | 'axioms' = 'local'): CheckRead {
  if (v === null || v === undefined) return { ok: null, detail: '' };
  if (typeof v === 'boolean') return { ok: v, detail: '' };
  if (Array.isArray(v)) {
    if (kind !== 'axioms') return { ok: v.length === 0, detail: v.join(', ') };
    const extra = v.filter((a) => !STANDARD_AXIOMS.has(a));
    return { ok: extra.length === 0, detail: v.join(', ') };
  }
  if (typeof v === 'string') {
    const low = v.trim().toLowerCase();
    if (['ok', 'pass', 'passed', 'true', 'yes'].includes(low)) return { ok: true, detail: '' };
    if (['', 'pending', 'unknown', 'not_run', 'skipped'].includes(low)) return { ok: null, detail: '' };
    return { ok: false, detail: v };
  }
  const detail = v.detail ?? v.text ?? (v.axioms ? v.axioms.join(', ') : '');
  let ok = v.ok ?? null;
  if (ok === null && kind === 'axioms' && v.axioms) ok = v.axioms.every((a) => STANDARD_AXIOMS.has(a));
  return { ok, detail };
}
export const STANDARD_AXIOMS = new Set(['propext', 'Classical.choice', 'Quot.sound']);

/** All three local checks passed: only then is a file « prête » (D69). */
export function allChecksPass(s: AttackSubmission): boolean {
  return (['local', 'rules', 'axioms'] as const).every((k) => readCheck(s.check?.[k], k).ok === true);
}

export function fileText(f: AttackSubmission['file']): string {
  return typeof f === 'string' ? f : f?.text ?? '';
}
export function filePath(s: AttackSubmission): string {
  if (typeof s.file === 'object' && s.file?.path) return s.file.path;
  return s.plan?.path ?? '';
}

/** The GitHub account the plan uses: its own field, else the owner of the first `/repos/<owner>/` request. */
export function planLogin(s: AttackSubmission): string {
  if (s.plan?.login) return s.plan.login;
  for (const r of s.plan?.requests ?? []) {
    const m = /\/repos\/([^/]+)\//.exec(r.url);
    if (m && r.method.toUpperCase() !== 'GET' && !/forks$/.test(r.url)) return m[1]!;
  }
  return '';
}

/** One GitHub request said in words (the exact request stays shown under it): fork, branch, file, pull request. */
export function requestWords(r: { method: string; url: string }): { key: string; params: Record<string, string> } {
  const u = r.url.replace(/^https:\/\/api\.github\.com/, '');
  const m = /^\/repos\/([^/]+)\/([^/]+)(\/.*)?$/.exec(u);
  const repo = m ? `${m[1]}/${m[2]}` : '';
  const rest = m?.[3] ?? '';
  const M = r.method.toUpperCase();
  if (M === 'POST' && rest === '/forks') return { key: 'attack.req.fork', params: { repo } };
  if (M === 'POST' && rest === '/git/refs') return { key: 'attack.req.branch', params: { repo } };
  if (M === 'PUT' && rest.startsWith('/contents/')) return { key: 'attack.req.file', params: { repo, path: decodeURIComponent(rest.slice(10)) } };
  if (M === 'POST' && rest === '/pulls') return { key: 'attack.req.pr', params: { repo } };
  if (M === 'GET') return { key: 'attack.req.read', params: { repo } };
  return { key: 'attack.req.other', params: { repo } };
}

export function submissionMark(state: AttackSubmission['state']): Phase {
  return state === 'merged' ? 'proved' : state === 'rejected' ? 'failed' : state === 'sent' ? 'running' : state === 'expired' ? 'stopped' : 'queued';
}
export function outcomeMark(o: AttackHistoryItem['outcome']): Phase {
  return o === 'solved' ? 'proved' : o === 'rejected' ? 'failed' : o === 'submitted' ? 'running' : o === 'reduced' ? 'stopped' : 'draft';
}

/** `attack.state` carries the whole GET /api/attack answer, either at the top level or under `attack` / `status`. */
export function statusFromEvent(ev: Record<string, unknown>): AttackStatus | null {
  for (const k of ['attack', 'status', 'state']) {
    const v = ev[k];
    if (v && typeof v === 'object' && typeof (v as AttackStatus).state === 'string') return v as AttackStatus;
  }
  if (typeof ev['state'] === 'string' && ev['today'] && ev['workspace']) return ev as unknown as AttackStatus;
  return null;
}

/** `attack.submission` carries one submission under `submission`, or at the top level. */
export function submissionFromEvent(ev: Record<string, unknown>): AttackSubmission | null {
  const v = (ev['submission'] ?? ev) as AttackSubmission;
  return v && typeof v.id === 'string' && typeof v.state === 'string' ? v : null;
}

/** Inserts or replaces by id, newest first; a submission marked `discarded` leaves the list. */
export function upsertSubmission(list: AttackSubmission[], s: AttackSubmission): AttackSubmission[] {
  const rest = list.filter((x) => x.id !== s.id);
  if ((s.state as string) === 'discarded') return rest;
  return [s, ...rest].sort((a, b) => (b.created ?? 0) - (a.created ?? 0));
}

export function filterHistory(list: AttackHistoryItem[], kind: string): AttackHistoryItem[] {
  const l = kind ? list.filter((h) => h.kind === kind) : list;
  return [...l].sort((a, b) => b.t - a.t);
}
export function totalUsd(list: { usd: number }[]): number {
  return list.reduce((a, h) => a + (Number.isFinite(h.usd) ? h.usd : 0), 0);
}

/** A coarse elapsed time (no seconds: the cards do not tick every second): « < 1 min », « 12 min », « 2 h 05 ». */
export function ago(seconds: number): string {
  const s = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  if (s < 60) return '< 1 min';
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
}

/** Share of today's cap already spent, 0–1 (bar under the header). */
export function spentRatio(s: AttackStatus): number {
  return s.today.cap > 0 ? Math.min(1, Math.max(0, s.today.usd / s.today.cap)) : 0;
}
