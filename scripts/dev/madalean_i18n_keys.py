#!/usr/bin/env python3
"""French source strings of the Madalean server that must exist in madalean/i18n_en.EN (tests/test_i18n.py).

Collected from calls `_(s)`, `msg(s)`, `Failed(s)`, `error(status, kind, s)`, `event(d, job, kind, s)`,
`ctx.toast(s)`, health checks `add(id, ok, s)`, and the STEPS / ROLE tables. The brain (madalean/brain, session S-B)
and the web UI keep their own catalogues."""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "madalean"
CALLS = {"_": 0, "msg": 0, "Failed": 0, "error": 2, "event": 3, "toast": 0, "add": 2}
SKIP_DIRS = {"brain", "static", "__pycache__"}
TABLES = {"updates_mgr.py": ("STEPS", "ROLE")}


def _consts(node) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return _consts(node.body) | _consts(node.orelse)
    if isinstance(node, ast.BoolOp):
        out = set()
        for v in node.values:
            out |= _consts(v)
        return out
    return set()


def keys() -> set[str]:
    out: set[str] = set()
    for f in ROOT.rglob("*.py"):
        if SKIP_DIRS & set(f.relative_to(ROOT).parts) or f.name in ("i18n_en.py", "i18n_mg.py"):
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if name in CALLS and len(n.args) > CALLS[name]:
                    out |= _consts(n.args[CALLS[name]])
            if isinstance(n, ast.Assign) and f.name in TABLES and isinstance(n.value, ast.Dict):
                if any(getattr(t, "id", "") in TABLES[f.name] for t in n.targets):
                    for v in n.value.values:
                        out |= _consts(v)
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict) and \
                    any(getattr(t, "id", "") == "keys" for t in n.targets):
                for v in n.value.values:
                    out |= _consts(v)
    # localized data tables of the core modules
    import sys
    sys.path.insert(0, str(ROOT.parent))
    from madalean import errors, examples, leancheck, texio
    for e in examples.EXAMPLES:
        out |= {e.title, e.level, e.blurb}
    for fr in errors.MESSAGES.values():
        out |= {fr.title} | ({fr.message} if fr.message else set()) | {a for a, _x in fr.actions}
    out |= {lab for _p, lab in leancheck.FORBIDDEN} | set(texio._LABELS.values())
    out |= {"Prouveur (Lean 4.9, Mathlib de Goedel)", "Lean actuel (Mathlib récent)",
            "Version exacte utilisée pour entraîner Goedel-Prover-V2 : meilleurs résultats du modèle.",
            "Lean et Mathlib récents, pour le travail quotidien et les cours."}
    return {k for k in out if k.strip() and any(c.isalpha() for c in k)}


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, str(ROOT.parent))
    from madalean.i18n_en import EN
    missing = sorted(keys() - set(EN))
    print(json.dumps(missing, ensure_ascii=False, indent=0))
    print(len(keys()), "keys,", len(missing), "missing", file=sys.stderr)
