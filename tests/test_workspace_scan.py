"""User Lean project discovery skips folders marked `.madalean-noscan` (Madalean's own checkout under ~/GitHub)."""
from __future__ import annotations

from madalean import workspaces


def _lake_project(d):
    (d / ".lake" / "packages" / "mathlib").mkdir(parents=True)
    (d / "lean-toolchain").write_text("leanprover/lean4:v4.9.0-rc1\n")
    (d / "lakefile.lean").write_text("import Lake\n")


def test_marker_hides_a_tree(tmp_path, monkeypatch):
    root = tmp_path / "GitHub"
    mine = root / "Maths" / "proj"
    theirs = root / "Madalean" / "madalean" / "workspaces" / "lean-prover49"
    _lake_project(mine.parent / "proj")
    _lake_project(theirs)
    (root / "Madalean" / workspaces.NOSCAN_MARKER).write_text("")
    monkeypatch.setattr(workspaces, "SCAN_ROOTS", [root])
    monkeypatch.setattr(workspaces.Workspace, "has_mathlib", lambda self: True)
    found = {w.path for w in workspaces.discover_user_workspaces()}
    assert mine in found and theirs not in found
