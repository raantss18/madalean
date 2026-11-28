// « Problèmes ouverts » (S-BK, D70): the state said in words, money and sizes, the checks read whatever their shape,
// live events merged, the history filter, the API client's paths, every word the screen may build at run time.
import { describe, it, expect, beforeEach } from 'vitest';
import { configureClient } from '../../src/lib/api/client';
import { attack, ATTACK_KINDS, type AttackStatus, type AttackSubmission } from '../../src/lib/api/attack';
import {
  money, gb, downloaded, headline, isOn, needsAgreement, readCheck, allChecksPass, fileText, filePath, planLogin, submissionMark,
  outcomeMark, requestWords, statusFromEvent, submissionFromEvent, upsertSubmission, filterHistory, totalUsd, spentRatio, ago,
} from '../../src/lib/attack';
import fr from '../../src/lib/i18n/fr';
import en from '../../src/lib/i18n/en';

const st = (x: Partial<AttackStatus> = {}): AttackStatus => ({
  state: 'off', reason: '', today: { usd: 0, cap: 5, taken: 0, proofs: 0, released: 0 },
  workspace: { state: 'ready', commit: 'abc', size: 0, progress: 0 }, current: [], queue: 0, ...x,
});
const sub = (x: Partial<AttackSubmission> = {}): AttackSubmission => ({
  id: 's1', problem: 'erdos-1', title: 'Erdős 1', kind: 'proof', file: 'theorem x : True := trivial',
  check: { local: true, rules: { ok: true }, axioms: ['propext'] }, plan: { requests: [] }, state: 'ready', pr_url: '', created: 10, ...x,
});

describe('words and numbers', () => {
  it('money in both languages', () => {
    expect(money(5, 'fr')).toBe('5,00 $');
    expect(money(0.237, 'en')).toBe('$0.24');
    expect(money(NaN, 'fr')).toBe('0,00 $');
  });
  it('gigabytes, one decimal at most', () => {
    expect(gb(3.2e9, 'fr')).toBe('3,2');
    expect(gb(8e9, 'fr')).toBe('8');
    expect(gb(3.25e9, 'en')).toBe('3.3');
  });
  it('download progress as a fraction or as bytes', () => {
    expect(downloaded({ state: 'downloading', commit: '', size: 8e9, progress: 0.4 }).done).toBeCloseTo(3.2e9);
    expect(downloaded({ state: 'downloading', commit: '', size: 8e9, progress: 2e9 }).ratio).toBeCloseTo(0.25);
    expect(downloaded({ state: 'downloading', commit: '', size: 0, progress: 0.5 }).ratio).toBe(0.5);
  });
  it('the headline for every state', () => {
    expect(headline(st(), 'fr').key).toBe('attack.state.off');
    const d = headline(st({ state: 'setup', workspace: { state: 'downloading', commit: '', size: 8e9, progress: 0.4 } }), 'fr');
    expect(d).toEqual({ key: 'attack.state.downloading', params: { done: '3,2', total: '8' } });
    expect(headline(st({ state: 'setup', workspace: { state: 'downloading', commit: '', size: 0, progress: 0 } }), 'fr').key).toBe('attack.state.downloadingNoSize');
    expect(headline(st({ state: 'setup', workspace: { state: 'building', commit: '', size: 0, progress: 0 } }), 'fr').key).toBe('attack.state.building');
    const cur = { problem: 'p', title: 'P', kind: 'known', difficulty: 10, dossier_id: 'd', phase: 'proving', since: 0 };
    expect(headline(st({ state: 'running', current: [cur, { ...cur, problem: 'q' }] }), 'fr')).toEqual({ key: 'attack.state.running', params: {}, plural: 2 });
    expect(headline(st({ state: 'running' }), 'fr').key).toBe('attack.state.looking');
    expect(headline(st({ state: 'budget' }), 'fr').params).toEqual({ cap: '5,00 $' });
    expect(headline(st({ state: 'paused', reason: 'user_jobs' }), 'fr').params).toEqual({ reason: 'user_jobs' });
  });
  it('on / agreement', () => {
    expect(isOn(st({ state: 'budget' }))).toBe(true);
    expect(isOn(st({ state: 'error' }))).toBe(false);
    expect(needsAgreement(st({ workspace: { state: 'none', commit: '', size: 0, progress: 0 } }))).toBe(true);
    expect(needsAgreement(st())).toBe(false);
  });
  it('elapsed time and spend ratio', () => {
    expect(ago(30)).toBe('< 1 min');
    expect(ago(12 * 60 + 5)).toBe('12 min');
    expect(ago(2 * 3600 + 5 * 60)).toBe('2 h 05');
    expect(spentRatio(st({ today: { usd: 7, cap: 5, taken: 0, proofs: 0, released: 0 } }))).toBe(1);
  });
});

describe('checks and plans', () => {
  it('reads every shape', () => {
    expect(readCheck(true).ok).toBe(true);
    expect(readCheck(null).ok).toBe(null);
    expect(readCheck('ok').ok).toBe(true);
    expect(readCheck('forbidden word: sorry')).toEqual({ ok: false, detail: 'forbidden word: sorry' });
    expect(readCheck({ ok: false, detail: 'x' })).toEqual({ ok: false, detail: 'x' });
    expect(readCheck(['propext', 'Classical.choice'], 'axioms').ok).toBe(true);
    expect(readCheck(['propext', 'sorryAx'], 'axioms').ok).toBe(false);
    expect(readCheck({ axioms: ['Quot.sound'] }, 'axioms').ok).toBe(true);
  });
  it('ready only when the three pass', () => {
    expect(allChecksPass(sub())).toBe(true);
    expect(allChecksPass(sub({ check: { local: true, rules: null, axioms: true } }))).toBe(false);
  });
  it('file, path, login', () => {
    expect(fileText({ path: 'A.lean', text: 'x' })).toBe('x');
    expect(filePath(sub({ file: { path: 'FormalConjectures/A.lean', text: '' } }))).toBe('FormalConjectures/A.lean');
    expect(planLogin(sub({ plan: { login: 'ada', requests: [] } }))).toBe('ada');
    expect(planLogin(sub({ plan: { requests: [{ method: 'POST', url: 'https://api.github.com/repos/owner/fc/forks' },
      { method: 'PUT', url: 'https://api.github.com/repos/ada/fc/contents/A.lean' }] } }))).toBe('ada');
  });
  it('says each GitHub request in words', () => {
    const gh = 'https://api.github.com/repos';
    expect(requestWords({ method: 'POST', url: `${gh}/o/fc/forks` })).toEqual({ key: 'attack.req.fork', params: { repo: 'o/fc' } });
    expect(requestWords({ method: 'post', url: `${gh}/ada/fc/git/refs` }).key).toBe('attack.req.branch');
    expect(requestWords({ method: 'PUT', url: `${gh}/ada/fc/contents/A/B%20C.lean` }).params).toEqual({ repo: 'ada/fc', path: 'A/B C.lean' });
    expect(requestWords({ method: 'POST', url: `${gh}/o/fc/pulls` }).key).toBe('attack.req.pr');
    expect(requestWords({ method: 'DELETE', url: `${gh}/o/fc/x` }).key).toBe('attack.req.other');
    for (const k of ['fork', 'branch', 'file', 'pr', 'read', 'other']) {
      expect((fr as Record<string, string>)[`attack.req.${k}`]).toBeTruthy();
      expect((en as Record<string, string>)[`attack.req.${k}`]).toBeTruthy();
    }
  });
  it('marks', () => {
    expect(submissionMark('merged')).toBe('proved');
    expect(submissionMark('rejected')).toBe('failed');
    expect(outcomeMark('solved')).toBe('proved');
    expect(outcomeMark('released')).toBe('draft');
  });
});

describe('live events and history', () => {
  it('reads attack.state in its possible envelopes', () => {
    expect(statusFromEvent({ type: 'attack.state', attack: st({ state: 'running' }) })?.state).toBe('running');
    expect(statusFromEvent({ type: 'attack.state', ...st({ state: 'budget' }) })?.state).toBe('budget');
    expect(statusFromEvent({ type: 'attack.state' })).toBe(null);
  });
  it('merges attack.submission', () => {
    const a = sub({ id: 'a', created: 1 });
    const list = upsertSubmission([a], sub({ id: 'b', created: 2 }));
    expect(list.map((x) => x.id)).toEqual(['b', 'a']);
    expect(upsertSubmission(list, { ...a, state: 'sent' }).find((x) => x.id === 'a')?.state).toBe('sent');
    expect(upsertSubmission(list, { ...a, state: 'discarded' as never }).map((x) => x.id)).toEqual(['b']);
    expect(submissionFromEvent({ type: 'attack.submission', submission: a })?.id).toBe('a');
    expect(submissionFromEvent({ type: 'attack.submission' })).toBe(null);
  });
  it('filters history by kind, newest first, and sums', () => {
    const h = [
      { problem: 'a', title: 'A', kind: 'known', outcome: 'solved' as const, reason: '', t: 1, usd: 0.5, dossier_id: '' },
      { problem: 'b', title: 'B', kind: 'open', outcome: 'released' as const, reason: 'stuck', t: 2, usd: 1.25, dossier_id: '' },
    ];
    expect(filterHistory(h, '').map((x) => x.problem)).toEqual(['b', 'a']);
    expect(filterHistory(h, 'known').map((x) => x.problem)).toEqual(['a']);
    expect(totalUsd(h)).toBe(1.75);
  });
});

describe('API client and words', () => {
  let calls: { url: string; method: string; body: unknown }[] = [];
  beforeEach(() => {
    calls = [];
    configureClient({ fetcher: (async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return new Response('{}', { status: 200 });
    }) as typeof fetch });
  });
  it('uses the contract paths', async () => {
    await attack.get(); await attack.start(); await attack.stop(); await attack.workspace();
    await attack.submissions(); await attack.send('a/b', 'pl-1'); await attack.discard('x'); await attack.history();
    await attack.settings({ attack_parallel: 1 });
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'GET /api/attack', 'POST /api/attack/start', 'POST /api/attack/stop', 'POST /api/attack/workspace', 'GET /api/attack/submissions',
      'POST /api/attack/submissions/a%2Fb/send', 'POST /api/attack/submissions/x/discard', 'GET /api/attack/history', 'PATCH /api/attack/settings']);
    expect(calls[3]!.body).toEqual({ accept: true });
    expect(calls[5]!.body).toEqual({ plan: 'pl-1' });
  });
  it('has every runtime-built word in both languages', () => {
    const need = [
      ...['off', 'setup', 'downloading', 'downloadingNoSize', 'building', 'running.one', 'running.other', 'looking', 'budget', 'paused', 'error'].map((k) => `attack.state.${k}`),
      ...ATTACK_KINDS.flatMap((k) => [`attack.kind.${k}`, `attack.set.kind.${k}`]),
      ...['proof', 'disproof', 'reduction', 'statement'].map((k) => `attack.sub.kind.${k}`),
      ...['ready', 'sent', 'merged', 'rejected', 'expired'].map((k) => `attack.sub.state.${k}`),
      ...['solved', 'released', 'reduced', 'submitted', 'rejected'].map((k) => `attack.hist.outcome.${k}`),
      ...['local', 'rules', 'axioms'].map((k) => `attack.check.${k}`),
    ];
    for (const k of need) {
      expect((fr as Record<string, string>)[k], k).toBeTruthy();
      expect((en as Record<string, string>)[k], k).toBeTruthy();
    }
  });
});
