// Built-in exercises (same list as madalean/examples.py, school → olympiad). Bilingual content.
export interface Example { key: string; level: { fr: string; en: string }; title: { fr: string; en: string }; problem: { fr: string; en: string }; statement: string }

export const EXAMPLES: Example[] = [
  { key: 'logique', level: { fr: 'Initiation', en: 'Beginner' }, title: { fr: 'Et logique', en: 'Logical and' },
    problem: { fr: 'Si P et Q sont vraies, alors « P et Q » est vraie.', en: 'If P and Q are true, then “P and Q” is true.' },
    statement: 'theorem et_logique (P Q : Prop) (hp : P) (hq : Q) : P ∧ Q := by sorry' },
  { key: 'pairs', level: { fr: 'Collège', en: 'Middle school' }, title: { fr: 'Somme de deux nombres pairs', en: 'Sum of two even numbers' },
    problem: { fr: 'Montrer que la somme de deux entiers pairs est paire.', en: 'Show that the sum of two even integers is even.' },
    statement: 'theorem somme_pairs (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry' },
  { key: 'identite', level: { fr: 'Collège', en: 'Middle school' }, title: { fr: 'Identité remarquable', en: 'Square of a sum' },
    problem: { fr: 'Pour tous réels $a, b$ : $(a + b)^2 = a^2 + 2ab + b^2$.', en: 'For all reals $a, b$: $(a + b)^2 = a^2 + 2ab + b^2$.' },
    statement: 'theorem identite_remarquable (a b : ℝ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by sorry' },
  { key: 'amgm', level: { fr: 'Lycée', en: 'High school' }, title: { fr: 'Inégalité $2ab \\le a^2 + b^2$', en: 'Inequality $2ab \\le a^2 + b^2$' },
    problem: { fr: 'Pour tous réels $a, b$ : $2ab \\le a^2 + b^2$ (penser à $(a-b)^2 \\ge 0$).', en: 'For all reals $a, b$: $2ab \\le a^2 + b^2$ (think of $(a-b)^2 \\ge 0$).' },
    statement: 'theorem deux_ab_le (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by sorry' },
  { key: 'triangulaire', level: { fr: 'Licence', en: 'Undergraduate' }, title: { fr: 'Inégalité triangulaire', en: 'Triangle inequality' },
    problem: { fr: 'Pour tous réels $a, b$ : $|a + b| \\le |a| + |b|$.', en: 'For all reals $a, b$: $|a + b| \\le |a| + |b|$.' },
    statement: 'theorem triangulaire (a b : ℝ) : |a + b| ≤ |a| + |b| := by sorry' },
  { key: 'divisible', level: { fr: 'Licence', en: 'Undergraduate' }, title: { fr: 'Trois entiers consécutifs', en: 'Three consecutive integers' },
    problem: { fr: 'Pour tout entier naturel $n$, $6$ divise $n(n+1)(n+2)$.', en: 'For every natural number $n$, $6$ divides $n(n+1)(n+2)$.' },
    statement: 'theorem six_dvd (n : ℕ) : 6 ∣ n * (n + 1) * (n + 2) := by sorry' },
];
