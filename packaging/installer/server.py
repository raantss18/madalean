#!/usr/bin/env python3
"""Graphical install wizard of `Madalean-installer.run` (session S-AL, DECISIONS D44) — standard library only.

A tiny HTTP server on 127.0.0.1 (random port, never another interface) serves the wizard page and a JSON API; the
page is opened in the user's browser with a one-time token in the URL (`/?t=<token>`). Every API call must carry
that token (header `X-Install-Token`), the Host header must be the loopback address of this server (DNS
rebinding) and POSTs must come from this origin. Machine check and plan come from the SAME engine as the terminal
assistant (madalean/deps/assistant.py); the install itself is `install.sh --plan FILE`, whose output is streamed to
the page. No sudo, ever: system package commands are only shown to copy. The server stops when the user closes the
wizard, or after `--idle` seconds without any request while no install runs.

  python3 -I packaging/installer/server.py [--src DIR] [--no-browser] [--idle S] [-- INSTALL_SH_ARGS…]
Exit codes: 0 finished, 3 the wizard could not start (caller falls back to the terminal)."""
from __future__ import annotations

import argparse
import hmac
import http.server
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
STATIC = {"/wizard.css": ("wizard.css", "text/css; charset=utf-8"),
          "/wizard.js": ("wizard.js", "text/javascript; charset=utf-8"),
          "/wordmark.svg": ("wordmark.svg", "image/svg+xml"), "/wordmark-dark.svg": ("wordmark-dark.svg", "image/svg+xml"),
          "/icon.svg": ("icon.svg", "image/svg+xml")}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
STEP_RE = re.compile(r"^==> (\d+)/(\d+) (.*)$")
SITE = "https://raantss18.github.io/madalean/"
MAX_LINES = 20000


class Install:
    """State of the wizard: machine check, plan, one install.sh run at a time (re-runnable: install.sh resumes)."""

    def __init__(self, src: Path, install_sh: Path, extra: list[str], config_dir: Path | None):
        self.src, self.install_sh, self.extra = src, install_sh, extra
        self.config_dir = config_dir
        self.lock = threading.Lock()
        self.state = "detecting"           # detecting | ready | running | done | failed
        self.detected: dict = {}
        self.rec: dict = {}
        self.lines: list[str] = []
        self.step = (0, 9, "")
        self.rc: int | None = None
        self.plan: dict = {}
        self.proc: subprocess.Popen | None = None
        self.work = Path(tempfile.mkdtemp(prefix="madalean-wizard-"))
        sys.path.insert(0, str(src))
        from madalean.deps import assistant        # the shared engine
        self.engine = assistant
        threading.Thread(target=self._detect, daemon=True).start()

    def _detect(self) -> None:
        prefix = None
        if "--prefix" in self.extra:
            i = self.extra.index("--prefix")
            prefix = self.extra[i + 1] if i + 1 < len(self.extra) else None
        det = self.engine.detect(prefix)
        rec = {lg: self.engine.recommend(det, lg) for lg in ("fr", "en")}
        with self.lock:
            self.detected, self.rec, self.state = det, rec, "ready"

    def madalean_port(self) -> int:
        if "--port" in self.extra:
            i = self.extra.index("--port")
            try:
                return int(self.extra[i + 1])
            except (IndexError, ValueError):
                pass
        return 11500

    def public(self) -> dict:
        from madalean import __version__
        with self.lock:
            return {"state": self.state, "detected": self.detected, "recommendation": self.rec,
                    "choices": {k: list(v) for k, v in self.engine.CHOICES.items()},
                    "default_plan": self.engine.DEFAULT_PLAN, "plan": self.plan, "version": __version__,
                    "madalean_url": f"http://127.0.0.1:{self.madalean_port()}/", "site": SITE,
                    "progress": self._progress(0)}

    def _progress(self, since: int) -> dict:
        n, total, title = self.step
        pct = 100 if self.state == "done" else int(100 * max(n - 1, 0) / max(total, 1))
        return {"state": self.state, "lines": self.lines[since:], "next": len(self.lines), "step": n, "total": total,
                "title": title, "percent": pct, "rc": self.rc}

    def progress(self, since: int) -> dict:
        with self.lock:
            return self._progress(max(0, since))

    def start(self, plan: dict) -> tuple[int, dict]:
        try:
            plan = self.engine.validate(plan)
        except ValueError as e:
            return 400, {"error": "bad_plan", "detail": str(e)}
        with self.lock:
            if self.state == "running":
                return 409, {"error": "busy"}
            if self.state == "detecting":
                return 409, {"error": "detecting"}
            doc = self.engine._plan_doc(self.detected, plan, True, "fr")
            pf = self.work / "plan.json"
            pf.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            self.plan, self.lines, self.step, self.rc, self.state = plan, [], (0, 9, ""), None, "running"
            cmd = ["bash", str(self.install_sh), "--plan", str(pf), *self.extra]
            env = {**os.environ, "MADALEAN_INSTALL_SOURCE": "installer (graphical)", "PYTHONUNBUFFERED": "1"}
            env.pop("PYTHONPATH", None)
            try:
                self.proc = subprocess.Popen(cmd, cwd=str(self.src), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, env=env, start_new_session=True)
            except OSError as e:
                self.state, self.rc = "failed", 127
                self.lines.append(f"{e}")
                return 500, {"error": "spawn", "detail": str(e)}
        threading.Thread(target=self._pump, daemon=True).start()
        return 202, {"ok": True}

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip("\n")
            m = STEP_RE.match(line)
            with self.lock:
                if len(self.lines) < MAX_LINES:
                    self.lines.append(line)
                if m:
                    self.step = (int(m.group(1)), int(m.group(2)), m.group(3))
        rc = self.proc.wait()
        with self.lock:
            self.rc = rc
            self.state = "done" if rc == 0 else "failed"

    def stop(self) -> None:
        p = self.proc
        if p and p.poll() is None:
            try:
                os.killpg(p.pid, 15)
            except OSError:
                pass
        shutil.rmtree(self.work, ignore_errors=True)


def make_handler(inst: Install, token: str, port_box: list, activity: list, quit_ev: threading.Event, browser):
    class H(http.server.BaseHTTPRequestHandler):
        server_version = "madalean-installer"
        sys_version = ""

        def log_message(self, fmt, *args):         # quiet (the token is in the first URL)
            pass

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code: int, data) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            p = port_box[0]
            return self.headers.get("Host", "") in (f"127.0.0.1:{p}", f"localhost:{p}")

        def _token_ok(self, value: str | None) -> bool:
            return bool(value) and hmac.compare_digest(value.encode(), token.encode())

        def _guard(self) -> bool:
            activity[0] = time.monotonic()
            if not self._host_ok():
                self._json(403, {"error": "bad_host"})
                return False
            return True

        def do_GET(self):  # noqa: N802
            if not self._guard():
                return
            u = urlsplit(self.path)
            if u.path in ("/", "/index.html"):
                if not self._token_ok((parse_qs(u.query).get("t") or [""])[0]):
                    self._send(403, "Lien invalide : relancez l'installateur. / Invalid link: start the installer again."
                               .encode(), "text/plain; charset=utf-8")
                    return
                self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
                return
            if u.path in STATIC:
                name, ctype = STATIC[u.path]
                f = WEB / name
                if f.is_file():
                    self._send(200, f.read_bytes(), ctype)
                    return
            if u.path.startswith("/api/"):
                if not self._token_ok(self.headers.get("X-Install-Token")):
                    self._json(401, {"error": "token"})
                    return
                if u.path == "/api/state":
                    self._json(200, inst.public())
                    return
                if u.path == "/api/progress":
                    try:
                        since = int((parse_qs(u.query).get("since") or ["0"])[0])
                    except ValueError:
                        since = 0
                    self._json(200, inst.progress(since))
                    return
            self._json(404, {"error": "not_found"})

        def do_POST(self):  # noqa: N802
            if not self._guard():
                return
            u = urlsplit(self.path)
            if not self._token_ok(self.headers.get("X-Install-Token")):
                self._json(401, {"error": "token"})
                return
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{port_box[0]}", f"http://localhost:{port_box[0]}"):
                self._json(403, {"error": "origin"})
                return
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 100_000)
                data = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                self._json(400, {"error": "bad_json"})
                return
            if u.path == "/api/install":
                code, body = inst.start(data.get("plan") or {})
                self._json(code, body)
            elif u.path == "/api/open":
                browser(inst.public()["madalean_url"])
                self._json(200, {"ok": True})
            elif u.path == "/api/quit":
                self._json(200, {"ok": True})
                quit_ev.set()
            else:
                self._json(404, {"error": "not_found"})

        do_HEAD = do_GET

    return H


def host_app_command(data_home: Path | None = None) -> list[str] | None:
    """The Exec line of the « Madalean Server » menu entry install.sh just wrote (D50: the host's desktop app, else a
    browser window), so « Ouvrir Madalean » opens the same thing as the menu. None when there is no such entry."""
    import shlex
    data = data_home or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    entry = data / "applications" / "madalean-server.desktop"
    try:
        text = entry.read_text(encoding="utf-8")
    except OSError:
        return None
    if "X-Madalean-Host=1" not in text:
        return None
    m = re.search(r"^Exec=(.+)$", text, re.M)
    try:
        cmd = shlex.split(m.group(1)) if m else []
    except ValueError:
        return None
    cmd = [c for c in cmd if not c.startswith("%")]           # no field codes are written, but never pass one
    return cmd if cmd and (Path(cmd[0]).is_file() or shutil.which(cmd[0])) else None


def open_madalean(url: str) -> bool:
    """« Ouvrir Madalean » at the end of the install: the Madalean Server app (menu entry), else the browser."""
    cmd = host_app_command()
    if cmd:
        try:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
        except OSError:
            pass
    return open_browser(url)


def open_browser(url: str) -> bool:
    exe = shutil.which("xdg-open")
    if not exe:
        return False
    try:
        subprocess.Popen([exe, url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Madalean graphical installer")
    ap.add_argument("--src", default=str(HERE.parent.parent), help="unpacked Madalean source tree")
    ap.add_argument("--install-sh", default=os.environ.get("MADALEAN_INSTALLER_INSTALL_SH", ""),
                    help="install script (tests use a fake one)")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--idle", type=float, default=1800.0, help="stop after S seconds without request (no install running)")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--url-file", help="write the wizard URL here (tests)")
    ap.add_argument("rest", nargs="*", help="arguments passed to install.sh (after --)")
    a = ap.parse_args(argv)
    src = Path(a.src).resolve()
    install_sh = Path(a.install_sh).resolve() if a.install_sh else src / "install.sh"
    if not install_sh.is_file() or not (src / "madalean" / "deps" / "assistant.py").is_file():
        print("Installateur incomplet / incomplete installer", file=sys.stderr)
        return 3
    token = secrets.token_urlsafe(32)
    port_box = [0]
    activity = [time.monotonic()]
    quit_ev = threading.Event()
    inst = Install(src, install_sh, list(a.rest), None)
    handler = make_handler(inst, token, port_box, activity, quit_ev, open_madalean)
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    except OSError as e:
        print(f"Serveur local impossible / cannot start the local server: {e}", file=sys.stderr)
        return 3
    httpd.daemon_threads = True
    port_box[0] = httpd.server_address[1]
    url = f"http://127.0.0.1:{port_box[0]}/?t={token}"
    if a.url_file:
        Path(a.url_file).write_text(url)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
    print("Assistant d'installation de Madalean / Madalean install wizard:")
    print(f"  {url}")
    print("(Si le navigateur ne s'ouvre pas, copiez cette adresse. / If no browser opens, copy this address.)",
          flush=True)
    if not a.no_browser and not open_browser(url):
        httpd.shutdown()
        inst.stop()
        return 3
    try:
        while not quit_ev.wait(0.25):
            running = inst.progress(0)["state"] == "running"
            if not running and time.monotonic() - activity[0] > a.idle:
                print("Assistant fermé (inactif). / Wizard closed (idle).", flush=True)
                break
    except KeyboardInterrupt:
        pass
    httpd.shutdown()
    httpd.server_close()
    st = inst.progress(0)
    inst.stop()
    return 0 if st["state"] in ("done", "ready", "detecting") else (1 if st["state"] == "failed" else 0)


if __name__ == "__main__":
    sys.exit(main())
