// FigureSpec: the JSON contract of a « Figure » cell (stored in the .ipynb cell metadata by the server, and emitted by
// Sage's helper fig(...) as the mime type application/vnd.madalean.figure+json). Versioned; loading is tolerant.
export interface ViewBox { xmin: number; xmax: number; ymin: number; ymax: number }
export interface CurveSpec { id: string; expr: string; color?: string; label?: string; hidden?: boolean }
export interface ObjectSpec {
  id: string; name: string; kind: string; parents: string[]; params?: number[];
  x?: number; y?: number; hidden?: boolean; color?: string;
}
export interface GraphSpec {
  vertices: string[]; edges: [string, string, (string | number)?][];
  pos?: Record<string, [number, number]>; directed?: boolean;
}
export interface FigureSpec {
  v: 1; title?: string; view: ViewBox; grid?: boolean; axes?: boolean; exact?: boolean;
  curves: CurveSpec[]; objects: ObjectSpec[]; graph?: GraphSpec; points?: { x: number; y: number; label?: string }[];
}
export const FIGURE_MIME = 'application/vnd.madalean.figure+json';

const num = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d);
const str = (v: unknown, max = 400) => (typeof v === 'string' ? v.slice(0, max) : '');

export function emptySpec(): FigureSpec {
  return { v: 1, view: { xmin: -8, xmax: 8, ymin: -5, ymax: 5 }, grid: true, axes: true, exact: false, curves: [], objects: [] };
}

/** Validate and normalise anything that claims to be a figure (untrusted: Sage output, files). */
export function normalizeSpec(raw: unknown, warnings: string[] = []): FigureSpec {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const out = emptySpec();
  if (r['v'] !== undefined && r['v'] !== 1) warnings.push(`version ${String(r['v'])}`);
  const vw = (r['view'] ?? {}) as Record<string, unknown>;
  const view = { xmin: num(vw['xmin'], -8), xmax: num(vw['xmax'], 8), ymin: num(vw['ymin'], -5), ymax: num(vw['ymax'], 5) };
  if (view.xmin < view.xmax && view.ymin < view.ymax) out.view = view; else warnings.push('view');
  if (typeof r['title'] === 'string') out.title = str(r['title'], 200);
  for (const k of ['grid', 'axes', 'exact'] as const) if (typeof r[k] === 'boolean') out[k] = r[k] as boolean;
  const curves = Array.isArray(r['curves']) ? r['curves'] : [];
  curves.slice(0, 50).forEach((c, i) => {
    const o = (c ?? {}) as Record<string, unknown>;
    const expr = str(o['expr'], 2000);
    if (!expr) { warnings.push(`curve ${i}`); return; }
    const cs: CurveSpec = { id: str(o['id'], 40) || `f${i + 1}`, expr };
    if (typeof o['color'] === 'string' && /^#[0-9a-f]{3,8}$/i.test(o['color'])) cs.color = o['color'];
    if (typeof o['label'] === 'string') cs.label = str(o['label'], 80);
    if (o['hidden'] === true) cs.hidden = true;
    out.curves.push(cs);
  });
  const objs = Array.isArray(r['objects']) ? r['objects'] : [];
  const ids = new Set<string>();
  objs.slice(0, 500).forEach((x, i) => {
    const o = (x ?? {}) as Record<string, unknown>;
    const id = str(o['id'], 40) || `o${i + 1}`;
    const kind = str(o['kind'], 40);
    if (!kind || ids.has(id)) { warnings.push(`object ${id}`); return; }
    const parents = Array.isArray(o['parents']) ? o['parents'].filter((p): p is string => typeof p === 'string' && ids.has(p)) : [];
    if (Array.isArray(o['parents']) && parents.length !== o['parents'].length) warnings.push(`object ${id}: parents`);
    const os: ObjectSpec = { id, name: str(o['name'], 40) || id, kind, parents };
    if (Array.isArray(o['params'])) os.params = o['params'].filter((p): p is number => typeof p === 'number' && Number.isFinite(p)).slice(0, 8);
    if (typeof o['x'] === 'number' && Number.isFinite(o['x'])) os.x = o['x'];
    if (typeof o['y'] === 'number' && Number.isFinite(o['y'])) os.y = o['y'];
    if (o['hidden'] === true) os.hidden = true;
    if (typeof o['color'] === 'string' && /^#[0-9a-f]{3,8}$/i.test(o['color'])) os.color = o['color'];
    ids.add(id);
    out.objects.push(os);
  });
  const g = r['graph'] as Record<string, unknown> | undefined;
  if (g && Array.isArray(g['vertices'])) {
    const vertices = g['vertices'].slice(0, 2000).map((v) => String(v).slice(0, 40));
    const vs = new Set(vertices);
    const edges = (Array.isArray(g['edges']) ? g['edges'] : []).slice(0, 20000)
      .filter((e): e is unknown[] => Array.isArray(e) && e.length >= 2)
      .map((e) => {
        const ed: [string, string, (string | number)?] = [String(e[0]).slice(0, 40), String(e[1]).slice(0, 40)];
        if (typeof e[2] === 'string' || typeof e[2] === 'number') ed.push(e[2]);
        return ed;
      })
      .filter((e) => vs.has(e[0]) && vs.has(e[1]));
    const gs: GraphSpec = { vertices, edges };
    const pos = g['pos'] as Record<string, unknown> | undefined;
    if (pos && typeof pos === 'object') {
      gs.pos = {};
      for (const v of vertices) {
        const p = pos[v];
        if (Array.isArray(p) && typeof p[0] === 'number' && typeof p[1] === 'number') gs.pos[v] = [p[0], p[1]];
      }
    }
    if (g['directed'] === true) gs.directed = true;
    out.graph = gs;
  }
  if (Array.isArray(r['points'])) {
    out.points = r['points'].slice(0, 5000).filter((p): p is Record<string, unknown> => !!p && typeof p === 'object'
      && typeof (p as Record<string, unknown>)['x'] === 'number' && typeof (p as Record<string, unknown>)['y'] === 'number')
      .map((p) => (typeof p['label'] === 'string' ? { x: p['x'] as number, y: p['y'] as number, label: str(p['label'], 40) } : { x: p['x'] as number, y: p['y'] as number }));
  }
  return out;
}
