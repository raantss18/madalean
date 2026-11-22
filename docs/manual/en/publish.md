---
id: publish
title: Publishing a project
order: 250
section: research
audience: researcher
summary: Publish a verified project as a static site on a GitHub repository of your choice, independently re-verified by lake build.
---

# Publishing a project

The “Publish” screen (project menu) turns a project into a **static site** that anyone can read and re-verify:

- the article (HTML, and the PDF if you attach it);
- the **dependency graph**, with the state of each result;
- one page per result: natural-language statement, coloured Lean code, written proof, verification information
  (Lean version, Mathlib revision, axioms);
- the verification table and the bibliography;
- the complete **Lean (Lake) project** to download, and, if you ask for it, your computations (Calcul).

A published result takes along everything it depends on: a result is never shown without what it relies on.

The site is sent to a GitHub repository **that you choose**, with a GitHub action that runs `lake build` again on the
published Lean project. The verification badge shown by the site comes from that action, independent of your
computer: a reader does not have to take Madalean's word for it.

## What leaves, and only with your consent

1. **“What you publish”**: tick the results, the notes (none by default), “Attach the paper’s PDF”, “Include the
   computations (Calcul)”, and choose the site licence.
2. **“Prepare the exact list”**: nothing is sent at this step. The screen lists **exactly** what will leave the
   computer (“What will leave this computer”): each file, its type, its origin and its size, what is excluded, and
   what is never published (your keys, your private notes, the PDFs of other authors' papers, your settings).
3. **“Local preview”** builds the site on the computer; “Open the preview” shows it before anything is published.
4. **“Send to GitHub”**: give the repository (`account/name`), tick if needed “Create the repository if it does not
   exist” (and “Private repository”), then “Publish” and confirm with “Yes, publish”. A GitHub key (token) is needed,
   saved in the key settings (the screen links to them); otherwise, the login of the `gh` tool, if it is installed on
   the host, is used. Madalean then turns on the repository's GitHub Pages site; if it cannot, it gives the link to
   turn it on by hand.

Publishing is started from the host computer. If the list changes between its preparation and the sending, Madalean
asks you to prepare it again. A new publication adds a commit to the repository; nothing is sent if nothing changed.

## What the site shows

Each state has a colour, a border style and a written label (never colour alone):

| Mark | Label on the site |
|---|---|
| ✓ | verified by Lean (proof accepted by Lean, and all its dependencies verified) |
| (✓) | proved, dependencies not verified |
| ≔ | definition accepted by Lean |
| ◇ | Lean statement accepted, no proof |
| … | natural-language statement only |
| ✕ | blocked: uses a definition not formalised |

An unverified theorem is never presented as a theorem: it is titled “Claim”, with a warning. The site uses no
tracker, no external font or script.
