"""A scripted brain with a conductor (session S-AI, D41), for tests and for the measurements of
`scripts/dev/conductor_bench.py`: `FakeBrain`'s workers (scripted answers, no network) plus the interface the
conductor uses (`call_model`, catalogue view, states, ledger, caps), where the Claude calls are SCRIPTED: no request
leaves the process. Usage tokens are counted from the prompt (≈ 3.5 characters per token) and priced with the real
list prices; the stable system block is « cached » by model like the Anthropic prompt cache (5 minutes)."""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Any, Callable

from . import spend
from .catalogue import Catalogue, Model, Provider
from .fake import FakeBrain
from .leaderboard import Leaderboard
from .providers.base import ProviderError, StreamResult
from .settings import merged
from .state import States

CLAUDE_IDS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
# seconds per decision on each model (scaled by `time_scale`), from the real validation runs (docs/PERFORMANCE.md)
LATENCY = {"claude-haiku-5-5": 1.5, "claude-sonnet-5-5": 4.0, "claude-opus-5-5": 7.0, "free": 6.0}


def _kind(messages: list[dict]) -> str:
    sys = " ".join(m.get("content", "") for m in messages if m.get("role") == "system")
    if "Lean 4 + Mathlib rejected the translation" in sys:
        return "fix_statement"
    if "Prover models failed to prove" in sys:
        return "fix_proof"
    if "final coherence" in sys:
        return "final"
    return "plan"


def demo_conductor(kind: str, messages: list[dict], brain: "ConductedFakeBrain") -> dict:
    """Answers like a conductor would on the demo theorem (sum of two even numbers)."""
    import json
    user = messages[-1].get("content", "")
    if kind == "plan":
        c = re.findall(r"(fake:fake-\w+|anthropic:claude-[\w-]+)", user)
        pick = lambda role: next((k for k in c if k.endswith(role)), "auto")  # noqa: E731
        return {"text": json.dumps({"difficulty": "easy", "summary": "Traduire, chercher dans Mathlib, prouver, "
                                    "expliquer.", "tasks": [
            {"id": "t1", "kind": "formalize", "goal": "Lean statement", "depends_on": [], "model":
             pick("formalize"), "why": "best measured", "hint": "Use `Even` from Mathlib."},
            {"id": "t2", "kind": "mathlib", "goal": "Mathlib", "depends_on": ["t1"], "model": "auto", "why": "",
             "hint": "Try `Even.add`."},
            {"id": "t3", "kind": "prove", "goal": "proof", "depends_on": ["t1"], "model": pick("prove"),
             "why": "fast", "hint": "`Even.add ha hb` closes it."},
            {"id": "t4", "kind": "explain", "goal": "explanation", "depends_on": ["t3"], "model":
             pick("explain"), "why": "French writing", "hint": ""}]})}
    if kind == "fix_statement":
        name = re.search(r"Theorem name: (\S+)", user)
        n = name.group(1) if name else "t"
        return {"text": json.dumps({"statement": f"theorem {n} (a b : ℕ) (ha : Even a) (hb : Even b) : "
                                    "Even (a + b) := by sorry", "what": "parenthèse manquante après `Even a`."})}
    if kind == "fix_proof":
        m = re.search(r"```lean4\n(.*?)```", user, re.S)
        stmt = m.group(1) if m else ""
        sig = stmt[stmt.rindex("theorem"):].replace(":= by sorry", ":= by") if "theorem" in stmt else ""
        return {"text": json.dumps({"proof": f"{sig}\n  exact Even.add ha hb", "what": "lemme inexistant "
                                    "remplacé par `Even.add`."})}
    return {"text": json.dumps({"consistent": True, "issues": [], "summary": "Tout concorde."})}


class ConductedFakeBrain(FakeBrain):
    """FakeBrain + the conductor's interface. `conductor`: callable(kind, messages, brain) → {text, finish?, error?,
    delay?} per call; `claude_key`: whether an Anthropic key is « set »; `free`: whether free conductors exist."""

    def __init__(self, config_dir: Path, *, conductor: Callable | None = None, claude_key: bool = True,
                 free: bool = True, time_scale: float = 0.0, settings: dict | None = None, **kw):
        super().__init__(**kw)
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings = merged({"conductor": True, **(settings or {})})
        self.ledger = spend.Ledger(self.config_dir / "brain-spend.json")
        self.states = States(self.config_dir / "brain-state.json")
        self.leaderboard = Leaderboard(self.config_dir / "brain-leaderboard.json")
        self.rankings = None
        self.down: dict[str, float] = {}
        self.conductor_fn = conductor or demo_conductor
        self.claude_key = claude_key
        self.free = free
        self.time_scale = time_scale
        self.calls: list[dict[str, Any]] = []         # every conductor call (model, kind, usage, usd)
        self._cache: dict[tuple[str, str], float] = {}

    # ------------------------------------------------------------ what the conductor reads
    def update_settings(self, s: dict) -> None:
        self.settings = merged({**self.settings, **s})

    def effective_mode(self, mode: str) -> str:
        return "local" if "local" in (mode, self.settings.get("mode")) else mode

    def key(self, provider: str) -> str | None:
        return "sk-ant-fake" if provider == "anthropic" and self.claude_key else None

    def caps(self) -> tuple[float, float]:
        return float(self.settings.get("claude_cap_proof_usd", 1.0)), float(self.settings.get("claude_cap_month_usd",
                                                                                                20.0))

    def _view(self) -> Catalogue:
        q = lambda v: {c: v for c in ("chat", "code", "math", "reasoning", "writing")}  # noqa: E731
        models = [Model("fake", f"fake-{r}", f"Fake {r}", quality=q(0.8)) for r in
                  ("understand", "formalize", "prove", "explain")]
        if not self.free:
            models = [Model("fake", f"fake-{r}", f"Fake {r}", quality=q(0.3)) for r in
                      ("understand", "formalize", "prove", "explain")]
        if self.claude_key:
            from .catalogue import ANTHROPIC_MODELS
            models += [Model("anthropic", m, n, quality=dict(qq), paid=True) for m, n, qq in ANTHROPIC_MODELS]
        return Catalogue(time.time(), [Provider("fake", "Fake", "http://127.0.0.1:0/v1"),
                                       Provider("anthropic", "Anthropic", "", keyed=True, paid=True,
                                                api="anthropic")], models)

    def model_of(self, key: str) -> Model | None:
        return next((m for m in self._view().models if m.key == key), None)

    # ------------------------------------------------------------ one conductor call
    async def call_model(self, key: str, role: str, messages: list[dict], *, mode: str = "auto",
                         max_tokens: int | None = None, extra: dict | None = None, on_chunk=None):
        m = self.model_of(key)
        if m is None:
            raise ProviderError("unavailable", f"{key}: not available")
        if self.states.pause_of(key):
            raise ProviderError("unavailable", f"{key}: paused")
        kind = _kind(messages)
        ans = self.conductor_fn(kind, messages, self)
        if asyncio.iscoroutine(ans):
            ans = await ans
        tier = m.model_id if m.paid else "free"
        delay = ans.get("delay", LATENCY.get(tier, 3.0) * self.time_scale)
        if delay:
            await asyncio.sleep(delay)
        if ans.get("error"):
            status = int(ans.get("status", 429))
            if status == 429:
                self.states.record(key, False, 429, "rate limited", 30.0)
            raise ProviderError("http", ans["error"], status)
        text = ans.get("text", "")
        stable = next((x.get("content", "") for x in messages if x.get("stable")), "")
        n_in = int(sum(len(str(x.get("content", ""))) for x in messages) / spend.CHARS_PER_TOKEN) + 1
        n_st = int(len(stable) / spend.CHARS_PER_TOKEN)
        h = hashlib.sha256(stable.encode()).hexdigest()
        warm = time.monotonic() - self._cache.get((key, h), -1e9) < 300
        cache_read = n_st if (warm and m.paid) else 0
        cache_write = 0 if (warm or not m.paid) else n_st
        self._cache[(key, h)] = time.monotonic()
        n_out = int(len(text) / spend.CHARS_PER_TOKEN) + 1
        res = StreamResult(text=text, finish=ans.get("finish", "stop"), tokens_in=n_in, tokens_out=n_out,
                           cache_read=cache_read, cache_write=cache_write)
        usd = 0.0
        if m.paid:
            row = self.ledger.record(m.model_id, spend.SPEND_SCOPE.get(), n_in, n_out, cache_read, cache_write)
            usd = row.usd
        from . import usage                     # S-AK: counted like a real provider call
        usage.record(m.provider if hasattr(m, "provider") else "fake", m.model_id, n_in, n_out, usd=usd)
        self.calls.append({"model": key, "kind": kind, "tokens_in": n_in, "tokens_out": n_out,
                           "cache_read": cache_read, "cache_write": cache_write, "usd": usd,
                           "extra": dict(extra or {}), "messages": messages})
        if res.finish != "refusal":
            self.states.record(key, True)
        return res, delay, delay
