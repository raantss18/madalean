---
id: jupyter
title: Jupyter and Sage
order: 240
section: research
audience: researcher
summary: Built-in JupyterLab with the Python and SageMath kernels, the assistant next to the notebook, and who can access it.
---

# Jupyter and Sage

The “Notebook” screen opens **JupyterLab**, started on demand by the host computer, behind the same connection as
the rest of Madalean. Notebooks are stored in `~/Documents/Madalean/notebooks/`.

## Kernels

| Kernel | Available if |
|---|---|
| Python 3 | always (with JupyterLab) |
| SageMath | Madalean's copy is installed, or the system's SageMath is compatible |
| Lean 4 | not provided: no Lean 4 kernel is reliable enough today. Use dossiers or the `lean` blocks of [notes](notes.md). |

Madalean installs its own copy of SageMath on demand, or reuses your system's if it is compatible: see
[What Madalean installs › SageMath](components.md#sagemath).

## The assistant next to the notebook

The assistant panel reads the open notebook (cells and outputs) and can **append a cell** at the end, which you run
yourself. It answers with the model of the current mode; in *Local* mode, only a local model.

## Who can access it

A Jupyter kernel runs arbitrary code on the host computer. Therefore:

- on the host, the notebook is always available;
- from a linked device, it is reachable only if the host allowed it (“Settings › Notebook and access”), a setting
  that can be changed **only from the host**;
- Jupyter's internal token never leaves the server.

The experiments of the [conjecture workshop](conjectures.md) use separate, confined kernels, and run only after your
approval.
