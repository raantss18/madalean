"""Structured logging to <config>/logs/server.log (rotated), with secrets redacted from every record."""
from __future__ import annotations

import json
import logging
import logging.handlers
import re
import time
from pathlib import Path

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(authorization:\s*(?:bearer|token)\s+)[^\s\"']+"), r"\1***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1***"),
    (re.compile(r"(?i)((?:token|key|api_key|apikey|password|secret)[\"']?\s*[:=]\s*[\"']?)[^\s\"'&,}]+"), r"\1***"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "sk-***"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "AIza***"),
    (re.compile(r"(madalean_token=)[^;\s]+"), r"\1***"),
]


def redact(text: str) -> str:
    for pat, rep in _SECRET_PATTERNS:
        text = pat.sub(rep, text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # noqa: BLE001 (a log line must never crash the server)
            pass
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {"t": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)), "lvl": record.levelname,
             "log": record.name, "msg": record.getMessage()}
        extra = getattr(record, "data", None)
        if isinstance(extra, dict):
            d["data"] = json.loads(redact(json.dumps(extra, default=str)))
        if record.exc_info:
            d["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(d, ensure_ascii=False)


def setup(log_dir: Path, level: int = logging.INFO, console: bool = True) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("madalean")
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.handlers.RotatingFileHandler(log_dir / "server.log", maxBytes=2_000_000, backupCount=5,
                                              encoding="utf-8")
    fh.setFormatter(JsonFormatter())
    fh.addFilter(RedactFilter())
    root.addHandler(fh)
    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
        ch.addFilter(RedactFilter())
        root.addHandler(ch)
    root.propagate = False
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


def get(name: str) -> logging.Logger:
    return logging.getLogger("madalean." + name)
