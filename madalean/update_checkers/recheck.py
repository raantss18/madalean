"""Re-verification after a Lean library update (ARCHITECTURE §12): every proven dossier and every library entry of
the affected workspace is re-checked with the strict verdict. Before the checks start, the proven dossiers are marked
`extra.recheck.state = "pending"` (« à revérifier »); each one then becomes `ok` or `regressed` — a regression is
never hidden behind the old verdict: event `updates.recheck`, a thread event on the dossier, and the report in
`<config>/research/recheck.json`."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from .. import config, leancheck
from ..dossiers import closure
from ..i18n import msg


def proofs_of_workspace(ctx, ws_key: str) -> list[dict]:
    """Proven dossiers + library entries of a workspace, as {name, dossier, code} (for the installer's pre-switch
    verification and for the post-update re-check)."""
    out, seen = [], set()
    for d in ctx.repo.list():
        if d.proof_is_current and (d.workspace or ctx.settings.workspace) == ws_key:
            try:
                name = leancheck.theorem_name(d.proof)
            except leancheck.StatementError:
                continue
            out.append({"name": name, "dossier": d.id, "code": d.proof, "kind": "dossier"})
            seen.add(name)
    for e in ctx.library.entries:
        if e.workspace != ws_key or e.name in seen:
            continue
        code = leancheck.GOEDEL_HEADER + "\n\n".join(x.code.strip() for x in closure(ctx.library, [e])) + "\n"
        out.append({"name": e.name, "dossier": e.dossier, "code": code, "kind": "library"})
    return out


class Rechecker:
    def __init__(self, ctx, report_file: Path):
        self.ctx = ctx
        self.report_file = Path(report_file)
        self.running: asyncio.Task | None = None
        self.report: dict = config.read_json(self.report_file)[0] or {}

    def status(self) -> dict:
        return {"running": bool(self.running and not self.running.done()), "report": self.report}

    def start(self, ws_key: str, reason: str) -> asyncio.Task:
        if self.running and not self.running.done():
            self.running.cancel()
        self.running = self.ctx.spawn(self.run(ws_key, reason))
        return self.running

    async def run(self, ws_key: str, reason: str) -> dict:
        ctx = self.ctx
        ws = ctx.workspace(ws_key)
        items = proofs_of_workspace(ctx, ws_key)
        t0 = time.time()
        report = {"workspace": ws_key, "reason": reason, "started": t0, "ended": None, "total": len(items),
                  "ok": 0, "regressed": [], "errors": []}
        for it in items:
            d = ctx.repo.get(it["dossier"]) if it["kind"] == "dossier" else None
            if d is not None:
                d.extra["recheck"] = {"state": "pending", "reason": reason, "since": t0}
                await ctx.repo.save(d)
        self.report = report
        ctx.publish("updates.recheck", {"report": report})
        for it in items:
            if ws is None:
                report["errors"].append("no_workspace")
                break
            code = leancheck.with_axiom_probe(it["code"], it["name"])
            r = await ctx.lean.check(code, ws, ctx.settings.compile_timeout_s, it["name"], owner=f"recheck-{ws_key}")
            ok = r.verdict.ok
            d = ctx.repo.get(it["dossier"]) if it["kind"] == "dossier" else None
            if ok:
                report["ok"] += 1
            else:
                report["regressed"].append({"name": it["name"], "dossier": it["dossier"], "kind": it["kind"],
                                            "summary": r.verdict.summary,
                                            "errors": [e["text"][:300] for e in r.to_dict()["errors"][:3]]})
            if d is not None:
                d.extra["recheck"] = {"state": "ok" if ok else "regressed", "reason": reason, "since": t0,
                                      "checked": time.time(), "summary": r.verdict.summary}
                if not ok:
                    m = msg("Après la mise à jour ({reason}), Lean n'accepte plus cette preuve : à revérifier.",
                            reason=reason)
                    d.add_event("error", m["text"], key=m["key"], params=m["params"])
                await ctx.repo.save(d)
            ctx.publish("updates.recheck", {"item": {"name": it["name"], "dossier": it["dossier"], "ok": ok}})
        report["ended"] = time.time()
        self.report = report
        await asyncio.to_thread(config.atomic_write_text, self.report_file,
                                json.dumps(report, ensure_ascii=False, indent=1))
        ctx.publish("updates.recheck", {"report": report})
        if report["regressed"]:
            ctx.toast("Mise à jour : {n} preuve(s) à revérifier (voir la liste).", "warn", n=len(report["regressed"]))
        return report
