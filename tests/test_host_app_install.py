"""« Madalean Server » menu entry on the host (D50): scripts/install_host_app.sh with a fake PATH and a temporary
HOME / XDG_DATA_HOME (the real ~/.local/share/applications is never touched), install.sh --dry-run, the self-update
refresh hook, the graphical installer's « Ouvrir Madalean », the brand build."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_host_app.sh"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
BASIC = ("bash", "sh", "sed", "grep", "tr", "head", "mkdir", "install", "rm", "mv", "chmod", "cat", "dirname",
         "basename", "touch", "sort", "cut")


def toolbox(tmp: Path, *, ldd: str | None = "ok", browsers: tuple[str, ...] = ()) -> Path:
    """A PATH with only the basic tools, fake ldd / browsers / cache tools (they record their calls)."""
    b = tmp / "bin"
    b.mkdir(exist_ok=True)
    for t in BASIC:
        p = shutil.which(t)
        if p and not (b / t).exists():
            (b / t).symlink_to(p)

    def fake(name: str, body: str) -> None:
        (b / name).write_text(f"#!/bin/sh\necho \"{name} $*\" >> '{tmp}/calls.txt'\n{body}\n")
        (b / name).chmod(0o755)

    if ldd == "ok":
        fake("ldd", "echo '\tlibwebkit2gtk-4.1.so.0 => /usr/lib/libwebkit2gtk-4.1.so.0 (0x1)'")
    elif ldd == "missing":
        fake("ldd", "echo '\tlibwebkit2gtk-4.1.so.0 => not found'; echo '\tlibgtk-3.so.0 => not found'")
    for br in browsers:
        fake(br, "")
    for t in ("update-desktop-database", "gtk-update-icon-cache", "kbuildsycoca6"):
        fake(t, "")
    return b


def prefix(tmp: Path, *, binary: bool = True) -> Path:
    pfx = tmp / "pfx"
    v = pfx / "versions" / "2.0.2"
    (v / "dist" / "host-app").mkdir(parents=True)
    shutil.copytree(ROOT / "shells" / "branding", v / "shells" / "branding")
    if binary:
        b = v / "dist" / "host-app" / "madalean-server"
        b.write_text("#!/bin/sh\nexit 0\n")
        b.chmod(0o755)
    (pfx / "current").symlink_to("versions/2.0.2")
    return pfx


def run(tmp: Path, path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {"PATH": str(path), "HOME": str(tmp / "home"), "XDG_DATA_HOME": str(tmp / "data"), "LANG": "C.UTF-8"}
    return subprocess.run([shutil.which("bash"), str(SCRIPT), *args], env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60)


def entry(tmp: Path) -> str:
    return (tmp / "data" / "applications" / "madalean-server.desktop").read_text()


def test_native_entry_icons_record_and_caches(tmp_path):
    pfx = prefix(tmp_path)
    apps = tmp_path / "data" / "applications"
    apps.mkdir(parents=True)
    # the old install.sh ≤ 2.0.1 entry (replaced) and a client AppImage entry of another kind (kept)
    (apps / "madalean.desktop").write_text("[Desktop Entry]\nName=Madalean\nExec=xdg-open http://127.0.0.1:11500/\n")
    r = run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().endswith("LAUNCHER=native")
    e = entry(tmp_path)
    assert "Name=Madalean Server\n" in e and "Icon=madalean-server\n" in e and "StartupWMClass=madalean-server\n" in e
    assert f'Exec="{pfx}/current/dist/host-app/madalean-server" --host\n' in e
    assert f"X-Madalean-Prefix={pfx}\n" in e and "X-Madalean-Launcher=native\n" in e
    assert "%u" not in e and "MimeType" not in e                       # never the client's madalean:// handler
    assert not (apps / "madalean.desktop").exists()                     # old xdg-open entry replaced
    icons = tmp_path / "data" / "icons" / "hicolor"
    assert (icons / "scalable" / "apps" / "madalean-server.svg").read_text().count("Madalean Server") == 1
    for s in SIZES:
        assert (icons / f"{s}x{s}" / "apps" / "madalean-server.png").is_file(), s
    rec = (pfx / "installed-files.txt").read_text().splitlines()
    assert str(apps / "madalean-server.desktop") in rec and len(rec) == 1 + 1 + len(SIZES)
    calls = (tmp_path / "calls.txt").read_text()
    assert "update-desktop-database" in calls and "gtk-update-icon-cache -q -t -f" in calls and "kbuildsycoca6" in calls
    # idempotent: a second run records nothing twice
    run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx))
    assert len((pfx / "installed-files.txt").read_text().splitlines()) == len(rec)


def test_client_appimage_entry_is_never_touched(tmp_path):
    pfx = prefix(tmp_path)
    apps = tmp_path / "data" / "applications"
    apps.mkdir(parents=True)
    client = "[Desktop Entry]\nName=Madalean\nExec=env APPIMAGELAUNCHER_DISABLE=1 \"/x/Madalean.AppImage\" %u\n"
    (apps / "madalean.desktop").write_text(client)
    assert run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx)).returncode == 0
    assert (apps / "madalean.desktop").read_text() == client


def test_port_and_unit_are_passed(tmp_path):
    pfx = prefix(tmp_path)
    r = run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx), "--port", "11600", "--unit", "m2")
    assert r.returncode == 0, r.stderr
    assert '--host --port 11600 --unit m2\n' in entry(tmp_path) and "X-Madalean-Unit=m2" in entry(tmp_path)
    assert run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx), "--unit", "a;b").returncode == 2


def test_webkit_missing_falls_back_to_a_chromium_window(tmp_path):
    pfx = prefix(tmp_path)
    r = run(tmp_path, toolbox(tmp_path, ldd="missing", browsers=("brave",)), "--prefix", str(pfx), "--port", "11600")
    assert r.returncode == 0 and r.stdout.strip().endswith("LAUNCHER=browser"), r.stdout
    assert "libwebkit2gtk-4.1.so.0" in r.stdout                           # the summary says why
    e = entry(tmp_path)
    assert f'Exec="{tmp_path}/bin/brave" --app=http://127.0.0.1:11600/ --class=madalean-server\n' in e
    assert "X-Madalean-Launcher=browser" in e


def test_no_webkit_no_chromium_falls_back_to_xdg_open(tmp_path):
    pfx = prefix(tmp_path)
    r = run(tmp_path, toolbox(tmp_path, ldd="missing"), "--prefix", str(pfx))
    assert r.stdout.strip().endswith("LAUNCHER=xdg-open") and "Exec=xdg-open http://127.0.0.1:11500/\n" in entry(tmp_path)
    # a version without the app (built without cargo / --no-host-app): same fallback chain
    shutil.rmtree(tmp_path / "data")
    pfx2 = tmp_path / "p2"
    shutil.move(str(pfx), str(pfx2))
    (pfx2 / "current").unlink()
    (pfx2 / "current").symlink_to("versions/2.0.2")
    (pfx2 / "versions" / "2.0.2" / "dist" / "host-app" / "madalean-server").unlink()
    r = run(tmp_path, toolbox(tmp_path, browsers=("chromium",)), "--prefix", str(pfx2))
    assert r.stdout.strip().endswith("LAUNCHER=browser") and "absente de cette version" in r.stdout


def test_dry_run_writes_nothing_and_detect(tmp_path):
    pfx = prefix(tmp_path)
    r = run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx), "--dry-run")
    assert r.returncode == 0 and "+ write" in r.stdout and not (tmp_path / "data").exists()
    assert not (pfx / "installed-files.txt").exists()
    r = run(tmp_path, toolbox(tmp_path, ldd="missing", browsers=("chromium",)), "--detect", "--binary",
            str(pfx / "current" / "dist" / "host-app" / "madalean-server"))
    assert r.stdout.strip().endswith("LAUNCHER=browser") and not (tmp_path / "data").exists()


def test_refresh_only_for_this_prefix(tmp_path):
    pfx = prefix(tmp_path)
    tb = toolbox(tmp_path)
    # nothing installed: nothing to refresh, nothing written
    r = run(tmp_path, tb, "--prefix", str(pfx), "--refresh")
    assert r.returncode == 0 and "aucune entrée" in r.stdout and not (tmp_path / "data").exists()
    # an entry of ANOTHER prefix (e.g. a test install): left alone
    apps = tmp_path / "data" / "applications"
    apps.mkdir(parents=True)
    other = "[Desktop Entry]\nName=Madalean Server\nX-Madalean-Host=1\nX-Madalean-Prefix=/elsewhere\n"
    (apps / "madalean-server.desktop").write_text(other)
    run(tmp_path, tb, "--prefix", str(pfx), "--refresh")
    assert entry(tmp_path) == other
    # our own entry: rewritten, port and unit kept
    run(tmp_path, tb, "--prefix", str(pfx), "--port", "11700", "--unit", "m3")
    (tmp_path / "data" / "icons" / "hicolor" / "48x48" / "apps" / "madalean-server.png").unlink()
    r = run(tmp_path, tb, "--prefix", str(pfx), "--refresh")
    assert r.stdout.strip().endswith("LAUNCHER=native")
    assert "--host --port 11700 --unit m3" in entry(tmp_path)
    assert (tmp_path / "data" / "icons" / "hicolor" / "48x48" / "apps" / "madalean-server.png").is_file()


def test_refresh_replaces_the_recorded_2_0_1_entry(tmp_path):
    """Self-update from 2.0.1: the old « Madalean » xdg-open entry that install.sh recorded becomes Madalean Server."""
    pfx = prefix(tmp_path)
    apps = tmp_path / "data" / "applications"
    apps.mkdir(parents=True)
    old = apps / "madalean.desktop"
    old.write_text("[Desktop Entry]\nType=Application\nName=Madalean\nExec=xdg-open http://127.0.0.1:11580/\n"
                   "Icon=applications-science\n")
    # not recorded by this prefix: not ours → untouched
    r = run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx), "--refresh")
    assert "aucune entrée" in r.stdout and old.exists()
    (pfx / "installed-files.txt").write_text(f"{old}\n")
    r = run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx), "--refresh")
    assert r.returncode == 0 and not old.exists(), r.stdout + r.stderr
    assert "--host --port 11580\n" in entry(tmp_path)


def test_uninstall_removes_entry_and_icons(tmp_path):
    pfx = prefix(tmp_path)
    run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx))
    r = run(tmp_path, toolbox(tmp_path), "--prefix", str(pfx), "--uninstall")
    assert r.returncode == 0
    assert not list((tmp_path / "data").rglob("madalean-server*"))


def test_install_sh_dry_run_shows_the_launcher(tmp_path):
    (tmp_path / "home").mkdir()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "home"), "LANG": "C.UTF-8", "TMPDIR": str(tmp_path),
           "XDG_DATA_HOME": str(tmp_path / "data"), "MADALEAN_SETUP_KERNEL_DIRS": str(tmp_path / "nok")}
    r = subprocess.run(["bash", str(ROOT / "install.sh"), "--dry-run", "--yes", "--prefix", str(tmp_path / "pfx"),
                        "--config-dir", str(tmp_path / "cfg")], env=env, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("DRY-RUN hostapp=")]
    assert line and line[0].split("=", 1)[1] in ("native", "browser", "xdg-open")
    assert not (tmp_path / "data").exists() and not (tmp_path / "pfx").exists()
    # --no-desktop: no menu line at all
    r = subprocess.run(["bash", str(ROOT / "install.sh"), "--dry-run", "--yes", "--no-desktop", "--prefix",
                        str(tmp_path / "pfx"), "--config-dir", str(tmp_path / "cfg")], env=env, capture_output=True,
                       text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert "DRY-RUN hostapp=" not in r.stdout


def test_install_sh_installs_only_the_host_entry():
    text = (ROOT / "install.sh").read_text()
    step8 = text[text.index('step "8/9 Menu"'):text.index('step "9/9')]
    code = "\n".join(ln for ln in step8.splitlines() if not ln.lstrip().startswith("#"))
    assert "install_host_app.sh" in code
    assert "install_desktop_entry.sh" not in code and "AppImage" not in code
    assert "applications-science" not in text


def test_selfupdate_refreshes_the_menu_entry(tmp_path):
    from madalean.update_checkers import selfupdate as su
    app = tmp_path / "versions" / "2.0.2"
    (app / "scripts").mkdir(parents=True)
    (app / "scripts" / "install_host_app.sh").write_text(
        f"#!/bin/sh\necho \"$@\" > '{tmp_path}/args'\necho 'Menu : ok'\necho LAUNCHER=native\n")
    u = su.SelfUpdater(tmp_path, "http://127.0.0.1:9/x", b"\0" * 32, current="2.0.1", restart_cmd=[], manifest="")
    assert u.refresh_desktop_entry(app) == "native"
    assert (tmp_path / "args").read_text().split() == ["--refresh", "--prefix", str(tmp_path)]
    (app / "scripts" / "install_host_app.sh").write_text("#!/bin/sh\necho boom >&2\nexit 3\n")
    assert u.refresh_desktop_entry(app).startswith("error: boom")      # reported, never raised
    off = su.SelfUpdater(tmp_path, "http://127.0.0.1:9/x", b"\0" * 32, restart_cmd=[], manifest="", refresh_desktop=False)
    assert off.refresh_desktop_entry(app) == ""
    assert u.refresh_desktop_entry(tmp_path / "nowhere") == ""          # a release without the script


def test_graphical_installer_opens_the_host_app(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("inst_server", ROOT / "packaging" / "installer" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    apps = tmp_path / "applications"
    apps.mkdir()
    assert mod.host_app_command(tmp_path) is None
    binary = tmp_path / "madalean server"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    (apps / "madalean-server.desktop").write_text(
        f'[Desktop Entry]\nName=Madalean Server\nExec="{binary}" --host --port 11600\nX-Madalean-Host=1\n')
    assert mod.host_app_command(tmp_path) == [str(binary), "--host", "--port", "11600"]
    (apps / "madalean-server.desktop").write_text(f'[Desktop Entry]\nExec="{binary}" --host\n')   # not ours
    assert mod.host_app_command(tmp_path) is None


@pytest.mark.skipif(not (shutil.which("rsvg-convert") and shutil.which("magick")), reason="brand tools missing")
def test_brand_server_icon_is_generated_and_reproducible(tmp_path):
    """The committed server icon files equal a fresh build_brand.py run (never hand-edited)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_brand", ROOT / "scripts" / "build_brand.py")
    bb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bb)
    m = bb.read_master()
    for small, name in ((False, "madalean-server-icon.svg"), (True, "madalean-server-icon-small.svg")):
        assert bb.server_icon_svg(m, small=small) == (ROOT / "shells" / "branding" / name).read_text()
        assert (ROOT / "shells" / "desktop" / "ui" / "server-icon.svg").read_text() == \
            (ROOT / "shells" / "branding" / "madalean-server-icon.svg").read_text()
    out = tmp_path / "48.png"
    bb.png(ROOT / "shells" / "branding" / "madalean-server-icon.svg", out, 48, rgba=True)
    assert out.read_bytes() == (ROOT / "shells" / "branding" / "png" / "madalean-server-icon-48.png").read_bytes()
    # Tauri needs RGBA PNGs (the 32x32 palette PNG made `cargo build` fail)
    for p in (ROOT / "shells" / "desktop" / "src-tauri" / "icons").glob("*.png"):
        assert p.read_bytes()[25] == 6, p.name                          # IHDR colour type 6 = RGBA
