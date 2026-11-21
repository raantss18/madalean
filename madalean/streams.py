"""Replay of the text a job streamed (GET /api/jobs/{id}/stream), so a page opened or reloaded mid-job can rebuild
every stage's partial text. Bounded memory: `per_job` characters per job (oldest text dropped first), at most
`max_jobs` jobs, kept until `keep_s` seconds after the job ended."""
from __future__ import annotations

import time
from collections import OrderedDict


class StreamStore:
    def __init__(self, per_job: int = 1_000_000, max_jobs: int = 40, keep_s: float = 600.0, clock=time.monotonic):
        self.per_job, self.max_jobs, self.keep_s, self.clock = per_job, max_jobs, keep_s, clock
        self.jobs: OrderedDict[str, dict] = OrderedDict()

    def record(self, job_id: str, stage: str, attempt: int, kind: str, text: str) -> None:
        if not text:
            return
        j = self.jobs.get(job_id)
        if j is None:
            self._gc()
            j = self.jobs[job_id] = {"chunks": [], "start": 0, "end": 0, "size": 0, "ended": None}
        ch = j["chunks"]
        if ch and ch[-1][1:4] == (stage, attempt, kind):          # merge with the previous piece of the same stream
            off, st, at, kd, tx = ch[-1]
            ch[-1] = (off, st, at, kd, tx + text)
        else:
            ch.append((j["end"], stage, attempt, kind, text))
        j["end"] += len(text)
        j["size"] += len(text)
        while j["size"] > self.per_job and len(ch) > 1:            # drop the oldest chunks
            off, _s, _a, _k, tx = ch.pop(0)
            j["size"] -= len(tx)
            j["start"] = ch[0][0]
        if j["size"] > self.per_job:                               # one huge chunk: keep its tail
            off, st, at, kd, tx = ch[0]
            cut = j["size"] - self.per_job
            ch[0] = (off + cut, st, at, kd, tx[cut:])
            j["start"], j["size"] = off + cut, self.per_job

    def finish(self, job_id: str) -> None:
        j = self.jobs.get(job_id)
        if j is not None:
            j["ended"] = self.clock()

    def read(self, job_id: str, start: int = 0) -> dict | None:
        """Text streamed after character offset `start`: {start, end, truncated, segments:[{offset, stage,
        attempt, kind, text}]}. `truncated` = part of what was asked was already dropped."""
        self._gc()
        j = self.jobs.get(job_id)
        if j is None:
            return None
        start = max(0, int(start))
        segs = []
        for off, st, at, kd, tx in j["chunks"]:
            if off + len(tx) <= start:
                continue
            cut = max(0, start - off)
            segs.append({"offset": off + cut, "stage": st, "attempt": at, "kind": kd, "text": tx[cut:]})
        return {"start": max(start, j["start"]), "end": j["end"], "truncated": start < j["start"],
                "ended": j["ended"] is not None, "segments": segs}

    def _gc(self) -> None:
        now = self.clock()
        for jid in [k for k, v in self.jobs.items() if v["ended"] is not None and now - v["ended"] > self.keep_s]:
            del self.jobs[jid]
        while len(self.jobs) >= self.max_jobs:
            done = next((k for k, v in self.jobs.items() if v["ended"] is not None), None)
            self.jobs.pop(done if done is not None else next(iter(self.jobs)))
