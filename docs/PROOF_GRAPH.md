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
  the dossier's shared context ignored). Identity holds inside one top-level dossier and workspace; a statement with
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
combination, equivalence probes against the parent) and probed for counterexamples (Lean tries the negation; a
closed probe is re-checked strictly) — a refuted lemma gets a `refutes` edge from its counterexample. A dead lemma
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

Statement identity is syntactic (binder names matter: `(n : ℕ)` and `(k : ℕ)` give different keys). Counterexample
probes use automatic tactics and degenerate values only. The deterministic rename is applied in the graph's own
attempts; in the main pipeline a lesson reaches the model as a hint and as Lean feedback (the pipeline's proof is
never rewritten behind its back). Explanations are templated text (FR / EN), not prose.
