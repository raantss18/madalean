"""Brain settings (the `settings` dict given to create_brain; exposed by the server in PATCH /settings).
Every key is optional; see docs/BRAIN.md for the user-facing meaning."""
from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    "mode": "auto",                 # ceiling: "local" forces every call to stay on this machine
    "paid_first": False,            # paid models (Anthropic, OpenAI…) tried first; otherwise only when chosen
    "models": {},                   # {role: "provider:model_id"} preferred model per role ("auto" = router)
    "max_parallel": 3,              # simultaneous online requests
    "max_chain": 5,                 # online models tried per answer before the local fallback
    "agent_max_steps": 24,
    "agent_max_seconds": 900,
    "agent_max_tokens": 600_000,    # generated + uncached prompt tokens per agent run
    "online_search": True,          # lean_search_online tool (LeanSearch, Loogle) when mode != local
    "refresh_catalogue": True,      # refresh the free-model catalogue every 12 h (never in local mode)
    "ollama": True,                 # use models of a running Ollama (127.0.0.1:11434)
    "anthropic_thinking": True,     # adaptive thinking (summarised, streamed as `thinking` chunks)
    "anthropic_effort": {},         # {role: low|medium|high|xhigh|max}; defaults below
    "gemini_effort": {},            # {role: minimal|low|medium|high} (Gemini reasoning_effort); engine.GEMINI_EFFORT
    "anthropic_fallbacks": True,    # server-side refusal fallback (beta) on the models that accept it
    "local_native_tools": False,    # local llama-server: OpenAI tools (needs --jinja) instead of the text protocol
    "stall_online": 90,             # seconds without data before an online stream is abandoned
    "stall_local": 180,
    "claude_reinforce": True,       # Claude joins the proof tournament's final round when the free models failed
    "claude_model": "auto",         # which Claude for that round ("auto" = best for the role)
    "claude_cap_proof_usd": 1.0,    # spending cap per proof (USD, list prices, real usage) — every paid Claude call
    "claude_cap_month_usd": 20.0,   # spending cap per calendar month (USD)
    "embeddings": True,             # semantic re-ranking with an Ollama embedding model when installed
}

EFFORT = {"prove": "high", "formalize": "high", "explain": "medium", "assistant": "medium", "understand": "low",
          "route": "low"}
MAX_TOKENS = {"prove": 64000, "formalize": 16000, "explain": 16000, "assistant": 16000, "understand": 4000,
              "route": 2000}


def merged(settings: dict | None) -> dict[str, Any]:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k, v in (settings or {}).items():
        if k in out or k.startswith("_"):
            out[k] = v
    return out
