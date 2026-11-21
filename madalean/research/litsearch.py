"""Scholarly API clients (identifier lookup) and literature search.

Lookup by identifier: DOI (doi.org content negotiation → Crossref / DataCite CSL-JSON), arXiv id (arXiv API +
e-print source), ISBN (OpenLibrary), zbMATH Open id / Zbl number, OpenAlex (open-access status, related / cited by /
references), URL (recognised identifiers, else the page's `citation_*` meta tags — metadata only).

Search: one query → arXiv, zbMATH Open, Crossref, OpenAlex (+ Semantic Scholar, keyless, often rate-limited) in
parallel → merged (same DOI / arXiv id / title+year+first author), deduplicated, ranked by reciprocal-rank fusion
plus agreement between providers and title match. Only the query leaves the machine.

Model-assisted reading list: the brain turns a research question into queries, reads the abstracts of the merged
results and picks a short annotated list. Every returned item is an API result BY CONSTRUCTION: the model only
returns candidate ids (`R3`), which are looked up in the candidate table; unknown ids are dropped and counted; the
record shown is the API's, never the model's text."""
from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote, urlencode, urlsplit

from . import biblio
from .fetch import Fetcher, FetchError
from .safety import UNTRUSTED_RULE, parse_xml, wrap_untrusted

ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom",
        "os": "http://a9.com/-/spec/opensearch/1.1/"}
CSL_ACCEPT = "application/vnd.citationstyles.csl+json"
JSON_TYPES = ("application/json", "application/vnd.citationstyles.csl+json", "application/citeproc+json",
              "text/plain", "application/x-javascript")
EPRINT_TYPES = ("application/gzip", "application/x-gzip", "application/x-eprint-tar", "application/x-eprint",
                "application/x-tar", "application/pdf", "application/octet-stream")
PROVIDERS = ("arxiv", "zbmath", "crossref", "openalex", "semanticscholar")


class NotFound(Exception):
    pass


# ================================================================ identifier detection
def detect_identifier(text: str) -> tuple[str, str]:
    """(kind, normalised id) for what the user typed: doi | arxiv | isbn | zbl | zbmath | openalex | url | ''."""
    t = (text or "").strip()
    if not t:
        return "", ""
    low = t.lower()
    if low.startswith(("https://", "http://")):
        u = urlsplit(t)
        host = (u.hostname or "").lower()
        if host.endswith("arxiv.org"):
            m = re.search(r"/(?:abs|pdf|src|e-print)/(.+?)(?:\.pdf)?$", u.path)
            if m and biblio.norm_arxiv(m.group(1)):
                return "arxiv", biblio.norm_arxiv(m.group(1)) + (re.search(r"v\d+$", m.group(1)) or [""])[0]
        if host in ("doi.org", "dx.doi.org"):
            return "doi", biblio.norm_doi(u.path.lstrip("/"))
        if host.endswith("zbmath.org"):
            m = re.search(r"(?:an:|q=an%3A|q=an:)(\d{4}\.\d{5})", t) or re.search(r"/(\d{4}\.\d{5})", t)
            if m:
                return "zbl", m.group(1)
            m = re.search(r"zbmath\.org/(\d{5,9})", t)
            if m:
                return "zbmath", m.group(1)
        if host.endswith("openalex.org"):
            m = re.search(r"(W\d+)", t)
            if m:
                return "openalex", m.group(1)
        m = biblio.DOI_RE.search(t)
        if m:
            return "doi", biblio.norm_doi(m.group(1))
        return "url", t
    if re.match(r"^(doi:\s*)?10\.\d{4,9}/\S+$", t, re.I):
        return "doi", biblio.norm_doi(t)
    m = re.match(r"^(?:arxiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)$", t, re.I)
    if m:
        return "arxiv", m.group(1)
    m = re.match(r"^(?:zbl:?\s*)?(\d{4}\.\d{5})$", t, re.I)
    if m:
        return "zbl", m.group(1)
    m = re.match(r"^(?:zbmath:?\s*)(\d{5,9})$", t, re.I)
    if m:
        return "zbmath", m.group(1)
    digits = re.sub(r"[\s-]", "", t)
    if re.match(r"^(?:isbn:?)?(\d{9}[\dXx]|\d{13})$", digits, re.I):
        d = re.sub(r"(?i)^isbn:?", "", digits).upper()
        if _isbn_ok(d):
            return "isbn", d
    if re.match(r"^W\d{4,12}$", t):
        return "openalex", t
    return "", ""


def _isbn_ok(d: str) -> bool:
    if len(d) == 10:
        s = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(d))
        return s % 11 == 0
    if len(d) == 13 and d.isdigit():
        s = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(d))
        return s % 10 == 0
    return False


# ================================================================ lookups
@dataclass
class Found:
    item: dict                                     # CSL record (+ arxiv/zbl/msc/openalex)
    via: str
    oa: dict = field(default_factory=dict)          # {is_oa, url, status}
    eprint: bool = False                            # arXiv: source archive available


async def by_doi(f: Fetcher, doi: str, mode: str) -> Found:
    doi = biblio.norm_doi(doi)
    try:
        r = await f.get("https://doi.org/" + quote(doi, safe="/:;()"), mode=mode, accept=CSL_ACCEPT, types=JSON_TYPES)
        raw = r.json()
    except FetchError as e:
        if e.status == 404:
            raise NotFound(doi)
        raise
    except ValueError:
        raise NotFound(doi)
    item = biblio.clean_csl(raw)
    if not item.get("title"):
        raise NotFound(doi)
    item["DOI"] = doi
    if doi.startswith("10.48550/arxiv."):
        item["arxiv"] = doi.split("arxiv.", 1)[1]
    return Found(item, "doi")


def parse_arxiv_atom(xml: bytes) -> list[dict]:
    root = parse_xml(xml)
    out = []
    for e in root.findall("a:entry", ATOM):
        eid = (e.findtext("a:id", default="", namespaces=ATOM) or "").strip()
        title = re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=ATOM) or "").strip()
        if not eid or not title or title.lower() == "error":
            continue
        aid = eid.rsplit("/abs/", 1)[-1]
        base = biblio.norm_arxiv(aid)
        authors = []
        for a in e.findall("a:author", ATOM):
            name = (a.findtext("a:name", default="", namespaces=ATOM) or "").strip()
            if name:
                parts = name.split()
                authors.append({"family": parts[-1], "given": " ".join(parts[:-1])} if len(parts) > 1 else
                               {"literal": name})
        pub = e.findtext("a:published", default="", namespaces=ATOM) or ""
        y = re.match(r"(\d{4})-(\d{2})", pub)
        cats = [c.get("term") for c in e.findall("a:category", ATOM) if c.get("term")]
        item = {"type": "article", "title": title, "author": authors, "arxiv": base,
                "abstract": re.sub(r"\s+", " ", e.findtext("a:summary", default="", namespaces=ATOM) or "").strip(),
                "URL": f"https://arxiv.org/abs/{base}", "number": f"arXiv:{base}", "publisher": "arXiv",
                "_categories": cats, "_version": (re.search(r"v(\d+)$", aid) or [None, ""])[1]}
        if y:
            item["issued"] = {"date-parts": [[int(y.group(1)), int(y.group(2))]]}
        doi = e.findtext("x:doi", default="", namespaces=ATOM)
        if doi:
            item["DOI"] = biblio.norm_doi(doi)
        jref = e.findtext("x:journal_ref", default="", namespaces=ATOM)
        if jref:
            item["note"] = re.sub(r"\s+", " ", jref).strip()
        comment = e.findtext("x:comment", default="", namespaces=ATOM)
        if comment:
            item["_comment"] = re.sub(r"\s+", " ", comment).strip()[:300]
        out.append(item)
    return out


async def by_arxiv(f: Fetcher, aid: str, mode: str) -> Found:
    base = biblio.norm_arxiv(aid)
    if not base:
        raise NotFound(aid)
    r = await f.get("https://export.arxiv.org/api/query?" + urlencode({"id_list": base, "max_results": 1}),
                    mode=mode, types=("application/atom+xml", "application/xml", "text/xml"))
    items = parse_arxiv_atom(r.body)
    if not items:
        raise NotFound(aid)
    item = items[0]
    return Found(item, "arxiv", {"is_oa": True, "url": f"https://arxiv.org/pdf/{base}", "status": "green"}, True)


async def arxiv_source(f: Fetcher, aid: str, mode: str) -> tuple[bytes, str]:
    """The e-print (source archive, or the PDF for PDF-only submissions). Returns (bytes, content-type)."""
    base = biblio.norm_arxiv(aid)
    r = await f.get(f"https://arxiv.org/src/{base}", mode=mode, types=EPRINT_TYPES, max_bytes=40 * 1024 * 1024,
                    timeout=90, cache=False)
    return r.body, r.content_type


async def arxiv_pdf(f: Fetcher, aid: str, mode: str) -> bytes:
    base = biblio.norm_arxiv(aid)
    r = await f.get(f"https://arxiv.org/pdf/{base}", mode=mode, types=("application/pdf",),
                    max_bytes=50 * 1024 * 1024, timeout=90, cache=False)
    return r.body


async def by_isbn(f: Fetcher, isbn: str, mode: str) -> Found:
    r = await f.get("https://openlibrary.org/api/books?" + urlencode({"bibkeys": f"ISBN:{isbn}", "format": "json",
                                                                     "jscmd": "data"}), mode=mode, types=JSON_TYPES)
    data = r.json().get(f"ISBN:{isbn}")
    if not data:
        raise NotFound(isbn)
    item = {"type": "book", "title": data.get("title", "") + (": " + data["subtitle"] if data.get("subtitle") else ""),
            "ISBN": isbn, "author": [], "URL": data.get("url", "")}
    for a in data.get("authors") or []:
        parts = (a.get("name") or "").split()
        if parts:
            item["author"].append({"family": parts[-1], "given": " ".join(parts[:-1])})
    pubs = [p.get("name") for p in data.get("publishers") or [] if p.get("name")]
    if pubs:
        item["publisher"] = pubs[0]
    places = [p.get("name") for p in data.get("publish_places") or [] if p.get("name")]
    if places:
        item["publisher-place"] = places[0]
    y = re.search(r"\d{4}", data.get("publish_date", ""))
    if y:
        item["issued"] = {"date-parts": [[int(y.group(0))]]}
    if data.get("number_of_pages"):
        item["number-of-pages"] = str(data["number_of_pages"])
    return Found(biblio.clean_csl(item) | {"ISBN": isbn}, "isbn")


def zbmath_to_item(doc: dict) -> dict:
    t = doc.get("title") or {}
    title = t.get("title") if isinstance(t, dict) else str(t)
    item: dict = {"title": re.sub(r"\s+", " ", title or "").strip(), "zbmath": str(doc.get("id", "")),
                  "zbl": doc.get("identifier") or "", "author": []}
    for a in ((doc.get("contributors") or {}).get("authors") or []):
        name = a.get("name") or ""
        fam, _, given = name.partition(",")
        item["author"].append({"family": fam.strip(), "given": given.strip()} if given else {"literal": name})
    y = re.search(r"\d{4}", str(doc.get("year") or ""))
    if y:
        item["issued"] = {"date-parts": [[int(y.group(0))]]}
    item["msc"] = [m.get("code") for m in doc.get("msc") or [] if m.get("code")][:12]
    dt = (doc.get("document_type") or {}).get("code", "")
    src = doc.get("source") or {}
    series = src.get("series") or []
    if dt == "j" or series:
        item["type"] = "article-journal"
        if series and isinstance(series[0], dict):
            s0 = series[0]
            item["container-title"] = s0.get("short_title") or s0.get("title") or ""
            if s0.get("volume"):
                item["volume"] = str(s0["volume"])
            if s0.get("issue"):
                item["issue"] = str(s0["issue"])
    elif dt == "b":
        item["type"] = "book"
    elif dt == "a":
        item["type"] = "chapter"
        item["container-title"] = (src.get("source") or "")[:300]
    else:
        item["type"] = "document"
    if src.get("pages"):
        item["page"] = str(src["pages"])
    books = src.get("book") or []
    if books and isinstance(books[0], dict) and books[0].get("publisher"):
        item["publisher"] = books[0]["publisher"]
    for link in doc.get("links") or []:
        if isinstance(link, dict) and link.get("type") == "doi" and link.get("identifier"):
            item["DOI"] = biblio.norm_doi(link["identifier"])
        if isinstance(link, dict) and link.get("type") == "arxiv" and link.get("identifier"):
            item["arxiv"] = biblio.norm_arxiv(link["identifier"])
    rev = [c.get("text") for c in doc.get("editorial_contributions") or [] if c.get("contribution_type") in
           ("review", "summary") and c.get("text") and "contents unavailable" not in c.get("text", "")]
    if rev:
        item["abstract"] = rev[0][:3000]
    item["URL"] = doc.get("zbmath_url") or f"https://zbmath.org/{doc.get('id', '')}"
    return item


async def by_zbmath(f: Fetcher, ident: str, kind: str, mode: str) -> Found:
    if kind == "zbmath":
        r = await f.get(f"https://api.zbmath.org/v1/document/{int(ident)}", mode=mode, types=JSON_TYPES)
        doc = r.json().get("result")
    else:
        r = await f.get("https://api.zbmath.org/v1/document/_search?" + urlencode(
            {"search_string": f"an:{ident}", "page": 0, "results_per_page": 1}), mode=mode, types=JSON_TYPES)
        res = r.json().get("result") or []
        doc = res[0] if res else None
    if not doc:
        raise NotFound(ident)
    return Found(biblio.clean_csl(zbmath_to_item(doc)), "zbmath")


def openalex_to_item(w: dict) -> dict:
    item: dict = {"title": re.sub(r"<[^>]+>", "", w.get("display_name") or w.get("title") or ""), "author": [],
                  "openalex": (w.get("id") or "").rsplit("/", 1)[-1]}
    for a in w.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if name:
            parts = name.split()
            item["author"].append({"family": parts[-1], "given": " ".join(parts[:-1])} if len(parts) > 1 else
                                  {"literal": name})
    if w.get("publication_year"):
        item["issued"] = {"date-parts": [[int(w["publication_year"])]]}
    if w.get("doi"):
        item["DOI"] = biblio.norm_doi(w["doi"])
    src = ((w.get("primary_location") or {}).get("source") or {})
    if src.get("display_name"):
        item["container-title"] = src["display_name"]
    b = w.get("biblio") or {}
    if b.get("volume"):
        item["volume"] = str(b["volume"])
    if b.get("issue"):
        item["issue"] = str(b["issue"])
    if b.get("first_page"):
        item["page"] = str(b["first_page"]) + (f"-{b['last_page']}" if b.get("last_page") else "")
    item["type"] = {"article": "article-journal", "book": "book", "book-chapter": "chapter",
                    "preprint": "article", "dissertation": "thesis", "report": "report"}.get(w.get("type", ""),
                                                                                             "document")
    ids = w.get("ids") or {}
    for loc in w.get("locations") or []:
        u = (loc.get("landing_page_url") or "") + " " + (loc.get("pdf_url") or "")
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s/]+?)(?:v\d+)?(?:\.pdf)?(?:\s|$)", u)
        if m and biblio.norm_arxiv(m.group(1)):
            item["arxiv"] = biblio.norm_arxiv(m.group(1))
            break
    if ids.get("openalex"):
        item["openalex"] = ids["openalex"].rsplit("/", 1)[-1]
    abstract = inverted_abstract(w.get("abstract_inverted_index"))
    if abstract:
        item["abstract"] = abstract
    return item


def inverted_abstract(inv) -> str:
    if not isinstance(inv, dict):
        return ""
    pos = []
    for word, idxs in inv.items():
        for i in idxs or []:
            if isinstance(i, int) and 0 <= i < 5000:
                pos.append((i, word))
    return " ".join(w for _i, w in sorted(pos))[:5000]


def openalex_oa(w: dict) -> dict:
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    url = best.get("pdf_url") or ""
    return {"is_oa": bool(oa.get("is_oa")), "status": oa.get("oa_status") or "", "url": url,
            "landing": best.get("landing_page_url") or oa.get("oa_url") or ""}


async def openalex_work(f: Fetcher, ident: str, mode: str) -> dict:
    """OpenAlex work by W-id or DOI (raw JSON)."""
    if ident.upper().startswith("W"):
        url = f"https://api.openalex.org/works/{ident}"
    else:
        url = "https://api.openalex.org/works/doi:" + quote(biblio.norm_doi(ident), safe="/:;()")
    try:
        r = await f.get(url, mode=mode, types=JSON_TYPES)
    except FetchError as e:
        if e.status == 404:
            raise NotFound(ident)
        raise
    return r.json()


async def by_openalex(f: Fetcher, ident: str, mode: str) -> Found:
    w = await openalex_work(f, ident, mode)
    return Found(biblio.clean_csl(openalex_to_item(w)), "openalex", openalex_oa(w))


async def oa_status(f: Fetcher, item: dict, mode: str) -> dict:
    """Open-access status of a record (Unpaywall data through OpenAlex). {} when unknown."""
    if item.get("arxiv"):
        return {"is_oa": True, "status": "green", "url": f"https://arxiv.org/pdf/{item['arxiv']}"}
    if not item.get("DOI"):
        return {}
    try:
        return openalex_oa(await openalex_work(f, item["DOI"], mode))
    except (NotFound, FetchError, ValueError):
        return {}


_META = re.compile(r"<meta\s+[^>]*?(?:name|property)\s*=\s*[\"']([^\"']+)[\"'][^>]*?content\s*=\s*[\"']([^\"']*)[\"']",
                   re.I)
_META2 = re.compile(r"<meta\s+[^>]*?content\s*=\s*[\"']([^\"']*)[\"'][^>]*?(?:name|property)\s*=\s*[\"']([^\"']+)[\"']",
                    re.I)


async def by_url(f: Fetcher, url: str, mode: str) -> Found:
    """Metadata of a web page (Highwire `citation_*` / Dublin Core meta tags). Never downloads a full text."""
    r = await f.get(url, mode=mode, policy="public", types=("text/html", "application/xhtml+xml"),
                    max_bytes=3 * 1024 * 1024, timeout=20)
    page = r.body[:3 * 1024 * 1024].decode("utf-8", "replace")
    meta: dict[str, list[str]] = {}
    for name, content in _META.findall(page):
        meta.setdefault(name.lower(), []).append(html.unescape(content).strip())
    for content, name in _META2.findall(page):
        meta.setdefault(name.lower(), []).append(html.unescape(content).strip())
    doi = (meta.get("citation_doi") or meta.get("dc.identifier") or [""])[0]
    if doi and biblio.DOI_RE.search(doi):
        try:
            return await by_doi(f, biblio.DOI_RE.search(doi).group(1), mode)
        except (NotFound, FetchError):
            pass
    title = (meta.get("citation_title") or meta.get("dc.title") or meta.get("og:title") or [""])[0]
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    if not title:
        raise NotFound(url)
    item: dict = {"type": "webpage" if not meta.get("citation_journal_title") else "article-journal",
                  "title": title[:500], "URL": url, "author": []}
    for a in (meta.get("citation_author") or meta.get("dc.creator") or [])[:50]:
        fam, _, given = a.partition(",")
        item["author"].append({"family": fam.strip(), "given": given.strip()} if given else
                              ({"family": a.split()[-1], "given": " ".join(a.split()[:-1])} if a.split() else
                               {"literal": a}))
    date = (meta.get("citation_publication_date") or meta.get("citation_date") or meta.get("dc.date") or [""])[0]
    y = re.search(r"\d{4}", date)
    if y:
        item["issued"] = {"date-parts": [[int(y.group(0))]]}
    if meta.get("citation_journal_title"):
        item["container-title"] = meta["citation_journal_title"][0]
    for k, ck in (("citation_volume", "volume"), ("citation_issue", "issue"), ("citation_publisher", "publisher")):
        if meta.get(k):
            item[ck] = meta[k][0]
    pdf = (meta.get("citation_pdf_url") or [""])[0]
    found = Found(biblio.clean_csl(item), "url")
    if pdf.startswith("https://"):
        found.oa = {"is_oa": None, "status": "unknown", "url": "", "landing": url, "page_pdf": pdf}
    return found


async def resolve(f: Fetcher, text: str, mode: str) -> Found:
    kind, ident = detect_identifier(text)
    if kind == "doi":
        found = await by_doi(f, ident, mode)
        if not found.item.get("arxiv"):
            found.oa = await oa_status(f, found.item, mode)
        return found
    if kind == "arxiv":
        return await by_arxiv(f, ident, mode)
    if kind == "isbn":
        return await by_isbn(f, ident, mode)
    if kind in ("zbl", "zbmath"):
        found = await by_zbmath(f, ident, kind, mode)
        if found.item.get("DOI"):
            found.oa = await oa_status(f, found.item, mode)
        return found
    if kind == "openalex":
        return await by_openalex(f, ident, mode)
    if kind == "url":
        return await by_url(f, ident, mode)
    raise NotFound(text)


async def download_oa_pdf(f: Fetcher, oa: dict, mode: str) -> bytes:
    """Only when the API reported the work as open access and gave a PDF URL."""
    if not oa.get("is_oa") or not str(oa.get("url", "")).startswith("https://"):
        raise NotFound("not open access")
    r = await f.get(oa["url"], mode=mode, policy="public", types=("application/pdf", "application/octet-stream"),
                    max_bytes=50 * 1024 * 1024, timeout=90, cache=False)
    if not r.body.startswith(b"%PDF"):
        raise FetchError("bad_type", "not a PDF", url=oa["url"])
    return r.body


# ================================================================ search
@dataclass
class Hit:
    item: dict
    provider: str
    rank: int
    oa: dict = field(default_factory=dict)


async def search_arxiv(f: Fetcher, q: str, mode: str, n: int) -> list[Hit]:
    terms = " AND ".join(f"all:{_arxiv_term(w)}" for w in _words(q)[:8]) or f"all:{_arxiv_term(q)}"
    r = await f.get("https://export.arxiv.org/api/query?" + urlencode(
        {"search_query": terms, "start": 0, "max_results": n, "sortBy": "relevance"}), mode=mode,
        types=("application/atom+xml", "application/xml", "text/xml"))
    return [Hit(it, "arxiv", i, {"is_oa": True, "status": "green", "url": f"https://arxiv.org/pdf/{it['arxiv']}"})
            for i, it in enumerate(parse_arxiv_atom(r.body))]


def _arxiv_term(w: str) -> str:
    w = re.sub(r"[^\w\-']", "", w)
    return w or "math"


def _words(q: str) -> list[str]:
    return [w for w in re.findall(r"[\w'-]+", q) if len(w) > 1 and w.lower() not in biblio.STOP]


async def search_zbmath(f: Fetcher, q: str, mode: str, n: int) -> list[Hit]:
    r = await f.get("https://api.zbmath.org/v1/document/_search?" + urlencode(
        {"search_string": q, "page": 0, "results_per_page": n}), mode=mode, types=JSON_TYPES)
    out = []
    for i, doc in enumerate(r.json().get("result") or []):
        it = zbmath_to_item(doc)
        if it.get("title"):
            out.append(Hit(biblio.clean_csl(it), "zbmath", i))
    return out


async def search_crossref(f: Fetcher, q: str, mode: str, n: int) -> list[Hit]:
    r = await f.get("https://api.crossref.org/works?" + urlencode(
        {"query.bibliographic": q, "rows": n,
         "select": "DOI,title,author,issued,container-title,type,abstract,volume,issue,page,publisher"}),
        mode=mode, types=JSON_TYPES)
    out = []
    for i, raw in enumerate((r.json().get("message") or {}).get("items") or []):
        typ = {"journal-article": "article-journal", "book-chapter": "chapter", "proceedings-article":
               "paper-conference", "posted-content": "article", "monograph": "book"}.get(raw.get("type", ""),
                                                                                         raw.get("type", "document"))
        it = biblio.clean_csl({**raw, "type": typ})
        if it.get("title"):
            out.append(Hit(it, "crossref", i))
    return out


async def search_openalex(f: Fetcher, q: str, mode: str, n: int) -> list[Hit]:
    r = await f.get("https://api.openalex.org/works?" + urlencode({"search": q, "per-page": n}), mode=mode,
                    types=JSON_TYPES)
    out = []
    for i, w in enumerate(r.json().get("results") or []):
        it = biblio.clean_csl(openalex_to_item(w))
        if it.get("title"):
            out.append(Hit(it, "openalex", i, openalex_oa(w)))
    return out


async def search_s2(f: Fetcher, q: str, mode: str, n: int) -> list[Hit]:
    r = await f.get("https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode(
        {"query": q, "limit": n, "fields": "title,year,authors,externalIds,abstract,openAccessPdf,venue"}),
        mode=mode, types=JSON_TYPES)
    out = []
    for i, p in enumerate(r.json().get("data") or []):
        ext = p.get("externalIds") or {}
        it: dict = {"type": "article-journal" if p.get("venue") else "article", "title": p.get("title") or "",
                    "author": [], "abstract": p.get("abstract") or ""}
        for a in p.get("authors") or []:
            parts = (a.get("name") or "").split()
            if parts:
                it["author"].append({"family": parts[-1], "given": " ".join(parts[:-1])})
        if p.get("year"):
            it["issued"] = {"date-parts": [[int(p["year"])]]}
        if p.get("venue"):
            it["container-title"] = p["venue"]
        if ext.get("DOI"):
            it["DOI"] = biblio.norm_doi(ext["DOI"])
        if ext.get("ArXiv"):
            it["arxiv"] = biblio.norm_arxiv(ext["ArXiv"])
        oa = p.get("openAccessPdf") or {}
        it = biblio.clean_csl(it)
        if it.get("title"):
            out.append(Hit(it, "semanticscholar", i, {"is_oa": bool(oa.get("url")), "url": oa.get("url") or "",
                                                       "status": oa.get("status") or ""}))
    return out


SEARCHERS = {"arxiv": search_arxiv, "zbmath": search_zbmath, "crossref": search_crossref,
             "openalex": search_openalex, "semanticscholar": search_s2}


def result_id(it: dict) -> str:
    if it.get("DOI"):
        return "doi:" + it["DOI"]
    if it.get("arxiv"):
        return "arxiv:" + it["arxiv"]
    if it.get("zbl"):
        return "zbl:" + it["zbl"]
    if it.get("openalex"):
        return "openalex:" + it["openalex"]
    return "t:" + biblio.norm_title(it.get("title", ""))[:60]


def _merge_item(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if k not in out or out[k] in ("", [], None):
            out[k] = v
        elif k == "msc" and isinstance(v, list):
            out[k] = list(dict.fromkeys(list(out[k]) + v))
        elif k == "abstract" and len(str(v)) > len(str(out[k])) and b.get("arxiv"):
            out[k] = v                                       # the author's abstract beats a review excerpt
    return out


def merge_hits(lists: list[list[Hit]], query: str) -> list[dict]:
    groups: list[dict] = []
    for hits in lists:
        for h in hits:
            target = None
            for g in groups:
                if biblio.same_work(g["item"], h.item):
                    target = g
                    break
            if target is None:
                groups.append({"item": dict(h.item), "providers": {h.provider: h.rank}, "oa": dict(h.oa)})
            else:
                target["item"] = _merge_item(target["item"], h.item)
                target["providers"].setdefault(h.provider, h.rank)
                if h.oa.get("is_oa") and not target["oa"].get("is_oa"):
                    target["oa"] = dict(h.oa)
    qw = {w.lower() for w in _words(query)}
    out = []
    for g in groups:
        rrf = sum(1.0 / (10 + r) for r in g["providers"].values())
        tw = set(biblio.norm_title(g["item"].get("title", "")).split())
        overlap = len(qw & tw) / max(1, len(qw))
        score = rrf + 0.05 * (len(g["providers"]) - 1) + 0.08 * overlap
        it = g["item"]
        out.append({"id": result_id(it), "title": it.get("title", ""), "authors": biblio.format_names(it.get("author")
                                                                                                    or []),
                    "year": biblio.year_of(it), "venue": it.get("container-title", ""), "doi": it.get("DOI", ""),
                    "arxiv": it.get("arxiv", ""), "zbl": it.get("zbl", ""), "openalex": it.get("openalex", ""),
                    "msc": it.get("msc", []), "abstract": it.get("abstract", ""), "oa": g["oa"],
                    "providers": sorted(g["providers"]), "score": round(score, 4),
                    "csl": {k: v for k, v in it.items() if not k.startswith("_")}})
    out.sort(key=lambda r: -r["score"])
    return out


async def search(f: Fetcher, query: str, mode: str, providers: list[str] | None = None, n: int = 10,
                 timeout: float = 25.0) -> dict:
    """{results:[Result], providers:{name: {ok, count, error}}}. A provider that fails is reported, not fatal."""
    names = [p for p in (providers or PROVIDERS) if p in SEARCHERS]
    status: dict = {}

    async def one(name: str) -> list[Hit]:
        try:
            hits = await asyncio.wait_for(SEARCHERS[name](f, query, mode, n), timeout)
            status[name] = {"ok": True, "count": len(hits), "error": ""}
            return hits
        except FetchError as e:
            if e.kind == "local_mode":
                raise
            status[name] = {"ok": False, "count": 0, "error": f"{e.kind}:{e.status}" if e.status else e.kind}
        except asyncio.TimeoutError:
            status[name] = {"ok": False, "count": 0, "error": "timeout"}
        except Exception as e:  # noqa: BLE001 (a provider changing its format must not break the others)
            status[name] = {"ok": False, "count": 0, "error": f"parse:{type(e).__name__}"}
        return []
    lists = await asyncio.gather(*(one(nm) for nm in names))
    return {"results": merge_hits(list(lists), query), "providers": status}


async def related(f: Fetcher, ident: str, how: str, mode: str, n: int = 20) -> list[dict]:
    """OpenAlex: how = related | cited_by | references, for a DOI or an OpenAlex W-id."""
    w = await openalex_work(f, ident, mode)
    wid = (w.get("id") or "").rsplit("/", 1)[-1]
    if how == "cited_by":
        r = await f.get("https://api.openalex.org/works?" + urlencode({"filter": f"cites:{wid}", "per-page": n,
                                                                      "sort": "cited_by_count:desc"}),
                        mode=mode, types=JSON_TYPES)
        works = r.json().get("results") or []
    else:
        ids = [x.rsplit("/", 1)[-1] for x in (w.get("related_works" if how == "related" else "referenced_works")
                                               or [])][:n]
        if not ids:
            return []
        r = await f.get("https://api.openalex.org/works?" + urlencode({"filter": "openalex:" + "|".join(ids),
                                                                      "per-page": n}), mode=mode, types=JSON_TYPES)
        works = r.json().get("results") or []
    hits = [Hit(biblio.clean_csl(openalex_to_item(x)), "openalex", i, openalex_oa(x)) for i, x in enumerate(works)]
    return merge_hits([hits], "")


# ================================================================ model-assisted reading list
QUERIES_PROMPT = (
    "You help a mathematician find literature. Turn the research question below into {n} short search queries for "
    "scholarly databases (arXiv, zbMATH, Crossref): keywords and standard terminology, no boolean syntax, no "
    "author names unless the question gives them. Answer ONLY with a JSON list of strings.\n\nQuestion: {q}")
PICK_PROMPT = (
    "You help a mathematician build a short reading list for the question below. Candidate works found in "
    "scholarly databases are listed as data, each with an id R1, R2, …\n{rule}\n\nQuestion: {q}\n\n{cands}\n\n"
    "Choose at most {k} candidates that best help answer the question, most useful first. For each, write one "
    "sentence saying why it is relevant, based only on its title and abstract. You may ONLY use the ids above; "
    "never mention or invent any other work. Answer ONLY with JSON: "
    '[{{"id": "R3", "why": "…"}}, …]')


def parse_json_block(text: str):
    t = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.S)
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1)
    start = min([i for i in (t.find("["), t.find("{")) if i >= 0] or [-1])
    if start < 0:
        return None
    for end in range(len(t), start, -1):
        if t[end - 1] in "]}":
            try:
                return json.loads(t[start:end])
            except ValueError:
                continue
    return None


def _clean_why(why: str, item: dict) -> str:
    why = re.sub(r"\s+", " ", str(why or "")).strip()[:400]
    why = biblio.CITE_GROUP.sub("", why)
    own = {biblio.norm_doi(item.get("DOI", "")), item.get("arxiv", "")}
    why = biblio.DOI_RE.sub(lambda m: m.group(0) if biblio.norm_doi(m.group(0)) in own else "[…]", why)
    why = re.sub(r"\barXiv:\s*\S+", lambda m: m.group(0) if biblio.norm_arxiv(m.group(0)) in own else "[…]", why,
                 flags=re.I)
    return why


async def reading_list(f: Fetcher, complete, question: str, mode: str, k: int = 8, n_queries: int = 4,
                       per_query: int = 8, on_progress=None) -> dict:
    """`complete(role, messages) -> Completion`. Returns {queries, items:[Result + why], rejected, model, providers}."""
    def progress(step: str, **kw):
        if on_progress:
            on_progress(step, kw)
    c = await complete("understand", [{"role": "user", "content": QUERIES_PROMPT.format(n=n_queries, q=question)}])
    qs = parse_json_block(c.text)
    queries = [str(x)[:200] for x in qs if isinstance(x, str) and x.strip()][:n_queries] if isinstance(qs, list) else []
    if not queries:
        queries = [question[:200]]
    progress("queries", queries=queries)
    merged: list[dict] = []
    providers: dict = {}
    for q in queries:
        res = await search(f, q, mode, n=per_query)
        providers[q] = res["providers"]
        for r in res["results"]:
            if not any(r["id"] == m["id"] or biblio.same_work(r["csl"], m["csl"]) for m in merged):
                merged.append(r)
        progress("searched", query=q, total=len(merged))
    merged.sort(key=lambda r: -r["score"])
    cands = merged[:20]
    table = {f"R{i + 1}": r for i, r in enumerate(cands)}
    if not cands:
        return {"queries": queries, "items": [], "rejected": 0, "model": c.model.key, "providers": providers}
    blocks = "\n\n".join(wrap_untrusted(f"{rid}. {r['title']} — {r['authors']} ({r['year'] or 's.d.'})\n"
                                        f"{(r['abstract'] or '(no abstract)')[:1200]}", f"candidate {rid}")
                         for rid, r in table.items())
    c2 = await complete("understand", [{"role": "user", "content": PICK_PROMPT.format(
        rule=UNTRUSTED_RULE, q=question, cands=blocks, k=k)}])
    picked = parse_json_block(c2.text)
    items, rejected, seen = [], 0, set()
    for p in picked if isinstance(picked, list) else []:
        rid = str(p.get("id", "")).strip() if isinstance(p, dict) else str(p).strip()
        r = table.get(rid)
        if r is None or rid in seen:
            rejected += 1                       # invented / unknown id: never shown
            continue
        seen.add(rid)
        items.append({**r, "why": _clean_why(p.get("why", "") if isinstance(p, dict) else "", r["csl"])})
        if len(items) >= k:
            break
    if not items:                                # the model gave nothing usable: the API ranking, unannotated
        items = [{**r, "why": ""} for r in cands[:k]]
    return {"queries": queries, "items": items, "rejected": rejected, "model": c2.model.key, "providers": providers}
