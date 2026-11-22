---
id: sources
title: Sources, literature search and grounded questions
order: 210
section: research
audience: researcher
summary: The sources library (papers, books), searching the databases, the annotated reader, and answers that cite your sources.
---

# Sources, literature search and grounded questions

## The sources library

The project's “Sources” screen has three tabs: “Library”, “Literature search” and “Ask a question”. Papers, books,
lecture notes are arranged there on **shelves**: one per project, a general shelf, and the *Mathlib* shelf
(read-only, taken from Mathlib's bibliography). To add a source, “Add” offers three ways: “Identifier”, “File”,
“Paste”.

| By | What Madalean does |
|---|---|
| “Identifier”: DOI, arXiv identifier, ISBN, `Zbl …`, OpenAlex identifier | fetches verified metadata; for arXiv, also the TeX sources and the PDF; for a DOI, the PDF only if it is open access |
| “Identifier”: web address | metadata of the page only |
| “File”: PDF, TeX source (`.tex`, `.tar.gz`, `.zip`) | looks for an identifier in the first pages; otherwise guessed metadata, marked **unverified** |
| “File” or “Paste”: BibTeX, RIS, CSL-JSON, Zotero export (RDF, or `.zip` with the attached files) | imports the references and the files attached in the archive |

Duplicates (same DOI, same arXiv id, same title) are flagged. Each source has tags, a reading status, annotations,
and its BibTeX key. The “BibTeX” button exports the shelf.

Metadata guessed from a file stays marked “metadata to check” until you confirm it (“They are right” in the
reader).

## Literature search

The “Literature search” tab queries arXiv, zbMATH Open, Crossref, OpenAlex and Semantic Scholar and merges the
results. **Only your query is sent.** A service that does not answer is marked “unavailable”, without blocking the
others. “Add” puts a result in your sources.

In *Local* mode these searches are refused: they need the network.

## Reading and annotating

The reader shows the PDF next to the extracted text. “Highlight” a passage, add a “Margin note”: annotations are
anchored to the page and position, and can be found by search.

The full text of each source is indexed **locally**, split into passages with their page and section. For a PDF
without a text layer (scan), character recognition exists, but formulas read this way are not reliable.

## Questions grounded in your sources

Ask a question (“Ask a question” tab, or “Questions about this text” in the reader): the answer cites precise
**passages**.

- Each citation leads to the passage (click: the page opens at the right place).
- The citation is checked by code: the cited passage must contain the quoted text. A sentence without a valid
  citation is shown struck through or greyed.
- If no relevant passage is found, the answer says so, **without calling a model**.
- An optional “general knowledge” part (“Add general knowledge (marked)”) is kept separate and marked as such,
  without citations.

What the check guarantees: the cited passage exists and contains the quotation. What it does not guarantee: that the
passage *justifies* the sentence. Read the passage for the important points.

Other requests: “Summarise” (what the paper proves, its definitions, its dependencies) and “Compare” several
sources (“Compare with…” in the reader).

## What goes over the Internet

Search queries, identifiers (DOI, arXiv…) and the download of open-access files. Questions about your sources go
through the chosen model, with the retained passages: in *Local* mode, only through a local model. See
[Models and keys](models-keys.md#what-is-sent-and-to-whom).
