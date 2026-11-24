# « Mémoire qui grossit » — memory bundles, backups, training dataset (D62, S-BD)

Everything Madalean learns without training a model — the library of Lean-checked results, the lessons (D57b), the
Calcul recipes (D39), the problem graphs (D57), the attachment digests (D56) — can leave the machine as **one
portable, verifiable file** and come back **without being trusted**. Code: `madalean/memory.py`, plugin
`madalean/server/plugins/memory.py`, screen Réglages › « Mémoire » (`web/src/screens/settings/Memory.svelte`).
Tests: `tests/test_memory.py`, `web/e2e/memory.spec.ts`.

## 1. The bundle: `.madalean-memory`

A zip with a fixed set of member names (anything else is refused on import):

| Member | Content |
|---|---|
| `manifest.json` | `format: "madalean-memory"`, `schema: 1`, `madalean` (version), `created` (UTC), `workspaces` (`{key: {lean, mathlib}}` of every workspace a library row comes from), `parts` (`{name: {path, sha256, count, bytes}}`), `files` (`[{path, sha256, bytes}]`), `excluded` (`[{what, why, license}]`), `integrity` |
| `parts/library.json` | `[{name, title, statement, code, workspace, deps, t, nl, stamp: {workspace, lean, mathlib, axioms, checked, verdict: "strict"}, provenance: {model, by_user, imported}}]` — the closure: a result travels with the results it uses |
| `parts/lessons.json` | the lessons store's rows (D57b), evidence included |
| `parts/recipes.json` | the **best** version of each intent: `{request, requests, summary, language: sage\|python, version, uses, code, runs_ok, approved, origin}` |
| `parts/graphs.json` | `[{dossier_id, project_id, project, title, graph}]` (the plan file's `graph`, D57/D59) |
| `parts/digests.json` | `[{shelf, project, license, digest, files: [{sha256, name}]}]` — text only |
| `files/<sha256>` | original attachment files, only when « Inclure les fichiers d'origine » is ticked |

`integrity` is the SHA-256 of the canonical JSON of the manifest without that field (sorted keys, no spaces). With
the per-part SHA-256 it detects corruption and naive tampering. **It is not a signature**: anybody can rebuild a
consistent bundle, which is why nothing in it is trusted (§3). Signing bundles was rejected for now: it would only
say who made the file, and a proof from a trusted friend must be re-checked by Lean anyway.

Choices at export (Réglages › Mémoire, or `GET /api/memory/export?…`): parts, projects (graphs, digests and the
library entries of those projects' dossiers; « Hors projet » = the global shelf), © digests, original files.

**Licences.** A digest is included by default only when its Source's licence is redistributable (the same rule as the
publication of source files, `research/publish.REDISTRIBUTABLE`: CC BY / CC0 / public domain). Others (© or unknown)
are left out and listed in `manifest.excluded` with `why: license_not_redistributable`, unless the user ticks « Inclure
les résumés de sources protégées ». Original files are never included unless ticked. The glossary is built into the
application (no user entries): it is not part of the bundle.

## 2. Import: preview first, then re-verification

`POST /api/memory/import` (host only, raw bytes) reads and checks the bundle and returns a **dry-run preview** — per
part and per item: `add`, `verify`, `validate`, `reference`, `unverified` or `skip`, with the reason. Nothing is
written. `POST /api/memory/import/{token}` applies it in the background (one import at a time); progress events
`memory.import`; `GET /api/memory/import/{token}` gives the report.

| Part | What happens |
|---|---|
| Library | A local workspace with the **same Lean and Mathlib versions** as the exporting one is looked for (any key). None → « importée, non vérifiée » (`no_matching_workspace`). Otherwise comments are stripped, the last theorem must have the row's name and the displayed statement must be the one proved, then a **fresh strict Lean** checks `GOEDEL_HEADER + dependencies + proof` with the axiom probe (D28 filter, sandbox, no warm Lean). Accepted → library entry with `origin = {bundle, from, checked, lean, mathlib, axioms, nl, model}`. Refused → `<config>/memory/unverified.json` with the reason (`lean_rejected`, `statement_mismatch`, `missing_dependency`, `lean_timeout`…), never used by a prover; « Revérifier » retries them (after installing the right workspace). |
| Duplicates | Same statement up to renaming (D59 `statement_key`) in the same workspace → `duplicate`; same name, other statement → `name_taken`. |
| Lessons | Evidence kept, counters **neutral** (`ok = bad = used = 0`, `unconfirmed`): they must help a Lean-accepted proof here to count. Same id → `duplicate`. A rename must be two plain identifiers; tactics must be tactic names. |
| Recipes | Statically screened (no `os` / `subprocess` / `socket` / `open(` / `eval(` …), re-keyed by the local request analysis, then re-validated: Sage's preparser + compile + names of the installed Sage (`syntaxcards.validate_sage`; without Sage → skipped, `sage_unavailable`), Python `compile`. Stored as a version `origin: import`: it becomes the best version only when the request had none — it never replaces local work. |
| Graphs | **Read-only references** in `<config>/memory/references/graphs/` with the number of their statements already present in local graphs (same `statement_key`). Local graphs are never changed. |
| Digests | Into the project's shelf when a project with the same id exists (they become « résultats fournis », D56: conditional, never proofs), else a read-only reference. Statements that read like instructions to a model are dropped. Original files go through the normal Sources import (type sniffing, sizes, archives) and only into an existing project. |

All text goes through the hostile-content rules: control / bidirectional characters removed, bounded lengths,
`looks_like_injection` (the news heuristic) → item refused (`suspect_text`).

## 3. Threat model (summary — details in SECURITY.md « Memory bundles »)

An imported bundle is attacker-controlled. It can try to: make a false statement look « vérifiée » (→ only a local
fresh strict Lean makes anything verified; the statement shown is recomputed from the proved code); run code on the
host (→ Lean: D28 filter + bubblewrap sandbox; recipes: static screen + validation without execution; nothing is
executed at import); inject instructions into prover prompts via titles, comments, lessons or digest quotes (→
comments stripped, injection heuristic, bounded text); exhaust resources (→ 200 MB bundle, 40 MB per file, 64 MB per
part, 2000 members, ratio 200, 20 000 rows per part, 2 MB per graph); escape the target directory (→ fixed member
names, files stored by verified SHA-256, nothing extracted to disk by name). Import is host-only.

## 4. Automatic backups

Réglages › Mémoire › « Sauvegardes automatiques » (off by default): every day / week / month, keep N (1–100), folder
(absolute path; default `<config>/backups`, i.e. `~/.config/madalean/backups`). The server checks hourly; a backup is
`madalean-memory-YYYYMMDD-HHMMSS.madalean-memory` (0600, folder 0700), written atomically; rotation deletes only files
matching that exact pattern. Never uploaded anywhere. Settings in `<config>/memory/backups.json`. A failure is
logged, shown in the screen, and retried at the next period. Backups follow the export defaults (© digests left out
unless ticked).

## 5. API

See API.md « Memory (D62) ».

## 6. Training dataset — input for a future, optional local fine-tune (not implemented)

`GET /api/memory/dataset` (« Exporter le jeu de données ») writes JSONL, one row per verified pair:

```json
{"schema": "madalean-train/1", "type": "statement_proof", "statement": "theorem … :=", "nl": "…", "proof": "theorem … := by …",
 "deps": [], "lean": "v4.9.0-rc1", "mathlib": "…", "workspace": "lean-prover49", "verified": "lean-strict",
 "license": "user (own work, not redistributed without the user's consent)",
 "provenance": {"source": "madalean" | "imported+reverified", "model": "…", "by_user": false}}
{"schema": "madalean-train/1", "type": "error_fix", "error": "unknown identifier 'Nat.foo'", "fix": "use `Nat.bar`",
 "shape": "…", "lean": "…", "mathlib": "…", "verified": "lean-strict (learned from a verified proof)",
 "license": "user (own work)", "provenance": {"source": "lessons", "lesson": "ls-…", "ok": 3, "bad": 0}}
```

Only verified items: library results (every one passed a strict Lean verdict, here or at import), rename / fix
lessons with `ok ≥ 1` (learned from a verified success; imported lessons start at 0 and enter only once they helped a
proof Lean accepted here). Conditional results, unverified imports, failed approaches are left out.

**Future LoRA fine-tune of the local prover (off by default, not implemented).** The intended use is a small LoRA
adapter on the local prover (Goedel-Prover-V2 8B, D33), trained on `statement_proof` rows of one Lean / Mathlib
version (the rows carry them; mixing versions teaches wrong names) and `error_fix` rows as correction turns. Resource
estimate: a 4-bit QLoRA of an 8B model needs ≈ 10–12 GB of GPU memory (rank 16, sequence 2048, batch 1 with gradient
accumulation), ≈ 1–3 h per epoch for 1 000–5 000 rows on a consumer card, ≈ 100–200 MB per adapter; useful only from
a few hundred verified rows of one version. It must stay optional, off by default, user-started, never during
Lean / prover work (D51 GPU sharing), and its gain measured with « Mesurer » (D53) before the adapter is used. The
lessons and the library already give most of the benefit without training (D57b): this is why nothing is trained in
2.x.

## 7. Cut in this session (S-BD)

- Merging imported graphs into local graphs: they are references; the preview counts the statements already present.
- Glossary entries: the glossary has no user entries (built-in), nothing to export.
- Lean « recipes »: the Calcul recipes store has Sage / Python only; the Lean catalogue is rebuilt per workspace.
- Viewing an imported graph reference in the graph view (only listed with counts; deletable).
- Bundle signatures (see §1).
