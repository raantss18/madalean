// Dynamic geometry: free points, points on objects, and constructions that depend on them. Moving a point
// recomputes every dependant in creation order (parents are always created first). An undefined result (two
// parallel lines, a point inside a circle for a tangent…) hides the object instead of failing. Tool vocabulary
// from Fikajiana (ADR 0019): the same named tools, the « Relation » check by 24 random deformations; fresh code.
import type { FigureSpec, ObjectSpec, CurveSpec, GraphSpec, ViewBox } from './spec';
import { normalizeSpec, emptySpec } from './spec';
import { implicitSegments, type XY } from './curves';

export interface Pt { x: number; y: number }
export type LineSub = 'line' | 'segment' | 'ray' | 'vector';
export type Val =
  | { t: 'point'; x: number; y: number }
  | { t: 'line'; p: Pt; d: Pt; sub: LineSub }
  | { t: 'circle'; c: Pt; r: number; a0?: number; a1?: number }
  | { t: 'conic'; k: number[] }                       // A x² + B xy + C y² + D x + E y + F = 0
  | { t: 'polygon'; pts: Pt[] }
  | { t: 'number'; v: number; unit: 'length' | 'angle' | 'area' | 'slope' | 'plain' }
  | { t: 'locus'; lines: Pt[][] };

export interface Obj extends ObjectSpec { val: Val | null; known: boolean }
const EPS = 1e-9;
const TAU = 2 * Math.PI;

// ------------------------------------------------------------------ vector helpers
const sub = (a: Pt, b: Pt): Pt => ({ x: a.x - b.x, y: a.y - b.y });
const add = (a: Pt, b: Pt): Pt => ({ x: a.x + b.x, y: a.y + b.y });
const mul = (a: Pt, k: number): Pt => ({ x: a.x * k, y: a.y * k });
const dot = (a: Pt, b: Pt) => a.x * b.x + a.y * b.y;
const cross = (a: Pt, b: Pt) => a.x * b.y - a.y * b.x;
const len = (a: Pt) => Math.hypot(a.x, a.y);
const dist = (a: Pt, b: Pt) => len(sub(a, b));
const perp = (a: Pt): Pt => ({ x: -a.y, y: a.x });
const P = (x: number, y: number): Val => ({ t: 'point', x, y });
const norm = (a: number) => ((a % TAU) + TAU) % TAU;
const ang = (c: Pt, p: Pt) => Math.atan2(p.y - c.y, p.x - c.x);

export function circumcenter(a: Pt, b: Pt, c: Pt): Pt | null {
  const d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
  if (Math.abs(d) < EPS) return null;
  const a2 = dot(a, a), b2 = dot(b, b), c2 = dot(c, c);
  return { x: (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d, y: (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d };
}

/** Line through p with direction d as a·x + b·y = c (unit normal). */
export function lineEq(l: { p: Pt; d: Pt }): [number, number, number] {
  const n = perp(l.d), k = len(n);
  return [n.x / k, n.y / k, (n.x * l.p.x + n.y * l.p.y) / k];
}

export function circleConic(c: Pt, r: number): number[] {
  return [1, 0, 1, -2 * c.x, -2 * c.y, c.x * c.x + c.y * c.y - r * r];
}
export const conicAt = (k: number[], x: number, y: number) => k[0]! * x * x + k[1]! * x * y + k[2]! * y * y + k[3]! * x + k[4]! * y + k[5]!;
const conicGrad = (k: number[], p: Pt): Pt => ({ x: 2 * k[0]! * p.x + k[1]! * p.y + k[3]!, y: k[1]! * p.x + 2 * k[2]! * p.y + k[4]! });

/** Conic X²·p + Y²·q = 1 in the frame centred at c turned by φ. */
function canonicalConic(c: Pt, phi: number, p: number, q: number): number[] {
  const co = Math.cos(phi), si = Math.sin(phi);
  const A = p * co * co + q * si * si, B = 2 * (p - q) * co * si, C = p * si * si + q * co * co;
  return [A, B, C, -2 * A * c.x - B * c.y, -2 * C * c.y - B * c.x, A * c.x * c.x + B * c.x * c.y + C * c.y * c.y - 1];
}

function det(m: number[][]): number {
  const a = m.map((r) => [...r]);
  const n = a.length;
  let d = 1;
  for (let i = 0; i < n; i++) {
    let piv = i;
    for (let r = i + 1; r < n; r++) if (Math.abs(a[r]![i]!) > Math.abs(a[piv]![i]!)) piv = r;
    if (Math.abs(a[piv]![i]!) < 1e-300) return 0;
    if (piv !== i) { [a[i], a[piv]] = [a[piv]!, a[i]!]; d = -d; }
    d *= a[i]![i]!;
    for (let r = i + 1; r < n; r++) {
      const f = a[r]![i]! / a[i]![i]!;
      for (let c = i; c < n; c++) a[r]![c]! -= f * a[i]![c]!;
    }
  }
  return d;
}

/** Conic through five points (null when they do not determine one). */
export function conicThrough(pts: Pt[]): number[] | null {
  const rows = pts.map((p) => [p.x * p.x, p.x * p.y, p.y * p.y, p.x, p.y, 1]);
  const k = [0, 1, 2, 3, 4, 5].map((j) => (j % 2 ? -1 : 1) * det(rows.map((r) => r.filter((_, c) => c !== j))));
  const m = Math.max(...k.map(Math.abs));
  return m < 1e-12 ? null : k.map((v) => v / m);
}

function conicCenter(k: number[]): Pt | null {
  const [A, B, C, D, E] = k as [number, number, number, number, number];
  const d = 4 * A * C - B * B;
  if (Math.abs(d) < 1e-12) return null;
  return { x: (B * E - 2 * C * D) / d, y: (B * D - 2 * A * E) / d };
}

// ------------------------------------------------------------------ intersections
function lineParamOk(l: { sub: LineSub }, s: number) {
  return l.sub === 'line' || (l.sub === 'ray' ? s >= -EPS : s >= -EPS && s <= 1 + EPS);
}
function onArc(c: { c: Pt; a0?: number; a1?: number }, p: Pt) {
  if (c.a0 === undefined || c.a1 === undefined) return true;
  const span = norm(c.a1 - c.a0), a = norm(ang(c.c, p) - c.a0);
  return a <= span + 1e-9;
}
function lineConic(l: { p: Pt; d: Pt; sub: LineSub }, k: number[]): Pt[] {
  const { p, d } = l;
  const [A, B, C, D, E] = k as [number, number, number, number, number];
  const qa = A * d.x * d.x + B * d.x * d.y + C * d.y * d.y;
  const qb = 2 * A * p.x * d.x + B * (p.x * d.y + p.y * d.x) + 2 * C * p.y * d.y + D * d.x + E * d.y;
  const qc = conicAt(k, p.x, p.y);
  let ss: number[];
  if (Math.abs(qa) < 1e-12 * (Math.abs(qb) + Math.abs(qc) + 1)) ss = Math.abs(qb) < 1e-15 ? [] : [-qc / qb];
  else {
    const disc = qb * qb - 4 * qa * qc;
    const scale = qb * qb + Math.abs(4 * qa * qc) + 1e-300;
    if (disc < -1e-10 * scale) ss = [];
    else if (Math.abs(disc) <= 1e-10 * scale) ss = [-qb / (2 * qa)];
    else { const r = Math.sqrt(disc); ss = [(-qb - r) / (2 * qa), (-qb + r) / (2 * qa)].sort((a, b) => a - b); }
  }
  return ss.filter((s) => lineParamOk(l, s)).map((s) => add(p, mul(d, s)));
}
function sampleCircle(c: { c: Pt; r: number }, f: (p: Pt) => number): Pt[] {
  const out: Pt[] = [];
  const at = (t: number) => ({ x: c.c.x + c.r * Math.cos(t), y: c.c.y + c.r * Math.sin(t) });
  const n = 720;
  let t0 = 0, f0 = f(at(0));
  for (let i = 1; i <= n; i++) {
    const t1 = (TAU * i) / n, f1 = f(at(t1));
    if (f0 === 0) out.push(at(t0));
    else if (f0 * f1 < 0) {
      let a = t0, b = t1, fa = f0;
      for (let k = 0; k < 50; k++) { const m = (a + b) / 2, fm = f(at(m)); if (fa * fm <= 0) b = m; else { a = m; fa = fm; } }
      out.push(at((a + b) / 2));
    }
    t0 = t1; f0 = f1;
  }
  return out;
}
export function intersections(a: Val, b: Val): Pt[] {
  if (a.t === 'polygon' && b.t !== 'polygon') return intersections(b, a);
  if (a.t === 'line' && b.t === 'line') {
    const den = cross(a.d, b.d);
    if (Math.abs(den) < EPS) return [];
    const s = cross(sub(b.p, a.p), b.d) / den, u = cross(sub(b.p, a.p), a.d) / den;
    return lineParamOk(a, s) && lineParamOk(b, u) ? [add(a.p, mul(a.d, s))] : [];
  }
  if (a.t === 'line' && b.t === 'polygon') {
    const out: Pt[] = [];
    b.pts.forEach((p, i) => { const q = b.pts[(i + 1) % b.pts.length]!; out.push(...intersections(a, { t: 'line', p, d: sub(q, p), sub: 'segment' })); });
    return out;
  }
  if (a.t === 'line' && (b.t === 'circle' || b.t === 'conic')) {
    const pts = lineConic(a, b.t === 'circle' ? circleConic(b.c, b.r) : b.k);
    return b.t === 'circle' ? pts.filter((p) => onArc(b, p)) : pts;
  }
  if ((a.t === 'circle' || a.t === 'conic') && b.t === 'line') return intersections(b, a);
  if (a.t === 'circle' && b.t === 'circle') {
    const d = dist(a.c, b.c);
    if (d < EPS || d > a.r + b.r + 1e-9 || d < Math.abs(a.r - b.r) - 1e-9) return [];
    const x = (d * d + a.r * a.r - b.r * b.r) / (2 * d);
    const h = Math.sqrt(Math.max(0, a.r * a.r - x * x));
    const u = mul(sub(b.c, a.c), 1 / d), m = add(a.c, mul(u, x));
    const pts = h < 1e-9 ? [m] : [add(m, mul(perp(u), -h)), add(m, mul(perp(u), h))];
    return pts.filter((p) => onArc(a, p) && onArc(b, p));
  }
  if (a.t === 'circle' && b.t === 'conic') return sampleCircle(a, (p) => conicAt(b.k, p.x, p.y)).filter((p) => onArc(a, p));
  if (a.t === 'conic' && b.t === 'circle') return intersections(b, a);
  return [];                 // conic ∩ conic, loci: not computed (said in the docs)
}

// ------------------------------------------------------------------ points on objects
export function atParam(v: Val, t: number): Pt | null {
  switch (v.t) {
    case 'line': {
      const s = v.sub === 'segment' || v.sub === 'vector' ? Math.max(0, Math.min(1, t)) : v.sub === 'ray' ? Math.max(0, t) : t;
      return add(v.p, mul(v.d, s));
    }
    case 'circle': {
      let a = t;
      if (v.a0 !== undefined && v.a1 !== undefined) a = v.a0 + Math.max(0, Math.min(1, t)) * norm(v.a1 - v.a0);
      return { x: v.c.x + v.r * Math.cos(a), y: v.c.y + v.r * Math.sin(a) };
    }
    case 'polygon': {
      const n = v.pts.length;
      if (!n) return null;
      const s = ((t % n) + n) % n, i = Math.floor(s), f = s - i;
      const a = v.pts[i]!, b = v.pts[(i + 1) % n]!;
      return add(a, mul(sub(b, a), f));
    }
    default: return null;
  }
}
export function paramOf(v: Val, q: Pt): number | null {
  switch (v.t) {
    case 'line': return dot(sub(q, v.p), v.d) / dot(v.d, v.d);
    case 'circle': {
      const a = ang(v.c, q);
      if (v.a0 === undefined || v.a1 === undefined) return a;
      return norm(a - v.a0) / (norm(v.a1 - v.a0) || 1);
    }
    case 'polygon': {
      let best = 0, bd = Infinity;
      v.pts.forEach((a, i) => {
        const b = v.pts[(i + 1) % v.pts.length]!, d = sub(b, a);
        const f = Math.max(0, Math.min(1, dot(sub(q, a), d) / (dot(d, d) || 1)));
        const e = dist(q, add(a, mul(d, f)));
        if (e < bd) { bd = e; best = i + f; }
      });
      return best;
    }
    default: return null;
  }
}
function projectConic(k: number[], q: Pt): Pt {
  let p = { ...q };
  for (let i = 0; i < 30; i++) {
    const f = conicAt(k, p.x, p.y), g = conicGrad(k, p), gg = dot(g, g);
    if (gg < 1e-18) break;
    p = sub(p, mul(g, f / gg));
    if (Math.abs(f) < 1e-12) break;
  }
  return p;
}

// ------------------------------------------------------------------ affine maps (transformations)
type Affine = [number, number, number, number, number, number];   // x' = a x + b y + e ; y' = c x + d y + f
const ap = (T: Affine, p: Pt): Pt => ({ x: T[0] * p.x + T[1] * p.y + T[4], y: T[2] * p.x + T[3] * p.y + T[5] });
const al = (T: Affine, v: Pt): Pt => ({ x: T[0] * v.x + T[1] * v.y, y: T[2] * v.x + T[3] * v.y });
function applyMap(T: Affine, v: Val): Val | null {
  const detT = T[0] * T[3] - T[1] * T[2];
  switch (v.t) {
    case 'point': { const q = ap(T, v); return P(q.x, q.y); }
    case 'line': return { t: 'line', p: ap(T, v.p), d: al(T, v.d), sub: v.sub };
    case 'polygon': return { t: 'polygon', pts: v.pts.map((p) => ap(T, p)) };
    case 'locus': return { t: 'locus', lines: v.lines.map((l) => l.map((p) => ap(T, p))) };
    case 'circle': {
      const c = ap(T, v.c), r = v.r * Math.sqrt(Math.abs(detT));
      if (v.a0 === undefined || v.a1 === undefined) return { t: 'circle', c, r };
      const e0 = ap(T, { x: v.c.x + v.r * Math.cos(v.a0), y: v.c.y + v.r * Math.sin(v.a0) });
      const e1 = ap(T, { x: v.c.x + v.r * Math.cos(v.a1), y: v.c.y + v.r * Math.sin(v.a1) });
      return detT > 0 ? { t: 'circle', c, r, a0: ang(c, e0), a1: ang(c, e1) } : { t: 'circle', c, r, a0: ang(c, e1), a1: ang(c, e0) };
    }
    case 'conic': {
      // F'(X) = F(T⁻¹ X): substitute the inverse map
      if (Math.abs(detT) < EPS) return null;
      const ia = T[3] / detT, ib = -T[1] / detT, ic = -T[2] / detT, id = T[0] / detT;
      const ie = -(ia * T[4] + ib * T[5]), iff = -(ic * T[4] + id * T[5]);
      const [A, B, C, D, E, F] = v.k as [number, number, number, number, number, number];
      // x = ia X + ib Y + ie ; y = ic X + id Y + iff
      const qx = [ia, ib, ie], qy = [ic, id, iff];
      const out = [0, 0, 0, 0, 0, 0];
      const prod = (u: number[], w: number[], k: number) => {   // add k·u·w (u, w affine in X, Y)
        out[0]! += k * u[0]! * w[0]!; out[1]! += k * (u[0]! * w[1]! + u[1]! * w[0]!); out[2]! += k * u[1]! * w[1]!;
        out[3]! += k * (u[0]! * w[2]! + u[2]! * w[0]!); out[4]! += k * (u[1]! * w[2]! + u[2]! * w[1]!); out[5]! += k * u[2]! * w[2]!;
      };
      prod(qx, qx, A); prod(qx, qy, B); prod(qy, qy, C);
      const one = [0, 0, 1];
      prod(qx, one, D); prod(qy, one, E); out[5]! += F;
      return { t: 'conic', k: out };
    }
    default: return null;
  }
}
const pointReflection = (o: Pt): Affine => [-1, 0, 0, -1, 2 * o.x, 2 * o.y];
function lineReflection(l: { p: Pt; d: Pt }): Affine {
  const u = mul(l.d, 1 / len(l.d));
  const a = u.x * u.x - u.y * u.y, b = 2 * u.x * u.y;
  return [a, b, b, -a, l.p.x - (a * l.p.x + b * l.p.y), l.p.y - (b * l.p.x - a * l.p.y)];
}
function rotation(o: Pt, th: number): Affine {
  const c = Math.cos(th), s = Math.sin(th);
  return [c, -s, s, c, o.x - c * o.x + s * o.y, o.y - s * o.x - c * o.y];
}
const homothety = (o: Pt, k: number): Affine => [k, 0, 0, k, o.x * (1 - k), o.y * (1 - k)];

// ------------------------------------------------------------------ constructions
type Ctx = { o: Obj; ps: (Val | null)[]; fig: Figure };
const isPt = (v: Val | null | undefined): v is Extract<Val, { t: 'point' }> => v?.t === 'point';
const isLine = (v: Val | null | undefined): v is Extract<Val, { t: 'line' }> => v?.t === 'line';
const isCirc = (v: Val | null | undefined): v is Extract<Val, { t: 'circle' }> => v?.t === 'circle';
const asConic = (v: Val | null | undefined): number[] | null => (v?.t === 'conic' ? v.k : v?.t === 'circle' ? circleConic(v.c, v.r) : null);
const pick = <T extends Val['t']>(ps: (Val | null)[], t: T) => ps.find((v) => v?.t === t) as Extract<Val, { t: T }> | undefined;
function numberArg(c: Ctx, at: number, d = 0): number {
  const v = c.ps[at];
  if (v?.t === 'number') return v.v;
  return c.o.params?.[0] ?? d;
}
const line = (p: Pt, q: Pt, s: LineSub): Val | null => (dist(p, q) < EPS ? null : { t: 'line', p: { x: p.x, y: p.y }, d: sub(q, p), sub: s });

/** kind → how it is computed. Kind ids are the stable spec vocabulary (English snake_case). */
export const KINDS: Record<string, (c: Ctx) => Val | null> = {
  point: ({ o }) => P(o.x ?? 0, o.y ?? 0),
  point_on: ({ o, ps }) => {
    const s = ps[0];
    if (!s) return null;
    if (s.t === 'conic') { const q = projectConic(s.k, { x: o.x ?? 0, y: o.y ?? 0 }); return P(q.x, q.y); }
    const q = atParam(s, o.params?.[0] ?? 0);
    return q ? P(q.x, q.y) : null;
  },
  midpoint: ({ ps }) => {
    const [a, b] = ps;
    if (isPt(a) && isPt(b)) return P((a.x + b.x) / 2, (a.y + b.y) / 2);
    if (isLine(a) && a.sub !== 'line' && a.sub !== 'ray') return P(a.p.x + a.d.x / 2, a.p.y + a.d.y / 2);
    return null;
  },
  intersection: ({ o, ps }) => {
    const [a, b] = ps;
    if (!a || !b) return null;
    const pts = intersections(a, b);
    const q = pts[o.params?.[0] ?? 0];
    return q ? P(q.x, q.y) : null;
  },
  center: ({ ps }) => { const v = ps[0]; if (isCirc(v)) return P(v.c.x, v.c.y); const k = asConic(v); const c = k && conicCenter(k); return c ? P(c.x, c.y) : null; },
  centroid: ({ ps }) => {
    const pts = ps.length === 1 && ps[0]?.t === 'polygon' ? ps[0].pts : ps.filter(isPt);
    if (pts.length < 2) return null;
    if (pts.length >= 3) {     // centroid of the polygonal region
      let A = 0, cx = 0, cy = 0;
      pts.forEach((p, i) => { const q = pts[(i + 1) % pts.length]!; const w = cross(p, q); A += w; cx += (p.x + q.x) * w; cy += (p.y + q.y) * w; });
      if (Math.abs(A) > EPS) return P(cx / (3 * A), cy / (3 * A));
    }
    return P(pts.reduce((s, p) => s + p.x, 0) / pts.length, pts.reduce((s, p) => s + p.y, 0) / pts.length);
  },
  segment: ({ ps: [a, b] }) => (isPt(a) && isPt(b) ? line(a, b, 'segment') : null),
  line: ({ ps: [a, b] }) => (isPt(a) && isPt(b) ? line(a, b, 'line') : null),
  ray: ({ ps: [a, b] }) => (isPt(a) && isPt(b) ? line(a, b, 'ray') : null),
  vector: ({ ps: [a, b] }) => (isPt(a) && isPt(b) ? line(a, b, 'vector') : null),
  parallel: ({ ps }) => { const l = pick(ps, 'line'), p = pick(ps, 'point'); return l && p ? { t: 'line', p: { x: p.x, y: p.y }, d: l.d, sub: 'line' } : null; },
  perpendicular: ({ ps }) => { const l = pick(ps, 'line'), p = pick(ps, 'point'); return l && p ? { t: 'line', p: { x: p.x, y: p.y }, d: perp(l.d), sub: 'line' } : null; },
  perp_bisector: ({ ps: [a, b] }) => {
    if (isLine(a) && a.sub === 'segment') return { t: 'line', p: add(a.p, mul(a.d, 0.5)), d: perp(a.d), sub: 'line' };
    return isPt(a) && isPt(b) && dist(a, b) > EPS ? { t: 'line', p: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, d: perp(sub(b, a)), sub: 'line' } : null;
  },
  angle_bisector: ({ ps: [a, b, c] }) => {
    if (!(isPt(a) && isPt(b) && isPt(c))) return null;
    const u = sub(a, b), w = sub(c, b);
    if (len(u) < EPS || len(w) < EPS) return null;
    let d = add(mul(u, 1 / len(u)), mul(w, 1 / len(w)));
    if (len(d) < 1e-9) d = perp(u);
    return { t: 'line', p: { x: b.x, y: b.y }, d, sub: 'line' };
  },
  tangent: ({ o, ps }) => {
    const curve = ps.find((v) => v?.t === 'circle' || v?.t === 'conic') ?? null, p = pick(ps, 'point');
    const k = asConic(curve);
    if (!k || !p) return null;
    const g = conicGrad(k, p);
    if (Math.abs(conicAt(k, p.x, p.y)) < 1e-9 * (1 + len(g))) return len(g) < EPS ? null : { t: 'line', p: { x: p.x, y: p.y }, d: perp(g), sub: 'line' };
    // polar line of p, then the tangent points on it
    const l1 = k[0]! * p.x + (k[1]! / 2) * p.y + k[3]! / 2, l2 = (k[1]! / 2) * p.x + k[2]! * p.y + k[4]! / 2, l3 = (k[3]! / 2) * p.x + (k[4]! / 2) * p.y + k[5]!;
    if (Math.hypot(l1, l2) < EPS) return null;
    const base = Math.abs(l1) > Math.abs(l2) ? { x: -l3 / l1, y: 0 } : { x: 0, y: -l3 / l2 };
    const pts = lineConic({ p: base, d: { x: -l2, y: l1 }, sub: 'line' }, k);
    const q = pts[o.params?.[0] ?? 0];
    return q ? line(p, q, 'line') : null;
  },
  circle_center_point: ({ ps: [c, a] }) => (isPt(c) && isPt(a) && dist(c, a) > EPS ? { t: 'circle', c: { x: c.x, y: c.y }, r: dist(c, a) } : null),
  circle_center_radius: (cx) => { const c = cx.ps[0]; const r = Math.abs(numberArg(cx, 1, 1)); return isPt(c) && r > EPS ? { t: 'circle', c: { x: c.x, y: c.y }, r } : null; },
  circle_3_points: ({ ps: [a, b, c] }) => {
    if (!(isPt(a) && isPt(b) && isPt(c))) return null;
    const o = circumcenter(a, b, c);
    return o ? { t: 'circle', c: o, r: dist(o, a) } : null;
  },
  arc: ({ ps: [c, a, b] }) => (isPt(c) && isPt(a) && isPt(b) && dist(c, a) > EPS ? { t: 'circle', c: { x: c.x, y: c.y }, r: dist(c, a), a0: ang(c, a), a1: ang(c, b) } : null),
  arc_3_points: ({ ps: [a, b, c] }) => {
    if (!(isPt(a) && isPt(b) && isPt(c))) return null;
    const o = circumcenter(a, b, c);
    if (!o) return null;
    const a0 = ang(o, a), a1 = ang(o, c), am = ang(o, b);
    const through = norm(am - a0) <= norm(a1 - a0);
    return { t: 'circle', c: o, r: dist(o, a), a0: through ? a0 : a1, a1: through ? a1 : a0 };
  },
  semicircle: ({ ps: [a, b] }) => {
    if (!(isPt(a) && isPt(b)) || dist(a, b) < EPS) return null;
    const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    return { t: 'circle', c: m, r: dist(a, b) / 2, a0: ang(m, a), a1: ang(m, a) + Math.PI };
  },
  polygon: ({ ps }) => { const pts = ps.filter(isPt).map((p) => ({ x: p.x, y: p.y })); return pts.length >= 2 && pts.length === ps.length ? { t: 'polygon', pts } : null; },
  regular_polygon: (cx) => {
    const [a, b] = cx.ps;
    const n = Math.round(numberArg(cx, 2, 5));
    if (!(isPt(a) && isPt(b)) || n < 3 || n > 200 || dist(a, b) < EPS) return null;
    const pts: Pt[] = [{ x: a.x, y: a.y }, { x: b.x, y: b.y }];
    const T = rotation({ x: 0, y: 0 }, TAU / n);
    while (pts.length < n) { const p = pts[pts.length - 1]!, q = pts[pts.length - 2]!; pts.push(add(p, al(T, sub(p, q)))); }
    return { t: 'polygon', pts };
  },
  ellipse: ({ ps: [f1, f2, p] }) => {
    if (!(isPt(f1) && isPt(f2) && isPt(p))) return null;
    const a = (dist(p, f1) + dist(p, f2)) / 2, c = dist(f1, f2) / 2;
    if (a <= c + EPS) return null;
    return { t: 'conic', k: canonicalConic({ x: (f1.x + f2.x) / 2, y: (f1.y + f2.y) / 2 }, ang(f1, f2), 1 / (a * a), 1 / (a * a - c * c)) };
  },
  hyperbola: ({ ps: [f1, f2, p] }) => {
    if (!(isPt(f1) && isPt(f2) && isPt(p))) return null;
    const a = Math.abs(dist(p, f1) - dist(p, f2)) / 2, c = dist(f1, f2) / 2;
    if (a < EPS || a >= c - EPS) return null;
    return { t: 'conic', k: canonicalConic({ x: (f1.x + f2.x) / 2, y: (f1.y + f2.y) / 2 }, ang(f1, f2), 1 / (a * a), -1 / (c * c - a * a)) };
  },
  parabola: ({ ps }) => {
    const f = pick(ps, 'point'), l = pick(ps, 'line');
    if (!f || !l) return null;
    const [a, b, c] = lineEq(l);
    if (Math.abs(a * f.x + b * f.y - c) < EPS) return null;
    return { t: 'conic', k: [1 - a * a, -2 * a * b, 1 - b * b, -2 * f.x + 2 * a * c, -2 * f.y + 2 * b * c, f.x * f.x + f.y * f.y - c * c] };
  },
  conic_5_points: ({ ps }) => { const pts = ps.filter(isPt); if (pts.length !== 5) return null; const k = conicThrough(pts); return k ? { t: 'conic', k } : null; },
  point_reflection: ({ ps: [v, o] }) => (v && isPt(o) ? applyMap(pointReflection(o), v) : null),
  line_reflection: ({ ps: [v, l] }) => (v && isLine(l) ? applyMap(lineReflection(l), v) : null),
  translation: ({ ps: [v, w] }) => (v && isLine(w) ? applyMap([1, 0, 0, 1, w.d.x, w.d.y], v) : null),
  rotation: (cx) => {
    const [v, o, n] = cx.ps;
    if (!v || !isPt(o)) return null;
    const th = n?.t === 'number' ? (n.unit === 'angle' ? n.v : (n.v * Math.PI) / 180) : ((cx.o.params?.[0] ?? 90) * Math.PI) / 180;
    return applyMap(rotation(o, th), v);
  },
  homothety: (cx) => { const [v, o] = cx.ps; return v && isPt(o) ? applyMap(homothety(o, numberArg(cx, 2, 2)), v) : null; },
  distance: ({ ps: [a, b] }) => {
    if (isPt(a) && isPt(b)) return { t: 'number', v: dist(a, b), unit: 'length' };
    if (isPt(a) && isLine(b)) { const [p, q, r] = lineEq(b); return { t: 'number', v: Math.abs(p * a.x + q * a.y - r), unit: 'length' }; }
    if (isLine(a) && a.sub !== 'line' && a.sub !== 'ray' && !b) return { t: 'number', v: len(a.d), unit: 'length' };
    if (isCirc(a) && !b) return { t: 'number', v: a.a0 === undefined || a.a1 === undefined ? TAU * a.r : a.r * norm(a.a1 - a.a0), unit: 'length' };
    if (a?.t === 'polygon' && !b) return { t: 'number', v: a.pts.reduce((s, p, i) => s + dist(p, a.pts[(i + 1) % a.pts.length]!), 0), unit: 'length' };
    return null;
  },
  angle: ({ ps: [a, b, c] }) => {
    if (isPt(a) && isPt(b) && isPt(c)) {
      const u = sub(a, b), w = sub(c, b);
      if (len(u) < EPS || len(w) < EPS) return null;
      return { t: 'number', v: Math.acos(Math.max(-1, Math.min(1, dot(u, w) / (len(u) * len(w))))), unit: 'angle' };
    }
    if (isLine(a) && isLine(b)) { const v = Math.acos(Math.min(1, Math.abs(dot(a.d, b.d)) / (len(a.d) * len(b.d)))); return { t: 'number', v, unit: 'angle' }; }
    return null;
  },
  area: ({ ps: [a] }) => {
    if (a?.t === 'polygon') return { t: 'number', v: Math.abs(a.pts.reduce((s, p, i) => s + cross(p, a.pts[(i + 1) % a.pts.length]!), 0)) / 2, unit: 'area' };
    if (isCirc(a)) return { t: 'number', v: a.a0 === undefined || a.a1 === undefined ? Math.PI * a.r * a.r : (a.r * a.r * norm(a.a1 - a.a0)) / 2, unit: 'area' };
    if (a?.t === 'conic') {
      let k = a.k;
      const c = conicCenter(k);
      if (!c || 4 * k[0]! * k[2]! - k[1]! * k[1]! <= 0) return null;
      if (k[0]! < 0) k = k.map((x) => -x);
      const f0 = conicAt(k, c.x, c.y);
      return f0 < 0 ? { t: 'number', v: (2 * Math.PI * -f0) / Math.sqrt(4 * k[0]! * k[2]! - k[1]! * k[1]!), unit: 'area' } : null;
    }
    return null;
  },
  slope: ({ ps: [l] }) => (isLine(l) && Math.abs(l.d.x) > EPS ? { t: 'number', v: l.d.y / l.d.x, unit: 'slope' } : null),
  slider: ({ o }) => ({ t: 'number', v: o.params?.[0] ?? 1, unit: 'plain' }),
  locus: ({ o, fig }) => fig.locusOf(o),
};

/** Which parents a kind expects, for the UI and for loading checks. */
export const ARITY: Record<string, [number, number]> = {
  point: [0, 0], point_on: [1, 1], midpoint: [1, 2], intersection: [2, 2], center: [1, 1], centroid: [1, 50],
  segment: [2, 2], line: [2, 2], ray: [2, 2], vector: [2, 2], parallel: [2, 2], perpendicular: [2, 2],
  perp_bisector: [1, 2], angle_bisector: [3, 3], tangent: [2, 2], circle_center_point: [2, 2],
  circle_center_radius: [1, 2], circle_3_points: [3, 3], arc: [3, 3], arc_3_points: [3, 3], semicircle: [2, 2],
  polygon: [2, 100], regular_polygon: [2, 3], ellipse: [3, 3], hyperbola: [3, 3], parabola: [2, 2], conic_5_points: [5, 5],
  point_reflection: [2, 2], line_reflection: [2, 2], translation: [2, 2], rotation: [2, 3], homothety: [2, 3],
  distance: [1, 2], angle: [2, 3], area: [1, 1], slope: [1, 1], slider: [0, 0], locus: [2, 2],
};

// ------------------------------------------------------------------ relations (Fikajiana's « Relation » tool)
export type RelKey = 'equal' | 'parallel' | 'perpendicular' | 'same_length' | 'incident' | 'tangent' | 'concentric' | 'collinear' | 'concyclic';
const TOL = 1e-7;
function relationsOf(vals: Val[]): RelKey[] {
  const out: RelKey[] = [];
  const eq = (u: number, v: number) => Math.abs(u - v) < TOL * (1 + Math.abs(u) + Math.abs(v));
  if (vals.length >= 3 && vals.every(isPt)) {
    const p = vals as Pt[];
    if (p.slice(2).every((q) => Math.abs(cross(sub(p[1]!, p[0]!), sub(q, p[0]!))) < TOL * (1 + dot(sub(p[1]!, p[0]!), sub(p[1]!, p[0]!))))) out.push('collinear');
    else if (p.length >= 4) { const o = circumcenter(p[0]!, p[1]!, p[2]!); if (o && p.slice(3).every((q) => eq(dist(o, q), dist(o, p[0]!)))) out.push('concyclic'); }
    return out;
  }
  const [a, b] = vals as [Val, Val];
  if (isPt(a) && isPt(b)) { if (dist(a, b) < TOL) out.push('equal'); return out; }
  if (isPt(a) || isPt(b)) {
    const p = (isPt(a) ? a : b) as Pt, f = isPt(a) ? b : a;
    let on = false;
    if (isLine(f)) { const [u, v, w] = lineEq(f); on = Math.abs(u * p.x + v * p.y - w) < TOL * (1 + Math.abs(w)); }
    else if (isCirc(f)) on = eq(dist(f.c, p), f.r) && onArc(f, p);
    else if (f.t === 'conic') { const g = conicGrad(f.k, p); on = Math.abs(conicAt(f.k, p.x, p.y)) < TOL * (1 + len(g)); }
    else if (f.t === 'polygon') { const t = paramOf(f, p); const q = t === null ? null : atParam(f, t); on = !!q && dist(p, q) < TOL; }
    if (on) out.push('incident');
    return out;
  }
  if (isLine(a) && isLine(b)) {
    if (Math.abs(cross(a.d, b.d)) < TOL * len(a.d) * len(b.d)) {
      const [u, v, w] = lineEq(a);
      out.push(Math.abs(u * b.p.x + v * b.p.y - w) < TOL * (1 + Math.abs(w)) ? 'equal' : 'parallel');
    }
    if (Math.abs(dot(a.d, b.d)) < TOL * len(a.d) * len(b.d)) out.push('perpendicular');
    if (a.sub !== 'line' && b.sub !== 'line' && a.sub !== 'ray' && b.sub !== 'ray' && eq(len(a.d), len(b.d))) out.push('same_length');
    return out;
  }
  if ((isLine(a) && isCirc(b)) || (isCirc(a) && isLine(b))) {
    const l = (isLine(a) ? a : b) as Extract<Val, { t: 'line' }>, c = (isCirc(a) ? a : b) as Extract<Val, { t: 'circle' }>;
    const [u, v, w] = lineEq(l);
    if (eq(Math.abs(u * c.c.x + v * c.c.y - w), c.r)) out.push('tangent');
    return out;
  }
  if (isCirc(a) && isCirc(b)) {
    const d = dist(a.c, b.c);
    if (eq(a.r, b.r)) out.push(d < TOL ? 'equal' : 'same_length');
    if (d < TOL && !eq(a.r, b.r)) out.push('concentric');
    else if (d >= TOL && (eq(d, a.r + b.r) || eq(d, Math.abs(a.r - b.r)))) out.push('tangent');
    return out;
  }
  if (a.t === 'number' && b.t === 'number' && eq(a.v, b.v)) out.push('equal');
  return out;
}
export interface RelationResult { now: RelKey[]; checked: { rel: RelKey; held: number; trials: number }[] }

/** Small deterministic generator for the random deformations (tests reproducible). */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// ------------------------------------------------------------------ the figure
const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
export class Figure {
  objects: Obj[] = [];
  curves: CurveSpec[] = [];
  view: ViewBox = emptySpec().view;
  grid = true; axes = true; exact = false;
  title?: string; graph?: GraphSpec; points?: { x: number; y: number; label?: string }[];
  warnings: string[] = [];
  private undoStack: string[] = [];
  private redoStack: string[] = [];

  static load(raw: unknown): Figure {
    const f = new Figure();
    const spec = normalizeSpec(raw, f.warnings);
    f.apply(spec);
    return f;
  }
  private apply(spec: FigureSpec) {
    this.view = { ...spec.view };
    this.grid = spec.grid ?? true; this.axes = spec.axes ?? true; this.exact = spec.exact ?? false;
    this.title = spec.title; this.graph = spec.graph; this.points = spec.points;
    this.curves = spec.curves.map((c) => ({ ...c }));
    this.objects = spec.objects.map((o) => {
      const known = o.kind in KINDS;
      const w = `unknown kind « ${o.kind} » (${o.name})`;
      if (!known && !this.warnings.includes(w)) this.warnings.push(w);
      return { ...o, parents: [...o.parents], ...(o.params ? { params: [...o.params] } : {}), val: null, known };
    });
    this.recompute();
  }
  toSpec(): FigureSpec {
    const s: FigureSpec = { v: 1, view: { ...this.view }, grid: this.grid, axes: this.axes, exact: this.exact,
      curves: this.curves.map((c) => ({ ...c })),
      objects: this.objects.map(({ val: _v, known: _k, ...o }) => ({ ...o, parents: [...o.parents], ...(o.params ? { params: [...o.params] } : {}) })) };
    if (this.title !== undefined) s.title = this.title;
    if (this.graph) s.graph = this.graph;
    if (this.points) s.points = this.points;
    return s;
  }
  byId(id: string): Obj | undefined { return this.objects.find((o) => o.id === id); }
  byName(name: string): Obj | undefined { return this.objects.find((o) => o.name === name); }
  /** Numbers usable in curve expressions: sliders and measures, by name. */
  env(): Record<string, number> {
    const e: Record<string, number> = {};
    for (const o of this.objects) if (o.val?.t === 'number' && /^[A-Za-z][A-Za-z0-9_]*$/.test(o.name)) e[o.name] = o.val.v;
    return e;
  }
  recompute(from = 0): void {
    const idx = new Map(this.objects.map((o, i) => [o.id, i]));
    for (let i = from; i < this.objects.length; i++) {
      const o = this.objects[i]!;
      if (!o.known) { o.val = null; continue; }
      const ps = o.parents.map((p) => { const j = idx.get(p); return j !== undefined && j < i ? this.objects[j]!.val : null; });
      try {
        const v = ps.some((x) => x === null) && o.kind !== 'locus' ? null : KINDS[o.kind]!({ o, ps, fig: this });
        o.val = v && valid(v) ? v : null;
      } catch { o.val = null; }
    }
  }
  locusOf(o: Obj): Val | null {
    const [pid, gid] = o.parents;
    const pi = this.objects.findIndex((x) => x.id === pid), gi = this.objects.findIndex((x) => x.id === gid);
    const g = this.objects[gi];
    if (!g || pi < 0 || g.kind !== 'point_on' || gi > pi) return null;
    const support = this.byId(g.parents[0] ?? '')?.val;
    if (!support) return null;
    const saved = { params: g.params ? [...g.params] : undefined, x: g.x, y: g.y };
    const ts: (number | Pt)[] = [];
    if (support.t === 'line') {
      if (support.sub === 'segment' || support.sub === 'vector') for (let i = 0; i <= 200; i++) ts.push(i / 200);
      else { const span = Math.hypot(this.view.xmax - this.view.xmin, this.view.ymax - this.view.ymin) / len(support.d); for (let i = 0; i <= 300; i++) ts.push((support.sub === 'ray' ? 0 : -span) + (i / 300) * span * (support.sub === 'ray' ? 1 : 2)); }
    } else if (support.t === 'circle') for (let i = 0; i <= 240; i++) ts.push(support.a0 === undefined ? (TAU * i) / 240 : i / 240);
    else if (support.t === 'polygon') for (let i = 0; i <= 60 * support.pts.length; i++) ts.push(i / 60);
    else if (support.t === 'conic') for (const l of implicitSegments((x, y) => conicAt(support.k, x, y), this.view, 80, 60)) for (const q of l) ts.push({ x: q[0], y: q[1] });
    const lines: Pt[][] = [];
    let cur: Pt[] = [];
    for (const t of ts) {
      if (typeof t === 'number') g.params = [t]; else { g.x = t.x; g.y = t.y; }
      this.recomputeRange(gi, pi);
      const v = this.objects[pi]!.val;
      if (isPt(v)) cur.push({ x: v.x, y: v.y }); else if (cur.length) { lines.push(cur); cur = []; }
    }
    if (cur.length) lines.push(cur);
    g.params = saved.params; g.x = saved.x; g.y = saved.y;
    this.recomputeRange(gi, pi);
    return lines.length ? { t: 'locus', lines } : null;
  }
  private recomputeRange(a: number, b: number) {
    const idx = new Map(this.objects.map((o, i) => [o.id, i]));
    for (let i = a; i <= b; i++) {
      const o = this.objects[i]!;
      if (!o.known || o.kind === 'locus') continue;
      const ps = o.parents.map((p) => this.objects[idx.get(p) ?? -1]?.val ?? null);
      try { const v = ps.some((x) => x === null) ? null : KINDS[o.kind]!({ o, ps, fig: this }); o.val = v && valid(v) ? v : null; } catch { o.val = null; }
    }
  }

  // ---------------------------------------------------------------- editing (with undo)
  snapshot(): void {
    this.undoStack.push(JSON.stringify(this.toSpec()));
    if (this.undoStack.length > 100) this.undoStack.shift();
    this.redoStack = [];
  }
  get canUndo() { return this.undoStack.length > 0; }
  get canRedo() { return this.redoStack.length > 0; }
  undo(): boolean { const s = this.undoStack.pop(); if (!s) return false; this.redoStack.push(JSON.stringify(this.toSpec())); this.apply(JSON.parse(s)); return true; }
  redo(): boolean { const s = this.redoStack.pop(); if (!s) return false; this.undoStack.push(JSON.stringify(this.toSpec())); this.apply(JSON.parse(s)); return true; }

  nextName(kind: string): string {
    const taken = new Set(this.objects.map((o) => o.name));
    const pointish = ['point', 'point_on', 'midpoint', 'intersection', 'center', 'centroid'].includes(kind);
    const pool = pointish ? LETTERS : kind === 'slider' ? 'abcdkmpqrsuvw' : ['line', 'ray', 'parallel', 'perpendicular', 'perp_bisector', 'angle_bisector', 'tangent'].includes(kind) ? 'defgh'
      : kind.startsWith('circle') || kind.startsWith('arc') || kind === 'semicircle' ? 'c' : kind === 'polygon' || kind === 'regular_polygon' ? 'P' : kind === 'locus' ? 'L' : 'm';
    for (let k = 0; ; k++) for (const ch of pool) { const n = k ? `${ch}_${k}` : ch; if (!taken.has(n)) return n; }
  }
  add(kind: string, parents: string[] = [], opts: Partial<ObjectSpec> = {}, record = true): Obj {
    if (record) this.snapshot();
    let n = 1;
    while (this.byId(`o${n}`)) n++;
    const o: Obj = { id: opts.id ?? `o${n}`, name: opts.name ?? this.nextName(kind), kind, parents, val: null, known: kind in KINDS };
    for (const k of ['params', 'x', 'y', 'hidden', 'color'] as const) if (opts[k] !== undefined) (o as unknown as Record<string, unknown>)[k] = opts[k];
    this.objects.push(o);
    this.recompute(this.objects.length - 1);
    return o;
  }
  /** Drag a free point or a point on an object (other objects do not move by themselves). */
  move(id: string, x: number, y: number): boolean {
    const i = this.objects.findIndex((o) => o.id === id);
    const o = this.objects[i];
    if (!o) return false;
    if (o.kind === 'point') { o.x = x; o.y = y; }
    else if (o.kind === 'point_on') {
      const s = this.byId(o.parents[0] ?? '')?.val;
      if (!s) return false;
      if (s.t === 'conic') { o.x = x; o.y = y; }
      else { const t = paramOf(s, { x, y }); if (t === null) return false; o.params = [t]; }
    } else return false;
    this.recompute(i);
    return true;
  }
  setParam(id: string, value: number): void {
    const i = this.objects.findIndex((o) => o.id === id);
    const o = this.objects[i];
    if (!o) return;
    o.params = [value, ...(o.params ?? []).slice(1)];
    this.recompute(i);
  }
  /** Remove an object and everything built on it. */
  remove(id: string, record = true): string[] {
    if (record) this.snapshot();
    const gone = new Set([id]);
    for (const o of this.objects) if (o.parents.some((p) => gone.has(p))) gone.add(o.id);
    this.objects = this.objects.filter((o) => !gone.has(o.id));
    this.recompute();
    return [...gone];
  }
  movable(o: Obj) { return o.kind === 'point' || o.kind === 'point_on'; }

  /** What is true between these objects now, then how often it stays true over 24 random deformations. */
  relation(ids: string[], trials = 24, seed = 1): RelationResult {
    const vals = () => ids.map((id) => this.byId(id)?.val).filter((v): v is Val => !!v);
    const v0 = vals();
    const now = v0.length === ids.length ? relationsOf(v0) : [];
    const saved = this.objects.map((o) => ({ x: o.x, y: o.y, params: o.params ? [...o.params] : undefined }));
    const restore = () => { this.objects.forEach((o, i) => { const s = saved[i]!; o.x = s.x; o.y = s.y; if (s.params) o.params = [...s.params]; }); this.recompute(); };
    const rand = rng(seed);
    const span = Math.max(this.view.xmax - this.view.xmin, this.view.ymax - this.view.ymin) / 4;
    const held = new Map(now.map((r) => [r, 0]));
    for (let k = 0; k < trials; k++) {
      for (const o of this.objects) {
        if (o.kind === 'point') { o.x = (o.x ?? 0) + (rand() - 0.5) * span; o.y = (o.y ?? 0) + (rand() - 0.5) * span; }
        else if (o.kind === 'point_on' && o.params) o.params = [o.params[0]! + (rand() - 0.5)];
      }
      this.recompute();
      const v = vals();
      const rs = v.length === ids.length ? relationsOf(v) : [];
      for (const r of now) if (rs.includes(r)) held.set(r, held.get(r)! + 1);
      restore();
    }
    return { now, checked: now.map((rel) => ({ rel, held: held.get(rel)!, trials })) };
  }
}

function valid(v: Val): boolean {
  const ok = (p: Pt) => Number.isFinite(p.x) && Number.isFinite(p.y);
  switch (v.t) {
    case 'point': return ok(v);
    case 'line': return ok(v.p) && ok(v.d) && len(v.d) > EPS;
    case 'circle': return ok(v.c) && Number.isFinite(v.r) && v.r > 0;
    case 'conic': return v.k.every(Number.isFinite);
    case 'polygon': return v.pts.every(ok);
    case 'number': return Number.isFinite(v.v);
    case 'locus': return true;
  }
}

export type { XY };
