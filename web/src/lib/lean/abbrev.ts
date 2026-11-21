// Unicode abbreviations, ported verbatim from the 1.x LeanEditor (app/lean_ai_station/ui/widgets.py ABBREVIATIONS,
// same as VS Code Lean), plus a few common additions marked "+".
export const ABBREVIATIONS: Record<string, string> = {
  R: 'ℝ', N: 'ℕ', Z: 'ℤ', Q: 'ℚ', C: 'ℂ', to: '→', r: '→', l: '←', iff: '↔', lr: '↔',
  le: '≤', ge: '≥', ne: '≠', neq: '≠', and: '∧', or: '∨', not: '¬', forall: '∀', all: '∀',
  exists: '∃', ex: '∃', in: '∈', notin: '∉', sub: '⊆', subset: '⊆', ssub: '⊂', cap: '∩',
  cup: '∪', inter: '∩', union: '∪', empty: '∅', lam: 'λ', fun: 'λ', x: '×', times: '×',
  cdot: '·', '.': '·', sqrt: '√', inf: '∞', infty: '∞', alpha: 'α', beta: 'β', gamma: 'γ',
  delta: 'δ', epsilon: 'ε', eps: 'ε', theta: 'θ', lambda: 'λ', mu: 'μ', pi: 'π', sigma: 'σ',
  phi: 'φ', psi: 'ψ', omega: 'ω', Sum: '∑', sum: '∑', Prod: '∏', prod: '∏', circ: '∘',
  comp: '∘', '|': '∣', dvd: '∣', langle: '⟨', rangle: '⟩', '<': '⟨', '>': '⟩', '^-1': '⁻¹', inv: '⁻¹',
  '1': '₁', '2': '₂', '3': '₃', '0': '₀', n: 'ₙ', abs: '|', norm: '‖', deg: '°', mid: '∣',
  // + additions
  mapsto: '↦', '|-': '⊢', vdash: '⊢', top: '⊤', bot: '⊥', equiv: '≃', iso: '≅', approx: '≈', '4': '₄',
  '5': '₅', i: 'ᵢ', '^2': '²', '^3': '³', '^n': 'ⁿ', ell: 'ℓ', nabla: '∇', partial: '∂',
};

/**
 * If `before` (text up to the cursor) ends with a backslash abbreviation, returns [length to replace, symbol].
 */
export function abbreviationAt(before: string): [number, string] | null {
  const m = /\\([^\s\\]+)$/.exec(before);
  if (!m) return null;
  const sym = ABBREVIATIONS[m[1]!];
  return sym ? [m[0].length, sym] : null;
}

/** True when the cursor (end of `before`) sits inside an unclosed $…$ (LaTeX maths: keep `\le` as LaTeX). */
export function insideDollarMath(before: string): boolean {
  let n = 0;
  for (let i = 0; i < before.length; i++) {
    if (before[i] === '\\') { i++; continue; }
    if (before[i] === '$') n++;
  }
  return n % 2 === 1;
}
