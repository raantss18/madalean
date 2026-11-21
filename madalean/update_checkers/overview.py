"""« Composants suivis » (session S-V): one line per component the user asked to keep up to date — Lean, Mathlib,
SageMath, LaTeX (tectonic engine + its TeX bundle) — with the installed version, the newest one known from the last
check, whether it installs by itself (verify → switch → old version removed, rollback on failure) or is notify-only,
and the last / next check. Pure function of the updates state + local files: no network."""
from __future__ import annotations

from pathlib import Path

from .. import config, updates

TRACKED = ("lean", "mathlib", "sage", "latex", "tex-bundle")


def _toolchain(ws_root: Path) -> str:
    try:
        return (ws_root / "lean-current" / "lean-toolchain").read_text().strip().split(":")[-1]
    except OSError:
        return ""


def _health() -> dict[str, dict]:
    try:
        from ..deps import health
        return {h["component"]: h for h in health.components()}
    except Exception:  # noqa: BLE001 (no prefix / unreadable manifest: show what we can)
        return {}


def _env_version(pkg: str) -> str:
    try:
        from ..deps import manifest
        return manifest.lock_versions(manifest.component("env")).get(pkg, "")
    except Exception:  # noqa: BLE001
        return ""


def overview(state: dict, cands: list[updates.Candidate], *, ws_root: Path | None = None,
             health_rows: dict[str, dict] | None = None, enabled: bool = True) -> dict:
    ws_root = Path(ws_root or config.WORKSPACES_DIR)
    hr = _health() if health_rows is None else health_rows
    by = {c.key: c for c in cands}

    def first(*keys: str) -> updates.Candidate | None:
        return next((by[k] for k in keys if k in by), None)

    def row(id_: str, current: str, c: updates.Candidate | None, policy: str, **extra) -> dict:
        return {"id": id_, "current": current or "", "latest": (c.latest if c else "") or "",
                "pending": c is not None, "installable": bool(c and c.installable), "key": c.key if c else "",
                "policy": policy, **extra}

    sage = hr.get("sage", {})
    bundle = hr.get("tex-bundle", {})
    rows = [
        row("lean", _toolchain(ws_root), first("lean-toolchain"), "with_mathlib"),
        row("mathlib", updates.installed_mathlib(ws_root / "lean-current") or "", first("mathlib"), "auto"),
        row("sage", sage.get("version") or "", first("deps:sage", "deps-upstream:sage:sage"),
            "auto_pin", state_=sage.get("state", ""), pinned=sage.get("pinned", "")),
        row("latex", _env_version("tectonic"), first("deps:env", "deps-upstream:env:tectonic"), "auto_pin"),
        row("tex-bundle", bundle.get("version") or "", first("deps:tex-bundle", "deps-upstream:tex-bundle:tex-bundle"),
            "auto_pin", state_=bundle.get("state", ""), pinned=bundle.get("pinned", "")),
    ]
    for r in rows:
        if "state_" in r:
            r["state"] = r.pop("state_")
    t = float(state.get("t") or 0)
    return {"components": rows, "last_check": t or None,
            "next_check": (t + updates.CHECK_EVERY_S if t else None) if enabled else None,
            "every_days": updates.CHECK_EVERY_S // 86400}
