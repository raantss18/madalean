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
- Settings: `attack_enabled` (false until the user starts it), `attack_kinds` (⊆ known, counterexample, open;
  default all three), `attack_usd_per_day` (5.0), `attack_parallel` (2), `attack_max_difficulty_open` (40),
  `attack_post_notes` (**false**: notes to the site's teams are outward), `attack_download_max_gb` (0 until the user
  accepts the download; 10 then, covering updates up to that size). All host only, all in `GET /api/settings` and in
  the state snapshot (`settings`).

| Method | Path | Answer |
|---|---|---|
| GET | `/api/attack` | `{state: off\|setup\|running\|paused\|budget\|error, reason: user_jobs\|month_cap\|day_cap\|site\|no_github\|workspace\|error\|"", detail (internal reason), handle, today: {usd, cap, taken, proofs, released}, workspace: {state: none\|downloading\|building\|ready\|error, commit, size, percent, step, error, building, progress: {done_bytes, total_bytes, estimated}}, current: [{problem, title, kind, difficulty, dossier_id, phase: reading\|planning\|proving\|searching\|checking\|formalizing\|reducing\|preparing\|releasing, waiting, since, lease, submission, running}], queue: n, settings: {attack_*}}` |
| POST | `/api/attack/start` · `/api/attack/stop` | same (host only; stop releases every lease `out_of_time`) |
| POST | `/api/attack/workspace` | `{accept: true}` starts the download (host only) |
| GET | `/api/attack/submissions` | `[{id, problem, title, kind: proof\|disproof\|reduction\|statement, lease, model, file: {path, text}, check: {local: {ok, detail}, rules: {ok, detail}, axioms: {ok, detail: "propext, Quot.sound"}, review, failures: [{rule, ok, detail}]}, plan: {id, login, fork, branch, sha256, requests: [{method, url, body}]} \| null, state: ready\|sent\|merged\|rejected\|expired\|discarded\|failed, pr_url, created, dossier_id?}]` |
| POST | `/api/attack/submissions/{id}/send` | body `{plan: <plan.id>}` (the plan the user saw) → `{submission}`; host only, once, needs the GitHub key |
| POST | `/api/attack/submissions/{id}/discard` | `{submission}`; host only |
| GET | `/api/attack/history` | `[{problem, title, kind, outcome: solved\|released\|reduced\|submitted\|rejected, reason, t, usd, dossier_id}]` |
| PATCH | `/api/attack/settings` | the settings above |
Events: `attack.state` (the full GET /api/attack answer at top level), `attack.submission` = `{submission: <one item>}`.
Every problem's work is visible in its dossier (one thread, D66).

## Changes made by S-BJ (2026-11-28, after S-BK's interface)
- `send` needs `{plan: <plan.id>}`: only the plan the user was shown can be sent (login re-read and compared, file
  hash pinned). `send` / `discard` answer `{submission}`.
- `workspace.progress.total_bytes` is the stated estimate (10 GB, `estimated: true`); `done_bytes` is measured on disk
  in the folder being built (the toolchain, kept by elan, is not counted). The old step percentage is `percent`.
- `reason` uses the interface's words; `detail` keeps the internal one (`no_github_key`, `github_<error>`,
  `workspace_consent`, `workspace_downloading|building|error`, `catalogue`, `desk_busy`, …). `month_cap`: the month's
  Claude cap is reached — the attack takes no new problem (as at the day's cap).
- `current[].waiting`: the proof job waits for a slot (lowest priority). Phases `formalizing` / `reducing` are reserved:
  this version produces neither (below).
- Cut from this version (rules implemented and tested, the engine does not produce them yet): reductions and special
  cases written by models, `formalize`, board take / done, teammates' notes given to the prover, tracking merged /
  rejected pull requests (`/api/pending`). Notes posted (with `attack_post_notes`) are only factual DEAD END notes
  written by rules.
