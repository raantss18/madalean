"""Every file the server writes, derived from one config directory (``--config-dir``) and one cache directory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class Paths:
    config: Path
    cache: Path

    @classmethod
    def default(cls) -> "Paths":
        return cls(config.CONFIG_DIR, config.CACHE_DIR)

    @property
    def settings(self) -> Path:
        return self.config / "settings.json"

    @property
    def dossiers(self) -> Path:
        return self.config / "dossiers"

    @property
    def projects(self) -> Path:
        return self.config / "projects"

    @property
    def library(self) -> Path:
        return self.config / "library.json"

    @property
    def jobs(self) -> Path:
        return self.config / "jobs"

    @property
    def devices(self) -> Path:
        return self.config / "devices.json"

    @property
    def keys(self) -> Path:
        return self.config / "keys.json"

    @property
    def logs(self) -> Path:
        return self.config / "logs"

    @property
    def llama_pid(self) -> Path:
        return self.config / "llama-server.pid"

    @property
    def lock(self) -> Path:
        return self.config / "server.lock"

    @property
    def server_info(self) -> Path:
        """Ports of the running server (read by `madalean pair` / `status`)."""
        return self.config / "server.json"

    @property
    def migrated_marker(self) -> Path:
        return self.config / ".migrated-from-1.x"

    @property
    def tmp(self) -> Path:
        return self.cache / "tmp"

    @property
    def exports(self) -> Path:
        return self.cache / "exports"

    def ensure(self) -> None:
        for d in (self.config, self.dossiers, self.projects, self.jobs, self.logs, self.cache, self.tmp, self.exports):
            d.mkdir(parents=True, exist_ok=True)
        try:
            self.config.chmod(0o700)
        except OSError:
            pass
