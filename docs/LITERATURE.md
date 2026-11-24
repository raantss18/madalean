# « Littérature d'abord » — published results and attachments as cited lemmas (S-AX, DECISIONS D56)

For every statement to prove, Madalean looks in the reviewed literature (and in what the user attached) for results
related to it, quotes them **word for word** with their place, states them in Lean when it can, links them to Mathlib
when Mathlib has them, and offers them to the provers. Lean stays the only judge: a result that is cited but not
proved in Lean is never counted as proved — a proof through it is **« preuve conditionnelle : repose sur [réf.] »**,
never « vérifiée ».

Code: `madalean/literature/` (`engine.py` search, `retrieve.py` sources, `quotes.py` verbatim rule, `formal.py`
Lean statements and conditional proofs, `attach.py` attachments, `types.py` typed results), the pipeline hook
`madalean/pipeline/literature_hook.py`, the API `madalean/server/plugins/literature.py`, the panel
`web/src/screens/dossier/LiteraturePanel.svelte`. Tests: `tests/test_literature.py`, `tests/test_attachments.py`,
`web/e2e/literature.spec.ts`.

## 1. Sources

| Source | What it gives | Endpoint (host allow-list) | Terms |
|---|---|---|---|
| zbMATH Open | reviewed mathematical literature: record, MSC, **review** or authors' summary, DOI | `api.zbmath.org/v1/document/_search` | open API; reviews CC BY-SA 4.0, quoted with attribution |
| OpenAlex | works, open-access status, abstract (inverted index) | `api.openalex.org/works` | CC0 metadata, no key |
| arXiv | preprints and their abstracts | `export.arxiv.org/api/query` (3 s between calls) | documented API, metadata CC0 |
| Crossref | **confirmation** of a DOI: it exists, its title, its venue and type | `api.crossref.org/works/{doi}` | public metadata |
| DOI registry | does a non-Crossref (DataCite) DOI exist | `doi.org/api/handles/{doi}` | public |
| Your Sources | full text of the PDFs / TeX you imported (theorem environments first) | local | your copies |
| Mathlib index | related declarations (real names, signatures) | local (RAG index) | Apache 2.0 |

Every network call goes through `research/fetch.py` (https only, public addresses only, resolve-then-connect, no
cookies, contact-less User-Agent, per-host politeness, size and time limits, short cache) and, on top, through
`retrieve.Guarded`: each source may reach **only its own host** and spends one request of the search budget.

**What leaves the machine**: the search words built from the statement (e.g. « Bertrand postulate prime »), DOIs
and arXiv ids to confirm. Never the Lean file, a project text, a note, a key, a name or an e-mail address.
**Local mode** (setting or project « local only »): no request at all — the Sources and the Mathlib index are still
searched; an attachment URL is refused (`409 local_mode`).

## 2. Anti-hallucination rules (hard)

1. **A reference shown comes from a retrieved record.** Title, authors, year and venue are the API's, never a
   model's. A record without an identifier that resolves (DOI, arXiv id, zbMATH id, OpenAlex W-id, a Source of
   yours) is dropped. A DOI is confirmed by Crossref, else by the DOI registry; a DOI neither knows is removed and
   counted (`rejected.unresolved_dois`). Withdrawn / retracted works are dropped.
2. **A quoted result is verbatim.** The retrieved text is cleaned once, deterministically (tags, entities, NFKC,
   white space — no rewording); a quote must be found in that text by `quotes.verify` (white space aside). The
   candidates are cut by rules (sentences stating a result and sharing the statement's keywords); in « approfondi »
   mode a free model may **pick** among numbered passages (`P1…`), never write one; an unknown id is dropped and
   counted. Every quote carries its place: « résumé, phrase 2 », « recension zbMATH », « Theorem 2.1, p. 5 ».
3. **Peer-reviewed vs preprint** comes from Crossref's type or zbMATH's document type (journal / proceedings →
   peer-reviewed; posted content / arXiv only → preprint; otherwise « type inconnu »).
4. **Nothing reliable found** is said as such (« Littérature : rien de fiable trouvé »): nothing fills the gap.
5. **Hostile text**: retrieved text is data. A text that addresses a model (shared detector with the news watch) is
   kept as inert plain text, flagged `suspect`, and never sent to a model (no passage choice, no formalization);
   texts that are sent are wrapped with `wrap_untrusted`. The UI renders quotes as plain text.

## 3. Cited results in Lean

For the best quotes (1 in « rapide », 3 in « approfondi »), the usual formalizer (Goedel prompt, Lean check of the
statement, catalogue of D45) translates the **verified quote** into `theorem cited_<author>_<year>_<id> … := by
sorry` — free online models only, never the GPU model, never a paid one. Then:

- Mathlib proves it (index candidates + templates + `exact?`, strict verdict, no model) → **dans Mathlib** + name;
- the library holds it → **prouvé en Lean**;
- else → **à prouver**: a *cited lemma*. « Prouver ce lemme » makes a lemma dossier (normal pipeline, budgeted like
  any job), marked `extra.cited_from`.

The Lean statement is a model's translation: shown « à relire ». A wrong translation can never produce a wrong
« vérifiée »: a cited lemma counts only once it is proved in Lean.

**Conditional proof.** Short tactics through each cited lemma (`exact`, `simpa using`, `apply` + side goals…), in
one Lean file, the cited lemmas stated with `sorry` before the theorem (the « admitted lemma » form of proof plans).
Accepted → `dossier.extra.conditional_proof = {verdict: "proved_modulo", source: "literature", cited: [...], code,
axioms ∋ sorryAx, strict_ok: false}` — never in `dossier.proofs`, never in the library, labelled everywhere (proof
step, header, export: « Preuve conditionnelle, NON vérifiée : … »). When the cited lemma's dossier is proved, the
lemma's real proof replaces the `sorry` and the strict check decides; only an acceptance makes the dossier
« vérifiée » (`formal.upgrade`).

## 4. In the pipeline (D38)

Stage `literature`, started with Mathlib-first / certificates when the proof search starts (own task, owner
`<job>#literature`); no racer waits for it; « Arrêter » cancels it; the job ends after it like the optional stages
(bounded by its budget). Budgets: « rapide » 45 s, 10 requests, 3 model calls, 8 Lean checks, 6 references, 1
formalization; « approfondi » 150 s, 24 requests, 8 model calls, 24 Lean checks, 12 references, 3 formalizations.
Cached in the stage cache (`kind: literature`, key = normalised statement + workspace + Lean + Mathlib versions +
depth + words, 30 days); a Local-mode or all-providers-failed result is not cached.

Uses: (a) the thread event lists the references with their quotes — evidence for the user next to the statement
check, never an automatic change; (b) `job.literature_hint` for the provers (Mathlib names first, then the results
that are not available in Lean); (c) the panel: « Ajouter aux Sources » (the retrieved record, verified), « Ajouter
à la bibliographie de l'article » (Sources + the dossier's references → the article's bibliography), BibTeX.

**Loop guards**: every phase runs once (no retry loop); a cited lemma's dossier never searches the literature
again; one search per dossier at a time (`409 busy`); the cache answers a repeated statement.

Setting « Chercher dans la littérature » (Réglages › Modèles › avancé, on by default, never in Local mode) and
« Profondeur » (rapide / approfondie). The benchmark turns it off (D53: it measures proofs).

## 5. Attachments, read once

On the dossier's follow-up field (paperclip) and in the « Littérature » panel: an image (PNG / JPEG / WebP), a PDF,
a LaTeX or BibTeX file, or a URL. It becomes a **Source of the project** (the existing Sources import: size and type
limits from the magic bytes, hostile archives refused, SSRF-safe fetch of URLs), linked to the dossier as « pièce
jointe N ».

- **Read once**: the digest is content-addressed (SHA-256 of the file or of the URL) in `<shelf>/digests/<sha>.json`,
  versioned by `EXTRACTOR_VERSION`; the same file in any dossier of the project is linked to it, never read again
  (no extraction, no model, no vision call). « Relire » is the only way to read it again.
- **Digest**: the record (verified when an identifier in the text resolves through the scholarly APIs, else
  « référence non vérifiée »), the statements (theorem environments of the extracted text; sentences of an image
  transcription), each a typed item with `origin: "attachment"` and a verbatim quote (same rule as §2), an optional
  Lean statement (free models, Lean-checked).
- **Images**: one call to a vision model (a free online one, a local one in Local mode); the transcription is marked
  as such and the original stays in the Sources. Without a vision model the image is kept, « non lue ».
- **Understanding first**: when the project has digests, the stage writes « À prouver : … » and, apart, the
  « résultats fournis » with their origin; they enter the pipeline exactly like cited lemmas (hints; conditional
  proof until proved in Lean or found in Mathlib). A provided result is never merged into the target.
- **Discussing**: a follow-up that names « pièce jointe 2, lemme 3.1 » gets the digest's verbatim quote (and Lean
  statement) appended to the request; the raw document is never re-sent.

## 6. Python API (lemma graph S-AY, MCP S-AZ)

```python
from madalean import literature
res = await literature.search(statement, ctx, literature.Budget.for_depth("quick"), text=words, mode=None)
res.items            # LiteratureItem: reference (Reference), texts, quotes (Quote), lean (LeanLink), origin, label
res.cited_lemmas()   # compiled Lean statement, nothing proves it yet
it.node()            # {id, kind: "cited", origin, name, lean, status, conditional, citation, quote}
from madalean.literature import attach
attach.provided_items(ctx, dossier)   # the project's attachment statements, same type, origin "attachment"
literature.try_conditional / check_conditional / upgrade / verdict_of   # conditional proofs
```

## 7. Limits (honest)

- Full texts are read only from your Sources (an arXiv source imported with « Ajouter aux Sources » is then quoted
  from its theorem environments); open-access PDFs found online are not downloaded by the search itself.
- Quotes come from abstracts and reviews, which state the main result only; the exact hypotheses may be in the
  paper. The quote is exact, its scope is the reviewer's / the authors' summary.
- The real vision path depends on the provider adapters accepting image parts (OpenAI-style `image_url`); it was not
  measured with a real model here (tests use a fake vision model). No notation table, no Sage code in digests yet.
- Calcul « Demande » cells (D59): the paperclip attaches to the PROJECT (`POST /api/calcul/{pid}/attachments`,
  `attach.ProjectNotebook`: same Sources import, same read-once digest by SHA-256 + `EXTRACTOR_VERSION`, links in
  `<shelf>/calcul_attachments.json`, each with the `cells` that use it); a request naming « pièce jointe N » gets
  the digest's quotes (`with_mentions`, ≤ 4 quotes of ≤ 800 characters) in the text sent to the model, while the
  cell keeps the user's words. The numbering is the project notebook's, separate from each dossier's.
