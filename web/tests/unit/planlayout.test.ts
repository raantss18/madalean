import { describe, it, expect } from 'vitest';
import { layout, pathTo, otherTracks } from '../../src/lib/plan/layout';
import type { Plan, PlanNode, PlanTrack } from '../../src/lib/api/research';

function mk(id: string, parent: string | null, children: string[] = [], tracks: PlanTrack[] = [], active = ''): PlanNode {
  return { id, parent, children, title: id, statement_nl: '', why: '', lean: '', status: 'draft', state: 'draft', dossier_id: '', admitted: false,
    edited: false, cancelled: false, proved: false, conditional: null, dossier_status: '', ui: 'to_validate', off: '', depth: 0, track: '',
    tracks, active_track: active, uses: [], lean_ok: null, lean_error: '', obvious: false, obvious_proof: '', combine: null } as PlanNode;
}
const tr = (id: string, lemmas: string[], extra: Partial<PlanTrack> = {}): PlanTrack =>
  ({ id, idea: id, lemmas, combination: '', check: { state: 'ok', why: '', t: 0 }, abandoned: false, refused: '', ...extra });

function bigPlan(): Plan {
  // 30 nodes: root → 6 lemmas (+2 alternative tracks), first three split into 4–5 lemmas each, one more level
  const nodes: Record<string, PlanNode> = {};
  const kids = ['a1', 'a2', 'a3', 'a4', 'a5', 'a6'];
  nodes['r'] = mk('r', null, kids, [tr('a', kids), tr('b', ['b1']), tr('c', ['c1']), tr('d', ['d1'], { refused: 'equivalent' })], 'a');
  nodes['b1'] = mk('b1', 'r'); nodes['c1'] = mk('c1', 'r'); nodes['d1'] = mk('d1', 'r');
  for (const k of kids) nodes[k] = mk(k, 'r');
  let n = 10;
  for (const k of ['a1', 'a2', 'a3']) {
    const sub = Array.from({ length: 5 }, () => `n${n++}`);
    nodes[k] = mk(k, 'r', sub, [tr('a', sub)], 'a');
    for (const s of sub) nodes[s] = mk(s, k);
  }
  const deep = ['z1', 'z2'];
  nodes['n10'] = mk('n10', 'a1', deep, [tr('a', deep)], 'a');
  for (const s of deep) nodes[s] = mk(s, 'n10');
  return { root: 'r', nodes } as unknown as Plan;
}

describe('plan mind map layout', () => {
  it('places every active node and alternative track without overlap', () => {
    const plan = bigPlan();
    const { items, edges, width, height } = layout(plan);
    const keys = items.map((i) => i.key);
    expect(keys).toContain('r#b');
    expect(keys).toContain('r#c');
    expect(keys).not.toContain('r#d');                 // refused tracks are not drawn
    expect(keys).not.toContain('b1');                  // a track's lemmas live in the panel, not on the map
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i]!, b = items[j]!;
        const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
        expect(overlap, `${a.key} / ${b.key}`).toBe(false);
      }
      expect(items[i]!.x + items[i]!.w).toBeLessThanOrEqual(width);
      expect(items[i]!.y + items[i]!.h).toBeLessThanOrEqual(height);
    }
    expect(edges.length).toBe(items.length - 1);
    expect(edges.filter((e) => e.dashed).map((e) => e.to).sort()).toEqual(['r#b', 'r#c']);
  });
  it('breadcrumb and switchable tracks', () => {
    const plan = bigPlan();
    expect(pathTo(plan, 'z2').map((n) => n.id)).toEqual(['r', 'a1', 'n10', 'z2']);
    expect(otherTracks(plan, 'r').map((t) => t.id)).toEqual(['b', 'c']);
  });
});
