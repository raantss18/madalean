"""Source of madalean/teaching/seed.json (run from the repository root; tests/test_exercises.py compiles it with Lean)."""
import json
from pathlib import Path

X: list[dict] = []
PUB = "Classique, énoncé rédigé pour Madalean"


def tr(t) -> dict:
    return dict(zip(("fr", "mg", "en"), (t, t, t) if isinstance(t, str) else t))


def ex(id, level, domain, title, statement, sig, solution, hints, source="Madalean"):
    X.append({"id": id, "level": level, "domain": domain, "title": tr(title), "statement": tr(statement),
              "lean": f"theorem {sig} := by sorry", "hints": [tr(h) for h in hints], "solution": solution,
              "source": source, "licence": "CC0-1.0"})


ex("pair-somme", "lycee", "arithmetique",
   ("Somme de deux nombres pairs", "Fitambaran'ny isa roa azo zaraina amin'ny 2", "Sum of two even numbers"),
   ("Soient $a$ et $b$ deux entiers naturels pairs. Montrer que $a+b$ est pair.",
    "Isa natoraly azo zaraina amin'ny 2 ny $a$ sy $b$. Porofoy fa azo zaraina amin'ny 2 koa ny $a+b$.",
    "Let $a$ and $b$ be even natural numbers. Show that $a+b$ is even."),
   "ex_pair_somme (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)",
   "obtain ⟨x, hx⟩ := ha\nobtain ⟨y, hy⟩ := hb\nexact ⟨x + y, by omega⟩",
   [("Que veut dire « pair » ?", "Inona no dikan'ny hoe azo zaraina amin'ny 2?", "What does “even” mean?"),
    ("Écrivez $a=x+x$ et $b=y+y$.", "Soraty hoe $a=x+x$ sy $b=y+y$.", "Write $a=x+x$ and $b=y+y$."),
    ("Le témoin pour $a+b$ est $x+y$.", "Raiso ny $x+y$ ho an'ny $a+b$.", "The witness for $a+b$ is $x+y$.")])
ex("carre-somme", "lycee", "algebre",
   ("Carré d'une somme", "Karen'ny fitambarana", "Square of a sum"),
   ("Montrer que $(a+b)^2=a^2+2ab+b^2$ pour tous réels $a,b$.",
    "Porofoy fa $(a+b)^2=a^2+2ab+b^2$ ho an'ny réel $a,b$ rehetra.",
    "Show that $(a+b)^2=a^2+2ab+b^2$ for all real $a,b$."),
   "ex_carre_somme (a b : ℝ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2", "ring",
   [("Développez le produit.", "Velaro ny fampitomboana.", "Expand the product."),
    "$(a+b)(a+b)=a^2+ab+ba+b^2$."])
ex("trinome-positif", "lycee", "inegalites",
   ("Un trinôme positif", "Trinôme tsy latsaky ny aotra", "A nonnegative trinomial"),
   ("Montrer que $x^2-2x+1\\ge 0$ pour tout réel $x$.", "Porofoy fa $x^2-2x+1\\ge 0$ ho an'ny réel $x$ rehetra.",
    "Show that $x^2-2x+1\\ge 0$ for every real $x$."),
   "ex_trinome_positif (x : ℝ) : 0 ≤ x ^ 2 - 2 * x + 1", "nlinarith [sq_nonneg (x - 1)]",
   [("Reconnaissez un carré.", "Jereo raha karen'ny zavatra iray io.", "Recognise a square."), "$x^2-2x+1=(x-1)^2$."])
ex("equation-affine", "lycee", "algebre",
   ("Une équation du premier degré", "Équation degré voalohany", "A linear equation"),
   ("Soit $x$ un réel tel que $3x+5=11$. Montrer que $x=2$.", "Réel ny $x$ ary $3x+5=11$. Porofoy fa $x=2$.",
    "Let $x$ be a real number with $3x+5=11$. Show that $x=2$."),
   "ex_equation_affine (x : ℝ) (h : 3 * x + 5 = 11) : x = 2", "linarith",
   [("Isolez $x$.", "Ataovy mitokana ny $x$.", "Isolate $x$."), "$3x=6$."])
ex("moyennes", "lycee", "inegalites",
   ("Produit et carrés", "Vokatra sy kare", "Product and squares"),
   ("Montrer que $2ab\\le a^2+b^2$ pour tous réels $a,b$.", "Porofoy fa $2ab\\le a^2+b^2$ ho an'ny réel $a,b$ rehetra.",
    "Show that $2ab\\le a^2+b^2$ for all real $a,b$."),
   "ex_moyennes (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2", "nlinarith [sq_nonneg (a - b)]",
   [("Étudiez la différence des deux membres.", "Jereo ny elanelan'ny lafiny roa.", "Study the difference of both sides."),
    "$(a-b)^2\\ge 0$."])
ex("produit-consecutifs", "lycee", "arithmetique",
   ("Deux entiers consécutifs", "Isa roa mifanesy", "Two consecutive integers"),
   ("Montrer que $n(n+1)$ est pair pour tout entier naturel $n$.",
    "Porofoy fa azo zaraina amin'ny 2 ny $n(n+1)$ ho an'ny isa natoraly $n$ rehetra.",
    "Show that $n(n+1)$ is even for every natural number $n$."),
   "ex_produit_consecutifs (n : ℕ) : Even (n * (n + 1))", "exact Nat.even_mul_succ_self n",
   [("L'un des deux facteurs est pair.", "Misy iray azo zaraina amin'ny 2 amin'ireo.", "One of the two factors is even."),
    ("Distinguez $n$ pair et $n$ impair.", "Saraho: azo zaraina amin'ny 2 ny $n$, na tsia.", "Split into $n$ even and $n$ odd.")])
ex("somme-impairs", "licence", "arithmetique",
   ("Somme des impairs", "Fitambaran'ny isa tsy azo zaraina amin'ny 2", "Sum of odd numbers"),
   ("Montrer par récurrence que $\\sum_{i=0}^{n-1}(2i+1)=n^2$.", "Porofoy amin'ny récurrence fa $\\sum_{i=0}^{n-1}(2i+1)=n^2$.",
    "Show by induction that $\\sum_{i=0}^{n-1}(2i+1)=n^2$."),
   "ex_somme_impairs (n : ℕ) : ∑ i in Finset.range n, (2 * i + 1) = n ^ 2",
   "induction n with\n| zero => simp\n| succ k ih =>\n  rw [Finset.sum_range_succ, ih]\n  ring",
   [("Raisonnez par récurrence sur $n$.", "Ampiasao ny récurrence amin'ny $n$.", "Use induction on $n$."),
    ("Isolez le dernier terme de la somme.", "Saraho ny singa farany amin'ny fitambarana.", "Split off the last term."),
    "$k^2+2k+1=(k+1)^2$."])
ex("somme-entiers", "licence", "arithmetique",
   ("Somme des entiers", "Fitambaran'ny isa", "Sum of integers"),
   ("Montrer que $2\\sum_{i=0}^{n} i=n(n+1)$.", "Porofoy fa $2\\sum_{i=0}^{n} i=n(n+1)$.", "Show that $2\\sum_{i=0}^{n} i=n(n+1)$."),
   "ex_somme_entiers (n : ℕ) : 2 * ∑ i in Finset.range (n + 1), i = n * (n + 1)",
   "induction n with\n| zero => simp\n| succ k ih =>\n  rw [Finset.sum_range_succ, mul_add, ih]\n  ring",
   [("Raisonnez par récurrence sur $n$.", "Ampiasao ny récurrence amin'ny $n$.", "Use induction on $n$."),
    "$k(k+1)+2(k+1)=(k+1)(k+2)$."])
ex("composee-injective", "licence", "ensembles",
   ("Composée d'injections", "Composée an'ny injection", "Composition of injections"),
   ("Montrer que la composée de deux fonctions injectives est injective.",
    "Porofoy fa injective ny composée an'ny fonction injective roa.",
    "Show that the composition of two injective functions is injective."),
   "ex_composee_injective {α β γ : Type*} (f : α → β) (g : β → γ) (hf : Function.Injective f) "
   "(hg : Function.Injective g) : Function.Injective (g ∘ f)", "intro a b h\nexact hf (hg h)",
   [("Partez de $g(f(a))=g(f(b))$.", "Manomboha amin'ny $g(f(a))=g(f(b))$.", "Start from $g(f(a))=g(f(b))$."),
    ("Utilisez d'abord l'injectivité de $g$.", "Ampiasao aloha ny maha injective ny $g$.", "Use the injectivity of $g$ first.")])
ex("distributivite", "licence", "ensembles",
   ("Distributivité", "Distributivité", "Distributivity"),
   ("Montrer que $A\\cap(B\\cup C)=(A\\cap B)\\cup(A\\cap C)$.", "Porofoy fa $A\\cap(B\\cup C)=(A\\cap B)\\cup(A\\cap C)$.",
    "Show that $A\\cap(B\\cup C)=(A\\cap B)\\cup(A\\cap C)$."),
   "ex_distributivite {α : Type*} (A B C : Set α) : A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)",
   "ext x\nsimp only [Set.mem_inter_iff, Set.mem_union]\ntauto",
   [("Montrez l'égalité élément par élément.", "Porofoy isaky ny singa.", "Prove it element by element.")])
ex("groupe-involutions", "licence", "algebre",
   ("Groupe d'involutions", "Groupe feno involution", "Group of involutions"),
   ("Soit $G$ un groupe tel que $g^2=1$ pour tout $g$. Montrer que $G$ est commutatif.",
    "Groupe ny $G$ ary $g^2=1$ ho an'ny $g$ rehetra. Porofoy fa commutatif ny $G$.",
    "Let $G$ be a group with $g^2=1$ for all $g$. Show that $G$ is commutative."),
   "ex_groupe_involutions {G : Type*} [Group G] (h : ∀ g : G, g * g = 1) (a b : G) : a * b = b * a",
   "have h1 : ∀ g : G, g⁻¹ = g := fun g => by\n  rw [inv_eq_iff_mul_eq_one]\n  exact h g\n"
   "calc a * b = (a * b)⁻¹ := (h1 _).symm\n  _ = b⁻¹ * a⁻¹ := mul_inv_rev a b\n  _ = b * a := by rw [h1, h1]",
   [("Que vaut l'inverse de $g$ ?", "Inona ny inverse an'ny $g$?", "What is the inverse of $g$?"), "$g^{-1}=g$.",
    "$(ab)^{-1}=b^{-1}a^{-1}$."], PUB)
ex("continue-polynome", "licence", "analyse",
   ("Continuité", "Fitohizana", "Continuity"),
   ("Montrer que $x\\mapsto x^2+1$ est continue sur $\\mathbb R$.", "Porofoy fa mitohy ao amin'ny $\\mathbb R$ ny $x\\mapsto x^2+1$.",
    "Show that $x\\mapsto x^2+1$ is continuous on $\\mathbb R$."),
   "ex_continue_polynome : Continuous (fun x : ℝ => x ^ 2 + 1)", "exact (continuous_pow 2).add continuous_const",
   [("Une somme de fonctions continues est continue.", "Mitohy ny fitambaran'ny fonction mitohy.",
     "A sum of continuous functions is continuous.")])
ex("limite-inverse", "licence", "analyse",
   ("Une limite", "Limite iray", "A limit"),
   ("Montrer que $\\frac1{n+1}\\to 0$.", "Porofoy fa $\\frac1{n+1}\\to 0$.", "Show that $\\frac1{n+1}\\to 0$."),
   "ex_limite_inverse : Filter.Tendsto (fun n : ℕ => 1 / ((n : ℝ) + 1)) Filter.atTop (nhds 0)",
   "exact tendsto_one_div_add_atTop_nhds_zero_nat",
   [("Cherchez le lemme de Mathlib sur `1 / (n + 1)`.", "Tadiavo ao Mathlib ny lemma momba ny `1 / (n + 1)`.",
     "Look for Mathlib's lemma on `1 / (n + 1)`.")])
ex("racine-deux", "licence", "arithmetique",
   ("Irrationalité de √2", "Tsy rationnel ny √2", "Irrationality of √2"),
   ("Montrer que $\\sqrt2$ est irrationnel.", "Porofoy fa tsy rationnel ny $\\sqrt2$.", "Show that $\\sqrt2$ is irrational."),
   "ex_racine_deux : Irrational (Real.sqrt 2)", "exact irrational_sqrt_two",
   [("Raisonnez par l'absurde avec une fraction irréductible.", "Ataovy hoe rationnel izy, dia tadiavo ny mifanohitra.",
     "Argue by contradiction with a reduced fraction.")], PUB)
ex("premiers-infinis", "licence", "arithmetique",
   ("Infinité des nombres premiers", "Tsy manam-pahataperana ny isa voalohany", "Infinitely many primes"),
   ("Montrer que pour tout $n$ il existe un nombre premier $p\\ge n$.",
    "Porofoy fa ho an'ny $n$ rehetra dia misy isa voalohany $p\\ge n$.", "Show that for every $n$ there is a prime $p\\ge n$."),
   "ex_premiers_infinis (n : ℕ) : ∃ p, n ≤ p ∧ Nat.Prime p", "exact Nat.exists_infinite_primes n",
   [("Considérez un diviseur premier de $n!+1$.", "Jereo ny isa voalohany mizara ny $n!+1$.", "Consider a prime divisor of $n!+1$.")], PUB)
ex("noyau-injectif", "master", "algebre-lineaire",
   ("Noyau et injectivité", "Noyau sy injectivité", "Kernel and injectivity"),
   ("Montrer qu'une application linéaire est injective si et seulement si son noyau est nul.",
    "Porofoy fa injective ny application linéaire raha aotra ny noyau, ary raha izany ihany.",
    "Show that a linear map is injective if and only if its kernel is zero."),
   "ex_noyau_injectif {K V W : Type*} [Field K] [AddCommGroup V] [Module K V] [AddCommGroup W] [Module K W] "
   "(f : V →ₗ[K] W) : LinearMap.ker f = ⊥ ↔ Function.Injective f", "exact LinearMap.ker_eq_bot",
   [("$f(x)=f(y)$ équivaut à $x-y\\in\\ker f$.", "Mitovy dika ny $f(x)=f(y)$ sy ny $x-y\\in\\ker f$.",
     "$f(x)=f(y)$ is equivalent to $x-y\\in\\ker f$.")])
ex("image-compact", "master", "topologie",
   ("Image d'un compact", "Image an'ny compact", "Image of a compact set"),
   ("Montrer que l'image d'un compact par une fonction continue est compacte.",
    "Porofoy fa compact ny image an'ny compact amin'ny fonction mitohy.", "Show that the continuous image of a compact set is compact."),
   "ex_image_compact {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y] {K : Set X} (f : X → Y) "
   "(hK : IsCompact K) (hf : Continuous f) : IsCompact (f '' K)", "exact hK.image hf",
   [("Ramenez un recouvrement ouvert par $f^{-1}$.", "Avereno amin'ny $f^{-1}$ ny recouvrement ouvert.",
     "Pull an open cover back by $f$.")], PUB)
ex("ordre-premier", "master", "algebre",
   ("Groupe d'ordre premier", "Groupe manana ordre isa voalohany", "Group of prime order"),
   ("Montrer qu'un groupe d'ordre premier est cyclique.", "Porofoy fa cyclique ny groupe manana ordre isa voalohany.",
    "Show that a group of prime order is cyclic."),
   "ex_ordre_premier {G : Type*} [Group G] [Fintype G] {p : ℕ} [Fact p.Prime] (h : Fintype.card G = p) : IsCyclic G",
   "exact isCyclic_of_prime_card h",
   [("Prenez un élément différent de $1$ et utilisez Lagrange.", "Makà singa tsy $1$ ary ampiasao ny teorema an'i Lagrange.",
     "Take an element other than $1$ and use Lagrange.")], PUB)
ex("suite-monotone", "master", "analyse",
   ("Suite croissante majorée", "Suite croissante misy majorant", "Bounded monotone sequence"),
   ("Montrer qu'une suite réelle croissante et majorée converge.", "Porofoy fa converge ny suite réelle croissante misy majorant.",
    "Show that a nondecreasing real sequence bounded above converges."),
   "ex_suite_monotone (u : ℕ → ℝ) (hu : Monotone u) (hb : BddAbove (Set.range u)) : "
   "∃ l, Filter.Tendsto u Filter.atTop (nhds l)", "exact ⟨_, tendsto_atTop_ciSup hu hb⟩",
   [("Le candidat pour la limite est la borne supérieure.", "Ny borne supérieure no mety ho limite.",
     "The candidate limit is the supremum.")], PUB)
ex("cube-moins-n", "olympiade", "arithmetique",
   ("Divisible par 6", "Azo zaraina amin'ny 6", "Divisible by 6"),
   ("Montrer que $6$ divise $n^3-n$ pour tout entier $n$.", "Porofoy fa azo zaraina amin'ny 6 ny $n^3-n$ ho an'ny entier $n$ rehetra.",
    "Show that $6$ divides $n^3-n$ for every integer $n$."),
   "ex_cube_moins_n (n : ℤ) : 6 ∣ n ^ 3 - n",
   "have h : n % 6 = 0 ∨ n % 6 = 1 ∨ n % 6 = 2 ∨ n % 6 = 3 ∨ n % 6 = 4 ∨ n % 6 = 5 := by omega\n"
   "apply Int.dvd_of_emod_eq_zero\n"
   "rcases h with h | h | h | h | h | h <;> simp [pow_succ, Int.sub_emod, Int.mul_emod, h]",
   [("Factorisez $n^3-n$.", "Soraty ho vokatra ny $n^3-n$.", "Factor $n^3-n$."), "$n^3-n=(n-1)n(n+1)$."], PUB)
ex("carre-mod-quatre", "olympiade", "arithmetique",
   ("Carrés modulo 4", "Kare modulo 4", "Squares modulo 4"),
   ("Montrer que le reste de $n^2$ dans la division par $4$ est $0$ ou $1$.",
    "Porofoy fa $0$ na $1$ ny ambiny rehefa zaraina amin'ny $4$ ny $n^2$.", "Show that $n^2$ leaves remainder $0$ or $1$ when divided by $4$."),
   "ex_carre_mod_quatre (n : ℤ) : n ^ 2 % 4 = 0 ∨ n ^ 2 % 4 = 1",
   "have h : n % 4 = 0 ∨ n % 4 = 1 ∨ n % 4 = 2 ∨ n % 4 = 3 := by omega\n"
   "rcases h with h | h | h | h <;> simp [pow_two, Int.mul_emod, h]",
   [("Distinguez les restes possibles de $n$ modulo $4$.", "Saraho ny ambiny mety ho azo amin'ny $n$ modulo $4$.",
     "Split on the remainder of $n$ modulo $4$.")], PUB)
ex("somme-inverses", "olympiade", "inegalites",
   ("Somme et inverses", "Fitambarana sy inverse", "Sum and inverses"),
   ("Soient $a,b>0$ réels. Montrer que $(a+b)\\left(\\frac1a+\\frac1b\\right)\\ge 4$.",
    "Réel ny $a,b>0$. Porofoy fa $(a+b)\\left(\\frac1a+\\frac1b\\right)\\ge 4$.",
    "Let $a,b>0$ be real. Show that $(a+b)\\left(\\frac1a+\\frac1b\\right)\\ge 4$."),
   "ex_somme_inverses (a b : ℝ) (ha : 0 < a) (hb : 0 < b) : 4 ≤ (a + b) * (1 / a + 1 / b)",
   "have h : (a + b) * (1 / a + 1 / b) - 4 = (a - b) ^ 2 / (a * b) := by\n  field_simp\n  ring\n"
   "have h2 : 0 ≤ (a - b) ^ 2 / (a * b) := by positivity\nlinarith",
   [("Réduisez au même dénominateur.", "Ataovy mitovy dénominateur.", "Use a common denominator."),
    ("La différence vaut $\\frac{(a-b)^2}{ab}$.", "Mitovy amin'ny $\\frac{(a-b)^2}{ab}$ ny elanelana.",
     "The difference is $\\frac{(a-b)^2}{ab}$.")], PUB)
ex("puissance-sept", "olympiade", "arithmetique",
   ("Divisible par 7", "Azo zaraina amin'ny 7", "Divisible by 7"),
   ("Montrer que $7$ divise $2^{3n}-1$ pour tout entier naturel $n$.",
    "Porofoy fa azo zaraina amin'ny 7 ny $2^{3n}-1$ ho an'ny isa natoraly $n$ rehetra.",
    "Show that $7$ divides $2^{3n}-1$ for every natural number $n$."),
   "ex_puissance_sept (n : ℕ) : 7 ∣ 2 ^ (3 * n) - 1",
   "have h : 2 ^ (3 * n) = 8 ^ n := by rw [pow_mul]; norm_num\nrw [h]\nsimpa using nat_sub_dvd_pow_sub_pow 8 1 n",
   ["$2^{3n}=8^n$.", ("$x-1$ divise $x^n-1$.", "Mizara ny $x^n-1$ ny $x-1$.", "$x-1$ divides $x^n-1$.")], PUB)

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "madalean" / "teaching" / "seed.json"
    out.write_text(json.dumps({"format": "madalean-exercises/1", "title": "Madalean", "licence": "CC0-1.0",
                               "exercises": X}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
