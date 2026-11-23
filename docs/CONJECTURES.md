# Moteur de conjectures (session S-AW, DECISIONS D55)

A guided loop that helps a mathematician find **what to prove**: from a question in words or a formula to data, to
patterns, to precise conjectures with a Lean statement, to a counter-example hunt, to a proof attempt — every step
visible, stoppable and recorded. It sits on top of what existed (the conjecture workshop of
[RESEARCH_WORKSHOP.md](RESEARCH_WORKSHOP.md) §3, the Calcul notebook of [CALCUL.md](CALCUL.md), the proof pipeline)
and replaces none of it. Screen: Conjectures › « Explorer » (`/explorer`). API: [API.md](API.md) §6e.

Nothing in this module says « true ». A candidate carries the range it was tested on (« vérifié jusqu'à n = 59
(60 cas…), pas démontré »); `proved` only comes from the normal pipeline (a fresh strict Lean); `refuted` only from
a counter-example recomputed independently and, when there is a Lean statement, closed by Lean.

| File | Role |
|---|---|
| `madalean/research/cjcatalog.py` | request → intent without a model; deterministic experiment code (Sage / Python), exact value in-process, LaTeX, Lean term per Mathlib flavour; the fixed driver |
| `madalean/research/cjpatterns.py` | local pattern finders (pure Python, exact rationals, no network), re-check of a finding on new data |
| `madalean/research/oeis.py` | OEIS look-up (one official JSON call, cached, rate-limited, off in Local mode) |
| `madalean/research/cjstate.py` | finding → conjecture in words + LaTeX (FR / EN), Lean statement, strength label, normalised key |
| `madalean/research/cjengine.py` | the loop, the store, the hunt, the journal, export |
| `madalean/server/plugins/conjecture_engine.py` | HTTP API, demo wiring |
| `web/src/screens/research/Explore.svelte`, `web/src/lib/conjectures/` | the guided screen (its own lazy chunk), strings FR / EN, plot |

## 1. The loop

```
question ──► 1 Explorer ──► 2 Reconnaître ──► 3 Énoncer ──► 4 Attaquer ──► preuve (dossier) / conjecture ouverte
              table          motifs + OEIS      conjectures     chasse au        réfutée : gardée avec son
              (carnet)       (gardés/écartés)   + énoncé Lean   contre-exemple   contre-exemple
                                          5 Journal : tout ce qui a été essayé
```

An exploration belongs to a project and is one JSON file,
`<config>/research/explore/<project>/<x-id>.json`: question, intent, experiment, table (≤ 4000 rows), every finding
(kept and discarded), candidates, journal (≤ 400 entries). Steps have a state (`todo`, `running`,
`awaiting_approval`, `done`, `failed`, `stopped`) and are published as `explore.updated` events. One run at a time
per exploration; « Arrêter » cancels the task and interrupts the kernel.

## 2. Explore — data

### 2.1 What is recognised without a model (`cjcatalog.recognise`)

Same idea as D39 for Calcul: the request is parsed, not guessed.

- **Sequences** (one to three, « … et … »): named arithmetic functions (σ_k, τ, φ, n!, Fibonacci, Lucas, p_n, π(n),
  Catalan, binomials, partitions, Bell, harmonic numbers, ω, μ, gcd), « somme / produit des n premiers … » (odd,
  even, integers, squares, cubes, primes, Fibonacci, triangular, factorials, powers of 2), « somme des carrés des
  diviseurs », and any **formula in n** over those (`n^2 + n + 41`, `fib(n)^2 + fib(n+1)^2`, `H_n`, `n!`), French or
  English, Unicode or LaTeX. A range may be given (« jusqu'à 200 »); default 60 terms.
- **Given terms** (« 1, 1, 2, 5, 14, 42, 132 », at least 6): nothing is computed; the terms are the table.
- **Families of small objects**: graphs (« graphes connexes à n sommets », « arbres », « graphes bipartis ») with
  their invariants n, m, Δ, δ, χ, ω, α, diameter and the graph6 string — exhaustive through Sage's generators for
  small n, random samples (fixed seeds) beyond. Sage only.
- Words that are not understood make the request **unknown** (« somme des carrés des diviseurs impairs » is not σ₂):
  two different questions never share a code.

One expression tree per sequence gives, deterministically: the experiment's code (Sage, or Python with explicit
helper definitions and `Fraction`s), the exact value in this process (no `eval`; used by the demo and as the
reference of the tests), the LaTeX of the definition and the Lean term in the right ring (ℕ when there is no
subtraction or division, else ℤ, else ℚ) for the workspace's Mathlib (`∑ … in` for Lean 4.9, `∑ … ∈` otherwise).
The formula parser is strict (integers, `n`, `+ − * / ^ !`, parentheses, catalogue functions): nothing else of the
user's text reaches the code.

### 2.2 The experiment's contract

Every experiment — catalogue or model — defines `cj_columns`, `cj_index` and `cj_rows_for(n)` (the rows of the
table at index n), computes `cj_rows` and displays the first rows. The engine reads the table with its **fixed
driver** (`cjcatalog.driver`: Madalean's own program, only integers enter it), run in the same kernel outside the
notebook's history; the hunt calls `cj_rows_for` at other indices through the same driver, within a time budget.
Values travel as strings (integers of any size, `p/q`); floating-point values are not data.

### 2.3 Where it runs, and the approval rule

The experiment is a cell of the project's Calcul notebook « Explorations (conjectures) » (`explorations.ipynb`,
`explorations-python.ipynb` for Python): the same sandboxed kernel, private home, memory and time limits, warm
start (D47, `POST …/warm`) and file as any Calcul cell — it opens in Calcul and in JupyterLab, the table is in it.
The engine never executes code itself: it asks the workbench (`Workbench.run_cell`), which applies Calcul's rule
unchanged (`NotebookStore.may_run`, [SECURITY.md](SECURITY.md)):

- catalogue code (Madalean's deterministic program) and the user's own code are ordinary cells: they run;
- **model code runs only once this exact code was approved on this host** (by hash, with Calcul's own endpoint and
  the same prompt in the UI), or when the host enabled `experiments_auto`; an edit drops the approval, and a model's
  cell edited by the user stays model code;
- from a paired device, only when the host enabled `experiments_remote`.

The driver, the hunt and Sage's guesser run only after the same `may_run` check on the cell as it is now. Given
terms need no execution. When no model is available for an unrecognised request, the screen says so and the user
may write the code (the contract is checked).

## 3. Recognise — patterns

### 3.1 Look-ups

**OEIS** (`oeis.py`): one call to the official JSON search (`https://oeis.org/search?q=<first terms>&fmt=json`)
through the research layer's only network client (`fetch.Fetcher`: https only, allow-listed host, no cookie, no
proxy from the environment, a contact-less client name). Anonymous: only the terms are sent. Polite: one request per
look-up, ≥ 5 s between requests, answers cached on disk (`<cache>/oeis/`, 30 days; 1 day for « nothing ») and in
memory. **Local mode, or a project marked « local only »: no request at all** (the client is not called; the
journal says « OEIS non interrogé : mode Local »). An entry is a match only when every computed term agrees with the
entry's listed terms where they overlap; the others are journalled as discarded with the first index that differs.
A match becomes a candidate « a(n) est le terme d'indice n + s de A… » with the label « coïncide sur k termes ».
OEIS content is © The OEIS Foundation, CC BY-SA 4.0; the recorded answer used by the demo and the tests
(`madalean/research/demo_oeis/`, one real query, trimmed to the fields the client reads) is attributed in NOTICE.

**LMFDB: not queried.** Its API (`lmfdb.org/api/<table>/?_format=json`, checked on 2026-11-22: it answers, and is
declared beta by LMFDB) is keyed by object fields (label, conductor, degree…), not by a list of computed terms, so
it offers no look-up that fits this step; matching a sequence of traces to a curve or a form would need
object-specific queries the engine does not have yet. The journal of every exploration says it. A later version
can add recognisers for elliptic curves, number fields and modular forms once the catalogue knows those objects.

### 3.2 Local finders (`cjpatterns.py`)

Pure Python over exact rationals, no network, no model, at most 240 terms. A fit uses a first part of the data and
is **validated on held-out terms** (a quarter, at least 3) it never saw, with at least 3 equations more than
unknowns; a fit that fails there is `discarded: held_out` with the first failing term.

| Finder | Method | Statement |
|---|---|---|
| polynomial | finite differences, Newton interpolation, small integer roots factored out | a(n) = n(n+1)(2n+1)/6 |
| rational function | exact nullspace of a(n)·Q(n) − P(n) = 0, deg ≤ 4 in total | a(n) = P(n)/Q(n) |
| linear recurrence | Berlekamp–Massey over ℚ (order ≤ 12, 2·order + 3 ≤ terms fitted) | a(n) = Σ cᵢ a(n−i), and the generating function P/Q |
| polynomial coefficients | exact nullspace, shapes (order, degree) from (1,1) to (3,1) | (n+2)·a(n+1) = (4n+2)·a(n) |
| algebraic generating function | exact nullspace on truncated powers of the series | x·A² − A + 1 = 0 |
| multiplicativity | every coprime pair in range (≥ 6), completeness | a(mn) = a(m)a(n) |
| periodicity, congruences | exact period; gcd of the differences; periodic residues mod 2–5 | a(n) ≡ r (mod g) |
| properties | all prime (deterministic Miller–Rabin), all squares, strictly increasing | — |
| growth | least squares on the second half, floating point | **heuristic**, labelled as such, no Lean statement |
| relations between columns | equalities, exact linear relations, inequalities a ≤ b + d (d ∈ {0, 1}, transitive ones dropped) | χ ≤ Δ + 1, m = n − 1 |

Redundant findings are journalled, not offered twice (the recurrence a polynomial implies; a formula the user typed
« found » again: `definition`). When the kernel is Sage, `CFiniteSequences(QQ).guess` gives a second opinion on a
rational generating function (a fixed program; `ore_algebra` is reported when present and not required). Sage's
graph generators (`nauty_geng`, `graphs.trees`) provide the families; relations between invariants come from the
same finders.

## 4. State — conjectures

Each kept finding becomes a candidate (`cjstate.candidate`): the statement in words + LaTeX in French and English
(« Soit a(n) = Σ_{k=1}^{n} (2k−1) (somme des n premiers nombres impairs). Alors pour tout entier n ≥ 0 : a(n) =
n². »), a **Lean 4 statement** when every sequence involved has a Lean term, the evidence (range, number of cases,
held-out terms, the code) and the strength label. All Lean statements of an exploration are compiled in **one**
file on the project's workspace; a refused statement is shown as refused and never attached. Statements without a
deterministic Lean form (given terms, model experiments, graphs, generating functions, OEIS identifications) are
formalised by the normal pipeline when the user asks for a proof.

Duplicates: a candidate with the same normalised key (sequence + kind + parameters), the same Lean statement (name
and spacing aside) or the same words as a conjecture of the project is flagged with a link, and « Garder » returns
the existing conjecture.

## 5. Attack — the counter-example hunt

« Chercher un contre-exemple » recomputes the experiment beyond the tested range: a contiguous block, then
structured indices (powers of two, primes, factorials…) and random ones (seeded), with the neighbours a recurrence
needs; for objects, the next sizes, then random samples; for an OEIS identification, the further terms the entry
lists. The finding is re-checked exactly on the new data (`cjpatterns.check`).

- Nothing found: the label grows (« vérifié jusqu'à n = 261 (276 cas…), et par sondage jusqu'à n = 299, pas
  démontré »), the candidate is `survived`, and the screen offers « Tenter la preuve » (the candidate becomes a
  conjecture dossier and goes through the normal pipeline — formalisation first when it has no accepted Lean
  statement; S-AT's certificate strategy applies there when it lands) or « Garder comme conjecture ouverte ».
- A violation is believed only once **recomputed in a fresh kernel** (the same approved code) and, when the
  candidate has a Lean statement, **closed by Lean** at the witness (`conjectures.negation_file`, the existing
  path). Then the candidate is `refuted` and is kept as a conjecture of the project with its counter-example
  (status « réfutée », evidence chained). Otherwise it is `disputed` (« contre-exemple non confirmé »).
- Given terms cannot be hunted (« ajoutez des termes »); heuristics and generating-function statements are not
  tested term by term: said, not hidden.

## 6. Journal

Everything tried is in the exploration's journal, in both languages: what was recognised, the data, each pattern
kept, each pattern discarded and why, the OEIS answer (or why it was not asked), the LMFDB note, each candidate
(duplicates included), each hunt, each refutation, what the user kept or discarded. « Exporter vers une note »
writes the whole exploration (data, conjectures with their labels and Lean statements, code, journal) as a note of
the project; « Exporter vers l'article » appends the conjectures to the article.

A kept conjecture is an ordinary conjecture (`POST /api/conjectures` semantics, `origin.engine = {exploration,
candidate, norm, kind, question}`) with evidence entries `exploration`, `hunt`, `counterexample_check` in its
hash-chained log.

## 7. Demo mode

No kernel in the demo: a recognised sequence is computed by the catalogue's own reference implementation; the fake
Lean answers; OEIS answers from the recorded fixture (the Catalan terms; other look-ups say « démonstration »). The
screen proposes: the sum of the first n odd numbers (→ a(n) = n²), the Catalan terms (→ A000108, the recurrence, the
algebraic generating function), `n^2 + n + 41 jusqu'à 30` (→ « toujours premier », refuted at n = 40), σ₂, graphs
(needs a real kernel). An unrecognised question shows the approval prompt with a scripted model answer.

## 8. Limits

- The catalogue is small on purpose (verified constructions); everything else goes through a model + approval.
- Finders see at most 240 terms and skip the linear algebra when entries exceed 6000 bits.
- Lean statements for graphs, generating functions and OEIS identifications are left to the formalizer.
- LMFDB is not queried (§3.1). `ore_algebra` is not installed with Madalean's Sage; the engine's own finders cover
  the shapes above.

## 9. Tests

`tests/test_conjecture_engine.py`: finders on squares, Fibonacci, Catalan (recurrence + generating function), σ₂, a
false pattern rejected by the held-out check; the catalogue (same request → same code; Python experiments equal to
the reference values); the OEIS client on the recorded answer, its cache, **zero requests in Local mode**; the loop
through the API with a fake kernel (keep, duplicates, hunt, export); **unapproved model code never runs** (route
and engine, wrong hash, paired device, edited code); the planted false conjecture refuted (fresh recomputation +
Lean negation), `disputed` when the recomputation disagrees; real Lean (`lean-prover49`): every generated statement
compiles and the negation closes at n = 40 and not at n = 39; real Sage (`sage` marker): every catalogue cell
preparsed by Sage equals the reference, the graph family, Sage's guesser, and the whole loop in the real sandboxed
kernel. Web: `web/tests/unit/explore.test.ts`, `web/e2e/explore.spec.ts` (flows, axe light / dark, phone width).
