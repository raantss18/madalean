"""Public Lean search services, used by the agent's optional `lean_search_online` tool (never in local mode).

Evaluated on 2026-11-21 with real requests:
- LeanSearch (https://leansearch.net) — POST /search {"query": [q], "num_results": n}: natural-language semantic
  search, works (≈1–3 s), answers with name, kind, signature, docstring, informal name, module.
- Loogle (https://loogle.lean-lang.org) — GET /json?q=…: Lean-syntax search (names, `_ + _ = _` patterns,
  constants), works; natural-language queries return an error.
- Moogle (https://www.moogle.ai) — TLS certificate error from this machine: treated as unavailable.
Both index a *recent* Mathlib: results must be checked against the workspace (read_declaration / lean_check).
Only the query text is sent (no statement, no file, no key)."""
from __future__ import annotations

import asyncio
import re

from .net import Http

LEANSEARCH_URL = "https://leansearch.net/search"
LOOGLE_URL = "https://loogle.lean-lang.org/json"


def looks_like_lean(q: str) -> bool:
    return bool(re.search(r"[_∀∃≤≥→↔∑∏⁻¹]|\b[A-Z][a-z]+\.[a-z_]|\w_\w|\?\w", q)) or q.strip().startswith(('"', "|-"))


async def leansearch(http: Http, query: str, k: int = 6) -> list[dict]:
    v = await http.post_json(LEANSEARCH_URL, {"query": [query], "num_results": k}, mode="online", timeout=20)
    out = []
    try:
        for item in (v or [[]])[0]:
            r = item.get("result") or {}
            name = r.get("name")
            name = ".".join(name) if isinstance(name, list) else str(name or "")
            mod = r.get("module_name")
            out.append({"name": name, "signature": (r.get("signature") or r.get("type") or "")[:400],
                        "doc": (r.get("docstring") or r.get("informal_name") or "")[:300],
                        "module": ".".join(mod) if isinstance(mod, list) else str(mod or ""), "source": "LeanSearch"})
    except (TypeError, AttributeError, IndexError):
        return []
    return out


async def loogle(http: Http, query: str, k: int = 6) -> list[dict]:
    v = await http.get_json(LOOGLE_URL, mode="online", timeout=20, params={"q": query})
    if not isinstance(v, dict) or v.get("error"):
        return []
    return [{"name": h.get("name", ""), "signature": (h.get("type") or "").strip()[:400], "doc": (h.get("doc") or "")[:300],
             "module": h.get("module", ""), "source": "Loogle"} for h in (v.get("hits") or [])[:k]]


async def search_online(http: Http, query: str, k: int = 6) -> tuple[list[dict], list[str]]:
    """(results, services that failed). Loogle only for Lean-looking queries."""
    tasks = {"LeanSearch": leansearch(http, query, k)}
    if looks_like_lean(query):
        tasks["Loogle"] = loogle(http, query, k)
    res = await asyncio.gather(*tasks.values(), return_exceptions=True)
    out, failed, seen = [], [], set()
    for name, r in zip(tasks, res):
        if isinstance(r, BaseException) or not r:
            failed.append(name)
            continue
        for x in r:
            if x["name"] not in seen:
                seen.add(x["name"])
                out.append(x)
    return out[: 2 * k], failed
