# Madalean 2.0 — research layer: sources, bibliography, grounded answers, blueprint, article (session S-E)

Server side of ARCHITECTURE §11 / §14 / §15. Same conventions as [API.md](API.md): JSON bodies, `/api` prefix,
errors `{"error": kind, "message"?: Message}`, i18n `Message = {key, params, text}`, authentication / Origin /
host checks by the server's middleware (every route below needs a device token on the remote listener), undo
through a `restore` route, `409 busy` when the item is already being worked on. Plugin:
`madalean/server/plugins/research_sources.py`; code: `madalean/research/{sources,fulltext,biblio,litsearch,qa,
papers,article,fetch,safety,demo_seed}.py`.

- [Data model](#1-data-model)
- [Sources library](#2-sources-library)
- [Literature search](#3-literature-search)
- [Grounded answers](#4-grounded-answers)
- [Bibliography in dossiers and exports](#5-bibliography-in-dossiers-and-exports)
- [Paper → blueprint](#6-paper--blueprint)
- [Lean → article](#7-lean--article)
- [WebSocket events](#8-websocket-events)
- [Security](#9-security-hostile-input)
- [Measured quality and limits](#10-measured-quality-and-honest-limits)
- [Demo mode and tests](#11-demo-mode-and-tests)
- [« Publier »](#12-publier--publish-to-github-pages)

## 1. Data model

```ts
type ShelfId = "global" | "mathlib" | string;          // a project id = that project's shelf
interface Csl {                                          // CSL-JSON (the internal record) + a few extra keys
  type: string; title: string; author?: Name[]; editor?: Name[]; issued?: {"date-parts": number[][]};
  "container-title"?: string; volume?: string; issue?: string; page?: string; DOI?: string; URL?: string;
  ISBN?: string; publisher?: string; "publisher-place"?: string; abstract?: string; note?: string;
  arxiv?: string; zbl?: string; zbmath?: string; mrnumber?: string; msc?: string[]; openalex?: string;
}
type Name = { family?: string; given?: string; literal?: string };
interface SourceFile { sha256: string; name: string; kind: "pdf" | "tex" | "archive" | "epub"; size: number;
                       role: string; added: number }
interface Annotation { id: string; page?: number | null;          // 1-based page
  quads?: number[][];                                               // PDF points, [x0,y0,x1,y1(,x2,y2,x3,y3)] per quad
  range?: { chunk: string; start: number; end: number } | null;     // or a character range inside a chunk
  text: string; note: string; color: "yellow"|"green"|"blue"|"pink"|"purple"|"red"|"orange"|"grey";
  created: number; updated: number }
interface Source {
  id: string;                     // "s-…" (Mathlib shelf: "m-…", read-only)
  key: string;                    // BibTeX key: stable, unique in the project + global shelves
  csl: Csl; files: SourceFile[]; tags: string[]; collections: string[];
  status: "unread" | "reading" | "read" | "to_read" | "skimmed"; notes: string; annotations: Annotation[];
  verified: boolean;              // false = metadata guessed from a file; confirm with PATCH {verified:true} or {csl}
  proposed: Csl | null;           // metadata proposed by the model (unverified), with proposed_by: model key
  origin: { via: string; at: number }; oa: { is_oa?: boolean; status?: string; url?: string; landing?: string };
  fulltext: { state: "none" | "ok" | "no_text_layer" | "ocr" | "error"; method?: "tex" | "pdf" | "epub";
              chunks?: number; pages?: number; two_columns?: number; headers_removed?: number; nodes?: number;
              warnings: string[]; at: number };
  warnings?: string[]; added: number; updated: number; readonly?: boolean;
}
type SourceSummary = { id, key, title, authors, year, type, venue, doi, arxiv, tags, collections, status, verified,
                       has_pdf, has_tex, fulltext /* state */, oa, annotations /* count */, updated, readonly };
interface Chunk { id: string /* "c-<16 hex>", stable */; source_id: string; ord: number;
  kind: "paragraph" | "abstract" | "theorem" | "lemma" | "proposition" | "corollary" | "definition" | "conjecture" |
        "claim" | "remark" | "proof" | "ocr" | …; text: string /* Markdown-ish, $math$ kept */;
  page: number | null; bbox: [number, number, number, number] | null /* PDF points, top-left origin */;
  section: string; label: string; locator: string /* « Theorem 2.1 », « §3, p. 5 » */; meta: object }
```

Storage: `<config>/projects/<pid>/sources/{items/<sid>.json, files/<sha256>, unpacked/<sha256>/, .trash/,
index.sqlite}`, global shelf `<config>/sources/`. Blueprints `<config>/projects/<pid>/blueprints/<sid>.json`,
article `<config>/projects/<pid>/article.json`.

## 2. Sources library

| | |
|---|---|
| `GET /research/shelves` | `{shelves:[{id, title, count, readonly, project?}]}` (global, every project, mathlib if a workspace has `docs/references.bib`) |
| `GET /research/shelves/{shelf}/sources?q=&tag=&collection=&status=&limit=` | `{shelf, sources:[SourceSummary], total}` |
| `POST /research/shelves/{shelf}/sources` JSON `{identifier, files?:true, force?}` | add by DOI / arXiv id / ISBN / `Zbl 0965.11001` / `zbmath:123` / OpenAlex `W…` / URL → `201 {source, duplicate:null}` or `200 {source: existing, duplicate:{of, reason: doi\|arxiv\|title}}`. arXiv: e-print source **and** PDF are fetched; DOI/zbMATH: OA PDF only when OpenAlex says `is_oa`; URL: metadata only (`citation_*` tags). `400 unknown_identifier`, `404 no_result`, `409 local_mode`, `502 network` |
| … JSON `{csl, key?, force?}` | form → `201 {source, duplicate}` |
| … JSON `{text, format?: bib\|ris\|csljson\|rdf, force?}` | paste BibTeX / RIS / CSL-JSON / Zotero RDF → `201 {added:[{id,key}], duplicates:[{id,key,duplicate}], errors:[…], unattached_files:[paths]}` |
| … multipart `file` (+ `force=1`, `mode`) | `.bib/.ris/.json/.rdf` → as above; Zotero export **zip** (metadata file + its `files/`) → files attached from inside the archive only; PDF → identifiers on the first pages resolved online (verified record) else heuristics (`verified:false`) and a background model proposal; TeX / source archive → `\title`/`\author` (`verified:false`). Limits: 60 MB, type sniffed from bytes (`415 bad_type`), archives checked at upload (`422 bad_archive`) |
| `GET …/sources/{sid}` | `{source}` |
| `PATCH …/sources/{sid}` `{tags?, collections?, status?, notes?, csl?, key?, verified?:true}` | `{source}`; `csl` = user-confirmed record; `verified:true` accepts `proposed`; `key` must be unique (`400 bad_fields` + `fields`) |
| `DELETE …/sources/{sid}` | `{ok, undo}` (409 busy while extracting); `POST …/restore` → `{source}` |
| `POST …/sources/{sid}/copy` `{to: shelf}` | copies record + files (e.g. global/mathlib → project) → `201 {source, duplicate}` |
| `POST …/sources/{sid}/files` multipart `file` | attach a PDF / TeX / archive / EPUB → `{source}` (full text re-extracted) |
| `GET …/sources/{sid}/files/{sha256}[?download]` | the file (`inline` for PDF, `Content-Security-Policy: sandbox`) |
| `POST …/sources/{sid}/extract` | `202 {started}` (re-extract full text; `sources.updated` when done); `409 busy` |
| `GET …/sources/{sid}/chunks[?page=n]` | `{chunks:[Chunk]}` |
| `POST …/sources/{sid}/annotations` `{page?, quads?, range?, text?, note?, color?}` | `201 {source, annotation}` (an anchor — page or range — is required) |
| `PATCH …/annotations/{aid}`, `DELETE …/annotations/{aid}` | `{source}` (deleted ones kept in `annotations_trash`, last 50) |
| `POST …/sources/{sid}/propose` | `202` model (role `understand`) proposes metadata from page 1 → `proposed` |
| `GET /research/shelves/{shelf}/export?format=bib\|ris\|csljson[&ids=a,b]` | file (BibTeX fields escaped) |
| `POST /research/shelves/{shelf}/search` `{query, k?, sources?:[sid], semantic?}` | `{hits:[Chunk + score, shelf, source_key]}` (FTS5 BM25; local Ollama re-ranking when available) |
| `GET /research/resolve?id=…` | preview `{csl, via, oa, eprint}` without adding |

Shelf `mathlib` is read-only (GET routes, copy to a project). Deduplication: same DOI, same arXiv id (any version),
or title similarity ≥ 0.93 with year ±1 and same first author.

## 3. Literature search

`POST /research/litsearch` `{query, providers?:["arxiv","zbmath","crossref","openalex","semanticscholar"], n?:10,
mode?}` → `{results:[Result], providers:{name:{ok, count, error}}}` (a failing provider — 429, timeout — is
reported, never fatal).

```ts
interface Result { id: string /* doi:… | arxiv:… | zbl:… | openalex:… */; title; authors: string; year: number|null;
  venue; doi; arxiv; zbl; openalex; msc: string[]; abstract; oa: {is_oa?, status?, url?};
  providers: string[]; score: number; csl: Csl /* POST it as {csl} to add */ }
```

`POST /research/litsearch/related` `{id: DOI | W-id, how: related|cited_by|references, n?:20}` → `{results}`
(OpenAlex). `POST /research/litsearch/reading-list` `{question, k?:8}` → `202 {request_id}`; events
`litsearch.progress {request_id, step: queries|searched, …}`, `litsearch.done {request_id, result:{queries,
items:[Result + why], rejected, model, providers}}`, `litsearch.error`. Every item is an API result **by
construction** (the model only picks candidate ids `R3`; unknown ids are dropped and counted in `rejected`; `why` is
cleaned of citations / foreign DOIs). Local mode → `409 local_mode`.

## 4. Grounded answers

`POST /research/ask` `{question, project?, scope?:{shelves?:[…], sources?:[sid]}, general?:false, k?:8, mode?}` →
`202 {request_id}`. Default scope: the project's shelf + the global shelf. Streams `qa.token {request_id, kind,
phase: answer|general, text}` then `qa.done {request_id, result}` / `qa.error`. Stop: `POST
/research/requests/{request_id}/stop`.

```ts
interface QaResult { kind: "ask" | "summary" | "compare"; question: string;
  status: "ok" | "no_passages" | "not_in_sources" | "unsupported"; model: string; dropped: number;
  passages: { passage: "P1"; chunk_id; source_id; source_key; shelf; page; bbox; locator; kind; text; score }[];
  sentences: { text: string; supported: boolean; general: false; notice?: true;
               citations: { passage; chunk_id; source_id; source_key; shelf; page; bbox; locator;
                            quote: string; span: [number, number] /* in chunk.text */; match: number }[] }[];
  general: { text; supported: false; general: true; citations: [] }[]; general_model?: string }
```

- No passage retrieved → `status:"no_passages"` with a notice sentence, **no model call**.
- Each cited quote is searched in the cited chunk (normalised, exact or fuzzy ≥ 0.85); failures are dropped
  (`dropped`), a sentence without any valid citation has `supported:false` (show it struck / greyed).
- `general:true` adds a separately generated part, marked `general`, with every `[@…]` removed.

`POST /research/summarize` `{shelf, source}` and `POST /research/compare` `{sources:[{shelf, id}×2..4]}` → same
flow (`kind` summary / compare; « what it proves, main definitions, dependencies »).

## 5. Bibliography in dossiers and exports

- Dossier `refs: [{key, locator, note}]` (PATCH /dossiers/{id}); in any text (statement, proofs, explanations,
  notes, article blocks): `[@key]`, `[@key, Thm 2.1]`, `[see @a, p. 3; @b]`.
- The pipeline's explanation and informal-proof prompts receive the project's keys with titles (project shelf, then
  global shelf, then the dossier's own `refs`, Mathlib keys included); after generation every `[@key]` that does not
  exist is **removed by code** and an `info` event « Références inventées par l'IA retirées : {keys}. » is added.
- `GET /research/projects/{pid}/keys` → `{keys:[{key, title, label /* Wil95 */, authors, year}]}` (autocomplete);
  `GET /research/projects/{pid}/bibliography` → `.bib`; `POST /research/check-citations {text, project}` →
  `{text, cited, unknown}`.
- Exports (`GET /dossiers/{id}/export`): cited entries only (`refs` + valid `[@key]`). PDF: biblatex + biber
  (`style=alphabetic`) when both are installed, else bibtex + `amsalpha`, else a hand-formatted
  `thebibliography`; a failing backend falls back to the next. `.tex` export: self-contained `thebibliography`;
  `.zip`: + `refs.bib`; Markdown / HTML: `[Wil95, Thm 2.1]` + a reference list. Python API:
  `export_dossier(..., bib_entries=[(key, csl)])` (and the older `bib_keys` / `bib_path`).

## 6. Paper → blueprint

| | |
|---|---|
| `POST /research/projects/{pid}/blueprints` `{source_id, shelf?: pid\|global, model_pass?: false, mode?}` | extract → `201 {blueprint, request_id}` (TeX when the source has one, else PDF text layer, OCR last). Re-extracting keeps the node ↔ dossier links. `model_pass` adds `proposed` edges in the background (`blueprint.updated`) |
| `GET …/blueprints` | `{blueprints:[{source_id, paper_key, method, nodes, created, warnings}]}` |
| `GET …/blueprints/{sid}` | `{blueprint, status:{node_id: NodeState}}` |
| `DELETE …/blueprints/{sid}` / `POST …/{sid}/restore` | undo |
| `POST …/blueprints/{sid}/edges` `{from, to, action: add\|remove\|accept\|reject}` | user curation; dossier `uses` follow |
| `POST …/blueprints/{sid}/dossiers` `{nodes?:[node ids]}` | draft dossiers (all nodes when omitted) → `201 {dossiers, blueprint}`. **Never starts a job** |
| `POST /research/projects/{pid}/formalise` `{dossier_ids, mode?, use_paper_proof?: true}` | explicit action → `202 {jobs, busy, skipped}` (`409 busy` when all are busy). Plan = normal pipeline (`understand → statement → proof → explanation`; definitions: `understand → statement`). The paper's proof goes as a hint wrapped as data to the **Goedel** prover only (`strategy: "goedel"` for those jobs): a tool-using agent never receives paper text. `use_paper_proof:false` = normal strategy, no hint |
| `GET /research/projects/{pid}/blueprint-status` | `{nodes:[NodeState], counts:{state: n}}` |

```ts
interface Node { id: string /* "n-<label>" */; kind: "theorem"|"lemma"|"proposition"|"corollary"|"definition"|
  "conjecture"|"claim"|"question"; name: string /* « Theorem » as printed */; number: string /* "2.1" */;
  label: string; title: string; text: string /* $math$, refs resolved */; tex: string; proof: string;
  proof_tex: string; section: string; locator: string; page?: number; cites: string[];
  uses: { to: string; via: "proof_ref"|"statement_ref"|"text_ref"|"model"|"user"; proposed: boolean;
          accepted?: boolean; rejected?: boolean }[];
  quality: "high"|"medium"|"low"; dossier_id: string }
interface Blueprint { source_id; paper_key; method: "tex"|"pdf"|"pdf_ocr"|"none"; title; nodes: Node[];
  bibitems: Record<string, string>; warnings: string[]; shelf; model_pass?: {model, added}; created; updated }
interface NodeState { node_id; source_id; dossier_id;
  state: "not_created"|"stated"|"statement"|"proved"|"defined"|"verified"|"blocked"|"failed";
  verified: boolean; missing_definitions: string[]; unverified_uses: string[] }
```

`verified` = the dossier's current proof proves its current statement (Lean strict verdict) **and** every `uses`
node is verified, transitively (cycles are never verified; proposed edges count until the user rejects them —
stricter, never laxer). A definition is verified once its Lean statement is accepted. `blocked` = uses a definition
without an accepted Lean statement. Dossiers created from nodes: `kind` (theorem/proposition/corollary → theorem,
lemma, definition, conjecture/claim/question → conjecture when S-G's kind exists, else claim), `source
{paper_key, locator, original_text}`, `refs [{key: paper_key, locator: "Lemma 1.2"}, + cited keys that exist]`,
`uses` (dossier ids), `blueprint {source_id, node_id, paper_kind, quality, statement}` (extra field), `problem` =
statement + the definitions it uses (context for the formalizer).

## 7. Lean → article

| | |
|---|---|
| `GET /research/projects/{pid}/article` | `{article, generating:[block ids]}` (created on first read: intro + one block per top-level dossier) |
| `PATCH …/article` `{title?, authors?:[{name, affiliation?, email?}], options?:{lean_appendix, verification_table, lang: fr\|en, numbering: section\|global}, order?:[block ids]}` | `{article}` |
| `POST …/article/sync` | adds blocks for new dossiers → `{article, added}` |
| `POST …/article/blocks` `{kind: intro\|section\|prose\|dossier\|conclusion, title?, text?, dossier_id?, after?}` | `201 {article, block}` |
| `PATCH …/article/blocks/{bid}` `{text?, title?}` (`bid` may be `abstract`) | user version → `{article, block}` |
| `DELETE …/article/blocks/{bid}` / `POST …/{bid}/restore` | undo |
| `POST …/article/blocks/{bid}/generate` `{force?, instructions?, mode?}` | AI draft of **this block only** (role `explain`) → `202 {request_id}`; `409 user_edited` when the current text is the user's (use `force`; the user's text stays in `versions`), `409 busy`. Events `article.token {project, block_id, request_id, text}`, `article.done {…, model, removed_citations}`, `article.error`, then `article.updated` |
| `POST …/article/blocks/{bid}/versions/{i}/restore` | `{article, block}` |
| `GET …/article/export?format=pdf\|tex\|zip\|md` | file; `X-Madalean-Fallback`: `""`, `"verbatim"`, `"html"` |

```ts
interface Block { id: string; kind: string; title: string; source: "ai"|"user"|"dossier"; text: string;
  dossier_id: string; versions: {text, source, t, model, note, title, removed_citations?}[]; updated: number }
interface Article { title: string; authors: {name, affiliation, email}[]; abstract: Block; blocks: Block[];
  options: {lean_appendix: boolean; verification_table: boolean; lang: "fr"|"en"; numbering: "section"|"global"};
  trash: {block: Block; index: number}[]; created: number; updated: number }
```

Typesetting (amsart, XeLaTeX): a dossier whose current proof is Lean-verified → theorem / lemma / proposition /
corollary (the paper's kind when it comes from a blueprint) + natural-language proof + « Verified by Lean:
`name` (table N) »; anything else → **Claim / Conjecture** with a red « not verified by Lean » mark — never a
theorem environment; definitions → definition. Verification table (result, Lean name, verified / statement
accepted / no, Lean, Mathlib, axioms), references, appendix with the Lean listings. ZIP: `.tex`, `refs.bib`,
`.pdf`, `.md`, `lean/<name>.lean` for each verified result.

## 8. WebSocket events

| type | payload |
|---|---|
| `sources.updated` | `{shelf, source?: Source, removed?: sid}` — add, edit, file, full-text state, annotation |
| `litsearch.progress` / `litsearch.done` / `litsearch.error` | §3 |
| `qa.token` / `qa.done` / `qa.error` | §4 |
| `blueprint.updated` | `{project, source_id, blueprint?, removed?, error?}` |
| `article.updated` | `{project, article}` |
| `article.token` / `article.done` / `article.error` | §7 |

Dossiers created or changed by these routes publish the usual `dossier.updated`; formalisation jobs the usual
`job.*`.

## 9. Security (hostile input)

- **One network client** (`research/fetch.py`): `mode == "local"` (settings, or a project's `mode: "local"`)
  refuses before any socket; https only, default port, no user-info, no IP literal / `.local` / single-label /
  `.ts.net` host; API calls only to `doi.org, api.crossref.org, data.crossref.org, api.datacite.org,
  data.datacite.org, export.arxiv.org, arxiv.org, api.openalex.org, openlibrary.org, api.zbmath.org, zbmath.org,
  api.semanticscholar.org`; OA PDFs / user URLs (`public` policy) any public host. Resolve-then-connect: a custom
  aiohttp resolver refuses a name if **any** address is loopback / private / link-local / CGNAT / multicast /
  reserved / IPv4-mapped-private, and aiohttp connects to exactly those addresses. Redirects re-validated (≤ 5),
  size limits on decompressed bytes, timeouts, content-type checks, no cookies, no proxy from the environment,
  contact-less User-Agent, per-host rate limits (arXiv 3 s).
- **Uploads**: 60 MB, type from the bytes; archives extracted by `safety.extract_archive` (regular files only, no
  absolute path / `..` / symlink / hardlink / device, ≤ 2 000 entries, ≤ 40 MB per file, total ≤ min(200 MB, 200 ×
  compressed size) counted while writing — zip and gzip bombs stop); file names sanitised; XML with DTD / entities
  refused.
- **PDF** handled only by poppler (`pdfinfo`, `pdftotext`, `pdftoppm`) and `tesseract`, each with a timeout,
  CPU / address-space / file-size rlimits, nice 10, own process group, empty environment.
- **Paper TeX is never compiled** — only parsed; `\input` resolved inside the extracted archive only. Our own TeX
  (dossier exports and articles) is compiled with `-no-shell-escape` and `openin_any=p`, `openout_any=p`,
  `shell_escape=f` (now for every export of the server). BibTeX fields escaped on output (math only through texio's
  allow-list), citation keys restricted to `[A-Za-z0-9_:.-+/]` and to keys that exist.
- **Prompt injection**: text from sources / APIs reaches models only wrapped in `<<<SOURCE_DATA …>>>` with a rule
  saying it is data (look-alike delimiters inside are neutralised); grounded answers, summaries, reading lists,
  metadata proposals, blueprint edge proposals and article drafts use `complete` only — **no tool is ever offered**;
  model outputs are validated by code (quotes must occur in the cited chunk, candidate ids must exist, edge ids must
  exist, citation keys must exist, identifiers in a metadata proposal must occur on the page). Paper proofs go to the
  Goedel prover (no tools) only. Tested with a fake brain that « obeys » an injected passage.
- **Paths**: shelf / source / sha / block / node ids validated by regex; files served only by `sha256` listed in the
  record; tests enumerate every `/api/research/*` route on the remote listener (401 without a token).

Open point for the security review (S-H): Lean code written by any model is compiled by `lean`; `#eval` (which can
run IO at elaboration time) is not in `leancheck.FORBIDDEN` — independent of this layer, but paper text reaching the
prover makes it worth closing (forbid `#eval`/`#print`-with-IO/`initialize`/`IO.` in model code before compiling).

## 10. Measured quality and honest limits

**Blueprint extraction, 3 real arXiv papers** (e-print sources and PDFs fetched once, 2026-11-21, hand-checked
against the TeX; not redistributed): A = 2603.29961 *Short proofs in combinatorics and number theory* (amsart,
`\newtheorem[section]` shared counters, `\cref`, proofs placed after other material as `proof[Proof of \cref{…}]`);
B = 2411.02513 *A short proof of the Hilton–Milner theorem* (LyX export, Latin-1, `\protect\theoremname` titles,
starred subsections « Proof of Theorem \ref{…} », one proof written as prose); C = 2603.29335 *A short proof of an
inequality on spectral radius perturbation* (article class, the proof is a whole section without `proof`
environment).

| | A (TeX) | B (TeX) | C (TeX) | A (PDF) | B (PDF) | C (PDF) |
|---|---|---|---|---|---|---|
| statements found / true | 6/6 | 5/5 | 1/1 | 6/6 | 5/5 | 1/1 |
| false statements | 0 | 0 | 0 | 0 | 0 | 0 |
| numbers correct | 6/6 | 5/5 | 1/1 | 6/6 | 5/5 | 1/1 |
| proofs attached correctly / true proofs | 5/5 | 4/5 | 1/1 | 5/5 | 3/5 (1 wrong) | 0/1 |
| `\ref` edges inside proofs: correct / extracted | 1/1 | 1/2 (+1 statement ref, marked proposed) | — | 1/1 (text refs) | 1/5 | — |
| true dependencies found (recall) | 1/3 | 1/4 | — | 1/3 | 1/4 | — |

Totals: statements precision = recall = 12/12 from TeX and 12/12 from the PDF text layer (after two fixes made
during the evaluation: « Proof of Theorem N » headings, mentions at a line start no longer taken as headers — before
them, the PDF path had 2 false statements and 3 misplaced proofs); proofs 10/11 from TeX (0 wrong), 8/11 from PDF
(1 wrong). Dependencies: the `\ref` edges inside proofs are mostly right (2/3 from TeX; the wrong one is « given F
as in Theorem 1 », a reference to a setting, not to a result), but most real
dependencies are written in prose (« Given the lemma… », « the main input is the following theorem ») — recall 2/7.
That is what the optional model pass is for (edges marked `proposed`, never trusted silently); it was **not
measured** with a real model (no key).

Other limits:
- PDF maths come out as poppler's text (`n 2` for $n^2$, `X ∞` for $\sum_\infty$); statements from PDFs are for
  reading and search, not for formalisation without review. OCR exists (tesseract eng+fra) but was only exercised by
  code paths, not measured; OCR maths are flagged `ocr_math_unreliable`.
- TeX numbering emulation covers `\newtheorem` (shared counters, `[section]`/`[subsection]`), `\numberwithin`,
  `\declaretheorem`, `\spnewtheorem`, appendix letters; not `\setcounter`, `cleveref` custom names, or classes that
  predefine environments with their own counters (llncs, elsarticle…: undeclared environments are numbered by their
  own counter).
- Macro expansion: simple `\newcommand` / `\def` / `\DeclareMathOperator` bodies only (≤ 400 chars, nothing that
  defines or reads anything), 4 rounds.
- Grounded answers: quote verification proves the quote is in the passage, **not** that the passage supports the
  sentence (an entailment check would need another model call); retrieval is lexical (FTS5) unless a local Ollama
  embedding model runs (re-ranking only, not measured here). Answer quality with real models: **needs a key to
  verify** (only the fake brain ran).
- Reading lists and metadata proposals with a real model: needs a key to verify. Semantic Scholar keyless often
  answers 429 (it answered 200 during the recording).
- Zotero: BibTeX (incl. Better BibTeX `file` fields), CSL-JSON and RDF are read; attached files only from an
  uploaded zip of the export folder (never from a path written in the file).

## 11. Demo mode and tests

`madalean serve --demo` seeds « Recherche (démo) — parité »: 2 sources (a CC0 note written for Madalean, TeX + PDF,
with full text, an annotation and reading status; Hardy & Wright as a record), its blueprint with 5 dossiers (Lemma
1.2 proved, Definition 1.1 with an accepted statement), and an article (abstract + introduction drafts with
citations). Network calls in demo mode replay recorded answers (`madalean/research/demo_http/`, same endpoint →
recorded answer), so literature search works offline.

Tests (no network): `tests/test_sources_security.py`, `test_sources_api.py`, `test_biblio.py`, `test_article.py`;
`tests/test_sources_online.py` (marker `online`, `MADALEAN_ONLINE_TESTS=1`; `MADALEAN_RECORD=1` re-records
`tests/data/research/http/`).

## 12. « Publier » — publish to GitHub Pages

ARCHITECTURE §17 role 1; template and `publication.json` schema: docs/SITE.md §4 (session S-F). Code:
`madalean/research/publish.py`. Files: `<config>/projects/<pid>/publish/{input/, lean/, preview/, manifest.json,
state.json}`.

| | |
|---|---|
| `GET /research/publish/{pid}` | `{manifest \| null, state, preview: bool, running: bool}` (`state` = last push, see below) |
| `POST /research/publish/{pid}/plan` `{dossiers?:[ids], notes?:[note ids], source_files?:[{shelf, id, sha256}], include_pdf?:false, lang?, license?:"CC-BY-4.0", authors?, title?}` | builds `input/publication.json` + `lean/` and returns `{manifest}` — **nothing is sent** |
| `POST /research/publish/{pid}/preview` `{manifest_id}` | renders with `site/build.py publication` → `{pages, url}`; `409 manifest_changed` when the plan changed since the user reviewed it, `422 build_failed {log}` |
| `GET /research/publish/{pid}/preview/{path}` | the static site (CSP `script-src 'none'` + `sandbox allow-same-origin allow-popups`; paths confined to the preview) |
| `POST /research/publish/{pid}/push` **host** `{manifest_id, repo:"owner/name", create?:false, private?:false, branch?:"main"}` | `202 {request_id}`; events `publish.progress {project, request_id, step: repository\|created\|fetch\|commit\|push\|pages, …}`, then `publish.done {project, request_id, state}` or `publish.error {project, request_id, error, message?}`. `409 busy`, `409 local_mode`, `409 manifest_changed` |

```ts
interface PublishManifest {
  id: string;                     // give it back to preview / push: the user confirmed exactly this list
  project: string; created: number; workspace: string; toolchain: string; mathlib: string /* full commit */;
  items: { path: string /* publication.json | files/… | lean/… | .github/… */; kind: "metadata"|"lake"|"pdf"|
           "lean"|"ci"|"other"|"file"; size: number; sha256: string; origin: string /* project | lean | article |
           note:<id> | source:<key> | template */; note: string }[];
  excluded: { what: string; why: "not_found" | "no_such_file" | "license_not_redistributable"; license?: string }[];
  warnings: string[];             // dependency_added:<dossier id>, other_workspace:<id>
  statuses: Record<string, "verified"|"proved"|"defined"|"statement"|"stated"|"blocked">;  // what the site will show
  counts: Record<string, number>;
  not_included: string[];         // never published: sources' full texts, unselected notes, dossier threads, …
}
interface PublishState { repo: string; branch: string; commit: string; changed: boolean /* false = already up to
  date, nothing committed */; created: boolean; pages: boolean; pages_url: string; pushed_at: number }
```

Content: nodes = the article's dossier blocks in order (or `dossiers`), plus every transitive `uses` dependency
(added automatically and reported: a result is never published without what it relies on), sections from the
article blocks, abstract, bibliography = cited CSL records only. Facts: `statement_ok` = current Lean statement
accepted; `proof_ok` = current proof proves the current statement under the strict verdict **and** its recorded
axioms ⊆ {propext, Classical.choice, Quot.sound} (a `sorryAx` proof is never `proof_ok`); the template recomputes
the statuses (a node with any unverified transitive dependency is never « verified »). Lean: a Lake project with the
workspace's `lean-toolchain`, `require mathlib … @ "<exact commit>"` (URL identical to the manifest's),
the workspace's `lake-manifest.json` re-targeted (every dependency pinned), one module per result
(`<Root>/M01….lean`, code inside `namespace <Root>.M01…` so helper names never clash), a root module importing
all, and `Verify.lean` (`#print axioms` of every result the site calls verified). The repository gets `site/`,
`lean/`, `.github/workflows/verify-and-publish.yml`, `.github/madalean/make_badge.py` (+ README/.gitignore if
absent; other files of the repository are left alone).

Privacy: notes only when listed in `notes`; a source's file only when its `license` (PATCH the source
`{license:"CC-BY-4.0"}`) is a Creative Commons / public-domain licence **and** it is listed in `source_files`;
everything else is in `excluded` with the reason. Credentials: a token stored with `POST /models/keys
{provider:"github", key}` (keyring service `madalean`, attribute `provider=github`; whitespace of a copy-paste
removed) else `gh auth token`; sent only to the GitHub API and to git through a GIT_ASKPASS helper that reads it
from the environment (never in a URL, a command line, a config file or a log; no credential helper of the user is
consulted). Never `--force`: a remote that diverged or refuses is reported (`git_push_rejected`) and nothing is
overwritten; pushing the same content again commits nothing.

GitHub permissions (session S-Q, 2026-11-21 — the user's « clé GitHub » failure was the key test of Réglages → Clés
treating GitHub as a model provider and answering « aucun modèle trouvé : la clé est-elle valide ? »; publishing also
needs the `workflow` right, which the old code reported as « historique différent »):

| step | classic token (`ghp_`, `gho_`) | fine-grained token (`github_pat_`) |
|---|---|---|
| identity | — | — |
| create the repository | `repo` (`public_repo` for a public one) | Administration: write, « All repositories » |
| push | `repo` | Contents: write |
| push `.github/workflows/*.yml` | `workflow` | Workflows: write |
| enable Pages (`build_type: workflow`) | `repo` | Pages: write (+ Administration: write) |

The push checks the identity first (`GET /user`: an expired / revoked token is `github_token_invalid`, never
« repository not found »), then classic scopes before trying (`X-OAuth-Scopes`), and maps every refusal:
`github_scope_missing {scope, settings}`, `github_permission_missing {permission: "Contents (Read and write)", …,
settings}` (from GitHub's `X-Accepted-GitHub-Permissions`), `github_sso_required {org, url}` (`X-GitHub-SSO`),
`github_2fa_required {org}`, `github_rate_limited`, `github_repo_not_granted` (exists but outside the fine-grained
token's repositories), `github_org_not_found`, `github_unreachable`; git's own refusals likewise (`workflow` scope,
403, 401, diverged history). Pages that cannot be enabled no longer fail the publication: `state.pages_error` +
`state.pages_settings` (link to enable it by hand). The UI builds the preview itself when needed (a push without
preview used to stop on `no_preview`).

| | |
|---|---|
| `GET /research/github/check?repo=owner/name&private=1` | « Tester la connexion GitHub », read-only (GET requests only): `{ok, login, name, token_kind: classic\|fine_grained\|oauth\|app\|unknown, source: keyring\|gh, scopes, expires, checks:[{id: token\|identity\|expiry\|create\|push\|workflow\|pages\|org\|repo\|rate, ok: true\|false\|null, code, params}]}` — `ok: null` = GitHub cannot tell before trying (fine-grained) |
| `POST /models/test {provider:"github"}` | the same identity check (Réglages → Clés), `{ok, login, token_kind, reason: "github:<code>"}` — never a model call |

Verified: everything above against a local fake GitHub API and a local bare git remote (`tests/test_article_publish.py`,
`tests/test_publish_github.py`: good classic token, classic token without `workflow`, fine-grained token without
Pages, expired token, SAML-SSO and 2FA organisations, askpass over HTTP Basic);
a generated project and the template sample were built with the real Lean 4.34.1 + Mathlib d13f23b (`lake build`,
`lake env lean Verify.lean`). Not verified: a push to the real github.com and the Action running on GitHub.
