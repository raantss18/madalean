"""« Chercher dans Mathlib d'abord » (S-K, TODO P0 #3): before any prover model, look for the theorem in Mathlib.

1. Candidates: the RAG index (premises of the Lean statement + search with the understood text) and the table of
   famous results (`rag.FAMOUS`: Cayley-Hamilton → `LinearMap.aeval_self_charpoly`, Riesz → `FiniteDimensional.
   of_isCompact_closedBall`, first isomorphism theorem → `LinearMap.quotKerEquivRange`…), only names that exist in
   the workspace's Mathlib.
2. ONE compilation tries short templates on the top-k (`exact N`, `exact N _`, `exact ⟨N _⟩`, `simpa using N`,
   `apply N` with side goals by assumption / norm_num, also after `intros`); `exact?` runs once, in parallel, in its own file (unless the statement check already
   ran it).
3. Otherwise the general model may write a 1–5 line proof that uses one of the candidates (≤ 2 calls, Lean-checked).
Success → the proof is recorded with the model « mathlib:<name> » and the explanation cites the lemma. Failure → the
candidates are handed to the provers as hints. Every proof is re-checked with the strict verdict."""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field

from .. import leancheck
from ..brain import rag
from ..brain.api import BrainError
from ..i18n import msg
from ..logs import get
from . import probes as P

log = get("pipeline.mathlib")

K = 12
BATCH_TIMEOUT = 120
EXACT_TIMEOUT = 60
STRICT_TIMEOUT = 90
ADAPT_CALLS = 2
INDEX_WAIT = 90
KINDS = {"theorem", "lemma", "def", "abbrev", "alias", "structure", ""}
TEMPLATES = ["exact {n}", "exact {n} _", "exact ⟨{n} _⟩", "simpa using {n}",
             # side goals after `apply`: hypotheses first (they fix the metavariables), then numerals (`0 < 1`)
             "apply {n}\nall_goals try assumption\nall_goals try norm_num",
             # hypotheses written as implications in the conclusion (`IsCompact … → FiniteDimensional …`)
             "intros\napply {n}\nall_goals try assumption\nall_goals try norm_num"]


@dataclass
class MathlibResult:
    ok: bool = False
    code: str = ""                  # the full checked proof file
    lemma: str = ""                 # the Mathlib name used
    tactic: str = ""
    source: str = ""                # template | exact? | adapted | check
    model: str = ""                 # model that adapted the lemma (adapted only)
    axioms: list | None = None
    candidates: list[dict] = field(default_factory=list)   # [{name, signature}] tried, best first
    seconds: float = 0.0

    def hint(self, n: int = 8) -> str:
        """For the provers when Mathlib-first failed."""
        if not self.candidates:
            return ""
        lines = [f"- {c['name']} : {c.get('signature', '')[:300]}" for c in self.candidates[:n]]
        return ("Mathlib lemmas that look relevant (they exist in this Mathlib; none closed the goal directly):\n"
                + "\n".join(lines))


def lemma_in(tactic: str, names: list[str]) -> str:
    """The candidate (or any qualified name) a tactic such as `exact LinearMap.aeval_self_charpoly f` uses."""
    for n in names:
        if re.search(rf"(?<![\w.]){re.escape(n)}(?![\w'])", tactic):
            return n
    m = re.search(r"\b([A-Z][\w']*(?:\.[\w'₀-₉]+)+|[a-z][\w']*_[\w'₀-₉.]+)", tactic)
    return m.group(1) if m else ""


async def candidates(retriever, ws_key: str, statement: str, texts: list[str], k: int = K) -> list[dict]:
    """Famous names first (exact lookup), then premises of the Lean statement, then the text search."""
    if retriever is None:
        return []
    ensure = getattr(retriever, "ensure", None)
    if ensure is not None:
        try:
            await asyncio.wait_for(ensure(ws_key, INDEX_WAIT), INDEX_WAIT + 5)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001 (no index yet: fewer candidates, never an error)
            pass
    out: list[dict] = []
    seen: set[str] = set()

    def add(ds):
        for d in ds or []:
            n = d.get("name") or ""
            if not n or n in seen or d.get("deprecated") or (d.get("kind") or "") not in KINDS:
                continue
            if leancheck.exec_risks(n) or not re.fullmatch(r"[\w'.₀-₉ᵢ]+", n):
                continue                    # never put a name that the D28 gate refuses into the batch
            seen.add(n)
            out.append(d)

    for t in texts:
        for n in rag.famous(t or ""):
            if n in seen:
                continue
            try:
                d = await retriever.declaration(ws_key, n)
            except Exception:  # noqa: BLE001
                d = None
            if d:
                add([{**d, "famous": True}])
    try:
        add(await retriever.premises(ws_key, statement, k))
    except Exception as e:  # noqa: BLE001
        log.info("premises failed: %s", e)
    for t in texts:
        if t and len(out) < 2 * k:
            try:
                add(await retriever.search(ws_key, t[:600], 8))
            except Exception as e:  # noqa: BLE001
                log.info("search failed: %s", e)
    return out[:k]


ADAPT_PROMPT = (
    "Prove the following Lean 4 theorem (Mathlib) with a SHORT proof (1 to 5 tactic lines) that uses one of the "
    "Mathlib results listed below. The theorem is very likely one of them, up to notation, coercions, argument "
    "order, implicit arguments or an equivalent formulation.\n\n```lean4\n{statement}```\n\n"
    "Mathlib results (they exist; the signature follows the name, `variables` are the section variables):\n{lemmas}\n\n"
    "Answer with ONE ```lean4 block containing the complete theorem with its proof (same name, same statement), "
    "or with the single word NONE if none of these results applies."
)


def _lemma_lines(cands: list[dict]) -> str:
    lines = []
    for c in cands:
        v = f" (variables: {c['variables'][:300]})" if c.get("variables") else ""
        lines.append(f"- {c['name']} : {(c.get('signature') or '?')[:400]}{v}")
    return "\n".join(lines)


class MathlibFirst:
    def __init__(self, io, mode: str, retriever, lean_real: bool = True, use_model: bool = True):
        self.io, self.mode, self.retriever = io, mode, retriever
        self.lean_real, self.use_model = lean_real, use_model

    async def run(self, statement: str, ws, texts: list[str], timeout_s: int, quick: tuple[str, str] | None = None,
                  ) -> MathlibResult:
        t0 = time.monotonic()
        res = MathlibResult()
        sig = P.split_statement(statement)
        if sig is None or not self.lean_real:
            return res
        name = leancheck.theorem_name(statement)
        cands = await candidates(self.retriever, ws.key, statement, texts)
        res.candidates = [{"name": c["name"], "signature": c.get("signature", ""),
                           **({"variables": c["variables"]} if c.get("variables") else {})} for c in cands]
        a = self.io.new_attempt("proof", "mathlib")
        a.model = "mathlib:search"
        a.summary = msg("Recherche dans Mathlib : {n} résultats candidats.", n=len(cands))["text"]
        self.io.update_attempt(a)
        # a quick proof already found by the statement check (`exact?`, `simp`…) is tried first
        tries: list[tuple[str, str, str]] = []
        if quick and quick[0]:
            tries.append((quick[0], "check", lemma_in(quick[0], [c["name"] for c in cands])))
        probes: list[P.Probe] = []
        head = f"{sig.binders} : {sig.concl}"
        for i, c in enumerate(cands):
            for j, tpl in enumerate(TEMPLATES):
                tac = tpl.format(n=c["name"])
                probes.append(P.Probe(f"madalean_mlf_{i}_{j}", P.decl(f"madalean_mlf_{i}_{j}", head, tac, 40000),
                                      "mathlib", {"tactic": tac, "lemma": c["name"]}))
        exq = [] if quick else [P.Probe("madalean_exact", P.decl("madalean_exact", head, "exact?", 60000), "pos",
                                        {"tactic": "exact?"})]
        a.status = "compiling"
        self.io.update_attempt(a)
        jobs = [P.run_batch(self.io, ws, sig.preamble, probes, BATCH_TIMEOUT)]
        if exq:
            jobs.append(P.run_batch(self.io, ws, sig.preamble, exq, EXACT_TIMEOUT))
        secs = await asyncio.gather(*jobs, return_exceptions=True)
        a.compile_seconds = sum(s for s in secs if isinstance(s, (int, float)))
        for p in probes:
            if p.ok:
                tries.append((p.meta["tactic"], "template", p.meta["lemma"]))
        for p in exq:
            if p.suggestion and "?" not in p.suggestion:
                tries.append((p.suggestion, "exact?", lemma_in(p.suggestion, [c["name"] for c in cands])))
        for tac, src, lemma in tries[:4]:
            ok = await self._accept(res, statement, name, ws, tac, src, lemma, timeout_s)
            if ok:
                break
        if not res.ok and self.use_model and cands:
            await self._adapt(res, statement, name, ws, cands[:6], timeout_s)
        a.status = "accepted" if res.ok else "rejected"
        a.code = res.code
        a.summary = (msg("Trouvé dans Mathlib : {name}.", name=res.lemma or res.tactic)["text"] if res.ok else
                     msg("Rien de directement applicable dans Mathlib ({n} candidats essayés).", n=len(cands))["text"])
        a.errors_text = "\n".join(f"{c['name']} : {c.get('signature', '')[:200]}" for c in cands)
        self.io.update_attempt(a)
        res.seconds = time.monotonic() - t0
        return res

    async def _accept(self, res: MathlibResult, statement: str, name: str, ws, tac: str, src: str, lemma: str,
                      timeout_s: int) -> bool:
        try:
            code = leancheck.assemble_proof(statement, f"theorem {name} := by\n  {tac}")
        except leancheck.StatementError:
            return False
        r = await self.io.check(leancheck.with_axiom_probe(code, name), ws, min(timeout_s, STRICT_TIMEOUT), name)
        if not r.verdict.ok:
            return False
        res.ok, res.code, res.tactic, res.source, res.axioms = True, code, tac, src, r.verdict.axioms
        res.lemma = lemma or lemma_in(tac, [c["name"] for c in res.candidates])
        return True

    async def _adapt(self, res: MathlibResult, statement: str, name: str, ws, cands: list[dict], timeout_s: int):
        body = statement[statement.rfind("theorem"):] if "theorem" in statement else statement
        messages = [{"role": "user", "content": ADAPT_PROMPT.format(statement=body, lemmas=_lemma_lines(cands))}]
        for k in range(ADAPT_CALLS):
            a = self.io.new_attempt("proof", "mathlib")
            try:
                c = await asyncio.wait_for(self.io.complete("prove", messages, a, temperature=0.3, max_tokens=4000,
                                                            extra={"top_p": 0.95}, mode=self.mode, stage="proof"), 240)
            except (asyncio.TimeoutError, BrainError) as e:
                a.status, a.summary = "error", msg("La génération a échoué.")["text"]
                a.errors_text = str(e)[:500]
                self.io.update_attempt(a)
                return
            a.raw, a.model, a.finish, a.gen_seconds, a.tokens = c.text, c.model.key, c.finish, c.seconds, c.tokens_out
            text = leancheck.clean_model_text(c.text)
            code = leancheck.extract_code(text)
            if code is None:                      # « NONE », or no Lean block
                a.status, a.summary = "rejected", msg("Aucun résultat de Mathlib ne s'applique directement.")["text"]
                self.io.update_attempt(a)
                return
            try:
                a.code = leancheck.assemble_proof(statement, code)
            except leancheck.StatementError as e:
                a.status, a.summary = "rejected", str(e)
                self.io.update_attempt(a)
                return
            a.status = "compiling"
            self.io.update_attempt(a)
            r = await self.io.check(leancheck.with_axiom_probe(a.code, name), ws, min(timeout_s, STRICT_TIMEOUT), name)
            a.compile_seconds, a.summary = r.seconds, r.verdict.summary
            if r.verdict.ok:
                a.status = "accepted"
                self.io.update_attempt(a)
                used = lemma_in(a.code.split(":= by", 1)[-1], [x["name"] for x in cands])
                res.ok, res.code, res.source, res.model, res.axioms = True, a.code, "adapted", c.model.key, r.verdict.axioms
                res.lemma, res.tactic = used, ""
                return
            a.status = "rejected"
            a.errors_text = leancheck.errors_for_feedback(r.code, r.verdict)
            self.io.update_attempt(a)
            messages = messages + [{"role": "assistant", "content": c.text},
                                   {"role": "user", "content": "Lean rejects this proof:\n" + a.errors_text[:3000]
                                    + "\nGive a corrected complete theorem in one ```lean4 block (or NONE)."}]
