"""Security middleware (ARCHITECTURE §4).

- local listener (127.0.0.1:11500): trusted, but the Host header must be a loopback name (DNS-rebinding guard) and a
  cross-site browser Origin is refused on state-changing requests and WebSocket upgrades (CSRF guard).
- remote listener (127.0.0.1:11501, published by `tailscale serve`) and the optional LAN listener: every request
  needs a device token (`Authorization: Bearer` or the `madalean_token` cookie), except `GET /api/hello`,
  `POST /api/pair`, `POST /api/logout` and the static UI files (the pairing screen must load). Host-only routes
  answer 403 there. CORS stays closed (no Access-Control-* header is ever sent)."""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from aiohttp import web

from ..logs import get
from ..security import TOKEN_COOKIE
from .common import CTX, error

log = get("auth")
LOCAL_PORTS = web.AppKey("local_ports", set)
# Remote listener (§18): Host allow-list = loopback names, Tailscale names (*.ts.net: the embedded node
# madalean.<tailnet>.ts.net through madalean-net, or `tailscale serve` as the documented alternative) and the extra
# names in REMOTE_HOSTS (the node's current DNS name, set by the net plugin). Anything else is a DNS-rebinding attempt.
REMOTE_PORTS = web.AppKey("remote_ports", set)
REMOTE_HOSTS = web.AppKey("remote_hosts", set)
# /api/session authenticates with its one-time ticket; /api/session/ticket and /api/devices/self/forget check the
# Bearer token themselves (they also work on the local listener, where no device is attached to the request).
PUBLIC_API = {("GET", "/api/hello"), ("HEAD", "/api/hello"), ("POST", "/api/pair"), ("POST", "/api/logout"),
              ("GET", "/api/session")}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _sock_port(request: web.Request) -> int | None:
    t = request.transport
    sn = t.get_extra_info("sockname") if t else None
    return sn[1] if sn else None


def _peer_loopback(request: web.Request) -> bool:
    try:
        return ipaddress.ip_address((request.remote or "").split("%")[0]).is_loopback
    except ValueError:
        return False


def token_of(request: web.Request) -> tuple[str | None, str]:
    """(token, how): how = bearer | cookie | ''."""
    h = request.headers.get("Authorization", "")
    if h[:7].lower() == "bearer ":
        return h[7:].strip(), "bearer"
    c = request.cookies.get(TOKEN_COOKIE)
    if c:
        return c, "cookie"
    return None, ""


def _host_name(host: str) -> str:
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def origin_ok(request: web.Request, local: bool) -> bool:
    origin = request.headers.get("Origin")
    if origin is None:
        return True
    if origin == "null":
        return False
    o = urlsplit(origin)
    if not o.netloc:
        return False
    # Exact host:port only. S-H: « any loopback origin » let every other web server of the machine
    # (http://127.0.0.1:8888, a dev server, a page of another local app) drive the trusted listener.
    # X-Forwarded-Host is the madalean-net sidecar's (it overwrites the client's); never trusted on the local port.
    hosts = {request.headers.get("Host", "")}
    if not local:
        hosts.add(request.headers.get("X-Forwarded-Host", ""))
    hosts.discard("")
    return o.netloc.lower() in {h.lower() for h in hosts}


# Cross-site requests a browser may still send without an Origin check biting (Fetch Metadata): <img>/<script>/
# <link> GETs, no-cors fetches, cross-site navigations. Only a top-level navigation to the UI (or to the shells'
# /api/session ticket exchange) may come from another site; everything else must be same-origin.
NAV_OK_API = {"/api/session", "/api/hello"}


def fetch_metadata_ok(request: web.Request) -> bool:
    site = request.headers.get("Sec-Fetch-Site", "").lower()
    if site in ("", "same-origin", "none"):
        return True
    if request.method in ("GET", "HEAD") and request.headers.get("Sec-Fetch-Mode", "").lower() == "navigate":
        path = request.path
        return is_static(path) or path in NAV_OK_API
    return False


def remote_host_ok(request: web.Request) -> bool:
    name = _host_name(request.headers.get("Host", "")).lower().rstrip(".")
    if name in LOOPBACK_HOSTS or name.endswith(".ts.net"):
        return True
    return name in {h.lower().rstrip(".") for h in request.app.get(REMOTE_HOSTS, set())}


def is_static(path: str) -> bool:
    return not (path.startswith("/api/") or path == "/api" or path.startswith("/jupyter"))


@web.middleware
async def security_middleware(request: web.Request, handler):
    ctx = request.app[CTX]
    local = _sock_port(request) in request.app[LOCAL_PORTS] and _peer_loopback(request)
    request["local"] = local
    request["device"] = None
    path = request.path
    if local:
        if _host_name(request.headers.get("Host", "")) not in LOOPBACK_HOSTS:
            return error(403, "bad_host")
    elif _sock_port(request) in request.app.get(REMOTE_PORTS, set()) and not remote_host_ok(request):
        return error(403, "bad_host")
    is_ws = request.headers.get("Upgrade", "").lower() == "websocket"
    if not fetch_metadata_ok(request):
        log.warning("refused cross-site %s %s (%s)", request.method, path, request.headers.get("Sec-Fetch-Site"))
        return error(403, "cross_site")
    how = ""
    if not local:
        public = (request.method, path) in PUBLIC_API or (request.method in ("GET", "HEAD") and is_static(path))
        token, how = token_of(request)
        dev = ctx.devices.check(token, request.headers.get("X-Forwarded-For", request.remote or "")) if token else None
        if dev is None and not public:
            return error(401, "unauthorized")
        request["device"] = dev
    request["auth"] = how if request["device"] is not None else ""
    if (request.method not in SAFE_METHODS or is_ws) and how != "bearer" and not origin_ok(request, local):
        log.warning("refused origin %s on %s %s", request.headers.get("Origin"), request.method, path)
        return error(403, "bad_origin")
    if not local and getattr(request.match_info.route.handler, "__madalean_host_only__", False):
        return error(403, "host_only")
    resp = await handler(request)
    if not is_ws:
        try:
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("Referrer-Policy", "no-referrer")
            resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            if path.startswith("/api/"):
                resp.headers.setdefault("Cache-Control", "no-store")
        except (AttributeError, RuntimeError):
            pass
    return resp
