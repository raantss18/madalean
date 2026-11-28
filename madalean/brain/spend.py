"""Paid-model spending (session S-M, user decision 2026-11-21): Claude is a paid reinforcement, used only within the
caps the user sets in Réglages → Modèles — a cap per proof (default 1.00 USD) and a cap per calendar month
(default 20 USD). Session S-T (user decision 2026-11-22): the SAME caps and ledger cover every keyed paid provider
with a known or estimated price — Hugging Face Inference Providers (Goedel-Prover-V2-32B online) included.

- Before each call to a paid model, `estimate()` gives an upper bound from the request size (≈ 3.5 characters per
  token, nothing assumed cached) and the call's `max_tokens`, at list prices (claude-api skill, cached 2026-11-03).
- `Ledger.check()` refuses the call when the estimate would take the proof or the month past its cap: the engine
  raises ProviderError("budget") and says so; nothing is sent.
- After the call, `Ledger.record()` stores the real cost from the API's usage (input, output, cache read, cache
  write tokens) in `<config_dir>/brain-spend.json` (mode 0600, no keys, no prompts; bounded).

The proof scope comes from the context variable SPEND_SCOPE (set by the pipeline around a proof stage); a call made
outside any proof only counts towards the month.

S-BJ (D69): a GROUP (context variable SPEND_GROUP, e.g. « attack:2026-11-28 ») spans many proofs. It is set by the
caller before a job is submitted, so the job's task inherits it whatever proof scopes the pipeline sets inside; a
group with a cap in `Ledger.group_caps` is refused past that cap (on top of the proof and month caps)."""
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
# Hugging Face Inference Providers bill the provider's price with no markup (huggingface.co/docs/inference-providers/
# pricing, 2026-11-22: PRO accounts get 2 USD of credits a month, free accounts must buy credits, then pay-as-you-go).
# The router publishes no price for Goedel on featherless-ai (GET router.huggingface.co/v1/models/<repo>: no
# `pricing`), so this is a CONSERVATIVE ESTIMATE, not a real price: about the router's published price of a much
# larger model on the same provider (GLM-5.3 on featherless-ai: 0.98 / 3.08 USD per MTok), rounded up. A price the
# router publishes later (catalogue `Model.price`) replaces it. Featherless's own plans are flat-rate subscriptions;
# how HF bills them per request is not documented.
HF_ESTIMATE = (1.00, 3.20)
DYNAMIC: dict[str, tuple[float, float, float, float]] = {}    # "provider:model_id" -> price published by a provider
CHARS_PER_TOKEN = 3.5
MAX_ROWS = 5000
DEFAULT_CAP_PROOF = 1.0
DEFAULT_CAP_MONTH = 20.0
MIN_OUTPUT = 2048          # a paid call whose affordable answer would be shorter than this is not made

SPEND_SCOPE: contextvars.ContextVar[str | None] = contextvars.ContextVar("madalean_spend_scope", default=None)
SPEND_GROUP: contextvars.ContextVar[str] = contextvars.ContextVar("madalean_spend_group", default="")


LONG_PROMPT = {"claude-haiku-5-5": (100_000, 5.0)}   # prompts above 100K tokens: every price × 5 ($0.50 / $2.50)


def set_price(key: str, price: list[float] | tuple | None) -> None:
    """Record a price a provider publishes for one model (catalogue refresh), USD per million tokens (in, out)."""
    if price and len(price) >= 2 and all(isinstance(x, (int, float)) and x >= 0 for x in price[:2]):
        DYNAMIC[key] = (float(price[0]), float(price[1]), float(price[0]), float(price[0]))


def estimated_price(model_id: str) -> bool:
    """True when the price of this model is Madalean's estimate (no published price)."""
    return model_id.startswith("huggingface:") and model_id not in DYNAMIC


def price_of(model_id: str, prompt_tokens: int = 0) -> tuple[float, float, float, float] | None:
    """`model_id`: a Claude model id (« claude-opus-5-5 ») or a full key (« huggingface:<repo>:<provider> »)."""
    if model_id in DYNAMIC:
        return DYNAMIC[model_id]
    if model_id.startswith("huggingface:"):
        return (HF_ESTIMATE[0], HF_ESTIMATE[1], HF_ESTIMATE[0], HF_ESTIMATE[0])
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


def day_of_rows(ledger: "Ledger", now: float | None = None) -> tuple[float, float]:
    """Paid USD spent today and this month (local time), from the ledger's rows (S-AK status panel)."""
    now = now if now is not None else time.time()
    d, m = time.strftime("%Y-%m-%d", time.localtime(now)), month_of(now)
    today = sum(r.usd for r in ledger.rows if time.strftime("%Y-%m-%d", time.localtime(r.ts)) == d)
    month = sum(r.usd for r in ledger.rows if month_of(r.ts) == m)
    return round(today, 6), round(month, 6)


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
    group: str = ""       # S-BJ: spend group (« attack:<date> ») or ""


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
        # S-AI (D41): a request directed by the conductor has its own cap (default 1 USD, + 0.50 USD per « yes » to the
        # cap question); it replaces the per-proof cap for that scope (the request's scope IS its proof scope). Kept in
        # memory for the job's lifetime only; the monthly cap always applies on top.
        self.scope_caps: dict[str, float] = {}
        self.group_caps: dict[str, float] = {}     # S-BJ (D69): group -> cap in USD (e.g. the attack's day)
        self._reserved_group: dict[str, float] = {}

    def group_total(self, group: str) -> float:
        return sum(r.usd for r in self.rows if group and r.group == group)

    def group_room(self, group: str | None = None) -> float:
        group = SPEND_GROUP.get() if group is None else group
        if not group or group not in self.group_caps:
            return float("inf")
        return self.group_caps[group] - self.group_total(group) - self._reserved_group.get(group, 0.0)

    def cap_for(self, scope: str | None, cap_proof: float) -> float:
        return self.scope_caps.get(scope or "", cap_proof) if scope else cap_proof

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
            return self.cap_for(scope, cap_proof) - self.scope_total(scope) - self._reserved.get(scope, 0.0)

    def room(self, scope: str | None, cap_proof: float, cap_month: float) -> float:
        """USD still allowed for one call now (calls in flight count with their estimate)."""
        return max(0.0, min(self.month_room(cap_month), self.proof_room(scope, cap_proof), self.group_room()))

    def check(self, scope: str | None, est: float, cap_proof: float, cap_month: float) -> None:
        """Raise BudgetExceeded when the call would pass a cap (calls in flight count with their estimate)."""
        with self._lock:
            inflight = sum(self._reserved.values())
            month = self.month_total() + inflight
            if month + est > cap_month + 1e-9:
                raise BudgetExceeded("month", est, month, cap_month)
            if scope:
                s = self.scope_total(scope) + self._reserved.get(scope, 0.0)
                cap = self.cap_for(scope, cap_proof)
                if s + est > cap + 1e-9:
                    raise BudgetExceeded("proof", est, s, cap)
            group = SPEND_GROUP.get()
            if group and group in self.group_caps:
                g = self.group_total(group) + self._reserved_group.get(group, 0.0)
                if g + est > self.group_caps[group] + 1e-9:
                    raise BudgetExceeded("group", est, g, self.group_caps[group])
                self._reserved_group[group] = self._reserved_group.get(group, 0.0) + est
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
            group = SPEND_GROUP.get()
            if group in self._reserved_group:
                g = self._reserved_group[group] - est
                if g > 1e-9:
                    self._reserved_group[group] = g
                else:
                    self._reserved_group.pop(group, None)

    def record(self, model: str, scope: str | None, tokens_in: int, tokens_out: int, cache_read: int = 0,
               cache_write: int = 0) -> Row:
        row = Row(time.time(), model, scope or "", int(tokens_in), int(tokens_out), int(cache_read),
                  int(cache_write), round(cost(model, tokens_in, tokens_out, cache_read, cache_write), 6),
                  SPEND_GROUP.get())
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
                           for k, p in PRICES.items()},
                "hf_estimate": {"input": HF_ESTIMATE[0], "output": HF_ESTIMATE[1], "estimated": True}}
