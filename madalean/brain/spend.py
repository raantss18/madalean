"""Paid-model spending (session S-M, user decision 2026-11-21): Claude is a paid reinforcement, used only within the
caps the user sets in Réglages → Modèles — a cap per proof (default 1.00 USD) and a cap per calendar month
(default 20 USD).

- Before each call to a paid model, `estimate()` gives an upper bound from the request size (≈ 3.5 characters per
  token, nothing assumed cached) and the call's `max_tokens`, at list prices (claude-api skill, cached 2026-11-03).
- `Ledger.check()` refuses the call when the estimate would take the proof or the month past its cap: the engine
  raises ProviderError("budget") and says so; nothing is sent.
- After the call, `Ledger.record()` stores the real cost from the API's usage (input, output, cache read, cache
  write tokens) in `<config_dir>/brain-spend.json` (mode 0600, no keys, no prompts; bounded).

The proof scope comes from the context variable SPEND_SCOPE (set by the pipeline around a proof stage); a call made
outside any proof only counts towards the month."""
from __future__ import annotations

import contextvars
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ._util import read_json, write_private

# $ per million tokens: (input, output, cache read, cache write 5 min). Cache writes are billed 1.25 × input.
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-fable-5-2": (8.0, 40.0, 0.20, 10.0),
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.5),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}
CHARS_PER_TOKEN = 3.5
MAX_ROWS = 5000
DEFAULT_CAP_PROOF = 1.0
DEFAULT_CAP_MONTH = 20.0
MIN_OUTPUT = 2048          # a paid call whose affordable answer would be shorter than this is not made

SPEND_SCOPE: contextvars.ContextVar[str | None] = contextvars.ContextVar("madalean_spend_scope", default=None)


LONG_PROMPT = {"claude-haiku-5-5": (100_000, 5.0)}   # prompts above 100K tokens: every price × 5 ($0.50 / $2.50)


def price_of(model_id: str, prompt_tokens: int = 0) -> tuple[float, float, float, float] | None:
    mid = model_id.split(":", 1)[-1]
    base = PRICES.get(mid) or next((p for k, p in PRICES.items() if mid.startswith(k)), None)  # dated ids
    if base is None:
        return None
    for k, (limit, factor) in LONG_PROMPT.items():
        if mid.startswith(k) and prompt_tokens > limit:
            return tuple(x * factor for x in base)  # type: ignore[return-value]
    return base


def tokens_of(payload) -> int:
    """Rough token count of a request payload (system + messages + tools), rounded up."""
    try:
        n = len(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError):
        n = len(str(payload))
    return int(n / CHARS_PER_TOKEN) + 1


def estimate(model_id: str, input_tokens: int, max_output: int) -> float | None:
    """Upper bound in USD of one call: every input token uncached, the whole output budget used."""
    p = price_of(model_id, input_tokens)
    if p is None:
        return None
    return input_tokens / 1e6 * p[0] + max_output / 1e6 * p[1]


def cost(model_id: str, tokens_in: int, tokens_out: int, cache_read: int = 0, cache_write: int = 0) -> float:
    """Real cost of one call. `tokens_in` includes the cached tokens (as StreamResult reports it)."""
    p = price_of(model_id, tokens_in) or (0.0, 0.0, 0.0, 0.0)
    fresh = max(0, tokens_in - cache_read - cache_write)
    return (fresh * p[0] + tokens_out * p[1] + cache_read * p[2] + cache_write * p[3]) / 1e6


def month_of(ts: float) -> str:
    return time.strftime("%Y-%m", time.localtime(ts))


@dataclass
class Row:
    ts: float
    model: str
    scope: str            # proof scope (job id) or "" outside any proof
    tokens_in: int
    tokens_out: int
    cache_read: int
    cache_write: int
    usd: float


class BudgetExceeded(Exception):
    def __init__(self, which: str, estimate_: float, spent: float, cap: float):
        self.which, self.estimate, self.spent, self.cap = which, estimate_, spent, cap
        super().__init__(f"{which} cap: {spent:.2f} $ spent + {estimate_:.2f} $ estimated > {cap:.2f} $")


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.rows: list[Row] = []
        raw = read_json(path)
        for r in (raw or {}).get("rows", []) if isinstance(raw, dict) else []:
            try:
                self.rows.append(Row(**r))
            except TypeError:
                continue
        self._reserved: dict[str, float] = {}      # scope -> estimates of calls in flight

    def _save(self) -> None:
        self.rows = self.rows[-MAX_ROWS:]
        try:
            write_private(self.path, json.dumps({"rows": [asdict(r) for r in self.rows]}))
        except OSError:
            pass

    def month_total(self, when: float | None = None) -> float:
        m = month_of(when if when is not None else time.time())
        return sum(r.usd for r in self.rows if month_of(r.ts) == m)

    def scope_total(self, scope: str) -> float:
        return sum(r.usd for r in self.rows if scope and r.scope == scope)

    def month_room(self, cap_month: float) -> float:
        with self._lock:
            return cap_month - self.month_total() - sum(self._reserved.values())

    def proof_room(self, scope: str | None, cap_proof: float) -> float:
        if not scope:
            return float("inf")
        with self._lock:
            return cap_proof - self.scope_total(scope) - self._reserved.get(scope, 0.0)

    def room(self, scope: str | None, cap_proof: float, cap_month: float) -> float:
        """USD still allowed for one call now (calls in flight count with their estimate)."""
        return max(0.0, min(self.month_room(cap_month), self.proof_room(scope, cap_proof)))

    def check(self, scope: str | None, est: float, cap_proof: float, cap_month: float) -> None:
        """Raise BudgetExceeded when the call would pass a cap (calls in flight count with their estimate)."""
        with self._lock:
            inflight = sum(self._reserved.values())
            month = self.month_total() + inflight
            if month + est > cap_month + 1e-9:
                raise BudgetExceeded("month", est, month, cap_month)
            if scope:
                s = self.scope_total(scope) + self._reserved.get(scope, 0.0)
                if s + est > cap_proof + 1e-9:
                    raise BudgetExceeded("proof", est, s, cap_proof)
            key = scope or ""
            self._reserved[key] = self._reserved.get(key, 0.0) + est

    def release(self, scope: str | None, est: float) -> None:
        with self._lock:
            key = scope or ""
            left = self._reserved.get(key, 0.0) - est
            if left > 1e-9:
                self._reserved[key] = left
            else:
                self._reserved.pop(key, None)

    def record(self, model: str, scope: str | None, tokens_in: int, tokens_out: int, cache_read: int = 0,
               cache_write: int = 0) -> Row:
        row = Row(time.time(), model, scope or "", int(tokens_in), int(tokens_out), int(cache_read),
                  int(cache_write), round(cost(model, tokens_in, tokens_out, cache_read, cache_write), 6))
        with self._lock:
            self.rows.append(row)
            self._save()
        return row

    def summary(self, cap_proof: float, cap_month: float) -> dict:
        now_ = time.time()
        m = month_of(now_)
        rows = [r for r in self.rows if month_of(r.ts) == m]
        by_model: dict[str, float] = {}
        for r in rows:
            by_model[r.model] = by_model.get(r.model, 0.0) + r.usd
        return {"month": m, "spent_month": round(sum(r.usd for r in rows), 6), "cap_month": cap_month,
                "cap_proof": cap_proof, "calls_month": len(rows),
                "by_model": {k: round(v, 6) for k, v in sorted(by_model.items(), key=lambda x: -x[1])},
                "recent": [asdict(r) for r in self.rows[-20:]][::-1],
                "prices": {k: {"input": p[0], "output": p[1], "cache_read": p[2], "cache_write": p[3]}
                           for k, p in PRICES.items()}}
