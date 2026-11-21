import { describe, it, expect } from 'vitest';
import { abbreviationAt, insideDollarMath, ABBREVIATIONS } from '../../src/lib/lean/abbrev';
import { lookupGloss, tokenAt } from '../../src/lib/lean/glossary';
import { refusalOf, isRefusal } from '../../src/lib/lean/refusal';
import { linkify, leanBlocks, resolveConflicts } from '../../src/lib/notes';
import { forceLayout, layeredLayout } from '../../src/lib/graph/layout';
import { match, addRoute, routes } from '../../src/lib/router.svelte';
import { modelLabel, phaseOf } from '../../src/lib/status';

describe('Lean helpers', () => {
  it('expands the 1.x abbreviation table', () => {
    expect(abbreviationAt('theorem t (x : \\R')).toEqual([2, 'ℝ']);
    expect(abbreviationAt('a \\le')).toEqual([3, '≤']);
    expect(abbreviationAt('\\unknownthing')).toBeNull();
    expect(ABBREVIATIONS['forall']).toBe('∀');
    expect(insideDollarMath('Soit $x \\le')).toBe(true);
    expect(insideDollarMath('Soit $x$ et \\R')).toBe(false);
  });
  it('finds tokens and their gloss; prototype names are not glossary entries', () => {
    expect(tokenAt('  exact Even.add ha hb', 9)?.text).toBe('Even.add');
    expect(lookupGloss('Nat.Prime')?.token).toBe('Prime');
    expect(lookupGloss('toString')).toBeNull();
    expect(lookupGloss('constructor')?.entry.kind).toBe('tactic');
    expect(tokenAt('a := b', 2)?.text).toBe(':=');
  });
  it('recognises a D28 refusal (code that could run on the host is refused before compiling)', () => {
    const c = { summary: 'Refusé avant compilation : commande exécutée à la compilation (#eval…).', reasons: ['commande exécutée à la compilation (#eval…)'], errors: [] };
    expect(isRefusal(c)).toBe(true);
    expect(refusalOf(c)?.length).toBe(1);
    expect(isRefusal({ summary: 'Lean accepte le fichier', reasons: [] })).toBe(false);
    expect(refusalOf({ summary: 'Refused before compiling: IO', reasons: [] })?.length).toBe(1);
  });
});

describe('router and status', () => {
  it('matches patterns with optional params', () => {
    if (!routes.length) {
      addRoute({ name: 'home', pattern: '/', load: async () => ({ default: null as never }) });
      addRoute({ name: 'dossier', pattern: '/d/:id/:step?', load: async () => ({ default: null as never }) });
    }
    expect(match('/')?.def.name).toBe('home');
    expect(match('/d/abc')?.params).toEqual({ id: 'abc' });
    expect(match('/d/a%20b/lean')?.params).toEqual({ id: 'a b', step: 'lean' });
    expect(match('/d')).toBeNull();
  });
  it('labels models (incl. a Python repr) and phases', () => {
    expect(modelLabel('local:Goedel-Prover-V2-8B.Q4_K_M.gguf')).toEqual({ name: 'Goedel-Prover-V2-8B', provider: 'local', local: true });
    expect(modelLabel("ModelRef(provider='fake', model_id='fake-prove', name='x')").name).toBe('fake-prove');
    expect(modelLabel('openrouter:meta/llama:free').name).toBe('llama');
    expect(phaseOf('proved', null)).toBe('proved');
    expect(phaseOf('draft', { state: 'queued', waiting: 'gpu' } as never)).toBe('queued');
  });
});

describe('notes and graphs', () => {
  it('turns [[links]] into Markdown links, leaves code alone', () => {
    const ctx = { noteIdByTitle: new Map([['parité', 'n-1']]), dossierIdByTitle: new Map<string, string>() };
    const out = linkify('Voir [[Parité]] et [[dossier:d-9|ce théorème]], [[@hardy#p12]]; `[[pas un lien]]`', ctx);
    expect(out).toContain('[Parité](/notes/n-1)');
    expect(out).toContain('[ce théorème](/d/d-9)');
    expect(out).toContain('(/sources?tab=library&key=hardy)');
    expect(out).toContain('`[[pas un lien]]`');
    expect(linkify('[[Inconnue]]', ctx)).toBe('**Inconnue**');
  });
  it('finds fenced Lean blocks', () => {
    const b = leanBlocks('a\n```lean\ntheorem t : True := trivial\n```\nb\n```lean4\nexample : 1 = 1 := rfl\n```');
    expect(b.map((x) => x.index)).toEqual([0, 1]);
    expect(b[1]!.code).toBe('example : 1 = 1 := rfl');
  });
  it('rebuilds a body from conflict choices', () => {
    const theirs = 'a\nY\nc\n';
    expect(resolveConflicts(theirs, [{ mine: 'X\n', theirs: 'Y\n' }], ['mine'])).toBe('a\nX\nc\n');
    expect(resolveConflicts(theirs, [{ mine: 'X\n', theirs: 'Y\n' }], ['both'])).toBe('a\nY\nX\nc\n');
    expect(resolveConflicts(theirs, [{ mine: 'X\n', theirs: 'Y\n' }], ['theirs'])).toBe(theirs);
  });
  it('lays out 500 nodes quickly and deterministically; layers a DAG with dependencies first', () => {
    const nodes = Array.from({ length: 500 }, (_, i) => ({ id: `n${i}` }));
    const edges = nodes.slice(1).map((n, i) => ({ source: n.id, target: `n${Math.floor(i / 3)}` }));
    const t0 = performance.now();
    const p = forceLayout(nodes, edges);
    expect(performance.now() - t0).toBeLessThan(3000);
    expect(Object.keys(p).length).toBe(500);
    expect(forceLayout(nodes, edges)['n7']).toEqual(p['n7']);
    const l = layeredLayout([{ id: 'thm' }, { id: 'lem' }, { id: 'def' }], [{ source: 'thm', target: 'lem' }, { source: 'lem', target: 'def' }]);
    expect(l.layers.map((x) => x[0])).toEqual(['def', 'lem', 'thm']);
    const cyc = layeredLayout([{ id: 'a' }, { id: 'b' }], [{ source: 'a', target: 'b' }, { source: 'b', target: 'a' }]);
    expect(Object.keys(cyc.pos).length).toBe(2);
  });
});
