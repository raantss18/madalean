"""Internet search for research context (session S-U): Tavily, Exa, Brave Search with the user's keys, and the
keyless Wikipedia search as the fallback. Facts checked on the providers' own pages on 2026-11-22 (docs/PROVIDERS.md):

- Tavily  — POST https://api.tavily.com/search, `Authorization: Bearer tvly-…`; free « Researcher » plan 1 000
  credits / month, no card; basic search = 1 credit. Errors: 401 bad key, 429 rate (Retry-After), 432 plan limit,
  433 pay-as-you-go limit.
- Exa     — POST https://api.exa.ai/search, `x-api-key`; 10 USD of free credits each month; `type: "lite"` = 4 USD per
  1 000 searches (+1 USD per 1 000 pages of text); answer carries `costDollars`. Errors: 401, 402 (no credit), 429.
- Brave   — GET https://api.search.brave.com/res/v1/web/search, `X-Subscription-Token`; 5 USD of free credits per
  month (≈ 1 000 requests at 5 USD / 1 000), card required. Terms: no storing or database of results (transient use
  only), no use to train models — Madalean shows results and cites them, never stores them beyond the answer.
- Wikipedia — GET https://<lang>.wikipedia.org/w/api.php?action=query&list=search (no key, permitted; descriptive
  User-Agent required; requests one at a time). Only titles and snippets of encyclopedia articles.

Rules: never in local mode (the request is refused before any connection, by `Http.check` as for the models); a key
only ever goes to its provider's host; only the QUERY is sent (never a dossier, a file or a key of another service);
results are returned with their URL so that every claim can be cited; nothing is fetched from the result URLs here
(the research layer's `research.fetch.Fetcher` with policy `public` is the SSRF-safe way to read a page). Usage
(credits / USD) is counted per month in `<config_dir>/websearch-usage.json` (0600, no queries, no keys)."""
from __future__ import annotations

import asyncio
import html
import json
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import aiohttp

from ._util import read_json, write_private
from .api import BrainError, ToolSpec
from .net import CONNECT_TIMEOUT, Http

# descriptive, contact-less (no user data ever goes into it): Wikimedia's User-Agent policy refuses generic agents
USER_AGENT = f"Madalean/2.0 (open-source mathematics research assistant, desktop app) aiohttp/{aiohttp.__version__}"


@dataclass(frozen=True)
class SearchProvider:
    id: str
    name: str
    url: str                 # endpoint (its host is the only one the key may go to)
    keyed: bool = True
    unit: str = "credits"    # what `usage` counts: credits (Tavily) | usd (Exa, Brave) | requests (Wikipedia)
    free_month: float = 0.0  # free allowance per month in `unit` (0 = none / unknown)


PROVIDERS: list[SearchProvider] = [
    SearchProvider("tavily", "Tavily", "https://api.tavily.com/search", unit="credits", free_month=1000),
    SearchProvider("exa", "Exa", "https://api.exa.ai/search", unit="usd", free_month=10.0),
    SearchProvider("brave", "Brave Search", "https://api.search.brave.com/res/v1/web/search", unit="usd",
                   free_month=5.0),
    SearchProvider("wikipedia", "Wikipedia", "https://{lang}.wikipedia.org/w/api.php", keyed=False,
                   unit="requests"),
]
BY_ID = {p.id: p for p in PROVIDERS}
KEYED_IDS = tuple(p.id for p in PROVIDERS if p.keyed)
EXA_LITE_USD = 0.004          # per search (≤ 10 results), exa.ai/pricing 2026-11-22
EXA_TEXT_USD = 0.001          # per page of text
BRAVE_USD = 0.005             # per request, brave.com/search/api 2026-11-22


class SearchError(Exception):
    """kind: no_key | key_refused | quota | rate_limit | network | local_mode | disabled | http"""

    def __init__(self, kind: str, message: str = "", status: int = 0):
        super().__init__(message or kind)
        self.kind, self.message, self.status = kind, message or kind, status


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def kind_of(status: int, provider: str, body: str = "") -> str:
    if status in (401, 403):
        return "key_refused"
    if status == 402 or (provider == "tavily" and status in (432, 433)):
        return "quota"
    if status == 429:
        low = body.lower()
        return "quota" if ("quota" in low or "limit exceeded" in low or "usage limit" in low) else "rate_limit"
    return "http"


class Usage:
    """Per month, per provider: units used and number of searches (no query text)."""

    def __init__(self, path: Path | None):
        self.path = path
        self._lock = threading.Lock()
        raw = read_json(path) if path else None
        self.data: dict[str, dict[str, dict[str, float]]] = raw if isinstance(raw, dict) else {}

    @staticmethod
    def month() -> str:
        return time.strftime("%Y-%m")

    def add(self, provider: str, units: float) -> None:
        with self._lock:
            m = self.data.setdefault(self.month(), {})
            row = m.setdefault(provider, {"units": 0.0, "searches": 0})
            row["units"] = round(float(row.get("units", 0)) + float(units), 6)
            row["searches"] = int(row.get("searches", 0)) + 1
            for k in sorted(self.data)[:-13]:          # keep about a year
                self.data.pop(k, None)
            if self.path:
                try:
                    write_private(self.path, json.dumps(self.data))
                except OSError:
                    pass

    def of(self, provider: str) -> dict:
        row = (self.data.get(self.month()) or {}).get(provider) or {}
        return {"units": float(row.get("units", 0)), "searches": int(row.get("searches", 0))}


class WebSearch:
    """`get_key(provider) -> str | None`; `settings() -> dict` (brain settings: `mode`, `web_search`,
    `providers_disabled`); `endpoints` re-binds provider URLs (tests only: never exposed)."""

    def __init__(self, get_key: Callable[[str], str | None], settings: Callable[[], dict] | None = None, *,
                 config_dir: Path | None = None, endpoints: dict[str, str] | None = None, http: Http | None = None):
        self._get_key = get_key
        self._settings = settings or (lambda: {})
        self.endpoints = dict(endpoints or {})
        self.http = http or Http({p.id: (urlsplit(self.url(p)).hostname or "").lower() for p in PROVIDERS if p.keyed})
        self.usage = Usage(Path(config_dir) / "websearch-usage.json" if config_dir else None)
        self._wiki_lock = asyncio.Lock()              # Wikimedia etiquette: one request at a time

    # ------------------------------------------------------------------ configuration
    def url(self, p: SearchProvider, lang: str = "en") -> str:
        return self.endpoints.get(p.id, p.url).replace("{lang}", lang)

    def key(self, provider: str) -> str | None:
        if provider not in KEYED_IDS:
            return None
        try:
            k = self._get_key(provider)
        except Exception:  # noqa: BLE001
            return None
        return k.strip() if isinstance(k, str) and k.strip() else None

    def disabled(self, provider: str) -> bool:
        return provider in (self._settings().get("providers_disabled") or [])

    def local_mode(self) -> bool:
        return self._settings().get("mode") == "local"

    def enabled(self) -> bool:
        return bool(self._settings().get("web_search", True)) and not self.local_mode()

    def order(self) -> list[str]:
        """Providers to try, best first: keyed ones with a key whose free monthly allowance is not used up, then the
        keyed ones past their allowance (they may still have paid credit), then Wikipedia (keyless)."""
        fresh, spent = [], []
        for p in PROVIDERS:
            if not p.keyed or self.disabled(p.id) or self.key(p.id) is None:
                continue
            u = self.usage.of(p.id)["units"]
            (spent if p.free_month and u >= p.free_month else fresh).append(p.id)
        out = fresh + spent
        if not self.disabled("wikipedia"):
            out.append("wikipedia")
        return out

    def status(self) -> list[dict]:
        return [{"id": p.id, "name": p.name, "keyed": p.keyed, "key_set": (self.key(p.id) is not None) if p.keyed else None,
                 "disabled": self.disabled(p.id), "unit": p.unit, "free_month": p.free_month, **self.usage.of(p.id)}
                for p in PROVIDERS]

    # ------------------------------------------------------------------ HTTP
    async def _call(self, method: str, url: str, provider: str, *, key: str | None, headers: dict,
                    body: Any = None, params: dict | None = None, timeout: float = 20) -> Any:
        self.http.check(url, "online", provider if key else None, key)     # local mode / key host: raises BrainError
        h = {**headers, "User-Agent": USER_AGENT}
        try:
            async with self.http.session().request(
                    method, url, json=body, params=params, headers=h,
                    timeout=aiohttp.ClientTimeout(total=timeout, sock_connect=min(timeout, CONNECT_TIMEOUT))) as r:
                raw = await r.read()
                if r.status >= 400:
                    text = raw.decode("utf-8", "replace")[:500]
                    raise SearchError(kind_of(r.status, provider, text), f"HTTP {r.status}", r.status)
                try:
                    return json.loads(raw)
                except ValueError as e:
                    raise SearchError("http", "unreadable answer", r.status) from e
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            raise SearchError("network", type(e).__name__) from e

    # ------------------------------------------------------------------ providers
    async def _tavily(self, q: str, k: int, key: str) -> list[dict]:
        p = BY_ID["tavily"]
        v = await self._call("POST", self.url(p), p.id, key=key, headers={"Authorization": f"Bearer {key}"},
                             body={"query": q, "max_results": k, "search_depth": "basic", "include_answer": False})
        self.usage.add(p.id, 1)
        return [{"title": str(r.get("title") or ""), "url": str(r.get("url") or ""),
                 "snippet": str(r.get("content") or "")[:600], "published": str(r.get("published_date") or "")}
                for r in (v or {}).get("results") or [] if isinstance(r, dict)]

    async def _exa(self, q: str, k: int, key: str) -> list[dict]:
        p = BY_ID["exa"]
        v = await self._call("POST", self.url(p), p.id, key=key, headers={"x-api-key": key},
                             body={"query": q, "numResults": k, "type": "lite",
                                   "contents": {"highlights": True}})
        cost = (v or {}).get("costDollars")
        usd = cost.get("total") if isinstance(cost, dict) else None
        self.usage.add(p.id, float(usd) if isinstance(usd, (int, float)) else EXA_LITE_USD)
        out = []
        for r in (v or {}).get("results") or []:
            if not isinstance(r, dict):
                continue
            hl = r.get("highlights")
            snip = " … ".join(str(x) for x in hl[:3]) if isinstance(hl, list) else str(r.get("text") or "")
            out.append({"title": str(r.get("title") or ""), "url": str(r.get("url") or ""), "snippet": snip[:600],
                        "published": str(r.get("publishedDate") or "")})
        return out

    async def _brave(self, q: str, k: int, key: str) -> list[dict]:
        p = BY_ID["brave"]
        v = await self._call("GET", self.url(p), p.id, key=key,
                             headers={"X-Subscription-Token": key, "Accept": "application/json"},
                             params={"q": q, "count": str(min(k, 20))})
        self.usage.add(p.id, BRAVE_USD)
        return [{"title": _strip_tags(str(r.get("title") or "")), "url": str(r.get("url") or ""),
                 "snippet": _strip_tags(str(r.get("description") or ""))[:600], "published": str(r.get("age") or "")}
                for r in ((v or {}).get("web") or {}).get("results") or [] if isinstance(r, dict)]

    async def _wikipedia(self, q: str, k: int, lang: str) -> list[dict]:
        p = BY_ID["wikipedia"]
        lang = lang if lang in ("en", "fr") else "en"
        async with self._wiki_lock:
            v = await self._call("GET", self.url(p, lang), p.id, key=None, headers={"Accept": "application/json"},
                                 params={"action": "query", "list": "search", "srsearch": q, "srlimit": str(min(k, 10)),
                                         "format": "json", "formatversion": "2"})
        self.usage.add(p.id, 1)
        base = f"https://{lang}.wikipedia.org/wiki/"
        return [{"title": str(r.get("title") or ""), "url": base + str(r.get("title") or "").replace(" ", "_"),
                 "snippet": _strip_tags(str(r.get("snippet") or ""))[:600], "published": ""}
                for r in ((v or {}).get("query") or {}).get("search") or [] if isinstance(r, dict)]

    async def encyclopedia(self, name: str, *, mode: str = "auto") -> dict | None:
        """The introduction of the English Wikipedia article called exactly like `name` (a problem's or theorem's
        classical name), verbatim; None when there is no such article, or when Wikipedia is disabled or unreachable."""
        p = BY_ID["wikipedia"]
        if mode == "local" or self.disabled(p.id) or not name.strip():
            return None

        def words(t: str) -> set[str]:
            t = re.sub(r"[‐-―]", "-", unicodedata.normalize("NFKD", t)).encode("ascii", "ignore").decode()
            return set(re.findall(r"[a-z0-9]+", t.lower())) - {"the", "s", "of"}
        try:
            async with self._wiki_lock:
                v = await self._call("GET", self.url(p, "en"), p.id, key=None, headers={"Accept": "application/json"},
                                     params={"action": "query", "prop": "extracts|pageprops", "ppprop": "disambiguation",
                                             "explaintext": "1", "exintro": "1", "redirects": "1", "titles": name[:120],
                                             "format": "json", "formatversion": "2"})
                hit = self._page(v)
                if hit is None:
                    s = await self._call("GET", self.url(p, "en"), p.id, key=None, headers={"Accept": "application/json"},
                                         params={"action": "query", "generator": "search", "gsrsearch": name[:120],
                                                 "gsrlimit": "1", "prop": "extracts|pageprops",
                                                 "ppprop": "disambiguation", "explaintext": "1", "exintro": "1",
                                                 "format": "json", "formatversion": "2"})
                    hit = self._page(s)
                    # a search hit is used only when its title has all the words of the name (accents and dashes aside)
                    if hit is not None and not words(name) <= words(hit["title"]):
                        hit = None
            self.usage.add(p.id, 1)
        except (SearchError, BrainError):
            return None
        return hit

    @staticmethod
    def _page(v) -> dict | None:
        for r in ((v or {}).get("query") or {}).get("pages") or []:
            if isinstance(r, dict) and r.get("extract") and not r.get("missing") and not r.get("pageprops"):
                t = str(r["title"])
                return {"title": t, "url": "https://en.wikipedia.org/wiki/" + t.replace(" ", "_"),
                        "text": str(r["extract"])[:4000]}
        return None

    async def _one(self, pid: str, q: str, k: int, lang: str) -> list[dict]:
        if pid == "wikipedia":
            return await self._wikipedia(q, k, lang)
        key = self.key(pid)
        if key is None:
            raise SearchError("no_key")
        return await getattr(self, f"_{pid}")(q, k, key)

    # ------------------------------------------------------------------ API
    async def search(self, query: str, k: int = 6, *, mode: str = "auto", providers: list[str] | None = None,
                     lang: str = "en") -> dict:
        """→ {query, provider, results: [{n, title, url, snippet, published, source}], tried: [{provider, error}]}.
        The first provider (see `order`) that answers wins; a refused key, an exhausted quota or a network error
        moves on to the next one. Raises SearchError("local_mode" | "disabled" | "no_provider")."""
        query = " ".join(str(query or "").split())[:400]
        if not query:
            raise SearchError("http", "empty query")
        if mode == "local" or self.local_mode():
            raise SearchError("local_mode", "local mode: no Internet search")
        if not bool(self._settings().get("web_search", True)):
            raise SearchError("disabled", "Internet search is turned off")
        k = max(1, min(int(k or 6), 10))
        order = [p for p in (providers or self.order()) if p in BY_ID and not self.disabled(p)]
        tried: list[dict] = []
        for pid in order:
            try:
                res = await self._one(pid, query, k, lang)
            except SearchError as e:
                tried.append({"provider": pid, "error": e.kind})
                continue
            except Exception as e:  # noqa: BLE001 (BrainError from the guards: local mode, key host)
                tried.append({"provider": pid, "error": getattr(e, "kind", "error")})
                continue
            res = [r for r in res if r["url"].startswith("https://")][:k]
            for i, r in enumerate(res, 1):
                r["n"], r["source"] = i, BY_ID[pid].name
            return {"query": query, "provider": pid, "results": res, "tried": tried}
        raise SearchError("no_provider", "no search provider answered: " +
                          ", ".join(f"{t['provider']} ({t['error']})" for t in tried) if tried else "no provider")

    async def test(self, provider: str) -> dict:
        """Key test: one tiny real search (Tavily: 1 credit; Exa: ≈ 0.004 USD of the free credit; Brave: one request
        of the free credit). Never echoes the key."""
        p = BY_ID.get(provider)
        if p is None:
            return {"ok": False, "reason": "unknown_provider"}
        if self.local_mode():
            return {"ok": None, "reason": "local_mode"}
        if p.keyed and self.key(provider) is None:
            return {"ok": False, "reason": "no_key"}
        t0 = time.monotonic()
        try:
            res = await self._one(provider, "Pythagorean theorem", 1, "en")
        except SearchError as e:
            return {"ok": False, "reason": e.kind, "status": e.status}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "reason": getattr(e, "kind", "error")}
        return {"ok": True, "reason": "", "results": len(res), "latency_s": round(time.monotonic() - t0, 2)}

    async def close(self) -> None:
        await self.http.close()


def format_results(res: dict) -> str:
    """Text given to a model: numbered, with URLs, so that the answer can cite [n]."""
    lines = [f"Web results for « {res['query']} » (via {BY_ID[res['provider']].name}); cite them as [n] with the URL:"]
    for r in res["results"]:
        lines.append(f"[{r['n']}] {r['title']} — {r['url']}\n    {r['snippet']}")
    if not res["results"]:
        lines.append("(no result)")
    return "\n".join(lines)


def tool_spec(search: WebSearch, *, mode: str = "auto", lang: str = "en") -> ToolSpec:
    """The `web_search` tool for `brain.run_agent` (research orchestrator, grounded answers). Only the query goes
    out; in local mode the tool answers that the Internet is not used."""
    async def run(a: dict) -> str:
        try:
            res = await search.search(str(a.get("query") or ""), int(a.get("k") or 6), mode=mode, lang=lang)
        except SearchError as e:
            return f"Web search unavailable ({e.kind})."
        return format_results(res)
    return ToolSpec("web_search",
                    "Search the Internet (Tavily / Exa / Brave / Wikipedia) for context: definitions, recent results, "
                    "where a theorem is proved. Returns numbered results with URLs; cite them as [n]. Never send "
                    "private material in the query.",
                    {"type": "object", "properties": {
                        "query": {"type": "string", "description": "Short search query (keywords)."},
                        "k": {"type": "integer", "description": "Number of results (1–10, default 6)."}},
                     "required": ["query"]}, run)
