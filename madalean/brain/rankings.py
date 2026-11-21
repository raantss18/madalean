"""« Classement » of the models (session S-V, DECISIONS D31): per Madalean domain, the best models usable now, from
three kinds of evidence, each shown with its source — never an invented score.

1. **Measured here** (leaderboard.py): Lean-verified results of this machine's tasks (prove / formalize / explain).
   The strongest evidence; it takes over as its confidence grows.
2. **Public signal** (LMArena, CC BY 4.0, verified 2026-11-22): the Hugging Face dataset `lmarena-ai/leaderboard-
   dataset` read through the keyless datasets-server API (`/filter`, config `text`, split `latest`, one category per
   request, top 100 by rating; each row carries `leaderboard_publish_date`). Same source as Tontolo
   (core/tontolo/catalog/sources/rankings.py). An LMArena row counts only when its name normalises EXACTLY to the
   model id of the catalogue (`slug`); effort variants « (High) », « (Max) » are folded conservatively (the lowest
   rating). It is a proxy (human preference votes on math / coding / writing prompts), not a Lean benchmark.
3. **Catalogue estimate** (catalogue.py): the seed's quality or the family estimate, labelled as an estimate.

Model news: every catalogue refresh diffs the usable models (keyless providers + providers whose key is set) against
the previous snapshot: « new » (badge « Nouveau » for NEW_DAYS days) and « gone » events, bounded. A provider seen
for the first time (key just added) gives one `provider_added` event, not a flood of « new ». New models with no
result here get a small router bonus so the tournament's exploration rounds try them (`router_bonus`).

Cadence: catalogue every CATALOGUE_SECS (12 h, catalogue.REFRESH_SECS), public rankings every PUBLIC_SECS (7 days),
both from the server's periodic tick; a manual refresh is allowed once per MIN_FORCE_SECS. Network: at most
len(SLICES) GETs per public refresh, through brain.net.Http (so `mode = local` never leaves the machine).
Persisted in `<config_dir>/brain-rankings.json` (0600)."""
from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass, field

from ._util import now, read_json, write_private
from .catalogue import REFRESH_SECS, Model, unfit_reason
from .leaderboard import Leaderboard, confidence, score_of

LMARENA_FILTER = "https://datasets-server.huggingface.co/filter"
LMARENA_DATASET = "lmarena-ai/leaderboard-dataset"
LMARENA_PAGE = "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset"
LMARENA_LICENSE = "CC BY 4.0"
VERIFIED = "2026-11-22"            # endpoint, fields and licence checked by hand on this date
SLICES = ("overall", "math", "coding", "creative_writing", "hard_prompts")   # config `text`
TOP_N = 100
PUBLIC_SECS = 7 * 86400.0
CATALOGUE_SECS = float(REFRESH_SECS)
MIN_FORCE_SECS = 3600.0
NEW_DAYS = 14
MAX_EVENTS = 200
NEW_BONUS = 0.05                   # router: a new model without any result here is worth one exploration try
PUBLIC_WEIGHT = 0.10               # router: ± half of this from the public percentile when nothing is measured here
SHOWN = 8

# Madalean domains: own leaderboard task, public slices (weights), catalogue category
DOMAINS: dict[str, dict] = {
    "lean": {"task": "prove", "public": {"math": 1.0}, "cat": "lean", "formal": True},
    "formalize": {"task": "formalize", "public": {"math": 0.6, "coding": 0.4}, "cat": "lean", "formal": True},
    "writing": {"task": "explain", "public": {"overall": 0.5, "creative_writing": 0.5}, "cat": "writing"},
    "code": {"task": None, "public": {"coding": 1.0}, "cat": "code"},
    "reasoning": {"task": None, "public": {"hard_prompts": 0.5, "math": 0.5}, "cat": "reasoning"},
}
ROLE_DOMAIN = {"prove": "lean", "formalize": "formalize", "explain": "writing", "assistant": "reasoning",
               "understand": "reasoning", "route": "reasoning"}

_PAREN = re.compile(r"\s*\([^)]*\)")
# only suffixes that never change the model (a « preview » or a size is a different model: kept)
_SUFFIX = re.compile(r"(-(instruct|it|chat|latest|free|\d{8}|\d{4}-\d{2}-\d{2}))+$")


def slug(name: str) -> str:
    """Normalised model name: « Claude Opus 5.5 (High) » and « anthropic/claude-opus-5.5:free » → claude-opus-5-5."""
    s = (name or "").split("/")[-1].split(":")[0]
    s = _PAREN.sub("", s).strip().lower()
    s = re.sub(r"[\s._]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return _SUFFIX.sub("", s)


def parse_lmarena(payload) -> list[dict]:
    """Rows of one datasets-server `/filter` answer → [{slug, name, org, rating, rank, total, published}]."""
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        return []
    total = payload.get("num_rows_total")
    out = []
    for item in payload["rows"]:
        row = item.get("row", item) if isinstance(item, dict) else None
        if not isinstance(row, dict):
            continue
        name, rating = row.get("model_name"), row.get("rating")
        if not isinstance(name, str) or not isinstance(rating, (int, float)) or isinstance(rating, bool):
            continue
        rk = row.get("rank")
        out.append({"slug": slug(name), "name": name[:120], "org": str(row.get("organization") or "")[:40],
                    "rating": round(float(rating), 1), "rank": int(rk) if isinstance(rk, (int, float)) else None,
                    "total": int(total) if isinstance(total, int) else None,
                    "published": str(row.get("leaderboard_publish_date") or "")[:10]})
    return out


def fold(rows: list[dict]) -> dict[str, dict]:
    """slug → row; effort variants of one model keep the plain name if listed, else the lowest rating; plus the
    model's percentile among the slice's rows (1 = best)."""
    best: dict[str, dict] = {}
    for r in rows:
        if not r["slug"]:
            continue
        plain = "(" not in r["name"]
        cur = best.get(r["slug"])
        if cur is None or (plain and not cur["_plain"]) or (plain == cur["_plain"] and r["rating"] < cur["rating"]):
            best[r["slug"]] = {**r, "_plain": plain}
    ratings = sorted((r["rating"] for r in rows), reverse=True)
    n = len(ratings)
    for r in best.values():
        pos = ratings.index(r["rating"])
        r["pct"] = round(1.0 - pos / (n - 1), 3) if n > 1 else 1.0
        r.pop("_plain", None)
    return best


@dataclass
class Rankings:
    """Public slices + model news, persisted. Thread-safe for the few writers (refresh tasks)."""
    path: object
    public: dict = field(default_factory=dict)      # {"fetched", "published", "error", "slices": {cat: [rows]}}
    news: dict = field(default_factory=dict)        # {"snapshot": [keys], "providers": [ids], "first_seen", "events"}
    last_force: float = 0.0

    def __post_init__(self):
        self._lock = threading.Lock()
        self._index: dict[str, dict[str, dict]] | None = None
        raw = read_json(self.path) or {}
        if isinstance(raw, dict):
            self.public = raw.get("public") if isinstance(raw.get("public"), dict) else {}
            self.news = raw.get("news") if isinstance(raw.get("news"), dict) else {}

    def save(self) -> None:
        try:
            write_private(self.path, json.dumps({"version": 1, "public": self.public, "news": self.news}))
        except OSError:
            pass

    # ------------------------------------------------------------ public signal
    def public_due(self, at: float | None = None) -> bool:
        return (at or now()) - float(self.public.get("fetched") or 0) >= PUBLIC_SECS

    async def fetch_public(self, http, url: str = LMARENA_FILTER) -> bool:
        """One GET per slice (Http enforces local mode; any failure keeps the previous data). True if refreshed."""
        async def one(cat: str):
            params = {"dataset": LMARENA_DATASET, "config": "text", "split": "latest",
                      "where": f"\"category\"='{cat}'", "orderby": "\"rating\" DESC", "length": str(TOP_N)}
            return cat, parse_lmarena(await http.get_json(url, mode="online", timeout=30, params=params))
        res = await asyncio.gather(*(one(c) for c in SLICES), return_exceptions=True)
        slices = {c: rows for r in res if not isinstance(r, BaseException) for c, rows in [r] if rows}
        t = now()
        with self._lock:
            if not slices:
                self.public = {**self.public, "error": "unreachable", "tried": t}
                self.save()
                return False
            pub = max((r["published"] for rows in slices.values() for r in rows if r["published"]), default="")
            self.public = {"fetched": t, "published": pub, "error": "",
                           "slices": {**(self.public.get("slices") or {}), **slices}}
            self._index = None
            self.save()
        return True

    def index(self) -> dict[str, dict[str, dict]]:
        if self._index is None:
            self._index = {c: fold(rows) for c, rows in (self.public.get("slices") or {}).items()
                           if isinstance(rows, list)}
        return self._index

    def public_of(self, m: Model, weights: dict[str, float]) -> tuple[float | None, list[dict]]:
        """Weighted percentile of the model in the public slices where it is listed (exact slug match)."""
        idx = self.index()
        s = slug(m.model_id)
        found, tot, acc = [], 0.0, 0.0
        for cat, w in weights.items():
            r = idx.get(cat, {}).get(s)
            if r is None:
                continue
            tot += w
            acc += w * r["pct"]
            found.append({"slice": cat, "name": r["name"], "rating": r["rating"], "rank": r["rank"],
                          "total": r["total"], "published": r["published"]})
        return (acc / tot if tot else None), found

    # ------------------------------------------------------------ news
    def update_news(self, models: list[Model]) -> list[dict]:
        """Diff the usable online models against the previous snapshot; returns the new events."""
        keys = {m.key: m for m in models if not m.local}
        t = now()
        with self._lock:
            prev = set(self.news.get("snapshot") or [])
            prev_provs = set(self.news.get("providers") or [])
            first = dict(self.news.get("first_seen") or {})
            events: list[dict] = []
            provs = {m.provider for m in keys.values()}
            if prev:
                for p in sorted(provs - prev_provs):
                    events.append({"t": t, "kind": "provider_added", "provider": p,
                                   "models": sum(1 for m in keys.values() if m.provider == p)})
                for k in sorted(set(keys) - prev):
                    m = keys[k]
                    if m.provider in prev_provs:
                        events.append({"t": t, "kind": "new", "key": k, "name": m.name, "provider": m.provider})
                        first[k] = t
                for k in sorted(prev - set(keys)):
                    p = k.split(":", 1)[0]
                    if p in provs:                     # a whole provider missing = key removed / down, not retired
                        events.append({"t": t, "kind": "gone", "key": k, "provider": p})
            for k in keys:
                first.setdefault(k, 0.0)               # 0 = present since the first snapshot (never « new »)
            first = {k: v for k, v in first.items() if k in keys or v > t - 90 * 86400}
            self.news = {"snapshot": sorted(keys), "providers": sorted(provs), "first_seen": first,
                         "events": ((self.news.get("events") or []) + events)[-MAX_EVENTS:], "updated": t}
            self.save()
        return events

    def is_new(self, key: str, at: float | None = None) -> bool:
        t0 = float((self.news.get("first_seen") or {}).get(key) or 0)
        return t0 > 0 and (at or now()) - t0 < NEW_DAYS * 86400

    def events(self, limit: int = 40) -> list[dict]:
        return list(reversed((self.news.get("events") or [])[-limit:]))

    # ------------------------------------------------------------ router
    def router_bonus(self, m: Model, role: str, lb: Leaderboard | None) -> tuple[float, str]:
        """Small bonus for the router (only while nothing is measured here for this task)."""
        dom = DOMAINS.get(ROLE_DOMAIN.get(role, ""), {})
        task = dom.get("task")
        e = lb.entry(m.key, task) if lb is not None and task else None
        if e is not None and e.n + e.pauses > 0:
            return 0.0, ""
        b, why = 0.0, []
        if self.is_new(m.key):
            b += NEW_BONUS
            why.append(f"new model, worth a try +{NEW_BONUS:.2f}")
        p, found = self.public_of(m, dom.get("public") or {})
        if p is not None:
            pb = PUBLIC_WEIGHT * (p - 0.5)
            b += pb
            why.append(f"LMArena {'/'.join(f['slice'] for f in found)} {pb:+.2f}")
        return b, ", ".join(why)


def table(rk: Rankings, models: list[Model], lb: Leaderboard | None, *, shown: int = SHOWN) -> list[dict]:
    """Per domain, the best usable models with the evidence behind each score."""
    t = now()
    out = []
    for dom, spec in DOMAINS.items():
        rows = []
        for m in models:
            if spec.get("formal") and unfit_reason(m):
                continue
            q = m.score(spec["cat"])
            sources: list[dict] = []
            p, found = rk.public_of(m, spec["public"])
            if found:
                sources.append({"kind": "public", "source": "LMArena", "license": LMARENA_LICENSE, "url": LMARENA_PAGE,
                                "rows": found})
            base = 0.5 * q + 0.5 * p if p is not None else q
            sources.append({"kind": "estimate", "value": round(q, 3), "family": m.est or ""})
            score, conf = base, 0.0
            e = lb.entry(m.key, spec["task"]) if lb is not None and spec.get("task") else None
            if e is not None and e.n + e.pauses > 0:
                conf = confidence(e)
                own = score_of(e)
                score = conf * own + (1 - conf) * base
                sources.insert(0, {"kind": "measured", "score": round(own, 3), "solved": e.total_ok,
                                   "tasks": e.total, "confidence": round(conf, 2)})
            rows.append({"key": m.key, "name": m.name, "provider": m.provider, "paid": m.paid, "local": m.local,
                         "score": round(score, 3), "evidence": "measured" if conf >= 0.5 else
                         "public" if p is not None else "estimate", "new": rk.is_new(m.key, t), "sources": sources})
        rows.sort(key=lambda r: -r["score"])
        out.append({"domain": dom, "task": spec.get("task"), "public_slices": list(spec["public"]),
                    "rows": rows[:shown]})
    return out
