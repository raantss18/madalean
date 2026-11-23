"""Never redo the same work twice (TODO B14, DECISIONS D38): the statement-check verdict and the Mathlib-first result
of a Lean statement, kept per (normalized statement, workspace, Lean and Mathlib versions).

- A check verdict is advice, reused as is (with a visible « déjà vérifié » event). Its key also holds the user's own
  words (fidelity is judged against them), the learning-mode flag and the language.
- A Mathlib-first success is kept as its tactic and lemma only: on reuse the proof is re-assembled for the current
  statement and judged by a fresh strict Lean check like any proof (nothing becomes « vérifiée » from the cache).
  A failure that had candidates is kept too (the provers get the same hint at once, no new search).
- A new Lean or Mathlib version, or another workspace, changes the key: nothing older is ever reused.

Stored in `<cache dir>/stage-cache.json` (bounded, least recently used dropped first)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

from .. import config, leancheck
from ..logs import get

log = get("stagecache")
MAX_ENTRIES = 400              # per kind
KINDS = ("check", "mathlib", "literature")      # literature: S-AX (D56), the search result of a statement


def normalize_statement(statement: str) -> str:
    """Comments, blank space and the theorem's own name do not change what is proved."""
    text = leancheck.remove_comments(statement or "")
    name = ""
    try:
        name = leancheck.theorem_name(text)
    except Exception:  # noqa: BLE001
        name = ""
    if name:
        text = re.sub(rf"(?<![\w.']){re.escape(name)}(?![\w'])", "_thm_", text)
    text = re.sub(r":=\s*by\s+sorry\s*$", "", text.strip())
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def make_key(statement: str, versions: dict, *extra: str) -> str:
    parts = [normalize_statement(statement), versions.get("workspace", ""), versions.get("lean", ""),
             versions.get("mathlib", ""), *extra]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]


class StageCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self.data: dict[str, dict[str, dict]] = {k: {} for k in KINDS}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for k in KINDS:
                if isinstance(raw.get(k), dict):
                    self.data[k] = {kk: v for kk, v in raw[k].items() if isinstance(v, dict)}
        except (OSError, ValueError, AttributeError):
            pass

    def get(self, kind: str, key: str) -> dict | None:
        e = self.data.get(kind, {}).get(key)
        if e is None:
            return None
        e["used"] = time.time()
        return dict(e.get("value") or {})

    async def put(self, kind: str, key: str, value: dict) -> None:
        table = self.data.setdefault(kind, {})
        table[key] = {"value": value, "t": time.time(), "used": time.time()}
        if len(table) > MAX_ENTRIES:
            for k in sorted(table, key=lambda k: table[k].get("used", 0))[: len(table) - MAX_ENTRIES]:
                del table[k]
        await self._save()

    async def drop(self, kind: str, key: str) -> None:
        if self.data.get(kind, {}).pop(key, None) is not None:
            await self._save()

    async def _save(self) -> None:
        async with self._lock:
            text = json.dumps(self.data, ensure_ascii=False)
            try:
                await asyncio.to_thread(config.atomic_write_text, self.path, text)
            except OSError as e:          # a cache that cannot be written is only a slower next run
                log.warning("stage cache not saved: %s", e)


def shared(ctx) -> StageCache:
    """The one StageCache of a server context (the pipeline and the literature search write the same file: two
    instances would overwrite each other's entries)."""
    c = getattr(ctx, "_stage_cache", None)
    if c is None:
        c = StageCache(ctx.paths.cache / "stage-cache.json")
        try:
            ctx._stage_cache = c
        except AttributeError:
            pass
    return c
