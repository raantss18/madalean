"""Stable release asset names (S-AL, D44): manifest kinds/arches, site links never versioned."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_manifest_kinds_and_arches():
    m = _load(ROOT / "scripts" / "make_update_manifest.py", "make_update_manifest")
    assert m.kind_of("madalean-server.tar.gz") == "server" and m.kind_of("madalean-2.0.0.tar.gz") == "server"
    assert m.kind_of("Madalean-installer.run") == "installer"
    assert (m.kind_of("Madalean-x86_64.AppImage"), m.arch_of("Madalean-x86_64.AppImage")) == ("appimage", "x86_64")
    assert m.arch_of("Madalean-android.apk") == "universal"
    assert m.arch_of("Madalean-android-arm64-v8a.apk") == "arm64-v8a"
    assert m.arch_of("madalean-armeabi-v7a-release.apk") == "armeabi-v7a"


def test_site_links_use_latest_and_no_version():
    sys.path.insert(0, str(ROOT / "site"))
    try:
        from madasite import install
    finally:
        sys.path.pop(0)
    files = [{"name": "Madalean-installer.run"}, {"name": "madalean-2.0.0.tar.gz"}]
    assert install.asset_url("Madalean-installer.run", files) == (
        "https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run", True)
    assert install.asset_url("madalean-server.tar.gz", files) == (
        "https://github.com/raantss18/madalean/releases/latest", False)
    page = install._page("fr", {"version": "9.8.7", "date": "x", "files": files, "notes": {"fr": "n"}}, False,
                         bytes(32))
    assert "9.8.7" not in page and "releases/latest/download/Madalean-installer.run" in page
    assert "Serveur" in page and "Clients" in page
