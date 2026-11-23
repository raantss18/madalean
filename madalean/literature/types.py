"""Typed results of the literature search (DECISIONS D56, docs/LITERATURE.md).

Everything a user sees comes from a retrieved record: a `Reference` is built from an API answer (zbMATH Open,
OpenAlex, Crossref, arXiv) or from the user's own Sources, never from a model; a `Quote` is a passage of a retrieved
text, string-matched against that text (`quotes.verify`). A model may only *propose* keywords or *pick* a passage
among numbered candidates; what it writes is never shown as a reference or a quotation.

Statuses of a cited result's Lean statement (`LeanLink.status`):
- ``in_mathlib``   Mathlib proves it (a Mathlib name closed the Lean statement under a strict check);
- ``proved``       a Lean proof of it is in the user's library (strict check);
- ``to_prove``     the Lean statement compiles, nothing proves it yet: a *cited lemma*; a proof that uses it is
                   « conditionnelle » and never « vérifiée »;
- ``unformalized`` no Lean statement that compiles (or formalization skipped / out of budget)."""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any

STATUSES = ("in_mathlib", "proved", "to_prove", "unformalized")
KINDS = ("journal", "book", "proceedings", "preprint", "thesis", "unknown")
TEXT_KINDS = ("abstract", "review", "summary", "fulltext")
DEPTHS = ("quick", "deep")


# ---------------------------------------------------------------- budget
@dataclass
class Budget:
    """Hard limits of one search: wall-clock seconds, HTTP requests, model calls, Lean checks, results kept,
    statements formalized. `cancel()` (or the deadline) stops the search at the next step; nothing is retried in
    a loop: every phase runs once."""
    seconds: float = 45.0
    requests: int = 10
    model_calls: int = 3
    lean_checks: int = 8
    items: int = 6
    formalize: int = 1
    deadline: float = 0.0
    used_requests: int = 0
    used_model_calls: int = 0
    used_lean_checks: int = 0
    _cancel: asyncio.Event | None = field(default=None, repr=False, compare=False)

    @classmethod
    def for_depth(cls, depth: str) -> "Budget":
        if depth == "deep":
            return cls(seconds=150.0, requests=24, model_calls=8, lean_checks=24, items=12, formalize=3)
        return cls()

    def start(self) -> "Budget":
        if not self.deadline:
            self.deadline = time.monotonic() + max(1.0, float(self.seconds))
        return self

    def cancel(self) -> None:
        if self._cancel is None:
            self._cancel = asyncio.Event()
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel is not None and self._cancel.is_set()

    def left(self) -> float:
        if not self.deadline:
            return float(self.seconds)
        return max(0.0, self.deadline - time.monotonic())

    @property
    def over(self) -> bool:
        return self.cancelled or (bool(self.deadline) and self.left() <= 0)

    def take(self, what: str) -> bool:
        """Spend one unit of `request` | `model` | `lean`; False (and nothing spent) when exhausted or over."""
        if self.over:
            return False
        if what == "request":
            if self.used_requests >= self.requests:
                return False
            self.used_requests += 1
        elif what == "model":
            if self.used_model_calls >= self.model_calls:
                return False
            self.used_model_calls += 1
        elif what == "lean":
            if self.used_lean_checks >= self.lean_checks:
                return False
            self.used_lean_checks += 1
        return True

    def usage(self) -> dict:
        return {"seconds": self.seconds, "requests": [self.used_requests, self.requests],
                "model_calls": [self.used_model_calls, self.model_calls],
                "lean_checks": [self.used_lean_checks, self.lean_checks]}


# ---------------------------------------------------------------- records
@dataclass
class SourceText:
    """One retrieved text of a work (what quotes are matched against)."""
    kind: str                       # abstract | review | summary | fulltext
    provider: str                   # zbmath | openalex | crossref | arxiv | sources
    text: str                       # cleaned plain text (tags removed, NFKC, single spaces)
    locator: str = ""               # « Theorem 2.1 », « p. 5 » (full text only)
    page: int | None = None
    licence: str = ""               # what allows us to quote it (see docs/LITERATURE.md §3)
    attribution: str = ""           # zbMATH reviewer, …
    suspect: bool = False           # addresses a model: never sent to one


@dataclass
class Reference:
    id: str                         # doi:… | arxiv:… | zbl:… | zbmath:… | openalex:… | source:<shelf>/<sid>
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    arxiv: str = ""
    zbl: str = ""
    zbmath: str = ""
    openalex: str = ""
    url: str = ""
    msc: list[str] = field(default_factory=list)
    kind: str = "unknown"           # journal | book | proceedings | preprint | thesis | unknown
    peer_reviewed: bool = False     # published in a journal / proceedings (venue from Crossref or zbMATH)
    confirmed_by: list[str] = field(default_factory=list)   # services that returned this record
    providers: list[str] = field(default_factory=list)
    shelf: str = ""                 # set when the reference is one of the user's Sources
    source_id: str = ""
    source_verified: bool = True    # a Source whose metadata was only guessed from its PDF: False
    csl: dict = field(default_factory=dict)                 # the record, as retrieved (CSL-JSON)
    oa: dict = field(default_factory=dict)

    def short(self) -> str:
        who = self.authors[0].split()[-1] if self.authors else ""
        more = " et al." if len(self.authors) > 2 else (f" & {self.authors[1].split()[-1]}" if len(self.authors) == 2
                                                         else "")
        return f"{who}{more} ({self.year or 's. d.'})".strip()


@dataclass
class Quote:
    """A passage of a retrieved text, verified verbatim (`start`/`end` index `SourceText.text` of `text_index`)."""
    text: str
    text_index: int                 # index into LiteratureItem.texts
    start: int
    end: int
    location: str                   # human locator: « résumé, phrase 2 », « Theorem 2.1, p. 5 », « recension zbMATH »
    picked_by: str = "rules"        # rules | model:<key> (the model only chose among numbered passages)
    score: float = 0.0


@dataclass
class LeanLink:
    name: str = ""                  # the Lean name of the cited lemma (`cited_…`)
    statement: str = ""             # Lean file ending with `:= by sorry` (empty when not formalized)
    compiled: bool = False
    status: str = "unformalized"
    mathlib_name: str = ""
    library_name: str = ""
    model: str = ""                 # who translated the quote into Lean (always to be re-read)
    note: str = ""                  # why unformalized (budget, no model, Lean refused…)
    child_dossier: str = ""         # « Prouver ce lemme » created this dossier


@dataclass
class LiteratureItem:
    id: str
    reference: Reference
    texts: list[SourceText] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
    lean: LeanLink = field(default_factory=LeanLink)
    score: float = 0.0
    matched: list[str] = field(default_factory=list)          # query keywords found in its title / texts
    bibtex: str = ""
    key: str = ""                   # BibTeX key proposed (the shelf may choose another one when added)
    origin: str = "literature"      # literature (search) | attachment (a file / URL the user gave, read once)
    label: str = ""                 # « Theorem 3.1 » when the source numbers it

    @property
    def is_cited_lemma(self) -> bool:
        return self.lean.status == "to_prove" and bool(self.lean.statement)

    def node(self) -> dict:
        """The cited-lemma node consumed by the lemma graph (S-AY): enough to state, cite and track it."""
        q = self.quotes[0] if self.quotes else None
        return {"id": self.id, "kind": "cited", "origin": self.origin, "label": self.label, "name": self.lean.name,
                "lean": self.lean.statement,
                "status": self.lean.status, "mathlib_name": self.lean.mathlib_name,
                "library_name": self.lean.library_name, "conditional": self.lean.status == "to_prove",
                "citation": {"ref": self.reference.id, "title": self.reference.title,
                             "authors": self.reference.authors, "year": self.reference.year,
                             "venue": self.reference.venue, "kind": self.reference.kind,
                             "peer_reviewed": self.reference.peer_reviewed},
                "quote": {"text": q.text, "location": q.location} if q else None}


@dataclass
class QueryPlan:
    keywords: list[str] = field(default_factory=list)          # deterministic, from the statement
    extra_keywords: list[str] = field(default_factory=list)    # proposed by a model (search terms only)
    lean_names: list[str] = field(default_factory=list)
    msc: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


@dataclass
class LiteratureResult:
    statement: str = ""
    depth: str = "quick"
    query: QueryPlan = field(default_factory=QueryPlan)
    items: list[LiteratureItem] = field(default_factory=list)
    mathlib: list[dict] = field(default_factory=list)          # related Mathlib declarations (RAG index), real names
    providers: dict = field(default_factory=dict)              # name -> {ok, count, error}
    rejected: dict = field(default_factory=dict)               # unresolved ids, invented passages, suspect texts…
    local_mode: bool = False
    cancelled: bool = False
    cached: bool = False
    message: str = ""               # i18n key of the outcome (« rien de fiable trouvé » …)
    started: float = field(default_factory=time.time)
    seconds: float = 0.0
    usage: dict = field(default_factory=dict)
    versions: dict = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return any(it.quotes for it in self.items)

    def cited_lemmas(self) -> list[LiteratureItem]:
        return [it for it in self.items if it.is_cited_lemma]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LiteratureResult":
        data = dict(data or {})
        items = []
        for raw in data.pop("items", []) or []:
            raw = dict(raw)
            ref = Reference(**_known(Reference, raw.pop("reference", {}) or {}))
            texts = [SourceText(**_known(SourceText, t)) for t in raw.pop("texts", []) or []]
            quotes = [Quote(**_known(Quote, q)) for q in raw.pop("quotes", []) or []]
            lean = LeanLink(**_known(LeanLink, raw.pop("lean", {}) or {}))
            items.append(LiteratureItem(reference=ref, texts=texts, quotes=quotes, lean=lean,
                                        **_known(LiteratureItem, raw)))
        q = QueryPlan(**_known(QueryPlan, data.pop("query", {}) or {}))
        return cls(items=items, query=q, **_known(cls, data))


def _known(cls, d: dict) -> dict:
    names = set(cls.__dataclass_fields__) - {"reference", "texts", "quotes", "lean", "items", "query", "_cancel"}
    return {k: v for k, v in (d or {}).items() if k in names}


def item_id(ref_id: str) -> str:
    return "L" + hashlib.sha1(ref_id.encode("utf-8")).hexdigest()[:10]


Json = dict[str, Any]
