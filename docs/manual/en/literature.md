---
id: literature
title: Literature first: published results and attachments
order: 208
section: research
audience: researcher
summary: During the proof, Madalean looks for published results related to the statement, quotes them word for word and states them in Lean; a result cited but not proved in Lean never makes a proof « verified ».
---

# Literature first: published results and attachments

When the proof of a statement starts, Madalean searches the scholarly databases, in parallel, for related published
results: **zbMATH Open** (reviewed literature, with its reviews), **OpenAlex**, **arXiv**, and your **Sources**. The
search never delays the proof.

## What you see

In the **Proof** step, the **Literature** panel:

- every **reference** comes from a scholarly database (never from a model); a badge says whether it is **published in
  a journal (peer reviewed)** or a **preprint (not reviewed)**;
- the **statement quoted word for word**, with its place (“abstract, sentence 2”, “zbMATH review”, “Theorem 2.1,
  p. 5”);
- its **Lean statement** when a model could translate it (read it again) and its status: **In Mathlib**, **Proved in
  Lean**, **To prove (conditional)** or **No Lean statement**;
- the buttons **Add to Sources**, **Add to the article’s bibliography**, **Prove this lemma**, and the BibTeX record.

When nothing reliable is found, it says so: Madalean never invents a reference or a quotation.

## Conditional proof

When a cited result lets Lean conclude but is not proved in Lean, Madalean says so: **“Conditional proof — not
verified”**, with the reference it rests on. It enters neither the dossier’s proofs nor the library, and the export
spells it out. Click **Prove this lemma**: once Lean accepts the proof of the cited result, the proof is checked again
strictly and becomes **verified**.

## Attachments

The paperclip of the dossier’s thread (and the **Literature** panel) attaches an **image**, a **PDF**, a **LaTeX** or
**BibTeX** file, or a **web address**. The attachment becomes a Source of the project and is **read only once**:
Madalean keeps a digest (the reference, the statements quoted word for word, their Lean statement). Attaching the same
file in another dossier of the project does not read it again. An image is read by a model that can read images
(otherwise it stays “not read”); its transcription is marked as such and the original stays in Sources. **Read again**
reads it again when you ask.

In the thread you can write, for example, “from attachment 2, lemma 3.1, conclude”: Madalean quotes that lemma as
written in the attachment.

In **Calcul**, a “Request” cell has a paperclip too: the file joins the project's Sources (read once, as above) and
the cell shows its attachments. A request such as “according to attachment 1, lemma 1, check p = 7” sends the exact
quote to the model (never the whole document); the code written still needs your approval before it runs.

## Settings and privacy

**Settings › Models › Advanced options**: “Search the literature” (on by default) and its depth (quick ≈ 45 s,
thorough ≈ 2 min 30). In **local mode**, no search is sent over the network: only your Sources and Mathlib are used.
What leaves the computer: the search words drawn from the statement and the identifiers (DOI, arXiv) to check; never
your Lean file, your notes, a key or your name.
