"""One job = one plan of stages run on one dossier (port of 1.1.4 `ui/pipeline.py` to asyncio + Brain).

Stages: understand → statement (+ notes) → proof → explanation (+ informal). `route` reads a follow-up message and
rewrites the rest of the plan (D26). Every event written to the thread records the model that produced it."""
from __future__ import annotations

import asyncio
import inspect
import re
import time
from typing import Any

from .. import leancheck, prompts
from ..brain.api import BrainError, Chunk, Completion, ModelRef
from ..dossiers import Dossier, closure, route, route_scores, with_lemmas
from ..errors import friendly
from ..i18n import language, msg
from ..jobs import Attempt, Job
from ..logs import get
from ..runtime.lean import workspace_info
from .goedel import Formalizer, GoedelProver, ProveResult
from .mathlib_first import MathlibFirst, MathlibResult
from .verify import CheckResult, StatementChecker
from .io import InfraError, LoopGuard, outer_cancelled
from . import tournament as tourn

log = get("pipeline")
STAGES = ("understand", "route", "statement", "notes", "verify", "proof", "explanation", "informal")
NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}
RAW_CAP = 200_000


def full_plan() -> list[dict]:
    return [{"stage": "understand"}, {"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}]


def stage_plan(d: Dossier, stage: str, text: str) -> list[dict]:
    plan = {"statement": [{"stage": "statement", "request": text}, {"stage": "proof"}, {"stage": "explanation"}],
            "proof": [{"stage": "proof", "request": text}, {"stage": "explanation"}],
            "explanation": [{"stage": "explanation", "request": text}]}[stage]
    if stage == "explanation" and not d.proof_is_current:
        plan = [{"stage": "proof"}, {"stage": "explanation", "request": text}]
    return plan


def plan_for_message(d: Dossier, text: str, stage: str, route_available: bool) -> tuple[list[dict], str]:
    """Plan for a follow-up message (1.1.4 `Pipeline.request`). Returns (plan, stage shown on the user's message).
    Mutates `d.problem` when nothing has been translated yet (the message completes the problem)."""
    if not d.statement:
        d.problem = (d.problem + "\n" + text).strip() if d.problem else text
        return full_plan(), "statement"
    if stage == "auto" and route_available:
        return [{"stage": "route", "request": text}], "auto"
    if stage == "auto":
        stage = route(text, d.proof_is_current, bool(d.explanation))
    return stage_plan(d, stage, text), stage


class JobIO:
    """StageIO bound to one job: attempts are published as `job.updated`, streamed text as `job.token`."""

    def __init__(self, ctx, job: Job):
        self.ctx, self.job = ctx, job

    def new_attempt(self, stage: str, kind: str) -> Attempt:
        a = Attempt(len(self.job.attempts), stage, kind)
        self.job.attempts.append(a)
        self.ctx.publish_job(self.job)
        return a

    def drop_attempt(self, a: Attempt) -> None:
        if a in self.job.attempts:
            self.job.attempts.remove(a)
            for i, x in enumerate(self.job.attempts):
                x.index = i
        self.ctx.publish_job(self.job)

    def update_attempt(self, a: Attempt) -> None:
        if len(a.raw) > RAW_CAP:
            a.raw = a.raw[:RAW_CAP] + "\n…"
        self.ctx.publish_job(self.job)

    def _model_guess(self, role: str, mode: str) -> ModelRef:
        try:
            c = self.ctx.brain.candidates(role, mode)
            if c:
                return c[0]
        except Exception:  # noqa: BLE001
            pass
        return ModelRef("unknown", "unknown")

    async def complete(self, role: str, messages: list[dict], attempt: Attempt | None = None, *,
                       temperature: float | None = None, max_tokens: int | None = None, extra: dict | None = None,
                       mode: str | None = None, stage: str = "", only: str | None = None,
                       prefer: str | None = None) -> Completion:
        """`only`: this model alone (online Goedel, S-T); `prefer`: tried first (the user's choice wins)."""
        ctx, job = self.ctx, self.job
        mode = mode or job.mode
        guard = LoopGuard()
        idx = attempt.index if attempt is not None else -1
        stage = stage or job.stage
        inner: asyncio.Task | None = None
        streamed = {"pieces": 0, "model": "", "t0": time.monotonic()}

        def on_chunk(ch: Chunk) -> None:
            nonlocal guard
            if ch.kind in ("text", "thinking"):
                if attempt is not None and len(attempt.raw) < RAW_CAP:
                    attempt.raw += ch.text
                streamed["pieces"] += 1
                ctx.bus.token(job.id, stage, idx, ch.text, ch.kind)
                if guard.feed(ch.text) and inner is not None and not inner.done():
                    inner.cancel()                 # the model is going round in circles: stop wasting minutes
            elif ch.kind == "info":
                data = ch.data or {}
                if data.get("event") in ("restart", "switch"):
                    # another model (or a retry) starts from scratch: its text must not be judged together with the
                    # partial answer that was dropped (S-K: false « loop » verdicts across fallbacks)
                    guard = LoopGuard()
                    if attempt is not None and data.get("event") == "restart":
                        attempt.raw = ""
                if data.get("event") == "switch" and data.get("model"):
                    streamed["model"] = str(data["model"])
                elif data.get("event") == "model" and data.get("model"):
                    streamed["model"] = str(data["model"])
                if attempt is not None and streamed["model"] and data.get("event") in ("switch", "model"):
                    attempt.model = streamed["model"]      # known even if the call never returns (timeouts)
                ctx.bus.publish("job.info", {"job_id": job.id, "stage": stage, "text": ch.text, "data": ch.data})

        need_online = mode != "local"
        if need_online:
            job.waiting = "online"
            ctx.publish_job(job)
            await ctx.slots.acquire("online", job.id)
            job.waiting = ""
            ctx.publish_job(job)
        try:
            inner = asyncio.create_task(ctx.brain.complete(
                role, messages, mode=mode, temperature=temperature, max_tokens=max_tokens, on_chunk=on_chunk,
                prefer=(ctx.settings.prefer or {}).get(role) or prefer or None, extra=extra,
                **({"only": only} if only else {})))
            try:
                return await inner
            except asyncio.CancelledError:
                if guard.loop is not None and not outer_cancelled():
                    # the provider's usage report never arrives on a stopped stream: count what was streamed
                    # (≈ one token per streamed piece, at least chars/4) and the real generation time
                    text = guard.trimmed()
                    model = self._model_guess(role, mode)
                    if streamed["model"] and ":" in streamed["model"]:
                        p, mid = streamed["model"].split(":", 1)
                        model = ModelRef(p, mid)
                    toks = max(int(streamed["pieces"]), len("".join(guard.parts)) // 4)
                    return Completion(text, model, "loop", tokens_out=toks,
                                      seconds=time.monotonic() - streamed["t0"])
                inner.cancel()
                raise
        finally:
            if need_online:
                ctx.slots.release("online", job.id)
            try:
                ctx.local.release()
            except Exception:  # noqa: BLE001
                pass

    async def check(self, code: str, ws, timeout_s: int, strict_name: str | None):
        return await self.ctx.lean.check(code, ws, timeout_s, strict_name, owner=self.job.id)


class Failed(Exception):
    def __init__(self, key: str, error: str = "failed", **params: Any):
        super().__init__(key)
        self.key, self.error, self.params = key, error, params


class DossierPipeline:
    def __init__(self, ctx):
        self.ctx = ctx

    # ------------------------------------------------------------ helpers
    @property
    def settings(self):
        return self.ctx.settings

    async def event(self, d: Dossier, job: Job | None, kind: str, key: str, ref: int | None = None, stage: str = "",
                    model: str = "", detail: str = "", **params: Any) -> None:
        m = msg(key, **params)
        text = m["text"] + ("\n" + detail if detail else "")
        if detail:
            params = {**params, "detail": detail}
        d.add_event(kind, text, ref, stage, model, key, params, job.id if job else "")
        await self.ctx.repo.save(d)

    def has_model(self, role: str, mode: str) -> bool:
        try:
            return bool(self.ctx.brain.candidates(role, mode))
        except Exception:  # noqa: BLE001
            return False

    async def workspace(self, d: Dossier):
        ws = self.ctx.workspace(d.workspace or self.settings.workspace)
        problems = [] if ws is None else await self.ctx.lean.problems(ws)
        if ws is None or problems:
            f = friendly("workspace")
            raise Failed("Étape impossible : l'espace de travail Lean n'est pas prêt ({why}).", "workspace",
                         why=(problems[0] if problems else f.title))
        if not d.workspace:
            d.workspace = ws.key
        return ws

    # ------------------------------------------------------------ main loop
    async def run(self, job: Job) -> None:
        d = self.ctx.repo.get(job.dossier_id)
        if d is None:
            job.error = "missing"
            return
        io = JobIO(self.ctx, job)
        try:
            while job.plan:
                step = job.plan.pop(0)
                stage, req = step.get("stage", ""), step.get("request", "") or ""
                if stage not in STAGES:
                    continue
                job.stage = stage
                job.step_flags = {k: bool(step.get(k)) for k in ("force", "learn")}   # « Prouver quand même », Apprendre
                self.ctx.publish_job(job)
                try:
                    await getattr(self, "_" + stage)(job, d, io, req)
                except InfraError as e:
                    if e.kind == "no_model":
                        raise Failed("Étape impossible : le modèle nécessaire n'est pas installé (voir « Modèles »).",
                                     "no_model") from e
                    if e.kind == "workspace":
                        raise Failed("Étape impossible : l'espace de travail Lean n'est pas prêt ({why}).",
                                     "workspace", why=e.details[-300:]) from e
                    raise Failed("Interrompu : le moteur d'IA ou Lean ne répond plus. Voir le message en haut, "
                                 "puis renvoyez votre demande.", e.kind) from e
                except BrainError as e:
                    if e.kind == "no_model":
                        raise Failed("Étape impossible : le modèle nécessaire n'est pas installé (voir « Modèles »).",
                                     "no_model") from e
                    raise Failed("Interrompu : le moteur d'IA ou Lean ne répond plus. Voir le message en haut, "
                                 "puis renvoyez votre demande.", e.kind) from e
                job.done_stages.append(stage)
        except Failed as f:
            job.plan = []
            job.error = f.error
            job.summary = msg(f.key, **f.params)
            if d.status in ("translating", "proving"):
                d.status = "proved" if d.proof_is_current else "failed"
            await self.event(d, job, "error", f.key, **f.params)
            return
        if d.status in ("translating", "proving"):
            d.status = "proved" if d.proof_is_current else "draft"
            await self.ctx.repo.save(d)

    # ------------------------------------------------------------ stages
    async def _short(self, io: JobIO, role: str, messages: list[dict], temperature: float, max_tokens: int = 700):
        return await io.complete(role, messages, None, temperature=temperature, max_tokens=max_tokens,
                                 extra={"top_p": 0.9, **NO_THINK})

    async def _understand(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not (self.has_model("understand", job.mode) and self.has_model("formalize", job.mode)):
            return                     # optional step: the formalizer then gets the user's own words
        try:
            c = await self._short(io, "understand", leancheck.understand_messages(d.problem, self.settings.profile,
                                                                                   language()), 0.3)
        except BrainError:
            return
        text = leancheck.clean_model_text(c.text)
        ok = bool(text) and c.finish not in ("loop", "length")
        if ok and leancheck.is_unknown(text):
            raise Failed("Je ne reconnais pas d'énoncé mathématique dans votre demande. Écrivez le résultat à prouver "
                         "avec ses hypothèses, par exemple : « toute famille libre d'un espace vectoriel de dimension "
                         "finie se complète en une base ».", "unknown")
        if ok and text.strip():
            eng, disp = leancheck.parse_understood(text)
            d.understood, d.understood_display = eng, disp
            await self.event(d, job, "understood", "Problème compris ainsi (c'est ce texte que l'IA traduit en Lean) :",
                             model=c.model.key, detail=disp)

    async def _route(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        try:
            c = await self._short(io, "route", leancheck.route_messages(d.understood or d.problem, d.statement,
                                                                        d.proof_is_current, req, language()), 0.2)
            text = leancheck.clean_model_text(c.text)
            parsed = leancheck.parse_route(text) if text and c.finish not in ("loop",) else None
            model = c.model.key
        except BrainError:
            parsed, model = None, ""
        kw = route(req, d.proof_is_current, bool(d.explanation))
        sc = route_scores(req)
        if parsed is None:
            stage, eng, disp = kw, "", ""
        else:
            stage, eng, disp = parsed
            if stage == "proof" and kw != "proof" and sc[kw] and not sc["proof"]:
                stage = kw                     # the model missed an explicit « pourquoi » / « hypothèse »
        for e in reversed(d.events):
            if e.kind == "user":
                e.stage = stage
                break
        if stage == "statement" and eng:
            d.understood, d.understood_display = eng, disp
            await self.event(d, job, "understood",
                             "Nouvel énoncé compris ainsi (c'est ce texte que l'IA traduit en Lean) :", model=model,
                             detail=disp)
            job.plan = [{"stage": "statement"}, {"stage": "proof"}, {"stage": "explanation"}]
        else:
            job.plan = stage_plan(d, stage, req)
            await self.ctx.repo.save(d)

    async def _statement(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        ws = await self.workspace(d)
        s = self.settings
        d.status = "translating"
        await self.ctx.repo.save(d)
        previous = d.statement if req else ""
        first = len(job.attempts)
        text = (d.understood or d.problem) + await self._mathlib_reference(job, d, ws, req)
        f = await Formalizer(io, job.mode, prefer=self._goedel_online_key("formalize", job.mode)).run(
                                                text, ws, s.translate_attempts,
                                                s.compile_timeout_s, name=d.theorem, profile=s.profile,
                                                previous=previous, request=req)
        self._record_stage(job, d, first, "statement", "formalize")
        if not f.statement:
            raise Failed("Pas d'énoncé produit. Reformulez le problème (plus précis, avec les hypothèses) ou écrivez "
                         "l'énoncé Lean vous-même dans l'onglet « Énoncé Lean ».", "no_statement")
        idx = d.add_statement(f.statement, ok=f.ok, note=req, model=f.model)
        if f.ok:
            d.status = "draft"
            await self.event(d, job, "statement", "L'IA a traduit le problème en Lean et Lean accepte l'énoncé. "
                             "Relisez-le : la preuve portera exactement sur ce texte.", ref=idx, model=f.model)
            if s.pause_after_translation:
                job.plan = []
                await self.event(d, job, "info", "Pause : relisez l'énoncé, puis cliquez sur « Prouver cet énoncé ».")
            if s.statement_notes:
                job.plan.insert(0, {"stage": "notes"})
        else:
            job.plan = []
            d.status = "draft"
            job.error = "statement_rejected"
            job.summary = msg("Lean refuse la traduction. Corrigez l'énoncé dans l'onglet « Énoncé Lean », ou "
                              "demandez une correction ci-dessous.")
            await self.event(d, job, "error", "Lean refuse la traduction. Corrigez l'énoncé dans l'onglet « Énoncé "
                             "Lean », ou demandez une correction ci-dessous.", ref=idx, model=f.model)

    async def _notes(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not d.statement or not self.has_model("explain", job.mode):
            return
        nl = d.understood_display or d.understood or d.problem
        try:
            # 6000: a thinking model (Gemini 3.x) spends part of the budget before writing; with 1500 its gloss stopped
            # after one sentence and the PDF printed it cut (real dossiers, 2026-11-21)
            c = await self._short(io, "explain", prompts.notes_messages(d.statement, nl, language()), 0.3, 6000)
        except BrainError:
            return                     # optional: the statement stays usable without its gloss
        text = leancheck.clean_model_text(c.text)
        if c.finish in ("length", "loop"):
            return                     # a cut gloss is worse than none (an earlier complete one stays shown)
        if text:
            idx = d.add_notes(text, c.model.key)
            await self.event(d, job, "notes", "Lecture guidée de l'énoncé Lean, rédigée par l'IA :", ref=idx,
                             model=c.model.key)

    # ------------------------------------------------------------ statement check + Mathlib first (S-K)
    def _lean_real(self) -> bool:
        from ..brain.fake import FakeLean
        return not isinstance(self.ctx.lean, FakeLean)    # the demo's fake Lean would « prove » any negation

    async def _mathlib_reference(self, job: Job, d: Dossier, ws, req: str) -> str:
        """When the request names a known theorem, the formalizer gets Mathlib's own statement as a reference (so
        that it states the same thing with definitions that exist: Cayley-Hamilton, Riesz…)."""
        if not self.settings.mathlib_first or self.ctx.retriever is None:
            return ""
        from ..brain import rag
        names: list[str] = []
        for t in (req, d.understood, d.problem):
            names += [n for n in rag.famous(t or "") if n not in names]
        found = []
        ensure = getattr(self.ctx.retriever, "ensure", None) if names else None
        if ensure is not None:        # first use after a start: the index may still be building (≈ 20–70 s)
            try:
                await asyncio.wait_for(ensure(ws.key, 90), 95)
            except Exception:  # noqa: BLE001
                pass
        for n in names[:6]:
            try:
                dd = await asyncio.wait_for(self.ctx.retriever.declaration(ws.key, n), 30)
            except Exception:  # noqa: BLE001 (index not built yet: no reference, never an error)
                dd = None
            if dd and dd.get("signature"):
                found.append(dd)
            if len(found) >= 3:
                break
        if not found:
            return ""
        await self.event(d, job, "info", "Résultat connu de Mathlib donné au traducteur comme référence : {names}.",
                         names=", ".join(x["name"] for x in found))
        lines = [f"- `{x['name']}`" + (f" (variables: `{x['variables'][:300]}`)" if x.get("variables") else "")
                 + f": `{x['signature'][:400]}`" for x in found]
        return ("\n\nReference: Mathlib already contains this result:\n" + "\n".join(lines) +
                "\nState the same mathematical content, with the same hypotheses, using these Mathlib definitions "
                "and their exact argument conventions, so that the statement compiles. The signatures are copied "
                "from Mathlib's sources, which `open` namespaces: write fully qualified names (`Polynomial.aeval`, "
                "`LinearMap.charpoly`, `Metric.closedBall`).\n" +
                ("A `def` above is a construction (for example an isomorphism ≃ₗ), not a proposition: a theorem "
                 "must state that it exists, e.g. `Nonempty ((E ⧸ LinearMap.ker f) ≃ₗ[K] LinearMap.range f)`.\n"
                 if any(x.get("kind") in ("def", "abbrev") for x in found) else ""))

    def _check_of(self, d: Dossier) -> dict | None:
        if 0 <= d.cur_statement < len(d.statements):
            c = d.statements[d.cur_statement].meta.get("check")
            return c if isinstance(c, dict) else None
        return None

    async def _verify(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        """« Vérifier l'énoncé » (also run by `_proof` before the first proof search of a statement)."""
        await self._run_check(job, d, io, stop_plan=False)

    async def _run_check(self, job: Job, d: Dossier, io: JobIO, stop_plan: bool) -> CheckResult | None:
        if not d.statement:
            raise Failed("Pas d'énoncé à prouver : écrivez ou traduisez d'abord l'énoncé.", "no_statement")
        ws = await self.workspace(d)
        stage_before = job.stage
        job.stage = "verify"
        self.ctx.publish_job(job)
        learn = bool((getattr(job, "step_flags", None) or {}).get("learn"))
        chk = StatementChecker(io, job.mode, lean_real=self._lean_real(),
                               use_model=self.has_model("understand", job.mode))
        r = await chk.run(d.problem, d.understood_display or d.understood, d.statement, ws, lang=language(),
                          learn=learn)
        r.statement_index = d.cur_statement
        if 0 <= d.cur_statement < len(d.statements):
            d.statements[d.cur_statement].meta["check"] = r.to_dict()
        await self._check_event(job, d, r)
        job.stage = stage_before
        self.ctx.publish_job(job)
        if stop_plan and r.verdict in ("false", "doubtful"):
            self._stop_for_check(job, d, r.verdict)
        return r

    def _stop_for_check(self, job: Job, d: Dossier, verdict: str) -> None:
        job.plan = []
        d.status = "draft"
        job.error = "statement_false" if verdict == "false" else "statement_doubtful"
        job.summary = msg("Preuve non lancée : l'énoncé est faux." if verdict == "false" else
                          "Preuve non lancée : l'énoncé est douteux.")

    async def _check_event(self, job: Job, d: Dossier, r: CheckResult) -> None:
        labels = {"wrong_object": "Mauvais objet", "missing_hypothesis": "Hypothèse manquante",
                  "extra_hypothesis": "Hypothèse en trop", "wrong_quantifier": "Mauvais quantificateur",
                  "wrong_direction": "Mauvais sens", "false_statement": "Énoncé faux", "other": "Remarque"}
        lines: list[str] = []
        if r.summary:
            lines.append(msg("Lecture du modèle : {text}", text=r.summary)["text"])
        for i in r.issues:
            tag = msg(labels.get(i["kind"], "Remarque"))["text"]
            sev = "" if i["severity"] == "high" else " " + msg("(mineur)")["text"]
            lines.append(f"- **{tag}**{sev} : {i['explanation']}")
        if r.evidence:
            lines.append(msg("Preuve Lean de la négation (vérifiée) :")["text"] +
                         (" " + r.evidence["idea"] if r.evidence.get("idea") else ""))
            lines.append("```lean4\n" + r.evidence["code"] + "\n```")
        if r.proof:
            lines.append(msg("Lean prouve l'énoncé directement ({tactic}) : il est vrai.", tactic=r.proof)["text"])
        if r.fix and r.verdict != "faithful":
            lines.append(msg("Correction proposée : {fix}", fix=r.fix)["text"])
        key = {"faithful": "Vérification de l'énoncé : fidèle à votre demande.",
               "doubtful": "Vérification de l'énoncé : douteux. La preuve n'est pas lancée : corrigez l'énoncé ou "
                           "cliquez sur « Prouver quand même ».",
               "false": "Vérification de l'énoncé : FAUX, Lean prouve le contraire. La preuve n'est pas lancée : "
                        "corrigez l'énoncé ou cliquez sur « Prouver quand même ».",
               "unknown": "Vérification de l'énoncé : rien n'a pu être vérifié (modèle ou Lean indisponible)."}[r.verdict]
        await self.event(d, job, "check", key, ref=d.cur_statement, model=r.model, detail="\n".join(lines),
                         verdict=r.verdict, fix=r.fix, issues=r.issues, evidence=r.evidence, proved=bool(r.proof),
                         seconds=round(r.seconds, 1))

    async def _mathlib(self, job: Job, d: Dossier, io: JobIO, ws, statement: str) -> MathlibResult:
        chk = self._check_of(d) or {}
        quick = (chk.get("proof"), chk.get("proof_source", "")) if chk.get("proof") else None
        mf = MathlibFirst(io, job.mode, self.ctx.retriever, lean_real=self._lean_real(),
                          use_model=self.has_model("prove", job.mode))
        texts = [t for t in (d.understood, d.problem) if t]
        return await mf.run(statement, ws, texts, self.settings.compile_timeout_s, quick=quick)

    # ------------------------------------------------------------ leaderboard (S-J)
    def _record(self, model: str, task: str, d: Dossier, **kw) -> None:
        if not model or model == "unknown:unknown":
            return
        try:
            from ..brain.leaderboard import domain_of
            tourn.leaderboard_of(self.ctx).record(model, task, domain_of(d.statement + "\n" + (d.understood or d.problem
                                                                                                 or "")), **kw)
        except Exception:  # noqa: BLE001 (statistics never break a job)
            log.exception("leaderboard record failed")

    def _record_stage(self, job: Job, d: Dossier, first: int, stage: str, task: str) -> None:
        """One leaderboard row per model that worked on this stage: success = Lean accepted its output."""
        per: dict[str, list] = {}
        for a in job.attempts[first:]:
            if a.stage == stage and a.model and a.status in ("accepted", "rejected"):
                per.setdefault(a.model, []).append(a)
        for model, atts in per.items():
            ok = any(a.status == "accepted" for a in atts)
            self._record(model, task, d, ok=ok, attempts=len(atts),
                         lean_errors=sum(1 for a in atts if a.status == "rejected" and a.code),
                         seconds=sum(a.gen_seconds + a.compile_seconds for a in atts))

    def _choose_strategy(self, job: Job) -> str:
        st = job.strategy or self.settings.prove_strategy
        if st == "goedel":
            return "goedel"
        agent = _agent_fn()
        if agent is None:
            return "goedel"
        if st == "agent":
            return "agent"
        # auto: the agent with an online model when allowed, else goedel (ARCHITECTURE §7)
        if job.mode == "local":
            return "goedel"
        try:
            cands = self.ctx.brain.candidates("prove", job.mode)
        except Exception:  # noqa: BLE001
            cands = []
        return "agent" if any(not c.local for c in cands) else "goedel"

    def _goedel_online_key(self, role: str, mode: str) -> str | None:
        """The Goedel specialist served online for `role` (Hugging Face, S-T), or None."""
        fn = getattr(self.ctx.brain, "goedel_online", None)
        if fn is None or mode == "local":
            return None
        try:
            r = fn(role, mode)
        except Exception:  # noqa: BLE001
            return None
        return r.key if r is not None else None

    def _legacy_fallback(self) -> bool:
        """A brain that cannot tell whether the Internet works (the scripted demo brain, older brains) keeps the
        1.x/S-J behaviour: the local Goedel after a failed online search. The real engine has `internet` (S-T)."""
        return getattr(self.ctx.brain, "internet", None) is None

    async def _internet(self, mode: str) -> bool:
        """Reachability as the brain sees it (cached probe); a brain without a probe is trusted to be online."""
        if mode == "local":
            return False
        fn = getattr(self.ctx.brain, "internet", None)
        if fn is None:
            return True
        try:
            return bool(await asyncio.wait_for(fn(), 5))
        except Exception:  # noqa: BLE001
            return True

    async def _goedel_online(self, io, key: str, statement: str, ws, n: int, refine, hint: str) -> ProveResult:
        """Goedel's own loop on Goedel-Prover-V2 served online (verbatim prompts, ≤ 2 corrections per line of attack,
        pinned model, Goedel's sampling); paid within the spending caps (spend.py)."""
        from ..brain.spend import SPEND_SCOPE
        from .goedel import ONLINE_CTX, ONLINE_SAMPLING
        tok = SPEND_SCOPE.set(f"{io.job.dossier_id}:{io.job.id}") if hasattr(io, "job") else None
        try:
            return await GoedelProver(io, "online", model=key).run(statement, ws, n, ONLINE_SAMPLING,
                                                                   self.settings.compile_timeout_s, ONLINE_CTX,
                                                                   refine=refine, hint=hint)
        finally:
            if tok is not None:
                SPEND_SCOPE.reset(tok)

    async def _proof(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        ws = await self.workspace(d)
        if not d.statement:
            raise Failed("Pas d'énoncé à prouver : écrivez ou traduisez d'abord l'énoncé.", "no_statement")
        s, lib = self.settings, self.ctx.library
        force = bool((getattr(job, "step_flags", None) or {}).get("force"))
        if s.statement_check and not force and not (req and d.proof_is_current):
            chk = self._check_of(d)
            if chk is None:
                # first proof search of this statement: check it first (S-K), bounded, never silent
                r = await self._run_check(job, d, io, stop_plan=False)
                chk = r.to_dict() if r is not None else None
            if chk and chk.get("verdict") in ("false", "doubtful") and not req:
                # an explicit request of the user (« prouve-le par récurrence ») goes on; the automatic chain stops
                self._stop_for_check(job, d, chk["verdict"])
                if self._check_of(d) is chk:      # already reported earlier: remind once in the thread
                    await self.event(d, job, "info", "Preuve non lancée : l'énoncé a été signalé "
                                     "({verdict}). Corrigez-le ou cliquez sur « Prouver quand même ».",
                                     verdict=msg({"false": "faux", "doubtful": "douteux"}[chk["verdict"]])["text"])
                await self.ctx.repo.save(d)
                return
        d.status = "proving"
        await self.ctx.repo.save(d)
        exclude = leancheck.declared_names(d.statement)
        child_ids = {c.id for c in self.ctx.repo.children(d.id)}
        forced = [e for e in lib.entries if e.dossier in child_ids and e.workspace == ws.key and e.name not in exclude]
        rel = [e for e in lib.relevant(d.statement, ws.key, exclude=exclude) if e not in forced]
        used = closure(lib, forced + rel)
        d.lemmas_used = [e.name for e in used]
        statement = with_lemmas(d.statement, used)
        if used:
            await self.event(d, job, "info", "Résultats de votre bibliothèque proposés à l'IA : {names}.",
                             names=", ".join(e.title for e in used))
        refine = (d.proof, req) if (req and d.proof_is_current) else None
        hint = req if (req and not d.proof_is_current) else ""
        strategy = self._choose_strategy(job)
        if job.mode == "auto" and strategy == "agent" and not await self._internet(job.mode):
            # no Internet (S-T): the local models do the work, without waiting for every online model to time out
            strategy = "goedel"
            await self.event(d, job, "info", "Pas d'accès à Internet : la preuve est cherchée avec le modèle local.")
        res: ProveResult | None = None
        try:
            statement = leancheck.prepare_statement(statement)
        except leancheck.StatementError as e:
            raise Failed("{why}", "statement", why=str(e)) from e
        local_ok = True              # may the local prover still run? (S-T: only offline or when no online model could)
        mf: MathlibResult | None = None
        if s.mathlib_first and refine is None:
            mf = await self._mathlib(job, d, io, ws, statement)
            if mf.ok:
                lemma = mf.lemma or mf.tactic
                res = ProveResult(True, mf.code, msg("Trouvé dans Mathlib : {name}.", name=lemma), [],
                                  f"mathlib:{lemma}", mf.axioms, mf.seconds)
                strategy = "mathlib"
        if res is not None and res.ok:
            pass
        elif strategy == "agent":
            job.mathlib_hint = mf.hint() if mf is not None else ""
            tcfg = tourn.Config.from_settings(s)
            if tcfg.enabled:
                # best model first, then races of untried models (S-J, pipeline/tournament.py): bounded, recorded
                res, strategy, local_ok = await self._tournament(job, d, io, ws, statement, hint or req, refine,
                                                                 tcfg)
            else:
                # an agent run is one attempt; free providers often fail transiently (quota, overload), so retry
                # with a fresh run up to the attempt budget, keeping the user's hint
                res = None
                ran = False
                for _i in range(max(1, min(s.prove_attempts, 4))):
                    st: dict = {}
                    res = await self._agent(job, d, io, ws, statement,
                                            ((hint or req) + "\n\n" + job.mathlib_hint).strip(), stats=st)
                    ran = ran or (res is not None and not st.get("unavailable"))
                    if res is None or res.ok:
                        break
                local_ok = not ran or not await self._internet(job.mode) or self._legacy_fallback()
            if not (res and res.ok) and (job.strategy or s.prove_strategy) == "auto" and local_ok \
                    and (job.mode != "online" or self._legacy_fallback()):
                strategy = "goedel"
                res = None
                if not self._legacy_fallback():
                    await self.event(d, job, "info",
                                     "Aucun modèle en ligne n'a pu travailler : repli sur le modèle local.")
        if res is None and job.mode != "local" and (key := self._goedel_online_key("prove", job.mode)) \
                and await self._internet(job.mode):
            # « Goedel » strategy with a Hugging Face token: the same loop on Goedel-Prover-V2-32B online (S-T)
            try:
                res = await self._goedel_online(io, key, statement, ws, s.prove_attempts, refine, hint)
                self._record(res.model or key, "prove", d, ok=res.ok, attempts=len(res.attempts),
                             seconds=res.seconds,
                             lean_errors=sum(1 for x in res.attempts if x.status == "rejected" and x.code))
            except InfraError as e:
                if e.kind == "workspace":
                    raise
                res = None             # could not run at all (cap, credits, provider down): the local prover may
                await self.event(d, job, "info", "Goedel en ligne indisponible ({why}).", why=str(e.details)[:200])
        if res is None:
            if job.mode == "online" and not self._legacy_fallback():
                raise Failed("Aucun modèle en ligne n'a pu travailler (mode « en ligne » : pas de modèle local).",
                             "no_model")
            ctx_len = (self.ctx.local.plan.ctx if getattr(self.ctx.local, "plan", None) else s.server.ctx_size)
            res = await GoedelProver(io, "local").run(statement, ws, s.prove_attempts, s.sampling, s.compile_timeout_s,
                                                      ctx_len, refine=refine, hint=hint)
            self._record(res.model, "prove", d, ok=res.ok, attempts=len(res.attempts), seconds=res.seconds,
                         lean_errors=sum(1 for x in res.attempts if x.status == "rejected" and x.code))
        if not res.ok:
            d.status = "failed"
            raise Failed("Aucune preuve trouvée après {n} essais. Essayez : « autre méthode », un énoncé plus simple, "
                         "ou plus d'essais (⚙ Options).", "no_proof",
                         n=len([a for a in job.attempts if a.stage == "proof"]))
        info = workspace_info(ws)
        meta = {"axioms": res.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
                "workspace": ws.key, "seconds": round(res.seconds, 1), "strategy": strategy,
                "attempts": len([a for a in job.attempts if a.stage == "proof"]), "checked": time.time()}
        if mf is not None and mf.ok:
            meta.update(mathlib_lemma=mf.lemma, mathlib_source=mf.source, mathlib_tactic=mf.tactic,
                        **({"adapted_by": mf.model} if mf.model else {}))
        idx = d.add_proof(res.code, note=req, model=res.model, meta=meta)
        d.status = "proved"
        await self.event(d, job, "proof", "Preuve trouvée et vérifiée par Lean (essai {i}, {s:.0f} s).", ref=idx,
                         model=res.model, i=meta["attempts"], s=res.seconds)
        if mf is not None and mf.ok and mf.lemma:
            await self.event(d, job, "info", "Ce théorème est dans Mathlib sous le nom « {name} » : la preuve "
                             "l'utilise directement.", name=mf.lemma)
        entry = await asyncio.to_thread(lib.add_proof, res.code, d.title, ws.key, d.id, d.lemmas_used)
        if entry:
            self.ctx.bus.publish("library.updated", {"added": entry.name})
            await self.event(d, job, "info", "Ajouté à votre bibliothèque sous le nom « {name} » : réutilisable dans "
                             "vos prochaines preuves.", name=entry.name)

    async def _tournament(self, job: Job, d: Dossier, io: JobIO, ws, statement: str, hint: str, refine,
                          cfg: "tourn.Config") -> tuple[ProveResult | None, str, bool]:
        """Returns (result, strategy of the winner, whether the local prover may still run afterwards).

        S-T (user decision 2026-11-22): round 0 starts with Goedel-Prover-V2-32B served online (Hugging Face) when its
        token is set — Goedel's own loop and prompts, paid within the caps —, then the free online models as before.
        The local models are never contestants while online: they run after the tournament only when no online
        contestant could work at all (all unavailable: no Internet, every provider down or refusing)."""
        from ..brain.leaderboard import domain_of
        ctx, s = self.ctx, self.settings
        brain = ctx.brain
        lb = tourn.leaderboard_of(ctx)
        domain = domain_of(statement + "\n" + (d.understood or d.problem or ""))
        bset = getattr(brain, "settings", None) or {}
        paid_ok = bool(bset.get("paid_first"))
        chosen = (s.prefer or {}).get("prove") or (bset.get("models") or {}).get("prove") or ""
        fn = _agent_fn()
        pins = fn is not None and _accepts(fn, "only")
        gkey = self._goedel_online_key("prove", job.mode) if pins else None
        gonline = None
        if gkey:
            gref = brain.goedel_online("prove", job.mode)
            gonline = tourn.Contestant(gkey, getattr(gref, "name", "") or gkey.split(":", 1)[-1], "goedel_online",
                                       paid=True)
        goedel = None                  # the local prover is no tournament contestant (S-T): only the fallback

        def candidates() -> list[tourn.Contestant]:
            try:
                refs = brain.pool("prove", job.mode, domain=domain) if hasattr(brain, "pool") \
                    else brain.candidates("prove", job.mode)
            except Exception:  # noqa: BLE001
                refs = []
            out = [tourn.Contestant(r.key, r.name or r.model_id, "agent", bool(r.paid)) for r in refs
                   if not r.local and r.provider != "huggingface" and (not r.paid or paid_ok or r.key == chosen)]
            if not pins:
                out = out[:1]              # an agent that cannot be pinned to a model is one contestant (the router)
            if gonline is not None:
                out.insert(0, gonline)     # leads round 0 (S-T); « tried » keeps it out of later rounds
            if goedel is not None:
                g = lb.entry(goedel.key, "prove")
                first = out[0].key if out else ""
                if out and g is not None and g.n >= 2 and lb.score(goedel.key, "prove") > lb.score(first, "prove"):
                    out.insert(0, goedel)  # the local prover has done better here: it leads round 0
                else:
                    out.append(goedel)
            return out

        reinforced: set[str] = set()
        t_start = time.monotonic()
        state = {"round": 0, "models": [], "names": [], "state": "running", "domain": domain}
        job.tournament = state

        async def on_round(k: int, cs: list) -> None:
            state.update(round=k, models=[c.key for c in cs], names=[c.name for c in cs])
            ctx.publish_job(job)
            names = ", ".join(c.name for c in cs)
            ctx.bus.publish("job.info", {"job_id": job.id, "stage": "proof", "text": msg(
                "Tournoi, round {k} : {models}.", k=k, models=names)["text"], "data": {"tournament": dict(state)}})
            if k >= 1:
                await self.event(d, job, "info", "Tournoi, round {k} : {models}.", k=k, models=names)
            for c in cs:
                if c.kind == "goedel_online":
                    cap_p, cap_m = brain.caps() if hasattr(brain, "caps") else (1.0, 20.0)
                    await self.event(d, job, "info", "Goedel-Prover en ligne : {name}, la boucle de Goedel servie par "
                                     "Hugging Face (payant, plafonds : {cap_p} $ pour cette preuve, {cap_m} $ par mois).",
                                     name=c.name, cap_p=f"{cap_p:.2f}", cap_m=f"{cap_m:.2f}")
                elif c.paid and c.key in reinforced:
                    cap_p, cap_m = brain.caps() if hasattr(brain, "caps") else (1.0, 20.0)
                    await self.event(d, job, "info", "Renfort payant : {name} entre au tournoi car les modèles gratuits "
                                     "ont échoué (plafonds : {cap_p} $ pour cette preuve, {cap_m} $ par mois).",
                                     name=c.name, cap_p=f"{cap_p:.2f}", cap_m=f"{cap_m:.2f}")
                elif c.paid:
                    cost = tourn.estimated_cost(c.key, int(bset.get("agent_max_tokens") or 600_000))
                    await self.event(d, job, "info", "Modèle payant dans le tournoi : {name} (coût estimé : au plus "
                                     "{cost} $ par essai).", name=c.name, cost=cost if cost is not None else "?")

        def record(o: tourn.Outcome) -> None:
            lb.record(o.contestant.key, "prove", domain, ok=o.ok, attempts=o.attempts, lean_errors=o.lean_errors,
                      seconds=o.seconds, unavailable=o.unavailable)

        async def run(c: tourn.Contestant, k: int, n: int, deadline: float) -> tourn.Outcome:
            rio = _RoundIO(io, k)
            t0 = time.monotonic()
            try:
                if c.kind == "goedel":
                    return await self._goedel_contestant(c, k, n, rio, ws, statement, hint, refine, t0)
                if c.kind == "goedel_online":
                    return await self._goedel_contestant(c, k, n, rio, ws, statement, hint, refine, t0, online=True)
                o = tourn.Outcome(c, k)
                for i in range(n):
                    left = deadline - time.monotonic()
                    if left < 30:
                        break
                    st: dict = {}
                    r = await self._agent(job, d, rio, ws, statement,
                                          (hint + "\n\n" + getattr(job, "mathlib_hint", "")).strip(),
                                          only=c.key if pins else None,
                                          release_local=not pins, stats=st,
                                          max_seconds=min(float(s.agent_max_seconds), left))
                    o.attempts += 1
                    o.lean_errors += max(0, int(st.get("checks") or 0) - (1 if r is not None and r.ok else 0))
                    if r is not None and r.ok:
                        o.ok, o.result = True, r
                        break
                    if r is None or st.get("unavailable"):
                        o.unavailable = i == 0     # could not run at all: a pause, not a mathematical failure
                        o.error = str(st.get("error") or "")
                        break
                o.seconds = time.monotonic() - t0
                return o
            except asyncio.CancelledError:
                for a in rio.attempts:
                    if a.status in ("generating", "compiling"):
                        a.status, a.summary = "cancelled", msg("Essai arrêté : la course est terminée.")["text"]
                raise

        def on_join(k: int, c) -> None:            # a model replaces one that could not run (429…)
            state["models"] = state["models"] + [c.key]
            state["names"] = state["names"] + [c.name]
            ctx.publish_job(job)

        def reinforce() -> list[tourn.Contestant]:     # Claude, final round, within the user's caps (S-M)
            if not pins or not hasattr(brain, "reinforcements"):
                return []
            out = [tourn.Contestant(r.key, r.name or r.model_id, "agent", True)
                   for r in brain.reinforcements("prove", job.mode, domain=domain)]
            reinforced.update(c.key for c in out)
            return out

        from ..brain.spend import SPEND_SCOPE
        t = tourn.Tournament(cfg, candidates=candidates, run=run, record=record, on_round=on_round, on_join=on_join,
                             online_slots=int(ctx.slots.caps.get("online", 3)), reinforce=reinforce)
        scope_token = SPEND_SCOPE.set(f"{d.id}:{job.id}")
        try:
            res = await t.run()
        finally:
            SPEND_SCOPE.reset(scope_token)
        w = res.winner
        state.update(state=res.stop, winner=w.contestant.key if w else "", tried=res.tried, rounds=res.rounds,
                     minutes=round((time.monotonic() - t_start) / 60, 1))
        ctx.publish_job(job)
        if res.rounds > 1:
            if w is not None:
                await self.event(d, job, "info", "Tournoi : {name} a trouvé la preuve au round {k}. Classement des "
                                 "modèles mis à jour.", name=w.contestant.name, k=w.round)
            else:
                await self.event(d, job, "info", "Tournoi terminé sans preuve : {n} modèles essayés en {m} min.",
                                 n=len(res.tried), m=state["minutes"])
        # the local prover may run afterwards only when no online contestant could work at all (S-T)
        local_ok = not any(not o.unavailable and not o.cancelled for o in res.outcomes) or self._legacy_fallback()
        if w is None:
            return ProveResult(False), "agent", local_ok
        return w.result, ("goedel" if w.contestant.kind in ("goedel", "goedel_online") else "agent"), False

    async def _goedel_contestant(self, c, k: int, n: int, rio: "_RoundIO", ws, statement: str, hint: str, refine,
                                 t0: float, online: bool = False):
        s = self.settings
        if online:
            from .goedel import ONLINE_CTX, ONLINE_SAMPLING
            prover = GoedelProver(rio, "online", model=c.key)
            sampling, ctx_len = ONLINE_SAMPLING, ONLINE_CTX
        else:
            ctx_len = (self.ctx.local.plan.ctx if getattr(self.ctx.local, "plan", None) else s.server.ctx_size)
            prover = GoedelProver(rio, "local")
            sampling = s.sampling
        o = tourn.Outcome(c, k)
        try:
            r = await prover.run(statement, ws, n, sampling, s.compile_timeout_s, ctx_len, refine=refine, hint=hint)
            o.ok, o.result = r.ok, (r if r.ok else None)
        except InfraError as e:
            if e.kind == "workspace":
                raise
            o.unavailable = not any(a.code for a in rio.attempts)
            o.error = f"{e.kind}: {e.details}"[:300]
        atts = getattr(prover, "attempts", rio.attempts)
        o.attempts = max(1, len(atts))
        o.lean_errors = sum(1 for a in atts if a.status == "rejected" and a.code)
        o.tokens = sum(int(a.tokens or 0) for a in atts)
        o.seconds = time.monotonic() - t0
        return o

    async def _agent(self, job: Job, d: Dossier, io: JobIO, ws, statement: str, hint: str, *, only: str | None = None,
                     release_local: bool = True, stats: dict | None = None,
                     max_seconds: float | None = None) -> ProveResult | None:
        """One agent run (one attempt). `only`: pin it to one model (tournament contestant); `stats` receives
        {checks, steps, finish, unavailable, error}."""
        fn = _agent_fn()
        if fn is None:
            return None
        stats = stats if stats is not None else {}
        name = leancheck.theorem_name(statement)
        a = io.new_attempt("proof", "agent")

        async def check(code: str) -> dict:
            try:
                assembled = leancheck.assemble_proof(statement, code)
            except leancheck.StatementError as e:
                return {"ok": False, "feedback": str(e), "verdict": {"ok": False, "summary": str(e)}}
            r = await io.check(leancheck.with_axiom_probe(assembled, name), ws, self.settings.compile_timeout_s, name)
            fb = "" if r.verdict.ok else leancheck.errors_for_feedback(r.code, r.verdict)
            return {"ok": r.verdict.ok, "feedback": fb, "verdict": r.to_dict()}

        async def library_search(query: str, k: int = 8) -> list[dict]:
            from ..dossiers import tokens
            q = tokens(query)
            out = []
            for e in self.ctx.library.entries:
                if e.workspace != ws.key:
                    continue
                sc = len(q & tokens(e.statement)) / max(1, len(q | tokens(e.statement)))
                if sc > 0:
                    out.append({"name": e.name, "title": e.title, "statement": e.statement, "code": e.code,
                                "score": sc})
            return sorted(out, key=lambda x: -x["score"])[:k]

        def on_chunk(ch: Chunk) -> None:
            if ch.kind in ("text", "thinking", "tool_call", "tool_result", "info"):
                self.ctx.bus.token(job.id, "proof", a.index, ch.text, ch.kind)

        need_online = job.mode != "local"
        if need_online:
            await self.ctx.slots.acquire("online", job.id)
        t0 = time.monotonic()
        kw = {"only": only} if only and _accepts(fn, "only") else {}
        try:
            out = await fn(self.ctx.brain, self.ctx.retriever, statement=statement, workspace_key=ws.key, check=check,
                           library_search=library_search, hint=hint, on_chunk=on_chunk, mode=job.mode,
                           max_steps=self.settings.agent_max_steps,
                           max_seconds=max_seconds or self.settings.agent_max_seconds, **kw)
        except BrainError as e:
            a.status, a.summary, a.errors_text = "error", msg("La génération a échoué.")["text"], str(e)
            a.model = a.model or (only or "")
            stats.update(unavailable=True, error=str(e)[:300])
            io.update_attempt(a)
            return None
        finally:
            if need_online:
                self.ctx.slots.release("online", job.id)
            if release_local:
                self.ctx.local.release()
        a.gen_seconds = time.monotonic() - t0
        a.model = model_key(out.get("model")) or (only or "")
        a.finish = str(out.get("finish") or "")
        stats.update(checks=int(out.get("checks") or 0), steps=int(out.get("steps") or 0),
                     finish=str(out.get("finish") or ""))
        if out.get("finish") == "error" and not out.get("steps"):
            stats.update(unavailable=True, error="; ".join(str(m.get("text") or m.get("reason") or "")
                                                           for m in (out.get("transcript") or [])
                                                           if isinstance(m, dict) and m.get("type") in
                                                           ("error", "model_error"))[:300])
            if not out.get("code"):
                a.status, a.summary = "error", msg("Modèle indisponible : {why}", why=(stats["error"] or "?")[:200])["text"]
                a.errors_text = stats["error"]
                io.update_attempt(a)
                return ProveResult(False, model=a.model)
        a.raw = "\n".join(str(m.get("content", ""))[:4000] for m in (out.get("transcript") or [])[-40:])
        code = out.get("code")
        if not code:
            a.status, a.summary = "rejected", msg("L'agent n'a pas trouvé de preuve ({steps} étapes).",
                                                  steps=out.get("steps", 0))["text"]
            a.finish = str(out.get("finish") or "")
            a.errors_text = "\n".join(f"{m.get('role', '')}: {str(m.get('content', ''))[:600]}"
                                       for m in (out.get("transcript") or [])[-6:])
            io.update_attempt(a)
            return ProveResult(False, model=a.model)
        # never trust the agent: the server re-checks the final proof with the strict verdict
        try:
            a.code = leancheck.assemble_proof(statement, code)
        except leancheck.StatementError as e:
            a.status, a.summary = "rejected", str(e)
            io.update_attempt(a)
            return ProveResult(False, model=a.model)
        a.status = "compiling"
        io.update_attempt(a)
        r = await io.check(leancheck.with_axiom_probe(a.code, name), ws, self.settings.compile_timeout_s, name)
        a.compile_seconds, a.summary = r.seconds, r.verdict.summary
        if not r.verdict.ok:
            a.status = "rejected"
            a.errors_text = leancheck.errors_for_feedback(r.code, r.verdict)
            io.update_attempt(a)
            return ProveResult(False, model=a.model)
        a.status = "accepted"
        io.update_attempt(a)
        return ProveResult(True, a.code, msg("Preuve trouvée et vérifiée par Lean (essai {i}).", i=1), [a], a.model,
                           r.verdict.axioms, a.gen_seconds + a.compile_seconds)

    async def _explanation(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not d.proof:
            raise Failed("Pas de preuve à expliquer.", "no_proof")
        s = self.settings
        prev = d.explanation if req else ""
        cites = _citations(self.ctx, d)
        msgs = leancheck.explain_messages(d.proof, d.understood or d.problem, language(), s.profile, prev, req)
        if cites:
            msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + cites["prompt"]}
        lemma = (d.proofs[d.cur_proof].meta.get("mathlib_lemma") if 0 <= d.cur_proof < len(d.proofs) else "") or ""
        if lemma:
            msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + (
                f"\n\nThis theorem is already in Mathlib under the name `{lemma}` and the proof uses it. Say so "
                f"explicitly at the start (« ce théorème est dans Mathlib sous le nom `{lemma}` »), then explain the "
                "mathematical idea of that result." if language() != "en" else
                f"\n\nThis theorem is already in Mathlib under the name `{lemma}` and the proof uses it. Say so "
                "explicitly at the start, then explain the mathematical idea of that result.")}
        c = await io.complete("explain", msgs, None,
                              temperature=0.5, max_tokens=2000, extra={"top_p": 0.9, **NO_THINK, "repeat_penalty": 1.05})
        text = leancheck.clean_model_text(c.text)
        text = await self._check_citations(job, d, text, cites)
        if not text:
            raise Failed("L'IA n'a rien écrit : réessayez.", "empty")
        idx = d.add_explanation(text, note=req, model=c.model.key)
        self._record(c.model.key, "explain", d, ok=c.finish != "loop", seconds=c.seconds)
        await self.event(d, job, "explanation", "Explication rédigée par l'IA (la preuve Lean fait foi).", ref=idx,
                         model=c.model.key)
        if c.finish == "loop":
            await self.event(d, job, "info", "Explication prête (réponse interrompue : l'IA tournait en rond).")
        if s.informal_proof and (not req or not d.informal_proof):
            job.plan.insert(0, {"stage": "informal"})

    async def _check_citations(self, job: Job, d: Dossier, text: str, cites: dict | None) -> str:
        """Citations `[@key]` of keys that do not exist are removed by code (never printed) and reported."""
        if not text or "@" not in text:
            return text
        from ..research.biblio import check_citations
        res = check_citations(text, (cites or {}).get("keys") or set())
        if res.unknown:
            await self.event(d, job, "info", "Références inventées par l'IA retirées : {keys}.",
                             keys=", ".join(res.unknown[:10]))
        return res.text

    async def _informal(self, job: Job, d: Dossier, io: JobIO, req: str) -> None:
        if not d.proof:
            return
        nl = d.understood_display or d.understood or d.problem
        cites = _citations(self.ctx, d)
        msgs = prompts.informal_messages(d.proof, nl, language())
        if cites:
            msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + cites["prompt"]}
        try:
            c = await io.complete("explain", msgs, None,
                                  temperature=0.4, max_tokens=2500, extra={"top_p": 0.9, **NO_THINK})
        except BrainError:
            return
        text = leancheck.clean_model_text(c.text)
        text = await self._check_citations(job, d, text, cites)
        if text:
            idx = d.add_informal_proof(text, c.model.key)
            await self.event(d, job, "informal", "Preuve rédigée en langage naturel par l'IA (la preuve Lean fait foi).",
                             ref=idx, model=c.model.key)


def _citations(ctx, d: Dossier) -> dict | None:
    """Keys the model may cite in this dossier's texts (research layer, S-E); None without references."""
    try:
        from ..research.biblio import citation_support
        return citation_support(ctx, d, language())
    except Exception:  # noqa: BLE001 (the research layer must never break the pipeline)
        return None


def model_key(m) -> str:
    """"provider:model_id" for a ModelRef (never its Python repr), the string itself otherwise."""
    if m is None:
        return ""
    key = getattr(m, "key", None)
    return key if isinstance(key, str) else str(m)


def _accepts(fn, name: str) -> bool:
    try:
        ps = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return name in ps or any(p.kind == p.VAR_KEYWORD for p in ps.values())


class _RoundIO:
    """The job's StageIO for one tournament contestant: its attempts carry the round number and are remembered."""

    def __init__(self, io, k: int):
        self._io, self.k = io, k
        self.attempts: list = []

    def new_attempt(self, stage: str, kind: str):
        a = self._io.new_attempt(stage, kind)
        a.round = self.k
        self.attempts.append(a)
        return a

    def __getattr__(self, name):
        return getattr(self._io, name)


def _agent_fn():
    try:
        from ..brain.prover_agent import prove_with_agent  # type: ignore
        return prove_with_agent
    except Exception:  # noqa: BLE001 (S-B module absent or broken: goedel only)
        return None


def parse_split(text: str) -> list[dict]:
    """Lemmas proposed by a model for « split into lemmas »: [{title, statement}]."""
    code = leancheck.extract_code(text) or text
    out = []
    pending = ""
    for block in re.split(r"(?m)^(?=--|theorem\s|lemma\s)", code):
        b = block.strip()
        if b.startswith("--"):
            pending = b.split("\n", 1)[0].lstrip("- ").strip()
            rest = b.split("\n", 1)[1].strip() if "\n" in b else ""
            if not rest:
                continue
            b = rest
        if re.match(r"(theorem|lemma)\s", b):
            stmt = b.split(":= by", 1)[0].split(":=", 1)[0].rstrip() + " := by sorry"
            name = re.match(r"(?:theorem|lemma)\s+(\S+)", b).group(1)
            out.append({"title": pending or name, "statement": stmt.replace("lemma ", "theorem ", 1)})
            pending = ""
    return out
