"""Session S-T (user decisions 2026-11-22): Hugging Face Inference Providers as a keyed paid provider, Goedel-Prover-V2
served online (pinned, Goedel's own prompts and sampling) leading the proof, the spending caps shared with Claude,
and local models only offline / when no online model could work (llama-server never started in normal online use).

A fake server mimics the HF Hub (model info with `inferenceProviderMapping`, whoami-v2) and the HF router
(OpenAI-compatible SSE, 401 body `{"error": "Invalid username or password."}` as the real router answers). No network."""
from __future__ import annotations

import asyncio
import dataclasses
import json

import pytest
from aiohttp import web

from madalean import leancheck
from madalean.brain import spend
from madalean.brain.api import BrainError, ModelRef
from madalean.brain.catalogue import hf_live_providers
from madalean.brain.net import Http, KeyHostError
from madalean.pipeline import runner
from madalean.server.routes_work import create_dossier
from test_brain_fakes import FakeServer, free_provider, make_brain, model, oa_stream, run, write_catalogue
from helpers import make_ctx, started, wait_idle

HF_KEY = "hf_test_0123456789abcdefghij"
G32 = "Goedel-LM/Goedel-Prover-V2-32B:featherless-ai"
G8 = "Goedel-LM/Goedel-Prover-V2-8B:featherless-ai"
STMT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"
GOEDEL_ANSWER = ("### Detailed Proof and Analysis\nBoth are even, so the sum is even.\n\n### Lean 4 Proof\n"
                 "```lean4\ntheorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n"
                 "  exact Even.add ha hb\n```")

# Hub answers as recorded on 2026-11-22 (GET /api/models/<repo>?expand[]=inferenceProviderMapping)
MAPPING = {
    "Goedel-LM/Goedel-Prover-V2-32B": {"featherless-ai": {"status": "live", "providerId": "Goedel-LM/Goedel-Prover-V2-32B",
                                                          "task": "conversational", "isModelAuthor": False}},
    "Goedel-LM/Goedel-Prover-V2-8B": {"featherless-ai": {"status": "live", "providerId": "Goedel-LM/Goedel-Prover-V2-8B",
                                                         "task": "conversational", "isModelAuthor": False},
                                      "other-provider": {"status": "staging", "task": "conversational"}},
    "Goedel-LM/Goedel-Formalizer-V2-32B": {},
    "Goedel-LM/Goedel-Formalizer-V2-8B": {},
}


class FakeHF:
    """Hub + router on one loopback port."""

    def __init__(self):
        self.requests: list[dict] = []
        self.chat: list = []           # scripted chat answers (dict as FakeServer items), last one repeats
        self.runner = None
        self.port = 0

    @property
    def hub(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def router(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    async def start(self) -> "FakeHF":
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.handle)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        await self.runner.cleanup()

    def _auth_ok(self, req) -> bool:
        return req.headers.get("Authorization") == f"Bearer {HF_KEY}"

    async def handle(self, req: web.Request) -> web.StreamResponse:
        raw = await req.read()
        body = json.loads(raw) if raw else None
        self.requests.append({"method": req.method, "path": req.path, "query": dict(req.query),
                              "auth": req.headers.get("Authorization"), "body": body})
        p = req.path
        if p == "/api/whoami-v2":
            if not self._auth_ok(req):
                return web.json_response({"error": "Invalid username or password."}, status=401)
            return web.json_response({"type": "user", "name": "tester", "auth": {"type": "access_token", "accessToken": {
                "displayName": "madalean", "role": "fineGrained",
                "fineGrained": {"global": ["inference.serverless.write"], "scoped": []}}}})
        if p.startswith("/api/models/"):
            repo = p.removeprefix("/api/models/")
            return web.json_response({"id": repo, "inferenceProviderMapping": MAPPING.get(repo, {})})
        if p.startswith("/v1/models/"):
            repo = p.removeprefix("/v1/models/")
            if not MAPPING.get(repo):
                return web.json_response({"error": "Chat completion model not found"}, status=404)
            return web.json_response({"data": {"id": repo, "providers": [
                {"provider": "featherless-ai", "status": "live", "is_free": False, "is_model_author": False}]}})
        if p == "/v1/chat/completions":
            if not self._auth_ok(req):
                return web.json_response({"error": "Invalid username or password."}, status=401)
            item = self.chat[0] if len(self.chat) == 1 else (self.chat.pop(0) if self.chat
                                                              else oa_stream(GOEDEL_ANSWER, usage=(900, 2500)))
            if "status" in item:
                return web.json_response(item.get("body", {"error": "error"}), status=item["status"])
            resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await resp.prepare(req)
            for ev in item["events"]:
                await resp.write(ev.encode())
            return resp
        return web.json_response({"error": "not found"}, status=404)


def hf_brain(tmp_path, srv: FakeHF, key: str | None = HF_KEY, local=None, extra_endpoints=None, **kw):
    ends = {"huggingface": srv.router, "huggingface_hub": srv.hub, **(extra_endpoints or {})}
    return make_brain(tmp_path / "cfg", keys={"huggingface": key} if key else {}, endpoints=ends, local=local, **kw)


# ---------------------------------------------------------------- key isolation
def test_hf_token_goes_only_to_the_two_hf_hosts(tmp_path):
    from madalean.brain import create_brain
    b = create_brain(tmp_path, None, lambda p: None, {"refresh_catalogue": False})
    hosts = b.http.key_hosts["huggingface"]
    assert hosts == {"router.huggingface.co", "huggingface.co"}
    h = b.http
    h.check("https://router.huggingface.co/v1/chat/completions", "online", "huggingface", HF_KEY)
    h.check("https://huggingface.co/api/whoami-v2", "online", "huggingface", HF_KEY)
    for url in ("https://huggingface.co.evil.example/api/whoami-v2", "https://api-inference.huggingface.co/x",
                "https://evil.example/?u=router.huggingface.co", "https://openrouter.ai/api/v1/chat/completions"):
        with pytest.raises(KeyHostError):
            h.check(url, "online", "huggingface", HF_KEY)
    with pytest.raises(KeyHostError):                     # another provider's key never goes to HF either
        h.check("https://router.huggingface.co/v1/chat/completions", "online", "anthropic", "sk-ant-x")
    with pytest.raises(KeyHostError):                     # nor the HF token to a single-host provider's host
        Http({"anthropic": "api.anthropic.com"}).check("https://huggingface.co/x", "online", "anthropic", "k")


def test_hub_mapping_parsing():
    assert hf_live_providers({"inferenceProviderMapping": MAPPING["Goedel-LM/Goedel-Prover-V2-8B"]}) == ["featherless-ai"]
    assert hf_live_providers({"inferenceProviderMapping": {}}) == []
    assert hf_live_providers({"inferenceProviderMapping": [   # listing shape
        {"provider": "featherless-ai", "status": "live", "task": "conversational"},
        {"provider": "x", "status": "error", "task": "conversational"}]}) == ["featherless-ai"]
    assert hf_live_providers(None) == []


# ---------------------------------------------------------------- discovery, refresh, key test
def test_refresh_lists_only_live_goedel_models_and_never_sends_the_token_to_discovery(tmp_path):
    async def go():
        srv = await FakeHF().start()
        try:
            b = hf_brain(tmp_path, srv)
            await b.refresh()
            view = [m for m in b._view().models if m.provider == "huggingface"]
            assert sorted(m.model_id for m in view) == sorted([G32, G8])          # no formalizer: no live provider
            assert all(m.paid and not m.tools for m in view)
            disc = [r for r in srv.requests if r["path"].startswith(("/api/models/", "/v1/models/"))]
            assert disc and all(r["auth"] is None for r in disc)                   # public API, keyless
            assert all(r["query"].get("expand[]") == "inferenceProviderMapping" for r in disc
                       if r["path"].startswith("/api/models/"))
            g = b.goedel_model("prove", "auto")
            assert g is not None and g.model_id == G32                             # the 32B first
            assert b.goedel_model("formalize", "auto") is None                     # absence handled
            assert b.goedel_model("prove", "local") is None
            # never in the general pool, never an agent, never another role
            for role in ("prove", "explain", "assistant", "understand"):
                assert not any(c.model.provider == "huggingface" for c in b.ranking(role, "online"))
            # …but shown first for prove (« qui reçoit quoi », « pourquoi ce modèle »)
            ex = b.explain("prove", "auto")
            assert ex[0]["model"] == "huggingface:" + G32 and "Hugging Face" in ex[0]["why"]
            assert b.candidates("prove", "auto")[0].key == "huggingface:" + G32
            st = await b.status()
            assert st["goedel_online"]["key"] == "huggingface:" + G32 and st["local_policy"] == "fallback"
            # without the token: nothing from HF is offered
            b2 = hf_brain(tmp_path / "nokey", srv, key=None)
            await b2.refresh()
            assert b2.goedel_model("prove") is None and not any(
                m.provider == "huggingface" for m in b2._view().models)
            await b.close()
            await b2.close()
        finally:
            await srv.stop()
    run(go())


def test_key_test_is_an_identity_check_without_inference(tmp_path):
    async def go():
        srv = await FakeHF().start()
        try:
            b = hf_brain(tmp_path, srv)
            r = await b.hf_check()
            assert r["ok"] is True and r["login"] == "tester" and r["models"] == 2 and r["warning"] == ""
            assert r["model"] == "huggingface:" + G32 and HF_KEY not in json.dumps(r)
            assert not any(x["path"] == "/v1/chat/completions" for x in srv.requests)   # nothing billed
            who = [x for x in srv.requests if x["path"] == "/api/whoami-v2"]
            assert who[0]["auth"] == f"Bearer {HF_KEY}"
            bad = hf_brain(tmp_path / "bad", srv, key="hf_wrong_token_xxxxxxxxxxxx")
            r = await bad.hf_check()
            assert r["ok"] is False and r["reason"] == "key_refused"
            await bad.refresh()
            await bad.hf_check()
            assert bad.goedel_model("prove") is None                                 # refused token: not offered
            await b.close()
            await bad.close()
        finally:
            await srv.stop()
    run(go())


# ---------------------------------------------------------------- wire, pinning, caps
def test_pinned_goedel_call_wire_format_usage_and_ledger(tmp_path):
    async def go():
        srv = await FakeHF().start()
        try:
            b = hf_brain(tmp_path, srv)
            await b.refresh()
            key = "huggingface:" + G32
            tok = spend.SPEND_SCOPE.set("d1:j1")
            chunks = []
            try:
                c = await b.complete("prove", [{"role": "user", "content": leancheck.initial_prompt(STMT)}],
                                     mode="auto", temperature=1.0, max_tokens=32000, extra={"top_p": 0.95},
                                     only=key, on_chunk=chunks.append)
            finally:
                spend.SPEND_SCOPE.reset(tok)
            assert c.model.key == key and "Even.add" in c.text
            req = [x for x in srv.requests if x["path"] == "/v1/chat/completions"][-1]
            assert req["auth"] == f"Bearer {HF_KEY}" and req["body"]["model"] == G32 and req["body"]["stream"] is True
            assert req["body"]["temperature"] == 1.0 and req["body"]["top_p"] == 0.95
            assert req["body"]["messages"][0]["content"] == leancheck.initial_prompt(STMT)
            assert 2048 <= req["body"]["max_tokens"] <= 32000
            row = b.ledger.rows[-1]
            assert row.model == key and row.scope == "d1:j1" and (row.tokens_in, row.tokens_out) == (900, 2500)
            assert abs(row.usd - (900 * spend.HF_ESTIMATE[0] + 2500 * spend.HF_ESTIMATE[1]) / 1e6) < 1e-9
            infos = [ch.data for ch in chunks if ch.kind == "info"]
            assert any(d.get("event") == "cost" and d.get("estimated_price") for d in infos)
            assert any(d.get("event") == "spent" for d in infos)
            # pinned: a refused token is never replaced by another model
            srv.chat = [{"status": 402, "body": {"error": "You have exceeded your monthly included credits"}}]
            n = len(srv.requests)
            with pytest.raises(BrainError):
                await b.complete("prove", [{"role": "user", "content": "x"}], mode="auto", only=key, max_tokens=4000)
            assert len([x for x in srv.requests[n:] if x["path"] == "/v1/chat/completions"]) == 1
            assert b.states.pause_of(key)[1] == "no_credit" and b.goedel_model("prove") is not None \
                and b.goedel_model("prove").model_id == G8          # the 32B is paused: the 8B online remains
            await b.close()
        finally:
            await srv.stop()
    run(go())


def test_caps_refuse_before_sending_and_month_cap_hides_goedel(tmp_path):
    async def go():
        srv = await FakeHF().start()
        try:
            b = hf_brain(tmp_path, srv, claude_cap_proof_usd=0.005)
            await b.refresh()
            tok = spend.SPEND_SCOPE.set("d2:j2")
            try:
                with pytest.raises(BrainError) as e:
                    await b.complete("prove", [{"role": "user", "content": leancheck.initial_prompt(STMT)}],
                                     mode="auto", only="huggingface:" + G32, max_tokens=32000)
            finally:
                spend.SPEND_SCOPE.reset(tok)
            assert "spending cap" in str(e.value)
            assert not any(x["path"] == "/v1/chat/completions" for x in srv.requests)   # nothing sent
            # the SAME monthly cap as Claude: once reached, Goedel online is not offered any more
            b.update_settings({"claude_cap_proof_usd": 1.0, "claude_cap_month_usd": 0.5})
            b.ledger.record("claude-opus-5-5", "", 100_000, 20_000)                       # 0.80 $ of Claude
            assert b.goedel_model("prove") is None
            await b.close()
        finally:
            await srv.stop()
    run(go())


# ---------------------------------------------------------------- local only offline / as the last fallback (engine)
class CountingLocal:
    """A LocalRuntime whose « llama-server » is a fake OpenAI server; counts the starts."""

    def __init__(self, url: str):
        self.url, self.ensured, self.released = url, 0, 0

    def model_for(self, role):
        return ModelRef("local", "Goedel-Prover-V2-8B.Q4_K_M", "Goedel 8B", local=True)

    async def ensure(self, role):
        self.ensured += 1
        return self.url

    def release(self):
        self.released += 1


def _free_catalogue(tmp_path, url):
    write_catalogue(tmp_path / "cfg", [free_provider("free", url)], [model("free", "m1", 0.7), model("free", "m2", 0.6)])


def test_auto_online_never_starts_the_local_model(tmp_path):
    async def go():
        free, loc = await FakeServer([oa_stream("OK")]).start(), await FakeServer([oa_stream("local OK")]).start()
        try:
            _free_catalogue(tmp_path, free.url)
            local = CountingLocal(loc.url)
            b = make_brain(tmp_path / "cfg", endpoints={}, local=local)
            for role in ("explain", "formalize", "prove"):
                c = await b.complete(role, [{"role": "user", "content": "hi"}], mode="auto")
                assert not c.model.local
            assert local.ensured == 0 and not loc.requests
            await b.close()
        finally:
            await free.stop()
            await loc.stop()
    run(go())


def test_offline_goes_straight_to_the_local_model(tmp_path):
    async def go():
        free, loc = await FakeServer([oa_stream("OK")]).start(), await FakeServer([oa_stream("local OK")]).start()
        try:
            _free_catalogue(tmp_path, free.url)
            local = CountingLocal(loc.url)
            b = make_brain(tmp_path / "cfg", endpoints={}, local=local, _offline=True)
            b.http.mark(False)                               # the probe said: no Internet (cached)
            c = await b.complete("explain", [{"role": "user", "content": "hi"}], mode="auto")
            assert c.model.local and local.ensured == 1 and not free.requests
            assert all("offline" in f for f in c.fallbacks)
            await b.close()
        finally:
            await free.stop()
            await loc.stop()
    run(go())


def test_every_online_model_failing_falls_back_to_local(tmp_path):
    async def go():
        free = await FakeServer([{"status": 500, "body": {"error": {"message": "boom"}}}]).start()
        loc = await FakeServer([oa_stream("local OK")]).start()
        try:
            _free_catalogue(tmp_path, free.url)
            local = CountingLocal(loc.url)
            b = make_brain(tmp_path / "cfg", endpoints={}, local=local)
            c = await b.complete("explain", [{"role": "user", "content": "hi"}], mode="auto")
            assert c.model.local and local.ensured == 1 and len(free.requests) >= 2
            # mode « online »: never the local model
            b2 = make_brain(tmp_path / "cfg", endpoints={}, local=local)
            with pytest.raises(BrainError):
                await b2.complete("explain", [{"role": "user", "content": "hi"}], mode="online")
            assert local.ensured == 1
            await b.close()
            await b2.close()
        finally:
            await free.stop()
            await loc.stop()
    run(go())


def test_provider_down_is_not_no_internet(tmp_path):
    async def go():
        dead = "http://127.0.0.1:9/v1"                       # nothing listens: connection refused
        ok = await FakeServer([oa_stream("OK")]).start()
        try:
            write_catalogue(tmp_path / "cfg", [free_provider("dead", dead), free_provider("free", ok.url)],
                            [model("dead", "d1", 0.9), model("dead", "d2", 0.85), model("free", "m1", 0.5)])
            b = make_brain(tmp_path / "cfg", endpoints={})
            c = await b.complete("explain", [{"role": "user", "content": "hi"}], mode="auto")
            assert c.model.key == "free:m1"
            assert any("provider unreachable" in f for f in c.fallbacks)
            assert any("skipped (provider unreachable)" in f for f in c.fallbacks)   # d2 not tried: no 2nd timeout
            st = await b.status()
            assert st["internet"] is True and next(p for p in st["providers"] if p["id"] == "dead")["down"] is True
            await b.close()
        finally:
            await ok.stop()
    run(go())


def test_probe_answers_fast_and_caches(tmp_path):
    async def go():
        import madalean.brain.net as net
        h = Http({})
        calls = []

        async def fake_open(host, port):
            calls.append(host)
            if host == "1.1.1.1":
                await asyncio.sleep(5)                       # a slow resolver does not delay the answer
            if host == "8.8.8.8":
                raise OSError("unreachable")

            class W:
                def close(self):
                    pass
            return None, W()
        orig = asyncio.open_connection
        asyncio.open_connection = fake_open
        try:
            t0 = asyncio.get_running_loop().time()
            assert await h.online() is True
            assert asyncio.get_running_loop().time() - t0 < 1.0
            n = len(calls)
            assert await h.online() is True and len(calls) == n          # cached
            h.mark(False)
            assert h.known_offline() and await h.online() is False       # offline cached (re-checked after 10 s)
            assert net.OFFLINE_TTL < net.PROBE_TTL
        finally:
            asyncio.open_connection = orig
    run(go())


# ---------------------------------------------------------------- pipeline (runner + tournament), fake brain
class HFBrain:
    """Wraps a FakeBrain: free online models (agent contestants), Goedel online (HF), reachability."""

    def __new__(cls, *, hf: bool = True, internet: bool = True, models=None):
        from test_tournament import PoolBrain
        b = PoolBrain()
        if models is not None:
            b.MODELS = models
        b.calls = []
        b._net = internet

        def goedel_online(role="prove", mode="auto"):
            if not hf or mode == "local" or role != "prove":
                return None
            return ModelRef("huggingface", G32, "Goedel-Prover-V2-32B (featherless-ai, Hugging Face)", paid=True)

        async def internet():
            return b._net
        inner = b.complete

        async def complete(role, messages, *, only=None, **kw):
            b.calls.append({"role": role, "only": only, "messages": [dict(m) for m in messages], **kw})
            c = await inner(role, messages, **kw)
            return dataclasses.replace(c, model=ModelRef("huggingface", G32, "G32", paid=True)) if only else c
        b.goedel_online, b.internet, b.complete = goedel_online, internet, complete
        b.caps = lambda: (1.0, 20.0)
        return b


async def _pipeline(tmp_path, monkeypatch, brain, mode="auto", strategy="auto"):
    from test_tournament import scripted_agent
    log: list = []
    monkeypatch.setattr(runner, "_agent_fn", lambda: scripted_agent(log))
    ctx = await started(make_ctx(tmp_path, brain=brain, lean_seconds=0.05))
    ctx.settings.mode = mode
    from madalean.pipeline.tournament import leaderboard_of
    brain.lb = leaderboard_of(ctx)
    d, _j = await create_dossier(ctx, {"statement": STMT, "start": False})
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy=strategy)
    await wait_idle(ctx, timeout=60)
    await ctx.stop()
    return ctx, d, job, log


async def test_pipeline_goedel_32b_online_leads_round_0_with_verbatim_prompts(tmp_path, monkeypatch):
    brain = HFBrain()
    ctx, d, job, log = await _pipeline(tmp_path, monkeypatch, brain)
    assert job.state == "done", (job.error, job.summary)
    assert d.proofs[-1].model == "huggingface:" + G32 and d.proofs[-1].meta["strategy"] == "goedel"
    assert log == []                                         # it won at once: no free agent ran
    pinned = [c for c in brain.calls if c["only"]]
    assert pinned and pinned[0]["only"] == "huggingface:" + G32
    first = pinned[0]
    assert first["messages"] == [{"role": "user", "content": leancheck.initial_prompt(leancheck.prepare_statement(d.statement))}]
    assert first["messages"][0]["content"].startswith("Complete the following Lean 4 code:\n\n```lean4\n")
    assert first["temperature"] == 1.0 and first["extra"] == {"top_p": 0.95} and first["mode"] == "online" \
        and 30000 < first["max_tokens"] <= 32768
    assert job.tournament["round"] == 0 and job.tournament["models"][0] == "huggingface:" + G32
    assert any("Goedel-Prover en ligne" in e.text for e in d.events)
    assert ctx.local.loads == 0                              # llama-server never started


async def test_pipeline_goedel_online_failing_then_free_models_never_local(tmp_path, monkeypatch):
    brain = HFBrain()
    brain.behaviour["fail_unless_hint"] = True               # Goedel's answers are refused by Lean
    from test_tournament import PoolBrain
    brain.MODELS = [m for m in PoolBrain.MODELS if m.model_id not in ("winner", "opus")]
    ctx, d, job, log = await _pipeline(tmp_path, monkeypatch, brain)
    assert job.state == "failed" and job.error == "no_proof"
    assert [c["only"] for c in brain.calls if c["only"]][:1] == ["huggingface:" + G32]
    assert log and "huggingface:" + G32 not in log           # free models raced after it, Goedel never as an agent
    assert ctx.local.loads == 0                              # online models ran: no local fallback


async def test_pipeline_offline_uses_the_local_prover(tmp_path, monkeypatch):
    brain = HFBrain(internet=False)
    ctx, d, job, log = await _pipeline(tmp_path, monkeypatch, brain)
    assert job.state == "done" and d.proofs[-1].model.startswith("local:"), (job.error, d.proofs[-1].model)
    assert log == [] and not any(c["only"] for c in brain.calls) and ctx.local.loads >= 1
    assert any("Pas d'accès à Internet" in e.text for e in d.events)


async def test_pipeline_all_online_unavailable_falls_back_to_local(tmp_path, monkeypatch):
    brain = HFBrain(hf=False, models=[ModelRef("free", "rate", "Rate-limited")])
    ctx, d, job, log = await _pipeline(tmp_path, monkeypatch, brain)
    assert job.state == "done" and d.proofs[-1].model.startswith("local:"), (job.error, job.summary)
    assert log and set(log) == {"free:rate"} and ctx.local.loads >= 1
    assert any("repli sur le modèle local" in e.text for e in d.events)


async def test_pipeline_online_mode_never_local(tmp_path, monkeypatch):
    brain = HFBrain(hf=False, models=[ModelRef("free", "rate", "Rate-limited")])
    ctx, d, job, log = await _pipeline(tmp_path, monkeypatch, brain, mode="online")
    assert job.state == "failed" and ctx.local.loads == 0
