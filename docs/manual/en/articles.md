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
| Paper → Lean statements | Medium (textbook, graduate level), low (research level with objects absent from Mathlib) | Each node goes through understanding → translation with lemma retrieval; missing definitions are detected and become nodes “to define”. Always reviewed by you: the paper's text is shown next to the Lean statement. |
| Paper → Lean proofs | Low to medium | The paper's proof is given to the prover as a hint. Elementary lemmas are often proved, deep results rarely. The graph shows honestly what is proved, only stated, or blocked. |

**No result is presented as verified unless Lean accepted its proof and the proofs of all its dependencies.**

## Citing

In any text (statement, written proof, explanation, note, article section), a citation uses the BibTeX key:
`[@hardy-wright]`, `[@hardy-wright, Thm 2.1]`, `[see @a, p. 3; @b]`. Autocompletion offers the project's keys. Exports
print only the cited references: PDF with biblatex and biber if installed, otherwise BibTeX; the `.zip` contains
`refs.bib`.

## Writing the article

The project's “Article” screen is a visual LaTeX editor: the text you see *is* the LaTeX source (rendered
formulas, theorem boxes, citations, figures), and “LaTeX source” shows the same text raw. On first opening,
Madalean prepares the article from the project: an introduction and one block per dossier. The outline is on the
left, the “PDF preview” on the right on a wide screen; “Compile” produces the PDF. The assistant (“Rewrite”,
“Shorten”, “Make more formal”…) only makes suggestions, which you accept or reject in the text.

When compiling, Madalean adds the bibliography (only the cited references), the **Lean verification table** (for
each result: Lean name, verified or not, Lean and Mathlib versions, axioms) and, if you ask for it in “Advanced
options”, an appendix with the Lean code. A theorem linked to a dossier whose proof is not verified by Lean is
printed as a claim, never as a theorem.

Under “More actions”: “Versions” (an automatic version at most every 2 minutes of writing, plus your own),
“Download the PDF”, and “Overleaf…” to send the project to Overleaf (or download the project as a `.zip`) and take
it back.

## From a paper to a blueprint

1. Add the paper to your sources (preferably by its arXiv identifier: the LaTeX sources give a much better result
   than the PDF).
2. In the source's reader, “Extract the blueprint”: definitions, lemmas, theorems, with their number (“Lemma 2.3”), text, proof, and the
   dependencies found in the proofs (`\ref`, “by Lemma 2.3”).
3. Dependencies written in prose (“by the previous lemma”) often escape extraction: an optional model pass
   proposes links marked **“proposed (to confirm)”**, which you confirm (“Confirm”) or set aside
   (“Discard”).
4. “Create the dossiers”: each node becomes a dossier linked to the source and to its location in the paper.
5. The “Blueprint” screen colours each result by its state: no dossier, stated in words, Lean statement accepted,
   defined, proved (dependencies not verified), verified (proved and all its dependencies verified), blocked (uses
   a definition without an accepted Lean statement), failed. “Open the dossier” opens the dossier.

Honest measurement (three short arXiv papers, checked by hand): statements found 12 of 12 from the TeX and from the
PDF; proofs 10 of 11 from the TeX, 8 of 11 from the PDF; dependencies written in prose: 2 of 7 without a model pass.
These figures come from a small sample.

## From the blueprint to a formal plan

The “Formal plan” tab of the “Blueprint” screen turns the paper into a plan of Lean work, progressively:

1. Tick the theorems you want (the main result, for instance). The button shows how many statements their
   **dependency closure** holds: everything they use according to the paper's explicit references (`\ref`,
   “Proof of Theorem 3”, “by Lemma 2.3” in a PDF), and the links proposed by a model only once you confirmed them.
   An unknown dependency stays unknown: nothing is invented.
2. “Formalise the selection and its dependencies”: dependencies first, each statement **quoted verbatim** from the
   paper (with the definitions it uses) goes to the formalizer; Lean checks the statement; then Madalean looks
   whether Mathlib (or your library) already proves it. A run stops after the chosen number of statements
   (“Statements per run”) or when you press “Stop”; start it again to **resume** where it stopped.
3. When the whole closure is processed, Madalean opens a dossier for the main theorem and, in its problem graph, one
   node per result it uses: those in Mathlib are verified, the others are **conditional** (the paper claims them,
   Lean has not proved them) and each one to prove becomes a **sub-dossier**. Nothing is started: you launch the
   provers from the dossiers.

Each result shows one state: *proved (Lean)*, *in Mathlib*, *to prove*, *statement formalised*, *not formalised*;
“Conditional: rests on …” lists what is not proved yet. The counter gives the proved or in-Mathlib results of the
plan. Clicking a result shows its text from the paper (verbatim, with its place: number, section, line or page)
beside the Lean statement — a model's translation accepted by Lean, to be re-read. “Export (LaTeX)” writes a
blueprint in the style of `leanblueprint` (`\lean`, `\leanok`, `\mathlibok`, `\uses`), “Export (HTML)” a summary
page. Definitions are not formalised yet.

## Publishing

A project can be published as a static site that anyone can verify: see [Publishing a project](publish.md).
