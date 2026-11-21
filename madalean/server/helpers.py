"""Model calls made outside a job (split proposal, assistant), with the same slot discipline as jobs."""
from __future__ import annotations

from ..brain.api import Completion, OnChunk
from ..slots import CURRENT_JOB


async def complete_once(ctx, role: str, messages: list[dict], mode: str, *, owner: str, on_chunk: OnChunk | None = None,
                        max_tokens: int | None = None, temperature: float | None = None) -> Completion:
    token = CURRENT_JOB.set(owner)
    need_online = mode != "local"
    try:
        if need_online:
            await ctx.slots.acquire("online", owner)
        try:
            return await ctx.brain.complete(role, messages, mode=mode, temperature=temperature, max_tokens=max_tokens,
                                            on_chunk=on_chunk, prefer=(ctx.settings.prefer or {}).get(role) or None)
        finally:
            if need_online:
                ctx.slots.release("online", owner)
            try:
                ctx.local.release_owner(owner)
            except Exception:  # noqa: BLE001
                pass
    finally:
        CURRENT_JOB.reset(token)
