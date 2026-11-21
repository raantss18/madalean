---
id: projects
title: Projects and parallel dossiers
order: 130
section: use
audience: all
summary: Grouping dossiers into projects, running several jobs at once, understanding the queue.
---

# Projects and parallel dossiers

## Projects

A **project** groups dossiers: a course chapter, a paper in preparation, a set of exercises. The selector at the top
left (“All projects”) filters the list of dossiers. A project has its Lean workspace, its bibliography, its sources,
its notes, its article outline.

Deleting a project moves it to the trash: “Undo” restores it. Its dossiers are not deleted.

## Several dossiers at once

You can start as many dossiers as you like; they progress in parallel, limited by the host's resources:

| Resource | Slots | Used by |
|---|---|---|
| graphics card | 1 | one local model at a time (Madalean switches models according to the stage) |
| online | 3 | calls to online models |
| Lean | 2 | compilations |

A job only waits for the resource of its current stage; your jobs go before automatic retries. The “Activity” screen
shows what is running, what is waiting and why (“waiting: graphics card”).

![Activity: jobs in parallel](../img/activity.png)

A dossier has only one active job at a time; a new request on a busy dossier is refused with a clear message. Any job
stops on request.

## On every device

All linked devices see the same projects, the same dossiers and the same jobs live. Start a proof from the phone,
follow it on the PC. After a network cut, the device resynchronises by itself.

## Lean workspaces

Each project uses a Lean **workspace** (“Settings › Lean workspaces”):

- *Prover*: Lean 4.9 and the Mathlib the Goedel models were trained on. Pinned: it is never updated, so that the
  local models remain effective.
- *Recent Lean*: latest Mathlib, updated automatically (see [Updates](updates.md)).

A library result can be reused only in the workspace where it was proved.
