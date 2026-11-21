"""Common types of the provider clients."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..api import Chunk, OnChunk


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""                 # raw JSON text as received
    input: dict | None = None           # parsed (None when invalid)
    error: str = ""                     # why the arguments could not be used


@dataclass
class StreamResult:
    text: str = ""
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish: str = "stop"                # stop | length | loop | tool_use | refusal | context
    tokens_in: int = 0
    tokens_out: int = 0
    model_reported: str = ""
    raw_blocks: list[dict] = field(default_factory=list)   # Anthropic content blocks, replayed unchanged
    cache_read: int = 0
    cache_write: int = 0


class ProviderError(Exception):
    """kind: http | network | stall | empty | context | refusal | tools_unsupported | bad_param"""

    def __init__(self, kind: str, message: str, status: int = 0, wait: float | None = None, param: str = ""):
        super().__init__(message)
        self.kind, self.message, self.status, self.wait, self.param = kind, message, status, wait, param


def emit(on_chunk: OnChunk | None, kind: str, text: str = "", **data: Any) -> None:
    if on_chunk is not None:
        try:
            on_chunk(Chunk(kind, text, data))
        except Exception:  # noqa: BLE001 (a UI callback must never break a generation)
            pass


def parse_args(raw: str) -> tuple[dict | None, str]:
    import json
    s = (raw or "").strip()
    if not s:
        return {}, ""
    try:
        v = json.loads(s)
    except ValueError as e:
        return None, f"INVALID_JSON: {e}"
    if not isinstance(v, dict):
        return None, "INVALID_JSON: arguments must be a JSON object"
    return v, ""
