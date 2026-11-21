"""Jobs of different dossiers run in parallel, limited by the resource slots (ARCHITECTURE §6).

A dossier has at most one active job. Each job is an asyncio task carrying its id (`slots.CURRENT_JOB`) and its
priority (user-started first), so every slot it waits for is attributed to it. Cancelling a job cancels the task:
the model request is aborted and the Lean process killed. Finished jobs go to the dossier's history.

Sub-dossiers: when a lemma split from a parent (`parent_id`) ends and all the parent's children are finished, the
parent is retried automatically (proof + explanation) with the proven children given as library lemmas."""
from __future__ import annotations

import asyncio
import time

from .i18n import msg
from .jobs import Job, JobHistory
from .logs import get
from .pipeline.runner import DossierPipeline
from .slots import CURRENT_JOB, CURRENT_PRIORITY

log = get("orchestrator")
KEEP_FINISHED = 200


class DossierBusy(Exception):
    def __init__(self, job: Job):
        super().__init__(job.id)
        self.job = job


class Orchestrator:
    def __init__(self, ctx, history: JobHistory):
        self.ctx = ctx
        self.history = history
        self.jobs: dict[str, Job] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.by_dossier: dict[str, str] = {}
        self.pipeline = DossierPipeline(ctx)
        ctx.slots.on_wait = self._on_wait

    # ------------------------------------------------------------ queries
    def active(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.active]

    def recent(self, n: int = 50) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created, reverse=True)[:n]

    def active_for(self, dossier_id: str) -> Job | None:
        jid = self.by_dossier.get(dossier_id)
        return self.jobs.get(jid) if jid else None

    async def history_for(self, dossier_id: str) -> list[Job]:
        done = await asyncio.to_thread(self.history.load, dossier_id)
        act = self.active_for(dossier_id)
        return done + ([act] if act else [])

    # ------------------------------------------------------------ control
    def submit(self, dossier_id: str, plan: list[dict], *, mode: str | None = None, strategy: str | None = None,
               user: bool = True) -> Job:
        cur = self.active_for(dossier_id)
        if cur is not None:
            raise DossierBusy(cur)
        s = self.ctx.settings
        job = Job.new(dossier_id, plan, mode or s.mode, strategy or s.prove_strategy, user)
        self.jobs[job.id] = job
        self.by_dossier[dossier_id] = job.id
        self.tasks[job.id] = asyncio.create_task(self._run(job), name=f"job-{job.id}")
        self._trim()
        self.ctx.publish_job(job)
        log.info("job %s submitted for %s: %s (%s)", job.id, dossier_id, [p.get("stage") for p in plan], job.mode)
        return job

    async def cancel(self, job_id: str, wait: bool = True) -> bool:
        t = self.tasks.get(job_id)
        if t is None or t.done():
            return False
        t.cancel()
        if wait:
            try:
                await asyncio.wait_for(asyncio.shield(t), 15)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass
        return True

    async def cancel_dossier(self, dossier_id: str) -> bool:
        j = self.active_for(dossier_id)
        return await self.cancel(j.id) if j else False

    async def shutdown(self) -> None:
        for t in list(self.tasks.values()):
            t.cancel()
        if self.tasks:
            await asyncio.wait(list(self.tasks.values()), timeout=10)

    # ------------------------------------------------------------ internals
    def _on_wait(self, owner: str, resource: str, waiting: bool) -> None:
        job = self.jobs.get(owner)
        if job is None or not job.active:
            return
        job.waiting = resource if waiting else ""
        job.state = "queued" if waiting else "running"
        self.ctx.publish_job(job)

    def _trim(self) -> None:
        done = [j for j in self.jobs.values() if not j.active]
        if len(done) > KEEP_FINISHED:
            for j in sorted(done, key=lambda j: j.created)[: len(done) - KEEP_FINISHED]:
                self.jobs.pop(j.id, None)
                self.tasks.pop(j.id, None)

    async def _run(self, job: Job) -> None:
        CURRENT_JOB.set(job.id)
        CURRENT_PRIORITY.set(0 if job.user else 1)
        job.state, job.started = "running", time.time()
        self.ctx.publish_job(job)
        d = self.ctx.repo.get(job.dossier_id)
        try:
            await self.pipeline.run(job)
            job.state = "failed" if job.error else "done"
        except asyncio.CancelledError:
            job.state, job.error = "cancelled", "cancelled"
            job.summary = msg("Arrêté à votre demande.")
            for a in job.attempts:
                if a.status in ("generating", "compiling"):
                    a.status = "cancelled"
            if d is not None:
                if d.status in ("translating", "proving"):
                    d.status = "proved" if d.proof_is_current else "stopped"
                try:
                    await self.pipeline.event(d, job, "info", "Arrêté à votre demande.")
                except Exception:  # noqa: BLE001
                    log.exception("could not record the cancellation")
        except Exception as e:  # noqa: BLE001
            log.exception("job %s crashed", job.id)
            job.state, job.error = "failed", "internal"
            job.summary = msg("Erreur interne : {err}", err=str(e)[:300])
            if d is not None:
                if d.status in ("translating", "proving"):
                    d.status = "failed"
                try:
                    await self.pipeline.event(d, job, "error", "Erreur interne : {err}", err=str(e)[:300])
                except Exception:  # noqa: BLE001
                    pass
        finally:
            job.ended = time.time()
            job.stage, job.waiting = "", ""
            self.ctx.slots.release_all(job.id)
            try:
                self.ctx.local.release_owner(job.id)
            except Exception:  # noqa: BLE001
                pass
            if self.by_dossier.get(job.dossier_id) == job.id:
                del self.by_dossier[job.dossier_id]
            self.ctx.publish_job(job)
            try:
                await asyncio.shield(asyncio.to_thread(self.history.append, job))
            except Exception:  # noqa: BLE001
                log.exception("could not write job history")
            log.info("job %s %s", job.id, job.state)
        if job.state != "cancelled":
            await self._after(job)

    async def _after(self, job: Job) -> None:
        d = self.ctx.repo.get(job.dossier_id)
        if d is None or not d.parent_id:
            return
        parent = self.ctx.repo.get(d.parent_id)
        if parent is None or not parent.retry_parent or parent.proof_is_current or not parent.statement:
            return
        kids = self.ctx.repo.children(parent.id)
        if any(self.active_for(k.id) for k in kids):
            return
        proven = [k for k in kids if k.proof_is_current]
        if not proven or self.active_for(parent.id):
            return
        parent.retry_parent = False
        await self.pipeline.event(parent, None, "info", "Lemmes prouvés : {n}/{m}. Nouvel essai de la preuve avec ces "
                                  "lemmes.", n=len(proven), m=len(kids))
        try:
            self.submit(parent.id, [{"stage": "proof"}, {"stage": "explanation"}], user=False)
        except DossierBusy:
            pass
