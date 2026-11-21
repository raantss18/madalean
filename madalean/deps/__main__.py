"""`python -m madalean.deps …` — used by install.sh / uninstall.sh / export_offline.sh and for repairs.

  install COMPONENT… [--variant auto|cpu|cuda12|cuda13] [--offline-dir DIR]… [--offline] [--build-net] [--progress]
  rollback COMPONENT
  health [--json] [--sizes]
  tool NAME                      print the resolved path (exit 1 when missing)
  paths                          print the prefix layout as JSON
  import-workspaces [ROOT…]      hard-link import of already built workspaces (+ toolchains)
  sbom OUT.json                  CycloneDX 1.5 SBOM of the prefix
  list                           components of the manifest (name, version, need, url)"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import elan_home, env_dir, home, manifest, tool, tool_info, workspaces_dir


def _progress_printer(as_json: bool):
    last = {}

    def p(e: dict) -> None:
        if as_json:
            print(json.dumps(e), flush=True)
            return
        key = (e["component"], e["phase"])
        if e["phase"] == "download" and e.get("total"):
            pct = int(100 * e["done"] / max(e["total"], 1))
            if last.get(key) == pct // 10:
                return
            last[key] = pct // 10
            print(f"   {e['component']}: {e['phase']} {pct}% {e.get('message', '')}", flush=True)
        elif e["phase"] != "download":
            print(f"   {e['component']}: {e['phase']} {e.get('message', '')}".rstrip(), flush=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m madalean.deps")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("install")
    i.add_argument("components", nargs="+")
    i.add_argument("--variant", default="auto")
    i.add_argument("--offline-dir", action="append", default=[], type=Path)
    i.add_argument("--offline", action="store_true")
    i.add_argument("--build-net", action="store_true")
    i.add_argument("--progress", action="store_true", help="JSON progress lines")
    rb = sub.add_parser("rollback")
    rb.add_argument("component")
    h = sub.add_parser("health")
    h.add_argument("--json", action="store_true")
    h.add_argument("--sizes", action="store_true")
    t = sub.add_parser("tool")
    t.add_argument("name")
    sub.add_parser("paths")
    sub.add_parser("list")
    iw = sub.add_parser("import-workspaces")
    iw.add_argument("roots", nargs="*", type=Path)
    sb = sub.add_parser("sbom")
    sb.add_argument("out", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "install":
        from .installer import InstallError, install
        pr = _progress_printer(a.progress)
        for comp in a.components:
            try:
                r = install(comp, pr, a.variant, a.offline_dir, a.offline, a.build_net)
            except (InstallError, KeyError) as e:
                print(f"FAIL {comp}: {e}", file=sys.stderr, flush=True)
                return 1
            print(f"OK {comp} {r.get('version', '')}{' ' + r['variant'] if r.get('variant') else ''}", flush=True)
        return 0
    if a.cmd == "rollback":
        from .installer import InstallError, rollback
        try:
            print(json.dumps(rollback(a.component)))
        except InstallError as e:
            print(f"FAIL {e}", file=sys.stderr)
            return 1
        return 0
    if a.cmd == "health":
        from .health import report
        r = report(a.sizes)
        if a.json:
            print(json.dumps(r, indent=1))
        else:
            print(f"MADALEAN_HOME = {r['home']}")
            for c in r["components"]:
                sz = f" {c['bytes'] / 1e6:8.1f} MB" if "bytes" in c else ""
                print(f"  {c['state']:9} {c['component']:13} {c['version'] or '-':12} {c['source']:10}{sz} {c['path']}")
            for s in r["system"]:
                print(f"  system    {s['tool']:13} {s['path']}  ({s['why']})")
        return 0 if all(c["ok"] for c in r["components"]) else 3
    if a.cmd == "tool":
        info = tool_info(a.name)
        if not info["path"]:
            return 1
        print(info["path"])
        return 0
    if a.cmd == "paths":
        print(json.dumps({"home": str(home()), "env": str(env_dir()), "elan_home": str(elan_home()),
                          "workspaces": str(workspaces_dir()), "python": tool("python")}, indent=1))
        return 0
    if a.cmd == "list":
        for n, c in manifest.components().items():
            print(f"{n:13} {c.get('version', ''):12} {c.get('need', ''):9} {c.get('url') or c.get('lock') or ''}")
        return 0
    if a.cmd == "import-workspaces":
        from .workspaces_import import candidates, import_workspace
        found = candidates(a.roots)
        if not found:
            print("no built workspace found")
        for name, src in found.items():
            try:
                print(json.dumps(import_workspace(src, name)))
            except (OSError, FileNotFoundError) as e:
                print(f"FAIL {name}: {e}", file=sys.stderr)
        return 0
    if a.cmd == "sbom":
        from .sbom import write_sbom
        n = write_sbom(a.out)
        print(f"{a.out}: {n} components")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
