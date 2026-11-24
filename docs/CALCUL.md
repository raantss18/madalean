# Calcul — the Sage notebook of Madalean (session S-P)

« Calcul » is a real notebook: a sequence of cells that share one kernel state, like JupyterLab, connected to the
whole research flow (conjectures, Lean dossiers, notes, article, « Publier »). **One engine** computes and plots
everything: SageMath (or Python for a Python document). **One file**: a standard `.ipynb` that JupyterLab opens.
**One kernel** per document, shared with JupyterLab. Code: `madalean/research/notebook.py` (documents, cells,
outputs, publication producer), `madalean/research/nbkernels.py` (kernels), `madalean/server/plugins/workbench.py`
(HTTP API), `web/src/screens/research/Calcul.svelte`, `web/src/lib/figure/**` + `web/src/components/figure/`
(interactive figures). Tests: `tests/test_calcul_notebook.py`, `tests/test_workbench.py`, `tests/test_brain_fast.py`, `tests/test_syntaxcards.py`,
`web/tests/unit/calcul-detect.test.ts`, `web/tests/unit/calcul-texwrap.test.ts`,
`web/tests/unit/figure.test.ts`, `web/e2e/workbench.spec.ts` (« calcul notebook … »).

## 1. Documents and cells

- A project has one or more documents, `<notebooks>/calcul/<project id>/<doc>.ipynb` inside the integrated
  JupyterLab's tree (`~/Documents/Madalean/notebooks` by default). The default document is `calcul`.
  nbformat 4.5, validated by `nbformat.validate` in the tests; kernelspec `madalean-sage` or `madalean-python`.
- Cell types (nbformat mapping):

  | Madalean | .ipynb | Shown in JupyterLab as |
  |---|---|---|
  | Code (Sage / Python) | code cell | the same code cell |
  | Demander (natural language) | code cell, `metadata.madalean = {kind: "ask", prompt}` | the generated code |
  | Texte (Markdown + `$LaTeX$`) | markdown cell | the same text |
  | Figure (curves, dynamic geometry) | markdown cell `![…](attachment:figure.svg)` + SVG attachment, `metadata.madalean = {kind: "figure", figure: FigureSpec}` | a static image |

- What must not travel with a file — who wrote a cell (model or user), the approval by hash, the version history and
  the run history — lives on the host in `<config>/research/calcul/<pid>/<doc>.json`. A notebook received from
  someone else can therefore never carry an approval (tested).
- **Sequential execution, one state**: « Tout exécuter », « Exécuter jusqu'ici », « Exécuter à partir d'ici », one
  cell (Shift+Enter / Ctrl+Enter). Runs stop at the first error or at model code not yet approved. Execution
  counters come from the kernel (`store_history`).
- **Stale cells**: each run records the hash of the code of all code cells above it (`upstream`). A result is
  « Périmé » when its code changed (`code`), when a cell above changed, was inserted or removed (`upstream`), or when
  a cell above was run again after it in the same kernel (`order`). Results from an earlier kernel session (after a
  restart) are marked as such.
- Restart, interrupt, stop, clear outputs; versions of each cell (20) and runs (8) kept in the sidecar; deleted
  cells restorable (Z); drag to reorder (and Move up / down in the menu for keyboard users).
- **Migration**: an S-M worksheet `<config>/research/calcul/<pid>.json` becomes the `calcul` document on first
  use (code, versions, approvals, last outputs with their images); the JSON is kept as `<pid>.json.migrated`.
  The old routes `/api/calcul/{pid}/…` act on the default document; `NotebookStore.add/load/asset_path` keep the
  S-M call shapes for the article editor (S-R) and the research agent (S-Q).

## 2. Kernels and memory (`nbkernels.py`)

- The kernel of a document is the kernel of the Jupyter **session** of its path in Madalean's JupyterLab child.
  If JupyterLab has the notebook open, Madalean attaches to that session's kernel; otherwise Madalean creates the
  session itself (`POST /api/sessions`), so JupyterLab finds it when it opens the file. Never two kernels for one
  document (tested with a real jupyter-lab, real sandboxed Python and Sage kernels, in both orders).
- Only Madalean's sandboxed kernelspecs run notebook code (offline network namespace, bubblewrap, allow-listed
  environment, rlimits — docs/SECURITY.md). If the user switches the session to another kernel in JupyterLab,
  Madalean refuses to execute (`kernel_not_sandboxed`) and says so.
- Madalean's helpers are loaded once per kernel (`tex`, `fig`, `report`, `_madalean_vars`, `_madalean_approx`,
  `_madalean_latex`); a restart from JupyterLab is detected (cheap probe) and they are reloaded.
- A Python kernel never imports Sage for these helpers.
- S-AO (D47): opening a document — or its project — prepares its kernel in advance (§11, setting « Calcul prêt
  d'avance », on by default). With the setting off, opening starts nothing and the first run starts the kernel.
  Kernels stay warm (user decision) and stop
  after `calcul_idle_minutes` (default 30, 0 = never; setting) without activity, counting both Madalean's runs and
  the kernel's own `last_activity` (JupyterLab use keeps it alive). Notebook kernels are separate from the
  experiment kernels of conjectures (`SageBridge.kernels`, bounded by S-Q's `MAX_WARM_KERNELS`).
- Measured (2026-11-21, this machine, sandboxed): Sage 10.10 kernel ≈ 250 MB RSS after `graphs.PetersenGraph()`
  + its TCP→IPC relay ≈ 18 MB; Python kernel ≈ 48 MB + relay ≈ 10 MB; JupyterLab ≈ 85 MB. Two warm notebooks
  (one Sage, one Python) ≈ 0.4 GB in all.
- Outputs are stored once, in the `.ipynb` (standard: JupyterLab, nbviewer and nbconvert read them). Images are
  addressed by content (sha-256, 32 hex): `/api/calcul/assets/<id>` reads them from the notebook, no copy on disk.
  No `text/html` and no scripts are ever kept; PNG is checked by magic number, SVG sanitised (when recorded and
  again when served). Text outputs are capped (200 000 characters); the model receives at most ≈ 1 500 characters
  per output.

## 3. Natural language → Sage (« Demander »)

The user writes a request (« trace sin(x)/x sur [-10,10] », « factorise x^4+4 sur Z[i] », « graphe de Petersen et
son nombre chromatique »). The model receives a compact summary of the names defined in the kernel (name, type,
80-character value excerpt — asked to the running kernel through Madalean's own helper, or read from the code above
when no kernel runs, the device may not execute, or the kernel is busy) and the last earlier cells (≤ 2 500
characters), and returns one code cell. The code is shown; it runs under the unchanged rules: model code runs only
once its exact hash was approved on the host (or the host enabled `experiments_auto`); paired devices need
`experiments_remote`.

**Attachments (S-BA, D59).** A « Demande » cell has a paperclip: the image / PDF / LaTeX / BibTeX file becomes a
Source of the project and is read once into a digest (the dossier attachments' code, `literature/attach.py`,
SHA-256 + extractor version; a file the project already read is only linked). Calcul cells are project notebooks, so
the attachment belongs to the project (`attach.ProjectNotebook`, links in `<shelf>/calcul_attachments.json` with the
cells that use each one); the cell shows chips « Pièce jointe N — nom · lue ». A request naming « pièce jointe N
(, lemme 3.1) » gets the digest's verbatim quotes (≤ 4 × 800 characters) appended to the text the model sees; the
cell's stored request is the user's own words. The written code keeps the approval rule above.

### 3.1 Speed (session S-AB, DECISIONS D35) — `research/codegen.py`

| Cause found (2026-11-22, measured) | Fix |
|---|---|
| Role `assistant` → best-quality chain (Gemini 4 Hydrogen, 2.5 Pro, GLM…), tried one after the other with a 120–300 s first-byte wait: one real run took **128 s** (503, 404, a 120 s stall, 402) before Gemini 3.6 Flash answered; a good run 5.5–6 s (Hydrogen thinking « low ») | `classify.task("transcribe")`: code models ranked with their **measured latency** (`States.record_latency`, moving average of the time to the first visible text; ≤ 1.5 s +0.20 … ≥ 12 s −0.30), thinking capped (Gemini `reasoning_effort: minimal`, Claude effort low, no thinking), 20 s first-byte / stall timeouts, a chain of 10 online models, and a **staggered race**: the next model starts when nothing was written after 2.5 s (≤ 3 at once), a failure starts the next one at once, the first complete answer wins, the others are cancelled |
| The call took one of the job scheduler's 3 `online` slots and the brain's 3-request pool: it queued behind a dossier's long proof calls | no scheduler slot; a separate pool of 4 for interactive transcriptions |
| The names query to the kernel waited (up to 20 s) when a cell was running | names read from the code when the kernel is busy; 3 s cap otherwise |
| Long prompt (≈ 6 000 characters of earlier cells), rules mixed with variable parts | fixed system prompt per tool version (rules + syntax card, §3.3: cacheable) + short user message |
| The whole answer arrived at the end | the code streams into the cell (`calcul.draft {cell_id, code, state}` events) |

S-AG (DECISIONS D39) replaced the « first model to answer wins » choice for code: one pinned model per language,
temperature 0 + seed, the race only as fallback, and a request whose code was already written gets that same code
(§3.6) — « Réécrire » included. Measured after (same machine, same keys, free models, 2026-11-22): first code **0.6–1.7 s** (Gemini
Flash-Lite / 3 Flash, minimal thinking), 3.9 s when the first model was slow (race), 6.7 s when two providers
answered 503 / 429; before: 5.5–6 s at best, 128 s in the bad case.

### 3.2 Checked before it is shown, corrected automatically

- **Before display**: the installed Sage's own preparser + Python's compiler (never executes) + names defined
  nowhere (not in Sage's `sage.all`, the builtins, the cell, the kernel / earlier cells). On an error the model gets
  the exact error and the signatures of what the code calls, up to 2 times; every attempt is kept as a version of
  the cell.
- **After a failed run** (`ask` cells): the error goes back to the model, at most 3 corrections per request, each a
  version (« Corrigé automatiquement (n/3) », « Revenir à la version précédente »). **Policy (D35)**: the corrected
  code runs again by itself only where model code needs no approval (`experiments_auto`); otherwise it waits for
  « Approuver et exécuter » like any model code. The correction runs after the kernel lock is released (other cells
  can run meanwhile) and is cancelled by a new request on that cell.
- **Who corrects** (S-AG then S-AN, D39 / D46): (1) the deterministic fixer (a missing import, a library load, a
  conventional object, a definition of an earlier cell — no model); (2) else **the conductor** (docs/BRAIN.md §18):
  Claude, the tier chosen by its scoring within this request's budget (1 $ by default, then « Plafond atteint :
  continuer avec Claude (+0,50 $) ? »), else the best free model, with the Sage / Python rule cards and the
  catalogue's canonical constructions of the recognized request; (3) else, or when its answer does not even pass the
  installed Sage's preparser, the usual Calcul model as before. Whoever wrote it, the correction is model code:
  same approval rule, same sandboxed kernel, same ≤ 3 per request. The cell says « Corrigé par Claude Sonnet ·
  0,004 $ » (also in « Historique »); a correction that runs OK becomes the request's « meilleure version » through
  the recipes ranking (§3.6) — and only counts for the conductor's measurements, never for the pinned Calcul model.
- **« Réécrire » is always possible**: one generation per cell (`codegen.Generations`); a new request cancels the one
  still running for that cell (the replaced request answers 409 `replaced`, ignored by the UI). Cause of the old
  refusal: the automatic correction ran INSIDE the notebook's kernel lock (15–30 s of model time measured in the
  user's notebook), so « Approuver et exécuter » / « Exécuter » got 409 `busy`, which the UI showed with the generic
  text « Ce dossier travaille déjà ». The notebook now answers `calcul_busy` (« Des cellules sont en cours
  d'exécution… ») only while cells really run.
- When the code relies on names of earlier cells, the cell says so (« Utilise F, f des cellules précédentes »).

### 3.3 Version-aware syntax catalogue — `madalean/syntaxcards.py`

- **Sage card**: 23 idioms and pitfalls (`var`, `^`, exactness / `N`, callable functions, `integral` = `integrate`,
  `assume` / `forget`, symbolic `sum` and `hold=True`, Fourier series, limits, Taylor, `solve` / `find_root`,
  polynomial rings incl. `ZZ[I]`, ODE, matrices, number theory, `srange` / `[a..b]`, plots as last expression,
  implicit / parametric / polar / 3D, `latex` / `tex`, graphs). Each entry carries a snippet with `assert`s that the
  **installed Sage runs** during the build (its own `DOT_SAGE` / `MAXIMA_USERDIR` under the cache); a failing entry
  is dropped. Same build: the name index of `sage.all` (1 887 names on 10.10) and exact signatures + first doc
  paragraph of ≈ 35 functions, chosen per request from its words (FR/EN). Build ≈ 15 s, file
  `<cache>/syntax/sage-<version>.json`. Version read at runtime from the interpreter of the `sagemath` kernelspec
  (Madalean's own Sage env first, else /usr/bin/python).
- **Lean card**: 13 Lean 4 / Mathlib rules (no Lean 3 syntax, naming, `∑ i ∈ s` vs the older `∑ i in s`,
  `obtain` / `rcases`, induction, closing tactics, casts, `calc`, predicates, reals). Names cited by an entry are
  checked in the workspace's declaration index (`names.py`, reused; `@[to_additive]` names via their
  multiplicative source), then all entries are compiled in ONE file with the workspace's Lean; an entry with an error
  or a deprecation warning is dropped (measured: `lean-prover49` keeps `∑ … in`, `lean-current` (Lean 4.36) drops
  it). Key = workspace + toolchain + Mathlib revision. Injected in the prover agent's system prompt (cached on
  Anthropic).
- **Regeneration**: 90 s after the server starts (missing or outdated cards only), at every pass of the update
  checkers (checker « Syntaxe », no network, also in local mode), after a Mathlib / Lake update applied; a first
  ask with a new Sage version uses the unverified built-in card and schedules the build. Learned recipes are
  re-checked after a new Sage card (§3.5).

### 3.4 Cells (UI, S-AB)

One « + » under the last cell; running the last cell adds a new empty one. A new cell recognises what is typed: code
(the installed Sage compiles it, names exist) or a request in words (request verb, French / English words, `?`,
accents) — `POST …/detect`, with an instant local guess (`lib/calcul/detect.ts`); the chip « Code / Demande » shows
the guess and switches it in one click. Shift+Enter runs code or sends the request. The cell type (Code, Demande,
Texte, Figure) is a small menu in the cell's head; the head keeps only « ⋯ ». Request cell: the request, « Réécrire »
right below it, the code (filling live while the model writes), « Approuver et exécuter » right below the code.

« Expliquer » on demand (`research/explain.py`, generic: `POST /api/code/explain {language: sage|python|lean, code,
error?, mode: error|lines|steps}`, reusable by the Lean screens; `steps`: §3.7): on an error, « Expliquer l'erreur » (plain French, a
proposed fix shown as a suggestion; « Appliquer la correction » makes it model code, approval needed); « Expliquer
ligne par ligne » (« ⋯ »): one sentence under each line. Same fast role and syntax card. The Lean screens (dossier
statement and proof, notes' Lean blocks) use the same service with a Lean prompt, Lean's goal states and a correction
checked by Lean before it is shown (S-AM, [BRAIN.md §19](BRAIN.md), [API.md §3.8a](API.md)).

Long LaTeX results wrap (outer commas, inline KaTeX) or scroll inside their focusable box; never clipped (e2e checks
360 / 412 / 768 / 1440 px, light and dark).

### 3.5 Learned recipes — `research/recipes.py` (S-AB, keyed by intent since S-AG)

A recipe is one request **intent** (§3.6: « F_125 », « F_{5^3} », « GF(125) » share it) in one tool version, with
every code version written for it and what happened to it (origin catalogue / model / variant / fix, runs OK and
failed, approvals, best run time). The best version is what any later identical request gets, without a model.
Ranking: ran OK > approved > ≥ 30 % faster run > older; a version that only ever failed is never preferred again
(and is shown to the model as « do not repeat »). The S-AB shortcut stays: same template, each old parameter found
exactly once in the code (`F_16` ↔ `GF(16)`), relied-on names defined again → the code with the new parameters,
checked by the preparser, without a model; a close request (word overlap ≥ 0.5) is a proven example for the model.
After a Sage update each recipe is re-checked (preparser + new name index) and dropped when it fails. Local file
`<config>/research/recipes.json` (0600, schema 2; an S-AB file is migrated on first read, `recipes.v1.json` kept);
« ⋯ » (notebook) → « Recettes apprises » lists and deletes them (`GET /api/calcul/recipes`,
`DELETE /api/calcul/recipes/{id}`).

### 3.6 One canonical code per request (S-AG, DECISIONS D39)

**Analysis** (`research/intent.py`, no model, ≈ 1–2 ms): the request (French / English, LaTeX, Unicode) → objects with
canonical parameters, the operation, formulas in one spelling, variables. Examples: `F_125`, `F_{125}`, `F_{5^3}`,
`\mathbb{F}_{125}`, `GF(125)`, `GF(5^3)`, `𝔽₁₂₅`, `F125` → the finite field of order 5³ (`F_12`: « Il n'existe pas
de corps fini à 12 éléments : 12 = 2^2 × 3 … », no code); `Z/12Z`, `ℤ/12ℤ`, `Zmod(12)`; `Q[x]`, `F_7[x,y]`,
`Z[i]`; `Q(√-5)` (`Q(√8)` = `Q(√2)`), `Q(i)`, `Q(ζ_7)`, `Q(∛2)`; `[[1,2],[3,4]]`, `\begin{pmatrix}…`, `M_2(Q)`,
`GL_2(F_7)`; `S_5`, `A_4`, `D_4` (8 elements, Sage's convention), `C_6`; `y^2 = x^3 + x + 1` with « courbe
elliptique », Cremona labels; integers. Operations: factor, roots, irreducibility / list of irreducible polynomials
of a degree, gcd / lcm, integral (definite or not), derivative (order), limit (point, side), sum (bounds), Taylor
(point, order), plot (interval, several functions), solve, simplify, expand, determinant, inverse, eigenvalues /
vectors, rank, kernel, characteristic / minimal polynomial, trace, Jordan form, order, elements, generator, units,
subgroups, conjugacy classes, centre, commutativity, character / Cayley table, class number, discriminant, degree,
ring of integers, Galois group, curve rank / points / number of points / torsion / j-invariant / conductor, primes,
divisors, Euler φ, modular inverse. `POST /api/calcul/analyze {text, language}` shows the analysis.

**Catalogue** (`research/codecat.py`, `GET /api/calcul/catalogue`): one construction per object / operation —
Sage `F125.<a> = GF(5^3)`, `F7 = GF(7)`, `Z12 = Zmod(12)`, `R.<x> = PolynomialRing(F125)`, `K.<a> = QuadraticField(-5)`,
`M = matrix(QQ, …)`, `G = DihedralGroup(4)`, `E = EllipticCurve(F7, [0, 0, 0, 1, 1])`, symbolic variables always
declared (`x = var('x')`); Python with sympy / numpy / matplotlib and explicit sorted imports
(`from sympy import integrate, pi, sin, symbols`; Python covers prime fields only); Lean / Mathlib per version
(`GaloisField 5 3` with `Fact (Nat.Prime 5)`; `Nat.card` on the current Mathlib, `Fintype.card` on Lean 4.9;
`Nat.primeFactorsList` / `Nat.factors`; `∑ i ∈` / `∑ i in`). **Verified**: 55 samples (request → assembly →
assertion on the result) run in the installed Sage 10.10 (3.8 s), 39 in the kernel's Python (sympy 1.14, numpy 2.5,
matplotlib 3.11; 1.1 s), the 21 Lean entries compiled in `lean-current` (Lean 4.36) and `lean-prover49` (Lean 4.9);
built into `<cache>/syntax/codecat-*.json` by the syntax-card hooks; a failing entry is not used.

**Generation** (`research/codegen.py`): the best version of the intent (§3.5) → else the catalogue (fully covered,
no model) → else the S-AB shortcut → else the model, with the catalogue's constructions as a mandatory first lines
(the model's redefinitions of those names are removed), temperature 0 + seed, the pinned model of the language
(`<config>/research/codegen-models.json`: measured run success per model, sticky; the race of §3.1 only when it
fails). Every code is then canonicalized (`research/codefix.py`): imports at the top, deduplicated, ordered; missing
imports (`np`, `plt`, sympy names, `Fraction`…), conventional objects (`F9` → `F9.<a> = GF(3^2)`) and single-line
definitions of earlier cells added. A run error « name '…' is not defined » is fixed the same way before any
model. « Réécrire » returns the best version; « Autre version » (cell menu « ⋯ ») asks the model for a different one
(temperature 0.7, another seed), kept as a version, best only if it ranks higher. Under the request: « Reconnu :
corps fini F₁₂₅ = F_{5³} · anneau de polynômes F₁₂₅[x] · factorisation de x^5 + 4*x - 1 »; the cell head says
« construction vérifiée » (catalogue) or « meilleure version ».

Measured (`scripts/dev/calcul_determinism.py --sage`, 31 typical requests written two ways each, a fake model that
answers differently every time): **31/31 identical** after « Réécrire » and **31/31 identical** across the two
notations; Sage: 29 fully from the catalogue, 2 partial (model with the canonical prefix), 2 model calls in total
(the second asks of those two are the stored best), **31/31 cells ran** in the installed Sage; analysis + assembly
median **2 ms** (max 44 ms), best-version answer 37 ms (preparser check). Python: 22/31 from the catalogue, 31/31
identical.

### 3.7 « Expliquer les étapes du calcul » (S-AJ, DECISIONS D42) — `research/steps.py`

« ⋯ » of a code or request cell whose current code ran successfully → « Expliquer les étapes du calcul »: how the
result is obtained, as a mathematician would do it by hand — 3 to 7 numbered steps in French or English (UI
language), formulas rendered by KaTeX, the last step being the cell's actual result; for what cannot be done by
hand (huge numbers, large systems), the method and its key facts.

**Facts computed by Sage first.** A small table of deterministic *step probes*, keyed by the operation recognized in
the request (§3.6) or else written in the code's last expression (`f.factor()`, `integrate(…)`, `M.det()`, …):

| Operation | Computed / checked by Sage in the cell's kernel |
|---|---|
| factor (polynomial) | degree and ring, base field order and characteristic, each factor's degree and irreducibility, product of the factors == the polynomial |
| factor (integer) | each factor is prime, product == n |
| integrate | an antiderivative F and F' == f; definite: F(b) − F(a) (limits at ±∞) == the result |
| roots | f(r) == 0 for each root, multiplicity, minimal polynomial; number of roots vs degree |
| det | triangular form U (Gaussian elimination with permutation P), det(P) · ∏ diag(U) == det; rank |
| solve | each solution substituted into every equation (== 0); `solve_right/left`: A·x == b and the kernel's dimension (unique or not) |

The probe is Madalean's fixed program (`steps.PROBE`); the cell's code reaches it only as a JSON string, and it
re-evaluates that code in a **copy** of the kernel's namespace (the user's names, `_` and the execution counter are
untouched: run outside the history, `NotebookKernels.probe`). It runs only when the cell itself may run (user code,
or model code approved on this host — the rule of every run, D35), from a device allowed to execute, when the
result is not stale and the notebook is not running; its recomputed value must equal what the cell shows, otherwise
its facts are dropped. The facts are given to the model with the instruction to use them as is and invent no other
intermediate value; they are shown above the derivation with a mark: « vérifié par Sage » (a check passed),
« calculé par Sage » (a value), « non confirmé par Sage » (a check failed: not given to the model). Without facts
(no probe for the operation, Python notebook, model code not approved, another device…) the answer is shown with
« Explication sans vérification » and the reason.

**Fast**: the latency-first short-text path (BRAIN.md §15, `classify.task("transcribe")`, no job slot), streamed into
the cell (`calcul.steps` events), cached per (language, code, output, request, UI language) in memory (200 entries;
a state that may pass — busy, not approved — is not cached). Collapsible, « Copier » (Markdown with the facts),
« Insérer dans l'article » (the send dialog, prefilled). Inline maths starting with a digit is written `${}641$`
(the Markdown renderer reads `$641$` as money).

Limits: probes for Sage cells only (a Python/sympy cell gets the model-only explanation); one probe per cell, on its
last expression; the re-evaluation re-runs the cell's code (≤ 60 s) — a cell with side effects (files, randomness)
may differ and then loses its facts.

### 3.8 « Certifier avec Lean » (S-AT, DECISIONS D52) — `madalean/certs/fromcalcul.py`

A Sage result is a computation, not a proof. For the cells whose result has a certificate — `factor(n)`,
`is_prime(n)`, `next_prime`, `gcd`, `lcm`, `xgcd`, `power_mod`, `inverse_mod`, `factorial`, `binomial`, an integer
expression — the cell menu offers « Certifier avec Lean »: the cell's text and its stored result become a Lean
statement (nothing is executed again; integer expressions only, names assigned on earlier lines of the same cell are
substituted), Sage computes the witness that statement needs (a Pratt certificate for a prime, a divisor…) and a
fresh strict Lean checks the proof. On success a dossier is created in the project with the statement and the proof,
and the panel under the cell shows the witness, the size of the proof, the two times and « Ouvrir le dossier ». A
refusal by Lean, a missing witness or an unsupported cell is said in plain words; nothing is ever shown as certified
without Lean. Route `POST /api/certificates/dossier` (docs/API.md §6g), same permission as a run. Everything else
about certificates: docs/CERTIFICATES.md.

## 4. Outputs

LaTeX (KaTeX; for Sage results Madalean adds `text/latex` from `latex(_)` so JupyterLab shows it too), plots as
PNG/SVG, Sage `Graphics` (2D as PNG; 3D through Tachyon as a static PNG — the three.js viewer is HTML+JS and is never
kept), graph-theory objects drawn by Sage with its layout (and interactively with `fig(G)`), matrices and tables as
LaTeX/text, `fig(...)` figures (mime `application/vnd.madalean.figure+json`) drawn by the interactive figure engine.
**Exact ↔ approché**: for a result with a decimal value (`N(_)`, 15 digits), a toggle shows `≈ 4.44288293815837`
instead of `\sqrt{2}\pi` (Fikajiana's « ≈ » rule).

## 5. Graphs and geometry — what comes from Fikajiana

Fikajiana (`~/GitHub/Fikajiana`, the user's own Flutter app, GPL-3.0) was studied without its handwriting part.
Madalean is Apache-2.0: ideas, behaviour and vocabulary are reused, the TypeScript is written afresh.

| Fikajiana | Madalean |
|---|---|
| Graphe: explicit `y=f(x)` with adaptive sampling and asymptote breaks (ADR 0005) | `lib/figure/curves.ts`, same behaviour; or Sage `plot` |
| Implicit `x^2+y^2=4` by marching squares (ADR 0020) | marching squares refined by bisection; or Sage `implicit_plot` |
| Parametric `(cos t, sin t)`, `t ∈ [-10,10]` default; polar `r=1+cos θ`, `θ ∈ [0,4π]` | same syntax and defaults |
| Sequences (u(n)) | `u(n)=…` drawn as points |
| Several curves, legend, value table (21 rows, ADR 0056) | several curves per figure, value table per curve |
| Pan / zoom / pinch, point reading | drag, wheel, two-finger pinch, double-click reset; tooltip + live region |
| ~40 named geometry tools in 9 groups (ADR 0019): points, milieu, intersection, centre, centre de gravité, segment, droite, demi-droite, vecteur, parallèle, perpendiculaire, médiatrice, bissectrice, tangente, cercles (3 kinds), arcs, demi-cercle, polygone (régulier), ellipse, hyperbole, parabole, conique par 5 points, symétries, translation, rotation, homothétie, longueur, angle, aire, pente, curseur, lieu, relation | the same tools and groups (`lib/figure/tools.ts`, `geometry.ts`); not taken: hand drawing (`mainLevee`) |
| Dependent constructions: moving a point updates the figure | dependency graph recomputed in order; undefined objects hidden |
| « Relation »: what is true here, then 24 random deformations — a hint, not a proof | same, with the same wording |
| Exact vs approximate, `≈` (ADR 0034) | `lib/figure/exact.ts` (√2, π/4…) + the exact/approché toggle on Sage results |
| Exact checks with Giac (ADR 0025/0046) | « Envoyer à Sage » (`toSage`): free points as rationals, constructions as exact Sage formulas, a new code cell |
| History (undo / redo), several documents (Classeur) | undo/redo in the figure; several notebooks per project |
| Export PNG / PDF (ADR 0022) | PNG, SVG, TikZ (plain TikZ, compiled with pdflatex in the tests) |

**Library choice**: an own engine (≈ 2 400 lines TS/Svelte, lazy chunk ≈ 34 KB, 12 KB gzip) rather than JSXGraph
(MIT/LGPL, ≈ 900 KB, uses `new Function` through JessieCode — at odds with the CSP), GeoGebra (EUPL + non-commercial
terms) or Desmos (proprietary). No `eval`, self-hosted, offline, SVG rendering with a text description of the
figure, keyboard moves (arrows, Shift = fine), AA in light and dark (axe 0).

Two-way bridge with Sage: `fig(expr | equation | points | Graph, …)` in a cell draws Sage objects in an interactive
figure (it can become a Figure cell); a Figure cell's « Envoyer à Sage » writes exact Sage code in a new cell.

## 6. Connections (everything goes to Publier)

From any cell (menu « … »): **Créer une conjecture** (code + output as motivation), **Créer un dossier Lean**
(statement prefilled from the computed fact), **Ajouter à une note**, **Insérer dans l'article** — a figure becomes
a `figure` environment over a content-addressed PNG in the article's LaTeX project (docs/ARTICLE.md §4), a
computation becomes its result (formula or verbatim output) with a reference to its code, placed in a
« Calculs (SageMath) » section at the end of the article — and **Publier**: `notebook.publication_computations`
produces the `computations` section of `publication.json` (docs/SITE.md §4).

```python
from madalean.research.notebook import publication_computations
comp = publication_computations(wb.calc, pid, DIR / "files")    # wb = app[workbench.WB]; None if nothing
if comp: publication["computations"] = comp
```
It copies each `.ipynb` to `files/calcul/<doc>.ipynb` and each image once to `files/calcul/<sha>.png|svg`.
Wired in `publish.plan` (S-W): the plan route passes the workbench store; the Publier screen has « Joindre les
calculs » (on by default). The site renders it as `computations.html` (docs/SITE.md §4).

Kernel problems in a cell (S-W): an error output whose `ename` is `unavailable` / `died` (kernel could not start,
stopped, or `kernel_unavailable: no sage kernel`) is shown as one sentence (« Le noyau Sage n'a pas pu démarrer. »,
« SageMath n'est pas installé. ») with « Redémarrer le noyau » (restart, then run the cell again) or « Installer
SageMath » (POST /api/deps/sage/install, progress from GET /api/deps, then the cell is run again); the raw log stays
under « Détails » (`web/src/lib/calcul/kernel.ts`).

## 7. HTTP API

See the docstring of `madalean/server/plugins/workbench.py` (routes `/api/calcul/{pid}/docs…`). Events:
`calcul.updated {project_id, doc, cell|run|order|removed…}`, `calcul.running`, `calcul.output` (streamed text),
`calcul.docs`, `calcul.attachments {project_id, attachment}`. Attachments: `GET /api/calcul/{pid}/attachments?cell=`,
`POST` (multipart `file` + `cell`, or `{url, cell}`) → `201 {attachment, read}`, `DELETE …/{n}?cell=` (unlink the
cell; the Source stays), `POST …/{n}/reread`.

## 8. Keyboard (JupyterLab-like)

Command mode (Esc): ↑/↓ or K/J move, Enter edits, A/B insert above/below, M text, Y code, D D delete, Z undo delete,
O fold the output. Edit mode: Shift+Enter run and go to the next cell (a new one at the end), Ctrl+Enter run.
Phone: one column, run buttons ≥ 44 px, toolbar not sticky.

## 9. Limits

- If both JupyterLab and Madalean edit the same notebook at the same moment, JupyterLab shows its « file changed
  on disk » dialog on its next save; Madalean always re-reads the file before changing it.
- 3D: static image only (no interactive 3D viewer yet).
- The article's « Calculs » section is a normal section (not `\appendix`) so that it works with every template.
- Conic ∩ conic intersections and loci of loci are not computed by the figure engine (Sage does it exactly).

## 10. The kernel's home, the smoke suite and the health self-test (S-AC)

**Root cause of the 2026-11-22 failure.** The sandboxed kernel had `HOME=/nonexistent` (kept short because Sage's
GAP probe breaks on a long home) and a read-only file system outside the experiments directory. Every library that
writes under `HOME` without asking therefore failed, one at a time: Maxima (used by `integral`, `limit`, `sum`)
could not create its cache (« OSError: Read-only file system: '/nonexistent' »), and the half-initialised Maxima
interface then made the next symbolic calls (`var('n')`) fail with a `SystemError` cascade. Setting
`MAXIMA_USERDIR` fixed only Maxima.

**Fix at the root** (`sagebridge.launcher_env / bwrap_argv / prepare_home`). Every kernel gets a real home:
`HOME=/tmp/h` inside bubblewrap, a bind of `<experiments>/.home/<key>` (`p-<project>` for a Calcul notebook — from
Jupyter's `JPY_SESSION_NAME` —, `shared` for conjecture experiments). It is writable, private (0700, never the
user's home, empty of the user's files), persistent (caches survive restarts: the first Fourier cell of a
new kernel takes 0.9 s instead of 8.1 s once Maxima's cache exists) and short (GAP: `<HOME>/.gap/` must
stay under ~78 characters; `GAP_HOME_MAX = 64`, tested against the real `gap`). `TMPDIR`, all XDG directories,
`DOT_SAGE`, `MAXIMA_USERDIR`, `MAXIMA_TEMPDIR`, `IPYTHONDIR`, `MPLCONFIGDIR`, `NUMBA_CACHE_DIR`, `CYTHON_CACHE_DIR`,
`PYTHONUSERBASE`, `PIP_CACHE_DIR`, `TEXMFVAR`, `TEXMFCONFIG` point inside it. `PYTHONPYCACHEPREFIX` is deliberately
not set: Python would ignore the system `__pycache__` and recompile Sage at each start (`import sage.all` 0.9 s →
3.0 s, measured). Without bubblewrap (rlimits only) the kernel uses the same directory, through a short symlink in a
private `/tmp/madalean-<uid>/` when the real path is too long. In that mode the launcher also stays the kernel's
parent and kills what the kernel leaves in its process group at exit (a Sage pexpect helper could deadlock and
survive; found by the smoke suite). The kernel's IPC sockets use paths relative to the
experiments directory (the 107-byte unix socket limit killed kernels in long directories). Lean and TeX follow the
same principle: a private writable `HOME` with its XDG directories (`/tmp/home` on the sandbox's own tmpfs).

**Clear French messages.** An IPython startup file (`sagebridge.STARTUP_PY`, rewritten at every start) appends one
sentence « Madalean : … » to tracebacks caused by the sandbox: no network, writing outside the working directory,
memory or file-size limit, a Python module missing from the system (e.g. `cython()` needs `python-pkgconfig`,
absent on this Arch host). The original `ename: evalue` is kept.

**Smoke suite** (`madalean/research/sagesmoke.py`, `tests/test_sage_smoke.py`, marker `sage`, runs whenever Sage
and JupyterLab are installed). One real sandboxed kernel, one cell per item: home, GAP probe, `var`, Fourier
coefficients with `assume` + `integral`, `integrate`, `limit`, `sum`/`hold`, `taylor`/`series`, `solve`,
`simplify_full`, `diff`, `laplace`/`inverse_laplace`, Maxima, GAP (libgap and pexpect), PARI (+ gp), number fields,
Singular (Gröbner), FLINT/NTL, linear algebra over QQ/GF(p)/RR/RDF, numerics (`find_root`, `numerical_integral`,
scipy, numpy), 2D plots (PNG + SVG), 3D (Tachyon PNG), implicit/parametric plots, `show()` (image/png output),
`latex()`, ipywidgets, randomness, matplotlib, sympy ↔ Sage, `cython()` (or its clear message), files in the
working directory, multiprocessing + `@parallel`, and three items that must fail with the French message (network,
read-only file system, memory). The Python kernel runs its own subset; the rlimits-only mode runs the fast subset.

**Health self-test** (`madalean/update_checkers/selftest.py`). Réglages › Système › État de santé shows
« Auto-test SageMath / Python / Lean / LaTeX »: the `fast` items in a fresh Sage and Python kernel, a tiny Lean file
plus a probe of the Lean sandbox (writable private home, only `lo`, the user's home absent), a tiny LaTeX document
plus the same probe in the TeX sandbox. It runs by itself when the tools' fingerprint changes (Madalean version,
kernelspecs, the Sage library, the prefix's component versions, Lean toolchain, tectonic): checked at start (after
3 minutes), every 30 minutes, at each pass of the update checkers (« Auto-test » checker) and after each applied
update. A failure shows the failed items and a toast; « Réparer » moves the kernels' homes aside (`.home.old`,
caches rebuilt) and runs the test again; « Relancer le test » re-runs it. Report: `<config>/selftest.json`; event
`system.selftest`.

## 11. Kernel ready in advance (S-AO, TODO B15, DECISIONS D47) — `nbkernels.py`, `sagebridge.py`

**When.** `GET /api/calcul/{pid}/docs/{doc}` of a document whose kernel is not running, and
`POST /api/calcul/{pid}/warm {doc?}` (sent by the project page; the project's most recently changed document, never
a new one) call `NotebookKernels.prewarm`: a background task starts (or attaches to) the document's kernel exactly as
the first run would (same session, same sandbox, same private home, same preamble). Only when the setting
`calcul_warm` is on (host-only, « Réglages › Carnet »), not in the demo, only for a device allowed to run cells
(the host, or `experiments_remote`), only when the kernel is installed. `status.warm` of the document view says
`starting | warming | ready | failed | skipped | off`, with the start time and each step's time.

**Warm-up.** In a fresh session (never in a session JupyterLab opened, where user code may have run) Madalean runs
three fixed programs, each its own execution, outside the history (`store_history=False`: no `_`, no execution
count, no output in the notebook; everything inside a function deleted afterwards, no name left): `integral`
(`integrate`, a definite integral, a `limit`, `latex`), `plot` (a 2D plot rendered to PNG in memory), `finite_field`
(a factorisation over GF(3⁴), an integer factorisation). The Python kernel only builds matplotlib's font cache.
**The user always wins**: any run, probe or restart of the document marks it used; the warm-up stops after its
current step (a user's run waits at most for that step).

**Caches prepared once per Sage version.** The first integral of a new project took ≈ 8 s because each project has
its own home (D36) and Maxima compiled its `linearalgebra` share package there. A warm-up that ran undisturbed in a
fresh kernel copies what it just created (files modified since it started, matching `sagebridge.SEED_PATTERNS`:
`.sage/maxima/binary/…`, `.sage/maxima/test-directory-cached/…`, Sage's lazy-import cache, matplotlib's
`fontlist-v*.json`; regular files only, no symlink, ≤ 64 MB) into `<experiments>/.home/.seed/` and writes
`.done-<Sage version>`. At every kernel start the launcher copies into the home what it lacks from the seed
(`seed_home`, before the kernel starts; the names carry their own Maxima / ECL / matplotlib versions, so a copy is
never used by another version). If the user ran a cell first (or the home already had its caches), the seed is
prepared once aside by a kernel that only ever runs the warm-up (`calcul/.seed/seed.ipynb`, home `warm-seed`), then
stopped. The setting off: no seed copy either (`launcher.json` `seed: false`).

**Memory.** Nothing beyond the kernel the document would start anyway: at most `WARM_MAX_UNUSED` = 2 kernels started
in advance and not used yet (the oldest is stopped beyond that), never when the machine has less than 1.5 GB
available (`/proc/meminfo`), idle stop unchanged (`calcul_idle_minutes`, counted from the warm-up). Health row
« Calcul prêt d'avance » (off / preparing / n kernels ready and the last preparation time / a failed step / memory).

**Measured** (Sage 10.10, this machine, sandboxed, `scripts/dev/bench_calcul_first_run.py`; seconds from « run » to
the answer; « ready in advance » = the document was open long enough for the warm-up: 14 s for a new project, 4–5 s
otherwise):

| first … | new project, before | new project, ready in advance | reopened project, before | after | another new project, before | after |
|---|---|---|---|---|---|---|
| cell `1 + 1` | 4.18 | **0.11** | 2.70 | **0.11** | 2.81 | **0.11** |
| integral `integrate(x*sin(x), x)` | 8.32 | **0.11** | 1.04 | **0.11** | 8.72 | **0.11** |
| plot `plot(sin(x), (x, 0, 2*pi))` | 1.16 | **0.16** | 0.52 | **0.16** | 1.22 | **0.18** |
| factorisation over GF(3⁴)[y] | 0.17 | **0.11** | 0.17 | **0.11** | 0.17 | **0.12** |

Running at once after opening (`--warm --now`): no regression (4.18 / 8.56 / 1.29 / 0.18 s in a new project), and
the seed prepared aside makes the next new project's first integral 1.06 s instead of 8.7 s even without waiting.

## 12. Explorations of the conjecture engine (S-AW, DECISIONS D55)

The « Moteur de conjectures » (docs/CONJECTURES.md) stores each experiment as a cell of a notebook of the project,
« Explorations (conjectures) » (`explorations.ipynb`; `explorations-python.ipynb` for Python): a title cell, then
the experiment, whose output is the table. Nothing is special about it — same kernel and sandbox, same approval of
model code by hash (`may_run`), same warm start (§11), same file in JupyterLab — except three names every
experiment defines (`cj_columns`, `cj_index`, `cj_rows_for`), which the engine's fixed driver reads outside the
history, like the step probes of §3.7. Catalogue experiments are written from the parsed request without a model
(the sequence counterpart of §3.6) and are ordinary cells; an unrecognised request is written by a model and waits
for « Approuver et exécuter ».
