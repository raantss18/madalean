// « Exact ↔ approché » (Fikajiana): a measure is shown exactly when its value is recognisably a small rational
// times 1, √2, √3, √5, √6 or π (√2, π/4, 3√3/2…), else as a decimal written with « ≈ ».
const BASES: [number, string][] = [[1, ''], [Math.SQRT2, '√2'], [Math.sqrt(3), '√3'], [Math.sqrt(5), '√5'], [Math.sqrt(6), '√6'], [Math.PI, 'π']];

export function recognize(v: number): string | null {
  if (!Number.isFinite(v)) return null;
  if (Math.abs(v) < 1e-12) return '0';
  for (const [k, sym] of BASES) {
    for (let q = 1; q <= 12; q++) {
      const p = Math.round((v * q) / k);
      if (p === 0 || Math.abs(p) > 1000) continue;
      if (Math.abs((p * k) / q - v) > 1e-9 * (1 + Math.abs(v))) continue;
      const g = gcd(Math.abs(p), q), pp = p / g, qq = q / g;
      const sign = pp < 0 ? '−' : '';
      const a = Math.abs(pp);
      const num = sym ? (a === 1 ? sym : `${a}${sym}`) : String(a);
      return sign + (qq === 1 ? num : `${num}/${qq}`);
    }
  }
  return null;
}
const gcd = (a: number, b: number): number => (b ? gcd(b, a % b) : a);

export function decimal(v: number, digits = 6): string {
  if (!Number.isFinite(v)) return '—';
  const s = Math.abs(v) >= 1e6 || (Math.abs(v) < 1e-4 && v !== 0) ? v.toExponential(digits - 1) : String(+v.toPrecision(digits));
  return s.replace('-', '−');
}

/** Text of a number: exact when asked and recognisable, else « ≈ decimal » (or « = decimal » when it is exact). */
export function fmtNum(v: number, exact: boolean, unit: 'length' | 'angle' | 'area' | 'slope' | 'plain' = 'plain'): string {
  if (unit === 'angle') {
    const deg = (v * 180) / Math.PI;
    if (exact) { const r = recognize(v); if (r) return `${r} rad`; }
    const d = decimal(deg, 6);
    return Math.abs(deg - Math.round(deg)) < 1e-9 ? `${d}°` : `≈ ${d}°`;
  }
  const r = recognize(v);
  if (exact && r) return r;
  const d = decimal(v);
  return r !== null && !r.includes('√') && !r.includes('π') && !r.includes('/') ? d : `≈ ${d}`;
}

/** Rational written for Sage: a short decimal becomes its exact fraction (0.5 → 1/2), else a close fraction. */
export function toFraction(v: number): string {
  if (!Number.isFinite(v)) return '0';
  if (Number.isInteger(v)) return String(v);
  const s = String(+v.toPrecision(12));
  const m = /^(-?)(\d+)\.(\d{1,6})$/.exec(s);
  if (m) {
    const q = 10 ** m[3]!.length, p = Number(m[2]) * q + Number(m[3]);
    const g = gcd(p, q);
    return `${m[1]}${p / g}/${q / g}`;
  }
  // continued fraction, denominator ≤ 10⁶
  let h0 = 1, h1 = 0, k0 = 0, k1 = 1, x = v;
  for (let i = 0; i < 30; i++) {
    const a = Math.floor(x);
    [h0, h1] = [a * h0 + h1, h0]; [k0, k1] = [a * k0 + k1, k0];
    if (k0 > 1e6 || Math.abs(h0 / k0 - v) < 1e-12) break;
    x = 1 / (x - a);
    if (!Number.isFinite(x)) break;
  }
  return k0 === 1 ? String(h0) : `${h0}/${k0}`;
}
