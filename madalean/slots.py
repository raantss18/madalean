"""Resource slots shared by every job (ARCHITECTURE §6): gpu = 1 (the local llama-server), online = 3, lean = 2.

A job only waits for the slot its current step needs. Waiters are served by priority (user-started jobs first),
then FIFO. `CURRENT_JOB` / `CURRENT_PRIORITY` travel with the asyncio context, so code deep inside a job (the local
runtime called by the brain, the Lean runner) knows which job it works for."""
from __future__ import annotations

import asyncio
import contextvars
import heapq
import itertools
from contextlib import asynccontextmanager
from typing import Callable

CURRENT_JOB: contextvars.ContextVar[str] = contextvars.ContextVar("madalean_job", default="")
CURRENT_PRIORITY: contextvars.ContextVar[int] = contextvars.ContextVar("madalean_priority", default=0)

DEFAULT_CAPS = {"gpu": 1, "online": 3, "lean": 2}


def current_owner() -> str:
    job = CURRENT_JOB.get()
    if job:
        return job
    t = asyncio.current_task()
    return f"task-{id(t)}"


class Slots:
    def __init__(self, caps: dict[str, int] | None = None):
        self.caps = dict(DEFAULT_CAPS if caps is None else caps)
        self.holders: dict[str, list[str]] = {r: [] for r in self.caps}
        self._waiters: dict[str, list] = {r: [] for r in self.caps}
        self._seq = itertools.count()
        self.max_seen: dict[str, int] = {r: 0 for r in self.caps}     # for tests: never above capacity
        self.on_wait: Callable[[str, str, bool], None] | None = None   # (owner, resource, waiting)
        self.on_change: Callable[[], None] | None = None

    def usage(self) -> dict:
        return {r: {"capacity": self.caps[r], "used": len(self.holders[r]), "holders": list(self.holders[r]),
                    "waiting": sum(1 for w in self._waiters[r] if not w[3].done())} for r in self.caps}

    async def acquire(self, resource: str, owner: str | None = None, priority: int | None = None) -> None:
        owner = owner or current_owner()
        prio = CURRENT_PRIORITY.get() if priority is None else priority
        if len(self.holders[resource]) < self.caps[resource] and not self._pending(resource):
            self._grant(resource, owner)
            return
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        heapq.heappush(self._waiters[resource], (prio, next(self._seq), owner, fut))
        self._notify_wait(owner, resource, True)
        try:
            await fut
        except asyncio.CancelledError:
            if fut.done() and not fut.cancelled():
                self.release(resource, owner)        # granted while being cancelled: give it back
            raise
        finally:
            self._notify_wait(owner, resource, False)

    def _pending(self, resource: str) -> bool:
        return any(not w[3].done() for w in self._waiters[resource])

    def _grant(self, resource: str, owner: str) -> None:
        self.holders[resource].append(owner)
        self.max_seen[resource] = max(self.max_seen[resource], len(self.holders[resource]))
        assert len(self.holders[resource]) <= self.caps[resource], f"{resource} slot over-booked"
        if self.on_change:
            self.on_change()

    def release(self, resource: str, owner: str | None = None) -> bool:
        owner = owner or current_owner()
        hs = self.holders[resource]
        if owner not in hs:
            return False
        hs.remove(owner)
        q = self._waiters[resource]
        while q and len(hs) < self.caps[resource]:
            _p, _s, w_owner, fut = heapq.heappop(q)
            if fut.done():
                continue
            self._grant(resource, w_owner)
            fut.set_result(True)
        if self.on_change:
            self.on_change()
        return True

    def release_all(self, owner: str) -> None:
        for r in self.caps:
            while owner in self.holders[r]:
                self.release(r, owner)

    def holds(self, resource: str, owner: str | None = None) -> bool:
        return (owner or current_owner()) in self.holders[resource]

    @asynccontextmanager
    async def hold(self, resource: str, owner: str | None = None, priority: int | None = None):
        owner = owner or current_owner()
        await self.acquire(resource, owner, priority)
        try:
            yield
        finally:
            self.release(resource, owner)

    def _notify_wait(self, owner: str, resource: str, waiting: bool) -> None:
        if self.on_wait:
            try:
                self.on_wait(owner, resource, waiting)
            except Exception:  # noqa: BLE001
                pass
