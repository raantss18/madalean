"""Streaming guards shared by every provider: loop / rambling detection (leancheck, DECISIONS D22) and stall
timeouts. The watchdog itself lives in net.sse_events (per-read timeout)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import leancheck

STALL_ONLINE = 90.0       # seconds without any byte from an online provider
STALL_LOCAL = 180.0       # local llama-server (ChatStream.stall_s)
FIRST_BYTE_ONLINE = 120.0
FIRST_BYTE_LOCAL = 600.0  # model loading / long prompt processing
# Reasoning models may send NOTHING (not even the HTTP headers) while they think: Gemini's OpenAI-compatible endpoint
# answers only when the first visible token exists. 120 s cut real Gemini 3.x runs (« stalled », 2026-11-21) that
# were thinking, not dead: they get a longer first-byte wait (their effort is also capped, engine.GEMINI_EFFORT).
FIRST_BYTE_REASONING = 300.0
_REASONING = re.compile(r"^gemini-(2\.5|[3-9])|^gemini-(flash|flash-lite|pro)-latest$|magistral|deepseek-r1|reasoner|"
                        r"qwq|(^|[/-])o[134](-|$)|gpt-5|thinking|goedel-prover|grok-[34].*(reason|mini)|kimi-k2-thinking", re.I)


def reasoning_model(model_id: str) -> bool:
    """A model that thinks before its first visible token (longer first-byte timeout)."""
    return bool(_REASONING.search(model_id or ""))


def gemini_thinking(model_id: str) -> bool:
    """A Gemini model whose thinking is set with `reasoning_effort` on the OpenAI-compatible API (2.5, 3.x, 4,
    the `-latest` aliases; not Gemma, not 2.0)."""
    return bool(re.match(r"gemini-(2\.5|[3-9])|gemini-(flash|flash-lite|pro)-latest$", (model_id or "").lower()))


@dataclass
class LoopGuard:
    """Feed every streamed piece; `tripped` becomes (unit, reps) when the generation goes round in circles."""
    pieces: int = 0
    parts: list[str] = field(default_factory=list)
    tripped: tuple[int, int] | None = None

    def feed(self, piece: str) -> bool:
        if self.tripped or not piece:
            return bool(self.tripped)
        self.parts.append(piece)
        self.pieces += 1
        if self.pieces % 40 == 0:
            self.tripped = leancheck.detect_loop("".join(self.parts))
        if self.pieces % 200 == 0 and self.tripped is None and leancheck.detect_rambling("".join(self.parts)):
            self.tripped = (0, 1)          # recycled paragraphs: keep the text as it is
        return bool(self.tripped)

    def cut(self, text: str) -> str:
        """Keep the first occurrence of the repeated block (as ChatStream did)."""
        if not self.tripped:
            return text
        unit, reps = self.tripped
        if unit and text.endswith(text[-unit:] * reps):
            return text[: len(text) - unit * (reps - 1)]
        return text
