import { describe, it, expect } from 'vitest';
import { abbreviationAt, insideDollarMath, ABBREVIATIONS } from '../../src/lib/lean/abbrev';
import { lookupGloss, tokenAt } from '../../src/lib/lean/glossary';
import { fadeProof, splitProof, hintPrompt } from '../../src/lib/learn/tutor';
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
  it('fades a proof from the end backwards', () => {
    const code = 'import Mathlib\n\ntheorem t (a b : ℕ) : a + b = b + a := by\n  rw [Nat.add_comm]\n  rfl\n  done\n';
    expect(splitProof(code)?.tactics.length).toBe(3);
    const f1 = fadeProof(code, 1)!;
    expect(f1.hidden).toEqual(['  done']);
    expect(f1.exercise).toContain('rw [Nat.add_comm]');
    expect(f1.exercise).toContain('sorry');
    const all = fadeProof(code, 99)!;
    expect(all.hidden.length).toBe(3);
    expect(all.exercise).not.toContain('rw [');
  });
  it('hint prompts never contain the proof', () => {
    const d = { understood_display: 'P', problem: 'P', current: { statement: 'theorem t : True := by sorry', proof: 'theorem t : True := by trivial' } } as never;
    const p = hintPrompt(d, 'nudge', { tried: 'x', helpType: '', reflections: [], lang: 'fr' });
    expect(p).not.toContain('trivial');
    expect(p).toContain('JAMAIS');
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
