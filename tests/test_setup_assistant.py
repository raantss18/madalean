"""Install assistant engine, install.sh planning (non-interactive + dry run), setup.json, /api/setup (S-AL, D44).

Fakes only: nvidia-smi / sage / xelatex… are shell scripts in a temporary PATH; nothing is installed and the real
prefix (~/.local/share/madalean) and config (~/.config/madalean) are never touched."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import aiohttp

from madalean import config
from madalean.deps import assistant as A

from helpers import make_ctx, running

ROOT = Path(__file__).resolve().parents[1]
SMI_CSV = "NVIDIA GeForce RTX 4070, 12282, 580.95.05\n"
SMI_BANNER = "| NVIDIA-SMI 580.95.05   Driver Version: 580.95.05   CUDA Version: 13.5 |\n"


# ---------------------------------------------------------------- parsers
def test_parsers():
    assert A.parse_meminfo("MemTotal:       32603000 kB\nMemFree: 1 kB") == 32603000 * 1024
    assert A.parse_cpuinfo("processor\t: 0\nmodel name\t: AMD Ryzen 7\nprocessor\t: 1\n") == \
        {"model": "AMD Ryzen 7", "threads": 2}
    assert A.parse_nvidia_smi(SMI_CSV + "garbage\n") == [{"name": "NVIDIA GeForce RTX 4070", "vram_mib": 12282,
                                                          "driver": "580.95.05"}]
    assert A.parse_cuda(SMI_BANNER) == "13.5"
    assert A.parse_sage_version("SageMath version 10.4, Release Date: 2024-07-19") == "10.4"
    assert A.parse_texlive_year("XeTeX 3.141592653-2.6-0.999997 (TeX Live 2025/Arch Linux)") == 2025
    assert A.parse_elan_toolchains("leanprover/lean4:v4.9.0 (default)\nleanprover/lean4:v4.34.1\nnoise here\n") == \
        ["leanprover/lean4:v4.9.0", "leanprover/lean4:v4.34.1"]
    assert A.distro_family({"ID": "cachyos", "ID_LIKE": "arch"}) == "arch"
    assert A.install_command("bubblewrap", "debian") == "sudo apt install bubblewrap"


def _det(vram=0, ram_gib=32, free_gib=500, sage=None, tex=None, bwrap=True, ws=(), models=None):
    return {"os": {"family": "arch", "supported": True},
            "hardware": {"ram_bytes": ram_gib * A.GIB, "disk": {"free_bytes": free_gib * A.GIB, "path": "/x"},
                         "gpus": [{"name": "RTX", "vram_mib": vram, "driver": "580"}] if vram else [], "cuda": "13.5",
                         "cpu": {"model": "cpu", "threads": 8}},
            "tools": {"sage": sage or {"found": False}, "tex": tex or {"found": False}, "bwrap": {"found": bwrap},
                      "elan": {"found": False}, "ollama": {"found": False}, "tailscale": {"found": False},
                      "python": []},
            "madalean": {"models": models or {}, "workspaces": list(ws), "sage_own": False}}


def test_recommendations_follow_the_machine():
    big = A.recommend(_det(vram=12282), "fr")
    assert big["plan"]["models"] == "all" and big["plan"]["variant"] == "auto" and big["plan"]["mode"] == "auto"
    mid = A.recommend(_det(vram=8192), "en")
    assert mid["plan"]["models"] == "prover"
    none = A.recommend(_det(vram=0), "fr")
    assert none["plan"]["models"] == "none" and none["plan"]["variant"] == "cpu" and none["plan"]["mode"] == "online"
    assert "Pas de modèle local conseillé" in next(i["why"] for i in none["items"] if i["id"] == "models")
    # Sage: reuse when compatible (version + kernel), own copy otherwise; « system » not offered when incompatible
    ok = {"found": True, "version": "10.4", "kernelspec": "/usr/share/jupyter/kernels/sagemath/kernel.json",
          "compatible": True, "path": "/usr/bin/sage"}
    assert A.recommend(_det(sage=ok))["plan"]["sage"] == "system"
    old = {**ok, "version": "9.5", "compatible": False}
    r = A.recommend(_det(sage=old), "en")
    sage = next(i for i in r["items"] if i["id"] == "sage")
    assert r["plan"]["sage"] == "later" and "too old" in sage["why"]
    assert next(o for o in sage["options"] if o["value"] == "system")["available"] is False
    # TeX: own copy recommended even with a TeX Live, which stays a fallback
    tex = {"found": True, "year": 2025, "fontspec": True, "compatible": True, "xelatex": "/usr/bin/xelatex"}
    r = A.recommend(_det(tex=tex), "fr")
    assert r["plan"]["tex"] == "own" and "secours" in next(i["why"] for i in r["items"] if i["id"] == "tex")
    # workspace: build when none and enough disk, import when present
    assert A.recommend(_det())["plan"]["workspace"] == "build"
    assert A.recommend(_det(ws=["lean-current"]))["plan"]["workspace"] == "import"
    assert A.recommend(_det(free_gib=8))["plan"]["workspace"] == "import"
    # advice: bubblewrap command (never run), disk
    r = A.recommend(_det(bwrap=False, vram=12282, free_gib=10), "fr")
    ids = {a["id"]: a for a in r["advice"]}
    assert ids["bwrap"]["command"] == "sudo pacman -S --needed bubblewrap" and "disk" in ids


def test_validate_vars_and_settings():
    assert A.validate({}) == A.DEFAULT_PLAN
    for bad in ({"models": "x"}, {"nope": "all"}):
        try:
            A.validate(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)
    v = A.shell_vars({"models": "prover", "sage": "system"})
    assert "PLAN_MODEL_LIST=Q4_K_M\n" in v and "PLAN_SAGE=system" in v
    assert A.settings_from_plan({"sage": "system", "tex": "system", "mode": "online"}) == \
        {"sage_source": "system", "tex_engine": "system", "mode": "online"}
    assert A.settings_from_plan({}) == {"sage_source": "auto", "tex_engine": "auto", "mode": "auto"}


def test_terminal_assistant_accept_and_customise():
    det = _det(vram=12282)
    out: list[str] = []
    answers = iter(["", ])
    plan = A.interactive(det, lang="fr", ask=lambda p: next(answers), out=out.append)
    assert plan == A.recommend(det)["plan"]
    assert any("Plan conseillé" in line for line in out)
    # change item 1 (models) to option 3 (none), then item 3 (sage) with a refused choice, then accept
    answers = iter(["1", "3", "3", "3", "x", ""])
    plan = A.interactive(det, lang="en", ask=lambda p: next(answers), out=out.append)
    assert plan["models"] == "none" and plan["sage"] == "later"     # system Sage not available on this machine


def test_record_and_apply_pending(tmp_path):
    doc = {"plan": {"sage": "system", "tex": "system", "mode": "online"}, "detected": {"x": 1}}
    A.record(tmp_path, doc, 0, "install.sh")
    s = config.Settings()
    assert A.apply_pending(s, tmp_path) is True
    assert (s.sage_source, s.tex_engine, s.mode) == ("system", "system", "online")
    s2 = config.Settings()
    assert A.apply_pending(s2, tmp_path) is False and s2.sage_source == "auto"       # applied once only
    A.record(tmp_path, doc, 0, "install.sh")                                      # same plan: not re-armed
    assert A.load(tmp_path)["applied"] is True
    A.record(tmp_path, {"plan": {"sage": "later"}}, 0, "install.sh")              # new plan: re-armed
    assert A.load(tmp_path)["applied"] is False and len(A.load(tmp_path)["history"]) == 3
    A.record(tmp_path, {"plan": {"tex": "system"}}, 1, "install.sh")              # failed run: nothing applied
    assert A.apply_pending(config.Settings(), tmp_path) is False


# ---------------------------------------------------------------- detection with fake tools
def fake_bin(tmp: Path) -> Path:
    b = tmp / "bin"
    b.mkdir()
    scripts = {
        "nvidia-smi": f'if [ "$1" = "--query-gpu=name,memory.total,driver_version" ]; then printf "{SMI_CSV}"; '
                      f'else printf "{SMI_BANNER}"; fi',
        "sage": 'echo "SageMath version 10.5, Release Date: 2024-12-04"',
        "xelatex": 'echo "XeTeX 3.14 (TeX Live 2025/Arch Linux)"',
        "kpsewhich": 'echo "/usr/share/texmf-dist/tex/latex/fontspec/fontspec.sty"',
        "bwrap": "exit 0",
    }
    for name, body in scripts.items():
        f = b / name
        f.write_text("#!/bin/sh\n" + body + "\n")
        f.chmod(0o755)
    return b


def test_detect_with_fakes(tmp_path):
    b = fake_bin(tmp_path)
    kd = tmp_path / "kernels" / "sagemath"
    kd.mkdir(parents=True)
    (kd / "kernel.json").write_text("{}")
    import shutil
    det = A.detect(str(tmp_path / "pfx"), home=str(tmp_path / "home"),
                   which=lambda n: shutil.which(n, path=str(b)), kernel_dirs=[str(tmp_path / "kernels")])
    assert det["hardware"]["gpus"][0]["vram_mib"] == 12282 and det["hardware"]["cuda"] == "13.5"
    assert det["tools"]["sage"]["compatible"] and det["tools"]["sage"]["version"] == "10.5"
    assert det["tools"]["tex"]["compatible"] and det["tools"]["tex"]["year"] == 2025
    assert det["tools"]["bwrap"]["found"] and not det["tools"]["ollama"]["found"]
    assert det["madalean"]["installed"] is False and det["madalean"]["workspaces"] == []
    rec = A.recommend(det)
    assert rec["plan"]["sage"] == "system" and rec["plan"]["models"] == "all"


def _install_sh(tmp: Path, *args: str, path_extra: Path | None = None) -> subprocess.CompletedProcess:
    env = {"PATH": (f"{path_extra}:" if path_extra else "") + "/usr/bin:/bin", "HOME": str(tmp / "home"),
           "LANG": "fr_FR.UTF-8", "MADALEAN_SETUP_KERNEL_DIRS": str(tmp / "nokernels"), "TMPDIR": str(tmp)}
    (tmp / "home").mkdir(exist_ok=True)
    return subprocess.run(["bash", str(ROOT / "install.sh"), "--dry-run", "--prefix", str(tmp / "pfx"),
                           "--config-dir", str(tmp / "cfg"), *args], capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, timeout=120)


def test_install_sh_yes_keeps_the_2_0_0_defaults(tmp_path):
    r = _install_sh(tmp_path, "--yes", path_extra=fake_bin(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DRY-RUN models=all variant=auto sage=later tex=own workspaces=1 build=0" in r.stdout
    assert not (tmp_path / "pfx").exists() and not (tmp_path / "cfg").exists()       # dry run writes nothing


def test_install_sh_options_and_recommended_dry_run(tmp_path):
    b = fake_bin(tmp_path)
    r = _install_sh(tmp_path, "--yes", "--no-models", "--cpu", "--sage", "now", "--tex", "system",
                    "--build-workspace", path_extra=b)
    assert "DRY-RUN models=none variant=cpu sage=now tex=system workspaces=1 build=1" in r.stdout, r.stdout + r.stderr
    r = _install_sh(tmp_path, "--yes", "--models", "prover", path_extra=b)
    assert "models=prover" in r.stdout and "6 modèles (Q4_K_M)" in r.stdout
    r = _install_sh(tmp_path, "--models", "bogus")
    assert r.returncode == 2 and "bogus" in r.stderr
    # dry run without --yes: the machine check + the recommended plan (fake 12 GB GPU → all models, CUDA)
    r = _install_sh(tmp_path, path_extra=b)
    assert r.returncode == 0 and "RTX 4070" in r.stdout and "models=all variant=auto" in r.stdout
    # a plan file from the graphical installer
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"plan": {"models": "none", "sage": "system", "workspace": "skip"}}))
    r = _install_sh(tmp_path, "--plan", str(plan), path_extra=b)
    assert "DRY-RUN models=none variant=auto sage=system tex=own workspaces=0" in r.stdout, r.stdout + r.stderr


# ---------------------------------------------------------------- runtime preferences + API
def test_preferences_reorder_tex_and_sage(tmp_path, monkeypatch):
    from madalean import deps, export
    from madalean.research import sagebridge
    s = config.Settings()
    s.tex_engine = "system"
    config.publish_preferences(s)
    try:
        monkeypatch.setattr(export, "tectonic_cmd", lambda: ["/p/tectonic"])
        monkeypatch.setattr(deps, "tool", lambda n: f"/usr/bin/{n}" if n in ("xelatex", "latexmk") else None)
        eng = export._engines()
        assert eng[0][0] == "/usr/bin/latexmk" and eng[-1] == ["/p/tectonic"]
        s.tex_engine = "tectonic"
        config.publish_preferences(s)
        assert export._engines() == [["/p/tectonic"]]
        # Sage: own = prefix kernels only, system = system dirs only
        own, sysd = tmp_path / "own", tmp_path / "sys"
        for d, exe in ((own, "/own/python3"), (sysd, "/usr/bin/sage-python")):
            (d / "sagemath").mkdir(parents=True)
            (d / "sagemath" / "kernel.json").write_text(json.dumps({"argv": [exe, "-m", "sage"]}))
        monkeypatch.setattr(sagebridge, "PREFIX_KERNELS", str(own))
        monkeypatch.setattr(sagebridge, "KERNEL_DIRS", [str(own), str(sysd)])
        for pref, want in (("auto", "/own/python3"), ("own", "/own/python3"), ("system", "/usr/bin/sage-python")):
            s.sage_source = pref
            config.publish_preferences(s)
            assert sagebridge.find_kernelspec("sagemath")["argv"][0] == want, pref
        (own / "sagemath" / "kernel.json").unlink()
        s.sage_source = "own"
        config.publish_preferences(s)
        assert sagebridge.find_kernelspec("sagemath") is None
    finally:
        config.publish_preferences(config.Settings())


async def test_api_setup_and_first_start_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    cfg = tmp_path / "config"
    A.record(cfg, {"plan": {"sage": "system", "mode": "online"}, "detected": _det(vram=0)}, 0, "install.sh --yes",
             "2.0.0")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        assert ctx.settings.sage_source == "system"                   # applied at start
        assert json.loads((cfg / "settings.json").read_text())["sage_source"] == "system"
        async with aiohttp.ClientSession() as s:
            async with s.get(local + "/api/setup") as r:
                assert r.status == 200
                d = await r.json()
            async with s.get(remote + "/api/setup") as r:
                assert r.status in (401, 403)                         # host only
    assert d["schema"] == "madalean-setup-status/1"
    assert d["setup"]["plan"]["sage"] == "system" and d["setup"]["applied"] is True
    assert d["prefs"]["sage_source"] == "system" and d["prefs"]["mode"] == ctx.settings.mode
    assert {"sage", "tex"} <= set(d["reuse"]) and d["reuse"]["sage"]["preference"] == "system"
    steps = {x["id"]: x for x in d["next_steps"]}
    assert steps["keys"]["done"] is False and steps["keys"]["help"] == "first-config"
    assert set(steps["keys"]["title"]) == {"fr", "en"}
    assert isinstance(d["components"], list) and d["keys"] == [] and d["devices"] == 0
    assert os.environ.get("MADALEAN_NO_NET") == "1"
