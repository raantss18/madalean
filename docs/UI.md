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
- **Restrained palette**: cool paper `#F4F5F7`, ink text, indigo `#2C46AD` for links/focus, laterite only for the
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
Top bar:  [☰ dossiers] [Madalean] [Projet ▾]  ……  [Chercher Ctrl K] [Qui reçoit quoi] [Activité n] [Apprendre|Recherche] [⚙]
Rail (≥1024 px, drawer below): project sections (Dossiers · Sources · Notes · Graphe · Blueprint · Article ·
                                Conjectures · Calcul · Publier), dossiers of the project with live status, lemmas nested;
                                Activité · Bibliothèque · Glossaire · Carnet · Aide · Réglages
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
Phone (<768 px): bottom navigation Accueil · Projet · Activité · Aide · Réglages; mode switch moves into the drawer;
                 the privacy indicator becomes an icon when idle, shows the model while work runs.
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
| `--bg` / `--surface` / `--surface-2` | `#F4F5F7` / `#FFF` / `#ECEEF2` | `#13161D` / `#1A1E27` / `#222734` | page, panels, wells |
| `--text` / `--text-2` / `--text-3` | `#1A2031` 16.2:1 / `#464E62` 8.3:1 / `#5B6376` 6.0:1 | `#E8EAF0` 13.9:1 / `#B9BFCC` 9.1:1 / `#A0A7B6` 6.9:1 | text levels |
| `--ink` / `--on-ink` | `#1F2A44` / `#FFF` 14.3:1 | `#DFE4F2` / `#151A26` 13.7:1 | primary buttons, brand |
| `--accent` | `#2C46AD` 8.1:1 | `#A3B4FF` 8.4:1 | links, focus ring, selection |
| `--laterite` / `--laterite-mark` | `#B44A26` 5.3:1 / `#D9643F` | `#F0936D` / `#E0754E` | brand rule, current step |
| `--proved` on `--proved-soft` | `#1A7246` 5.2:1 | `#66D398` 7.7:1 | proved |
| `--failed` on `--failed-soft` | `#B42318` 5.6:1 | `#FF8E82` 6.9:1 | failed / errors |
| `--running` on `--running-soft` | `#8A5200` 5.7:1 | `#F3BF68` 8.7:1 | running / waiting |
| `--online` / `--local` (on soft) | `#6A3FB0` 6.0:1 / `#1A6A7A` 5.4:1 | `#C7A8FF` 7.5:1 / `#79D0DE` 7.8:1 | who receives what |
| `--line-strong` | `#858EA2` 3.3:1 | `#6D768B` 3.7:1 | input borders (non-text 3:1) |
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
  localStorage only: library grouping and view.
- Layout: glossary 2 columns ≥ 900 px (category rail + list), select below; library cards/table + sticky detail
  ≥ 1024 px, detail above the list below; Calcul sheet + sticky assistant ≥ 1024 px, assistant collapsed on top below
  (single column on phones, no gutter < 600 px). Checked at 360 / 820 / 1440 px, light and dark
  (`docs/screenshots/v2/{glossary,library,calcul,settings-claude}-*.png`), axe 0 violation (`e2e/workbench.spec.ts`,
  `/calcul` added to `e2e/a11y.spec.ts`).
- Plots are shown with `<img>` from `/api/calcul/assets/{id}` (CSP `img-src 'self'`; SVG sanitised server-side and
  served with `sandbox` CSP); LaTeX outputs go through KaTeX (`renderMath`, trust off), never as HTML.
