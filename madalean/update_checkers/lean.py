"""Lean toolchains (elan) and every package of each managed workspace's lake-manifest.json.

Policy (ARCHITECTURE §12, existing rules kept):
- toolchains: notify only — a toolchain alone changes nothing; it comes with a Mathlib bump, and a toolchain is never
  removed while another project pins it (scripts/updater.py `toolchain_users`);
- `lean-current`: Mathlib keeps its own installer (key `mathlib`, scripts/updater.py install-mathlib); packages that
  Mathlib itself requires (batteries, aesop, Qq, …) move WITH Mathlib (notify only: bumping one alone would break
  Mathlib); libraries the user added to the workspace (direct requirements other than mathlib) are installable:
  bump in a COPY of the workspace, build, verify (test theorem + proven dossiers re-checked), switch, delete;
- `lean-prover49`: pinned on purpose (the exact Lean/Mathlib Goedel-Prover-V2 was trained on) — notify only;
- user projects found on disk are read-only: never checked for bumps."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import config
from ..i18n import _
from .common import CheckError, candidate, is_version, ls_remote, newer, newest_rc, newest_version

LEAN4_GIT = "https://github.com/leanprover/lean4"
PINNED = {"lean-prover49": "Épinglé volontairement : Goedel-Prover-V2 a été entraîné sur exactement cette version "
                           "de Lean et de Mathlib ; la changer dégraderait le prouveur."}


def managed_workspaces(root: Path | None = None) -> list[Path]:
    root = Path(root or config.WORKSPACES_DIR)
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "lake-manifest.json").is_file()
                  and not p.name.endswith((".next", ".old"))) if root.is_dir() else []


def read_manifest(ws: Path) -> list[dict]:
    try:
        data = json.loads((ws / "lake-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in data.get("packages", []) if isinstance(p, dict) and p.get("type", "git") == "git"]


def direct_requires(ws: Path) -> list[str]:
    names = []
    toml = ws / "lakefile.toml"
    lean = ws / "lakefile.lean"
    if toml.is_file():
        for block in re.split(r"(?m)^\[\[require\]\]\s*$", toml.read_text(encoding="utf-8"))[1:]:
            m = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', block.split("\n[", 1)[0])
            if m:
                names.append(m.group(1))
    elif lean.is_file():
        names = re.findall(r'(?m)^\s*require\s+[«"]?([\w\-]+)[»"]?\s+from', lean.read_text(encoding="utf-8"))
    return names


def dependents(ws: Path, pkg: str) -> list[str]:
    """Packages of the workspace that (transitively) require `pkg`, from each package's own manifest."""
    graph: dict[str, set[str]] = {}
    pk = ws / ".lake" / "packages"
    for p in (pk.iterdir() if pk.is_dir() else []):
        deps = {d.get("name") for d in read_manifest(p)}
        graph[p.name] = {d for d in deps if d}
    out, frontier = set(), {pkg}
    while frontier:
        nxt = {n for n, deps in graph.items() if deps & frontier and n not in out}
        out |= nxt
        frontier = nxt
    return sorted(out)


def release_notes(url: str, old: str, new: str, is_tag: bool) -> str:
    base = url[:-4] if url.endswith(".git") else url
    if "github.com" in base:
        return f"{base}/releases/tag/{new}" if is_tag else f"{base}/compare/{old[:12]}...{new[:12]}"
    return base


def package_candidates(ws: Path, *, allow_schemes=("https",), remote=None) -> tuple[list, list[str]]:
    """Candidates for every git package of one workspace manifest. `remote(url)` = ls_remote (injectable)."""
    remote = remote or (lambda u: ls_remote(u, allow_schemes))
    key = ws.name
    direct = set(direct_requires(ws))
    pkgs = read_manifest(ws)
    errors: list[str] = []
    out = []

    def one(p: dict):
        name, url, rev, inp = p.get("name", ""), p.get("url", ""), p.get("rev", ""), p.get("inputRev") or ""
        try:
            refs = remote(url)
        except CheckError as e:
            return None, f"{key}/{name}: {e}"
        if is_version(inp):
            latest = newest_version(refs["tags"], "v" if inp.startswith("v") else "")
            if not newer(latest, inp):
                return None, None
            to_rev, to_commit, is_tag, cur = latest, refs["tags"].get(latest, ""), True, inp
        elif inp and inp in refs["heads"]:
            head = refs["heads"][inp]
            if head == rev:
                return None, None
            to_rev, to_commit, is_tag, cur = inp, head, False, f"{inp}@{rev[:10]}"
        else:
            return None, None                               # pinned to a commit / unknown branch: nothing to say
        rebuild = dependents(ws, name)
        if key in PINNED:
            installable, note, risk = False, _(PINNED[key]), "pinned"
        elif name not in direct:
            installable = False
            note = (_("Dépendance de Mathlib : elle change avec Mathlib (mise à jour « Lean + Mathlib »), jamais seule.")
                    if "mathlib" in direct else _("Dépendance indirecte : mise à jour par le paquet qui la requiert."))
            risk = "transitive"
        elif name == "mathlib":
            return None, None                               # handled by the existing Mathlib installer
        else:
            installable, note = True, ""
            risk = _("Reconstruit : {names}").format(names=", ".join([name] + rebuild + [key]))
        latest_label = to_rev if is_tag else f"{to_rev}@{to_commit[:10]}"
        c = candidate("lake-package", f"lake:{key}:{name}", f"{name} ({key})", cur, latest_label,
                      installable=installable, note=note, workspace=key, workspace_path=str(ws), package=name,
                      url=url, from_rev=rev, to_rev=to_rev, to_commit=to_commit,
                      release_notes=release_notes(url, rev, to_rev if is_tag else to_commit, is_tag),
                      rebuild=rebuild + [key], risk=risk,
                      estimate={"download_mb": 50 if not rebuild else 500,
                                "minutes": 2 + 3 * len(rebuild), "copy_workspace": True})
        return c, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for c, err in pool.map(one, pkgs):
            if c is not None:
                out.append(c)
            if err:
                errors.append(err)
    return out, errors


def lake_checker(root: Path | None = None, allow_schemes=("https",), remote=None):
    def check():
        cands, errs = [], []
        for ws in managed_workspaces(root):
            c, e = package_candidates(ws, allow_schemes=allow_schemes, remote=remote)
            cands += c
            errs += e
        if errs and not cands:
            raise CheckError("; ".join(errs[:5]))
        return cands
    return check


# ---------------------------------------------------------------- toolchains
def installed_toolchains(elan_home: Path | None = None) -> list[str]:
    d = Path(elan_home or (Path.home() / ".elan")) / "toolchains"
    out = []
    for p in sorted(d.iterdir()) if d.is_dir() else []:
        m = re.fullmatch(r"leanprover--lean4---(.+)", p.name)
        if m:
            out.append(m.group(1))
    return out


def toolchain_users(root: Path | None = None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for ws in managed_workspaces(root):
        try:
            tc = (ws / "lean-toolchain").read_text().strip().split(":")[-1]
        except OSError:
            continue
        out.setdefault(tc, []).append(ws.name)
    return out


def toolchain_candidates(tags: list[str], installed: list[str], users: dict[str, list[str]]) -> list:
    stable, rc = newest_version(tags, "v"), newest_rc(tags)
    inst_stable = [t for t in installed if is_version(t)]
    best = max(inst_stable, key=lambda t: tuple(int(x) for x in re.findall(r"\d+", t))) if inst_stable else ""
    out = []
    if stable and (not best or newer(stable, best)):
        used = ", ".join(f"{t} ({', '.join(w)})" for t, w in sorted(users.items())) or "—"
        out.append(candidate("lean-toolchain", "lean-toolchain", f"Lean {stable}", best or "—", stable,
                             note=_("Notification seulement : une nouvelle version de Lean arrive avec la mise à jour "
                                    "de Mathlib. Un toolchain n'est jamais supprimé tant qu'un projet l'utilise."),
                             release_notes=f"https://github.com/leanprover/lean4/releases/tag/{stable}",
                             installed=installed, release_candidate=rc or "", used_by=used, risk="none",
                             command=f"elan toolchain install leanprover/lean4:{stable}"))
    return out


def toolchain_checker(root: Path | None = None, remote=None):
    def check():
        refs = (remote or (lambda u: ls_remote(u, patterns=("v4.*",))))(LEAN4_GIT)
        return toolchain_candidates(list(refs["tags"]), installed_toolchains(), toolchain_users(root))
    return check
