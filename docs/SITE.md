# Madalean site, reference manual and publication template (session S-F)

ARCHITECTURE §17: the GitHub Pages site has three roles and no showcase: **reference manual** (one Markdown source,
also the in-app help), **signed update channel**, **publication of verified work** (template used by « Publier »).
It plays no part in synchronisation.

| Path | Content |
|---|---|
| `docs/manual/{fr,en}/<id>.md` | the manual — single source of the site AND of the in-app help |
| `docs/manual/img/` | images of the manual (screenshots from `docs/screenshots/v2/`) |
| `docs/manual/index.json` | **generated** index of the manual for the web UI (commit it; CI fails when stale) |
| `site/build.py`, `site/madasite/` | generator (Python ≥ 3.10 stdlib) |
| `site/assets/` | `style.css`, `theme.js` (theme before first paint), `site.js` (theme toggle + search; optional) |
| `site/vendor/katex/` | KaTeX 0.19.1 (MIT): `katex.min.js` used at **build** time by `site/tools/katex_render.cjs`; css + woff2 fonts shipped |
| `site/vendor/fonts/` | Source Serif 4 / Source Sans 3 variable, latin subset (SIL OFL 1.1, licences included) |
| `site/updates/` | input of the update channel: `stable.json` + `stable.json.sig` written by the release process |
| `site/fixtures/stable.sample.json` | sample release, only for `--sample-release` previews |
| `site/publication/sample/` | sample project (5 nodes, one unproven) for reviewing the publication template |
| `site/publication/ci/` | workflow template + `make_badge.py` copied into a published repository |
| `scripts/build_site.sh` | build / `--preview` (serves on a free localhost port) / `--ci` |
| `.github/workflows/pages.yml` | builds on push to `main` and `v*` tags, deploys to Pages (Pages must be enabled by the owner) |

```
scripts/build_site.sh                 # site/_site + docs/manual/index.json, then checks
scripts/build_site.sh --preview       # + sample publication + install page with SAMPLE data, served on 127.0.0.1
python3 site/build.py publication --input DIR --out OUT      # render a project (DIR/publication.json + DIR/files/)
```

Output (`site/_site/`): `index.html` (neutral bilingual door: links only), `fr/` and `en/` (manual pages
`<id>.html`, `download.html` = install page, `search.html`), `updates/` (`stable.json`, `stable.json.sig`,
`madalean-release.pub.pem`, `index.html`), `assets/` (css, js, fonts, KaTeX css+fonts, generated `math.css`,
`search-fr.json`, `search-en.json`), `img/`, `404.html`, `.nojekyll`.

**Pages are strict-CSP friendly**: every page carries `<meta http-equiv="Content-Security-Policy" content="default-src
'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri
'none'; form-action 'none'; manifest-src 'self'">`; no inline script, no `style` attribute (KaTeX's inline styles are
moved at build time into generated classes in `assets/math.css`), no external script, font, stylesheet or image, no
tracker, no cookie. Everything is readable without JavaScript (JS only adds the theme toggle and search). Light/dark
follow the system, with a toggle stored in `localStorage` (`madalean-site-theme`).

## 1. Manual source format (`docs/manual/`)

One file per page and per language, same file name in `fr/` and `en/` (`id` = file name). French is written first;
English must be complete (the build fails when a page is missing in one language or when `order`, `section` or
`audience` differ).

```markdown
---
id: pairing
title: Relier un téléphone, une tablette ou un autre PC
order: 30
section: start
audience: all
summary: One sentence (shown in search results and as the page description).
---

# Title of the page

Text…
```

- `section`: `start`, `use`, `research`, `settings`, `help`, `reference` (titles in `site/madasite/layout.py`).
  Pages are ordered by section, then `order`.
- `audience`: `learner` | `researcher` | `all` (a badge is shown for the first two).
- Markdown subset (the UI renderer must accept exactly this): CommonMark blocks (ATX headings, paragraphs, block quotes,
  nested lists, fenced code, `---`), **GFM pipe tables** (a literal `|` in a cell, even in backticks, is written `\|`),
  inline code, `**strong**`, `*em*`, links, images, `<https://…>` autolinks, maths `$…$` (not when followed by a space
  or digit: `$5` is not maths) and `$$…$$` (inline or on its own lines). No raw HTML, no definition lists, no footnotes.
- Code: ```` ```lean ```` is highlighted at build time; ```` ```bash ```` is shown as is.
- **Links**: `other-page.md` or `other-page.md#anchor` (same language); `site:install` (install/download page),
  `site:install#verify`, `site:updates`, `site:search`; absolute `https://…` links (allowed hosts below).
- **Anchors** = slug of the heading: Unicode NFKD, combining marks dropped, lowercase, every character outside
  `[a-z0-9 -]` deleted, spaces → `-`, repeated `-` collapsed, trimmed; duplicates get `-1`, `-2`. Example:
  « L'appareil ne joint pas l'hôte » → `lappareil-ne-joint-pas-lhote`. The build fails on a broken page or anchor link.
- **Images**: `![alt text](../img/name.png)` (path valid on GitHub too). A missing file is rendered as a dashed
  placeholder « Capture d'écran à venir » with its file name and listed as a warning by the build.
- `<!-- verify after integration: … -->` marks a statement about a feature not checked on the real system; removed
  from the output, collected in `index.json` (`verify`) and counted by the build. The integrator checks each one and
  deletes the comment.

Pages (23 per language): index, install, first-run, pairing, tailscale · workflow, reading-lean, follow-ups, projects,
proof-plans · conjectures, sources, articles, notes, jupyter, publish · models-keys, updates, security ·
troubleshooting · glossary, tactics, shortcuts.

Images used (copied from `docs/screenshots/v2/`, demo mode, light theme): `home.png`, `devices-add.png`,
`pair-phone.png`, `lean-statement.png`, `proof-learn.png`, `hint-ladder.png`, `activity.png`, `settings-keys.png`.
No placeholder is used today. Screens of the research layer (sources reader, blueprint graph, plan tree, conjecture
log) have no image yet: add them to `img/` and reference them when S-D/S-E screenshots exist.

## 2. `docs/manual/index.json` — in-app help (for S-D)

Generated by every build, deterministic (no timestamp), committed. **The help panel must use this file (or the same
`.md` files), never its own copy of the texts.**

```ts
interface ManualIndex {
  schema: "madalean-manual/1";
  source: "docs/manual";
  site_url: "https://raantss18.github.io/madalean/";
  languages: ["fr", "en"];
  sections: { fr: {id: string; title: string}[]; en: {id: string; title: string}[] };   // display order
  site_links: Record<string, string>;      // site:<name> -> path relative to <site_url><lang>/ (e.g. install -> download.html)
  pages: ManualPage[];                      // grouped by language, in reading order
}
interface ManualPage {
  id: string; lang: "fr" | "en"; title: string; order: number;
  section: string; audience: "learner" | "researcher" | "all"; summary: string;
  source: string;                           // "fr/pairing.md"
  site_path: string;                        // "fr/pairing.html" (relative to site_url)
  headings: { level: number; text: string; id: string }[];   // in document order; id = anchor (slug rule above)
  images: { src: string; exists: boolean }[];                // src relative to docs/manual/ ("img/x.png")
  verify: string[];                         // integration notes (do not display)
  body: string;                             // Markdown, front matter and comments removed, image paths "img/x.png"
  text: string;                             // plain text for search
}
```

How the UI consumes it:
1. Import it at build time (`import manual from '../../docs/manual/index.json'`) and copy `docs/manual/img/` into the
   built assets (e.g. `madalean/static/help/img/`); or fetch it lazily — it is 340 KiB (≈ 70 KiB gzipped).
2. Pick pages with `lang === ui language`; list them by `sections` order; a page route like `/aide/<id>#<anchor>`.
3. Render `body` with the UI's Markdown renderer in a **trusted-content** configuration (images allowed, maths with
   KaTeX, Lean fences highlighted). Assign heading ids **in order** from `headings[]` (do not re-slugify) so that
   anchors match the site. Rewrite links: `<id>.md#a` → help route; `site:<name>#a` →
   `site_url + lang + "/" + site_links[name] + "#a"` (opens the browser; or, for `site:install`/`site:updates`, the
   Settings › Updates screen); `img/x.png` → the copied asset; `https://…` → external (`rel="noopener noreferrer"`).
4. Search: over `title`, `headings[].text`, `summary`, `text` (accent-folded). Context help: link a screen to a page id
   + anchor (e.g. Settings › Devices → `pairing#etape-2-afficher-un-code-sur-lhote` in French; anchors differ per
   language, so prefer page-level links or look the anchor up by heading order).
5. The site's own search uses `assets/search-<lang>.json`: `[{u: "page.html#anchor", t: page title, h: heading,
   x: text (≤ 600 chars), s?: summary}]`, one entry per h2 section.

## 3. Signed update channel (`updates/`) — for S-G / the release process

The site **consumes** the channel; it never signs. The release process writes into `site/updates/` with the ONE
producer of the format, `scripts/make_update_manifest.py` (called by `scripts/sign_release.sh`):

`stable.json` (UTF-8 JSON):
```json
{
 "schema": "madalean-updates/1",
 "channel": "stable",
 "version": "2.0.0",
 "tag": "v2.0.0",
 "date": "2026-12-01",
 "published": "2026-12-01T10:00:00+00:00",
 "notes": {"fr": "…", "en": "…"},
 "notes_url": "https://github.com/raantss18/madalean/releases/tag/v2.0.0",
 "min_version": "2.0.0",
 "files": [
  {"kind": "server",   "name": "madalean-2.0.0.tar.gz", "url": "https://github.com/…/madalean-2.0.0.tar.gz", "size": 9800000, "sha256": "<64 hex>"},
  {"kind": "appimage", "arch": "x86_64", "name": "Madalean-2.0.0-x86_64.AppImage", "url": "…", "size": 0, "sha256": "…"},
  {"kind": "apk", "arch": "arm64-v8a|armeabi-v7a|x86_64|universal", "name": "madalean-<arch>-release.apk", "url": "…", "size": 0, "sha256": "…"}
 ],
 "sums_url": "https://github.com/raantss18/madalean/releases/download/v2.0.0/SHA256SUMS",
 "sums_sig_url": "https://github.com/raantss18/madalean/releases/download/v2.0.0/SHA256SUMS.sig",
 "apk_certificate_sha256": "0d43426b…c544"
}
```
`channel` is signed and must equal the requested file's base name (`stable`); `min_version` is the oldest version
that may update directly (older → manual install). Updaters (server, AppImage, APK) check, in this order: signature →
channel → strictly newer → https-only file URL → size → SHA-256 (docs/SHELLS.md "Updates").
`stable.json.sig` = base64 of the Ed25519 signature of the **exact bytes** of `stable.json`, with the release key
(the one of `SHA256SUMS.sig`):
```
openssl pkeyutl -sign -inkey ~/.config/madalean/release-keys/ed25519.pem -rawin -in stable.json | base64 -w0 > stable.json.sig
```
Readers (server self-update, AppImage, APK) must verify `stable.json.sig` with the embedded public key before using
any field, then verify each downloaded file against `sha256` (and `SHA256SUMS` + its signature). The build verifies the
signature with the public key parsed from `madalean/update_checkers/selfupdate.py` (`PUBLIC_KEY`), **refuses to
build** when `stable.json` has no valid signature, requires every file URL to be a `https://github.com/` release URL
and every `sha256` to be 64 hex digits, and copies both files byte for byte. It also publishes
`updates/madalean-release.pub.pem` (SPKI PEM of `PUBLIC_KEY`). The install page (`download.html`) shows the latest
version, APK per architecture with a QR code (SVG generated at build time; every QR code is decoded back with
`zbarimg` by the checks when installed), the AppImage, install-from-source commands, and checksum + signature
verification commands (tested: `sha256sum -c --ignore-missing SHA256SUMS`; `base64 -d SHA256SUMS.sig >
SHA256SUMS.sig.bin; openssl pkeyutl -verify -pubin -inkey madalean-release.pub.pem -rawin -in SHA256SUMS -sigfile
SHA256SUMS.sig.bin` → « Signature Verified Successfully »). The Tauri updater needs its own `latest.json` format: not
produced here.

## 4. Publication template — input format (for S-E / S-G / « Publier »)

`python3 site/build.py publication --input DIR --out OUT`, or from Python: `sys.path.insert(0, "site");
from madasite import publication; publication.build(Path(DIR), Path(OUT))` (then copy assets: see `build.py`
`build_publication`). `DIR/publication.json` + `DIR/files/…`. Output: `index.html` (article), `graph.html`,
`results/<id>.html`, `verification.html`, `bibliography.html`, `files/`, `assets/`, `verification/{badge.svg,
result.json, expected.json, Verify.lean}`. No client script needed. Errors in the input raise `PublicationError`.

```ts
interface Publication {
  schema: "madalean-publication/1";
  lang: "fr" | "en";                               // language of the site's labels
  project: {
    title: string; short_title?: string; subtitle?: string;
    authors: { name: string; affiliation?: string; orcid?: string }[];
    date: string;                                  // free text, e.g. "2026-11-21"
    license?: string; keywords?: string[];
    abstract?: string;                             // Markdown (subset of §1) with $maths$ and citations
  };
  lean: {
    toolchain: string;                             // content of lean-toolchain, e.g. "leanprover/lean4:v4.9.0"
    mathlib: string;                               // Mathlib revision
    checked_at: string; checker: string;           // e.g. "Madalean 2.0.0, verdict strict"
    root_module: string;                           // module imported by Verify.lean
    lake_project?: string;                         // "files/<name>.zip"
  };
  article?: { pdf?: string; sections: { id: string; title: string; body: string /* Markdown */; nodes: string[] }[] };
  nodes: Node[];                                   // the blueprint, in reading order
  bibliography: { key: string; label?: string /* "HW08" */; csl: Csl /* CSL-JSON as in RESEARCH_SOURCES.md */ }[];
  files: { path: string /* "files/<name>" */; title: string; kind: "lake" | "pdf" | "tex" | "other" }[];
  computations?: Computations;                     // S-P: Calcul notebooks (docs/CALCUL.md §6)
}
interface Computations {                           // producer: madalean.research.notebook.publication_computations
  engine: { name: "SageMath" | "Python"; version: string };   // e.g. SageMath 10.10
  documents: { id: string; title: string; language: "sage" | "python";
    notebook: string;                              // "files/calcul/<doc>.ipynb" (downloadable, re-runnable)
    cells: { id: string; kind: "code" | "ask" | "markdown" | "figure";
      code?: string; prompt?: string /* ask */; language?: string; execution_count?: number | null;
      origin?: "user" | "assistant"; status?: string /* ok | error | timeout | not_run … */;
      stale?: boolean;                             // an earlier cell changed since this result: show it as such
      markdown?: string;                           // Markdown + $maths$ (markdown cells)
      outputs?: ({ kind: "text"; text: string; approx?: string } | { kind: "latex"; latex: string; text?: string /* plain fallback */; approx?: string }
               | { kind: "image"; path: string /* files/calcul/<sha>.png|svg */; mime: string; alt: string }
               | { kind: "figure"; spec: object /* FigureSpec */ } | { kind: "error"; text: string })[];
      figure?: { spec: object; svg?: string /* files/calcul/<sha>.svg */ };
    }[] }[];
}
// Rendering (site/madasite/computations.py, S-W): page computations.html, in the menu as « Calculs / Computations »
// when at least one document has cells. Requests, code (« Entrée [n] »), outputs; LaTeX rendered by KaTeX at build
// time (Sage macros \Bold, \ZZ… mapped; a formula KaTeX refuses falls back to `text`, never a build error);
// `figure` outputs and Figure cells without `svg` are drawn as static SVG by site/madasite/figure.py (explicit,
// implicit, polar, parametric curves, points, graphs — same grammar as web/src/lib/figure/expr.ts, no eval);
// geometric constructions come from the cell's own `svg`. Paths must match files/calcul/<name> (validated); the
// referenced files are copied. « Publier » adds the section unless `computations: false` (or a list of document
// ids), and lists every files/calcul/* in the manifest (kind "calcul").
interface Node {
  id: string;                                      // ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ (dossier id or blueprint node id)
  kind: "definition" | "lemma" | "theorem" | "proposition" | "corollary" | "conjecture" | "claim";
  number?: string; title?: string;
  statement: string;                               // Markdown, natural language
  informal_proof?: string;                         // Markdown
  uses: string[];                                  // ids of nodes this one depends on
  refs?: { key: string; locator?: string; note?: string }[];
  source?: { paper_key: string; locator: string }; // where it comes from (bib key + « Lemma 2.3 »)
  lean?: {
    name: string;                                  // Lean declaration name
    code: string;                                  // statement + proof as published (shown, highlighted)
    statement_ok: boolean;                         // Lean accepted the statement
    proof_ok: boolean;                             // strict verdict on the proof (never true with sorryAx)
    axioms: string[] | null;
    toolchain?: string; mathlib?: string; checked_at?: string;  // per-node overrides
  };
}
```
In Markdown texts: citations `[@key]`, `[@key, Thm 2.1]`, `[see @a, p. 3; @b]` (unknown keys are build errors);
links `node:<id>` (result page), `page:graph|verification|bibliography|index`, `https://…`.

**Statuses are recomputed by the template from the facts** (the input cannot make a result look verified):
`verified` = `proof_ok` and every `uses` dependency verified, transitively (a definition counts when `statement_ok`;
cycles are never verified) · `proved` = own proof accepted, some dependency not verified · `defined` = definition with
accepted Lean statement · `statement` = Lean statement accepted, no proof · `stated` = natural language only ·
`blocked` = uses a definition without accepted Lean statement. Each status has a colour, a border pattern and a text
label (never colour alone). A theorem/lemma/proposition/corollary that is not `verified` is titled **« Affirmation /
Claim »** with a warning, never « Théorème ». The dependency graph is laid out at build time (layered, barycentre
ordering) as inline SVG whose nodes are links; a table repeats it for screen readers.

**Independent re-verification** (`site/publication/ci/`): « Publier » creates a repository with `site/` (this output)
and `lean/` (the Lake project + `Verify.lean` from `publication.verify_file()`), and copies
`verify-and-publish.yml` → `.github/workflows/`, `make_badge.py` → `.github/madalean/`. The workflow (actions pinned by
commit SHA, `contents: read` except `pages: write` + `id-token: write` in the deploy job, no secret) installs the
toolchain of `lean/lean-toolchain` through `leanprover/lean-action` (elan) with the Mathlib cache, runs `lake build`,
runs `lake env lean Verify.lean` (`#print axioms` of every result the site calls verified), and `make_badge.py`
compares with `site/verification/expected.json`: verdict `verified` (build OK, every expected result reports only
`propext`, `Classical.choice`, `Quot.sound`), `sorry` (builds, some declaration uses `sorry` — normal when unproven
claims are published), `failed` (build fails, a result missing, a non-standard axiom incl. `sorryAx`). It writes
`site/verification/badge.svg` + `result.json`, then deploys (a failing badge is deployed too, and the job fails).
Before CI runs, the local preview shows a grey « en attente / pending » badge.

The sample (`site/publication/sample/`) **was compiled with Lean** by session S-E (2026-11-21): toolchain
`leanprover/lean4:v4.34.1`, Mathlib pinned to the exact commit `d13f23b723b8a846827a245b89c10fc7d3f11612` (tag
v4.34.1, the `lean-current` workspace), `lake-manifest.json` included (every dependency pinned), `lake build` OK
(only `isEven_sq_add_self` uses `sorry`, as intended) and `lake env lean Verify.lean` prints only standard axioms.
Fixes made then: the former pin `mathlib4 @ "v4.9.0"` did not match any built Mathlib here; the package name must
be a plain identifier (`package ParityNotes`, not `«parity-notes»`: lake rejects it in `lake-manifest.json`); the
Mathlib URL in the lakefile must equal the manifest's (`…/mathlib4`, without `.git`), else lake reports the
manifest out of date. « Publier » (`madalean/research/publish.py`) generates projects the same way.

## 5. Checks run by every build

- manual: front matter, both languages present with the same structure, every page/anchor/`site:` link resolves;
- every HTML page: doctype, `lang`, exactly one `<h1>`, balanced tags, unique ids, `alt` on images, CSP meta, no inline
  script/style/event handler; every internal `href`/`src` resolves (anchors included); CSS `url()` resolve;
- no external **resource** at all; external **links** only to: `https://github.com/raantss18/madalean…` (sources,
  releases), scholarly hosts (`doi.org`, `arxiv.org`, `zbmath.org`, MathSciNet), and the three instruction pages the
  manual needs (`tailscale.com`, `platform.claude.com` for an Anthropic key, `aistudio.google.com` for a Gemini key).
  Anything else fails the build (allow-list in `site/madasite/checks.py`);
- QR codes decoded (rsvg-convert + zbarimg, skipped when absent, e.g. on GitHub runners).

Last local run (2026-11-21, `--preview` build): 62 HTML pages, 0 errors, 8 QR codes decoded, 46 manual pages, 44
« verify » notes. Playwright (Chromium, `web/node_modules`) at 1440×900 and 390×844, light and dark, axe-core
WCAG 2.1 A/AA on manual, install, search and all publication pages: 0 violations after fixes, no horizontal
overflow, no console error, no request outside the local server. Sizes: site without sample ≈ 2.2 MiB (images
1.1 MiB, assets 0.5 MiB — KaTeX fonts 0.3 MiB, Source fonts 80 KiB), sample publication ≈ 0.5 MiB (assets copied).

## 6. Vendored files

- KaTeX 0.19.1 (`web/node_modules/katex`, MIT): `dist/katex.min.js`, `dist/fonts/*.woff2`, `LICENSE`, and
  `dist/katex.min.css` filtered to woff2 only with
  `re.sub(r'src:url\((fonts/[^)]+\.woff2)\) format\("woff2"\)(,url\([^)]+\) format\("[a-z]+"\))*', r'src:url(\1) format("woff2")', css)`.
- Source Serif 4 / Source Sans 3 (`@fontsource-variable/*@5.3.1`, OFL 1.1): `*-latin-wght-normal.woff2` + licences.

## 7. To verify / update at integration

- The 44 `<!-- verify after integration -->` notes (list: `jq '.pages[] | select(.verify|length>0) | {source, verify}'
  docs/manual/index.json`): repository name and install flow of 2.0, Tailscale setup applied for real, browser pairing
  from Safari, research-screen button names, « Publier » (not built), self-update/rollback controls (§16), prices and
  the per-proof cost estimate with a real key, Gemini free-tier terms, exact D28 refusal message.
- Screenshots: refresh `docs/manual/img/` from the final UI; add research-layer screens.
- Enable GitHub Pages (Settings › Pages › Source: GitHub Actions) — the owner's decision; then check the deployed URL
  `https://raantss18.github.io/madalean/` and that `404.html` works under `/madalean/`.
- First real release: `site/updates/stable.json(.sig)` from the release process (format §3); rebuild; check the
  install page's QR codes on a real phone.
- `.gitignore`: `site/.gitignore` ignores `site/_site/`, `site/_site_report.json`, `__pycache__/`.
