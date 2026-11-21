#!/usr/bin/env python3
"""Build and sign the update channel manifest read by the shells (docs/SHELLS.md, "Update channel").

  scripts/make_update_manifest.py --version 2.0.1 --base-url https://github.com/raantss18/madalean/releases/download/v2.0.1 \
      [--channel stable] [--notes-url URL] [--min-version 2.0.0] [--out DIR] FILE...

Writes DIR/<channel>.json and DIR/<channel>.json.sig: base64 Ed25519 signature of the EXACT bytes of the JSON file,
made with the private release key kept outside git (~/.config/madalean/release-keys/ed25519.pem or
$MADALEAN_RELEASE_KEY) through `openssl pkeyutl -rawin` (same scheme as scripts/sign_release.sh). The signed
`channel` field must equal the file name the client requested (a manifest signed for a test channel is refused on
"stable"). kind: *.tar.gz → server, *.AppImage → appimage, *.apk → apk, else other; `arch` from the file name.

This is the ONE producer of the channel format (docs/SITE.md §3 = docs/SHELLS.md "Updates"); scripts/sign_release.sh
calls it. Readers: server self-update (madalean/update_checkers/selfupdate.py), AppImage, APK, site build.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys


def kind_of(name: str) -> str:
    low = name.lower()
    if low.endswith(".tar.gz"):
        return "server"
    if low.endswith(".appimage"):
        return "appimage"
    if low.endswith(".apk"):
        return "apk"
    return "other"


def arch_of(name: str) -> str:
    low = name.lower()
    for a in ("arm64-v8a", "armeabi-v7a", "x86_64", "universal"):
        if a in low:
            return a
    return "x86_64" if low.endswith(".appimage") else ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--version", required=True)
    p.add_argument("--base-url", required=True, help="URL prefix of the files (GitHub release download URL)")
    p.add_argument("--channel", default="stable")
    p.add_argument("--notes-url", default="")
    p.add_argument("--min-version", default="")
    p.add_argument("--published", default="")
    p.add_argument("--notes-fr", default="")
    p.add_argument("--notes-en", default="")
    p.add_argument("--apk-cert", default="", help="SHA-256 of the APK signing certificate (shown by the site)")
    p.add_argument("--sums", action="store_true", help="the release also publishes SHA256SUMS + .sig (sign_release.sh)")
    p.add_argument("--out", default=".")
    p.add_argument("--key", default=os.environ.get("MADALEAN_RELEASE_KEY",
                                                   str(pathlib.Path.home() / ".config/madalean/release-keys/ed25519.pem")))
    p.add_argument("--no-sign", action="store_true", help="write the manifest only (tests)")
    p.add_argument("files", nargs="+")
    a = p.parse_args()
    files = []
    base = a.base_url.rstrip("/")
    for f in a.files:
        path = pathlib.Path(f)
        if path.name.startswith("SHA256SUMS"):
            continue
        data = path.read_bytes()
        entry = {"kind": kind_of(path.name), "name": path.name, "url": base + "/" + path.name,
                 "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if arch_of(path.name):
            entry["arch"] = arch_of(path.name)
        files.append(entry)
    published = a.published or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    version = a.version.lstrip("v")
    manifest = {
        "schema": "madalean-updates/1",
        "channel": a.channel,
        "version": version,
        "tag": "v" + version,
        "date": published[:10],
        "published": published,
        "notes": {"fr": a.notes_fr, "en": a.notes_en},
        "notes_url": a.notes_url,
        "min_version": a.min_version,
        "files": files,
    }
    if a.sums:
        manifest["sums_url"] = base + "/SHA256SUMS"
        manifest["sums_sig_url"] = base + "/SHA256SUMS.sig"
    if a.apk_cert:
        manifest["apk_certificate_sha256"] = a.apk_cert
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jpath = out / f"{a.channel}.json"
    jpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.no_sign:
        print(jpath)
        return 0
    if not pathlib.Path(a.key).is_file():
        print(f"missing private key {a.key}", file=sys.stderr)
        return 1
    sig = subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", a.key, "-rawin", "-in", str(jpath)],
                         check=True, capture_output=True).stdout
    import base64
    (out / f"{a.channel}.json.sig").write_text(base64.b64encode(sig).decode() + "\n", encoding="ascii")
    print(jpath, out / f"{a.channel}.json.sig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
