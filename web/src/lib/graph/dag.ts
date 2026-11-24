// Layered layout of the problem graph's DAG (S-BA, D59). Pure: unit-tested, no DOM, no dependency.
// Why not the plan's tidy-tree layout (lib/plan/layout.ts): the problem graph is a DAG (a shared sub-lemma has several
// users) and a tree layout would draw it twice. Here: layer = longest path from the goal along « uses » edges (a node
// sits below every node that uses it), then a few barycentre sweeps order each layer to shorten the edges. Nodes the
// goal does not reach (known results, proposals) go to a last row. Edges are cubic curves between box centres.
import type { Graph } from '../api/graph';

export const BOX_W = 196;
export const BOX_H = 64;
export const GAP_X = 28;
export const GAP_Y = 64;
export const PAD = 16;

export interface DagBox { id: string; layer: number; x: number; y: number; w: number; h: number }
export interface DagEdge { from: string; to: string; kind: string; d: string }
export interface DagLayout { boxes: DagBox[]; edges: DagEdge[]; width: number; height: number }

export function dagLayout(graph: Graph, maxLayers = 12): DagLayout {
  const ids = Object.keys(graph.nodes);
  const uses: Record<string, string[]> = {};
  for (const [s, k, d] of graph.edges) if (k === 'uses' && graph.nodes[s] && graph.nodes[d]) (uses[s] ??= []).push(d);
  // longest-path layering from the root (bounded relaxation: the graph is a DAG, cycles are refused server-side)
  const layer: Record<string, number> = {};
  if (graph.nodes[graph.root]) layer[graph.root] = 0;
  for (let pass = 0; pass < ids.length + 1; pass++) {
    let changed = false;
    for (const s of Object.keys(layer)) {
      for (const d of uses[s] ?? []) {
        const l = Math.min(maxLayers, layer[s]! + 1);
        if ((layer[d] ?? -1) < l) { layer[d] = l; changed = true; }
      }
    }
    if (!changed) break;
  }
  const reached = Math.max(0, ...Object.values(layer));
  for (const id of ids.sort()) if (!(id in layer)) layer[id] = reached + 1;    // not used by the goal (yet)
  const rows: string[][] = [];
  for (const id of ids) (rows[layer[id]!] ??= []).push(id);
  for (let i = 0; i < rows.length; i++) rows[i] ??= [];
  const pos: Record<string, number> = {};
  const index = () => rows.forEach((r) => r.forEach((id, i) => { pos[id] = i; }));
  rows.forEach((r) => r.sort((a, b) => (graph.nodes[a]!.title || '').localeCompare(graph.nodes[b]!.title || '')));
  index();
  const parents: Record<string, string[]> = {};
  for (const [s, ds] of Object.entries(uses)) for (const d of ds) (parents[d] ??= []).push(s);
  const bary = (id: string, nb: Record<string, string[]>) => {
    const xs = (nb[id] ?? []).map((x) => pos[x]).filter((v): v is number => v !== undefined);
    return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : pos[id]!;
  };
  for (let sweep = 0; sweep < 4; sweep++) {                                     // down then up, twice
    const order = sweep % 2 === 0 ? rows.map((_, i) => i).slice(1) : rows.map((_, i) => i).reverse().slice(1);
    for (const i of order) {
      const nb = sweep % 2 === 0 ? parents : uses;
      const b: Record<string, number> = {};
      for (const id of rows[i]!) b[id] = bary(id, nb);
      rows[i]!.sort((x, y) => b[x]! - b[y]! || x.localeCompare(y));
      rows[i]!.forEach((id, k) => { pos[id] = k; });
    }
  }
  const widest = Math.max(1, ...rows.map((r) => r.length));
  const width = PAD * 2 + widest * BOX_W + (widest - 1) * GAP_X;
  const boxes: DagBox[] = [];
  const by: Record<string, DagBox> = {};
  rows.forEach((r, li) => {
    const rowW = r.length * BOX_W + Math.max(0, r.length - 1) * GAP_X;
    const x0 = (width - rowW) / 2;
    r.forEach((id, k) => {
      const b = { id, layer: li, x: x0 + k * (BOX_W + GAP_X), y: PAD + li * (BOX_H + GAP_Y), w: BOX_W, h: BOX_H };
      boxes.push(b);
      by[id] = b;
    });
  });
  const edges: DagEdge[] = [];
  for (const [s, k, d] of graph.edges) {
    const a = by[s], b = by[d];
    if (!a || !b || s === d) continue;
    const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = b.x + b.w / 2, y2 = b.y;
    const my = (y1 + y2) / 2;
    edges.push({ from: s, to: d, kind: k, d: `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}` });
  }
  const height = PAD * 2 + rows.length * BOX_H + Math.max(0, rows.length - 1) * GAP_Y;
  return { boxes, edges, width, height };
}

/** Pan / zoom state of the drawing, clamped (pure, for the tests). */
export function zoomAt(view: { x: number; y: number; k: number }, factor: number, cx: number, cy: number) {
  const k = Math.max(0.3, Math.min(3, view.k * factor));
  const f = k / view.k;
  return { k, x: cx - (cx - view.x) * f, y: cy - (cy - view.y) * f };
}
