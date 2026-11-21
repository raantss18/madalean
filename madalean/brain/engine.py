"""The model engine: implements `madalean.brain.api.Brain` (complete, run_agent, candidates, status, refresh)."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .. import leancheck
from .api import (AgentResult, BrainError, Completion, LocalRuntime, Mode, ModelRef, OnChunk, Role, ToolSpec)
from .catalogue import KEYED, OLLAMA_URL, CatalogueStore, Model, Provider
from .guards import FIRST_BYTE_LOCAL, FIRST_BYTE_ONLINE, FIRST_BYTE_REASONING, gemini_thinking, reasoning_model
from .net import CALL_MODE, Http, is_loopback_host
from .providers import anthropic as anthropic_api
from .providers import openai_compat
from .providers.base import ProviderError, StreamResult, emit
from .leaderboard import Leaderboard
from . import spend
from .router import Candidate, compose, rank, score_model
from .settings import EFFORT, MAX_TOKENS, merged
from .state import States

log = logging.getLogger("madalean.brain")
LOST_TIME_LIMIT = 240.0          # seconds lost in failures before giving up on the remaining online models


def ref_of(m: Model, cat=None) -> ModelRef:
    return ModelRef(m.provider, m.model_id, m.name, m.local, m.paid)


# Gemini thinking per role on the OpenAI-compatible API (`reasoning_effort`: minimal | low | medium | high): enough for
# Lean work, short enough to answer before the first-byte timeout
GEMINI_EFFORT = {"prove": "medium", "formalize": "medium", "explain": "low", "assistant": "low", "understand": "low",
                 "route": "low"}
UNUSABLE_PAUSE = 120 * 86400.0          # ≈ 4 months
_UNUSABLE = re.compile(r"only supports? (real-time|bidi|bidirectional)|bidiGenerateContent|live api|"
                       r"not supported for (generatecontent|chat|this (method|endpoint))|"
                       r"(is not|isn't) a (chat|text generation) model|does not support (chat|generatecontent|"
                       r"text generation)|only supports? (embedding|audio|image|speech|tts)", re.I)


def unusable_model(status: int, message: str) -> bool:
    """A 400/404 that says the MODEL cannot be used for text chat at all (not a bad parameter)."""
    return status in (400, 404) and bool(_UNUSABLE.search(message or ""))


class MadaleanBrain:
    def __init__(self, config_dir: Path, local: LocalRuntime | None, get_key: Callable[[str], str | None],
                 settings: dict | None = None):
        self.config_dir = Path(config_dir)
        self.local = local
        self._get_key = get_key
        self.settings = merged(settings)
        self.endpoints: dict[str, str] = dict(self.settings.get("_endpoints") or {})   # tests / development only
        self.http = Http(self._key_hosts())
        self.store = CatalogueStore(self.config_dir / "brain-catalogue.json")
        self.states = States(self.config_dir / "brain-state.json")
        self.leaderboard = Leaderboard(self.config_dir / "brain-leaderboard.json")
        self.ledger = spend.Ledger(self.config_dir / "brain-spend.json")
        self._sem: asyncio.Semaphore | None = None
        self._refresh_task: asyncio.Task | None = None
        self.last_error: dict[str, str] = {}
        self._first_done = False

    # ------------------------------------------------------------------ settings / keys
    def update_settings(self, settings: dict) -> None:
        """Apply new settings (server PATCH /settings)."""
        self.settings = merged({**self.settings, **settings})
        self._sem = None

    def _key_hosts(self) -> dict[str, str]:
        return {p.id: (urlsplit(self.endpoints.get(p.id, p.base_url)).hostname or "").lower() for p in KEYED}

    def key(self, provider: str) -> str | None:
        if not any(p.id == provider for p in KEYED):
            return None
        try:
            k = self._get_key(provider)
        except Exception:  # noqa: BLE001
            return None
        return k.strip() if isinstance(k, str) and k.strip() else None

    def base_url(self, p: Provider) -> str:
        return self.endpoints.get(p.id, p.base_url)

    def effective_mode(self, mode: str) -> str:
        if "local" in (mode, self.settings.get("mode")):
            return "local"
        return mode if mode in ("auto", "online") else "auto"

    def sem(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(max(1, int(self.settings.get("max_parallel") or 3)))
        return self._sem

    # ------------------------------------------------------------------ catalogue
    def _view(self):
        cat = self.store.with_keys(lambda pid: self.key(pid) is not None)
        if not self.settings.get("ollama", True):
            cat.models = [m for m in cat.models if m.provider != "ollama"]
        for pid, url in self.endpoints.items():          # test endpoints may be keyless fakes
            if not any(p.id == pid for p in cat.providers) and pid in ("ollama",):
                cat.providers.append(Provider(pid, pid, url, local=True))
        return cat

    def _local_models(self, role: str) -> list[Model]:
        if self.local is None:
            return []
        try:
            r = self.local.model_for(role)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            r = None
        if r is None:
            return []
        q = {"lean": 0.8, "math": 0.7, "chat": 0.5, "writing": 0.5, "reasoning": 0.6, "code": 0.6}
        return [Model("local", r.model_id, r.name or r.model_id, tools=bool(self.settings.get("local_native_tools")),
                      quality=q, local=True)]

    def _rank(self, role: str, mode: str, prefer: str | None, messages: list[dict] | None, need_tools: bool,
              domain: str | None) -> list[Candidate]:
        from ..i18n import language
        mode = self.effective_mode(mode)
        prefer = prefer or (self.settings.get("models") or {}).get(role)
        return rank(self._view(), self.states, role, messages=messages, prefer=prefer,
                    paid_first=bool(self.settings.get("paid_first")), need_tools=need_tools,
                    local_models=self._local_models(role), allow_online=mode != "local",
                    allow_local=mode != "online", leaderboard=self.leaderboard, domain=domain, lang=language())

    def ranking(self, role: str, mode: str = "auto", *, prefer: str | None = None, messages: list[dict] | None = None,
                need_tools: bool = False, domain: str | None = None) -> list[Candidate]:
        return compose(self._rank(role, mode, prefer, messages, need_tools, domain),
                       int(self.settings.get("max_chain") or 5))

    def pool(self, role: Role, mode: Mode = "auto", *, domain: str | None = None) -> list[ModelRef]:
        """Every model the router may use for `role`, best first (leaderboard included), not cut to a chain: the
        tournament's contestants (pipeline/tournament.py). Paused models are left out; paid ones only when chosen or
        with `paid_first`."""
        return [ref_of(c.model) for c in self._rank(role, mode, None, None, False, domain)]

    def candidates(self, role: Role, mode: Mode = "auto") -> list[ModelRef]:
        self._maybe_refresh()
        return [ref_of(c.model) for c in self.ranking(role, mode)]

    def explain(self, role: Role, mode: Mode = "auto", domain: str | None = None) -> list[dict]:
        """Ranking with the reason of each position (for the UI's « why this model? »)."""
        return [{"model": c.model.key, "name": c.model.name, "score": round(c.score, 3), "why": c.why}
                for c in self.ranking(role, mode, domain=domain)]

    def test_model(self, provider: str) -> dict | None:
        """The model the key test calls for `provider`: cheap and stable, not the strongest (catalogue.test_model)."""
        from .catalogue import key_test_model
        models = [m for m in self._view().models if m.provider == provider and not self.states.pause_of(m.key)]
        r = key_test_model(models, provider)
        if r is None:
            return None
        return {"key": r[0].key, "name": r[0].name, "why": r[1], "models": len(models)}

    # ------------------------------------------------------------------ paid reinforcement (Claude) and spending
    def caps(self) -> tuple[float, float]:
        def f(name: str, default: float) -> float:
            v = self.settings.get(name)
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else default
        return f("claude_cap_proof_usd", spend.DEFAULT_CAP_PROOF), f("claude_cap_month_usd", spend.DEFAULT_CAP_MONTH)

    def spend_summary(self) -> dict:
        cp, cm = self.caps()
        out = self.ledger.summary(cp, cm)
        out.update(enabled=bool(self.settings.get("claude_reinforce", True)), key_set=self.key("anthropic") is not None,
                   model=str(self.settings.get("claude_model") or "auto"),
                   models=[{"key": m.key, "name": m.name} for m in self._view().models
                           if m.paid and m.provider == "anthropic"])
        return out

    def reinforcements(self, role: Role, mode: Mode = "auto", *, domain: str | None = None) -> list[ModelRef]:
        """The paid model that may join the tournament's final round when the free models failed (user decision
        2026-11-21): Claude, only with its key, `claude_reinforce` on, outside local mode and while the month's cap
        leaves room. The model is `claude_model` when set, else the best Claude for the role. At most one."""
        if not self.settings.get("claude_reinforce", True) or self.effective_mode(mode) == "local" \
                or self.key("anthropic") is None:
            return []
        cp, cm = self.caps()
        if self.ledger.month_total() >= cm or cp <= 0:
            return []
        from .classify import role_categories
        cat, cat2, fast = role_categories(role, None)
        pool = [m for m in self._view().models if m.paid and m.provider == "anthropic"
                and not self.states.pause_of(m.key)]
        want = str(self.settings.get("claude_model") or "auto")
        chosen = [m for m in pool if want in (m.key, m.model_id)]
        if chosen:
            return [ref_of(chosen[0])]
        pool.sort(key=lambda m: score_model(m, cat, cat2, fast, self.states, True)[0], reverse=True)
        return [ref_of(m) for m in pool[:1]]

    def _budget(self, m: Model, role: str, payload, max_tokens: int, on_chunk) -> tuple[int, float]:
        """Before a paid call: fit `max_tokens` to what the caps leave, reserve the estimate. Raises
        ProviderError("budget") when even a short answer would pass a cap (nothing is sent)."""
        p = spend.price_of(m.model_id)
        if p is None:
            return max_tokens, 0.0
        scope = spend.SPEND_SCOPE.get()
        cp, cm = self.caps()
        n_in = spend.tokens_of(payload)
        p = spend.price_of(m.model_id, n_in) or p
        room = self.ledger.room(scope, cp, cm)
        affordable = int((room - n_in * p[0] / 1e6) / p[1] * 1e6) if p[1] else max_tokens
        floor_ = min(max_tokens, spend.MIN_OUTPUT)
        if affordable < floor_:
            which = "proof" if scope and self.ledger.proof_room(scope, cp) <= self.ledger.month_room(cm) else "month"
            why = (f"spending cap reached ({which}: {cp if which == 'proof' else cm:.2f} $); "
                   f"{m.name} not called")
            emit(on_chunk, "info", why, event="budget", model=m.key, cap=which)
            raise ProviderError("budget", why)
        mt = min(max_tokens, affordable)
        est = n_in * p[0] / 1e6 + mt * p[1] / 1e6
        try:
            self.ledger.check(scope, est, cp, cm)
        except spend.BudgetExceeded as e:
            why = f"spending cap reached ({e.which}: {e.cap:.2f} $); {m.name} not called"
            emit(on_chunk, "info", why, event="budget", model=m.key, cap=e.which)
            raise ProviderError("budget", why) from None
        emit(on_chunk, "info", f"{m.name}: at most {est:.2f} $ for this call", event="cost", model=m.key,
             estimate=round(est, 4))
        return mt, est

    def _maybe_refresh(self) -> None:
        if not self.settings.get("refresh_catalogue", True) or self.settings.get("mode") == "local":
            return
        if not self.store.stale() or (self._refresh_task and not self._refresh_task.done()):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._refresh_task = loop.create_task(self._refresh_quiet())

    async def _first_refresh(self, mode: str) -> None:
        """Never refreshed (first start): wait up to 8 s for the online catalogue once, otherwise the seed is used."""
        if self._first_done or mode == "local" or self.store.cat.updated or not self.settings.get("refresh_catalogue", True) \
                or self.settings.get("mode") == "local":
            return
        self._first_done = True
        self._maybe_refresh()
        if self._refresh_task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._refresh_task), 8)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass

    async def _refresh_quiet(self) -> None:
        try:
            await self.refresh()
        except Exception as e:  # noqa: BLE001
            log.info("catalogue refresh failed: %s", e)

    async def refresh(self) -> None:
        online = self.settings.get("mode") != "local" and await self.http.online()
        await self.store.refresh(self.http, self.key, online=online)

    # ------------------------------------------------------------------ status
    async def status(self) -> dict[str, Any]:
        online = False if self.settings.get("mode") == "local" else await self.http.online()
        cat = self._view()
        provs = []
        for p in {**{p.id: p for p in cat.providers}, **{p.id: p for p in KEYED}}.values():
            keys = [m.key for m in cat.models if m.provider == p.id]
            pauses = [self.states.pause_of(k) for k in keys]
            pauses = [x for x in pauses if x]
            all_paused = bool(keys) and len(pauses) == len(keys)
            provs.append({"id": p.id, "name": p.name, "keyed": p.keyed, "paid": p.paid,
                          "key_set": self.key(p.id) is not None if p.keyed else None,
                          "models": len(keys), "ok": bool(keys) and not all_paused,
                          "paused_until": max((u for u, _ in pauses), default=None) if all_paused else None,
                          "reason": pauses[0][1] if all_paused else self.last_error.get(p.id, "")})
        loc = {"runtime": self.local is not None,
               "models": {r: (self.local.model_for(r).key if self.local and self.local.model_for(r) else None)
                          for r in ("understand", "route", "formalize", "prove", "explain", "assistant")}
               if self.local else {},
               "ollama": [m.model_id for m in cat.models if m.provider == "ollama"]}
        return {"online": online, "catalogue_updated": self.store.cat.updated, "providers": provs, "local": loc,
                "mode": self.settings.get("mode")}

    async def close(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        await self.http.close()

    # ------------------------------------------------------------------ one generation on one model
    async def _generate(self, m: Model, role: str, *, mode: str, messages: list[dict] | None = None,
                        history: list[dict] | None = None, tools: list[dict] | None = None,
                        temperature: float | None = None, max_tokens: int | None = None, extra: dict | None = None,
                        on_chunk: OnChunk | None = None) -> StreamResult:
        """messages: OpenAI-style (complete); history: neutral (agent). Raises ProviderError."""
        from . import convo
        oa_tools = [{"type": "function", "function": t} for t in tools] if tools else None
        stall = float(self.settings.get("stall_local" if m.local else "stall_online") or 90)
        first = FIRST_BYTE_LOCAL if m.local else (FIRST_BYTE_REASONING if reasoning_model(m.model_id)
                                                   else FIRST_BYTE_ONLINE)
        if m.provider == "local":
            if self.local is None:
                raise ProviderError("unavailable", "no local runtime")
            base = await self.local.ensure(role)  # type: ignore[arg-type]
            try:
                if not base:
                    raise ProviderError("unavailable", f"no local model installed for {role}")
                base = base.rstrip("/")
                if not base.endswith("/v1"):
                    base += "/v1"
                if not is_loopback_host(urlsplit(base).hostname):
                    raise ProviderError("unavailable", "local runtime must be on this machine")
                msgs = messages if history is None else convo.to_openai(history, bool(tools))
                return await openai_compat.stream_chat(
                    self.http, base_url=base, model=m.model_id, messages=msgs, mode="local", provider="local",
                    max_tokens=max_tokens, temperature=temperature, tools=oa_tools,
                    extra=extra, on_chunk=on_chunk, stall=stall, first_byte=first)
            finally:
                self.local.release()
        cat = self._view()
        p = cat.provider(m.provider) or next((x for x in KEYED if x.id == m.provider), None)
        if p is None and m.provider == "ollama":
            p = Provider("ollama", "Ollama", f"{OLLAMA_URL}/v1", local=True)
        if p is None:
            raise ProviderError("unavailable", f"unknown provider {m.provider}")
        key = self.key(p.id) if p.keyed else None
        if p.keyed and not key:
            raise ProviderError("http", "no key", 401)
        base = self.base_url(p)
        if p.api == "anthropic":
            if history is not None:
                system, amsgs = convo.to_anthropic(history)
            else:
                system, amsgs = anthropic_api.split_system(messages or [])
            effort = (self.settings.get("anthropic_effort") or {}).get(role) or (extra or {}).get("effort") \
                or EFFORT.get(role, "medium")
            mt = max_tokens or MAX_TOKENS.get(role, 16000)
            est = 0.0
            scope = spend.SPEND_SCOPE.get()
            if m.paid:
                mt, est = self._budget(m, role, [system, amsgs, tools], mt, on_chunk)
            try:
                async with self.sem():
                    res = await anthropic_api.stream_messages(
                        self.http, base_url=base, model=m.model_id, system=system, messages=amsgs, mode=mode, key=key,
                        max_tokens=mt, tools=tools, effort=effort,
                        thinking=bool(self.settings.get("anthropic_thinking", True)),
                        fallbacks=bool(self.settings.get("anthropic_fallbacks", True)), cache=True,
                        on_chunk=on_chunk, stall=stall, first_byte=first)
            except ProviderError as e:
                if m.paid and est and e.kind in ("network", "stall", "empty"):
                    # the request may have been billed without usage reaching us: count its prompt (estimated)
                    self.ledger.record(m.model_id, scope, spend.tokens_of([system, amsgs, tools]), 0)
                raise
            finally:
                if est:
                    self.ledger.release(scope, est)
            if m.paid:
                row = self.ledger.record(m.model_id, scope, res.tokens_in, res.tokens_out, res.cache_read,
                                         res.cache_write)
                emit(on_chunk, "info", f"{m.name}: {row.usd:.4f} $", event="spent", model=m.key, usd=row.usd,
                     month=round(self.ledger.month_total(), 4))
            return res
        msgs = messages if history is None else convo.to_openai(history, bool(tools))
        ex = {k: v for k, v in (extra or {}).items() if k not in ("effort",)}
        if not m.local:
            ex = {k: v for k, v in ex.items() if k in ("top_p", "seed", "stop", "presence_penalty", "frequency_penalty")}
        if p.id == "gemini" and gemini_thinking(m.model_id):
            # documented OpenAI-compatible parameter (ai.google.dev/gemini-api/docs/openai): bounds the thinking that
            # happens before the first byte; refused values are dropped by stream_chat (HTTP 400 → retry without)
            ex["reasoning_effort"] = (self.settings.get("gemini_effort") or {}).get(role) \
                or GEMINI_EFFORT.get(role, "medium")
        if m.local:
            async with _nullctx():
                return await openai_compat.stream_chat(
                    self.http, base_url=base, model=m.model_id, messages=msgs, mode="local", provider=p.id,
                    max_tokens=max_tokens, temperature=temperature, tools=oa_tools, extra=ex, on_chunk=on_chunk,
                    stall=stall, first_byte=first)
        async with self.sem():
            return await openai_compat.stream_chat(
                self.http, base_url=base, model=m.model_id, messages=msgs, mode=mode, provider=p.id, key=key,
                max_tokens=max_tokens, temperature=temperature, tools=oa_tools, extra=ex, on_chunk=on_chunk,
                stall=stall, first_byte=first)

    async def _on_failure(self, m: Model, e: ProviderError, mode: str) -> str:
        """Record a failure; returns a short reason. Detects a lost network."""
        if e.kind == "network" and not m.local:
            if not await self.http.online(mode):
                return "offline"
            self.states.record(m.key, False, 0, e.message)
            return f"network error: {e.message}"
        if e.kind in ("unavailable", "budget"):
            return e.message
        if e.kind == "context":
            return "conversation too long for this model"
        if e.kind == "empty":
            self.states.record(m.key, False, 0, "empty answer")
            return "empty answer"
        if e.kind == "stall":
            self.states.record(m.key, False, 0, e.message)
            return f"stalled ({e.message})"
        if e.kind == "refusal":
            return "refused"
        if e.status in (401, 403):
            if any(p.id == m.provider for p in KEYED):          # the user's key is refused: the whole provider
                keys = [x.key for x in self._view().models if x.provider == m.provider]
                self.states.pause_provider(m.provider, keys or [m.key])
                self.last_error[m.provider] = "key_refused"
                return f"key refused (HTTP {e.status})"
            self.states.pause_provider(m.provider, [m.key], "needs_key")   # keyless provider: this model needs a key
            return f"needs a key (HTTP {e.status})"
        if unusable_model(e.status, e.message):
            # not a text chat model (Live API, audio, image, embeddings…): it will never answer generateContent /
            # chat completions — out of every role for months, not a short pause (seen: gemini-*-live-preview)
            self.states.pause_provider(m.provider, [m.key], "unsupported", UNUSABLE_PAUSE)
            return f"model unusable here (HTTP {e.status})"
        if e.status == 404 or (e.status == 400 and ("does not exist" in e.message.lower() or "unavailable" in e.message.lower()
                                                    or "not found" in e.message.lower())):
            self.states.pause_provider(m.provider, [m.key], "not_found", 6 * 3600.0)
            return f"model unavailable (HTTP {e.status})"
        self.states.record(m.key, False, e.status, e.message, e.wait)
        if e.status == 429:
            self.last_error[m.provider] = "rate_limit"
        return f"HTTP {e.status} {e.message}".strip() if e.status else e.message

    # ------------------------------------------------------------------ complete
    async def complete(self, role: Role, messages: list[dict], *, mode: Mode = "auto",
                       temperature: float | None = None, max_tokens: int | None = None,
                       on_chunk: OnChunk | None = None, prefer: str | None = None,
                       extra: dict | None = None) -> Completion:
        mode = self.effective_mode(mode)
        token = CALL_MODE.set(mode)
        try:
            await self._first_refresh(mode)
            self._maybe_refresh()
            chain = self.ranking(role, mode, prefer=prefer, messages=messages)
            if mode == "online" and not chain:
                raise BrainError("no_model", "online mode: no online model is available (all paused or none known)")
            if not chain:
                raise BrainError("no_model", f"no model available for {role} in {mode} mode")
            if mode == "online" and not await self.http.online(mode):
                raise BrainError("offline", "online mode: the Internet is not reachable", [c.model.key for c in chain])
            fallbacks: list[str] = []
            reasons: list[str] = []
            lost = 0.0
            extended = False
            i = -1
            while True:
                i += 1
                if i >= len(chain):
                    if extended or lost > LOST_TIME_LIMIT:
                        break
                    extended = True                  # all failed: once more with models not tried yet
                    used = {x.model.key for x in chain}
                    chain = chain + [x for x in self.ranking(role, mode, messages=messages)
                                     if x.model.key not in used and not x.model.paid][:5]
                    if i >= len(chain):
                        break
                c = chain[i]
                m = c.model
                if not m.local and (self.http.known_offline() or lost > LOST_TIME_LIMIT):
                    fallbacks.append(f"{m.key}: skipped ({'offline' if self.http.known_offline() else 'too much time lost'})")
                    continue
                if fallbacks:
                    emit(on_chunk, "info", f"→ {m.name}", event="switch", model=m.key, reason=fallbacks[-1])
                else:                      # the caller knows which model is working even if the call never returns
                    emit(on_chunk, "info", "", event="model", model=m.key)
                t0 = time.monotonic()
                try:
                    res = await self._generate(m, role, mode=mode, messages=messages, temperature=temperature,
                                               max_tokens=max_tokens, extra=extra, on_chunk=on_chunk)
                except ProviderError as e:
                    lost += time.monotonic() - t0
                    why = await self._on_failure(m, e, mode)
                    fallbacks.append(f"{m.key}: {why}")
                    reasons.append(why)
                    emit(on_chunk, "info", "", event="restart", model=m.key, reason=why)
                    continue
                except BrainError:
                    raise
                if res.finish == "refusal" and not res.text.strip():
                    fallbacks.append(f"{m.key}: refused")
                    reasons.append("refused")
                    emit(on_chunk, "info", "", event="restart", model=m.key, reason="refused")
                    continue
                if res.finish != "loop" and not leancheck.clean_model_text(res.text) and not res.tool_calls:
                    self.states.record(m.key, False, 0, "empty answer")
                    fallbacks.append(f"{m.key}: empty answer")
                    reasons.append("empty answer")
                    emit(on_chunk, "info", "", event="restart", model=m.key, reason="empty answer")
                    continue
                self.states.record(m.key, True)
                return Completion(res.text, ref_of(m), _api_finish(res.finish), res.tokens_in, res.tokens_out,
                                  time.monotonic() - t0, fallbacks)
            raise BrainError(_error_kind(reasons, mode), "no model could answer:\n" + "\n".join(fallbacks), fallbacks)
        finally:
            CALL_MODE.reset(token)

    # ------------------------------------------------------------------ agent
    async def run_agent(self, role: Role, system: str, task: str, tools: list[ToolSpec], *, mode: Mode = "auto",
                        max_steps: int = 24, max_seconds: float = 900, on_chunk: OnChunk | None = None,
                        prefer: str | None = None, require_tool: str | None = None,
                        max_tokens_budget: int | None = None, only: str | None = None) -> AgentResult:
        """`only`: run on this model key alone (a tournament contestant): no switch to another model on failure."""
        from .agent import run_agent_loop
        mode = self.effective_mode(mode)
        token = CALL_MODE.set(mode)
        try:
            await self._first_refresh(mode)
            self._maybe_refresh()
            return await run_agent_loop(self, role, system, task, tools, mode=mode, max_steps=max_steps,
                                        max_seconds=max_seconds, on_chunk=on_chunk, prefer=prefer,
                                        require_tool=require_tool, only=only,
                                        max_tokens_budget=max_tokens_budget or int(self.settings.get("agent_max_tokens") or 600_000))
        finally:
            CALL_MODE.reset(token)


class _nullctx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


def _api_finish(f: str) -> str:
    return f if f in ("stop", "length", "loop") else ("stop" if f in ("tool_use", "refusal") else "stop")


def _error_kind(reasons: list[str], mode: str) -> str:
    if not reasons:
        return "no_model"
    if all(r == "offline" for r in reasons) or ("offline" in reasons and mode == "online"):
        return "offline"
    if all(r.startswith("key refused") for r in reasons):
        return "auth"
    if all(r.startswith("HTTP 429") or "quota" in r.lower() for r in reasons):
        return "quota"
    return "error"
