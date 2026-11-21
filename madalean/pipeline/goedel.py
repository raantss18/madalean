"""The 1.1.4 prove loop and formalizer, on asyncio and on top of the Brain (role "prove"/"formalize").

Behaviour preserved exactly (DECISIONS D4, D13, D22, D24, D25, D26): verbatim Goedel prompts, ≤ 2 corrections per
line of attack, a fresh sample when Lean returns the same feedback twice or a rejected name comes back, the
conversation restarts instead of asking for fewer than 8 192 tokens, user hint appended with HINT_TEMPLATE only,
names rejected by Lean recalled in every fresh sample, real-name suggestions after unknown names, loop/rambling
answers ended as « loop » and followed by a fresh sample."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import config, leancheck, names
from ..brain.api import BrainError
from ..i18n import msg
from ..jobs import Attempt
from .io import InfraError, StageIO, is_context_error


@dataclass
class ProveResult:
    ok: bool
    code: str = ""
    summary: dict = field(default_factory=dict)
    attempts: list[Attempt] = field(default_factory=list)
    model: str = ""
    axioms: list[str] | None = None
    seconds: float = 0.0


class GoedelProver:
    MAX_CORRECTIONS = 2      # correction rounds on one line of attack, then a fresh sample (D24)
    MIN_GEN_TOKENS = 8192    # never ask for an answer shorter than this: restart the conversation instead (D24)

    def __init__(self, io: StageIO, mode: str = "local"):
        self.io = io
        self.mode = mode

    async def run(self, statement: str, ws, n_attempts: int, sampling: config.SamplingSettings, timeout_s: int,
                  ctx: int, refine: tuple[str, str] | None = None, hint: str = "") -> ProveResult:
        self.statement = leancheck.prepare_statement(statement)
        self.name = leancheck.theorem_name(self.statement)
        self.ws, self.n, self.sampling, self.timeout_s, self.ctx = ws, max(1, n_attempts), sampling, timeout_s, ctx
        self.attempts: list[Attempt] = []
        if refine:
            self._base = leancheck.refine_messages(self.statement, *refine)
        else:
            self._base = [{"role": "user", "content": leancheck.initial_prompt(self.statement, hint)}]
        self.messages = list(self._base)
        self._round, self._last_feedback = 0, None
        self._bad_names: list[str] = []
        names.get(ws)                    # start indexing the workspace's declarations in the background
        res = ProveResult(False, attempts=self.attempts)
        while len(self.attempts) < self.n:
            kind = ("correction" if len(self.messages) > len(self._base) else
                    "refinement" if len(self._base) > 1 else "initial")
            a = self.io.new_attempt("proof", kind)
            self.attempts.append(a)
            max_tokens = self._fit_messages()
            try:
                c = await self.io.complete("prove", list(self.messages), a, temperature=sampling.temperature,
                                           max_tokens=max_tokens, extra={"top_p": sampling.top_p}, mode=self.mode,
                                           stage="proof")
            except BrainError as e:
                if is_context_error(e) and len(self.messages) > len(self._base):
                    # prompt too long for the context window: shorten the history, retry this same attempt
                    nb = len(self._base)
                    self.messages = (list(self._base) if len(self.messages) <= nb + 2
                                     else list(self._base) + self.messages[nb + 2:])
                    self.attempts.pop()
                    self.io.drop_attempt(a)
                    continue
                a.status, a.summary, a.errors_text = "error", msg("La génération a échoué.")["text"], str(e)
                self.io.update_attempt(a)
                raise InfraError("no_model" if e.kind == "no_model" else "generation", str(e)) from e
            a.raw, a.model, a.finish = c.text, c.model.key, c.finish
            a.gen_seconds, a.tokens = c.seconds, c.tokens_out
            res.model = c.model.key
            if c.finish == "loop":
                a.status, a.summary = "rejected", msg("L'IA tournait en rond : essai interrompu, nouvel essai.")["text"]
                self.io.update_attempt(a)
                self._restart()
                continue
            code = leancheck.extract_code(a.raw)
            if code is None:
                a.status = "rejected"
                a.summary = (msg("Réponse trop longue, coupée avant le code Lean.") if a.finish == "length"
                             else msg("Le modèle n'a pas produit de code Lean."))["text"]
                self.io.update_attempt(a)
                self._restart()
                continue
            try:
                a.code = leancheck.assemble_proof(self.statement, code)
            except leancheck.StatementError as e:
                a.status, a.summary = "rejected", str(e)
                self.io.update_attempt(a)
                self._restart()
                continue
            a.status = "compiling"
            self.io.update_attempt(a)
            r = await self.io.check(leancheck.with_axiom_probe(a.code, self.name), ws, timeout_s, self.name)
            a.compile_seconds = r.seconds
            if r.infra_error and not r.verdict.errors:
                a.status, a.summary = "error", r.verdict.summary
                self.io.update_attempt(a)
                raise InfraError("workspace", r.infra_error)
            a.summary = r.verdict.summary
            if r.verdict.ok:
                a.status = "accepted"
                self.io.update_attempt(a)
                res.ok, res.code, res.axioms = True, a.code, r.verdict.axioms
                res.seconds = sum(x.gen_seconds + x.compile_seconds for x in self.attempts)
                res.summary = msg("Preuve trouvée et vérifiée par Lean (essai {i}).", i=len(self.attempts))
                return res
            a.status = "rejected"
            feedback = leancheck.errors_for_feedback(r.code, r.verdict)
            idx = names.get(ws)
            missing = names.missing_names(feedback, idx)
            repeated = any(nm in self._bad_names for nm in missing)
            for nm in missing:
                if nm not in self._bad_names:
                    self._bad_names.append(nm)
            if idx is not None:
                feedback += idx.feedback_note(feedback)
            a.errors_text = feedback
            self.io.update_attempt(a)
            if self._round >= self.MAX_CORRECTIONS or feedback == self._last_feedback or repeated:
                self._restart()
            else:
                self._round += 1
                self._last_feedback = feedback
                self.messages = self.messages + [
                    {"role": "assistant", "content": a.raw},
                    {"role": "user", "content": leancheck.correction_prompt(self._round - 1, feedback)},
                ]
        res.summary = msg("Aucune preuve trouvée après {n} essais.", n=self.n)
        res.seconds = sum(x.gen_seconds + x.compile_seconds for x in self.attempts)
        return res

    def _restart(self) -> None:
        """Fresh sample from the original task: forget the line of attack, not the invented names."""
        self.messages = list(self._base)
        self._round, self._last_feedback = 0, None
        note = names.avoid_note(self._bad_names, names.get(self.ws))
        if note:
            self.messages[0] = {**self.messages[0], "content": self.messages[0]["content"] + note}

    def _fit_messages(self) -> int:
        budget = self.ctx - 256

        def est(ms):
            return int(sum(len(m["content"]) for m in ms) / 3.0) + 50
        nb = len(self._base)
        while est(self.messages) > budget - 2048 and len(self.messages) > nb + 2:
            del self.messages[nb:nb + 2]
        floor = min(self.MIN_GEN_TOKENS, self.sampling.max_tokens)
        if est(self.messages) > budget - floor and len(self.messages) > nb:
            self._restart()
        return max(512, min(self.sampling.max_tokens, budget - est(self.messages)))


@dataclass
class FormalizeResult:
    ok: bool
    statement: str = ""                 # best statement so far (with `:= by sorry`), kept even if Lean refuses it
    errors: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    model: str = ""


class Formalizer:
    """Natural language → Lean statement: generation + Lean check of the statement, up to `tries` (D12)."""

    def __init__(self, io: StageIO, mode: str = "local"):
        self.io, self.mode = io, mode

    async def run(self, text: str, ws, tries: int, timeout_s: int, name: str = leancheck.DEFAULT_THEOREM_NAME,
                  profile: str = "", previous: str = "", request: str = "") -> FormalizeResult:
        text = leancheck.formalize_input(text, profile, previous, request)
        n = max(1, tries)
        res = FormalizeResult(False)
        feedback = ""
        for i in range(n):
            a = self.io.new_attempt("statement", "translation")
            try:
                c = await self.io.complete("formalize", [{"role": "user", "content": leancheck.formalize_prompt(
                                               text + feedback, name)}],
                                           a, temperature=0.9, max_tokens=12000,
                                           extra={"top_p": 0.95, "top_k": 20}, mode=self.mode, stage="statement")
            except BrainError as e:
                a.status, a.summary, a.errors_text = "error", msg("La traduction a échoué.")["text"], str(e)
                self.io.update_attempt(a)
                raise InfraError("no_model" if e.kind == "no_model" else "generation", str(e)) from e
            a.raw, a.model, a.finish, a.gen_seconds, a.tokens = c.text, c.model.key, c.finish, c.seconds, c.tokens_out
            res.model = c.model.key
            # a model that degenerates at the end (seen with free reasoning models: endless `import Mathlib.…` lines
            # after a complete statement) is stopped by the loop guard; a complete ```lean4 block written before
            # the loop is still a candidate statement — Lean decides, as for any other answer (S-K)
            code = leancheck.extract_code(a.raw)
            if code is not None and c.finish == "loop" and not re.search(r"\btheorem\b", code):
                code = None
            if code is None:
                a.status = "rejected"
                a.summary = (msg("L'IA tournait en rond : nouvel essai.") if c.finish == "loop" else
                             msg("Pas d'énoncé Lean dans la réponse : nouvel essai."))["text"]
                self.io.update_attempt(a)
                continue
            try:
                a.code = leancheck.normalize_formal_statement(code)
            except leancheck.StatementError as e:
                a.status, a.summary = "rejected", f"{e} " + msg("Nouvel essai.")["text"]
                self.io.update_attempt(a)
                continue
            res.statement = a.code
            a.status = "compiling"
            self.io.update_attempt(a)
            r = await self.io.check(a.code, ws, timeout_s, None)
            a.compile_seconds = r.seconds
            if r.infra_error and not r.verdict.errors:
                a.status, a.summary = "error", r.verdict.summary
                self.io.update_attempt(a)
                raise InfraError("workspace", r.infra_error)
            res.errors = r.verdict.errors
            if not r.verdict.errors and not r.timed_out:
                a.status, a.summary = "accepted", msg("Énoncé valide en Lean (à relire)")["text"]
                self.io.update_attempt(a)
                res.ok = True
                res.summary = msg("Énoncé traduit : Lean le comprend. Relisez-le avant de prouver.")
                return res
            a.status = "rejected"
            a.summary = (msg("Lean refuse cette traduction : nouvel essai.") if i + 1 < n
                         else msg("Lean refuse cette traduction."))["text"]
            a.errors_text = "\n".join(msg("ligne {line} : {text}", line=m.line, text=m.text)["text"]
                                      for m in r.verdict.errors)
            self.io.update_attempt(a)
            # the next attempt sees what Lean said (S-K: the user's Cayley-Hamilton / Riesz translations failed 3×
            # on the same small mistake: `aeval` without `Polynomial.`, `CompleteSpace 𝕜 E`)
            errs = "\n".join(f"line {m.line}: {m.text[:400]}" for m in r.verdict.errors[:4])
            feedback = (f"\n\nA previous attempt was:\n```lean4\n{leancheck._body(a.code)}\n```\nLean rejected it:\n"
                        f"{errs}\nAvoid this mistake (write fully qualified Mathlib names, e.g. `Polynomial.aeval`, "
                        "`Polynomial R` "
                        "instead of `R[X]` — only the header's namespaces are open — and "
                        "check the number of arguments of each class).\n")
        res.summary = msg("La traduction ne compile pas encore : corrigez-la dans l'éditeur ou reformulez le problème.")
        return res
