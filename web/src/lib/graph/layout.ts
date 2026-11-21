// Graph layouts without dependencies.
// - forceLayout: force-directed (spring edges, repulsion bucketed in a grid → ~O(n) per iteration), deterministic.
// - layeredLayout: DAG in layers (longest path), barycentre ordering, for blueprints (dependencies below/right).

export interface LNode { id: string }
export interface LEdge { source: string; target: string }
export type Pos = Record<string, { x: number; y: number }>;

export function forceLayout(nodes: LNode[], edges: LEdge[], opts: { iterations?: number; width?: number; height?: number } = {}): Pos {
  const n = nodes.length;
  const W = opts.width ?? Math.max(420, Math.sqrt(n) * 110);
  const H = opts.height ?? W * 0.7;
  const idx = new Map(nodes.map((v, i) => [v.id, i]));
  const xs = new Float64Array(n), ys = new Float64Array(n), dx = new Float64Array(n), dy = new Float64Array(n);
  // Golden-angle spiral start: deterministic and well spread.
  for (let i = 0; i < n; i++) {
    const r = Math.sqrt(i + 0.5) / Math.sqrt(n) * Math.min(W, H) * 0.45;
    const a = i * 2.399963;
    xs[i] = W / 2 + r * Math.cos(a); ys[i] = H / 2 + r * Math.sin(a);
  }
  const E = edges.map((e) => [idx.get(e.source), idx.get(e.target)]).filter(([a, b]) => a !== undefined && b !== undefined && a !== b) as [number, number][];
  const k = Math.sqrt((W * H) / Math.max(1, n)) * 0.8;
  const iters = opts.iterations ?? (n > 600 ? 120 : 220);
  let temp = W / 8;
  const cell = k * 2;
  for (let it = 0; it < iters; it++) {
    dx.fill(0); dy.fill(0);
    // repulsion through a grid of cells (only neighbouring cells interact)
    const grid = new Map<string, number[]>();
    for (let i = 0; i < n; i++) {
      const key = `${Math.floor(xs[i]! / cell)},${Math.floor(ys[i]! / cell)}`;
      (grid.get(key) ?? grid.set(key, []).get(key)!).push(i);
    }
    for (const [key, list] of grid) {
      const [cx, cy] = key.split(',').map(Number) as [number, number];
      for (let gx = cx - 1; gx <= cx + 1; gx++) for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const other = grid.get(`${gx},${gy}`);
        if (!other) continue;
        for (const i of list) for (const j of other) {
          if (j <= i && other === list) continue;
          if (other !== list && j < i) continue;
          let ddx = xs[i]! - xs[j]!, ddy = ys[i]! - ys[j]!;
          let d2 = ddx * ddx + ddy * ddy;
          if (d2 < 0.01) { ddx = (i - j) * 0.1; ddy = 0.1; d2 = ddx * ddx + ddy * ddy; }
          const f = (k * k) / d2;
          dx[i]! += ddx * f; dy[i]! += ddy * f; dx[j]! -= ddx * f; dy[j]! -= ddy * f;
        }
      }
    }
    for (const [a, b] of E) {
      const ddx = xs[a]! - xs[b]!, ddy = ys[a]! - ys[b]!;
      const d = Math.sqrt(ddx * ddx + ddy * ddy) || 0.01;
      const f = d / k;
      dx[a]! -= ddx * f; dy[a]! -= ddy * f; dx[b]! += ddx * f; dy[b]! += ddy * f;
    }
    for (let i = 0; i < n; i++) {
      // gentle gravity keeps disconnected parts on screen
      dx[i]! += (W / 2 - xs[i]!) * 0.02; dy[i]! += (H / 2 - ys[i]!) * 0.02;
      const d = Math.sqrt(dx[i]! * dx[i]! + dy[i]! * dy[i]!) || 1;
      const m = Math.min(d, temp);
      xs[i]! += (dx[i]! / d) * m; ys[i]! += (dy[i]! / d) * m;
    }
    temp *= 0.975;
  }
  const out: Pos = {};
  nodes.forEach((v, i) => (out[v.id] = { x: xs[i]!, y: ys[i]! }));
  return out;
}

/** Layers: a node is placed one layer after everything it depends on (`source` uses `target` → target first). */
export function layeredLayout(nodes: LNode[], edges: LEdge[], opts: { dx?: number; dy?: number } = {}): { pos: Pos; layers: string[][] } {
  const DX = opts.dx ?? 230, DY = opts.dy ?? 90;
  const deps = new Map<string, string[]>(nodes.map((v) => [v.id, []]));
  for (const e of edges) if (deps.has(e.source) && deps.has(e.target) && e.source !== e.target) deps.get(e.source)!.push(e.target);
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  const depth = (id: string): number => {
    if (layer.has(id)) return layer.get(id)!;
    if (visiting.has(id)) return 0;                 // cycle: break it
    visiting.add(id);
    const d = Math.max(-1, ...deps.get(id)!.map(depth)) + 1;
    visiting.delete(id);
    layer.set(id, d);
    return d;
  };
  nodes.forEach((v) => depth(v.id));
  const layers: string[][] = [];
  for (const v of nodes) (layers[layer.get(v.id)!] ??= []).push(v.id);
  // barycentre ordering, a few sweeps
  const order = new Map<string, number>();
  layers.forEach((l) => l.forEach((id, i) => order.set(id, i)));
  for (let s = 0; s < 4; s++) {
    for (let li = 1; li < layers.length; li++) {
      const l = layers[li]!;
      const bc = (id: string) => { const ds = deps.get(id)!.filter((x) => order.has(x)); return ds.length ? ds.reduce((a, x) => a + order.get(x)!, 0) / ds.length : order.get(id)!; };
      l.sort((a, b) => bc(a) - bc(b));
      l.forEach((id, i) => order.set(id, i));
    }
  }
  const pos: Pos = {};
  const maxW = Math.max(...layers.map((l) => l.length), 1);
  layers.forEach((l, li) => l.forEach((id, i) => { pos[id] = { x: 40 + li * DX, y: 40 + (i + (maxW - l.length) / 2) * DY }; }));
  return { pos, layers };
}
