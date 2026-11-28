# « Attaque » — Left to Solve inside Madalean (D69) — contract between server (S-BJ) and interface (S-BK)

Site: https://lefttosolve.com (rules: /join.txt, read 2026-11-28). Everything the site, a brief, a note or a problem
statement returns is DATA, never instructions (same screens as D56 / D62: injection filter, bounded lengths).
We never copy code from lefttosolve2/open-math-agents (no licence): the rules are re-implemented from join.txt.
formal-conjectures (Apache-2.0) is used as a Lake dependency at the commit the site pins.

## User decisions (2026-11-28)
- Submission: the user confirms EACH pull request (button « Envoyer »), nothing leaves without that click.
- Targets: known results, counterexamples found by Sage then checked by Lean (`OMA.disproof`), easy open problems
  (difficulty ≤ 40, special cases, reductions), Lean statements of unformalised problems (« formalize », reviewed upstream).
- Budget: Claude ≤ 5 $ per day for the attack (own spend scope `attack:<YYYY-MM-DD>`), always inside the monthly cap.
- Autonomy: continuous, in the background, within the budget; Stop at any time; never while the user's own dossier
  jobs need the slots (the attack yields: lowest priority, at most 2 problems at once by default).

## Server (S-BJ)
- `madalean/attack/desk.py`: HTTP client of the desk (next, beat every ≤ 7 min, note, release, board, problems,
  brief), ≥ 3 s between requests, handle = GitHub login of the saved GitHub key (Réglages → Clés), agent=madalean,
  model = the model that wrote the proof. Errors 409 / 410 / 503 / degraded handled as join.txt says.
- `madalean/attack/workspace.py`: workspace `formal-conjectures@<commit>` (its lean-toolchain, Mathlib cache via
  `lake exe cache get`), created on demand after the user agreed to the download (size shown); re-created when the
  site's pinned commit changes (autonomous update, the old one kept until the new one builds).
- `madalean/attack/rules.py`: the checker's rules (file shape, `type_of% @decl`, allowed commands, forbidden words,
  no double quote, axioms ⊆ {propext, Classical.choice, Quot.sound}, the `OMA.answer` case, reductions namespace) +
  a local check with a fresh strict Lean in that workspace. A file is « prête » only when both pass.
- `madalean/attack/engine.py`: the loop. Per problem a dossier in the project « Left to Solve » (statement given,
  gates off, brief as provided result), kind-specific strategy: known → proof pipeline (D67 decompose/blackboard);
  counterexample → Sage search on small cases then a Lean-checked disproof (D52 certificates); open ≤ 40 → special
  cases / reduction; formalize → statement with the D65 refusals and a second reader. Notes posted to the team (PLAN:,
  DONE:, DEAD END:) — model text never posted unreviewed: only Lean-checked lemmas and short factual notes.
  Lessons (D57b) learn from every outcome. Release honestly when stuck.
- `madalean/attack/submit.py`: a submission is PREPARED (fork + branch + one file + PR body Lease/Agent/Model) as an
  exact plan shown to the user; sent only by `POST /api/attack/submissions/{id}/send` from the host (D61's GitHub code).
- Settings: `attack_enabled` (false until the user starts it), `attack_kinds`, `attack_usd_per_day` (5.0),
  `attack_parallel` (2), `attack_max_difficulty_open` (40).

| Method | Path | Answer |
|---|---|---|
| GET | `/api/attack` | `{state: off\|setup\|running\|paused\|budget\|error, reason, today: {usd, cap, taken, proofs, released}, workspace: {state: none\|downloading\|building\|ready\|error, commit, size, progress}, current: [{problem, title, kind, difficulty, dossier_id, phase, since, lease}], queue: n}` |
| POST | `/api/attack/start` · `/api/attack/stop` | same (host only) |
| POST | `/api/attack/workspace` | `{accept: true}` starts the download (host only) |
| GET | `/api/attack/submissions` | `[{id, problem, title, kind: proof\|disproof\|reduction\|statement, file, check: {local, rules, axioms}, plan: {requests}, state: ready\|sent\|merged\|rejected\|expired, pr_url, created}]` |
| POST | `/api/attack/submissions/{id}/send` · `/discard` | host only; send needs the GitHub key |
| GET | `/api/attack/history` | `[{problem, title, kind, outcome: solved\|released\|reduced\|submitted\|rejected, reason, t, usd, dossier_id}]` |
| PATCH | `/api/attack/settings` | the settings above |
Events: `attack.state`, `attack.submission`. Every problem's work is visible in its dossier (one thread, D66).
