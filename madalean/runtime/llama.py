"""The single local llama-server (implements `madalean.brain.api.LocalRuntime`).

Port of 1.1.4 `LlamaServer` + `AppContext.ensure_model`: one model in VRAM at a time (swap per role), launch plan
fitted to the free VRAM (`plan_launch`, verbatim), automatic OOM fallback (smaller context, then fewer GPU layers,
3 retries), orphan cleanup through our own pid file only (never another program's server), port chosen from 8765
upwards when busy. Holding the `gpu` slot is reentrant per job (`slots.CURRENT_JOB`)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import aiohttp

from .. import config
from ..brain.api import BrainError, ModelRef
from ..brain.providers.base import ProviderError
from ..gguf import GGUFError, GGUFInfo, find_models, read_info
from ..i18n import _
from ..logs import get
from ..slots import Slots, current_owner
from . import guarded, ollama_share
from .monitor import Monitor

log = get("llama")

# role of the brain -> kind of local model
ROLE_KIND = {"formalize": "formalizer", "prove": "prover", "understand": "explainer", "route": "explainer",
             "explain": "explainer", "assistant": "explainer"}


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _proc_cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def kill_orphan_server(pid_file: Path) -> bool:
    """Kill a llama-server left by a previous crashed session of *this* server (our pid file only)."""
    try:
        pid = int(pid_file.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return False
    killed = False
    if "llama-server" in _proc_cmdline(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for _i in range(30):
                time.sleep(0.1)
                if not _proc_cmdline(pid):
                    break
            else:
                os.kill(pid, signal.SIGKILL)
            killed = True
        except ProcessLookupError:
            pass
    try:
        pid_file.unlink()
    except OSError:
        pass
    return killed


# ---------------------------------------------------------------- model choice (port of AppContext)
def is_formalizer(path: Path | str) -> bool:
    return "formalizer" in Path(path).name.lower()


def is_explainer(path: Path | str) -> bool:
    n = Path(path).name.lower()
    return "qwen3" in n and "goedel" not in n


def pick_model(kind: str, models: list[GGUFInfo], preferred: str = "", vram_total: int | None = None) -> Path | None:
    good = [m for m in models if isinstance(m, GGUFInfo)]
    if kind == "formalizer":
        c = [m for m in good if is_formalizer(m.path)]
        return max(c, key=lambda m: ("Q4_K_M" in m.path.name, -m.size)).path if c else None
    if kind == "explainer":
        c = [m for m in good if is_explainer(m.path)]
        return max(c, key=lambda m: ("Q4_K_M" in m.path.name, -m.size)).path if c else None
    provers = [m for m in good if not is_formalizer(m.path) and not is_explainer(m.path)]
    # S-H: `model_path` is a setting a paired device may change; only a model of the scanned list is loaded
    # (never an arbitrary file handed to llama.cpp's GGUF parser, e.g. an uploaded attachment)
    known = {str(m.path.resolve()): m.path for m in provers}
    if preferred and str(Path(preferred).expanduser().resolve()) in known:
        return known[str(Path(preferred).expanduser().resolve())]
    goedel = [m for m in provers if "goedel" in m.path.name.lower()]
    cands = goedel or provers
    if not cands:
        return None
    q4 = [m for m in cands if m.quant == "Q4_K_M"]
    if q4:
        return q4[0].path
    fit = [m for m in cands if vram_total and m.size < vram_total * 0.75 * 2**20]
    return max(fit or cands, key=lambda m: m.size).path


# ---------------------------------------------------------------- launch plan (verbatim port)
@dataclass
class LaunchPlan:
    model: Path
    info: GGUFInfo | None
    gpu_layers: int
    ctx: int
    kv_type: str
    note: str = ""


def plan_launch(model: Path, s: config.ServerSettings, vram_free_mib: int | None) -> LaunchPlan:
    """Choose GPU layers / context so the model fits; never refuses, downgrades with an explanation."""
    try:
        info = read_info(model)
    except (OSError, GGUFError):
        info = None
    ctx, ngl, kv = s.ctx_size, s.gpu_layers, s.kv_type if s.flash_attn else "f16"
    if info is not None and info.ctx_train:
        ctx = min(ctx, info.ctx_train)
    if vram_free_mib is None:
        return LaunchPlan(model, info, 0, min(ctx, 8192), kv,
                          _("Aucune carte graphique NVIDIA utilisable : le modèle tourne sur le processeur (beaucoup plus lent)."))
    if info is None:
        return LaunchPlan(model, None, ngl, ctx, kv)
    budget = vram_free_mib * 1024 * 1024 - 450 * 1024 * 1024    # CUDA context + compute buffers
    need = info.size + info.kv_bytes(ctx, kv) + 300 * 1024 * 1024
    if need <= budget or ngl < 99:
        return LaunchPlan(model, info, ngl, ctx, kv)
    c = ctx
    while c > 8192 and info.size + info.kv_bytes(c, kv) + 300 * 1024 * 1024 > budget:
        c //= 2
    if info.size + info.kv_bytes(c, kv) + 300 * 1024 * 1024 <= budget:
        return LaunchPlan(model, info, ngl, c, kv,
                          _("Mémoire graphique limitée : contexte réduit à {c} tokens pour que tout tienne sur la carte.").format(c=c))
    per_layer = info.size / max(info.n_layers + 1, 1)
    layers = int((budget - info.kv_bytes(c, kv) - 300 * 1024 * 1024) // per_layer)
    layers = max(0, min(info.n_layers, layers))
    return LaunchPlan(model, info, layers, c, kv,
                      _("Le modèle est trop gros pour la carte graphique : {l}/{n} couches sur la carte, le reste sur le "
                        "processeur (plus lent). Un modèle plus petit (Q4_K_M) serait plus rapide.").format(l=layers, n=info.n_layers))


def oom_fallback(pl: LaunchPlan) -> LaunchPlan:
    """Next plan after an out-of-memory failure: smaller context first, then 30 % fewer GPU layers."""
    if pl.ctx > 8192:
        n = max(8192, pl.ctx // 2)
        return LaunchPlan(pl.model, pl.info, pl.gpu_layers, n, pl.kv_type,
                          _("Mémoire graphique insuffisante : nouvel essai avec un contexte de {n} tokens.").format(n=n))
    total = pl.info.n_layers if pl.info else 36
    cur = min(pl.gpu_layers, total)
    n = max(0, int(cur * 0.7))
    return LaunchPlan(pl.model, pl.info, n, pl.ctx, pl.kv_type,
                      _("Mémoire graphique insuffisante : nouvel essai avec {n} couches sur la carte.").format(n=n))


# ---------------------------------------------------------------- GPU lending (S-N, user decision 2026-11-21)
# When the GPU is short, Ollama (user service, used by mi-saina / Sampana / L Katta) is asked to unload its models
# through its documented API (keep_alive 0) — nothing is killed or stopped, Ollama reloads on its next request.
# Preferred path: the separate tool `fitantanana gpu lend` (inventory + coordination); fallback: the same request
# made here directly. Madalean gives the GPU back by stopping llama-server after `local_idle_unload_minutes`.
def full_gpu_need_mib(model: Path, s: config.ServerSettings) -> int | None:
    """VRAM (MiB) for the whole model + KV cache on the GPU, with the margins of `plan_launch`."""
    try:
        info = read_info(model)
    except (OSError, GGUFError):
        return None
    ctx = min(s.ctx_size, info.ctx_train) if info.ctx_train else s.ctx_size
    kv = s.kv_type if s.flash_attn else "f16"
    return int((info.size + info.kv_bytes(ctx, kv) + 750 * 1024 * 1024) / 2**20) + 1


def fitantanana_exe() -> str | None:
    for c in (os.environ.get("MADALEAN_FITANTANANA"), shutil.which("fitantanana"),
              str(Path.home() / ".local/bin/fitantanana"), str(Path.home() / "GitHub/fitantanana/bin/fitantanana")):
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def ollama_url() -> str:
    h = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
    return (h if h.startswith("http") else "http://" + h).rstrip("/")


async def _ollama_loaded(http: aiohttp.ClientSession, base: str) -> list[dict] | None:
    try:
        async with http.get(base + "/api/ps") as r:
            return list((await r.json(content_type=None)).get("models") or []) if r.status == 200 else None
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
        return None


async def lend_gpu(need_mib: int, timeout: float = 60.0, base: str | None = None) -> dict:
    """Ask for `need_mib` MiB of free VRAM. Never raises; returns the lending report (`via`: fitantanana|builtin)."""
    exe = fitantanana_exe()
    if exe:
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                exe, "gpu", "lend", "--to", "madalean", "--need", str(need_mib), "--timeout", str(int(timeout)),
                "--json", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            out, _e = await asyncio.wait_for(proc.communicate(), timeout + 15)
            d = json.loads(out.decode() or "{}")
            if isinstance(d, dict) and "reason" in d:
                return {**d, "via": "fitantanana"}
        except (OSError, asyncio.TimeoutError, ValueError):
            if proc is not None and proc.returncode is None:
                proc.kill()
    # built-in minimal fallback: unload every model Ollama keeps in VRAM, then wait until they are gone
    base = base or ollama_url()
    out: dict = {"via": "builtin", "need_mib": need_mib, "unloaded": [], "ok": False}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as http:
        loaded = await _ollama_loaded(http, base)
        if loaded is None:
            return {**out, "reason": "ollama_unreachable"}
        for m in sorted((m for m in loaded if m.get("size_vram")), key=lambda m: -m["size_vram"]):
            try:
                async with http.post(base + "/api/generate", json={"model": m["name"], "keep_alive": 0,
                                                                   "stream": False}) as r:
                    if r.status == 200:
                        out["unloaded"].append(m["name"])
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                continue
        t0 = time.monotonic()
        while out["unloaded"] and time.monotonic() - t0 < timeout:
            still = {m.get("name") for m in (await _ollama_loaded(http, base) or [])} & set(out["unloaded"])
            if not still:
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.0 if out["unloaded"] else 0)    # the runner process releases its CUDA memory
    return {**out, "ok": bool(out["unloaded"]), "reason": "freed" if out["unloaded"] else "nothing_to_unload"}


async def give_back_gpu() -> None:
    exe = fitantanana_exe()
    if not exe:
        return
    try:
        p = await asyncio.create_subprocess_exec(exe, "gpu", "return", "--from", "madalean", "--json",
                                                 stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.wait_for(p.wait(), 15)
    except (OSError, asyncio.TimeoutError):
        pass


def gpu_share(gpu: dict | None, own_pid: int | None) -> dict | None:
    """Who holds the GPU now (for Système → santé): Ollama, Madalean, others — from the monitor snapshot."""
    if not gpu:
        return None
    by: dict[str, int] = {}
    for pid, mib in (gpu.get("apps") or {}).items():
        pid = int(pid)
        cmd = _proc_cmdline(pid)
        name = ("Madalean" if pid == own_pid or "llama-server" in cmd else "Ollama" if "ollama" in cmd
                else (Path(cmd.split(" ")[0]).name if cmd else f"pid {pid}"))
        by[name] = by.get(name, 0) + int(mib)
    return {"holders": [{"app": k, "mib": v} for k, v in sorted(by.items(), key=lambda x: -x[1])],
            "free": gpu.get("free"), "total": gpu.get("total")}


class LaunchError(Exception):
    def __init__(self, kind: str, details: str = ""):
        super().__init__(f"{kind}: {details[-300:]}")
        self.kind, self.details = kind, details     # crashed | oom | bad_model | no_binary | port | timeout


# ---------------------------------------------------------------- runtime
class LocalLlama:
    STOPPED, STARTING, READY, STOPPING = "stopped", "starting", "ready", "stopping"

    def __init__(self, slots: Slots, monitor: Monitor, pid_file: Path, get_settings: Callable[[], config.Settings],
                 models_dir: Path | None = None, bin_dir: Path | None = None, load_timeout: float = 300.0):
        self.slots, self.monitor, self.pid_file = slots, monitor, Path(pid_file)
        self.get_settings = get_settings
        self.models_dir = Path(models_dir or config.MODELS_DIR)
        self.bin_dir = Path(bin_dir or config.LLAMA_BIN_DIR)
        self.load_timeout = load_timeout
        self.models: list = []                  # GGUFInfo | (Path, error)
        self.state = self.STOPPED
        self.proc: asyncio.subprocess.Process | None = None
        self.plan: LaunchPlan | None = None
        self.port = 8765
        self.offload = ""
        self.load_seconds: float | None = None
        self.last_pid: int | None = None
        self.notes: list[str] = []
        self.last_error: dict | None = None
        self.loads = 0                          # number of model loads (tests: swaps)
        self._tail: list[str] = []
        self._holder: str | None = None
        self._load_lock = asyncio.Lock()
        self._reader: asyncio.Task | None = None
        self.on_change: Callable[[], None] | None = None
        self.last_used = time.monotonic()       # S-N: idle unload gives the GPU back to the other apps
        self.idle_poll = 30.0
        self._idle_task: asyncio.Task | None = None
        self.last_lend: dict | None = None
        self.ollama: dict | None = None         # S-AS: last look at Ollama (reachable, models, busy)
        self.busy_poll = 1.0

    # ------------------------------------------------------------ models
    async def refresh_models(self) -> list:
        def scan():
            out = []
            for p in find_models(self.models_dir):
                try:
                    out.append(read_info(p))
                except (OSError, GGUFError) as e:
                    out.append((p, str(e)))
            return out
        self.models = await asyncio.to_thread(scan)
        self._changed()
        return self.models

    def path_for(self, role: str) -> Path | None:
        kind = ROLE_KIND.get(role, "prover")
        total = self.monitor.gpu["total"] if self.monitor.gpu else None
        return pick_model(kind, self.models, self.get_settings().model_path, total)

    def model_for(self, role: str) -> ModelRef | None:
        p = self.path_for(role)
        if p is None:
            return None
        return ModelRef("local", p.name, p.stem, local=True, paid=False)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def model_path(self) -> Path | None:
        return self.plan.model if self.plan else None

    def status(self) -> dict:
        return {"state": self.state, "model": self.model_path.name if self.model_path else None,
                "port": self.port if self.state != self.STOPPED else None, "offload": self.offload,
                "load_seconds": self.load_seconds, "ctx": self.plan.ctx if self.plan else None,
                "gpu_layers": self.plan.gpu_layers if self.plan else None, "notes": self.notes[-3:],
                "error": self.last_error, "holder": self._holder, "last_lend": self.last_lend,
                "gpu_share": gpu_share(self.monitor.gpu, self.last_pid if self.state != self.STOPPED else None),
                "share_ollama": self.share_status(),
                "roles": {r: (self.path_for(r).name if self.path_for(r) else None)
                          for r in ("formalize", "prove", "explain")}}

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                log.exception("on_change failed")

    # ------------------------------------------------------------ LocalRuntime
    async def ensure(self, role: str) -> str | None:
        target = self.path_for(role)
        if target is None:
            return None
        owner = current_owner()
        self.last_used = time.monotonic()
        if self._holder != owner:
            await self.slots.acquire("gpu", owner)
            self._holder = owner
            self._changed()
        try:
            async with self._load_lock:
                if not (self.state == self.READY and self.model_path == target and self.proc
                        and self.proc.returncode is None):
                    await self._start(target)
            return self.url + "/v1"
        except BaseException:
            self.release()
            raise

    def release(self) -> None:
        self.last_used = time.monotonic()
        owner = current_owner()
        if self._holder is not None and (self._holder == owner or not self._holder_alive()):
            self.slots.release("gpu", self._holder)
            self._holder = None
            self._changed()

    def release_owner(self, owner: str) -> None:
        self.last_used = time.monotonic()
        if self._holder == owner:
            self.slots.release("gpu", owner)
            self._holder = None
            self._changed()

    def _holder_alive(self) -> bool:
        return self._holder in self.slots.holders.get("gpu", [])

    # ------------------------------------------------------------ process
    async def _start(self, model: Path) -> None:
        exe = self.bin_dir / "llama-server"
        if not exe.exists():
            self._fail("no_binary", f"{exe} not found")
        if not model.exists():
            self._fail("bad_model", f"missing file: {model}")
        await self.stop()
        await self.monitor.first_snapshot()
        s = self.get_settings().server
        vram = None if not self.monitor.gpu_ok else self.monitor.free_excluding(self.last_pid)
        vram = await self._borrow_gpu(model, s, vram)
        plan = plan_launch(model, s, vram)
        for retry in range(4):
            try:
                await self._launch(plan, s)
                return
            except LaunchError as e:
                if e.kind == "oom" and retry < 3:
                    plan = oom_fallback(plan)
                    continue
                self._fail(e.kind, e.details)

    async def _borrow_gpu(self, model: Path, s: config.ServerSettings, vram: int | None) -> int | None:
        """Free VRAM held by Ollama when the model would not fit entirely (S-N); returns the new free VRAM.

        S-AS (D51): only with « Partage de la carte graphique avec Ollama » on, and never while Ollama is answering
        another application — wait up to `gpu_share_busy_wait_s`, then the fallback of the settings."""
        need = full_gpu_need_mib(model, s) if vram is not None else None
        if need is None or vram >= need or not self._ollama_holds_gpu():
            return vram
        st = self.get_settings()
        if not getattr(st, "gpu_share_ollama", True):
            self.last_lend = {"ok": False, "reason": "disabled", "need_mib": need, "t": time.time()}
            self.notes.append(_("Partage de la carte graphique avec Ollama désactivé : le modèle utilise la mémoire "
                                "graphique libre (en partie sur le processeur, plus lent)."))
            return vram
        if not await self._wait_ollama_idle(float(getattr(st, "gpu_share_busy_wait_s", 30) or 0)):
            self.last_lend = {"ok": False, "reason": "ollama_busy", "need_mib": need, "t": time.time(),
                              "unloaded": []}
            self._changed()
            if getattr(st, "gpu_share_busy_fallback", "cpu") == "online":
                self.notes.append(_("Ollama répond toujours à une autre application : Madalean ne l'interrompt pas "
                                    "et confie la tâche au modèle suivant (en ligne)."))
                raise ProviderError("unavailable", "GPU busy: Ollama is answering another application "
                                                   "(not interrupted)")
            self.notes.append(_("Ollama répond toujours à une autre application : Madalean ne l'interrompt pas et "
                                "charge son modèle avec la mémoire graphique libre (en partie sur le processeur, "
                                "plus lent)."))
            return vram
        res = await lend_gpu(need - vram + int(self.monitor.gpu["free"]) if self.monitor.gpu else need)
        self.last_lend = {k: res.get(k) for k in ("ok", "reason", "via", "unloaded", "free_before", "free_after",
                                                   "need_mib")}
        self.last_lend["t"] = time.time()
        if res.get("unloaded"):
            self.notes.append(_("Carte graphique prêtée par Ollama : {models} déchargé(s) (Ollama les rechargera "
                                "à la demande).").format(models=", ".join(res["unloaded"])))
            log.info("GPU lent by Ollama: %s (%s)", res["unloaded"], res.get("via"))
        try:
            await self.monitor.poll()
        except Exception:  # noqa: BLE001
            log.exception("monitor poll after GPU lending failed")
        return self.monitor.free_excluding(self.last_pid) if self.monitor.gpu_ok else vram

    async def look_at_ollama(self, sample: float = 0.5) -> dict:
        """Is Ollama answering someone now? (ollama_share.activity, cached for the status views)."""
        self.ollama = await ollama_share.activity(ollama_url(), (self.monitor.gpu or {}).get("util"), sample)
        return self.ollama

    async def _wait_ollama_idle(self, wait_s: float) -> bool:
        act = await self.look_at_ollama()
        if not act["busy"]:
            return True
        log.info("Ollama is answering another application (%s): waiting up to %s s", act["signals"], wait_s)
        self.notes.append(_("Ollama répond à une autre application : Madalean attend qu'il ait fini (au plus {s} s) "
                            "avant de lui emprunter la carte graphique.").format(s=int(wait_s)))
        self._changed()
        t0 = time.monotonic()
        while time.monotonic() - t0 < wait_s:
            await asyncio.sleep(self.busy_poll)
            try:
                await self.monitor.poll()
            except Exception:  # noqa: BLE001
                pass
            if not (await self.look_at_ollama())["busy"]:
                return True
        return False

    def share_status(self) -> dict:
        """« Partage de la carte graphique avec Ollama » for the status panel and the health page."""
        st = self.get_settings()
        o = self.ollama or {}
        return {"enabled": bool(getattr(st, "gpu_share_ollama", True)),
                "fallback": getattr(st, "gpu_share_busy_fallback", "cpu"),
                "wait_s": getattr(st, "gpu_share_busy_wait_s", 30),
                "idle_unload_minutes": getattr(st, "local_idle_unload_minutes", 10),
                "ollama": {"reachable": o.get("reachable"), "models": o.get("models", []), "busy": o.get("busy", False),
                           "t": o.get("t")} if o else None,
                "last_lend": self.last_lend}

    def _ollama_holds_gpu(self) -> bool:
        return any("ollama" in _proc_cmdline(int(p)) for p in (self.monitor.gpu or {}).get("apps", {}))

    async def _idle_watch(self) -> None:
        """Stop llama-server after `local_idle_unload_minutes` without use, to give the GPU back (0 = never)."""
        while self.state == self.READY:
            await asyncio.sleep(self.idle_poll)
            minutes = float(getattr(self.get_settings(), "local_idle_unload_minutes", 10) or 0)
            if (minutes > 0 and self.state == self.READY and self._holder is None and not self._load_lock.locked()
                    and time.monotonic() - self.last_used >= minutes * 60):
                log.info("local model idle for %s min: stopping llama-server to give the GPU back", minutes)
                await self.stop()
                self.notes.append(_("Modèle local arrêté après {m} min sans utilisation : la carte graphique est "
                                    "rendue aux autres applications.").format(m=int(minutes)))
                await give_back_gpu()
                self._changed()
                return

    def _fail(self, kind: str, details: str) -> None:
        self.last_error = {"kind": kind, "details": details[-2000:]}
        self.state = self.STOPPED
        self._changed()
        log.warning("local model failed: %s", kind)
        raise BrainError("error", f"local model: {kind}", [f"local: {kind}"])

    async def _launch(self, plan: LaunchPlan, s: config.ServerSettings) -> None:
        await asyncio.to_thread(kill_orphan_server, self.pid_file)
        port = s.port
        if not port_free(port):
            for p in range(port + 1, port + 50):
                if port_free(p):
                    self.notes.append(_("Le port {port} est déjà utilisé : le serveur utilise le port {p}.").format(port=port, p=p))
                    port = p
                    break
            else:
                raise LaunchError("port", _("Aucun port libre à partir de {port}").format(port=port))
        self.port, self.plan = port, plan
        if plan.note:
            self.notes.append(plan.note)
        fa = s.flash_attn and plan.gpu_layers > 0
        kv = plan.kv_type if fa else "f16"
        args = ["-m", str(plan.model), "--host", "127.0.0.1", "--port", str(port),
                "-ngl", str(plan.gpu_layers), "-c", str(plan.ctx), "-b", str(s.batch_size), "-ub", str(s.ubatch_size),
                "-fa", "on" if fa else "off", "-ctk", kv, "-ctv", kv, "-t", str(s.threads),
                "-np", "1", "--jinja", "--reasoning-format", "none", "--no-webui", "--fit", "off", "-lv", "4", "-cram", "1024"]
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(self.bin_dir)
        if plan.gpu_layers == 0:
            env["CUDA_VISIBLE_DEVICES"] = ""
        self._tail, self.offload, self.load_seconds = [], "", None
        self.state = self.STARTING
        self._changed()
        log.info("starting llama-server %s", " ".join(args))
        t0 = time.monotonic()
        try:
            self.proc = await asyncio.create_subprocess_exec(*guarded(str(self.bin_dir / "llama-server"), args),
                                                             stdout=asyncio.subprocess.PIPE,
                                                             stderr=asyncio.subprocess.STDOUT, env=env)
        except OSError as e:
            self.state = self.STOPPED
            raise LaunchError("no_binary", str(e)) from e
        self.last_pid = self.proc.pid
        self.loads += 1
        proc = self.proc
        self._reader = asyncio.create_task(self._read(proc))
        flags = {"oom": False, "bad": False}
        self._flags = flags
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as http:
            while True:
                if proc.returncode is not None:
                    await asyncio.sleep(0.05)              # let the reader drain the last lines
                    self.proc = None
                    self.state = self.STOPPED
                    details = "\n".join(self._tail[-25:])
                    kind = "oom" if flags["oom"] else "bad_model" if flags["bad"] else "crashed"
                    raise LaunchError(kind, details)
                if time.monotonic() - t0 > self.load_timeout:
                    await self.stop()
                    raise LaunchError("timeout", "\n".join(self._tail[-15:]))
                try:
                    async with http.get(f"http://127.0.0.1:{port}/health") as r:
                        if r.status == 200:
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    pass
                await asyncio.sleep(0.4)
        self.load_seconds = time.monotonic() - t0
        self.state = self.READY
        self.last_error = None
        try:
            await asyncio.to_thread(config.atomic_write_text, self.pid_file, f"{proc.pid} {port} {plan.model}\n")
        except OSError:
            pass
        log.info("llama-server ready in %.1f s (%s, offload %s)", self.load_seconds, plan.model.name, self.offload)
        self.last_used = time.monotonic()
        if self._idle_task is None or self._idle_task.done():
            self._idle_task = asyncio.create_task(self._idle_watch(), name="llama-idle")
        self._changed()

    async def _read(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        while True:
            line_b = await proc.stdout.readline()
            if not line_b:
                break
            line = line_b.decode("utf-8", "replace").rstrip()
            if not line:
                continue
            self._tail = (self._tail + [line])[-60:]
            low = line.lower()
            m = re.search(r"offloaded (\d+)/(\d+) layers to gpu", low)
            if m:
                self.offload = f"{m.group(1)}/{m.group(2)}"
            flags = getattr(self, "_flags", {})
            if "out of memory" in low or "cudamalloc failed" in low or "failed to allocate" in low:
                flags["oom"] = True
            if ("failed to load model" in low or "error loading model" in low or "invalid magic" in low
                    or "gguf_init_from_file" in low and "failed" in low):
                flags["bad"] = True
        await proc.wait()
        if proc is self.proc and self.state == self.READY:
            self.state = self.STOPPED
            self.proc = None
            self.last_error = {"kind": "crashed", "details": "\n".join(self._tail[-25:])}
            log.warning("llama-server exited unexpectedly")
            self._changed()

    async def stop(self, timeout: float = 5.0) -> None:
        idle = self._idle_task
        if idle is not None and idle is not asyncio.current_task() and not idle.done():
            idle.cancel()
        proc, self.proc = self.proc, None
        if proc is None or proc.returncode is not None:
            self.state = self.STOPPED
            return
        self.state = self.STOPPING
        self._changed()
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass
        self.state = self.STOPPED
        try:
            self.pid_file.unlink()
        except OSError:
            pass
        self._changed()
