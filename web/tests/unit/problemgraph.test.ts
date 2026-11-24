import { describe, it, expect } from 'vitest';
import { treeOf, type Graph, type GraphNode } from '../../src/lib/api/graph';
import { dagLayout, zoomAt, BOX_W } from '../../src/lib/graph/dag';

const n = (id: string, title = id): GraphNode => ({ id, title } as unknown as GraphNode);

function graph(edges: [string, string, string][], ids: string[]): Graph {
  return { root: 'g', nodes: Object.fromEntries(ids.map((i) => [i, n(i)])), edges } as unknown as Graph;
}

describe('problem graph as a list (S-AY)', () => {
  it('lists a shared lemma once, under its first user, and says who else uses it', () => {
    const g = graph([['g', 'uses', 'a'], ['g', 'uses', 'b'], ['a', 'uses', 's'], ['b', 'uses', 's']], ['g', 'a', 'b', 's']);
    const { order, alsoUsedBy } = treeOf(g);
    expect(order.map((x) => x.id)).toEqual(['g', 'a', 's', 'b']);
    expect(order.find((x) => x.id === 's')!.depth).toBe(2);
    expect(alsoUsedBy['s']).toEqual(['b']);
  });
  it('lists known results not used yet after the tree, and survives cycles', () => {
    const g = graph([['g', 'uses', 'a'], ['a', 'uses', 'g'], ['x', 'refutes', 'a']], ['g', 'a', 'k', 'x']);
    const ids = treeOf(g).order.map((x) => x.id);
    expect(ids.slice(0, 2)).toEqual(['g', 'a']);
    expect(new Set(ids)).toEqual(new Set(['g', 'a', 'k', 'x']));
    expect(ids.length).toBe(4);
  });
});

describe('problem graph drawn (S-BA, D59)', () => {
  it('layers the DAG: a lemma below every user, a shared lemma drawn once, no overlap', () => {
    const g = graph([['g', 'uses', 'a'], ['g', 'uses', 'b'], ['a', 'uses', 's'], ['b', 'uses', 's'], ['g', 'uses', 's'],
      ['x', 'refutes', 'a']], ['g', 'a', 'b', 's', 'k', 'x']);
    const L = dagLayout(g);
    const by = Object.fromEntries(L.boxes.map((b) => [b.id, b]));
    expect(L.boxes.length).toBe(6);
    expect(by['g']!.layer).toBe(0);
    expect(by['a']!.layer).toBe(1);
    expect(by['s']!.layer).toBe(2);                    // longest path: below a and b, not beside them
    expect(by['k']!.layer).toBe(3);                    // not used by the goal: last row
    for (const p of L.boxes) for (const q of L.boxes)
      if (p !== q && p.layer === q.layer) expect(Math.abs(p.x - q.x)).toBeGreaterThanOrEqual(BOX_W);
    expect(L.edges.filter((e) => e.to === 's').length).toBe(3);
  });
  it('survives a cycle and keeps zoom bounded around a point', () => {
    const L = dagLayout(graph([['g', 'uses', 'a'], ['a', 'uses', 'g']], ['g', 'a']));
    expect(L.boxes.length).toBe(2);
    let v = { x: 0, y: 0, k: 1 };
    for (let i = 0; i < 40; i++) v = zoomAt(v, 1.5, 100, 100);
    expect(v.k).toBe(3);
    const w = zoomAt({ x: 0, y: 0, k: 1 }, 2, 100, 50);
    expect([w.x, w.y, w.k]).toEqual([-100, -50, 2]);   // the point under the cursor stays put
  });
});
