---
id: follow-ups
title: Follow-up requests and versions
order: 120
section: use
audience: all
summary: Continuing the discussion on a dossier, choosing which stage to redo, going back to an earlier version.
---

# Follow-up requests and versions

A dossier is never frozen. In the dossier thread, the field “A clarification, a correction?” accepts a request in
plain language:

- “add the hypothesis $n > 0$”
- “and the converse?”
- “a shorter proof”
- “explain step 2”
- “without using `nlinarith`”

`Ctrl+Enter` sends.

## Which stage is redone?

The menu next to “Send” chooses what must change:

| Choice | Effect |
|---|---|
| *Automatic* | a model reads the request and chooses the stage; failing that, keywords decide |
| *Statement* | new Lean statement (following the request) → new proof → new explanation |
| *Proof* | new proof of the same statement → new explanation |
| *Explanation* | new explanation only |

If the request changes the statement, the old proof no longer applies: Madalean searches for a new one. The buttons
below the proof (“Simpler proof”, “Another method”, “Explain in more detail”, “Split into lemmas”) are ready-made
requests.

## Versions

Each statement, each proof, each explanation produces a **new version**; nothing is erased. Each version shows its
source (a model, with its name, or you), the request that produced it and, for a proof, its Lean verdict.

“Go back to this one” makes a version current without deleting the others. Going back to a proof also brings back
the statement it proves. A proof counts as the dossier's proof only if it proves the **current** statement.

## What the assistant remembers

- **Your profile** (“Settings › Profile”): read before every translation and every explanation.
- **The dossier thread**: each correction builds on the previous versions.
- **The library**: each proved result is offered as a lemma to later proofs in the same Lean workspace.
- Lemma names already rejected by Lean in this dossier are no longer proposed.
