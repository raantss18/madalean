"""Extended update checkers (ARCHITECTURE §12) — session S-G. Plugged into the data-driven updates manager
(`madalean.updates.register_checker`, `madalean.updates.INSTALL_ARGS`); nothing of the manager is forked.

Checkers: Lean toolchains (elan), Lake packages of every managed workspace, llama.cpp (notify), Madalean releases
(notify + steps), the online catalogue (refresh), system components (SageMath, JupyterLab, ipykernel, TeX Live,
Poppler: notify + exact command for the detected distribution). In `mode = local` no checker touches the network.
Installable: `lake-package` (bump a user library of a managed workspace) and `lake-add` (add a library), both
through scripts/updater.py → installer.py (copy → build → verify incl. proven dossiers → switch → delete)."""
from __future__ import annotations

import json
import re
import weakref

from .. import updates
from ..i18n import _

_CTX: dict = {"ctx": None, "loop": None}


def current():
    ref = _CTX["ctx"]
    return (ref() if ref is not None else None), _CTX["loop"]


def _guard_local(name: str, fn):
    def check():
        ctx, _loop = current()
        if ctx is not None and getattr(ctx.settings, "mode", "") == "local":
            return []                          # « local »: nothing leaves the machine
        return fn()
    check.__name__ = "check_" + re.sub(r"\W", "_", name)
    return check


def spec_file(ctx, c: updates.Candidate, op: str) -> str:
    from .recheck import proofs_of_workspace
    ws_key = c.spec.get("workspace", "")
    ws = ctx.workspace(ws_key)
    test = ""
    if ws is not None and ws.has_mathlib():
        test = "import Mathlib\n\nexample (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := Even.add ha hb\n"
    spec = {"workspace_path": c.spec.get("workspace_path"), "workspace_key": ws_key, "package": c.spec["package"],
            "rev": c.spec["to_rev"], "url": c.spec.get("url", ""), "test_lean": c.spec.get("test_lean", test),
            "proofs": proofs_of_workspace(ctx, ws_key)}
    d = ctx.paths.cache / "updates"
    d.mkdir(parents=True, exist_ok=True)
    f = d / (re.sub(r"[^\w.-]", "_", c.key) + ".json")
    f.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return str(f)


def _args_bump(c: updates.Candidate) -> list[str]:
    ctx, _loop = current()
    return ["bump-package", spec_file(ctx, c, "bump")]


def _args_add(c: updates.Candidate) -> list[str]:
    ctx, _loop = current()
    return ["add-library", spec_file(ctx, c, "add")]


def register(ctx, loop=None) -> None:
    from .lean import lake_checker, toolchain_checker
    from .system import catalogue_checker, llama_checker, madalean_checker, system_checker
    _CTX["ctx"], _CTX["loop"] = weakref.ref(ctx), loop
    updates.INSTALL_ARGS["lake-package"] = _args_bump
    updates.INSTALL_ARGS["lake-add"] = _args_add
    for name, fn in (("Lean (elan)", toolchain_checker()), ("Lake", lake_checker()), ("llama.cpp", llama_checker()),
                     ("Madalean", madalean_checker()), ("Système", system_checker())):
        updates.register_checker(name, _guard_local(name, fn))
    updates.register_checker("Catalogue", _guard_local("Catalogue", catalogue_checker(current)))


def add_library_candidate(ws, name: str, url: str, rev: str) -> updates.Candidate:
    """Synthetic installable candidate for « add a library to this workspace » (installed by the same manager)."""
    return updates.Candidate("lake-add", f"add:{ws.key}:{name}", _("Ajouter {name} à {ws}").format(name=name, ws=ws.key),
                             "—", rev, True, "", 0,
                             {"workspace": ws.key, "workspace_path": str(ws.path), "package": name, "url": url,
                              "to_rev": rev, "release_notes": url, "risk": _("Copie de l'espace de travail, "
                                                                            "compilation et vérification avant la "
                                                                            "bascule.")})
