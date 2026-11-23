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

__all__ = ["search", "cache_key", "Budget", "LiteratureResult", "LiteratureItem", "Reference", "Quote", "LeanLink",
           "SourceText", "QueryPlan", "STATUSES", "DEPTHS", "conditional_statement", "check_conditional",
           "try_conditional", "record_conditional", "supersede", "upgrade", "verdict_of"]
