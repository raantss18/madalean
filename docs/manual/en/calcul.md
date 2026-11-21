---
id: calcul
title: Compute (Sage and Python)
order: 205
section: research
audience: researcher
summary: Sage or Python cells in an offline sandbox, the assistant alongside, and one click to turn a result into a conjecture, a note, a Lean dossier or an article block.
---

# Compute (Sage and Python)

The **Compute** screen (project menu) is one worksheet per project: a list of SageMath or Python cells run on the
host computer in the **same sandbox** as the conjecture workshop's experiments: no network access, no access to your
keys or personal files, limited time and output. Variables persist from one cell to the next (one kernel per
project).

## Who can run what

- **Your cells** (the ones you type) run when you click **Run** (or Ctrl+Enter).
- **The assistant's cells** are marked “To review”: they run only after **Approve this code**. The approval is for
  that exact code: if you or the assistant change it, read it and approve it again.
- From a paired phone or tablet you can read and write cells; running them is allowed only when the host enabled
  “experiments from devices” (host-only setting).

## The assistant

On the right (at the top on a phone), describe the computation you want: the assistant **writes a cell**. Under each
cell, **Fix** proposes a repaired version after an error, **Explain** comments on the code and its output. A
computation proves nothing in general: it checks cases.

## Outputs

Text, formulas (with `tex(x)`, rendered by KaTeX) and plots (PNG or SVG, sanitised before display). Each cell keeps
its latest runs and the versions of its code (**History**).

## Using a result

Under a successful output:

| Button | Effect |
|---|---|
| → Conjecture | creates a project conjecture; the computation is attached as motivation |
| → Note | copies the code and its output into a note (tag “calcul”) |
| → Lean dossier | opens a dossier with the statement you write; nothing starts before you open it |
| → Article | adds the formula or the output as a block of the project's article |

Plots are not yet copied into the article's PDF export.

## SageMath not installed yet

Python cells work right away. SageMath (about 2 GB) installs on demand: **Install SageMath** button on the host,
with progress shown.
<!-- verify after integration: Sage on-demand install progress from the Calcul screen on a machine without Sage -->
