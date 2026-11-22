---
id: calcul
title: Compute (Sage and Python)
order: 205
section: research
audience: researcher
summary: Sage or Python notebooks in an offline sandbox, a model that writes code on request, and one click to turn a result into a conjecture, a note, a Lean dossier or an article block.
---

# Compute (Sage and Python)

The **Compute** screen (project menu) holds the project's **notebooks** (“New notebook”, SageMath or Python). A
notebook is a list of cells sharing one kernel: variables persist from one cell to the next. The file is an ordinary
Jupyter notebook: “Open in JupyterLab” opens it as is, “Download (.ipynb)” gives a copy. Code runs on the host
computer in the **same sandbox** as the conjecture workshop's experiments: no network access, no access to your keys
or personal files, limited time and output.

## Who can run what

- **Your cells** (the ones you type) run with **Run** (or Ctrl+Enter, Shift+Enter to move to the next one). “Run
  all” runs the whole notebook again.
- **Code written by the model** is marked “To review”: it runs only after **Approve and run**. The approval is for
  that exact code: if it changes, read it and approve it again.
- From a linked phone or tablet you can read and write cells; running them is allowed only when the host ticked
  “Allow experiments from linked devices” (“Settings › Notebook and access”, host-only setting).

## Asking the model

The **+** button under the last cell adds a cell (an empty one also appears after the last cell runs). Type Sage
code, or describe the computation in words (“the roots of x^5+x^3+x+1 in F_16”): the cell recognises what you typed
and shows it as “Code / Request” — one click fixes a wrong guess. Shift+Enter runs the code or sends the request.
The cell type (Code, Request, Text, Figure) is the small menu at the top of the cell.

For a request, the model writes the code in a few seconds; it appears while being written, checked against the
installed Sage version before it is shown. “Rewrite”, right under the request, starts again at any time; “Approve
and run” is right under the code. When the code uses names defined above, the cell says so. If the run fails, the
model corrects it automatically (at most three times): each correction is a version of the cell (“Go back to the
previous version”) and still needs your approval, unless the host chose to run model code without approval.

On an error, “Explain the error” says in plain words what is wrong and proposes a fix you apply in one click (to
approve). In “⋯”, “Explain line by line” comments each line. Requests that worked become **learned recipes**: a
similar request is written at once (notebook “⋯” › “Learned recipes” to see or delete them). A computation proves nothing in
general: it checks cases.

## Outputs

Text, formulas (rendered as in LaTeX) and plots. An output that is “Out of date” (code or a cell above changed since)
is flagged. Each cell keeps the versions of its code (“History”).

## Using a result

In the “More actions” of a cell that has an output:

| Action | Effect |
|---|---|
| Create a conjecture | creates a project conjecture; the code and its output are attached as motivation |
| Add to a note | copies the code and its output into a new note |
| Create a Lean dossier | opens a dossier with the statement to prove, prefilled from the result (correct it if needed) |
| Insert in the article | the result goes into the article; the code goes to the “Computations” section at the end |

A PNG plot from Compute can also be inserted as an article figure (“Insert › Figure… › From Calcul” in the article
editor).

## SageMath not installed yet

Python notebooks work right away. SageMath is installed on demand (about 1.5 GB to download, nearly 5 GB on disk):
**Install Sage** button in a Sage notebook, on the host computer. The screen shows the current step and the
percentage.
