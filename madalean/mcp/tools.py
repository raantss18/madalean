"""The tools Madalean offers to MCP clients (session S-AZ, DECISIONS D58, docs/MCP.md §2).

A small, read-mostly set. Each tool is a `Tool` in `REGISTRY`: a name, a strict input schema (mcp/schema.py), MCP
annotations, a per-minute rate limit, an `available(ctx)` predicate (a tool that is not available is not listed) and
an async `run(env, args)` that returns a JSON-able dict. New tools plug in with `register(Tool(...))` — that is how
`literature_search` appears once the literature package of session S-AX provides its hook.

Rules every tool follows:
- nothing is written: no dossier, no library entry, no note, no file of a workspace (check_lean / certify compile in
  the Lean sandbox's private temporary directory, like every check);
- Lean is the judge: check_lean and certify use a FRESH strict Lean run, never the warm Lean (D37);
- code is never taken from the client: sage_compute runs only the code Madalean's verified catalogue (D39) assembles
  from a request in words, in Calcul's sandboxed kernel, and only when the host switched it on;
- outputs are data (JSON), never instructions."""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .. import leancheck
from ..logs import get

log = get("mcp")
WS_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$"
ID_PATTERN = WS_PATTERN
CHECK_TIMEOUT_MAX = 300
SAGE_SECONDS = 30
SAGE_KERNEL = "madalean-mcp"
LEAN_PARALLEL = 2


class ToolError(Exception):
    """A failure the client should read (isError result), not a protocol error."""

    def __init__(self, kind: str, message: str, **extra: Any):
        super().__init__(message)
        self.kind, self.message, self.extra = kind, message, extra


@dataclass
class ToolEnv:
    ctx: Any
    request: Any = None           # the aiohttp request that carried the call (explain_lean reuses its handler)
    transport: str = "http"


@dataclass
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict
    run: Callable[[ToolEnv, dict], Awaitable[dict]]
    read_only: bool = True
    open_world: bool = False                  # reaches models or services outside the host
    rate: int = 60                            # calls per minute
    available: Callable[[Any], bool] = field(default=lambda ctx: True)

    def describe(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": self.input_schema,
                "annotations": {"title": self.title, "readOnlyHint": self.read_only, "destructiveHint": False,
                                "idempotentHint": self.read_only, "openWorldHint": self.open_world}}


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    REGISTRY[tool.name] = tool
    return tool


def listed(ctx) -> list[Tool]:
    out = []
    for t in REGISTRY.values():
        try:
            if t.available(ctx):
                out.append(t)
        except Exception:  # noqa: BLE001 (a broken predicate hides its tool, never the list)
            log.exception("mcp tool %s: availability", t.name)
    return out


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


_WS = {"type": "string", "pattern": WS_PATTERN, "maxLength": 80,
       "description": "Lean workspace key (see Madalean › Réglages › Espaces Lean). Default: the user's workspace."}


def _workspace(ctx, args: dict):
    ws = ctx.workspace(str(args.get("workspace") or "") or ctx.settings.workspace)
    if ws is None:
        raise ToolError("workspace", "unknown or unavailable Lean workspace")
    return ws


_LEAN_SEM: dict[int, asyncio.Semaphore] = {}


def _lean_sem() -> asyncio.Semaphore:
    loop = id(asyncio.get_running_loop())
    if loop not in _LEAN_SEM:
        _LEAN_SEM.clear()
        _LEAN_SEM[loop] = asyncio.Semaphore(LEAN_PARALLEL)
    return _LEAN_SEM[loop]


# ---------------------------------------------------------------- search_mathlib
async def _search_mathlib(env: ToolEnv, args: dict) -> dict:
    from ..server.routes_extra import _lookup
    ctx = env.ctx
    ws = str(args.get("workspace") or "") or ctx.settings.workspace
    status, res = await _lookup(ctx, ws, "search", args["query"].strip(), int(args.get("k") or 8))
    keep = ("name", "kind", "signature", "doc", "module", "deprecated")
    return {"workspace": ws, "status": status,
            "results": [{k: d.get(k) for k in keep if d.get(k) not in (None, "")} for d in (res or [])
                        if isinstance(d, dict)]}


register(Tool(
    "search_mathlib", "Search Mathlib",
    "Search the declarations (Mathlib, Batteries, Lean core) of one of Madalean's Lean workspaces by meaning or by "
    "name words. Returns exact names and signatures of THIS Mathlib version. status: ok | indexing (retry in a "
    "minute) | unavailable.",
    _obj({"query": {"type": "string", "minLength": 1, "maxLength": 200,
                    "description": "What you look for, e.g. 'sum of a geometric series' or 'Finset sum le'."},
          "k": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Number of results (default 8)."},
          "workspace": _WS}, ["query"]),
    _search_mathlib))


# ---------------------------------------------------------------- check_lean
def _assemble(statement: str, proof: str) -> tuple[str, str]:
    """(prepared statement, assembled code) — the statement is pinned (D19 rule: a proof cannot change it)."""
    from ..brain.prover_agent import _Session
    s = _Session(statement, None, None, "", None)       # prepares the statement, raises StatementError
    return s.statement, s.assemble({"proof": proof})


async def _check_lean(env: ToolEnv, args: dict) -> dict:
    ctx = env.ctx
    ws = _workspace(ctx, args)
    statement, proof = args["statement"], str(args.get("proof") or "")
    timeout = min(int(ctx.settings.compile_timeout_s or 180), CHECK_TIMEOUT_MAX)
    try:
        if proof.strip():
            st, code = _assemble(statement, proof)
            name = leancheck.theorem_name(st)
            code = leancheck.with_axiom_probe(code, name)
            mode = "proof"
        else:
            code, name, mode = leancheck.prepare_statement(statement), None, "statement"
    except (leancheck.StatementError, ValueError) as e:
        raise ToolError("bad_statement", f"cannot assemble: {e}")
    risks = leancheck.exec_risks(code.rsplit("#print axioms", 1)[0] if name else code)
    if risks:        # D28, also enforced by the Lean runner: code that could run on the host is never compiled
        return {"workspace": ws.key, "mode": mode, "ok": False, "verdict": "rejected",
                "summary": "refused before compiling: " + ", ".join(risks), "reasons": risks, "errors": [],
                "axioms": None, "has_sorry": False, "seconds": 0.0, "via": "none", "checked_code": ""}
    if await ctx.lean.problems(ws):
        raise ToolError("workspace", "the Lean workspace is not ready")
    async with _lean_sem():
        # warm=False: always a fresh `lean --json` in the sandbox, the strict verdict (D37: warm verdicts never decide)
        r = await ctx.lean.check(code, ws, timeout, name, owner="mcp", warm=False)
    v = r.verdict
    ok = v.ok if mode == "proof" else (not v.errors and not r.timed_out and not r.infra_error)
    return {"workspace": ws.key, "mode": mode, "ok": bool(ok),
            "verdict": "accepted" if ok else ("timeout" if r.timed_out else "rejected"),
            "summary": v.summary, "reasons": list(v.reasons),
            "errors": [{"line": m.line, "col": m.col, "severity": m.severity, "text": m.text[:2000]}
                       for m in v.errors[:20]],
            "axioms": v.axioms, "has_sorry": bool(v.has_sorry), "seconds": round(r.seconds, 2), "via": r.via,
            "checked_code": code if mode == "proof" else ""}


register(Tool(
    "check_lean", "Check with Lean",
    "Compile a Lean 4 statement, or a proof of it, with Madalean's Lean + Mathlib (fresh run, sandboxed). With "
    "`proof`: the statement is pinned and the STRICT verdict applies (no sorry/admit, no new axiom, standard axioms "
    "only); ok=true means Lean accepted the proof. Without `proof`: checks that the statement compiles (`sorry` "
    "allowed). Nothing is stored.",
    _obj({"statement": {"type": "string", "minLength": 1, "maxLength": 20000,
                        "description": "`theorem name (binders) : prop := by sorry` (Mathlib is imported)."},
          "proof": {"type": "string", "maxLength": 100000,
                    "description": "Tactic block after `:= by`, or full code (helper lemmas + the same theorem)."},
          "workspace": _WS}, ["statement"]),
    _check_lean, rate=20))


# ---------------------------------------------------------------- certify
async def _certify(env: ToolEnv, args: dict) -> dict:
    from ..certs import engine
    from ..server.plugins import certificates as C
    ctx = env.ctx
    st = C._prepared(args["statement"])
    if st is None:
        raise ToolError("bad_statement", "malformed statement (`theorem … := by sorry` or `(binders) : prop`)")
    ws = _workspace(ctx, args)
    if await ctx.lean.problems(ws):
        raise ToolError("workspace", "the Lean workspace is not ready")
    if ctx.demo:
        return {"status": "none", "kinds": engine.kinds_of(st), "workspace": ws.key}
    if env.request is None or C.LOCK not in env.request.app:
        raise ToolError("unavailable", "certificates are not available")
    o = await C._certify(env.request, ctx, st, ws)
    return {**o.to_dict(), "kinds": [t["kind"] for t in o.tried], "workspace": ws.key}


register(Tool(
    "certify", "Certificate check",
    "« Sage computes, Lean checks » (Madalean certificates): for a decidable or computational statement (primality, "
    "factorisation, polynomial identity, explicit witness, bounded check…), Madalean's fixed program computes a "
    "witness and a fresh strict Lean run checks the resulting proof. status verified = Lean accepted it.",
    _obj({"statement": {"type": "string", "minLength": 1, "maxLength": 20000,
                        "description": "`theorem name … := by sorry`, or just `(binders) : prop`."},
          "workspace": _WS}, ["statement"]),
    _certify, rate=10))


# ---------------------------------------------------------------- explain_lean
async def _explain_lean(env: ToolEnv, args: dict) -> dict:
    import json
    from ..server.plugins import lean_explain
    if env.request is None:
        raise ToolError("unavailable", "explanations are not available")
    data = {"mode": args.get("mode") or "error", "code": args["code"], "part": args.get("part") or ""}
    for k in ("workspace", "error"):
        if args.get(k):
            data[k] = args[k]
    resp = await lean_explain.handle(env.request, data)
    out = json.loads(resp.text or "{}")
    if resp.status >= 400:
        raise ToolError(str(out.get("error") or "error"), str((out.get("message") or {}).get("text") or
                                                              out.get("error") or "error"))
    out.pop("stream", None)
    return out


register(Tool(
    "explain_lean", "Explain Lean",
    "Explain Lean 4 code in plain words. mode=error: what Lean's error means and a correction — `fix` is non-empty "
    "only when Lean accepted it (fix_status accepted). mode=lines: a gloss of each line with the goal Lean prints "
    "after it. Uses Madalean's models; nothing is stored.",
    _obj({"code": {"type": "string", "minLength": 1, "maxLength": 50000},
          "mode": {"type": "string", "enum": ["error", "lines"]},
          "part": {"type": "string", "enum": ["", "statement", "proof"],
                   "description": "statement: the code is a statement (sorry allowed); proof: a full theorem."},
          "error": {"type": "string", "maxLength": 4000, "description": "Lean's error text, if you have it."},
          "workspace": _WS}, ["code"]),
    _explain_lean, open_world=True, rate=10))


# ---------------------------------------------------------------- library_search
async def _library_search(env: ToolEnv, args: dict) -> dict:
    from ..dossiers import tokens
    ctx = env.ctx
    ws = str(args.get("workspace") or "")
    q = tokens(args["query"])
    scored = []
    for e in ctx.library.entries:
        if ws and e.workspace != ws:
            continue
        words = tokens(e.statement) | tokens(e.title)
        sc = len(q & words) / max(1, len(q | words))
        if sc > 0 or args["query"].lower() in (e.title + " " + e.name).lower():
            scored.append((sc, e))
    scored.sort(key=lambda x: -x[0])
    k = int(args.get("k") or 8)
    return {"results": [{"name": e.name, "title": e.title, "statement": e.statement, "code": e.code,
                         "workspace": e.workspace, "dossier": e.dossier} for _sc, e in scored[:k]],
            "total": len(ctx.library.entries)}


register(Tool(
    "library_search", "Search the library",
    "Search the user's Madalean library: results already proved and accepted by Lean, reusable as lemmas (paste "
    "`code` above a new theorem of the same workspace).",
    _obj({"query": {"type": "string", "minLength": 1, "maxLength": 200},
          "k": {"type": "integer", "minimum": 1, "maximum": 20},
          "workspace": _WS}, ["query"]),
    _library_search))


# ---------------------------------------------------------------- dossier_status
def _dossier(ctx, d) -> dict:
    job = ctx.orchestrator.active_for(d.id) if getattr(ctx, "orchestrator", None) is not None else None
    jd = job.to_dict() if job is not None else None
    return {"id": d.id, "title": d.title, "status": d.status, "proved": bool(d.proof_is_current),
            "statement": d.statement, "proof": d.proof if d.proof_is_current else "", "workspace": d.workspace,
            "project_id": d.project_id, "updated": d.updated,
            "job": {"state": jd.get("state"), "stage": jd.get("stage")} if jd else None}


async def _dossier_status(env: ToolEnv, args: dict) -> dict:
    ctx = env.ctx
    if args.get("dossier_id"):
        d = ctx.repo.get(args["dossier_id"])
        if d is None or d.archived:
            raise ToolError("not_found", "no such dossier")
        return {"dossier": _dossier(ctx, d)}
    q = str(args.get("query") or "").lower()
    items = [d for d in ctx.repo.list(include_archived=False) if not q or q in (d.title or "").lower()]
    items.sort(key=lambda d: -(d.updated or 0))
    return {"dossiers": [{"id": d.id, "title": d.title, "status": d.status, "proved": bool(d.proof_is_current),
                          "updated": d.updated} for d in items[: int(args.get("k") or 20)]]}


register(Tool(
    "dossier_status", "Dossier status",
    "Status of the user's Madalean dossiers (one request each: statement, proof, state of the running job). With "
    "`dossier_id`: that dossier; otherwise the most recent ones, optionally filtered by words of the title.",
    _obj({"dossier_id": {"type": "string", "pattern": ID_PATTERN, "maxLength": 80},
          "query": {"type": "string", "maxLength": 200},
          "k": {"type": "integer", "minimum": 1, "maximum": 50}}),
    _dossier_status))


# ---------------------------------------------------------------- literature_search (session S-AX's package)
LITERATURE_MODULE = "madalean.literature"


def _literature_hook():
    """`madalean.literature.mcp_search(ctx, query, k) -> list[dict]` when the literature package (S-AX) provides
    it; None otherwise (then the tool is not listed)."""
    try:
        if importlib.util.find_spec(LITERATURE_MODULE) is None:
            return None
        fn = getattr(importlib.import_module(LITERATURE_MODULE), "mcp_search", None)
    except Exception:  # noqa: BLE001
        return None
    return fn if callable(fn) else None


async def _literature_search(env: ToolEnv, args: dict) -> dict:
    fn = _literature_hook()
    if fn is None:
        raise ToolError("unavailable", "the literature search is not installed")
    res = fn(env.ctx, args["query"], int(args.get("k") or 8))
    if asyncio.iscoroutine(res):
        res = await res
    return {"results": [r for r in (res or []) if isinstance(r, dict)][:20]}


register(Tool(
    "literature_search", "Search the literature",
    "Search the mathematical literature known to Madalean (papers, theorems, references) for a statement or a "
    "topic. Results are bibliographic data.",
    _obj({"query": {"type": "string", "minLength": 1, "maxLength": 300},
          "k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["query"]),
    _literature_search, open_world=True, rate=20, available=lambda ctx: _literature_hook() is not None))


# ---------------------------------------------------------------- sage_compute (catalogue code only, D39)
def _sage_runner(ctx):
    """async (language, code, seconds) -> {status, stdout, result, error}. A test double on the context wins."""
    custom = getattr(ctx, "mcp_sage_runner", None)
    if custom is not None:
        return custom
    from ..certs.producer import bridge_of
    br = bridge_of(ctx)
    if br is None:
        return None

    async def run(language: str, code: str, seconds: float) -> dict:
        r = await br.run(SAGE_KERNEL, language, code, timeout=seconds, max_output=200_000)
        return {"status": r.status, "stdout": r.stdout, "result": r.result, "error": r.error}
    return run


def catalogue_code(request: str, language: str) -> tuple[str, dict]:
    """The code Madalean's verified catalogue writes ENTIRELY for this request, else ToolError. Never a model's
    code, never the client's."""
    from ..research import codecat, intent as I
    it = I.analyze(request)
    if it.errors:
        raise ToolError("request_error", "the request is mathematically wrong", detail=it.errors[0])
    st = codecat.status(language)
    a = codecat.assemble(it, language, st)
    if a is None or not a.full or not a.code:
        why = a.reason if a is not None else "not recognized"
        raise ToolError("not_in_catalogue", "Madalean's catalogue does not cover this request entirely "
                        f"({why}); sage_compute runs only Madalean's own verified code", reason=why)
    return a.code, {"fr": I.summary(it, "fr"), "en": I.summary(it, "en"), "entries": list(a.entries)}


async def _sage_compute(env: ToolEnv, args: dict) -> dict:
    ctx = env.ctx
    language = args.get("language") or "sage"
    code, recognized = await asyncio.to_thread(catalogue_code, args["request"], language)
    run = _sage_runner(ctx)
    if run is None:
        raise ToolError("unavailable", "SageMath is not available")
    t0 = time.monotonic()
    r = await run(language, code, SAGE_SECONDS)
    if r.get("status") != "ok":
        raise ToolError("run_failed", f"the computation did not finish ({r.get('status')})",
                        detail=str(r.get("error") or "")[:500], code=code)
    return {"recognized": recognized, "language": language, "code": code,
            "output": (str(r.get("stdout") or "") + str(r.get("result") or ""))[:20000],
            "seconds": round(time.monotonic() - t0, 2)}


register(Tool(
    "sage_compute", "Compute with Sage",
    "Compute with SageMath from a request in words (e.g. 'factor x^4 - 1 over GF(5)', 'is 2^61-1 prime', 'divisors "
    "of 360'). Madalean recognises the request and runs ONLY the code of its own verified catalogue, in the "
    "sandboxed kernel; a request the catalogue does not cover entirely is refused (no code is accepted from you).",
    _obj({"request": {"type": "string", "minLength": 1, "maxLength": 2000},
          "language": {"type": "string", "enum": ["sage", "python"]}}, ["request"]),
    _sage_compute, read_only=True, rate=10,
    available=lambda ctx: bool(getattr(ctx.settings, "mcp_server_sage", False))))


def tool_names() -> list[str]:
    return sorted(REGISTRY)


def safe_name(name: Any) -> str:
    return name if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.-]{1,64}$", name) else "?"
