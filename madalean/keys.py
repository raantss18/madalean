"""API keys of online providers. Stored in the system keyring through `secret-tool` when it works, else in
`keys.json` (mode 0600). Keys are never returned by the API (only whether one is set) and never logged."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from . import config
from .logs import get

log = get("keys")
SERVICE = "madalean"
PROVIDER_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9_.-]{0,40}$")


class KeyStore:
    def __init__(self, file: Path, use_keyring: bool | None = None):
        self.file = Path(file)
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        exe = shutil.which("secret-tool")
        if use_keyring is None:
            use_keyring = os.environ.get("MADALEAN_NO_KEYRING") != "1"
        self.keyring = bool(use_keyring and exe)
        self._exe = exe
        self._index: set[str] = set()       # providers known to be in the keyring (names only, in keys.json)
        self._load_file()

    # ---------------------------------------------------------------- file backend
    def _load_file(self) -> None:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self._file_keys = {k: v for k, v in (data.get("keys") or {}).items() if isinstance(v, str)}
        self._index = set(data.get("keyring") or [])

    def _save_file(self) -> None:
        data = {"keys": self._file_keys, "keyring": sorted(self._index)}
        config.atomic_write_text(self.file, json.dumps(data, indent=1))
        os.chmod(self.file, 0o600)

    # ---------------------------------------------------------------- keyring backend
    def _st(self, args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess | None:
        try:
            return subprocess.run([self._exe, *args], input=stdin, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None

    # ---------------------------------------------------------------- API (blocking: call from a thread)
    def set(self, provider: str, key: str) -> str:
        """Store a key; returns the backend used ("keyring" | "file")."""
        if not PROVIDER_RE.match(provider):
            raise ValueError("bad provider")
        key = key.strip()
        if not key:
            raise ValueError("empty key")
        with self._lock:
            if self.keyring:
                r = self._st(["store", "--label", f"Madalean {provider}", "service", SERVICE, "provider", provider],
                             stdin=key)
                if r is not None and r.returncode == 0:
                    self._index.add(provider)
                    self._file_keys.pop(provider, None)
                    self._save_file()
                    self._cache[provider] = key
                    log.info("key stored in keyring for %s", provider)
                    return "keyring"
                log.warning("secret-tool store failed for %s: falling back to keys.json", provider)
            self._file_keys[provider] = key
            self._index.discard(provider)
            self._save_file()
            self._cache[provider] = key
            log.info("key stored in keys.json for %s", provider)
            return "file"

    def get(self, provider: str) -> str | None:
        with self._lock:
            if provider in self._cache:
                return self._cache[provider]
            if provider in self._file_keys:
                return self._file_keys[provider]
            if self.keyring and provider in self._index:
                r = self._st(["lookup", "service", SERVICE, "provider", provider])
                if r is not None and r.returncode == 0 and r.stdout.strip():
                    self._cache[provider] = r.stdout.strip()
                    return self._cache[provider]
            return None

    def delete(self, provider: str) -> bool:
        with self._lock:
            had = provider in self._file_keys or provider in self._index or provider in self._cache
            if self.keyring and provider in self._index:
                self._st(["clear", "service", SERVICE, "provider", provider])
            self._file_keys.pop(provider, None)
            self._index.discard(provider)
            self._cache.pop(provider, None)
            self._save_file()
            return had

    def providers(self) -> list[str]:
        """Names of providers with a key (never the keys)."""
        with self._lock:
            return sorted(set(self._file_keys) | self._index)

    def is_set(self, provider: str) -> bool:
        return provider in self.providers()
