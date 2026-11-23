"""The MCP activity log and the rate limits (session S-AZ, DECISIONS D58).

Every tool call — made TO Madalean by an MCP client, or BY Madalean to an external MCP server — is one line of
`<config>/logs/mcp-activity.jsonl` (0600, rotated at 1 MB, one old file kept) and is kept in memory (the 200 most
recent) for Réglages › Outils (MCP). A line holds: time, direction (in | out), transport, server, tool, outcome,
duration, the size of the arguments and of the answer, and a short redacted preview of the arguments. Never the
answer itself (it can be a whole proof or a page of an external tool's output), never a key."""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path

from ..logs import get, redact

log = get("mcp")
MAX_BYTES = 1_000_000
KEEP = 200
PREVIEW = 160


class ActivityLog:
    def __init__(self, path: Path | None):
        self.path = path
        self.recent: deque[dict] = deque(maxlen=KEEP)
        self._lock = threading.Lock()

    def record(self, *, direction: str, transport: str, tool: str, ok: bool, ms: float, server: str = "madalean",
               args: object = None, out_size: int = 0, error: str = "") -> dict:
        try:
            raw = json.dumps(args, ensure_ascii=False, default=str) if args is not None else ""
        except (TypeError, ValueError):
            raw = ""
        entry = {"t": round(time.time(), 3), "dir": direction, "transport": transport, "server": server[:80],
                 "tool": tool[:80], "ok": bool(ok), "ms": int(ms), "in": len(raw), "out": int(out_size),
                 "args": redact(raw[:PREVIEW]) + ("…" if len(raw) > PREVIEW else ""), "error": redact(error[:200])}
        with self._lock:
            self.recent.append(entry)
            if self.path is not None:
                try:
                    self._append(entry)
                except OSError as e:
                    log.warning("mcp activity log: %s", e)
        log.info("mcp %s %s/%s %s %d ms", direction, entry["server"], entry["tool"], "ok" if ok else "error",
                 entry["ms"])
        return entry

    def _append(self, entry: dict) -> None:
        p = self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            if p.stat().st_size > MAX_BYTES:
                os.replace(p, p.with_suffix(".jsonl.1"))
        except FileNotFoundError:
            pass
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def list(self, limit: int = 100, direction: str = "") -> list[dict]:
        with self._lock:
            items = [e for e in self.recent if not direction or e["dir"] == direction]
        return list(reversed(items))[:limit]


class RateLimiter:
    """Sliding window per key: at most `limit` events per `window` seconds."""

    def __init__(self):
        self.events: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, window: float = 60.0) -> float:
        """0 when allowed (and counted), else the seconds to wait."""
        now = time.monotonic()
        q = self.events.setdefault(key, deque())
        while q and now - q[0] >= window:
            q.popleft()
        if len(q) >= limit:
            return round(window - (now - q[0]), 1)
        q.append(now)
        return 0.0
