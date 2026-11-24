import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import fr from '../../src/lib/i18n/fr';
import en from '../../src/lib/i18n/en';
import { GLOSSARY } from '../../src/lib/lean/glossary';
import { EXAMPLES } from '../../src/lib/examples';

const ph = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('i18n catalogues', () => {
  it('fr and en have exactly the same keys, none empty', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
    for (const [k, v] of Object.entries(fr)) expect(v.trim(), `fr ${k}`).not.toBe('');
    for (const [k, v] of Object.entries(en)) expect(v.trim(), `en ${k}`).not.toBe('');
  });
  it('placeholders match between languages', () => {
    for (const k of Object.keys(fr) as (keyof typeof fr)[]) expect(ph(en[k]), k).toEqual(ph(fr[k]));
  });
  it('every static key used in the sources exists', () => {
    const files: string[] = [];
    const walk = (d: string) => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) walk(p); else if (/\.(ts|svelte)$/.test(f)) files.push(p); } };
    walk(join(__dirname, '../../src'));
    const missing: string[] = [];
    for (const f of files) {
      const src = readFileSync(f, 'utf8');
      for (const m of src.matchAll(/\b(?:t|tn)\(\s*'([a-zA-Z0-9_.]+)'/g)) {
        const k = m[1]!;
        if (src.includes(`tn('${k}'`)) { if (!(`${k}.one` in fr) || !(`${k}.other` in fr)) missing.push(`${f}: ${k}.one/.other`); }
        else if (!(k in fr)) missing.push(`${f}: ${k}`);
      }
    }
    expect(missing).toEqual([]);
  });
  it('dynamic key families are complete', () => {
    const families: Record<string, string[]> = {
      phase: ['draft', 'queued', 'running', 'proved', 'failed', 'stopped'],
      stage: ['understand', 'route', 'statement', 'notes', 'proof', 'explanation', 'informal'],
      waiting: ['gpu', 'online', 'lean'], slot: ['gpu', 'online', 'lean'],
      jobstate: ['queued', 'running', 'done', 'failed', 'cancelled'],
      'hints.level': ['nudge', 'strategy', 'lemma', 'step', 'full'], follow: ['auto', 'statement', 'proof', 'explanation'],
      role: ['prove', 'formalize', 'understand', 'explain', 'route', 'assistant'],
      'attempt.status': ['generating', 'compiling', 'accepted', 'rejected', 'error', 'cancelled'],
      'gloss.kind': ['tactic', 'keyword', 'notation', 'type', 'predicate'], step: ['enonce', 'lean', 'preuve'],
      stepstate: ['todo', 'running', 'queued', 'done', 'failed'], 'versions.title': ['statement', 'proof', 'explanation'],
      'status.mode': ['local', 'auto', 'online'], enter: ['send', 'run', 'check'],
    };
    for (const [fam, ks] of Object.entries(families)) for (const k of ks) expect(`${fam}.${k}` in fr, `${fam}.${k}`).toBe(true);
  });
  it('bilingual content (glossary, examples) is complete', () => {
    for (const [k, g] of Object.entries(GLOSSARY)) { expect(g.fr, k).toBeTruthy(); expect(g.en, k).toBeTruthy(); }
    for (const ex of EXAMPLES) for (const f of ['title', 'problem', 'level'] as const) { expect(ex[f].fr).toBeTruthy(); expect(ex[f].en).toBeTruthy(); }
  });
});
