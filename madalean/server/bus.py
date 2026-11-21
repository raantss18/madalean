"""WebSocket event bus: every event gets a sequence number and goes to every client; a ring buffer lets a client
that reconnects get what it missed (`{"type":"resume","seq":N}`), or a `resync` order when it is too late.

Streamed model text is coalesced per (job, stage, attempt) and flushed every 100 ms as one `job.token` event, so a
fast model does not flood the clients or the ring buffer."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

from ..logs import get

log = get("bus")


class EventBus:
    def __init__(self, ring: int = 5000, flush_s: float = 0.1):
        self.seq = 0
        self.ring: deque[dict] = deque(maxlen=ring)
        self.subscribers: set[asyncio.Queue] = set()
        self.flush_s = flush_s
        self._tokens: dict[tuple, list[str]] = {}
        self._flusher: asyncio.TimerHandle | None = None
        self.boot = int(time.time() * 1000)          # changes on restart: clients must resync
        self.recorder = None                         # callable(job_id, stage, attempt, kind, text): replay store
        # open WebSockets and in-flight streaming tasks per credential (device / browser-session id), so that a
        # revoked or expired credential loses them at once
        self.sockets: dict[str, set] = {}
        self.owned: dict[str, set] = {}

    def publish(self, type_: str, payload: dict[str, Any] | None = None) -> dict:
        if type_ != "job.token":
            self._flush_tokens()                     # keep the order: tokens written before this event come first
        self.seq += 1
        ev = {"type": type_, "seq": self.seq, "ts": time.time(), **(payload or {})}
        self.ring.append(ev)
        for q in list(self.subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                self.subscribers.discard(q)          # too slow: it will reconnect and resume/resync
                try:
                    q.put_nowait(None)
                except asyncio.QueueFull:
                    pass
        return ev

    def token(self, job_id: str, stage: str, attempt: int, text: str, kind: str = "text") -> None:
        if not text:
            return
        if self.recorder is not None:
            self.recorder(job_id, stage, attempt, kind, text)
        self._tokens.setdefault((job_id, stage, attempt, kind), []).append(text)
        if self._flusher is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                self._flush_tokens()
                return
            self._flusher = loop.call_later(self.flush_s, self._flush_tokens)

    def _flush_tokens(self) -> None:
        if self._flusher is not None:
            self._flusher.cancel()
            self._flusher = None
        if not self._tokens:
            return
        pending, self._tokens = self._tokens, {}
        for (job_id, stage, attempt, kind), parts in pending.items():
            self.publish("job.token", {"job_id": job_id, "stage": stage, "attempt": attempt, "kind": kind,
                                       "text": "".join(parts)})

    def since(self, seq: int) -> list[dict] | None:
        """Events after `seq`, or None when some of them already left the ring buffer (→ resync)."""
        if seq >= self.seq:
            return []
        if not self.ring or self.ring[0]["seq"] > seq + 1:
            return None
        return [e for e in self.ring if e["seq"] > seq]

    def subscribe(self, maxsize: int = 10000) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)
