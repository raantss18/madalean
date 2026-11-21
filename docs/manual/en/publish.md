---
id: publish
title: Publishing a project
order: 250
section: research
audience: researcher
summary: Publish a verified project as a static site on a GitHub repository of your choice, independently re-verified by lake build.
---

# Publishing a project

<!-- verify after integration: the « Publier » feature is not built yet; this page describes the design of ARCHITECTURE §17 and the template in site/publication -->

« Publish » turns a project into a **static site** that anyone can read and re-verify:

- the article (HTML and PDF);
- the blueprint's **dependency graph**, with the state of each result;
- one page per statement: natural-language statement, highlighted Lean code, written proof, verification
  information (Lean version, Mathlib revision, axioms, date);
- the bibliography;
- the complete **Lake project** to download.

The site is pushed to a GitHub repository **of your choice**, with a GitHub Action that re-runs `lake build` on the
published Lean project. The verification badge shown on the site comes from that action, independent of your
computer: a reader does not have to take Madalean's word for it.

## What leaves the machine, and only with your consent

1. « Preview » builds the site locally: you browse it before anything is published.
2. The publish screen lists **exactly** what will leave the machine: files, dossiers, notes, sources. Nothing private
   is published without an explicit choice, item by item. The PDFs of your sources are never published: only their
   bibliographic reference is.
3. Publishing uses the `gh` tool or a GitHub token kept in the host's keyring.

## What the site shows

| Colour and mark | State |
|---|---|
| solid green, ✓ | verified: proof accepted by Lean, and all its dependencies verified |
| light green | proved, but a dependency is not yet |
| blue | Lean statement accepted, no proof |
| dashed outline | natural-language statement only |
| red | blocked: depends on a definition without a Lean statement |

An unverified result is never presented as a theorem. The site uses no tracker, no external font or script, and can
be read without JavaScript.
