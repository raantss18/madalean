"""Interface between the server (pipeline, orchestrator) and the model engine. See docs/ARCHITECTURE.md §7.

The server only uses what is declared here; `madalean.brain` implements it, and `madalean.brain.fake` provides a
scripted implementation for tests and for `madalean serve --demo`."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Literal, Protocol

Role = Literal["understand", "route", "formalize", "prove", "explain", "assistant"]
Mode = Literal["local", "auto", "online"]


@dataclass
class ModelRef:
    provider: str            # "local", "anthropic", "gemini", "openrouter", "ollama", "llm7", …
    model_id: str
    name: str = ""
    local: bool = False
    paid: bool = False

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"


@dataclass
class Chunk:
    """One streamed piece. `kind`: text | thinking | tool_call | tool_result | info (model switch, fallback…)."""
    kind: str
    text: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class Completion:
    text: str
    model: ModelRef
    finish: str = "stop"          # stop | length | loop | cancelled | error
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    fallbacks: list[str] = field(default_factory=list)   # models tried before this one, with the reason


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict                                  # JSON schema
    run: Callable[[dict], Awaitable[str]]             # returns the text given back to the model


@dataclass
class AgentResult:
    final_text: str
    model: ModelRef
    steps: int
    finish: str                   # done | max_steps | budget | cancelled | error
    transcript: list[dict] = field(default_factory=list)   # for the history (no secrets)


OnChunk = Callable[[Chunk], None]


class Brain(Protocol):
    async def complete(self, role: Role, messages: list[dict], *, mode: Mode = "auto", temperature: float | None = None,
                       max_tokens: int | None = None, on_chunk: OnChunk | None = None, prefer: str | None = None,
                       extra: dict | None = None) -> Completion:
        """One answer for `role`. Picks the model (router), streams through `on_chunk`, falls back on failure
        (other online model, then local). `prefer` = model key forced by the user. Raises BrainError when nothing
        can answer. Cancelled by cancelling the task."""

    async def run_agent(self, role: Role, system: str, task: str, tools: list[ToolSpec], *, mode: Mode = "auto",
                        max_steps: int = 24, max_seconds: float = 900, on_chunk: OnChunk | None = None,
                        prefer: str | None = None) -> AgentResult:
        """Tool-using loop with a model that supports tools (native Anthropic tool use, or OpenAI-style tools)."""

    def candidates(self, role: Role, mode: Mode = "auto") -> list[ModelRef]:
        """Models the router would try, best first (shown in the UI)."""

    async def status(self) -> dict[str, Any]:
        """{online: bool, providers: [{id, name, keyed, key_set, ok, paused_until, reason}], local: {...}}"""

    async def refresh(self) -> None:
        """Refresh the online catalogue (never blocks answering)."""

    async def close(self) -> None: ...


class BrainError(Exception):
    def __init__(self, kind: str, message: str = "", tried: list[str] | None = None):
        super().__init__(message or kind)
        self.kind, self.tried = kind, tried or []     # kind: no_model | offline | quota | auth | cancelled | error


class LocalRuntime(Protocol):
    """Provided by the server to the brain: the single local llama-server (one model in VRAM at a time)."""

    async def ensure(self, role: Role) -> str | None:
        """Load the local model for this role if needed; returns its OpenAI-compatible base URL, or None if the
        role has no local model installed. Holds the `gpu` slot for the caller until `release()`."""

    def release(self) -> None: ...

    def model_for(self, role: Role) -> ModelRef | None: ...


class Retriever(Protocol):
    """RAG over the workspace's declarations (madalean.brain.rag)."""

    async def search(self, workspace_key: str, query: str, k: int = 8) -> list[dict]:
        """[{name, signature, doc, module, score}] — lexical (FTS5) + semantic when embeddings are available."""

    async def premises(self, workspace_key: str, lean_statement: str, k: int = 8) -> list[dict]: ...

    async def declaration(self, workspace_key: str, name: str) -> dict | None: ...
