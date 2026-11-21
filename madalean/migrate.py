"""First start: COPY (never move, never modify) the 1.x data from ~/.config/lean-ai-station.

Copied: a subset of the settings (only when Madalean has no settings yet), every dossier (placed in a project
« Lean AI Station 1.x », existing Madalean dossiers are never overwritten) and the library (only when Madalean has
none). A marker file records what was done, so the copy happens once."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import config
from .dossiers import Dossier
from .logs import get
from .paths import Paths
from .projects import ProjectStore

log = get("migrate")
SETTINGS_KEYS = ("language", "profile", "workspace", "model_path", "prove_attempts", "translate_attempts",
                 "pause_after_translation", "check_updates", "compile_timeout_s", "overleaf_url", "autoload_model",
                 "server", "sampling", "wizard_done")


def migrate(legacy: Path, paths: Paths) -> dict:
    report = {"t": time.time(), "from": str(legacy), "settings": False, "dossiers": 0, "library": False, "project": ""}
    if paths.migrated_marker.exists():
        return {"skipped": "already"}
    if not legacy.is_dir():
        config.atomic_write_text(paths.migrated_marker, json.dumps({"skipped": "no 1.x data", "t": time.time()}))
        return {"skipped": "none"}
    # settings
    old, _corrupt = _read(legacy / "settings.json")
    if old and not paths.settings.exists():
        new = {k: old[k] for k in SETTINGS_KEYS if k in old}
        new["mode"] = "local" if old.get("offline", True) else "auto"
        config.atomic_write_text(paths.settings, json.dumps(new, indent=2, ensure_ascii=False))
        report["settings"] = True
    # dossiers → project « Lean AI Station 1.x »
    src = legacy / "dossiers"
    files = sorted(src.glob("*.json")) if src.is_dir() else []
    if files:
        store = ProjectStore(paths.projects)
        p = store.new("Lean AI Station 1.x", "Dossiers copiés depuis Lean AI Station 1.x")
        n = 0
        for f in files:
            dst = paths.dossiers / f.name
            if dst.exists():
                continue
            data, corrupt = _read(f)
            if corrupt or not data:
                continue
            try:
                d = Dossier.from_dict(data)
            except (TypeError, ValueError):
                log.warning("unreadable 1.x dossier skipped: %s", f.name)
                continue
            d.project_id = p.id
            config.atomic_write_text(dst, d.to_json())
            n += 1
        if n:
            store.save(p)
            report["project"] = p.id
        report["dossiers"] = n
    # library
    lib = legacy / "library.json"
    if lib.exists() and not paths.library.exists():
        paths.library.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lib, paths.library)
        report["library"] = True
    config.atomic_write_text(paths.migrated_marker, json.dumps(report, indent=1))
    log.info("1.x data copied: %s", report)
    return report


def _read(f: Path) -> tuple[dict, bool]:
    """Read without ever renaming the source (unlike config.read_json, which moves corrupt files aside)."""
    try:
        return json.loads(f.read_text(encoding="utf-8")), False
    except FileNotFoundError:
        return {}, False
    except (OSError, ValueError):
        return {}, True
