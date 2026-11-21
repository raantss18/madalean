"""Shared helpers of the extended update checkers: safe `git ls-remote`, version comparison, distro detection,
read-only package-manager queries. Nothing here installs anything."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from .. import updates

UA = {"User-Agent": "madalean-update-check"}
LS_REMOTE_TIMEOUT = 25


class CheckError(Exception):
    pass


def safe_git_url(url: str, allow_schemes: tuple[str, ...] = ("https",)) -> str:
    """Only plain https URLs (as found in lake manifests) — no credentials in the URL, no option injection.
    `file` may be allowed by tests (fixture repositories)."""
    u = (url or "").strip()
    m = re.match(r"^([a-z][a-z0-9+.-]*)://", u)
    if not m or m.group(1) not in allow_schemes or u.startswith("-") or any(c in u for c in " \n\r\t\\"):
        raise CheckError(f"refused URL: {u[:120]}")
    if m.group(1) == "https" and ("@" in u.split("://", 1)[1].split("/", 1)[0] or
                                 not re.match(r"^https://[A-Za-z0-9.-]+(:\d+)?/", u)):
        raise CheckError(f"refused URL: {u[:120]}")
    return u


def git_env() -> dict[str, str]:
    """No prompt, no user/system git config (credential helpers, insteadOf rewrites), no askpass."""
    home = tempfile.gettempdir()
    return {"PATH": "/usr/bin:/bin:/usr/local/bin", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "HOME": home,
            "LANG": "C"}


def ls_remote(url: str, allow_schemes: tuple[str, ...] = ("https",), timeout: float = LS_REMOTE_TIMEOUT,
              patterns: tuple[str, ...] = ()) -> dict[str, dict[str, str]]:
    """{"tags": {name: sha}, "heads": {name: sha}} of a remote, with peeled tags resolved."""
    u = safe_git_url(url, allow_schemes)
    cmd = ["git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null", "-c", "protocol.ext.allow=never",
           "-c", f"protocol.file.allow={'always' if 'file' in allow_schemes else 'never'}",
           "ls-remote", "--tags", "--heads", "--", u, *patterns]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=git_env(),
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as e:
        raise CheckError(f"git ls-remote timeout ({u})") from e
    if r.returncode != 0:
        raise CheckError((r.stderr.strip() or "git ls-remote failed")[-300:])
    tags, heads = {}, {}
    for ln in r.stdout.splitlines():
        sha, _, ref = ln.partition("\t")
        if ref.startswith("refs/tags/"):
            name = ref[len("refs/tags/"):]
            if name.endswith("^{}"):
                tags[name[:-3]] = sha                 # peeled: the commit
            else:
                tags.setdefault(name, sha)
        elif ref.startswith("refs/heads/"):
            heads[ref[len("refs/heads/"):]] = sha
    return {"tags": tags, "heads": heads}


VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)+)$")


def is_version(tag: str) -> bool:
    return bool(VERSION_RE.match(tag))


def newest_version(tags, prefix: str = "") -> str | None:
    """Newest stable `vX.Y[.Z]` / `X.Y` tag (release candidates, betas, nightlies excluded)."""
    stable = [t for t in tags if t.startswith(prefix) and VERSION_RE.match(t[len(prefix):])]
    return max(stable, key=lambda t: updates.vtuple(t)) if stable else None


def newest_rc(tags) -> str | None:
    rc = [t for t in tags if re.fullmatch(r"v?\d+(\.\d+)+-rc\d+", t)]
    return max(rc, key=lambda t: updates.vtuple(t)) if rc else None


def newer(a: str | None, b: str | None) -> bool:
    return bool(a and b) and updates.vtuple(a) > updates.vtuple(b)


def get_json(url: str, timeout: float = 20):
    if not url.startswith("https://"):
        raise CheckError("refused URL")
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(2_000_000).decode("utf-8"))


def run(cmd: list[str], timeout: float = 20) -> str:
    """Read-only command (version queries); '' when missing or failing."""
    if not shutil.which(cmd[0]):
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           env={**os.environ, "LANG": "C", "LC_ALL": "C"})
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------- distro
def os_release(path: str = "/etc/os-release") -> dict[str, str]:
    out = {}
    try:
        for ln in Path(path).read_text().splitlines():
            k, _, v = ln.partition("=")
            out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
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


def owner_package(path: str, family: str) -> str:
    """Package that owns a file (read-only query), '' when unknown / not packaged."""
    if not path:
        return ""
    if family == "arch":
        out = run(["pacman", "-Qoq", path])
        return out.split()[0] if out and "error" not in out.lower() else ""
    if family == "debian":
        out = run(["dpkg", "-S", path])
        return out.split(":")[0] if out and "no path" not in out else ""
    if family in ("fedora", "suse"):
        out = run(["rpm", "-qf", "--qf", "%{NAME}", path])
        return out if out and "not owned" not in out else ""
    return ""


def repo_version(pkg: str, family: str) -> str:
    """Version in the distribution's repositories as last synchronised (never refreshes: no `pacman -Sy`)."""
    if not pkg:
        return ""
    if family == "arch":
        m = re.search(r"(?m)^Version\s*:\s*(\S+)", run(["pacman", "-Si", pkg]))
        return m.group(1) if m else ""
    if family == "debian":
        m = re.search(r"(?m)^\s*Candidate:\s*(\S+)", run(["apt-cache", "policy", pkg]))
        return m.group(1) if m and m.group(1) != "(none)" else ""
    if family == "fedora":
        m = re.search(r"(?m)^Version\s*:\s*(\S+)", run(["dnf", "-q", "--cacheonly", "info", pkg], 40))
        return m.group(1) if m else ""
    return ""


def upgrade_command(pkg: str, family: str, pip_name: str = "") -> str:
    if pkg:
        # Arch: only the full upgrade is supported (no partial upgrades); it brings the new `pkg`
        return {"arch": "sudo pacman -Syu",
                "debian": f"sudo apt update && sudo apt install --only-upgrade {pkg}",
                "fedora": f"sudo dnf upgrade {pkg}", "suse": f"sudo zypper update {pkg}"}.get(family, "")
    if pip_name:
        return f"python3 -m pip install --user --upgrade {pip_name}"
    return ""


def candidate(kind: str, key: str, title: str, current: str, latest: str, *, installable: bool = False,
              note: str = "", size: int = 0, **spec) -> updates.Candidate:
    return updates.Candidate(kind, key, title, current or "?", latest or "?", installable, note, size, spec)
