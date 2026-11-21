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
- **Hint ladder before the proof** (`HintLadder.svelte`): diagnosis first (« Qu'avez-vous essayé ? » + « De quelle aide
  avez-vous besoin ? concept / approche / étape »), then nudge → strategy → key lemma → next step → full proof. Each rung
  requires a one-sentence reflection on the previous hint (« Qu'est-ce que cet indice vous a appris ? ») — the skill's
  anti hint-clicking safeguard; the reflections are sent with the next request so the tutor builds on them. An honest
  escape stays available (« J'ai trouvé » / « Voir directement la preuve »). Progress is kept per device and per
  statement version. Hint prompts never contain the proof (unit-tested).
- **Explain it back** (`ExplainBack.svelte`): the learner writes first (minimum length), the tutor names what is right
  and asks *one* question about the weakest part, never rewrites the explanation; after three rounds it asks for a
  cleaner final version (explain-first interrogator's synthesis step). Offered on the Lean statement (« que dit cet
  énoncé ? ») and on the proof (« pourquoi marche-t-elle ? ») — self-explanation prompts placed at the points of highest
  conceptual density, not everywhere.
- **Faded worked example** (`Exercise.svelte`): from a proven dossier, the proof with its last *k* tactic lines replaced
  by `sorry` — fading from the end backwards — checked by Lean in strict mode; success unlocks « remove one more step »
  and asks « why does your step work? ». Level « whole proof » = independent practice (expertise-reversal: the learner
  can jump there directly).
- **Glossary and token meanings**: hover (desktop) or tap (phone) any Lean token to see its meaning in the learn
  panel; a bilingual glossary screen with the abbreviation table.
- **Research mode** removes all of this from the way: proof shown at once, learn panel collapsed, denser spacing,
  keyboard shortcuts (`n` new, `/` palette).

## 2. Information architecture

```
Top bar:  [☰ dossiers] [Madalean] [Projet ▾]  ……  [Chercher Ctrl K] [Qui reçoit quoi] [Activité n] [Apprendre|Recherche] [⚙]
Rail (≥1024 px, drawer below): dossiers of the project, live status per row, lemmas nested; Activité, Bibliothèque,
                                Glossaire, Carnet, Réglages
Main:
  /                         Énoncé of a NEW dossier (natural language/LaTeX with live preview, or Lean), .tex import,
                            examples, recent dossiers
  /d/:id/(enonce|lean|preuve)  one dossier: stepper Énoncé → Traduction Lean → Preuve + thread (side ≥1280 px, below otherwise)
  /activite                 all jobs of all dossiers, resource slots, cancel each
  /bibliotheque             proven results (remove with undo, export .lean per workspace)
  /glossaire                Lean words + abbreviations
  /carnet                   JupyterLab iframe + assistant panel
  /reglages/:section        modeles · cles · appareils · espaces · mises-a-jour · profil · langue · apparence · carnet · systeme · a-propos
  /pair                     pairing screen (public; remote browsers)
  /__perf                   measurement page used by e2e/perf.spec.ts
Phone (<768 px): bottom navigation Accueil · Activité · Bibliothèque · Réglages; mode switch moves into the drawer;
                 the privacy indicator becomes an icon when idle, shows the model while work runs.
```

**Data layer** (`web/src/lib/`): `api/types.ts` (types of docs/API.md §5), `api/client.ts` (typed client, errors as
`ApiError{status, kind, body}`, 401 → `/pair?reason=auth`, exports as real URLs), `store/sequencer.ts` (seq / resume /
resync, pure), `store/model.ts` (reducer, pure), `store/connection.ts` (WebSocket with backoff, ping, online/offline,
visibility), `store/streams.ts` (token streams outside reactive state, one notification per frame),
`store/app.svelte.ts` (the single reactive store), `store/optimistic.ts`. Screens never hold their own copy of server
data: they read `app.m` and the server's events update it, which is what keeps every device in sync.

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

## 4. How to add a screen (for the research-layer session)

1. Create `web/src/screens/Sources.svelte` taking `{ params }: { params: Record<string, string> }`. Put an `<h1>` first
   (focus moves there on navigation).
2. Register it in `web/src/routes.ts`:
   `addRoute({ name: 'sources', pattern: '/sources/:id?', load: () => import('./screens/Sources.svelte'), nav: { label: 'nav.sources', icon: 'book', order: 5 } })`
   — it becomes its own chunk, appears in the rail, the command palette (and the phone bar with `phone: true`).
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

Bundle (gzip): entry `index` 20.6 kB + Svelte runtime/i18n/shared 49.7 kB = **~70 kB before first render**; screens are
separate chunks (Dossier 21 kB, Home 5 kB, settings sections 1–6 kB each); lazy: CodeMirror 102 kB, KaTeX+markdown
131 kB (+ KaTeX fonts). Everything together ≈ 330 kB gzip, within the ≈ 350 kB budget. Served pre-compressed
(brotli: 1133 kB raw → 323 kB).

| Measurement | Result |
|---|---|
| Time to interactive, phone 360×780, 4× CPU throttling, fast-3G (150 ms RTT, 1.6 Mb/s), **cold cache** (first heading visible + statement field accepts a key) | **2.6 s** (DOMContentLoaded 0.96 s; 185 kB JS transferred) |
| Same, **warm cache** (hashed assets are immutable) | **1.3 s** (target < 1.5 s) |
| 10 000-line stream (40 lines every 16 ms, faster than the server's 100 ms coalescing): frame times | p50 16.7 ms, p95 16.8, p99 16.8, max 16.8 ms, 0 frames > 50 ms |
| Typing in an input while that stream runs | keystroke → value: p50 8 ms, max 16 ms |
| Scrolling through the 10 000 lines (201 422 px, 600 px per frame) | p50 16.7 ms, p95 17.8, p99 18.5, max 19.2 ms — 60 fps |

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

## 7b. Test results (2026-11-21)

- `npm test`: 24 unit tests pass (sequencer: order, duplicates, gap → resume, boot change → resync with buffered events,
  overflow → resync; reducer; optimistic rollback; stream coalescing; i18n: same keys, same placeholders, every static
  key used exists, dynamic families complete, bilingual glossary/examples; abbreviations, token lookup, proof fading,
  hint prompt without proof, router, model labels). The sequencer test found and fixed a real bug (events after a
  server restart were dropped while the resync was pending).
- `npm run e2e` (+ screens + perf): 26 Playwright tests pass — full flow statement → Lean → proof → export (.lean
  download) → follow-up → version restore; pairing on the remote listener (no code, wrong code, good code, host-only
  lock, unlink); revoked device → back to pairing; parallel dossiers in the activity centre + cancel one; 409 busy;
  keys flow; models/mode/per-role + out-of-range refusal; language switch FR→EN→FR; devices code + QR; phone layout,
  token tap, touch targets; two contexts in sync live (create, status, rename, settings, delete + undo); reconnect after
  offline with missed events; Learn mode (hint ladder with required reflection, explain-back, faded exercise accepted
  by Lean) and Research mode (+ split into lemmas tree); axe on 14 screens × 2 themes; keyboard; 13 screenshot sets.
- `npm audit`: 0 vulnerabilities. `svelte-check`: 0 errors, 0 warnings.

## 8. Requests to the server (precise; the UI works around each today)

1. **Manual edits as versions** — `POST /api/dossiers/{id}/versions/{kind}` `{code, check?}` for `kind` = `proof |
   explanation | informal | notes` (user version, `source:"user"`, proof re-checked strictly, event + `dossier.updated`).
   *Today*: proof/explanation/informal-proof edits are local drafts on the device (`LocalDraft.svelte`, clearly
   labelled), checkable with `POST /check strict`, never overwritten without asking.
2. **Router explanations** — include `brain.explain(role, mode)` in `GET /models` (`roles[role].candidates[i].why` and
   `.score`). *Today*: the « Pourquoi ? » list shows rank, local/online, free/paid.
3. **Key test** — `brain.test(provider)` is missing, so `POST /models/test` always answers `ok:null,
   reason:"not_supported"`. Implement a cheap authenticated call (list models) returning `{ok, reason, models:n}`.
   *Today*: models unlocked are counted after `/models/refresh`.
4. **Declaration lookup** for hover/tap on Mathlib names — `GET /api/lean/declaration?name=&workspace=` →
   `{name, kind, signature, doc, module}` and `GET /api/lean/search?q=` (the S-B retriever has both). The editor already
   has the hook (`declLookup` in `lib/lean/editor.ts`). *Today*: built-in bilingual glossary only.
5. **Learn endpoints** — `POST /api/dossiers/{id}/hint {level, tried, help, reflections}` (server builds the prompt from
   the dossier, guarantees the proof is not leaked before `full`) and `POST /api/dossiers/{id}/explain-back {target,
   text, previous}`; plus storing learner progress server-side so it follows the user across devices. *Today*: both
   go through `POST /assistant` with prompts built in `lib/learn/tutor.ts`; progress is per device.
6. **Model key repr** — in demo (FakeBrain) runs, `Attempt.model` / `job.attempts[].model` contain a Python repr
   (`ModelRef(provider='fake', model_id='fake-prove', …)`) instead of `"provider:model_id"`. *Today*: `modelLabel()`
   parses it.
7. **Remote address for pairing** — `POST /pairing/start` should return the address other devices use
   (`remote_url`, e.g. `https://<host>.<tailnet>.ts.net:10500`, from `tailscale serve status`) so the QR link needs no
   typing. *Today*: the host types it once (remembered per device).
8. **Examples** — `GET /api/examples` (server `madalean/examples.py`) so both sides share one list. *Today*: duplicated
   bilingually in `web/src/lib/examples.ts`.
9. **CSP as a header** — send the CSP of §5 as a `Content-Security-Policy` header on `index.html` (meta cannot carry
   `frame-ancestors`); `X-Frame-Options: SAMEORIGIN` already covers framing.
10. **Assistant/WS ordering** — `assistant.*` events can arrive before the `202 {request_id}` reaches the client.
    *Today*: the store buffers unclaimed assistant events for 60 s. Optionally accept a client-chosen `request_id`.
11. **`POST /api/devices/self/forget`** (docs/SHELLS.md §8) — used by « Délier cet appareil »; the UI falls back to
    `POST /logout` while it returns 404/405/401.
12. **Job history in `dossier.updated`** — when a page is opened mid-job, earlier streamed text is rebuilt from
    `GET /jobs/{id}` `attempts[].raw` (proof attempts only). Single-call stages (understand, notes, explanation…) lose
    their partial text on reload; a `GET /jobs/{id}/stream?since=` (or keeping the last N tokens per job) would fix it.

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
- Tutor quality (hints, explain-back) depends on the real assistant model; the demo assistant echoes its prompt.
