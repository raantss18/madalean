"""Updates manager (port of 1.1.4 `ui/updates_ui.UpdateManager`): weekly check at start, one install at a time
through `scripts/updater.py` (verify, switch, then delete the old version), progress published as events."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Callable

from .. import config, deps, updates
from ..i18n import _, msg
from ..logs import get
from . import guarded

log = get("updates")

STEPS = {
    "toolchain": "Installation de la nouvelle version de Lean…",
    "deps": "Téléchargement de Mathlib…",
    "cache": "Téléchargement des fichiers compilés de Mathlib (plusieurs Go)…",
    "build": "Finalisation de Mathlib…",
    "verify": "Vérification avec un théorème test…",
    "download": "Téléchargement du modèle…",
    "smoke": "Test du nouveau modèle (chargement et réponse)…",
    "switch": "Bascule vers la nouvelle version…",
    "cleanup": "Suppression de l'ancienne version…",
}
ROLE = {"prover": "prouveur", "formalizer": "traducteur"}


def describe(c: updates.Candidate) -> str:
    gb = f"{c.size / 1e9:.1f}"
    if c.kind == "mathlib":
        return _("Lean + Mathlib {new} (installé : {cur}). Environ 8 Go, 10 à 60 minutes.").format(new=c.latest,
                                                                                                    cur=c.current)
    if c.note == "gguf_pending":
        return _("{name} est publié, mais pas encore au format utilisable ici (GGUF). L'outil revérifiera la semaine "
                 "prochaine.").format(name=c.title)
    if c.note == "revision":
        return _("{name} : fichier republié par son auteur (correctifs), {gb} Go.").format(name=c.title, gb=gb)
    if c.kind != "model":
        return f"{c.title}: {c.current} → {c.latest}" + (f" — {c.note}" if c.note else "")
    return _("{name} : nouvelle version du {role} ({cur} → {new}), {gb} Go.").format(
        name=c.title, role=_(ROLE.get(c.key, c.key)), cur=c.current, new=c.latest, gb=gb)


LEAN_KINDS = ("mathlib", "toolchain", "lake-package")


def prefix_elan_ok() -> bool:
    """D29: Lean installs only into the prefix's ELAN_HOME, never ~/.elan (the user's own toolchains)."""
    try:
        eh = config.ELAN_HOME.resolve()
        return (eh != (Path.home() / ".elan").resolve() and eh == deps.elan_home().resolve()
                and (deps.elan_home() / "bin" / "elan").exists())
    except OSError:
        return False


def auto_install_blocked(config_dir: Path) -> str | None:
    """D29 (incident 2026-11-21): reason why AUTOMATIC installs are off for this server, None when allowed.
    Allowed only for an installed Madalean (code under MADALEAN_HOME, i.e. <prefix>/versions/<v>), with the default
    config directory, and with the prefix's own elan. A dev checkout, a test server with --config-dir/--demo,
    or a machine without the prefix elan only notifies."""
    try:
        if deps.home().resolve() not in config.STATION_DIR.resolve().parents:
            return "dev_checkout"
        if Path(config_dir).resolve() != (Path.home() / ".config" / "madalean").resolve():
            return "custom_config_dir"
    except OSError:
        return "unknown_layout"
    if not prefix_elan_ok():
        return "no_prefix_elan"
    return None


class UpdatesManager:
    def __init__(self, state_file: Path, publish: Callable[[str, dict], None], on_applied: Callable[[dict], None],
                 is_busy: Callable[[], bool], updater: Path | None = None):
        self.state_file = state_file
        self.publish = publish
        self.on_applied = on_applied
        self.is_busy = is_busy
        self.updater = updater or (config.STATION_DIR / "scripts" / "updater.py")
        self.state = updates.load_state(state_file)
        self.checking = False
        self.proc: asyncio.subprocess.Process | None = None
        self.current: updates.Candidate | None = None
        self.step = ""
        self.progress = ""
        self.output: list[str] = []
        self.last_result: dict | None = None

    @property
    def candidates(self) -> list[updates.Candidate]:
        return updates.candidates_from(self.state)

    @property
    def busy(self) -> bool:
        return self.checking or self.proc is not None

    def status(self) -> dict:
        return {"checking": self.checking, "t": self.state.get("t"), "errors": self.state.get("errors") or [],
                "installed": {"mathlib": updates.installed_mathlib(),
                              "models": {k: v.get("version") for k, v in updates.installed_models().items()}},
                "candidates": [{**c.__dict__, "description": describe(c)} for c in self.candidates],
                "install": None if self.current is None else {
                    "key": self.current.key, "title": self.current.title, "step": self.step,
                    "step_text": _(STEPS.get(self.step, "Préparation…")), "progress": self.progress},
                "last_result": self.last_result, "tracked": self._tracked()}

    def _tracked(self) -> dict | None:
        """S-V: Lean, Mathlib, Sage, LaTeX at a glance (current / latest / last and next check)."""
        try:
            from ..update_checkers.overview import overview
            return overview(self.state, self.candidates)
        except Exception:  # noqa: BLE001 (a status must always answer)
            log.exception("updates overview failed")
            return None

    def _changed(self) -> None:
        self.publish("updates.status", {"updates": self.status()})

    async def maybe_check(self, enabled: bool) -> None:
        if enabled and updates.due(self.state) and os.environ.get("MADALEAN_NO_UPDATE_CHECK") != "1":
            await self.check(manual=False)

    async def check(self, manual: bool = True) -> dict:
        if self.busy:
            return self.status()
        self.checking = True
        self._changed()
        try:
            st = await asyncio.to_thread(updates.check_all, self.state_file)
        except Exception as e:  # noqa: BLE001
            st = {"t": 0, "candidates": [], "errors": [str(e)]}
        self.checking = False
        notified = set(self.state.get("notified", []))
        self.state = st if st.get("t") else {**self.state, "errors": st.get("errors", [])}
        fresh = [c for c in self.candidates if c.installable and f"{c.key}:{c.latest}" not in notified]
        self.state["notified"] = sorted(notified | {f"{c.key}:{c.latest}" for c in self.candidates})
        try:
            await asyncio.to_thread(updates.save_state, self.state, self.state_file)
        except OSError:
            pass
        if fresh:
            self.publish("toast", {"level": "info", **msg("Mise à jour disponible : {names}.",
                                                           names=", ".join(c.title for c in fresh))})
        elif manual:
            errs = self.state.get("errors") or []
            key = ("Vérification impossible (pas d'Internet ?)." if errs and not st.get("t")
                   else "Tout est à jour." if not self.candidates else "Pas de nouvelle mise à jour installable.")
            self.publish("toast", {"level": "info", **msg(key)})
        self._changed()
        return self.status()

    async def install(self, key: str) -> str | None:
        """Start the install of candidate `key`. Returns an error key, or None when started."""
        c = next((c for c in self.candidates if c.key == key), None)
        if c is None or not c.installable:
            return "unknown"
        if self.busy:
            return "busy"
        if self.is_busy():
            return "jobs_running"
        if c.kind in LEAN_KINDS and not prefix_elan_ok():
            return "no_prefix_elan"                    # D29: never install into ~/.elan (notify only)
        self.current, self.step, self.progress, self.output = c, "", "", []
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        if c.kind in LEAN_KINDS:
            env["ELAN_HOME"] = str(config.ELAN_HOME)  # explicit: elan/lake never fall back to ~/.elan
        self.proc = await asyncio.create_subprocess_exec(*guarded(sys.executable, [str(self.updater), *c.args()]),
                                                         stdout=asyncio.subprocess.PIPE,
                                                         stderr=asyncio.subprocess.STDOUT, env=env)
        asyncio.create_task(self._follow(self.proc, c))
        self._changed()
        return None

    async def cancel(self) -> bool:
        if self.proc is None:
            return False
        try:
            self.proc.kill()          # the updater only switches after verification: the old version stays
        except ProcessLookupError:
            pass
        return True

    async def _follow(self, proc: asyncio.subprocess.Process, c: updates.Candidate) -> None:
        assert proc.stdout is not None
        while True:
            b = await proc.stdout.readline()
            if not b:
                break
            line = b.decode("utf-8", "replace").rstrip()
            self.output.append(line)
            self.output = self.output[-400:]
            if line.startswith("STEP "):
                self.step, self.progress = line.split()[1], ""
                self._changed()
            elif "segments" in line and "GB" in line:
                self.progress = line.split("segments", 1)[1].strip()
                self._changed()
        code = await proc.wait()
        self.proc, self.current = None, None
        done = next((ln[5:] for ln in self.output if ln.startswith("DONE ")), None)
        fail = next((ln for ln in self.output if ln.startswith("FAIL ")), None)
        if done:
            try:
                res = json.loads(done)
            except ValueError:
                res = {}
            self.state["candidates"] = [d for d in self.state.get("candidates", []) if d.get("key") != c.key]
            await asyncio.to_thread(updates.save_state, self.state, self.state_file)
            removed = ", ".join(res.get("removed") or []) or "—"
            self.last_result = {"ok": True, **msg("{name} est installé et vérifié. Supprimé : {removed}.",
                                                   name=c.title, removed=removed)}
            try:
                self.on_applied(res)
            except Exception:  # noqa: BLE001
                log.exception("apply update failed")
        else:
            k = fail.split()[1] if fail else ("cancelled" if code != 0 else "error")
            if k == "disk":
                m = msg("Pas assez d'espace disque. L'ancienne version est conservée.")
            elif fail is None and code != 0:
                m = msg("Mise à jour annulée. L'ancienne version est conservée.")
            else:
                m = msg("La mise à jour a échoué à l'étape « {step} ». L'ancienne version est conservée.",
                        step=_(STEPS.get(self.step, self.step or "?")).rstrip("…"))
            self.last_result = {"ok": False, **m, "details": "\n".join(self.output[-40:])}
        self.step = self.progress = ""
        self.publish("toast", {"level": "ok" if done else "warn", "key": self.last_result["key"],
                               "params": self.last_result["params"], "text": self.last_result["text"]})
        self._changed()
