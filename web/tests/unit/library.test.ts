import { describe, it, expect } from 'vitest';
import { facets, filterResults, groupResults } from '../../src/lib/library';
import { GLOSSARY, GLOSS_CATS, groupByCategory, glossSortKey, type GlossEntry } from '../../src/lib/lean/glossary';
import type { CatalogEntry } from '../../src/lib/api/workbench';

const base: CatalogEntry = { name: '', title: '', statement: '', nl: '', code: '', workspace: 'w', dossier: '', t: 0, project_id: '',
  project: '', domain: 'other', domain_auto: 'other', domain_manual: false, tags: [], status: 'verified', admitted: [], model: '',
  by_user: false, axioms: null, uses: [], used_by: [] };
const e = (x: Partial<CatalogEntry>): CatalogEntry => ({ ...base, ...x });
const list = [
  e({ name: 'riesz', domain: 'analysis', project_id: 'p1', project: 'Thèse', tags: ['banach', 'compacité'], t: 3 }),
  e({ name: 'cayley', domain: 'linear_algebra', project_id: 'p1', project: 'Thèse', tags: ['matrices'], t: 2 }),
  e({ name: 'compact', domain: 'analysis', tags: [], t: 1, status: 'conditional' }),
];

describe('library of results', () => {
  it('filters by domain, project, tag and status, combined', () => {
    expect(filterResults(list, { domain: 'analysis' }).map((x) => x.name)).toEqual(['riesz', 'compact']);
    expect(filterResults(list, { project: 'p1' }).map((x) => x.name)).toEqual(['riesz', 'cayley']);
    expect(filterResults(list, { project: '' }).map((x) => x.name)).toEqual(['compact']);
    expect(filterResults(list, { tag: 'banach' }).map((x) => x.name)).toEqual(['riesz']);
    expect(filterResults(list, { tag: '' }).map((x) => x.name)).toEqual(['compact']);
    expect(filterResults(list, { domain: 'analysis', status: 'verified' }).map((x) => x.name)).toEqual(['riesz']);
    expect(filterResults(list, { q: 'COMPACITE' }).map((x) => x.name)).toEqual(['riesz']); // accents and case ignored
    expect(filterResults(list, { q: 'analyse', label: (x) => (x.domain === 'analysis' ? 'Analyse' : '') }).length).toBe(2);
  });
  it('groups without losing or duplicating results', () => {
    const byDomain = groupResults(list, 'domain');
    expect(byDomain.map(([k, l]) => [k, l.length])).toEqual([['analysis', 2], ['linear_algebra', 1]]);
    const byProject = groupResults(list, 'project');
    expect(byProject.at(-1)![0]).toBe(''); // « without project » last
    const byTag = groupResults(list, 'tag');
    expect(byTag.flatMap(([, l]) => l).filter((x) => x.name === 'riesz').length).toBe(2); // one per tag
    const oneTag = groupResults(filterResults(list, { tag: 'banach' }), 'tag', 'banach');
    expect(oneTag).toEqual([['banach', [list[0]]]]); // a chosen tag: listed once
  });
  it('offers only the values that exist, with counts', () => {
    const f = facets([...list, e({ name: 'dup', tags: ['banach', 'banach'] })]);
    expect(f.domains[0]).toEqual(['analysis', 2]);
    expect(f.tags.find(([k]) => k === 'banach')).toEqual(['banach', 2]);
    expect(f.untagged).toBe(1);
    expect(f.projects.map(([k]) => k).sort()).toEqual(['', 'p1']);
  });
});

describe('glossary by category and level', () => {
  const all = Object.entries(GLOSSARY) as [string, GlossEntry][];
  it('lists every entry once, in category order, easiest first', () => {
    const g = groupByCategory(all);
    expect(g.map(([c]) => c)).toEqual(GLOSS_CATS.filter((c) => all.some(([, x]) => x.cat === c)));
    expect(g.reduce((n, [, l]) => n + l.length, 0)).toBe(all.length);
    for (const [, l] of g) for (let i = 1; i < l.length; i++) expect(l[i]![1].level).toBeGreaterThanOrEqual(l[i - 1]![1].level);
  });
  it('every entry has a known category and level; related terms exist', () => {
    for (const [k, x] of all) {
      expect(GLOSS_CATS, k).toContain(x.cat);
      expect([1, 2, 3], k).toContain(x.level);
    }
    const missing = all.flatMap(([k, x]) => (x.related ?? []).filter((r) => !GLOSSARY[r]).map((r) => `${k} → ${r}`));
    expect(missing).toEqual([]);
  });
  it('sorts ignoring accents and leading symbols', () => {
    expect(glossSortKey('Équiv')).toBe('equiv');
    expect(glossSortKey('¬')).toBe('¬');
  });
});

import { kernelProblem } from '../../src/lib/calcul/kernel';
describe('Calcul: kernel problems are told in words', () => {
  it('recognises a kernel that cannot start, a missing Sage and a stopped kernel', () => {
    expect(kernelProblem({ type: 'error', ename: 'unavailable', evalue: 'kernel_died: [I 12:00 ServerApp] …\nTraceback…' })).toBe('nostart');
    expect(kernelProblem({ type: 'error', ename: 'unavailable', evalue: 'kernel_unavailable: no sage kernel installed' })).toBe('nosage');
    expect(kernelProblem({ type: 'error', ename: 'unavailable', evalue: 'kernel_unavailable: the session has no kernel' })).toBe('nostart');
    expect(kernelProblem({ type: 'error', ename: 'died', evalue: 'died' })).toBe('stopped');
    expect(kernelProblem({ type: 'error', ename: 'ZeroDivisionError', evalue: 'division by zero' })).toBeNull();
    expect(kernelProblem({ type: 'stream' })).toBeNull();
  });
});
