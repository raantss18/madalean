"""Model catalogue: seed (assets/seed.json, from Tontolo), refreshed every 12 h from the keyless free providers,
from keyed providers whose key is set, and from Ollama when it runs on 127.0.0.1:11434. Ported from L Katta's
moteur.rs (`seed`, `refresh`, `estimate`, `is_text_chat`), plus Lean-specific quality and the native Anthropic API.

Keys are never stored here: the catalogue only says which models exist."""
from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from ._util import now, read_json, write_private

SEED_FILE = Path(__file__).with_name("assets") / "seed.json"
REFRESH_SECS = 12 * 3600
CATEGORIES = ("chat", "code", "math", "reasoning", "writing", "translation", "search", "agentic", "lean")
OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass
class Provider:
    id: str
    name: str
    base_url: str
    keyed: bool = False
    paid: bool = False
    api: str = "openai"            # openai (chat/completions) | anthropic (native Messages API)
    local: bool = False
    free_suffix: str | None = None
    key_url: str = ""


@dataclass
class Model:
    provider: str
    model_id: str
    name: str
    tools: bool = True
    vision: bool = False
    quality: dict[str, float] = field(default_factory=dict)
    local: bool = False
    paid: bool = False
    context: int = 0

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    def score(self, cat: str) -> float:
        q = self.quality
        if cat in q:
            return q[cat]
        if cat == "lean":
            return lean_quality(self)
        return q.get("chat", 0.4)


# Keyed providers (OpenAI-compatible unless `api` says otherwise). Base URLs are the only hosts a key may go to.
KEYED: list[Provider] = [
    Provider("anthropic", "Anthropic (Claude)", "https://api.anthropic.com/v1", True, True, "anthropic",
             key_url="https://console.anthropic.com/settings/keys"),
    Provider("gemini", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", True, False,
             key_url="https://aistudio.google.com/apikey"),
    Provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", True, False, free_suffix=":free",
             key_url="https://openrouter.ai/settings/keys"),
    Provider("groq", "Groq", "https://api.groq.com/openai/v1", True, False, key_url="https://console.groq.com/keys"),
    Provider("mistral", "Mistral AI", "https://api.mistral.ai/v1", True, False,
             key_url="https://console.mistral.ai/api-keys"),
    Provider("cerebras", "Cerebras", "https://api.cerebras.ai/v1", True, False, key_url="https://cloud.cerebras.ai"),
    Provider("openai", "OpenAI", "https://api.openai.com/v1", True, True, key_url="https://platform.openai.com/api-keys"),
    Provider("deepseek", "DeepSeek", "https://api.deepseek.com/v1", True, True,
             key_url="https://platform.deepseek.com/api_keys"),
]

# Claude models (claude-api skill, cached 2026-11-03). Paid: used only when chosen or with `paid_first`.
ANTHROPIC_MODELS = [
    ("claude-opus-5-5", "Claude Opus 5.5", {"chat": 0.95, "code": 0.97, "math": 0.96, "reasoning": 0.97,
                                            "writing": 0.95, "agentic": 0.97, "lean": 0.95}),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5", {"chat": 0.92, "code": 0.94, "math": 0.92, "reasoning": 0.93,
                                                "writing": 0.92, "agentic": 0.94, "lean": 0.9}),
    ("claude-haiku-5-5", "Claude Haiku 5.5", {"chat": 0.85, "code": 0.84, "math": 0.8, "reasoning": 0.8,
                                              "writing": 0.85, "agentic": 0.82, "lean": 0.72}),
]

# Families known to be good at formal mathematics / Lean (bonus on the `lean` category; explainable).
LEAN_FAMILIES: list[tuple[str, float, str]] = [
    (r"prover|goedel|kimina|deepseek-?math|leanabell|stepfun-?prover", 0.30, "trained for formal proofs"),
    (r"claude-(opus|sonnet|fable)", 0.15, "strong at Lean 4 / Mathlib"),
    (r"gemini.*pro|gpt-?[56]|o[34]-|grok-?[45]", 0.12, "strong reasoning model"),
    (r"deepseek|qwen-?3|qwen3|kimi|glm-?[45]|gpt-oss-120b|ling-|minimax|nemotron.*ultra", 0.08,
     "good at maths and code"),
]


def lean_bonus(m: Model) -> tuple[float, str]:
    n = f"{m.model_id} {m.name}".lower()
    for pat, bonus, why in LEAN_FAMILIES:
        if re.search(pat, n):
            return bonus, why
    return 0.0, ""


def lean_quality(m: Model) -> float:
    base = 0.6 * m.quality.get("math", m.quality.get("chat", 0.4)) + 0.4 * m.quality.get("code", m.quality.get("chat", 0.4))
    return min(1.0, base + lean_bonus(m)[0])


def is_text_chat(model_id: str) -> bool:
    low = model_id.lower()
    return not any(w in low for w in (
        "embed", "bge", "guard", "whisper", "diffusion", "tts", "flux", "lyria", "rerank", "moderation", "image",
        "veo", "dall-e", "audio", "realtime", "transcribe", "sora", "babbage", "davinci", "voxtral", "-vl", "vl-",
        "ocr", "nano-banana"))


def estimate(name: str, known: list[Model]) -> dict[str, float]:
    """Quality of a model absent from the seed: same family (first two name parts) else from its size (« 70b »)."""
    n = name.lower()
    stem = "-".join(re.split(r"[-:/._]", n)[:2])
    if len(stem) > 4:
        for m in known:
            k = "-".join(re.split(r"[-:/._]", m.name.lower())[:2])
            if k == stem and m.quality:
                return {c: v * 0.95 for c, v in m.quality.items()}
    mm = re.search(r"(\d+(?:\.\d+)?)\s*b\b", n)
    size = float(mm.group(1)) if mm else 8.0
    q = min(0.3 + 0.12 * math.log10(max(size, 1.0)), 0.72)
    return {c: q for c in CATEGORIES if c != "lean"}


@dataclass
class Catalogue:
    updated: float = 0.0
    providers: list[Provider] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)

    def provider(self, pid: str) -> Provider | None:
        return next((p for p in self.providers if p.id == pid), None)

    def to_json(self) -> str:
        return json.dumps({"updated": self.updated, "providers": [asdict(p) for p in self.providers],
                           "models": [asdict(m) for m in self.models]})

    @classmethod
    def from_json(cls, raw: dict) -> "Catalogue":
        return cls(raw.get("updated", 0.0), [Provider(**p) for p in raw.get("providers", [])],
                   [Model(**m) for m in raw.get("models", [])])


def seed() -> Catalogue:
    """Embedded fallback catalogue (keyless OpenAI-compatible providers only) + the keyed providers' static lists."""
    v = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    provs: list[Provider] = []
    for pid, p in (v.get("providers") or {}).items():
        base = (p.get("base_url") or "").rstrip("/")
        if not base or "huggingface.co" in base:
            continue
        provs.append(Provider(pid, p.get("name") or pid, base, key_url=p.get("key_url") or ""))
    ids = {p.id for p in provs}
    models = []
    for m in v.get("models") or []:
        if m.get("provider") not in ids or not m.get("is_free") or m.get("needs_key"):
            continue
        if m.get("output_modalities") and "text" not in m["output_modalities"]:
            continue
        models.append(Model(m["provider"], m["model_id"], m.get("name") or m["model_id"],
                            bool(m.get("supports_tools")), "image" in (m.get("input_modalities") or []),
                            {k: float(x) for k, x in (m.get("quality") or {}).items() if isinstance(x, (int, float))},
                            context=int(m.get("context_length") or 0)))
    return Catalogue(0.0, provs, models)


def keyed_static(pid: str) -> list[Model]:
    if pid == "anthropic":
        return [Model("anthropic", mid, name, True, True, dict(q), paid=True, context=1_000_000)
                for mid, name, q in ANTHROPIC_MODELS]
    return []


class CatalogueStore:
    """Current catalogue (refreshed copy if any, else the seed), refresh in the background."""

    def __init__(self, path: Path):
        self.path = path
        raw = read_json(path)
        cat = None
        if raw:
            try:
                cat = Catalogue.from_json(raw)
            except (TypeError, KeyError):
                cat = None
        self.cat = cat if cat and cat.models else seed()
        self._lock = asyncio.Lock()

    def save(self) -> None:
        try:
            write_private(self.path, self.cat.to_json())
        except OSError:
            pass

    def stale(self) -> bool:
        return now() - self.cat.updated > REFRESH_SECS

    def with_keys(self, has_key: Callable[[str], bool]) -> Catalogue:
        """The catalogue as the router sees it: keyed providers only when their key is set (static lists added)."""
        provs = [p for p in self.cat.providers if not p.keyed or has_key(p.id)]
        models = [m for m in self.cat.models if any(p.id == m.provider for p in provs)]
        for p in KEYED:
            if has_key(p.id):
                if not any(x.id == p.id for x in provs):
                    provs.append(p)
                for m in keyed_static(p.id):
                    if not any(x.key == m.key for x in models):
                        models.append(m)
        return Catalogue(self.cat.updated, provs, models)

    async def refresh(self, http, get_key: Callable[[str], str | None], online: bool = True) -> int:
        """Refresh from the providers (http: brain.net.Http). Returns the number of models found."""
        async with self._lock:
            base = seed()
            provs = list(base.providers)
            models: list[Model] = []
            seen: set[str] = set()

            def push(pid: str, mid: str, name: str, tools: bool, vision: bool, local: bool = False,
                     paid: bool = False, context: int = 0) -> None:
                if not mid or not is_text_chat(mid) or any(m.provider == pid and m.model_id == mid for m in models):
                    return
                known = next((m for m in base.models if m.provider == pid and m.model_id == mid), None)
                q = dict(known.quality) if known else estimate(name, base.models)
                models.append(Model(pid, mid, name, tools, vision, q, local, paid, context))

            async def fetch_free(p: Provider):
                return p, await http.get_json(f"{p.base_url}/models", mode="online", timeout=15)

            results = await asyncio.gather(*(fetch_free(p) for p in base.providers), return_exceptions=True) \
                if online else []
            for r in results:
                if isinstance(r, BaseException):
                    continue
                p, v = r
                if v is None:
                    continue
                seen.add(p.id)
                items = v if isinstance(v, list) else (v.get("data") or [])
                for m in items:
                    if not isinstance(m, dict):
                        continue
                    if p.id == "pollinations":
                        if m.get("tier") not in (None, "anonymous"):
                            continue
                        mid = m.get("name") or m.get("id") or ""
                        known = next((k for k in base.models if k.provider == p.id and k.model_id == mid), None)
                        push(p.id, mid, m.get("description") or mid, bool(m.get("tools", known.tools if known else False)),
                             bool(m.get("vision")))
                        continue
                    mid = m.get("id") or ""
                    if p.id == "kilo":
                        free = bool(m.get("isFree")) or mid.endswith(":free")
                    elif p.id == "llm7":
                        free = m.get("tier") != "pro" and m.get("model_type", "chat") == "chat"
                    else:
                        free = (m.get("context_length") is None) or (m.get("context_length") or 0) > 0
                    if not free:
                        continue
                    sp = m.get("supported_parameters")
                    tools = ("tools" in sp) if isinstance(sp, list) else bool(m.get("tools_calling", True))
                    vision = "image" in ((m.get("architecture") or {}).get("input_modalities") or [])
                    push(p.id, mid, m.get("name") or mid, tools, vision, context=int(m.get("context_length") or 0))
            for m in base.models:                       # unreachable providers keep their seed models
                if m.provider not in seen and not any(x.key == m.key for x in models):
                    models.append(m)
            for p in KEYED:
                key = get_key(p.id)
                if not key or not online:
                    continue
                if p.api == "anthropic":
                    v = await http.get_json(f"{p.base_url}/models", mode="online", timeout=15, provider=p.id, key=key)
                    found = {m["id"] for m in (v or {}).get("data", []) if isinstance(m, dict) and m.get("id")}
                    provs.append(p)
                    for m in keyed_static(p.id):
                        if not found or m.model_id in found:
                            models.append(m)
                    continue
                v = await http.get_json(f"{p.base_url}/models", mode="online", timeout=15, provider=p.id, key=key)
                if v is None:
                    continue
                provs.append(p)
                items = v if isinstance(v, list) else (v.get("data") or v.get("models") or [])
                for m in items:
                    if not isinstance(m, dict):
                        continue
                    mid = (m.get("id") or m.get("name") or "").removeprefix("models/")
                    if p.free_suffix and not mid.endswith(p.free_suffix):
                        continue
                    if p.id == "openrouter" and str((m.get("pricing") or {}).get("prompt", "0")) not in ("0", "0.0"):
                        continue
                    sp = m.get("supported_parameters")
                    tools = ("tools" in sp) if isinstance(sp, list) else True
                    vision = "image" in ((m.get("architecture") or {}).get("input_modalities") or [])
                    push(p.id, mid, m.get("name") or m.get("display_name") or mid, tools, vision, paid=p.paid,
                         context=int(m.get("context_length") or 0))
            tags = await http.get_json(f"{OLLAMA_URL}/api/tags", mode="local", timeout=3)
            if tags:
                provs.append(Provider("ollama", "Ollama (local)", f"{OLLAMA_URL}/v1", local=True))
                for m in tags.get("models") or []:
                    mid = m.get("name") or ""
                    push("ollama", mid, f"{mid} (Ollama)", True, False, local=True)
            if not models:
                return 0
            self.cat = Catalogue(now(), provs, models)
            self.save()
            return len(models)
