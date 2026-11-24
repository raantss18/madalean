"""S-AY (D57, D57b): what the provers are told from memory — the problem graph's digest (proved lemmas, cited results,
failed approaches, tactics) and the host's lessons (renames, fixes, strategies). Both are bounded, deterministic text
appended to the provers' hint; any failure here gives "" (memory is a help, never a failure)."""
from __future__ import annotations

from ..logs import get

log = get("memory_hook")


def _env(ctx, d) -> dict:
    try:
        from ..runtime.lean import workspace_info
        return workspace_info(ctx.workspace(d.workspace or ctx.settings.workspace)) or {}
    except Exception:  # noqa: BLE001
        return {}


def memory_hint(ctx, d, ids: list | None = None) -> str:
    """`ids` receives the lessons put in the hint (their outcome is recorded, D67)."""
    parts = []
    try:
        gs = getattr(getattr(ctx, "research", None), "graphs", None)
        if gs is not None:
            parts.append(gs.prover_hint(d))
    except Exception:  # noqa: BLE001
        log.exception("graph digest")
    try:
        from ..research import lessons
        st = lessons.store_of(ctx)
        if st is not None and d.statement:
            parts.append(st.hint(d.statement, _env(ctx, d), ids=ids))
    except Exception:  # noqa: BLE001
        log.exception("lessons hint")
    return "\n\n".join(p for p in parts if p)


def error_hint(ctx, d, feedback: str) -> str:
    try:
        from ..research import lessons
        st = lessons.store_of(ctx)
        return st.error_hint(feedback, _env(ctx, d)) if st is not None and feedback else ""
    except Exception:  # noqa: BLE001
        return ""
