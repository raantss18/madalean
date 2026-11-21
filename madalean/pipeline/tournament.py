"""Proof tournament (session S-J, DECISIONS D30, docs/BRAIN.md §11): which model proves this statement, fast and
safely.

- Round 0 (exploit): the best model for this task and domain (router order, which includes the leaderboard bonus)
  gets up to `attempts_per_model` attempts. When it cannot run at all (429, quota, pause), the second best takes its
  place — « keep the two best ».
- Rounds 1…`max_rounds` (explore): K distinct models not yet tried in this task race in parallel on the same
  statement (K = `contestants`, at most the number of `online` slots; the local Goedel prover is one contestant when
  the GPU is usable). The first Lean-verified proof wins and cancels the others.
- Every finished contestant's outcome goes to the leaderboard, so the winners become round 0 next time.

Termination is structural, not hoped for: round 0 runs at most 2 contestants, each exploration round takes models
never tried in this task (a finite pool), the number of rounds is capped, and every round is bounded by the
remaining wall time (`max_minutes`), the attempt budget (`max_attempts`) and the token budget. No recursion, no
retry of a model inside the tournament beyond round 0. Cancelling the job cancels every contestant (their HTTP
requests and Lean processes die with their tasks)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..logs import get

log = get("tournament")

MAX_TOTAL_ATTEMPTS = 16        # agent runs + Goedel attempts in one proof stage
MAX_TOTAL_TOKENS = 3_000_000   # when known (Goedel attempts report their tokens; agents report theirs if any)
ROUND0_TIME_SHARE = 0.5        # round 0 may use at most half of the wall-time budget: exploration must get its turn
EXPLORE_RUNS = 1               # attempts of an online contestant in an exploration round (one agent run)
CANCEL_GRACE = 20.0            # seconds to wait for cancelled contestants to unwind
REFILLS_PER_SLOT = 2           # a contestant that could not run at all (429…) is replaced at once by the next untried
                               # model, at most 2 × K times per round (free providers are often saturated)

# $/million tokens (input, output) of the paid models we know (claude-api skill, cached 2026-11-03). Rough upper
# bound shown to the user before a paid model enters a race.
PRICES = {"anthropic:claude-opus-5-5": (4.0, 20.0), "anthropic:claude-sonnet-5-5": (2.0, 10.0),
          "anthropic:claude-haiku-5-5": (0.10, 0.50)}


@dataclass
class Config:
    enabled: bool = True
    contestants: int = 3
    max_rounds: int = 3
    max_minutes: float = 40.0
    attempts_per_model: int = 4
    max_attempts: int = MAX_TOTAL_ATTEMPTS
    max_tokens: int = MAX_TOTAL_TOKENS

    @classmethod
    def from_settings(cls, s: Any) -> "Config":
        def g(name: str, default):
            v = getattr(s, name, default)
            return v if isinstance(v, type(default)) and not (isinstance(default, int) and isinstance(v, bool)) \
                else default
        return cls(bool(getattr(s, "tournament_enabled", True)), max(1, g("tournament_contestants", 3)),
                   max(0, g("tournament_max_rounds", 3)), float(max(1, g("tournament_max_minutes", 40))),
                   max(1, min(g("tournament_attempts_per_model", 4), max(1, g("prove_attempts", 8)))))


@dataclass
class Contestant:
    key: str                  # model key "provider:model_id" (local Goedel: "local:<file>")
    name: str = ""
    kind: str = "agent"       # agent | goedel
    paid: bool = False
    local: bool = False


@dataclass
class Outcome:
    contestant: Contestant
    round: int
    ok: bool = False
    result: Any = None        # ProveResult when ok
    attempts: int = 0
    lean_errors: int = 0
    seconds: float = 0.0
    tokens: int = 0
    unavailable: bool = False  # could not run at all (429, quota, pause, no model): not a mathematical failure
    cancelled: bool = False
    error: str = ""


@dataclass
class Result:
    winner: Outcome | None = None
    outcomes: list[Outcome] = field(default_factory=list)
    rounds: int = 0
    stop: str = ""            # won | exhausted | rounds | time | attempts | tokens | reinforcement (paid round failed)
    tried: list[str] = field(default_factory=list)


RunFn = Callable[[Contestant, int, int, float], Awaitable[Outcome]]   # (contestant, round, attempts, deadline)


class Tournament:
    def __init__(self, cfg: Config, *, candidates: Callable[[], list[Contestant]], run: RunFn,
                 record: Callable[[Outcome], None] | None = None,
                 on_round: Callable[[int, list[Contestant]], Any] | None = None,
                 on_join: Callable[[int, Contestant], Any] | None = None, online_slots: int = 3,
                 clock: Callable[[], float] = time.monotonic,
                 reinforce: Callable[[], list[Contestant]] | None = None):
        self.cfg, self.candidates, self.run_one = cfg, candidates, run
        self.reinforce = reinforce            # paid reinforcement (S-M): final round when every free model failed
        self.record_fn, self.on_round, self.on_join = record, on_round, on_join
        self.online_slots = max(1, online_slots)
        self.clock = clock
        self.res = Result()
        self.used_attempts = 0
        self.used_tokens = 0
        self.tried: set[str] = set()

    # ------------------------------------------------------------ helpers
    def _record(self, o: Outcome) -> None:
        self.res.outcomes.append(o)
        if o.cancelled:
            return
        if not o.unavailable:                      # a model that could not run spent no attempt (refills are capped)
            self.used_attempts += max(0, o.attempts)
        self.used_tokens += max(0, o.tokens)
        if self.record_fn is not None:
            try:
                self.record_fn(o)
            except Exception:  # noqa: BLE001 (the leaderboard must never break a proof)
                log.exception("leaderboard record failed")

    async def _announce(self, k: int, cs: list[Contestant]) -> None:
        self.res.rounds = k + 1
        if self.on_round is not None:
            r = self.on_round(k, cs)
            if asyncio.iscoroutine(r):
                await r

    def _budget_stop(self, deadline: float) -> str:
        if self.clock() >= deadline - 1:
            return "time"
        if self.used_attempts >= self.cfg.max_attempts:
            return "attempts"
        if self.used_tokens >= self.cfg.max_tokens:
            return "tokens"
        return ""

    def _fresh(self) -> list[Contestant]:
        out, seen = [], set()
        for c in self.candidates():
            if c.key in self.tried or c.key in seen:
                continue
            seen.add(c.key)
            out.append(c)
        return out

    async def _guarded(self, c: Contestant, k: int, n: int, deadline: float) -> Outcome:
        """One contestant, bounded by the deadline whatever it does."""
        t0 = self.clock()
        try:
            return await asyncio.wait_for(self.run_one(c, k, n, deadline), max(1.0, deadline - self.clock()))
        except asyncio.TimeoutError:
            return Outcome(c, k, attempts=n, seconds=self.clock() - t0, error="time")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 (one contestant's crash is its own failure, not the tournament's)
            if _fatal(e):
                raise
            return Outcome(c, k, unavailable=True, seconds=self.clock() - t0, error=f"{type(e).__name__}: {e}"[:300])

    # ------------------------------------------------------------ main
    async def run(self) -> Result:
        res = await self._free_rounds()
        if res.winner is not None or self.reinforce is None or res.stop == "time":
            return res
        return await self._reinforcement(res.stop)

    async def _reinforcement(self, stop: str) -> Result:
        """Final round (user decision 2026-11-21): the free models failed, the paid reinforcement (Claude) gets one
        run, bounded by the remaining wall time and by the spending caps the engine enforces on every call. It is
        not bound by the attempt/token budgets of the free rounds (they are what ran out)."""
        try:
            cs = [c for c in (self.reinforce() or []) if c.key not in self.tried][:1]
        except Exception:  # noqa: BLE001
            log.exception("reinforcement candidates failed")
            cs = []
        deadline = self._deadline
        if not cs or self.clock() >= deadline - 30:
            return self._done(None, stop)
        k = self.res.rounds
        await self._announce(k, cs)
        self.tried.add(cs[0].key)
        o = await self._guarded(cs[0], k, EXPLORE_RUNS, deadline)
        self._record(o)
        return self._done(o if o.ok else None, "won" if o.ok else "reinforcement")

    async def _free_rounds(self) -> Result:
        cfg = self.cfg
        start = self.clock()
        deadline = start + cfg.max_minutes * 60.0
        self._deadline = deadline
        # ---- round 0: the best model, then the second best only if the best could not run at all
        r0_deadline = start + cfg.max_minutes * 60.0 * ROUND0_TIME_SHARE
        best = self._fresh()[:2]
        announced = False
        for c in best:
            if (why := self._budget_stop(r0_deadline)):
                break
            if not announced:
                await self._announce(0, best)
                announced = True
            self.tried.add(c.key)
            n = max(1, min(cfg.attempts_per_model, cfg.max_attempts - self.used_attempts))
            o = await self._guarded(c, 0, n, r0_deadline)
            self._record(o)
            if o.ok:
                return self._done(o, "won")
            if not o.unavailable:
                break                              # it ran and failed: race other models now
        # ---- rounds 1…max_rounds: races of untried models
        for k in range(1, cfg.max_rounds + 1):
            if (why := self._budget_stop(deadline)):
                return self._done(None, why)
            fresh = self._fresh()
            if not fresh:
                return self._done(None, "exhausted")
            cs = self._pick(fresh)
            left = cfg.max_attempts - self.used_attempts
            cs = cs[:max(1, left)]
            if not cs:
                return self._done(None, "exhausted")
            await self._announce(k, cs)
            for c in cs:
                self.tried.add(c.key)
            online = sum(1 for c in cs if c.kind != "goedel")
            plan = [(c, EXPLORE_RUNS if c.kind != "goedel" else
                     max(1, min(cfg.attempts_per_model, left - online))) for c in cs]
            winner = await self._race(k, plan, deadline)
            if winner is not None:
                return self._done(winner, "won")
        why = self._budget_stop(deadline)
        return self._done(None, why or ("exhausted" if not self._fresh() else "rounds"))

    def _pick(self, fresh: list[Contestant]) -> list[Contestant]:
        """K contestants: the local Goedel prover (when offered) is one of them; online ones ≤ online slots."""
        k = max(1, self.cfg.contestants)
        goedel = [c for c in fresh if c.kind == "goedel"][:1]
        online = [c for c in fresh if c.kind != "goedel"][:max(0, min(k - len(goedel), self.online_slots))]
        return (online + goedel)[:k] if online or goedel else []

    async def _race(self, k: int, plan: list[tuple[Contestant, int]], deadline: float) -> Outcome | None:
        tasks: dict[asyncio.Task, Contestant] = {
            asyncio.create_task(self._guarded(c, k, n, deadline), name=f"tournament-{k}-{c.key}"): c for c, n in plan}
        pending = set(tasks)
        winner = None
        refills = REFILLS_PER_SLOT * max(1, len(plan))

        def refill() -> asyncio.Task | None:
            nonlocal refills
            if refills <= 0 or self._budget_stop(deadline):
                return None
            nxt = next((c for c in self._fresh() if c.kind != "goedel"), None)
            if nxt is None:
                return None
            refills -= 1
            self.tried.add(nxt.key)
            if self.on_join is not None:
                try:
                    self.on_join(k, nxt)
                except Exception:  # noqa: BLE001
                    pass
            t = asyncio.create_task(self._guarded(nxt, k, EXPLORE_RUNS, deadline), name=f"tournament-{k}-{nxt.key}")
            tasks[t] = nxt
            return t
        try:
            while pending and winner is None:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED,
                                                   timeout=max(1.0, deadline - self.clock() + 5))
                if not done:
                    break                                       # deadline (each contestant is also bounded)
                for t in done:
                    c = tasks[t]
                    try:
                        o = t.result()
                    except asyncio.CancelledError:
                        o = Outcome(c, k, cancelled=True)
                    except Exception as e:  # noqa: BLE001
                        if _fatal(e):
                            raise
                        o = Outcome(c, k, unavailable=True, error=f"{type(e).__name__}: {e}"[:300])
                    self._record(o)
                    if o.ok and winner is None:
                        winner = o
                    elif o.unavailable and winner is None and c.kind != "goedel" and (t2 := refill()) is not None:
                        pending.add(t2)
        finally:
            if pending:
                for t in pending:
                    t.cancel()
                done, _ = await asyncio.wait(pending, timeout=CANCEL_GRACE)
                for t in pending:
                    self._record(Outcome(tasks[t], k, cancelled=True))
        return winner

    def _done(self, winner: Outcome | None, stop: str) -> Result:
        self.res.winner, self.res.stop = winner, stop
        self.res.tried = sorted(self.tried)
        return self.res


def _fatal(e: BaseException) -> bool:
    """Errors that must stop the whole proof stage (the Lean workspace is broken), not just one contestant."""
    return getattr(e, "kind", "") == "workspace"


def estimated_cost(key: str, tokens: int) -> float | None:
    """Upper bound in $ of one agent run on a paid model with this token budget (≈ 85 % prompt, 15 % output)."""
    p = PRICES.get(key)
    if p is None:
        return None
    return round(tokens / 1e6 * (0.85 * p[0] + 0.15 * p[1]), 2)


def leaderboard_of(ctx):
    """The brain's leaderboard, or one kept by the server next to it (fake brains in tests and `--demo`)."""
    lb = getattr(getattr(ctx, "brain", None), "leaderboard", None)
    if lb is not None:
        return lb
    lb = getattr(ctx, "_leaderboard", None)
    if lb is None:
        from ..brain.leaderboard import Leaderboard
        lb = Leaderboard(ctx.paths.config / "brain-leaderboard.json")
        ctx._leaderboard = lb
    return lb
