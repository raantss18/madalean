"""Pairing codes, device tokens and rate limiting (ARCHITECTURE §4).

- A pairing code: 6 digits, valid 5 minutes, single use. 5 wrong tries lock pairing for 10 minutes (and burn the
  code). Codes are created only from the local (trusted) listener.
- A device token: 256 random bits (urlsafe base64). Only its SHA-256 is stored, in devices.json (0600)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config
from .logs import get

log = get("security")
CODE_TTL = 300.0
MAX_WRONG = 5
LOCK_S = 600.0
TOKEN_COOKIE = "madalean_token"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Device:
    id: str
    name: str
    token_sha256: str
    created: float = field(default_factory=time.time)
    last_seen: float = 0.0
    last_ip: str = ""

    def public(self) -> dict:
        d = asdict(self)
        d.pop("token_sha256")
        return d


class PairingError(Exception):
    def __init__(self, kind: str, retry_after: float = 0.0):
        super().__init__(kind)
        self.kind, self.retry_after = kind, retry_after     # kind: no_code | expired | wrong | locked


class Pairing:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.code: str | None = None
        self.expires = 0.0
        self.wrong = 0
        self.locked_until = 0.0
        self._lock = threading.Lock()

    def start(self) -> tuple[str, float]:
        """New code (replaces the previous one). Returns (code, seconds of validity)."""
        with self._lock:
            self.code = f"{secrets.randbelow(10**6):06d}"
            self.expires = self.clock() + CODE_TTL
            self.wrong = 0
            return self.code, CODE_TTL

    def status(self) -> dict:
        now = self.clock()
        return {"active": bool(self.code) and now < self.expires, "expires_in": max(0.0, self.expires - now),
                "locked_for": max(0.0, self.locked_until - now)}

    def consume(self, code: str) -> None:
        """Raises PairingError unless `code` is the current valid code (which is then burnt)."""
        with self._lock:
            now = self.clock()
            if now < self.locked_until:
                raise PairingError("locked", self.locked_until - now)
            if not self.code:
                raise PairingError("no_code")
            if now >= self.expires:
                self.code = None
                raise PairingError("expired")
            if not (isinstance(code, str) and hmac.compare_digest(code.strip(), self.code)):
                self.wrong += 1
                if self.wrong >= MAX_WRONG:
                    self.locked_until = now + LOCK_S
                    self.code = None
                    self.wrong = 0
                    log.warning("pairing locked for %d s after %d wrong codes", LOCK_S, MAX_WRONG)
                    raise PairingError("locked", LOCK_S)
                raise PairingError("wrong")
            self.code = None
            self.wrong = 0


class Devices:
    def __init__(self, file: Path):
        self.file = Path(file)
        self._lock = threading.Lock()
        self.items: dict[str, Device] = {}
        self._by_hash: dict[str, str] = {}
        self._dirty_seen = 0.0
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = []
        names = set(Device.__dataclass_fields__)
        self.items = {}
        for d in data if isinstance(data, list) else []:
            try:
                dev = Device(**{k: v for k, v in d.items() if k in names})
            except TypeError:
                continue
            self.items[dev.id] = dev
        self._by_hash = {d.token_sha256: d.id for d in self.items.values()}

    def save(self) -> None:
        config.atomic_write_text(self.file, json.dumps([asdict(d) for d in self.items.values()], indent=1))
        os.chmod(self.file, 0o600)

    def add(self, name: str) -> tuple[Device, str]:
        """New device; returns (device, token). The token is shown once and never stored."""
        token = secrets.token_urlsafe(32)
        name = (name or "").strip()[:80] or "device"
        with self._lock:
            dev = Device("d-" + uuid.uuid4().hex[:10], name, hash_token(token))
            self.items[dev.id] = dev
            self._by_hash[dev.token_sha256] = dev.id
            self.save()
        log.info("device paired: %s (%s)", dev.id, name)
        return dev, token

    def check(self, token: str | None, ip: str = "") -> Device | None:
        if not token or len(token) > 200:
            return None
        h = hash_token(token)
        with self._lock:
            did = None
            for known, dev_id in self._by_hash.items():       # constant-time comparison of every candidate
                if hmac.compare_digest(known, h):
                    did = dev_id
            dev = self.items.get(did) if did else None
            if dev is not None:
                now = time.time()
                dev.last_ip = ip or dev.last_ip
                if now - dev.last_seen > 60:                  # do not rewrite the file on every request
                    dev.last_seen = now
                    try:
                        self.save()
                    except OSError:
                        pass
            return dev

    def revoke(self, did: str) -> bool:
        with self._lock:
            dev = self.items.pop(did, None)
            if dev is None:
                return False
            self._by_hash.pop(dev.token_sha256, None)
            self.save()
        log.info("device revoked: %s", did)
        return True

    def list(self) -> list[dict]:
        return [d.public() for d in sorted(self.items.values(), key=lambda d: d.created)]


class RateLimiter:
    """Sliding window: at most `n` events per `window` seconds per key."""

    def __init__(self, n: int, window: float, clock=time.monotonic):
        self.n, self.window, self.clock = n, window, clock
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = self.clock()
        h = [t for t in self.hits.get(key, []) if now - t < self.window]
        if len(h) >= self.n:
            self.hits[key] = h
            return False
        h.append(now)
        self.hits[key] = h
        if len(self.hits) > 10000:
            self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < self.window}
        return True
