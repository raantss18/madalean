# The flow of one dossier (D64) — contract between server (S-BG) and interface (S-BH)

Case that must work: « Le nombre chromatique du plan est 6 » (open problem, 5 ≤ χ ≤ 7).

## Stages, always in this order
`understand` → gate `meaning` → `translate` → gate `statement` → `prove` (contains `literature`, `decompose`) → `verify` → `explain`.
All fields are optional on old data; old dossiers load and prove as before and are shown by mapping `stage` / `kind`.

## Every new event (dossier.events[])
Existing fields, plus `phase` (one of the stages above, or `literature` / `decompose` inside `prove`; `""` when none), `run` (id of the user request that caused it),
`attempt` (1… inside run+phase, else 0). Order = list order; `t` is the moment it ended.

## Live « now »
`dossier.now` (REST and event `dossier.now` `{dossier_id, now}`): `null` or
`{phase, run, attempt, activity, model, started, waiting: "" | "user" | "slot" | "quota", side: [{phase, activity}]}`.
`activity` is a key with `params` beside it (`stage.<job stage>` or `gate.meaning` / `gate.statement`; `side` rows are
`{phase, activity, params}`), translated by the interface. It is derived from the job and the gate, never stored
as a second truth; after a crash or restart no job ⇒ `null`, or `waiting: "user"` when a gate is pending.

## Gates (user decision: ALWAYS asked before any proof)
`dossier.gate`: `null` or `{id, kind: "meaning" | "statement", state: "pending" | "approved" | "rejected", version, t,
 meaning?, statement?}`.
- meaning: `{restated, objects: [{name, meaning}], hypotheses: [], claim, known_status: "known" | "open" | "false" |
  "unclear" | "unknown", status_sources: [{title, url, quote}], status_confidence: "cited" | "model_only",
  known_results: [{id, title, statement, source?, dossier_id?}], questions: []}`
- statement: `{candidates: [{version, code, back_translation, back_model, model, objects_missing: [], verdict, reasons: [], hard}],
  chosen, agreement: "equivalent" | "different" | "single" | "unchecked"}`
`known_status` without a retrieved source is `model_only` and worded « d'après un modèle, à vérifier ».

| Method | Path | Body | Effect |
| --- | --- | --- | --- |
| POST | `/api/dossiers/{id}/gate` | `{gate_id, action: "approve" \| "edit" \| "reject", text?, candidate?}` | approve continues (`candidate` = a candidate's `version`); edit/reject reruns that stage with the text (a Lean theorem given as `text` of a statement gate becomes the user's own statement); stale `gate_id` → 409 `stale_gate`; a `hard` refused candidate → 409 `refused_statement`; job running → 409 `busy` |
| POST | `/api/dossiers/gates/approve` | `{items: [{dossier_id, gate_id}]}` | approves several pending STATEMENT gates (known results) |
| POST | `/api/dossiers/{id}/report` | `{target: "meaning" \| "statement" \| "proof" \| "event", ref?, reason: "wrong_object" \| "too_general" \| "missing_hypothesis" \| "wrong_claim" \| "ignored_request" \| "other", text?}` | « Mal compris »: stops what depends on it, records it, reruns that stage with it, feeds the lessons |

`PATCH settings.validate_before_proof` (true). « Prouver quand même » approves the statement gate explicitly.

## Open or false problem
Said first, once, in the meaning gate. `known_results` become sub-dossiers launched automatically up to their
statement gate (one card approves several). The requested statement stays the dossier's own target: a suggested fix
must never silently change it, and is labelled « change l'énoncé » when it does.

## Precisions (S-BG)
- A gate is data of the dossier; the job ends when it opens (state `done`, summary « En attente de votre validation »)
  and the answer starts another job of the same `run`. `dossier.gate` of a statement gate also carries the approved
  `meaning`. Summaries (`GET /api/dossiers`) carry `gate: {id, kind, state} | null`.
- Candidate `verdict`: `ok | doubtful | false | refused`; `hard` = says nothing about the problem, cannot be approved
  (a text written by the user is never `hard`). `agreement: "different"` = Lean did not show in bounded time that the
  two are equivalent; `unchecked` = Lean could not decide.
- An approval belongs to the exact text of a statement: editing or restoring another one makes the gate stale.
- Gated: jobs of a person on dossiers created since this feature (stored `flow`). Opt-outs, explicit: `gates: false` on
  `POST /api/dossiers`, `/run`, `/message` (scripts), bench, lemmas of plans / reasoned search / splits / blueprints,
  research agent, Mathlib contribution. MCP tools start no dossier job. Plans and the reasoned search of a theorem
  nobody approved answer 409 `gate_pending`.
- New event kinds: `gate` (each decision, params `{gate_kind, action, gate}`; the opening is an `info`), `report` (each
  report, params `{target, reason, why}`), `status`, `oscillation`. A `check` event has `params.changes_statement: true`
  when its fix changes the claim (issues: `changes_claim`, `unsourced`). Events carry both `run` and `job`.
- `candidate` = `version` = 0-based index in `statements[]`. `report.ref` = version index (statement / proof) or index in
  `events[]` (event). `gate`, `gates/approve` rows and `report` start a job; `gate` and `report` answer `{dossier, job}`,
  `gates/approve` answers `{results: [{dossier_id, ok, error, dossier, job}]}`. Summaries also carry `now`.
- `activity` keys: `""` (queued), `gate.meaning`, `gate.statement`, and `stage.` + `understand | route | statement |
  notes | verify | proof | mathlib | certificate | literature | explanation | informal` (params `{}` today).
- Known results are opened for `open` / `false` (and `unclear` when a source contradicts the model).
- `known_status` when no status check answered at all: `unknown`. A model's word alone stays `model_only`.
