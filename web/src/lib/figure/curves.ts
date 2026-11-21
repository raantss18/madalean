// Curves of a figure: explicit y = f(x), implicit F(x, y) = 0, parametric (x(t), y(t)), polar r = f(θ) and
// sequences u(n). Sampling is adaptive for explicit curves (break at asymptotes), marching squares refined by
// bisection for implicit ones. Same behaviour as Fikajiana's grapher (ADR 0020), written afresh.
import { compile, evalConst, splitTop, ExprError, type Env, type Fn } from './expr';

export interface View { xmin: number; xmax: number; ymin: number; ymax: number }
export type XY = [number, number];
export type CurveDef =
  | { kind: 'explicit'; f: Fn; dom?: [number, number] }
  | { kind: 'implicit'; F: Fn }
  | { kind: 'parametric'; x: Fn; y: Fn; dom: [number, number]; v: string }
  | { kind: 'polar'; r: Fn; dom: [number, number]; v: string }
  | { kind: 'sequence'; u: Fn; dom: [number, number] | null };
export interface Sampled { lines: XY[][]; points: XY[] }

const DOM_RE = /^([A-Za-zθ]+)\s*(?:in|∈)\s*\[(.+),(.+)\]$/;

function domain(part: string | undefined, env: Env): [string, [number, number]] | null {
  const m = part ? DOM_RE.exec(part.trim()) : null;
  if (!m) return null;
  const a = evalConst(m[2]!, env), b = evalConst(m[3]!, env);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a >= b) throw new ExprError('bad interval');
  return [m[1] === 'theta' ? 'θ' : m[1]!, [a, b]];
}

/** Read a curve written by a person (or by Sage's fig()). `names`: sliders usable in the expression. */
export function parseCurve(src: string, names: string[] = [], env: Env = {}): CurveDef {
  const s = src.trim();
  if (!s) throw new ExprError('empty expression');
  let parts = splitTop(s);
  const dom = domain(parts[parts.length - 1], env);
  if (dom) parts = parts.slice(0, -1);
  const vars = ['x', 'y', 't', 'θ', 'theta', 'n', ...names];
  const c = (e: string) => compile(e, vars);
  // sequences: u(n) = …, u_n = …
  const seq = /^[a-z]\s*(?:\(\s*n\s*\)|_\s*n)\s*=(.+)$/.exec(parts.join(','));
  if (seq && parts.length === 1) return { kind: 'sequence', u: c(seq[1]!).fn, dom: dom ? dom[1] : null };
  // parametric: (x(t), y(t))  or  x = …, y = …
  if (parts.length === 1 && /^\(.*\)$/.test(parts[0]!)) {
    const inner = splitTop(parts[0]!.slice(1, -1));
    if (inner.length === 2) {
      const X = c(inner[0]!), Y = c(inner[1]!);
      const v = [...X.vars, ...Y.vars].find((n) => n === 't' || n === 'θ') ?? 't';
      return { kind: 'parametric', x: X.fn, y: Y.fn, dom: dom?.[1] ?? [-10, 10], v };
    }
  }
  if (parts.length === 2) {
    const px = /^x\s*=(.+)$/.exec(parts[0]!), py = /^y\s*=(.+)$/.exec(parts[1]!);
    if (px && py) {
      const X = c(px[1]!), Y = c(py[1]!);
      const v = [...X.vars, ...Y.vars].find((n) => n === 't' || n === 'θ') ?? 't';
      return { kind: 'parametric', x: X.fn, y: Y.fn, dom: dom?.[1] ?? [-10, 10], v };
    }
  }
  if (parts.length !== 1) throw new ExprError('unexpected « , »');
  const e = parts[0]!;
  const eq = splitTop(e, '=');
  if (eq.length > 2) throw new ExprError('too many « = »');
  if (eq.length === 2) {
    const [l, r] = eq as [string, string];
    if (/^r$/.test(l) || /^r\s*\(\s*(θ|theta|t)\s*\)$/.test(l)) {
      return { kind: 'polar', r: c(r.replace(/theta/g, 'θ')).fn, dom: dom?.[1] ?? [0, 4 * Math.PI], v: 'θ' };
    }
    if (/^(y|[a-z]\s*\(\s*x\s*\))$/.test(l)) {
      const R = c(r);
      if (!R.vars.has('y')) return { kind: 'explicit', f: R.fn, dom: dom?.[1] };
    }
    const L = c(l), R = c(r);
    return { kind: 'implicit', F: (env) => L.fn(env) - R.fn(env) };
  }
  const E = c(e);
  if (E.vars.has('y')) return { kind: 'implicit', F: E.fn };
  if (E.vars.has('θ') && !E.vars.has('x')) return { kind: 'polar', r: E.fn, dom: dom?.[1] ?? [0, 4 * Math.PI], v: 'θ' };
  return { kind: 'explicit', f: E.fn, dom: dom?.[1] };
}

function explicit(f: (x: number) => number, a: number, b: number, view: View, res: number): XY[][] {
  const h = view.ymax - view.ymin;
  const tol = h / 800;
  const lines: XY[][] = [];
  let cur: XY[] = [];
  const flush = () => { if (cur.length > 1) lines.push(cur); else if (cur.length === 1) lines.push(cur); cur = []; };
  const push = (x: number, y: number) => {
    if (!Number.isFinite(y)) { flush(); return; }
    cur.push([x, y]);
  };
  const seg = (x0: number, y0: number, x1: number, y1: number, depth: number) => {
    const xm = (x0 + x1) / 2, ym = f(xm);
    const finite = Number.isFinite(y0) && Number.isFinite(y1) && Number.isFinite(ym);
    if (finite) {
      const between = (ym - y0) * (ym - y1) <= 0 || Math.abs(ym - (y0 + y1) / 2) < Math.abs(y1 - y0);
      if (Math.abs(y1 - y0) > 2 * h && !between) { // a pole between x0 and x1: break the line
        if (depth > 0) { seg(x0, y0, xm, ym, depth - 1); seg(xm, ym, x1, y1, depth - 1); return; }
        flush(); push(x1, y1); return;
      }
      if (depth > 0 && Math.abs(ym - (y0 + y1) / 2) > tol) { seg(x0, y0, xm, ym, depth - 1); seg(xm, ym, x1, y1, depth - 1); return; }
      push(x1, y1); return;
    }
    if (depth > 0) { seg(x0, y0, xm, ym, depth - 1); seg(xm, ym, x1, y1, depth - 1); return; }
    push(x1, y1);
  };
  const n = Math.max(32, Math.round(res / 2));
  let x0 = a, y0 = f(a);
  push(x0, y0);
  for (let i = 1; i <= n; i++) {
    const x1 = a + ((b - a) * i) / n, y1 = f(x1);
    seg(x0, y0, x1, y1, 6);
    x0 = x1; y0 = y1;
  }
  flush();
  // clamp very large values so that SVG paths stay finite
  const lim = Math.max(Math.abs(view.ymin), Math.abs(view.ymax)) + 50 * h;
  return lines.map((l) => l.map(([x, y]) => [x, Math.max(-lim, Math.min(lim, y))] as XY));
}

function curveOf(px: (t: number) => XY, a: number, b: number, view: View, n = 1200): XY[][] {
  const jump = 0.5 * Math.hypot(view.xmax - view.xmin, view.ymax - view.ymin);
  const lines: XY[][] = [];
  let cur: XY[] = [];
  let prev: XY | null = null;
  for (let i = 0; i <= n; i++) {
    const p = px(a + ((b - a) * i) / n);
    if (!Number.isFinite(p[0]) || !Number.isFinite(p[1]) || (prev && Math.hypot(p[0] - prev[0], p[1] - prev[1]) > jump)) {
      if (cur.length > 1) lines.push(cur);
      cur = Number.isFinite(p[0]) && Number.isFinite(p[1]) ? [p] : [];
    } else cur.push(p);
    prev = Number.isFinite(p[0]) && Number.isFinite(p[1]) ? p : null;
  }
  if (cur.length > 1) lines.push(cur);
  return lines;
}

/** Zero set of F in the view: marching squares on a grid, each crossing refined by bisection on its edge. */
export function implicitSegments(F: (x: number, y: number) => number, view: View, nx = 160, ny = 120): XY[][] {
  const dx = (view.xmax - view.xmin) / nx, dy = (view.ymax - view.ymin) / ny;
  const g = new Float64Array((nx + 1) * (ny + 1));
  for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) g[j * (nx + 1) + i] = F(view.xmin + i * dx, view.ymin + j * dy);
  const out: XY[][] = [];
  const sg = (v: number) => (v >= 0 ? 1 : -1);      // zero counts as positive: a crossing is never seen twice
  const root = (x0: number, y0: number, f0: number, x1: number, y1: number, f1: number): XY | null => {
    if (!(Number.isFinite(f0) && Number.isFinite(f1)) || sg(f0) === sg(f1)) return null;
    let a: XY = [x0, y0], b: XY = [x1, y1];
    const s0 = sg(f0);
    for (let k = 0; k < 18; k++) {
      const m: XY = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      const fm = F(m[0], m[1]);
      if (!Number.isFinite(fm)) return null;
      if (sg(fm) === s0) a = m; else b = m;
    }
    const p: XY = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    // a pole (sign change through infinity) keeps |F| large at the crossing
    return Math.abs(F(p[0], p[1])) > 1e-3 * (Math.abs(f0) + Math.abs(f1)) + 1e-9 ? null : p;
  };
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const x = view.xmin + i * dx, y = view.ymin + j * dy, x1 = view.xmin + (i + 1) * dx, y1 = view.ymin + (j + 1) * dy;
    const f00 = g[j * (nx + 1) + i]!, f10 = g[j * (nx + 1) + i + 1]!, f01 = g[(j + 1) * (nx + 1) + i]!, f11 = g[(j + 1) * (nx + 1) + i + 1]!;
    const pts = [root(x, y, f00, x1, y, f10), root(x1, y, f10, x1, y1, f11),
      root(x, y1, f01, x1, y1, f11), root(x, y, f00, x, y1, f01)].filter((p): p is XY => !!p);
    if (pts.length === 2) out.push([pts[0]!, pts[1]!]);
    else if (pts.length === 4) { out.push([pts[0]!, pts[1]!]); out.push([pts[2]!, pts[3]!]); }
  }
  return joinSegments(out);
}

function joinSegments(segs: XY[][]): XY[][] {
  // chain segments sharing an end (exact match: neighbouring cells compute the same edge point)
  const key = (p: XY) => `${p[0].toPrecision(12)},${p[1].toPrecision(12)}`;
  const ends = new Map<string, number[]>();
  segs.forEach((s, k) => { for (const p of [s[0]!, s[1]!]) { const q = key(p); ends.set(q, [...(ends.get(q) ?? []), k]); } });
  const used = new Uint8Array(segs.length);
  const lines: XY[][] = [];
  for (let k = 0; k < segs.length; k++) {
    if (used[k]) continue;
    used[k] = 1;
    const line: XY[] = [segs[k]![0]!, segs[k]![1]!];
    for (const forward of [true, false]) {
      for (;;) {
        const end = forward ? line[line.length - 1]! : line[0]!;
        const next = (ends.get(key(end)) ?? []).find((m) => !used[m]);
        if (next === undefined) break;
        used[next] = 1;
        const s = segs[next]!;
        const other = key(s[0]!) === key(end) ? s[1]! : s[0]!;
        if (forward) line.push(other); else line.unshift(other);
      }
    }
    lines.push(line);
  }
  return lines;
}

export function sampleCurve(def: CurveDef, view: View, env: Env = {}, res = 600): Sampled {
  const e: Env = { ...env };
  switch (def.kind) {
    case 'explicit': {
      const a = Math.max(view.xmin, def.dom?.[0] ?? -Infinity), b = Math.min(view.xmax, def.dom?.[1] ?? Infinity);
      if (!(a < b)) return { lines: [], points: [] };
      return { lines: explicit((x) => { e['x'] = x; return def.f(e); }, a, b, view, res), points: [] };
    }
    case 'implicit':
      return { lines: implicitSegments((x, y) => { e['x'] = x; e['y'] = y; return def.F(e); }, view), points: [] };
    case 'parametric':
      return { lines: curveOf((t) => { e[def.v] = t; return [def.x(e), def.y(e)]; }, def.dom[0], def.dom[1], view), points: [] };
    case 'polar':
      return { lines: curveOf((t) => { e['θ'] = t; e['t'] = t; const r = def.r(e); return [r * Math.cos(t), r * Math.sin(t)]; }, def.dom[0], def.dom[1], view), points: [] };
    case 'sequence': {
      const [a, b] = def.dom ?? [0, 30];
      const points: XY[] = [];
      for (let n = Math.ceil(a); n <= Math.floor(b) && points.length < 2000; n++) {
        e['n'] = n; const u = def.u(e);
        if (Number.isFinite(u)) points.push([n, u]);
      }
      return { lines: [], points };
    }
  }
}

/** Value table of an explicit curve: at most 21 rows, from a to b. */
export function valueTable(def: CurveDef, a: number, b: number, step?: number, env: Env = {}): { x: number; y: number }[] {
  if (def.kind !== 'explicit' && def.kind !== 'sequence') return [];
  const s = step && step > 0 ? step : niceStep((b - a) / 10);
  const out: { x: number; y: number }[] = [];
  const e: Env = { ...env };
  for (let k = 0; out.length < 21; k++) {
    const x = +(a + k * s).toPrecision(12);
    if (x > b + 1e-12) break;
    if (def.kind === 'explicit') { e['x'] = x; out.push({ x, y: def.f(e) }); } else { e['n'] = x; out.push({ x, y: def.u(e) }); }
  }
  return out;
}

export function niceStep(raw: number): number {
  if (!(raw > 0) || !Number.isFinite(raw)) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const m = raw / p;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
}

/** Closest sampled point to (x, y), in world units. */
export function nearestOnCurve(s: Sampled, x: number, y: number): { x: number; y: number; d: number } | null {
  let best: { x: number; y: number; d: number } | null = null;
  const test = (p: XY) => { const d = Math.hypot(p[0] - x, p[1] - y); if (!best || d < best.d) best = { x: p[0], y: p[1], d }; };
  for (const l of s.lines) for (const p of l) test(p);
  for (const p of s.points) test(p);
  return best;
}
