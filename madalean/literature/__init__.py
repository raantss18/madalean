"""« Littérature d'abord » (session S-AX, DECISIONS D56, docs/LITERATURE.md).

Public Python API (also what the MCP exposure and the lemma graph call):

    from madalean import literature
    res = await literature.search(statement, ctx, literature.Budget.for_depth("quick"), text=words)
    for it in res.items:           # LiteratureItem: reference (retrieved record), verbatim quotes, Lean link
        ...
    res.cited_lemmas()             # items whose Lean statement compiles and that nothing proves yet
    it.node()                      # the cited-lemma node of the lemma graph

`search` never raises for a provider or a model failure, makes no request in Local mode, and is cached per
normalised statement + Lean/Mathlib versions + depth."""
from .engine import cache_key, search
from .formal import (check_conditional, conditional_statement, record_conditional, supersede, try_conditional,
                     upgrade, verdict_of)
from .types import (DEPTHS, STATUSES, Budget, LeanLink, LiteratureItem, LiteratureResult, QueryPlan, Quote, Reference,
                    SourceText)

__all__ = ["search", "mcp_search", "cache_key", "Budget", "LiteratureResult", "LiteratureItem", "Reference", "Quote", "LeanLink",
           "SourceText", "QueryPlan", "STATUSES", "DEPTHS", "conditional_statement", "check_conditional",
           "try_conditional", "record_conditional", "supersede", "upgrade", "verdict_of"]


async def mcp_search(ctx, query: str, k: int = 8) -> list[dict]:
    """The MCP tool `literature_search` (S-AZ, D58): a quick, bibliographic-only search — no Lean formalisation,
    no model call beyond the search's own rules; same verified-reference and verbatim-quote rules as `search`.
    Nothing in Local mode (the search itself makes no request then)."""
    res = await search("", ctx, Budget.for_depth("quick"), text=query, depth="quick", formalize=False,
                       owner="mcp-literature")
    out = []
    for it in res.items[: max(1, min(int(k or 8), 20))]:
        n = it.node()
        out.append({"citation": n["citation"], "quote": n["quote"], "origin": n["origin"], "label": n["label"],
                    "bibtex": it.bibtex})
    return out
