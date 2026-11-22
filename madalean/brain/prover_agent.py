"""Agentic prover: a tool-using model writes a Lean 4 proof incrementally, checking each attempt with the real Lean
compiler of the workspace (through the server's `check`), searching Mathlib for exact names, and finishing with
`submit`. The statement can never be altered (every attempt is assembled with leancheck.assemble_proof)."""
from __future__ import annotations

import inspect
import re
import time
from typing import Any, Awaitable, Callable

from .. import leancheck, names
from .agent import StopAgent
from .api import AgentResult, Brain, BrainError, OnChunk, Retriever, ToolSpec

CheckFn = Callable[[str], Awaitable[dict]]

WORKSPACE_NOTES = {
    "lean-prover49": (
        "Lean 4.9.0 with the Mathlib of mid-2024 (the exact version Goedel-Prover-V2 was trained on). Many lemma "
        "names differ from recent Mathlib (renamed since: e.g. `Finset.card_le_card` vs older `card_le_of_subset`, "
        "`Nat.pos_of_ne_zero`, `div_le_iff` without primes…). Recent tactics or lemmas you remember may not exist."),
    "lean-current": (
        "Lean 4.34 with a recent Mathlib (late 2026). Lemma names follow current Mathlib conventions; some older "
        "names you may remember are deprecated or removed."),
}

SYSTEM_PROMPT = """You are an expert Lean 4 and Mathlib proof engineer. Your task: produce a complete proof of the \
given theorem that the Lean compiler of THIS workspace accepts under a strict check.

# Environment
- Workspace: {workspace}. {version_note}
- Every attempt is compiled in a file whose header is fixed and cannot be changed:
```lean
{header}```
- The theorem statement is fixed: you write its proof. You may add helper lemmas ABOVE the theorem.
- Forbidden (the strict check rejects them): `sorry`, `admit`, new `axiom`s, `exact?`/`apply?`, `native_decide`, \
`#exit`, metaprogramming (`elab`, `macro`, `run_tac`…). Only the standard axioms are allowed.
- The compiler is the only judge. Tool results describe THIS Mathlib and are the truth, even when they contradict \
your memory.

# Tools
- `lean_check`: compile an attempt. Give either `proof` (the tactic block that follows `:= by`, the statement is \
added for you) or `code` (helper lemmas + the theorem with the identical statement). Returns Lean's errors with \
their position and the goal state, or "accepted".
- `search_mathlib`: find declarations of this workspace by meaning or by name words ("sum of even numbers is even", \
"Finset sum le", "Polynomial roots card"). Returns exact names and signatures.
- `read_declaration`: the exact signature, docstring and module of one name (and close names if it does not exist).
- `library_search`: results the user already proved in Madalean (reusable as lemmas: copy them above the theorem).
{online_tool}- `submit`: finish with the complete accepted code. The run ends only when `submit` succeeds.

# Method — follow it
1. Plan first, briefly (2–6 lines, in your text): the mathematical argument and the Mathlib facts it needs.
2. Look up names before using them. Never guess a lemma name: search_mathlib / read_declaration it. If Lean says \
`unknown identifier` / `unknown constant`, search for the real name instead of trying variations from memory.
3. Check early and often. A first attempt with automation (`simp`, `omega`, `linarith`, `nlinarith [sq_nonneg (a - b)]`, \
`positivity`, `norm_num`, `ring`, `decide`, `aesop`, `field_simp`, `gcongr`) costs little: call lean_check.
4. Work incrementally. Split the proof with `have h : … := by …` steps and `calc` chains; check after each \
significant change. Read the error position and the goal Lean prints; fix that specific problem.
5. If the same approach fails three times, change strategy: another decomposition, a helper lemma, induction, case \
analysis (`rcases`, `obtain ⟨x, hx⟩ := h`, `by_cases`), contraposition, or unfolding a definition \
(`Even a` is `∃ r, a = r + r`; `Odd a` is `∃ k, a = 2 * k + 1`).
6. As soon as lean_check answers "accepted", call `submit` with exactly that code (same `proof` or `code`).

# Lean 4 reminders
- Tactic blocks are indentation-sensitive (2 spaces); focus goals with `·`; `<;>` applies a tactic to all goals.
- `induction n with | zero => … | succ n ih => …`; `rcases h with ⟨x, rfl⟩ | h2`; `refine ⟨_, ?_⟩`.
- Coercions: `(n : ℝ)`, `push_cast`, `Nat.cast_le`, `exact_mod_cast`. Natural subtraction truncates: prefer `omega`.
- Keep your messages short; the reasoning belongs in your thinking, the actions in tool calls."""

ONLINE_TOOL = ("- `lean_search_online`: query public Lean search engines (LeanSearch, Loogle) with a short query. "
               "They index a RECENT Mathlib: confirm every name with read_declaration before using it.\n")

TOOLS_PARAMS = {
    "lean_check": {"type": "object", "properties": {
        "proof": {"type": "string", "description": "Tactic block after `:= by` (statement added automatically)."},
        "code": {"type": "string", "description": "Helper lemmas + the theorem with the identical statement."}},
        "required": []},
    "search_mathlib": {"type": "object", "properties": {
        "query": {"type": "string", "description": "What you look for, in words or name fragments."},
        "k": {"type": "integer", "description": "Number of results (default 8, max 20)."}}, "required": ["query"]},
    "read_declaration": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Full name, e.g. `Finset.sum_le_sum`."}}, "required": ["name"]},
    "library_search": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    "lean_search_online": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    # aliases for Leanstral (S-U): its card's example tool is `lean_run_code` {code | file_path}, and it was trained
    # with the Lean language server's tools (lean-lsp-mcp names) — same strict check, statement re-assembled
    "lean_run_code": {"type": "object", "properties": {
        "code": {"type": "string", "description": "Lean 4 code: helper lemmas + the theorem with the identical statement."},
        "file_path": {"type": "string", "description": "Not supported here: give `code`."}}, "required": []},
    "lean_leansearch": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    "lean_loogle": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    "submit": {"type": "object", "properties": {
        "proof": {"type": "string", "description": "Accepted tactic block."},
        "code": {"type": "string", "description": "Accepted full code (helpers + theorem)."}}, "required": []},
}


def _fmt_decls(items: list[dict], limit_sig: int = 300) -> str:
    lines = []
    for d in items:
        sig = (d.get("signature") or "").replace("\n", " ")
        line = f"- `{d['name']}` {sig[:limit_sig]}"
        if d.get("doc"):
            line += f"\n    doc: {d['doc'].strip().splitlines()[0][:200]}"
        if d.get("note"):
            line += f"\n    note: {d['note']}"
        if d.get("deprecated"):
            line += "\n    (deprecated)"
        lines.append(line)
    return "\n".join(lines)


def dedent_tactics(body: str) -> str:
    """Re-indent a tactic block to 2 spaces. Models often give the first line unindented and the following ones
    indented as inside `:= by` (copied from a file): then the base indent is that of the last top-level line."""
    lines = [l.rstrip() for l in body.split("\n")]
    ind = [len(l) - len(l.lstrip()) for l in lines]
    nonempty = [i for i, l in enumerate(lines) if l.strip()]
    if not nonempty:
        return ""
    base = min(ind[i] for i in nonempty)
    rest = [i for i in nonempty[1:]]
    if ind[nonempty[0]] == 0 and rest and min(ind[i] for i in rest) > 0 and ind[rest[-1]] == min(ind[i] for i in rest):
        k = min(ind[i] for i in rest)
        lines[nonempty[0]] = " " * k + lines[nonempty[0]]
        ind[nonempty[0]] = k
        base = k
    return "\n".join("  " + l[base:] if l.strip() else "" for l in lines)


class _Session:
    def __init__(self, statement: str, check: CheckFn, retriever: Retriever | None, workspace_key: str,
                 on_chunk: OnChunk | None):
        self.statement = leancheck.prepare_statement(statement)
        self.name = leancheck.theorem_name(self.statement)
        self.check, self.retriever, self.ws = check, retriever, workspace_key
        self.on_chunk = on_chunk
        self.cache: dict[str, dict] = {}
        self.best: str | None = None
        self.checks = 0
        self.rejected_names: list[str] = []

    def assemble(self, args: dict) -> str:
        code, proof = (args.get("code") or "").strip("\n"), (args.get("proof") or "").strip("\n")
        if not code.strip() and re.search(r"(?m)^\s*(?:theorem|lemma)\s", leancheck.remove_comments(proof)):
            code, proof = proof, ""                     # a whole theorem given as `proof`
        code = code.strip()
        if not code and not proof.strip():
            raise ValueError("give `proof` (tactic block) or `code` (full theorem)")
        if code and re.search(r"(?m)^\s*(?:theorem|lemma)\b", leancheck.remove_comments(code)):
            src = code if re.search(r"(?m)^\s*theorem\b", code) else re.sub(r"(?m)^(\s*)lemma\b", r"\1theorem", code)
            return leancheck.assemble_proof(self.statement, src)
        body = proof or code
        body = re.sub(r"^\s*:=\s*by\b", "", body).strip("\n")
        if body.lstrip().startswith("by\n") or body.lstrip() == "by":
            body = body.lstrip()[2:]
        body = dedent_tactics(body)
        model_code = self.statement.rsplit("sorry", 1)[0].rstrip() + "\n" + body + "\n"
        return leancheck.assemble_proof(self.statement, model_code)

    async def run_check(self, args: dict) -> tuple[bool, str, str]:
        """(ok, message for the model, code)."""
        try:
            code = self.assemble(args)
        except (ValueError, leancheck.StatementError) as e:
            return False, f"Could not assemble the attempt: {e}", ""
        bad = leancheck.forbidden_reasons(code)
        if bad:
            return False, ("Rejected before compiling: the attempt contains forbidden constructs (" + ", ".join(bad) +
                           "). Write a complete proof without sorry/admit/axioms/exact?/apply?."), code
        if code in self.cache:
            r = self.cache[code]
            prefix = "(This exact code was already checked.) "
        else:
            self.checks += 1
            r = await self.check(code)
            self.cache[code] = r
            prefix = ""
        if r.get("ok"):
            self.best = code
            return True, prefix + "Lean ACCEPTED this proof (strict check passed). Now call `submit` with it.", code
        fb = r.get("feedback") or r.get("summary") or "rejected"
        note = await self._names_note(fb)
        return False, f"{prefix}Lean rejected the attempt.\n{fb}{note}", code

    async def _names_note(self, feedback: str) -> str:
        if "Note on unknown names" in feedback or self.retriever is None:
            return ""
        missing = names.missing_names(feedback)
        for name, _rest, msg in names._BLOCK.findall(feedback):      # Lean 4.9: `T.foo x` reported as a field error
            if ("invalid field notation" in msg or "unknown" in msg) and "." in name and name not in missing:
                try:
                    if await self.retriever.declaration(self.ws, name) is None:
                        missing.append(name)
                except Exception:  # noqa: BLE001
                    pass
        if not missing:
            return ""
        parts = []
        for m in missing[:3]:
            if m not in self.rejected_names:
                self.rejected_names.append(m)
            try:
                sug = await self.retriever.suggest(self.ws, m, 5) if hasattr(self.retriever, "suggest") \
                    else await self.retriever.search(self.ws, m.replace(".", " ").replace("_", " "), 5)
            except Exception:  # noqa: BLE001
                sug = []
            if sug:
                parts.append(f"`{m}` does not exist here. Close existing names:\n" + _fmt_decls(sug, 160))
        return ("\n\nNote on unknown names:\n" + "\n".join(parts)) if parts else ""


async def prove_with_agent(brain: Brain, retriever: Retriever | None, *, statement: str, workspace_key: str,
                           check: CheckFn, library_search: Callable[[str], Awaitable[Any]] | None = None,
                           hint: str = "", on_chunk: OnChunk | None = None, mode: str = "auto", max_steps: int = 24,
                           max_seconds: float = 900, only: str | None = None, request: str = "") -> dict:
    """Agentic proof search. Returns {code, model, steps, finish, transcript, checks, seconds}; `code` is the best
    code Lean accepted (the server re-checks it), finish: proved | max_steps | budget | error | gave_up.
    `only`: run on this model key alone (tournament contestant, pipeline/tournament.py). `request`: the problem in
    words (S-AM, D45): with the statement, it selects the verified catalogue constructions given in the task."""
    t0 = time.monotonic()
    s = _Session(statement, check, retriever, workspace_key, on_chunk)
    settings = getattr(brain, "settings", {}) or {}
    online_ok = mode != "local" and settings.get("mode") != "local" and settings.get("online_search", True)

    async def t_check(a: dict) -> str:
        ok, msg, _code = await s.run_check(a)
        return msg

    async def t_submit(a: dict) -> str:
        try:
            code = s.assemble(a)
        except (ValueError, leancheck.StatementError) as e:
            return f"Could not assemble the submission: {e}"
        if code == s.best or (s.cache.get(code) or {}).get("ok"):
            raise StopAgent(code, "Submitted: proof accepted.")
        ok, msg, code = await s.run_check(a)
        if ok:
            raise StopAgent(code, "Submitted: proof accepted.")
        return "Submission refused (it does not compile under the strict check).\n" + msg

    async def t_search(a: dict) -> str:
        if retriever is None:
            return "No declaration index is available."
        if hasattr(retriever, "ready") and not retriever.ready(workspace_key):
            retriever.start(workspace_key) if hasattr(retriever, "start") else None
            return "The declaration index is still being built (about a minute). Meanwhile use read_declaration on precise names or lean_check."
        k = max(1, min(int(a.get("k") or 8), 20))
        res = await retriever.search(workspace_key, str(a["query"]), k)
        return _fmt_decls(res) if res else "No declaration found. Try other words (Mathlib naming: le, lt, add, mul, sum, card, dvd…)."

    async def t_read(a: dict) -> str:
        if retriever is None:
            return "No declaration index is available."
        nm = str(a["name"]).strip().strip("`")
        d = await retriever.declaration(workspace_key, nm)
        if d is None:
            sug = await retriever.suggest(workspace_key, nm, 6) if hasattr(retriever, "suggest") else []
            return f"`{nm}` does not exist in this workspace." + ("\nClose names:\n" + _fmt_decls(sug) if sug else "")
        out = [f"{d.get('kind', '')} `{d['name']}`", f"signature: {d.get('signature', '')}"]
        if d.get("variables"):
            out.append(f"variables in scope where it is declared: {d['variables'][-400:]}")
        if d.get("original_signature"):
            out.append(f"original (multiplicative) signature: {d['original_signature']}")
        for k in ("doc", "module", "note"):
            if d.get(k):
                out.append(f"{k}: {d[k]}")
        return "\n".join(out)

    async def t_library(a: dict) -> str:
        if library_search is None:
            return "The user's library is empty."
        res = await library_search(str(a["query"]))
        if not res:
            return "Nothing relevant in the user's library."
        if isinstance(res, str):
            return res
        return "\n\n".join(f"- {r.get('name', '')}:\n```lean\n{r.get('code') or r.get('statement') or ''}\n```"
                           if isinstance(r, dict) else str(r) for r in res[:6])

    async def t_online(a: dict) -> str:
        from .lean_search import search_online
        http = getattr(brain, "http", None)
        if http is None:
            return "Online search is not available."
        res, failed = await search_online(http, str(a["query"]), 6)
        if not res:
            return "No result (services unreachable: " + ", ".join(failed) + ")." if failed else "No result."
        return ("Results from RECENT Mathlib (verify each name here with read_declaration):\n" + _fmt_decls(res)
                + (f"\n(unavailable: {', '.join(failed)})" if failed else ""))

    def spec(name: str, desc: str, fn) -> ToolSpec:
        return ToolSpec(name, desc, TOOLS_PARAMS[name], fn)

    tools = [
        spec("lean_check", "Compile an attempt with the workspace's Lean (strict check). Give `proof` or `code`.", t_check),
        spec("search_mathlib", "Search the declarations of this workspace (Mathlib, Batteries, Lean core).", t_search),
        spec("read_declaration", "Exact signature, doc and module of a declaration of this workspace.", t_read),
        spec("library_search", "Search the user's library of already proven results.", t_library),
    ]
    if online_ok:
        tools.append(spec("lean_search_online", "Ask LeanSearch / Loogle (recent Mathlib) about a short query.", t_online))
    if only and "leanstral" in only.lower():
        async def t_run_code(a: dict) -> str:
            if not str(a.get("code") or "").strip():
                return "Give the Lean code in `code` (files are not available here)."
            return await t_check({"code": a["code"]})
        tools.append(spec("lean_run_code", "Compile Lean 4 code (helpers + the theorem, identical statement) with the "
                          "workspace's Lean under the strict check; returns errors and remaining goals.", t_run_code))
        if online_ok:
            tools.append(spec("lean_leansearch", "LeanSearch: natural-language search of (recent) Mathlib.", t_online))
            tools.append(spec("lean_loogle", "Loogle: search Mathlib by name or type pattern.", t_online))
    tools.append(spec("submit", "Finish: submit the complete accepted proof (`proof` or `code`).", t_submit))

    ws_note = WORKSPACE_NOTES.get(workspace_key, "")
    if not ws_note:
        try:
            from .rag import default_resolve
            w = default_resolve(workspace_key)
            ws_note = f"Toolchain {w.toolchain}." if w else ""
        except Exception:  # noqa: BLE001
            ws_note = ""
    try:                         # S-AB: the syntax card verified on this toolchain + Mathlib (syntaxcards.py)
        from .rag import default_resolve
        from .. import syntaxcards
        card = syntaxcards.lean_card(default_resolve(workspace_key))
    except Exception:  # noqa: BLE001 (no card: the prompt as before)
        card = ""
    if card:
        ws_note = (ws_note + "\n\n" + card).strip()
    system = SYSTEM_PROMPT.format(workspace=workspace_key, version_note=ws_note, header=leancheck.GOEDEL_HEADER,
                                  online_tool=ONLINE_TOOL if online_ok else "")
    premises_txt = ""
    if retriever is not None:
        try:
            if hasattr(retriever, "ready") and not retriever.ready(workspace_key):
                if hasattr(retriever, "ensure"):
                    await retriever.ensure(workspace_key, timeout=min(120.0, max_seconds / 4))
            prem = await retriever.premises(workspace_key, s.statement, 8)
            if prem:
                premises_txt = ("\n\nDeclarations of this workspace that may be relevant (found by search, check "
                                "that they fit):\n" + _fmt_decls(prem, 200))
        except Exception:  # noqa: BLE001
            premises_txt = ""
    catalogue_txt = ""
    try:                         # S-AM (D45): verified constructions of this workspace relevant to the request
        from .rag import default_resolve
        from ..pipeline.leancat import block_for
        block, _ids = block_for(default_resolve(workspace_key), "prove", request, s.statement)
        catalogue_txt = ("\n\n" + block) if block else ""
    except Exception:  # noqa: BLE001 (no catalogue: the task as before)
        catalogue_txt = ""
    target = s.statement.split("\n\n")[-1] if "theorem" in s.statement.split("\n\n")[-1] else s.statement
    task = (f"Prove this theorem (workspace {workspace_key}):\n\n```lean\n{target.strip()}\n```"
            + (f"\n\nOther declarations above it in the file (already available):\n```lean\n"
               f"{s.statement.replace(leancheck.GOEDEL_HEADER, '').rsplit(target.strip(), 1)[0].strip()}\n```"
               if s.statement.replace(leancheck.GOEDEL_HEADER, "").strip() != target.strip() else "")
            + (f"\n\nHint from the user: {hint.strip()}" if hint.strip() else "")
            + premises_txt
            + catalogue_txt
            + "\n\nStart with your plan, then use the tools. Finish with `submit`.")

    kwargs: dict = {"mode": mode, "max_steps": max_steps, "max_seconds": max_seconds, "on_chunk": on_chunk}
    run = brain.run_agent
    params = inspect.signature(run).parameters
    if "require_tool" in params:
        kwargs["require_tool"] = "submit"
    if only and "only" in params:
        kwargs["only"] = only
    try:
        res: AgentResult = await run("prove", system, task, tools, **kwargs)
    except BrainError as e:
        return {"code": s.best, "model": None, "steps": 0, "finish": "error", "transcript": [{"type": "error",
                "kind": e.kind, "text": str(e)}], "checks": s.checks, "seconds": time.monotonic() - t0}
    code = s.best
    finish = "proved" if code else (res.finish if res.finish != "done" else "gave_up")
    return {"code": code, "model": res.model, "steps": res.steps, "finish": finish, "transcript": res.transcript,
            "checks": s.checks, "seconds": round(time.monotonic() - t0, 1)}
