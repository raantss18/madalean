"""hello, pairing, devices, state, settings, models, system, updates."""
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import time
from pathlib import Path

from aiohttp import web

from .. import config, deps, names
from ..deps import health as deps_health
from ..context import HOST_ONLY_SETTINGS
from ..i18n import msg
from ..security import TOKEN_COOKIE, PairingError, RateLimiter
from .common import body, ctx_of, error, host_only, ok, valid_id

routes = web.RouteTableDef()
PAIR_LIMIT = RateLimiter(10, 60.0)
PAIR_GLOBAL = RateLimiter(30, 60.0)


@routes.get("/api/hello")
async def hello(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    return ok({"name": "madalean", "version": ctx.version, "paired": request["local"] or request["device"] is not None,
               "local": request["local"], "host_name": ctx.settings.host_name or ctx.host_name, "demo": ctx.demo,
               "lang": ctx.settings.language})


@routes.post("/api/pair")
async def pair(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    who = request.headers.get("X-Forwarded-For", request.remote or "?").split(",")[0].strip()
    if not PAIR_GLOBAL.allow("*") or not PAIR_LIMIT.allow(who):
        return error(429, "rate_limited", "Trop d'essais : attendez une minute.")
    data = await body(request)
    try:
        ctx.pairing.consume(str(data.get("code", "")))
    except PairingError as e:
        keys = {"locked": "Appairage bloqué pendant {m} minutes après trop d'erreurs.",
                "expired": "Ce code a expiré : demandez-en un nouveau sur l'ordinateur hôte.",
                "no_code": "Aucun code actif : affichez-en un sur l'ordinateur hôte.",
                "wrong": "Code incorrect."}
        status = 429 if e.kind == "locked" else 403
        return error(status, e.kind, keys[e.kind], m=int(round(e.retry_after / 60)) or 1)
    name = str(data.get("device_name", ""))[:80]
    if pair_kind(request, data) == "app":
        # app shells: long-lived token kept in the OS keystore, cookie obtained later through a session ticket
        dev, token = await asyncio.to_thread(ctx.devices.add, name, str(data.get("client")))
        publish_devices(ctx)
        return ok({"kind": "app", "token": token, "device": dev.public()})
    # plain browser: a temporary session (no token in the body, cookie without Max-Age, idle/absolute expiry)
    sess, secret = ctx.browser_sessions.add(name or _browser_name(request), request.headers.get("X-Forwarded-For",
                                                                                              request.remote or ""))
    publish_devices(ctx)
    resp = ok({"kind": "browser", "device": sess.public(ctx.browser_sessions.idle_s(), ctx.browser_sessions.clock()),
               "idle_minutes": ctx.settings.browser_session_idle_minutes})
    resp.set_cookie(TOKEN_COOKIE, secret, httponly=True, secure=is_https(request), samesite="Strict", path="/")
    return resp


def is_https(request: web.Request) -> bool:
    return request.secure or request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower() == "https"


def pair_kind(request: web.Request, data: dict) -> str:
    """"app" only for the shells' native HTTP clients (`client: app-desktop|app-android`). Anything a browser sends
    (it always adds Origin / Sec-Fetch-* on a POST) is a browser, whatever `client` it claims: a web page can never
    obtain a long-lived device token."""
    from ..security import APP_CLIENTS
    browserish = "Origin" in request.headers or "Sec-Fetch-Site" in request.headers or "Sec-Fetch-Mode" in request.headers
    if browserish:
        return "browser"
    if data.get("client") in APP_CLIENTS:
        return "app"
    if data.get("client") == "browser":
        return "browser"
    return "app"          # shells of before 2.0.x (no `client` field) talk without browser headers


def _browser_name(request: web.Request) -> str:
    ua = request.headers.get("User-Agent", "")
    for k in ("Firefox", "Edg", "Chrome", "Safari"):
        if k in ua:
            return {"Edg": "Edge"}.get(k, k)
    return "browser"


def publish_devices(ctx) -> None:
    ctx.publish("devices.updated", {"devices": ctx.devices.list(), "apps": ctx.devices.list(),
                                    "browsers": ctx.browser_sessions.list()})


async def revoke_any(ctx, did: str) -> bool:
    ok_ = (ctx.browser_sessions.revoke(did) if did.startswith("b-")
           else await asyncio.to_thread(ctx.devices.revoke, did))
    if ok_:
        publish_devices(ctx)
    ctx.close_credential(did)          # open WebSockets → 4401, streaming it started is cancelled
    return ok_


@routes.post("/api/logout")
async def logout(request: web.Request) -> web.Response:
    """Forget this device (remote): its token is revoked and the cookie cleared."""
    ctx = ctx_of(request)
    dev = request["device"]
    if dev is not None:
        await revoke_any(ctx, dev.id)
    resp = ok({"ok": True})
    resp.del_cookie(TOKEN_COOKIE, path="/")
    return resp


# ---------------------------------------------------------------- shells: ticket → cookie (docs/SHELLS.md)
def _bearer_device(request: web.Request):
    """The device of the `Authorization: Bearer` token (never the cookie: no CSRF surface)."""
    h = request.headers.get("Authorization", "")
    if h[:7].lower() != "bearer ":
        return None
    return ctx_of(request).devices.check(h[7:].strip(), request.headers.get("X-Forwarded-For", request.remote or ""))


@routes.post("/api/session/ticket")
async def session_ticket(request: web.Request) -> web.Response:
    dev = _bearer_device(request)
    if dev is None:
        return error(401, "unauthorized")
    ctx = ctx_of(request)
    return ok({"ticket": ctx.tickets.issue(dev.id), "expires_in": int(ctx.tickets.ttl)})


def safe_next(value: str | None) -> str:
    """Same-origin relative path only: starts with one `/`, no `//`, no backslash, no control character."""
    v = value or ""
    if (not v.startswith("/") or v.startswith("//") or "\\" in v or "//" in v.split("?", 1)[0]
            or any(ord(c) < 0x20 or ord(c) == 0x7f for c in v) or len(v) > 2000):
        return "/"
    return v


SESSION_PAGE = ('<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer">'
                '<meta http-equiv="refresh" content="0;url={url}"><title>Madalean</title></head>'
                '<body><p><a href="{url}">Madalean</a></p></body></html>')


@routes.get("/api/session")
async def session_open(request: web.Request) -> web.Response:
    """Swap a one-time ticket for the HttpOnly session cookie. 200 + meta refresh (not a 303: WebKitGTK withholds a
    SameSite=Strict cookie after a redirect started by a cross-site page). The query string is never logged."""
    import html
    ctx = ctx_of(request)
    did = ctx.tickets.consume(request.query.get("ticket", ""))
    secret = await asyncio.to_thread(ctx.devices.add_session, did) if did else None
    if secret is None:
        return web.Response(status=303, headers={"Location": "/pair?reason=ticket", "Cache-Control": "no-store",
                                                 "Referrer-Policy": "no-referrer"})
    url = html.escape(safe_next(request.query.get("next")), quote=True)
    resp = web.Response(text=SESSION_PAGE.format(url=url), content_type="text/html", headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; script-src 'none'; style-src 'none'; img-src 'none'; "
                                   "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"})
    secure = request.secure or request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower() == "https"
    resp.set_cookie(TOKEN_COOKIE, secret, max_age=10 * 365 * 86400, httponly=True, secure=secure, samesite="Strict",
                    path="/")
    return resp


@routes.post("/api/devices/self/forget")
async def device_forget_self(request: web.Request) -> web.Response:
    """A device revokes itself (Bearer, or the cookie of a paired browser) → 204."""
    ctx = ctx_of(request)
    dev = request["device"] or _bearer_device(request)
    if dev is None:
        return error(401, "unauthorized")
    await revoke_any(ctx, dev.id)
    resp = web.Response(status=204)
    resp.del_cookie(TOKEN_COOKIE, path="/")
    return resp


@routes.post("/api/pairing/start")
@host_only
async def pairing_start(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    code, ttl = ctx.pairing.start()
    url = await remote_url(ctx)
    return ok({"code": code, "expires": time.time() + ttl, "expires_in": ttl, "remote_url": url,
               "addresses": await pair_addresses(ctx, request.app, url)})


def _is_tailnet_ipv4(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10")


def _is_lan_ipv4(ip: str) -> bool:
    """Private IPv4 of a home/office network (RFC 1918), never loopback, link-local or the tailnet's CGNAT range."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and any(a in ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12",
                                                                          "192.168.0.0/16"))


def lan_ipv4() -> str | None:
    """The host's address on its local network: source address of the default route (a UDP `connect` sends no
    packet). None when it is not a private RFC 1918 address."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))           # TEST-NET-1: never contacted
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip if _is_lan_ipv4(ip) else None


async def pair_addresses(ctx, app: web.Application, url: str | None) -> dict:
    """Fallback addresses for the pairing QR code (docs/SHELLS.md « Pair link »): the tailnet name (HTTPS), the
    node's tailnet IPv4 (the app then still talks TLS to the name, only the DNS lookup is skipped) and, only while
    the LAN listener is open, `<LAN IPv4>:<port>` (plain HTTP, same rules as any LAN client: code + token)."""
    from .auth import LAN_PORTS
    host = url.split("://", 1)[1].split("/", 1)[0] if url else None
    ip = None
    nm = getattr(ctx, "net", None)
    if nm is not None and host:
        try:
            ip = next((a for a in nm.status().get("ips") or [] if _is_tailnet_ipv4(str(a))), None)
        except Exception:  # noqa: BLE001
            ip = None
    lan: list[str] = []
    ports = sorted(app.get(LAN_PORTS, set()))
    if ports:
        lip = await asyncio.to_thread(lan_ipv4)
        if lip:
            lan.append(f"{lip}:{ports[0]}")
    return {"host": host, "ip": ip, "lan": lan}


async def remote_url(ctx) -> str | None:
    """Address other devices use: from the Tailscale node status (madalean.runtime.net, session S-I, when present),
    else from the configured host name when it is a tailnet name; None when unknown."""
    nm = getattr(ctx, "net", None)          # embedded Tailscale node (S-I): its own HTTPS name, port 443
    if nm is not None:
        try:
            st = nm.status()
            dns = (st.get("dns_name") or "").rstrip(".")
            if st.get("state") == "running" and dns:
                return f"https://{dns}"
        except Exception:  # noqa: BLE001
            pass
    try:
        from ..runtime import net  # type: ignore[attr-defined]
        fn = getattr(net, "remote_url", None)
        if fn is not None:
            try:
                u = fn(ctx)
            except TypeError:
                u = fn()
            if asyncio.iscoroutine(u):
                u = await asyncio.wait_for(u, 5)
            if isinstance(u, str) and u.startswith("https://"):
                return u
    except Exception:  # noqa: BLE001 (absent or failing: fall back)
        pass
    host = (ctx.settings.host_name or "").strip().rstrip(".")
    if host.endswith(".ts.net"):
        return f"https://{host}:10500"
    return None


@routes.get("/api/pairing")
@host_only
async def pairing_status(request: web.Request) -> web.Response:
    return ok(ctx_of(request).pairing.status())


@routes.get("/api/devices")
@host_only
async def devices(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    apps = ctx.devices.list()
    return ok({"devices": apps, "apps": apps, "browsers": ctx.browser_sessions.list(),
               "browser_idle_minutes": ctx.settings.browser_session_idle_minutes})


@routes.delete("/api/devices/{id}")
@host_only
async def device_revoke(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if not await revoke_any(ctx, valid_id(request.match_info["id"])):
        return error(404, "not_found")
    return ok({"ok": True})


@routes.get("/api/state")
async def state(request: web.Request) -> web.Response:
    from ..repo import dossier_summary
    ctx = ctx_of(request)
    dev = request["device"]
    return ok({
        "version": ctx.version, "host_name": ctx.settings.host_name or ctx.host_name, "local": request["local"],
        "device": dev.public() if dev else None, "demo": ctx.demo, "brain": ctx.brain_kind,
        "lang": ctx.settings.language, "seq": ctx.bus.seq, "boot": ctx.bus.boot,
        "settings": ctx.settings_public(), "host_only_settings": sorted(HOST_ONLY_SETTINGS),
        "projects": [p.to_dict() for p in ctx.projects.list()],
        "dossiers": [dossier_summary(d) for d in ctx.repo.list()],
        "jobs": {"active": [j.to_dict() for j in ctx.orchestrator.active()],
                 "recent": [j.to_dict() for j in ctx.orchestrator.recent(30)]},
        "models": await ctx.models_public(),
        "system": {**ctx.system_light(), "workspaces": ctx.workspaces_public()},
        "library": {"count": len(ctx.library.entries)},
        "updates": ctx.updates.status(),
        "jupyter": ctx.jupyter.status(),
        "migration": ctx.migration,
    })


# ---------------------------------------------------------------- settings
@routes.get("/api/settings")
async def settings_get(request: web.Request) -> web.Response:
    return ok({"settings": ctx_of(request).settings_public()})


@routes.patch("/api/settings")
async def settings_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    s, errors = await ctx.patch_settings(data, request["local"])
    if errors:
        status = 403 if any(e.startswith("host_only:") for e in errors) else 400
        return web.json_response({"error": "invalid_settings", "details": errors, "settings": s}, status=status)
    return ok({"settings": s})


# ---------------------------------------------------------------- models
@routes.get("/api/models")
async def models(request: web.Request) -> web.Response:
    return ok(await ctx_of(request).models_public())


@routes.post("/api/models/keys")
async def models_key_set(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    provider, key = str(data.get("provider", "")), data.get("key")
    if not isinstance(key, str) or not key.strip() or len(key) > 4096:
        return error(400, "bad_key")
    try:
        backend = await asyncio.to_thread(ctx.keys.set, provider, key)
    except ValueError:
        return error(400, "bad_provider")
    cleared: dict = {}
    fn = getattr(ctx.brain, "key_saved", None)      # S-AO (D47): a new key lifts the provider's pauses at once
    if fn is not None:
        try:
            cleared = fn(provider) or {}
        except Exception:  # noqa: BLE001
            cleared = {}
    _notify_keys(ctx)
    testing = data.get("test", True) is not False
    if testing:                                     # the quick key test (the web UI runs its own: `test: false`)
        async def run_test() -> None:
            try:
                res = await asyncio.wait_for(key_test(ctx, provider), 90)
            except Exception as e:  # noqa: BLE001
                from ..logs import redact
                res = {"provider": provider, "ok": False, "reason": redact(str(e))[:300]}
            ctx.publish("models.key_test", res)
        ctx.spawn(run_test())
    return ok({"provider": provider, "set": True, "backend": backend, "unpaused": int(cleared.get("unpaused", 0)),
               "testing": testing})


@routes.delete("/api/models/keys/{provider}")
async def models_key_delete(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    had = await asyncio.to_thread(ctx.keys.delete, request.match_info["provider"][:41])
    _notify_keys(ctx)
    return ok({"provider": request.match_info["provider"], "set": False, "existed": had})


def _notify_keys(ctx) -> None:
    if hasattr(ctx.brain, "keys_changed"):
        try:
            ctx.brain.keys_changed()
        except Exception:  # noqa: BLE001
            pass
    ctx.publish("models.status", {"keys": {p: True for p in ctx.keys.providers()}})


@routes.post("/api/models/test")
async def models_test(request: web.Request) -> web.Response:
    """A real call: one tiny completion restricted to `provider` (its best model for role explain, online).
    → {provider, ok, reason, model, models (models of this provider the router can use), latency_s}. The key is never
    echoed (errors are redacted)."""
    ctx = ctx_of(request)
    data = await body(request)
    return ok(await key_test(ctx, str(data.get("provider", ""))[:41]))


async def key_test(ctx, provider: str) -> dict:
    """The quick key test of `provider` (POST /api/models/test; S-AO: also right after a key is saved)."""
    from ..logs import redact
    from ..pipeline.runner import model_key
    if provider == "github":
        # not a model provider: the GitHub token is tested by a read-only identity check (« Publier »), never by an LLM
        # call (which reported « no model, is the key valid? » for a perfectly good token) nor a catalogue refresh
        from ..research import publish
        res = await publish.check(ctx)
        first_bad = next((c for c in res["checks"] if c["ok"] is False), None)
        return {"provider": provider, "ok": bool(res.get("ok")), "login": res.get("login", ""),
                "token_kind": res.get("token_kind", ""), "github": res, "models": 0,
                "reason": "" if res.get("ok") else ("github:" + (first_bad or {}).get("code", "unknown"))}
    if provider == "huggingface" and hasattr(ctx.brain, "hf_check"):
        # S-T: a read-only identity check on the Hub (no inference, nothing billed), then the live Goedel models
        try:
            res = await asyncio.wait_for(ctx.brain.hf_check(), 60)
        except Exception as e:  # noqa: BLE001
            return {"provider": provider, "ok": False, "reason": redact(str(e))[:300], "models": 0}
        return {"provider": provider, **res}
    fn = getattr(ctx.brain, "test", None)
    if fn is not None:
        try:
            res = await asyncio.wait_for(fn(provider), 60)
        except Exception as e:  # noqa: BLE001
            return {"provider": provider, "ok": False, "reason": redact(str(e))[:300]}
        return {"provider": provider, **(res if isinstance(res, dict) else {"ok": bool(res)})}
    if ctx.settings.mode == "local":
        return {"provider": provider, "ok": None, "reason": "local_mode", "models": 0}

    def mine(role: str) -> list:
        try:
            return [c for c in ctx.brain.candidates(role, "online") if c.provider == provider]
        except Exception:  # noqa: BLE001
            return []
    pick_fn = getattr(ctx.brain, "test_model", None)        # S-M: a cheap, reliable model of this provider

    def pick() -> dict | None:
        try:
            return pick_fn(provider) if pick_fn is not None else None
        except Exception:  # noqa: BLE001
            return None
    cands = mine("explain")
    chosen = pick()
    if not cands and chosen is None:
        try:
            await asyncio.wait_for(ctx.brain.refresh(), 30)
        except Exception:  # noqa: BLE001
            pass
        cands = mine("explain") or mine("assistant") or mine("prove")
        chosen = pick()
    unlocked = {c.key for role in ("explain", "prove", "formalize", "assistant") for c in mine(role)}
    if chosen is not None:
        unlocked = unlocked or {chosen["key"]}
        n_models = max(len(unlocked), int(chosen.get("models") or 0))
    else:
        n_models = len(unlocked)
    if not cands and chosen is None:
        return {"provider": provider, "ok": False, "reason": "no_model", "models": 0}
    test_key = chosen["key"] if chosen is not None else cands[0].key
    t0 = time.monotonic()
    try:
        # max_tokens 16 is too short for a model that thinks first: 256 still costs almost nothing
        c = await asyncio.wait_for(ctx.brain.complete("explain", [{"role": "user", "content": "Reply with exactly: OK"}],
                                                      mode="online", prefer=test_key, max_tokens=256 if chosen else 16,
                                                      temperature=0.0), 60)
    except asyncio.TimeoutError:
        return {"provider": provider, "ok": False, "reason": "timeout", "models": n_models, "tested": test_key}
    except Exception as e:  # noqa: BLE001
        return {"provider": provider, "ok": False, "reason": redact(str(e))[:300], "models": n_models,
                "tested": test_key}
    latency = round(time.monotonic() - t0, 2)
    used = model_key(c.model)
    good = getattr(c.model, "provider", "") == provider
    return {"provider": provider, "ok": good, "model": used, "models": n_models, "latency_s": latency,
            "tested": test_key, "why": (chosen or {}).get("why", ""),
            "reason": "" if good else "fallback: " + redact("; ".join(c.fallbacks or []))[:300]}


@routes.get("/api/models/leaderboard")
async def models_leaderboard(request: web.Request) -> web.Response:
    """Which model really solved what here (S-J): rows per model × task (× domain), best first. Read-only."""
    from ..pipeline.tournament import leaderboard_of
    ctx = ctx_of(request)
    task = request.query.get("task") or None
    lb = leaderboard_of(ctx)
    s = ctx.settings
    return ok({"entries": lb.table(task if task in ("prove", "formalize", "explain") else None),
               "tournament": {k: getattr(s, k) for k in ("tournament_enabled", "tournament_contestants",
                                                         "tournament_max_rounds", "tournament_max_minutes",
                                                         "tournament_attempts_per_model")}})


@routes.post("/api/models/leaderboard/reset")
@host_only
async def models_leaderboard_reset(request: web.Request) -> web.Response:
    from ..pipeline.tournament import leaderboard_of
    ctx = ctx_of(request)
    await asyncio.to_thread(leaderboard_of(ctx).reset)
    ctx.publish("models.status", {"leaderboard": "reset"})
    return ok({"entries": []})


@routes.get("/api/models/spend")
async def models_spend(request: web.Request) -> web.Response:
    """Paid-model spending (S-M): this month's total, the caps, recent calls (model, tokens, USD), list prices.
    Read-only; the caps are settings (`claude_cap_proof_usd`, `claude_cap_month_usd`)."""
    ctx = ctx_of(request)
    fn = getattr(ctx.brain, "spend_summary", None)
    if fn is not None:
        return ok(await asyncio.to_thread(fn))
    from ..brain.spend import Ledger
    s = ctx.settings
    out = Ledger(ctx.paths.config / "brain-spend.json").summary(s.claude_cap_proof_usd, s.claude_cap_month_usd)
    out.update(enabled=s.claude_reinforce, key_set="anthropic" in set(ctx.keys.providers()), model=s.claude_model,
               models=[])
    return ok(out)


_CPU_LAST: list[int] = []
_REQ_ID = re.compile(r"[A-Za-z0-9_.:-]{1,80}")


def _cpu_percent() -> float | None:
    """Whole-machine CPU use since the previous call (two reads of /proc/stat); None on the first call or off Linux."""
    try:
        with open("/proc/stat", encoding="ascii") as f:
            vals = [int(x) for x in f.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    idle, total = vals[3] + (vals[4] if len(vals) > 4 else 0), sum(vals)
    prev = list(_CPU_LAST)
    _CPU_LAST[:] = [idle, total]
    if not prev or total <= prev[1]:
        return None
    return round(100.0 * (1 - (idle - prev[0]) / (total - prev[1])), 1)


def _memory() -> dict | None:
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0])
        total, avail = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0))
        return {"total_mb": total // 1024, "used_mb": (total - avail) // 1024}
    except (OSError, ValueError, KeyError):
        return None


@routes.get("/api/usage")
async def usage_status(request: web.Request) -> web.Response:
    """Status panel of the web UI (S-AK, D43): machine resources now, tokens and spending (today / this month / the
    requests named in `?requests=`). Read only when the panel is open (the UI polls it every few seconds then, never
    otherwise)."""
    ctx = ctx_of(request)
    from ..brain import usage
    from ..brain.spend import Ledger, day_of_rows
    if time.time() - ctx.monitor.t > 4:
        try:
            await ctx.monitor.poll()
        except Exception:  # noqa: BLE001
            pass
    gpu = ctx.monitor.gpu
    cpu = await asyncio.to_thread(_cpu_percent)
    try:
        load = round(os.getloadavg()[0], 2)
    except OSError:
        load = None
    wanted = [x for x in request.query.get("requests", "").split(",") if _REQ_ID.fullmatch(x)][:20]
    tally = usage.TALLY.summary(wanted)
    ledger = getattr(ctx.brain, "ledger", None)
    if ledger is None:
        ledger = await asyncio.to_thread(Ledger, ctx.paths.config / "brain-spend.json")
    s = ctx.settings
    paid_today, paid_month = day_of_rows(ledger)
    return ok({
        "mode": s.mode,
        "resources": {"cpu_percent": cpu, "cpus": os.cpu_count(), "load": load, "memory": await asyncio.to_thread(_memory),
                      "gpu": ({k: gpu[k] for k in ("name", "total", "used", "util", "temp")} if gpu else None),
                      "t": time.time()},
        "tokens": {"today": tally["today"], "month": tally["month"], "by_provider_today": tally["by_provider_today"]},
        "spend": {"today_usd": paid_today, "month_usd": paid_month, "cap_month_usd": s.claude_cap_month_usd,
                  "cap_request_usd": s.claude_cap_proof_usd},
        "requests": tally["requests"],
    })


@routes.post("/api/models/refresh")
async def models_refresh(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if hasattr(ctx.local, "refresh_models"):
        await ctx.local.refresh_models()
    if ctx.brain is not None:
        ctx.spawn(ctx.brain.refresh())
    return ok(await ctx.models_public())


def _rankings_of(ctx) -> dict:
    fn = getattr(ctx.brain, "rankings_view", None)
    if fn is None:                                   # fake brains (tests, --demo): nothing to rank
        return {"domains": [], "public": {}, "news": [], "next": {}, "auto": False, "catalogue_updated": None}
    return fn()


@routes.get("/api/models/rankings")
async def models_rankings(request: web.Request) -> web.Response:
    """« Classement » (S-V, docs/BRAIN.md §12): per domain the best usable models with their evidence (measured here,
    LMArena, catalogue estimate), the public source and its dates, the model news, the next automatic refreshes."""
    ctx = ctx_of(request)
    return ok(await asyncio.to_thread(_rankings_of, ctx))


@routes.post("/api/models/rankings/refresh")
async def models_rankings_refresh(request: web.Request) -> web.Response:
    """Refresh the catalogue now and the public rankings (at most once an hour); nothing in local mode."""
    ctx = ctx_of(request)
    br = ctx.brain
    if ctx.settings.mode != "local" and br is not None and hasattr(br, "refresh_public"):
        async def run() -> None:
            try:
                await br.refresh()
                await br.refresh_public(force=True)
            except Exception:  # noqa: BLE001
                from ..logs import get
                get("models").exception("rankings refresh failed")
            ctx.publish("models.rankings", {"updated": True})
        await asyncio.wait({ctx.spawn(run())}, timeout=45)
    return ok(await asyncio.to_thread(_rankings_of, ctx))


@routes.post("/api/models/local/stop")
async def models_local_stop(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if ctx.slots.holders.get("gpu"):
        return error(409, "busy", "Une opération est en cours : arrêtez-la d'abord (Échap).")
    if hasattr(ctx.local, "stop"):
        await ctx.local.stop()
    return ok({"local": ctx.local.status() if hasattr(ctx.local, "status") else {}})


# ---------------------------------------------------------------- system
def _fonts() -> dict:
    import subprocess
    out = {}
    for fam in ("DejaVu Sans Mono", "Noto Sans Math"):
        try:
            fc = deps.tool("fc-list")
            if not fc:
                out[fam] = False
                continue
            r = subprocess.run([fc, fam], capture_output=True, text=True, timeout=10)
            out[fam] = bool(r.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            out[fam] = False
    return out


async def health(ctx) -> list[dict]:
    checks = []

    def add(cid: str, okv: bool, key: str, repair: str = "", level: str = "", **params):
        checks.append({"id": cid, "ok": okv, "level": level or ("ok" if okv else "warn"), "repair": repair,
                       "message": msg(key, **params)})
    ws = ctx.workspace()
    add("workspace", ws is not None and not ws.problems,
        "Espace de travail Lean prêt : {ws}." if ws is not None and not ws.problems else
        "L'espace de travail Lean n'est pas prêt : {ws}.", repair="workspaces",
        ws=(ws.key if ws else "—") + ("" if ws is None or not ws.problems else f" ({ws.problems[0]})"))
    exe = Path(deps.tool("llama-server") or config.LLAMA_BIN_DIR / "llama-server")
    add("llama", exe.exists() or ctx.demo, "Moteur local llama-server présent." if exe.exists() or ctx.demo else
        "llama-server introuvable : relancez install.sh.")
    for role, key in (("prove", "prover"), ("formalize", "formalizer"), ("explain", "explainer")):
        m = ctx.local.model_for(role) if hasattr(ctx.local, "model_for") else None
        add("model_" + key, m is not None, "Modèle local « {role} » : {name}." if m else
            "Aucun modèle local « {role} » installé.", repair="models", role=key, name=m.model_id if m else "")
    from ..export import tectonic_cmd
    if tectonic_cmd():
        add("tex", True, "LaTeX (tectonic de Madalean, hors ligne) présent : export PDF possible.")
    else:
        tex = deps.tool("latexmk") and deps.tool("xelatex")
        add("tex", bool(tex), "LaTeX du système (latexmk + XeLaTeX) utilisé : export PDF possible." if tex else
            "LaTeX absent : l'export PDF devient une page HTML à imprimer.", repair="dep_tex-bundle" if not tex else "")
    fonts = await asyncio.to_thread(_fonts)
    for fam, present in fonts.items():
        add("font_" + fam.replace(" ", "_").lower(), present, "Police {f} : présente." if present else
            "Police {f} absente (export PDF moins lisible).", f=fam)
    jl = deps.tool("jupyter-lab")
    add("jupyter", bool(jl), "JupyterLab présent." if jl else
        "JupyterLab absent : les carnets ne sont pas disponibles.", repair="" if jl else "dep_env")
    from .. import leansandbox
    sbx = await asyncio.to_thread(leansandbox.bwrap)
    add("sandbox", bool(sbx), "Bac à sable actif (bubblewrap) : Lean, LaTeX et les expériences tournent sans réseau "
        "ni accès à vos fichiers." if sbx else "Bac à sable indisponible (bubblewrap absent ou espaces de noms "
        "utilisateur désactivés) : Lean, LaTeX et les expériences tournent sans isolation.")
    warm = getattr(ctx.lean, "warm", None)          # S-AE (D37): Lean kept ready with Mathlib loaded
    if warm is not None and not ctx.demo:
        checks.append(_warm_check(warm.status()))
    wb = getattr(ctx, "workbench", None)            # S-AO (D47): Calcul kernels ready in advance
    if wb is not None and not ctx.demo:
        checks.append(_calcul_warm_check(ctx, wb))
    st = getattr(ctx, "selftest", None)          # S-AC: smoke tests of the sandboxed tools, after each update
    if st is not None:
        for c in st.health():
            checks.append({**c, "repair": "selftest" if not c["ok"] else "selftest_run", "rerun": True})
    # components of the prefix (§18): one line each, with its repair action
    for c in await asyncio.to_thread(deps_health.components):
        if c["state"] in ("dev",):
            continue
        add("dep_" + c["component"], c["ok"], {
            "ok": "Composant {name} {version} : installé ({path}).",
            "on_demand": "Composant {name} : installé à la première utilisation.",
            "outdated": "Composant {name} : la version {pinned} est prête à être installée.",
        }.get(c["state"], "Composant {name} absent ou incomplet : réparez-le."),
            repair=c["repair"], level="ok" if c["state"] in ("ok", "on_demand") else "warn",
            name=c["component"], version=c["version"], pinned=c["pinned"], path=c["path"])
    disks = ctx.monitor.disk or []
    low = [d for d in disks if d["free_gb"] < 10]
    add("disk", not low, "Espace disque suffisant." if not low else "Disque presque plein : {n} Go libres.",
        n=low[0]["free_gb"] if low else 0)
    from ..runtime.llama import gpu_share          # S-N: who holds the GPU (automatic lending with Ollama)
    share = gpu_share(ctx.monitor.gpu, getattr(ctx.local, "last_pid", None))
    if share:
        add("gpu_share", True, "Carte graphique : {who} ; {free} Mo libres. Si la place manque, Madalean fait "
            "décharger les modèles d'Ollama (rechargés à la demande) et rend la carte après inactivité.",
            who=", ".join(f"{h['app']} {h['mib']} Mo" for h in share["holders"]) or "personne", free=share["free"])
    add("brain", ctx.brain_kind != "fake" or ctx.demo, "Moteur de modèles : {kind}." if ctx.brain_kind != "fake"
        or ctx.demo else "Moteur de modèles absent : réponses simulées (installation incomplète).", kind=ctx.brain_kind)
    return checks


def _warm_check(st: dict) -> dict:
    """Health row of the warm Lean (D37), in plain words."""
    live = [w for w in st["workers"] if w["state"] in ("ready", "busy")]
    loading = [w for w in st["workers"] if w["state"] == "loading"]
    row = {"id": "lean_warm", "ok": True, "level": "ok", "repair": "", "rerun": False}
    if not st["enabled"]:
        m = msg("Lean prêt d'avance : désactivé ; chaque essai relance Lean et recharge Mathlib.")
    elif st["distrusted"]:
        m = msg("Lean prêt d'avance mis de côté pour {ws} : un de ses résultats différait de la vérification "
                "complète. Les essais sont vérifiés par un Lean relancé à chaque fois.", ws=", ".join(st["distrusted"]))
        row.update(ok=False, level="warn", repair="lean_warm")
    elif live:
        m = msg("Lean prêt d'avance pour {ws} : chaque essai est vérifié en une fraction de seconde ({gb} Go de "
                "mémoire, arrêté après {min} min sans essai). Une preuve trouvée est toujours revérifiée par un "
                "Lean neuf.", ws=", ".join(w["workspace"] for w in live),
                gb=f"{sum(w['rss_mb'] for w in live) / 1024:.1f}", min=st["idle_minutes"])
    elif loading:
        m = msg("Lean prêt d'avance : chargement de Mathlib pour {ws}…", ws=", ".join(w["workspace"] for w in loading))
    elif st["failures"]:
        m = msg("Lean prêt d'avance n'a pas pu démarrer ({why}) : les essais sont vérifiés par un Lean relancé à "
                "chaque fois.", why=next(iter(st["failures"].values()))[:200])
        row.update(ok=False, level="warn", repair="lean_warm")
    else:
        m = msg("Lean prêt d'avance : au repos ; il démarre avec la prochaine preuve et s'arrête après {min} min "
                "sans essai.", min=st["idle_minutes"])
    row["message"] = m
    return row


def _calcul_warm_check(ctx, wb) -> dict:
    """Health row of « Calcul prêt d'avance » (S-AO, D47), in plain words."""
    row = {"id": "calcul_warm", "ok": True, "level": "ok", "repair": "", "rerun": False}
    idle = int(getattr(ctx.settings, "calcul_idle_minutes", 30) or 0)
    k = wb._kernels
    st = k.warm_summary() if k is not None and hasattr(k, "warm_summary") else {"live": 0, "loading": 0, "failed": [],
                                                                                 "skipped": [], "last": []}
    last = st["last"][-1] if st["last"] else None
    from .plugins.workbench import _warm_on
    if not _warm_on(ctx):
        m = msg("Calcul prêt d'avance : désactivé ; le noyau d'un document démarre à sa première exécution.")
    elif st["failed"]:
        m = msg("Calcul prêt d'avance n'a pas pu préparer un noyau ({why}) : il démarrera à la première exécution.",
                why=st["failed"][-1][:200])
        row.update(ok=False, level="warn")
    elif st["loading"]:
        m = msg("Calcul prêt d'avance : préparation de {n} noyau(x) en arrière-plan…", n=st["loading"])
    elif st["live"]:
        m = msg("Calcul prêt d'avance : {n} noyau(x) prêt(s) ; dernière préparation en {s} s. Arrêt après {min} min "
                "sans activité.", n=st["live"], s=last["seconds"] if last else 0, min=idle)
    elif st["skipped"]:
        m = msg("Calcul prêt d'avance : noyau non préparé, mémoire disponible insuffisante ({why}).",
                why=st["skipped"][-1][:100])
    else:
        m = msg("Calcul prêt d'avance : au repos ; le noyau d'un document démarre dès son ouverture et s'arrête "
                "après {min} min sans activité.", min=idle)
    row["message"] = m
    return row


@routes.get("/api/system")
async def system(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if ctx.monitor.t == 0:
        await ctx.monitor.poll()
    return ok({**ctx.system_light(), "workspaces": ctx.workspaces_public(), "checks": await health(ctx),
               "local": ctx.local.status() if hasattr(ctx.local, "status") else {}, "brain": ctx.brain_kind,
               "lean_running": list((getattr(ctx.lean, "running", {}) or {}).values()),
               "lean_warm": ctx.lean.warm.status() if getattr(ctx.lean, "warm", None) is not None else None})


REPAIRS = ("workspaces", "models", "local_model", "names_index", "selftest", "selftest_run", "lean_warm")


@routes.post("/api/system/repair/{id}")
@host_only
async def system_repair(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    rid = request.match_info["id"]
    if rid.startswith("dep_"):                      # component of the prefix (§18): reinstall in the background
        from ..deps import service
        name = rid[4:]
        if name not in {c["component"] for c in deps_health.components()}:
            return error(404, "unknown_repair")

        async def run():
            try:
                await service.install_async(name, ctx.publish)
            except Exception as e:  # noqa: BLE001
                ctx.publish("deps.progress", {"component": name, "phase": "error", "done": 0, "total": 0,
                                              "message": str(e)[:300]})
        ctx.spawn(run())
        return ok({"repair": rid, "ok": True, "started": True}, status=202)
    if rid not in REPAIRS:
        return error(404, "unknown_repair")
    if rid == "workspaces":
        await ctx.refresh_workspaces()
    elif rid == "models":
        if hasattr(ctx.local, "refresh_models"):
            await ctx.local.refresh_models()
    elif rid == "local_model":
        if ctx.slots.holders.get("gpu"):
            return error(409, "busy", "Une opération est en cours : arrêtez-la d'abord (Échap).")
        if hasattr(ctx.local, "stop"):
            await ctx.local.stop()
    elif rid in ("selftest", "selftest_run"):         # S-AC: « Réparer » resets the tools' homes, then tests
        st = getattr(ctx, "selftest", None)
        if st is None:
            return error(404, "unknown_repair")
        if st.is_running():
            return error(409, "busy", "L'auto-test est déjà en cours : patientez une minute.")
        rep = await (st.repair() if rid == "selftest" else st.run("manual"))
        bad = [p for p, r in rep["parts"].items() if r.get("state") == "failed"]
        return ok({"repair": rid, "ok": not bad, "failed": bad, "checks": await health(ctx)})
    elif rid == "lean_warm":                       # D37: forget failures / disagreements, start again when needed
        if getattr(ctx.lean, "warm", None) is not None:
            ctx.lean.warm.reset()
    elif rid == "names_index":
        ws = ctx.workspace()
        if ws is None:
            return error(409, "no_workspace")
        idx = await asyncio.to_thread(names.get, ws, True)
        return ok({"repair": rid, "ok": idx is not None, "names": len(idx) if idx else 0})
    return ok({"repair": rid, "ok": True, "checks": await health(ctx)})


# ---------------------------------------------------------------- updates
@routes.get("/api/updates")
async def updates_get(request: web.Request) -> web.Response:
    return ok(ctx_of(request).updates.status())


@routes.post("/api/updates/check")
async def updates_check(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    ctx.spawn(ctx.updates.check(manual=True))
    return ok({"checking": True}, status=202)


@routes.post("/api/updates/install")
@host_only
async def updates_install(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    err = await ctx.updates.install(str(data.get("key", "")))
    if err == "jobs_running":
        return error(409, err, "Une opération est en cours : arrêtez-la d'abord (Échap).")
    if err:
        return error(409 if err == "busy" else 404, err)
    return ok(ctx.updates.status(), status=202)


@routes.post("/api/updates/cancel")
@host_only
async def updates_cancel(request: web.Request) -> web.Response:
    return ok({"cancelled": await ctx_of(request).updates.cancel()})
