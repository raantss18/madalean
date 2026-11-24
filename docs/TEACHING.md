# Verified exercises (DECISIONS D63)

Screen: logo menu › **Exercices** (« Apprendre » mode; `/exercices`, `/exercices/<id>`). Code: `madalean/teaching/`,
`madalean/server/plugins/teaching.py`, `web/src/screens/learn/`. API: docs/API.md §6m. Terms in Malagasy: docs/I18N_MG.md.

## Learner
1. Filters: level (lycée, licence, master, olympiade), domain, progress, text, language of the statements.
2. Answer **in Lean** (a tactic block; a whole theorem is accepted, only its proof is used) or **in words**.
   - Lean: the server writes the header and the signature itself, then a fresh strict check (no `sorry`, no other
     declaration, standard axioms only).
   - Words: a model writes a Lean proof that follows the argument (two tries, the second one with Lean's errors; it
     answers `NO_PROOF` when the argument proves nothing), Lean checks it, then the model names the gaps. What Lean
     certifies is the formal proof shown on the screen, not the words; a failure never means the statement is false.
3. Hints one by one, the first one after an attempt. The solution comes after all of them (or once solved), only if
   Lean accepts it in the current workspace; « Expliquer » (D45) reads it line by line.
4. Progress per device (browser session of the host = `host`), in `<config>/teaching/progress/` on the host; the draft
   stays in the browser.

## Teacher
- « En faire un exercice » from a dossier's ⋯ menu or the screen: Lean must read the theorem alone (no library lemma
  above it); the dossier's proof becomes the solution if Lean accepts it.
- Worksheet (PDF / LaTeX) of the ticked exercises, with or without the Lean statements and the verified solutions, in
  French, Malagasy or English (the solutions a learner has not reached yet are in it: it is the teacher's file).
- Import / export of a bank file.

## Bank file
`{"format": "madalean-exercises/1", "exercises": [ … ]}`, at most 512 KB and 300 exercises. An exercise:

| Field | |
|---|---|
| `id` | `[a-z0-9-]`, 64 characters |
| `level`, `domain` | `lycee licence master olympiade`; `arithmetique algebre algebre-lineaire analyse ensembles inegalites topologie autre` |
| `title`, `statement` | `{fr, mg?, en?}` (Markdown + `$…$`) |
| `lean` | exactly one `theorem name … := by sorry` (no import: Madalean's header is used) |
| `hints` | up to 8 `{fr, mg?, en?}`, from light to complete |
| `solution` | optional tactic block |
| `source`, `licence` | text |

An import is untrusted and refused as a whole on the first problem: unknown field, HTML, image, `javascript:`, file or
definition TeX commands, control / bidi characters, any Lean command. Nothing imported is shown as verified before
Lean accepted it.

## Seed bank
23 exercises written for Madalean (CC0; classics restated), source `scripts/dev/exercise_seed.py`;
`tests/test_exercises.py` compiles every statement and every solution (axioms included) with the real Lean.

## Limits
No accounts or classes: progress is per device, and the gates (attempt, hints) help learning, they are not an exam.
The fidelity of a formalised proof in words to the words is the model's reading.
