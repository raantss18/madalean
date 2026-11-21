"""Kernelspec lookup: a system spec with a bare interpreter is resolved on the system PATH, not Madalean's env."""
import json
import os

from madalean.research import sagebridge


def test_bare_python_resolved_on_system_path(tmp_path, monkeypatch):
    sysd, prefix = tmp_path / "sys", tmp_path / "prefix"
    (sysd / "sagemath").mkdir(parents=True)
    (sysd / "sagemath" / "kernel.json").write_text(json.dumps({"argv": ["python", "-m", "sage.repl.ipython_kernel"]}))
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    py = fakebin / "python"
    py.write_text("#!/bin/sh\n")
    py.chmod(0o755)
    monkeypatch.setattr(sagebridge, "PREFIX_KERNELS", str(prefix))
    monkeypatch.setattr(sagebridge, "KERNEL_DIRS", [str(prefix), str(sysd)])
    monkeypatch.setattr(sagebridge, "SYSTEM_PATH", str(fakebin))
    monkeypatch.setenv("PATH", "/nonexistent")
    spec = sagebridge.find_kernelspec("sagemath")
    assert spec["argv"][0] == str(py) and spec["argv"][1:] == ["-m", "sage.repl.ipython_kernel"]


def test_prefix_spec_wins(tmp_path, monkeypatch):
    sysd, prefix = tmp_path / "sys", tmp_path / "prefix"
    for d, exe in ((sysd, "/usr/bin/python"), (prefix, "/opt/madalean/envs/sage/bin/python3")):
        (d / "sagemath").mkdir(parents=True)
        (d / "sagemath" / "kernel.json").write_text(json.dumps({"argv": [exe, "-m", "sage.repl.ipython_kernel"]}))
    monkeypatch.setattr(sagebridge, "PREFIX_KERNELS", str(prefix))
    monkeypatch.setattr(sagebridge, "KERNEL_DIRS", [str(prefix), str(sysd)])
    assert sagebridge.find_kernelspec("sagemath")["argv"][0] == "/opt/madalean/envs/sage/bin/python3"


def test_unresolvable_bare_interpreter_skipped(tmp_path, monkeypatch):
    sysd = tmp_path / "sys"
    (sysd / "sagemath").mkdir(parents=True)
    (sysd / "sagemath" / "kernel.json").write_text(json.dumps({"argv": ["nosuchpython", "-m", "x"]}))
    monkeypatch.setattr(sagebridge, "KERNEL_DIRS", [str(sysd)])
    monkeypatch.setattr(sagebridge, "SYSTEM_PATH", str(tmp_path))
    assert sagebridge.find_kernelspec("sagemath") is None
