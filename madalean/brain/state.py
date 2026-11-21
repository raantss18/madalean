"""Observed state of each model: pauses (429, daily quota, refused key…) and reliability. Ported from L Katta's
moteur.rs (`Etat`, `record_attente`, `pause_provider`, `duree`, `contexte_trop_long`).

Persisted in `<config_dir>/brain-state.json` (mode 0600)."""
from __future__ import annotations

import json
import math
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from ._util import now, read_json, write_private

KEY_REFUSED_PAUSE = 12 * 3600.0
CREDIT_PAUSE = 12 * 3600.0


@dataclass
class ModelState:
    until: float = 0.0        # paused until (unix seconds)
    reason: str = ""          # rate_limit | daily_quota | key_refused | no_credit | paused | overloaded
    failures: int = 0         # consecutive failures
    ok: float = 0.0           # exponentially decayed successes
    total: float = 0.0        # exponentially decayed attempts


def context_too_long(status: int, message: str) -> bool:
    """The conversation is too long for this model: not the model's fault (no penalty)."""
    low = message.lower()
    return status in (400, 413, 422) and any(k in low for k in (
        "context", "too long", "too many tokens", "maximum length", "prompt is too long",
        "context_length", "trop long"))


def parse_duration(v: str) -> float | None:
    """Delay announced by a provider: seconds, a unix date (s or ms), or « 1m30s », « 250ms », « 2h »."""
    v = v.strip()
    if not v:
        return None
    try:
        n = float(v)
    except ValueError:
        n = None
    if n is not None:
        d = n / 1000.0 - now() if n > 1e12 else (n - now() if n > 1e9 else n)
        return d if d > 0 else None
    total, num, i = 0.0, "", 0
    while i < len(v):
        c = v[i]
        if c.isdigit() or c == ".":
            num += c
            i += 1
            continue
        try:
            x = float(num)
        except ValueError:
            return None
        num = ""
        if c == "h":
            total += x * 3600
        elif c == "m" and i + 1 < len(v) and v[i + 1] == "s":
            total += x / 1000
            i += 1
        elif c == "m":
            total += x * 60
        elif c == "s":
            total += x
        else:
            return None
        i += 1
    return total if not num and total > 0 else None


def wait_from_headers(headers) -> float | None:
    """`Retry-After` (seconds) or `x-ratelimit-reset*` / `anthropic-ratelimit-*-reset` headers."""
    def get(k: str) -> str | None:
        try:
            v = headers.get(k)
        except Exception:  # noqa: BLE001
            return None
        return v.strip() if isinstance(v, str) else None
    ra = get("retry-after")
    if ra:
        try:
            return float(ra)
        except ValueError:
            pass
    for k in ("x-ratelimit-reset-requests", "x-ratelimit-reset", "x-ratelimit-reset-tokens"):
        v = get(k)
        if v and (d := parse_duration(v)) is not None:
            return d
    return None


class States:
    """Thread-safe table of model states, saved after each change."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        raw = read_json(path) or {}
        self.models: dict[str, ModelState] = {}
        for k, v in (raw.get("models") or {}).items():
            try:
                self.models[k] = ModelState(**{f: v[f] for f in ModelState.__dataclass_fields__ if f in v})
            except (TypeError, KeyError):
                pass

    def _save(self) -> None:
        try:
            write_private(self.path, json.dumps({"models": {k: asdict(v) for k, v in self.models.items()}}))
        except OSError:
            pass

    def pause_of(self, key: str) -> tuple[float, str] | None:
        s = self.models.get(key)
        return (s.until, s.reason) if s and s.until > now() else None

    def reliability(self, key: str) -> float:
        s = self.models.get(key)
        ok, total = (s.ok, s.total) if s else (0.0, 0.0)
        return (ok + 4.0) / (total + 5.0)

    def pause_provider(self, provider: str, keys: list[str], reason: str = "key_refused",
                       seconds: float = KEY_REFUSED_PAUSE) -> None:
        with self._lock:
            for k in keys:
                st = self.models.setdefault(k, ModelState())
                st.until, st.reason = now() + seconds, reason
            self._save()

    def record(self, key: str, ok: bool, status: int = 0, message: str = "", wait: float | None = None) -> None:
        if not ok and context_too_long(status, message):
            return
        with self._lock:
            st = self.models.setdefault(key, ModelState())
            st.ok = st.ok * 0.97 + (1.0 if ok else 0.0)
            st.total = st.total * 0.97 + 1.0
            if ok:
                st.failures, st.until, st.reason = 0, 0.0, ""
            elif status != 400:
                st.failures += 1
                low = message.lower()
                t = now()
                if status == 402:
                    st.until, st.reason = t + CREDIT_PAUSE, "no_credit"
                elif wait is not None and wait > 0:
                    st.until, st.reason = t + min(max(wait, 5.0), 3600.0), "rate_limit"
                elif any(w in low for w in ("daily", "per day", "per-day", "quota")):
                    st.until, st.reason = math.floor(t / 86400.0) * 86400.0 + 86400.0, "daily_quota"   # midnight UTC
                elif status in (529, 503) or "overloaded" in low:
                    st.until, st.reason = t + min(15.0 * 2 ** (min(st.failures, 6) - 1), 600.0), "overloaded"
                else:
                    st.until, st.reason = t + min(30.0 * 2 ** (min(st.failures, 6) - 1), 1800.0), "paused"
            self._save()

    def clear(self) -> None:
        with self._lock:
            self.models.clear()
            self._save()
