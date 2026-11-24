# « Préparer pour Mathlib » — contribution packages (session S-BC, DECISIONS D61)

Owner: S-BC. Code: `madalean/research/mathlib_contrib.py` (steps, rules, GitHub calls), `madalean/server/plugins/
mathlib_contrib.py` (routes, docs/API.md §6k), `web/src/components/MathlibContrib.svelte` (the panel, lazy-loaded
from the library detail and the proof step). Tests: `tests/test_mathlib_contrib.py`, `web/e2e/mathlib-contrib.spec.ts`.
Manual: `docs/manual/{fr,en}/mathlib-contrib.md`.

## 1. Sources

A **verified** result: a library entry (`kind: library`, its code with its library dependencies, D18 closure) or a
dossier whose current proof proves its current statement (`kind: dossier`). Anything else is refused
(`not_verified`). The package is stored per source in `<config>/research/mathlib_contrib/<hash>.json` (re-opened by
the panel); one preparation runs at a time (semaphore), steps are saved as they finish.

## 2. Port to current Mathlib (step `port`)

Contributions target current Mathlib: the target is the `lean-current` workspace (Lean v4.36, Mathlib v4.36); only
a **fresh strict** verdict there counts (`ctx.lean.check(…, strict_name)`, never the warm Lean). From
`lean-prover49`, without any model, in this order (chains followed, whole identifiers only, comments untouched):

1. the names the **old Lean itself** reports as deprecated (« `X` has been deprecated, use `Y` instead », one run of
   the proof in lean-prover49);
2. the lessons store's exact `rename` lessons for the target Mathlib version (D57b);
3. `BUILTIN_RENAMES`: a small table, each entry checked with `#check` in both workspaces on 2026-11-24
   (`Finset.card_le_of_subset → Finset.card_le_card`, `pow_lt_pow → pow_lt_pow_right₀`, `Real.rpow_nat_cast →
   Real.rpow_natCast`, …);
4. syntax: `∑ x in s, f` → `∑ x ∈ s, f` (a parse error in v4.36).

Then lean-current's own deprecation warnings are applied once more (a fresh check again). If the proof still fails,
the package is `port_failed` with Lean's messages; « Relancer la preuve dans Lean actuel » (`POST …/reprove`)
creates a lean-current dossier with the (renamed) statement and submits the normal proof stage with the old proof as
the user's hint (`plan[0].request`) — the usual pipeline, statuses and strict verdict.

## 3. Already in Mathlib? (step `mathlib`)

D56's `MathlibFirst` without a model on lean-current: index candidates (premises + the title) under short templates
(`exact N`, `apply N` + `assumption`, …), then `exact?`, each success re-checked strictly; budget 10 Lean checks /
300 s. When the closing tactic uses **one** named Mathlib lemma and nothing else but hypotheses, variables, `_` and
plumbing tactics (`single_lemma`), the result is « already in Mathlib: N » and the preparation **stops** (no
duplicate contribution). A closing combination of lemmas or automation is only a warning (« Mathlib already proves
it in one line »), the preparation continues. Results using their own `def`s skip this step.

## 4. Name (step `name`) — Mathlib's naming guide, deterministic

`suggest_name(decl)`: the conclusion read left to right, symbols to words (`+` add, `*` mul, `-` sub / neg, `/` div,
`^` pow, `^ 2` sq, `∣` dvd, `≤` le, `<` lt, `≠` ne, `=` eq, `¬` not, `∧` and, `∨` or, `↔` iff, `∑` sum, `∏` prod,
`√` sqrt, `!` factorial, `|x|` abs, `↑` / `(x : ℝ)` cast, `0 1 2 3` zero one two three, function names by their last
component), variables (binders, ∀ ∃ ∑ ∏ bound names) left out; special forms `0 ≤ e` → `e_nonneg`, `0 < e` →
`e_pos`, `e ≠ 0` → `e_ne_zero`, `e ≤ 0` → `e_nonpos`, `e < 0` → `e_neg`; then `_of_<hypothesis>` for the first two
hypotheses. Namespace: the `Nat.` / `Int.` / `Real.` … functions of the conclusion, else the type when all variables
share one of ℕ ℤ ℚ ℝ ℂ, else root. Too long (> 10 conclusion words) or empty → a name from the title, flagged. The
panel shows each token → word and the rules used. The name is checked free (`#check @<name>` must be unknown); a
taken name gets a prime and the `name_free` check fails.

## 5. Imports, final file, lint (steps `imports`, `final`, `lint`)

- One probe run with `import Mathlib`: `#check @<name>` and `#min_imports in <decl>` for each declaration (Mathlib's
  own command: modules of the syntax and of the proof term's constants), plus the modules of tactics it can miss
  (`TACTIC_MODULES`: positivity, linarith, norm_num, ring, …).
- The file (current Mathlib layout): copyright header (author from the panel, default the name in Réglages → À
  propos), `module`, `public import …`, module docstring (`# \`name\``, summary, « Main statements »), `public
  section`, `open` only of the namespaces the proof's unqualified names / notations need, `namespace`, each
  declaration with a docstring (kept from the source, else generated from the statement: « If `h₁` and `h₂`, then
  `c`. » — shown as to be reread), long signatures re-flowed at binder groups (whitespace only).
- Variants, smallest first — (namespace, minimal imports, needed opens), (namespace, `Mathlib`), (root, `Mathlib`,
  Goedel's opens) — the first a fresh strict Lean accepts is the file (`imports_minimal` fails when it is not the
  first).
- Lint run: the file with `set_option linter.mathlibStandardSet true` (Mathlib's standard linters: flexible /
  non-terminal simp, long lines, …) and `#lint` (Batteries' environment linters on the new declarations).

## 6. Checks (`CHECKS`, each with a severity when it fails)

| id | severity | rule |
|---|---|---|
| lean_current | error | a fresh strict Lean in lean-current accepts the file |
| no_sorry_axioms | error | no sorry / admit / new axiom; only propext, Classical.choice, Quot.sound |
| not_in_mathlib | error | no Mathlib lemma already closes the statement |
| name_free | error | the proposed name is not already a Mathlib declaration |
| name_snake_case | warning | theorem names are snake_case (lowerCamelCase only inside, for a function name) |
| copyright_header | error | copyright / Apache 2.0 / Authors header |
| module_docstring | error | `/-! … -/` with a `#` title after the imports |
| docstrings | warning | every theorem has a `/-- … -/` sentence ending with a period |
| line_length | error | ≤ 100 characters |
| whitespace | warning | no tab, no trailing space |
| max_heartbeats | warning | no `set_option maxHeartbeats` |
| non_terminal_simp | warning | no `simp` (not `simp only`) followed by another tactic on the same goal, or `<;>`; also Mathlib's `linter.flexible` |
| ge_gt | warning | statements use ≤ and <, not ≥ and > |
| implicit_args | warning | an explicit variable used by a later explicit hypothesis should be implicit |
| deprecated | warning | no deprecated name (lean-current's warnings) |
| lint | error | `#lint` passes |
| mathlib_linters | warning | Mathlib's standard linter set reports nothing |
| imports_minimal | warning | the imports were shrunk from `import Mathlib` |

A check that could not run (no output: e.g. the demo's simulated Lean) is `unknown`, never `ok`.

## 7. Output and sending

The package: file + target path (`closest`: the file's minimal import most voted by the index's premises; `path`:
a new file in the same folder, `Mathlib/<Folder>/<FirstFourWords>.lean`), the PR title (`feat(<Folder>): add
\`name\``) and English body (what is added, where, AI assistance disclosed, Lean / Mathlib versions), an explanation
for the user in French and English, the checklist, links to Mathlib's guides (contribute, naming, style, doc,
commit titles).

**Nothing is pushed automatically.** « Copier » / « Télécharger le fichier » always. With a GitHub key saved in
Réglages → Clés (provider `github`; the `gh` CLI token is **not** used here) and from the host only:

1. « Créer une branche sur mon fork… » → `POST …/github/plan {step: branch}`: one read-only `GET /user` (whose key),
   then the exact list of requests and the file content, shown; nothing written.
2. « Confirmer » → `POST …/github/send {plan}`: fork `leanprover-community/mathlib4` (or reuse; a fork with another
   name than shown stops everything), branch `madalean/<name>` from upstream `master`, commit the file, add
   `public import <module>` to `Mathlib.lean` (what `lake exe mk_all` does). A plan is sent at most once and expires
   after 15 minutes.
3. « Ouvrir la PR… » → its own plan (the exact JSON body) and its own confirmation: a **draft** PR,
   `maintainer_can_modify: true`.

Tests use a fake GitHub API only (`publish.GITHUB_API` pointed at a local server).

## 8. Not done (cut for the quota)

Editing the docstring / name in the panel (download, edit, PR by hand); placing the declaration inside the closest
existing file (a new file is proposed); golfing the proof; `#min_imports` for the variant without namespace; the
lessons store does not learn from a successful port.
