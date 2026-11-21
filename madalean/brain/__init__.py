"""Madalean's model engine (docs/ARCHITECTURE.md §7, docs/BRAIN.md). The server only calls `create_brain` and
`create_retriever`; the interface is madalean/brain/api.py."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .api import (AgentResult, Brain, BrainError, Chunk, Completion, LocalRuntime, Mode, ModelRef, Retriever, Role,
                  ToolSpec)

__all__ = ["create_brain", "create_retriever", "AgentResult", "Brain", "BrainError", "Chunk", "Completion",
           "LocalRuntime", "Mode", "ModelRef", "Retriever", "Role", "ToolSpec"]


def create_brain(config_dir: Path, local: LocalRuntime | None, get_key: Callable[[str], str | None],
                 settings: dict) -> Brain:
    """The model engine. `get_key(provider)` returns the API key of a provider ("anthropic", "gemini",
    "openrouter", …) or None; keys are read at each call, never stored. `settings`: see madalean.brain.settings /
    docs/BRAIN.md. Call `brain.update_settings(d)` after PATCH /settings, `await brain.close()` at shutdown."""
    from .engine import MadaleanBrain
    return MadaleanBrain(Path(config_dir), local, get_key, settings)


def create_retriever(cache_dir: Path, *, resolve=None, embeddings: bool = True) -> Retriever:
    """RAG over the declarations of a workspace (index under <cache_dir>/rag/). `resolve(workspace_key)` returns a
    madalean.workspaces.Workspace (default: built-in workspaces and `user:<path>` keys). Extra methods:
    `start(key)` (background build), `await ensure(key)`, `ready(key)`, `await suggest(key, name)`."""
    from .rag import LeanRetriever
    return LeanRetriever(Path(cache_dir), resolve=resolve, embeddings=embeddings)
