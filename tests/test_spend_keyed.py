"""Session S-M: keyed models ranked by family (Gemini, Mistral, Claude), the key test's cheap model, Claude as a paid
reinforcement within the user's caps (ledger, estimates before each call, real usage after it, refusal), the
tournament's final round — fake Anthropic server, fake Lean, no network."""
from __future__ import annotations

import asyncio
import json
import os
import stat

import pytest

from madalean.brain import spend
from madalean.brain.api import BrainError, ModelRef
from madalean.brain.catalogue import Catalogue, CatalogueStore, Model, family_quality, key_test_model
from madalean.brain.router import rank
from madalean.brain.state import States
from madalean.pipeline import runner
from madalean.pipeline.tournament import Config, Contestant, Outcome, Tournament
from madalean.server.routes_work import create_dossier
from test_brain_fakes import FakeServer, an_stream, free_provider, make_brain, model, run, write_catalogue
from helpers import make_ctx, running, session, wait_idle

ANTHROPIC_KEY = "sk-ant-test-0123456789"

# Model ids as the providers list them (Gemini's OpenAI-compatible /models returns « models/<id> »; Mistral's
# /v1/models plain ids). Built from the providers' documented model lists, not recorded with a real key.
GEMINI_IDS = ["models/gemini-2.5-pro", "models/gemini-2.5-flash", "models/gemini-2.5-flash-lite",
              "models/gemini-2.0-flash", "models/gemini-2.0-flash-lite", "models/gemini-3-pro-preview",
              "models/gemini-3-flash-preview", "models/gemini-flash-latest", "models/gemma-4-31b-it",
              "models/gemma-4-26b-a4b-it", "models/gemma-3n-e4b-it", "models/gemini-2.5-flash-preview-tts",
              "models/gemini-2.5-computer-use-preview-10-2025", "models/gemini-embedding-001"]
MISTRAL_IDS = ["mistral-large-latest", "mistral-medium-latest", "magistral-medium-latest", "magistral-small-latest",
               "devstral-medium-latest", "devstral-small-latest", "codestral-latest", "mistral-small-latest",
               "ministral-14b-2512", "ministral-14b-latest", "ministral-8b-latest", "ministral-3b-latest",
               "open-mistral-nemo", "pixtral-large-latest", "voxtral-small-latest", "mistral-ocr-latest",
               "mistral-embed", "mistral-moderation-latest"]


# ---------------------------------------------------------------- task 1: keyed families
def test_family_quality_orders_the_keyed_families():
    q = {mid: family_quality(mid) for mid in GEMINI_IDS + MISTRAL_IDS}
    lean = lambda mid: q[mid][0]["math"]  # noqa: E731
    assert lean("models/gemini-3-pro-preview") > lean("models/gemini-2.5-pro") > lean("models/gemini-2.5-flash") \
        > lean("models/gemini-2.5-flash-lite") > lean("models/gemma-4-31b-it")
    assert q["models/gemini-flash-latest"][1] == "Gemini 3 Flash family"
    assert lean("magistral-medium-latest") > lean("mistral-large-latest") > lean("ministral-14b-2512")
    assert q["devstral-medium-latest"][0]["code"] > q["mistral-large-latest"][0]["code"]
    assert family_quality("some-unknown-model") is None


def _keyed_store(tmp_path) -> CatalogueStore:
    """A catalogue saved by the previous version: keyed models with the size-based guess (0.41 / 0.44 / 0.48)."""
    from madalean.brain.catalogue import KEYED, estimate, is_text_chat
    provs = [p for p in KEYED if p.id in ("gemini", "mistral")]
    models = []
    for pid, ids in (("gemini", GEMINI_IDS), ("mistral", MISTRAL_IDS)):
        for raw in ids:
            mid = raw.removeprefix("models/")
            if is_text_chat(mid):
                models.append(Model(pid, mid, mid, quality=estimate(mid, [])))
    st = CatalogueStore(tmp_path / "cat.json")
    st.cat = Catalogue(1.0, provs, models)
    return st


def test_old_catalogue_is_re_estimated_and_strong_keyed_models_lead(tmp_path):
    st = _keyed_store(tmp_path)
    ids = {m.model_id for m in st.cat.models}
    assert "gemini-2.5-flash-preview-tts" not in ids and "gemini-2.5-computer-use-preview-10-2025" not in ids
    assert "mistral-ocr-latest" not in ids and "voxtral-small-latest" not in ids
    view = st.with_keys(lambda p: p in ("gemini", "mistral"))
    states = States(tmp_path / "s.json")
    prove = rank(view, states, "prove")
    top = [c.model.key for c in prove[:4]]
    assert top[0] == "gemini:gemini-3-pro-preview" and "gemini:gemini-2.5-pro" in top
    assert "(estimated: Gemini 3 Pro family)" in prove[0].why and "strong reasoning model" in prove[0].why
    pos = {c.model.key: i for i, c in enumerate(prove)}
    assert pos["gemini:gemini-2.5-pro"] < pos["gemini:gemma-4-31b-it"]
    assert pos["mistral:magistral-medium-latest"] < pos["mistral:ministral-14b-2512"]
    assert pos["mistral:mistral-large-latest"] < pos["mistral:ministral-14b-latest"]
    explain = rank(view, states, "explain")
    assert explain[0].model.provider == "gemini" and "gemma" not in explain[0].model.model_id


def test_key_test_picks_a_cheap_reliable_model(tmp_path):
    view = _keyed_store(tmp_path).with_keys(lambda p: True)
    m, why = key_test_model(view.models, "gemini")
    assert m.model_id == "gemini-2.5-flash-lite" and "cheap" in why
    assert key_test_model(view.models, "mistral")[0].model_id == "mistral-small-latest"
    claude = [Model("anthropic", mid, mid, paid=True) for mid in ("claude-opus-5-5", "claude-haiku-5-5")]
    assert key_test_model(claude, "anthropic")[0].model_id == "claude-haiku-5-5"
    odd = [Model("gemini", "gemma-4-31b-it", "g"), Model("gemini", "gemini-9-ultra", "u")]
    assert key_test_model(odd, "gemini")[0].model_id == "gemini-9-ultra"       # never Gemma for the Gemini key test
    assert key_test_model([], "gemini") is None


def test_refresh_applies_families_and_skips_non_chat(tmp_path):
    from madalean.brain.catalogue import KEYED

    class Http:
        async def get_json(self, url, mode="online", timeout=15, provider=None, key=None):
            if provider == "gemini":
                return {"object": "list", "data": [{"id": i, "object": "model", "owned_by": "google"}
                                                   for i in GEMINI_IDS]}
            if provider == "mistral":
                return {"object": "list", "data": [{"id": i, "name": i} for i in MISTRAL_IDS]}
            return None

    st = CatalogueStore(tmp_path / "cat.json")
    n = run(st.refresh(Http(), lambda p: "k" if p in ("gemini", "mistral") else None))
    assert n > 0
    g = {m.model_id: m for m in st.cat.models if m.provider == "gemini"}
    assert g["gemini-2.5-pro"].est == "Gemini 2.5 Pro family" and g["gemini-2.5-pro"].quality["math"] > 0.8
    assert "gemini-embedding-001" not in g and "gemini-2.5-flash-preview-tts" not in g
    assert any(p.id == "gemini" for p in st.cat.providers) and KEYED


# ---------------------------------------------------------------- task 2: ledger and estimates
def test_prices_costs_and_ledger(tmp_path):
    assert spend.estimate("claude-opus-5-5", 1_000_000, 0) == pytest.approx(4.0)
    assert spend.estimate("anthropic:claude-sonnet-5-5", 0, 1_000_000) == pytest.approx(10.0)
    assert spend.estimate("claude-haiku-5-5", 200_000, 0) == pytest.approx(0.2 * 0.5)      # long prompt: ×5
    assert spend.estimate("gpt-unknown", 10, 10) is None
    # tokens_in includes cached tokens: 300 fresh + 600 read + 100 written
    c = spend.cost("claude-opus-5-5", 1000, 500, cache_read=600, cache_write=100)
    assert c == pytest.approx((300 * 4 + 500 * 20 + 600 * 0.2 + 100 * 5) / 1e6)
    led = spend.Ledger(tmp_path / "spend.json")
    led.record("claude-opus-5-5", "d1:j1", 10_000, 20_000)
    assert led.scope_total("d1:j1") == pytest.approx(0.44) and led.month_total() == pytest.approx(0.44)
    assert stat.S_IMODE(os.stat(tmp_path / "spend.json").st_mode) == 0o600
    raw = json.loads((tmp_path / "spend.json").read_text())
    assert set(raw["rows"][0]) == {"ts", "model", "scope", "tokens_in", "tokens_out", "cache_read", "cache_write", "usd"}
    with pytest.raises(spend.BudgetExceeded) as e:
        led.check("d1:j1", 0.6, cap_proof=1.0, cap_month=20.0)
    assert e.value.which == "proof"
    led.check("d2:j2", 0.6, cap_proof=1.0, cap_month=1.1)          # fits, and is now reserved (in flight)
    with pytest.raises(spend.BudgetExceeded) as e:
        led.check("d3:j3", 0.1, cap_proof=1.0, cap_month=1.1)
    assert e.value.which == "month"
    led.release("d2:j2", 0.6)
    led.check("d3:j3", 0.1, cap_proof=1.0, cap_month=1.1)
    assert spend.Ledger(tmp_path / "spend.json").month_total() == pytest.approx(0.44)   # persisted
    s = led.summary(1.0, 20.0)
    assert s["spent_month"] == pytest.approx(0.44) and s["by_model"] == {"claude-opus-5-5": 0.44}


def _claude_brain(tmp_path, srv, **kw):
    write_catalogue(tmp_path, [free_provider("dead", "http://127.0.0.1:9/v1")], [model("dead", "dead", 0.01)])
    return make_brain(tmp_path, keys={"anthropic": ANTHROPIC_KEY}, endpoints={"anthropic": srv.url}, **kw)


def _with_cache(item: dict, read: int, write: int) -> dict:
    ev = list(item["events"])
    ev[0] = ev[0].replace('"cache_read_input_tokens": 0', f'"cache_read_input_tokens": {read}') \
                 .replace('"cache_creation_input_tokens": 0', f'"cache_creation_input_tokens": {write}')
    return {"events": ev}


def test_paid_call_fits_the_proof_cap_records_real_usage_then_is_refused(tmp_path):
    async def main():
        srv = await FakeServer([_with_cache(an_stream([("text", "Proof idea")], usage=(1000, 400)), 600, 100)]).start()
        b = _claude_brain(tmp_path, srv, claude_cap_proof_usd=0.05, claude_cap_month_usd=20.0)
        seen = []
        tok = spend.SPEND_SCOPE.set("d1:j1")
        try:
            c = await b.complete("prove", [{"role": "user", "content": "prove it"}], prefer="anthropic:claude-opus-5-5",
                                 on_chunk=seen.append)
            assert c.text == "Proof idea"
            sent = srv.requests[-1].body["max_tokens"]
            assert 2048 <= sent < 64000 and sent <= int(0.05 / 20e-6)      # output budget fitted to the cap
            est = [x for x in seen if x.data.get("event") == "cost"]
            spent = [x for x in seen if x.data.get("event") == "spent"]
            assert est and est[0].data["estimate"] <= 0.05 and spent
            row = b.ledger.rows[-1]
            assert (row.model, row.scope, row.tokens_in, row.tokens_out, row.cache_read, row.cache_write) == \
                ("claude-opus-5-5", "d1:j1", 1700, 400, 600, 100)
            assert row.usd == pytest.approx(spend.cost("claude-opus-5-5", 1700, 400, 600, 100))
            assert b.ledger._reserved == {}                                  # the reservation was released
            # the proof's cap is now (almost) used up: the next call is refused before anything is sent
            b.update_settings({"claude_cap_proof_usd": row.usd + 0.001})
            n = len(srv.requests)
            seen.clear()
            with pytest.raises(BrainError) as e:
                await b.complete("prove", [{"role": "user", "content": "again"}], prefer="anthropic:claude-opus-5-5",
                                 on_chunk=seen.append)
            assert len(srv.requests) == n and "spending cap reached (proof" in str(e.value)
            assert any(x.data.get("event") == "budget" for x in seen)
            assert b.states.models.get("anthropic:claude-opus-5-5") is None or \
                not b.states.pause_of("anthropic:claude-opus-5-5")           # a cap is not a model failure
        finally:
            spend.SPEND_SCOPE.reset(tok)
            await b.close()
            await srv.stop()
    run(main())


def test_month_cap_applies_outside_a_proof_and_summary(tmp_path):
    async def main():
        srv = await FakeServer([an_stream([("text", "OK")])]).start()
        b = _claude_brain(tmp_path, srv, claude_cap_month_usd=0.0)
        try:
            with pytest.raises(BrainError) as e:
                await b.complete("explain", [{"role": "user", "content": "x"}], prefer="anthropic:claude-haiku-5-5")
            assert "month" in str(e.value) and not srv.requests
            b.update_settings({"claude_cap_month_usd": 5.0})
            await b.complete("explain", [{"role": "user", "content": "x"}], prefer="anthropic:claude-haiku-5-5")
            s = b.spend_summary()
            assert s["cap_month"] == 5.0 and s["cap_proof"] == 1.0 and s["calls_month"] == 1 and s["key_set"]
            assert s["spent_month"] > 0 and {m["key"] for m in s["models"]} >= {"anthropic:claude-opus-5-5"}
        finally:
            await b.close()
            await srv.stop()
    run(main())


def test_reinforcement_candidates(tmp_path):
    async def main():
        srv = await FakeServer([an_stream([("text", "OK")])]).start()
        b = _claude_brain(tmp_path, srv)
        try:
            assert [r.key for r in b.reinforcements("prove")] == ["anthropic:claude-opus-5-5"]
            assert all(not r.paid for r in b.pool("prove"))          # free rounds never see Claude
            b.update_settings({"claude_model": "anthropic:claude-sonnet-5-5"})
            assert [r.key for r in b.reinforcements("prove")] == ["anthropic:claude-sonnet-5-5"]
            assert b.reinforcements("prove", "local") == []
            b.update_settings({"claude_reinforce": False})
            assert b.reinforcements("prove") == []
            b.update_settings({"claude_reinforce": True, "claude_cap_month_usd": 0.0})
            assert b.reinforcements("prove") == []
        finally:
            await b.close()
            await srv.stop()
        nokey = make_brain(tmp_path / "nk")
        assert nokey.reinforcements("prove") == []
        await nokey.close()
    run(main())


# ---------------------------------------------------------------- tournament final round
def _tournament(outcomes: dict, reinforce, free=("f:a", "f:b", "f:c")):
    calls: list = []

    async def run_one(c, k, n, deadline):
        calls.append((c.key, k))
        await asyncio.sleep(0)
        return Outcome(c, k, ok=outcomes.get(c.key, False), attempts=n)
    t = Tournament(Config(contestants=2, max_rounds=1, max_minutes=5), run=run_one,
                   candidates=lambda: [Contestant(k) for k in free], reinforce=reinforce)
    return t, calls


def test_reinforcement_round_only_after_the_free_models_failed():
    asked = []

    def reinforce():
        asked.append(1)
        return [Contestant("anthropic:claude-opus-5-5", "Opus", paid=True)]

    t, calls = _tournament({"anthropic:claude-opus-5-5": True}, reinforce)
    res = asyncio.run(t.run())
    assert res.stop == "won" and res.winner.contestant.paid and calls[-1] == ("anthropic:claude-opus-5-5", 2)
    assert [c for c, _k in calls[:-1]] == ["f:a", "f:b", "f:c"]
    asked.clear()
    t, calls = _tournament({"f:b": True}, reinforce)
    res = asyncio.run(t.run())
    assert res.winner.contestant.key == "f:b" and not asked                 # a free model won: no paid call
    t, calls = _tournament({}, reinforce)
    res = asyncio.run(t.run())
    assert res.winner is None and res.stop == "reinforcement" and len(calls) == 4
    t, calls = _tournament({}, lambda: [])
    assert asyncio.run(t.run()).stop in ("exhausted", "rounds")


async def test_pipeline_claude_joins_last_within_caps(tmp_path, monkeypatch):
    from test_tournament import PoolBrain, make, STMT
    log: list = []
    saved = PoolBrain.MODELS
    PoolBrain.MODELS = [m for m in saved if m.model_id not in ("winner", "opus")]
    try:
        ctx, brain = await make(tmp_path, monkeypatch, log)
        brain.reinforcements = lambda role, mode="auto", domain=None: [ModelRef("paid", "opus", "Opus", paid=True)]
        brain.caps = lambda: (1.0, 20.0)
        d, _j = await create_dossier(ctx, {"statement": STMT, "start": False})
        job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
        await wait_idle(ctx, timeout=60)
    finally:
        PoolBrain.MODELS = saved
    assert job.state == "done" and d.proofs[-1].model == "paid:opus", (job.error, job.summary)
    assert log[-1] == "paid:opus" and log.count("paid:opus") == 1
    assert any("Renfort payant : Opus" in e.text and "1.00 $" in e.text for e in d.events)
    await ctx.stop()


async def test_spend_api_and_cap_settings(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _remote):
        async with session() as s:
            async with s.get(local + "/api/models/spend") as r:
                body = await r.json()
            assert r.status == 200 and body["cap_proof"] == 1.0 and body["cap_month"] == 20.0
            assert body["spent_month"] == 0 and body["enabled"] is True and "claude-opus-5-5" in body["prices"]
            async with s.patch(local + "/api/settings", json={"claude_cap_month_usd": 5, "claude_cap_proof_usd": 0.5}) as r:
                st = (await r.json())["settings"]
            assert st["claude_cap_month_usd"] == 5.0 and st["claude_cap_proof_usd"] == 0.5
            async with s.patch(local + "/api/settings", json={"claude_cap_month_usd": -1}) as r:
                assert r.status == 400
            async with s.get(local + "/api/models/spend") as r:
                assert (await r.json())["cap_month"] == 5.0


# ---------------------------------------------------------------- unfit models (S-L real runs: a summariser proved)
def test_summariser_and_tiny_models_never_prove_or_formalize(tmp_path):
    from madalean.brain.catalogue import unfit_reason
    from madalean.brain.leaderboard import Leaderboard
    models = [Model("ovh", "Olala-v1.0-summarise", "Olala-v1.0-summarise", quality={"chat": 0.9, "math": 0.9, "code": 0.9}),
              Model("ovh", "Qwen3.6-27B", "Qwen3.6-27B", quality={"chat": 0.5, "math": 0.5, "code": 0.6}),
              Model("kilo", "liquid/lfm-2.5-2.6b:free", "LFM 2.6B", quality={"chat": 0.8, "math": 0.8, "code": 0.8}),
              Model("gemini", "gemma-3n-e4b-it", "gemma-3n-e4b-it", quality={"chat": 0.8, "math": 0.8, "code": 0.8}),
              Model("ovh", "Qwen2.5-VL-72B-Instruct", "VL", quality={"chat": 0.8, "math": 0.8, "code": 0.8})]
    assert unfit_reason(models[0]).startswith("task-specific") and unfit_reason(models[1]) == ""
    assert unfit_reason(models[2]).startswith("too small") and unfit_reason(models[3]).startswith("small model")
    cat = Catalogue(1.0, [], models)
    states = States(tmp_path / "s.json")
    for role in ("prove", "formalize"):
        assert [c.model.model_id for c in rank(cat, states, role)] == ["Qwen3.6-27B"]
    route = rank(cat, states, "route")
    assert route[0].model.model_id == "Qwen3.6-27B" and "summar" in next(c.why for c in route if "Olala" in c.model.model_id)
    explain = [c.model.model_id for c in rank(cat, states, "explain")]
    assert "Olala-v1.0-summarise" in explain                           # free to summarise / explain
    chosen = rank(cat, states, "prove", prefer="ovh:Olala-v1.0-summarise")
    assert chosen[0].model.model_id == "Olala-v1.0-summarise"           # the user's explicit choice still wins
    # leaderboard: a model whose Lean never compiles sinks below an unknown one
    lb = Leaderboard(tmp_path / "lb.json")
    for _ in range(3):
        lb.record("ovh:junk", "prove", ok=False, attempts=2, lean_errors=2)
        lb.record("ovh:tries", "prove", ok=False, attempts=2, lean_errors=0)
    assert lb.score("ovh:junk", "prove") < lb.score("ovh:tries", "prove") < lb.score("ovh:unknown", "prove")
    b, why = lb.bonus("ovh:junk", "prove")
    assert b < -0.1 and why
