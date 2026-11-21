# Calcul — the Sage notebook of Madalean (session S-P)

« Calcul » is a real notebook: a sequence of cells that share one kernel state, like JupyterLab, connected to the
whole research flow (conjectures, Lean dossiers, notes, article, « Publier »). **One engine** computes and plots
everything: SageMath (or Python for a Python document). **One file**: a standard `.ipynb` that JupyterLab opens.
**One kernel** per document, shared with JupyterLab. Code: `madalean/research/notebook.py` (documents, cells,
outputs, publication producer), `madalean/research/nbkernels.py` (kernels), `madalean/server/plugins/workbench.py`
(HTTP API), `web/src/screens/research/Calcul.svelte`, `web/src/lib/figure/**` + `web/src/components/figure/`
(interactive figures). Tests: `tests/test_calcul_notebook.py`, `tests/test_workbench.py`,
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
- Opening the screen starts nothing; the first run starts the kernel. Kernels stay warm (user decision) and stop
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
when no kernel runs or the device may not execute) and the cells above with cut outputs, and returns one code cell.
The code is shown; it runs under the unchanged rules: model code runs only once its exact hash was approved on the
host (or the host enabled `experiments_auto`); paired devices need `experiments_remote`. If it fails, the error goes
back to the model **once** for a corrected proposal, which needs approval again.

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

## 7. HTTP API

See the docstring of `madalean/server/plugins/workbench.py` (routes `/api/calcul/{pid}/docs…`). Events:
`calcul.updated {project_id, doc, cell|run|order|removed…}`, `calcul.running`, `calcul.output` (streamed text),
`calcul.docs`.

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
