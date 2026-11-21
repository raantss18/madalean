"""All HTTP traffic of the brain goes through `Http`: one aiohttp session, central enforcement of `mode="local"`
(only loopback hosts), key isolation (a provider's key is only ever sent to that provider's host), fast offline
detection (short connect timeouts + cached reachability) and an SSE reader with a stall watchdog."""
from __future__ import annotations

import asyncio
import contextvars
import ipaddress
import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

import aiohttp

from .api import BrainError

# Mode of the current brain call: set by Brain.complete / run_agent so that any request made below them obeys it,
# whatever the code that issues it believes.
CALL_MODE: contextvars.ContextVar[str] = contextvars.ContextVar("madalean_brain_mode", default="auto")

USER_AGENT = "Madalean/2.0 (model engine)"
CONNECT_TIMEOUT = 4.0          # seconds to open a TCP+TLS connection to an online provider
PROBE_TTL = 30.0               # reachability cache
PROBES = [("1.1.1.1", 443), ("8.8.8.8", 443)]


class LocalModeViolation(BrainError):
    def __init__(self, host: str):
        super().__init__("offline", f"local mode: connection to {host!r} refused (only this machine is allowed)")


class KeyHostError(BrainError):
    def __init__(self, provider: str, host: str):
        super().__init__("error", f"refusing to send the {provider} key to {host!r}")


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.strip("[]").lower()
    if h == "localhost" or h.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


class HttpStatusError(Exception):
    def __init__(self, status: int, message: str, headers: Any = None, body: str = ""):
        super().__init__(f"HTTP {status}: {message}")
        self.status, self.message, self.headers, self.body = status, message, headers or {}, body


class NetworkError(Exception):
    """Connection failed (DNS, refused, TLS, connect timeout)."""


class StallError(Exception):
    """No data received for too long."""


def error_message(body: str) -> str:
    try:
        v = json.loads(body)
    except ValueError:
        return body.strip()[:500]
    if isinstance(v, list) and v:
        v = v[0]
    if isinstance(v, dict):
        e = v.get("error", v)
        if isinstance(e, dict):
            return str(e.get("message") or e.get("type") or e)[:500]
        if isinstance(e, str):
            return e[:500]
    return body.strip()[:500]


class Http:
    def __init__(self, key_hosts: dict[str, str]):
        """key_hosts: provider id -> the only hostname its key may be sent to."""
        self.key_hosts = dict(key_hosts)
        self._session: aiohttp.ClientSession | None = None
        self._online: tuple[float, bool] | None = None
        self._probe_lock = asyncio.Lock()

    # ------------------------------------------------------------------ guards
    def effective_mode(self, mode: str) -> str:
        return "local" if "local" in (mode, CALL_MODE.get()) else mode

    def check(self, url: str, mode: str, provider: str | None = None, key: str | None = None) -> None:
        host = host_of(url)
        if self.effective_mode(mode) == "local" and not is_loopback_host(host):
            raise LocalModeViolation(host)
        if key:
            allowed = self.key_hosts.get(provider or "")
            if not allowed or host != allowed:
                raise KeyHostError(provider or "?", host)

    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            trace = aiohttp.TraceConfig()

            async def on_start(_s, _ctx, params):          # second line of defence, for every request
                if CALL_MODE.get() == "local" and not is_loopback_host(params.url.host):
                    raise LocalModeViolation(params.url.host or "")
            trace.on_request_start.append(on_start)
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT}, trace_configs=[trace],
                connector=aiohttp.TCPConnector(limit=32, ttl_dns_cache=300),
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=CONNECT_TIMEOUT, connect=CONNECT_TIMEOUT + 4))
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    # ------------------------------------------------------------------ reachability
    def known_offline(self) -> bool:
        return self._online is not None and not self._online[1] and time.monotonic() - self._online[0] < PROBE_TTL

    def mark(self, online: bool) -> None:
        self._online = (time.monotonic(), online)

    async def online(self, mode: str = "auto") -> bool:
        """Is the Internet reachable? (two public resolvers, 1.5 s each, cached 30 s; never probed in local mode)"""
        if self.effective_mode(mode) == "local":
            return False
        if self._online is not None and time.monotonic() - self._online[0] < PROBE_TTL:
            return self._online[1]
        async with self._probe_lock:
            if self._online is not None and time.monotonic() - self._online[0] < PROBE_TTL:
                return self._online[1]

            async def one(h: str, p: int) -> bool:
                try:
                    _r, w = await asyncio.wait_for(asyncio.open_connection(h, p), 1.5)
                    w.close()
                    return True
                except (OSError, asyncio.TimeoutError):
                    return False
            res = await asyncio.gather(*(one(h, p) for h, p in PROBES))
            self.mark(any(res))
            return self._online[1]

    # ------------------------------------------------------------------ requests
    async def get_json(self, url: str, *, mode: str, timeout: float = 15, provider: str | None = None,
                       key: str | None = None, headers: dict | None = None, params: dict | None = None) -> Any:
        """GET and parse JSON; None on any failure (used for catalogue refresh and searches)."""
        try:
            self.check(url, mode, provider, key)
        except BrainError:
            return None
        h = dict(headers or {})
        if key:
            h.update(auth_headers(provider or "", key))
        try:
            async with self.session().get(url, headers=h, params=params,
                                          timeout=aiohttp.ClientTimeout(total=timeout, sock_connect=min(timeout, CONNECT_TIMEOUT))) as r:
                if r.status >= 400:
                    return None
                return json.loads(await r.read())
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError):
            return None

    async def post_json(self, url: str, body: Any, *, mode: str, timeout: float = 20, headers: dict | None = None) -> Any:
        try:
            self.check(url, mode)
        except BrainError:
            return None
        try:
            async with self.session().post(url, json=body, headers=headers or {},
                                           timeout=aiohttp.ClientTimeout(total=timeout, sock_connect=min(timeout, CONNECT_TIMEOUT))) as r:
                if r.status >= 400:
                    return None
                return json.loads(await r.read())
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError):
            return None

    @asynccontextmanager
    async def stream(self, url: str, body: dict, *, mode: str, provider: str | None = None, key: str | None = None,
                     headers: dict | None = None, first_byte_timeout: float = 120) -> AsyncIterator[aiohttp.ClientResponse]:
        """POST a streaming request. Raises HttpStatusError (status ≥ 400, body read), NetworkError, LocalModeViolation,
        KeyHostError."""
        self.check(url, mode, provider, key)
        h = {"Content-Type": "application/json", **(headers or {})}
        if key:
            h.update(auth_headers(provider or "", key))
        try:
            resp = await asyncio.wait_for(self.session().post(url, data=json.dumps(body), headers=h), first_byte_timeout)
        except asyncio.TimeoutError as e:
            raise StallError(f"no response after {first_byte_timeout:.0f} s") from e
        except aiohttp.ClientConnectorError as e:
            raise NetworkError(str(e)) from e
        except (aiohttp.ClientError, OSError) as e:
            raise NetworkError(str(e)) from e
        try:
            if resp.status >= 400:
                try:
                    text = (await asyncio.wait_for(resp.read(), 30)).decode("utf-8", "replace")
                except (asyncio.TimeoutError, aiohttp.ClientError):
                    text = ""
                raise HttpStatusError(resp.status, error_message(text) or resp.reason or "", resp.headers, text)
            yield resp
        finally:
            resp.close()


def auth_headers(provider: str, key: str) -> dict[str, str]:
    if provider == "anthropic":
        return {"x-api-key": key}
    return {"Authorization": f"Bearer {key}"}


async def sse_events(resp: aiohttp.ClientResponse, stall: float) -> AsyncIterator[tuple[str, str]]:
    """(event, data) pairs of a Server-Sent-Events body; a JSON body (provider ignored `stream`) is yielded once as
    ("json", body). Raises StallError when nothing arrives for `stall` seconds."""
    ctype = resp.headers.get("Content-Type", "")
    if "event-stream" not in ctype:
        try:
            raw = await asyncio.wait_for(resp.read(), stall)
        except asyncio.TimeoutError as e:
            raise StallError(f"no data for {stall:.0f} s") from e
        yield "json", raw.decode("utf-8", "replace")
        return
    buf = b""
    event, data = "", []
    while True:
        try:
            chunk = await asyncio.wait_for(resp.content.readany(), stall)
        except asyncio.TimeoutError as e:
            raise StallError(f"no data for {stall:.0f} s") from e
        except (aiohttp.ClientPayloadError, aiohttp.ClientConnectionError) as e:
            raise NetworkError(f"stream cut: {e}") from e
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            s = line.decode("utf-8", "replace").rstrip("\r")
            if not s:
                if data:
                    yield event or "message", "\n".join(data)
                event, data = "", []
                continue
            if s.startswith(":"):
                continue
            if s.startswith("event:"):
                event = s[6:].strip()
            elif s.startswith("data:"):
                data.append(s[5:].lstrip(" "))
    if data:
        yield event or "message", "\n".join(data)
