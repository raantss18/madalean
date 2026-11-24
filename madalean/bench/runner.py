"""The benchmark runner: problems through the real pipeline, headless (DECISIONS D53, docs/BENCH.md).

For each problem: the formal statement is put into a dossier exactly as the statement editor would, a `proof` job is
submitted to the application's own orchestrator (same slots, same Mathlib-first, tournament, conductor code), and the
proof the pipeline recorded is then judged AGAIN by the runner: the theorem signature must be the one given, and a
fresh strict Lean (`#print axioms`, no `sorry`, no forbidden construct, standard axioms only) must accept it. Only
that verdict counts.

The runner owns a private configuration / cache directory inside the run directory: it never writes to the user's
Madalean, never starts the local GPU model unless asked, never asks Ollama for anything, and gives the engine the
keys of FREE providers only — paid providers get no key unless `paid_budget` > 0, and then the engine's own ledger
(month cap = the budget, in the run's private ledger) plus the runner's check after each problem enforce the cap."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .. import __version__, config, leancheck
from ..brain import usage
from ..brain.api import BrainError
from ..logs import get
from ..paths import Paths
from ..runtime.lean import workspace_info
from . import sets as S

log = get("bench")
FORMAT = 1
STRATEGIES = {
    "mathlib": "Mathlib-first (library search and templates), then the Goedel loop only if a Goedel-type model is reachable (free online tier included); no tournament",
    "single": "one model (agent loop), no Mathlib-first, no tournament",
    "tournament": "the application's default: Mathlib-first, then the tournament of free online models",
    "conductor": "tournament directed by the conductor (the best free model unless a paid budget allows Claude)",
    "goedel-local": "the local Goedel-Prover GGUF on this machine's GPU (uses the GPU: never while it is lent)",
    "certificate": "as « mathlib » plus certificates (Sage computes, Lean checks, D52); no tournament",
}
FINAL = ("verified", "failed", "timeout", "statement_error", "rejected")     # rows never redone on resume
VERIFY_OWNER = "bench-verify"
SEED_STATE = ("brain-catalogue.json", "brain-leaderboard.json", "brain-rankings.json")


class BenchError(Exception):
    pass


@dataclass
class BenchConfig:
    strategy: str = "mathlib"
    workspace: str = "lean-prover49"
    model: str = ""                      # single: the model key (« provider:model_id »)
    providers: list = field(default_factory=list)   # model set: only these providers (empty = every free one)
    attempts: int = 4                    # attempts budget (prove_attempts; per model in a tournament)
    rounds: int = 1                      # tournament exploration rounds after round 0
    contestants: int = 3
    time_per_problem: float = 240.0      # seconds, wall clock, cancel after
    time_budget: float = 0.0             # seconds for the whole run (0 = none): stops scheduling, resumable
    paid_budget: float = 0.0             # USD for the whole run; 0 = no paid model can be called at all
    jobs: int = 2                        # problems in flight (the pipeline's own slots bound the real parallelism)
    compile_timeout: int = 120
    mathlib_first: bool = True
    label: str = ""

    @property
    def name(self) -> str:
        if self.label:
            return self.label
        n = self.strategy + (f":{self.model}" if self.model else "")
        if self.strategy in ("tournament", "conductor") and not self.mathlib_first:
            n += "-nomathlib"
        return n + ("+paid" if self.paid_budget > 0 else "")

    def ident(self) -> str:
        """What must not change between a run and its resume (budgets may)."""
        d = asdict(self)
        for k in ("time_budget", "jobs", "label", "paid_budget"):
            d.pop(k)
        d["paid"] = self.paid_budget > 0
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- stand-ins that keep the run inside its box
class NoModelBrain:
    """A brain with no model at all: the « mathlib » strategy (and nothing else can answer)."""
    local = None

    async def complete(self, role, messages, **kw):
        raise BrainError("no_model", "benchmark strategy without model")

    async def run_agent(self, role, system, task, tools, **kw):
        raise BrainError("no_model", "benchmark strategy without model")

    def candidates(self, role, mode="auto"):
        return []

    async def internet(self) -> bool:
        return False

    async def status(self) -> dict:
        return {"online": False, "providers": [], "local": {}}

    def update_settings(self, settings: dict) -> None:
        pass

    async def refresh(self) -> None:
        pass

    async def close(self) -> None:
        pass


class NoLocal:
    """No local GPU model: the benchmark never loads llama-server unless the strategy is « goedel-local »."""
    plan = None
    model_path = None
    models: list = []

    def model_for(self, role):
        return None

    async def ensure(self, role):
        return None

    def release(self) -> None:
        pass

    def release_owner(self, owner) -> None:
        pass

    def status(self) -> dict:
        return {"state": "stopped", "model": None, "bench": True}

    async def refresh_models(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class ReadOnlyKeys:
    """The user's key store, read through the application's own loader, filtered: a provider outside `allowed`
    has no key for this run. Never writes, never returns a key to anything but the engine."""

    def __init__(self, store, allowed: set[str]):
        self._store, self.allowed = store, set(allowed)

    def get(self, provider: str) -> str | None:
        return self._store.get(provider) if provider in self.allowed else None

    def providers(self) -> list[str]:
        return [p for p in self._store.providers() if p in self.allowed]

    def is_set(self, provider: str) -> bool:
        return provider in self.providers()

    def set(self, provider: str, key: str):
        raise BenchError("the benchmark never stores keys")

    def delete(self, provider: str):
        raise BenchError("the benchmark never deletes keys")


def allowed_providers(cfg: BenchConfig) -> set[str]:
    """Keyed providers whose key the engine may read: the free ones, the paid ones only with a paid budget."""
    from ..brain.catalogue import KEYED
    ok = {p.id for p in KEYED if not p.paid or cfg.paid_budget > 0}
    if cfg.providers:
        ok &= set(cfg.providers)
    return ok


def settings_for(cfg: BenchConfig) -> dict:
    """The application settings of a benchmark configuration (written to the run's private settings.json)."""
    paid = cfg.paid_budget > 0
    s = asdict(config.Settings())
    s.update(wizard_done=True, offline=False, workspace=cfg.workspace, check_updates=False, updates_auto=False,
             language="en", prove_attempts=max(1, cfg.attempts), compile_timeout_s=cfg.compile_timeout,
             statement_check=False, statement_notes=False, informal_proof=False, autoload_model=False,
             mathlib_first=cfg.mathlib_first, tournament_contestants=max(1, cfg.contestants),
             tournament_max_rounds=max(0, cfg.rounds), tournament_attempts_per_model=max(1, cfg.attempts),
             tournament_max_minutes=max(1, int(cfg.time_per_problem // 60) + 1),
             agent_max_seconds=int(max(30, cfg.time_per_problem)), web_search=False, gpu_share_ollama=False,
             calcul_warm=False, experiments_auto=False, agent_exec=False,
             literature=False,              # S-AX: the bench measures proofs; the literature stage is not a racer
             claude_reinforce=paid, hf_goedel=paid, conductor=False,
             claude_cap_proof_usd=min(1.0, cfg.paid_budget) if paid else 0.0,
             claude_cap_month_usd=cfg.paid_budget if paid else 0.0,
             conductor_cap_usd=min(1.0, cfg.paid_budget) if paid else 0.0)
    if cfg.strategy == "mathlib":
        s.update(mode="online", prove_strategy="goedel", mathlib_first=True, tournament_enabled=False,
                 certificates=False)                 # comparable with the 2.0.2 runs (no certificate strategy)
    elif cfg.strategy == "single":
        if not cfg.model:
            raise BenchError("strategy « single » needs --model provider:model_id")
        s.update(mode="online", prove_strategy="agent", mathlib_first=False, tournament_enabled=False,
                 prefer={"prove": cfg.model})
    elif cfg.strategy == "tournament":
        s.update(mode="online", prove_strategy="agent", tournament_enabled=True)
    elif cfg.strategy == "conductor":
        s.update(mode="online", prove_strategy="agent", tournament_enabled=True, conductor=True)
    elif cfg.strategy == "goedel-local":
        s.update(mode="local", prove_strategy="goedel", tournament_enabled=False, autoload_model=True)
    elif cfg.strategy == "certificate":
        # no model at all: Mathlib-first + « Sage computes, Lean checks » (D52)
        s.update(mode="online", prove_strategy="goedel", mathlib_first=True, tournament_enabled=False,
                 certificates=True)
    else:
        raise BenchError(f"unknown strategy: {cfg.strategy} (known: {', '.join(STRATEGIES)})")
    return s


def build_context(state_dir: Path, cfg: BenchConfig, *, keys_from: Path | None = None, seed_from: Path | None = None,
                  seed_cache: Path | None = None):
    """A private ServerContext for the run (real Lean, real engine or no model). `keys_from`: the configuration
    directory whose key store is READ (default: the user's); `seed_from` / `seed_cache`: copy the model catalogue,
    measured rankings and the Mathlib search index from there so that the run starts as the application would."""
    from ..context import ServerContext
    from ..keys import KeyStore
    from ..workspaces import all_workspaces
    os.environ.setdefault("MADALEAN_EMBEDDINGS", "0")        # never ask Ollama for embeddings
    os.environ.setdefault("MADALEAN_NO_SYNTAX_BUILD", "1")
    os.environ.setdefault("MADALEAN_NO_CALCUL_WARM", "1")
    paths = Paths(state_dir / "config", state_dir / "cache")
    paths.ensure()
    settings = settings_for(cfg)
    config.atomic_write_text(paths.settings, json.dumps(settings, indent=1, ensure_ascii=False))
    if seed_from is not None:
        for name in SEED_STATE:
            src, dst = Path(seed_from) / name, paths.config / name
            if src.is_file() and not dst.exists():
                shutil.copy2(src, dst)
    if seed_cache is not None and (Path(seed_cache) / "rag").is_dir() and not (paths.cache / "rag").exists():
        (paths.cache / "rag").mkdir(parents=True)
        for f in (Path(seed_cache) / "rag").glob(f"{cfg.workspace}-*"):
            if f.is_file():
                shutil.copy2(f, paths.cache / "rag" / f.name)
    ws = next((w for w in all_workspaces(scan_user=False) if w.key == cfg.workspace), None)
    if ws is None:
        raise BenchError(f"unknown workspace: {cfg.workspace}")
    local = None if cfg.strategy == "goedel-local" else NoLocal()
    brain = NoModelBrain() if cfg.strategy == "mathlib" else None
    ctx = ServerContext(paths, workspaces=[ws], local=local, brain=brain, legacy_dir=None,
                        jupyter_root=state_dir / "notebooks", use_keyring=False)
    store = KeyStore((Path(keys_from) if keys_from else config.CONFIG_DIR) / "keys.json")
    ctx.keys = ReadOnlyKeys(store, allowed_providers(cfg) if brain is None else set())
    return ctx


async def start_context(ctx, cfg: BenchConfig) -> None:
    await ctx.start()
    brain = ctx.brain
    if isinstance(brain, NoModelBrain):
        return
    if getattr(ctx, "brain_kind", "") == "fake" and cfg.strategy not in ("mathlib",):
        raise BenchError("the model engine could not be created (scripted fake brain): no real run possible")
    upd = getattr(brain, "update_settings", None)
    if upd is not None and getattr(ctx, "brain_kind", "") == "real":
        extra: dict = {"ollama": False}          # Ollama stays its own engine: never called by a benchmark
        if cfg.providers:
            try:
                from ..brain.catalogue import KEYED
                known = {p.id for p in KEYED} | {p.id for p in brain.store.cat.providers}
                extra["providers_disabled"] = sorted(known - set(cfg.providers))
            except Exception:  # noqa: BLE001
                log.exception("could not restrict the providers")
        upd({**ctx.settings_public(), **extra})
        for k, v in extra.items():
            if hasattr(ctx.settings, k):
                setattr(ctx.settings, k, v)


def isolate(ctx) -> None:
    """Problems must not help each other: nothing proven in the run is offered to the next problem."""
    ctx.library.relevant = lambda *a, **k: []        # type: ignore[method-assign]
    ctx.library.add_proof = lambda *a, **k: None     # type: ignore[method-assign]


# ---------------------------------------------------------------- statements that compile (reported apart)
IMPORT = re.compile(r"(?m)^\s*import\s+\S+[ \t]*\n?")


def batch_file(problems: list[S.Problem]) -> tuple[str, dict[str, tuple[int, int]]]:
    """One Lean file holding every statement in its own `section` (its `open`s and options stay local), and the
    line range of each problem."""
    imports: list[str] = []
    for p in problems:
        for m in IMPORT.finditer(p.statement):
            line = m.group(0).strip()
            if line not in imports:
                imports.append(line)
    lines = [*imports, ""]
    ranges: dict[str, tuple[int, int]] = {}
    for p in problems:
        body = IMPORT.sub("", p.statement).strip("\n").split("\n")
        start = len(lines) + 1
        lines += ["section", *body, "end", ""]
        ranges[p.id] = (start, len(lines))
    return "\n".join(lines) + "\n", ranges


async def check_statements(ctx, ws, problems: list[S.Problem], timeout_s: int = 120, batch: int = 40,
                           progress: Callable[[str], None] | None = None) -> S.Compiled:
    """Which statements does this workspace's Lean accept (with `sorry`)? Batches first (one Mathlib import for many
    statements); every problem touched by an error of its batch is checked again ALONE, and that verdict decides."""
    out = S.Compiled()
    alone: list[S.Problem] = []
    todo = []
    for p in problems:
        if not p.statement:
            out.bad[p.id] = p.note or "unreadable upstream file"
        else:
            todo.append(p)
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        if len(chunk) == 1:
            alone += chunk
            continue
        code, ranges = batch_file(chunk)
        r = await ctx.lean.check(code, ws, timeout_s + 3 * len(chunk), None, owner=_owner())
        if r.infra_error:
            raise BenchError(f"Lean workspace not usable: {r.infra_error}")
        if r.timed_out or r.cancelled or (not r.verdict.errors and not _statement_ok(r)):
            alone += chunk                                   # no usable verdict for the batch
            continue
        hit = set()
        for e in r.verdict.errors:
            owner = next((pid for pid, (a, b) in ranges.items() if a <= (e.line or 0) <= b), None)
            if owner is None:
                hit = set(ranges)
                break
            hit.add(owner)
        for p in chunk:
            if p.id in hit:
                alone.append(p)
            else:
                out.ok.append(p.id)
        if progress:
            progress(f"statements: {min(i + batch, len(todo))}/{len(todo)} read, {len(alone)} to check alone")

    async def one(p: S.Problem) -> None:
        r = await ctx.lean.check(p.statement, ws, timeout_s, None, owner=_owner())
        if r.infra_error:
            raise BenchError(f"Lean workspace not usable: {r.infra_error}")
        if _statement_ok(r):
            out.ok.append(p.id)
        else:
            e = r.verdict.errors[0] if r.verdict.errors else None
            out.bad[p.id] = ("timeout" if r.timed_out else f"line {e.line}: {e.text}" if e else
                             r.verdict.summary)[:400]
    sem = asyncio.Semaphore(2)

    async def guarded(p):
        async with sem:
            await one(p)
    await asyncio.gather(*(guarded(p) for p in alone))
    out.ok.sort()
    return out


def _statement_ok(r) -> bool:
    """Lean read the whole file and found no error: accepted, or refused only for its `sorry` (an abnormal exit
    without a positioned error has neither)."""
    v = r.verdict
    return not v.errors and not r.timed_out and not r.cancelled and not r.infra_error and bool(v.ok or v.reasons)


_owners = __import__("itertools").count(1)


def _owner() -> str:
    return f"{VERIFY_OWNER}:{next(_owners)}"


# ---------------------------------------------------------------- the bench's own verdict
def _norm(text: str) -> str:
    return " ".join(leancheck.remove_comments(text).split())


def signature(statement: str) -> tuple[str, str]:
    """(everything before the target theorem, the theorem up to `:= by`), comment-free, whitespace-normalised."""
    code = leancheck.remove_comments(statement)
    starts = [m.start(1) for m in re.finditer(r"(?:^|\s)(theorem)\s", code)]
    if not starts:
        return "", ""
    tail = code[starts[-1]:]
    m = re.match(r"theorem\s.*?:=\s*by", tail, re.S)
    return " ".join(code[:starts[-1]].split()), " ".join((m.group(0) if m else tail).split())


def pinned(statement: str, proof: str) -> bool:
    """The proof file starts with the statement's own preamble and proves the theorem exactly as it was given."""
    pre, sig = signature(statement)
    got = _norm(proof)
    return bool(sig) and got.startswith(pre) and sig in got


async def verify(ctx, ws, problem: S.Problem, proof: str, timeout_s: int) -> dict:
    """Fresh strict Lean verdict on the recorded proof (never the warm Lean, never the pipeline's own word)."""
    if not proof.strip():
        return {"ok": False, "why": "no proof", "seconds": 0.0, "axioms": None}
    if not pinned(problem.statement, proof):
        return {"ok": False, "why": "the proof file does not contain the given statement", "seconds": 0.0,
                "axioms": None}
    name = problem.theorem
    r = await ctx.lean.check(leancheck.with_axiom_probe(proof, name), ws, timeout_s, name, owner=_owner())
    v = r.verdict
    why = "" if v.ok else ("timeout" if r.timed_out else (r.infra_error or v.summary))
    return {"ok": bool(v.ok) and not r.timed_out and not r.infra_error and r.via == "fresh", "why": why,
            "seconds": round(r.seconds, 2), "axioms": v.axioms}


# ---------------------------------------------------------------- accounting
def tokens_of(job_id: str) -> dict:
    """Tokens and list-price cost of every model call made for a job (its parallel stages own « <job>#… »)."""
    tin = tout = calls = 0
    usd = 0.0
    models: list[str] = []
    with usage.TALLY._lock:                                   # noqa: SLF001 (read-only snapshot)
        for scope, v in usage.TALLY.scopes.items():
            if scope == job_id or scope.startswith(job_id + "#"):
                tin += v["tokens_in"]
                tout += v["tokens_out"]
                calls += v["calls"]
                usd += v["usd"]
                models += [m for m in v.get("models", []) if m not in models]
    return {"tokens_in": tin, "tokens_out": tout, "calls": calls, "usd": round(usd, 6), "models": models}


def ledger_usd(ctx, job_id: str | None = None) -> float:
    """Paid USD recorded by the engine's ledger (real usage × price), for one job or for the whole run."""
    rows = getattr(getattr(ctx.brain, "ledger", None), "rows", None) or []
    return round(sum(r.usd for r in rows if job_id is None or job_id in (r.scope or "")), 6)


# ---------------------------------------------------------------- one problem
async def run_problem(ctx, cfg: BenchConfig, ws, p: S.Problem, timeout_s: float, proofs_dir: Path | None) -> dict:
    t0 = time.monotonic()
    row = {"id": p.id, "set": p.set, "split": p.split, "config": cfg.name, "workspace": ws.key, "status": "failed",
           "verified": False, "attempts": 0, "wall_s": 0.0, "lean_s": 0.0, "verify_s": 0.0, "tokens_in": 0,
           "tokens_out": 0, "model_calls": 0, "cost_usd": 0.0, "model": "", "found_by": "", "models": [],
           "axioms": None, "error": "", "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    d = ctx.repo.new(problem=p.informal, workspace=ws.key, title=p.id)
    d.add_statement(p.statement, source="user")
    await ctx.repo.save(d, publish=False)
    mode = "local" if cfg.strategy == "goedel-local" else "online"
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof", "force": True}], mode=mode, gates=False,
                                  strategy="goedel" if cfg.strategy in ("mathlib", "goedel-local") else "agent")
    task = ctx.orchestrator.tasks[job.id]
    done, _ = await asyncio.wait({task}, timeout=max(1.0, timeout_s))
    timed_out = not done
    if timed_out:
        await ctx.orchestrator.cancel(job.id)
    d = ctx.repo.get(d.id) or d
    proof_attempts = [a for a in job.attempts if a.stage == "proof"]
    row["attempts"] = len(proof_attempts)
    row["lean_s"] = round(sum(a.compile_seconds or 0.0 for a in job.attempts), 2)
    tk = tokens_of(job.id)
    row.update(tokens_in=tk["tokens_in"], tokens_out=tk["tokens_out"], model_calls=tk["calls"], models=tk["models"],
               cost_usd=round(max(tk["usd"], ledger_usd(ctx, job.id)), 6))
    proof = d.proof if d.proof_is_current else ""
    if proof:
        v = await verify(ctx, ws, p, proof, cfg.compile_timeout)
        row["verify_s"] = v["seconds"]
        row["lean_s"] = round(row["lean_s"] + v["seconds"], 2)
        row["axioms"] = v["axioms"]
        ver = d.proofs[d.cur_proof]
        row["model"] = ver.model or ""
        row["found_by"] = (ver.meta or {}).get("strategy", "")
        if v["ok"]:
            row.update(status="verified", verified=True)
            row["proof_sha256"] = hashlib.sha256(proof.encode()).hexdigest()
            if proofs_dir is not None:
                proofs_dir.mkdir(parents=True, exist_ok=True)
                (proofs_dir / f"{p.id}.lean").write_text(proof, encoding="utf-8")
        else:
            row.update(status="rejected", error=("bench verdict: " + v["why"])[:300])
    elif timed_out:
        row.update(status="timeout", error=f"no proof in {timeout_s:.0f} s")
    else:
        row.update(status="failed", error=(job.error or "no_proof")[:300])
        if job.error in ("internal", "workspace", "infra"):
            row["status"] = "error"
    row["wall_s"] = round(time.monotonic() - t0, 2)
    try:
        await ctx.repo.delete(d.id)              # keep the private state small; the row and the proof file remain
    except Exception:  # noqa: BLE001
        pass
    return row


# ---------------------------------------------------------------- the run
def read_rows(path: Path) -> list[dict]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue                         # a row cut by a crash: redone
    except OSError:
        pass
    return rows


def final_rows(rows: list[dict]) -> dict[str, dict]:
    """The last row of each problem; rows that are not final (`error`, `unfinished`) are redone on resume."""
    last: dict[str, dict] = {}
    for r in rows:
        if r.get("id"):
            last[r["id"]] = r
    return last


def _git_commit() -> str:
    try:
        root = Path(__file__).resolve().parents[2]
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True,
                           timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


NO_MODEL = "mathlib (no model)"
ADAPTED = "mathlib-first (short proof written by a model)"


def winner_of(row: dict) -> str:
    """Who found a verified proof: the Mathlib search alone (no model call in the whole job), Mathlib-first with a
    short proof adapted by a model, or the model of the search."""
    k = row.get("model") or row.get("found_by") or "?"
    if k.startswith("mathlib:"):
        return ADAPTED if row.get("model_calls") or row.get("models") else NO_MODEL
    return k


def summarise(cfg: BenchConfig, set_name: str, source: dict, selection: dict, ws_info: dict, rows: dict[str, dict],
              ids: list[str], *, stop: str, started: float, elapsed: float) -> dict:
    """The summary of a run, from the rows only (so that `madalean bench report` can rebuild it)."""
    have = [rows[i] for i in ids if i in rows]
    counted = [r for r in have if r["status"] in FINAL]
    bad = [r for r in counted if r["status"] == "statement_error"]
    tried = [r for r in counted if r["status"] != "statement_error"]
    solved = [r for r in tried if r["verified"]]
    cost = round(sum(r.get("cost_usd", 0.0) for r in tried), 6)

    def med(xs):
        return round(statistics.median(xs), 1) if xs else None
    winners: dict[str, int] = {}
    for r in solved:
        winners[winner_of(r)] = winners.get(winner_of(r), 0) + 1
    models = sorted({m for r in tried for m in r.get("models", [])})
    return {
        "format": FORMAT, "set": set_name, "config": cfg.name, "strategy": cfg.strategy,
        "description": STRATEGIES.get(cfg.strategy, ""),
        "date": time.strftime("%Y-%m-%d", time.localtime(started)),
        "madalean": __version__, "commit": _git_commit(),
        "workspace": ws_info.get("workspace", cfg.workspace), "lean": ws_info.get("lean", ""),
        "mathlib": ws_info.get("mathlib", ""),
        "source": {k: source.get(k) for k in ("repo", "commit", "licence", "content_sha256", "problems", "upstream_lean")
                   if source.get(k) not in (None, "")},
        "selection": selection,
        "budgets": {"attempts": cfg.attempts, "rounds": cfg.rounds, "contestants": cfg.contestants,
                    "time_per_problem_s": cfg.time_per_problem, "time_budget_s": cfg.time_budget,
                    "paid_budget_usd": cfg.paid_budget, "jobs": cfg.jobs, "compile_timeout_s": cfg.compile_timeout},
        "selected": len(ids), "attempted": len(tried), "statement_errors": len(bad),
        "statement_error_ids": sorted(r["id"] for r in bad),
        "solved": len(solved), "solved_ids": sorted(r["id"] for r in solved),
        "solved_without_model": sum(1 for r in solved if winner_of(r) == NO_MODEL),
        "rate": round(len(solved) / len(tried), 4) if tried else None,
        "complete": len(counted) == len(ids), "stop": stop,
        "by_status": {s: sum(1 for r in have if r["status"] == s) for s in sorted({r["status"] for r in have})},
        "median_wall_s_solved": med([r["wall_s"] for r in solved]),
        "median_wall_s_all": med([r["wall_s"] for r in tried]),
        "median_lean_s_solved": med([r["lean_s"] for r in solved]),
        "wall_s_total": round(sum(r["wall_s"] for r in tried), 1), "elapsed_s": round(elapsed, 1),
        "attempts_total": sum(r.get("attempts", 0) for r in tried),
        "tokens_in": sum(r.get("tokens_in", 0) for r in tried),
        "tokens_out": sum(r.get("tokens_out", 0) for r in tried),
        "model_calls": sum(r.get("model_calls", 0) for r in tried),
        "cost_usd": cost, "cost_per_verified_usd": round(cost / len(solved), 6) if solved else None,
        "paid": cfg.paid_budget > 0, "found_by": dict(sorted(winners.items(), key=lambda kv: -kv[1])),
        "models": models,
    }


async def run_bench(cfg: BenchConfig, set_name: str, problems: list[S.Problem], run_dir: Path, *, source: dict,
                    selection: dict, context_factory: Callable | None = None, keys_from: Path | None = None,
                    seed_from: Path | None = None, seed_cache: Path | None = None,
                    progress: Callable[[str], None] | None = None) -> dict:
    """Run (or resume) a benchmark. Writes `<run_dir>/rows.jsonl` (one row per problem, appended as they end),
    `<run_dir>/summary.json`, `<run_dir>/run.json` and the verified proofs under `<run_dir>/proofs/`."""
    say = progress or (lambda s: None)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    ids = [p.id for p in problems]
    ident = {"format": FORMAT, "set": set_name, "config": cfg.ident(), "ids": hashlib.sha256(
        "\n".join(ids).encode()).hexdigest()[:16], "source": source.get("content_sha256", "")}
    run_file = run_dir / "run.json"
    if run_file.exists():
        old = json.loads(run_file.read_text(encoding="utf-8"))
        if old.get("ident") != ident:
            raise BenchError(f"{run_dir} holds another run (set, configuration or problems differ): use a new "
                             "directory")
    config.atomic_write_text(run_file, json.dumps({"ident": ident, "config": asdict(cfg), "set": set_name,
                                                   "selection": selection, "source": source}, indent=1))
    rows_file = run_dir / "rows.jsonl"
    rows = final_rows(read_rows(rows_file))
    started, t0 = time.time(), time.monotonic()
    deadline = t0 + cfg.time_budget if cfg.time_budget > 0 else None
    ctx = context_factory(run_dir / "state", cfg) if context_factory else build_context(
        run_dir / "state", cfg, keys_from=keys_from, seed_from=seed_from, seed_cache=seed_cache)
    stop = ""
    ws_info: dict = {}
    lock = asyncio.Lock()

    async def write(row: dict) -> None:
        async with lock:
            rows[row["id"]] = row
            with rows_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())

    try:
        if context_factory is None:
            await start_context(ctx, cfg)
        else:
            await ctx.start()
        isolate(ctx)
        ws = ctx.workspace(cfg.workspace) or ctx.workspace()
        if ws is None or await ctx.lean.problems(ws):
            raise BenchError(f"workspace {cfg.workspace} is not ready")
        ws_info = workspace_info(ws) if ws.path.exists() else {"workspace": ws.key, "lean": ws.toolchain.split(":")[-1]}
        todo = [p for p in problems if rows.get(p.id, {}).get("status") not in FINAL]
        say(f"{set_name} × {cfg.name} on {ws.key}: {len(problems)} problems, {len(problems) - len(todo)} already done")
        # 1. statements this Lean does not accept are reported apart, never counted as failures
        comp_file = run_dir / "statements.json"
        try:
            known = json.loads(comp_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            known = {"ok": [], "bad": {}}
        unknown = [p for p in todo if p.id not in known["ok"] and p.id not in known["bad"]]
        if unknown:
            c = await check_statements(ctx, ws, unknown, cfg.compile_timeout, progress=say)
            known["ok"] = sorted(set(known["ok"]) | set(c.ok))
            known["bad"].update(c.bad)
            config.atomic_write_text(comp_file, json.dumps(known, indent=1, ensure_ascii=False))
        for p in todo:
            if p.id in known["bad"]:
                await write({"id": p.id, "set": p.set, "split": p.split, "config": cfg.name, "workspace": ws.key,
                             "status": "statement_error", "verified": False, "error": known["bad"][p.id],
                             "attempts": 0, "wall_s": 0.0, "lean_s": 0.0, "tokens_in": 0, "tokens_out": 0,
                             "cost_usd": 0.0, "models": [], "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        # scheduled in a seeded shuffled order: a run cut by its time budget has attempted an unbiased sub-sample
        # (sorted ids put a whole family of problems first), and the order is the same at every run
        queue = [p for p in problems if p.id in known["ok"]]
        random.Random(selection.get("seed") or 0).shuffle(queue)
        queue = [p for p in queue if rows.get(p.id, {}).get("status") not in FINAL]
        say(f"statements accepted by Lean: {len(known['ok'])}; not compiling here: {len(known['bad'])}")
        it = iter(queue)
        halt = asyncio.Event()

        async def worker() -> None:
            nonlocal stop
            while not halt.is_set():
                if deadline is not None and time.monotonic() >= deadline:
                    stop = stop or "time_budget"
                    return
                spent = max(ledger_usd(ctx), sum(r.get("cost_usd", 0.0) for r in rows.values()))
                if cfg.paid_budget > 0 and spent >= cfg.paid_budget - 1e-9:
                    stop = stop or "paid_budget"
                    return
                p = next(it, None)
                if p is None:
                    return
                limit = cfg.time_per_problem
                cut = False
                if deadline is not None and deadline - time.monotonic() < limit:
                    limit, cut = max(1.0, deadline - time.monotonic()), True
                try:
                    row = await run_problem(ctx, cfg, ws, p, limit, run_dir / "proofs")
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 (one broken problem never ends the run)
                    log.exception("problem %s crashed", p.id)
                    row = {"id": p.id, "set": p.set, "split": p.split, "config": cfg.name, "workspace": ws.key,
                           "status": "error", "verified": False, "error": f"{type(e).__name__}: {e}"[:300],
                           "attempts": 0, "wall_s": 0.0, "lean_s": 0.0, "tokens_in": 0, "tokens_out": 0,
                           "cost_usd": 0.0, "models": [], "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
                if cut and row["status"] == "timeout":
                    row["status"] = "unfinished"           # cut by the run's budget, not by its own: redone on resume
                    stop = stop or "time_budget"
                if cfg.paid_budget <= 0 and (row.get("cost_usd", 0.0) > 0 or ledger_usd(ctx) > 0):
                    row["error"] = (row.get("error", "") + " | paid call without a paid budget").strip(" |")
                    stop = "paid_call_without_budget"      # must never happen: stop everything, say it loudly
                    halt.set()
                await write(row)
                say(f"{row['id']}: {row['status']}"
                    + (f" by {row.get('model') or row.get('found_by')}" if row["verified"] else "")
                    + f" ({row['wall_s']:.0f} s, {row.get('attempts', 0)} attempts"
                    + (f", {row['cost_usd']:.4f} $" if row.get("cost_usd") else "") + ")")

        await asyncio.gather(*(worker() for _ in range(max(1, cfg.jobs))))
    finally:
        try:
            await ctx.stop()
        except Exception:  # noqa: BLE001
            log.exception("context stop failed")
    summary = summarise(cfg, set_name, source, selection, ws_info, rows, ids, stop=stop or "done", started=started,
                        elapsed=time.monotonic() - t0)
    config.atomic_write_text(run_dir / "summary.json", json.dumps(summary, indent=1, ensure_ascii=False))
    return summary
