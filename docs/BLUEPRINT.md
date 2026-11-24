# From a paper to a formal plan (TODO « Stratégie 2.1 » item 6, DECISIONS D60, session S-BB)

The Blueprint screen already reads a paper (RESEARCH_SOURCES.md §6: `papers.extract`, TeX first, PDF text layer
otherwise) into nodes with numbers, labels, proofs and dependency edges. This layer turns that blueprint into a
**formal plan**: Lean statements, a Mathlib check, a problem graph with sub-dossiers, honest statuses, exports.
Code: `madalean/research/paperplan.py` (pure functions + `PlanRun`), routes in
`madalean/server/plugins/research_sources.py`, UI: the « Plan formel » tab of `web/src/screens/research/Blueprint.svelte`.

## 1. Structure (deterministic)

- **TeX** (`fulltext.parse_tex`): theorem-like environments declared by the paper, LaTeX numbering emulated, labels,
  `\ref`/`\cref`/`\eqref` in proofs (`via: proof_ref`) and statements (`statement_ref`, *proposed*), `\cite` keys,
  `\begin{proof}[Proof of Theorem~\ref{x}]` and « Proof of Theorem \ref{x} » *sections* attached to their result.
  New in D60: each node keeps `verbatim` (the statement as written in the source, comments removed, macros **not**
  expanded) and `line` (its line in the main TeX file; 0 when it comes from an `\input` file).
- **PDF**: text-layer heuristics (« Theorem 2.1. », « Proof. » … « □ », « by Lemma 2.3 » → `text_ref`); `verbatim`
  is the text layer as read, located by page. OCR'd PDFs are marked `quality: low`.
- **A model** may only propose `uses` edges between existing nodes (`via: model`, `proposed: true`); it never writes
  a statement. The formal plan follows a proposed edge only once the user accepted it.

## 2. Dependency closure

`closure(bp, selected)`: the selected nodes and everything they use transitively through explicit edges (and
accepted proposed ones), dependencies first, paper order otherwise; cycles are cut. `mains(bp, selected)`: the
selected nodes no other selected node uses — one top-level dossier each. Unknown dependencies stay unknown.

## 3. A run (`PlanRun`, budgeted, resumable)

For each node of the closure that has no final record (`needs_work`), dependencies first:

1. **Statement**: `pipeline.goedel.Formalizer` on the verbatim statement plus the verbatim definitions it uses and its
   place (« Result quoted verbatim from the paper … State exactly this result »), `tries` attempts with Lean's errors
   fed back, Lean check of the statement (the D39/D45 catalogue is the formalizer's own). The theorem is renamed
   `paper_<label>`. Texts that address a model (`literature.quotes.suspect`) are never sent.
2. **Mathlib first**: `literature.formal.mathlib_status` (D56) without a model: the user's library (same statement
   key) → `proved`; a Mathlib name closing it under the strict verdict (templates on the index candidates, then
   `exact?`) → `in_mathlib`; else `to_prove`.
3. The record `node.formal = {status, lean, name, compiled, mathlib_name, library_name, model, note, dossier_id,
   graph}` is saved at once (merged into the current blueprint file, so edges curated meanwhile survive).

Models: free ones only (never a paid model); in Local mode the local models translate, since the user started the
run. Budget per run (`PlanBudget`): `statements` (1–40, default 6), `seconds` (default 900), `tries` (1–3, default
2), counted model calls and Lean checks; « Arrêter » stops after the current statement. Final notes (definition,
suspect text, Lean refused, no statement) are not retried; `budget`, `no_model`, `error` are.

**Problem graph** (only when the whole closure has been processed): for each main result, a top-level dossier
(kind theorem, statement = its Lean statement when it compiled, `source.original_text` = verbatim, never started);
in its graph (D57, through `GraphService.ensure / save / open_node / publish` and `proofgraph.new_node / add_node /
add_edge`) one node per result of the closure with the paper's edges: `mathlib` nodes (verified), `library`
(proved), and `cited` nodes with `source.kind: paper` and `claimed: proved|stated` for the rest — conditional until
Lean proves them. Each formalised `to_prove` node is opened as a **sub-dossier** (D57b), whose verdict rolls up
through the graph service. A second run is idempotent (no new dossier, no model call).

## 4. Statuses and view

`plan_status`: per node `proved` (a dossier of the node has a strict proof, or the library proves it) · `in_mathlib`
· `to_prove` (formalised, a dossier exists) · `formalised` (Lean statement, no dossier yet) · `unformalised`; plus
`rests_on` (results of its closure not proved nor in Mathlib: « conditionnel ») and `progress` over the plan's
closure. The UI tab shows the counter, the legend, the graph or list coloured by status, and per node the verbatim
statement with its place beside the Lean statement (« traduction à relire »), the Mathlib name, the dossier.

## 5. API (`/api/research/projects/{pid}/blueprints/{sid}/…`)

| Route | |
|---|---|
| `POST …/plan` `{nodes: [ids], statements?, seconds?, tries?, mode?, dossiers?: true}` | `202 {run, order}`; 400 on unknown nodes; 409 `busy` while a run of this blueprint is active. Publishes `blueprint.updated` after each node |
| `GET …/plan` | `{nodes: {id: {status, rests_on, deps, lean, compiled, name, dossier_id, note, mathlib_name, library_name, model, location, verbatim, tried}}, progress, plan: {selected, order, mains, tops, runs}, run}` |
| `POST …/plan/stop` | stops after the current statement |
| `GET …/export?format=tex\|html&lang=fr\|en` | blueprint-style LaTeX (`\lean`, `\leanok`, `\mathlibok`, `\uses`, verbatim statements, Lean statements in `verbatim`; macros defined as no-ops when `leanblueprint` is absent) or a self-contained HTML page (no script, everything escaped) |

## 6. Cut in this version

Definitions are not formalised (honestly « non formalisé »); no model classification of ambiguous PDF blocks (the
existing heuristics only); no automatic launch of provers (the user starts the dossiers); one top-level dossier per
main result (a lemma shared by two mains gets one sub-dossier in each family); the PDF line number (page only); the
arXiv e-print path is tested on our own fixture paper — the real answer recorded once (arXiv:1907.00847, 2026-11-24)
is not redistributed, its structure is in `tests/data/paperplan/arxiv-1907.00847.json` and re-checked when
`MADALEAN_ARXIV_EPRINT` points to a local copy.

## 7. Tests

`tests/test_paperplan.py`: structure of a small TeX paper (numbers, labels, verbatim text located by line), exact
dependency graph (proof environment, a proof citing two lemmas, a « Proof of Theorem » section, nothing invented,
proposed edge followed only once accepted, cycles), PDF verbatim, exports; the run with a fake model and the **real
Lean** (lean-prover49): budget of 2 then resume, `in_mathlib` by `exact?`, top-level dossier + sub-dossier,
conditional until a real Lean proof of the lemma rolls up, idempotent third run, exports; the arXiv e-print path.
`web/e2e/paper-plan.spec.ts`: the tab on the demo paper (statuses, counter, verbatim beside Lean, closure count,
exports, axe).
