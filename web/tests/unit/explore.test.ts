import { describe, expect, it } from 'vitest';
import { EN, FR, errText, pick, xt } from '../../src/lib/conjectures/strings';
import { buildPlot, parseCell, shortValue, useLog } from '../../src/lib/conjectures/plot';

const ph = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('conjecture engine strings (S-AW)', () => {
  it('fr and en have the same keys, none empty, same placeholders', () => {
    expect(Object.keys(EN).sort()).toEqual(Object.keys(FR).sort());
    for (const k of Object.keys(FR)) {
      expect(FR[k]!.trim(), `fr ${k}`).not.toBe('');
      expect(EN[k]!.trim(), `en ${k}`).not.toBe('');
      expect(ph(EN[k]!), k).toEqual(ph(FR[k]!));
    }
  });
  it('every kind, state, error and OEIS status the server can send has a label', () => {
    const families: Record<string, string[]> = {
      kind: ['polynomial', 'constant', 'rational', 'recurrence', 'holonomic', 'algebraic_gf', 'multiplicative', 'periodic', 'congruence',
        'residue_periodic', 'all_prime', 'all_square', 'increasing', 'growth', 'equal', 'inequality', 'linear', 'oeis'],
      state: ['todo', 'running', 'awaiting_approval', 'done', 'failed', 'stopped'],
      step: ['explore', 'recognise', 'state', 'attack', 'journal'], stepLead: ['explore', 'recognise', 'state', 'attack', 'journal'],
      cstatus: ['candidate', 'kept', 'survived', 'refuted', 'disputed', 'discarded'],
      oeis: ['ok', 'none', 'off', 'too_short', 'error', 'unrecorded'],
      err: ['empty', 'too_many', 'busy', 'not_approved', 'experiments_host_only', 'bad_code', 'bad_contract', 'no_model', 'no_code',
        'demo_no_kernel', 'calcul_busy', 'run_failed', 'no_table', 'keep_failed', 'refuted', 'nothing_to_export', 'internal',
        'not_checkable', 'no_more_terms', 'not_found'],
    };
    for (const [fam, ks] of Object.entries(families)) for (const k of ks) expect(`${fam}.${k}` in FR, `${fam}.${k}`).toBe(true);
  });
  it('never says « vrai » / “true” about a conjecture', () => {
    for (const v of [...Object.values(FR), ...Object.values(EN)]) expect(/\bvraie?\b|\btrue\b/i.test(v), v).toBe(false);
  });
  it('formats, picks the language and falls back', () => {
    expect(xt('survived', { n: 216, max: 299 })).toBe('Aucun contre-exemple : 216 cas de plus, jusqu’à n = 299.');
    expect(xt('no.such.key')).toBe('no.such.key');
    expect(pick({ fr: 'bonjour', en: 'hello' })).toBe('bonjour');
    expect(pick(null)).toBe('');
    expect(errText('not_approved')).toContain('approuvez');
    expect(errText('unknown_kind')).toBe('');
  });
});

describe('conjecture engine plot (S-AW)', () => {
  it('parses integers, fractions and huge integers; refuses the rest', () => {
    expect(parseCell('12')!.value).toBe(12);
    expect(parseCell('-3/4')!.value).toBe(-0.75);
    expect(parseCell('0')!.value).toBe(0);
    expect(parseCell('abc')).toBeNull();
    expect(parseCell('1.5')).toBeNull();
    expect(parseCell('1/0')).toBeNull();
    const big = parseCell('1' + '0'.repeat(400))!;
    expect(big.value).toBe(Infinity);
    expect(Math.round(big.log)).toBe(400);
  });
  it('scales linearly inside the box, in row order of x', () => {
    const rows = Array.from({ length: 10 }, (_v, n) => [String(n), String(n * n)]);
    const p = buildPlot(rows, 1, 0, 320, 160, 12)!;
    expect(p.log).toBe(false);
    expect(p.points).toHaveLength(10);
    expect(p.points[0]).toMatchObject({ cx: 12, cy: 148 });
    expect(p.points[9]).toMatchObject({ cx: 308, cy: 12 });
    expect(p.path.startsWith('M12 148')).toBe(true);
    for (const q of p.points) { expect(q.cx).toBeGreaterThanOrEqual(12); expect(q.cx).toBeLessThanOrEqual(308); expect(q.cy).toBeGreaterThanOrEqual(12); expect(q.cy).toBeLessThanOrEqual(148); }
  });
  it('switches to a log scale when positive values span many orders of magnitude (also beyond floats)', () => {
    const fact = (n: number) => { let f = 1n; for (let k = 2n; k <= BigInt(n); k++) f *= k; return f.toString(); };
    const rows = Array.from({ length: 200 }, (_v, n) => [String(n), fact(n)]);
    const p = buildPlot(rows, 1)!;
    expect(p.log).toBe(true);
    expect(p.points.every((q) => Number.isFinite(q.cy))).toBe(true);
    expect(useLog([{ value: 1, log: 0 }, { value: 50, log: Math.log10(50) }])).toBe(false);
    expect(useLog([{ value: 0, log: NaN }, { value: 1e9, log: 9 }])).toBe(false);          // a zero: no logarithm
    expect(buildPlot([['0', '-5'], ['1', '100000'], ['2', '7']], 1)!.log).toBe(false);
  });
  it('gives nothing for empty or non-numeric data, and a constant column stays inside the box', () => {
    expect(buildPlot([], 1)).toBeNull();
    expect(buildPlot([['0', 'x']], 1)).toBeNull();
    expect(buildPlot([['0', 'A_'], ['1', 'Bw']], 1)).toBeNull();
    const c = buildPlot([['0', '7'], ['1', '7'], ['2', '7']], 1, 0, 320, 160, 12)!;
    expect(c.points.every((q) => q.cy === 80)).toBe(true);
    expect(shortValue('123456789012345678901234567890')).toBe('1.23e29');
    expect(shortValue('42')).toBe('42');
  });
});
