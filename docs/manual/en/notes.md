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

Each note shows its **backlinks** (the notes pointing to it). The project's **graph** connects notes, dossiers and
sources; it can be filtered by tag. Tags are written `#tag` in the text.

Renaming a note updates the `[[Old title]]` links in the project's other notes.

## Lean in notes

“Check with Lean” compiles every `lean` block of the note in the project's workspace and shows the errors at the
right line. “Create a dossier” from a block containing a theorem opens a dossier with that statement (or, from a
paragraph, a dossier whose problem it is) and adds a link to it below the block.
<!-- verify after integration: button labels in the notes editor (S-D) -->

## Research log

“Today's note” creates (or opens) the note dated today, with the list of dossiers worked on that day.

## Versions and several devices

Every save creates a revision; all are kept. Two revisions can be compared and an old one restored (which creates a
new revision: nothing is lost). A deleted note goes to the trash.

If the same note is edited on two devices, changes to different lines are merged automatically. If both devices
changed the same lines, Madalean shows both versions of each conflicting passage and you choose.

## Attachments and export

Images (PNG, JPEG, GIF, WebP) and PDFs up to 10 MB. Export a note, or the whole notebook of the project, as
Markdown, HTML or PDF.
