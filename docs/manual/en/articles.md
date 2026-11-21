---
id: articles
title: Bibliography, article and blueprint
order: 220
section: research
audience: researcher
summary: Citing in proofs, writing an article from a project, turning a paper into a blueprint of Lean dossiers, and what is reliable.
---

# Bibliography, article and blueprint

## What is reliable, and what is not

| Feature | Reliability | How |
|---|---|---|
| Bibliography in proofs and exports | High | One BibTeX file per project. Add by DOI, arXiv, zbMATH, pasted BibTeX, or from Mathlib's bibliography. A model may only cite existing keys: an invented reference is removed by code, never printed. |
| Lean → article | High for the structure, model-dependent for the prose | Project → LaTeX article (amsart): abstract, sections, each dossier as theorem + written proof, optional Lean appendix, bibliography, verification table. An unproved statement is typeset as a conjecture or claim, marked — never as a theorem. |
| Paper → structured statements | High from LaTeX sources (arXiv), medium from a PDF | arXiv sources first; a PDF through its text layer, and a model that reads PDFs when a key allows it; formulas from a scanned PDF are not reliable without review. Result: a **blueprint**, one dossier per definition, lemma or theorem, with the original text, its place in the paper and its dependencies. |
| Paper → Lean statements | Medium (textbook, graduate level), low (research level with objects absent from Mathlib) | Each node goes through understanding → translation with lemma retrieval; missing definitions are detected and become nodes « to define ». Always reviewed by you: the paper's text is shown next to the Lean statement. |
| Paper → Lean proofs | Low to medium | The paper's proof is given to the prover as a hint. Elementary lemmas are often proved, deep results rarely. The graph shows honestly what is proved, only stated, or blocked. |

**No result is presented as verified unless Lean accepted its proof and the proofs of all its dependencies.**

## Citing

In any text (statement, written proof, explanation, note, article section), a citation uses the BibTeX key:
`[@hardy-wright]`, `[@hardy-wright, Thm 2.1]`, `[see @a, p. 3; @b]`. Autocompletion offers the project's keys. Exports
print only the cited references: PDF with biblatex and biber if installed, otherwise BibTeX; the `.zip` contains
`refs.bib`.

## Writing the article
<!-- verify after integration: button and screen names of the research screens (S-D) -->

« Write the article » assembles an article from the project: title, authors, abstract, sections, one block per
dossier. Each block is an editable, versioned draft. The verification table gives, for each result: Lean name,
state (verified, statement accepted, no), Lean version, Mathlib revision, axioms. Output: PDF, `.tex`, `.md`, and a
`.zip` with the Lean files of the verified results.

## From a paper to a blueprint

1. Add the paper to your sources (preferably by its arXiv identifier: the LaTeX sources give a much better result
   than the PDF).
2. « Extract the blueprint »: definitions, lemmas, theorems, with their number (« Lemma 2.3 »), text, proof, and the
   dependencies found in the proofs (`\ref`, « by Lemma 2.3 »).
3. Dependencies written in prose (« by the previous lemma ») often escape extraction: an optional model pass
   proposes edges **marked « proposed »**, which you accept or reject.
4. Create the dossiers: each node becomes a dossier linked to the source and to its location in the paper.
5. The **blueprint graph** colours each node by its state: not created, stated, Lean statement accepted, defined,
   proved, verified (proved and all its dependencies verified), blocked (uses a definition without an accepted Lean
   statement). A click opens the dossier.

Honest measurement (three short arXiv papers, checked by hand): statements found 12 of 12 from the TeX and from the
PDF; proofs 10 of 11 from the TeX, 8 of 11 from the PDF; dependencies written in prose: 2 of 7 without a model pass.
These figures come from a small sample.

## Publishing

A project can be published as a static site that anyone can verify: see [Publishing a project](publish.md).
