# Madalean 2.0 — research workshop API (notes, conjectures, proof plans, learning, updates)

Server side written by session S-G (plugin `madalean/server/plugins/research_workshop.py`, modules
`madalean/research/{notes,conjectures,proofplan,learn,sagebridge}.py`, package `madalean/update_checkers/`).
Same conventions as [API.md](API.md): JSON bodies, prefix `/api`, `Message = {key, params, text}`, errors
`{"error": kind, "message"?: Message, …}`, authentication / Origin / host-only rules of API.md §1 apply to every route
below (remote devices need their token; **host** = local listener only). Ids match `^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$`.

- [Notes](#1-notes) · [Conjectures](#2-conjecture-workshop) · [Proof plans](#3-guided-proof-design) ·
  [Learn](#4-learning-support) · [Updates](#5-update-checkers-and-re-verification) · [Events](#6-websocket-events) ·
  [Types](#7-types) · [Security boundary](#8-security-boundary) · [Demo](#9-demo-mode)

## 1. Notes

Markdown + LaTeX (`$…$`, `$$…$$`) + fenced ```` ```lean ```` blocks, per project. Links (ignored inside code):

| Syntax | Target |
|---|---|
| `[[Title]]`, `[[Title\|label]]`, `[[note:ID]]` | note of the same project (title match is case-insensitive) |
| `[[dossier:ID]]`, `[[dossier:Title]]` | dossier (theorem, conjecture, lemma…) |
| `[[@key]]`, `[[@key#p12]]`, `[[@key#chunk-ID]]` | source of the sources library (BibTeX key + locator); works without S-E (node marked `missing`) |
| `[[passage:CHUNK]]` | a passage (chunk id of the sources library) |
| `[[lib:Name]]` | library result (Lean name) — drawn as an edge to its dossier |

Tags: `#tag` in the text (not headings) plus the note's `tags` field. Links are stored raw and resolved on read, so
backlinks and the graph stay right after rename / delete / restore. Renaming a note rewrites `[[Old title…]]` in the
other notes of the project (each one gets a new revision, event `note.updated` with `reason:"rename"`).

| | |
|---|---|
| `GET /notes?project=&tag=&trash=1` | `{notes:[NoteSummary]}` (most recently updated first; `trash=1` = deleted notes) |
| `POST /notes {project_id, title, body?, tags?}` | `201 {note: Note}`; 409 `title_exists`; 400 `title_required` |
| `GET /notes/{id}` | `{note: Note, backlinks:[{id,title,label,context}], attachments:[Attachment]}` |
| `PATCH /notes/{id} {base_rev, title?, body?, tags?}` | `{note, merged:bool, renamed_links_in:[id]}`; **409 `conflict`** (see below); 400 `base_rev_required` / `bad_rev`; 409 `title_exists`, `deleted` |
| `DELETE /notes/{id}` | `{ok, undo:"/api/notes/{id}/restore"}` (trash) |
| `POST /notes/{id}/restore` | `{note}` (a title clash gets a suffix) |
| `GET /notes/{id}/versions` | `{versions:[{rev,title,size,t,device,reason}], rev}` (newest first; every revision is kept) |
| `GET /notes/{id}/versions/{rev}` | `{version:{rev,title,body,tags,t,device,reason}}` |
| `GET /notes/{id}/diff?from=&to=` | `{from,to,diff (unified),title_changed,titles}` |
| `POST /notes/{id}/versions/{rev}/restore {base_rev?}` | `{note}` — a NEW revision with the old content (nothing is lost) |
| `GET /notes/search?q=&project=` | `{results:[NoteSummary & {snippet, score}]}` — SQLite FTS5, accents folded, `[`…`]` mark hits |
| `GET /projects/{pid}/graph?kinds=note,dossier,source&edges=link,uses,cites&tag=&orphans=0` | `{nodes:[GraphNode], edges:[GraphEdge]}` |
| `GET /projects/{pid}/tags` | `{tags:[{tag,count}]}` |
| `POST /projects/{pid}/notes/daily {date?:"YYYY-MM-DD"}` | research-log note of the day (`201` created, `200` existing), lists the dossiers touched that day |
| `GET /dossiers/{id}/notes` | notes linking to a dossier |
| `POST /notes/{id}/attachments` (multipart `file`, ≤ 10 MB) | `201 {attachment:{id,url,mime,name,size,sha256,markdown}}`; 415 `bad_type`; 413 |
| `GET /notes/{id}/attachments` · `GET /attachments/{aid}` · `DELETE /attachments/{aid}` · `POST /attachments/{aid}/restore` | files; delete is undoable |
| `POST /notes/{id}/lean-check {block?}` | compiles every ```` ```lean ```` block (or one) with the project's workspace → `{results:[LeanBlockResult], note}`; 409 `busy`, `no_lean_block`, `no_workspace` |
| `POST /notes/{id}/to-dossier {block? \| paragraph? \| text?, kind?, title?, start?:false, link?:true}` | `201 {dossier, job, note}`: a Lean block with a theorem → dossier with that statement; otherwise the text is the problem; a `→ [[dossier:ID\|title]]` line is added below the source (new revision) |
| `GET /notes/{id}/export?format=md\|html\|pdf` · `GET /projects/{pid}/notebook/export?format=…` | file (`Content-Disposition: attachment`); PDF through XeLaTeX (export code of S-A), `X-Madalean-Fallback: html` when TeX is missing or fails |

**Live editing / optimistic concurrency.** Every write carries `base_rev` (the revision the client edited).
- `base_rev == rev` → applied, `rev+1`.
- `base_rev < rev` → server-side three-way merge, line by line (base = revision `base_rev`, theirs = current, mine =
  request). Edits of different lines (even adjacent) merge → `200 {merged:true}`. Same edit on both sides → fine.
  Title/tags: taken from the side that changed them.
- Overlapping edits (or two inserts at the same place, or both sides changed the title differently) → `409`:
  ```json
  {"error":"conflict","base_rev":3,"current":Note,
   "conflicts":[{"base_start":2,"base_end":2,"base":"b\n","mine":"X\n","theirs":"Y\n"}],"fields":["title"]}
  ```
  The UI shows both versions of each hunk, lets the user choose, and re-sends with `base_rev = current.rev`.
- Every applied change publishes `note.updated {note, device, merged?, reason?}`; editors on other devices apply it
  when they have no local changes, else they rebase (send their text with their old `base_rev`: the server merges).

Lean results are stored per block hash (`note.lean_blocks[i].result`), are dropped when the block text changes, and do
not create revisions. Error lines are given relative to the block (`line`) and to the note (`note_line`).

## 2. Conjecture workshop

A conjecture is a **dossier of kind `conjecture`** (`GET /dossiers/{id}` works as usual; its Lean statement, versions
and jobs are the dossier's). Workshop data: `dossier.extra.conjecture` (exposed as `Conjecture` below).

Status (recomputed): `proposed` → `tested-n-cases` (Lean instances or experiments that held; `cases_tested`) →
`lean-statement` (a Lean statement accepted by Lean) → `proved` (**only** the dossier's current proof, i.e. the normal
pipeline with the strict verdict) — or `refuted` (a counter-example re-verified independently).

| | |
|---|---|
| `GET /conjectures?project=` | `{conjectures:[Conjecture]}` |
| `POST /projects/{pid}/conjectures/generate {note_ids?, dossier_ids?, library?, source_keys?, n?:5, mode?}` | `{proposals:[Proposal], filtered:[Proposal & {reason, match}], model}` — context = selected notes, dossiers, library results, and source summaries when S-E's module is importable. Filtered: `duplicate_proposal`, `duplicate_dossier`, `known_library`, `known_mathlib` (retriever). 503 `no_model` |
| `POST /conjectures {project_id, statement, motivation?, lean?, title?, origin?, model?}` | `201 {conjecture}` (accept a proposal, or write one); with `lean`, Lean checks it first |
| `GET /conjectures/{id}` | `{conjecture}` |
| `POST /conjectures/{id}/lean {code}` | `{conjecture, check}` — set/replace the Lean statement (renamed to the dossier's theorem) |
| `POST /conjectures/{id}/formalize {mode?}` | `202 {job}`: pipeline `understand → statement` |
| `POST /conjectures/{id}/prove {mode?, strategy?}` | `202 {job}`: pipeline `proof → explanation` (409 `no_statement`, `busy`) |
| `POST /conjectures/{id}/lean-cases {cases?:[{var:value}], bounded?:K}` | `{entry, conjecture}`: one `example` per case closed by `first \| (norm_num; done) \| decide \| (simp; done) \| omega`, optional `∀ n < K → …` by `decide`; default cases `n = 0..9` for the first ℕ/ℤ variable |
| `POST /conjectures/{id}/refute-lean {witness}` | `{ok, code, check}` — `example : ¬ (∀ …) := by intro h; have hw := h <witness>; revert hw; …` |
| `POST /conjectures/{id}/experiments {kind:"counterexample"\|"test", language:"sage"\|"python", code?, mode?}` | `201 {experiment, approval_required}` — the brain writes the code (or `code` is the user's): `# PREDICATE` (defines `holds(**vars)`) then `# SEARCH` (calls `report(verdict, witness, cases)`) |
| `PATCH /conjectures/{id}/experiments/{eid} {code}` | edit (drops any approval) |
| `POST /conjectures/{id}/experiments/{eid}/approve {code_hash}` | approval of THIS exact code (409 `stale_code` if it changed); **exec gate** |
| `POST /conjectures/{id}/experiments/{eid}/reject` | |
| `POST /conjectures/{id}/experiments/{eid}/run {timeout?:60}` | `202 {started}`; output streams as `experiment.output`, result as `conjecture.updated`; 403 `not_approved`; 409 `busy`; **exec gate** |
| `GET /experiments/status` | `{available:{sage,python}, sandbox:"bwrap"\|"rlimits", auto, remote_allowed, jupyter, workdir}` |
| `POST /conjectures/{id}/literature` | literature check through S-E's `litsearch` (`{result:{available:false}}` when absent) |
| `POST /conjectures/{id}/promote` | kind → `theorem`, history kept; 409 `not_proved` |

**Exec gate**: from a paired device → `403 experiments_host_only` unless the host enabled the host-only setting
`experiments_remote`. **Approval**: a run needs an approval whose hash equals the current code hash, unless the host
enabled `experiments_auto` (host-only setting, `PATCH /settings`). Both checks are server-side.

**Counter-examples**: when an experiment reports `counterexample` with a witness, the server re-verifies it
independently before believing it: (1) the predicate alone (`# PREDICATE` part, no search state) in a **fresh
kernel** must return False at the witness; (2) when the conjecture has a Lean statement, Lean must accept
`¬ statement` closed at the witness. Only then `status = refuted` and `counterexample = {witness, verified, sage,
lean, evidence}`.

**Evidence log** (`conjecture.evidence`): append-only, never edited by the API; each entry `{id, t, kind, summary:
Message, verdict, code, language, output, data, model, device, prev, hash}`, chained by SHA-256 (`chain_ok`). Kinds:
`created`, `lean_statement`, `lean_cases`, `experiment`, `counterexample_check`, `literature`, `promoted`.

## 3. Guided proof design

A plan is a tree attached to a dossier (`root` = the dossier's goal). Every change is a new version (`rev`);
writes carry `base_rev` (409 `conflict` with `current` plan when stale — plans are not merged).

| | |
|---|---|
| `GET /dossiers/{id}/plan` | `{plan: Plan}` (404 `no_plan`) |
| `POST /dossiers/{id}/plan` | empty plan (root only) |
| `POST /dossiers/{id}/plan/draft {hint?, sketch?, mode?, force?}` | the brain drafts (agent with `search_mathlib` when available, else one completion); `sketch` = a paper's proof text used as a hint (source `sketch`); 409 `would_overwrite` when the current version has manual edits (send `force:true`; the old version stays restorable) |
| `POST /dossiers/{id}/plan/nodes {base_rev, parent, index?, title, statement_nl?, why?, lean?}` | add a node |
| `PATCH /dossiers/{id}/plan/nodes/{nid} {base_rev, title?, statement_nl?, why?, lean?}` | manual correction (`edited:true`) |
| `DELETE /dossiers/{id}/plan/nodes/{nid}?base_rev=` | subtree deleted (409 `busy` if a job runs in it) |
| `POST /dossiers/{id}/plan/nodes/{nid}/move {base_rev, parent, index?}` | reorder / re-parent (400 `cycle`) |
| `POST /dossiers/{id}/plan/accept {base_rev, nodes:[nid]}` · `…/reject` | |
| `POST /dossiers/{id}/plan/submit {base_rev, nodes?, mode?}` | `{plan, submitted:[nid]}`: one sub-dossier per accepted node (`kind:"lemma"`, `parent_id` = parent node's dossier, parent `uses` += child, `retry_parent`), leaves queued, internal nodes proved after their children by the orchestrator's existing parent retry |
| `POST /dossiers/{id}/plan/nodes/{nid}/cancel` | cancels the subtree (queued leaves dropped, running jobs cancelled) |
| `POST /dossiers/{id}/plan/nodes/{nid}/replan {hint?, base_rev?}` | split a (failed) node further |
| `POST /dossiers/{id}/plan/nodes/{nid}/admit {base_rev}` · `…/unadmit` | « admitted for now » (needs an accepted Lean statement) |
| `POST /dossiers/{id}/plan/prove-modulo {node?, code?, attempts?}` | proof of a node using its proven children AND its admitted children (stated with `sorry`) → `{ok, conditional, tries, plan}` |
| `POST /dossiers/{id}/plan/versions/{rev}/restore` | |

Scheduling: at most `plan.limit` jobs of one plan are in the orchestrator at once (default
`min(4, online + gpu slots)`); the orchestrator's slots still decide what runs.

**Proved modulo admitted lemmas — never verified.** `prove-modulo` compiles the proof with the admitted lemmas as
`theorem … := by sorry`; it succeeds when Lean reports no error, the target's own proof has no forbidden construct,
and its axioms are the standard ones plus `sorryAx`. The result goes to `dossier.extra.conditional_proof =
{verdict:"proved_modulo", admitted:[names], code, axioms (contains "sorryAx"), strict_ok:false, strict_summary}` —
never to `dossier.proofs`: the dossier status stays not proved, `DossierSummary.proved` is false, the plan's
`verdict = {state:"proved_modulo", verified:false, admitted:N, admitted_names}`. When every admitted lemma later gets
a real proof (library entry), the server substitutes the real lemma code and re-checks the parent with the **strict
verdict**; only then the proof is added to the dossier (`meta.strategy:"plan"`, axioms without `sorryAx`),
`conditional_proof.verdict = "superseded"`, plan `verdict = {state:"proved", verified:true}`.

Node `state` (computed): `draft`, `accepted`, `rejected`, `submitted`, `queued`, `proving`, `proved`, `failed`,
`stopped`, `admitted`, `proved_modulo`.

## 4. Learning support

Only for dossiers whose current proof is accepted by Lean (409 `not_proved` otherwise). Progress is per device
(`device` = the paired device id, `"host"` on the local listener) and published as `learn.progress`.

| | |
|---|---|
| `POST /learn/{did}/attempt {text, confidence?:0-100}` | retrieve-first gate: required before the first hint |
| `GET /learn/{did}/ladder` | `{attempted, revealed:[levels], hints:{level: Hint}, next, levels:{1:"nudge",2:"strategy",3:"key_lemma",4:"next_step",5:"full_proof"}}` |
| `POST /learn/{did}/hint {level, reflection?}` | `{level, name, text, model, source:"ai"\|"lean", redacted}` — 409 `attempt_first`, `in_order`, `reflect_first` (levels ≥ 3 need a sentence on what the previous hint told you). Level 5 = the Lean-verified proof (never model text). Generated lazily, cached per proof version (other devices reuse the cache but have their own gate) |
| `GET /learn/token?name=&workspace=` | tactic → curated explanation; declaration → retriever `{signature, doc, module}`; unknown → `{known:false, suggestions, text}` (never invented) |
| `POST /learn/{did}/explain-back {text, confidence?}` | `{criteria:[{criterion, met, evidence}], met, total, gap, question, redacted, graded_against:"lean_verified_proof"}` |
| `POST /learn/{did}/exercises/faded {k}` | faded proof: `{id, template (with `sorry -- ⟨i⟩`), blanks, k, verified:{original_compiles, holes_compile, nontrivial, trivial_blocks, battery}}` — blanks taken from the END of the proof backwards, each checked non-trivial (the automation battery does not fill it) by one real Lean run |
| `POST /learn/{did}/exercises/erroneous` | `{id, wrong_proof, mutation, block, prompts}` — one plausible wrong step that Lean really rejects |
| `GET /learn/{did}/exercises/{eid}` | the exercise (solutions never sent) |
| `POST /learn/{did}/exercises/{eid}/submit` | faded: `{fills:[text per blank]}` → `{checked:true, ok, check: CheckResult}` (strict verdict, statement pinned). Erroneous: `{diagnosis}` → `{checked:false, lean_error, wrong_block}` (Lean's real error, after the diagnosis), then `{code, diagnosis}` → checked fix |
| `GET /learn/progress?dossier=` | `{device, entries:[{t, dossier, kind, …}]}` (kinds: attempt, hint, reflection, explain_back, exercise_created, exercise_submit, exercise_diagnosis) |

**Mapping for the web UI** (`web/src/lib/learn/tutor.ts`, docs/UI.md §8 item 5) — the `Tutor` interface switches
from `/assistant` to these two routes with no prompt on the client:

| UI | server |
|---|---|
| `tutor.hint(d, level, {tried, helpType, reflections, lang})` | `POST /dossiers/{id}/hint {level: "nudge"\|"strategy"\|"lemma"\|"step"\|"full", tried, help, reflections:[…], confidence?}` → `{level (1-5), level_name, text, model, source, redacted}`. `tried` satisfies the retrieve-first gate (logged as the attempt), the last item of `reflections` the reflection gate; `full` returns the Lean-verified proof. The answer is a single JSON (not streamed): wrap it as a `TutorStream` whose `done` resolves immediately |
| `tutor.explainBack(d, text, {target, lang, previous})` | `POST /dossiers/{id}/explain-back {target: "statement"\|"proof", text, previous:[…]}` → `{text (feedback to display: gap + question), criteria, met, total, gap, question, redacted, graded_against}`; `target:"statement"` works on unproved dossiers (graded against the Lean statement) |
| `fadeProof(code, k)` (client-side, unchecked) | `POST /learn/{id}/exercises/faded {k}` + `…/submit {fills}`: same fading from the end, but blanks verified non-trivial and answers checked by Lean |
| per-device progress (local) | `GET /learn/progress` (per paired device, `"host"` locally) + event `learn.progress` |
| glossary hover | `GET /learn/token?name=&workspace=` (tactic table + retriever; unknown names are reported unknown) |

Language: the server answers in the interface language setting (`language`), not a per-request `lang`.

Leak detector (built from the verified proof): level 1 must not contain a proof line, a lemma name of the proof or a
tactic in backticks; level 2 no proof line nor lemma name; level 3 at most one lemma name, no proof line; level 4 at
most half of the proof lines. A leaking answer is regenerated once with feedback, then redacted (`redacted:true`).

## 5. Update checkers and re-verification

The updates manager of API.md §3.10 is unchanged; new checkers are registered (`updates.register_checker`) and two
installable kinds (`updates.INSTALL_ARGS`). Candidates keep the `UpdatesStatus.candidates` shape; extra data is in
`spec`: `release_notes` (URL), `risk`, `estimate {minutes, download_mb?}`, `command` (system: exact command, never
run), `rebuild` (Lake: packages rebuilt), `steps` (Madalean).

| kind | key | install |
|---|---|---|
| `lean-toolchain` | `lean-toolchain` | notify (comes with the Mathlib update; toolchains in use are never removed) |
| `lake-package` | `lake:<ws>:<pkg>` | **installable** for libraries the user added to a managed workspace; notify for Mathlib's own dependencies (they move with Mathlib), for `lean-prover49` (pinned, explanation in `note`) — Mathlib itself keeps key `mathlib` |
| `lake-add` | `add:<ws>:<pkg>` | created by `POST /workspaces/{key}/libraries` |
| `llama.cpp` | `llama.cpp` | notify (pinned) + rebuild command |
| `madalean` | `madalean` | notify (the self-update below installs it) |
| `system` | `system:sage\|jupyterlab\|ipykernel\|texlive\|poppler` | notify + exact command for the distro (Arch: `sudo pacman -Syu`; Debian/Ubuntu: `sudo apt update && sudo apt install --only-upgrade <pkg>`; Fedora: `sudo dnf upgrade <pkg>`; pip installs: `python3 -m pip install --user --upgrade <pkg>`) |

The catalogue checker refreshes the brain's online catalogue. In `mode = local` none of these checkers touches the
network. Checks run weekly (at start and every 10 min the plugin asks the manager whether a week passed) and on demand
(`POST /updates/check`); results are cached in `updates.json`.

| | |
|---|---|
| `GET /workspaces/{key}/packages` | `{workspace, readonly, packages:[{name,url,rev,input_rev,direct,dependents}]}` |
| `POST /workspaces/{key}/libraries {name, url (https), rev}` **host** | `202 UpdatesStatus` (progress as `updates.status`): copy → edit lakefile → `lake update` → `lake build` → verify (test file + every proven dossier / library entry of the workspace, strict) → switch → delete. 409 `readonly_workspace` (user projects), `pinned` (lean-prover49), `busy`, `jobs_running` |
| `GET /updates/recheck` | `{running, report:{workspace, reason, started, ended, total, ok, regressed:[{name,dossier,kind,summary,errors}]}}` |
| `POST /updates/recheck {workspace?, reason?}` | `202` — re-check every proven dossier + library entry of a workspace |

After any Lean library update (Mathlib through the existing installer, or a Lake package), the proven dossiers of the
workspace get `extra.recheck = {state:"pending"}` (« à revérifier »), then `ok` or `regressed` (thread event, toast,
`updates.recheck` events) — the UI must show « à revérifier » for `pending`/`regressed`, never the old verdict alone.

**Automatic installs (ARCHITECTURE §16).** Setting `updates_auto` (host-only, default `true`; `false` = « demander
avant d'installer »). Every minute the plugin looks for a quiet moment (no job in the orchestrator, no update running)
and installs, one at a time, the installable candidates of kind `mathlib`, `model`, `lake-package` through the
manager's verify-then-switch-then-delete path; each `key:version` is tried once (a failure changes nothing; the
manager's `last_result` + toast explain it); `lean-prover49` is never touched. Event `updates.auto {key, latest,
started, error}`. Toolchains come with Mathlib; the catalogue checker refreshes the brain's catalogue at each check.

**System components — « Installer ».** `POST /updates/system/{comp}/terminal` **host** (`comp` = `sage`,
`jupyterlab`, `ipykernel`, `texlive`, `poppler`) opens the user's terminal (Konsole first, then gnome-terminal, kgx,
xfce4-terminal, x-terminal-emulator, alacritty, kitty, foot, xterm) on the exact command of the cached candidate
(never a command sent by the client), which shows the command and waits for Enter; the password is typed by the user;
Madalean never runs sudo → `{opened, command, terminal}`; 409 `no_terminal` (with `command` to copy).

**Self-update of Madalean** (`madalean/update_checkers/selfupdate.py`, like L Katta's `maj.rs`).
- Channel (ARCHITECTURE §17): `https://raantss18.github.io/madalean/updates/stable.json` + `stable.json.sig`
  (Ed25519 over the exact bytes): `{version, published, notes_url, files:[{name, url, sha256, size, kind:
  server|appimage|apk}], min_version}`. Checked first; when unreachable, fallback to the GitHub Releases API with
  `SHA256SUMS` + `SHA256SUMS.sig`. A bad signature is a refusal (never a silent fallback); a release without
  signature is refused; `min_version` above the running version → `manual`.
- Key: private key `~/.config/madalean/release-keys/ed25519.pem` (0600, outside git, generated 2026-11-21);
  public key embedded (`selfupdate.PUBLIC_KEY`). `scripts/sign_release.sh DIR` writes `SHA256SUMS`,
  `SHA256SUMS.sig`, checks them against the embedded key, and writes `site/updates/stable.json` (+ `.sig`)
  (`SITE_DIR`, `MIN_VERSION`, `NOTES_URL`, `RELEASE_URL_BASE` env). Verification uses `cryptography` when importable,
  else a pure-Python RFC 8032 verifier (tested equal to openssl): no runtime dependency.
- Install: download (≤ 300 MB) → signature → SHA-256 → safe extraction (no absolute path, `..`, link or device)
  into `~/.local/share/madalean/versions/<v>` → health check (the new tree is started with `serve --demo` on spare
  ports and a throw-away config; `/api/hello` must report the new version) → atomic switch of the symlink
  `~/.local/share/madalean/current` → previous version kept for rollback, older ones pruned → restart with
  `systemctl --user restart madalean.service` at a quiet moment. Automatic only when the server runs from that layout
  (`managed_install`), i.e. when the systemd unit's `ExecStart` is `~/.local/share/madalean/current/bin/madalean`
  — **integration step for install.sh (not done by S-G)**; a git checkout is updated with git.
- API: `GET /selfupdate` → `{version, installed, previous, available, last, busy, pending_restart, versions,
  managed_install, public_key}`; **host**: `POST /selfupdate/check`, `POST /selfupdate/install` (202), `POST
  /selfupdate/rollback`, `POST /selfupdate/restart` (409 `jobs_running`). Event `selfupdate.status {selfupdate,
  installing?, restarting?}`.

## 6. WebSocket events

| type | payload |
|---|---|
| `note.updated` | `{note: Note, device, merged?, reason?: "rename"\|"restore"\|"lean"}` |
| `note.deleted` | `{id, project_id}` |
| `conjecture.updated` | `{conjecture: Conjecture}` |
| `experiment.output` | `{conjecture_id, experiment_id, stream: "stdout"\|"stderr"\|"result", text}` |
| `plan.updated` | `{dossier_id, plan: Plan}` |
| `learn.progress` | `{device, entry}` |
| `updates.recheck` | `{report}` or `{item: {name, dossier, ok}}` |
| `updates.auto` | `{key, latest, started, error}` |
| `selfupdate.status` | `{selfupdate, installing?, restarting?}` |
| (existing) `updates.status`, `dossier.updated`, `job.updated`, `toast` | as API.md |

## 7. Types

```ts
interface NoteSummary { id: string; project_id: string; title: string; tags: string[]; kind: "note" | "daily";
  rev: number; created: number; updated: number; deleted: number | null; size: number; excerpt: string }
interface Note extends NoteSummary { body: string; user_tags: string[]; device: string;
  lean_blocks: { index: number; hash: string; start_line: number; result: LeanBlockResult | null }[];
  links: { kind: "note" | "dossier" | "source" | "lib" | "passage"; ref: string; label: string; locator: string }[] }
interface LeanBlockResult { ok: boolean; statement_ok: boolean; has_sorry: boolean; summary: string; seconds: number;
  errors: { line: number; note_line: number; col: number; text: string; severity: string }[]; timed_out: boolean;
  infra_error: string; workspace: string; t: number; hash: string; index: number }
interface GraphNode { id: string; kind: "note" | "dossier" | "source"; ref: string; title: string; missing?: boolean;
  tags?: string[]; status?: string; dossier_kind?: string; proved?: boolean }
interface GraphEdge { source: string; target: string; kind: "link" | "uses" | "cites"; label?: string; locator?: string }

interface Proposal { statement: string; motivation: string; lean: string; test: string; origin?: object }
interface Experiment { id: string; kind: "counterexample" | "test"; language: "sage" | "python"; code: string;
  predicate: string; code_hash: string; source: "ai" | "user"; model: string;
  status: "awaiting_approval" | "approved" | "running" | "done" | "failed" | "rejected";
  approved: { hash: string; t: number; device: string } | null; runs: { t; status; verdict; seconds }[] }
interface Evidence { id: string; t: number; kind: string; summary: Message; verdict: string; code: string;
  language: string; output: string; data: object; model: string; device: string; prev: string; hash: string }
interface Conjecture { id: string; title: string; project_id: string; kind: string;
  status: "proposed" | "tested-n-cases" | "lean-statement" | "proved" | "refuted"; cases_tested: number;
  statement_nl: string; motivation: string; origin: object; lean_statement: string; statement_ok: boolean;
  proved: boolean; counterexample: { witness: object; verified: boolean; sage: boolean; lean: boolean } | null;
  promoted: object | null; evidence: Evidence[]; experiments: Experiment[]; chain_ok: boolean }

interface PlanNode { id: string; parent: string | null; children: string[]; title: string; statement_nl: string;
  why: string; lean: string; status: string; state: string; dossier_id: string; admitted: boolean; edited: boolean;
  cancelled: boolean; proved: boolean; conditional: object | null; dossier_status: string }
interface Plan { rev: number; t: number; source: "ai" | "user" | "sketch"; model: string; root: string;
  nodes: Record<string, PlanNode>; root_state: string; queued: string[]; limit: number;
  verdict: { state: "open" | "proved_modulo" | "proved"; verified: boolean; admitted: number; admitted_names?: string[] };
  versions: { rev; t; source; model; device; note }[] }
```

## 8. Security boundary

- **Code execution** happens only through `madalean/research/sagebridge.py` (experiments) and Lean checks. Model text
  never becomes a shell command. Experiment code: drafted by the model or written by the user, shown to the user,
  executed only (a) after an explicit approval of that exact code (hash), or (b) when the host enabled
  `experiments_auto`; approval and run are refused from paired devices unless the host enabled `experiments_remote`
  (both settings host-only). Lean `example`s for small cases / refutations are generated by the server from the
  statement (values validated, no tactic text from the model).
- **Kernel confinement**: Madalean's kernelspecs `madalean-sage` / `madalean-python` (in the Jupyter manager's
  `JUPYTER_PATH`) start the system kernel through the launcher: environment rebuilt from an allow-list (no API key,
  token, cookie, credential variable — verified by a test), HOME / cwd = `<cache>/experiments/<conjecture>`,
  `RLIMIT_AS` 4 GB, `RLIMIT_FSIZE` 512 MB, no core dumps; with bubblewrap (present here): whole file system read-only,
  only the experiments directory writable, Madalean's config directory (keys.json, devices.json), ~/.ssh, ~/.gnupg,
  keyrings, ~/.aws, ~/.netrc, git credentials hidden behind empty tmpfs (verified by a test). Without bubblewrap:
  rlimits + env + cwd only (`/experiments/status` → `sandbox:"rlimits"`). Network from the kernel is NOT blocked.
  Each run: wall-clock timeout → interrupt → kernel killed; output cap 200 kB → kernel killed. jupyter-lab itself now
  starts with secret-looking variables removed from its environment.
- **Attachments**: type sniffed from magic bytes (PNG, JPEG, GIF, WebP, PDF only; images fully decoded by Pillow),
  SVG / HTML refused, ≤ 10 MB, stored under random ids, served with the sniffed type, `nosniff`,
  `Content-Security-Policy: default-src 'none'; sandbox`, PDFs as `attachment`. Rendering notes (Markdown/KaTeX
  sanitising) is the UI's job.
- **Paths**: no file route takes a path; ids are validated (`bad_id`); attachment ids must match `a-[0-9a-f]{16}`.
- **git**: `git ls-remote` only on `https://` URLs (from manifests or the add-library form; no credentials in the URL,
  no option injection), `GIT_TERMINAL_PROMPT=0`, askpass disabled, user/system git config ignored, `credential.helper`
  empty, hooks path `/dev/null`, `protocol.file`/`ext` disabled, 25 s timeout. Installs only in managed workspaces
  (never user projects, never lean-prover49), always copy → verify → switch.
- **System packages**: read-only queries only; Madalean never runs pacman/apt/dnf/sudo/pip; « Installer » only opens
  a terminal on the server's own command (no `#`, no newline), the user confirms and types the password.
- **Self-update**: signed channel / signed checksums with the embedded Ed25519 key, safe extraction, health check
  before the switch, rollback kept; host-only endpoints.

## 9. Demo mode

`madalean serve --demo` seeds, in the demo project: three linked notes (note ↔ note, note → dossier, note → library
result, note → source `@hardy-wright#p12`, a Lean block, tags), the conjecture « n² + n + 41 est premier » with an
evidence log (10 Lean cases, a Python experiment, the counter-example n = 40 re-verified → `refuted`), the conjecture
« n² + n est pair » (`tested-n-cases`), a proof plan tree (3 claims, one accepted) on the draft dossier, and a hint
ladder on the proven dossier (levels 1–2 revealed for `host`). The scripted brain answers the workshop's prompts
(generation, experiment code, plan draft, hints, explain-back).
