"""Running Madalean's fixed certificate producer in Sage (session S-AT, DECISIONS D52).

The program is always the same text: evalcore.py + sage_producer.py of this package. A request is JSON data. Both
travel base64-encoded inside one cell, so that nothing of it goes through Sage's preparser and no part of a
statement can become code. In the server the cell runs in the sandboxed Sage kernel of Calcul (`SageBridge`, same
confinement, memory and time limits as every Calcul cell)."""
from __future__ import annotations

import asyncio
import base64
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from ..logs import get

log = get("certs")
MARK = "MADALEAN_CERT "
KERNEL_KEY = "madalean-certificates"
DEFAULT_SECONDS = 30
MAX_REQUEST = 400_000


class SageUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def source() -> str:
    here = Path(__file__).parent
    return (here / "evalcore.py").read_text(encoding="utf-8") + "\n\n" + \
        (here / "sage_producer.py").read_text(encoding="utf-8")


def program(req: dict) -> str:
    """The cell text: Madalean's fixed program and the request, both as base64 data."""
    data = json.dumps(req)
    if len(data) > MAX_REQUEST:
        raise ValueError("request too large")
    b = lambda s: base64.b64encode(s.encode("utf-8")).decode("ascii")  # noqa: E731
    return ("import base64 as _madalean_b64\n"
            f"exec(compile(_madalean_b64.b64decode('{b(source())}').decode('utf-8'), '<madalean-certificates>', "
            f"'exec'), {{'__name__': 'madalean_certificates', "
            f"'_madalean_cert_req': _madalean_b64.b64decode('{b(data)}').decode('utf-8')}})\n"
            "del _madalean_b64\n")


def parse(stdout: str) -> dict:
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(MARK):
            try:
                d = json.loads(line[len(MARK):])
            except ValueError:
                break
            return d if isinstance(d, dict) else {"ok": False, "reason": "error"}
    return {"ok": False, "reason": "no_output"}


class BridgeProducer:
    """The production path: the sandboxed Sage kernel of Calcul, one warm kernel for all certificates."""

    def __init__(self, bridge):
        self.bridge = bridge

    def available(self) -> bool:
        try:
            return bool(self.bridge.available().get("sage"))
        except Exception:  # noqa: BLE001
            return False

    async def __call__(self, req: dict, seconds: float = DEFAULT_SECONDS) -> dict:
        if not self.available():
            raise SageUnavailable("sage")
        req = {**req, "seconds": seconds}
        res = await self.bridge.run(KERNEL_KEY, "sage", program(req), timeout=seconds + 15, max_output=2_000_000)
        if res.status in ("unavailable", "died"):
            raise SageUnavailable(res.error[:200] or res.status)
        if res.status != "ok":
            return {"ok": False, "reason": "timeout" if res.status == "timeout" else "error",
                    "detail": (res.error or res.status)[:300]}
        return parse(res.stdout)


class SubprocessProducer:
    """The same program run by the installed Sage's Python, without a kernel. NOT sandboxed: for the tests and the
    benchmark script only (they pass their own statements); never used by the server."""

    def __init__(self, python: str, workdir: Path):
        self.python, self.workdir = python, Path(workdir)

    def available(self) -> bool:
        return bool(self.python)

    def run(self, req: dict, seconds: float = DEFAULT_SECONDS) -> dict:
        from .. import syntaxcards
        env = syntaxcards._sage_env(self.workdir)
        try:
            p = subprocess.run([self.python, "-c", program({**req, "seconds": seconds})], capture_output=True,
                               text=True, env=env, timeout=seconds + 60)
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "timeout"}
        out = parse(p.stdout)
        if out.get("reason") == "no_output":
            out["detail"] = p.stderr[-400:]
        return out

    async def __call__(self, req: dict, seconds: float = DEFAULT_SECONDS) -> dict:
        return await asyncio.to_thread(self.run, req, seconds)


def bridge_of(ctx):
    """The server's Sage bridge (the research workshop's, else Calcul's); None when there is none."""
    rs = getattr(ctx, "research", None)
    if rs is not None and getattr(rs, "bridge", None) is not None:
        return rs.bridge
    wb = getattr(ctx, "workbench", None)
    if wb is not None and hasattr(wb, "bridge"):
        try:
            return wb.bridge()
        except Exception:  # noqa: BLE001
            return None
    return None


def for_ctx(ctx):
    """The producer of a running server: a test double set on the context wins (`ctx.cert_producer`)."""
    custom = getattr(ctx, "cert_producer", None)
    if custom is not None:
        return custom
    br = bridge_of(ctx)
    return BridgeProducer(br) if br is not None else None
