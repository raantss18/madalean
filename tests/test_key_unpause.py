"""S-AO (DECISIONS D47): saving or replacing a key lifts that provider's pauses, backoffs and failure counters at once
— for every provider, not only Hugging Face — and a quick key test runs (server side unless the client runs it)."""
from __future__ import annotations

import asyncio
import time

import pytest

from helpers import make_ctx, running, session
from madalean.brain.state import States
from test_brain_fakes import make_brain, model, write_catalogue


def test_clear_provider_lifts_every_pause_of_that_provider_only(tmp_path):
    st = States(tmp_path / "brain-state.json")
    st.record("openrouter:a", False, 429, "rate limited", wait=600)
    for _ in range(3):
        st.record("openrouter:b", False, 500, "boom")
    st.pause_provider("openrouter", ["openrouter:c"], "key_refused")
    st.record("openrouter:d", True)
    st.record("groq:x", False, 429, "slow down", wait=600)
    st.record_latency("openrouter:a", 2.0)
    assert st.pause_of("openrouter:a") and st.pause_of("openrouter:b") and st.pause_of("openrouter:c")
    rel = st.reliability("openrouter:b")
    assert st.clear_provider("openrouter") == 3
    for k in ("openrouter:a", "openrouter:b", "openrouter:c", "openrouter:d"):
        assert st.pause_of(k) is None and st.models[k].failures == 0 and st.models[k].reason == "", k
    assert st.reliability("openrouter:b") == rel and st.latency("openrouter:a") == 2.0   # statistics kept
    assert st.pause_of("groq:x") is not None                                            # other providers untouched
    assert States(tmp_path / "brain-state.json").pause_of("openrouter:c") is None        # persisted
    assert st.clear_provider("openrouter") == 0


@pytest.mark.parametrize("provider", ["openrouter", "groq", "anthropic", "huggingface", "mistral", "gemini"])
def test_engine_key_saved_forgets_pauses_down_and_last_error(tmp_path, provider):
    write_catalogue(tmp_path, [], [model(provider, "m1"), model(provider, "m2"), model("other", "z")])
    b = make_brain(tmp_path, keys={provider: "k" * 20})
    k1, k2 = f"{provider}:m1", f"{provider}:m2"
    b.states.pause_provider(provider, [k1, k2], "key_refused")
    b.states.record("other:z", False, 429, "x", wait=600)
    b.down[provider] = time.monotonic() + 60
    b.last_error[provider] = "key_refused"
    r = b.key_saved(provider)
    assert r == {"unpaused": 2, "was_down": True, "last_error": "key_refused"}
    assert b.states.pause_of(k1) is None and b.states.pause_of(k2) is None
    assert provider not in b.down and provider not in b.last_error
    assert b.states.pause_of("other:z") is not None
    asyncio.run(b.close()) if hasattr(b, "close") else None


async def test_saving_a_key_unpauses_and_runs_the_quick_test(tmp_path):
    ctx = make_ctx(tmp_path)
    saved, tested = [], []
    ctx.brain.key_saved = lambda p: saved.append(p) or {"unpaused": 4}

    async def fake_test(provider):
        tested.append(provider)
        return {"ok": True, "model": f"{provider}:m1", "models": 3}
    ctx.brain.test = fake_test
    async with running(ctx) as (_srv, L, _R), session() as s:
        events = []
        orig = ctx.bus.publish

        def spy(kind, payload):
            events.append((kind, payload))
            return orig(kind, payload)
        ctx.bus.publish = spy
        r = await (await s.post(L + "/api/models/keys", json={"provider": "openrouter", "key": "sk-or-" + "x" * 30})).json()
        assert r["unpaused"] == 4 and r["testing"] is True and saved == ["openrouter"]
        for _ in range(100):
            if any(k == "models.key_test" for k, _p in events):
                break
            await asyncio.sleep(0.02)
        res = next(p for k, p in events if k == "models.key_test")
        assert res == {"provider": "openrouter", "ok": True, "model": "openrouter:m1", "models": 3}
        assert "x" * 30 not in str(events)                                     # the key is never echoed
        # the web form runs the test itself: no second test on the server
        r = await (await s.post(L + "/api/models/keys", json={"provider": "groq", "key": "gsk_" + "y" * 30,
                                                               "test": False})).json()
        await asyncio.sleep(0.2)
        assert r["testing"] is False and saved == ["openrouter", "groq"] and tested == ["openrouter"]
        # the explicit test route is the same test
        j = await (await s.post(L + "/api/models/test", json={"provider": "groq"})).json()
        assert j["ok"] is True and tested == ["openrouter", "groq"]
