---
id: notes
title: Notes
order: 230
section: research
audience: all
summary: Linked notes in Markdown, LaTeX and Lean; links, backlinks, graph, versions and editing on several devices.
---

# Notes

Notes belong to Madalean (this is not an Obsidian vault) and are filed by project. They are written in Markdown,
with `$…$` and `$$…$$` formulas and Lean code blocks.

## Links

| Syntax | Target |
|---|---|
| `[[Title]]`, `[[Title\|displayed text]]` | a note of the same project (title, case-insensitive) |
| `[[dossier:Title]]` or `[[dossier:ID]]` | a dossier (theorem, conjecture, lemma…) |
| `[[@key]]`, `[[@key#p12]]` | a source, optionally at a page |
| `[[passage:ID]]` | a specific passage of a source |
| `[[lib:Name]]` | a library result (Lean name) |

Each note shows its **backlinks** (the notes pointing to it). The project's **graph** (“Graph” button)
connects notes, dossiers and sources; it can be filtered by tag. Tags are written `#tag` in the text.

Renaming a note updates the `[[Old title]]` links in the project's other notes.

## Lean in notes

Below the editor, the “Lean blocks” part lists every `lean` block of the note. “Check all with Lean” compiles them
all in the project's workspace (“Check with Lean” on one block checks only that one); each block shows “Lean
accepts” or “Lean rejects”, with the errors at the right line. “Make it a dossier” opens a dossier with the block's
statement and adds a link to it below the block.

## Research log

“Today’s note” creates (or opens) the “research log” note dated today, with the list of dossiers worked on that
day.

## Versions and several devices

Every save creates a revision; all are kept. Two revisions can be compared and an old one restored (which creates a
new revision: nothing is lost). A deleted note goes to the trash.

If the same note is edited on two devices, changes to different lines are merged automatically. If both devices
changed the same lines, Madalean shows both versions of each conflicting passage and you choose.

## Export

The “.md” button of the editor downloads the note as Markdown.
