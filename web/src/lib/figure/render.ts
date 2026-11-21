// Drawing of a figure as a list of primitives in screen pixels: one source for the live SVG view, the SVG/PNG
// exports (TikZ is written from world coordinates in export.ts).
import { parseCurve, sampleCurve, implicitSegments, niceStep, type Sampled, type View, type XY } from './curves';
import { conicAt, type Figure, type Obj, type Pt } from './geometry';

export type Role = 'grid' | 'axis' | 'tick' | 'curve' | 'point' | 'free' | 'line' | 'circle' | 'poly' | 'conic' | 'locus' | 'graph' | 'vertex' | 'label';
export interface Prim {
  kind: 'path' | 'dot' | 'text'; role: Role; d?: string; x?: number; y?: number; r?: number; text?: string;
  color?: string; id?: string; dash?: boolean; fill?: boolean; anchor?: 'start' | 'middle' | 'end';
}
export interface Frame { w: number; h: number; view: View }

/** Same scale on both axes: widen the y range (or x) of the view to the frame's ratio. */
export function fitView(v: View, w: number, h: number): View {
  const sx = (v.xmax - v.xmin) / w, sy = (v.ymax - v.ymin) / h;
  if (sx > sy) { const c = (v.ymin + v.ymax) / 2, half = (sx * h) / 2; return { ...v, ymin: c - half, ymax: c + half }; }
  const c = (v.xmin + v.xmax) / 2, half = (sy * w) / 2;
  return { ...v, xmin: c - half, xmax: c + half };
}
export const toScreen = (f: Frame, x: number, y: number): [number, number] =>
  [((x - f.view.xmin) / (f.view.xmax - f.view.xmin)) * f.w, f.h - ((y - f.view.ymin) / (f.view.ymax - f.view.ymin)) * f.h];
export const toWorld = (f: Frame, sx: number, sy: number): [number, number] =>
  [f.view.xmin + (sx / f.w) * (f.view.xmax - f.view.xmin), f.view.ymin + ((f.h - sy) / f.h) * (f.view.ymax - f.view.ymin)];

const r1 = (v: number) => Math.round(v * 10) / 10;
function pathOf(f: Frame, pts: (XY | Pt)[], close = false): string {
  let s = '';
  pts.forEach((p, i) => {
    const [x, y] = Array.isArray(p) ? toScreen(f, p[0], p[1]) : toScreen(f, p.x, p.y);
    s += `${i ? 'L' : 'M'}${r1(x)} ${r1(y)}`;
  });
  return close ? s + 'Z' : s;
}

/** Part of the line p + s·d inside the view (s limited for segments and rays); null when outside. */
export function clipLine(v: View, p: Pt, d: Pt, smin: number, smax: number): [Pt, Pt] | null {
  let a = smin, b = smax;
  const edges: [number, number, number, number][] = [[-d.x, p.x - v.xmin, 0, 0], [d.x, v.xmax - p.x, 0, 0], [-d.y, p.y - v.ymin, 0, 0], [d.y, v.ymax - p.y, 0, 0]];
  for (const [q, r] of edges) {
    if (Math.abs(q) < 1e-15) { if (r < 0) return null; continue; }
    const t = r / q;
    if (q < 0) a = Math.max(a, t); else b = Math.min(b, t);
  }
  if (a > b) return null;
  return [{ x: p.x + a * d.x, y: p.y + a * d.y }, { x: p.x + b * d.x, y: p.y + b * d.y }];
}

const cache = new Map<string, Sampled | null>();
export function sampled(expr: string, env: Record<string, number>, view: View): Sampled | null {
  const key = `${expr}|${view.xmin},${view.xmax},${view.ymin},${view.ymax}|${JSON.stringify(env)}`;
  if (cache.has(key)) return cache.get(key)!;
  let s: Sampled | null = null;
  try { s = sampleCurve(parseCurve(expr, Object.keys(env), env), view, env); } catch { s = null; }
  if (cache.size > 60) cache.delete(cache.keys().next().value!);
  cache.set(key, s);
  return s;
}

export function graphLayout(g: NonNullable<Figure['graph']>, view: View): Map<string, Pt> {
  const out = new Map<string, Pt>();
  const cx = (view.xmin + view.xmax) / 2, cy = (view.ymin + view.ymax) / 2;
  const R = 0.8 * Math.min(view.xmax - view.xmin, view.ymax - view.ymin) / 2;
  g.vertices.forEach((v, i) => {
    const p = g.pos?.[v];
    out.set(v, p ? { x: p[0], y: p[1] } : { x: cx + R * Math.cos((2 * Math.PI * i) / g.vertices.length + Math.PI / 2), y: cy + R * Math.sin((2 * Math.PI * i) / g.vertices.length + Math.PI / 2) });
  });
  return out;
}

function arrow(f: Frame, from: Pt, to: Pt, size = 9): string {
  const [x1, y1] = toScreen(f, from.x, from.y), [x2, y2] = toScreen(f, to.x, to.y);
  const a = Math.atan2(y2 - y1, x2 - x1);
  const p = (da: number) => `${r1(x2 - size * Math.cos(a + da))} ${r1(y2 - size * Math.sin(a + da))}`;
  return `M${p(0.4)}L${r1(x2)} ${r1(y2)}L${p(-0.4)}`;
}

export function render(fig: Figure, f: Frame): Prim[] {
  const out: Prim[] = [];
  const v = f.view;
  if (fig.grid || fig.axes) {
    const step = niceStep((v.xmax - v.xmin) / Math.max(4, f.w / 70));
    const xs: number[] = [], ys: number[] = [];
    for (let x = Math.ceil(v.xmin / step) * step; x <= v.xmax; x += step) xs.push(+x.toPrecision(12));
    for (let y = Math.ceil(v.ymin / step) * step; y <= v.ymax; y += step) ys.push(+y.toPrecision(12));
    if (fig.grid) {
      let d = '';
      for (const x of xs) { const [sx] = toScreen(f, x, 0); d += `M${r1(sx)} 0L${r1(sx)} ${f.h}`; }
      for (const y of ys) { const [, sy] = toScreen(f, 0, y); d += `M0 ${r1(sy)}L${f.w} ${r1(sy)}`; }
      out.push({ kind: 'path', role: 'grid', d });
    }
    if (fig.axes) {
      const [ox, oy] = toScreen(f, 0, 0);
      const ay = Math.max(0, Math.min(f.h, oy)), ax = Math.max(0, Math.min(f.w, ox));
      out.push({ kind: 'path', role: 'axis', d: `M0 ${r1(ay)}L${f.w} ${r1(ay)}M${r1(ax)} 0L${r1(ax)} ${f.h}` });
      const fmt = (n: number) => String(+n.toPrecision(6)).replace('-', '−');
      for (const x of xs) if (Math.abs(x) > step / 2) { const [sx] = toScreen(f, x, 0); if (sx < 12 || sx > f.w - 12) continue; out.push({ kind: 'text', role: 'tick', x: r1(sx), y: r1(Math.min(f.h - 4, ay + 14)), text: fmt(x), anchor: 'middle' }); }
      for (const y of ys) if (Math.abs(y) > step / 2) { const [, sy] = toScreen(f, 0, y); if (sy < 12 || sy > f.h - 8) continue; out.push({ kind: 'text', role: 'tick', x: r1(Math.max(2, ax - 4)), y: r1(sy + 4), text: fmt(y), anchor: ax - 4 < 20 ? 'start' : 'end' }); }
    }
  }
  const env = fig.env();
  fig.curves.forEach((c, i) => {
    if (c.hidden) return;
    const s = sampled(c.expr, env, v);
    if (!s) return;
    const color = c.color ?? `c${i % 6}`;
    for (const l of s.lines) if (l.length > 1) out.push({ kind: 'path', role: 'curve', d: pathOf(f, l), color, id: c.id });
    for (const p of s.points) { const [x, y] = toScreen(f, p[0], p[1]); out.push({ kind: 'dot', role: 'curve', x: r1(x), y: r1(y), r: 3, color, id: c.id }); }
  });
  if (fig.graph) {
    const pos = graphLayout(fig.graph, v);
    for (const [a, b] of fig.graph.edges) {
      const p = pos.get(a)!, q = pos.get(b)!;
      out.push({ kind: 'path', role: 'graph', d: pathOf(f, [p, q]) });
      if (fig.graph.directed) {
        const back = { x: q.x - (q.x - p.x) * 0.06, y: q.y - (q.y - p.y) * 0.06 };
        out.push({ kind: 'path', role: 'graph', d: arrow(f, p, back) });
      }
    }
    for (const [name, p] of pos) {
      const [x, y] = toScreen(f, p.x, p.y);
      out.push({ kind: 'dot', role: 'vertex', x: r1(x), y: r1(y), r: 9 });
      out.push({ kind: 'text', role: 'label', x: r1(x), y: r1(y + 4), text: name, anchor: 'middle' });
    }
  }
  for (const p of fig.points ?? []) {
    const [x, y] = toScreen(f, p.x, p.y);
    out.push({ kind: 'dot', role: 'point', x: r1(x), y: r1(y), r: 3.5 });
    if (p.label) out.push({ kind: 'text', role: 'label', x: r1(x + 6), y: r1(y - 6), text: p.label });
  }
  const pts: Prim[] = [];
  for (const o of fig.objects) if (!o.hidden && o.val) drawObj(fig, f, o, out, pts);
  return out.concat(pts);   // points on top
}

function drawObj(fig: Figure, f: Frame, o: Obj, out: Prim[], pts: Prim[]) {
  const v = o.val!;
  const color = o.color;
  switch (v.t) {
    case 'point': {
      const [x, y] = toScreen(f, v.x, v.y);
      if (x < -20 || y < -20 || x > f.w + 20 || y > f.h + 20) return;
      pts.push({ kind: 'dot', role: fig.movable(o) ? 'free' : 'point', x: r1(x), y: r1(y), r: fig.movable(o) ? 5 : 4, id: o.id, color });
      pts.push({ kind: 'text', role: 'label', x: r1(x + 7), y: r1(y - 7), text: o.name, id: o.id });
      return;
    }
    case 'line': {
      const [smin, smax] = v.sub === 'line' ? [-Infinity, Infinity] : v.sub === 'ray' ? [0, Infinity] : [0, 1];
      const seg = clipLine(f.view, v.p, v.d, smin, smax);
      if (!seg) return;
      out.push({ kind: 'path', role: 'line', d: pathOf(f, seg), id: o.id, color });
      if (v.sub === 'vector') out.push({ kind: 'path', role: 'line', d: arrow(f, v.p, { x: v.p.x + v.d.x, y: v.p.y + v.d.y }), id: o.id, color });
      return;
    }
    case 'circle': {
      const full = v.a0 === undefined || v.a1 === undefined;
      const a0 = full ? 0 : v.a0!, span = full ? 2 * Math.PI : (((v.a1! - v.a0!) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      const n = Math.max(24, Math.min(360, Math.round(v.r / ((f.view.xmax - f.view.xmin) / f.w) / 2)));
      const ring: Pt[] = [];
      for (let i = 0; i <= n; i++) { const a = a0 + (span * i) / n; ring.push({ x: v.c.x + v.r * Math.cos(a), y: v.c.y + v.r * Math.sin(a) }); }
      out.push({ kind: 'path', role: 'circle', d: pathOf(f, ring, full), id: o.id, color });
      return;
    }
    case 'conic': {
      const k = v.k;
      for (const l of implicitSegments((x, y) => conicAt(k, x, y), f.view, 120, 90)) out.push({ kind: 'path', role: 'conic', d: pathOf(f, l), id: o.id, color });
      return;
    }
    case 'polygon':
      out.push({ kind: 'path', role: 'poly', d: pathOf(f, v.pts, true), id: o.id, color, fill: true });
      return;
    case 'locus':
      for (const l of v.lines) if (l.length > 1) out.push({ kind: 'path', role: 'locus', d: pathOf(f, l), id: o.id, color, dash: true });
      return;
    default:
  }
}
