import { describe, it, expect } from 'vitest';
import { treeOf, type Graph, type GraphNode } from '../../src/lib/api/graph';

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
