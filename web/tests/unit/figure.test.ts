import { describe, it, expect } from 'vitest';
import { compile, parse, ExprError } from '../../src/lib/figure/expr';
import { parseCurve, sampleCurve, valueTable, nearestOnCurve } from '../../src/lib/figure/curves';
import { Figure, conicAt } from '../../src/lib/figure/geometry';
import { normalizeSpec, emptySpec, type FigureSpec } from '../../src/lib/figure/spec';
import { toSVG, toTikZ, toSage } from '../../src/lib/figure/export';
import { recognize, fmtNum, toFraction } from '../../src/lib/figure/exact';

const ev = (s: string, env: Record<string, number> = {}) => compile(s, Object.keys(env)).fn(env);
const view = { xmin: -5, xmax: 5, ymin: -5, ymax: 5 };

describe('figure expressions', () => {
  it('precedence and associativity', () => {
    expect(ev('1+2*3')).toBe(7);
    expect(ev('2^3^2')).toBe(512);
    expect(ev('-2^2')).toBe(-4);
    expect(ev('2^-1')).toBe(0.5);
    expect(ev('(1+2)*3')).toBe(9);
    expect(ev('8/2/2')).toBe(2);
  });
  it('implicit multiplication, functions, constants', () => {
    expect(ev('2x', { x: 3 })).toBe(6);
    expect(ev('2(x+1)', { x: 3 })).toBe(8);
    expect(ev('x y', { x: 2, y: 5 })).toBe(10);
    expect(ev('xy', { x: 2, y: 5 })).toBe(10);
    expect(ev('(x+1)(x-1)', { x: 3 })).toBe(8);
    expect(ev('2pi')).toBeCloseTo(2 * Math.PI);
    expect(ev('sin(pi/2) + ln(e) + sqrt(16) + abs(-2)')).toBeCloseTo(8);
    expect(ev('cos θ', { 'θ': 0 })).toBe(1);
    expect(ev('a x', { a: 2, x: 4 })).toBe(8);
    expect(ev('(-8)^(1/3)')).toBeCloseTo(-2);
  });
  it('errors are reported, never evaluated', () => {
    expect(() => parse('2+')).toThrow(ExprError);
    expect(() => parse('foo(2)')).toThrow(ExprError);
    expect(() => parse('alert(1)')).toThrow(ExprError);
    expect(() => parse('x;y')).toThrow(ExprError);
    expect(() => parse('(1')).toThrow(ExprError);
  });
});

describe('curves', () => {
  it('recognises every form', () => {
    expect(parseCurve('sin(x)/x').kind).toBe('explicit');
    expect(parseCurve('y=x^2').kind).toBe('explicit');
    expect(parseCurve('x^2+y^2=4').kind).toBe('implicit');
    expect(parseCurve('(cos(t), sin(t))').kind).toBe('parametric');
    expect(parseCurve('x=cos(t), y=sin(t), t in [0, 2pi]').kind).toBe('parametric');
    expect(parseCurve('r=1+cos(θ)').kind).toBe('polar');
    expect(parseCurve('u(n)=1/n').kind).toBe('sequence');
  });
  it('implicit circle: points satisfy x²+y²=4', () => {
    const s = sampleCurve(parseCurve('x^2+y^2=4'), view);
    const pts = s.lines.flat();
    expect(pts.length).toBeGreaterThan(100);
    for (const [x, y] of pts) expect(Math.abs(x * x + y * y - 4)).toBeLessThan(1e-6);
    expect(s.lines.length).toBeLessThanOrEqual(2);   // chained into one closed line
  });
  it('cardioid r = 1 + cos θ: extreme x is 2, closed', () => {
    const s = sampleCurve(parseCurve('r=1+cos(θ)'), view);
    const xs = s.lines.flat().map((p) => p[0]);
    expect(Math.max(...xs)).toBeCloseTo(2, 3);
    expect(Math.min(...xs)).toBeCloseTo(-0.25, 2);
  });
  it('asymptote of 1/x breaks the line', () => {
    const s = sampleCurve(parseCurve('1/x'), view);
    expect(s.lines.length).toBe(2);
    for (const l of s.lines) expect(l.every(([x]) => Math.sign(x) === Math.sign(l[0]![0]))).toBe(true);
  });
  it('parametric with domain and sequences', () => {
    const s = sampleCurve(parseCurve('x=cos(t), y=sin(t), t in [0, pi]'), view);
    expect(s.lines.flat().every(([, y]) => y >= -1e-9)).toBe(true);
    const u = sampleCurve(parseCurve('u(n)=1/n, n in [1, 10]'), view);
    expect(u.points.length).toBe(10);
    expect(u.points[1]).toEqual([2, 0.5]);
  });
  it('value table and point reading', () => {
    const tb = valueTable(parseCurve('x^2'), -2, 2, 1);
    expect(tb.map((r) => r.y)).toEqual([4, 1, 0, 1, 4]);
    expect(valueTable(parseCurve('x'), 0, 100, 1).length).toBe(21);
    const s = sampleCurve(parseCurve('x^2+y^2=4'), view);
    const n = nearestOnCurve(s, 3, 0)!;
    expect(n.d).toBeCloseTo(1, 2);
  });
});

function fig(): Figure { return Figure.load(emptySpec()); }

describe('geometry', () => {
  it('midpoint and dependency update when a point moves', () => {
    const f = fig();
    const A = f.add('point', [], { x: 0, y: 0 }), B = f.add('point', [], { x: 4, y: 2 });
    const M = f.add('midpoint', [A.id, B.id]);
    expect(M.val).toEqual({ t: 'point', x: 2, y: 1 });
    f.move(B.id, 6, 6);
    expect(f.byId(M.id)!.val).toEqual({ t: 'point', x: 3, y: 3 });
  });
  it('perpendicular through a point', () => {
    const f = fig();
    const A = f.add('point', [], { x: 0, y: 0 }), B = f.add('point', [], { x: 2, y: 1 }), C = f.add('point', [], { x: 1, y: 3 });
    const d = f.add('line', [A.id, B.id]), p = f.add('perpendicular', [d.id, C.id]);
    const I = f.add('intersection', [d.id, p.id]);
    expect(f.relation([d.id, p.id]).now).toContain('perpendicular');
    const v = I.val as { x: number; y: number };
    expect(v.x).toBeCloseTo(2, 9); expect(v.y).toBeCloseTo(1, 9);
  });
  it('circle through 3 points', () => {
    const f = fig();
    const ps = [[2, 0], [0, 2], [-2, 0]].map(([x, y]) => f.add('point', [], { x, y }));
    const c = f.add('circle_3_points', ps.map((p) => p.id));
    expect(c.val).toMatchObject({ t: 'circle', r: 2 });
    expect((c.val as { c: { x: number } }).c.x).toBeCloseTo(0, 12);
  });
  it('conic through 5 points recovers the ellipse x²/9 + y²/4 = 1', () => {
    const f = fig();
    const pts = [0, 1, 2, 3, 4].map((k) => { const a = 0.3 + k * 1.1; return f.add('point', [], { x: 3 * Math.cos(a), y: 2 * Math.sin(a) }); });
    const c = f.add('conic_5_points', pts.map((p) => p.id));
    const k = (c.val as { k: number[] }).k;
    for (const a of [0.1, 1.7, 4]) expect(Math.abs(conicAt(k, 3 * Math.cos(a), 2 * Math.sin(a)))).toBeLessThan(1e-9);
    expect(Math.abs(conicAt(k, 0, 0))).toBeGreaterThan(1e-3);
    const area = f.add('area', [c.id]);
    expect((area.val as { v: number }).v).toBeCloseTo(6 * Math.PI, 6);
    const e = f.add('ellipse', [f.add('point', [], { x: -Math.sqrt(5), y: 0 }).id, f.add('point', [], { x: Math.sqrt(5), y: 0 }).id, pts[0]!.id]);
    for (const a of [0.2, 2.5]) expect(Math.abs(conicAt((e.val as { k: number[] }).k, 3 * Math.cos(a), 2 * Math.sin(a)))).toBeLessThan(1e-9);
  });
  it('rotation of a segment and a circle; tangents from an outside point', () => {
    const f = fig();
    const O = f.add('point', [], { x: 0, y: 0 }), A = f.add('point', [], { x: 1, y: 0 });
    const R = f.add('rotation', [A.id, O.id], { params: [90] });
    expect((R.val as { x: number }).x).toBeCloseTo(0, 12); expect((R.val as { y: number }).y).toBeCloseTo(1, 12);
    const c = f.add('circle_center_radius', [O.id], { params: [1] });
    const P = f.add('point', [], { x: 2, y: 0 });
    const t1 = f.add('tangent', [c.id, P.id], { params: [0] }), t2 = f.add('tangent', [c.id, P.id], { params: [1] });
    expect(f.relation([t1.id, c.id]).now).toContain('tangent');
    expect(f.relation([t2.id, c.id]).now).toContain('tangent');
    const ang = f.add('angle', [f.add('intersection', [t1.id, c.id]).id, P.id, f.add('intersection', [t2.id, c.id]).id]);
    expect((ang.val as { v: number }).v).toBeCloseTo(Math.PI / 3, 6);
  });
  it('undefined objects are hidden, not errors', () => {
    const f = fig();
    const A = f.add('point', [], { x: 0, y: 0 }), B = f.add('point', [], { x: 1, y: 0 }), C = f.add('point', [], { x: 0, y: 1 }), D = f.add('point', [], { x: 1, y: 1 });
    const I = f.add('intersection', [f.add('line', [A.id, B.id]).id, f.add('line', [C.id, D.id]).id]);
    expect(I.val).toBeNull();
    f.move(D.id, 2, 0);
    expect(f.byId(I.id)!.val).toMatchObject({ t: 'point', x: 2, y: 0 });
  });
  it('locus of the midpoint of [AM] when M runs on a circle is a circle', () => {
    const f = fig();
    const O = f.add('point', [], { x: 0, y: 0 }), A = f.add('point', [], { x: 4, y: 0 });
    const c = f.add('circle_center_radius', [O.id], { params: [2] });
    const M = f.add('point_on', [c.id], { params: [1] });
    const I = f.add('midpoint', [A.id, M.id]);
    const L = f.add('locus', [I.id, M.id]);
    const pts = (L.val as { lines: { x: number; y: number }[][] }).lines.flat();
    expect(pts.length).toBeGreaterThan(100);
    for (const p of pts) expect(Math.hypot(p.x - 2, p.y)).toBeCloseTo(1, 9);
    expect(f.byId(M.id)!.params).toEqual([1]);   // the glider is put back
  });
  it('relation: a true property survives 24 deformations, a coincidence does not', () => {
    const f = fig();
    const A = f.add('point', [], { x: 0, y: 0 }), B = f.add('point', [], { x: 4, y: 0 }), C = f.add('point', [], { x: 1, y: 3 });
    const I = f.add('midpoint', [A.id, C.id]), J = f.add('midpoint', [B.id, C.id]);
    const ij = f.add('segment', [I.id, J.id]), ab = f.add('segment', [A.id, B.id]);
    const r = f.relation([ij.id, ab.id]);
    expect(r.now).toEqual(['parallel']);
    expect(r.checked[0]).toEqual({ rel: 'parallel', held: 24, trials: 24 });
    const D = f.add('point', [], { x: 4, y: 3 });
    const cd = f.add('segment', [C.id, D.id]);
    const r2 = f.relation([cd.id, ab.id]);
    expect(r2.now).toContain('parallel');
    expect(r2.checked[0]!.held).toBeLessThan(24);
    expect((f.byId(D.id)!.val as { x: number }).x).toBe(4);   // figure restored
  });
  it('undo / redo, remove takes dependants', () => {
    const f = fig();
    const A = f.add('point', [], { x: 0, y: 0 }), B = f.add('point', [], { x: 1, y: 0 });
    f.add('segment', [A.id, B.id]);
    expect(f.remove(A.id).length).toBe(2);
    expect(f.objects.length).toBe(1);
    f.undo();
    expect(f.objects.length).toBe(3);
    f.redo();
    expect(f.objects.length).toBe(1);
  });
});

describe('spec', () => {
  const spec: FigureSpec = {
    v: 1, title: 'T', view: { xmin: -3, xmax: 3, ymin: -2, ymax: 2 }, grid: false, axes: true, exact: true,
    curves: [{ id: 'f1', expr: 'sin(x)', color: '#ff0000' }],
    objects: [{ id: 'o1', name: 'A', kind: 'point', parents: [], x: 0.5, y: 1 }, { id: 'o2', name: 'B', kind: 'point', parents: [], x: 2, y: 0 },
      { id: 'o3', name: 'd', kind: 'line', parents: ['o1', 'o2'] }, { id: 'o4', name: 'w', kind: 'wormhole', parents: ['o3'], params: [1] }],
    graph: { vertices: ['a', 'b'], edges: [['a', 'b', 3]], pos: { a: [0, 0], b: [1, 1] } },
  };
  it('round trips and keeps unknown kinds with a warning', () => {
    const f = Figure.load(spec);
    expect(f.warnings.some((w) => w.includes('wormhole'))).toBe(true);
    expect(f.toSpec()).toEqual(spec);
    expect(Figure.load(f.toSpec()).toSpec()).toEqual(spec);
  });
  it('tolerates hostile input', () => {
    const w: string[] = [];
    const s = normalizeSpec({ v: 1, view: { xmin: 3, xmax: 1 }, curves: [{ expr: 5 }, { expr: 'x', color: 'url(x)' }], objects: [{ id: 'a', kind: 'point', parents: ['zz'] }], graph: { vertices: ['a'], edges: [['a', 'q']] } }, w);
    expect(s.view.xmin).toBe(-8);
    expect(s.curves).toEqual([{ id: 'f2', expr: 'x' }]);
    expect(s.objects[0]!.parents).toEqual([]);
    expect(s.graph!.edges).toEqual([]);
    expect(w.length).toBeGreaterThan(0);
  });
});

describe('exports', () => {
  const f = fig();
  const A = f.add('point', [], { x: 0.5, y: 0 }), B = f.add('point', [], { x: 2, y: 1.25 }), C = f.add('point', [], { x: 0, y: 2 });
  f.add('segment', [A.id, B.id]);
  const c = f.add('circle_center_point', [A.id, C.id]);
  f.add('polygon', [A.id, B.id, C.id]);
  const d = f.add('line', [B.id, C.id]);
  f.add('intersection', [d.id, c.id], { params: [0] });
  f.add('distance', [A.id, B.id]);
  f.curves.push({ id: 'f1', expr: 'x^2' });
  it('SVG is standalone, without script', () => {
    const s = toSVG(f);
    expect(s.startsWith('<svg')).toBe(true);
    expect(s).toContain('<path'); expect(s).toContain('<circle'); expect(s).toContain('>A</text>');
    expect(s).not.toMatch(/<script|on[a-z]+=/i);
  });
  it('TikZ uses plain TikZ primitives', () => {
    const t = toTikZ(f);
    expect(t).toContain('\\begin{tikzpicture}'); expect(t).toContain('\\end{tikzpicture}');
    expect(t).toContain('circle[radius='); expect(t).toContain('-- cycle'); expect(t).toContain('plot coordinates');
    expect(t).toContain('node[above right] {$A$}');
    expect(t).not.toContain('pgfplots');
  });
  it('Sage code uses exact rationals', () => {
    const s = toSage(f);
    expect(s).toContain('A = vector(QQ, [1/2, 0])');
    expect(s).toContain('B = vector(QQ, [2, 5/4])');
    expect(s).toContain('circle_eq(A,');
    expect(s).toMatch(/= meet\(d, c, /);
    expect(s).toContain('(A - B).norm()');
  });
  it('exact ↔ approximate', () => {
    expect(recognize(Math.SQRT2)).toBe('√2');
    expect(recognize(Math.PI / 4)).toBe('π/4');
    expect(recognize((3 * Math.sqrt(3)) / 2)).toBe('3√3/2');
    expect(recognize(-0.5)).toBe('−1/2');
    expect(recognize(Math.E)).toBeNull();
    expect(fmtNum(Math.SQRT2, true)).toBe('√2');
    expect(fmtNum(Math.SQRT2, false)).toBe('≈ 1.41421');
    expect(fmtNum(Math.PI / 4, false, 'angle')).toBe('45°');
    expect(toFraction(0.125)).toBe('1/8');
    expect(toFraction(1 / 3)).toBe('1/3');
  });
});
