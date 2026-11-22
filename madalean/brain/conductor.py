"""The conductor (« chef d'orchestre », session S-AI, DECISIONS D41).

For each request a conductor model reads the problem, writes a structured plan (tasks, dependencies, a model per
task chosen among candidates the CODE ranks), and is called again only when something fails (Lean rejects a
statement or no proof is found: it corrects) and for the final coherence check (statement ↔ proof ↔ explanation).
Madalean executes everything else with its existing stages. Lean stays the only judge of a proof.

Who directs is decided per decision, from data, never fixed:

- Claude (Haiku 5.5 / Sonnet 5.5 / Opus 5.5) when its key is set and the request's budget allows it. Each model gets
  a utility = min(quality, need) + 0.05·(quality − need)⁺ − cost/room − latency penalty, where *quality* is the
  Bayesian posterior of its measured success on that kind of decision (prior per tier, 4 virtual decisions),
  *need* depends on the estimated difficulty (easy 0.5, medium 0.8, hard 1.0), *cost* is the estimated cost of the
  call (prompt tokens, cache reads when the stable prefix is warm, expected output) and *room* what the request's
  and the month's caps leave. A correction that Sonnet failed twice goes to Opus first.
- otherwise (no key, provider down, 429, timeout, refusal, cap declined) the next best: the best FREE models for
  reasoning by measured quality, reliability and latency; and when none is capable, no conductor at all — the
  pipeline runs exactly as before.

Outside a job (S-AN, D46, `research/conductorfix.py`): `codefix` corrects a Calcul cell that failed when run and
`texfix` proposes one change for a failed article compilation; their success is the run / the recompilation.

Calls go through `MadaleanBrain.call_model` (one pinned model, raw stop reason, usage with cache reads, the spend
ledger and its caps). Structured output: `output_config.format` (JSON schema) on Claude; the JSON is validated
here anyway (free models answer in text)."""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import spend, toolcards
from ._util import fix_mojibake_deep, looks_mojibake
from ._util import now, read_json, write_private
from .providers.base import ProviderError

CLAUDE = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
TIER = {"claude-haiku-5-5": "haiku", "claude-sonnet-5-5": "sonnet", "claude-opus-5-5": "opus"}
NAMES = {"claude-haiku-5-5": "Claude Haiku", "claude-sonnet-5-5": "Claude Sonnet", "claude-opus-5-5": "Claude Opus"}
DECISIONS = ("plan", "fix", "final", "codefix", "texfix")     # codefix / texfix: Calcul and article (S-AN, D46)
# prior success of each tier per decision (before anything is measured here), worth PRIOR_N decisions
PRIOR = {"plan": {"haiku": 0.55, "sonnet": 0.80, "opus": 0.90},
         "fix": {"haiku": 0.40, "sonnet": 0.75, "opus": 0.88},
         "final": {"haiku": 0.70, "sonnet": 0.85, "opus": 0.90},
         "codefix": {"haiku": 0.55, "sonnet": 0.82, "opus": 0.88},
         "texfix": {"haiku": 0.60, "sonnet": 0.82, "opus": 0.88}}
PRIOR_N = 4.0
NEED = {"easy": 0.5, "medium": 0.8, "hard": 1.0}
# expected seconds per decision before anything is measured here (real API, 2026-11-22: plan Haiku 7.5 s, Sonnet
# 8.1–10.4 s, Opus 9.7 s; correction Sonnet 2.9 s; final check Haiku 3.3–4.1 s, Sonnet 3.1–4.0 s; others estimated)
LAT_PRIOR = {"plan": {"haiku": 7.5, "sonnet": 9.5, "opus": 10.0},
             "fix": {"haiku": 3.0, "sonnet": 3.5, "opus": 8.0},
             "final": {"haiku": 3.7, "sonnet": 3.6, "opus": 5.0},
             "codefix": {"haiku": 2.5, "sonnet": 3.5, "opus": 7.0},       # estimated (fakes only so far)
             "texfix": {"haiku": 2.5, "sonnet": 3.5, "opus": 7.0}}
OUT_TOKENS = {"plan": 900, "fix": 2500, "final": 450, "codefix": 700, "texfix": 500}   # expected output (cost)
MAX_TOKENS = {"plan": 4000, "fix": 12000, "final": 2000, "codefix": 4000, "texfix": 3000}   # ceiling sent to the API
EFFORT = {"plan": {"easy": "low", "medium": "low", "hard": "medium"}, "fix": "medium", "final": "low",
          "codefix": "low", "texfix": "low"}
FIXES = ("fix", "codefix", "texfix")     # corrections: success = the checker's verdict (Lean, a run, a recompilation)
CACHE_TTL = 280.0                 # a stable prefix used less than this ago is assumed warm (Anthropic: 5 min)
FREE_MIN_REASONING = 0.6          # a free model directs only if it reasons at least this well (catalogue scale)
CAP_STEP = 0.50                   # « continuer avec Claude (+0,50 $) ? »
TASK_KINDS = ("understand", "formalize", "check", "mathlib", "prove", "lemmas", "explain", "informal", "notes",
              "compute", "latex")
KIND_ROLE = {"understand": "understand", "formalize": "formalize", "check": "understand", "mathlib": "prove",
             "prove": "prove", "explain": "explain", "informal": "explain", "notes": "explain"}
KIND_STAGE = {"understand": "understand", "formalize": "statement", "check": "verify", "mathlib": "mathlib",
              "prove": "proof", "explain": "explanation", "informal": "informal", "notes": "notes"}
ADVISORY = ("lemmas", "compute", "latex")       # shown in the plan, never run by themselves (D31: splits are the user's)
# rough tokens (in, out) of one worker task: the cost a paid assignment would have
TASK_TOKENS = {"understand": (1500, 600), "formalize": (9000, 4500), "explain": (4500, 2500)}
MAX_TASKS = 10
PAID_WORKER_PENALTY = 0.10        # a paid worker is chosen only when clearly better than the best free one

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["difficulty", "summary", "tasks"],
    "properties": {
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "summary": {"type": "string"},
        "tasks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "kind", "goal", "depends_on", "model", "why", "hint"],
            "properties": {"id": {"type": "string"}, "kind": {"type": "string", "enum": list(TASK_KINDS)},
                           "goal": {"type": "string"}, "depends_on": {"type": "array", "items": {"type": "string"}},
                           "model": {"type": "string"}, "why": {"type": "string"}, "hint": {"type": "string"}}}}}}
FIX_STATEMENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["statement", "what"],
                        "properties": {"statement": {"type": "string"}, "what": {"type": "string"}}}
FIX_PROOF_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["proof", "what"],
                    "properties": {"proof": {"type": "string"}, "what": {"type": "string"}}}
FIX_CODE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code", "what"],
                   "properties": {"code": {"type": "string"}, "what": {"type": "string"}}}
FIX_LATEX_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["find", "replace", "what"],
                    "properties": {"find": {"type": "string"}, "replace": {"type": "string"},
                                   "what": {"type": "string"}}}
FINAL_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["consistent", "issues", "summary"],
    "properties": {"consistent": {"type": "boolean"}, "summary": {"type": "string"},
                   "issues": {"type": "array", "items": {
                       "type": "object", "additionalProperties": False, "required": ["part", "text"],
                       "properties": {"part": {"type": "string", "enum": ["statement", "proof", "explanation"]},
                                      "text": {"type": "string"}}}}}}

ROLE_TEXT = {
    "plan": """You are the conductor of Madalean, a French mathematics assistant whose proofs are checked by Lean 4
and Mathlib. You receive one request and decide how Madalean handles it; you do not solve it yourself.

Madalean's stages (they already run in parallel where possible): understand (rewrite the problem precisely),
formalize (Lean statement; Lean must accept it), check (fidelity of the statement + Lean probes of its negation),
mathlib (look for the theorem in Mathlib), prove (proof search by prover models, a tournament; Lean decides),
explain and informal (explanation and natural-language proof for the user), notes (guided reading of the statement).
Advisory kinds, never run automatically: lemmas (suggest a split into lemmas — the user decides), compute (a Sage
computation the user may run in Calcul), latex (article text).

Answer with the plan as JSON:
- difficulty: easy | medium | hard for a Lean proof;
- summary: one short French sentence for the user (what will be done), accents written as plain characters (é, è,
  «, ≠), never escaped or re-encoded;
- tasks: 3 to 8 tasks; id short (t1, t2…); depends_on lists ids that must finish first (tasks without a common
  dependency run in parallel); model: one key from the candidates given for that kind, or "auto" (Madalean's
  ranking); why: a few words; hint: what the model of that task should know (exact Mathlib names to try,
  hypotheses not to forget, proof strategy) — empty when nothing useful, never a whole proof.
Prefer the first candidate unless you have a reason; a paid model only when its task needs it.""",
    "fix_statement": """You are the conductor of Madalean. Lean 4 + Mathlib rejected the translation of a problem into
a Lean statement. Read the problem, the rejected attempts and Lean's errors, and write ONE corrected Lean statement:
a single `theorem NAME … := by sorry` with the given name, faithful to the problem (every hypothesis kept, nothing
trivial), using real Mathlib names. Answer as JSON: statement (the Lean code), what (one short French sentence for
the user: what was wrong and what you changed).""",
    "fix_proof": """You are the conductor of Madalean. Prover models failed to prove a Lean 4 + Mathlib theorem. Read the
statement, their closest attempts and Lean's errors, and write ONE complete corrected proof: the theorem exactly as
given (same name, same statement) followed by its proof, plus auxiliary lemmas before it if needed. Fix the errors
Lean reported; prefer short robust tactics. Answer as JSON: proof (the Lean code), what (one short French sentence
for the user: the error and the fix).""",
    "fix_sage": """You are the conductor of Madalean. A SageMath cell of the user's notebook failed when run in the
installed Sage. Read the user's request, the code, the error and the names already defined, and write ONE corrected
cell that does what the request asks: keep the canonical constructions given (same names, same lines), keep what
worked, fix only what the error shows; every library loaded in the cell; end with the result. Answer as JSON: code
(the whole corrected cell, no Markdown fence), what (one short French sentence for the user: the error and the fix).""",
    "fix_python": """You are the conductor of Madalean. A Python 3 cell of the user's notebook failed when run. Read the
user's request, the code, the error and the names already defined, and write ONE corrected cell that does what the
request asks: keep the canonical constructions given (same names, same lines), keep what worked, fix only what the
error shows; every import explicit. Answer as JSON: code (the whole corrected cell, no Markdown fence), what (one
short French sentence for the user: the error and the fix).""",
    "fix_latex": """You are the conductor of Madalean. The user's LaTeX article failed to compile. Read the error and
the excerpt of the file around it, and propose ONE minimal local change that makes it compile without changing the
meaning: find = an exact substring of the excerpt (copied character for character, without the line numbers, long
enough to be unique), replace = its corrected text. Never add packages, \\input, file or shell commands, never define
macros. Answer as JSON: find, replace, what (one short French sentence for the user: the error and the fix).""",
    "final":"""You are the conductor of Madalean. Check the final coherence of a finished request: does the Lean
statement say what the user's problem says, does the explanation explain THAT statement and match the Lean proof?
Lean has already verified the proof (when it says so); do not re-judge Lean. Report only real mismatches (missing or
extra hypothesis, wrong quantifier, the explanation proving something else or claiming more). Answer as JSON:
consistent (bool), issues ([{part: statement|proof|explanation, text: short French sentence}]), summary (one short
French sentence).""",
}


# ---------------------------------------------------------------- measurements of the conductors
@dataclass
class Stat:
    n: float = 0.0
    ok: float = 0.0
    sec: float = 0.0
    usd: float = 0.0
    t: float = 0.0
    total: int = 0


class Stats:
    """Per model × decision, decayed (half-life 30 days): decisions made, successful ones (a plan that validated, a
    correction Lean accepted, a final check delivered), wall seconds, USD. `<config>/brain-conductor.json` (0600)."""
    HALF_LIFE = 30 * 86400.0

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        raw = read_json(self.path) or {}
        self.rows: dict[str, Stat] = {}
        for k, v in (raw.get("rows") or {}).items() if isinstance(raw, dict) else []:
            try:
                self.rows[k] = Stat(**{f: v[f] for f in Stat.__dataclass_fields__ if f in v})
            except (TypeError, KeyError):
                pass

    def _get(self, key: str) -> Stat | None:
        s = self.rows.get(key)
        if s is None:
            return None
        f = 0.5 ** (max(0.0, now() - s.t) / self.HALF_LIFE) if s.t else 1.0
        return Stat(s.n * f, s.ok * f, s.sec * f, s.usd * f, s.t, s.total)

    def record(self, model: str, decision: str, ok: bool, seconds: float = 0.0, usd: float = 0.0) -> None:
        k = f"{model}|{decision}"
        with self._lock:
            s = self._get(k) or Stat()
            s.n += 1
            s.ok += 1.0 if ok else 0.0
            s.sec += max(0.0, seconds)
            s.usd += max(0.0, usd)
            s.t = now()
            s.total += 1
            self.rows[k] = s
            try:
                write_private(self.path, json.dumps({"rows": {k: asdict(v) for k, v in self.rows.items()}}))
            except OSError:
                pass

    def quality(self, model: str, decision: str, prior: float) -> float:
        s = self._get(f"{model}|{decision}")
        if s is None:
            return prior
        return (s.ok + prior * PRIOR_N) / (s.n + PRIOR_N)

    def seconds(self, model: str, decision: str) -> float | None:
        s = self._get(f"{model}|{decision}")
        return s.sec / s.n if s and s.n > 0.3 else None

    def table(self) -> list[dict]:
        out = []
        for k in self.rows:
            s = self._get(k)
            m, d = k.split("|", 1)
            out.append({"model": m, "decision": d, "n": s.total, "ok_rate": round(s.ok / s.n, 3) if s.n else None,
                        "mean_seconds": round(s.sec / s.n, 1) if s.n else None,
                        "mean_usd": round(s.usd / s.n, 5) if s.n else None})
        return sorted(out, key=lambda r: (r["decision"], r["model"]))


# ---------------------------------------------------------------- choices
@dataclass
class Choice:
    key: str
    name: str
    tier: str                    # haiku | sonnet | opus | free
    paid: bool
    est_usd: float = 0.0
    utility: float = 0.0
    why: str = ""


@dataclass
class Reply:
    data: dict
    key: str
    name: str
    tier: str
    usd: float = 0.0
    seconds: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read: int = 0
    cache_write: int = 0
    tried: list[str] = field(default_factory=list)


class NoConductor(Exception):
    def __init__(self, tried: list[str]):
        super().__init__("; ".join(tried) or "no conductor available")
        self.tried = tried


def difficulty_of(text: str, statement: str = "", failures: int = 0) -> str:
    """Rough difficulty of a request before any plan: length, quantifiers, domain, earlier failures."""
    from .leaderboard import domain_of
    t = f"{text}\n{statement}"
    s = 0.0
    if len(text) > 400:
        s += 1
    q = len(re.findall(r"∀|∃|pour tout|quel que soit|il existe|for all|there exists", t, re.I))
    s += 1 if q >= 3 else 0.5 if q >= 2 else 0
    if domain_of(t) in ("analysis", "linear_algebra", "geometry"):
        s += 1
    if re.search(r"si et seulement si|⇔|↔|iff\b|équivalen|unique|infinit", t, re.I):
        s += 0.5
    if re.search(r"\b(calcule|simple|trivial|vérifie que|compute)\b", t, re.I):
        s -= 1
    s += min(2, failures)
    return "easy" if s < 1 else "medium" if s < 2.5 else "hard"


def parse_json(text: str) -> dict | None:
    """The JSON object of an answer: plain, fenced, or the first balanced {...} in the text."""
    t = (text or "").strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    for cand in ([m.group(1)] if m else []) + [t]:
        try:
            v = json.loads(cand)
            if isinstance(v, dict):
                return v
        except ValueError:
            pass
    start = t.find("{")
    while start >= 0:
        depth, ins, esc = 0, False, False
        for i in range(start, len(t)):
            c = t[i]
            if ins:
                esc = (c == "\\") and not esc
                if c == '"' and not esc:
                    ins = False
                continue
            if c == '"':
                ins = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(t[start:i + 1])
                        if isinstance(v, dict):
                            return v
                    except ValueError:
                        pass
                    break
        start = t.find("{", start + 1)
    return None


@dataclass
class PlanTask:
    id: str
    kind: str
    goal: str
    depends_on: list[str]
    model: str                  # model key, "" = Madalean's ranking
    why: str
    hint: str
    wave: int = 0
    advisory: bool = False


def validate_plan(raw: dict | None, candidates: dict[str, list[str]]) -> tuple[str, str, list[PlanTask]] | None:
    """(difficulty, summary, tasks) — unknown kinds dropped, ids made unique, unknown dependencies and cycles removed,
    a model outside the candidates of its role replaced by "" (the ranking decides), ≤ MAX_TASKS tasks, each with
    its parallel wave (0 = can start at once). None when nothing usable is left."""
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        return None
    diff = raw.get("difficulty") if raw.get("difficulty") in NEED else "medium"
    summary = str(raw.get("summary") or "")[:300]
    if looks_mojibake(summary):                # not repairable: the UI builds the line from the steps instead
        summary = ""
    tasks: list[PlanTask] = []
    ids: set[str] = set()
    for i, t in enumerate(raw["tasks"][: MAX_TASKS * 2]):
        if not isinstance(t, dict) or t.get("kind") not in TASK_KINDS:
            continue
        tid = re.sub(r"[^\w-]", "", str(t.get("id") or ""))[:16] or f"t{i + 1}"
        while tid in ids:
            tid += "b"
        ids.add(tid)
        role = KIND_ROLE.get(t["kind"], "")
        model = str(t.get("model") or "")
        if model not in candidates.get(role, []):
            model = ""
        deps = [str(x) for x in (t.get("depends_on") or []) if isinstance(x, (str, int))]
        tasks.append(PlanTask(tid, t["kind"], str(t.get("goal") or "")[:300], deps, model,
                              str(t.get("why") or "")[:200], str(t.get("hint") or "")[:600],
                              advisory=t["kind"] in ADVISORY))
        if len(tasks) >= MAX_TASKS:
            break
    if not tasks:
        return None
    known = {t.id for t in tasks}
    for t in tasks:
        t.depends_on = [d for d in dict.fromkeys(t.depends_on) if d in known and d != t.id]
    # waves (Kahn); edges closing a cycle are dropped
    by = {t.id: t for t in tasks}
    wave: dict[str, int] = {}
    visiting: set[str] = set()

    def w(tid: str) -> int:
        if tid in wave:
            return wave[tid]
        visiting.add(tid)
        t = by[tid]
        deps = []
        for d in t.depends_on:
            if d in visiting:
                continue                       # cycle: this edge is dropped
            deps.append(d)
        t.depends_on = deps
        wave[tid] = 1 + max((w(d) for d in deps), default=-1)
        visiting.discard(tid)
        return wave[tid]
    for t in tasks:
        t.wave = w(t.id)
    return diff, summary, tasks


# ---------------------------------------------------------------- the conductor
class Conductor:
    """One per brain. Stateless per request (the pipeline hook keeps the request's state)."""

    def __init__(self, brain):
        self.brain = brain
        self.stats = Stats(Path(brain.config_dir) / "brain-conductor.json")
        self._warm: dict[tuple[str, str], float] = {}     # (model key, stable hash) → last use (monotonic)

    # ------------------------------------------------------------ availability
    @staticmethod
    def usable(brain) -> bool:
        return all(hasattr(brain, a) for a in ("call_model", "model_of", "ledger", "states", "_view", "settings"))

    def enabled(self, mode: str) -> bool:
        b = self.brain
        return bool(b.settings.get("conductor", True)) and b.effective_mode(mode) != "local"

    def caps(self) -> tuple[float, float]:
        return self.brain.caps()

    def room(self, scope: str | None) -> float:
        cp, cm = self.caps()
        return self.brain.ledger.room(scope, cp, cm)

    def month_room(self) -> float:
        return self.brain.ledger.month_room(self.caps()[1])

    def claude_models(self, mode: str) -> list[str]:
        """Claude model ids usable now (key set, provider on, not paused, provider reachable)."""
        b = self.brain
        if b.effective_mode(mode) == "local" or b.key("anthropic") is None:
            return []
        if b.down.get("anthropic", 0) > time.monotonic():
            return []
        out = []
        for mid in CLAUDE:
            k = f"anthropic:{mid}"
            if b.model_of(k) is not None and not b.states.pause_of(k):
                out.append(mid)
        return out

    # ------------------------------------------------------------ cost / utility
    def estimate(self, model_id: str, decision: str, prompt_tokens: int, stable_tokens: int, stable_hash: str) -> float:
        p = spend.price_of(model_id, prompt_tokens)
        if p is None:
            return 0.0
        warm = time.monotonic() - self._warm.get((f"anthropic:{model_id}", stable_hash), -1e9) < CACHE_TTL
        cached = stable_tokens if warm else 0
        fresh = max(0, prompt_tokens - cached)
        write = 0 if warm else stable_tokens
        fresh -= write
        out = OUT_TOKENS[decision] * (2 if decision == "fix" else 1)     # thinking at medium effort
        return (max(0, fresh) * p[0] + cached * p[2] + write * p[3] + out * p[1]) / 1e6

    def choose(self, decision: str, difficulty: str, *, mode: str, scope: str | None, prompt_tokens: int,
               stable_tokens: int = 0, stable_hash: str = "", attempt: int = 0, claude: bool = True) -> list[Choice]:
        """Claude models ordered by utility (affordable or not: the caller asks the user before an unaffordable one),
        then the free conductors. A correction Sonnet failed twice (attempt ≥ 2) goes to Opus first."""
        out: list[Choice] = []
        room = max(self.room(scope), 1e-6)
        need = 1.0 if decision == "fix" else NEED.get(difficulty, 0.8)
        if claude:
            for mid in self.claude_models(mode):
                tier = TIER[mid]
                key = f"anthropic:{mid}"
                q = self.stats.quality(key, decision, PRIOR[decision][tier])
                est = self.estimate(mid, decision, prompt_tokens, stable_tokens, stable_hash)
                measured = self.stats.seconds(key, decision)
                lat = measured if measured is not None else LAT_PRIOR[decision][tier]
                lat_pen = 0.004 * min(lat, 60.0)
                u = min(q, need) + 0.02 * max(0.0, q - need) - est / room - lat_pen
                why = (f"quality {q:.2f} (need {need:.2f}), ≈{est:.4f} $ of {room:.2f} $ left, "
                       f"{lat:.1f} s {'measured' if measured is not None else 'expected'}")
                out.append(Choice(key, NAMES[mid], tier, True, est, u, why))
            out.sort(key=lambda c: c.utility, reverse=True)
            if decision in FIXES and attempt >= 2:
                out.sort(key=lambda c: c.tier != "opus")          # stable: Opus first, the rest by utility
            elif decision in FIXES:
                out = [c for c in out if c.tier != "opus"] + [c for c in out if c.tier == "opus"]
        return out + self.free_conductors(mode)

    def free_conductors(self, mode: str, k: int = 2) -> list[Choice]:
        """The best free online models for reasoning: catalogue quality, measured reliability and latency."""
        from .catalogue import unfit_reason
        from .router import latency_bonus
        b = self.brain
        if b.effective_mode(mode) == "local":
            return []
        scored = []
        for m in b._view().models:                                         # noqa: SLF001
            if m.local or m.paid or m.provider == "huggingface" or b.states.pause_of(m.key):
                continue
            if b.down.get(m.provider, 0) > time.monotonic() or unfit_reason(m):
                continue
            q = 0.7 * m.score("reasoning") + 0.3 * m.score("math")
            if q < FREE_MIN_REASONING:
                continue
            rel = b.states.reliability(m.key)
            lb, _ = latency_bonus(b.states.latency(m.key), m)
            sq = self.stats.quality(m.key, "plan", q)
            u = 0.6 * sq + 0.25 * rel + 0.5 * lb
            scored.append(Choice(m.key, m.name or m.model_id, "free", False, 0.0, u,
                                 f"reasoning {q:.2f}, reliability {rel:.2f}" + (f", latency {lb:+.2f}" if lb else "")))
        scored.sort(key=lambda c: c.utility, reverse=True)
        return scored[:k]

    # ------------------------------------------------------------ worker candidates (assignment per task)
    def worker_candidates(self, role: str, mode: str, *, domain: str | None, scope: str | None,
                          claude: bool = True, k: int = 3) -> list[dict]:
        """Models for one task, best first: the router's score (quality for the role, measured reliability, the
        leaderboard for this domain, public signals) minus the measured latency and, for a paid model, its
        estimated cost relative to what the request may still spend (never more than half of it)."""
        from ..i18n import language
        from .router import rank
        b = self.brain
        if role not in ROLE_ROLES:
            return []
        ranked = rank(b._view(), b.states, role, paid_first=True, allow_local=False,             # noqa: SLF001
                      leaderboard=b.leaderboard, domain=domain, lang=language(), signals=b.rankings)
        room = max(self.room(scope), 1e-6)
        out = []
        for c in ranked[:16]:
            m = c.model
            if m.provider == "huggingface" or b.down.get(m.provider, 0) > time.monotonic():
                continue
            s = c.score - (1.0 if m.paid else 0.0)
            est = 0.0
            if m.paid:
                if m.provider != "anthropic" or not claude or role == "prove":
                    continue                          # paid provers: only the tournament's final round (S-M)
                tin, tout = TASK_TOKENS.get(role, (3000, 1500))
                est = spend.estimate(m.model_id, tin, tout) or 0.0
                if est > 0.5 * room:
                    continue
            lat = b.states.latency(m.key)
            lat_pen = 0.01 * min(lat, 30.0) if lat is not None else 0.03
            # economy first: a paid worker must beat the free ones by a clear margin (fixed + cost-relative penalty)
            u = s - lat_pen - ((PAID_WORKER_PENALTY + 3.0 * est / room) if m.paid else 0.0)
            out.append({"key": m.key, "name": m.name or m.model_id, "paid": m.paid, "utility": round(u, 3),
                        "latency": round(lat, 1) if lat is not None else None, "est_usd": round(est, 4),
                        "why": c.why})
        out.sort(key=lambda r: r["utility"], reverse=True)
        return out[:k]

    # ------------------------------------------------------------ one decision
    async def ask(self, decision: str, *, kind: str, user: str, schema: dict, difficulty: str, mode: str,
                  scope: str | None, features: frozenset = frozenset(), ws=None, attempt: int = 0,
                  claude: bool = True, deadline: float | None = None,
                  on_cap: Callable[[float], Awaitable[bool]] | None = None,
                  on_try: Callable[[Choice], None] | None = None) -> Reply:
        """Run one decision on the best conductor, falling back along the chain on 429, timeout, refusal, error,
        invalid JSON. `kind`: the prompt (plan | fix_statement | fix_proof | final). `on_cap(est)` is awaited before
        a Claude call that the request's cap cannot pay; it returns True when the cap was raised (the user said
        yes), False to go on without Claude."""
        comp = toolcards.compact(kind, features, ws, intent_text=user)     # S-AM: + verified Lean constructions
        stable = ROLE_TEXT[kind] + ("\n\n" + comp.stable if comp.stable else "")
        request = comp.request
        user_full = user
        prompt_tokens = toolcards.estimate_tokens(stable + request + user_full) + 8
        stable_tokens = toolcards.estimate_tokens(stable)
        stable_hash = comp.stable_hash + str(hash(ROLE_TEXT[kind]) & 0xffff)
        chain = self.choose(decision, difficulty, mode=mode, scope=scope, prompt_tokens=prompt_tokens,
                            stable_tokens=stable_tokens, stable_hash=stable_hash, attempt=attempt, claude=claude)
        tried: list[str] = []
        asked = False
        for ch in chain:
            left = (deadline - time.monotonic()) if deadline else 120.0
            if left < 3:
                tried.append(f"{ch.key}: no time left")
                break
            if ch.paid and not claude:
                continue
            if ch.paid and ch.est_usd > self.room(scope):
                if on_cap is None or asked:
                    tried.append(f"{ch.key}: cap ({ch.est_usd:.3f} $ > {self.room(scope):.3f} $)")
                    continue
                asked = True
                if not await on_cap(ch.est_usd):
                    claude = False
                    tried.append(f"{ch.key}: cap declined")
                    continue
                if ch.est_usd > self.room(scope):
                    tried.append(f"{ch.key}: cap")
                    continue
            if on_try is not None:
                on_try(ch)
            msgs = [{"role": "system", "content": stable, "stable": True}]
            if request:
                msgs.append({"role": "system", "content": request})
            if ch.paid:
                msgs.append({"role": "user", "content": user_full})
                extra = {"format": {"type": "json_schema", "schema": schema}, "thinking_off": decision != "fix",
                         "effort_force": EFFORT[decision] if isinstance(EFFORT[decision], str)
                         else EFFORT[decision].get(difficulty, "low")}
            else:
                msgs.append({"role": "user", "content": user_full + "\n\nAnswer with ONE JSON object only (no text "
                             "around it), with exactly these fields: " + json.dumps(schema["properties"])[:1500]})
                extra = {}
            t0 = time.monotonic()
            try:
                res, secs, _first = await asyncio.wait_for(
                    self.brain.call_model(ch.key, "assistant", msgs, mode=mode, max_tokens=MAX_TOKENS[decision],
                                          extra=extra), timeout=min(left, 180.0 if decision == "fix" else 90.0))
            except asyncio.TimeoutError:
                tried.append(f"{ch.key}: timeout")
                self.stats.record(ch.key, decision, False, time.monotonic() - t0)
                continue
            except ProviderError as e:
                tried.append(f"{ch.key}: {e.message or e.kind}"[:200])
                if e.kind not in ("unavailable", "budget"):
                    self.stats.record(ch.key, decision, False, time.monotonic() - t0)
                continue
            if ch.paid:
                self._warm[(ch.key, stable_hash)] = time.monotonic()
            usd = spend.cost(ch.key.split(":", 1)[1], res.tokens_in, res.tokens_out, res.cache_read,
                             res.cache_write) if ch.paid else 0.0
            if res.finish == "refusal":
                tried.append(f"{ch.key}: refused")
                continue
            data = parse_json(res.text)
            if data is not None:                 # French accents re-read in a legacy code page (seen on real answers)
                data = fix_mojibake_deep(data)
            if data is None or not all(k in data for k in schema.get("required", [])):
                tried.append(f"{ch.key}: invalid answer")
                self.stats.record(ch.key, decision, False, secs, usd)
                continue
            if decision not in FIXES:             # a correction's success is the checker's verdict (the caller)
                self.stats.record(ch.key, decision, True, secs, usd)
            return Reply(data, ch.key, ch.name, ch.tier, usd, secs, res.tokens_in, res.tokens_out, res.cache_read,
                         res.cache_write, tried)
        raise NoConductor(tried)


ROLE_ROLES = ("understand", "formalize", "explain", "prove")


def conductor_of(brain) -> Conductor | None:
    """The brain's conductor (created once), None for brains that cannot run it (fakes, tests)."""
    if brain is None or not Conductor.usable(brain):
        return None
    c = getattr(brain, "_conductor", None)
    if c is None:
        c = Conductor(brain)
        try:
            brain._conductor = c                                            # noqa: SLF001
        except AttributeError:
            return None
    return c


def describe(c: Choice) -> dict[str, Any]:
    return {"key": c.key, "name": c.name, "tier": c.tier, "paid": c.paid, "est_usd": round(c.est_usd, 5),
            "utility": round(c.utility, 3), "why": c.why}
