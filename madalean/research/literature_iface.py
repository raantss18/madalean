"""The problem graph (S-AY) ← the literature package (S-AX, `madalean.literature`, docs/LITERATURE.md §6).

`search` runs `literature.search` (quick budget; no request in Local mode, cached by S-AX) and `provided` reads the
dossier's attachment digests (`attach.provided_items`, origin « attachment »). Both return items in the shape
`proofgraph.cited_node` reads:

    {"id", "title", "statement_nl", "lean" (statement with sorry, may be empty), "status" (S-AX's claim),
     "origin" (literature | attachment), "mathlib_name",
     "citation": CSL-JSON of the retrieved record + {verified, quote, locator, key}}

S-AX's status (« in_mathlib », « proved ») is only a claim here: the graph keeps such a node « cité » until Lean
proves it. Without the package (or on any failure) the answer is None / [] — the graph never invents a reference."""
from __future__ import annotations

from ..logs import get

log = get("literature_iface")


def _lit():
    try:
        from .. import literature
        return literature
    except ImportError:
        return None


def to_item(it) -> dict:
    """A `LiteratureItem` (or an already plain dict) → the graph's item shape."""
    if isinstance(it, dict):
        return it
    ref = it.reference
    q = it.quotes[0] if it.quotes else None
    csl = dict(ref.csl or {})
    csl.setdefault("title", ref.title)
    if ref.doi:
        csl.setdefault("DOI", ref.doi)
    if ref.url:
        csl.setdefault("URL", ref.url)
    if ref.arxiv:
        csl.setdefault("arxiv", ref.arxiv)
    if ref.year and "issued" not in csl:
        csl["issued"] = {"date-parts": [[ref.year]]}
    if ref.authors and "author" not in csl:
        csl["author"] = [{"literal": a} for a in ref.authors]
    csl.update({"verified": bool(getattr(ref, "source_verified", True)) and bool(ref.confirmed_by or ref.shelf
                                                                                  or it.origin == "attachment"),
                "quote": q.text if q else "", "locator": (it.label or (q.location if q else "")), "key": it.key})
    title = (it.label + " — " if it.label else "") + (ref.title or "")
    return {"id": it.id, "title": title[:200] or "résultat cité", "statement_nl": q.text if q else "",
            "lean": it.lean.statement or "", "status": it.lean.status, "origin": it.origin,
            "mathlib_name": it.lean.mathlib_name, "citation": csl}


async def search(ctx, query: str, *, lean: str = "", limit: int = 5, verified_only: bool = True) -> list | None:
    lit = _lit()
    if lit is None:
        return None
    try:
        res = await lit.search(lean or "", ctx, lit.Budget.for_depth("quick"), text=query, owner="graph-literature")
    except TypeError:                       # older signature without `owner`
        try:
            res = await lit.search(lean or "", ctx, lit.Budget.for_depth("quick"), text=query)
        except Exception as e:  # noqa: BLE001
            log.info("literature search failed: %s", e)
            return []
    except Exception as e:  # noqa: BLE001
        log.info("literature search failed: %s", e)
        return []
    out = [to_item(it) for it in list(getattr(res, "items", []) or [])[:limit]]
    return [x for x in out if x["citation"].get("verified") or not verified_only]


def provided(ctx, d) -> list[dict]:
    """« Résultats fournis »: the statements of the dossier's attachments (read once by S-AX)."""
    try:
        from ..literature import attach
        return [to_item(it) for it in attach.provided_items(ctx, d)][:20]
    except Exception as e:  # noqa: BLE001
        log.info("provided items unavailable: %s", e)
        return []
