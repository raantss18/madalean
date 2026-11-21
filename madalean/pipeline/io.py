"""What a pipeline stage needs from the job it runs in: attempts, streamed completions, Lean checks."""
from __future__ import annotations

import asyncio
from typing import Protocol

from .. import leancheck
from ..brain.api import BrainError, Completion
from ..jobs import Attempt
from ..runtime.lean import CompileResult


class InfraError(Exception):
    """The stage cannot go on (model server down, workspace broken…). `kind` as in 1.1.4: server_down | generation |
    workspace | no_model."""

    def __init__(self, kind: str, details: str = ""):
        super().__init__(kind)
        self.kind, self.details = kind, details


class StageIO(Protocol):
    def new_attempt(self, stage: str, kind: str) -> Attempt: ...

    def update_attempt(self, a: Attempt) -> None: ...

    async def complete(self, role: str, messages: list[dict], attempt: Attempt | None = None, *,
                       temperature: float | None = None, max_tokens: int | None = None, extra: dict | None = None,
                       mode: str | None = None, stage: str = "") -> Completion: ...

    async def check(self, code: str, ws, timeout_s: int, strict_name: str | None) -> CompileResult: ...


class LoopGuard:
    """1.1.4 ChatStream guard: exact loop every 40 chunks, rambling every 200 chunks (D13, D22)."""

    def __init__(self):
        self.parts: list[str] = []
        self.chunks = 0
        self.loop: tuple[int, int] | None = None

    def feed(self, piece: str) -> bool:
        """Add a streamed piece; True when the generation must be stopped."""
        if self.loop is not None or not piece:
            return self.loop is not None
        self.parts.append(piece)
        self.chunks += 1
        if self.chunks % 40 == 0:
            self.loop = leancheck.detect_loop("".join(self.parts))
        if self.loop is None and self.chunks % 200 == 0 and leancheck.detect_rambling("".join(self.parts)):
            self.loop = (0, 1)
        return self.loop is not None

    def trimmed(self) -> str:
        text = "".join(self.parts)
        if self.loop:
            unit, reps = self.loop
            text = text[: len(text) - unit * (reps - 1)]
        return text


def is_context_error(e: BaseException) -> bool:
    s = str(e).lower()
    return isinstance(e, BrainError) and ("context" in s or "exceed" in s)


def outer_cancelled() -> bool:
    t = asyncio.current_task()
    return bool(t and t.cancelling())
