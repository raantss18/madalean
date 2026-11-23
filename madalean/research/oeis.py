"""OEIS look-up of the conjecture engine (S-AW, DECISIONS D55, docs/CONJECTURES.md §3.1).

One call: the official JSON search (`https://oeis.org/search?q=<terms>&fmt=json`), through the research layer's
only network client (`fetch.Fetcher`: https only, allow-listed host, no cookie, a contact-less client name, no
proxy from the environment). Rules:

- **Local mode → no request at all** (the client is not even called; `status: "off"`), also for a project marked
  « local only »;
- anonymous: no account, no key, nothing about the user or the project in the request — only the terms;
- polite: at most one request per 5 s to oeis.org (`fetch.MIN_INTERVAL`), one request per look-up, answers cached
  on disk (30 days for a hit, 1 day for « nothing found ») and in memory;
- an entry is a match only when EVERY computed term agrees with the entry's listed terms where they overlap (the
  search itself only matches the first terms sent); the others are reported as `rejected` with the first index
  that differs (journal).

LMFDB is not queried: its API (lmfdb.org/api, declared beta) is keyed by object fields, not by a list of terms, so
it has no look-up that fits this step; see docs/CONJECTURES.md §3.1."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote

from .fetch import FetchError, Fetcher

HOST = "oeis.org"
SEARCH = "https://oeis.org/search?q={q}&fmt=json"
TTL_HIT = 30 * 86400.0
TTL_MISS = 86400.0
QUERY_TERMS = 14
MIN_TERMS = 6
MAX_QUERY_CHARS = 160
MAX_ENTRIES = 5


def query_terms(terms: list[int]) -> list[int]:
    """The terms sent: the first ones, as many as fit (OEIS matches consecutive terms anywhere in an entry)."""
    out: list[int] = []
    size = 0
    for t in terms[:QUERY_TERMS]:
        size += len(str(t)) + 1
        if size > MAX_QUERY_CHARS:
            break
        out.append(t)
    return out


def search_url(terms: list[int]) -> str:
    return SEARCH.format(q=quote(",".join(str(t) for t in query_terms(terms)), safe=","))


def parse(body) -> list[dict]:
    """Entries of an OEIS JSON answer (a list of entries; older answers wrap it in {"results": […]}; null or a
    count without results when nothing matches)."""
    if isinstance(body, dict):
        body = body.get("results")
    out = []
    for e in body if isinstance(body, list) else []:
        if not isinstance(e, dict) or not isinstance(e.get("number"), int):
            continue
        data = []
        for x in str(e.get("data", "")).split(","):
            try:
                data.append(int(x))
            except ValueError:
                break
        offset = 0
        try:
            offset = int(str(e.get("offset", "0")).split(",")[0])
        except ValueError:
            pass
        num = f"A{e['number']:06d}"
        out.append({"number": num, "name": str(e.get("name", ""))[:300], "offset": offset, "data": data,
                    "keywords": [k for k in str(e.get("keyword", "")).split(",") if k][:12],
                    "formulas": [str(f)[:300] for f in (e.get("formula") or [])[:4] if isinstance(f, str)],
                    "url": f"https://oeis.org/{num}"})
    return out


def align(terms: list[int], entry: dict) -> dict:
    """Where the computed terms sit in an entry: {"ok", "pos", "matched"} or {"ok": False, "differs_at": i}."""
    data = entry["data"]
    best = {"ok": False, "differs_at": 0, "matched": 0}
    need = min(MIN_TERMS, len(terms))
    for pos in range(len(data)):
        overlap = min(len(terms), len(data) - pos)
        if overlap < need:
            break
        k = 0
        while k < overlap and terms[k] == data[pos + k]:
            k += 1
        if k == overlap:
            return {"ok": True, "pos": pos, "matched": overlap}
        if k > best["matched"]:
            best = {"ok": False, "differs_at": k, "matched": k}
    return best


class Oeis:
    def __init__(self, fetcher: Fetcher | None = None, cache_dir: Path | None = None):
        self.fetcher = fetcher or Fetcher()
        self.cache_dir = cache_dir
        self.memory: dict[str, tuple[float, list[dict]]] = {}

    def _cache_file(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")

    def _cached(self, url: str) -> list[dict] | None:
        hit = self.memory.get(url)
        if hit is None:
            f = self._cache_file(url)
            try:
                d = json.loads(f.read_text(encoding="utf-8")) if f is not None else None
            except (OSError, ValueError):
                d = None
            if isinstance(d, dict) and isinstance(d.get("entries"), list) and d.get("url") == url:
                hit = (float(d.get("t", 0)), d["entries"])
                self.memory[url] = hit
        if hit is None:
            return None
        age = time.time() - hit[0]
        return hit[1] if age < (TTL_HIT if hit[1] else TTL_MISS) else None

    def _store(self, url: str, entries: list[dict]) -> None:
        self.memory[url] = (time.time(), entries)
        if len(self.memory) > 200:
            self.memory.pop(next(iter(self.memory)))
        f = self._cache_file(url)
        if f is None:
            return
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps({"t": time.time(), "url": url, "entries": entries}), encoding="utf-8")
            tmp.replace(f)
        except OSError:
            pass

    async def lookup(self, terms: list[int], *, mode: str, n0: int = 0) -> dict:
        """{status: ok | none | off | too_short | error, matches, rejected, url, cached, error}. `matches` carry
        `shift` (OEIS index = n + shift) and `matched` (number of computed terms that agree)."""
        out = {"status": "off", "matches": [], "rejected": [], "url": "", "cached": False, "error": ""}
        if mode == "local":
            return out                                   # Local mode: nothing leaves this machine, not even a probe
        if len(terms) < MIN_TERMS or len(set(terms)) < 3:
            out["status"] = "too_short"
            return out
        url = search_url(terms)
        out["url"] = url
        entries = self._cached(url)
        if entries is None:
            try:
                r = await self.fetcher.get(url, mode=mode, policy="api", accept="application/json", cache=False,
                                           types=("application/json", "text/plain", "text/json"), timeout=25,
                                           max_bytes=4 * 1024 * 1024)
                entries = parse(r.json())
            except FetchError as e:
                out["status"], out["error"] = ("off" if e.kind == "local_mode" else "error"), e.kind
                return out
            except ValueError:
                out["status"], out["error"] = "error", "bad_answer"
                return out
            entries = entries[:MAX_ENTRIES]
            self._store(url, entries)
        else:
            out["cached"] = True
        for e in entries[:MAX_ENTRIES]:
            a = align(terms, e)
            brief = {k: e[k] for k in ("number", "name", "offset", "keywords", "formulas", "url")}
            brief["data"] = [str(x) for x in e["data"][:24]]
            if a["ok"]:
                out["matches"].append({**brief, "matched": a["matched"], "shift": e["offset"] + a["pos"] - n0})
            else:
                out["rejected"].append({**brief, "differs_at": n0 + a["differs_at"], "matched": a["matched"]})
        out["status"] = "ok" if out["matches"] else "none"
        return out

    async def close(self) -> None:
        await self.fetcher.close()
