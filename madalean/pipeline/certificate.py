"""« Certificat » (session S-AT, DECISIONS D52): the early proof strategy next to Mathlib-first.

When the statement has the shape of a certificate kind (madalean/certs), Sage computes a witness in Calcul's
sandbox with Madalean's fixed program, Madalean writes the Lean proof that checks it, and the job's strict Lean
check decides. No model is called. A success is a proof like any other (`ProveResult`, model
« certificat:<kind> »); a failure leaves the usual search untouched."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .. import certs
from ..certs import engine, producer
from ..i18n import msg
from ..logs import get

log = get("pipeline.certificate")
STRICT_TIMEOUT = 120
SAGE_SECONDS = 30


@dataclass
class CertificateResult:
    ok: bool = False
    code: str = ""
    kind: str = ""
    status: str = "none"
    witness: list[dict] = field(default_factory=list)
    checker: str = ""
    axioms: list | None = None
    reason: str = ""
    seconds: float = 0.0
    sage_seconds: float = 0.0

    @property
    def model(self) -> str:
        return f"certificat:{self.kind}"

    def witness_text(self) -> str:
        return "\n".join("- " + w["text"] for w in self.witness)


def matches(statement: str) -> list[str]:
    return certs.kinds_of(statement)


async def run(ctx, io, statement: str, ws, timeout_s: int) -> CertificateResult:
    """One attempt in the job's history, whatever the outcome (the user sees what was tried)."""
    t0 = time.monotonic()
    a = io.new_attempt("proof", "certificate")
    a.model = "certificat:sage+lean"
    a.summary = msg("Certificat : calcul d'un témoin par Sage…")["text"]
    io.update_attempt(a)

    def on_step(step: str, info: dict) -> None:
        if step == "lean":
            a.status, a.code = "compiling", info.get("code", "")
            a.summary = msg("Certificat : Lean vérifie le témoin…")["text"]
            io.update_attempt(a)

    async def check(code: str, name: str):
        return await io.check(code, ws, min(timeout_s, STRICT_TIMEOUT), name)
    o = await engine.certify(statement, ws, check, producer.for_ctx(ctx), sage_seconds=SAGE_SECONDS, on_step=on_step)
    res = CertificateResult(o.ok, o.code if o.ok else "", o.kind, o.status, o.witness, o.checker, o.axioms, o.reason,
                            time.monotonic() - t0, o.sage_seconds)
    title = msg(engine.KINDS[o.kind]["title"])["text"] if o.kind else ""
    a.gen_seconds, a.compile_seconds, a.code = o.sage_seconds, o.lean_seconds, o.code
    a.model = res.model if o.kind else a.model
    if o.ok:
        a.status = "accepted"
        a.summary = msg("Certificat vérifié par Lean ({title}).", title=title)["text"]
        a.errors_text = res.witness_text()
    else:
        a.status = "rejected" if o.status in ("rejected", "refuted", "no_witness") else "error"
        a.summary = summary(o.status, title, o.reason)["text"]
        a.errors_text = o.errors or o.reason
    io.update_attempt(a)
    return res


def summary(status: str, title: str, reason: str = "") -> dict:
    if status == "rejected":
        return msg("Certificat refusé par Lean ({title}) : le témoin calculé ne passe pas la vérification.", title=title)
    if status == "refuted":
        return msg("Le calcul indique que l'énoncé est faux ({title} : {why}).", title=title, why=reason)
    if status == "no_witness":
        return msg("Aucun témoin trouvé par Sage ({title}).", title=title)
    if status == "unavailable":
        return msg("Certificat impossible : SageMath n'est pas disponible ({title}).", title=title)
    return msg("Pas de certificat pour cet énoncé.")


async def tool_answer(ctx, statement: str, claim: str, ws, check) -> str:
    """The prover agent's tool « sage_witness »: a certificate for the theorem (empty claim) or for an auxiliary
    claim `BINDERS : PROP`. The model only sends a claim; the computation is Madalean's fixed producer in the Sage
    sandbox, and the answer is a proof only when the strict Lean check accepted it."""
    from .. import leancheck
    from . import probes as P
    target = statement
    claim = " ".join(claim.split())
    if claim:
        claim = re.sub(r"^\s*(theorem|lemma)\s+\S+\s*", "", claim.split(":=")[0]).strip()
        sig = P.split_statement(statement)
        pre = sig.preamble if sig is not None else leancheck.GOEDEL_HEADER
        target = f"{pre}\ntheorem madalean_witness {claim if claim.startswith((':', '(', '{', '[')) else ': ' + claim} := by sorry\n"
    kinds = matches(target)
    if not kinds:
        return ("No certificate kind matches this claim. Supported shapes: Nat.Prime n / ¬ Nat.Prime n, closed "
                "arithmetic, a ^ e % n = r, polynomial identities, equalities that follow from polynomial equations, "
                "linear and polynomial inequalities over ℝ or ℚ (hypotheses as binders), ∃ with number variables, "
                "¬ ∀, bounds on √q, π, exp 1, log 2, and ∀ n < bound over ℕ. Number variables need explicit types.")
    o = await engine.certify(target, ws, check, producer.for_ctx(ctx), sage_seconds=SAGE_SECONDS)
    if o.ok:
        body = "\n".join(ln for ln in o.code.split("\n") if not re.match(r"(import|open|set_option)\b", ln))
        wit = "\n".join("- " + w["text"] for w in o.witness)
        return (f"Certificate found ({o.kind}) and ACCEPTED by Lean (strict check).\nWitness:\n{wit}\n"
                f"Lean code (use it as is; for an auxiliary claim, put it above the theorem as a helper lemma):\n"
                f"```lean4\n{body.strip()}\n```")
    if o.status == "refuted":
        return f"The computation says this claim is FALSE ({o.kind}: {o.reason}). Do not try to prove it as stated."
    if o.status == "rejected":
        return f"A witness was computed ({o.kind}) but Lean refused the certificate proof:\n{o.errors[:1500]}"
    if o.status == "unavailable":
        return "The computer algebra system is not available on this machine."
    return f"No witness found ({o.kind or ', '.join(kinds)}: {o.reason or 'nothing found'})."
