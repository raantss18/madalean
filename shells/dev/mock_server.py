#!/usr/bin/env python3
"""Stand-in for the Madalean server, used to develop and test the thin clients (shells).

Implements only the surface the shells depend on (see docs/SHELLS.md, "Required server endpoints"):

  GET  /api/hello                      -> {name, version, paired, local, host_name}
  POST /api/pair {code, device_name}   -> {token, device_id} | 401 bad_code | 429 locked
  POST /api/session/ticket  (Bearer)   -> {ticket, expires_in}
  GET  /api/session?ticket=..&next=/   -> sets HttpOnly cookie, 200 page that meta-refreshes to next
  GET  /api/ws                         -> WebSocket echo (needs cookie/bearer on remote)
  GET  /                               -> test page: shows whether the cookie / bearer arrived
  GET  /pair                           -> placeholder browser pairing page (shells intercept it)
  GET  /api/export.pdf                 -> tiny PDF as attachment (download test)
  POST /api/upload                     -> echoes uploaded file names/sizes (upload test)

Test-only helpers (local listener only): GET /mock/events, POST /mock/revoke_all, POST /mock/new_code.

Two listeners like the real server: --local-port (trusted, no pairing) and --remote-port (token required).
Python stdlib + aiohttp (the project's .venv has it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import time
from html import escape as html_escape
from urllib.parse import quote

from aiohttp import WSMsgType, web

VERSION = "2.0.0-mock"
COOKIE = "madalean_token"  # name used by the real server (docs/API.md)


class State:
    def __init__(self, code: str, lock_seconds: int, host_name: str, secure_cookie: str):
        self.code = code
        self.code_expires = time.time() + 300
        self.lock_seconds = lock_seconds
        self.bad_tries = 0
        self.locked_until = 0.0
        self.host_name = host_name
        self.secure_cookie = secure_cookie  # "always" | "never" | "auto"
        self.devices: dict[str, dict] = {}  # sha256(token) -> {id, name}
        self.tickets: dict[str, tuple[str, float]] = {}  # ticket -> (token_hash, expiry)
        self.events: list[dict] = []

    def log(self, kind: str, **kw) -> None:
        # Never log tokens or tickets, only short hash prefixes.
        self.events.append({"t": round(time.time(), 3), "kind": kind, **kw})
        print(json.dumps(self.events[-1]), flush=True)


def h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def is_local(request: web.Request) -> bool:
    return request.app["local"]


def auth_hash(request: web.Request) -> str | None:
    """Return the device-token hash presented (Bearer or cookie) if valid."""
    st: State = request.app["state"]
    auth = request.headers.get("Authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE)
    if tok and h(tok) in st.devices:
        return h(tok)
    return None


def json_err(status: int, error: str, **extra) -> web.Response:
    headers = {"Cache-Control": "no-store"}
    if "retry_after" in extra:
        headers["Retry-After"] = str(extra["retry_after"])
    return web.json_response({"error": error, **extra}, status=status, headers=headers)


@web.middleware
async def guard(request: web.Request, handler):
    if is_local(request) or request.path in ("/api/hello", "/api/pair", "/api/session", "/pair",
                                                "/favicon.ico") or request.path.startswith("/mock/"):
        if request.path.startswith("/mock/") and not is_local(request):
            raise web.HTTPNotFound()
        return await handler(request)
    if request.path == "/api/session/ticket":
        return await handler(request)  # checks Bearer itself
    if auth_hash(request) is None:
        st: State = request.app["state"]
        st.log("unauthorized", path=request.path)
        if request.path.startswith("/api/"):
            return json_err(401, "unauthorized")
        raise web.HTTPSeeOther("/pair?reason=auth")
    return await handler(request)


async def hello(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    local = is_local(request)
    return web.json_response({"name": "madalean", "version": VERSION,
                              "paired": local or auth_hash(request) is not None,
                              "local": local, "host_name": st.host_name},
                             headers={"Cache-Control": "no-store"})


async def pair(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    now = time.time()
    if now < st.locked_until:
        st.log("pair_locked")
        return json_err(429, "locked", retry_after=int(st.locked_until - now) + 1)
    try:
        body = await request.json()
        code, name = str(body["code"]), str(body["device_name"])[:64]
    except Exception:
        return json_err(400, "bad_request")
    if not secrets.compare_digest(code, st.code) or now > st.code_expires:
        st.bad_tries += 1
        st.log("pair_bad_code", tries=st.bad_tries)
        if st.bad_tries >= 5:
            st.locked_until, st.bad_tries = now + st.lock_seconds, 0
            return json_err(429, "locked", retry_after=st.lock_seconds)
        return json_err(401, "bad_code")
    token = secrets.token_urlsafe(32)  # 256 bits
    dev_id = secrets.token_hex(4)
    st.devices[h(token)] = {"id": dev_id, "name": name}
    st.code = f"{secrets.randbelow(10**6):06d}"  # single use
    st.bad_tries = 0
    st.log("paired", device=name, id=dev_id)
    return web.json_response({"token": token, "device_id": dev_id}, headers={"Cache-Control": "no-store"})


async def ticket(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    auth = request.headers.get("Authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not tok or h(tok) not in st.devices:
        st.log("ticket_refused")
        return json_err(401, "unauthorized")
    t = secrets.token_urlsafe(16)
    st.tickets[t] = (h(tok), time.time() + 60)
    st.log("ticket_issued", device=st.devices[h(tok)]["name"])
    return web.json_response({"ticket": t, "expires_in": 60}, headers={"Cache-Control": "no-store"})


def safe_next(nxt: str | None) -> str:
    if not nxt or not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt:
        return "/"
    return nxt


async def session(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    t = request.query.get("ticket", "")
    entry = st.tickets.pop(t, None)  # single use
    if entry is None or time.time() > entry[1] or entry[0] not in st.devices:
        st.log("session_bad_ticket")
        raise web.HTTPSeeOther("/pair?reason=ticket", headers={"Cache-Control": "no-store",
                                                                "Referrer-Policy": "no-referrer"})
    token_hash = entry[0]
    nxt = safe_next(request.query.get("next"))
    headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    if request.app["session_mode"] == "redirect":
        resp = web.HTTPSeeOther(nxt, headers=headers)
    else:
        # 200 + same-origin meta refresh: the next navigation is initiated by the server's own page, so the
        # SameSite=Strict cookie is sent (after a 303 the chain keeps the shell's cross-site initiator and
        # WebKitGTK withholds the Strict cookie — observed in the desktop e2e test).
        page = SESSION_PAGE.format(next=html_escape(nxt, quote=True))
        resp = web.Response(text=page, content_type="text/html", headers={
            **headers, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
    secure = st.secure_cookie == "always" or (st.secure_cookie == "auto" and request.secure)
    # The cookie is a new random session secret bound to the device (revoked with it), not the token.
    sess = secrets.token_urlsafe(32)
    st.devices.setdefault(h(sess), {**st.devices[token_hash], "session_of": token_hash[:8]})
    resp.set_cookie(COOKIE, sess, httponly=True, secure=secure, samesite="Strict", path="/",
                    max_age=365 * 86400)
    st.log("session_opened", secure=secure, device=st.devices[token_hash]["name"])
    if isinstance(resp, web.HTTPException):
        raise resp
    return resp


SESSION_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0;url={next}"><meta name="referrer" content="no-referrer">
<title>Madalean</title><style>body{{background:#1f2a44}}</style></head><body></body></html>"""


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Madalean (mock)</title>
<style>body{{font:16px system-ui;margin:2rem;max-width:40rem}}code{{background:#eee;padding:0 .3em}}
.ok{{color:#060}}.bad{{color:#a00}}@media (prefers-color-scheme:dark){{body{{background:#111;color:#ddd}}code{{background:#333}}}}</style>
</head><body>
<h1>Madalean mock server</h1>
<p id="listener">listener: <b>{listener}</b></p>
<p id="auth" class="{cls}">auth: <b>{auth}</b></p>
<p>user agent: <code>{ua}</code></p>
<p>shell bridge: <b id="bridge">?</b></p>
<p>websocket: <b id="ws">connecting…</b></p>
<form id="up" action="/api/upload" method="post" enctype="multipart/form-data">
 <input type="file" name="file" accept=".tex,.lean" multiple> <button>Envoyer / Upload</button></form>
<p><a id="dl" href="/api/export.pdf">Télécharger le PDF / Download PDF</a></p>
<p><a id="ext" href="https://lean-lang.org/" target="_blank">Lien externe (nouvel onglet) / external link (new tab)</a> · <a id="ext2" href="https://leanprover-community.github.io/">même onglet / same tab</a></p>
<p><a id="pairlink" href="/pair?reason=auth">simulate 401 → /pair</a></p>
<script>
document.getElementById('bridge').textContent = window.madaleanShell ? JSON.stringify({{kind: madaleanShell.kind, version: madaleanShell.version}}) : 'none';
const ws = new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/ws');
ws.onopen = () => ws.send('ping');
ws.onmessage = e => document.getElementById('ws').textContent = 'echo: ' + e.data;
ws.onerror = () => document.getElementById('ws').textContent = 'error';
</script></body></html>"""


async def index(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    local = is_local(request)
    via = "local (trusted)" if local else ("bearer" if request.headers.get("Authorization") else "cookie")
    ok = local or auth_hash(request) is not None
    st.log("page", local=local, auth_ok=ok, via=via, ua=request.headers.get("User-Agent", "")[:80])
    html = PAGE.format(listener="local" if local else "remote", cls="ok" if ok else "bad",
                       auth=f"OK via {via}" if ok else "MISSING",
                       ua=request.headers.get("User-Agent", "").replace("<", "&lt;"))
    return web.Response(text=html, content_type="text/html",
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


async def pair_page(request: web.Request) -> web.Response:
    reason = request.query.get("reason", "")
    request.app["state"].log("pair_page", reason=reason)
    return web.Response(text=f"<!doctype html><meta charset=utf-8><h1>Pairing required ({quote(reason)})</h1>",
                        content_type="text/html", headers={"Cache-Control": "no-store"})


MINI_PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 40 Td (Madalean test) Tj ET\nendstream endobj\n"
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")


async def export_pdf(request: web.Request) -> web.Response:
    request.app["state"].log("download")
    return web.Response(body=MINI_PDF, content_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="theoreme-demo.pdf"'})


async def upload(request: web.Request) -> web.Response:
    files = []
    reader = await request.multipart()
    async for part in reader:
        data = await part.read()
        files.append({"name": part.filename, "size": len(data)})
    request.app["state"].log("upload", files=files)
    return web.json_response({"received": files})


async def ws(request: web.Request) -> web.WebSocketResponse:
    st: State = request.app["state"]
    sock = web.WebSocketResponse()
    await sock.prepare(request)
    st.log("ws_open", local=is_local(request))
    async for msg in sock:
        if msg.type == WSMsgType.TEXT:
            st.log("ws_msg", text=msg.data[:40])
            await sock.send_str(msg.data)
    return sock


async def mock_events(request: web.Request) -> web.Response:
    return web.json_response(request.app["state"].events)


async def mock_revoke(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    n = len(st.devices)
    st.devices.clear()
    st.tickets.clear()
    st.log("revoked_all", n=n)
    return web.json_response({"revoked": n})


async def mock_new_code(request: web.Request) -> web.Response:
    st: State = request.app["state"]
    body = await request.json() if request.can_read_body else {}
    st.code = str(body.get("code") or f"{secrets.randbelow(10**6):06d}")
    st.code_expires = time.time() + 300
    st.locked_until = 0
    st.log("new_code")
    return web.json_response({"code": st.code, "expires": st.code_expires})


def make_app(state: State, local: bool, session_mode: str = "html") -> web.Application:
    app = web.Application(middlewares=[guard])
    app["state"], app["local"], app["session_mode"] = state, local, session_mode
    app.router.add_get("/api/hello", hello)
    app.router.add_post("/api/pair", pair)
    app.router.add_post("/api/session/ticket", ticket)
    app.router.add_get("/api/session", session)
    app.router.add_get("/api/ws", ws)
    app.router.add_get("/api/export.pdf", export_pdf)
    app.router.add_post("/api/upload", upload)
    app.router.add_get("/pair", pair_page)
    app.router.add_get("/", index)
    if local:
        app.router.add_get("/mock/events", mock_events)
        app.router.add_post("/mock/revoke_all", mock_revoke)
        app.router.add_post("/mock/new_code", mock_new_code)
    return app


async def main_async(args) -> None:
    state = State(args.code, args.lock_seconds, args.host_name, args.secure_cookie)
    runners = []
    for port, local in ((args.local_port, True), (args.remote_port, False)):
        if port <= 0:
            continue
        runner = web.AppRunner(make_app(state, local, args.session_mode), access_log=None)  # no access log: tickets in URLs
        await runner.setup()
        await web.TCPSite(runner, args.bind, port).start()
        runners.append(runner)
        print(f"mock {'local ' if local else 'remote'} listener on http://{args.bind}:{port}", flush=True)
    print(f"pairing code: {state.code}", flush=True)
    import asyncio
    await asyncio.Event().wait()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bind", default="127.0.0.1", help="use 0.0.0.0 to reach it from the Android emulator (10.0.2.2)")
    p.add_argument("--local-port", type=int, default=11600, help="trusted listener (0 = off); real server: 11500")
    p.add_argument("--remote-port", type=int, default=11601, help="token listener (0 = off); real server: 11501")
    p.add_argument("--code", default="123456")
    p.add_argument("--lock-seconds", type=int, default=600)
    p.add_argument("--host-name", default="mock-host")
    p.add_argument("--secure-cookie", choices=["always", "never", "auto"], default="auto",
                   help="auto = Secure only when the request came over TLS")
    p.add_argument("--session-mode", choices=["html", "redirect"], default="html",
                   help="valid ticket answer: 200 page with meta refresh (contract) or 303 (shows the Strict-cookie issue)")
    args = p.parse_args()
    import asyncio
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
