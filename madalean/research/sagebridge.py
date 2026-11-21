"""Kernel bridge for conjecture experiments (Sage / Python) — session S-G. The ONLY way Madalean executes
experiment code (ARCHITECTURE §15: the documented code-execution boundary).

Boundary (enforced here and in the plugin, documented in docs/RESEARCH_WORKSHOP.md §Security):
- code reaches a kernel only through `SageBridge.execute`, called by the conjecture workshop after the server
  checked the approval flag (explicit approval of that exact code, or the host-only setting `experiments_auto`) and
  the origin of the request (remote devices only when the host enabled `experiments_remote`);
- kernels are started by the server's own JupyterLab child (JupyterManager) with Madalean's kernelspecs
  `madalean-sage` / `madalean-python`, whose argv is this file's launcher (`python3 -I sagebridge.py --launch`):
  environment rebuilt from an allow-list (no API key, token, cookie… can reach the kernel), HOME and the working
  directory set to the confined experiments directory, address-space and file-size limits (setrlimit), and — when
  bubblewrap is installed — a sandbox: the whole file system read-only, only the experiments directory writable,
  Madalean's config directory (keys.json, devices.json), ~/.ssh, ~/.gnupg, the keyrings… hidden behind empty tmpfs;
- every execution has a wall-clock timeout (interrupt, then the kernel is killed) and an output cap.
Network access from the kernel is NOT blocked (the kernel talks to JupyterLab over TCP on 127.0.0.1).

The launcher part of this file uses the standard library only (it runs under the system Python of the kernel)."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

ENV_ALLOW = {"PATH", "LANG", "LANGUAGE", "TZ", "TERM", "USER", "LOGNAME", "SHELL", "PYTHONUNBUFFERED",
             "SAGE_ROOT", "SAGE_LOCAL", "SAGE_VENV", "LD_LIBRARY_PATH"}
SPEC_NAMES = {"sage": ("madalean-sage", "sagemath", "SageMath (Madalean experiments)", "sage"),
              "python": ("madalean-python", "python3", "Python (Madalean experiments)", "python")}
KERNEL_DIRS = ["/usr/share/jupyter/kernels", "/usr/local/share/jupyter/kernels",
               os.path.expanduser("~/.local/share/jupyter/kernels"), os.path.join(sys.prefix, "share/jupyter/kernels")]
DEFAULT_MEM_MB = 4096
DEFAULT_TIMEOUT_S = 60.0
MAX_TIMEOUT_S = 1800.0
MAX_OUTPUT = 200_000
RICH_MIMES = ("image/png", "image/svg+xml", "text/latex")   # kept for the Calcul screen (S-M); text/html never
MAX_RICH = 12
MAX_RICH_BYTES = 3_000_000


# ---------------------------------------------------------------- launcher (runs before the kernel, stdlib only)
def launcher_env(cfg: dict, environ: dict[str, str]) -> dict[str, str]:
    wd = cfg["workdir"]
    env = {k: v for k, v in environ.items() if k in ENV_ALLOW or k.startswith("LC_")}
    # HOME is short and empty on purpose: Sage's GAP probe parses GAP's output, and GAP wraps lines at 80
    # characters, so a long HOME (in ~HOME/.gap/ of the root paths) makes the Sage kernel crash at start. Every
    # directory a kernel writes to is set explicitly below, inside the experiments directory.
    env.update({"HOME": "/nonexistent", "TMPDIR": os.path.join(wd, ".tmp"), "IPYTHONDIR": os.path.join(wd, ".ipython"),
                "DOT_SAGE": os.path.join(wd, ".sage"), "MPLCONFIGDIR": os.path.join(wd, ".mpl"),
                "XDG_CACHE_HOME": os.path.join(wd, ".cache"), "XDG_CONFIG_HOME": os.path.join(wd, ".config"),
                "MADALEAN_EXPERIMENT": "1"})
    return env


def bwrap_argv(cfg: dict, argv: list[str], isolate_net: bool = False) -> list[str]:
    wd = cfg["workdir"]
    out = [cfg["bwrap"], "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--die-with-parent",
           "--new-session", "--unshare-ipc", "--unshare-pid",
           # S-H: no session bus, systemd --user, X11/Wayland or madalean-net control sockets inside the sandbox
           "--tmpfs", "/run", "--tmpfs", "/tmp", "--tmpfs", "/dev/shm"]
    if isolate_net:
        out += ["--unshare-net"]          # S-H F6: no network at all (no exfiltration, no 127.0.0.1:11500)
    for p in cfg.get("hide", []):
        if os.path.isdir(p):
            out += ["--tmpfs", p]
        elif os.path.exists(p):
            out += ["--ro-bind", "/dev/null", p]
    out += ["--bind", wd, wd, "--chdir", wd, "--"]
    return out + argv


PORTS = ("shell_port", "iopub_port", "stdin_port", "control_port", "hb_port")


def ipc_connection(conn: dict, ipc_dir: str) -> dict:
    """The kernel's connection info moved from TCP to unix sockets `<ipc_dir>/k-<port>` (same ports, same key)."""
    out = dict(conn)
    out.update({"transport": "ipc", "ip": os.path.join(ipc_dir, "k")})
    return out


def relay_tcp_to_ipc(conn: dict, ipc_dir: str, stop) -> list:
    """S-H F6: the kernel runs in its own network namespace (`--unshare-net`); JupyterLab still talks TCP to the
    ports of the original connection file. One listener per port on 127.0.0.1 (outside the sandbox) relays bytes
    to the kernel's unix socket (ZMTP is the same over TCP and IPC). Daemon threads; returns the listeners."""
    import socket
    import threading

    def pump(a, b):
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                b.sendall(d)
        except OSError:
            pass
        for x in (a, b):
            try:
                x.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def serve(lsock, path):
        while not stop.is_set():
            try:
                c, _ = lsock.accept()
            except OSError:
                return
            u = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            for _ in range(600):                       # the kernel may still be starting
                try:
                    u.connect(path)
                    break
                except OSError:
                    if stop.wait(0.05):
                        return
            else:
                c.close()
                continue
            threading.Thread(target=pump, args=(c, u), daemon=True).start()
            threading.Thread(target=pump, args=(u, c), daemon=True).start()

    out = []
    for k in PORTS:
        port = int(conn[k])
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((conn.get("ip") or "127.0.0.1", port))
        ls.listen(16)
        threading.Thread(target=serve, args=(ls, os.path.join(ipc_dir, f"k-{port}")), daemon=True).start()
        out.append(ls)
    return out


def _isolated_run(cfg: dict, argv: list[str], env: dict) -> int:   # pragma: no cover (kernel process tree)
    """Fork: the child execs the sandboxed kernel (own netns, IPC transport), the parent relays TCP → IPC and
    forwards signals; the parent's exit code is the kernel's."""
    import signal
    import tempfile
    import threading
    i = argv.index("-f") + 1 if "-f" in argv else None
    if i is None:
        os.execvpe(bwrap_argv(cfg, argv)[0], bwrap_argv(cfg, argv), env)
    conn = json.load(open(argv[i], encoding="utf-8"))
    ipc_dir = tempfile.mkdtemp(prefix=".ipc-", dir=cfg["workdir"])
    new_conn = os.path.join(ipc_dir, "connection.json")
    with open(new_conn, "w", encoding="utf-8") as f:
        json.dump(ipc_connection(conn, ipc_dir), f)
    argv = list(argv)
    argv[i] = new_conn
    stop = threading.Event()
    listeners = relay_tcp_to_ipc(conn, ipc_dir, stop)
    pid = os.fork()
    if pid == 0:
        for ls in listeners:
            ls.close()
        full = bwrap_argv(cfg, argv, isolate_net=True)
        os.execvpe(full[0], full, env)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGUSR1, signal.SIGUSR2):
        signal.signal(sig, lambda s, _f: os.kill(pid, s))
    while True:
        try:
            _p, status = os.waitpid(pid, 0)
            break
        except InterruptedError:
            continue
    stop.set()
    return os.waitstatus_to_exitcode(status)


def launcher_main(args: list[str]) -> None:   # pragma: no cover (exec'd inside the kernel process tree)
    """python3 -I sagebridge.py --launch CONFIG.json -- <kernel argv…>"""
    import resource
    cfg = json.load(open(args[1], encoding="utf-8"))
    argv = args[args.index("--") + 1:]
    wd = cfg["workdir"]
    for d in ("", ".tmp", ".ipython", ".sage", ".mpl", ".cache", ".config"):
        os.makedirs(os.path.join(wd, d), exist_ok=True)
    env = launcher_env(cfg, dict(os.environ))
    mem = int(cfg.get("mem_bytes") or 0)
    if mem:
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    fsize = int(cfg.get("fsize_bytes") or 0)
    if fsize:
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.chdir(wd)
    if cfg.get("bwrap") and cfg.get("isolate_net", True):
        rc = _isolated_run(cfg, argv, env)
        sys.exit(rc if rc >= 0 else 128 - rc)
    if cfg.get("bwrap"):
        argv = bwrap_argv(cfg, argv)
    os.execvpe(argv[0], argv, env)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--launch":   # pragma: no cover
    launcher_main(sys.argv[1:])
    sys.exit(127)


# ---------------------------------------------------------------- server side
import asyncio  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402

PREAMBLE = r'''
import json as _mjson
def report(verdict, witness=None, cases=None, note=""):
    """Madalean: structured result of an experiment (verdict: 'holds' | 'counterexample' | 'inconclusive')."""
    def _c(v):
        try:
            if hasattr(v, "is_integer") and not isinstance(v, float) and v.is_integer():
                return int(v)
        except Exception:
            pass
        if isinstance(v, (bool, int, float, str)) or v is None:
            return v
        if isinstance(v, (list, tuple)):
            return [_c(x) for x in v]
        if isinstance(v, dict):
            return {str(k): _c(x) for k, x in v.items()}
        try:
            return int(v)
        except Exception:
            return str(v)
    print("MADALEAN_RESULT " + _mjson.dumps({"verdict": str(verdict), "witness": _c(witness),
                                            "cases": _c(cases), "note": str(note)[:500]}))
'''
RESULT_RE = re.compile(r"^MADALEAN_RESULT (\{.*\})\s*$", re.M)
# S-P notebooks: the representations kept in an .ipynb (never text/html nor scripts), the figure spec of Calcul
NB_MIMES = ("text/plain", "text/latex", "text/markdown", "image/png", "image/svg+xml",
            "application/vnd.madalean.figure+json")
NB_MAX_OUTPUTS = 40


def nb_data(data: dict) -> dict:
    """The kept, bounded representations of a display_data / execute_result bundle (JSON mimes stay objects)."""
    out = {}
    for mime in NB_MIMES:
        v = data.get(mime)
        if mime.endswith("+json"):
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except ValueError:
                    continue
            if isinstance(v, dict) and len(json.dumps(v)) <= 1_000_000:
                out[mime] = v
            continue
        if isinstance(v, list):
            v = "".join(str(x) for x in v)
        if isinstance(v, str) and v and len(v) <= MAX_RICH_BYTES:
            out[mime] = v if mime != "text/plain" else v[:MAX_OUTPUT]
    return out


@dataclass
class ExecResult:
    status: str                    # ok | error | timeout | output_limit | died | unavailable
    stdout: str = ""
    stderr: str = ""
    result: str = ""               # text/plain of execute_result / display_data
    error: str = ""                # ename: evalue (+ traceback tail)
    seconds: float = 0.0
    killed: bool = False
    kernel: str = ""
    language: str = ""
    sandbox: str = ""
    reports: list[dict] = field(default_factory=list)
    rich: list[dict] = field(default_factory=list)   # S-M (Calcul): [{mime, data}] text/latex, image/png (base64), image/svg+xml
    # S-P (Calcul notebooks, `nb_outputs=True`): nbformat-4 shaped outputs in order, the kernel's execution counter and
    # the evaluated user_expressions ({name: text/plain}); empty for every other caller
    outputs: list[dict] = field(default_factory=list)
    execution_count: int | None = None
    user_expressions: dict = field(default_factory=dict)

    @property
    def output(self) -> str:
        return self.stdout + (("\n" + self.result) if self.result else "")

    def to_dict(self) -> dict:
        return {"status": self.status, "stdout": self.stdout, "stderr": self.stderr, "result": self.result,
                "error": self.error, "seconds": round(self.seconds, 2), "killed": self.killed,
                "language": self.language, "sandbox": self.sandbox, "reports": self.reports}


def parse_reports(text: str) -> list[dict]:
    out = []
    for m in RESULT_RE.finditer(text or ""):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("verdict") in ("holds", "counterexample", "inconclusive"):
            out.append(d)
    return out


def find_kernelspec(name: str) -> dict | None:
    for d in KERNEL_DIRS:
        f = Path(d) / name / "kernel.json"
        try:
            spec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(spec.get("argv"), list) and spec["argv"]:
            return spec
    return None


def system_python() -> str:
    for p in ("/usr/bin/python3", shutil.which("python3") or ""):
        if p and os.path.exists(p):
            return p
    return sys.executable


MAX_WARM_KERNELS = 3            # ≈ 0.3–0.6 GB each (Sage): bounded, kept warm (session S-Q, docs/PERFORMANCE.md)
KERNEL_IDLE_S = 2 * 3600.0      # was 10 min: every new experiment paid a Sage start (≈ 10–20 s)


class SageBridge:
    def __init__(self, ctx, workroot: Path | None = None, mem_mb: int = DEFAULT_MEM_MB, sandbox: bool = True):
        self.ctx = ctx
        self.workroot = Path(workroot or (ctx.paths.cache / "experiments"))
        self.mem_mb = mem_mb
        self.use_sandbox = sandbox
        self.bwrap = shutil.which("bwrap") if sandbox else None
        self.kernels: dict[str, dict] = {}        # key -> {id, language, last}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ kernelspecs
    def hidden_paths(self) -> list[str]:
        home = Path.home()
        jm = getattr(self.ctx, "jupyter", None)
        cands = [self.ctx.paths.config, home / ".config" / "madalean", home / ".config" / "madalean-demo",
                 # S-H: JupyterLab's token (config) and the other kernels' connection files (HMAC keys)
                 *([Path(jm.runtime_dir)] if jm is not None and getattr(jm, "runtime_dir", None) else []),
                 home / ".mozilla", home / ".config" / "chromium", home / ".config" / "google-chrome",
                 home / ".config" / "BraveSoftware", home / ".local" / "share" / "madalean" / "tailscale",
                 home / ".password-store", home / ".config" / "Signal", home / ".thunderbird",
                 home / ".config" / "lean-ai-station", home / ".ssh", home / ".gnupg", home / ".local/share/keyrings",
                 home / ".aws", home / ".netrc", home / ".git-credentials", home / ".config" / "gh",
                 home / ".docker" / "config.json", home / ".pypirc", home / ".kube"]
        out = []
        for p in cands:
            p = Path(p).resolve() if Path(p).exists() else Path(p)
            if str(self.workroot.resolve()).startswith(str(p) + os.sep):
                continue                                   # never hide the experiments directory itself
            out.append(str(p))
        return out

    def available(self) -> dict:
        return {lang: find_kernelspec(SPEC_NAMES[lang][1]) is not None for lang in SPEC_NAMES}

    def install_specs(self) -> dict[str, str]:
        """Write Madalean's kernelspecs into the Jupyter manager's JUPYTER_PATH. Returns language -> spec name."""
        jm = self.ctx.jupyter
        out = {}
        self.workroot.mkdir(parents=True, exist_ok=True)
        for lang, (spec_name, base, display, language) in SPEC_NAMES.items():
            base_spec = find_kernelspec(base)
            if base_spec is None:
                continue
            d = Path(jm.share_dir) / "kernels" / spec_name
            d.mkdir(parents=True, exist_ok=True)
            cfg = {"workdir": str(self.workroot.resolve()), "mem_bytes": self.mem_mb * 1024 * 1024,
                   "fsize_bytes": 512 * 1024 * 1024, "bwrap": self.bwrap or "", "hide": self.hidden_paths()}
            (d / "launcher.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
            spec = {"argv": [system_python(), "-I", str(Path(__file__).resolve()), "--launch", str(d / "launcher.json"),
                             "--", *base_spec["argv"]],
                    "display_name": display, "language": language, "interrupt_mode": "message",
                    "metadata": {"madalean": True}}
            (d / "kernel.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
            out[lang] = spec_name
        return out

    @property
    def sandbox_kind(self) -> str:
        return "bwrap" if self.bwrap else "rlimits"

    # ------------------------------------------------------------ jupyter REST
    async def _jm(self):
        jm = self.ctx.jupyter
        await jm._ensure()
        return jm

    async def _post(self, path: str, payload: dict | None = None):
        jm = await self._jm()
        async with jm._http().post(jm.url + jm.base_url + path, headers=jm._headers(), json=payload or {}) as r:
            body = await r.read()
            if r.status >= 400:
                raise RuntimeError(f"jupyter {r.status}: {body[:300]!r}")
            return json.loads(body) if body else {}

    async def start_kernel(self, language: str) -> str:
        specs = await asyncio.to_thread(self.install_specs)
        if language not in specs:
            raise RuntimeError(f"no {language} kernel installed")
        d = await self._post("api/kernels", {"name": specs[language]})
        return d["id"]

    async def shutdown(self, kid: str) -> None:
        jm = self.ctx.jupyter
        if jm.port is None:
            return
        try:
            async with jm._http().delete(jm.url + jm.base_url + f"api/kernels/{kid}", headers=jm._headers()) as r:
                await r.read()
        except Exception:  # noqa: BLE001
            pass
        for k, v in list(self.kernels.items()):
            if v["id"] == kid:
                del self.kernels[k]

    def forget(self, kid: str) -> None:
        for k, v in list(self.kernels.items()):
            if v["id"] == kid:
                del self.kernels[k]

    async def wait_ready(self, kid: str, timeout: float = 120) -> bool:
        """True once the kernel answers kernel_info; False when it died while starting (Jupyter restarts or
        removes it)."""
        import aiohttp
        jm = await self._jm()
        msg_id, session = uuid.uuid4().hex, uuid.uuid4().hex
        url = (jm.url + jm.base_url + f"api/kernels/{kid}/channels?session_id={session}").replace("http://", "ws://", 1)
        try:
            async with jm._http().ws_connect(url, headers=jm._headers(), max_msg_size=0) as ws:
                await ws.send_str(json.dumps({
                    "header": {"msg_id": msg_id, "username": "madalean", "session": session,
                               "msg_type": "kernel_info_request", "version": "5.3", "date": ""},
                    "parent_header": {}, "metadata": {}, "channel": "shell", "buffers": [], "content": {}}))

                async def wait() -> bool:
                    async for m in ws:
                        if m.type != aiohttp.WSMsgType.TEXT:
                            return False
                        d = json.loads(m.data)
                        mt = d.get("msg_type") or d.get("header", {}).get("msg_type")
                        if mt == "status" and d.get("content", {}).get("execution_state") in ("restarting", "dead"):
                            return False
                        if mt == "kernel_info_reply" and d.get("parent_header", {}).get("msg_id") == msg_id:
                            return True
                    return False
                return await asyncio.wait_for(wait(), timeout)
        except (aiohttp.ClientError, aiohttp.WSServerHandshakeError, asyncio.TimeoutError):
            return False

    async def interrupt(self, kid: str) -> None:
        try:
            await self._post(f"api/kernels/{kid}/interrupt")
        except Exception:  # noqa: BLE001
            pass

    async def kernel_for(self, key: str, language: str) -> str:
        """Reuse the kernel of this conjecture (state kept between its experiments), else start one. Kernels stay
        warm (user decision 2026-11-21: ~1.5–2 GB at rest is fine, a Sage start is slow) but at most
        MAX_WARM_KERNELS live at once: the least recently used one is shut down to make room."""
        key = f"{key}/{language}"
        async with self._lock:
            k = self.kernels.get(key)
            if k is not None:
                k["last"] = time.time()
                return k["id"]
            while len(self.kernels) >= MAX_WARM_KERNELS:
                old = min(self.kernels.values(), key=lambda v: v["last"])
                await self.shutdown(old["id"])
                self.kernels = {kk: v for kk, v in self.kernels.items() if v is not old}
            kid = await self.start_kernel(language)
            self.kernels[key] = {"id": kid, "language": language, "last": time.time()}
            return kid

    async def reap(self, idle_s: float | None = None) -> None:
        idle_s = KERNEL_IDLE_S if idle_s is None else idle_s
        for key, k in list(self.kernels.items()):
            if time.time() - k["last"] > idle_s:
                await self.shutdown(k["id"])

    async def close(self) -> None:
        for k in list(self.kernels.values()):
            await self.shutdown(k["id"])

    # ------------------------------------------------------------ execution
    async def execute(self, kid: str, code: str, *, timeout: float = DEFAULT_TIMEOUT_S, max_output: int = MAX_OUTPUT,
                      on_output=None, language: str = "", store_history: bool = False,
                      user_expressions: dict | None = None, kill_on_limit: bool = True,
                      nb_outputs: bool = False) -> ExecResult:
        """`nb_outputs` (S-P notebooks): also collect nbformat outputs; `kill_on_limit=False`: on timeout / output
        limit the kernel is only interrupted (the notebook's caller decides whether it must be shut down)."""
        import aiohttp
        jm = await self._jm()
        timeout = max(1.0, min(float(timeout), MAX_TIMEOUT_S))
        res = ExecResult("ok", kernel=kid, language=language, sandbox=self.sandbox_kind)
        msg_id, session = uuid.uuid4().hex, uuid.uuid4().hex
        url = (jm.url + jm.base_url + f"api/kernels/{kid}/channels?session_id={session}").replace("http://", "ws://", 1)
        t0 = time.monotonic()
        total = 0
        done = asyncio.Event()
        finished = {"idle": False, "reply": not user_expressions}
        outs = res.outputs

        def nb_add(out: dict) -> None:
            if not nb_outputs or len(outs) >= NB_MAX_OUTPUTS:
                return
            if out["output_type"] == "stream" and outs and outs[-1]["output_type"] == "stream" \
                    and outs[-1]["name"] == out["name"]:
                outs[-1]["text"] += out["text"]
            else:
                outs.append(out)

        def emit(kind: str, text: str) -> None:
            nonlocal total
            if res.status == "output_limit":
                return
            total += len(text)
            if total > max_output:
                res.status = "output_limit"
                text = text[: max(0, len(text) - (total - max_output))] + "\n[… output truncated]"
            if kind == "stdout":
                res.stdout += text
            elif kind == "stderr":
                res.stderr += text
            else:
                res.result += text
            if kind in ("stdout", "stderr"):
                nb_add({"output_type": "stream", "name": kind, "text": text})
            if on_output:
                try:
                    on_output(kind, text)
                except Exception:  # noqa: BLE001
                    pass

        try:
            ws_cm = await jm._http().ws_connect(url, headers=jm._headers(), max_msg_size=0)
        except (aiohttp.ClientError, aiohttp.WSServerHandshakeError) as e:
            self.forget(kid)
            res.status, res.error = "died", f"kernel unreachable: {e}"[:300] + "\n" + "\n".join(jm._tail[-8:])
            return res
        async with ws_cm as ws:
            await ws.send_str(json.dumps({
                "header": {"msg_id": msg_id, "username": "madalean", "session": session,
                           "msg_type": "execute_request", "version": "5.3", "date": ""},
                "parent_header": {}, "metadata": {}, "channel": "shell", "buffers": [],
                "content": {"code": code, "silent": False, "store_history": bool(store_history),
                            "user_expressions": dict(user_expressions or {}),
                            "allow_stdin": False, "stop_on_error": True}}))

            async def pump() -> None:
                async for m in ws:
                    if m.type != aiohttp.WSMsgType.TEXT:
                        if m.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            break
                        continue
                    d = json.loads(m.data)
                    mt = d.get("msg_type") or d.get("header", {}).get("msg_type")
                    if mt == "status" and d.get("content", {}).get("execution_state") in ("restarting", "dead"):
                        res.status = "died"
                        break
                    if d.get("parent_header", {}).get("msg_id") != msg_id:
                        continue
                    c = d.get("content", {})
                    if mt == "execute_input" and isinstance(c.get("execution_count"), int):
                        res.execution_count = c["execution_count"]
                    elif mt == "execute_reply":
                        if isinstance(c.get("execution_count"), int):
                            res.execution_count = c["execution_count"]
                        for k, v in (c.get("user_expressions") or {}).items():
                            if isinstance(v, dict) and v.get("status") == "ok":
                                res.user_expressions[str(k)] = str((v.get("data") or {}).get("text/plain", ""))[:2000]
                        finished["reply"] = True
                        if finished["idle"]:
                            break
                    if mt == "stream":
                        emit("stdout" if c.get("name") == "stdout" else "stderr", c.get("text", ""))
                    elif mt in ("execute_result", "display_data"):
                        data = c.get("data") or {}
                        emit("result", str(data.get("text/plain", "")) + "\n")
                        for mime in RICH_MIMES:            # first rich representation only, bounded
                            v = data.get(mime)
                            if isinstance(v, list):
                                v = "".join(str(x) for x in v)
                            if isinstance(v, str) and v and len(res.rich) < MAX_RICH and len(v) <= MAX_RICH_BYTES:
                                res.rich.append({"mime": mime, "data": v})
                                break
                        if nb_outputs:
                            keep = nb_data(data)
                            if keep:
                                out = {"output_type": mt, "data": keep, "metadata": {}}
                                if mt == "execute_result":
                                    out["execution_count"] = c.get("execution_count")
                                nb_add(out)
                    elif mt == "error":
                        tb = "\n".join(re.sub(r"\x1b\[[0-9;]*m", "", t) for t in (c.get("traceback") or [])[-6:])
                        res.error = f"{c.get('ename')}: {c.get('evalue')}\n{tb}"[-4000:]
                        if res.status == "ok":
                            res.status = "error"
                        nb_add({"output_type": "error", "ename": str(c.get("ename"))[:200],
                                "evalue": str(c.get("evalue"))[:4000],
                                "traceback": [str(t)[:4000] for t in (c.get("traceback") or [])[-20:]]})
                    elif mt == "status" and c.get("execution_state") == "idle":
                        finished["idle"] = True
                        if finished["reply"]:
                            break
                    if res.status == "output_limit":
                        break
                if not finished["idle"] and res.status == "ok":
                    res.status = "died"                  # the channel closed before the execution finished
                done.set()

            task = asyncio.create_task(pump())
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout)
            except asyncio.TimeoutError:
                res.status = "timeout"
            except asyncio.CancelledError:
                task.cancel()
                await self.shutdown(kid)
                raise
            finally:
                if not task.done():
                    task.cancel()
        if res.status in ("timeout", "output_limit", "died"):
            # interrupt first, then kill: a runaway kernel never survives its experiment
            await self.interrupt(kid)
            if kill_on_limit or res.status == "died":
                await self.shutdown(kid)
                res.killed = True
        res.seconds = time.monotonic() - t0
        res.reports = parse_reports(res.stdout)
        return res

    async def run(self, key: str, language: str, code: str, *, timeout: float = DEFAULT_TIMEOUT_S,
                  max_output: int = MAX_OUTPUT, on_output=None, fresh: bool = False, workdir: str = "",
                  preamble: str = "") -> ExecResult:
        """Execute `code` (preceded by PREAMBLE) in the conjecture's kernel (`fresh`: a new kernel, shut down after).
        `preamble`: more helper definitions run with PREAMBLE (the Calcul screen's `tex`)."""
        prefix = PREAMBLE + (("\n" + preamble) if preamble else "")
        if workdir:
            prefix += f"\nimport os as _mos\n_mos.makedirs({workdir!r}, exist_ok=True)\n_mos.chdir({workdir!r})\n"
        kid = ""
        try:
            for attempt in range(3):
                # a kernel can die while starting (seen with Sage's GAP probe under load): start a new one
                try:
                    kid = await (self.start_kernel(language) if fresh else self.kernel_for(key, language))
                except Exception as e:  # noqa: BLE001
                    return ExecResult("unavailable", error=str(e)[:500], language=language, sandbox=self.sandbox_kind)
                if not await self.wait_ready(kid):
                    await self.shutdown(kid)
                    self.forget(kid)
                    pre = ExecResult("died", error="kernel died while starting\n" + "\n".join(self.ctx.jupyter._tail[-25:]), language=language,
                                     sandbox=self.sandbox_kind)
                    if attempt == 2:
                        return pre
                    continue
                # the preamble runs first so that line numbers of errors match the user's code
                pre = await self.execute(kid, prefix, timeout=120, language=language)
                if pre.status == "ok":
                    break
                await self.shutdown(kid)
                if pre.status != "died" or attempt == 2:
                    return pre
            return await self.execute(kid, code, timeout=timeout, max_output=max_output, on_output=on_output,
                                      language=language)
        finally:
            if fresh:
                await self.shutdown(kid)
