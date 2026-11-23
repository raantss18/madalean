"""Command line: `madalean serve [--demo]`, `madalean pair`, `madalean status`, `madalean bench …` (docs/BENCH.md),
`madalean mcp serve` (the stdio MCP server for a local client, docs/MCP.md).

The config/cache directories are fixed before any other madalean module is imported (they read them at import)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="madalean", description="Madalean — Lean 4 proving assistant server")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the server")
    s.add_argument("--demo", action="store_true", help="scripted fake models and fake Lean, seeded example project")
    s.add_argument("--port", type=int, default=11500, help="local (trusted) listener, 127.0.0.1")
    s.add_argument("--remote-port", type=int, default=11501, help="remote (token) listener, 127.0.0.1")
    s.add_argument("--lan", action="store_true", help="also listen on the LAN (token required)")
    s.add_argument("--static", type=Path, help="directory of the web UI (default: madalean/static)")
    s.add_argument("--no-migrate", action="store_true", help="do not copy the 1.x data on first start")
    s.add_argument("--debug", action="store_true")
    for name in ("pair", "status"):
        c = sub.add_parser(name, help="print a pairing code" if name == "pair" else "show the server status")
        c.add_argument("--port", type=int, help="local listener port (default: from server.json, else 11500)")
        c.add_argument("--json", action="store_true")
    m = sub.add_parser("mcp", help="Model Context Protocol (docs/MCP.md)")
    msub = m.add_subparsers(dest="mcp_cmd", required=True)
    ms = msub.add_parser("serve", help="stdio MCP server for a local client (relays to the running Madalean)")
    ms.add_argument("--port", type=int, help="local listener port (default: from server.json, else 11500)")
    for c in (s, ms, *[sub.choices[n] for n in ("pair", "status")]):
        c.add_argument("--config-dir", type=Path, help="default ~/.config/madalean (demo: ~/.config/madalean-demo)")
        c.add_argument("--cache-dir", type=Path)
    from .bench.cli import add_parser          # « Mesurer » (D53): `madalean bench …`, its own private directories
    add_parser(sub)
    return p


def _set_dirs(args) -> None:
    if args.config_dir:
        os.environ["MADALEAN_CONFIG_DIR"] = str(args.config_dir.expanduser().resolve())
    elif getattr(args, "demo", False):
        os.environ["MADALEAN_CONFIG_DIR"] = str(Path.home() / ".config" / "madalean-demo")
    if args.cache_dir:
        os.environ["MADALEAN_CACHE_DIR"] = str(args.cache_dir.expanduser().resolve())
    elif getattr(args, "demo", False) and "MADALEAN_CACHE_DIR" not in os.environ:
        os.environ["MADALEAN_CACHE_DIR"] = str(Path.home() / ".cache" / "madalean-demo")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "bench":
        from .bench import cli as bench_cli
        return bench_cli.main(args)
    _set_dirs(args)
    if args.cmd == "mcp":
        from .mcp.bridge import main as mcp_main
        return mcp_main(_port(args))
    if args.cmd == "serve":
        return serve(args)
    return client(args)


# ---------------------------------------------------------------- serve
def serve(args) -> int:
    import asyncio
    import fcntl
    import logging

    from . import deps
    deps.activate()          # §18: the prefix's programs first in PATH (+ ELAN_HOME, TECTONIC_CACHE_DIR, FONTCONFIG_FILE)
    from . import config, logs
    from .paths import Paths
    paths = Paths(config.CONFIG_DIR, config.CACHE_DIR)
    paths.ensure()
    logs.setup(paths.logs, logging.DEBUG if args.debug else logging.INFO)
    lock = open(paths.lock, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"madalean: another server already uses {paths.config}", file=sys.stderr)
        return 2
    from .server.app import Server, serve_forever
    if args.demo:
        from .demo import demo_context
        ctx = demo_context(paths)
    else:
        from .context import ServerContext
        ctx = ServerContext(paths, legacy_dir=None if args.no_migrate else config.LEGACY_CONFIG_DIR)
    server = Server(ctx, args.port, args.remote_port, args.static, lan=True if args.lan else None)
    try:
        asyncio.run(serve_forever(server))
    except OSError as e:
        print(f"madalean: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------- pair / status (clients of the local listener)
def _port(args) -> int:
    if args.port:
        return args.port
    from . import config
    try:
        return int(json.loads((config.CONFIG_DIR / "server.json").read_text())["local"])
    except (OSError, ValueError, KeyError):
        return 11500


def _call(port: int, method: str, path: str) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=b"" if method == "POST" else None,
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=15) as r:
        return json.loads(r.read().decode())


def client(args) -> int:
    port = _port(args)
    try:
        if args.cmd == "pair":
            d = _call(port, "POST", "/api/pairing/start")
            if args.json:
                print(json.dumps(d))
            else:
                print(f"Code d'appairage / pairing code: {d['code']}  (valid {int(d['expires_in'] // 60)} min)")
            return 0
        hello = _call(port, "GET", "/api/hello")
        st = _call(port, "GET", "/api/state")
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"madalean: server not reachable on 127.0.0.1:{port} ({e})", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"hello": hello, "jobs": st["jobs"]["active"], "system": st["system"]}, default=str))
        return 0
    act = st["jobs"]["active"]
    gpu = (st["system"]["monitor"] or {}).get("gpu") or {}
    print(f"Madalean {hello['version']} on {hello['host_name']}{' (demo)' if hello.get('demo') else ''} — "
          f"brain: {st['brain']}, mode: {st['settings']['mode']}")
    print(f"projects: {len(st['projects'])}, dossiers: {len(st['dossiers'])}, library: {st['library']['count']}")
    print(f"jobs running: {len(act)}" + "".join(f"\n  {j['id']} {j['dossier_id']} {j['state']} {j['stage']}"
                                                for j in act))
    if gpu:
        print(f"GPU: {gpu.get('name')} {gpu.get('used')}/{gpu.get('total')} MiB")
    loc = st["models"].get("local") or {}
    print(f"local model: {loc.get('state')} {loc.get('model') or ''}")
    return 0
