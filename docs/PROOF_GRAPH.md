# The problem graph (« graphe de lemmes raisonné ») — session S-AY, DECISIONS D57 / D57b

Code: `madalean/research/proofgraph.py` (pure model, explanations), `madalean/research/graphsearch.py` (reasoned
search, Lean operations, service), `madalean/research/lessons.py` (learning from mistakes),
`madalean/research/literature_iface.py` (the interface expected from S-AX), `madalean/pipeline/memory_hook.py` (what
the provers are told). UI: `web/src/screens/dossier/ProblemGraph.svelte` (« Plan » tab, « Graphe » view),
`web/src/screens/settings/Lessons.svelte`. API: docs/API.md §6j. Manual: `docs/manual/{fr,en}/proof-graph.md`.

## 1. Model and storage

One graph per dossier, stored in the dossier's proof-plan file (`<config>/research/plans/<id>.json`, key `graph`):
it extends the plan (S-L) instead of living beside it. The plan stays the user's editable tree of tracks; the graph
is the memory of the problem. `GraphService.ensure` creates it from the dossier on first use and brings the plan in
(`sync_from_plan`, idempotent, keyed by plan node id: lemmas, « uses » edges of the active track, abandoned tracks
with their reason, holes → admitted).

- **Nodes**: `kind` goal | lemma | mathlib | certificate | cited | library | proposal; `status` proved | mathlib |
  certified | cited | open | refuted | abandoned (with `reason` and, when closed, the environment and the set of
  verified lemmas at that time); `viability` (score, signals, the model's opinion labelled); `attempts` (≤ 6 kept,
  counters for the rest); `proof`, `tactics`; `source` (planner, search, mathlib, certificate, counterexample,
  literature, provided, attachment, library, method, user); `citation` (CSL-JSON + verified, quote, locator);
  `dossier_id` when opened as a sub-dossier.
- **Edges** `[src, kind, dst]`: uses · generalises · special_case · refutes. A « uses » edge that would close a
  cycle is refused and logged. The graph is a **DAG**: a sub-lemma used by two lemmas is one node.
- **Identity**: `statement_key` = hash of the last theorem's binders and type (name, comments, spacing, header and
  the dossier's shared context ignored) **up to the names of bound variables and hypotheses** (D59, `alpha_normal`:
  each bound name — binder groups, `∀ ∃ fun ∑ ∏ …` inside the type — is replaced by its rank of first binding;
  `n.succ` follows `n`, `Nat.succ` stays). `(n : ℕ) (hn : 0 < n)` and `(k : ℕ) (h : 0 < k)` are one node; another
  hypothesis, or the same binders in another order or grouping, stay apart (alpha-equivalence only). The wording
  as written is `exact` (`exact_key`); a second wording merged into a node is kept in `aliases` and, in a
  combination, declared as `theorem alias SIG := original` (the types are equal, so Lean accepts it). When a new
  lemma's key collides with a node of another wording, the search asks Lean once (`same_statement_code`:
  `theorem madalean_alpha_eq : (∀ …, A) = (∀ …, B) := rfl` with the axiom probe); a refusal keeps them apart
  (`alpha_refused` in the log). Migration v1 → v2 (`migrate`, on load): keys recomputed, exact alpha-duplicates
  merged into the one with the best status (the goal first), edges redirected, attempts / sources / errors folded
  in, the merge logged (`merged_alpha`); two nodes one of which uses the other are never merged. Identity holds inside one top-level dossier and workspace; a statement with
  another hypothesis is another node. A lemma of another dossier of the project is offered for reuse (viability
  signal, digest, through the library with its own Lean proof), never merged silently.
- **Versioned and compact**: every change bumps `rev` and appends to a bounded log (200); ≤ 120 nodes (closed
  unused leaves dropped first, their key and reason kept in `forgotten`); ≤ 10 run summaries.

## 2. Status the user sees (`effective`)

verified (mathlib, certified, or proved with a self-contained Lean proof) · conditional (cited / provided / admitted
hole, or proved with lemmas stated with `sorry` while one of them is not verified — `rests_on` lists them; a
sub-dossier whose own graph is conditional rolls up as conditional) · open · refuted · abandoned. A proof whose lemmas
all become verified is « vérifiée par composition » (`composed`): each part was checked by Lean against the same
statement. A source's own claim (« proved », « in Mathlib ») is kept as `claimed`, never as a status.

## 3. Reasoned search (`ReasonedSearch`)

Loop: pick the best action among live open nodes (reachable from the goal by « uses ») — finish a node whose lemmas
are done (combination), attempt a node, or expand it — by expected value per cost (`score / (1 + attempts +
depth/2)`). Before an expansion and for each new lemma: **viability** = deterministic signals (known in the graph /
library, proved in another dossier, failed before and nothing changed, similar to a failed node, repeated Lean
error, cycle, depth, cited) + one short model opinion (`graph_viability_model`, labelled, 0.4 weight); below 0.15 the
lemma is abandoned with the written reason. New lemmas are gated by ONE Lean compile (statements with `sorry`, the
combination, equivalence probes against the parent) and probed for counterexamples — first **on small instances**
(D59, `research/smallprobe.py`): when the statement is decidable there (number variables over ℕ / ℤ, polynomial
relations over ℚ / ℝ in ≤ 4 variables, read by the certificates' reader and evaluated by their exact evaluator, the
same Lean conventions as the `finite` / `counterexample` kinds — no model-written code), a box of small values
(ℕ 0..12, ℤ −12..12, 13 small rationals + 400 seeded random ones; hypotheses checked first) is evaluated within
`SMALL_PROBE_SECONDS` (2 s per lemma, cancelled by « Arrêter »). A violating point is only a candidate: it becomes a
Lean proof of the negation (`intro h; have := h 4 (by …); norm_num at this`) checked strictly with the other
negation probes (automatic tactics, degenerate values). A refuted lemma gets a `refutes` edge from its
counterexample, the witness recorded (`witness`, `probe.confirmed`); nothing found adds the evidence « testé sur
n ∈ 0..12 (13) » to the node (`tested`) and to its viability (+0.05 when the box was covered). A dead lemma
that the recorded combination does not use is dropped; otherwise the track is kept as abandoned with the reason and
the node may be split again.

Attempts (`LeanOps.attempt`): the recorded combination (no model) → cheap closers → a certificate (S-AT) → one model
proof with the memory digest; every proof is judged by the strict verdict, or by the conditional check when the node
uses admitted / cited lemmas. A solved goal is stored as the dossier's proof through the planner's strict path.

**Guards**: depth, new nodes, attempts per run and per branch, expansions per node, attempts per node (3, fewer when
the same Lean error repeats), wall time, tokens, USD (`graph_search_usd`, never above `conductor_cap_usd`, enforced
by the spend ledger with the run's own scope), no-progress (6 steps without a new node, a new verified node or a
refutation). Stop reasons: solved, conditional, exhausted, no_progress, stopped, budget_*. Abandoned nodes are not
reopened in a later run unless the Lean / Mathlib version changed or a new lemma was verified.

**Drawn view (D59)**: beside the list (which stays the reference, and the only view on phones), « Dessin » draws
the DAG (`web/src/lib/graph/dag.ts`: longest-path layers from the goal, barycentre ordering; `GraphMap.svelte`,
lazy-loaded, no new dependency). Status = colour + shape + words (verified square box, conditional dashed, open
pill, refuted double border, abandoned dotted and struck through); pan (drag, arrow buttons), zoom (wheel, + / −);
nodes are buttons in the list order (Tab), Enter opens the same detail panel.

## 4. Problem memory and the provers

`memory_hook.memory_hint` appends to the provers' hint (pipeline, after the conductor's advice): the graph digest —
« Cible / Target », then « Connu / Known » (proved; cited / provided, NOT proved), « À prouver / To prove », failed
approaches with reasons, refuted statements, tactics that worked, Lean errors already seen — then the lessons. Both
are bounded (≈ 600 + 250 tokens), deterministic (sorted: same memory, same bytes) and empty when nothing is known
(a fresh dossier's prompts are unchanged). Finished jobs are recorded on the dossier's node (proof, strategy, Mathlib
lemma, certificate; or the failure with its first Lean error).

## 5. Explanations

`explain(graph, node, lang)` builds a structured account from recorded facts only — path chosen and why (planner's
`why`, recorded viability reasons), alternatives, lemmas and states, tactics found in the recorded proofs with a fixed
glossary, failures with reasons, bibliography (Mathlib constants written in the proofs with documentation links,
cited works with their recorded references and BibTeX via `biblio.item_to_bibtex`). No model writes it; a test checks
that no lemma or tactic outside the record is mentioned. Exports: Markdown note, LaTeX with `\cite{key}` + BibTeX.
Goal states per tactic: the existing D45 « Expliquer ligne par ligne » on the proof.

## 6. Sub-dossiers

« Ouvrir comme sous-dossier » creates a dossier with `parent_id` (the existing field: no second concept), `kind`
lemma, `extra.graph = {graph_dossier, node}`. Depth bounded by `plan_max_depth` along the parent chain. A statement
already opened in the same top-level family and workspace is reused: the dossier stays under its first parent and
lists other users in `extra.graph_also`; the UI says « utilisé aussi par ». Roll-up goes to every user, up the chains
(bounded, cycle-safe). Archive / move / delete of a parent applies to its sub-dossiers; restore brings them back.
Breadcrumb « Projet › Dossier › Lemme » in the context switcher; sub-dossiers folded under their parent in lists.

## 7. Lessons (D57b)

`<config>/research/lessons.json`, ≤ 400 lessons, keyed by normalised signatures, never by model: rename (unknown
Mathlib name → the name the verified proof used, per Mathlib version), fix (normalised Lean error + statement shape →
tactics the verified proof added), approach (shape → why it failed), strategy (shape → what worked). Learned only from
verified successes (finished jobs, graph attempts) or recorded failure reasons. Used: `hint()` in the provers' prompt
(cheap shape / domain / token match, stable order), `error_hint()` in the agent's Lean feedback, `apply_renames()`
without a model in the graph's attempts (Lean re-checks; the lesson's counters follow). Hygiene: evidence (dossier,
date, workspace, Lean, Mathlib), ok / bad counters, dropped when useless or stale, import accepts only plain
identifiers for renames. Measured (tests/test_proofgraph_lean.py): the same wrong name on a second statement costs 1
model proof instead of 2.

## 8. The literature (S-AX)

`research/literature_iface.py` adapts S-AX's API (docs/LITERATURE.md §6): `search` runs `literature.search` (quick
budget, no request in Local mode) and `provided` reads the dossier's attachment digests (`attach.provided_items`).
Each `LiteratureItem` becomes `{title (label — title), statement_nl (verbatim quote), lean, status (S-AX's claim:
in_mathlib | proved | to_prove | unformalized), origin (literature | attachment), mathlib_name, citation (the
retrieved CSL record + verified, quote, locator, key)}`; `cited_node` keeps the claim as `claimed` — the node stays
« cité » (conditional) until Lean proves it. Provided results are placed as known nodes when the graph is created
and whenever the dossier's attachments change (« comprendre d'abord »: target apart from the known results).
« Littérature » (`POST …/graph/literature`) adds both; `POST …/graph/cited` takes plain items of the same shape.

## 9. Limits

Statement identity is alpha-equivalence of the written signature (D59): `(n k : ℕ)` and `(n : ℕ) (k : ℕ)`, a
reordering of independent binders, or definitionally equal statements stay distinct nodes; a name used both bound
and free in one statement could make the syntactic key too coarse, which is why a collision is confirmed by Lean in
the search (the migration of stored graphs merges on the syntactic key alone). Small-instance probes cover ℕ / ℤ /
ℚ / ℝ arithmetic only (no functions, sets, sqrt / exp in variables); they run in Python (the certificates' exact
evaluator), not in Sage — Sage is not needed to evaluate a polynomial on a few thousand points. The deterministic rename is applied in the graph's own
attempts; in the main pipeline a lesson reaches the model as a hint and as Lean feedback (the pipeline's proof is
never rewritten behind its back). Explanations are templated text (FR / EN), not prose.
