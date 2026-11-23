"""The news service: settings, polite conditional fetches, the periodic refresh, relevance and summaries.

Files, all under `<config>/news/`: `news.sqlite` (store.py), `settings.json` (what the user chose), `state.json`
(per source: ETag / Last-Modified, last check, last error, backoff).

Network (the ONLY place of this package that reaches it is `_get`):
- never in Local mode, never in demo mode (the demo reads the recorded answers of `demo_data/`);
- https only, public hosts only, resolve-then-connect and no cookies — the research layer's transport
  (`research.fetch`: `check_url`, `PublicResolver`, `AiohttpTransport`) with a generic, contact-less client name;
- a built-in source may only be answered (redirects included) by the hosts its registry entry lists; a feed added
  by the user by any public https host;
- one GET per source and per refresh, sent with `If-None-Match` / `If-Modified-Since` when the previous answer
  gave validators; sources are fetched one after the other;
- a source is never asked more often than its own interval (≥ 6 h), nor more often than the user's frequency; a
  failure doubles the wait (10 min … 24 h), HTTP 429 / 403 wait at least 6 h, the Stack Exchange `backoff` field
  is obeyed; a manual refresh skips the interval but not the backoff, and not within FORCE_MIN of the last check."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from ..config import atomic_write_text
from ..logs import get
from ..research import fetch
from ..research.fetch import FetchError, LocalModeError
from . import branches, parsers, registry, relevance, summarize
from .store import NewsStore

log = get("news")
USER_AGENT = "Madalean/2.0 (math news reader)"
DATA = Path(__file__).resolve().parent / "demo_data"
DEFAULTS: dict = {"enabled": True, "interval_hours": 6, "branches": [], "sources": {}, "feeds": [],
                  "summaries": False, "badge": True, "keep_days": 30, "max_items": 5000}
LIMITS = {"interval_hours": (1, 48), "keep_days": (3, 365), "max_items": (200, 20000)}
MAX_FEEDS = 20
FEED_KEEP_DAYS = 200
FEED_MAX_BYTES = 2 * 1024 * 1024
FORCE_MIN = 300.0                  # a manual refresh does not re-ask a source checked less than 5 minutes ago
RETRY_BASE = 600.0
RETRY_MAX = 86400.0
THROTTLED_MIN = 6 * 3600.0
AUTO_SUMMARIES = 8                 # per refresh, when the user turned the summaries on
TIMEOUT = 25.0
DEMO_FEED = {"id": "feed-demo", "url": "https://example.org/madalean-demo.xml", "title": "Flux de démonstration",
             "enabled": True}


class NewsError(Exception):
    def __init__(self, kind: str, message: str = "", status: int = 400):
        super().__init__(message or kind)
        self.kind, self.status = kind, status


def _read(path: Path) -> dict:
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


class NewsService:
    def __init__(self, ctx, root: Path | None = None, transport=None, clock=time.time):
        self.ctx = ctx
        self.root = Path(root or (ctx.paths.config / "news"))
        self.store = NewsStore(self.root)
        self.clock = clock
        self._transport = transport
        self._fetcher: fetch.Fetcher | None = None
        self._lock = asyncio.Lock()
        self._settings: dict | None = None
        self.state: dict = _read(self.root / "state.json")
        self.state.setdefault("sources", {})
        self.requests = 0                      # GETs actually sent (tests, the status view)
        self._profile_checked = 0.0
        self._summary_tasks: dict[int, asyncio.Task] = {}

    # ------------------------------------------------------------ settings
    def settings(self) -> dict:
        if self._settings is None:
            raw = _read(self.root / "settings.json")
            s = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}
            self._settings = self._validated(s, s)
        return json.loads(json.dumps(self._settings))

    def _validated(self, cur: dict, data: dict) -> dict:
        s = dict(cur)
        for k in ("enabled", "summaries", "badge"):
            if k in data:
                if not isinstance(data[k], bool):
                    raise NewsError("bad_value", k)
                s[k] = data[k]
        for k, (lo, hi) in LIMITS.items():
            if k in data:
                v = data[k]
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise NewsError("bad_value", k)
                s[k] = int(min(max(v, lo), hi))
        if "branches" in data:
            v = data["branches"]
            if not isinstance(v, list) or any(b not in branches.IDS for b in v):
                raise NewsError("bad_value", "branches")
            s["branches"] = [b for b in branches.IDS if b in v]
        if "sources" in data:
            v = data["sources"]
            if not isinstance(v, dict) or any(not isinstance(x, bool) for x in v.values()):
                raise NewsError("bad_value", "sources")
            known = set(registry.BY_ID)
            s["sources"] = {**{k: x for k, x in (cur.get("sources") or {}).items() if k in known},
                            **{k: x for k, x in v.items() if k in known}}
        if "feeds" in data:
            v = data["feeds"]
            if not isinstance(v, list) or len(v) > MAX_FEEDS:
                raise NewsError("bad_value", "feeds")
            feeds, seen = [], set()
            for f in v:
                if not isinstance(f, dict):
                    raise NewsError("bad_value", "feeds")
                url = self.check_feed_url(str(f.get("url") or ""))
                fid = str(f.get("id") or "")
                if not fid.startswith("feed-") or len(fid) > 40 or fid in seen:
                    fid = "feed-" + uuid.uuid4().hex[:8]
                seen.add(fid)
                title = parsers.clean_text(str(f.get("title") or ""), 80, one_line=True) or _host(url)
                feeds.append({"id": fid, "url": url, "title": title, "enabled": f.get("enabled") is not False})
            s["feeds"] = feeds
        return s

    @staticmethod
    def check_feed_url(url: str) -> str:
        """A feed the user adds: an https URL on a public host (no credentials, no IP literal, no local name)."""
        url = url.strip()
        if len(url) > 500:
            raise NewsError("bad_url", "too long")
        try:
            fetch.check_url(url, "public")
        except FetchError as e:
            raise NewsError("bad_url", str(e)) from e
        return url

    def patch_settings(self, data: dict) -> dict:
        cur = self.settings()
        new = self._validated(cur, data)
        gone = {f["id"] for f in cur["feeds"]} - {f["id"] for f in new["feeds"]}
        atomic_write_text(self.root / "settings.json", json.dumps(new, ensure_ascii=False, indent=1))
        self._settings = new
        for fid in gone:
            self.store.drop_source(fid)
            self.state["sources"].pop(fid, None)
        if gone:
            self._save_state()
        return self.settings()

    def mode(self) -> str:
        return str(getattr(self.ctx.settings, "mode", "auto"))

    # ------------------------------------------------------------ sources
    def _active(self, s: dict | None = None) -> list[dict]:
        """Every source (built-in and the user's feeds) as a plain dict, with `on`."""
        s = s or self.settings()
        out = []
        for src in registry.SOURCES:
            out.append({"id": src.id, "group": src.group, "url": src.url, "hosts": src.hosts, "parser": src.parser,
                        "kind": src.kind, "open": src.open, "interval_h": src.interval_h,
                        "keep_days": src.keep_days or s["keep_days"], "conditional": src.conditional,
                        "require": src.require, "max_bytes": src.max_bytes, "fixture": src.fixture,
                        "on": bool(s["sources"].get(src.id, src.default_on)), "custom": False})
        for f in s["feeds"]:
            out.append({"id": f["id"], "group": "custom", "url": f["url"], "hosts": None, "parser": "feed",
                        "kind": "post", "open": False, "interval_h": 6.0,
                        "keep_days": max(s["keep_days"], FEED_KEEP_DAYS), "conditional": True, "require": None,
                        "max_bytes": FEED_MAX_BYTES, "fixture": "", "on": bool(f.get("enabled", True)),
                        "custom": True, "title": f["title"]})
        return out

    def enabled_ids(self, s: dict | None = None) -> list[str]:
        return [x["id"] for x in self._active(s) if x["on"]]

    def sources_view(self) -> dict:
        s = self.settings()
        stats = self.store.stats()["sources"]
        rows = []
        for a in self._active(s):
            st = self.state["sources"].get(a["id"], {})
            row = {"id": a["id"], "group": a["group"], "enabled": a["on"], "custom": a["custom"],
                   "items": stats.get(a["id"], {}).get("items", 0), "unread": stats.get(a["id"], {}).get("unread", 0),
                   "checked": st.get("checked") or None, "ok": st.get("ok") or None, "error": st.get("error") or "",
                   "retry_at": st.get("next") if st.get("error") else None}
            src = registry.BY_ID.get(a["id"])
            if src is not None:
                row.update({"fr": src.fr, "en": src.en, "about_fr": src.about_fr, "about_en": src.about_en,
                            "home": src.home, "host": sorted(src.hosts)[0], "licence": src.licence,
                            "terms": src.terms, "summaries": src.summaries})
            else:
                row.update({"fr": a["title"], "en": a["title"], "about_fr": "", "about_en": "", "home": a["url"],
                            "host": _host(a["url"]), "licence": "",
                            "terms": "", "url": a["url"], "summaries": True})
            rows.append(row)
        return {"sources": rows, "verified": registry.VERIFIED,
                "groups": [{"id": g, "fr": fr, "en": en} for g, fr, en in registry.GROUPS],
                "branches": [{"id": b, "fr": fr, "en": en} for b, fr, en in branches.BRANCHES]}

    # ------------------------------------------------------------ network
    def fetcher(self) -> fetch.Fetcher:
        if self._fetcher is None:
            self._fetcher = fetch.Fetcher(self._transport)
        return self._fetcher

    async def _get(self, url: str, *, hosts, etag: str = "", modified: str = "", max_bytes: int) -> fetch.Response:
        """One conditional GET (≤ 4 redirects, each hop re-validated). Raises FetchError; Local mode refuses."""
        if self.mode() == "local":
            raise LocalModeError(url)
        if self.ctx.demo:
            raise FetchError("blocked", "demo mode: no network", url=url)
        headers = {"User-Agent": USER_AGENT,
                   "Accept": "application/atom+xml, application/rss+xml, application/json, application/xml;q=0.9, "
                             "text/xml;q=0.8, */*;q=0.1"}
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified
        f = self.fetcher()
        cur = url
        for _hop in range(5):
            host = fetch.check_url(cur, "public")
            if hosts is not None and host not in hosts:
                raise FetchError("blocked", f"host {host!r} is not one of this source's hosts", url=cur)
            await f._polite(host)
            self.requests += 1
            r = await f.transport(cur, headers, max_bytes, TIMEOUT)
            if r.status in (301, 302, 303, 307, 308):
                loc = r.headers.get("location", "")
                if not loc:
                    raise FetchError("http", "redirect without location", r.status, cur)
                cur = urljoin(cur, loc)
                continue
            if r.status not in (200, 304):
                raise FetchError("http", f"HTTP {r.status}", r.status, cur)
            return r
        raise FetchError("blocked", "too many redirects", url=url)

    async def close(self) -> None:
        for t in list(self._summary_tasks.values()):
            t.cancel()
        if self._fetcher is not None:
            await self._fetcher.close()
        self.store.close()

    # ------------------------------------------------------------ refresh
    def _save_state(self) -> None:
        try:
            atomic_write_text(self.root / "state.json", json.dumps(self.state, ensure_ascii=False))
        except OSError:
            log.exception("news state not saved")

    def _due(self, a: dict, st: dict, now: float, force: bool, user_hours: float) -> bool:
        if now < float(st.get("next") or 0):
            return False                                    # backoff (failure, throttling, Stack Exchange `backoff`)
        checked = float(st.get("checked") or 0)
        if force:
            return now - checked >= FORCE_MIN
        return now - checked >= max(a["interval_h"], user_hours) * 3600

    def _prepare(self, a: dict, body: bytes, now: float) -> list[dict]:
        """Parse an answer and tag its items (runs in a thread)."""
        fn = parsers.PARSERS[a["parser"]]
        items = fn(body, kind=a["kind"], open_=a["open"]) if a["parser"] == "feed" else fn(body)
        out = []
        for it in items:
            if a["require"] is not None and not a["require"].search(f"{it['title']}\n{it['summary']}"):
                continue
            it["branches"] = branches.tag(it["title"], it["summary"], it["cats"])
            if summarize.looks_like_injection(f"{it['title']}\n{it['summary']}"):
                it["extra"] = {**it["extra"], "suspect": True}
            out.append(it)
        return out

    async def _one(self, a: dict, now: float) -> dict:
        st = self.state["sources"].setdefault(a["id"], {})
        try:
            r = await self._get(a["url"], hosts=a["hosts"], etag=st.get("etag", "") if a["conditional"] else "",
                                modified=st.get("modified", "") if a["conditional"] else "", max_bytes=a["max_bytes"])
            st["checked"] = now
            if r.status == 304:
                st.update({"ok": now, "error": "", "failures": 0, "next": 0})
                return {"id": a["id"], "status": "unchanged", "new": 0}
            items = await asyncio.to_thread(self._prepare, a, r.body, now)
            res = await asyncio.to_thread(self.store.upsert, a["id"], a["group"], items, now=now,
                                          min_published=now - a["keep_days"] * 86400)
            wait = parsers.stackexchange_backoff(r.body) if a["parser"] == "stackexchange" else 0
            st.update({"ok": now, "error": "", "failures": 0, "next": now + wait if wait else 0,
                       "etag": r.headers.get("etag", ""), "modified": r.headers.get("last-modified", "")})
            return {"id": a["id"], "status": "ok", **res}
        except (FetchError, parsers.ParseError) as e:
            kind = e.kind if isinstance(e, FetchError) else "parse"
            code = getattr(e, "status", 0)
            n = int(st.get("failures") or 0) + 1
            wait = min(RETRY_BASE * 2 ** (n - 1), RETRY_MAX)
            if code in (403, 429):
                wait = max(wait, THROTTLED_MIN)
            st.update({"checked": now, "error": f"{kind}{f' {code}' if code else ''}", "failures": n,
                       "next": now + wait})
            log.info("news source %s: %s (%s); next try in %.0f min", a["id"], kind, e, wait / 60)
            return {"id": a["id"], "status": "error", "error": kind, "http": code, "new": 0}

    async def refresh(self, *, force: bool = False, only: str | None = None) -> dict:
        """Fetch what is due. → {"skipped": reason} or {"sources": [...], "new": n, "unread": n}."""
        if self.ctx.demo:
            await asyncio.to_thread(self.seed_demo)
            return {"demo": True, "sources": [], "new": 0, "unread": self.unread()}
        if self.mode() == "local":
            return {"skipped": "local_mode"}
        s = self.settings()
        if not s["enabled"] and not force:
            return {"skipped": "disabled"}
        if self._lock.locked():
            return {"skipped": "busy"}
        async with self._lock:
            now = self.clock()
            todo = [a for a in self._active(s) if a["on"] and (only is None or a["id"] == only)
                    and self._due(a, self.state["sources"].get(a["id"], {}), now, force, s["interval_hours"])]
            report, down = [], 0
            for a in todo:
                if self.mode() == "local":                  # switched to Local in the middle of a refresh
                    break
                res = await self._one(a, self.clock())
                report.append(res)
                down = down + 1 if res.get("error") in ("network", "timeout") else 0
                if down >= 2:                               # offline: stop asking, the next tick tries again
                    break
            self.state["last_refresh"] = now
            new = sum(r.get("new", 0) for r in report)
            if report:
                await asyncio.to_thread(self.store.purge, keep_days=s["keep_days"], max_items=s["max_items"],
                                        source_days={a["id"]: a["keep_days"] for a in self._active(s)}, now=now)
                await self.rescore(force=True)
                self._save_state()
            unread = self.unread()
            if new:
                self.ctx.publish("news.updated", {"unread": unread, "new": new})
        if new and s["summaries"]:
            self.ctx.spawn(self.auto_summaries())
        return {"sources": report, "new": new, "unread": unread}

    async def tick(self) -> None:
        """Called every few minutes by the plugin: refreshes the sources that are due (cheap when none is)."""
        if os.environ.get("MADALEAN_NO_UPDATE_CHECK") == "1" or self.ctx.demo or self.mode() == "local":
            return
        s = self.settings()
        if not s["enabled"]:
            return
        now = self.clock()
        if not any(a["on"] and self._due(a, self.state["sources"].get(a["id"], {}), now, False, s["interval_hours"])
                   for a in self._active(s)):
            return
        try:
            await self.refresh()
        except Exception:  # noqa: BLE001 (the watch must never disturb the server)
            log.exception("news refresh failed")

    def next_refresh(self) -> float | None:
        s = self.settings()
        if not s["enabled"] or self.mode() == "local" or self.ctx.demo:
            return None
        ts = []
        for a in self._active(s):
            if a["on"]:
                st = self.state["sources"].get(a["id"], {})
                ts.append(max(float(st.get("checked") or 0) + max(a["interval_h"], s["interval_hours"]) * 3600,
                              float(st.get("next") or 0)))
        return min(ts) if ts else None

    # ------------------------------------------------------------ reading
    def filters(self, s: dict | None = None) -> dict:
        s = s or self.settings()
        return {"followed": s["branches"] or None, "sources_on": self.enabled_ids(s)}

    def unread(self) -> int:
        """Unread items of the user's domains, from the sources that are on (the number on the badge)."""
        return self.store.count(unread=True, **self.filters())

    def overview(self) -> dict:
        s = self.settings()
        f = self.filters(s)
        newest = self.store.query(limit=3, unread=True, **f)["items"]
        st = self.store.stats()
        errors = [i for i, x in self.state["sources"].items() if x.get("error") and i in f["sources_on"]]
        return {"unread": self.store.count(unread=True, **f), "unread_all": st["unread"], "items": st["items"],
                "saved": st["saved"], "for_projects": self.store.count(unread=True, projects=True, **f),
                "open": self.store.count(unread=True, open_=True, **f), "newest": newest,
                "last_refresh": self.state.get("last_refresh") or None, "next_refresh": self.next_refresh(),
                "mode": self.mode(), "demo": bool(self.ctx.demo), "enabled": s["enabled"], "badge": s["badge"],
                "summaries": s["summaries"], "branches": s["branches"], "errors": errors}

    # ------------------------------------------------------------ relevance (local)
    async def rescore(self, force: bool = False) -> bool:
        """Recompute « pour mes projets » when the projects' texts changed (or after a refresh)."""
        now = time.monotonic()
        if not force and now - self._profile_checked < 60:
            return False
        self._profile_checked = now
        profiles = await asyncio.to_thread(relevance.project_texts, self.ctx)
        h = hashlib.sha256(json.dumps(profiles, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if not force and h == self.state.get("profile_hash"):
            return False

        def work():
            self.store.set_relevance(relevance.score_corpus(self.store.corpus(), profiles))
        await asyncio.to_thread(work)
        self.state["profile_hash"] = h
        self._save_state()
        return True

    # ------------------------------------------------------------ summaries
    async def summarize(self, item_id: int) -> dict:
        """French summary of one item (cached). Raises summarize.SummaryError / NewsError."""
        it = self.store.get(item_id)
        if it is None:
            raise NewsError("not_found", status=404)
        if it["fr"]:
            return it
        why = summarize.can_summarize(it)
        if why:
            raise summarize.SummaryError(why)
        if self.ctx.demo:
            raise summarize.SummaryError("no_model", "demo mode")
        task = self._summary_tasks.get(item_id)
        if task is None or task.done():
            task = asyncio.ensure_future(summarize.summarize(self.ctx.brain, it, mode=self.mode()))
            self._summary_tasks[item_id] = task
            task.add_done_callback(lambda _t, i=item_id: self._summary_tasks.pop(i, None))
        text, model = await asyncio.shield(task)
        return self.store.set_summary(item_id, text, model) or it

    async def auto_summaries(self) -> int:
        """After a refresh, with the summaries on: the newest unread items of the user's domains, a few at a time."""
        if self.mode() == "local" or self.ctx.demo or not self.settings()["summaries"]:
            return 0
        n = 0
        f = self.filters()
        f["sources_on"] = [i for i in f["sources_on"]                       # © sources are never summarised
                           if registry.BY_ID.get(i) is None or registry.BY_ID[i].summaries]
        for it in self.store.pending_summaries(AUTO_SUMMARIES * 2, **f):
            if n >= AUTO_SUMMARIES or self.mode() == "local":
                break
            if summarize.can_summarize(it):
                continue
            try:
                await self.summarize(it["id"])
                n += 1
            except summarize.SummaryError as e:
                if e.kind in ("no_model", "local_mode"):
                    break
            except Exception:  # noqa: BLE001
                log.exception("news summary failed")
                break
        if n:
            self.ctx.publish("news.updated", {"unread": self.unread(), "new": 0, "summaries": n})
        return n

    # ------------------------------------------------------------ demo data (recorded answers, no network)
    def seed_demo(self, now: float | None = None) -> int:
        """`serve --demo` and the tests: fill the store from the recorded answers of `demo_data/`. Dates are
        shifted so that each source's newest item is recent (the recordings do not age)."""
        now = now or self.clock()
        s = self.settings()
        if not any(f["id"] == DEMO_FEED["id"] for f in s["feeds"]):
            s = self.patch_settings({"feeds": [*s["feeds"], DEMO_FEED]})
        total = 0
        for i, a in enumerate(self._active(s)):
            name = a["fixture"] or ("demo-feed.xml" if a["id"] == DEMO_FEED["id"] else "")
            if not name or not (DATA / name).exists():
                continue
            try:
                items = self._prepare(a, (DATA / name).read_bytes(), now)
            except parsers.ParseError:
                log.exception("demo data %s", name)
                continue
            if not items:
                continue
            shift = now - 3600 * (1 + i) - max(it["published"] for it in items)
            for it in items:
                it["published"] = max(0.0, it["published"] + shift) if it["published"] else now
            total += self.store.upsert(a["id"], a["group"], items, now=now)["new"]
            self.state["sources"].setdefault(a["id"], {}).update({"checked": now, "ok": now, "error": ""})
        demo = self.store.by_key("url:example.org/madalean-demo/parite-des-carres")
        if demo is not None and not demo["fr"]:
            self.store.set_summary(demo["id"], "Question ouverte de démonstration : le carré d'un entier impair "
                                   "est-il toujours congru à $1$ modulo $8$ ? L'auteur relie la parité des carrés "
                                   "à la somme de deux entiers pairs.", "demo")
        self.state["last_refresh"] = now
        self._save_state()
        return total
