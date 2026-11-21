"""Health of the prefix: one line per component (version, where it lives, ok, repair action) and the system
programs Madalean still relies on (always flagged)."""
from __future__ import annotations

import os
from pathlib import Path

from . import SYSTEM_ALLOWED, home, installed, manifest, tool_info
from .installer import load_state

# component -> the tool whose presence proves it is usable
PROBE = {"micromamba": "micromamba", "env": "python", "sage": "sage", "elan": "elan", "llama.cpp": "llama-server",
         "madalean-net": "madalean-net", "tex-bundle": "tectonic", "fonts": ""}


def _dir_size(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def components(sizes: bool = False) -> list[dict]:
    st = load_state()
    out = []
    dev = not installed()
    for name, c in manifest.components().items():
        e = st.get(name) or {}
        probe = PROBE.get(name, "")
        ti = tool_info(probe) if probe else {"path": e.get("path"), "source": "prefix" if e else ""}
        present = bool(e) and Path(e.get("path", "/nonexistent")).exists()
        if name == "tex-bundle":
            present = present and (home() / "tectonic" / "files").is_dir()
        ok = present and (not probe or ti["source"] == "prefix")
        state = "ok" if ok else ("on_demand" if c.get("need") == "on-demand" and not present else
                                 "dev" if dev and ti.get("path") else "missing")
        if ok and e.get("version") != c.get("version"):
            state = "outdated"                     # a new pin arrived with a Madalean update: install it
        item = {"component": name, "title": c.get("title", name), "need": c.get("need", "required"),
                "version": e.get("version", ""), "pinned": c.get("version", ""), "variant": e.get("variant", ""),
                "path": e.get("path") or ti.get("path") or "", "source": ti.get("source", ""),
                "ok": state in ("ok", "on_demand", "dev"), "state": state, "license": c.get("license", ""),
                "repair": "" if state in ("ok",) else f"dep_{name}"}
        if sizes and present:
            item["bytes"] = _dir_size(Path(e["path"]))
        out.append(item)
    return out


def system_tools() -> list[dict]:
    out = []
    for name, why in SYSTEM_ALLOWED.items():
        ti = tool_info(name)
        if ti["path"]:
            out.append({"tool": name, "path": ti["path"], "source": "system", "why": why})
    return out


def report(sizes: bool = False) -> dict:
    return {"home": str(home()), "installed": installed(), "components": components(sizes),
            "system": system_tools()}
