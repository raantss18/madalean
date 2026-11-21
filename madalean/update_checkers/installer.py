"""Generalised verify-then-switch for Lake packages of a managed workspace (run by scripts/updater.py, which prints
the progress protocol `STEP …`, `DONE <json>`, `FAIL <key> <detail>`).

    updater.py bump-package SPEC.json     bump package X to a new rev
    updater.py add-library  SPEC.json     add a user library (git https URL + rev) to the workspace

Steps: copy the workspace to `<ws>.next` (the old one is never touched before the switch) → edit the lakefile
→ `lake update X` → `lake build` → verify in the copy: the test file compiles, every proven dossier / library entry of
the workspace given in the spec is re-checked with the strict verdict (a regression stops the install) → switch
(`ws` → `ws.old`, `ws.next` → `ws`) → delete `ws.old`. Any failure before the switch deletes the copy only.

SPEC.json: {"workspace_path", "workspace_key", "package", "rev", "url"? (add), "test_lean"?, "proofs": [{name,
dossier, code}], "allow_file_urls"? (tests only), "lake"?, "timeout"?}"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import config, leancheck
from ..workspaces import Workspace
from .common import CheckError, git_env, safe_git_url


class Fail(Exception):
    def __init__(self, key: str, detail: str = ""):
        super().__init__(detail)
        self.key, self.detail = key, detail


def _noop(key: str, detail: str = "") -> None:
    pass


def dir_size(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def edit_lakefile(ws: Path, package: str, rev: str, url: str = "", add: bool = False) -> None:
    if not re.fullmatch(r"[\w.\-/+]{1,100}", rev) or not re.fullmatch(r"[A-Za-z_][\w\-]{0,60}", package):
        raise Fail("bad_spec", f"{package} {rev}")
    toml, lean = ws / "lakefile.toml", ws / "lakefile.lean"
    if toml.is_file():
        text = toml.read_text(encoding="utf-8")
        blocks = re.split(r"(?m)^(?=\[\[require\]\]\s*$)", text)
        found = False
        for i, b in enumerate(blocks):
            if b.startswith("[[require]]") and re.search(rf'(?m)^\s*name\s*=\s*"{re.escape(package)}"', b):
                found = True
                if add:
                    raise Fail("exists", package)
                if re.search(r'(?m)^\s*rev\s*=', b):
                    blocks[i] = re.sub(r'(?m)^(\s*rev\s*=\s*)"[^"]*"', rf'\g<1>"{rev}"', b, count=1)
                else:
                    blocks[i] = b.rstrip("\n") + f'\nrev = "{rev}"\n\n'
        if not found:
            if not add:
                raise Fail("not_required", package)
            blocks.append(f'\n[[require]]\nname = "{package}"\ngit = "{url}"\nrev = "{rev}"\n')
        toml.write_text("".join(blocks), encoding="utf-8")
    elif lean.is_file():
        text = lean.read_text(encoding="utf-8")
        pat = re.compile(rf'(?m)^(\s*require\s+[«"]?{re.escape(package)}[»"]?\s+from\s+git\s+"[^"]+")(\s*@\s*"[^"]*")?')
        if pat.search(text):
            if add:
                raise Fail("exists", package)
            text = pat.sub(lambda m: f'{m.group(1)} @ "{rev}"', text, count=1)
        else:
            if not add:
                raise Fail("not_required", package)
            text = text.rstrip("\n") + f'\n\nrequire {package} from git\n  "{url}" @ "{rev}"\n'
        lean.write_text(text, encoding="utf-8")
    else:
        raise Fail("no_lakefile", str(ws))


def _run(cmd: list[str], cwd: Path, key: str, env: dict, timeout: int) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as e:
        raise Fail(key, "timeout") from e
    out = (r.stdout + r.stderr)[-4000:]
    if r.returncode != 0:
        raise Fail(key, out.strip()[-1500:])
    return out


def verify(ws_dir: Path, toolchain: str, test_lean: str, proofs: list[dict], timeout: int = 600) -> list[dict]:
    """Compile the test file and re-check every proof (strict verdict) in the copy. Returns the regressions."""
    ws = Workspace("verify", "verify", ws_dir, toolchain, False)
    if not ws.lean_bin or not ws.lean_bin.exists():
        raise Fail("verify", f"Lean {toolchain} missing")
    regressions = []
    with tempfile.TemporaryDirectory() as td:
        if test_lean.strip():
            f = Path(td) / "Check.lean"
            f.write_text(test_lean, encoding="utf-8")
            r = subprocess.run([str(ws.lean_bin), "--json", str(f)], env=ws.env(), cwd=ws_dir, capture_output=True,
                               text=True, timeout=timeout)
            msgs = leancheck.parse_lean_json(r.stdout)
            if r.returncode != 0 or any(m.severity == "error" for m in msgs):
                raise Fail("verify", (r.stdout + r.stderr)[-1500:])
        for i, p in enumerate(proofs):
            name = p.get("name") or leancheck.theorem_name(p["code"])
            code = leancheck.with_axiom_probe(p["code"], name)
            f = Path(td) / f"P{i}.lean"
            f.write_text(code, encoding="utf-8")
            try:
                r = subprocess.run([str(ws.lean_bin), "--json", str(f)], env=ws.env(), cwd=ws_dir,
                                   capture_output=True, text=True, timeout=timeout)
                v = leancheck.judge(code, leancheck.parse_lean_json(r.stdout), name, r.returncode)
                ok, summary = v.ok, v.summary
            except subprocess.TimeoutExpired:
                ok, summary = False, "timeout"
            if not ok:
                regressions.append({"name": name, "dossier": p.get("dossier", ""), "summary": summary})
    return regressions


def install(spec: dict, step=_noop) -> dict:
    ws = Path(spec["workspace_path"]).resolve()
    managed = config.WORKSPACES_DIR.resolve()
    if not spec.get("allow_any_root") and managed not in ws.parents:
        raise Fail("not_managed", str(ws))           # user projects are read-only: never modified
    if not (ws / "lake-manifest.json").is_file():
        raise Fail("no_manifest", str(ws))
    add = spec.get("op") == "add"
    package, rev = spec["package"], spec["rev"]
    url = ""
    if add:
        try:
            url = safe_git_url(spec.get("url", ""), ("https", "file") if spec.get("allow_file_urls") else ("https",))
        except CheckError as e:
            raise Fail("bad_url", str(e)) from e
    nxt, old = ws.with_name(ws.name + ".next"), ws.with_name(ws.name + ".old")
    size = dir_size(ws)
    free = shutil.disk_usage(ws.parent).free
    if free < size * 1.1 + 1e9:
        raise Fail("disk", f"{free / 1e9:.1f} GB free, {size / 1e9:.1f} GB needed")
    lake = spec.get("lake") or str(config.ELAN_BIN / "lake")
    env = {**os.environ, **{k: v for k, v in git_env().items() if k not in ("PATH", "HOME")},
           "PATH": f"{config.ELAN_BIN}:{os.environ.get('PATH', '')}"}
    if spec.get("allow_file_urls"):
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"] = "protocol.file.allow", "always"
    timeout = int(spec.get("timeout") or 7200)
    toolchain = (ws / "lean-toolchain").read_text().strip()
    try:
        step("copy", ws.name)
        shutil.rmtree(nxt, ignore_errors=True)
        r = subprocess.run(["cp", "-a", "--reflink=auto", str(ws), str(nxt)], capture_output=True, text=True)
        if r.returncode != 0:
            raise Fail("copy", r.stderr[-500:])
        step("deps", package)
        edit_lakefile(nxt, package, rev, url, add)
        _run([lake, "update", package], nxt, "deps", env, timeout)
        step("build")
        _run([lake, "build"], nxt, "build", env, timeout)
        step("verify")
        regressions = verify(nxt, toolchain, spec.get("test_lean", ""), list(spec.get("proofs") or []))
        if regressions:
            raise Fail("regression", json.dumps(regressions, ensure_ascii=False)[:3000])
    except BaseException:
        shutil.rmtree(nxt, ignore_errors=True)       # failed before the switch: the workspace is untouched
        raise
    step("switch")
    shutil.rmtree(old, ignore_errors=True)
    ws.rename(old)
    nxt.rename(ws)
    step("cleanup")
    shutil.rmtree(old, ignore_errors=True)
    new_rev = ""
    try:
        for p in json.loads((ws / "lake-manifest.json").read_text()).get("packages", []):
            if p.get("name") == package:
                new_rev = p.get("rev", "")
    except (OSError, ValueError):
        pass
    return {"kind": "lake-package", "op": "add" if add else "bump", "workspace": spec.get("workspace_key", ws.name),
            "package": package, "rev": rev, "commit": new_rev, "checked": len(spec.get("proofs") or []),
            "removed": [f"{package} (old)"] if not add else []}


def main(argv: list[str], step=_noop) -> dict:
    """Entry point used by scripts/updater.py: argv = [op, SPEC.json]."""
    if len(argv) != 2:
        raise Fail("usage", " ".join(argv))
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    spec["op"] = "add" if argv[0] == "add-library" else "bump"
    return install(spec, step)
