# The flow of one dossier (D64) — contract between server (S-BG) and interface (S-BH)

Case that must work: « Le nombre chromatique du plan est 6 » (open problem, 5 ≤ χ ≤ 7).

## Stages, always in this order
`understand` → gate `meaning` → `translate` → gate `statement` → `prove` (contains `literature`, `decompose`) → `verify` → `explain`.
All fields are optional on old data; old dossiers load and prove as before and are shown by mapping `stage` / `kind`.

## Every new event (dossier.events[])
Existing fields, plus `phase` (one of the stages above), `run` (id of the user request that caused it),
`attempt` (1… inside run+phase, else 0). Order = list order; `t` is the moment it ended.

## Live « now »
`dossier.now` (REST and event `dossier.now` `{dossier_id, now}`): `null` or
`{phase, run, attempt, activity, model, started, waiting: "" | "user" | "slot" | "quota", side: [{phase, activity}]}`.
`activity` is a key with `params`, translated by the interface. It is derived from the job and the gate, never stored
as a second truth; after a crash or restart no job ⇒ `null`, or `waiting: "user"` when a gate is pending.

## Gates (user decision: ALWAYS asked before any proof)
`dossier.gate`: `null` or `{id, kind: "meaning" | "statement", state: "pending" | "approved" | "rejected", version, t,
 meaning?, statement?}`.
- meaning: `{restated, objects: [{name, meaning}], hypotheses: [], claim, known_status: "known" | "open" | "false" |
  "unclear" | "unknown", status_sources: [{title, url, quote}], status_confidence: "cited" | "model_only",
  known_results: [{id, title, statement, source?, dossier_id?}], questions: []}`
- statement: `{candidates: [{version, code, back_translation, model, objects_missing: [], verdict, reasons: []}],
  chosen, agreement: "equivalent" | "different" | "single" | "unchecked"}`
`known_status` without a retrieved source is `model_only` and worded « d'après un modèle, à vérifier ».

| Method | Path | Body | Effect |
| --- | --- | --- | --- |
| POST | `/api/dossiers/{id}/gate` | `{gate_id, action: "approve" \| "edit" \| "reject", text?, candidate?}` | approve continues; edit/reject reruns that stage with the text; stale `gate_id` → 409 `stale_gate` |
| POST | `/api/dossiers/gates/approve` | `{items: [{dossier_id, gate_id}]}` | approves several pending STATEMENT gates (known results) |
| POST | `/api/dossiers/{id}/report` | `{target: "meaning" \| "statement" \| "proof" \| "event", ref?, reason: "wrong_object" \| "too_general" \| "missing_hypothesis" \| "wrong_claim" \| "ignored_request" \| "other", text?}` | « Mal compris »: stops what depends on it, records it, reruns that stage with it, feeds the lessons |

`PATCH settings.validate_before_proof` (true). « Prouver quand même » approves the statement gate explicitly.

## Open or false problem
Said first, once, in the meaning gate. `known_results` become sub-dossiers launched automatically up to their
statement gate (one card approves several). The requested statement stays the dossier's own target: a suggested fix
must never silently change it, and is labelled « change l'énoncé » when it does.
