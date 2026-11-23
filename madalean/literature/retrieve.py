"""Retrieval: zbMATH Open, OpenAlex, Crossref, arXiv (network), the user's Sources and the Mathlib index (local).

Network rules (on top of `research/fetch.py`, which already enforces https, public addresses, no cookies, a
contact-less User-Agent, per-host politeness and a short cache, and refuses everything in Local mode):
- `Guarded` lets each source reach ONLY its own host (`SOURCE_HOSTS`) and spends one request of the budget per call
  (no request once the budget or the deadline is reached, or once the search is cancelled);
- what is sent: the search words built from the statement (never the Lean file, a project text, a key or a name),
  or a DOI / arXiv id to confirm a record.
Every record kept comes from an API answer; a DOI is confirmed by Crossref when the budget allows (a DOI Crossref
does not know is dropped, and counted)."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import quote as urlquote
from urllib.parse import urlencode, urlsplit

from ..logs import get
from ..research import biblio, litsearch
from ..research.fetch import FetchError, LocalModeError
from . import quotes as Q
from .types import Budget, Reference, SourceText

log = get("literature")

SOURCE_HOSTS = {
    "zbmath": frozenset({"api.zbmath.org"}),
    "openalex": frozenset({"api.openalex.org"}),
    "crossref": frozenset({"api.crossref.org"}),
    "doi": frozenset({"doi.org"}),                    # the DOI handle API: does a non-Crossref DOI exist?
    "arxiv": frozenset({"export.arxiv.org"}),
}
ALL_HOSTS = frozenset().union(*SOURCE_HOSTS.values())
NETWORK_SOURCES = ("zbmath", "openalex", "arxiv", "crossref")
LICENCE = {
    "zbmath": "zbMATH Open (CC BY-SA 4.0), quoted with attribution",
    "openalex": "OpenAlex metadata (CC0); abstract as distributed by the publisher, short quotation",
    "crossref": "Crossref metadata; abstract as deposited by the publisher, short quotation",
    "arxiv": "arXiv metadata (CC0)",
    "sources": "your own copy (Sources)",
}
JSON_TYPES = litsearch.JSON_TYPES
ATOM_TYPES = ("application/atom+xml", "application/xml", "text/xml")


class BudgetExhausted(FetchError):
    def __init__(self, url: str = ""):
        super().__init__("budget", "literature budget exhausted", url=url)


class Guarded:
    """The research Fetcher seen through one source's host allow-list and the search budget."""

    def __init__(self, fetcher, budget: Budget, source: str):
        self.f, self.budget, self.source = fetcher, budget, source
        self.hosts = SOURCE_HOSTS[source]
        self.urls: list[str] = []

    async def get(self, url: str, *, mode: str, **kw):
        if mode == "local":
            raise LocalModeError(url)
        host = (urlsplit(url).hostname or "").lower()
        if host not in self.hosts:
            raise FetchError("blocked", f"{host!r} is not allowed for {self.source}", url=url)
        if not self.budget.take("request"):
            raise BudgetExhausted(url)
        self.urls.append(url)
        left = max(2.0, min(20.0, self.budget.left()))
        kw.setdefault("timeout", left)
        return await asyncio.wait_for(self.f.get(url, mode=mode, **kw), left + 2)


@dataclass
class Record:
    """One work as returned by one or more providers (before merging into a LiteratureItem)."""
    csl: dict
    providers: dict = field(default_factory=dict)          # provider -> rank
    texts: list[SourceText] = field(default_factory=list)
    oa: dict = field(default_factory=dict)
    zb_type: str = ""                                      # zbMATH document type (j / b / a …)
    crossref_type: str = ""
    shelf: str = ""
    source_id: str = ""
    source_verified: bool = True


# ---------------------------------------------------------------- provider searches
def _text(kind: str, provider: str, raw: str, attribution: str = "") -> SourceText | None:
    t = Q.clean(raw)
    if len(t) < 40:
        return None
    return SourceText(kind=kind, provider=provider, text=t, licence=LICENCE[provider], attribution=attribution,
                      suspect=Q.suspect(t))


async def search_zbmath(g: Guarded, q: str, mode: str, n: int) -> list[Record]:
    r = await g.get("https://api.zbmath.org/v1/document/_search?" + urlencode(
        {"search_string": q, "page": 0, "results_per_page": n}), mode=mode, types=JSON_TYPES)
    out = []
    for i, doc in enumerate(r.json().get("result") or []):
        if not isinstance(doc, dict):
            continue
        item = biblio.clean_csl(litsearch.zbmath_to_item(doc))
        if "contents unavailable" in item.get("title", "").lower():
            item["title"] = ""          # zbMATH's placeholder (licence conflict): the title must come from elsewhere
        if not item.get("title") and not item.get("DOI") and not item.get("arxiv"):
            continue
        item.pop("abstract", None)          # kept below with its kind (review vs. the authors' summary)
        rec = Record(item, {"zbmath": i}, zb_type=str((doc.get("document_type") or {}).get("code", "") or ""))
        for c in doc.get("editorial_contributions") or []:
            if not isinstance(c, dict):
                continue
            kind = c.get("contribution_type")
            txt = c.get("text") or ""
            if kind not in ("review", "summary") or "contents unavailable" in txt:
                continue
            who = (c.get("reviewer") or {}).get("name", "") if isinstance(c.get("reviewer"), dict) else ""
            st = _text(kind, "zbmath", txt, who)
            if st:
                rec.texts.append(st)
        out.append(rec)
    return out


async def search_openalex(g: Guarded, q: str, mode: str, n: int) -> list[Record]:
    r = await g.get("https://api.openalex.org/works?" + urlencode({"search": q, "per-page": n}), mode=mode,
                    types=JSON_TYPES)
    out = []
    for i, w in enumerate(r.json().get("results") or []):
        if not isinstance(w, dict):
            continue
        item = biblio.clean_csl(litsearch.openalex_to_item(w))
        if not item.get("title"):
            continue
        abstract = item.pop("abstract", "")
        rec = Record(item, {"openalex": i}, oa=litsearch.openalex_oa(w))
        st = _text("abstract", "openalex", abstract)
        if st:
            rec.texts.append(st)
        out.append(rec)
    return out


async def search_arxiv(g: Guarded, q: str, mode: str, n: int) -> list[Record]:
    words = [w for w in re.findall(r"[\w'-]+", q) if len(w) > 2 and w.lower() not in biblio.STOP][:6]
    terms = " AND ".join(f"all:{litsearch._arxiv_term(w)}" for w in words) or f"all:{litsearch._arxiv_term(q)}"
    r = await g.get("https://export.arxiv.org/api/query?" + urlencode(
        {"search_query": terms, "start": 0, "max_results": n, "sortBy": "relevance"}), mode=mode, types=ATOM_TYPES)
    out = []
    for i, it in enumerate(litsearch.parse_arxiv_atom(r.body)):
        abstract = it.pop("abstract", "")
        item = biblio.clean_csl({k: v for k, v in it.items() if not k.startswith("_")})
        rec = Record(item, {"arxiv": i}, oa={"is_oa": True, "status": "green",
                                              "url": f"https://arxiv.org/pdf/{it['arxiv']}"})
        st = _text("abstract", "arxiv", abstract)
        if st:
            rec.texts.append(st)
        out.append(rec)
    return out


SEARCHERS = {"zbmath": search_zbmath, "openalex": search_openalex, "arxiv": search_arxiv}


async def confirm_doi(g: Guarded, doi: str, mode: str) -> dict | None:
    """Crossref's record of a DOI: {type, venue, title, abstract} — None when Crossref does not know it (404)."""
    try:
        r = await g.get("https://api.crossref.org/works/" + urlquote(biblio.norm_doi(doi), safe="/:;()"),
                        mode=mode, types=JSON_TYPES)
    except FetchError as e:
        if e.status == 404:
            return None
        raise
    m = (r.json() or {}).get("message") or {}
    if not isinstance(m, dict) or not m.get("DOI"):
        return None
    ct = m.get("container-title") or []
    title = m.get("title") or []
    return {"type": str(m.get("type") or ""), "venue": (ct[0] if isinstance(ct, list) and ct else str(ct or "")),
            "title": (title[0] if isinstance(title, list) and title else str(title or "")),
            "abstract": str(m.get("abstract") or ""), "doi": biblio.norm_doi(m.get("DOI", "")),
            "volume": str(m.get("volume") or ""), "page": str(m.get("page") or "")}


async def doi_exists(g: Guarded, doi: str, mode: str) -> bool:
    """The DOI registry itself (`doi.org/api/handles`, no redirect to the publisher): True when the DOI is
    registered (DataCite DOIs: Zenodo, arXiv, theses are not in Crossref)."""
    try:
        r = await g.get("https://doi.org/api/handles/" + urlquote(biblio.norm_doi(doi), safe="/:;()"), mode=mode,
                        types=JSON_TYPES, ok_status=(200, 404))
    except FetchError as e:
        if e.status == 404:
            return False
        raise
    try:
        return r.status == 200 and int((r.json() or {}).get("responseCode", 0)) == 1
    except (ValueError, TypeError, AttributeError):
        return False


def title_matches(a: str, b: str) -> bool:
    ta, tb = set(biblio.norm_title(a).split()), set(biblio.norm_title(b).split())
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


# ---------------------------------------------------------------- merging
def merge(lists: list[list[Record]]) -> list[Record]:
    groups: list[Record] = []
    for recs in lists:
        for r in recs:
            tgt = next((g for g in groups if biblio.same_work(g.csl, r.csl)), None)
            if tgt is None:
                groups.append(r)
                continue
            tgt.csl = litsearch._merge_item(tgt.csl, r.csl)
            for p, rank in r.providers.items():
                tgt.providers.setdefault(p, rank)
            for t in r.texts:
                if not any(t.text == x.text for x in tgt.texts):
                    tgt.texts.append(t)
            if r.oa.get("is_oa") and not tgt.oa.get("is_oa"):
                tgt.oa = r.oa
            tgt.zb_type = tgt.zb_type or r.zb_type
    return groups


def classify(rec: Record) -> tuple[str, bool]:
    """(kind, peer_reviewed) from the venue that Crossref or zbMATH reported — never guessed from a model."""
    ct = rec.crossref_type
    if ct:
        if ct == "journal-article":
            return "journal", True
        if ct == "proceedings-article":
            return "proceedings", True
        if ct in ("book", "monograph", "book-chapter", "edited-book", "reference-book"):
            return "book", False
        if ct == "posted-content":
            return "preprint", False
        if ct == "dissertation":
            return "thesis", False
    if rec.zb_type:
        if rec.zb_type == "j":
            return "journal", True
        if rec.zb_type in ("b", "a"):
            return "book", False
    if rec.csl.get("arxiv") and set(rec.providers) <= {"arxiv", "openalex"}:
        return "preprint", False
    if rec.shelf:
        typ = rec.csl.get("type", "")
        if typ == "article-journal" and rec.csl.get("container-title") and rec.source_verified and \
                rec.csl.get("DOI"):
            return "journal", True
        if typ == "article" and rec.csl.get("arxiv"):
            return "preprint", False
    return "unknown", False


def reference_of(rec: Record) -> Reference:
    it = rec.csl
    rid = litsearch.result_id(it)
    if rid.startswith("t:") and rec.source_id:
        rid = f"source:{rec.shelf}/{rec.source_id}"
    if it.get("zbmath") and rid.startswith("t:"):
        rid = "zbmath:" + str(it["zbmath"])
    kind, peer = classify(rec)
    authors = []
    for a in it.get("author") or []:
        name = a.get("literal") or (" ".join(x for x in (a.get("given", ""), a.get("family", "")) if x))
        if name:
            authors.append(name.strip())
    url = it.get("URL") or (f"https://doi.org/{it['DOI']}" if it.get("DOI") else
                            f"https://arxiv.org/abs/{it['arxiv']}" if it.get("arxiv") else "")
    confirmed = sorted(p for p in rec.providers if p in ("zbmath", "openalex", "arxiv", "crossref"))
    return Reference(id=rid, title=it.get("title", ""), authors=authors, year=biblio.year_of(it),
                     venue=it.get("container-title", "") or (it.get("publisher", "") if kind == "book" else ""),
                     doi=it.get("DOI", ""), arxiv=it.get("arxiv", ""), zbl=it.get("zbl", ""),
                     zbmath=str(it.get("zbmath", "") or ""), openalex=it.get("openalex", ""), url=url,
                     msc=list(it.get("msc") or [])[:8], kind=kind, peer_reviewed=peer, confirmed_by=confirmed,
                     providers=sorted(rec.providers), shelf=rec.shelf, source_id=rec.source_id,
                     source_verified=rec.source_verified,
                     csl={k: v for k, v in it.items() if not k.startswith("_") and k != "abstract"}, oa=rec.oa)


# ---------------------------------------------------------------- local
async def local_sources(ctx, project_id: str, query: str, k: int = 8) -> list[Record]:
    """The user's Sources (project shelf + global shelf): full-text passages, theorem environments first."""
    try:
        from ..research.sources import GLOBAL, library
        lib = library(ctx)
        shelves = [GLOBAL]
        if project_id and ctx.projects.get(project_id) is not None:
            shelves.insert(0, project_id)
        hits = await lib.search(shelves, query, k=k * 2, semantic=False)
    except Exception as e:  # noqa: BLE001 (no research layer / no index: nothing local, never an error)
        log.info("local sources search failed: %s", e)
        return []
    out: dict[str, Record] = {}
    for h in hits:
        sid, shelf = h.get("source_id", ""), h.get("shelf", "")
        try:
            src = lib.get(shelf, sid)
        except Exception:  # noqa: BLE001
            continue
        rec = out.get(sid)
        if rec is None:
            rec = Record(dict(src.get("csl") or {}), {"sources": len(out)}, shelf=shelf, source_id=sid,
                         source_verified=bool(src.get("verified", True)), oa=dict(src.get("oa") or {}))
            out[sid] = rec
        st = _text("fulltext", "sources", h.get("text", ""))
        if st is None:
            continue
        st.locator = str(h.get("locator") or h.get("label") or "")[:80]
        st.page = h.get("page") if isinstance(h.get("page"), int) else None
        if h.get("kind") in ("theorem", "lemma", "proposition", "corollary"):
            rec.texts.insert(0, st)
        else:
            rec.texts.append(st)
    return list(out.values())[:k]


async def mathlib_related(ctx, ws_key: str, queries: list[str], k: int = 6) -> list[dict]:
    """Declarations of the workspace's Mathlib index for the search words (names that exist, with signatures)."""
    r = getattr(ctx, "retriever", None)
    if r is None or not ws_key:
        return []
    out: list[dict] = []
    for q in queries[:2]:
        try:
            res = await asyncio.wait_for(r.search(ws_key, q, k), 20)
        except Exception:  # noqa: BLE001
            continue
        for d in res or []:
            n = d.get("name") or ""
            if n and not any(n == x["name"] for x in out) and not d.get("deprecated"):
                out.append({"name": n, "signature": str(d.get("signature") or "")[:400],
                            "doc": str(d.get("doc") or d.get("docstring") or "")[:300],
                            "module": str(d.get("module") or "")})
    return out[:k]
