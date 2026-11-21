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
    est: str = ""                   # how the quality was estimated when the model is not in the seed (family name)
    price: list[float] = field(default_factory=list)   # [input, output] USD per million tokens when the provider says

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
    # Hugging Face Inference Providers (session S-T, user decision 2026-11-22): OpenAI-compatible router; only the
    # formal-maths specialists below are listed (never the router's general catalogue). Paid (HF credits, provider
    # price without markup); the token also goes to huggingface.co for the identity check (engine.HF_HUB).
    Provider("huggingface", "Hugging Face (Inference Providers)", "https://router.huggingface.co/v1", True, True,
             key_url="https://huggingface.co/settings/tokens"),
]

# Formal-maths specialists looked up on the Hub at each refresh (public API, no key): a model is listed only with a
# provider whose mapping says « live » (GET https://huggingface.co/api/models/<repo>?expand[]=inferenceProviderMapping,
# checked 2026-11-22: both provers live on featherless-ai, no provider for the formalizers). The router model id is
# « <repo>:<provider> » (provider pinned: the router never swaps it for another one).
HF_HUB = "https://huggingface.co"
HF_SPECIALISTS: list[tuple[str, str, str]] = [        # (repo, role, display name)
    ("Goedel-LM/Goedel-Prover-V2-32B", "prove", "Goedel-Prover-V2-32B"),
    ("Goedel-LM/Goedel-Prover-V2-8B", "prove", "Goedel-Prover-V2-8B"),
    ("Goedel-LM/Goedel-Formalizer-V2-32B", "formalize", "Goedel-Formalizer-V2-32B"),
    ("Goedel-LM/Goedel-Formalizer-V2-8B", "formalize", "Goedel-Formalizer-V2-8B"),
]
HF_CONTEXT = 40960      # Qwen3 base of Goedel-Prover-V2 (max_position_embeddings); the provider may allow less


def hf_live_providers(info) -> list[str]:
    """Providers whose mapping is « live » for chat, from the Hub's model info (the mapping is a dict keyed by
    provider for one model, a list of {provider, status…} in listings)."""
    mp = (info or {}).get("inferenceProviderMapping") if isinstance(info, dict) else None
    items = [{"provider": k, **v} for k, v in mp.items() if isinstance(v, dict)] if isinstance(mp, dict) \
        else [x for x in (mp or []) if isinstance(x, dict)]
    return [str(x["provider"]) for x in items if x.get("provider") and x.get("status") == "live"
            and x.get("task", "conversational") in ("conversational", "text-generation")]


def hf_specialist(model_id: str) -> tuple[str, str, str] | None:
    repo = model_id.rsplit(":", 1)[0]
    return next((x for x in HF_SPECIALISTS if x[0] == repo), None)

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
    (r"deepseek|qwen-?3|qwen3|kimi|glm-?[45]|gpt-oss-120b|ling-|minimax|nemotron.*ultra|magistral|devstral", 0.08,
     "good at maths and code"),
]


def _q(chat: float, code: float, math_: float, reasoning: float | None = None, agentic: float | None = None) -> dict:
    r = reasoning if reasoning is not None else math_
    return {"chat": chat, "code": code, "math": math_, "reasoning": r, "writing": chat, "translation": chat,
            "agentic": agentic if agentic is not None else (code + r) / 2, "search": chat}


# Quality of the keyed providers' families (session S-M). The seed only knows the keyless providers, so without
# this every Gemini / Mistral model got the size-based default (0.41 for an unknown size) and a small open model
# with a size in its name (« gemma-4-31b-it », « ministral-14b ») outranked Gemini Pro or Mistral Large. Values are
# on the seed's scale (top free models ≈ 0.55–0.85, Claude ≈ 0.95): an estimate from public benchmarks and model
# tiers, corrected on this machine by the observed reliability and the leaderboard (docs/BRAIN.md §3). First match
# wins: specific patterns (« flash-lite ») before general ones (« flash »). Matched on the lower-cased model id
# (« models/ » removed) — ids checked against the providers' documented model lists, to be confirmed with the user's
# key (GET /v1beta/openai/models, GET /v1/models).
FAMILIES: list[tuple[str, dict, str]] = [
    # Google Gemini (generativelanguage.googleapis.com)
    (r"gemini-3(\.\d+)?-pro|gemini-pro-latest", _q(0.86, 0.86, 0.88, 0.88, 0.84), "Gemini 3 Pro family"),
    (r"gemini-3(\.\d+)?-flash-lite|gemini-flash-lite-latest", _q(0.62, 0.6, 0.62), "Gemini Flash-Lite family"),
    (r"gemini-3(\.\d+)?-flash|gemini-flash-latest", _q(0.78, 0.78, 0.8, 0.8, 0.76), "Gemini 3 Flash family"),
    (r"gemini-2\.5-pro", _q(0.8, 0.8, 0.82, 0.82, 0.76), "Gemini 2.5 Pro family"),
    (r"gemini-2\.5-flash-lite", _q(0.55, 0.52, 0.55), "Gemini 2.5 Flash-Lite family"),
    (r"gemini-2\.5-flash", _q(0.7, 0.68, 0.72, 0.72, 0.66), "Gemini 2.5 Flash family"),
    (r"gemini-2\.0-flash-lite", _q(0.4, 0.38, 0.38), "Gemini 2.0 Flash-Lite family"),
    (r"gemini-2\.0-flash", _q(0.5, 0.48, 0.48), "Gemini 2.0 Flash family"),
    (r"gemini-1\.5|gemini-1\.0|gemini-pro$", _q(0.3, 0.3, 0.28), "older Gemini"),
    (r"gemma-?4", _q(0.42, 0.4, 0.4), "Gemma 4 (open model, below Gemini)"),
    (r"gemma-?3n", _q(0.18, 0.15, 0.15), "Gemma 3n (small open model)"),
    (r"gemma", _q(0.28, 0.26, 0.26), "Gemma (open model, below Gemini)"),
    (r"learnlm", _q(0.4, 0.3, 0.35), "LearnLM"),
    # Mistral AI (api.mistral.ai)
    (r"magistral-medium", _q(0.68, 0.64, 0.76, 0.76, 0.64), "Magistral Medium (reasoning)"),
    (r"magistral-small", _q(0.52, 0.5, 0.6, 0.6, 0.48), "Magistral Small (reasoning)"),
    (r"mistral-large", _q(0.68, 0.68, 0.64, 0.66, 0.68), "Mistral Large family"),
    (r"devstral-medium|devstral-2|devstral-latest", _q(0.6, 0.78, 0.52, 0.6, 0.74), "Devstral (code agent)"),
    (r"devstral", _q(0.5, 0.64, 0.42, 0.48, 0.6), "Devstral Small (code agent)"),
    (r"mistral-medium", _q(0.64, 0.64, 0.6, 0.62, 0.62), "Mistral Medium family"),
    (r"codestral", _q(0.45, 0.66, 0.4), "Codestral (code)"),
    (r"pixtral-large", _q(0.55, 0.52, 0.5), "Pixtral Large"),
    (r"mistral-small", _q(0.5, 0.5, 0.46), "Mistral Small family"),
    (r"ministral-14b", _q(0.42, 0.42, 0.4), "Ministral 14B"),
    (r"ministral-8b|pixtral-12b", _q(0.32, 0.32, 0.3), "Ministral 8B"),
    (r"ministral-3b", _q(0.22, 0.22, 0.2), "Ministral 3B"),
    (r"open-mistral-nemo|mistral-tiny|open-mistral-7b", _q(0.18, 0.18, 0.15), "small Mistral"),
    # other keyed providers' flagship families (same scale)
    (r"gpt-5(\.\d+)?-(mini)", _q(0.72, 0.74, 0.76), "GPT-5 mini"),
    (r"gpt-5(\.\d+)?-(nano)", _q(0.5, 0.5, 0.52), "GPT-5 nano"),
    (r"gpt-5", _q(0.86, 0.88, 0.9, 0.9, 0.86), "GPT-5 family"),
    (r"deepseek-reasoner", _q(0.74, 0.76, 0.82, 0.82, 0.7), "DeepSeek reasoner"),
    (r"deepseek-chat", _q(0.72, 0.78, 0.7, 0.7, 0.72), "DeepSeek chat"),
]
_FAMILY_RX = [(re.compile(p), q, why) for p, q, why in FAMILIES]


def family_quality(model_id: str) -> tuple[dict[str, float], str] | None:
    mid = model_id.lower().removeprefix("models/").split("/")[-1]
    for rx, q, why in _FAMILY_RX:
        if rx.search(mid):
            return dict(q), why
    return None


# Cheap, reliable model of each keyed provider for the key test (one tiny call): stable ids first.
TEST_MODELS: dict[str, list[str]] = {
    "gemini": [r"^gemini-2\.5-flash-lite$", r"^gemini-flash-lite-latest$", r"^gemini-2\.5-flash$",
               r"^gemini-flash-latest$", r"^gemini-2\.0-flash$", r"^gemini-.*flash"],
    "mistral": [r"^mistral-small-latest$", r"^ministral-8b-latest$", r"^mistral-small", r"^ministral",
                r"^mistral-medium"],
    "anthropic": [r"^claude-haiku"],
    "groq": [r"llama-3\.1-8b-instant", r"instant", r"8b"],
    "cerebras": [r"llama3?\.1-8b", r"8b"],
    "openai": [r"gpt-5(\.\d+)?-nano", r"mini"],
    "deepseek": [r"^deepseek-chat$"],
    "openrouter": [r":free$"],
}
_CHEAP = re.compile(r"flash|mini|small|lite|haiku|nano|instant|8b", re.I)
_UNSTABLE = re.compile(r"preview|exp|beta|alpha|-\d{2}-\d{2}$|gemma", re.I)


def key_test_model(models: list["Model"], provider: str) -> tuple["Model", str] | None:
    """The model a key test should call: the provider's cheap, reliable model (not its strongest: the test only
    checks that the key works). Returns (model, reason)."""
    mine = [m for m in models if m.provider == provider]
    if not mine:
        return None
    for pat in TEST_MODELS.get(provider, []):
        rx = re.compile(pat, re.I)
        hit = sorted((m for m in mine if rx.search(m.model_id)), key=lambda m: m.model_id)
        if hit:
            return hit[0], "cheap, stable model of this provider"
    stable = [m for m in mine if not _UNSTABLE.search(m.model_id)] or mine
    stable.sort(key=lambda m: (not _CHEAP.search(m.model_id), m.model_id))
    return stable[0], "first stable model of this provider"



# Models that must not prove, formalise or route (S-M, seen in real runs: « ovh:Olala-v1.0-summarise » got the
# prove role twice and its Lean never compiled): task-specific families, and tiny models (< 7 B parameters).
_UNFIT = re.compile(r"summar|embed|rerank|guard|moderat|classif|tts|whisper|transcri|caption|ocr|vision-only|"
                    r"-vl\b|\bvl-|translat(e|or|ion)\b|\bmini-?lm", re.I)
_SMALL = re.compile(r"nano\b|tiny|\be[1-4]b\b", re.I)
_SIZE = re.compile(r"(?<![a-z])(\d+(?:\.\d+)?)\s*b\b", re.I)
TINY_B = 7.0


def unfit_reason(m: Model) -> str:
    """Why `m` should not do formal work (prove / formalize / route), or "" when it may."""
    if m.provider == "local":
        return ""                                  # Madalean's own model for the role (Goedel / Qwen, 8 B)
    n = f"{m.model_id} {m.name}".lower()
    hit = _UNFIT.search(n)
    if hit:
        return f"task-specific model ({hit.group(0)})"
    small = _SMALL.search(n)
    if small:
        return f"small model ({small.group(0)})"
    sizes = [float(x) for x in _SIZE.findall(n.replace("a3b", "").replace("a4b", ""))]
    if sizes and max(sizes) < TINY_B and not re.search(r"\bx\d|moe", n):
        return f"too small ({max(sizes):g} B)"
    return ""


def lean_bonus(m: Model) -> tuple[float, str]:
    n = f"{m.model_id} {m.name}".lower()
    for pat, bonus, why in LEAN_FAMILIES:
        if re.search(pat, n):
            return bonus, why
    return 0.0, ""


def lean_quality(m: Model) -> float:
    base = 0.6 * m.quality.get("math", m.quality.get("chat", 0.4)) + 0.4 * m.quality.get("code", m.quality.get("chat", 0.4))
    return min(1.0, base + lean_bonus(m)[0])


_NOT_CHAT_WORD = re.compile(r"(^|[-_./ ])(live|aqa|genie|imagen|antigravity)([-_./ ]|$)", re.I)


def is_text_chat(model_id: str) -> bool:
    """A plain text chat / generateContent model. Live API (bidiGenerateContent only), native audio, TTS, image,
    video, embeddings, computer use, robotics, AQA, agents (Deep Research, Antigravity), world models (Genie) are
    not — for every role (2026-11-21: `gemini-3.1-flash-live-preview` was picked by the tournament, HTTP 400)."""
    low = model_id.lower()
    if _NOT_CHAT_WORD.search(low):
        return False
    return not any(w in low for w in (
        "embed", "bge", "guard", "whisper", "diffusion", "tts", "flux", "lyria", "rerank", "moderation", "image",
        "veo", "dall-e", "audio", "realtime", "transcribe", "sora", "babbage", "davinci", "voxtral", "-vl", "vl-",
        "ocr", "nano-banana", "computer-use", "robotics", "-live", "gemini-live", "aqa", "deep-research",
        "bidi", "speech"))


def alias_id(m: "Model") -> str:
    """Identity of the underlying model: providers such as Mistral list every alias (`mistral-medium-latest`,
    `mistral-medium-2604`, `mistral-medium-3`…) with the canonical name; the catalogue name is then the identity."""
    name = (m.name or "").strip().lower()
    if name and name != m.model_id.lower() and re.fullmatch(r"[\w.:/-]+", name):
        return f"{m.provider}:{name}"
    return f"{m.provider}:{m.model_id.lower()}"


def dedupe_aliases(models: list["Model"]) -> list["Model"]:
    """One entry per underlying model (the one whose id IS the canonical name first, else a dated id, else the
    first listed)."""
    groups: dict[str, list[Model]] = {}
    order: list[str] = []
    for m in models:
        k = alias_id(m)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(m)

    def rank(m: Model) -> tuple:
        return (m.model_id.lower() != (m.name or "").lower(), "latest" in m.model_id.lower(), 0)
    keep = {id(min(g, key=rank)) for g in groups.values()}
    return [m for m in models if id(m) in keep]


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


_SEED_KEYS: set[str] | None = None


def _seed_keys() -> set[str]:
    global _SEED_KEYS
    if _SEED_KEYS is None:
        _SEED_KEYS = {m.key for m in seed().models}
    return _SEED_KEYS


def _with_family(m: Model) -> Model:
    """A catalogue saved before the family table (or by an older version) still holds the size-based guess for
    keyed models: re-estimate them on the fly (models known to the seed or local ones keep their quality)."""
    if m.local or m.paid or m.est or m.key in _seed_keys():
        return m
    fam = family_quality(m.model_id)
    if fam is None:
        return m
    return Model(m.provider, m.model_id, m.name, m.tools, m.vision, fam[0], m.local, m.paid, m.context, fam[1])


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


def hf_model(repo: str, provider: str, name: str, price: list[float] | None = None) -> Model:
    q = {"chat": 0.2, "writing": 0.1, "translation": 0.1, "search": 0.1, "agentic": 0.1, "code": 0.6, "math": 0.8,
         "reasoning": 0.8, "lean": 0.97 if "32B" in repo else 0.9}
    return Model("huggingface", f"{repo}:{provider}", f"{name} ({provider}, Hugging Face)", False, False, q,
                 paid=True, context=HF_CONTEXT, est="Goedel-Prover-V2 (formal proofs)" if "Prover" in repo
                 else "Goedel-Formalizer-V2", price=list(price or []))


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
        # a catalogue saved by an older version may still hold non-chat models and aliases: filter on every read
        models = dedupe_aliases([_with_family(m) for m in self.cat.models if any(p.id == m.provider for p in provs)
                                 and (m.local or is_text_chat(m.model_id))])
        for p in KEYED:
            if has_key(p.id):
                if not any(x.id == p.id for x in provs):
                    provs.append(p)
                for m in keyed_static(p.id):
                    if not any(x.key == m.key for x in models):
                        models.append(m)
        return Catalogue(self.cat.updated, provs, models)

    async def refresh(self, http, get_key: Callable[[str], str | None], online: bool = True,
                      hf_urls: tuple[str, str] | None = None) -> int:
        """Refresh from the providers (http: brain.net.Http). Returns the number of models found. `hf_urls`: (Hub,
        router) base URLs (tests only)."""
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
                fam = None if known or local else family_quality(mid)
                q = dict(known.quality) if known else (fam[0] if fam else estimate(name, base.models))
                models.append(Model(pid, mid, name, tools, vision, q, local, paid, context, fam[1] if fam else ""))

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
            if online:
                hf = await refresh_hf(http, *(hf_urls or ()))
                if hf:
                    provs.append(next(p for p in KEYED if p.id == "huggingface"))
                    models.extend(hf)
            for p in KEYED:
                key = get_key(p.id)
                if not key or not online or p.id == "huggingface":
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


async def refresh_hf(http, hub: str = HF_HUB, router: str = "https://router.huggingface.co/v1") -> list[Model]:
    """The Goedel specialists that have a live provider now (public Hub API, sent WITHOUT the token), with the
    router's price when it publishes one (GET /v1/models/<repo>: `providers[].pricing` in USD per million tokens —
    absent for featherless-ai on 2026-11-22, spend.HF_ESTIMATE is then used)."""
    async def one(repo: str, role: str, name: str) -> list[Model]:
        info = await http.get_json(f"{hub}/api/models/{repo}", mode="online", timeout=10,
                                   params={"expand[]": "inferenceProviderMapping"})
        live = hf_live_providers(info)
        if not live:
            return []
        prices: dict[str, list[float]] = {}
        r = await http.get_json(f"{router}/models/{repo}", mode="online", timeout=10)
        for pv in ((r or {}).get("data") or {}).get("providers") or [] if isinstance(r, dict) else []:
            pr = pv.get("pricing") if isinstance(pv, dict) else None
            if isinstance(pr, dict) and isinstance(pr.get("input"), (int, float)) and isinstance(pr.get("output"), (int, float)):
                prices[str(pv.get("provider"))] = [float(pr["input"]), float(pr["output"])]
        return [hf_model(repo, prov, name, prices.get(prov)) for prov in live]
    res = await asyncio.gather(*(one(*x) for x in HF_SPECIALISTS), return_exceptions=True)
    return [m for r in res if not isinstance(r, BaseException) for m in r]
