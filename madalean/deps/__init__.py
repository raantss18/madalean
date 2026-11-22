"""Madalean's own dependencies, all inside one prefix (ARCHITECTURE §18) — session S-I.

`MADALEAN_HOME` (default `~/.local/share/madalean`) holds everything Madalean runs:

    env -> envs/main-<lock hash>/   micromamba env from locks/main.conda-lock.yml (python, aiohttp, jupyterlab,
                                    ipykernel, poppler, tesseract, tectonic, fontconfig, git, fonts…)
    envs/sage -> envs/sage-<hash>/  on-demand SageMath env (locks/sage.conda-lock.yml)
    components/<name>/<version>/    micromamba, elan (installer), llama.cpp (+ CUDA runtime), madalean-net, fonts
    components/<name>/current       symlink = the active version (atomic switch, previous kept for rollback)
    elan/                           ELAN_HOME (toolchains of the managed workspaces; ~/.elan is never touched)
    workspaces/                     managed Lean workspaces (lean-current, lean-prover49)
    tectonic/                       TECTONIC_CACHE_DIR (pinned bundle, offline after install) + extracted font files
    fonts/, fontconfig/fonts.conf   extra fonts (Noto Sans Math) and the fontconfig file that adds them
    tailscale/                      state of the embedded Tailscale node (madalean-net)
    versions/<v>/, current          Madalean itself (layout shared with the self-update, update_checkers/selfupdate)
    downloads/                      verified downloads (resume, export_offline.sh)
    deps-state.json                 installed version + previous version of each component

**The rule for every other module: locate an external program with `madalean.deps.tool(name)`** (never a bare
`/usr/bin/...` nor `shutil.which` for a managed tool). It returns an absolute path or None:
- inside the prefix first;
- a system program only for the names listed in `SYSTEM_ALLOWED` (driver tools, util-linux, the keyring, an
  existing system TeX as export fallback) — `tool_info(name)["source"] == "system"` and the health page flags it;
- in a development checkout with no installed prefix env ("dev mode"), PATH is used for everything (flagged
  `system-dev`), so the code and tests keep working without an install.
`activate()` (called once at server start) puts the prefix's bin directories first in PATH and sets ELAN_HOME,
TECTONIC_CACHE_DIR and FONTCONFIG_FILE, so children (and code that still calls shutil.which) see the prefix first.

This module imports nothing from the rest of Madalean (config imports it)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ENV_VAR = "MADALEAN_HOME"
PKG_DIR = Path(__file__).resolve().parent
MANIFEST = PKG_DIR / "manifest.toml"
LOCKS = PKG_DIR / "locks"


def home() -> Path:
    v = os.environ.get(ENV_VAR, "").strip()
    return Path(v).expanduser() if v else Path.home() / ".local" / "share" / "madalean"


def env_dir() -> Path:
    return home() / "env"


def sage_env_dir() -> Path:
    return home() / "envs" / "sage"


def component_dir(name: str) -> Path:
    return home() / "components" / name / "current"


def elan_home() -> Path:
    return home() / "elan"


def workspaces_dir() -> Path:
    return home() / "workspaces"


def tectonic_cache() -> Path:
    return home() / "tectonic"


def tex_files_dir() -> Path:
    """Files extracted from the pinned TeX bundle (fonts read by the export to know glyph coverage)."""
    return tectonic_cache() / "files"


def fontconfig_file() -> Path:
    return home() / "fontconfig" / "fonts.conf"


def tailscale_dir() -> Path:
    return home() / "tailscale"


def downloads_dir() -> Path:
    return home() / "downloads"


def state_file() -> Path:
    return home() / "deps-state.json"


def installed() -> bool:
    """True when the main env of the prefix exists (otherwise: development checkout, PATH lookups allowed)."""
    return (env_dir() / "bin" / "python").exists()


# ---------------------------------------------------------------- tool table
# name -> (component, candidate paths relative to MADALEAN_HOME)
TOOLS: dict[str, tuple[str, tuple[str, ...]]] = {
    "python": ("env", ("env/bin/python3",)),
    "python3": ("env", ("env/bin/python3",)),
    "jupyter-lab": ("env", ("env/bin/jupyter-lab",)),
    "jupyter": ("env", ("env/bin/jupyter",)),
    "pdftotext": ("env", ("env/bin/pdftotext",)),
    "pdfinfo": ("env", ("env/bin/pdfinfo",)),
    "pdftoppm": ("env", ("env/bin/pdftoppm",)),
    "tesseract": ("env", ("env/bin/tesseract",)),
    "tectonic": ("env", ("env/bin/tectonic",)),
    "fc-match": ("env", ("env/bin/fc-match",)),
    "fc-list": ("env", ("env/bin/fc-list",)),
    "fc-query": ("env", ("env/bin/fc-query",)),
    "git": ("env", ("env/bin/git",)),
    "micromamba": ("micromamba", ("components/micromamba/current/micromamba",)),
    "elan": ("elan", ("elan/bin/elan",)),
    "lake": ("elan", ("elan/bin/lake",)),
    "lean": ("elan", ("elan/bin/lean",)),
    "llama-server": ("llama.cpp", ("components/llama.cpp/current/llama-server",
                                   "components/llama.cpp/current/bin/llama-server")),
    "madalean-net": ("madalean-net", ("components/madalean-net/current/madalean-net",)),
    "sage": ("sage", ("envs/sage/bin/sage",)),
    "sage-python": ("sage", ("envs/sage/bin/python3",)),
}
# System programs that §18 allows (not part of the prefix); always flagged as `system` in health.
SYSTEM_ALLOWED = {
    "nvidia-smi": "NVIDIA driver",
    "setpriv": "util-linux (PR_SET_PDEATHSIG for children; a Python fallback exists)",
    "bwrap": "bubblewrap sandbox for experiments (optional)",
    "secret-tool": "system keyring (optional; else keys.json 0600)",
    "systemctl": "systemd user unit",
    "systemd-run": "systemd",
    "xdg-open": "desktop integration",
    "xelatex": "system TeX, export fallback only (§18)",
    "lualatex": "system TeX, export fallback only (§18)",
    "latexmk": "system TeX, export fallback only (§18)",
    "kpsewhich": "system TeX, export fallback only (§18)",
    "bibtex": "system TeX, export fallback only (§18)",
    "biber": "system TeX, export fallback only (§18)",
}
# legacy fallbacks of a development checkout (not used once the prefix is installed)
_DEV_EXTRA = {"elan": [Path.home() / ".elan" / "bin" / "elan"], "lake": [Path.home() / ".elan" / "bin" / "lake"],
              "lean": [Path.home() / ".elan" / "bin" / "lean"]}


def tool_info(name: str) -> dict:
    """{"name", "path" (str|None), "source": prefix|system|system-dev|"", "component"}."""
    comp, rels = TOOLS.get(name, ("", ()))
    h = home()
    for rel in rels:
        p = h / rel
        if p.exists() and os.access(p, os.X_OK):
            return {"name": name, "path": str(p), "source": "prefix", "component": comp}
    if name in SYSTEM_ALLOWED:
        p = shutil.which(name, path=_system_path())
        return {"name": name, "path": p, "source": "system" if p else "", "component": ""}
    if name in TOOLS and installed():
        return {"name": name, "path": None, "source": "", "component": comp}     # managed: never the system's
    # development checkout (no prefix env): PATH, then legacy locations
    p = shutil.which(name, path=_system_path())
    if not p:
        for c in _DEV_EXTRA.get(name, []):
            if c.exists():
                p = str(c)
                break
    if not p and name in ("python", "python3"):
        p = sys.executable
    return {"name": name, "path": p, "source": "system-dev" if p else "", "component": comp}


def tool(name: str) -> str | None:
    """Absolute path of an external program Madalean uses, or None (see module docstring for the rule)."""
    return tool_info(name)["path"]


def _system_path() -> str:
    """PATH without the prefix's own directories (so a system lookup never returns a prefix file twice)."""
    h = str(home())
    return os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                           if p and not p.startswith(h + os.sep))


def bin_dirs() -> list[Path]:
    h = home()
    return [d for d in (h / "env" / "bin", h / "elan" / "bin", h / "components" / "llama.cpp" / "current",
                        h / "components" / "madalean-net" / "current") if d.is_dir()]


def activate(environ: dict | None = None) -> dict:
    """Prefix first in PATH (+ ELAN_HOME, TECTONIC_CACHE_DIR, FONTCONFIG_FILE). No-op without an installed prefix.
    Returns the variables that were set."""
    env = os.environ if environ is None else environ
    if not installed():
        return {}
    dirs = [str(d) for d in bin_dirs()]
    rest = [p for p in env.get("PATH", "").split(os.pathsep) if p and p not in dirs]
    changes = {"PATH": os.pathsep.join(dirs + rest), "ELAN_HOME": str(elan_home()),
               "TECTONIC_CACHE_DIR": str(tectonic_cache())}
    if fontconfig_file().exists():
        changes["FONTCONFIG_FILE"] = str(fontconfig_file())
    env.update(changes)
    return changes


# ---------------------------------------------------------------- tool preferences (S-AL, D44)
# Which copy of a tool the user prefers when both exist (Settings.sage_source / tex_engine, chosen at install time in
# setup.json and applied at first start). Published by config.publish_preferences whenever settings load or change.
PREFERENCES = {"sage_source": ("auto", "own", "system"), "tex_engine": ("auto", "tectonic", "system")}
_PREFS: dict[str, str] = {}


def set_preferences(**kw: str) -> None:
    for k, v in kw.items():
        if k in PREFERENCES and v in PREFERENCES[k]:
            _PREFS[k] = v


def preference(name: str) -> str:
    return _PREFS.get(name, "auto")


def llama_bin_dir() -> Path | None:
    p = tool("llama-server")
    return Path(p).parent if p and tool_info("llama-server")["source"] == "prefix" else None
