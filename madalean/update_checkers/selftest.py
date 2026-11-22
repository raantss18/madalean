"""Health self-test of the sandboxed tools after each update (session S-AC, docs/CALCUL.md §10, docs/SECURITY.md).

A regression like the one of 2026-11-22 (Maxima could not write its cache: every integral of the Calcul screen
failed with « Read-only file system: '/nonexistent' ») must be caught before the user meets it. This module runs,
in the REAL sandboxes:

- SageMath and Python: the fast subset of `research/sagesmoke.py` in a fresh kernel started through Madalean's
  kernelspec (private home, no network, rlimits);
- Lean: a tiny file through `ctx.lean.check` (gate + leansandbox) and a probe of the sandbox (writable private
  home, only `lo`, the user's home absent);
- LaTeX: a tiny document through `export.compile_pdf` (tex_confine) and the same home probe.

When: at start (after a delay) and every 30 minutes the fingerprint of the tools (Madalean version, kernelspecs,
the Sage library, the prefix's component versions, the Lean toolchain, tectonic) is compared with the one of the
last report; a change (an update of Sage, Madalean, Lean, TeX…) runs the test in the background. Also after every
update applied by the updates manager, and on demand from Réglages › Système › État de santé (« Réparer »: the
kernels' private homes are moved aside — corrupt caches are the usual culprit — then everything is tested again).
Results: `<config>/selftest.json`, health lines `selftest_<part>`, event `system.selftest`, a toast on failure.
Never in tests (MADALEAN_NO_SELFTEST / MADALEAN_NO_UPDATE_CHECK) nor in demo mode."""
from __future__ import annotations

import asyncio
import glob
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from .. import config
from ..i18n import msg

PARTS = ("sage", "python", "lean", "tex")
NAMES = {"sage": "SageMath", "python": "Python", "lean": "Lean", "tex": "LaTeX"}
START_DELAY_S = 180.0
EVERY_S = 1800.0


def _mtime(p) -> float:
    try:
        return round(os.stat(p).st_mtime, 1)
    except (OSError, TypeError):
        return 0.0


def fingerprint(ctx) -> dict:
    """Cheap (stat calls only): what must change when a tool is updated."""
    from .. import __version__
    from ..research import sagebridge
    fp: dict = {"madalean": __version__, "launcher": _mtime(sagebridge.__file__)}
    for lang, (_spec, base, _d, _l) in sagebridge.SPEC_NAMES.items():
        spec = sagebridge.find_kernelspec(base)
        if spec is None:
            fp[lang] = None
            continue
        exe = spec["argv"][0]
        files = [os.path.join(d, base, "kernel.json") for d in sagebridge.KERNEL_DIRS]
        fp[lang] = {"argv": spec["argv"][:3], "exe": _mtime(exe), "spec": max(_mtime(f) for f in files)}
        if lang == "sage":                      # the Sage library itself (pacman / the prefix's env)
            root = Path(os.path.realpath(exe)).parent.parent
            fp[lang]["lib"] = max([_mtime(f) for f in glob.glob(str(root / "lib/python3*/site-packages/sage/version.py"))]
                                  or [0.0])
    try:
        from ..deps import installer
        fp["deps"] = {k: (v or {}).get("version") for k, v in sorted(installer.load_state().items())
                      if isinstance(v, dict)}
    except Exception:  # noqa: BLE001
        fp["deps"] = {}
    ws = ctx.workspace() if hasattr(ctx, "workspace") else None
    fp["lean"] = {"ws": getattr(ws, "key", ""), "toolchain": getattr(ws, "toolchain", ""),
                  "bin": _mtime(getattr(ws, "lean_bin", None))} if ws is not None else None
    try:
        from ..export import tectonic_cmd
        tec = tectonic_cmd()
        fp["tex"] = {"tectonic": tec[0], "mtime": _mtime(tec[0])} if tec else None
    except Exception:  # noqa: BLE001
        fp["tex"] = None
    return fp


def auto_enabled(ctx) -> bool:
    return not (getattr(ctx, "demo", False) or os.environ.get("MADALEAN_NO_SELFTEST") == "1"
                or os.environ.get("MADALEAN_NO_UPDATE_CHECK") == "1")


class SelfTest:
    def __init__(self, ctx, report_file: Path):
        self.ctx = ctx
        self.report_file = Path(report_file)
        self.report: dict = config.read_json(self.report_file)[0] or {}
        self.running: asyncio.Task | None = None
        self.current: dict = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ state
    def is_running(self) -> bool:
        return bool(self.running and not self.running.done()) or self._lock.locked()

    def status(self) -> dict:
        return {"running": self.is_running(), "report": self.report, "current": self.current}

    def bridge(self):
        rs = getattr(self.ctx, "research", None)
        if rs is not None and getattr(rs, "bridge", None) is not None:
            return rs.bridge
        from ..research.sagebridge import SageBridge
        return SageBridge(self.ctx)

    # ------------------------------------------------------------ parts
    async def _kernel(self, language: str) -> dict:
        from ..research import sagesmoke
        br = self.bridge()
        if not (await asyncio.to_thread(br.available)).get(language):
            return {"state": "absent"}
        items = sagesmoke.items_for(language, fast=True, sandbox=br.sandbox_kind)
        rep = await sagesmoke.run(br, language, items)
        rep["state"] = "ok" if rep["ok"] else "failed"
        return rep

    async def _lean(self) -> dict:
        from .. import leansandbox
        ctx = self.ctx
        ws = ctx.workspace()
        if ws is None or getattr(ws, "problems", None):
            return {"state": "absent"}
        t0 = time.monotonic()
        items = []
        r = await ctx.lean.check("theorem madalean_selftest : 1 + 1 = 2 := rfl\n", ws,
                                 min(120, int(ctx.settings.compile_timeout_s or 120)), None, owner="selftest")
        items.append({"id": "compile", "label": "Compilation d'un petit fichier", "ok": bool(r.verdict.ok),
                      "detail": "" if r.verdict.ok else str(r.verdict.summary)[:300]})
        if getattr(ws, "path", None) is not None and Path(ws.path).is_dir():
            out = await asyncio.to_thread(self._probe, leansandbox.wrap(ws, ["/bin/sh", "-c", PROBE], []),
                                          leansandbox.lean_env(ws), Path(ws.path))
            items.append(_probe_item(out, bool(leansandbox.bwrap())))
        return _summary(items, t0)

    async def _tex(self) -> dict:
        from .. import export
        engines = await asyncio.to_thread(export._engines)
        if not engines:
            return {"state": "absent"}
        t0 = time.monotonic()
        root = self.ctx.paths.cache / "selftest" / "tex"
        await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
        tex = ("\\documentclass{article}\n\\begin{document}\nMadalean : $\\int_0^1 x^2\\,dx = \\frac13$\n"
               "\\end{document}\n")
        pdf, log, timed_out = await export.compile_pdf(tex, root, 120.0, engines[:1])
        items = [{"id": "compile", "label": "Compilation d'un petit document", "ok": bool(pdf and pdf[:4] == b"%PDF"),
                  "detail": "" if pdf else ("timeout" if timed_out else log[-300:])}]
        work = Path(await asyncio.to_thread(tempfile.mkdtemp, prefix="probe-", dir=root))
        try:
            env = export.tex_env()
            cmd = export.tex_confine(["/bin/sh", "-c", PROBE + 'mkdir -p "$TEXMFVAR" && touch "$TEXMFVAR/p" && '
                                      'echo TEXMFVAR_OK\n'], work, env)
            from .. import leansandbox
            out = await asyncio.to_thread(self._probe, cmd, env, work)
            it = _probe_item(out, bool(leansandbox.bwrap()))
            if "TEXMFVAR_OK" not in out:
                it.update(ok=False, detail=(it["detail"] + " TEXMFVAR")[:300])
            items.append(it)
        finally:
            await asyncio.to_thread(shutil.rmtree, work, True)
        return _summary(items, t0)

    @staticmethod
    def _probe(argv: list[str], env: dict, cwd: Path) -> str:
        import subprocess
        try:
            r = subprocess.run(argv, env=env, cwd=str(cwd), capture_output=True, text=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            return r.stdout + r.stderr
        except (OSError, subprocess.SubprocessError) as e:
            return f"probe failed: {e}"

    # ------------------------------------------------------------ run
    async def run(self, reason: str = "manual", parts: tuple[str, ...] = PARTS) -> dict:
        ctx = self.ctx
        async with self._lock:
            fp = await asyncio.to_thread(fingerprint, ctx)
            rep = {"reason": reason, "started": time.time(), "ended": None, "fingerprint": fp, "parts": {}}
            self.current = rep
            ctx.publish("system.selftest", {"running": True, "reason": reason})
            for part in parts:
                try:
                    res = await (self._kernel(part) if part in ("sage", "python") else
                                 self._lean() if part == "lean" else self._tex())
                except Exception as e:  # noqa: BLE001 (a broken tool is a failed test, never a crash)
                    res = {"state": "failed", "error": f"{type(e).__name__}: {e}"[:500], "items": []}
                res["t"] = time.time()
                rep["parts"][part] = res
                ctx.publish("system.selftest", {"running": True, "part": part, "state": res.get("state")})
            rep["ended"] = time.time()
            self.report, self.current = rep, {}
            await asyncio.to_thread(config.atomic_write_text, self.report_file,
                                    json.dumps(rep, ensure_ascii=False, indent=1))
            ctx.publish("system.selftest", {"running": False, "report": rep})
            bad = [NAMES[p] for p, r in rep["parts"].items() if r.get("state") == "failed"]
            if bad:
                ctx.toast("Auto-test après mise à jour : {names} ne fonctionne plus correctement. Voir Réglages › "
                          "Système › État de santé.", "warn", names=", ".join(bad))
            return rep

    def start(self, reason: str) -> asyncio.Task:
        if self.running and not self.running.done():
            return self.running
        self.running = self.ctx.spawn(self.run(reason))
        return self.running

    async def maybe_run(self, reason: str = "update") -> bool:
        """Run when the tools changed since the last report (or never ran)."""
        if self.is_running():
            return False
        fp = await asyncio.to_thread(fingerprint, self.ctx)
        if fp == self.report.get("fingerprint"):
            return False
        self.start(reason)
        return True

    async def loop(self, delay: float = START_DELAY_S, every: float = EVERY_S) -> None:
        await asyncio.sleep(delay)
        while True:
            try:
                await self.maybe_run()
            except Exception:  # noqa: BLE001
                from ..logs import get
                get("server").exception("self-test check failed")
            await asyncio.sleep(every)

    async def repair(self) -> dict:
        """Move the kernels' private homes aside (caches rebuilt at the next start; one backup kept), refresh the
        Lean workspaces, then test everything again."""
        root = self.bridge().workroot

        def move():
            home = root / ".home"
            old = root / ".home.old"
            if home.exists():
                shutil.rmtree(old, ignore_errors=True)
                home.rename(old)
        await asyncio.to_thread(move)
        if hasattr(self.ctx, "refresh_workspaces"):
            await self.ctx.refresh_workspaces()
        return await self.run("repair")

    # ------------------------------------------------------------ health lines
    def health(self) -> list[dict]:
        out = []
        running = self.is_running()
        for part in PARTS:
            name = NAMES[part]
            r = (self.current.get("parts") or {}).get(part) if running else None
            r = r or (self.report.get("parts") or {}).get(part)
            ok, level = True, "ok"
            if running and part not in (self.current.get("parts") or {}):
                m = msg("Auto-test {part} : en cours…", part=name)
            elif r is None:
                m = msg("Auto-test {part} : pas encore lancé (il se lance après chaque mise à jour).", part=name)
            elif r.get("state") == "absent":
                m = msg("Auto-test {part} : non installé, rien à tester.", part=name)
            elif r.get("state") == "ok":
                m = msg("Auto-test {part} : {n} essais réussis dans le bac à sable ({s} s, le {when}).", part=name,
                        n=len(r.get("items") or []), s=round(float(r.get("seconds") or 0)),
                        when=time.strftime("%d/%m %H:%M", time.localtime(r.get("t") or 0)))
            else:
                ok, level = False, "warn"
                failed = [i.get("label") or i.get("id") for i in r.get("items") or [] if not i.get("ok")]
                if failed:
                    m = msg("Auto-test {part} : {n} essai(s) en échec : {names}. « Réparer » réinitialise les caches "
                            "des outils et relance le test.", part=name, n=len(failed), names=", ".join(failed)[:400])
                else:
                    m = msg("Auto-test {part} : l'outil n'a pas démarré ({error}). « Réparer » réinitialise les "
                            "caches des outils et relance le test.", part=name,
                            error=str(r.get("error") or "?").splitlines()[0][:200])
            out.append({"id": f"selftest_{part}", "ok": ok, "level": level, "message": m})
        return out


PROBE = ('mkdir -p "$XDG_CACHE_HOME" && echo x > "$XDG_CACHE_HOME/madalean-probe" && [ "$HOME" != "' +
         os.path.expanduser("~") + '" ] && echo HOME_OK\n'
         '[ -e "' + os.path.expanduser("~") + '/.config" ] && echo SEES_HOME\n'
         'grep -c : /proc/net/dev | sed "s/^/IFACES=/"\n')


def _probe_item(out: str, sandboxed: bool) -> dict:
    ok = "HOME_OK" in out
    why = [] if ok else ["home"]
    if sandboxed:
        if "SEES_HOME" in out:
            ok, why = False, why + ["home visible"]
        if "IFACES=1" not in out:
            ok, why = False, why + ["network"]
    return {"id": "sandbox", "label": "Bac à sable : dossier personnel privé inscriptible" +
            (", sans réseau" if sandboxed else ""), "ok": ok, "detail": (" ".join(why) + " " + out[-200:]).strip()
            if not ok else ""}


def _summary(items: list[dict], t0: float) -> dict:
    ok = all(i["ok"] for i in items)
    return {"state": "ok" if ok else "failed", "ok": ok, "items": items, "passed": sum(i["ok"] for i in items),
            "failed": sum(not i["ok"] for i in items), "seconds": round(time.monotonic() - t0, 1)}


def selftest_checker(current):
    """Update checker (runs in a worker thread at each pass): when a tool changed, the self-test runs. Local only,
    never a candidate."""
    def check():
        ctx, loop = current()
        st = getattr(ctx, "selftest", None) if ctx is not None else None
        if st is not None and loop is not None and auto_enabled(ctx):
            asyncio.run_coroutine_threadsafe(st.maybe_run("update"), loop)
        return []
    check.__name__ = "check_selftest"
    return check


def install(ctx, loop=None) -> SelfTest | None:
    if not hasattr(ctx, "paths"):
        return None
    st = SelfTest(ctx, ctx.paths.config / "selftest.json")
    ctx.selftest = st
    if loop is not None and auto_enabled(ctx):
        try:
            ctx.spawn(st.loop())
        except RuntimeError:
            pass
    return st
