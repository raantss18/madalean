"""Reuse of Lean workspaces that are already built on this machine (dev checkout, Lean AI Station 1.x) WITHOUT
depending on them at run time: the workspace and its toolchain are copied into the prefix as hard links (no extra
disk space, instant on the same file system; a real copy otherwise). The source is only read: ~/.elan and the old
checkout are never modified, and deleting them later does not break Madalean.

Safe because Madalean never writes into a workspace in place: checks compile temporary files, and updates build a
new `<name>.next` copy then switch (scripts/updater.py)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import elan_home, workspaces_dir


def toolchain_dirname(tc: str) -> str:
    return tc.strip().replace("/", "--").replace(":", "---")


def built(ws: Path) -> bool:
    for root in [ws, *sorted((ws / ".lake" / "packages").glob("*"))]:
        for lib in (root / ".lake" / "build" / "lib" / "lean", root / ".lake" / "build" / "lib"):
            if (lib / "Mathlib.olean").exists():
                return True
    return False


def _copy_tree(src: Path, dst: Path) -> str:
    """Hard-link copy (cp -al), else reflink/real copy. Returns the method used."""
    tmp = dst.with_name(dst.name + ".import")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["cp", "-al", "--", str(src), str(tmp)], capture_output=True, text=True)
    method = "hardlink"
    if r.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        r = subprocess.run(["cp", "-a", "--reflink=auto", "--", str(src), str(tmp)], capture_output=True, text=True)
        method = "copy"
        if r.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise OSError(r.stderr.strip()[-500:])
    os.replace(tmp, dst) if not dst.exists() else shutil.rmtree(tmp, ignore_errors=True)
    return method


def candidates(extra_roots: list[Path] | None = None) -> dict[str, Path]:
    """Built workspaces found in the known places (first found wins per name)."""
    home = Path.home()
    roots = list(extra_roots or []) + [home / "madalean" / "workspaces", home / "lean-ai-station" / "workspaces"]
    out: dict[str, Path] = {}
    for r in roots:
        for name in ("lean-current", "lean-prover49"):
            p = r / name
            if name not in out and (p / "lean-toolchain").exists() and built(p):
                out[name] = p
    return out


def import_workspace(src: Path, name: str, toolchains: Path | None = None) -> dict:
    """Bring `src` (a built workspace) and its Lean toolchain into the prefix. Idempotent."""
    dst = workspaces_dir() / name
    tc = (src / "lean-toolchain").read_text().strip()
    tcd = toolchain_dirname(tc)
    res = {"workspace": name, "source": str(src), "toolchain": tc}
    tc_dst = elan_home() / "toolchains" / tcd
    if not tc_dst.exists():
        tc_src = Path(toolchains or (Path.home() / ".elan" / "toolchains")) / tcd
        if not (tc_src / "bin" / "lean").exists():
            raise FileNotFoundError(f"toolchain {tc} not found in {tc_src.parent} (install it with elan)")
        res["toolchain_method"] = _copy_tree(tc_src, tc_dst)
    if dst.exists():
        res["method"] = "already"
        return res
    res["method"] = _copy_tree(src, dst)
    return res
