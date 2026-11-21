"""Paths and persistent settings (atomic JSON in ~/.config/madalean)."""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

HOME = Path.home()
STATION_DIR = Path(os.environ.get("MADALEAN_DIR", Path(__file__).resolve().parents[1]))  # repo root
CONFIG_DIR = Path(os.environ.get("MADALEAN_CONFIG_DIR", HOME / ".config" / "madalean"))
MODELS_DIR = Path(os.environ.get("MADALEAN_MODELS_DIR", HOME / "models"))
CACHE_DIR = Path(os.environ.get("MADALEAN_CACHE_DIR", HOME / ".cache" / "madalean"))
LLAMA_BIN_DIR = Path(os.environ.get("MADALEAN_LLAMA_BIN", STATION_DIR / "vendor" / "llama.cpp" / "build" / "bin"))
WORKSPACES_DIR = STATION_DIR / "workspaces"
ELAN_BIN = HOME / ".elan" / "bin"

LEGACY_CONFIG_DIR = HOME / ".config" / "lean-ai-station"   # 1.x data, copied on first start (never modified)
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SESSION_FILE = CONFIG_DIR / "session.json"
SERVER_PID_FILE = CONFIG_DIR / "llama-server.pid"
RUN_LOCK_FILE = CONFIG_DIR / "running.lock"
LOG_DIR = CONFIG_DIR / "logs"

DEFAULT_MODEL_NAME = "Goedel-Prover-V2-8B.Q4_K_M.gguf"


@dataclass
class ServerSettings:
    port: int = 8765
    ctx_size: int = 24576         # BENCH.md: answers reach ~16k tokens; 24k + q8_0 KV = 7.0 GiB VRAM
    gpu_layers: int = 99          # 99 = everything on GPU
    batch_size: int = 2048
    ubatch_size: int = 512
    kv_type: str = "q8_0"          # f16 | q8_0 | q4_0
    flash_attn: bool = True
    threads: int = 8


@dataclass
class SamplingSettings:
    temperature: float = 1.0       # Goedel-Prover-V2 inference default
    top_p: float = 0.95
    max_tokens: int = 16384


@dataclass
class Settings:
    wizard_done: bool = False
    offline: bool = True           # network hard-blocked in-app by default
    model_path: str = ""
    workspace: str = ""
    prove_attempts: int = 8
    translate_attempts: int = 3
    pause_after_translation: bool = False   # user choice (v1.1): fully automatic chain by default
    profile: str = ""                       # « mémoire » read by the translator and the explainer
    language: str = "fr"
    check_updates: bool = True              # weekly Lean/Mathlib + Goedel check (GitHub, Hugging Face only)
    overleaf_url: str = "http://127.0.0.1"
    compile_timeout_s: int = 180
    autoload_model: bool = True
    # ---- Madalean 2.0
    mode: str = "auto"                      # user choice 2026-11-21: online by default; local | auto | online
    prove_strategy: str = "auto"            # goedel | agent | auto
    prefer: dict = field(default_factory=dict)   # role -> model key forced by the user ("provider:model_id")
    statement_notes: bool = True            # gloss of the Lean statement for learners (role explain)
    informal_proof: bool = True             # natural-language proof (role explain)
    agent_max_steps: int = 24
    agent_max_seconds: int = 900
    host_name: str = ""                     # name shown to paired devices (default: hostname)
    # host-only switches (can only be changed from the local listener)
    lan_listener: bool = False
    lan_port: int = 11502
    remote_jupyter: bool = False
    agent_exec: bool = False
    experiments_auto: bool = False          # run conjecture experiments (Sage/Python) without asking first
    experiments_remote: bool = False        # paired devices may approve/run experiments (code runs on the host)
    updates_auto: bool = True               # install safe updates automatically at a quiet moment (else: ask first)
    server: ServerSettings = field(default_factory=ServerSettings)
    sampling: SamplingSettings = field(default_factory=SamplingSettings)


def _from_dict(cls, data: dict):
    kwargs = {}
    names = {f.name: f for f in fields(cls)}
    for k, v in (data or {}).items():
        if k not in names:
            continue
        default = getattr(cls(), k)
        if hasattr(default, "__dataclass_fields__") and isinstance(v, dict):
            kwargs[k] = _from_dict(type(default), v)
        elif isinstance(default, bool):
            kwargs[k] = bool(v)
        elif isinstance(default, dict):
            if isinstance(v, dict):
                kwargs[k] = {str(a): b for a, b in v.items() if isinstance(b, (str, int, float, bool))}
        elif isinstance(default, list):
            if isinstance(v, list):
                kwargs[k] = [x for x in v if isinstance(x, (str, int, float))]
        elif isinstance(default, (int, float, str)) and isinstance(v, (int, float, str)):
            try:
                kwargs[k] = type(default)(v)
            except (TypeError, ValueError):
                pass
    return cls(**kwargs)


def atomic_write_text(path: Path, text: str) -> None:
    """Write via temp file + fsync + rename so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path) -> tuple[dict, bool]:
    """Return (data, was_corrupt). A corrupt file is kept aside as *.corrupt-<ts>."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), False
    except FileNotFoundError:
        return {}, False
    except (OSError, ValueError):
        try:
            path.rename(path.with_name(f"{path.name}.corrupt-{int(time.time())}"))
        except OSError:
            pass
        return {}, True


def load_settings() -> tuple[Settings, bool]:
    data, corrupt = read_json(SETTINGS_FILE)
    return _from_dict(Settings, data), corrupt


def save_settings(s: Settings) -> None:
    atomic_write_text(SETTINGS_FILE, json.dumps(asdict(s), indent=2, ensure_ascii=False))


def load_session() -> dict:
    return read_json(SESSION_FILE)[0]


def save_session(data: dict) -> None:
    atomic_write_text(SESSION_FILE, json.dumps(data, indent=1, ensure_ascii=False))


def tilde(p: Path | str) -> str:
    """Display form of a path: ~/… instead of the full home directory."""
    s = str(p)
    h = str(HOME)
    return "~" + s[len(h):] if s == h or s.startswith(h + "/") else s


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, LOG_DIR, CACHE_DIR, CACHE_DIR / "tmp", MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)
