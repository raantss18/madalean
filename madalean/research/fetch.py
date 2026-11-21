"""The ONE network client of the research layer (ARCHITECTURE §15: SSRF through DOI/arXiv/URL fetchers).

Every URL the sources library, the literature search or the open-access download fetches goes through
`Fetcher.get`, which enforces, centrally:

- `mode == "local"` → nothing is fetched at all (`LocalModeError`), whatever the caller believes;
- `https` only, default port only, no user-info in the URL, no IP literal, no single-label / `.local` host;
- policy `api` (metadata calls): the host must be one of the scholarly API hosts of `API_HOSTS`;
  policy `public` (open-access PDF the API reported, metadata of a URL the user typed): any public host;
- resolve-then-connect: the DNS answer is checked by `PublicResolver` (every address must be globally routable:
  loopback, private, link-local, CGNAT, multicast, reserved and IPv4-mapped private addresses are refused) and
  aiohttp connects to exactly the checked addresses (no second resolution, so no DNS rebinding in between);
- redirects are followed by hand (≤ 5) and every hop is re-validated with the same rules;
- size limit (counted on the decompressed body), total and connect time limits, expected content types;
- no cookies (DummyCookieJar), no proxy from the environment, a contact-less User-Agent, a polite per-host
  rate limit (arXiv asks for 3 s between calls) and a short in-memory cache for API answers.

Tests and the demo mode replace the network with `ReplayTransport` (recorded answers); the checks above still run."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlsplit

USER_AGENT = "Madalean/2.0 (research library; scholarly metadata client)"
API_HOSTS = frozenset({
    "doi.org", "dx.doi.org", "api.crossref.org", "data.crossref.org", "api.datacite.org", "data.datacite.org",
    "export.arxiv.org", "arxiv.org", "api.openalex.org", "openlibrary.org", "api.zbmath.org", "zbmath.org",
    "api.semanticscholar.org",
})
MIN_INTERVAL = {"export.arxiv.org": 3.0, "arxiv.org": 3.0, "api.semanticscholar.org": 1.1}
DEFAULT_INTERVAL = 0.25
MAX_REDIRECTS = 5
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
CACHE_TTL = 600.0


class FetchError(Exception):
    """kind: local_mode | blocked | http | too_large | bad_type | timeout | network."""

    def __init__(self, kind: str, message: str = "", status: int = 0, url: str = ""):
        super().__init__(message or kind)
        self.kind, self.status, self.url = kind, status, url


class LocalModeError(FetchError):
    def __init__(self, url: str = ""):
        super().__init__("local_mode", "local mode: nothing leaves this machine", url=url)


@dataclass
class Response:
    url: str
    status: int
    headers: dict = field(default_factory=dict)      # lower-case names
    body: bytes = b""

    @property
    def content_type(self) -> str:
        return str(self.headers.get("content-type", "")).split(";")[0].strip().lower()

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.body.decode("utf-8", "replace"))


Transport = Callable[[str, dict, int, float], Awaitable[Response]]


# ---------------------------------------------------------------- address checks
def ip_allowed(addr: str) -> bool:
    """True only for globally routable unicast addresses (IPv4-mapped / 6to4 forms are unwrapped first)."""
    try:
        ip = ipaddress.ip_address(addr.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.sixtofour is not None:
            ip = ip.sixtofour
        elif ip.teredo is not None:
            return False
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or \
            ip.is_unspecified or getattr(ip, "is_site_local", False):
        return False
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
        return False                     # CGNAT (Tailscale addresses live here)
    return ip.is_global


def check_url(url: str, policy: str = "api") -> str:
    """Validate one URL (every redirect hop too). Returns the lower-case host; raises FetchError('blocked')."""
    try:
        u = urlsplit(url)
    except ValueError:
        raise FetchError("blocked", "malformed URL", url=url)
    if u.scheme != "https":
        raise FetchError("blocked", "only https URLs are fetched", url=url)
    if u.username or u.password or "@" in u.netloc:
        raise FetchError("blocked", "credentials in URL", url=url)
    try:
        port = u.port
    except ValueError:
        raise FetchError("blocked", "bad port", url=url)
    if port not in (None, 443):
        raise FetchError("blocked", "non-default port", url=url)
    host = (u.hostname or "").rstrip(".").lower()
    if not host:
        raise FetchError("blocked", "no host", url=url)
    try:
        ipaddress.ip_address(host.strip("[]"))
        raise FetchError("blocked", "IP literals are not fetched", url=url)
    except ValueError:
        pass
    if "." not in host or host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home",
                                                                 ".arpa", ".ts.net", ".corp")):
        raise FetchError("blocked", f"host {host!r} is not a public name", url=url)
    if policy == "api" and host not in API_HOSTS:
        raise FetchError("blocked", f"host {host!r} is not an allowed scholarly API", url=url)
    if policy not in ("api", "public"):
        raise FetchError("blocked", "unknown policy", url=url)
    return host


try:
    from aiohttp.abc import AbstractResolver, ResolveResult  # type: ignore
except Exception:  # noqa: BLE001
    AbstractResolver = object  # type: ignore
    ResolveResult = dict  # type: ignore


class PublicResolver(AbstractResolver):  # type: ignore[misc]
    """getaddrinfo, then refuse the host if ANY returned address is not public (resolve-then-connect)."""

    def __init__(self, getaddrinfo=None):
        self._gai = getaddrinfo

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET):
        loop = asyncio.get_running_loop()
        gai = self._gai or loop.getaddrinfo
        try:
            infos = await gai(host, port, type=socket.SOCK_STREAM, family=family)
        except socket.gaierror as e:
            raise OSError(f"cannot resolve {host}: {e}") from e
        out = []
        for fam, _t, proto, _c, sa in infos:
            addr = sa[0]
            if not ip_allowed(addr):
                raise FetchError("blocked", f"{host} resolves to a non-public address ({addr})", url=host)
            out.append({"hostname": host, "host": addr, "port": sa[1] or port, "family": fam, "proto": proto,
                        "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV})
        if not out:
            raise OSError(f"cannot resolve {host}")
        return out

    async def close(self) -> None:
        return None


# ---------------------------------------------------------------- transports
class AiohttpTransport:
    """One GET without redirects through a session that can only connect to checked public addresses."""

    def __init__(self, resolver: PublicResolver | None = None):
        self.resolver = resolver or PublicResolver()
        self._session = None

    async def _sess(self):
        import aiohttp
        if self._session is None or self._session.closed:
            conn = aiohttp.TCPConnector(resolver=self.resolver, use_dns_cache=False, limit=8, ttl_dns_cache=None)
            self._session = aiohttp.ClientSession(connector=conn, cookie_jar=aiohttp.DummyCookieJar(), trust_env=False,
                                                  headers={"User-Agent": USER_AGENT})
        return self._session

    async def __call__(self, url: str, headers: dict, max_bytes: int, timeout: float) -> Response:
        import aiohttp
        s = await self._sess()
        try:
            async with s.get(url, headers=headers, allow_redirects=False,
                             timeout=aiohttp.ClientTimeout(total=timeout, sock_connect=8, sock_read=timeout)) as r:
                hdrs = {k.lower(): v for k, v in r.headers.items()}
                if r.status in (301, 302, 303, 307, 308):
                    return Response(str(r.url), r.status, hdrs, b"")
                clen = hdrs.get("content-length")
                if clen and clen.isdigit() and int(clen) > max_bytes:
                    raise FetchError("too_large", f"{clen} bytes > limit {max_bytes}", url=url)
                buf = bytearray()
                async for chunk in r.content.iter_chunked(65536):
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise FetchError("too_large", f"more than {max_bytes} bytes", url=url)
                return Response(str(r.url), r.status, hdrs, bytes(buf))
        except FetchError:
            raise
        except asyncio.TimeoutError as e:
            raise FetchError("timeout", f"no answer within {timeout:.0f} s", url=url) from e
        except aiohttp.ClientConnectorError as e:
            cause = e.os_error if hasattr(e, "os_error") else e
            if isinstance(cause, FetchError):
                raise cause
            raise FetchError("network", str(e)[:300], url=url) from e
        except aiohttp.ClientError as e:
            inner = e.__cause__ or e.__context__
            if isinstance(inner, FetchError):
                raise inner
            raise FetchError("network", str(e)[:300], url=url) from e

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


def _fixture_name(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:20]


class ReplayTransport:
    """Answers from recorded fixtures (`<dir>/index.json`: {url: {status, headers, file}}); unknown URL → 404.
    Used by the tests and by `serve --demo`. `requests` lists every URL asked."""

    def __init__(self, directory: Path, strict: bool = False, loose: bool = False):
        self.dir = Path(directory)
        self.strict = strict
        self.loose = loose                 # demo: an unrecorded query gets a recorded answer of the same endpoint
        self.requests: list[str] = []
        try:
            self.index = json.loads((self.dir / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.index = {}
        self.extra: dict[str, Response] = {}

    def add(self, url: str, body: bytes | str, status: int = 200, content_type: str = "application/json",
            headers: dict | None = None) -> None:
        data = body.encode() if isinstance(body, str) else body
        self.extra[url] = Response(url, status, {"content-type": content_type, **(headers or {})}, data)

    async def __call__(self, url: str, headers: dict, max_bytes: int, timeout: float) -> Response:
        self.requests.append(url)
        if url in self.extra:
            r = self.extra[url]
        elif url in self.index:
            e = self.index[url]
            body = (self.dir / e["file"]).read_bytes() if e.get("file") else b""
            r = Response(url, int(e.get("status", 200)), {k.lower(): v for k, v in (e.get("headers") or {}).items()},
                         body)
        else:
            alt = None
            if self.loose:
                u = urlsplit(url)
                alt = next((k for k in self.index if urlsplit(k).hostname == u.hostname and
                            urlsplit(k).path == u.path and self.index[k].get("status") == 200), None)
            if alt is not None:
                return await self.__call__(alt, headers, max_bytes, timeout)
            if self.strict:
                raise AssertionError(f"no fixture for {url}")
            return Response(url, 404, {"content-type": "text/plain"}, b"not recorded")
        if len(r.body) > max_bytes:
            raise FetchError("too_large", url=url)
        return r

    async def close(self) -> None:
        return None


class RecordingTransport:
    """Wraps a real transport and stores every answer as a fixture (used once, by the online tests)."""

    def __init__(self, inner, directory: Path):
        self.inner, self.dir = inner, Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    async def __call__(self, url: str, headers: dict, max_bytes: int, timeout: float) -> Response:
        r = await self.inner(url, headers, max_bytes, timeout)
        idx_path = self.dir / "index.json"
        try:
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            idx = {}
        name = _fixture_name(url) + ".bin"
        (self.dir / name).write_bytes(r.body)
        keep = {k: v for k, v in r.headers.items() if k in ("content-type", "location")}
        idx[url] = {"status": r.status, "headers": keep, "file": name}
        idx_path.write_text(json.dumps(idx, indent=1, sort_keys=True), encoding="utf-8")
        return r

    async def close(self) -> None:
        await self.inner.close()


# ---------------------------------------------------------------- fetcher
class Fetcher:
    def __init__(self, transport: Transport | None = None, timeout: float = 20.0):
        self.transport = transport or AiohttpTransport()
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cache: dict[str, tuple[float, Response]] = {}
        self.calls = 0

    async def _polite(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            gap = MIN_INTERVAL.get(host, DEFAULT_INTERVAL)
            wait = self._last.get(host, 0.0) + gap - time.monotonic()
            if wait > 0 and not isinstance(self.transport, ReplayTransport):
                await asyncio.sleep(wait)
            self._last[host] = time.monotonic()

    async def get(self, url: str, *, mode: str, policy: str = "api", accept: str = "", types: tuple[str, ...] = (),
                  max_bytes: int = DEFAULT_MAX_BYTES, timeout: float | None = None, cache: bool = True,
                  ok_status: tuple[int, ...] = (200,)) -> Response:
        """GET `url` under every rule of the module docstring. `mode` is mandatory: "local" refuses."""
        if mode == "local":
            raise LocalModeError(url)
        key = f"{accept}|{url}"
        hit = self._cache.get(key) if cache else None
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return hit[1]
        headers = {"User-Agent": USER_AGENT}
        if accept:
            headers["Accept"] = accept
        cur = url
        for _hop in range(MAX_REDIRECTS + 1):
            host = check_url(cur, policy)
            await self._polite(host)
            self.calls += 1
            r = await self.transport(cur, headers, max_bytes, timeout or self.timeout)
            if r.status in (301, 302, 303, 307, 308):
                loc = r.headers.get("location", "")
                if not loc:
                    raise FetchError("http", "redirect without location", r.status, cur)
                cur = urljoin(cur, loc)
                continue
            if r.status not in ok_status:
                raise FetchError("http", f"HTTP {r.status}", r.status, cur)
            if types and not any(r.content_type.startswith(t) for t in types):
                raise FetchError("bad_type", f"unexpected content type {r.content_type!r}", r.status, cur)
            if cache:
                self._cache[key] = (time.monotonic(), r)
                if len(self._cache) > 500:
                    self._cache.pop(next(iter(self._cache)))
            return r
        raise FetchError("blocked", "too many redirects", url=url)

    async def close(self) -> None:
        close = getattr(self.transport, "close", None)
        if close is not None:
            await close()


def effective_mode(ctx, project=None) -> str:
    """The network mode of an action: `local` when the settings say so OR the project is « local only »."""
    mode = getattr(ctx.settings, "mode", "auto")
    if project is not None:
        pm = (getattr(project, "extra", {}) or {}).get("mode")
        if pm == "local":
            return "local"
    return mode
