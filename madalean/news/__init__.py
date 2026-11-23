"""« Actualités »: a permanent mathematical watch (session S-AV, DECISIONS D54, docs/NEWS.md).

- `registry.py`  the sources (endpoint, parser, licence / terms, politeness), all public, keyless, machine-readable;
- `parsers.py`   RSS / Atom, arXiv API, Stack Exchange API, GitHub REST API, the Erdős problems table → normalised items
                 (plain text only: markup, control characters and e-mail addresses are removed at the door);
- `branches.py`  tagging by branch of mathematics (arXiv categories, MSC codes, MathOverflow tags, keyword rules);
- `store.py`     bounded SQLite store with full-text search, deduplication, retention, read / saved flags;
- `relevance.py` « pour mes projets »: local matching against the projects' own texts (nothing leaves the machine);
- `summarize.py` optional short French summary by a free online model; the item's text is DATA, never instructions;
- `service.py`   settings, conditional fetches with backoff, the periodic refresh, the demo data.

Web content is untrusted: nothing fetched here is ever executed, rendered as HTML or followed as an instruction."""
