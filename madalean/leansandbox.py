"""Sandbox for every `lean` process that compiles untrusted text (DECISIONS D28, S-H review).

`leancheck.exec_risks` is a word-level deny list; the S-H review bypassed it (`attribute [command_elab …] f` then
`#check`, i.e. a user-defined elaborator registered without the `@[…]` syntax). A deny list over a language with
user-extensible syntax cannot be complete, so the gate is defence in depth and THIS is the boundary:

- bubblewrap (when installed): new user/mount/net/pid/ipc/uts namespaces (`--unshare-all`: no network at all, so
  no exfiltration and no request to Madalean's trusted local listener 127.0.0.1:11500), an empty root with only
  the system directories, the toolchain, the workspace (oleans) and the checked file mounted **read-only**, an
  empty `/tmp`, no home directory (config, keys, devices, sources, SSH keys… do not exist inside), `--die-with-parent`;
- environment rebuilt from an allow-list (no API key / token reaches Lean even without bubblewrap);
- without bubblewrap the check still runs (Lean is the product), unsandboxed: `status()` says so and the health
  page shows it (docs/SECURITY.md, accepted risk R-3)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ENV_ALLOW = ("PATH", "LANG", "LANGUAGE", "TZ", "LEAN_NUM_THREADS")
SYSTEM_DIRS = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/lib32", "/etc", "/opt", "/nix/store")
_BWRAP = {"path": None, "probed": False}


def bwrap() -> str | None:
    """Path of a working bubblewrap (probed once: user namespaces may be disabled by the kernel), else None."""
    if not _BWRAP["probed"]:
        _BWRAP["probed"] = True
        if os.environ.get("MADALEAN_LEAN_SANDBOX", "1") == "0":
            return None
        exe = shutil.which("bwrap")
        if exe:
            import subprocess
            try:
                r = subprocess.run([exe, "--unshare-all", "--die-with-parent", "--ro-bind", "/usr", "/usr",
                                    *_links(), "--", "/usr/bin/true"], capture_output=True, timeout=20)
                if r.returncode == 0:
                    _BWRAP["path"] = exe
            except (OSError, subprocess.SubprocessError):
                pass
    return _BWRAP["path"]


def status() -> dict:
    b = bwrap()
    return {"sandbox": "bwrap" if b else "none", "network": "blocked" if b else "allowed"}


def _links() -> list[str]:
    out = []
    for d in ("/bin", "/sbin", "/lib", "/lib64", "/lib32"):
        if os.path.islink(d):
            out += ["--symlink", os.readlink(d), d]
    return out


def lean_env(ws) -> dict[str, str]:
    e = {k: v for k, v in os.environ.items() if k in ENV_ALLOW or k.startswith("LC_")}
    e.update({k: v for k, v in ws.env().items() if k.startswith("LEAN") or k == "LD_LIBRARY_PATH"})
    e["HOME"] = "/nonexistent"
    e["TMPDIR"] = "/tmp"
    return e


def _ro(p: Path, seen: set[str], out: list[str]) -> None:
    for q in {str(p), str(Path(p).resolve())}:
        if q not in seen and os.path.exists(q):
            seen.add(q)
            out += ["--ro-bind", q, q]


def confine(argv: list[str], ro: list[Path], rw: list[Path], chdir: Path) -> list[str]:
    """Generic form (also used for TeX, export.py): system dirs + `ro` read-only, `rw` writable, nothing else of the
    home directory, no network. Returns `argv` unchanged without a working bubblewrap."""
    b = bwrap()
    if not b:
        return argv
    out = [b, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    out += _links()
    seen: set[str] = set()
    for d in SYSTEM_DIRS:
        if os.path.isdir(d) and not os.path.islink(d):
            _ro(Path(d), seen, out)
    for p in ro:
        _ro(Path(p), seen, out)
    for p in rw:
        for q in dict.fromkeys([str(p), str(Path(p).resolve())]):
            if os.path.exists(q):
                out += ["--bind", q, q]
    out += ["--chdir", str(chdir), "--"]
    return out + list(argv)


def wrap(ws, argv: list[str], files: list[Path]) -> list[str]:
    """`argv` (lean + args) wrapped in the sandbox; `files` = the .lean files given to Lean (mounted read-only)."""
    b = bwrap()
    if not b:
        return argv
    out = [b, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    out += _links()
    seen: set[str] = set()
    for d in SYSTEM_DIRS:
        if os.path.isdir(d) and not os.path.islink(d):
            _ro(Path(d), seen, out)
    if ws.sysroot:
        _ro(ws.sysroot, seen, out)
    _ro(Path(argv[0]).resolve().parent.parent, seen, out)
    _ro(ws.path, seen, out)
    for p in ws.lean_path():
        _ro(p, seen, out)
    for f in files:
        _ro(Path(f), seen, out)
    out += ["--chdir", str(ws.path), "--"]
    return out + list(argv)
