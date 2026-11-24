---
id: memory
title: Memory — export, import, back up
order: 146
section: settings
audience: researcher
summary: Everything Madalean learned (library, lessons, recipes, graphs, digests) in one file, re-checked by Lean on import; automatic backups; a dataset of verified pairs.
---

# Memory — export, import, back up

Madalean learns without training a model: the **library** of proved results, the **lessons** drawn from its
mistakes, the computation **recipes**, the **graphs** of your problems, the **digests** of attachments. Settings ›
“Memory” puts all of it in one `.madalean-memory` file, to keep or to move to another computer.

## Export

Tick the parts to include and, if you like, only some projects, then “Export the memory”.

- **Digests of protected sources** (©, or unknown licence) are left out by default: their licence may forbid
  redistribution. The file says what is missing. Tick “Include digests of copyrighted (©) sources” for a strictly
  personal copy.
- The **original files** of attachments (PDF, images…) are included only when you tick it.
- The file carries the fingerprint (SHA-256) of each part and the Lean and Mathlib versions of your workspaces.

## Import

On the host computer only. Choose a file: Madalean first shows a **preview** — what would be added, checked,
skipped, and why — without writing anything. “Import” applies it.

Nothing is taken on trust:

- every **proof** is re-checked here by Lean, in a workspace with **the same Lean and Mathlib versions**. Accepted,
  it enters the library. Otherwise it stays in “Imported, not verified” with the reason (no workspace with the same
  versions, Lean rejects the proof, a result it uses is missing…) and is not used. After installing the right
  workspace, “Re-check”;
- computation **recipes** are re-read by Sage or Python (never run); code that reaches the system is refused; an
  imported recipe never replaces yours;
- **lessons** keep their evidence but start again from zero: they count only once they helped here;
- **graphs** from elsewhere stay read-only **references** (the preview says how many of their lemmas are already in
  your graphs); your graphs are never changed;
- **digests** join the project with the same id when it exists (as “provided results”: never proofs), otherwise they
  are references;
- duplicates (same statement up to renaming, same lesson, same code) are skipped;
- text that addresses a model (“ignore the instructions…”) is refused; a modified file (different fingerprint) is
  refused as a whole.

## Automatic backups

Tick “Back up automatically”, choose the frequency (day, week, month), how many copies to keep and the folder
(default `~/.config/madalean/backups`). Copies stay on this computer; only Madalean's oldest copies are deleted,
never your other files. “Back up now” writes one at once. To restore: “Import” a copy.

## Training dataset

“Export the dataset” writes a JSONL file of the pairs **Lean verified** (statement → proof, error → fix), with the
licence and provenance of each row. It prepares a possible later fine-tune of a local model (off, not provided):
Madalean trains no model.

See also: [Problem graph and lessons](proof-graph.md) · [Library](library.md) · [Security](security.md).
