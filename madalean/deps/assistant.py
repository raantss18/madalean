"""Install assistant engine (session S-AL, DECISIONS D44): machine check, recommended plan, setup state.

ONE engine, several front-ends: the terminal assistant of install.sh (`python3 -m madalean.deps.assistant …`), the
graphical installer of the `.run` (packaging/installer/server.py) and, later, the in-app first-run wizard (through
`GET /api/setup`). It runs BEFORE Madalean's own environment exists, under whatever `python3` (≥ 3.8) the system
has, so it uses the standard library only and imports nothing from Madalean except `madalean.deps` (stdlib too).

Nothing here installs anything, runs sudo or a package manager: detection runs read-only commands (`--version`,
`nvidia-smi --query-gpu`, `kpsewhich`) with short timeouts; when a system package would help, the plan carries the
exact command for the user to run.

    detect()                    -> machine + existing tools (hardware, SageMath, TeX, Python, elan, Ollama, Tailscale…)
    recommend(det)              -> {"plan", "items", "advice", "disk"}: recommended choice per item, and why (FR/EN)
    DEFAULT_PLAN                -> what `install.sh --yes` installs (unchanged 2.0.0 behaviour)
    shell_vars(plan)            -> KEY=value lines read by install.sh (validated: no eval)
    record(config_dir, …)       -> <config>/setup.json (schema madalean-setup/1)
    apply_pending(settings, …)  -> first start: copy the install choices (sage_source, tex_engine, mode) into settings

CLI (used by install.sh): detect [--json] | plan --out F [--defaults|--interactive] [--set k=v]… | show F |
vars F | record --config-dir D --plan F --rc N [--source S]"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "madalean-setup/1"
GIB = 1024 ** 3
MIB = 1024 ** 2

# ---------------------------------------------------------------- the plan
# item -> allowed values. Defaults = 2.0.0 behaviour of `install.sh` without options (never change them silently:
# automation and tests rely on them).
CHOICES = {
    "models": ("all", "prover", "none"),        # GGUF models in ~/models (prover ≈ 5 GB; all three ≈ 15 GB)
    "variant": ("auto", "cpu"),                 # llama.cpp build: CUDA when the driver supports it, else CPU
    "sage": ("later", "now", "system"),         # own SageMath on first use / own SageMath now / reuse the system's
    "tex": ("own", "system"),                   # tectonic + pinned bundle first / an existing TeX Live first
    "workspace": ("import", "build", "skip"),   # import built Lean workspaces / build lean-current (≈ 5 GB) / none
    "mode": ("auto", "online", "local"),        # Settings.mode at first start
}
DEFAULT_PLAN = {"models": "all", "variant": "auto", "sage": "later", "tex": "own", "workspace": "import",
                "mode": "auto"}
MODEL_FILES = {"Q4_K_M": "Goedel-Prover-V2-8B.Q4_K_M.gguf", "formalizer": "Goedel-Formalizer-V2-8B.Q4_K_M.gguf",
               "explainer": "Qwen3-8B-Q4_K_M.gguf"}
MODEL_SETS = {"all": ("Q4_K_M", "formalizer", "explainer"), "prover": ("Q4_K_M",), "none": ()}
MODEL_BYTES = 5 * 10 ** 9                       # each Q4_K_M 8B model ≈ 5.0 GB
# sizes on disk used for the disk estimate (manifest.toml installed sizes, rounded up)
BASE_BYTES = 6 * 10 ** 9                        # code, main env 1.3 GB, llama.cpp CUDA ≈ 0.7 GB, bundle, fonts, elan…
SAGE_BYTES = 5 * 10 ** 9 + 1_500_000_000        # SageMath env on disk + the download kept for resume
WORKSPACE_BYTES = 5 * 10 ** 9
MIN_SAGE = (10, 0)
MIN_TEXLIVE = 2022
MIN_VRAM_PROVER_MIB = 7800                      # Goedel 8B Q4_K_M + 24k context, q8_0 KV ≈ 7.0 GiB (config.py)
MIN_VRAM_ALL_MIB = 10000
MIN_RAM_ALL = 15 * GIB                          # "16 GB" machines report ~15.5 GiB
KERNEL_DIRS = ["/usr/local/share/jupyter/kernels", "/usr/share/jupyter/kernels",
               os.path.expanduser("~/.local/share/jupyter/kernels")]

T = {   # (fr, en)
    "models": ("Modèles d'IA locaux", "Local AI models"),
    "variant": ("Moteur des modèles locaux (llama.cpp)", "Local model engine (llama.cpp)"),
    "sage": ("SageMath (calcul)", "SageMath (computations)"),
    "tex": ("LaTeX (export PDF, articles)", "LaTeX (PDF export, articles)"),
    "workspace": ("Espace Lean + Mathlib", "Lean + Mathlib workspace"),
    "mode": ("Où travaillent les modèles", "Where the models run"),
    "models.all": ("Les trois modèles (preuve, traduction, explications) ≈ 15 Go",
                   "All three models (proof, translation, explanations) ≈ 15 GB"),
    "models.prover": ("Le modèle de preuve seul ≈ 5 Go", "The prover model only ≈ 5 GB"),
    "models.none": ("Aucun modèle local (modèles en ligne)", "No local model (online models)"),
    "variant.auto": ("Carte graphique NVIDIA si possible (CUDA)", "NVIDIA graphics card when possible (CUDA)"),
    "variant.cpu": ("Processeur seulement (léger, 23 Mo)", "Processor only (light, 23 MB)"),
    "sage.later": ("Copie de Madalean, installée au premier calcul (≈ 1,5 Go à télécharger, 5 Go)",
                   "Madalean's own copy, installed on first use (≈ 1.5 GB download, 5 GB)"),
    "sage.now": ("Copie de Madalean, installée maintenant (≈ 1,5 Go à télécharger, 5 Go)",
                 "Madalean's own copy, installed now (≈ 1.5 GB download, 5 GB)"),
    "sage.system": ("Réutiliser le SageMath déjà installé", "Reuse the SageMath already installed"),
    "tex.own": ("tectonic de Madalean (épinglé, hors ligne)", "Madalean's tectonic (pinned, offline)"),
    "tex.system": ("Réutiliser le TeX Live déjà installé en premier", "Use the TeX Live already installed first"),
    "workspace.import": ("Reprendre les espaces déjà construits (sinon : plus tard)",
                         "Import already built workspaces (else: later)"),
    "workspace.build": ("Construire lean-current maintenant (≈ 5 Go, réseau)", "Build lean-current now (≈ 5 GB, network)"),
    "workspace.skip": ("Pas d'espace Lean pour l'instant", "No Lean workspace for now"),
    "mode.auto": ("Automatique : en ligne d'abord, local si pas de réseau",
                  "Automatic: online first, local when there is no network"),
    "mode.online": ("En ligne seulement", "Online only"),
    "mode.local": ("Local seulement (hors connexion)", "Local only (offline)"),
}


def tr(key: str, lang: str) -> str:
    v = T.get(key)
    return (v[0] if lang == "fr" else v[1]) if v else key


def lang_default() -> str:
    for k in ("MADALEAN_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(k, "")
        if v:
            return "fr" if v.lower().startswith("fr") else "en"
    return "fr"


# ---------------------------------------------------------------- parsers (pure, tested)
def parse_meminfo(text: str) -> int:
    m = re.search(r"^MemTotal:\s+(\d+)\s*kB", text or "", re.M)
    return int(m.group(1)) * 1024 if m else 0


def parse_cpuinfo(text: str) -> dict:
    model = re.search(r"^model name\s*:\s*(.+)$", text or "", re.M)
    cores = len(re.findall(r"^processor\s*:", text or "", re.M))
    return {"model": model.group(1).strip() if model else "", "threads": cores or (os.cpu_count() or 0)}


def parse_nvidia_smi(text: str) -> list[dict]:
    """`nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits`."""
    out = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[1].isdigit():
            out.append({"name": parts[0], "vram_mib": int(parts[1]), "driver": parts[2]})
    return out


def parse_cuda(text: str) -> str:
    m = re.search(r"CUDA Version\s*:?\s*(\d+\.\d+)", text or "")
    return m.group(1) if m else ""


def parse_version(text: str, pattern: str = r"(\d+\.\d+(?:\.\d+)?)") -> str:
    m = re.search(pattern, text or "")
    return m.group(1) if m else ""


def parse_sage_version(text: str) -> str:
    return parse_version(text, r"SageMath version (\d+\.\d+(?:\.\w+)?)") or parse_version(text)


def parse_texlive_year(text: str) -> int:
    m = re.search(r"TeX Live (\d{4})", text or "")
    return int(m.group(1)) if m else 0


def parse_elan_toolchains(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip().replace(" (default)", "").replace(" (resolved from default 'stable')", "")
        if re.match(r"^[\w.-]+/[\w.-]+:[\w.-]+$", line) or re.match(r"^leanprover[\w/.:-]+$", line):
            out.append(line)
    return out


def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


# ---------------------------------------------------------------- detection
def _run(argv: list[str], timeout: float = 20) -> str:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           env={**os.environ, "LC_ALL": "C"})
        return (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def os_release(text: str | None = None) -> dict[str, str]:
    text = _read("/etc/os-release") if text is None else text
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def distro_family(osr: dict[str, str] | None = None) -> str:
    osr = osr if osr is not None else os_release()
    ids = {osr.get("ID", "")} | set(osr.get("ID_LIKE", "").split())
    if ids & {"arch", "endeavouros", "manjaro", "cachyos", "garuda"}:
        return "arch"
    if ids & {"debian", "ubuntu", "linuxmint", "pop"}:
        return "debian"
    if ids & {"fedora", "rhel", "centos"}:
        return "fedora"
    if ids & {"opensuse", "suse", "opensuse-tumbleweed", "opensuse-leap"}:
        return "suse"
    return "unknown"


PKG = {   # system package names (shown, never installed by Madalean)
    "bubblewrap": {"arch": "bubblewrap", "debian": "bubblewrap", "fedora": "bubblewrap", "suse": "bubblewrap"},
}


def install_command(what: str, family: str) -> str:
    pkg = PKG.get(what, {}).get(family, "")
    if not pkg:
        return ""
    return {"arch": f"sudo pacman -S --needed {pkg}", "debian": f"sudo apt install {pkg}",
            "fedora": f"sudo dnf install {pkg}", "suse": f"sudo zypper install {pkg}"}[family]


def _existing_parent(p: Path) -> Path:
    p = p.expanduser()
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def find_kernelspec(name: str, dirs: list[str] | None = None) -> str:
    for d in dirs if dirs is not None else KERNEL_DIRS:
        f = Path(d) / name / "kernel.json"
        if f.is_file():
            return str(f)
    return ""


def detect(prefix: str | None = None, home: str | None = None, which=shutil.which, run=_run, read=_read,
           kernel_dirs: list[str] | None = None) -> dict:
    """What this machine has. Never raises; every probe is bounded (≤ 20 s, `sage --version` ≤ 60 s)."""
    home_p = Path(home or os.path.expanduser("~"))
    prefix_p = Path(prefix or os.environ.get("MADALEAN_HOME") or home_p / ".local" / "share" / "madalean")
    if kernel_dirs is None and os.environ.get("MADALEAN_SETUP_KERNEL_DIRS"):
        kernel_dirs = os.environ["MADALEAN_SETUP_KERNEL_DIRS"].split(os.pathsep)
    osr = os_release(read("/etc/os-release"))
    det: dict = {"schema": SCHEMA, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                 "os": {"name": osr.get("PRETTY_NAME", platform.system()), "family": distro_family(osr),
                        "arch": platform.machine(), "kernel": platform.release(),
                        "supported": platform.system() == "Linux" and platform.machine() == "x86_64"}}
    try:
        du = shutil.disk_usage(_existing_parent(prefix_p))
        disk = {"path": str(prefix_p), "free_bytes": du.free, "total_bytes": du.total}
    except OSError:
        disk = {"path": str(prefix_p), "free_bytes": 0, "total_bytes": 0}
    gpus, cuda = [], ""
    smi = which("nvidia-smi")
    if smi:
        gpus = parse_nvidia_smi(run([smi, "--query-gpu=name,memory.total,driver_version",
                                     "--format=csv,noheader,nounits"]))
        cuda = parse_cuda(run([smi]))
    det["hardware"] = {"cpu": parse_cpuinfo(read("/proc/cpuinfo")), "ram_bytes": parse_meminfo(read("/proc/meminfo")),
                       "disk": disk, "gpus": gpus, "cuda": cuda}
    tools: dict = {}
    # SageMath: version + its Jupyter kernel (Madalean's experiments and Calcul talk to the kernel)
    sage = which("sage")
    sv = parse_sage_version(run([sage, "--version"], 60)) if sage else ""
    spec = find_kernelspec("sagemath", kernel_dirs)
    s_ok = bool(sage and sv and vtuple(sv) >= MIN_SAGE and spec)
    tools["sage"] = {"found": bool(sage), "path": sage or "", "version": sv, "kernelspec": spec, "compatible": s_ok}
    # TeX Live (xelatex / lualatex + latexmk; fontspec needed by the export)
    xe, lua, mk, kpse = which("xelatex"), which("lualatex"), which("latexmk"), which("kpsewhich")
    year = parse_texlive_year(run([xe or lua, "--version"])) if (xe or lua) else 0
    fontspec = bool(kpse and run([kpse, "fontspec.sty"]).strip().endswith("fontspec.sty"))
    tools["tex"] = {"found": bool(xe or lua), "xelatex": xe or "", "lualatex": lua or "", "latexmk": mk or "",
                    "year": year, "fontspec": fontspec,
                    "compatible": bool((xe or lua) and fontspec and (year == 0 or year >= MIN_TEXLIVE))}
    tec = which("tectonic")
    tools["tectonic"] = {"found": bool(tec), "path": tec or "",
                         "version": parse_version(run([tec, "--version"])) if tec else ""}
    pys = []
    for name in ("python3", "python3.13", "python3.12", "python3.11", "python3.10"):
        p = which(name)
        if p and all(os.path.realpath(p) != os.path.realpath(x["path"]) for x in pys):
            pys.append({"path": p, "version": parse_version(run([p, "--version"]))})
    tools["python"] = pys
    elan = which("elan") or (str(home_p / ".elan" / "bin" / "elan") if (home_p / ".elan" / "bin" / "elan").exists() else "")
    tools["elan"] = {"found": bool(elan), "path": elan,
                     "toolchains": parse_elan_toolchains(run([elan, "toolchain", "list"])) if elan else []}
    for name, args in (("ollama", ["--version"]), ("tailscale", ["version"])):
        p = which(name)
        tools[name] = {"found": bool(p), "path": p or "", "version": parse_version(run([p, *args])) if p else ""}
    for name in ("bwrap", "curl", "systemctl", "xdg-open", "git"):
        tools[name] = {"found": bool(which(name)), "path": which(name) or ""}
    det["tools"] = tools
    models_dir = home_p / "models"
    det["madalean"] = {
        "prefix": str(prefix_p),
        "installed": (prefix_p / "env" / "bin" / "python").exists() or (prefix_p / "current").exists(),
        "version": os.path.basename(os.path.realpath(prefix_p / "current")) if (prefix_p / "current").exists() else "",
        "models": {k: (models_dir / f).is_file() for k, f in MODEL_FILES.items()},
        "sage_own": (prefix_p / "envs" / "sage" / "bin" / "sage").exists(),
        "workspaces": sorted(p.name for p in (prefix_p / "workspaces").iterdir()
                             if p.is_dir()) if (prefix_p / "workspaces").is_dir() else [],
    }
    return det


# ---------------------------------------------------------------- recommendations
def _gib(b: float) -> str:
    return f"{b / GIB:.0f}"


def best_gpu(det: dict) -> dict:
    gpus = det.get("hardware", {}).get("gpus") or []
    return max(gpus, key=lambda g: g.get("vram_mib", 0)) if gpus else {}


def disk_needed(plan: dict, det: dict | None = None) -> int:
    have = (det or {}).get("madalean", {}).get("models", {})
    n = sum(MODEL_BYTES for m in MODEL_SETS[plan["models"]] if not have.get(m))
    if plan["sage"] == "now" and not (det or {}).get("madalean", {}).get("sage_own"):
        n += SAGE_BYTES
    if plan["workspace"] == "build":
        n += WORKSPACE_BYTES
    return BASE_BYTES + n


def recommend(det: dict, lang: str = "fr") -> dict:
    """Recommended plan for this machine, with the reason for each item (FR and EN texts, `lang` chosen)."""
    fr = lang == "fr"
    hw, tools, mad = det.get("hardware", {}), det.get("tools", {}), det.get("madalean", {})
    ram = hw.get("ram_bytes", 0)
    free = hw.get("disk", {}).get("free_bytes", 0)
    gpu = best_gpu(det)
    vram = gpu.get("vram_mib", 0)
    plan = dict(DEFAULT_PLAN)
    items: list[dict] = []
    advice: list[dict] = []

    # local models
    if vram >= MIN_VRAM_ALL_MIB and ram >= MIN_RAM_ALL:
        plan["models"] = "all"
        why = (f"Carte {gpu['name']} ({vram // 1024} Go de mémoire graphique) et {_gib(ram)} Go de mémoire : les trois "
               "modèles tournent bien sur cette machine, même sans Internet." if fr else
               f"{gpu['name']} ({vram // 1024} GB of graphics memory) and {_gib(ram)} GB of RAM: the three models run "
               "well on this machine, even without Internet.")
    elif vram >= MIN_VRAM_PROVER_MIB:
        plan["models"] = "prover"
        why = (f"Carte {gpu['name']} ({vram // 1024} Go) : assez pour le modèle de preuve, pas pour les trois." if fr else
               f"{gpu['name']} ({vram // 1024} GB): enough for the prover model, not for all three.")
    else:
        plan["models"] = "none"
        why = ("Pas de modèle local conseillé : sans carte NVIDIA d'au moins 8 Go, un modèle local serait très lent. "
               "Les modèles en ligne (gratuits avec une clé) sont plus rapides et meilleurs. Les modèles déjà présents "
               "dans ~/models restent utilisables." if fr else
               "No local model recommended: without an NVIDIA card with at least 8 GB, a local model would be very "
               "slow. Online models (free with a key) are faster and better. Models already in ~/models stay usable.")
    have_models = [k for k, v in mad.get("models", {}).items() if v]
    det_txt = ((", ".join(MODEL_FILES[k] for k in have_models) + (" déjà présents" if fr else " already present"))
               if have_models else ("aucun modèle dans ~/models" if fr else "no model in ~/models"))
    items.append({"id": "models", "recommended": plan["models"], "why": why, "detected": det_txt})

    # llama.cpp build
    cuda = hw.get("cuda", "")
    plan["variant"] = "auto" if (gpu and plan["models"] != "none") else "cpu"
    items.append({"id": "variant", "recommended": plan["variant"],
                  "why": (("Le pilote NVIDIA (CUDA " + cuda + ") permet d'utiliser la carte." if fr else
                           "The NVIDIA driver (CUDA " + cuda + ") can use the card.") if plan["variant"] == "auto" else
                          ("Version processeur : légère (23 Mo au lieu de 660 Mo) ; suffisante sans modèle local." if fr
                           else "Processor build: light (23 MB instead of 660 MB); enough without a local model.")),
                  "detected": (f"{gpu['name']}, pilote {gpu.get('driver', '?')}" if gpu else
                               ("aucune carte NVIDIA" if fr else "no NVIDIA card"))})

    # SageMath
    s = tools.get("sage", {})
    if mad.get("sage_own"):
        plan["sage"] = "later"
        why = ("La copie de SageMath de Madalean est déjà installée." if fr else "Madalean's SageMath is already installed.")
    elif s.get("compatible"):
        plan["sage"] = "system"
        why = (f"SageMath {s['version']} est déjà installé et compatible (version ≥ 10.0, noyau Jupyter présent) : "
               "le réutiliser économise 5 Go ; votre distribution le met à jour. Le même bac à sable s'applique." if fr
               else f"SageMath {s['version']} is already installed and compatible (version ≥ 10.0, Jupyter kernel "
               "present): reusing it saves 5 GB; your distribution keeps it updated. The same sandbox applies.")
    else:
        plan["sage"] = "later"
        if s.get("found") and not s.get("kernelspec"):
            reason = ("le SageMath du système n'a pas de noyau Jupyter « sagemath »" if fr else
                      "the system SageMath has no « sagemath » Jupyter kernel")
        elif s.get("found"):
            reason = (f"le SageMath du système ({s.get('version') or '?'}) est trop ancien (10.0 minimum)" if fr else
                      f"the system SageMath ({s.get('version') or '?'}) is too old (10.0 minimum)")
        else:
            reason = "pas de SageMath sur cette machine" if fr else "no SageMath on this machine"
        why = (f"{reason[0].upper() + reason[1:]} : Madalean installera sa propre copie (SageMath 10.10) au premier "
               "calcul, seulement si vous vous en servez." if fr else
               f"{reason[0].upper() + reason[1:]}: Madalean will install its own copy (SageMath 10.10) the first time "
               "you compute, only if you use it.")
    items.append({"id": "sage", "recommended": plan["sage"], "why": why,
                  "detected": (f"SageMath {s.get('version') or '?'} ({s.get('path')})"
                               + ("" if s.get("kernelspec") else (", sans noyau Jupyter" if fr else ", no Jupyter kernel"))
                               ) if s.get("found") else ("absent" if fr else "not found"),
                  "options_ok": {"system": bool(s.get("compatible"))}})

    # LaTeX
    tex = tools.get("tex", {})
    plan["tex"] = "own"
    items.append({"id": "tex", "recommended": "own",
                  "why": ("tectonic (fourni) donne le même PDF partout et marche hors ligne." +
                          (" Votre TeX Live reste utilisé automatiquement en secours." if tex.get("compatible") else "")
                          if fr else "tectonic (included) gives the same PDF everywhere and works offline." +
                          (" Your TeX Live is still used automatically as a fallback." if tex.get("compatible") else "")),
                  "detected": (f"TeX Live {tex.get('year') or '?'} ({tex.get('xelatex') or tex.get('lualatex')})"
                               + ("" if tex.get("fontspec") else (", sans fontspec" if fr else ", no fontspec"))
                               ) if tex.get("found") else ("pas de TeX Live" if fr else "no TeX Live"),
                  "options_ok": {"system": bool(tex.get("compatible"))}})

    # Lean workspace
    ws = mad.get("workspaces", [])
    plan["workspace"] = "import" if ws else ("build" if free >= disk_needed({**plan, "workspace": "build"}, det)
                                               else "import")
    elan = tools.get("elan", {})
    items.append({"id": "workspace", "recommended": plan["workspace"],
                  "why": (("Espaces déjà installés : " + ", ".join(ws) + "." if fr else
                           "Workspaces already installed: " + ", ".join(ws) + ".") if ws else
                          ("Sans espace Lean, Madalean ne peut pas vérifier de preuve : construisez-le maintenant "
                           "(≈ 5 Go, 10 à 30 min)." if fr else "Without a Lean workspace Madalean cannot check proofs: "
                           "build it now (≈ 5 GB, 10–30 min).") if plan["workspace"] == "build" else
                          ("Pas assez de place pour construire l'espace Lean maintenant (≈ 5 Go) : libérez de la place, "
                           "puis construisez-le depuis Madalean (Réglages › Système) ou avec --build-workspace." if fr
                           else "Not enough space to build the Lean workspace now (≈ 5 GB): free some space, then "
                           "build it from Madalean (Settings › System) or with --build-workspace.")),
                  "detected": (("elan présent, chaînes : " if fr else "elan present, toolchains: ")
                               + (", ".join(elan.get("toolchains", [])[:4]) or "-")) if elan.get("found") else
                  ("pas d'elan (Madalean installe le sien)" if fr else "no elan (Madalean installs its own)")})

    # mode
    plan["mode"] = "auto" if plan["models"] != "none" else "online"
    items.append({"id": "mode", "recommended": plan["mode"],
                  "why": ("Avec un modèle local : en ligne quand c'est possible, local sans réseau." if fr else
                          "With a local model: online when possible, local without network.")
                  if plan["mode"] == "auto" else
                  ("Sans modèle local, tout passe par les modèles en ligne (clé gratuite à ajouter au premier "
                   "démarrage)." if fr else "Without a local model everything goes through online models (add a free "
                   "key at first start)."), "detected": ""})

    for it in items:
        it["title"] = tr(it["id"], lang)
        it["options"] = [{"value": v, "label": tr(f"{it['id']}.{v}", lang),
                          "available": it.get("options_ok", {}).get(v, True)} for v in CHOICES[it["id"]]]

    fam = det.get("os", {}).get("family", "unknown")
    if not tools.get("bwrap", {}).get("found"):
        advice.append({"id": "bwrap", "command": install_command("bubblewrap", fam),
                       "text": ("bubblewrap n'est pas installé : Lean, LaTeX et les calculs tourneront sans bac à sable. "
                                "Installez-le vous-même (Madalean n'utilise jamais sudo) :" if fr else
                                "bubblewrap is not installed: Lean, LaTeX and computations will run without a sandbox. "
                                "Install it yourself (Madalean never uses sudo):")})
    if tools.get("ollama", {}).get("found"):
        advice.append({"id": "ollama", "command": "",
                       "text": ("Ollama est présent : il reste installé ; ses modèles apparaissent parmi les modèles "
                                "locaux. Évitez de faire tourner les deux en même temps sur la carte graphique." if fr else
                                "Ollama is present: it stays installed; its models appear among the local models. "
                                "Avoid running both at once on the graphics card.")})
    if tools.get("tailscale", {}).get("found"):
        advice.append({"id": "tailscale", "command": "",
                       "text": ("Tailscale du système détecté : Madalean a son propre nœud (« madalean » dans votre "
                                "réseau Tailscale) ; les deux cohabitent." if fr else
                                "System Tailscale detected: Madalean runs its own node (« madalean » in your tailnet); "
                                "both coexist.")})
    if not det.get("os", {}).get("supported", True):
        advice.append({"id": "platform", "command": "",
                       "text": ("Madalean s'installe sur Linux x86_64 seulement." if fr else
                                "Madalean installs on Linux x86_64 only.")})
    need = disk_needed(plan, det)
    if free and need > free:
        advice.append({"id": "disk", "command": "",
                       "text": (f"Place insuffisante : ce plan demande ≈ {_gib(need)} Go, {_gib(free)} Go libres. "
                                "Choisissez moins de modèles ou libérez de la place." if fr else
                                f"Not enough space: this plan needs ≈ {_gib(need)} GB, {_gib(free)} GB free. "
                                "Choose fewer models or free some space.")})
    return {"plan": plan, "items": items, "advice": advice, "disk": {"needed_bytes": need, "free_bytes": free}}


def validate(plan: dict, base: dict | None = None) -> dict:
    """Complete `plan` from `base` (default plan) and refuse unknown items / values (ValueError)."""
    out = dict(base or DEFAULT_PLAN)
    for k, v in (plan or {}).items():
        if k not in CHOICES:
            raise ValueError(f"unknown item {k!r}")
        if v not in CHOICES[k]:
            raise ValueError(f"bad value {v!r} for {k} (allowed: {', '.join(CHOICES[k])})")
        out[k] = v
    return out


def shell_vars(plan: dict) -> str:
    """Lines read by install.sh (`KEY=value`, values from fixed allow-lists only)."""
    p = validate(plan)
    return "\n".join([f"PLAN_MODELS={p['models']}", f"PLAN_MODEL_LIST={' '.join(MODEL_SETS[p['models']])}",
                      f"PLAN_VARIANT={p['variant']}", f"PLAN_SAGE={p['sage']}", f"PLAN_TEX={p['tex']}",
                      f"PLAN_WORKSPACE={p['workspace']}", f"PLAN_MODE={p['mode']}"]) + "\n"


def settings_from_plan(plan: dict) -> dict:
    """The Settings fields the install choices set at first start."""
    p = validate(plan)
    return {"sage_source": "system" if p["sage"] == "system" else "auto",
            "tex_engine": "system" if p["tex"] == "system" else "auto", "mode": p["mode"]}


# ---------------------------------------------------------------- terminal front-end
def table(det: dict, lang: str = "fr") -> str:
    fr = lang == "fr"
    hw, tools = det.get("hardware", {}), det.get("tools", {})
    gpu = best_gpu(det)
    rows = [
        ("Processeur" if fr else "Processor", f"{hw.get('cpu', {}).get('model') or '?'} "
                                             f"({hw.get('cpu', {}).get('threads', '?')} threads)"),
        ("Mémoire" if fr else "Memory", f"{_gib(hw.get('ram_bytes', 0))} Go" if fr else f"{_gib(hw.get('ram_bytes', 0))} GB"),
        ("Disque libre" if fr else "Free disk", f"{_gib(hw.get('disk', {}).get('free_bytes', 0))} "
                                               f"{'Go' if fr else 'GB'} ({hw.get('disk', {}).get('path', '')})"),
        ("Carte graphique" if fr else "Graphics card", f"{gpu['name']} — {gpu['vram_mib'] // 1024} "
                                                      f"{'Go' if fr else 'GB'}, CUDA {hw.get('cuda') or '?'}" if gpu else
         ("aucune carte NVIDIA" if fr else "no NVIDIA card")),
        ("SageMath", (f"{tools['sage'].get('version') or '?'} " + ("compatible" if tools["sage"].get("compatible") else
                     ("non compatible" if fr else "not compatible"))) if tools.get("sage", {}).get("found") else "-"),
        ("TeX Live", (f"{tools['tex'].get('year') or '?'} " + ("compatible" if tools["tex"].get("compatible") else
                     ("non compatible" if fr else "not compatible"))) if tools.get("tex", {}).get("found") else "-"),
        ("Python", ", ".join(p["version"] for p in tools.get("python", []) if p.get("version")) or "-"),
        ("elan / Lean", ", ".join(tools.get("elan", {}).get("toolchains", [])[:3]) or
         ("présent" if fr else "present") if tools.get("elan", {}).get("found") else "-"),
        ("Ollama", tools.get("ollama", {}).get("version") or ("présent" if fr else "present")
         if tools.get("ollama", {}).get("found") else "-"),
        ("Tailscale", tools.get("tailscale", {}).get("version") or ("présent" if fr else "present")
         if tools.get("tailscale", {}).get("found") else "-"),
        ("bubblewrap", ("présent" if fr else "present") if tools.get("bwrap", {}).get("found") else
         ("absent" if fr else "missing")),
    ]
    w = max(len(r[0]) for r in rows)
    return "\n".join(f"  {a.ljust(w)}  {b}" for a, b in rows)


def describe_plan(rec: dict, plan: dict, lang: str = "fr") -> str:
    fr = lang == "fr"
    lines = []
    for i, it in enumerate(rec["items"], 1):
        v = plan[it["id"]]
        star = (" (conseillé)" if fr else " (recommended)") if v == it["recommended"] else ""
        lines.append(f"  {i}. {it['title']} : {tr(it['id'] + '.' + v, lang)}{star}")
    return "\n".join(lines)


def interactive(det: dict, start: dict | None = None, lang: str = "fr", ask=input, out=print) -> dict:
    """Terminal assistant: summary, recommended plan, accept or change each item. Returns the chosen plan."""
    fr = lang == "fr"
    rec = recommend(det, lang)
    plan = validate(start or {}, rec["plan"])
    out("")
    out("Votre machine" if fr else "Your machine")
    out(table(det, lang))
    out("")
    out("Plan conseillé pour cette machine" if fr else "Recommended plan for this machine")
    for it in rec["items"]:
        out(f"  • {it['title']} : {tr(it['id'] + '.' + rec['plan'][it['id']], lang)}")
        out(f"      {it['why']}")
    for a in rec["advice"]:
        out(f"  ! {a['text']}")
        if a.get("command"):
            out(f"      {a['command']}")
    while True:
        out("")
        out(("Plan retenu :" if fr else "Chosen plan:"))
        out(describe_plan(rec, plan, lang))
        need = disk_needed(plan, det)
        out(("  Place nécessaire ≈ " if fr else "  Space needed ≈ ") + _gib(need) + (" Go" if fr else " GB"))
        try:
            a = ask(("[Entrée] installer ce plan · numéro (1-%d) pour changer un élément · q pour quitter : " if fr else
                     "[Enter] install this plan · number (1-%d) to change an item · q to quit: ")
                    % len(rec["items"])).strip().lower()
        except EOFError:
            a = ""
        if a in ("", "o", "oui", "y", "yes"):
            return plan
        if a in ("q", "quit", "quitter"):
            raise KeyboardInterrupt
        if a.isdigit() and 1 <= int(a) <= len(rec["items"]):
            it = rec["items"][int(a) - 1]
            for j, o in enumerate(it["options"], 1):
                mark = ("  ← conseillé" if fr else "  ← recommended") if o["value"] == it["recommended"] else ""
                na = "" if o["available"] else ("  (non disponible ici)" if fr else "  (not available here)")
                out(f"    {j}) {o['label']}{mark}{na}")
            out(f"    {it['why']}")
            try:
                b = ask("Choix : " if fr else "Choice: ").strip()
            except EOFError:
                b = ""
            if b.isdigit() and 1 <= int(b) <= len(it["options"]) and it["options"][int(b) - 1]["available"]:
                plan[it["id"]] = it["options"][int(b) - 1]["value"]
            else:
                out("  (inchangé)" if fr else "  (unchanged)")


# ---------------------------------------------------------------- setup state (<config>/setup.json)
def setup_file(config_dir: str | Path) -> Path:
    return Path(config_dir) / "setup.json"


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load(config_dir: str | Path) -> dict | None:
    try:
        d = json.loads(setup_file(config_dir).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("schema") == SCHEMA else None
    except (OSError, ValueError):
        return None


def record(config_dir: str | Path, plan_doc: dict, rc: int, source: str, version: str = "") -> dict:
    """Write setup.json after an install run. `plan_doc` = the file written by `plan` (detected, recommended,
    plan, interactive). The settings to apply are re-armed only when the plan changed (a repair run with the same
    plan never overrides what the user changed in the app since)."""
    prev = load(config_dir) or {}
    plan = validate(plan_doc.get("plan") or {})
    apply = settings_from_plan(plan)
    same = prev.get("plan") == plan
    doc = {"schema": SCHEMA, "version": version, "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "source": source, "interactive": bool(plan_doc.get("interactive")),
           "detected": plan_doc.get("detected") or {}, "recommended": plan_doc.get("recommended") or {},
           "plan": plan, "result": {"rc": int(rc), "ok": int(rc) == 0},
           "apply": apply, "applied": bool(prev.get("applied")) and same,
           "applied_at": prev.get("applied_at", "") if same else "",
           "history": (prev.get("history") or [])[-9:] + [{"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                                            "source": source, "rc": int(rc), "plan": plan}]}
    _atomic_write(setup_file(config_dir), doc)
    return doc


def apply_pending(settings, config_dir: str | Path) -> bool:
    """At server start: copy the install choices into `settings` once (True when something changed; the caller
    saves the settings)."""
    doc = load(config_dir)
    if not doc or doc.get("applied") or not doc.get("result", {}).get("ok"):
        return False
    changed = False
    for k, v in (doc.get("apply") or {}).items():
        allowed = {"sage_source": ("auto", "own", "system"), "tex_engine": ("auto", "tectonic", "system"),
                   "mode": CHOICES["mode"]}.get(k)
        if allowed and v in allowed and hasattr(settings, k) and getattr(settings, k) != v:
            setattr(settings, k, v)
            changed = True
    doc["applied"] = True
    doc["applied_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    try:
        _atomic_write(setup_file(config_dir), doc)
    except OSError:
        pass
    return changed


# ---------------------------------------------------------------- CLI
def _plan_doc(det: dict, plan: dict, interactive_: bool, lang: str) -> dict:
    rec = recommend(det, lang)
    return {"schema": SCHEMA, "detected": det, "recommended": rec["plan"], "plan": validate(plan),
            "interactive": interactive_, "advice": rec["advice"], "disk_needed_bytes": disk_needed(validate(plan), det)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m madalean.deps.assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--json", action="store_true")
    d.add_argument("--prefix")
    p = sub.add_parser("plan", help="detect, then choose (defaults | recommendation | interactive) and write a plan file")
    p.add_argument("--out", required=True)
    p.add_argument("--prefix")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--defaults", action="store_true", help="the defaults of install.sh --yes (2.0.0 behaviour)")
    g.add_argument("--recommended", action="store_true", help="the recommended plan, no question")
    g.add_argument("--interactive", action="store_true")
    g.add_argument("--from", dest="src", help="a plan file written by the assistant or the graphical installer")
    p.add_argument("--set", action="append", default=[], help="item=value (command-line options of install.sh)")
    p.add_argument("--lang")
    s = sub.add_parser("show")
    s.add_argument("file")
    s.add_argument("--lang")
    v = sub.add_parser("vars")
    v.add_argument("file")
    r = sub.add_parser("record")
    r.add_argument("--config-dir", required=True)
    r.add_argument("--plan", required=True)
    r.add_argument("--rc", type=int, default=0)
    r.add_argument("--source", default="install.sh")
    r.add_argument("--version", default="")
    a = ap.parse_args(argv)
    lang = getattr(a, "lang", None) or lang_default()

    if a.cmd == "detect":
        det = detect(a.prefix)
        print(json.dumps(det, indent=1, ensure_ascii=False) if a.json else table(det, lang_default()))
        return 0
    if a.cmd == "plan":
        try:
            sets = dict(x.split("=", 1) for x in a.set)
            det = detect(a.prefix)
            if a.src:
                plan = validate(json.loads(Path(a.src).read_text(encoding="utf-8")).get("plan") or {})
                plan = validate(sets, plan)
            elif a.interactive:
                tty = None
                try:
                    tty = open("/dev/tty", encoding="utf-8")            # stdin may be a pipe (curl … | bash)

                    def ask(prompt: str) -> str:
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                        line = tty.readline()
                        if not line:
                            raise EOFError
                        return line
                except OSError:
                    ask = input
                try:
                    plan = interactive(det, sets, lang, ask=ask)
                finally:
                    if tty:
                        tty.close()
            elif a.recommended:
                plan = validate(sets, recommend(det, lang)["plan"])
            else:
                plan = validate(sets)
        except KeyboardInterrupt:
            print("\nInstallation annulée." if lang == "fr" else "\nInstallation cancelled.")
            return 130
        except (ValueError, OSError) as e:
            print(f"plan: {e}", file=sys.stderr)
            return 2
        doc = _plan_doc(det, plan, bool(a.interactive), lang)
        _atomic_write(Path(a.out), doc)
        return 0
    if a.cmd in ("show", "vars"):
        try:
            doc = json.loads(Path(a.file).read_text(encoding="utf-8"))
            plan = validate(doc.get("plan") or {})
        except (OSError, ValueError) as e:
            print(f"{a.cmd}: {e}", file=sys.stderr)
            return 2
        if a.cmd == "vars":
            sys.stdout.write(shell_vars(plan))
        else:
            rec = recommend(doc.get("detected") or {}, lang)
            print(describe_plan(rec, plan, lang))
            for adv in doc.get("advice") or []:
                print(f"  ! {adv.get('text', '')}" + (f"\n      {adv['command']}" if adv.get("command") else ""))
        return 0
    if a.cmd == "record":
        try:
            doc = json.loads(Path(a.plan).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {"plan": DEFAULT_PLAN}
        if not doc.get("detected"):
            doc["detected"] = detect()
        record(a.config_dir, doc, a.rc, a.source, a.version)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
