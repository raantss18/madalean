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
<!-- verify after integration: button and screen names of the research screens (S-D) -->

Papers, books, lecture notes, arranged on **shelves**: one per project, a general shelf, and the *Mathlib* shelf
(read-only, taken from Mathlib's bibliography). To add a source:

| By | What Madalean does |
|---|---|
| DOI, arXiv identifier, ISBN, `Zbl …`, OpenAlex identifier | fetches verified metadata; for arXiv, also the TeX sources and the PDF; for a DOI, the PDF only if it is open access |
| URL | metadata of the page only |
| PDF, TeX, archive or EPUB file | looks for an identifier in the first pages; otherwise guessed metadata, marked **unverified** |
| BibTeX, RIS, CSL-JSON, Zotero export (RDF or zip) | imports the references and the files attached in the archive |
| form | manual entry |

Duplicates (same DOI, same arXiv id, very close title) are flagged. Each source has tags, collections, a reading
status, notes, and its BibTeX key. Export as BibTeX, RIS or CSL-JSON.

Metadata guessed from a file, or proposed by a model, stays marked “unverified” until you confirm it.

## Literature search

“Search for papers” queries arXiv, zbMATH Open, Crossref, OpenAlex and Semantic Scholar. **Only your query is
sent.** A provider that does not answer is reported, without blocking the others. From a paper: related, citing and
cited works (OpenAlex).

“Reading list”: from a question, a model chooses among results **actually returned by the databases** and says why;
it cannot invent a reference (any unknown identifier is rejected and counted).

In *Local* mode these searches are refused: they need the network.

## Reading and annotating

The reader shows the PDF next to the extracted text. Highlight, add a margin note: annotations are anchored to the
page and position, and can be found by search.

The full text of each source is indexed **locally**, split into passages with their page and section. For a PDF
without a text layer (scan), character recognition exists, but formulas read this way are not reliable.

## Questions grounded in your sources

Ask a question about a source, a project, or a selection: the answer cites precise **passages**.

- Each citation leads to the passage (click: the page opens at the right place).
- The citation is checked by code: the cited passage must contain the quoted text. A sentence without a valid
  citation is shown struck through or greyed.
- If no relevant passage is found, the answer says so, **without calling a model**.
- An optional “general knowledge” part is kept separate and marked as such, without citations.

What the check guarantees: the cited passage exists and contains the quotation. What it does not guarantee: that the
passage *justifies* the sentence. Read the passage for the important points.

Other requests: “Summarise” (what the paper proves, its definitions, its dependencies), “Compare” two to four
sources.

## What goes over the Internet

Search queries, identifiers (DOI, arXiv…) and the download of open-access files. Questions about your sources go
through the chosen model, with the retained passages: in *Local* mode, only through a local model. See
[Models and keys](models-keys.md#what-is-sent-and-to-whom).
