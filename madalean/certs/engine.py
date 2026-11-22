"""« Sage calcule, Lean vérifie » (session S-AT, DECISIONS D52): from a statement to a Lean-checked certificate proof.

    statement ──read──▶ shape ──(Sage, sandboxed, fixed program)──▶ witness ──render──▶ Lean proof ──strict check──▶ verdict

Nothing is « vérifiée » here without the caller's strict Lean check (fresh Lean, no sorry, axiom probe). The
computation is not trusted: a witness that is wrong, or a proof that Lean refuses for any reason, gives `rejected`
with Lean's messages, never a proof."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .. import leancheck
from ..i18n import msg
from ..logs import get
from . import problem as PB
from . import render as RD
from .producer import DEFAULT_SECONDS, SageUnavailable

log = get("certs")
MAX_TASKS = 3
RANK = {"verified": 6, "refuted": 5, "rejected": 4, "no_witness": 3, "unavailable": 2, "none": 0}

# id -> (title, needs Sage, what Lean runs to check)
KINDS: dict[str, dict] = {
    "prime": {"title": "Primalité", "sage": True, "checker": "norm_num (< 100 000) · lucas_primality + decide"},
    "composite": {"title": "Nombre composé", "sage": True, "checker": "norm_num"},
    "arith": {"title": "Calcul sur des nombres", "sage": False, "checker": "norm_num / decide"},
    "powmod": {"title": "Puissance modulaire", "sage": False, "checker": "decide"},
    "identity": {"title": "Identité polynomiale", "sage": False, "checker": "ring"},
    "ideal": {"title": "Conséquence d'équations polynomiales", "sage": True, "checker": "linear_combination"},
    "linear": {"title": "Inégalités linéaires", "sage": True, "checker": "linarith"},
    "sos": {"title": "Inégalité polynomiale (somme de carrés)", "sage": True, "checker": "ring + positivity + linarith"},
    "exists": {"title": "Existence (témoin)", "sage": True, "checker": "norm_num / decide"},
    "counterexample": {"title": "Contre-exemple", "sage": True, "checker": "norm_num / decide"},
    "numeric": {"title": "Inégalité numérique", "sage": True, "checker": "norm_num + linarith"},
    "finite": {"title": "Vérification exhaustive", "sage": False, "checker": "decide"},
}


@dataclass
class Outcome:
    status: str = "none"             # verified | refuted | rejected | no_witness | unavailable | none
    kind: str = ""
    code: str = ""                   # the complete Lean file (meaningful when verified or rejected)
    witness: list[dict] = field(default_factory=list)      # i18n messages
    checker: str = ""
    axioms: list | None = None
    reason: str = ""                 # why there is no proof (producer's reason, or Lean's summary)
    errors: str = ""                 # Lean's messages when it refused the certificate
    sage_seconds: float = 0.0
    lean_seconds: float = 0.0
    seconds: float = 0.0
    tried: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "verified"

    def to_dict(self) -> dict:
        return {"status": self.status, "kind": self.kind, "title": msg(KINDS[self.kind]["title"]) if self.kind else None,
                "code": self.code, "witness": self.witness, "checker": self.checker, "axioms": self.axioms,
                "reason": self.reason, "errors": self.errors[:4000], "sage_seconds": round(self.sage_seconds, 2),
                "lean_seconds": round(self.lean_seconds, 2), "seconds": round(self.seconds, 2),
                "lines": len(self.code.splitlines()) if self.code else 0, "tried": self.tried}


def kinds_of(statement: str) -> list[str]:
    """The certificate kinds whose shape this statement has (cheap, no Sage, no Lean); [] for most statements."""
    try:
        pb = PB.read(statement)
        return [t.kind for t in PB.tasks(pb)] if pb is not None else []
    except Exception as e:  # noqa: BLE001 (a reader bug must never break a proof job)
        log.warning("certificate reader failed: %s", e)
        return []


async def certify(statement: str, ws, check: Callable[[str, str], Awaitable], produce=None, *,
                  sage_seconds: float = DEFAULT_SECONDS, on_step: Callable[[str, dict], None] | None = None) -> Outcome:
    """Try the certificate kinds that match `statement`, in order, until Lean accepts one.

    `check(code, theorem_name)` is the caller's STRICT Lean check (the code already carries the axiom probe) and
    returns a `CompileResult`; `produce(request, seconds)` runs the fixed producer in Sage (None: no Sage here)."""
    t0 = time.monotonic()
    best = Outcome()

    def keep(o: Outcome) -> None:
        nonlocal best
        if RANK[o.status] > RANK[best.status]:
            o.tried = best.tried
            best = o
    try:
        pb = await asyncio.to_thread(PB.read, statement)
        todo = await asyncio.to_thread(PB.tasks, pb) if pb is not None else []
    except Exception as e:  # noqa: BLE001
        log.warning("certificate reader failed: %s", e)
        return best
    fl = RD.flavor(ws)
    tried: list[dict] = []
    best.tried = tried
    for task in todo[:MAX_TASKS]:
        o = Outcome(kind=task.kind, tried=tried)
        if task.refuted:
            o.status, o.reason = "refuted", task.refuted
            tried.append({"kind": task.kind, "status": o.status})
            keep(o)
            continue
        ans = None
        if task.request is not None:
            if produce is None:
                o.status = "unavailable"
                tried.append({"kind": task.kind, "status": o.status})
                keep(o)
                continue
            if on_step:
                on_step("sage", {"kind": task.kind})
            req = dict(task.request)
            if req.get("kind") == "numeric":
                req["digits"] = RD.digits(fl)
            ts = time.monotonic()
            try:
                ans = await produce(req, sage_seconds)
            except SageUnavailable as e:
                o.status, o.reason = "unavailable", str(e)[:200]
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("certificate producer failed (%s): %s", task.kind, e)
                o.status, o.reason = "no_witness", "error"
            o.sage_seconds = time.monotonic() - ts
            if ans is not None and not ans.get("ok"):
                o.status, o.reason = "no_witness", str(ans.get("reason") or "error")[:200]
                if o.reason == "false" or (task.kind == "composite" and o.reason == "prime"):
                    o.status = "refuted"
            if o.status != "none":
                tried.append({"kind": task.kind, "status": o.status, "reason": o.reason})
                keep(o)
                continue
        try:
            rd = RD.render(pb, task, ans, fl)
            o.code = leancheck.assemble_proof(statement, rd.proof(pb.name))
        except (RD.BadWitness, leancheck.StatementError) as e:
            o.status, o.reason = "rejected", f"bad witness: {e}"[:200]
            tried.append({"kind": task.kind, "status": o.status, "reason": o.reason})
            keep(o)
            continue
        o.witness, o.checker = rd.witness, rd.checker
        if on_step:
            on_step("lean", {"kind": task.kind, "witness": rd.witness, "code": o.code})
        r = await check(leancheck.with_axiom_probe(o.code, pb.name), pb.name)
        o.lean_seconds = r.seconds
        if r.verdict.ok:
            o.status, o.axioms = "verified", r.verdict.axioms
            tried.append({"kind": task.kind, "status": o.status})
            keep(o)
            break
        o.status = "rejected"
        o.reason = r.verdict.summary
        o.errors = leancheck.errors_for_feedback(r.code, r.verdict) or r.infra_error or r.verdict.summary
        tried.append({"kind": task.kind, "status": o.status, "reason": o.reason})
        keep(o)
    best.seconds = time.monotonic() - t0
    return best
