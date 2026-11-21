"""Catalogue, classifier, router, pauses / quotas / reliability (ported from L Katta's moteur.rs tests)."""
import json
import os
import stat
import time

import pytest

from madalean.brain import catalogue, classify, router, state
from madalean.brain.api import ModelRef
from test_brain_fakes import free_provider, make_brain, model, write_catalogue


def test_seed_is_usable_without_keys():
    c = catalogue.seed()
    assert c.providers and all(not p.keyed and p.base_url.startswith("https://") for p in c.providers)
    assert not any("huggingface" in p.base_url for p in c.providers)
    assert sum(1 for m in c.models if m.tools) >= 10


def test_classifier():
    assert classify.classify("corrige ce bug dans ma fonction python") == "code"
    assert classify.classify("résous l'équation x^2 + 3x = 4") == "math"
    assert classify.classify("traduis ce texte en anglais") == "translation"
    assert classify.classify("rédige une lettre de motivation") == "writing"
    assert classify.classify("salut, ça va ?") == "chat"
    assert classify.role_categories("prove") == ("lean", "reasoning", False)
    assert classify.role_categories("route")[2] is True
    assert classify.role_categories("assistant", [{"role": "user", "content": "prove this theorem in Lean"}])[0] == "math"


def test_durations_and_context():
    assert state.parse_duration("20s") == 20
    assert state.parse_duration("1m30s") == 90
    assert state.parse_duration("250ms") == 0.25
    assert state.parse_duration("2h") == 7200
    assert state.parse_duration("45") == 45
    assert state.parse_duration("bientôt") is None
    assert state.context_too_long(400, "This model's maximum context length is 8192 tokens")
    assert state.context_too_long(400, "prompt is too long: 250000 tokens > 200000 maximum")
    assert not state.context_too_long(429, "context")
    assert state.wait_from_headers({"retry-after": "12"}) == 12
    assert state.wait_from_headers({"x-ratelimit-reset-requests": "1m"}) == 60


def test_pauses_reliability_and_private_file(tmp_path):
    s = state.States(tmp_path / "st.json")
    s.record("p:a", False, 429, "rate", wait=40)
    until, why = s.pause_of("p:a")
    assert why == "rate_limit" and 35 < until - time.time() <= 40
    s.record("p:b", False, 429, "You exceeded your daily quota")
    until, why = s.pause_of("p:b")
    assert why == "daily_quota" and until % 86400 == 0 and until > time.time()     # midnight UTC
    s.record("p:c", False, 400, "This model's maximum context length is 4096")    # not the model's fault
    assert "p:c" not in s.models
    s.record("p:d", False, 529, "Overloaded")
    assert s.pause_of("p:d")[1] == "overloaded"
    s.record("p:e", False, 500, "boom")
    s.record("p:e", False, 500, "boom")
    assert s.models["p:e"].failures == 2 and s.pause_of("p:e")[0] - time.time() > 50
    assert s.reliability("p:e") < s.reliability("p:new") == 0.8
    s.record("p:e", True)
    assert s.pause_of("p:e") is None and s.models["p:e"].failures == 0
    s.pause_provider("q", ["q:1", "q:2"])
    assert s.pause_of("q:2")[1] == "key_refused"
    mode = stat.S_IMODE(os.stat(tmp_path / "st.json").st_mode)
    assert mode == 0o600
    s2 = state.States(tmp_path / "st.json")                                       # persisted
    assert s2.pause_of("q:1") is not None


def _cat(tmp_path):
    write_catalogue(tmp_path, [free_provider("f1", "https://f1.example/v1"), free_provider("f2", "https://f2.example/v1")],
                    [model("f1", "qwen3-235b", 0.7), model("f1", "tiny-1b", 0.2), model("f2", "deepseek-v4", 0.65),
                     model("f2", "notools", 0.5, tools=False), model("f2", "writer", 0.3, quality={"writing": 0.99, "chat": 0.3})])


def test_router_roles_lean_bonus_and_why(tmp_path):
    _cat(tmp_path)
    b = make_brain(tmp_path)
    prove = b.explain("prove")
    assert prove[0]["model"] in ("f1:qwen3-235b", "f2:deepseek-v4")
    why = {r["model"]: r["why"] for r in prove}
    assert "good at maths and code" in why["f1:qwen3-235b"] and "reliability" in why["f1:qwen3-235b"]
    assert b.candidates("explain")[0].key == "f2:writer"            # explain -> writing quality
    # agents need tools: the router can filter them
    assert all(c.model.tools for c in b.ranking("prove", need_tools=True))


def test_preference_paid_and_pauses(tmp_path):
    _cat(tmp_path)
    b = make_brain(tmp_path, keys={"anthropic": "sk-ant-test"})
    keys = [c.key for c in b.candidates("prove")]
    assert not any(k.startswith("anthropic:") for k in keys)          # paid: only when chosen or paid_first
    assert b.candidates("prove")[0].key != "f1:tiny-1b"
    assert [c.model.key for c in b.ranking("prove", prefer="f1:tiny-1b")][0] == "f1:tiny-1b"
    assert b.ranking("prove", prefer="anthropic:claude-opus-5-5")[0].model.key == "anthropic:claude-opus-5-5"
    b.update_settings({"paid_first": True})
    chain = b.candidates("prove")
    assert chain[0].provider == "anthropic" and chain[0].paid
    assert sum(1 for c in chain if c.paid) == 2 and not chain[2].paid        # never a chain of paid models only
    b.update_settings({"paid_first": False, "models": {"prove": "f2:deepseek-v4"}})
    assert b.candidates("prove")[0].key == "f2:deepseek-v4"                   # per-role preferred model
    b.states.record("f2:deepseek-v4", False, 429, "slow down", wait=60)
    assert "f2:deepseek-v4" not in [c.key for c in b.candidates("route")]


class FakeLocal:
    def __init__(self, url="http://127.0.0.1:9/v1"):
        self.url, self.ensured, self.released = url, 0, 0

    async def ensure(self, role):
        self.ensured += 1
        return self.url

    def release(self):
        self.released += 1

    def model_for(self, role):
        return ModelRef("local", f"goedel-{role}", f"Goedel ({role})", local=True)


def test_modes_select_models(tmp_path):
    _cat(tmp_path)
    b = make_brain(tmp_path, local=FakeLocal())
    auto = b.candidates("prove", "auto")
    assert auto[-1].local and not auto[0].local                     # local is the offline fallback, last
    assert [c.key for c in b.candidates("prove", "local")] == ["local:goedel-prove"]
    assert not any(c.local for c in b.candidates("prove", "online"))
    b.update_settings({"mode": "local"})                            # settings ceiling: everything local
    assert all(c.local for c in b.candidates("prove", "online"))


def test_compose_limits():
    def c(k, paid=False, local=False, s=1.0):
        return router.Candidate(catalogue.Model("p", k, k, paid=paid, local=local), s, "")
    ch = router.compose([c("a", True), c("b", True), c("c", True), c("d"), c("e"), c("f"), c("g"), c("h"), c("l", local=True)], 5)
    assert [x.model.model_id for x in ch] == ["a", "b", "d", "e", "f", "l"]


def test_estimate_and_lean_quality():
    big = catalogue.estimate("Llama-3.3-70B-Instruct", [])
    small = catalogue.estimate("tiny-1b", [])
    assert big["chat"] > small["chat"]
    m = catalogue.Model("x", "deepseek-prover-v2", "DeepSeek Prover", quality={"math": 0.5, "code": 0.5})
    assert m.score("lean") == pytest.approx(0.8)
    assert not catalogue.is_text_chat("bge-m3") and catalogue.is_text_chat("Qwen3.8-27B")


def test_catalogue_refresh_from_fake_providers(tmp_path):
    """Refresh parses each provider's /models format (kilo isFree, llm7 tiers, OpenRouter pricing)."""
    import asyncio
    from madalean.brain.catalogue import CatalogueStore
    from madalean.brain.net import Http

    class FakeHttp(Http):
        def __init__(self):
            super().__init__({})

        async def get_json(self, url, **kw):
            if "kilo" in url:
                return {"data": [{"id": "a/free-one:free", "isFree": True, "supported_parameters": ["tools"]},
                                 {"id": "a/paid", "isFree": False}]}
            if "llm7" in url:
                return {"data": [{"id": "pro-model", "tier": "pro"}, {"id": "gemma-3-27b", "tier": "turbo", "model_type": "chat"},
                                 {"id": "flux-img", "model_type": "image"}]}
            if "openrouter" in url:
                return {"data": [{"id": "x/y:free", "pricing": {"prompt": "0"}}, {"id": "x/z", "pricing": {"prompt": "0.1"}}]}
            if "11434" in url:
                return {"models": [{"name": "qwen3.5:9b"}, {"name": "nomic-embed-text:latest"}]}
            return None
    st = CatalogueStore(tmp_path / "cat.json")
    n = asyncio.run(st.refresh(FakeHttp(), lambda p: "k" if p == "openrouter" else None))
    keys = {m.key for m in st.cat.models}
    assert {"kilo:a/free-one:free", "llm7:gemma-3-27b", "openrouter:x/y:free", "ollama:qwen3.5:9b"} <= keys
    assert not keys & {"kilo:a/paid", "llm7:pro-model", "llm7:flux-img", "openrouter:x/z", "ollama:nomic-embed-text:latest"}
    assert any(m.provider == "ovh" for m in st.cat.models)          # unreachable provider keeps its seed models
    assert n == len(st.cat.models) and json.loads((tmp_path / "cat.json").read_text())["updated"] > 0
    assert stat.S_IMODE(os.stat(tmp_path / "cat.json").st_mode) == 0o600
