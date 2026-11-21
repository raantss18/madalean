"""Install / repair / roll back the components of `manifest.toml` inside MADALEAN_HOME.

Every install follows the same discipline (ARCHITECTURE §16, §18): download with resume into `downloads/` →
SHA-256 (and size) checked against the manifest → safe extraction into a NEW versioned directory → check that it
runs → atomic switch of the `current` symlink (os.replace) → the previous version is kept for `rollback`, older ones
are deleted. A failure before the switch leaves the running version untouched.

Progress: `progress(event)` with event = {"component", "phase", "done", "total", "message"} (phases: download,
verify, extract, create, link, check, switch, done, error) — the server forwards them as `deps.progress` events.

Nothing here uses sudo, a system package manager, ~/.elan, /opt/miniforge or the system Python packages."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from . import (component_dir, downloads_dir, elan_home, env_dir, fontconfig_file, home, manifest, sage_env_dir,
               state_file, tectonic_cache, tex_files_dir, tool)

Progress = Callable[[dict], None]
UA = {"User-Agent": "madalean-installer"}
ROOT = Path(__file__).resolve().parents[2]          # source tree (for net/ and dist/ when installing from a checkout)


class InstallError(Exception):
    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key, self.detail = key, detail


def _noop(_e: dict) -> None:
    pass


def _emit(progress: Progress, comp: str, phase: str, done: int = 0, total: int = 0, message: str = "") -> None:
    try:
        progress({"component": comp, "phase": phase, "done": done, "total": total, "message": message})
    except Exception:  # noqa: BLE001 (a broken listener never breaks an install)
        pass


# ---------------------------------------------------------------- state
def load_state() -> dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st: dict) -> None:
    p = state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".deps-state.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def _record(name: str, **info) -> dict:
    st = load_state()
    prev = st.get(name, {})
    entry = {**info, "installed_at": time.time()}
    if prev.get("path") and prev.get("path") != info.get("path"):
        entry["previous"] = {k: prev[k] for k in ("version", "path", "sha256", "variant") if k in prev}
    elif prev.get("previous"):
        entry["previous"] = prev["previous"]
    st[name] = entry
    save_state(st)
    return entry


# ---------------------------------------------------------------- download
def fetch(url: str, sha256: str, size: int = 0, progress: Progress = _noop, comp: str = "", name: str = "",
          offline_dirs: list[Path] | tuple = (), offline: bool = False, timeout: float = 60) -> Path:
    """Verified file in downloads/ (resumed with HTTP Range when a .part exists). Looks first in `offline_dirs`
    (an export made by export_offline.sh) for a file with the same name and hash."""
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
        raise InstallError("no_hash", f"{comp}: the manifest has no SHA-256 for {url}")
    name = name or url.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[A-Za-z0-9._+-]{1,200}", name):
        raise InstallError("bad_name", name)
    dl = downloads_dir()
    dl.mkdir(parents=True, exist_ok=True)
    dest = dl / name
    if dest.exists():
        if manifest.sha256_file(dest) == sha256:
            return dest
        dest.unlink()
    for d in offline_dirs:
        cand = Path(d) / name
        if cand.is_file() and manifest.sha256_file(cand) == sha256:
            shutil.copyfile(cand, dest)
            return dest
    if offline:
        raise InstallError("offline_missing", name)
    part = dl / (name + ".part")
    for attempt in range(4):
        have = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(url, headers={**UA, **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if have and r.status != 206:
                    have = 0                                  # server ignored the Range: start again
                total = size or (have + int(r.headers.get("Content-Length") or 0))
                with open(part, "ab" if have else "wb") as f:
                    done, last = have, 0.0
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        f.write(b)
                        done += len(b)
                        if size and done > size:
                            raise InstallError("too_big", f"{name}: more than {size} bytes")
                        if time.monotonic() - last > 0.5:
                            _emit(progress, comp, "download", done, total, name)
                            last = time.monotonic()
            break
        except InstallError:
            part.unlink(missing_ok=True)
            raise
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if attempt == 3:
                raise InstallError("download", f"{name}: {e}") from e
            time.sleep(2 * (attempt + 1))
    _emit(progress, comp, "verify", 0, 0, name)
    got = manifest.sha256_file(part)
    if got != sha256 or (size and part.stat().st_size != size):
        part.unlink(missing_ok=True)
        raise InstallError("bad_hash", f"{name}: sha256 {got} != {sha256}")
    os.replace(part, dest)
    return dest


# ---------------------------------------------------------------- extraction
def safe_extract(archive: Path, dest: Path, keep: list[str] | None = None, strip_single_top: bool = True) -> Path:
    """Extract a .tar.* or .zip into `dest` (must not exist). Refuses absolute paths, `..`, devices and links that
    leave the tree. `keep`: only these member paths. A single top-level directory is stripped."""
    dest.mkdir(parents=True)
    names = str(archive.name)
    if names.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for m in z.infolist():
                p = Path(m.filename)
                if p.is_absolute() or ".." in p.parts:
                    raise InstallError("bad_archive", m.filename)
                if keep is not None and m.filename not in keep:
                    continue
                if m.is_dir():
                    continue
                target = dest / (p.name if keep is not None else p)
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    else:
        with tarfile.open(archive, "r:*") as t:
            members = []
            for m in t.getmembers():
                p = Path(m.name)
                if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir() or m.issym() or m.islnk()):
                    raise InstallError("bad_archive", m.name)
                if keep is not None and m.name not in keep:
                    continue
                members.append(m)
            t.extractall(dest, members=members, filter="data")   # "data" filter: links must stay inside dest
    if strip_single_top:
        tops = list(dest.iterdir())
        if len(tops) == 1 and tops[0].is_dir():
            tmp = dest.with_name(dest.name + ".strip")
            tops[0].rename(tmp)
            dest.rmdir()
            tmp.rename(dest)
    return dest


def merge_extract(archive: Path, dest: Path) -> None:
    """Extract an additional archive (CUDA runtime) into an existing directory, same checks."""
    tmp = dest.with_name(dest.name + ".extra")
    shutil.rmtree(tmp, ignore_errors=True)
    safe_extract(archive, tmp)
    for p in tmp.iterdir():
        target = dest / p.name
        if not target.exists() and not target.is_symlink():
            p.rename(target)
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- atomic switch
def switch_link(link: Path, target: Path) -> None:
    """Point `link` at `target` atomically (relative symlink, os.replace)."""
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.with_name(f".{link.name}.new")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(os.path.relpath(target, link.parent), tmp)
    os.replace(tmp, link)


def _prune(parent: Path, keep: set[Path], pattern: str = "*") -> list[str]:
    removed = []
    for p in parent.glob(pattern):
        if p.is_symlink() or p.name.startswith(".") or p.resolve() in {k.resolve() for k in keep}:
            continue
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            removed.append(p.name)
    return removed


def _switch_component(name: str, new_dir: Path) -> None:
    link = home() / "components" / name / "current"
    prev = link.resolve() if link.is_symlink() else None
    switch_link(link, new_dir)
    keep = {new_dir} | ({prev} if prev else set())
    _prune(link.parent, keep)


def rollback(name: str) -> dict:
    """Switch a component back to the version it had before its last install."""
    st = load_state()
    e = st.get(name) or {}
    prev = e.get("previous") or {}
    path = Path(prev.get("path", ""))
    if not prev or not path.exists():
        raise InstallError("no_previous", name)
    if name in ("env", "sage"):
        switch_link(env_dir() if name == "env" else sage_env_dir(), path)
    else:
        switch_link(home() / "components" / name / "current", path)
    cur = {k: e[k] for k in ("version", "path", "sha256", "variant") if k in e}
    st[name] = {**prev, "installed_at": time.time(), "previous": cur, "rolled_back": True}
    save_state(st)
    return st[name]


def _run(cmd: list[str], comp: str, env: dict | None = None, timeout: float = 3600, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InstallError("run", f"{comp}: {cmd[0]}: {e}") from e
    if r.returncode != 0:
        raise InstallError("run", f"{comp}: {' '.join(Path(cmd[0]).name for _ in [0])} rc={r.returncode}: "
                                  f"{(r.stdout + r.stderr)[-1500:]}")
    return r.stdout + r.stderr


def clean_env(extra: dict | None = None) -> dict:
    """Environment for children of the installer: no conda/mamba/python variables of the caller (the system
    miniforge must never leak in), no user site-packages."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CONDA", "MAMBA", "PYTHON", "VIRTUAL_ENV", "_CE_", "PIP_"))}
    env["PYTHONNOUSERSITE"] = "1"
    env.update(extra or {})
    return env


# ---------------------------------------------------------------- component installers
def _versioned_dir(name: str, version: str) -> Path:
    d = home() / "components" / name / version
    return d


def install_binary(name: str, c: dict, progress: Progress, offline_dirs=(), offline=False,
                   local_files: list[Path] | None = None) -> dict:
    src = None
    for lf in local_files or []:                  # e.g. dist/madalean-net/… built reproducibly from net/
        if lf.is_file() and manifest.sha256_file(lf) == c["sha256"]:
            src = lf
            break
    if src is None:
        src = fetch(c["url"], c["sha256"], c.get("size", 0), progress, name, offline_dirs=offline_dirs,
                    offline=offline)
    d = _versioned_dir(name, c["version"])
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    out = tmp / c["file"]
    shutil.copyfile(src, out)
    out.chmod(0o755)
    _emit(progress, name, "check")
    _run([str(out), "--version" if name == "micromamba" else "version"], name, env=clean_env(), timeout=60)
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    _switch_component(name, d)
    return _record(name, version=c["version"], path=str(d), sha256=c["sha256"])


def install_fonts(c: dict, progress: Progress, offline_dirs=(), offline=False) -> dict:
    name = "fonts"
    d = _versioned_dir(name, c["version"])
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for a in c.get("assets", []):
        src = fetch(a["url"], a["sha256"], a.get("size", 0), progress, name, offline_dirs=offline_dirs,
                    offline=offline)
        part = tmp / a["name"]
        safe_extract(src, part, keep=list(a.get("keep") or []) or None, strip_single_top=False)
        for f in list(part.rglob("*")):                 # flatten: the font files directly in the version dir
            if f.is_file():
                target = tmp / (f.name if f.suffix in (".ttf", ".otf") else f"{a['name']}-{f.name}")
                os.replace(f, target)
        shutil.rmtree(part, ignore_errors=True)
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    _switch_component(name, d)
    write_fontconfig()
    return _record(name, version=c["version"], path=str(d),
                   sha256=",".join(a["sha256"][:16] for a in c.get("assets", [])))


def write_fontconfig() -> Path:
    """fonts.conf of the prefix: only the env's fonts and the prefix's own fonts (no /usr/share/fonts, so the PDF
    export is the same on every machine), the env's rendering rules (conf.d) and a cache inside the prefix."""
    f = fontconfig_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    h = home()
    text = ('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n<fontconfig>\n'
            f'  <dir>{h / "env" / "fonts"}</dir>\n  <dir>{h / "env" / "share" / "fonts"}</dir>\n'
            f'  <dir>{h / "components" / "fonts" / "current"}</dir>\n'
            f'  <include ignore_missing="yes">{h / "env" / "etc" / "fonts" / "conf.d"}</include>\n'
            f'  <cachedir>{h / "cache" / "fontconfig"}</cachedir>\n</fontconfig>\n')
    f.write_text(text, encoding="utf-8")
    return f


def install_elan(c: dict, progress: Progress, offline_dirs=(), offline=False) -> dict:
    name = "elan"
    src = fetch(c["url"], c["sha256"], c.get("size", 0), progress, name, offline_dirs=offline_dirs, offline=offline)
    d = _versioned_dir(name, c["version"])
    shutil.rmtree(d, ignore_errors=True)
    safe_extract(src, d, strip_single_top=False)
    init = d / "elan-init"
    init.chmod(0o755)
    eh = elan_home()
    eh.mkdir(parents=True, exist_ok=True)
    _emit(progress, name, "create", message="elan-init")
    # ELAN_HOME inside the prefix; --no-modify-path: no shell profile is edited; no default toolchain.
    _run([str(init), "-y", "--no-modify-path", "--default-toolchain", "none"], name,
         env=clean_env({"ELAN_HOME": str(eh)}), timeout=600)
    _run([str(eh / "bin" / "elan"), "--version"], name, env=clean_env({"ELAN_HOME": str(eh)}), timeout=60)
    _switch_component(name, d)
    return _record(name, version=c["version"], path=str(d), sha256=c["sha256"])


def cuda_driver_version() -> tuple[int, int] | None:
    smi = tool("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run([smi], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_cuda_version(out)


def parse_cuda_version(out: str) -> tuple[int, int] | None:
    """Highest CUDA version the driver supports, from nvidia-smi's banner ("CUDA Version: 13.5", or since the
    620 drivers "CUDA UMD Version: 13.5")."""
    m = re.search(r"CUDA (?:UMD )?Version:\s*(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


def pick_llama_variant(c: dict, want: str = "auto") -> str:
    variants = c.get("variants", {})
    if want != "auto":
        if want not in variants:
            raise InstallError("bad_variant", want)
        return want
    drv = cuda_driver_version()
    if drv:
        for v in ("cuda13", "cuda12"):
            mc = variants.get(v, {}).get("min_cuda")
            if mc and drv >= tuple(int(x) for x in mc.split(".")):
                return v
    return c.get("default_variant", "cpu")


def install_llama(c: dict, progress: Progress, variant: str = "auto", offline_dirs=(), offline=False) -> dict:
    name = "llama.cpp"
    v = pick_llama_variant(c, variant)
    vc = c["variants"][v]
    src = fetch(vc["url"], vc["sha256"], vc.get("size", 0), progress, name, offline_dirs=offline_dirs, offline=offline)
    extra = None
    if vc.get("extra_url"):
        extra = fetch(vc["extra_url"], vc["extra_sha256"], vc.get("extra_size", 0), progress, name,
                      offline_dirs=offline_dirs, offline=offline)
    d = _versioned_dir(name, f"{c['version']}-{v}")
    shutil.rmtree(d, ignore_errors=True)
    _emit(progress, name, "extract")
    safe_extract(src, d)
    if extra is not None:
        merge_extract(extra, d)
    exe = d / "llama-server"
    if not exe.exists():
        raise InstallError("layout", "llama-server missing in the archive")
    _emit(progress, name, "check")
    env = clean_env({"LD_LIBRARY_PATH": str(d), "CUDA_VISIBLE_DEVICES": ""})   # never touches the GPU here
    out = _run([str(exe), "--version"], name, env=env, timeout=60)
    _switch_component(name, d)
    return _record(name, version=c["version"], variant=v, path=str(d), sha256=vc["sha256"],
                   check=out.strip().splitlines()[-1][:200] if out.strip() else "")


def install_net(c: dict, progress: Progress, offline_dirs=(), offline=False, build: bool = False) -> dict:
    """Release asset, or the reproducible local build (dist/madalean-net, net/build.sh) when it has the pinned
    SHA-256. `build=True` builds from net/ with the local Go toolchain first (install time only)."""
    local = [Path(d) / "madalean-net-linux-amd64" for d in offline_dirs] + \
            [ROOT / "dist" / "madalean-net" / "madalean-net-linux-amd64"]
    if build and (ROOT / "net" / "build.sh").exists() and shutil.which("go"):
        _emit(progress, "madalean-net", "create", message="go build")
        _run(["bash", str(ROOT / "net" / "build.sh")], "madalean-net", timeout=1800)
    try:
        return install_binary("madalean-net", c, progress, offline_dirs, offline, local_files=local)
    except InstallError as e:
        if e.key in ("download", "offline_missing") and any(p.is_file() for p in local):
            raise InstallError("net_hash", "the local madalean-net build does not have the pinned SHA-256 "
                                           "(different Go version?) and the release asset is unreachable") from e
        raise


def _pkgs_dir() -> Path:
    return downloads_dir() / "pkgs"


def install_conda_env(name: str, c: dict, progress: Progress, offline_dirs=(), offline=False) -> dict:
    """micromamba create -p envs/<name>-<lockhash> from the lock (exact URLs + hashes), verify every installed
    package against the lock (conda-meta sha256), then switch env / envs/sage to it."""
    mm = tool("micromamba")
    if not mm or not mm.startswith(str(home())):
        raise InstallError("no_micromamba", "install the micromamba component first")
    lock = manifest.lock_path(c)
    lh = manifest.sha256_file(lock)
    if c.get("sha256") and lh != c["sha256"]:
        raise InstallError("bad_lock", f"{lock.name}: {lh} != manifest")
    pkgs = manifest.read_lock(lock)
    base = "main" if name == "env" else name
    target = home() / "envs" / f"{base}-{lh[:12]}"
    link = env_dir() if name == "env" else sage_env_dir()
    marker = target / ".madalean-complete"
    pk = _pkgs_dir()
    if not marker.exists() and (target / "conda-meta").is_dir() and not verify_env(target, pkgs):
        # created by install.sh's bootstrap (same lock, same micromamba): adopt it after verification
        marker.write_text(json.dumps({"lock": lh, "packages": len(pkgs), "download_bytes": env_bytes(target)}))
    if not marker.exists():
        shutil.rmtree(target, ignore_errors=True)
        pk = _pkgs_dir()
        pk.mkdir(parents=True, exist_ok=True)
        for d in offline_dirs:                      # pre-seed the package cache from an offline export
            od = Path(d) / "pkgs"
            if od.is_dir():
                shutil.copytree(od, pk, dirs_exist_ok=True)
        env = clean_env({"MAMBA_ROOT_PREFIX": str(home() / "mamba"), "CONDA_PKGS_DIRS": str(pk),
                         "MAMBA_NO_BANNER": "1"})
        # the conda-lock file name must end with "-lock.yml" for micromamba to read it as a lock
        tmp_lock = home() / "mamba" / f"{base}.conda-lock.yml"
        tmp_lock.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(lock, tmp_lock)
        cmd = [mm, "create", "-y", "--no-rc", "-p", str(target), "-f", str(tmp_lock)]
        if offline:
            cmd.append("--offline")
        stop = threading.Event()

        def watch():
            names = {p.filename for p in pkgs}
            while not stop.wait(1.0):
                done = len(names & cached_archives(pk))
                _emit(progress, name, "download", done, len(pkgs), f"{done}/{len(pkgs)} packages")
        th = threading.Thread(target=watch, daemon=True)
        th.start()
        try:
            _emit(progress, name, "create", 0, len(pkgs))
            _run(cmd, name, env=env, timeout=7200)
        except InstallError:
            shutil.rmtree(target, ignore_errors=True)
            raise
        finally:
            stop.set()
        _emit(progress, name, "verify", 0, len(pkgs))
        bad = verify_env(target, pkgs)
        if bad:
            shutil.rmtree(target, ignore_errors=True)
            raise InstallError("bad_env", "packages differ from the lock: " + ", ".join(bad[:10]))
        marker.write_text(json.dumps({"lock": lh, "packages": len(pkgs), "download_bytes": env_bytes(target)}))
    _emit(progress, name, "switch")
    prev = link.resolve() if link.is_symlink() else None
    switch_link(link, target)
    keep = {target} | ({prev} if prev else set())
    _prune(target.parent, keep, f"{base}-*")
    info = json.loads(marker.read_text())
    extra = {}
    if name == "env":
        write_fontconfig()
        if sage_env_dir().exists():
            register_sage_kernel()
    else:
        extra["kernel"] = str(register_sage_kernel())
    return _record(name, version=c["version"], path=str(target), sha256=lh, packages=info.get("packages"),
                   download_bytes=info.get("download_bytes"), **extra)


def cached_archives(pk: Path) -> set[str]:
    """File names of the package archives in micromamba's cache (layout pkgs/https/<host>/<channel>/<subdir>/)."""
    if not pk.is_dir():
        return set()
    return {f.name for pat in ("*.conda", "*.tar.bz2") for f in pk.rglob(pat)}


def env_bytes(target: Path) -> int:
    """Sum of the package archive sizes recorded in conda-meta (= bytes downloaded for this env)."""
    total = 0
    for f in (target / "conda-meta").glob("*.json"):
        try:
            total += int(json.loads(f.read_text(encoding="utf-8")).get("size") or 0)
        except (OSError, ValueError):
            pass
    return total


def verify_env(target: Path, pkgs: list) -> list[str]:
    """Names of lock packages whose installed record (conda-meta) is missing or has another SHA-256."""
    bad = []
    meta = target / "conda-meta"
    for p in pkgs:
        f = meta / (p.dist + ".json")
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bad.append(p.name + " (missing)")
            continue
        sha = rec.get("sha256") or ""
        if p.sha256 and sha and sha != p.sha256:
            bad.append(p.name)
        elif p.sha256 and not sha and rec.get("md5") and p.md5 and rec["md5"] != p.md5:
            bad.append(p.name)
    return bad


def register_sage_kernel() -> Path:
    """Kernelspec `sagemath` in the main env's share/jupyter/kernels (seen by JupyterLab and by the experiment
    bridge, which looks in sys.prefix), pointing at the Sage env's Python."""
    sage_py = sage_env_dir() / "bin" / "python3"
    if not sage_py.exists():
        raise InstallError("no_sage", "Sage env missing")
    d = env_dir() / "share" / "jupyter" / "kernels" / "sagemath"
    d.mkdir(parents=True, exist_ok=True)
    src = sage_env_dir() / "share" / "jupyter" / "kernels" / "sagemath"
    for f in ("logo-64x64.png", "logo.svg", "logo-svg.svg"):
        if (src / f).exists():
            shutil.copyfile(src / f, d / f)
    argv = [str(sage_py), "-m", "sage.repl.ipython_kernel", "-f", "{connection_file}"]
    setpriv = tool("setpriv")
    if setpriv:                     # the kernel dies with its jupyter-lab (which dies with the server)
        argv = [setpriv, "--pdeathsig", "KILL", "--", *argv]
    spec = {"argv": argv,
            "display_name": "SageMath 10.10", "language": "sage",
            "env": {"SAGE_ROOT": str(sage_env_dir()), "SAGE_LOCAL": str(sage_env_dir())},
            "metadata": {"madalean": True}}
    (d / "kernel.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return d


# ---------------------------------------------------------------- TeX bundle (tectonic)
def install_tex_bundle(c: dict, progress: Progress, offline=False) -> dict:
    """Warm the tectonic cache (inside the prefix) with every file Madalean's exports use, then extract the font
    files the export reads for glyph coverage. Afterwards exports run with --only-cached (offline)."""
    name = "tex-bundle"
    from . import activate
    activate()                       # FONTCONFIG_FILE / TECTONIC_CACHE_DIR for this process (texio runs fc-match)
    tec = tool("tectonic")
    if not tec or not tec.startswith(str(home())):
        raise InstallError("no_tectonic", "install the main env first")
    cache = tectonic_cache()
    cache.mkdir(parents=True, exist_ok=True)
    env = clean_env({"TECTONIC_CACHE_DIR": str(cache)})
    if fontconfig_file().exists():
        env["FONTCONFIG_FILE"] = str(fontconfig_file())
    # 1. the files the export reads directly (font coverage, bibliography style), from the pinned bundle
    out_dir = tex_files_dir()
    tmp_out = out_dir.with_name("files.tmp")
    shutil.rmtree(tmp_out, ignore_errors=True)
    tmp_out.mkdir(parents=True)
    for fn in c.get("extract", []):
        _emit(progress, name, "download", 0, 0, fn)
        data = subprocess.run([tec, "-X", "bundle", "cat", *(["--only-cached"] if offline else []), fn],
                              capture_output=True, env=env, timeout=600,
                              stdin=subprocess.DEVNULL, cwd=str(cache))
        if data.returncode != 0 or not data.stdout:
            raise InstallError("tex", f"cannot extract {fn}: {data.stderr.decode('utf-8', 'replace')[-300:]}")
        (tmp_out / fn).write_bytes(data.stdout)
    shutil.rmtree(out_dir, ignore_errors=True)
    tmp_out.rename(out_dir)
    from .. import texio
    texio.tex_font_file.cache_clear()
    texio.font_file.cache_clear()
    texio.fonts.cache_clear()
    # 2. compile Madalean's real export documents once: every package/font they use lands in the cache
    with tempfile.TemporaryDirectory(prefix="tex-warmup-", dir=str(home())) as td:
        n = 0
        for doc, files in warmup_documents():
            n += 1
            wd = Path(td) / f"d{n}"
            wd.mkdir()
            (wd / "doc.tex").write_text(doc, encoding="utf-8")
            for fn, content in files.items():
                (wd / fn).write_text(content, encoding="utf-8")
            _emit(progress, name, "download", n, 0, f"warm-up document {n}")
            cmd = [tec, "-X", "compile", "--untrusted", "--keep-logs", "--bundle", c["url"], "doc.tex"]
            if offline:
                cmd.insert(3, "--only-cached")
            _run(cmd, name, env=env, cwd=wd, timeout=1800)
            if not (wd / "doc.pdf").exists():
                raise InstallError("tex", f"warm-up document {n} produced no PDF")
    # the same documents must now compile with the cache only (offline guarantee)
    with tempfile.TemporaryDirectory(prefix="tex-offline-", dir=str(home())) as td:
        doc, files = warmup_documents()[0]
        wd = Path(td)
        (wd / "doc.tex").write_text(doc, encoding="utf-8")
        for fn, content in files.items():
            (wd / fn).write_text(content, encoding="utf-8")
        _run([tec, "-X", "compile", "--untrusted", "--only-cached", "--bundle", c["url"], "doc.tex"], name, env=env,
             cwd=wd, timeout=600)
    digest = bundle_digest(c["url"])
    if c.get("sha256") and digest != c["sha256"]:
        raise InstallError("bad_hash", f"TeX bundle digest {digest} != pinned {c['sha256']}")
    size = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file())
    return _record(name, version=c["version"], path=str(cache), sha256=digest, cache_bytes=size,
                   url=c["url"])


def bundle_digest(url: str) -> str:
    """Digest of the bundle as recorded by tectonic in its cache (hashes/<url with ':'→',58,' and '/'→',47,'>)."""
    enc = url.replace(":", ",58,").replace("/", ",47,")
    try:
        return (tectonic_cache() / "bundles" / "hashes" / enc).read_text().strip()
    except OSError:
        return ""


def warmup_documents() -> list[tuple[str, dict]]:
    """Real export documents (dossier PDF FR and EN with a bibliography) produced by Madalean's own export code."""
    from .. import export, texio
    texio.fonts.cache_clear()
    out = []
    for lang in ("fr", "en"):
        item = {"type": "book", "_key": "knuth", "title": "The TeXbook", "publisher": "Addison-Wesley",
                "author": [{"family": "Knuth", "given": "Donald E."}], "issued": {"date-parts": [[1984]]}}
        c = export.Content(
            title="Somme de deux pairs ∀ ℕ", kind="theorem", theorem="t",
            nl_statement="Soient $a, b \\in \\mathbb{N}$ pairs ; alors $a + b$ est pair [@knuth].",
            lean_statement="theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  sorry",
            notes="ℕ : entiers naturels — ∀ ∃ ≤ ≠ ⟨⟩ → ↔ ∘",
            informal="Écrivons $a = 2k$ et $b = 2m$ ; alors $a+b = 2(k+m)$, d'où le résultat.",
            informal_is_explanation=False,
            proof="theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) :=\n  Even.add ha hb",
            proved=True, stamp={"lean": "v4.9.0", "mathlib": "abc", "workspace": "demo", "axioms": ["propext"]},
            explanation="", date=__import__("datetime").date.today(), lang=lang, bib_keys=["knuth"],
            bib=[("knuth", item)])
        c.bib_backend = "bibtex"
        tex = export.build_tex(c, False, texio.fonts())
        out.append((tex, {"refs.bib": export.bib_file(c)}))
    from ..research.texproject import warmup_documents as article_documents   # S-R: article templates (offline)
    out += article_documents()
    return out


# ---------------------------------------------------------------- dispatcher
ORDER = ["micromamba", "env", "fonts", "tex-bundle", "elan", "llama.cpp", "madalean-net"]


def install(name: str, progress: Progress = _noop, variant: str = "auto", offline_dirs: list | tuple = (),
            offline: bool = False, build_net: bool = False) -> dict:
    c = manifest.component(name)
    _emit(progress, name, "start", message=c.get("title", name))
    try:
        if name == "micromamba":
            r = install_binary(name, c, progress, offline_dirs, offline)
        elif name in ("env", "sage"):
            r = install_conda_env(name, c, progress, offline_dirs, offline)
        elif name == "fonts":
            r = install_fonts(c, progress, offline_dirs, offline)
        elif name == "tex-bundle":
            r = install_tex_bundle(c, progress, offline)
        elif name == "elan":
            r = install_elan(c, progress, offline_dirs, offline)
        elif name == "llama.cpp":
            r = install_llama(c, progress, variant, offline_dirs, offline)
        elif name == "madalean-net":
            r = install_net(c, progress, offline_dirs, offline, build_net)
        else:
            raise InstallError("unknown", name)
    except InstallError as e:
        _emit(progress, name, "error", message=str(e)[:500])
        raise
    _emit(progress, name, "done", message=r.get("version", ""))
    return r


_ = component_dir
