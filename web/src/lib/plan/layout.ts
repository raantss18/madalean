// Left-to-right tidy tree for the proof plan mind map (S-L). Pure: unit-tested, no DOM.
// Why left-to-right and not radial: lemma titles are sentences; columns keep every label horizontal and the reading
// order (theorem → lemmas → sub-lemmas) matches the proof's. Rows are assigned to leaves in depth-first order and a
// parent sits at the middle of its children, so boxes never overlap by construction.
// Alternative tracks are ONE dashed pill per track (not their lemmas): the map stays small; the pill opens the panel.
import type { Plan, PlanNode, PlanTrack } from '../api/research';

export const NODE_W = 216;
export const NODE_H = 76;
export const ROW = 92;          // NODE_H + vertical gap
export const COL = 268;         // NODE_W + horizontal gap for the curves
export const ROOT_H = 104;      // the theorem: a kind label + up to 3 lines of a serif title
export const PAD = 12;

export interface MapItem {
  key: string;                  // node id, or `${nodeId}#${trackId}` for a track pill
  kind: 'node' | 'track';
  node: string;                 // the plan node (the track's owner for a pill)
  track?: PlanTrack;
  depth: number;
  x: number; y: number; w: number; h: number;
}
export interface MapEdge { from: string; to: string; dashed: boolean; d: string }

export function layout(plan: Plan): { items: MapItem[]; edges: MapEdge[]; width: number; height: number } {
  const nodes = plan.nodes;
  const items: MapItem[] = [];
  const byKey = new Map<string, MapItem>();
  let row = 0;
  const seen = new Set<string>();

  function place(key: string, kind: 'node' | 'track', nid: string, depth: number, kids: () => MapItem[], track?: PlanTrack): MapItem {
    const it: MapItem = { key, kind, node: nid, depth, x: PAD + depth * COL, y: 0, w: NODE_W, h: kind === 'node' ? NODE_H : 56, ...(track ? { track } : {}) };
    items.push(it);
    byKey.set(key, it);
    const ch = kids();
    if (ch.length) {
      it.y = (ch[0]!.y + ch[ch.length - 1]!.y) / 2;
    } else {
      it.y = PAD + row * ROW;
      row += 1;
    }
    if (kind === 'track') it.y += (NODE_H - it.h) / 2;
    if (depth === 0) { it.h = ROOT_H; it.y = Math.max(PAD, it.y - (ROOT_H - NODE_H) / 2); }
    return it;
  }

  function walk(nid: string, depth: number): MapItem {
    seen.add(nid);
    const n: PlanNode = nodes[nid]!;
    return place(nid, 'node', nid, depth, () => {
      const out: MapItem[] = [];
      for (const c of n.children) if (nodes[c] && !seen.has(c)) out.push(walk(c, depth + 1));
      for (const tr of n.tracks ?? []) {
        if (tr.id === n.active_track || tr.refused || !tr.lemmas.length) continue;
        out.push(place(`${nid}#${tr.id}`, 'track', nid, depth + 1, () => [], tr));
      }
      return out;
    });
  }
  walk(plan.root, 0);

  const edges: MapEdge[] = [];
  for (const it of items) {
    if (it.key === plan.root) continue;
    const parentId = it.kind === 'track' ? it.node : nodes[it.node]?.parent;
    const p = parentId ? byKey.get(parentId) : undefined;
    if (!p) continue;
    const x1 = p.x + p.w, y1 = p.y + p.h / 2, x2 = it.x, y2 = it.y + it.h / 2, mx = (x1 + x2) / 2;
    edges.push({ from: p.key, to: it.key, dashed: it.kind === 'track', d: `M${x1} ${y1} C${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}` });
  }
  const width = Math.max(...items.map((i) => i.x + i.w)) + PAD;
  const height = Math.max(...items.map((i) => i.y + i.h)) + PAD;
  return { items, edges, width, height };
}

/** Root → … → node, for the breadcrumb. */
export function pathTo(plan: Plan, nid: string): PlanNode[] {
  const out: PlanNode[] = [];
  let x: string | null | undefined = nid;
  while (x && plan.nodes[x] && out.length < 20) {
    out.unshift(plan.nodes[x]!);
    x = plan.nodes[x]!.parent;
  }
  return out;
}

/** Tracks of `nid`'s parent (or of `nid` itself) the user may switch to: not active, not refused. */
export function otherTracks(plan: Plan, owner: string): PlanTrack[] {
  const n = plan.nodes[owner];
  if (!n) return [];
  return (n.tracks ?? []).filter((t) => t.id !== n.active_track && !t.refused && !t.abandoned && t.lemmas.length > 0);
}

export const UI_ICON: Record<string, string> = {
  to_validate: 'eye', validated: 'list', running: 'activity', proved: 'check', failed: 'x',
  abandoned: 'stop', alternative: 'split', hole: 'warn', conditional: 'warn',
};
