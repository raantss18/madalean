"""The small interface the problem graph (S-AY) expects from the literature package (S-AX).

S-AX exposes `literature.search(...)` with typed items. Until it is merged, this adapter looks for it and says
« unavailable » otherwise — the graph never invents a reference. Each item is mapped to the shape
`proofgraph.cited_node` reads (a dict or an object with these attributes):

    {"id": str, "title": str, "statement_nl": str, "lean": str (optional, Lean statement with sorry),
     "status": "cited" | "mathlib" | "proved",
     "citation": CSL-JSON item + {"verified": bool, "quote": verbatim text, "locator": "Thm 2.1"}}

Only `verified` references are kept by default (S-AX checks that the reference exists)."""
from __future__ import annotations

import inspect

from ..logs import get

log = get("literature_iface")


def _module():
    for name in ("madalean.literature", "madalean.research.literature"):
        try:
            mod = __import__(name, fromlist=["search"])
        except ImportError:
            continue
        if hasattr(mod, "search"):
            return mod
    return None


def _field(it, k, default=None):
    return it.get(k, default) if isinstance(it, dict) else getattr(it, k, default)


async def search(ctx, query: str, *, lean: str = "", limit: int = 5, verified_only: bool = True) -> list | None:
    """Items for `query`, or None when no literature package is installed. Never raises."""
    mod = _module()
    if mod is None:
        return None
    try:
        fn = mod.search
        kw = {k: v for k, v in {"ctx": ctx, "lean": lean, "limit": limit}.items()
              if k in inspect.signature(fn).parameters}
        res = fn(query, **kw)
        if inspect.isawaitable(res):
            res = await res
    except Exception as e:  # noqa: BLE001
        log.info("literature search failed: %s", e)
        return []
    items = list(_field(res, "items", res) or [])[:limit]
    out = []
    for it in items:
        cit = _field(it, "citation") or {}
        verified = cit.get("verified") if isinstance(cit, dict) else getattr(cit, "verified", False)
        if verified_only and not verified:
            continue
        out.append(it)
    return out
