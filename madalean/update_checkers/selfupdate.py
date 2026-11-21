"""Madalean self-update (ARCHITECTURE §16, like L Katta's src/maj.rs) — session S-G.

A release of raantss18/madalean publishes `madalean-<version>.tar.gz`, `SHA256SUMS` and `SHA256SUMS.sig` (the
Ed25519 signature of SHA256SUMS, base64, made by scripts/sign_release.sh with the private key kept OUTSIDE git in
`~/.config/madalean/release-keys/ed25519.pem`). The public key is embedded below: even with the GitHub account, nobody
can make an installed Madalean accept a file the key did not sign. A release without a valid signature is refused.

Install = download into a staging directory → verify the signature of SHA256SUMS → verify the archive's SHA-256 →
safe extraction into `<root>/versions/<version>` → health check (the new version is started with `serve --demo` on
spare ports with a throw-away config dir, `/api/hello` must answer its version) → atomic switch of the symlink
`<root>/current` → the previous version is kept for rollback → restart through the systemd user unit when no job
runs. Any failure leaves the running version untouched.

Ed25519 verification: `cryptography` when importable, else the pure-Python RFC 8032 verifier below (no dependency
is required at run time; signing uses openssl in scripts/sign_release.sh)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

from .. import __version__, config

REPO = "raantss18/madalean"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
# Signed update channel (ARCHITECTURE §17): checked first (cheap); the Releases API is the fallback when unreachable.
MANIFEST_URL = "https://raantss18.github.io/madalean/updates/stable.json"
# Public half of ~/.config/madalean/release-keys/ed25519.pem (generated 2026-11-21, private key never in git).
PUBLIC_KEY = bytes.fromhex("8a3380f9e8e51c7e954760ddb25e3b646b87c941749367fb0b1796a7540ca690")
MAX_DOWNLOAD = 300 * 1024 * 1024


class UpdateError(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(detail or kind)
        self.kind, self.detail = kind, detail


# ---------------------------------------------------------------- Ed25519 (RFC 8032 §5.1.7 verification)
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _xrecover(y: int, sign: int) -> int | None:
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P:
        x = x * _I % _P
    if (x * x - xx) % _P:
        return None
    if x & 1 != sign:
        x = _P - x
    return x


def _add(a, b):
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    aa = (y1 - x1) * (y2 - x2) % _P
    bb = (y1 + x1) * (y2 + x2) % _P
    c = t1 * 2 * _D * t2 % _P
    dd = z1 * 2 * z2 % _P
    e, f, g, h = bb - aa, dd - c, dd + c, bb + aa
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(s: int, p):
    q = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _decode_point(b: bytes):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _P:
        return None
    x = _xrecover(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _encode(p) -> bytes:
    x, y, z, _t = p
    zi = pow(z, _P - 2, _P)
    x, y = x * zi % _P, y * zi % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


_BY = 4 * pow(5, _P - 2, _P) % _P
_B = (_xrecover(_BY, 0), _BY, 1, _xrecover(_BY, 0) * _BY % _P)


def ed25519_verify_pure(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(sig) != 64 or len(pub) != 32:
        return False
    a = _decode_point(pub)
    r = _decode_point(sig[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _encode(_mul(s, _B)) == _encode(_add(r, _mul(h, a)))


def ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return ed25519_verify_pure(pub, msg, sig)
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except (InvalidSignature, ValueError):
        return False


def signature_valid(pub: bytes, sums: bytes, sig_b64: str) -> bool:
    try:
        sig = base64.b64decode("".join(sig_b64.split()), validate=True)
    except (ValueError, TypeError):
        return False
    return ed25519_verify(pub, sums, sig)


def expected_sha(sums: str, name: str) -> str | None:
    for ln in sums.splitlines():
        parts = ln.split(None, 1)
        if len(parts) == 2 and parts[1].strip().lstrip("*") == name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return None


def vtuple(v: str) -> tuple:
    base, _, dev = v.lstrip("v").partition(".dev")
    nums = tuple(int(x) for x in re.findall(r"\d+", base))
    return nums + ((-1, int(dev or 0)) if dev or ".dev" in v else (0, 0))


def newer(remote: str, local: str) -> bool:
    return vtuple(remote) > vtuple(local)


# ---------------------------------------------------------------- release discovery / download
def _open(url: str, timeout: float = 60):
    if not (url.startswith("https://") or url.startswith("http://127.0.0.1")):
        raise UpdateError("bad_url", url[:120])
    req = urllib.request.Request(url, headers={"User-Agent": f"madalean/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def latest_release(api: str = RELEASES_API, current: str = __version__) -> dict | None:
    with _open(api, 30) as r:
        v = json.loads(r.read(2_000_000))
    tag = str(v.get("tag_name") or "")
    if not tag or not newer(tag, current):
        return None
    assets = {a.get("name"): a.get("browser_download_url") for a in v.get("assets") or [] if isinstance(a, dict)}
    ver = tag.lstrip("v")
    archive = next((n for n in assets if n == f"madalean-{ver}.tar.gz"), None)
    out = {"version": ver, "tag": tag, "notes": str(v.get("body") or "")[:20000], "page": v.get("html_url", ""),
           "archive": assets.get(archive) if archive else "", "archive_name": archive or "",
           "sums": assets.get("SHA256SUMS", ""), "sig": assets.get("SHA256SUMS.sig", ""),
           "signed": "SHA256SUMS.sig" in assets}
    return out


def manifest_release(url: str = MANIFEST_URL, public_key: bytes = PUBLIC_KEY, current: str = __version__) -> dict | None:
    """The signed manifest `stable.json` + `stable.json.sig` (Ed25519 over the exact bytes). Raises OSError when the
    channel is unreachable (→ fallback), UpdateError when it is reachable but not trustworthy (→ refusal)."""
    with _open(url, 20) as r:
        raw = r.read(1_000_000)
    with _open(url + ".sig", 20) as r:
        sig = r.read(10_000).decode("ascii", "replace")
    if not signature_valid(public_key, raw, sig):
        raise UpdateError("bad_signature", "stable.json signature refused")
    try:
        m = json.loads(raw)
    except ValueError as e:
        raise UpdateError("bad_manifest", str(e)) from e
    if not isinstance(m, dict):
        raise UpdateError("bad_manifest", "not an object")
    # Same order as the shells (docs/SHELLS.md "Updates"): signature → channel → strictly newer → https-only file →
    # size → SHA-256. The signed `channel` must name the requested file, so a test-channel manifest is never accepted.
    want_channel = url.rsplit("/", 1)[-1].removesuffix(".json")
    if m.get("channel") != want_channel:
        raise UpdateError("bad_channel", f"{m.get('channel')!r} != {want_channel!r}")
    ver = str(m.get("version") or "")
    if not ver or not newer(ver, current):
        return None
    srv = next((f for f in m.get("files") or [] if isinstance(f, dict) and f.get("kind") == "server"), None)
    if srv is None or not re.fullmatch(r"[0-9a-f]{64}", str(srv.get("sha256", ""))):
        raise UpdateError("no_archive", ver)
    surl = str(srv.get("url", ""))
    if not (surl.startswith("https://") or surl.startswith("http://127.0.0.1")):   # loopback: tests only
        raise UpdateError("bad_url", surl[:120])
    try:
        size = int(srv.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if not 0 < size <= MAX_DOWNLOAD:
        raise UpdateError("bad_manifest", "size")
    min_v = str(m.get("min_version") or "")
    return {"version": ver.lstrip("v"), "tag": "v" + ver.lstrip("v"), "notes": "", "page": m.get("notes_url", ""),
            "archive": srv.get("url", ""), "archive_name": srv.get("name", ""), "sha256": srv["sha256"],
            "size": size, "sums": "", "sig": "", "signed": True, "source": "manifest",
            "published": m.get("published", ""), "min_version": min_v,
            "manual": bool(min_v) and newer(min_v, current)}


def download(url: str, dest: Path) -> None:
    with _open(url, 120) as r, open(dest, "wb") as f:
        total = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            total += len(b)
            if total > MAX_DOWNLOAD:
                raise UpdateError("too_large")
            f.write(b)


def safe_extract(tar_path: Path, dest: Path) -> Path:
    """Extract without absolute paths, `..`, devices or links leaving the tree. Returns the top directory."""
    dest.mkdir(parents=True)
    with tarfile.open(tar_path, "r:gz") as t:
        members = t.getmembers()
        for m in members:
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
                raise UpdateError("bad_archive", m.name)
        t.extractall(dest, members=members, filter="data")
    tops = [p for p in dest.iterdir()]
    return tops[0] if len(tops) == 1 and tops[0].is_dir() else dest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def health_check(app_dir: Path, version: str, timeout: float = 60) -> None:
    """Start the new version in demo mode on spare ports (throw-away config) and ask /api/hello."""
    import tempfile
    port, rport = _free_port(), _free_port()
    with tempfile.TemporaryDirectory(prefix="madalean-health-") as td:
        env = {k: v for k, v in os.environ.items() if not k.startswith("MADALEAN_")}
        env.update({"PYTHONPATH": str(app_dir), "MADALEAN_NO_UPDATE_CHECK": "1", "MADALEAN_NO_KEYRING": "1",
                    "MADALEAN_DIR": str(app_dir)})
        p = subprocess.Popen([sys.executable, "-m", "madalean", "serve", "--demo", "--port", str(port),
                              "--remote-port", str(rport), "--config-dir", f"{td}/config", "--cache-dir", f"{td}/cache"],
                             cwd=str(app_dir), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             start_new_session=True)
        try:
            t0 = time.monotonic()
            while time.monotonic() - t0 < timeout:
                if p.poll() is not None:
                    raise UpdateError("health", (p.stderr.read() or b"").decode("utf-8", "replace")[-800:])
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/hello", timeout=2) as r:
                        hello = json.loads(r.read())
                    if hello.get("name") == "madalean" and hello.get("version") == version:
                        return
                    raise UpdateError("health", f"version {hello.get('version')} != {version}")
                except (OSError, ValueError):
                    time.sleep(0.3)
            raise UpdateError("health", "timeout")
        finally:
            try:
                os.killpg(p.pid, 15)
                p.wait(10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(p.pid, 9)
                except ProcessLookupError:
                    pass


# ---------------------------------------------------------------- manager
class SelfUpdater:
    def __init__(self, root: Path | None = None, api: str = RELEASES_API, public_key: bytes = PUBLIC_KEY,
                 current: str = __version__, restart_cmd: list[str] | None = None, manifest: str = MANIFEST_URL):
        self.root = Path(root or (Path.home() / ".local" / "share" / "madalean"))
        self.api, self.public_key, self.current_version = api, public_key, current
        self.manifest = manifest
        self.restart_cmd = restart_cmd if restart_cmd is not None else ["systemctl", "--user", "restart",
                                                                        "madalean.service"]
        self.state_file = self.root / "selfupdate.json"
        self.state = config.read_json(self.state_file)[0] or {}
        self.busy = False

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        config.atomic_write_text(self.state_file, json.dumps(self.state, indent=1))

    @property
    def versions_dir(self) -> Path:
        return self.root / "versions"

    @property
    def current_link(self) -> Path:
        return self.root / "current"

    def status(self) -> dict:
        link = os.readlink(self.current_link) if self.current_link.is_symlink() else ""
        return {"version": self.current_version, "installed": Path(link).name if link else "",
                "previous": self.state.get("previous", ""), "available": self.state.get("available"),
                "last": self.state.get("last"), "busy": self.busy, "pending_restart": self.state.get("pending_restart",
                                                                                                    False),
                "versions": sorted(p.name for p in self.versions_dir.iterdir()) if self.versions_dir.is_dir() else []}

    def check(self) -> dict | None:
        rel = None
        try:
            rel = manifest_release(self.manifest, self.public_key, self.current_version) if self.manifest else None
            source_ok = bool(self.manifest)
        except OSError:                                  # channel unreachable: GitHub Releases API
            source_ok = False
        if not source_ok:
            rel = latest_release(self.api, self.current_version)
        self.state["available"] = rel
        self.state["checked"] = time.time()
        self._save()
        return rel

    def install(self, rel: dict | None = None, health: bool = True) -> dict:
        """Blocking (run in a thread). Returns {version, dir}; raises UpdateError (nothing changed)."""
        rel = rel or self.state.get("available") or self.check()
        if not rel:
            raise UpdateError("up_to_date")
        if rel.get("manual"):
            raise UpdateError("manual", f"needs version {rel.get('min_version')} first")
        manifest = rel.get("source") == "manifest"
        if not manifest and not rel.get("sig"):
            raise UpdateError("unsigned", f"{rel.get('tag')} has no SHA256SUMS.sig")
        if not rel.get("archive") or (not manifest and not rel.get("sums")):
            raise UpdateError("no_archive", str(rel.get("tag")))
        ver = rel["version"]
        if not re.fullmatch(r"\d+(\.\d+)*(\.dev\d+)?", ver):
            raise UpdateError("bad_version", ver)
        self.busy = True
        stage = self.root / "staging"
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)
        target = self.versions_dir / ver
        try:
            name = rel["archive_name"]
            if not re.fullmatch(r"madalean-[\w.]+\.tar\.gz", name or ""):
                raise UpdateError("bad_archive", str(name))
            download(rel["archive"], stage / name)
            if manifest:
                if (stage / name).stat().st_size != int(rel.get("size") or 0):
                    raise UpdateError("bad_size", name)
                want = rel["sha256"]                     # from the signed manifest (verified in check)
            else:
                download(rel["sums"], stage / "SHA256SUMS")
                download(rel["sig"], stage / "SHA256SUMS.sig")
                sums = (stage / "SHA256SUMS").read_bytes()
                if not signature_valid(self.public_key, sums,
                                       (stage / "SHA256SUMS.sig").read_text("ascii", "replace")):
                    raise UpdateError("bad_signature", "SHA256SUMS signature refused")
                want = expected_sha(sums.decode("utf-8", "replace"), name)
            got = hashlib.sha256((stage / name).read_bytes()).hexdigest()
            if want is None or want != got:
                raise UpdateError("bad_checksum", name)
            shutil.rmtree(target, ignore_errors=True)
            tmp_target = self.versions_dir / f".{ver}.tmp"
            shutil.rmtree(tmp_target, ignore_errors=True)
            top = safe_extract(stage / name, tmp_target)
            if not (top / "madalean" / "__init__.py").is_file():
                raise UpdateError("bad_archive", "no madalean package")
            if health:
                health_check(top, ver)
            top.rename(target) if top != tmp_target else tmp_target.rename(target)
            shutil.rmtree(tmp_target, ignore_errors=True)
            prev = os.readlink(self.current_link) if self.current_link.is_symlink() else ""
            new_link = self.root / ".current.new"
            if new_link.is_symlink() or new_link.exists():
                new_link.unlink()
            os.symlink(target, new_link)
            os.replace(new_link, self.current_link)          # atomic switch
            self.state.update({"previous": prev, "pending_restart": True,
                               "last": {"ok": True, "version": ver, "t": time.time()}})
            self._prune(keep={Path(prev).name if prev else "", ver})
            self._save()
            return {"version": ver, "dir": str(target), "previous": prev}
        except UpdateError as e:
            shutil.rmtree(self.versions_dir / f".{ver}.tmp", ignore_errors=True)
            self.state["last"] = {"ok": False, "version": ver, "error": e.kind, "detail": e.detail[:500],
                                  "t": time.time()}
            self._save()
            raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            self.busy = False

    def _prune(self, keep: set[str]) -> None:
        for p in self.versions_dir.iterdir() if self.versions_dir.is_dir() else []:
            if p.name not in keep and not p.name.startswith("."):
                shutil.rmtree(p, ignore_errors=True)

    def rollback(self) -> dict:
        prev = self.state.get("previous") or ""
        if not prev or not Path(prev).is_dir():
            raise UpdateError("no_previous")
        cur = os.readlink(self.current_link) if self.current_link.is_symlink() else ""
        new_link = self.root / ".current.new"
        if new_link.is_symlink():
            new_link.unlink()
        os.symlink(prev, new_link)
        os.replace(new_link, self.current_link)
        self.state.update({"previous": cur, "pending_restart": True,
                           "last": {"ok": True, "rollback": True, "version": Path(prev).name, "t": time.time()}})
        self._save()
        return {"version": Path(prev).name, "previous": cur}

    def restart(self) -> bool:
        """Restart through the systemd user unit (only meaningful when the unit runs `<root>/current`)."""
        if not self.restart_cmd:
            return False
        try:
            subprocess.Popen(self.restart_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return False
        self.state["pending_restart"] = False
        self._save()
        return True


async def install_async(su: SelfUpdater, rel: dict | None = None) -> dict:
    return await asyncio.to_thread(su.install, rel)
