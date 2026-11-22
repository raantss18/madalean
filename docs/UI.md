# Madalean 2.0 — web interface (session S-D)

Sources in `web/` (Vite + Svelte 5 + TypeScript strict), built output in `madalean/static/` (committed, hashed assets,
pre-compressed `.br`/`.gz` served by aiohttp). The same UI runs in the host's browser, in remote browsers paired over
the tailnet, and inside the desktop/Android shells (docs/SHELLS.md).

```
web/build.sh            # npm ci if needed → svelte-check → vite build → madalean/static/ (+ .br/.gz)
cd web && npm test      # unit tests (vitest): data layer, i18n completeness, Lean helpers, router
cd web && npm run e2e   # Playwright (headless Chromium) against its own `madalean serve --demo` (free ports, temp config)
cd web && npm run perf  # time-to-interactive (throttled phone) + 10 000-line stream measurements
cd web && npx playwright test --project=screens   # regenerates docs/screenshots/v2/
MADALEAN_DEV_API=http://127.0.0.1:<port> npm run dev   # dev server proxying /api (+ WS) to a demo server
```

The e2e global setup starts `bin/madalean serve --demo --port <free> --remote-port <free> --config-dir <tmp>` and kills
it at the end; it never touches `~/.config/madalean`, ports 11500/11501 or the GPU.

## 1. Design rationale

### What was taken from the user's own projects

**L Katta** (`~/GitHub/L-Katta`: README, docs, `chat.rs`, `config.rs`, `cles.rs`, `fils.rs`, `conseils.rs`, lang files,
screenshots):
- *Settings applied immediately*, no « Apply » button; a short status (« Enregistré. ») confirms. Sections are few and
  plain-named; power-user knobs are folded away (« Réglages avancés »). Every setting has a default.
- *Adding a key in two moves*: « Obtenir une clé » opens the provider's key page (through the shell bridge when present)
  and puts the focus in the field; paste → Enregistrer. The field is a password field and is emptied at once; a
  plausibility check runs first (prefix `sk-ant-`, `gsk_`, `AIza`, `sk-or-`, `csk-`; no spaces; ≥ 16 chars) with L
  Katta's wording (« ne ressemble pas à une clé Groq : vérifiez le copier-coller »). Then the key is saved, tested
  (`POST /models/test`; when the engine has no test, the models the key unlocks are counted after
  `POST /models/refresh`, exactly L Katta's « Clé enregistrée : N modèles ajoutés » / « aucun modèle trouvé : la clé
  est-elle valide ? »). The key is never displayed again; « Retirer la clé » asks inline (it cannot be undone).
- *Model choice*: « Automatique » first and recommended, with the current pick named; a per-task override for those who
  want it; a quality-ranked list with a « Pourquoi ? » disclosure (the router's `why` once the server exposes it, see
  Requests).
- *Plain-language errors with one way out*: « ce qui s'est passé : quoi faire » everywhere (`err.*` catalogue); a failed
  follow-up request returns to the input (L Katta: « Ta demande est revenue dans la saisie »).
- *Threads* (« côtés et fils »): each dossier has its thread (« Fil du dossier ») — every request and result in order,
  who produced it, with a link back to the step it changed. L Katta's two *sides* (Discussion/Code) map to Madalean's
  two *modes* (Apprendre/Recherche), remembered per device.
- *Guidance*: L Katta's bubbles always offer a primary + secondary action; Madalean's first-run tour does the same
  (« Suivant » / « Passer la visite »), one idea per step, and only in Learn mode.
- *Reversible*: L Katta uses a trash and inline confirmations; Madalean adds undo toasts (server `.trash` + restore
  endpoints) for dossiers, library entries, version restores, archives and discarded drafts.

**Sampana** (`~/GitHub/sampana/web`): *one door* — everything behind one address, one pairing, one session cookie;
*calm live status* — small dots/marks that change in place, a one-line summary, no dashboard noise; status pending →
up/degraded/down mapped to semantic colours, never colour alone; reduced motion honoured; 16 px inputs (no iOS zoom);
« le service met du temps » messages instead of endless spinners (here: queue reasons « attend la carte graphique »).

**Lean AI Station 1.1** (`app/lean_ai_station/ui/*.py`, `docs/screenshots/*.png`): the dossier as the unit of work
with its thread, versions (« Voir · version actuelle »), quick actions (« Corriger l'énoncé… », « Preuve plus simple »,
« Autre méthode », « Expliquer plus en détail »), examples by level (Initiation … Olympiade), « Importer un .tex »,
« Je sais écrire du Lean », the status bar showing the model and where it runs — and its weak points, fixed here: the
three tabs « Énoncé Lean / Preuve / Explication » were hidden in a side panel with a long chat; 2.0 makes the
statement → Lean → proof progression the primary navigation (a stepper whose steps show their state and stay
re-openable). The Unicode abbreviation table of the 1.x `LeanEditor` is ported verbatim (`web/src/lib/lean/abbrev.ts`).

### Identity

Built on the shells' brand (shells/branding/: a baobab whose crown is ∀, ink `#1F2A44`, laterite ground line
`#D9643F`). Choices made for *mathematics*, not a dashboard template:
- **Typography that sets theorems like a paper**: Source Serif 4 for headings and for statements, which are typeset
  amsthm-style (« **Énoncé.** *italic body* » with KaTeX inside); Source Sans 3 for the interface (same family, clear
  contrast of roles); DejaVu Sans Mono for Lean — chosen because it covers every glyph Lean/Mathlib uses (ℝ ℕ ≤ ⟨⟩ ∀ ∃
  ∣ ⁻¹ subscripts ₀…₉, checked against its cmap) and is the font the PDF export already uses (ARCHITECTURE §9), so
  screen and paper match. All self-hosted (fontsource packages), licences in « À propos ».
- **The status glyph family after ∎**: proved = filled square (the QED mark), running = a square being drawn,
  queued = dotted, failed = struck, stopped = half, draft = open. Always paired with a text label (sr-only in lists).
- **Restrained palette** (brand D40, docs/BRAND.md): cool paper `#F4F6F9`, navy `#002B5C` ink, blue `#0B4F9C` for links/focus, orange only for the
  wordmark rule and the current step underline; semantic proved green / failed red / running amber; privacy colours
  teal (« stays here ») and violet (« goes online »). Dark theme built from the same tokens.

### How the education skills shaped Learn mode

Skills loaded: `progressive-hint-ladder`, `worked-example-fading-designer`, `self-explanation-prompt-designer`,
`explain-first-interrogator` (+ `frontend-design`, `design:ux-copy`, `design:accessibility-review`, `a11y-enforcer`).
Since phase 2 every learning feature is **served and checked by the server** (docs/RESEARCH_WORKSHOP.md §4): the
client holds no prompt any more (`web/src/lib/learn/tutor.ts` only calls the endpoints and translates their gates).
- **Hint ladder before the proof** (`HintLadder.svelte` → `POST /dossiers/{id}/hint`, `GET /learn/{id}/ladder`):
  retrieve-first gate (« Qu'avez-vous essayé ? » + « De quelle aide avez-vous besoin ? »), then nudge → strategy →
  key lemma → next step → full proof (level 5 = the Lean-verified proof, never model text). Each rung needs a one-sentence
  reflection on the previous hint (the skill's anti hint-clicking safeguard; the server enforces it from level 3, the UI
  from level 2). Leaking hints are regenerated or shortened by the server and marked « indice raccourci ». Progress
  is kept by the host per device, refreshed live by `learn.progress`.
- **Explain it back** (`ExplainBack.svelte` → `POST /dossiers/{id}/explain-back`): the learner writes first; the answer
  is graded against criteria taken from the Lean-verified proof (or the Lean statement): « 1 critère sur 2 rempli »,
  ✓/✗ per criterion, the gap, and *one* question; after three rounds a cleaner final version is asked for.
- **Exercises** (`Exercise.svelte`): *faded proof* (`/learn/{id}/exercises/faded`: last k steps removed from the end
  backwards, each blank proven non-trivial by a real Lean run; the learner fills the blanks, Lean checks strictly) and
  *erroneous example* (`…/erroneous`: a plausible wrong step that Lean really rejects; diagnosis first, then Lean's real
  error, then the fix checked by Lean). When every step is automatic the server says so and the UI shows it.
- **Token meanings**: hover (desktop) or tap (phone) any Lean token: the built-in bilingual glossary first, then
  `GET /learn/token` (tactic table + the workspace's declaration index; unknown names reported unknown, never invented).
- **Research mode** removes all of this from the way: proof shown at once, learn panel collapsed, denser spacing,
  keyboard shortcuts (`n` new, `/` palette).

### Research screens (phase 2): NotebookLM + Zotero + Obsidian, unified around Lean

- **Sources** (`/sources`, reader `/sources/:shelf/:id`): Zotero-like library per project shelf (global and Mathlib
  shelves too), filters by tag / reading status, add by identifier (DOI, arXiv, ISBN, zbMATH, OpenAlex, URL), file
  (PDF, TeX, BibTeX/RIS/CSL-JSON/RDF, Zotero export zip) or paste, duplicates explained; merged literature search
  (arXiv, zbMATH, Crossref, OpenAlex, Semantic Scholar) with per-provider status and « Ajouter ». The reader shows the
  paper as a TeX-derived *structure* (theorem-like blocks typeset like the paper) or as the *PDF* (pdf.js, lazy:
  pages rendered when scrolled to, text layer for selection, highlights from annotation quads, « Surligner » on a
  selection), side by side with **grounded questions** (`QaPanel`): every sentence carries its passage buttons
  (P1, P2…); a click opens the PDF page at the passage box (flash) or the structure view at the chunk; sentences
  without a verified citation are struck « non étayé »; optional general knowledge is a separate, labelled part;
  « Résumer » and « Comparer avec… ». « Copier le lien » gives `[[passage:…]]` for notes; « Extraire le blueprint ».
- **Notes** (`/notes/:id`): Markdown + KaTeX + ```` ```lean ```` blocks with « Vérifier avec Lean » per block and « En faire
  un dossier »; `[[` opens a completion list (notes, dossiers, `@keys`); side-by-side preview with working links;
  backlinks; tags; daily note; versions with diff and restore; autosave with `base_rev`: the server merges edits from
  two devices, and when the same lines changed a **merge view** shows « Ma version / L'autre version / Les deux » per
  hunk with an editable result (never a silent overwrite).
- **Graph** (`/graphe`): notes, dossiers, sources and their links; dependency-free force layout (grid-bucketed
  repulsion, 500 nodes < 3 s, deterministic); labels appear near the pointer / selection or when zoomed in, constant
  screen size; filters (kinds, link kinds, tag, isolated nodes), find, keyboard pan/zoom, and a **list view** (table)
  that is the default on phones and the screen-reader alternative.
- **Blueprint** (`/blueprint`): layered DAG (dependencies on the left), each node with a status that is colour **and**
  border pattern **and** text (verified / proved with unverified dependencies / defined / Lean statement / stated /
  blocked / failed / no dossier); node panel with the paper's text beside the Lean statement, proposed edges to confirm
  or discard, « Créer les dossiers », « Formaliser la sélection » (the paper's proof goes to the Goedel prover only).
- **Article** (`/article`): blocks with « Brouillon IA · modèle » vs « Votre texte » vs result blocks (« vérifié par
  Lean » / « non vérifié »); regenerate one block (streams live); regenerating a block you edited asks first and keeps
  your text in its versions; reorder, add, delete with undo, cite from the project's keys, preview typeset like the
  paper (unverified results as « Affirmation », never « Théorème »), export PDF/TeX/zip/md.
- **Conjectures** (`/conjectures/:id`): propose from the project's notes / results (filtered duplicates explained) or
  write one; status steps (proposée → testée sur des cas → énoncé Lean → prouvée, or réfutée); counter-example card
  (re-verified by Sage/Python and Lean); experiments whose code is shown and runs only after « J'ai lu ce code :
  approuver et lancer » (editing the code drops the approval; host-only unless the host allows it), live output;
  append-only evidence timeline with its hash chain status; promote to theorem only after a Lean proof.
- **Proof plan as a mind map** (dossier tab « Plan », also linked from the thread and from a failed proof; S-L): one
  obvious path with big buttons — « Découper ce théorème » → read / edit the lemmas → « Valider le plan » → « Prouver le
  plan ». A one-line « où en est-on » at the top (computed from statuses, no model): what to do next, counts, depth and
  node budget. The map is a left-to-right tree (theorem on the left; readable for 5–30 nodes; rows assigned to leaves so
  boxes never overlap); solid curves = chosen track, dashed pill = another track kept in reserve (one pill per track,
  not its lemmas). Each node: status in words + icon + border pattern (à valider dashed, en cours striped band, prouvé
  green, échoué red, trou / conditionnel dashed amber, piste abandonnée / autre piste dashed grey) — never colour alone.
  Click a node → detail panel (beside the map when the plan area is ≥ 900 px wide, below it otherwise): breadcrumb from
  the theorem, words, « Pourquoi ce lemme aide », Lean statement and Lean's verdict, obvious proof, combination
  (vérifiée / à vérifier / refusée), actions (valider, modifier, autre piste, (re)découper, laisser un trou, ouvrir le
  sous-dossier, supprimer). A failed lemma shows « Que faire ? » with the three ways out in order. Phone (< 768 px):
  the collapsible outline (« Liste ») is the default view, the map is one tap away; the choice is remembered. The
  Plan tab gives the map the full width (the thread goes below). « Conditionnel — N trou(s) » is never « vérifié ».
- **Publier** (`/publier`): choose results (verified by default; unproved ones are published as « Affirmation ») and
  notes (none by default), « Préparer la liste exacte » (nothing sent), the exact file list with sizes and origins,
  what was excluded and why, what is never published, local preview, then push to GitHub with the id of the list you
  reviewed (host only; GitHub token in Réglages › Clés).
- **Aide** (`/aide/:page`): the manual of `docs/manual` (one source with the website), see §2b.
- **Project hub** (`/projet`, the phone's « Projet » tab): one door to every section of the current project with counts.
- **D28** (Lean code that could run programs on the host is refused before compiling): every check result shows the
  refusal as « Lean n'a pas été lancé : code refusé par sécurité » with the refused constructs in plain words
  (`lib/lean/refusal.ts`), distinct from a Lean error.

## 2. Information architecture

```
(S-AK, §14 — replaces the ☰ / rail / drawer / bottom bar of earlier versions)
Top bar:      [Madal∃an ▾ = menu]  [Projet › Dossier ▾]  ……  [Chercher Ctrl K] [état: mode · n]
Logo menu:    Accueil · (project sections when the bar is hidden) · Activité · Bibliothèque · Glossaire · Carnet ·
              Aide · Réglages · Apprendre | Recherche · Barre du projet
Project bar:  Dossiers · Sources · Notes · Graphe · Blueprint · Article · Conjectures · Calcul · Publier (project screens)
Main:
  /                         Énoncé of a NEW dossier (natural language/LaTeX with live preview, or Lean), .tex import,
                            examples, recent dossiers
  /d/:id/(enonce|lean|preuve|plan)  one dossier: stepper Énoncé → Traduction Lean → Preuve, + Plan; thread beside/below
  /projet                   project hub · /sources, /sources/:shelf/:id · /notes/:id? · /graphe · /blueprint · /article
  /conjectures/:id? · /publier · /aide/:page?
  /activite                 all jobs of all dossiers, resource slots, cancel each
  /calcul                   project worksheet: Sage/Python cells in the sandboxed offline kernel, assistant panel
                            (write / fix / explain), approval of assistant code, results → conjecture/note/dossier/article
  /bibliotheque             proven results by domain / project / tag, cards or table, detail (status verified /
                            conditional, model, uses / used-by, domain + tags editable), export md/json/.lean
  /glossaire                ≈ 250 Lean / Mathlib terms by category and level, A–Z index, entry detail (meaning, Lean
                            form, example, related, Mathlib declarations on demand, « in my dossiers ») + abbreviations
  /carnet                   JupyterLab iframe + assistant panel
  /reglages/:section        modeles · cles · appareils · espaces · mises-a-jour · profil · langue · apparence · carnet · systeme · a-propos
  /pair                     pairing screen (public; remote browsers)
  /__perf                   measurement page used by e2e/perf.spec.ts
Ctrl+K searches everything: screens, actions, dossiers, notes (full text), sources of the project, the manual.
Phone (<768 px): same top bar (logo icon, switcher on two lines, search icon, status icon), the logo menu is a sheet
                 from the left, panels are sheets under the top bar; the project bar scrolls sideways.
Tablet / desktop: labels become icons below 1280 px; ≥ 1280 px the dossier shows its thread beside the steps.
                 Details and adaptive patterns: §12 (bottom bar parts superseded by §14).
```

**Data layer** (`web/src/lib/`): `api/types.ts` (types of docs/API.md §5), `api/client.ts` (typed client, errors as
`ApiError{status, kind, body}`, 401 → `/pair?reason=auth`, exports as real URLs), `store/sequencer.ts` (seq / resume /
resync, pure), `store/model.ts` (reducer, pure), `store/connection.ts` (WebSocket with backoff, ping, online/offline,
visibility), `store/streams.ts` (token streams outside reactive state, one notification per frame),
`store/app.svelte.ts` (the single reactive store), `store/optimistic.ts`. Screens never hold their own copy of server
data: they read `app.m` and the server's events update it, which is what keeps every device in sync.

## 2b. In-app help from the manual (docs/SITE.md §2)

`web/src/lib/manual.ts` loads `docs/manual/index.json` (schema `madalean-manual/1`) as a lazy chunk (≈ 82 kB gzip) —
the same texts as the website, never a second copy. Pages of the interface language, grouped by `sections` order;
`body` rendered by `renderTrusted` (`lib/md.ts`: markdown-it with GFM tables, KaTeX, Lean fences highlighted, images
allowed only from `/help/img/`, then DOMPurify); heading ids are assigned **in order from `headings[]`** (never
re-slugified) so anchors match the site; links rewritten (`<id>.md#a` → `/aide/<id>#a`; `site:updates` /
`site:install` → Réglages › Mises à jour; other `site:<name>` → `site_url + lang + "/" + site_links[name]`, external);
`docs/manual/img/` is copied to `madalean/static/help/img/` by a small Vite plugin (served in dev too). Search over
title, headings, summary and text, accent-folded (also in Ctrl+K). Contextual « Aide » links (`HelpLink`) on Home
(workflow), each dossier step (workflow / reading-lean / proof-plans), Sources, Notes, Graph, Blueprint, Article,
Conjectures, Publier, Carnet and the settings sections (models-keys, pairing, updates, security, troubleshooting…).

## 3. Design tokens (`web/src/styles/tokens.css`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` / `--surface` / `--surface-2` | `#F4F6F9` / `#FFF` / `#EBEFF5` | `#0B1220` / `#111B2E` / `#18243A` (navy-tinted) | page, panels, wells |
| `--text` / `--text-2` / `--text-3` | `#14213A` 16.1:1 / `#44506A` 8.1:1 / `#58637A` 6.0:1 | `#E8EDF5` 14.6:1 / `#B6C2D6` 9.6:1 / `#9AA8C0` 7.2:1 | text levels |
| `--ink` / `--on-ink` | `#002B5C` (brand navy) / `#FFF` 14.0:1 | `#DBE6F5` / `#002B5C` 11.1:1 | primary buttons, brand |
| `--accent` | `#0B4F9C` 8.0:1 | `#8DB8F2` 8.4:1 | links, focus ring, selection |
| `--laterite` / `--laterite-mark` | `#A84B00` 5.7:1 / `#FE7B01` (brand orange, decoration only: 2.6:1) | `#FF9A3D` 8.2:1 / `#FE7B01` 6.6:1 | orange text / brand rule, current step, highlights |
| `--proved` on `--proved-soft` | `#1A7246` 5.2:1 | `#66D398` 7.7:1 | proved |
| `--failed` on `--failed-soft` | `#B42318` 5.6:1 | `#FF8E82` 6.9:1 | failed / errors |
| `--running` on `--running-soft` | `#8A5200` 5.7:1 | `#F3BF68` 8.7:1 | running / waiting |
| `--online` / `--local` (on soft) | `#6A3FB0` 6.0:1 / `#1A6A7A` 5.4:1 | `#C7A8FF` 7.5:1 / `#79D0DE` 7.8:1 | who receives what |
| `--line-strong` | `#7F8AA0` 3.5:1 | `#6B7D9E` 4.1:1 | input borders (non-text 3:1) |
| radii | 4 / 8 / 12 px | | chips·code / controls / panels |
| spacing | 4 8 12 16 24 32 48 | | `--s-1` … `--s-7` |
| type | 13 14 16 19 24 32 px | | `--fs-xs` … `--fs-2xl`; body 16/1.5 |
| `--touch` | 44 px (36 px in Research mode with a fine pointer) | | min target |

Ratios measured with the a11y-enforcer contrast script (all AA for their use). Research mode (`data-mode=research`)
tightens spacing and the top bar. Themes: system by default, per-device override (`data-theme`), applied before first
paint by `public/theme-init.js` (external file: CSP forbids inline scripts).

## 4. How to add a screen

1. Create `web/src/screens/Sources.svelte` taking `{ params }: { params: Record<string, string> }`. Put an `<h1>` first
   (focus moves there on navigation).
2. Register it in `web/src/routes.ts`:
   `addRoute({ name: 'sources', pattern: '/sources/:id?', load: () => import('./screens/Sources.svelte'), nav: { label: 'nav.sources', icon: 'book', order: 5 } })`
   — it becomes its own chunk, appears in the rail, the command palette (and the phone bar with `phone: true`).
   A screen of the current project uses `nav.group: 'project'` (rail top block + project hub), wraps its content in
   `<ProjectGate>` and reads the project with `currentProjectId()`; put a `<HelpLink page="…" />` next to its `<h1>`.
3. Add the strings to **both** `web/src/lib/i18n/fr.ts` and `en.ts` (TypeScript refuses an incomplete `en.ts`;
   `npm test` checks placeholders and every `t('…')` key used in the sources).
4. Data: add endpoint functions to `api` in `lib/api/client.ts` and types to `lib/api/types.ts`. If the server
   publishes new event types, either extend `applyEvent` in `lib/store/model.ts` (and its `Model`) or subscribe from
   the screen with `app.on('source.updated', fn)` (returns an unsubscribe function).
5. Long operations: show progress, make them cancellable (`AbortSignal` in `request`), errors through `errorText(e)`;
   destructive actions: optimistic + undo toast (`toast('ok', …, { action: { label: t('common.undo'), run } })`).
6. Add an axe pass for the new route in `e2e/a11y.spec.ts`, and a screenshot in `e2e/screens.spec.ts`.
7. Phones (S-AP, §16): import nothing heavy at the top of the screen — maths go through `Md` / `renderMath` (KaTeX
   loads on the first formula), code through `CodeEditor` (CodeMirror loads when idle), a part shown only on demand
   through a dynamic `import()`. A field that **sends** keeps its unsent text with `keepDraft(…)`.

## 5. Dependencies (exact versions, `web/package-lock.json`; `npm audit`: 0 vulnerabilities)

| Runtime | Why |
|---|---|
| `svelte` 5.59.1 | compiler + tiny runtime; runes give a single reactive store without a state library |
| `@codemirror/state, view, language, commands` 6.x + `@lezer/highlight` | Lean and natural-language editors (lazy chunk): Lean highlighting (StreamLanguage), abbreviations, hover gloss, error lines |
| `katex` 0.19.1 | maths rendering (statements, previews, explanations), `trust:false` |
| `markdown-it` 15.0.3 | Markdown of model output with `html:false` (raw HTML shown as text) |
| `dompurify` 3.4.18 | defence in depth on the final HTML (model output is untrusted) |
| `uqr` 0.1.3 | QR code for `madalean://pair?…` (rendered as our own SVG, no `{@html}`) |
| `pdfjs-dist` 5.4.394 | PDF reader with page anchors, text layer and highlights (lazy chunk of the reader only; `isEvalSupported:false` for the CSP; worker served from `/assets`) |
| `@codemirror/autocomplete` 6.20.0 | `[[` link completion in notes |
| `@fontsource-variable/source-sans-3`, `@fontsource-variable/source-serif-4`, `@fontsource/dejavu-mono` | self-hosted fonts (OFL / Bitstream Vera) |

| Dev | Why |
|---|---|
| `vite` 8.3.8, `@sveltejs/vite-plugin-svelte` 7.3.1 | build, hashed assets, route-level code splitting |
| `typescript` 5.9.3, `svelte-check` 4.7.8 | strict type checking (TS 7 not used: svelte-check does not support it yet) |
| `vitest` 5.1.1 | unit tests |
| `@playwright/test` 1.65.1, `@axe-core/playwright` 4.14.0 | e2e in headless Chromium, automated WCAG checks |
| `@types/node` | test tooling |

No CSS framework, no state library, no router library, no icon font (icons are 24×24 SVG paths in `Icon.svelte`).

**CSP** (meta tag in `index.html`): `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' blob:; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none';
form-action 'self'`. `style-src 'unsafe-inline'` is needed by CodeMirror (style-mod inserts `<style>`), KaTeX's inline
sizing and Svelte `style:` directives; no inline *script* anywhere. No remote origin is ever contacted by the page.

## 6. Measured performance (headless Chromium on this PC, demo server; `npm run perf`)

Bundle (gzip, after phase 2): first render needs **≈ 93 kB** (entry 23 + Svelte runtime 24 + store/i18n catalogues 44
+ client 2); every screen is its own chunk (research screens 1–7 kB each). All application code together: **219 kB**.
Heavy optional chunks, loaded only by the screens that need them: KaTeX + markdown-it + DOMPurify 125 kB (+ KaTeX
fonts), CodeMirror 107 kB, pdf.js 112 kB + its worker 282 kB (reader's PDF view only), the manual's index.json 81 kB
(Aide only). Served pre-compressed (brotli), hashed and immutable.

| Measurement | Result |
|---|---|
| Time to interactive, phone 360×780, 4× CPU throttling, fast-3G (150 ms RTT, 1.6 Mb/s), **cold cache** (heading visible + statement field accepts a key) | **2.6 s** (DOMContentLoaded 1.0 s; 206 kB JS transferred) |
| Same, **warm cache** | **1.26 s** (target < 1.5 s) |
| 10 000-line stream (40 lines every 16 ms): frame times | p50 16.7 ms, p99 16.8, max 16.8 ms, 0 frames > 50 ms |
| Typing while that stream runs | keystroke → value p50 7 ms, max 16 ms |
| Scrolling the 10 000 lines (201 422 px) | p50 16.7 ms, p95 17.2, p99 17.6, max 17.9 ms — 60 fps |
| Graph force layout (Node, this PC) | 100 nodes 62 ms · 300 nodes 111 ms · 500 nodes 121 ms · 1 000 nodes 223 ms |

How streaming stays smooth: tokens never enter reactive state; one paint per animation frame; text split into
frozen 200-line blocks (only the tail re-renders, splitting is O(new text)); finished blocks use
`content-visibility:auto` (browser-level virtualisation that keeps line wrapping); stick-to-bottom only when the reader
is at the bottom; `overflow-anchor:none` and fixed boxes so nothing shifts.

## 7. Accessibility (WCAG 2.1 AA)

- **Automated**: axe-core (wcag2a, 2aa, 21a, 21aa) runs in `e2e/a11y.spec.ts` on home, the three dossier steps, proof in
  both modes, activity, library, glossary, notebook, settings (models, keys, devices, system, appearance, updates),
  pairing, English home and phone Lean step — **light and dark: 0 violations** (findings fixed during the session:
  label-in-name on the search button, unlabelled hidden file input).
- **Keyboard**: skip link; every control native or ARIA-pattern-complete (tabs with arrows/Home/End, menu button with
  arrows/Escape, combobox palette, native `<dialog>` with focus trap and focus return); `Ctrl+K`/`/` palette; focus
  moves to the screen's `<h1>` after navigation; visible `:focus-visible` ring (`--focus`, ≥ 3:1).
- **Screen readers**: status never by colour alone (text labels, sr-only in lists); live regions: polite toasts,
  assertive errors, `role=log` for streams (aria-live off, a polite line-count summary every 50 lines), `role=timer`
  for the pairing countdown; errors linked with `aria-describedby`/`aria-invalid`.
- **Touch targets** ≥ 44 px (checked in `e2e/phone.spec.ts` for the bottom bar and the step tabs); 36 px only in
  Research mode with a fine pointer. **Reduced motion**: all animation off. **Zoom/text size**: rem-based, text size
  setting 100/112/125 %, no horizontal scroll at 360 px (checked on every screenshot).

## 7b. Test results (2026-11-21, after phase 2)

- `npm test`: **27 unit tests** pass — sequencer (order, duplicates, gap → resume, boot change → resync with buffered
  events, overflow → resync), reducer, optimistic rollback, stream coalescing, i18n (same keys, same placeholders,
  every static key used exists, dynamic families complete, bilingual glossary/examples), Lean helpers, D28 refusal
  recognition, `[[link]]` rendering, Lean-block finding, conflict resolution, graph layouts (500 nodes, determinism,
  layering, cycles), router, model labels.
- `npx playwright test` (e2e + screens + perf): **all pass** — phase 1 (flow statement → Lean → proof → export →
  follow-up → version restore, pairing, revocation, parallel + cancel, 409, keys, models, language, devices, phone,
  live sync of two contexts, reconnect, research mode + split, axe ×2 themes, keyboard) and phase 2 (`research.spec.ts`:
  sources add-by-paste / literature search / grounded answer → passage / highlight / PDF rendered; notes autosave, `[[`
  completion, versions + diff, live conflict → merge view → saved, Lean block check; graph + list; blueprint panel +
  formalise selected; article AI draft vs your text, regenerate asks before overwriting; conjectures counter-example,
  evidence, write one, experiment approval gate; plan accept / admit → conditional, never « vérifié »; learn ladder +
  explain-back criteria + faded/erroneous exercises through the server; manual proof version checked by Lean; D28
  refusal view; help from the manual (anchors from `headings[]`), publish, updates, Ctrl+K across notes/sources/manual).
  axe (WCAG 2.1 AA) has 0 violations on every checked view (29 routes of `a11y.spec.ts` in light and dark, plus 13 views in `research.spec.ts`) (findings fixed: label-in-name on graph nodes,
  duplicate accessible names). 13 screenshot sets for phase 1 + 4 research sets (desktop light/dark, tablet, phone)
  in `docs/screenshots/v2/`, all without horizontal scroll.
- `npm audit`: 0 vulnerabilities. `svelte-check`: 0 errors, 0 warnings.

## 8. Requests to the server

**Done by the server since phase 1 and now used by the UI**: manual edits as versions (`POST /dossiers/{id}/versions/
{kind}`, the « Modifier » editors save new versions; a manual proof counts only if Lean accepts it); real key test
(`POST /models/test` with `models`, `reason`); router `why`/`score` (shown in « Pourquoi ? »); declaration lookup
(through `GET /learn/token`, which adds the curated tactic table); `GET /examples` (Home; built-in list only as a
fallback); CSP header on HTML; `GET /jobs/{id}/stream` (replay of every stage when a page opens mid-job);
`remote_url` from `POST /pairing/start` (pre-fills the QR address); `POST /devices/self/forget`; learning endpoints
(hint, explain-back, faded and erroneous exercises, progress); publication (`/research/publish/*`).
Model leaderboard and proof tournament (S-J, BRAIN.md §11): Settings › Models shows `GET /models/leaderboard`
(general rows, top 12: model, task, solved/tasks, score ×100, mean attempts, mean time; « Remettre à zéro » only on
the host → `POST /models/leaderboard/reset`) and the five `tournament_*` settings under « Réglages avancés »; the
proof step shows « Tournoi : round k, modèles … » from `Job.tournament` above the attempts (each `Attempt` carries
`round`). Not done: per-domain rows and a per-attempt round badge.

Still open (the UI works around each):
1. **`Attempt.model` as a Python repr** in demo runs (`ModelRef(provider='fake', …)`) instead of `provider:model_id`;
   `modelLabel()` parses it.
2. **Assistant/qa/article streams can overtake their 202** (`request_id` unknown when the first events arrive): the
   store buffers unclaimed request events 60 s. A client-chosen `request_id` would remove the race.
3. **Learner reflections**: the hint endpoint takes `reflections` but the ladder (`GET /learn/{id}/ladder`) does not
   return them, so on a second device the UI asks for the last reflection again. Returning them would make the ladder
   fully device-independent.
4. **`GET /updates/recheck`** answers `report: {}` before any re-check; a `null` (as documented) would be clearer (the UI
   handles both).
5. **D28 refusal as data**: the refusal is recognised by the summary prefix (« Refusé avant compilation » / « Refused
   before compiling ») and the French `reasons` labels; a machine-readable `refused: ["eval", "io", …]` field in
   `CheckResult` would make it robust to rewording. The demo's fake Lean does not apply D28, so the refusal view is
   tested with a mocked response.
6. **Publication in demo mode** answers `no_mathlib_pin` (the demo workspace has no pinned Mathlib), so the manifest,
   preview and push views were only exercised up to that plain error; a demo manifest would allow testing them.
7. **Note conflict hunks** give base line numbers but not the position in the current text: the merge view finds the
   « theirs » text in the current body (unique in practice) and shows the editable result before saving.
8. **Search across everything**: Ctrl+K calls notes search, the project's sources and the manual separately; one
   `GET /search?q=` over dossiers, notes, sources, passages and library would rank results together.

## 9. What was NOT verified

- Real models, real Lean, real TeX: everything ran against `serve --demo` (fake brain, fake Lean). The PDF path with a
  TeX engine (real URL download) and the HTML fallback (decided from the `tex` health check) were not exercised
  end-to-end with real exports; `.lean` download was.
- The shells: the `madaleanShell` bridge (changeServer, openExternal), the Android re-download of export URLs and the
  `/api/session` ticket flow were not run (no shell in this session); only the code paths exist.
- Real tailnet (`tailscale serve`, HTTPS, `Secure` cookie): pairing was tested on the plain-HTTP remote listener on
  127.0.0.1.
- JupyterLab embedding: the notebook screen was rendered (status, host-only path) but Jupyter was never started (it
  would launch a real `jupyter-lab`).
- Screen readers (NVDA, VoiceOver, TalkBack) were not used; only axe + keyboard tests. Firefox and Safari/WebKit were
  not run (Chromium only). Real phones/tablets not used (viewport emulation).
- Updates install progress, system repairs and the « Libérer la carte graphique » action were rendered but not
  triggered against real installers/models.
- Tutor quality (hints, explain-back) depends on the real models; in demo the scripted brain answers.
- Research layer: grounded answers, literature search, blueprint extraction, article drafts and conjecture proposals
  ran only against the demo's scripted brain and recorded HTTP answers; experiments were created and approved in the UI
  but **never run** in tests (a run starts a real Sage/Python kernel on the host); publication was exercised only up to
  the demo's `no_mathlib_pin` refusal (no manifest, preview or push against a real workspace / GitHub); the PDF reader
  was checked on the demo's one-page PDF only (no long or scanned PDF, no annotation created from a mouse selection in
  a test — the highlight test uses the structure view).
- Self-update install / rollback / restart and system-component terminals were rendered, not triggered (the demo is
  not a managed install; opening a terminal would pop a window on the host).

## 10. Glossary, library, Calcul, Claude caps (session S-M)

- **Single source** of glossary content: `web/src/lib/lean/glossary.ts` (`GlossEntry {kind, cat, level, fr, en, lean?,
  example?, related?, decls?}`, `GLOSS_CATS`). The same object feeds the Glossaire screen, the editor hover help
  (`lookupGloss`) and is the in-app counterpart of `docs/manual/*/glossary.md` + `tactics.md` (every term of those
  pages is an entry). Examples and declaration names were compiled against Mathlib for Lean 4.36 (lean-current); a few
  names are recent (`Module.Basis`, `fun_prop`, `Module.End.HasEigenvalue`) and may be absent from the Lean 4.9
  workspace. Mathlib declarations are looked up on demand (`GET /api/lean/declaration`), dossiers using a term with
  `GET /api/glossary/uses`.
- New API module `web/src/lib/api/workbench.ts` (kept apart from `client.ts` for parallel sessions).
- Screens: `screens/Glossary.svelte`, `screens/Library.svelte`, `screens/research/Calcul.svelte` (route `/calcul`,
  project section), `screens/settings/ClaudeBudget.svelte` (inside Réglages › Modèles). Per-device conveniences in
  localStorage only: library grouping and view, glossary order.
- S-W: the glossary is browsed A–Z or « Par catégorie » (GLOSS_CATS order, easiest level first: `groupByCategory`);
  the library is filtered by domain, project, tag and status on top of « Ranger par » (`web/src/lib/library.ts`:
  `filterResults`, `groupResults`, `facets` — only values that exist are offered; with a tag filter a result is listed
  once). Domains: one list, `brain/leaderboard.DOMAINS`, used by the rankings and the library. Tests:
  `web/tests/unit/library.test.ts`.
- Layout: glossary 2 columns ≥ 900 px (category rail + list), select below; library cards/table + sticky detail
  ≥ 1024 px, detail above the list below; Calcul sheet + sticky assistant ≥ 1024 px, assistant collapsed on top below
  (single column on phones, no gutter < 600 px). Checked at 360 / 820 / 1440 px, light and dark
  (`docs/screenshots/v2/{glossary,library,calcul,settings-claude}-*.png`), axe 0 violation (`e2e/workbench.spec.ts`,
  `/calcul` added to `e2e/a11y.spec.ts`).
- Plots are shown with `<img>` from `/api/calcul/assets/{id}` (CSP `img-src 'self'`; SVG sanitised server-side and
  served with `sandbox` CSP); LaTeX outputs go through KaTeX (`renderMath`, trust off), never as HTML.

## 11. Article editor (session S-R, docs/ARTICLE.md)

- **Choice**: CodeMirror 6 (MIT, already in the bundle) used as a *live-preview* editor over the LaTeX source, not a
  ProseMirror/TipTap tree. The document the user types in IS the `.tex` file: visual mode only adds decorations
  (KaTeX maths, amsthm-style theorem boxes with numbers and the Lean state badge, `\cite`/`\ref` chips, figures,
  footnotes, bullets, hidden markers and markup) and reveals the raw LaTeX where the cursor is; « Source LaTeX »
  removes the decorations from the same EditorState (same selection, same undo history). Round trip is perfect by
  construction; unknown environments (TikZ, tables, algorithms…) are protected raw blocks shown as written. A
  ProseMirror model would have needed a lossy LaTeX ⇄ tree conversion.
- Files: `lib/article/latex.ts` (pure scanner: maths, environments, commands, markers, numbering, KaTeX macros —
  unit-tested), `lib/article/editor.ts` (lazy chunk: decorations, math live-preview tooltip, suggestions as track
  changes, compile diagnostics, completion of commands/environments/labels/citation keys, protected managed regions,
  Vim/Emacs keymaps loaded on demand), `lib/article/prefs.svelte.ts` (per-device personalisation),
  `lib/api/article.ts`, `screens/research/Article.svelte` + `article/ArticleOptions.svelte` (side drawer) +
  `article/ArticleDialogs.svelte`, `styles/article.css`. `PdfView` gained an optional `onpoint` (double-click →
  SyncTeX inverse search).
- Layout: toolbar (title · save state · Visuel/Source · Insérer · Suggestions · Aperçu PDF · Compiler · ⋯), outline
  (sections = files, sub-headings of the current file), writing surface set like a page (Source Serif, 62/72/92 ch),
  PDF preview on the right ≥ 1100 px (or below), diagnostics above the PDF with one-click fixes. Phone (< 760 px):
  visual mode only, single column, outline as a select, PDF opened in a tab. The selection shows a small assistant
  toolbar (Réécrire, Raccourcir, …, Vérifier avec Lean, Exemple avec Sage); results come back as suggestions.
- New dependencies: `@replit/codemirror-vim` 6.4.0, `@replit/codemirror-emacs` 6.1.0 (MIT, lazy chunks, loaded only
  when chosen), `@codemirror/search` 6.7.2 (MIT, their peer; also gives Ctrl+F). `npm audit --omit=dev`: 0.
- Tests: `tests/unit/article.test.ts`, `e2e/article.spec.ts` (visual/source/autosave/insert, compile + fix, drawer,
  versions, Overleaf, assistant suggestion accepted inline, phone, dark; axe on each state) →
  `docs/screenshots/v2/article-*.png`. `e2e/global-setup.ts` now starts the demo server with a temporary
  `MADALEAN_HOME` (it used to inherit the real prefix and therefore the user's tectonic cache).

## 12. Phone and tablet layouts (session S-X, 2026-11-22)

Goal: the APK (Flutter web view) and the AppImage (Tauri) on phones and tablets — « épuré, complet, sans chevauchement ».
Same UI, one rule as in Mahay (`~/GitHub/mahay-adaptive-layout`, DECISIONS D23): **the layout depends only on the
window width** (no « tablet mode » setting), so rotation and split screen just work. Size classes: phone < 600 px,
bottom bar < 768 px, drawer rail < 1024 px, permanent rail ≥ 1024 px, side thread ≥ 1280 px. Touch sizes follow
`(pointer: coarse)` (the shells and remote browsers on phones/tablets), so the desktop keeps its denser controls.

Patterns adopted (and where they come from):
- **Bottom navigation on phones** (already there) + **bottom sheets** instead of drop-downs: every `Menu` (« ⋯ »,
  « Insérer », « Plus d'actions ») opens as a sheet above the bottom bar below 768 px — the same width as the bottom
  bar, so wherever the bar is shown menus are sheets and from 768 px they are popovers (thumb reach, never cut by the
  screen edge; capped at 560 px and centred on wide phones and small tablets); every `Dialog` becomes a full-width sheet anchored to the bottom with its actions above the system bar
  (TONTOLO's modal bottom sheets, Mahay's compact dialogs).
- **Overflow menu for cramped toolbars**: Calcul's « Ouvrir dans JupyterLab », « Télécharger (.ipynb) », « Redémarrer
  le noyau », « Effacer les sorties » go into one « ⋯ » on phones (header + toolbar: 5 rows → 2). The dossier, the
  article editor and the cells already used overflow menus.
- **List → detail, one at a time** below 900 px for Notes and Conjectures (like Réglages): the list hides when an item
  is open, a « ‹ Notes » / « ‹ Conjectures » link goes back; two panes side by side from 901 px (tablet landscape).
- **Scrolling strip** instead of a wrapped grid (Mahay's command bar): the glossary's A–Z index on touch screens, only
  the letters that have entries, 44 px each.
- **On-screen keyboard** (`web/src/lib/ui/keyboard.ts`, unit-tested): the viewport asks for
  `interactive-widget=resizes-content` (the Android shell already uses `adjustResize`); when a field is focused and the
  page lost ≥ 22 % of its height, `html[data-kb=open]` hides fixed bars marked `.kb-hide` (bottom navigation)
  and the caret (or the top of a tall editor) is scrolled just above the keyboard; rotation resets the reference height.
  Once open, the state stays open while the page is still short even if the focus left the field (a menu was
  opened over the keyboard), and `--kb-inset` / `--kb-vh` give the keyboard's height when the browser draws it over
  the page instead of resizing it (visual viewport only); menu sheets, phone dialogs and the article's suggestions
  sit on `--kb-inset`.
- **Safe areas** (sampana): `viewport-fit=cover` + `env(safe-area-inset-*)` on the top bar, the page, the drawer, the
  bottom bar, sheets and toasts (landscape notches in a browser; the Android shell also wraps the web view in SafeArea).
- **Touch targets ≥ 44 px** on touch screens, everywhere: disclosure headings (`summary`), selects, checkboxes and
  radios (22 px box in a 44 px label where needed), text-like buttons (« Voir directement la preuve », passage links),
  tag chips, outline items (their tools are always visible on touch — no hover there), help contents, contact links.
- **Top bar never squeezes the logo**: brand fixed at 44 px; the project picker and the privacy pill shrink instead
  (at 768 px the logo had been crushed to 6–18 px).
- **Nothing under the bottom bar**: the article's suggestions panel sits above it.
- **First-run tour**: below 1024 px it is a card in the page flow, above « Que voulez-vous prouver ? » (it pushes the
  page down instead of covering it); from 1024 px it floats in the bottom-right corner and the page gets extra bottom
  room so everything can be scrolled clear of it (hidden while an on-screen keyboard is up).

Verification: demo server on spare ports with a temporary config, built-in browser at 360×800, 412×915 (touch
emulation), 768×1024, 1024×1366, 1366×1024, 1440×900, light and dark. A DOM audit (in-page script: horizontal page
scroll, elements past the right edge, visible interactive elements < 44 px on touch, overlapping visible controls in
the same layer) over 35 routes (every screen, the 11 settings sections, a dossier at each step, a source, a note, a
conjecture). Before: at 360 px 1 horizontal scroll (article editor, 4 px), 5 real touch-size problems on most screens
(summary 21–32 px, checkboxes 13 px, letters 32 px, links 24–31 px), the tour hiding the statement field, a crushed
logo at 768 px, three rows of Calcul buttons. After: 0 horizontal scroll, 0 overlaps, 0 targets < 44 px at 360 and 412
px (the only remaining audit hits are inline links that wrap inside manual paragraphs — WCAG inline exception — and
graph node labels at desktop size). Screenshots were taken during the session but not committed.

Not verified: real devices (only emulation; the keyboard was simulated by shrinking the viewport with a field focused),
WebKitGTK of the AppImage on a touch tablet, TalkBack.

### Fixes after S-X (session S-AA, 2026-11-22)

Three display defects reported by S-X are fixed (none remains open from that list):
1. **The tour covered the home screen** at 360/412 px (statement field) and 768 px (« Importer un .tex », the send
   hint, the examples): a fixed card in a corner, with 300 px of extra page room as the only remedy. Now the card is
   part of the page below 1024 px (`App.svelte` renders it at the top of `main`, `Tour.svelte` positions it only from
   1024 px) — nothing can sit under it; « Passer la visite » still dismisses it.
2. **Gap between a menu sheet and the on-screen keyboard**: tapping « ⋯ » moves the focus out of the field, so
   `keyboard.ts` dropped `data-kb` at once while the keyboard was still up; the bottom bar came back above the keyboard
   and the sheet sat on top of it (60 px + margins of empty band). Now the keyboard state is kept while the page is
   still short (`keyboardOpen(…, wasOpen)`), the sheet is placed on `--kb-inset` (0 when the page is resized, the
   keyboard height when it is drawn over the page) and limited to the visible height; when the keyboard goes down
   the bottom bar returns and the sheet moves above it. Editor bubbles (formula preview) are hidden while a sheet is
   open (they used to show through it).
3. **Menus between 600 and 767 px**: popovers there while the bottom bar is shown (a popover from a toolbar could run
   under the bar, a sheet rule existed only below 600 px). Menus now switch at 768 px like the bottom bar, the toasts
   and the tour; dialogs keep their own rule (sheet below 600 px, centred window above, which fits from 600 px).

Tests: `e2e/responsive.spec.ts` (32 cases) — tour vs statement field and send button at 360, 412, 600, 700, 768,
1024 px light and dark; sheet below 768 px / popover from 768 px at the same widths; menu opened with the keyboard
up (simulated by shrinking the viewport with the editor focused) at 360–700 px sits on the keyboard, then above the
bottom bar once it goes. Unit tests for `keyboardOpen(…, wasOpen)` and `keyboardInset`. `SHOTS_DIR=… npx playwright
test e2e/responsive.spec.ts` saves a screenshot of every case (checked by eye, not committed); `MADALEAN_E2E_STATIC`
runs the e2e suite against a build made elsewhere (`npx vite build --outDir …`) without touching `madalean/static`.

## 13. Collapsible panels around the article (session S-AD, 2026-11-22)

The article editor is full-bleed and every panel around the text folds away:

| Panel | Toggle | Shortcut | Remembered (per device) |
|---|---|---|---|
| App navigation rail (≥ 1024 px) | ☰ in the top bar (`aria-expanded`) — below 1024 px the same button opens the drawer | Ctrl+Maj+1 | `madalean.layout` (`lib/ui/layout.svelte.ts`): one choice for the app, one for the article (hidden by default there) |
| Project panel (Plan · Éléments) | panel icon at the left of the article toolbar, « ‹ » in the panel | Ctrl+Maj+2 | `aprefs.side`, `sideTab`, `fileTree`, `closedGroups`, `openFolders` |
| PDF preview | « Aperçu PDF » (`aria-expanded`) | Ctrl+Maj+3 | `aprefs.preview` |
| Focus mode | « Concentration » (`aria-pressed`) | Ctrl+Maj+F | `aprefs.focus` — hides rail, panel and preview, text column 92 ch |

Shortcuts use `KeyboardEvent.code`, so they are the same on AZERTY and QWERTY. Layout by window width (§12):
≥ 1280 px panel (256/272 px) · text · preview (38 %); 1024–1279 px text · preview, the panel is a drawer over the
text (beside the text when the preview is off); 768–1023 px panel and preview are drawers (left / right) opened on
demand, scrim click or Escape closes them and the focus returns to the toggle; < 768 px the panel is a bottom sheet
above the bottom bar (on `--kb-inset` with the keyboard up), PDF opens in a tab. Drawers and sheets are never
remembered open. Toolbar labels become icons when the toolbar is narrower than 1200 px (container query, so also
when the rail is shown), names kept for screen readers and tooltips. Default text column: ≈ 725 px at 1440, ≈ 600 px
at 1366 and 1024 (rail hidden on the article by default).

Verified with Playwright screenshots at 360, 768, 1024, 1366 and 1440 px, light and dark (no horizontal scroll), and
`e2e/article.spec.ts` (collapse + shortcuts + reload, drawers at 1024/768, sheet at 360, item kinds with icon + label,
Calcul cells, insertion, file tree toggle; axe on each state). Not verified: drag-and-drop of an item onto the text
(only « Insérer » is tested), real touch devices.

## 14. Refonte S-AK (2026-11-22, DECISIONS D43)

User request (FR): « le logo est à la fois le menu déroulant et le retour à l'accueil, les boutons du dessous ne sont
pas nécessaires ; le menu déroulant sur le nom de projet ou dossier, en texte complet ; le nuage de modèle affiche
aussi les ressources matérielles et les tokens dépensés ; une interface simple mais complète, sans redondance ni
superflu ; Entrée pour lancer, Maj+Entrée pour aller à la ligne ; un volet ouvert se ferme en cliquant ailleurs ;
enregistrement automatique de chaque dossier et modification ».

### 14.1 Audit (v2.0.0, before any change)

Inventory of every navigation element, measured on a demo server at 1440, 820 and 390 px, light and dark.

| # | Element | Where (width) | Problem found | Decision |
|---|---|---|---|---|
| 1 | ☰ button | top bar, all widths | a 4th way to reach the same places (rail ≥ 1024, drawer < 1024); does not say what it opens | **removed**: the logo opens the menu |
| 2 | Logo / wordmark | top bar | only a link to `/`; Home is also in the rail (« Dossiers »), the bottom bar (« Accueil ») and Ctrl K | **logo = menu button** whose first entry is « Accueil »; a second click on the logo while the menu is open goes home |
| 3 | Project `<select>` | top bar (max 240 px, « Tous les pr… » at 390 px) and again on the project hub | names truncated; two switchers; « Nouveau projet » hidden as an option of a select; no way to switch dossier there | **one context switcher** « Projet › Dossier », full names (two lines when needed, tooltip), panel with the projects *and* the dossiers of the chosen project; the hub's copy removed |
| 4 | « Qui reçoit quoi » pill | top bar (280 px: « Auto : en ligne (local seulement sans I… ») | a long sentence always visible and cut; nothing about cost or the machine | **status button** (icon + two words + running count); panel: mode and model of each running job, CPU / RAM / GPU, tokens and cost (today, this month, this request), running jobs with Stop, link to Réglages › Modèles |
| 5 | Activity button + floating drawer | top bar ≥ 768 | same list as the Activité screen and the bottom-bar tab; a third panel in the top bar | **merged** into the status panel (running jobs + « Toute l'activité ») |
| 6 | Apprendre / Recherche switch | top bar ≥ 768 **and** in the drawer < 768 | duplicated; 210 px of top bar for a rarely changed setting | **moved** into the logo menu (one radio pair) |
| 7 | ⚙ Réglages | top bar ≥ 768, rail bottom, bottom bar | three entries | **logo menu** only (+ Ctrl K) |
| 8 | Search (Ctrl K) | top bar ≥ 768 only | absent on phones | **kept** at every width (icon only below 1280 px) |
| 9 | Rail: project sections (9 links, 2 columns) | rail ≥ 1024, drawer below | the project's sections hidden behind ☰ on tablets and phones | **project bar**: one row of sections under the top bar on project screens, every width (scrolls on phones); not shown on global screens |
| 10 | Rail: dossier list | rail ≥ 1024, drawer below | the only full dossier list; behind ☰ below 1024 | **moved** into the context switcher (search, status, lemmas) and the « Dossiers » page (Home: the full list instead of the 6 most recent) |
| 11 | Rail bottom links: Activité · Bibliothèque · Glossaire · Carnet · Aide · Réglages | rail ≥ 1024, drawer | duplicate the top bar (Activité, Réglages) and the bottom bar (Activité, Aide, Réglages) | **removed**: in the logo menu |
| 12 | Phone bottom bar: Accueil · Projet · Activité · Aide · Réglages | < 768 | duplicates the drawer; takes 56 px of every phone screen; menus had to become sheets « above the bar » | **removed**: logo menu + project bar |
| 13 | Project hub `/projet` | phone tab « Projet », palette | 9 cards repeating the rail, a second project switcher; the project's title / description editable nowhere | **project page**: title and description edited in place (autosaved), counts as links, project search, conductor instruction; opened from the context switcher |
| 14 | Dossier « Renommer » (« ⋯ » → dialog → « Enregistrer ») | dossier header | three steps and a save button for a title | **title edited in place** (click the title), autosaved |
| 15 | Statement « Enregistrer et retraduire » / « Enregistrer seulement » / « Annuler » | step 1 | « Enregistrer seulement » is a save button | **autosaved while typing**; « Retraduire » kept (an action), « Terminer » closes the editor |
| 16 | Profile « Enregistrer » | Réglages › Profil | the only setting with a save button | **autosaved** |
| 17 | Calcul cells | Calcul | saved on blur only; Maj+Entrée = run, Entrée = new line | **autosaved while typing**; Entrée runs, Maj+Entrée new line (the user's wish), Tab indents |
| 18 | Conjecture experiment code | Conjectures | saved only by « Enregistrer le code » | **autosaved** (the edit still drops the approval: the run button asks again) |
| 19 | Sending inputs (follow-up, Q&A, explain-back, hints, conductor, Lean correction, Calcul request, notebook assistant, new problem) | everywhere | mixed rules (Ctrl+Entrée in most, Entrée in two), no hint in several | **Entrée sends, Maj+Entrée new line**, one discreet hint under each |
| 20 | Menus, popovers, status pill, activity drawer | everywhere | outside click closed `Menu` only; the pill and the activity drawer stayed open | **one `dismiss` action**: outside click / tap and Escape close every non-modal panel, focus back on its button |

Kept as they are (checked, not redundant): the dossier steps (Énoncé · Traduction Lean · Preuve · Plan), the Help
link next to each title (contextual), the article editor's own panels (§13, already outside click / Escape), native
dialogs (backdrop click and Escape close them; what was typed lives in the screen that opened them and is shown
again), the first-run tour, the demo band and the connection banner.

### 14.2 The new model

```
Top bar:      [Madal∃an ▾]  [📁 Projet › Dossier ▾] ……………… [🔍 Chercher Ctrl K] [☁ Auto · 2]
Project bar:  Dossiers · Sources · Notes · Graphe · Blueprint · Article · Conjectures · Calcul · Publier   (project screens)
Main:         full width — no rail, no drawer, no bottom bar
```

- **Logo menu** (`components/AppMenu.svelte`, ARIA menu button: `aria-haspopup`, `aria-expanded`, arrows / Home /
  End, Escape and outside click close it, focus back on the logo): Accueil · the project's sections (only when the
  project bar is not on screen) · Activité (count) · Bibliothèque · Glossaire · Carnet · Aide · Réglages · Apprendre /
  Recherche (`menuitemradio`) · Barre du projet (`menuitemcheckbox`, Ctrl+Maj+1). A popover under the logo; a sheet
  from the left edge on phones. A second click on the logo while the menu is open goes home.
- **Context switcher** (`components/ContextSwitcher.svelte`): the project name and, in a dossier, the dossier title,
  in full — wrapping on two lines when needed, each part with a tooltip. Panel: projects (full names, « Tous les
  projets », « Nouveau projet… », « Vue d'ensemble ») beside the dossiers of the highlighted project (search, live
  status, lemmas nested). Picking a project makes it current; picking a dossier opens it.
- **Status button** (`components/StatusPanel.svelte`): cloud (online) / chip (local) icon, the mode in two words, the
  number of running jobs. Its panel is sampled every 3 s *only while open* (`GET /api/usage`); nothing is polled when
  it is closed.
- **Project bar** (`components/ProjectBar.svelte`): the current project's sections; Ctrl+Maj+1 hides / shows it
  (remembered per device; hidden by default in the article editor, as the rail was; hidden in its focus mode).

### 14.3 Keyboard rules

| Input | Entrée | Maj+Entrée | Other |
|---|---|---|---|
| New problem (words or Lean), follow-up request, Q&A, explain-back, hints, conductor instruction, Lean correction, Calcul « Demande », notebook assistant, new conjecture | sends | new line | Ctrl+Entrée sends too; Entrée is ignored while an IME composes (`isComposing`) |
| Calcul code cell | runs the cell | new line | Tab / Maj+Tab indent / dedent; Ctrl+Entrée runs too; Échap → command mode |
| Lean proof editors (manual proof, exercise fix) | checks with Lean | new line | — |
| Long-form editors: article (visual and LaTeX source), notes body, Calcul text cells, profile, BibTeX paste, experiment code, merge result, plan node fields | new line / paragraph | new line | **exception on purpose**: writing several lines is the job there; Ctrl+Entrée keeps its own meaning (compile the article) |
| Single-line fields (titles, search) | validates / nothing (results are live) | — | — |

On touch-only screens (no mouse or trackpad: on-screen keyboards have no Shift+Enter) Enter stays a new line and the
field's button sends; the hint is hidden there. The hint « Entrée pour envoyer · Maj+Entrée pour aller à la ligne »
(`components/EnterHint.svelte`) sits under each sending field, small and muted (in Calcul it sits in the cell's
button row and shows while the cell has the focus, always laid out so nothing moves under the pointer). Shared code: `lib/ui/enter.ts` (`enterIntent`, `enterSubmit` action) and the
CodeMirror keymap in `lib/lean/editor.ts` (`enterSubmits`).

### 14.4 Panels close on an outside click

`lib/ui/dismiss.ts` (`dismiss` action): a `pointerdown` outside the panel and outside its button, or Escape, calls the
panel's close; when the focus was inside the panel it goes back to the button. Used by the logo menu, the context
switcher, the status panel, every `Menu` (« ⋯ », « Insérer », exports) and the article's suggestions panel. Native
`Dialog`s close on a backdrop click and Escape; their fields are bound to the screen that opened them, so reopening
shows what was typed; the plan's node editor saves when it closes instead of discarding.

### 14.5 Autosave

`lib/ui/autosave.svelte.ts` (`Autosave`): debounced (≈ 1 s after the last key), flushed on blur, before an in-app
navigation (router `beforeNavigate` hooks), on `pagehide` / hidden tab and on unmount; failures retried with backoff
(2, 4, 8… s, at most 30 s); a 409 keeps the user's text and says so. Indicator `components/SaveState.svelte`:
« Enregistré » / « Enregistrement… » / « Non enregistré — réessai » / « Modifié ailleurs » (polite live region).

| What | Endpoint | Before | Now |
|---|---|---|---|
| New problem draft (words, Lean, title) | localStorage `draft.new` | words and Lean | + title |
| Dossier title | `PATCH /dossiers/{id}` | dialog + Enregistrer | in place, autosaved |
| Dossier statement | `PATCH /dossiers/{id}` (`problem`) | « Enregistrer seulement » | autosaved while editing |
| Follow-up request draft | localStorage per dossier | lost when leaving | kept until sent |
| Notes (title, body) | `PATCH /research/notes/{id}` (`base_rev`, merge) | debounced, nothing on leave | + flush on leave / unload, retry, shared indicator |
| Article | article files (`hash`) | own autosave | + flush on leave / unload |
| Calcul cells (code, text) | `PATCH /calcul/…/cells/{id}` | on blur | debounced while typing + blur + leave |
| Conjecture experiment code | `PATCH /research/conjectures/{id}/experiments/{x}` | button | autosaved |
| Plan node | `PATCH …/plan/nodes/{id}` (`base_rev`) | « Enregistrer » | saved when the editor closes |
| Project title / description | `PATCH /projects/{id}` | not editable | edited on the project page, autosaved |
| Settings | `PATCH /settings` | immediate except Profile | Profile autosaved too |
| Library domain / tags | `PATCH /library/…` | immediate | unchanged |
| Glossary | — | read-only (built in) | unchanged |

Explicit buttons kept because they are not « save »: Traduire et prouver, Retraduire, Vérifier avec Lean, Exécuter,
Approuver et lancer, Publier, Compiler, Accepter une suggestion, the merge view's choice, and API keys (« Enregistrer
la clé » checks and tests the key, then empties the field: a secret is never autosaved).

### 14.6 Tests and screenshots

- `web/tests/unit/sak-ui.test.ts`: Enter intent (IME, Alt, Shift, Ctrl), newline-with-indent and Tab indent / dedent,
  outside test, Autosave (debounce, flush, change during a save, backoff retry, 409 conflict).
- `web/e2e/sak.spec.ts`: logo menu (Accueil first and focused, every destination, arrows / End / Escape → focus back,
  mode radio, second click → home, sections only when the bar is hidden, Ctrl+Shift+1); outside click and Escape on
  the logo menu, the switcher, the status panel and a « ⋯ » menu; context switcher (projects beside their dossiers,
  full title + tooltip); status panel (content, polled only while open, stops when closed); Enter / Shift+Enter on
  the new problem and the follow-up request; Calcul cell (Shift+Enter indentation, Shift+Tab, autosave without blur
  + reload, Enter runs); autosave + reload of dossier title, statement, project description, profile; a failing save
  shows « Non enregistré — réessai » and recovers; axe with each panel open at 1440 and 820 px, light and dark, and at
  390 px (sheets, 44 px targets, no bottom bar). Older specs updated (phone, responsive, article, parallel, sync,
  research, screens).
- `tests/test_usage_status.py` (tally, persistence, `GET /api/usage` after a real request) and
  `tests/test_autosave_persist.py` (every autosaved field read back after a server restart).
- Screenshots: `docs/screenshots/v2/{phone,tablet,desktop}-{light,dark}-{home,menu,switcher,status}.png` (+ the
  existing sets, regenerated); the manual's images copied from them.

## 15. « Premiers pas », the first-run assistant (session S-AQ, 2026-11-22, DECISIONS D49)

User request (FR, summarised): at the first opening on the host, Madalean guides the whole starting configuration —
tools (installed / missing, reuse the system's SageMath or LaTeX or Madalean's own copy, install or repair with live
progress), local model yes/no and which one, API keys one card per provider (« Tester », never autosaved, on the
host only), Hugging Face for Goedel-Prover, Claude as conductor and its caps, modes, automatic vs manual
behaviours, pairing, a final checklist; each step linked to its manual page.

### 15.1 Where it lives

| What | Where |
|---|---|
| Route | `/premiers-pas/:step?` (`routes.ts`), rendered by `App.svelte` **full screen** (no top bar): own header (wordmark, « Premiers pas · étape i sur 10 », « Plus tard »), an orange progress line, a stepper (`nav` « Étapes », `aria-current="step"`, ✓ for visited steps; one scrolling row of numbers below 1024 px), the step, « Précédent » / « Passer cette étape » / « Suivant » (« Terminer » at the end) |
| Steps | `screens/setup/Step{Welcome,Tools,Local,Keys,Hf,Claude,Modes,Auto,Pair,Done}.svelte`, one chunk each; shared provider card `ProviderKey.svelte` (wraps Réglages' `KeyForm`), Home card `SetupReminder.svelte` |
| Logic | `lib/setup/wizard.ts` (pure: steps, help pages + anchors per language, resume, auto-open rule, reminder rule, model choice, recommended reuse, checklist) — `tests/unit/setup-wizard.test.ts` |
| State | `lib/setup/state.svelte.ts`: `GET /api/setup/wizard` once at the start of the web app **on the host** (`setupBoot`, after `app.boot()`), `setup.wizard` events; `lib/setup/api.ts` typed client |
| Hooks | `App.svelte` (full-screen branch + `setupBoot`), `AppMenu.svelte` (« Premiers pas » after Aide, host only), `Home.svelte` (`<SetupReminder />`), `Settings.svelte` (link above the sections, host only) |

### 15.2 Rules

- **Opens by itself** only when: the request is local (host), the route is Home, `settings.wizard_done === false`
  and the server's `auto` is true (false after « Plus tard » / « Terminer »). An update from 2.0.0 opens it too, once
  (the user's choice, 2026-11-22). A deep link is never redirected. Paired devices: no
  automatic opening, no menu entry, no Home card, `/premiers-pas` says it is for the host; the API is host-only.
- **Progress on the server** (`first-run.json`): each move saves `step` + `visited`; opening `/premiers-pas` without a
  step resumes there (also from the browser's back / forward). « Plus tard » = `wizard_done: true`; the **Home card**
  (« Reprendre » / « Ne plus afficher ») stays until « Terminer » (`completed`).
- **Saving** follows D43: radios, switches and caps are saved when they change (`PATCH /api/settings`,
  `POST /api/setup/reuse`, `PATCH /api/setup/wizard` for the local-model choice); **keys** only by their own
  « Enregistrer » (the form submits on Enter), then tested; a saved key has « Tester » again
  (`POST /api/models/test`, `/api/search/test`). No panel opens inside the assistant, so no outside-click rule
  applies; Escape does nothing (it is a page, « Plus tard » leaves).
- **Real option names only**: `sage_source`, `tex_engine`, `mode`, `hf_goedel`, `conductor`, `conductor_cap_usd`,
  `claude_reinforce`, `claude_cap_proof_usd`, `claude_cap_month_usd`, `experiments_auto`, `parallel_stages`,
  `lean_warm`, `pause_after_translation`, `check_updates`, `updates_auto`, `language`; Apprendre / Recherche is the
  per-device preference of the logo menu.
- **Recommendations** come from the install engine (`assistant.recommend()` over the machine check: graphics
  memory, RAM, SageMath version + kernel, TeX Live), shown as a « conseillé » badge and the reason in an
  orange-ruled note; options that cannot work here are disabled with the reason (and refused by the server).
- **Components**: « Installer » / « Installer maintenant » / « Mettre à jour » call `POST /api/deps/{c}/install`;
  `deps.progress` events drive a progress bar (phase translated, percentage); a running install started elsewhere
  is picked up from `GET /api/deps`. bubblewrap stays a command for the user to type (copy button): Madalean never
  uses sudo.
- **Local models**: none / prover / all with the size still to download (files already in `~/models` count as
  present); « Télécharger » → `POST /api/setup/models`, progress `setup.models`, « Arrêter le téléchargement »;
  refused in Local mode and in the demo.
- **Help**: each step's « Aide » opens the in-app manual at the matching heading (anchors from
  `docs/manual/index.json`, one per language; a unit test checks they exist).

### 15.3 Accessibility and layouts

`main` with the step's `h1` (focused on each move by the router), `nav` « Étapes » with `aria-current="step"` and
« déjà vue » for screen readers, every choice a real radio in a `fieldset`/`legend`, progress bars
(`role="progressbar"`, values), polite live regions for key tests, installs and downloads. Colours are the theme
tokens (light / dark), orange only as decoration (progress line, reason rule, Home card top border; BRAND.md).
Phones: the stepper is a scrolling row of numbers (current step labelled and kept in view), 44 px targets, no
horizontal scroll (checked at 390 px). axe (WCAG 2.1 AA) clean on every step tested at 1440 px light and 390 px dark.

### 15.4 Tests and screenshots

- `tests/test_setup_wizard.py`: wizard progress (host only, validation, merge, persisted across a restart, « Plus
  tard », resume, completion), opens once after an update with existing dossiers, reuse checked against
  fake system Sage / TeX, local-model download with a fake downloader (progress events, Local mode, busy, nothing
  missing), refused in the demo.
- `web/e2e/setup-wizard.spec.ts`: first start on the host opens it, a deep link does not, a paired browser never
  sees it; skip, « Plus tard », Home card, resume from the card, the logo menu and Réglages, « Ne plus afficher »;
  each step's controls (reuse choice persisted, local-model choice persisted, key save + « Tester », cap saved,
  mode and Apprendre / Recherche, a behaviour switch), « Terminer » hides it; phone + dark: no horizontal scroll,
  axe, Enter in a key field saves it explicitly. `e2e/global-setup.ts` marks it finished for the other specs.
- `web/e2e/wizard-screens.spec.ts` (project `screens`): `docs/screenshots/v2/wizard-<step>-desktop-light.png` (10),
  `wizard-{welcome,tools,keys,claude,done}-desktop-dark.png`, `wizard-{welcome,tools,local,keys,done}-phone-light.png`,
  `wizard-home-card-desktop-light.png`; `docs/manual/img/wizard-tools.png` copied from them.

## 16. Phones: open time, batched updates, unsent text kept (S-AP, 2026-11-22, DECISIONS D48, TODO B16)

Measured with `scripts/dev/phone_perf.mjs` (production build, demo server, phone emulation, 4× CPU, 150 ms RTT,
1.6 Mbit/s); before / after numbers in docs/PERFORMANCE.md « Interface sur téléphone (S-AP) ».

**Loaded on use, not on start**

| What | Before | Now |
|---|---|---|
| KaTeX + its CSS (≈ 270 kB min.) | with `lib/md.ts`, i.e. before the first paint of every screen but Réglages | `lib/katex.svelte.ts`: on the first formula shown; meanwhile the TeX source (`.math-pending`), then reactive views render again. Calcul and the dossier screen start it at once (they always show formulas); the article editor refreshes its math widgets when it arrives |
| Language catalogues | French and English in the entry | French in the entry (source and fallback); English its own chunk — awaited before mounting on an English device, or loaded on a switch (`i18n.set` returns a promise; the last language asked for wins) |
| Screen chunk | requested after `GET /state` answered | requested together with it (`App.svelte`) |
| CodeMirror (≈ 110 kB br) | fetched and built right after mounting | built when the browser is idle (≤ 1.5 s) or at once when its plain field is focused (`CodeEditor.svelte`); the plain field shows the text meanwhile |
| Proof plan (tree, map, outline) | in the dossier chunk | own chunk, on the « Plan » step (prefetched when idle) |
| Command palette, first-run tour | in the entry | own chunks; the palette on its first opening or when idle |
| Markdown renderer on Home | via the .tex import dialog | `LazyMd` there too: Home's first paint needs no Markdown |

Idle prefetch (`lib/ui/idle.ts`): after the screen is on screen and the browser is idle, the likely next screen
(Home → dossier, dossier → Home, Sources → reader, project → Home) and the palette; never on Save-Data or 2G.

**One render per burst**: socket messages are queued and applied together at the next animation frame
(`lib/store/coalesce.ts`, `FrameBatcher`; 100 ms timer when the tab is hidden), in order, through the same sequencer;
streamed text is flushed in that same frame. `app.activeJob` / `lastJob` / `activeJobs` read one derived index
(one pass over the jobs per change) instead of each dossier row scanning every job. `app.batchStats` shows the
batching (perf page, tests).

**Unsent text kept per device** (`lib/ui/drafts.svelte.ts`: `keepDraft(key, get, set)`, `loadDraft` / `saveDraft` /
`clearDraft`, localStorage `madalean.draft.*`, the store of the S-AK new-problem and follow-up drafts). Sending
empties the field, which removes the draft.

| Field | Draft key | Dropped |
|---|---|---|
| Calcul « Demande » of a request cell | `calcul.<project>.<doc>.<cell>` | when it becomes the cell's prompt (« Écrire le code ») |
| Grounded question (Sources, reader) | `qa.<project>.<scope>` | when asked |
| Explain-back | `explain.<dossier>.statement` or `.proof` | when sent |
| Hint ladder: « qu'avez-vous essayé ? », reflection | `hints.tried.<dossier>`, `hints.reflection.<dossier>.<proof>` | first hint received / when sent |
| Conductor instruction | `consigne.<project>` | when the run starts |
| Lean « Corriger l'énoncé… » (the field reopens) | `lean.correction.<dossier>` | when sent |
| Notebook assistant | `notebook.ask` | when sent |
| New conjecture (statement, motivation) | `conjecture.<project>[.motivation]` | when created |

Tests: `web/tests/unit/sap-perf.test.ts` (batcher order / one flush per frame / hidden-tab timer, stream flush,
job index = reducer helpers, lazy KaTeX placeholder then render, lazy English with a switch back winning, idle
prefetch once and never on Save-Data / 2G, drafts), `web/e2e/drafts.spec.ts` (Calcul « Demande » across a screen
change and a reload, dropped once sent; Q&A, Lean correction, new conjecture). Screenshots: every
`docs/screenshots/v2` image regenerated (`e2e/screens.spec.ts`, `plan-screens.spec.ts`, `article.spec.ts`,
`workbench.spec.ts`, and `extra-screens.spec.ts` for the glossary, library, Claude caps, Calcul 820 / dark / phone,
hint ladder and `plan-real-compact-proved-desktop-light.png` — the latter now the demo's richest plan (« Le carré
d'un entier pair est pair », 7 nodes, 3 of 5 lemmas proved: the demo data has no fully proved plan), the user's own
« Fonction continue sur un compact » dossier being unavailable to a test server; the file name is kept for the
existing references).
