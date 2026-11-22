# Madalean 2.0 — article writing: LaTeX project, visual editor, compilation (session S-R)

Owner: S-R. This file is the contract with S-Q (suggestion engine, research orchestrator, publish, « Suggestions »
review list), S-P (Calcul: figures and computations inserted in articles) and S-O (texio / export fixes).
Code: `madalean/research/texproject.py` (model, view, history, suggestions), `madalean/research/texbuild.py`
(packages, guard, compilation, log, SyncTeX), `madalean/research/overleaf.py`, plugin
`madalean/server/plugins/article_editor.py`; web `web/src/screens/research/Article.svelte` +
`web/src/lib/article/*`.

## 1. One representation: the LaTeX files

An article is a directory `<config>/projects/<pid>/article/`:

| Path | What | Who writes it |
|---|---|---|
| `main.tex` | preamble region (generated from `madalean.toml`), your own preamble lines, front matter (generated), abstract (a block region), `\input{sections/…}` list, back matter | editor, settings |
| `sections/NN-slug.tex` | one file per top-level section; inside, **block regions** | editor |
| `figures/<sha256[:16]>.<png\|jpg\|pdf>` | content-addressed images (same bytes = same file, never duplicated) | figure insertion (upload, Calcul) |
| `madalean.toml` | document class, options, template, language, front matter (title, authors), extra packages, macros, theorem environments, bibliography style, layout, Madalean options | « Options avancées » drawer |
| `madalean.lock` | packages the source uses, each with its state in the pinned TeX bundle (`cached` / `bundle` / `missing`), bundle digest, engine | compilation (derived, never edited) |
| `.madalean/` | `history/` (content-addressed snapshots), `blocks.json` (per-block source + versions, trash), `suggestions.json` | server |

Not stored (derived at build/export time, so never duplicated): `refs.bib` (from the project's library: only cited
keys), `madalean-generated.tex` (verification table + Lean appendix from the linked dossiers).

### Markers (stable ids)

Regions are delimited by LaTeX comment lines, so they survive Overleaf, git and any other editor:

```tex
%% mdl:block b-1a2b3c4d section            ← a block region starts; kind ∈ intro|section|conclusion|prose|dossier|abstract
\section{Introduction}\label{sec:intro}
…text…
%% mdl:block b-5e6f7a8b dossier dossier=d-20261121-ab12cd   ← region linked to a Lean dossier
\begin{theorem}[Somme de deux pairs]\label{ml:d20261121ab12cd}
…
\end{theorem}
%% mdl:end                                   ← optional explicit end (used inside \begin{abstract})
```

A region extends to the next marker line, an `%% mdl:end` line or the end of its file. Managed regions of
`main.tex`: `%% mdl:preamble begin|end`, `%% mdl:front begin|end`, `%% mdl:sections begin|end`,
`%% mdl:backmatter begin|end` — regenerated from `madalean.toml` (read-only in source mode, edited through the
drawer). Setting `madalean.preamble = "manual"` stops the preamble regeneration (used automatically when an import
from Overleaf changed it). Text before the first marker of a file gets a deterministic id
(`b-` + sha1(path)[:8]) and the marker is written at the next save. Visual mode hides marker lines.

### Truth rule at build time (unchanged from §11)

The source is the author's. At build and export only (in the build copy, never in the source), a theorem-like
environment (`theorem|lemma|proposition|corollary`) inside a `dossier` region, or directly followed by a
`% mdl:lean <dossier id>` line, is typeset as `claim` with `\MLunverified` unless that dossier's current proof is
Lean-verified (strict verdict). The editor shows the same badge (verified / conditional / not verified).

## 2. The `article.py` view (compatibility for S-Q and older clients)

Once a project has a LaTeX project (created by opening the article editor; `article.json` is then renamed
`article.v1.json`), `article.load(ctx, pid)` returns a **view** built from the files and `article.save(ctx, pid,
art)` writes the changes back into the regions (`texproject.to_view` / `texproject.apply_view`). Projects never
opened in the new editor keep the v1 JSON untouched.

```ts
interface Block { id: string; kind: 'intro'|'section'|'conclusion'|'prose'|'dossier'|'abstract'; title: string;
  source: 'ai'|'user'|'dossier'; text: string /* LaTeX of the region, without marker and heading line */;
  md: string /* derived Markdown ([@key], *emph*, $math$) for readers like publish.py */; format: 'latex';
  dossier_id: string; path: string /* file of the region */; versions: {text, source, t, model, note, title}[];
  updated: number }
```

- Block ids never change (they are in the files). Deleting a block keeps it in `trash` (sidecar) for undo.
- Writers that produce Markdown/prose (AI drafts of `article.py`, Calcul « → article ») may keep doing so: on save,
  a changed `text` that looks like Markdown (`[@`, `**`, code fences, `# `, list bullets) is converted by
  `texproject.prose_to_latex(text, keys)` = `texio.sanitize_markdown` (maths through the allow-list, `[@key, loc]`
  → `\cite[loc]{key}` for keys that exist, everything else escaped). LaTeX text is kept as is.
- `title`, `authors`, `options.lang|lean_appendix|verification_table|numbering` map to `madalean.toml`.
- Exports (`GET …/article/export`) compile the LaTeX project when it exists.

## 3. Suggestions (track changes) — shared with S-Q

Storage and application belong to `texproject` (they touch the files); generation and the « Suggestions » review
list belong to S-Q; inline accept/reject in the editor belongs to S-R. **Nothing an AI writes enters the source
silently**: every AI change is a suggestion the user accepts.

```ts
interface Suggestion { id: string /* s-xxxxxxxx */; block_id: string; path: string;
  find: string /* exact text of the region (or of the file when block_id is "") */; occurrence: number /* 0-based */;
  at: 'replace'|'after'|'before'; replace: string /* LaTeX */;
  kind: string /* rewrite|shorten|formalise|translate|proof_sketch|lean|sage|research|… */;
  origin: 'assistant'|'research'|'user'; rationale: string; model: string; created: number;
  state: 'pending'|'accepted'|'rejected'|'stale'; decided: number; by: string;
  anchor?: { path: string; from: number; to: number } /* computed on read for the current text; absent = stale */ }
```

Python API (S-Q calls these; all thread-safe, all re-read the files):

```python
from madalean.research import texproject as tp
s = tp.add_suggestion(ctx, pid, block_id="b-…", find="old text", replace="new \\LaTeX", kind="research",
                      origin="research", rationale="…", model="…", at="replace")   # → dict (raises TexProjectError)
tp.list_suggestions(ctx, pid, state="pending")      # with anchors; a suggestion whose `find` vanished → state stale
tp.accept_suggestion(ctx, pid, sid, by="device")    # applies it to the file (history snapshot first)
tp.reject_suggestion(ctx, pid, sid, by="device")
```

`add_suggestion` refuses (`unsafe_tex`) replacement text containing file/shell primitives, `^^`, `\csname`,
`\catcode`, `\def`/`\let` or other definitions (texbuild.guard_ai), and `[@key]` citations of keys that do not
exist are removed (same rule as §5 of RESEARCH_SOURCES). HTTP: `GET|POST …/texproject/suggestions`,
`POST …/suggestions/{sid}/accept {applied?: bool}` (`applied:true` = the editor already applied it to its buffer and
will save it), `POST …/suggestions/{sid}/reject`. Event `article.suggestion {project, suggestion}` on every change.

## 4. Calcul (S-P) → article figures

`POST …/texproject/figures` with JSON `{calcul_asset: "<32 hex>"}` (an asset id of a Calcul run, PNG) or a
multipart `file` (PNG/JPEG/PDF, ≤ 15 MB, type sniffed from bytes) → `{path: "figures/<hash>.png", width?, height?}`.
The editor then inserts a `figure` environment. SVG plots cannot be included by TeX without shell escape: Calcul
should offer PNG (the editor says so). « Exemple avec Sage » creates an **assistant** Calcul cell through
`CalcStore.add(pid, code, "sage", "assistant", note=…)` — it runs only after the user approves it (S-M/S-P rule).

## 5. HTTP API (prefix `/api/research/projects/{pid}/texproject`)

| Route | |
|---|---|
| `GET ` | `{settings, files:[{path, text, hash}], order:[paths], templates, labels, cites, dossiers:{id:{title, status}}, suggestions, lock, overleaf_hint}` — creates/migrates the project on first call |
| `POST /file {path, text, base}` | save one file; `409 conflict {current:{path,text,hash}}` when `base` is not the stored hash |
| `POST /sections {title, after?}` · `DELETE /file?path=` · `POST /order {sections}` | structure |
| `PATCH /settings {…partial toml}` · `POST /template {template}` | settings → regenerated managed regions |
| `POST /compile {force?}` | `{ok, pdf:url|null, hash, seconds, engine, cached, diagnostics:[{severity, path, line, message, plain, fix?}], packages}` |
| `GET /pdf?h=` · `GET /synctex?path=&line=` · `GET /synctex?page=&x=&y=` | output, forward and inverse search |
| `GET /packages` · `POST /packages/fetch {names}` | analysis; fetch missing files of the pinned bundle once (online mode only) |
| `GET /versions` · `POST /versions {label}` · `POST /versions/{vid}/restore` · `GET /versions/{vid}?path=` | history |
| `POST /assist {action, path, from, to, text, lang?}` | `202 {request_id}` → `article.assist.done {project, request_id, suggestion}` / `article.assist.error` |
| `POST /figures` · `GET /figure?path=` | §4 |
| `POST /lean {text, title?, path, block_id?}` | creates a dossier (not started) + a suggestion linking it |
| `GET /overleaf` · `GET /export?format=overleaf\|zip\|pdf\|tex` · `POST /import` (zip) | §7 |

## 6. Compilation and packages (no second TeX)

Engine: the prefix's tectonic with the pinned bundle, `--untrusted --only-cached --synctex`, confined by
`export.tex_confine` (bubblewrap: build dir writable, prefix read-only, no network, no home). A development checkout
without a prefix uses the system XeLaTeX through latexmk (`-no-shell-escape`) — tests only; an installed Madalean
never compiles with the system TeX Live nor with the Overleaf container.

Before compiling: `texbuild.guard` (refuses `\write18`, `\immediate`, `\openout`, `\openin`, `\read`, absolute or
`..` `\input`/`\include`, `^^`, `\csname`, `\catcode`, `\scantokens`, `\endlinechar` — the F5 rules of
docs/SECURITY.md applied to the whole project), then the package analysis: every `\documentclass`, `\usepackage`,
`\RequirePackage`, `\usetikzlibrary` and every known command whose package is not loaded is checked against the
bundle index (`<tectonic cache>/bundles/data/<digest>.index`) and the local cache: `cached` = compiles offline,
`bundle` = in the pinned bundle but not downloaded yet (one click « Télécharger », online mode), `missing` = in
neither: the plain message says so and proposes the closest alternative. Redundant packages (loaded twice, or
implied by the class or by another package: amsart → amsmath/amsthm, mathtools → amsmath, unicode-math → fontspec,
beamer → hyperref/xcolor/graphicx/amsthm…) are reported with a one-click removal; `cleveref` before `hyperref` is
reordered by the generated preamble. Identical inputs (hash of files + bibliography + dossier states) reuse the last
PDF. Errors are parsed from the log into `{path, line, message, plain, fix}` (undefined command → add its package or
fix the typo, missing `$`, undefined environment, missing file, unbalanced braces, undefined reference or citation).

## 7. Overleaf (optional, never a permanent duplicate)

Detection (read-only): `docker ps` for a container named `sharelatex`/`overleaf` and its published port, then
`GET <url>/status`. Community Edition has no project API and no git bridge, so Madalean never writes Overleaf's
data: « Ouvrir dans Overleaf » downloads an Overleaf-ready zip (files + `refs.bib` + `madalean-generated.tex` +
`latexmkrc` selecting XeLaTeX) and opens Overleaf's « New project → Upload project » page. « Reprendre depuis
Overleaf » imports the zip downloaded from Overleaf (Menu → Source): `.tex`/`.bib`/images only (third-party
`.sty/.cls/.lua` are refused and listed), guarded like any source, a history snapshot first; markers make the blocks
and suggestions survive the round trip.

## 8. Editor and integration notes

- Editor: CodeMirror 6 live preview over the source (MIT, already bundled) — see docs/UI.md §11 for why not
  ProseMirror/TipTap. KaTeX renders maths with the article's macros (`madalean.toml` + simple `\newcommand`).
- S-Q's consigne suggestions (`/research/projects/{pid}/suggestions`, `target.mode = replace_excerpt|insert_after`
  with `block_id` + `before`) are ALSO shown inline in the editor: anchored client-side on the block region, accepted
  or rejected through S-Q's own routes (their accept writes through `article.save` → `apply_view`). The editor's own
  assistant suggestions use §3. S-Q's `SuggestionsReview` panel is embedded in the editor's « Suggestions » panel.
- S-P's Calcul « → article » (`workbench._to_article`) already uses `tp.ensure` / `tp.add_figure` and the view.
- Templates are compiled by `install tex-bundle` (`texproject.warmup_documents`, called from
  `deps/installer.warmup_documents`), so a fresh install compiles every template offline.

## 9. Around the editor: project panel, items, file tree (session S-AD)

Web only, no new route: everything comes from `GET …/texproject` (files, order, figures, labels) and the existing
project APIs (dossiers in the store, `/notes`, `/conjectures`, the project shelf's sources, Calcul notebooks
`/calcul/{pid}/docs[/{doc}]`, `…/texproject/versions`). Code: `screens/research/article/ArticleSide.svelte`
(tabs « Plan » / « Éléments »), `ArticleItems.svelte`, `ArticleFiles.svelte`, pure helpers `lib/article/items.ts`
(unit-tested in `tests/unit/article-items.test.ts`).

- **Éléments**: one group per kind — Preuves (dossiers), Calculs (notebooks; their cells on demand), Notes,
  Conjectures, Sources, Figures, Historique (versions) — each with its own icon (`proof` ∀✓, `plot`, `cell`, `note`,
  `conjecture`, `source`, `image`, `clock` in `Icon.svelte`), a text kind label and a colour token `--k-*`
  (`styles/tokens.css`, light + dark). Filter box; groups folded/unfolded per device.
- **Insertion** (« Insérer » at the cursor, or drag onto the text for items whose LaTeX is known in advance):
  dossier → `\begin{theorem|lemma}[title]\label{ml:<id sans tirets>}` + `% mdl:lean <id>` + statement (the §1 truth
  rule then typesets it « non vérifié » unless Lean verified it), or `\cref{ml:…}` when the article already has that
  label; conjecture → `conjecture` environment; source → `\cite{key}`; figure → `figure` environment; Calcul cell
  with a PNG output → `POST …/figures {calcul_asset}` then a `figure`; with a `text/latex` result → display maths.
  Notes and versions only open (note screen / versions dialog). Insertions are the user's own edits (not
  suggestions).
- **Fichiers du projet LaTeX** (under the outline, shown or hidden, remembered): `article/` with `main.tex`,
  `sections/` (document order, then files not included by `main.tex`, marked « non incluse »), `figures/`,
  `refs.bib` (generated at build time → opens Sources), `madalean.toml` (→ Options avancées), `madalean.lock`
  (→ Options › Paquets). A `.tex` opens in the editor, an image opens in a tab or is inserted. Read-only: the only
  structural action is « Ajouter une section » (existing route); no rename/delete from the tree.

## 10. Compilation errors corrected by the conductor (session S-AN, DECISIONS D46)

Code: `research/conductorfix.py` (`fix_compile`), `texbuild.trial_compile`, hook `_conductor_fix` of the plugin;
the conductor itself is docs/BRAIN.md §18.

- **When**: a compilation that really ran (`ran: true`) failed on an error for which §6 has no one-click fix
  (`fix: null` — e.g. « Missing $ inserted », unbalanced braces, an unknown command without a close match), a
  conductor can run (setting on, not `local`, Claude key or a capable free model) and this exact source (input hash)
  was not tried yet. `POST /compile` answers at once with `fixing: true`; the work runs after the answer. Guard
  refusals, missing packages and files to fetch are never sent to a model (they have their own fixes).
- **What the conductor sees**: the file and line of the first such error, the raw TeX message and Madalean's plain
  reading, an excerpt of ±20 numbered lines, the LaTeX rule card. It answers `{find, replace, what}`: `find` must
  be an exact substring of the excerpt (the occurrence nearest the error line is used), `replace` must pass
  `guard_ai` (no file / shell primitives, no definitions).
- **Checked before it is offered**: the project is compiled with the change in its own build directory
  (`build_dir/trial-<id>`, same engine and bubblewrap confinement, offline, no shell escape, deleted afterwards; the
  author's PDF, log and cache are untouched). A change that still fails goes back to the conductor with the new
  error (≤ 3 proposals per failed compilation). The source changed meanwhile → stop (the error may be gone).
- **Offered as a suggestion**: `kind: "compile_fix"`, `origin: "assistant"`, `rationale` = the conductor's sentence,
  `meta: {conductor, tier, usd (whole request), verified: "recompiled", error, line}` — shown « Proposé par Claude
  Sonnet · 0,01 $ · vérifié : l'article compile avec ce changement » in the suggestions panel, accept / refuse like
  every suggestion (§3); nothing is written to the source until the author accepts.
- **Budget**: scope `article:<pid>:<hash>`, cap `conductor_cap_usd`; the cap question is the global dialog
  « Plafond atteint » (`conductor.ask`, `POST /api/conductor/asks/{id}`). Events: `article.fix {project, state:
  working|proposed|none, suggestion?, name?, usd}` (the editor shows « Recherche d'une correction… » then a toast),
  `article.suggestion` as usual.
