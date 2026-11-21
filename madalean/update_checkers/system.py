"""System components, llama.cpp, Madalean itself, the online catalogue — all NOTIFY ONLY.

Madalean never runs pacman / apt / dnf / sudo / pip: each candidate carries the exact command for the detected
distribution (read-only queries only: `pacman -Qo/-Si`, `dpkg -S`, `apt-cache policy`, `rpm -qf`; never `pacman -Sy`).

Madalean releases (design, see docs/RESEARCH_WORKSHOP.md §Updates): a release publishes `SHA256SUMS` and
`SHA256SUMS.minisig` (minisign, Ed25519); the public key ships in the repository (`packaging/minisign.pub`) so the
installer verifies the signature of the checksums, then the checksum of the archive, before unpacking. For now
installing = notification + exact steps (git fetch of the signed tag + ./install.sh)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .. import __version__, config, updates
from ..i18n import _
from .common import (CheckError, candidate, distro_family, get_json, ls_remote, newer, newest_version,
                     owner_package, repo_version, run, upgrade_command)

SAGE_GIT = "https://github.com/sagemath/sage"
POPPLER_GIT = "https://gitlab.freedesktop.org/poppler/poppler.git"
LLAMA_GIT = "https://github.com/ggml-org/llama.cpp"
MADALEAN_RELEASES = "https://api.github.com/repos/raantss18/madalean/releases/latest"
PYPI = "https://pypi.org/pypi/{name}/json"


def _v(text: str, pattern: str) -> str:
    m = re.search(pattern, text or "")
    return m.group(1) if m else ""


def installed_versions() -> dict[str, dict]:
    """Detected versions and the file each comes from (for the package-owner query)."""
    out = {}
    sage = shutil.which("sage") or ""
    out["sage"] = {"version": _v(run(["sage", "--version"], 60), r"(\d+\.\d+(?:\.\d+)?)"), "path": sage}
    jl = shutil.which("jupyter-lab") or ""
    out["jupyterlab"] = {"version": _v(run(["jupyter-lab", "--version"]), r"(\d+\.\d+\.\d+)"), "path": jl}
    py = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else (shutil.which("python3") or "")
    ipk = run([py, "-c", "import ipykernel,os;print(ipykernel.__version__, os.path.dirname(ipykernel.__file__))"]) \
        if py else ""
    out["ipykernel"] = {"version": _v(ipk, r"^(\d+\.\d+\.\d+)"), "path": (ipk.split(" ", 1)[1].strip() + "/__init__.py")
                        if " " in ipk else ""}
    tex = shutil.which("tex") or ""
    out["texlive"] = {"version": _v(run(["tex", "--version"]), r"TeX Live (\d{4})"), "path": tex}
    pdft = shutil.which("pdftotext") or ""
    out["poppler"] = {"version": _v(run(["pdftotext", "-v"]), r"version (\d+\.\d+\.\d+)"), "path": pdft}
    return out


def pypi_latest(name: str) -> str:
    return str(get_json(PYPI.format(name=name)).get("info", {}).get("version", ""))


def system_candidates(installed: dict[str, dict], upstream: dict[str, str], family: str, owners: dict[str, str],
                      repo: dict[str, str]) -> list:
    out = []
    pip_names = {"jupyterlab": "jupyterlab", "ipykernel": "ipykernel"}
    titles = {"sage": "SageMath", "jupyterlab": "JupyterLab", "ipykernel": "IPython kernel (ipykernel)",
              "texlive": "TeX Live", "poppler": "Poppler (pdftotext)"}
    notes_url = {"sage": "https://github.com/sagemath/sage/releases",
                 "jupyterlab": "https://github.com/jupyterlab/jupyterlab/releases",
                 "ipykernel": "https://github.com/ipython/ipykernel/releases", "texlive": "https://tug.org/texlive/",
                 "poppler": "https://poppler.freedesktop.org/releases.html"}
    for comp, info in installed.items():
        cur = info.get("version") or ""
        if not cur:
            continue
        up, rp, pkg = upstream.get(comp, ""), repo.get(comp, ""), owners.get(comp, "")
        rp_clean = re.sub(r"^\d+:", "", rp).split("-")[0]
        repo_newer = bool(rp_clean) and newer(rp_clean, cur)
        up_newer = bool(up) and newer(up, cur)
        if not (repo_newer or up_newer):
            continue
        if repo_newer:
            cmd = upgrade_command(pkg, family)
            note = _("Mise à jour disponible dans les dépôts de votre distribution. Commande exacte (à lancer vous-même) "
                     ": {cmd}").format(cmd=cmd)
        elif pkg:
            cmd = ""
            note = _("Nouvelle version publiée en amont ({up}), pas encore dans les dépôts de votre distribution "
                     "({repo}) : attendre la mise à jour du paquet {pkg}.").format(up=up, repo=rp or "?", pkg=pkg)
        else:
            cmd = upgrade_command("", family, pip_names.get(comp, ""))
            note = (_("Installé hors gestionnaire de paquets. Commande exacte (à lancer vous-même) : {cmd}")
                    .format(cmd=cmd) if cmd else _("Installé hors gestionnaire de paquets : voir le site du projet."))
        out.append(candidate("system", f"system:{comp}", titles[comp], cur, rp_clean if repo_newer else up,
                             note=note, command=cmd, package=pkg, distro=family, upstream=up, repo=rp,
                             release_notes=notes_url.get(comp, ""),
                             risk=_("Paquet système : Madalean ne l'installe jamais lui-même."),
                             estimate={"minutes": 5}))
    return out


def system_checker(fetch_upstream: bool = True):
    def check():
        family = distro_family()
        inst = installed_versions()
        owners = {k: owner_package(v.get("path", ""), family) for k, v in inst.items()}
        repo = {k: repo_version(p, family) for k, p in owners.items() if p}
        upstream: dict[str, str] = {}
        errors = []
        if fetch_upstream:
            def guard(name, fn):
                try:
                    upstream[name] = fn()
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{name}: {e}")
            guard("sage", lambda: newest_version(ls_remote(SAGE_GIT, patterns=("1*",))["tags"]) or "")
            guard("jupyterlab", lambda: pypi_latest("jupyterlab"))
            guard("ipykernel", lambda: pypi_latest("ipykernel"))
            guard("poppler", lambda: (newest_version(ls_remote(POPPLER_GIT, patterns=("poppler-*",))["tags"],
                                                     "poppler-") or "").replace("poppler-", ""))
        cands = system_candidates(inst, upstream, family, owners, repo)
        if errors and not cands and len(errors) == 4:
            raise CheckError("; ".join(errors))
        return cands
    return check


# ---------------------------------------------------------------- llama.cpp (pinned, notify only)
def llama_installed(vendor: Path | None = None) -> str:
    d = Path(vendor or (config.STATION_DIR / "vendor" / "llama.cpp"))
    if not (d / ".git").exists():
        return ""
    try:
        r = subprocess.run(["git", "-C", str(d), "describe", "--tags", "--always"], capture_output=True, text=True,
                           timeout=10)
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def llama_candidates(installed: str, tags: list[str]) -> list:
    builds = [t for t in tags if re.fullmatch(r"b\d+", t)]
    if not builds:
        return []
    latest = max(builds, key=lambda t: int(t[1:]))
    cur_b = _v(installed, r"^(b\d+)")
    if cur_b and int(cur_b[1:]) >= int(latest[1:]):
        return []
    return [candidate("llama.cpp", "llama.cpp", f"llama.cpp {latest}", installed or "?", latest,
                      note=_("Épinglé : la version de llama.cpp est celle validée avec les modèles (BENCH.md). "
                             "Notification seulement."),
                      release_notes=f"{LLAMA_GIT}/releases/tag/{latest}", risk="pinned",
                      command=(f"git -C vendor/llama.cpp fetch --tags && git -C vendor/llama.cpp checkout {latest} && "
                               "cmake --build vendor/llama.cpp/build -j  # then re-run the model benchmarks"),
                      estimate={"minutes": 15})]


def llama_checker():
    def check():
        inst = llama_installed()
        return llama_candidates(inst, list(ls_remote(LLAMA_GIT, patterns=("b*",))["tags"])) if inst else []
    return check


# ---------------------------------------------------------------- Madalean itself
def madalean_candidates(release: dict, current: str = __version__) -> list:
    tag = str(release.get("tag_name") or "")
    base = current.split(".dev")[0]
    if not tag or not (updates.vtuple(tag) > updates.vtuple(base) or
                       (".dev" in current and updates.vtuple(tag) >= updates.vtuple(base))):
        return []
    assets = [a.get("name") for a in release.get("assets") or [] if isinstance(a, dict)]
    signed = "SHA256SUMS" in assets and "SHA256SUMS.minisig" in assets
    return [candidate("madalean", "madalean", f"Madalean {tag}", current, tag,
                      note=_("Installation manuelle pour l'instant : suivez les étapes indiquées."),
                      release_notes=str(release.get("html_url") or ""), signed=signed,
                      steps=[f"git -C {config.tilde(config.STATION_DIR)} fetch --tags",
                             f"git -C {config.tilde(config.STATION_DIR)} verify-tag {tag}  # when tags are signed",
                             f"git -C {config.tilde(config.STATION_DIR)} checkout {tag}", "./install.sh"],
                      risk=_("Redémarre le serveur ; vos données (~/.config/madalean) sont conservées."),
                      estimate={"minutes": 3})]


def madalean_checker():
    def check():
        try:
            rel = get_json(MADALEAN_RELEASES)
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):
                return []                   # no release published yet
            raise
        return madalean_candidates(rel)
    return check


def catalogue_checker(get_ctx):
    """Refresh the brain's online catalogue (no candidate: the models page shows the result)."""
    def check():
        import asyncio
        ctx, loop = get_ctx()
        if ctx is None or loop is None or ctx.brain is None or not hasattr(ctx.brain, "refresh"):
            return []
        fut = asyncio.run_coroutine_threadsafe(ctx.brain.refresh(), loop)
        fut.result(90)
        return []
    return check


# ---------------------------------------------------------------- « Installer » for system packages: a terminal
TERMINALS = (("konsole", ["konsole", "--hold", "-e"]), ("gnome-terminal", ["gnome-terminal", "--"]),
             ("kgx", ["kgx", "--"]), ("xfce4-terminal", ["xfce4-terminal", "--hold", "-x"]),
             ("x-terminal-emulator", ["x-terminal-emulator", "-e"]), ("alacritty", ["alacritty", "-e"]),
             ("kitty", ["kitty", "--hold"]), ("foot", ["foot", "--hold"]), ("xterm", ["xterm", "-hold", "-e"]))


def terminal_argv(command: str, which=shutil.which) -> list[str] | None:
    """argv opening the user's terminal (Konsole first) on `command`: the user reads it, types the password
    themselves; Madalean never runs sudo. The command comes from the server's own candidate, never from a client."""
    if not command or "\n" in command or "\x00" in command or "#" in command:
        return None
    script = (f"echo {shlex_quote('Madalean — commande proposée :')}; echo {shlex_quote(command)}; echo; "
              f"read -r -p {shlex_quote('Entrée pour lancer, Ctrl+C pour annuler… ')} _ && {command}; echo; "
              f"read -r -p {shlex_quote('Terminé. Entrée pour fermer.')} _")
    for name, prefix in TERMINALS:
        if which(name):
            return [which(name) or name, *prefix[1:], "bash", "-c", script]
    return None


def shlex_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)


def open_terminal(command: str, popen=subprocess.Popen) -> bool:
    argv = terminal_argv(command)
    if argv is None:
        return False
    env = {k: v for k, v in os.environ.items() if not re.search(r"KEY|TOKEN|SECRET|PASSW", k)}
    popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
          start_new_session=True, env=env)
    return True
