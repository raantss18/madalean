// Exports of a figure: standalone SVG (no script), PNG (canvas, ×2, side ≤ 4096), TikZ (plain TikZ, no pgfplots)
// and Sage code (exact rationals) — the « send the figure to Sage » bridge.
import { render, fitView, clipLine, graphLayout, sampled, type Prim, type Frame } from './render';
import { implicitSegments } from './curves';
import { conicAt, type Figure, type Obj } from './geometry';
import { toFraction } from './exact';

export const PALETTE = ['#2c46ad', '#b42318', '#1a7246', '#8a5200', '#6a3fb0', '#1a6a7a'];
const ROLE: Record<string, { stroke: string; width: number; fill?: string }> = {
  grid: { stroke: '#e2e5eb', width: 1 }, axis: { stroke: '#5b6376', width: 1.2 }, tick: { stroke: 'none', width: 0, fill: '#464e62' },
  curve: { stroke: '#2c46ad', width: 2 }, point: { stroke: '#1a2031', width: 1, fill: '#1a2031' }, free: { stroke: '#1a2031', width: 1.5, fill: '#2c46ad' },
  line: { stroke: '#1a2031', width: 1.6 }, circle: { stroke: '#1a2031', width: 1.6 }, conic: { stroke: '#6a3fb0', width: 1.8 },
  poly: { stroke: '#1a2031', width: 1.6, fill: 'rgba(44,70,173,0.08)' }, locus: { stroke: '#b42318', width: 1.8 },
  graph: { stroke: '#464e62', width: 1.4 }, vertex: { stroke: '#1a2031', width: 1.4, fill: '#ffffff' }, label: { stroke: 'none', width: 0, fill: '#1a2031' },
};
export const colorOf = (c: string | undefined, fallback: string) => (c && /^c\d$/.test(c) ? PALETTE[Number(c[1])]! : c ?? fallback);
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

export function frameFor(fig: Figure, w = 800, h = 560): Frame { return { w, h, view: fitView(fig.view, w, h) }; }

export function toSVG(fig: Figure, w = 800, h = 560): string {
  const f = frameFor(fig, w, h);
  const body = render(fig, f).map((p) => primSVG(p)).join('');
  const title = fig.title ? `<title>${esc(fig.title)}</title>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="sans-serif" font-size="12">${title}<rect width="100%" height="100%" fill="#ffffff"/>${body}</svg>`;
}
function primSVG(p: Prim): string {
  const st = ROLE[p.role]!;
  const stroke = p.role === 'curve' || p.color ? colorOf(p.color, st.stroke) : st.stroke;
  if (p.kind === 'path') return `<path d="${p.d}" fill="${p.fill ? st.fill ?? 'none' : 'none'}" stroke="${stroke}" stroke-width="${st.width}"${p.dash ? ' stroke-dasharray="5 4"' : ''} stroke-linejoin="round" stroke-linecap="round"/>`;
  if (p.kind === 'dot') return `<circle cx="${p.x}" cy="${p.y}" r="${p.r}" fill="${p.role === 'curve' ? stroke : st.fill ?? stroke}" stroke="${p.role === 'free' ? '#ffffff' : stroke}" stroke-width="${st.width}"/>`;
  return `<text x="${p.x}" y="${p.y}" fill="${st.fill}"${p.anchor ? ` text-anchor="${p.anchor}"` : ''}>${esc(p.text ?? '')}</text>`;
}

/** PNG drawn directly on a canvas (Path2D accepts the same path strings): no image decoding, CSP-safe. */
export async function toPNG(fig: Figure, w = 800, h = 560, scale = 2): Promise<Blob> {
  const k = Math.min(scale, 4096 / Math.max(w, h));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(w * k); canvas.height = Math.round(h * k);
  const g = canvas.getContext('2d')!;
  g.scale(k, k);
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, w, h);
  g.font = '12px sans-serif'; g.lineJoin = 'round'; g.lineCap = 'round';
  for (const p of render(fig, frameFor(fig, w, h))) {
    const st = ROLE[p.role]!;
    const stroke = p.role === 'curve' || p.color ? colorOf(p.color, st.stroke) : st.stroke;
    if (p.kind === 'path') {
      const path = new Path2D(p.d);
      if (p.fill && st.fill) { g.fillStyle = st.fill; g.fill(path); }
      g.setLineDash(p.dash ? [5, 4] : []); g.strokeStyle = stroke; g.lineWidth = st.width; g.stroke(path);
    } else if (p.kind === 'dot') {
      g.setLineDash([]); g.beginPath(); g.arc(p.x!, p.y!, p.r!, 0, 2 * Math.PI);
      g.fillStyle = p.role === 'curve' ? stroke : st.fill ?? stroke; g.fill();
      g.strokeStyle = p.role === 'free' ? '#ffffff' : stroke; g.lineWidth = st.width; g.stroke();
    } else {
      g.fillStyle = st.fill!; g.textAlign = p.anchor === 'middle' ? 'center' : p.anchor === 'end' ? 'right' : 'left';
      g.fillText(p.text ?? '', p.x!, p.y!);
    }
  }
  return new Promise((ok, ko) => canvas.toBlob((b) => (b ? ok(b) : ko(new Error('png'))), 'image/png'));
}

// ------------------------------------------------------------------ TikZ
const n4 = (v: number) => String(+v.toFixed(4));
const xy = (x: number, y: number) => `(${n4(x)},${n4(y)})`;
const texName = (s: string) => s.replace(/[^A-Za-z0-9_']/g, '').replace(/_(\w+)/, '_{$1}') || '?';
function thin<T>(a: T[], max = 400): T[] { if (a.length <= max) return a; const k = Math.ceil(a.length / max); return a.filter((_, i) => i % k === 0 || i === a.length - 1); }

export function toTikZ(fig: Figure, widthCm = 12): string {
  const v = fig.view;
  const s = widthCm / (v.xmax - v.xmin);
  const L: string[] = [];
  const colors = new Map<string, string>();
  const col = (c: string) => { const hex = c.replace('#', '').toUpperCase(); const full = hex.length === 3 ? hex.split('').map((ch) => ch + ch).join('') : hex.slice(0, 6); if (!colors.has(full)) colors.set(full, `mlc${colors.size}`); return colors.get(full)!; };
  L.push(`\\begin{tikzpicture}[x=${n4(s)}cm,y=${n4(s)}cm,line cap=round,line join=round]`);
  L.push(`  \\clip ${xy(v.xmin, v.ymin)} rectangle ${xy(v.xmax, v.ymax)};`);
  if (fig.grid) {
    const step = niceStepT((v.xmax - v.xmin) / 12);
    L.push(`  \\draw[very thin,black!12,step=${n4(step)}] ${xy(v.xmin, v.ymin)} grid ${xy(v.xmax, v.ymax)};`);
  }
  if (fig.axes) L.push(`  \\draw[->,black!70] ${xy(v.xmin, 0)} -- ${xy(v.xmax, 0)} node[below left] {$x$};`, `  \\draw[->,black!70] ${xy(0, v.ymin)} -- ${xy(0, v.ymax)} node[below right] {$y$};`);
  const env = fig.env();
  fig.curves.forEach((c, i) => {
    if (c.hidden) return;
    const sm = sampled(c.expr, env, v);
    if (!sm) return;
    const cn = col(colorOf(c.color, PALETTE[i % 6]!));
    for (const l of sm.lines) if (l.length > 1) L.push(`  \\draw[${cn},thick] plot coordinates {${thin(l).map((p) => xy(p[0], p[1])).join(' ')}};`);
    for (const p of sm.points) L.push(`  \\fill[${cn}] ${xy(p[0], p[1])} circle[radius=1.5pt];`);
  });
  if (fig.graph) {
    const pos = graphLayout(fig.graph, v);
    const id = new Map(fig.graph.vertices.map((name, i) => [name, `v${i}`]));
    for (const [name, p] of pos) L.push(`  \\node[circle,draw,fill=white,inner sep=1.5pt] (${id.get(name)}) at ${xy(p.x, p.y)} {\\scriptsize ${texName(name)}};`);
    for (const [a, b] of fig.graph.edges) L.push(`  \\draw${fig.graph.directed ? '[->]' : ''} (${id.get(a)}) -- (${id.get(b)});`);
  }
  for (const p of fig.points ?? []) L.push(`  \\fill ${xy(p.x, p.y)} circle[radius=1.5pt]${p.label ? ` node[above right] {$${texName(p.label)}$}` : ''};`);
  const later: string[] = [];
  for (const o of fig.objects) {
    if (o.hidden || !o.val) continue;
    const c = o.color ? `,${col(o.color)}` : '';
    const val = o.val;
    switch (val.t) {
      case 'point': later.push(`  \\fill${c ? `[${c.slice(1)}]` : ''} ${xy(val.x, val.y)} circle[radius=1.5pt] node[above right] {$${texName(o.name)}$};`); break;
      case 'line': {
        const [a, b] = val.sub === 'line' ? [-Infinity, Infinity] : val.sub === 'ray' ? [0, Infinity] : [0, 1];
        const seg = clipLine(v, val.p, val.d, a, b);
        if (seg) L.push(`  \\draw[thick${val.sub === 'vector' ? ',->' : ''}${c}] ${xy(seg[0].x, seg[0].y)} -- ${xy(seg[1].x, seg[1].y)};`);
        break;
      }
      case 'circle':
        if (val.a0 === undefined || val.a1 === undefined) L.push(`  \\draw[thick${c}] ${xy(val.c.x, val.c.y)} circle[radius=${n4(val.r)}];`);
        else {
          let a1 = val.a1; while (a1 <= val.a0) a1 += 2 * Math.PI;
          L.push(`  \\draw[thick${c}] ${xy(val.c.x + val.r * Math.cos(val.a0), val.c.y + val.r * Math.sin(val.a0))} arc[start angle=${n4((val.a0 * 180) / Math.PI)},end angle=${n4((a1 * 180) / Math.PI)},radius=${n4(val.r)}];`);
        }
        break;
      case 'conic':
        for (const l of implicitSegments((x, y) => conicAt(val.k, x, y), v, 120, 90)) L.push(`  \\draw[thick${c}] plot coordinates {${thin(l).map((p) => xy(p[0], p[1])).join(' ')}};`);
        break;
      case 'polygon': L.push(`  \\draw[thick${c}] ${val.pts.map((p) => xy(p.x, p.y)).join(' -- ')} -- cycle;`); break;
      case 'locus': for (const l of val.lines) if (l.length > 1) L.push(`  \\draw[thick,dashed${c || ',red!70!black'}] plot coordinates {${thin(l).map((p) => xy(p.x, p.y)).join(' ')}};`); break;
      default:
    }
  }
  L.push(...later, '\\end{tikzpicture}');
  const defs = [...colors].map(([hex, name]) => `\\definecolor{${name}}{HTML}{${hex}}`);
  return ['% Madalean figure — TikZ (\\usepackage{tikz})', ...defs, ...L].join('\n') + '\n';
}
function niceStepT(raw: number) { const p = Math.pow(10, Math.floor(Math.log10(raw))); const m = raw / p; return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p; }

// ------------------------------------------------------------------ Sage (exact)
const SAGE_HELPERS = `var('x y')
def line_eq(P, Q):
    return (Q[1] - P[1])*(x - P[0]) - (Q[0] - P[0])*(y - P[1])
def circle_eq(C, r2):
    return (x - C[0])^2 + (y - C[1])^2 - r2
def meet(e1, e2, near):
    """Exact common points of two curves, the one closest to the figure's point first."""
    sols = solve([e1 == 0, e2 == 0], x, y, solution_dict=True)
    pts = [vector([s[x], s[y]]) for s in sols if s[x] in RR and s[y] in RR]
    return sorted(pts, key=lambda P: (n(P[0]) - near[0])^2 + (n(P[1]) - near[1])^2)
def circumcenter(A, B, C):
    d = 2*(A[0]*(B[1] - C[1]) + B[0]*(C[1] - A[1]) + C[0]*(A[1] - B[1]))
    a2, b2, c2 = A.dot_product(A), B.dot_product(B), C.dot_product(C)
    return vector([(a2*(B[1] - C[1]) + b2*(C[1] - A[1]) + c2*(A[1] - B[1]))/d,
                   (a2*(C[0] - B[0]) + b2*(A[0] - C[0]) + c2*(B[0] - A[0]))/d])
def polygon_centroid(P):
    a = sum(P[i][0]*P[(i+1) % len(P)][1] - P[(i+1) % len(P)][0]*P[i][1] for i in range(len(P)))/2
    return vector([sum((P[i][k] + P[(i+1) % len(P)][k])*(P[i][0]*P[(i+1) % len(P)][1] - P[(i+1) % len(P)][0]*P[i][1]) for i in range(len(P)))/(6*a) for k in (0, 1)])
def polygon_area(P):
    return abs(sum(P[i][0]*P[(i+1) % len(P)][1] - P[(i+1) % len(P)][0]*P[i][1] for i in range(len(P))))/2
`;

/** Sage code rebuilding the figure exactly: free points as rationals, constructions as exact formulas. Objects the
 *  bridge cannot express exactly are given by a rational approximation, marked « approx ». */
export function toSage(fig: Figure): string {
  const L: string[] = ['# Figure Madalean → Sage : calcul exact', SAGE_HELPERS];
  const id = (o: Obj | undefined) => (o ? safe(o.name) : '_');
  const pt = new Set<string>(), line = new Map<string, [string, string]>(), circ = new Map<string, [string, string]>();
  const shown: string[] = [];
  const vec = (a: number, b: number) => `vector(QQ, [${toFraction(a)}, ${toFraction(b)}])`;
  for (const o of fig.objects) {
    const v = o.val;
    if (!v) continue;
    const name = safe(o.name);
    const par = o.parents.map((p) => fig.byId(p));
    const pn = par.map(id);
    const P = (i: number) => pt.has(pn[i] ?? '');
    const approxPoint = (why: string) => { if (v.t === 'point') { L.push(`${name} = ${vec(v.x, v.y)}   # approx (${why})`); pt.add(name); } else L.push(`# ${name}: ${o.kind} — not expressed exactly`); };
    switch (o.kind) {
      case 'point': if (v.t === 'point') { L.push(`${name} = ${vec(v.x, v.y)}`); pt.add(name); } break;
      case 'midpoint':
        if (P(0) && P(1)) { L.push(`${name} = (${pn[0]} + ${pn[1]})/2`); pt.add(name); }
        else if (line.has(pn[0]!) && par[0]?.kind === 'segment') { const [b, d] = line.get(pn[0]!)!; L.push(`${name} = ${b} + (${d})/2`); pt.add(name); }
        else approxPoint(o.kind);
        break;
      case 'centroid': if (par[0]?.kind === 'polygon' && par[0].parents.every((q) => pt.has(id(fig.byId(q))))) { L.push(`${name} = polygon_centroid([${par[0].parents.map((q) => id(fig.byId(q))).join(', ')}])`); pt.add(name); }
        else if (o.parents.every((_, i) => P(i)) && pn.length >= 2) { L.push(`${name} = (${pn.join(' + ')})/${pn.length}`); pt.add(name); } else approxPoint(o.kind); break;
      case 'segment': case 'line': case 'ray': case 'vector':
        if (P(0) && P(1)) { line.set(name, [pn[0]!, `${pn[1]} - ${pn[0]}`]); L.push(`${name} = line_eq(${pn[0]}, ${pn[1]})   # ${o.kind} ${pn[0]}${pn[1]}`); }
        break;
      case 'parallel': case 'perpendicular': {
        const li = par.findIndex((p) => line.has(id(p))), pi = par.findIndex((p) => pt.has(id(p)));
        if (li < 0 || pi < 0) { L.push(`# ${name}: ${o.kind} — not expressed exactly`); break; }
        const d = line.get(pn[li]!)![1];
        const dir = o.kind === 'parallel' ? `(${d})` : `vector([-(${d})[1], (${d})[0]])`;
        line.set(name, [pn[pi]!, dir]);
        L.push(`${name} = line_eq(${pn[pi]}, ${pn[pi]} + ${dir})`);
        break;
      }
      case 'perp_bisector':
        if (P(0) && P(1)) { const b = `(${pn[0]} + ${pn[1]})/2`, d = `vector([-(${pn[1]} - ${pn[0]})[1], (${pn[1]} - ${pn[0]})[0]])`; line.set(name, [b, d]); L.push(`${name} = line_eq(${b}, ${b} + ${d})`); }
        break;
      case 'circle_center_point':
        if (P(0) && P(1)) { circ.set(name, [pn[0]!, `(${pn[1]} - ${pn[0]}).dot_product(${pn[1]} - ${pn[0]})`]); L.push(`${name} = circle_eq(${pn[0]}, ${circ.get(name)![1]})`); }
        break;
      case 'circle_center_radius':
        if (P(0) && v.t === 'circle') { const r = par[1]?.kind === 'slider' ? pn[1]! : toFraction(v.r); circ.set(name, [pn[0]!, `(${r})^2`]); L.push(`${name} = circle_eq(${pn[0]}, (${r})^2)`); }
        break;
      case 'circle_3_points':
        if (P(0) && P(1) && P(2)) { const c = `${name}_O`; L.push(`${c} = circumcenter(${pn[0]}, ${pn[1]}, ${pn[2]})`); circ.set(name, [c, `(${pn[0]} - ${c}).dot_product(${pn[0]} - ${c})`]); L.push(`${name} = circle_eq(${c}, ${circ.get(name)![1]})`); }
        break;
      case 'intersection': {
        const eq = (i: number) => (line.has(pn[i]!) || circ.has(pn[i]!) ? pn[i] : null);
        if (eq(0) && eq(1) && v.t === 'point') { L.push(`${name} = meet(${eq(0)}, ${eq(1)}, (${n4(v.x)}, ${n4(v.y)}))[0]`); pt.add(name); shown.push(name); }
        else approxPoint(o.kind);
        break;
      }
      case 'center': if (circ.has(pn[0]!)) { L.push(`${name} = ${circ.get(pn[0]!)![0]}`); pt.add(name); } else approxPoint(o.kind); break;
      case 'point_reflection': if (P(0) && P(1)) { L.push(`${name} = 2*${pn[1]} - ${pn[0]}`); pt.add(name); } else approxPoint(o.kind); break;
      case 'translation': if (P(0) && line.has(pn[1]!)) { L.push(`${name} = ${pn[0]} + (${line.get(pn[1]!)![1]})`); pt.add(name); } else approxPoint(o.kind); break;
      case 'homothety': if (P(0) && P(1)) { const k = par[2]?.kind === 'slider' ? pn[2]! : toFraction(o.params?.[0] ?? 2); L.push(`${name} = ${pn[1]} + (${k})*(${pn[0]} - ${pn[1]})`); pt.add(name); } else approxPoint(o.kind); break;
      case 'rotation':
        if (P(0) && P(1) && !par[2]) { const th = `pi*${toFraction(o.params?.[0] ?? 90)}/180`; L.push(`${name} = ${pn[1]} + matrix([[cos(${th}), -sin(${th})], [sin(${th}), cos(${th})]])*(${pn[0]} - ${pn[1]})`); pt.add(name); }
        else approxPoint(o.kind);
        break;
      case 'conic_5_points':
        if (o.parents.every((_, i) => P(i))) { L.push(`${name} = matrix([[x^2, x*y, y^2, x, y, 1]] + [[Q[0]^2, Q[0]*Q[1], Q[1]^2, Q[0], Q[1], 1] for Q in [${pn.join(', ')}]]).det()`); shown.push(`${name} == 0`); }
        break;
      case 'distance':
        if (P(0) && P(1)) L.push(`${name} = (${pn[0]} - ${pn[1]}).norm()`);
        else if (line.has(pn[0]!) && par[0]?.kind === 'segment') L.push(`${name} = (${line.get(pn[0]!)![1]}).norm()`);
        else { L.push(`${name} = ${toFraction(v.t === 'number' ? v.v : 0)}   # approx`); }
        shown.push(name);
        break;
      case 'angle':
        if (P(0) && P(1) && P(2)) { L.push(`${name} = arccos((${pn[0]} - ${pn[1]}).dot_product(${pn[2]} - ${pn[1]})/((${pn[0]} - ${pn[1]}).norm()*(${pn[2]} - ${pn[1]}).norm()))`); shown.push(name); }
        break;
      case 'area': {
        const poly = par[0];
        if (poly?.kind === 'polygon' && poly.parents.every((p) => pt.has(id(fig.byId(p))))) { L.push(`${name} = polygon_area([${poly.parents.map((p) => id(fig.byId(p))).join(', ')}])`); shown.push(name); }
        else if (circ.has(pn[0]!)) { L.push(`${name} = pi*${circ.get(pn[0]!)![1]}`); shown.push(name); }
        break;
      }
      case 'slope': if (line.has(pn[0]!)) { const d = line.get(pn[0]!)![1]; L.push(`${name} = (${d})[1]/(${d})[0]`); shown.push(name); } break;
      case 'slider': if (v.t === 'number') L.push(`${name} = ${toFraction(v.v)}   # slider`); break;
      case 'polygon': if (o.parents.every((_, i) => P(i))) L.push(`${name} = [${pn.join(', ')}]   # polygon`); break;
      default: approxPoint(o.kind);
    }
  }
  for (const s of shown) L.push(s.includes('==') ? `show(${s})` : `print(${JSON.stringify(s + ' =')}, ${s}, '≈', N(${s}))`);
  return L.join('\n') + '\n';
}
const safe = (s: string) => { const t = s.replace(/'/g, 'p').replace(/[^A-Za-z0-9_]/g, '_'); return /^[A-Za-z_]/.test(t) ? t : `o_${t}`; };
