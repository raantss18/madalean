"""Everything the server runs, wired together: settings, stores, event bus, slots, children, brain, orchestrator."""
from __future__ import annotations

import asyncio
import json
import os
import socket
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import __version__, config, i18n
from .brain.api import ModelRef
from .dossiers import DossierStore, Library
from .jobs import Job, JobHistory
from .keys import KeyStore
from .logs import get
from .paths import Paths
from .projects import ProjectStore
from .repo import DossierRepo, ProjectRepo
from .runtime.lean import LeanRunner
from .runtime.llama import LocalLlama
from .runtime.monitor import Monitor
from .runtime.updates_mgr import UpdatesManager
from .security import BrowserSessions, Devices, Pairing, Tickets
from .server.bus import EventBus
from .slots import Slots
from .workspaces import Workspace, all_workspaces

log = get("context")
ENUMS = {"mode": ("local", "auto", "online"), "prove_strategy": ("goedel", "agent", "auto"), "language": tuple(i18n.LANGS),
         "sage_source": ("auto", "own", "system"), "tex_engine": ("auto", "tectonic", "system"),
         "gpu_share_busy_fallback": ("cpu", "online"), "literature_depth": ("quick", "deep")}
HOST_ONLY_SETTINGS = {"lan_listener", "lan_port", "remote_jupyter", "agent_exec", "experiments_auto",
                      "experiments_remote", "updates_auto", "browser_session_idle_minutes", "calcul_warm",
                      "gpu_share_ollama", "gpu_share_busy_wait_s", "gpu_share_busy_fallback",
                      "mcp_server", "mcp_server_http", "mcp_server_sage"}
LIMITS = {"browser_session_idle_minutes": (5, 1440), "prove_attempts": (1, 64), "translate_attempts": (1, 10), "compile_timeout_s": (10, 1800),
          "agent_max_steps": (1, 200), "agent_max_seconds": (30, 7200), "lan_port": (1024, 65535),
          "tournament_contestants": (1, 6), "tournament_max_rounds": (0, 10), "tournament_max_minutes": (1, 240),
          "tournament_attempts_per_model": (1, 16), "claude_cap_proof_usd": (0, 100),
          "claude_cap_month_usd": (0, 1000), "conductor_cap_usd": (0, 100), "plan_max_depth": (1, 5),
          "plan_budget_minutes": (10, 1440), "local_idle_unload_minutes": (0, 1440), "calcul_idle_minutes": (0, 1440),
          "lean_warm_idle_minutes": (1, 240), "gpu_share_busy_wait_s": (0, 600)}


class ServerContext:
    def __init__(self, paths: Paths, *, demo: bool = False, brain=None, retriever=None, lean=None, local=None,
                 workspaces: list[Workspace] | None = None, caps: dict | None = None, legacy_dir: Path | None = None,
                 jupyter_root: Path | None = None, monitor_interval: float = 3.0, use_keyring: bool | None = None):
        self.paths = paths
        self.demo = demo
        self.legacy_dir = legacy_dir
        self.version = __version__
        self.host_name = socket.gethostname()
        self.bus = EventBus()
        from .streams import StreamStore
        self.streams = StreamStore()
        self.bus.recorder = self.streams.record
        self.slots = Slots(caps)
        self.settings = config.Settings()
        self.settings_corrupt = False
        self.repo = DossierRepo(DossierStore(paths.dossiers), self.publish)
        self.projects = ProjectRepo(ProjectStore(paths.projects), self.publish)
        self.library = Library(paths.library)
        self.history = JobHistory(paths.jobs)
        self.keys = KeyStore(paths.keys, use_keyring)
        self.devices = Devices(paths.devices)
        self.pairing = Pairing()
        self.tickets = Tickets()
        self.browser_sessions = BrowserSessions(lambda: self.settings.browser_session_idle_minutes * 60.0)
        self.browser_sessions.on_expire = self.close_credential
        self.monitor = Monitor([config.MODELS_DIR, paths.config, Path.home()], monitor_interval)
        self.monitor.listeners.append(self._system_status)
        self.monitor.wanted = self._monitor_wanted
        self._last_system: dict | None = None
        self._fixed_workspaces = workspaces
        self.workspaces: list[Workspace] = list(workspaces or [])
        if local is None:
            local = LocalLlama(self.slots, self.monitor, paths.llama_pid, lambda: self.settings)
            local.on_change = lambda: (self.publish("models.status", {"local": local.status()}), self.monitor.wake())
        self.local = local
        self.lean = lean or LeanRunner(self.slots, paths.tmp, lambda: self.settings)
        self.brain = brain
        self.retriever = retriever
        self.brain_kind = "custom" if brain is not None else ""
        self.updates = UpdatesManager(paths.config / "updates.json", self.publish, self._update_applied,
                                      lambda: bool(self.orchestrator.active()))
        from .jupyter import JupyterManager
        self.jupyter = JupyterManager(jupyter_root or (Path.home() / "Documents" / "Madalean" / "notebooks"),
                                      paths.cache / "jupyter", self.publish)
        from .orchestrator import Orchestrator
        self.orchestrator = Orchestrator(self, self.history)
        self.migration: dict = {}
        self._bg: set[asyncio.Task] = set()

    # ------------------------------------------------------------ events
    def publish(self, type_: str, payload: dict[str, Any] | None = None) -> dict:
        return self.bus.publish(type_, payload)

    def publish_job(self, job: Job) -> None:
        self.bus.publish("job.updated", {"job": job.to_dict()})

    def toast(self, key: str, level: str = "info", **params) -> None:
        self.publish("toast", {"level": level, **i18n.msg(key, **params)})

    def close_credential(self, cid: str) -> int:
        """A device / browser session was revoked or expired: close its open WebSockets with code 4401 and cancel
        the streaming it started (assistant answers). Returns the number of sockets closed."""
        socks = self.bus.sockets.pop(cid, set())
        for t in self.bus.owned.pop(cid, set()):
            if not t.done():
                t.cancel()
        for ws in socks:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                break
            loop.create_task(ws.close(code=4401, message=b"credential revoked"))
        return len(socks)

    async def _sweeper(self, every: float = 5.0) -> None:
        while True:
            await asyncio.sleep(every)
            try:
                self.browser_sessions.sweep()
            except Exception:  # noqa: BLE001
                log.exception("browser session sweep failed")

    def spawn(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)
        return t

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self.paths.ensure()
        if self.legacy_dir is not None:
            from .migrate import migrate
            try:
                self.migration = await asyncio.to_thread(migrate, self.legacy_dir, self.paths)
            except Exception:  # noqa: BLE001 (never block the start on 1.x data)
                log.exception("migration failed")
        await asyncio.to_thread(self._load_settings)
        from .brain import usage                    # S-AK: tokens of every model call (status panel)
        usage.TALLY.attach(self.paths.config / "model-usage.json")
        await self.repo.load_all()
        await self.projects.load_all()
        await asyncio.to_thread(self.library.load)
        await self.refresh_workspaces()
        if isinstance(self.local, LocalLlama):
            await self.local.refresh_models()
            self.monitor.start()
        if self.brain is None:
            self._make_brain()
        self.spawn(self._sweeper())
        if not self.demo:
            self.spawn(self.updates.maybe_check(self.settings.check_updates))

    def _make_brain(self) -> None:
        try:
            from .brain import create_brain, create_retriever  # type: ignore[attr-defined]
            self.brain = create_brain(self.paths.config, self.local, self.keys.get, asdict(self.settings))
            # MADALEAN_EMBEDDINGS=0: never ask Ollama for embeddings (test servers while its models hold the GPU)
            self.retriever = create_retriever(self.paths.cache, resolve=self.workspace,
                                              embeddings=os.environ.get("MADALEAN_EMBEDDINGS", "1") != "0")
            self.brain_kind = "real"
        except Exception as e:  # noqa: BLE001 (S-B engine absent or broken: scripted fake, clearly reported)
            from .brain.fake import FakeBrain, FakeRetriever
            log.warning("model engine unavailable (%s): using the scripted fake brain", e)
            self.brain = FakeBrain(local=self.local, online=False)
            self.retriever = FakeRetriever()
            self.brain_kind = "fake"

    async def stop(self) -> None:
        await self.orchestrator.shutdown()
        if hasattr(self.lean, "kill_all"):
            self.lean.kill_all()
        await self.updates.cancel()
        try:
            await self.jupyter.stop()
        except Exception:  # noqa: BLE001
            log.exception("jupyter stop failed")
        if isinstance(self.local, LocalLlama):
            await self.local.stop()
        await self.monitor.stop()
        from .brain import usage
        usage.TALLY.flush()
        if self.brain is not None:
            try:
                await self.brain.close()
            except Exception:  # noqa: BLE001
                pass
        for t in list(self._bg):
            t.cancel()

    # ------------------------------------------------------------ settings
    def _load_settings(self) -> None:
        data, self.settings_corrupt = config.read_json(self.paths.settings)
        self.settings = config._from_dict(config.Settings, data)
        # S-AL (D44): the choices made at install time (setup.json: Sage / TeX reuse, mode) apply once, at first start
        from .deps import assistant
        if assistant.apply_pending(self.settings, self.paths.config):
            config.atomic_write_text(self.paths.settings, json.dumps(asdict(self.settings), indent=2, ensure_ascii=False))
        config.publish_preferences(self.settings)
        i18n.set_language(self.settings.language)

    async def save_settings(self) -> None:
        text = json.dumps(asdict(self.settings), indent=2, ensure_ascii=False)
        await asyncio.to_thread(config.atomic_write_text, self.paths.settings, text)
        config.publish_preferences(self.settings)

    def settings_public(self) -> dict:
        return asdict(self.settings)

    async def patch_settings(self, patch: dict, local: bool) -> tuple[dict, list[str]]:
        """Apply a partial update. Returns (settings, errors). Host-only keys are refused from remote devices."""
        errors = []
        cur = asdict(self.settings)
        for k, v in patch.items():
            if k not in cur:
                errors.append(f"unknown:{k}")
                continue
            if k in HOST_ONLY_SETTINGS and not local:
                errors.append(f"host_only:{k}")
                continue
            if k in ENUMS and v not in ENUMS[k]:
                errors.append(f"invalid:{k}")
                continue
            if k in LIMITS and isinstance(v, (int, float)) and not isinstance(v, bool):
                lo, hi = LIMITS[k]
                if not lo <= v <= hi:
                    errors.append(f"range:{k}")
                    continue
            if isinstance(cur[k], dict) and isinstance(v, dict) and k in ("server", "sampling"):
                cur[k] = {**cur[k], **v}
            else:
                cur[k] = v
        if errors:
            return asdict(self.settings), errors
        new = config._from_dict(config.Settings, cur)
        warm_changed = new.lean_warm != self.settings.lean_warm
        self.settings = new
        if warm_changed and getattr(self.lean, "warm", None) is not None:
            self.lean.warm.reset()                  # D37: switched off -> stopped now; on -> past failures forgotten
        i18n.set_language(new.language)
        await self.save_settings()
        if self.brain is not None and hasattr(self.brain, "update_settings"):
            try:
                self.brain.update_settings(asdict(new))
            except Exception:  # noqa: BLE001
                log.exception("brain.update_settings failed")
        self.publish("settings.updated", {"settings": asdict(new)})
        return asdict(new), []

    # ------------------------------------------------------------ workspaces
    async def refresh_workspaces(self) -> None:
        if self._fixed_workspaces is not None:
            ws = self._fixed_workspaces
            for w in ws:
                await asyncio.to_thread(w.check) if not self.demo else None
        else:
            ws = await asyncio.to_thread(all_workspaces)
        self.workspaces = list(ws)
        if getattr(self.lean, "warm", None) is not None:
            self.lean.warm.forget_changed(self.workspaces)     # D37: a changed workspace never keeps its warm Lean
        if not self.settings.workspace or not self.workspace(self.settings.workspace):
            ready = [w for w in self.workspaces if not w.problems]
            pref = [w for w in ready if w.key == "lean-prover49"] or ready
            if pref:
                self.settings.workspace = pref[0].key

    def workspace(self, key: str | None = None) -> Workspace | None:
        key = key or self.settings.workspace
        return next((w for w in self.workspaces if w.key == key), None)

    def workspaces_public(self) -> list[dict]:
        return [{"key": w.key, "label": i18n._(w.label), "path": config.tilde(w.path), "toolchain": w.toolchain,
                 "readonly": w.readonly, "description": i18n._(w.description), "problems": w.problems,
                 "ready": not w.problems} for w in self.workspaces]

    # ------------------------------------------------------------ models / system
    def _update_applied(self, res: dict) -> None:
        if res.get("kind") == "model":
            if res.get("role") == "prover" and res.get("path"):
                self.settings.model_path = res["path"]
                self.spawn(self.save_settings())
            if isinstance(self.local, LocalLlama):
                loaded = self.local.model_path
                if loaded and loaded.name in (res.get("removed") or []):
                    self.spawn(self.local.stop())
                self.spawn(self.local.refresh_models())
        else:
            self.spawn(self.refresh_workspaces())

    async def models_public(self) -> dict:
        local_files = []
        if isinstance(self.local, LocalLlama):
            for m in self.local.models:
                if isinstance(m, tuple):
                    local_files.append({"file": m[0].name, "path": config.tilde(m[0]), "error": m[1]})
                else:
                    local_files.append({"file": m.path.name, "path": config.tilde(m.path), "size": m.size,
                                        "quant": m.quant, "arch": m.arch, "n_layers": m.n_layers})
        roles = {}
        for role in ("understand", "route", "formalize", "prove", "explain", "assistant"):
            try:
                cands = self.brain.candidates(role, self.settings.mode) if self.brain else []
            except Exception:  # noqa: BLE001
                cands = []
            why: dict = {}
            if self.brain is not None and hasattr(self.brain, "explain"):
                try:
                    why = {w["model"]: w for w in self.brain.explain(role, self.settings.mode)}
                except Exception:  # noqa: BLE001
                    why = {}
            roles[role] = {"preferred": (self.settings.prefer or {}).get(role, ""),
                           "candidates": [{**_ref(c), "why": (why.get(c.key) or {}).get("why", ""),
                                           "score": (why.get(c.key) or {}).get("score")} for c in cands]}
        try:
            status = await self.brain.status() if self.brain else {}
        except Exception as e:  # noqa: BLE001
            status = {"error": str(e)}
        return {"brain": self.brain_kind, "mode": self.settings.mode, "local": self.local.status()
                if hasattr(self.local, "status") else {}, "local_files": local_files, "roles": roles,
                "status": status, "keys": {p: True for p in self.keys.providers()}}

    def _monitor_wanted(self) -> bool:
        """The fast GPU / disk pace is useful only when someone looks or something uses the GPU / Lean."""
        local = getattr(self, "local", None)
        state = getattr(local, "state", None)
        return bool(getattr(self.bus, "clients", 1)) or bool(getattr(self.lean, "running", None)) or \
            (state is not None and state != getattr(local, "STOPPED", "stopped"))

    def _system_status(self, _snap: dict) -> None:
        """system.status only to an audience and only when it changed: at rest nothing enters the event ring."""
        if not getattr(self.bus, "clients", 1):
            self._last_system = None
            return
        cur = self.system_light()
        key = {k: v for k, v in cur.items() if k != "monitor"} | {"m": {k: v for k, v in cur["monitor"].items()
                                                                     if k != "t"}}
        if key == self._last_system:
            return
        self._last_system = key
        self.publish("system.status", {"system": cur})

    def system_light(self) -> dict:
        return {"monitor": self.monitor.snapshot(), "slots": self.slots.usage(),
                "lean_running": len(getattr(self.lean, "running", {}) or {})}


def _ref(m: ModelRef) -> dict:
    return {"key": m.key, "provider": m.provider, "model_id": m.model_id, "name": m.name, "local": m.local,
            "paid": m.paid}


def env_flag(name: str) -> bool:
    return os.environ.get(name, "") not in ("", "0", "false")
