"""Token tally of every model call (session S-AK, DECISIONS D43): today, this month, per request.

The spending ledger (spend.py) only records *paid* calls, with their price; the status panel of the web UI also shows
the tokens of the free and local models. Every provider client calls `record()` once per answered call (and the
scripted brains of the demo do the same), so nothing else has to remember to count.

- per day (local date) and per provider: tokens in / out and calls, persisted (`model-usage.json` in the config directory,
  62 days kept), written at most every few seconds and on `flush()`;
- per request: the job / request owner of `slots.CURRENT_JOB` (in memory, the 200 most recent), with the USD cost of
  the paid calls (spend.cost of the list prices; 0 for free and local models).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

KEEP_DAYS = 62
KEEP_SCOPES = 200
WRITE_EVERY = 5.0


def day_of(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _blank() -> dict:
    return {"tokens_in": 0, "tokens_out": 0, "calls": 0, "usd": 0.0}


def _add(into: dict, tin: int, tout: int, usd: float) -> None:
    into["tokens_in"] += tin
    into["tokens_out"] += tout
    into["calls"] += 1
    into["usd"] = round(into["usd"] + usd, 6)


class Tally:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.path: Path | None = None
        self.days: dict[str, dict] = {}            # day -> {"all": totals, "by_provider": {provider: totals}}
        self.scopes: dict[str, dict] = {}          # job / request id -> totals (+ "models": [...])
        self._dirty = False
        self._written = 0.0

    # ------------------------------------------------------------ persistence
    def attach(self, path: Path) -> None:
        """Load the persisted days (called once by the server context)."""
        with self._lock:
            self.path, self.days, self.scopes, self._dirty = path, {}, {}, False
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            days = raw.get("days") if isinstance(raw, dict) else None
            if isinstance(days, dict):
                for d, v in days.items():
                    if isinstance(v, dict) and isinstance(v.get("all"), dict):
                        self.days.setdefault(d, v)

    def flush(self) -> None:
        with self._lock:
            self._write_locked()

    def _write_locked(self) -> None:
        if not self.path or not self._dirty:
            return
        for d in sorted(self.days)[:-KEEP_DAYS]:
            self.days.pop(d, None)
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"days": self.days}), encoding="utf-8")
            tmp.replace(self.path)
            self._dirty = False
            self._written = time.monotonic()
        except OSError:
            pass

    # ------------------------------------------------------------ recording
    def record(self, provider: str, model: str, tokens_in: int, tokens_out: int, *, usd: float | None = None,
               scope: str | None = None, when: float | None = None) -> None:
        tin, tout = max(0, int(tokens_in or 0)), max(0, int(tokens_out or 0))
        if usd is None:
            try:
                from .spend import cost
                usd = cost(model, tin, tout) if provider not in ("local", "ollama", "fake") else 0.0
            except Exception:  # noqa: BLE001
                usd = 0.0
        if scope is None:
            try:
                from ..slots import CURRENT_JOB
                scope = CURRENT_JOB.get()
            except Exception:  # noqa: BLE001
                scope = ""
        d = day_of(when if when is not None else time.time())
        with self._lock:
            day = self.days.setdefault(d, {"all": _blank(), "by_provider": {}})
            _add(day["all"], tin, tout, usd)
            _add(day["by_provider"].setdefault(provider or "?", _blank()), tin, tout, usd)
            if scope:
                s = self.scopes.pop(scope, None) or {**_blank(), "models": []}
                _add(s, tin, tout, usd)
                key = f"{provider}:{model}"
                if key not in s["models"]:
                    s["models"].append(key)
                self.scopes[scope] = s                 # most recent last
                while len(self.scopes) > KEEP_SCOPES:
                    self.scopes.pop(next(iter(self.scopes)))
            self._dirty = True
            if time.monotonic() - self._written >= WRITE_EVERY:
                self._write_locked()

    # ------------------------------------------------------------ reading
    def summary(self, scopes: list[str] | None = None, now: float | None = None) -> dict:
        now = now if now is not None else time.time()
        today, month = day_of(now), day_of(now)[:7]
        with self._lock:
            t = self.days.get(today, {}).get("all") or _blank()
            m = _blank()
            for d, v in self.days.items():
                if d.startswith(month):
                    a = v.get("all") or {}
                    m["tokens_in"] += int(a.get("tokens_in", 0))
                    m["tokens_out"] += int(a.get("tokens_out", 0))
                    m["calls"] += int(a.get("calls", 0))
                    m["usd"] = round(m["usd"] + float(a.get("usd", 0.0)), 6)
            by_provider = {k: dict(v) for k, v in (self.days.get(today, {}).get("by_provider") or {}).items()}
            sc = {k: {**v, "models": list(v["models"])} for k, v in self.scopes.items() if scopes is None or k in scopes}
        return {"today": dict(t), "month": m, "by_provider_today": by_provider, "requests": sc}


TALLY = Tally()


def record(provider: str, model: str, tokens_in: int, tokens_out: int, **kw) -> None:
    """Never raises: counting must not break a model call."""
    try:
        TALLY.record(provider, model, tokens_in, tokens_out, **kw)
    except Exception:  # noqa: BLE001
        pass
