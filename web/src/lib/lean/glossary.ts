// Meaning of common Lean tokens, for « hover/tap any token » in Learn mode and the glossary screen.
// Bilingual content (fr, en). Declarations not listed here are looked up through the server when it offers a
// declaration endpoint (see docs/UI.md « Requests to the server »).
export type GlossKind = 'tactic' | 'keyword' | 'notation' | 'type' | 'predicate';
export interface GlossEntry { kind: GlossKind; fr: string; en: string; example?: string }

export const GLOSSARY: Record<string, GlossEntry> = Object.assign(Object.create(null) as Record<string, GlossEntry>, {
  // keywords
  theorem: { kind: 'keyword', fr: 'Déclare un théorème : un nom, des hypothèses, une conclusion, puis sa preuve après `:=`.', en: 'Declares a theorem: a name, hypotheses, a conclusion, then its proof after `:=`.' },
  lemma: { kind: 'keyword', fr: 'Comme `theorem` (Mathlib) : un résultat intermédiaire.', en: 'Same as `theorem` (Mathlib): an intermediate result.' },
  example: { kind: 'keyword', fr: 'Un énoncé sans nom, prouvé sur place.', en: 'An unnamed statement, proved on the spot.' },
  def: { kind: 'keyword', fr: 'Définit un objet (fonction, constante…).', en: 'Defines an object (function, constant…).' },
  by: { kind: 'keyword', fr: 'Commence une preuve en mode tactique : une suite d’instructions qui transforment le but.', en: 'Starts a proof in tactic mode: a sequence of steps that transform the goal.' },
  sorry: { kind: 'keyword', fr: 'Trou volontaire dans une preuve. Lean l’accepte provisoirement, mais rien n’est prouvé tant qu’il reste un `sorry`.', en: 'A deliberate hole in a proof. Lean accepts it for now, but nothing is proved while a `sorry` remains.' },
  fun: { kind: 'keyword', fr: 'Fonction anonyme : `fun x => x + 1` envoie x sur x + 1.', en: 'Anonymous function: `fun x => x + 1` maps x to x + 1.' },
  import: { kind: 'keyword', fr: 'Charge une bibliothèque (ici Mathlib, la bibliothèque mathématique de Lean).', en: 'Loads a library (here Mathlib, Lean’s mathematics library).' },
  open: { kind: 'keyword', fr: 'Permet d’écrire des noms courts (`sqrt` au lieu de `Real.sqrt`).', en: 'Lets you write short names (`sqrt` instead of `Real.sqrt`).' },
  set_option: { kind: 'keyword', fr: 'Règle Lean (ici : le temps de calcul autorisé).', en: 'A Lean setting (here: how much computation is allowed).' },
  at: { kind: 'keyword', fr: 'Applique la tactique à une hypothèse plutôt qu’au but : `simp at h`.', en: 'Applies the tactic to a hypothesis instead of the goal: `simp at h`.' },
  with: { kind: 'keyword', fr: 'Nomme les morceaux produits par une tactique (`cases h with …`).', en: 'Names the pieces produced by a tactic (`cases h with …`).' },
  // tactics
  intro: { kind: 'tactic', fr: 'Pour prouver « ∀ x, … » ou « A → B » : on se donne x (ou on suppose A).', en: 'To prove “∀ x, …” or “A → B”: take an arbitrary x (or assume A).' },
  intros: { kind: 'tactic', fr: 'Comme `intro`, pour plusieurs variables d’un coup.', en: 'Like `intro`, for several variables at once.' },
  exact: { kind: 'tactic', fr: 'Termine le but en donnant exactement un terme qui le prouve.', en: 'Closes the goal by giving exactly a term that proves it.' },
  apply: { kind: 'tactic', fr: 'Utilise un résultat dont la conclusion est le but ; il reste à prouver ses hypothèses.', en: 'Uses a result whose conclusion is the goal; its hypotheses remain to be proved.' },
  rw: { kind: 'tactic', fr: 'Réécrit avec une égalité (ou une équivalence) : remplace le membre de gauche par celui de droite.', en: 'Rewrites with an equality (or iff): replaces the left side by the right side.' },
  simp: { kind: 'tactic', fr: 'Simplifie avec une grande liste de règles connues.', en: 'Simplifies using a large set of known rules.' },
  norm_num: { kind: 'tactic', fr: 'Calcule et vérifie des égalités/inégalités numériques.', en: 'Computes and checks numerical equalities/inequalities.' },
  linarith: { kind: 'tactic', fr: 'Combine linéairement les hypothèses pour prouver une inégalité.', en: 'Combines hypotheses linearly to prove an inequality.' },
  nlinarith: { kind: 'tactic', fr: 'Comme `linarith`, en multipliant aussi des hypothèses entre elles (non linéaire).', en: 'Like `linarith`, also multiplying hypotheses together (non-linear).' },
  ring: { kind: 'tactic', fr: 'Prouve une égalité qui découle des règles de calcul (développer, factoriser).', en: 'Proves an equality that follows from algebra rules (expand, factor).' },
  ring_nf: { kind: 'tactic', fr: 'Met les expressions sous forme normale de `ring`.', en: 'Puts expressions in `ring` normal form.' },
  field_simp: { kind: 'tactic', fr: 'Chasse les dénominateurs (quand ils sont non nuls).', en: 'Clears denominators (when they are non-zero).' },
  omega: { kind: 'tactic', fr: 'Décide l’arithmétique linéaire sur les entiers.', en: 'Decides linear arithmetic over the integers.' },
  decide: { kind: 'tactic', fr: 'Fait vérifier une proposition décidable par calcul.', en: 'Checks a decidable proposition by computation.' },
  cases: { kind: 'tactic', fr: 'Raisonne par cas sur une hypothèse (ou, existe, entier nul/successeur…).', en: 'Case analysis on a hypothesis (or, exists, zero/successor…).' },
  rcases: { kind: 'tactic', fr: 'Découpe une hypothèse en ses morceaux selon un motif `⟨x, hx⟩`.', en: 'Splits a hypothesis into pieces with a pattern `⟨x, hx⟩`.' },
  obtain: { kind: 'tactic', fr: 'Extrait un témoin : `obtain ⟨k, hk⟩ := h` depuis « h : ∃ k, … ».', en: 'Extracts a witness: `obtain ⟨k, hk⟩ := h` from “h : ∃ k, …”.' },
  induction: { kind: 'tactic', fr: 'Raisonnement par récurrence.', en: 'Proof by induction.' },
  use: { kind: 'tactic', fr: 'Pour prouver « ∃ x, … » : propose la valeur de x.', en: 'To prove “∃ x, …”: provide the value of x.' },
  refine: { kind: 'tactic', fr: 'Comme `exact`, avec des trous `?_` qui deviennent de nouveaux buts.', en: 'Like `exact`, with holes `?_` that become new goals.' },
  positivity: { kind: 'tactic', fr: 'Prouve qu’une expression est positive ou nulle (ou non nulle).', en: 'Proves that an expression is non-negative (or positive, or non-zero).' },
  gcongr: { kind: 'tactic', fr: 'Compare deux expressions de même forme terme à terme.', en: 'Compares two expressions of the same shape term by term.' },
  aesop: { kind: 'tactic', fr: 'Recherche automatique de preuve (règles et cas).', en: 'Automatic proof search (rules and cases).' },
  tauto: { kind: 'tactic', fr: 'Prouve les tautologies de logique propositionnelle.', en: 'Proves propositional tautologies.' },
  exfalso: { kind: 'tactic', fr: 'Remplace le but par « faux » : on va trouver une contradiction.', en: 'Replaces the goal with “false”: we will find a contradiction.' },
  contradiction: { kind: 'tactic', fr: 'Conclut quand deux hypothèses se contredisent.', en: 'Closes the goal when two hypotheses contradict each other.' },
  unfold: { kind: 'tactic', fr: 'Remplace un nom défini par sa définition.', en: 'Replaces a defined name by its definition.' },
  specialize: { kind: 'tactic', fr: 'Applique une hypothèse générale à une valeur précise.', en: 'Applies a general hypothesis to a specific value.' },
  have: { kind: 'tactic', fr: 'Énonce et prouve un fait intermédiaire, puis le garde comme hypothèse.', en: 'States and proves an intermediate fact, then keeps it as a hypothesis.' },
  show: { kind: 'tactic', fr: 'Rappelle (ou reformule) le but en cours.', en: 'Restates (or reformulates) the current goal.' },
  calc: { kind: 'tactic', fr: 'Chaîne de calculs « a = b = c ≤ d », chaque étape justifiée.', en: 'A chain of calculations “a = b = c ≤ d”, each step justified.' },
  push_cast: { kind: 'tactic', fr: 'Fait descendre les conversions de type (ℕ → ℝ…) vers les feuilles.', en: 'Pushes type casts (ℕ → ℝ…) towards the leaves.' },
  norm_cast: { kind: 'tactic', fr: 'Simplifie les conversions de type entre nombres.', en: 'Simplifies casts between number types.' },
  exact_mod_cast: { kind: 'tactic', fr: '`exact` à des conversions de type près.', en: '`exact` up to casts.' },
  trivial: { kind: 'tactic', fr: 'Essaie des preuves évidentes.', en: 'Tries obvious proofs.' },
  rfl: { kind: 'tactic', fr: 'Prouve « a = a » (les deux côtés sont identiques par calcul).', en: 'Proves “a = a” (both sides are identical by computation).' },
  left: { kind: 'tactic', fr: 'Pour « A ∨ B » : on choisit de prouver A.', en: 'For “A ∨ B”: choose to prove A.' },
  right: { kind: 'tactic', fr: 'Pour « A ∨ B » : on choisit de prouver B.', en: 'For “A ∨ B”: choose to prove B.' },
  by_contra: { kind: 'tactic', fr: 'Raisonnement par l’absurde.', en: 'Proof by contradiction.' },
  // types and predicates
  'ℕ': { kind: 'type', fr: 'Les entiers naturels 0, 1, 2, … (en Lean, 0 est un entier naturel).', en: 'Natural numbers 0, 1, 2, … (in Lean, 0 is a natural number).' },
  'ℤ': { kind: 'type', fr: 'Les entiers relatifs.', en: 'The integers.' },
  'ℚ': { kind: 'type', fr: 'Les rationnels.', en: 'The rationals.' },
  'ℝ': { kind: 'type', fr: 'Les réels.', en: 'The real numbers.' },
  'ℂ': { kind: 'type', fr: 'Les complexes.', en: 'The complex numbers.' },
  Prop: { kind: 'type', fr: 'Le type des propositions (énoncés vrais ou faux).', en: 'The type of propositions (statements that are true or false).' },
  Even: { kind: 'predicate', fr: '`Even n` : n est pair, c’est-à-dire n = r + r pour un certain r.', en: '`Even n`: n is even, i.e. n = r + r for some r.' },
  Odd: { kind: 'predicate', fr: '`Odd n` : n est impair, n = 2k + 1.', en: '`Odd n`: n is odd, n = 2k + 1.' },
  Prime: { kind: 'predicate', fr: '`Nat.Prime p` : p est premier.', en: '`Nat.Prime p`: p is prime.' },
  Finset: { kind: 'type', fr: 'Ensemble fini (on peut y sommer avec ∑).', en: 'A finite set (you can sum over it with ∑).' },
  Set: { kind: 'type', fr: 'Ensemble (de nature quelconque).', en: 'A set (of any kind).' },
  // notation
  '∀': { kind: 'notation', fr: '« pour tout ».', en: '“for all”.' },
  '∃': { kind: 'notation', fr: '« il existe ».', en: '“there exists”.' },
  '→': { kind: 'notation', fr: '« implique » (ou : fonction de … vers …).', en: '“implies” (or: function from … to …).' },
  '↔': { kind: 'notation', fr: '« si et seulement si ».', en: '“if and only if”.' },
  '∧': { kind: 'notation', fr: '« et ».', en: '“and”.' },
  '∨': { kind: 'notation', fr: '« ou ».', en: '“or”.' },
  '¬': { kind: 'notation', fr: '« non ».', en: '“not”.' },
  '∣': { kind: 'notation', fr: '« divise » : `a ∣ b` signifie que a divise b (barre verticale spéciale, tapez \\dvd).', en: '“divides”: `a ∣ b` means a divides b (special bar, type \\dvd).' },
  '∈': { kind: 'notation', fr: '« appartient à ».', en: '“is an element of”.' },
  '⊆': { kind: 'notation', fr: '« est inclus dans ».', en: '“is a subset of”.' },
  '≤': { kind: 'notation', fr: '« inférieur ou égal ».', en: '“less than or equal”.' },
  '≥': { kind: 'notation', fr: '« supérieur ou égal ».', en: '“greater than or equal”.' },
  '≠': { kind: 'notation', fr: '« différent de ».', en: '“not equal”.' },
  '∑': { kind: 'notation', fr: 'Somme : `∑ i in Finset.range n, f i` = f 0 + … + f (n−1).', en: 'Sum: `∑ i in Finset.range n, f i` = f 0 + … + f (n−1).' },
  '∏': { kind: 'notation', fr: 'Produit.', en: 'Product.' },
  '⟨': { kind: 'notation', fr: 'Chevrons ⟨a, b⟩ : assemble une preuve faite de plusieurs morceaux (témoin et propriété…).', en: 'Angle brackets ⟨a, b⟩: build a proof out of pieces (witness and property…).' },
  ':=': { kind: 'notation', fr: '« est défini par / est prouvé par ».', en: '“is defined as / is proved by”.' },
  ':': { kind: 'notation', fr: '« de type » : `(a : ℕ)` = a est un entier naturel ; `(h : a ≤ b)` = h est une preuve que a ≤ b.', en: '“of type”: `(a : ℕ)` = a is a natural number; `(h : a ≤ b)` = h is a proof that a ≤ b.' },
  '^': { kind: 'notation', fr: 'Puissance.', en: 'Power.' },
  '·': { kind: 'notation', fr: 'En début de ligne : traite un des buts ouverts.', en: 'At the start of a line: focuses on one of the open goals.' },
  '←': { kind: 'notation', fr: 'Dans `rw [← h]` : réécrit de droite à gauche.', en: 'In `rw [← h]`: rewrites right to left.' },
  '|': { kind: 'notation', fr: '`|x|` : valeur absolue.', en: '`|x|`: absolute value.' },
} satisfies Record<string, GlossEntry>);
// `constructor` is set apart: as an object-literal key TypeScript confuses it with Object.prototype.constructor.
GLOSSARY['constructor'] = { kind: 'tactic', fr: 'Découpe le but « A ∧ B » (ou « A ↔ B ») en deux buts.', en: 'Splits the goal “A ∧ B” (or “A ↔ B”) into two goals.' };

/** Normalises a token: `Nat.Prime` → `Prime`, `rw [h]` → `rw`. */
export function lookupGloss(token: string): { token: string; entry: GlossEntry } | null {
  const t = token.trim();
  if (!t) return null;
  if (GLOSSARY[t]) return { token: t, entry: GLOSSARY[t]! };
  const last = t.split('.').pop() ?? t;
  if (GLOSSARY[last]) return { token: last, entry: GLOSSARY[last]! };
  return null;
}

/** Extracts the token at `pos` in `line` (identifiers with dots/primes/subscripts, or one symbol). */
export function tokenAt(line: string, pos: number): { from: number; to: number; text: string } | null {
  const isId = (c: string) => /[\p{L}\p{N}_.'!?₀-₉ᵢₙ]/u.test(c);
  if (pos > 0 && (pos >= line.length || !isId(line[pos]!)) && isId(line[pos - 1] ?? '')) pos--;
  const c = line[pos];
  if (c === undefined) return null;
  if (isId(c)) {
    let a = pos;
    let b = pos;
    while (a > 0 && isId(line[a - 1]!)) a--;
    while (b < line.length && isId(line[b]!)) b++;
    return { from: a, to: b, text: line.slice(a, b).replace(/^\.+|\.+$/g, '') };
  }
  if (line.startsWith(':=', pos)) return { from: pos, to: pos + 2, text: ':=' };
  if (pos > 0 && line.startsWith(':=', pos - 1)) return { from: pos - 1, to: pos + 1, text: ':=' };
  if (/\s/.test(c)) return null;
  return { from: pos, to: pos + 1, text: c };
}
