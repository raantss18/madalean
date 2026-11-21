"""Session S-U: providers hub (cards, enable/disable), Internet search (Tavily, Exa, Brave, Wikipedia fallback), the new
keyed model providers (SambaNova, NVIDIA NIM), Leanstral as a Lean specialist with its tool aliases, task hints
(Sage code → code models, LaTeX → writing models). Fake servers only, no network.

Wire formats follow the providers' docs checked on 2026-11-22 (docs/PROVIDERS.md): Tavily POST /search with
`Authorization: Bearer`, errors 401 / 429 / 432; Exa POST /search with `x-api-key`, 402 when out of credit,
`costDollars.total`; Brave GET /res/v1/web/search with `X-Subscription-Token`; MediaWiki `list=search`."""
from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp import web

from madalean.brain import classify, hub, websearch
from madalean.brain.catalogue import KEYED, family_quality, lean_quality, Model
from madalean.brain.websearch import SearchError, WebSearch
from test_brain_fakes import FakeServer, free_provider, make_brain, model, oa_stream, run, write_catalogue
from helpers import make_ctx, running, session

TAVILY_KEY = "tvly-test-0123456789abcdef"
EXA_KEY = "exa-test-0123456789abcdef"
BRAVE_KEY = "BSA-test-0123456789abcdef"


class FakeSearch:
    """One loopback server answering as Tavily (/tavily), Exa (/exa), Brave (/brave) and MediaWiki (/wiki)."""

    def __init__(self):
        self.requests: list[dict] = []
        self.status: dict[str, int] = {}          # path → forced HTTP status
        self.port = 0
        self.runner = None

    def url(self, name: str) -> str:
        return f"http://127.0.0.1:{self.port}/{name}"

    async def start(self) -> "FakeSearch":
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

    async def handle(self, req: web.Request) -> web.Response:
        raw = await req.read()
        body = json.loads(raw) if raw else None
        name = req.path.strip("/")
        self.requests.append({"name": name, "method": req.method, "headers": dict(req.headers), "body": body,
                              "query": dict(req.query)})
        if name in self.status:
            return web.json_response({"detail": {"error": "forced"}}, status=self.status[name])
        if name == "tavily":
            return web.json_response({"query": body["query"], "results": [
                {"title": "Pythagorean theorem", "url": "https://en.wikipedia.org/wiki/Pythagorean_theorem",
                 "content": "In mathematics, the Pythagorean theorem…", "score": 0.9},
                {"title": "insecure", "url": "http://example.org/x", "content": "dropped (not https)"}]})
        if name == "exa":
            return web.json_response({"requestId": "r1", "costDollars": {"total": 0.005}, "results": [
                {"title": "Exa hit", "url": "https://arxiv.org/abs/1234.5678", "highlights": ["a", "b"],
                 "publishedDate": "2026-01-01"}]})
        if name == "brave":
            return web.json_response({"web": {"results": [
                {"title": "<strong>Brave</strong> hit", "url": "https://mathworld.wolfram.com/x.html",
                 "description": "desc &amp; <em>more</em>"}]}})
        if name == "wiki":
            return web.json_response({"batchcomplete": True, "query": {"search": [
                {"title": "Fermat's Last Theorem", "snippet": "<span class=\"searchmatch\">Fermat</span> …"}]}})
        return web.json_response({}, status=404)


def _ws(srv: FakeSearch, keys: dict, **settings) -> WebSearch:
    eps = {"tavily": srv.url("tavily"), "exa": srv.url("exa"), "brave": srv.url("brave"), "wikipedia": srv.url("wiki")}
    st = {"mode": "auto", "web_search": True, "providers_disabled": [], **settings}
    return WebSearch(lambda p: keys.get(p), lambda: st, endpoints=eps)


# ---------------------------------------------------------------- web search
def test_tavily_wire_format_results_and_usage(tmp_path):
    async def go():
        srv = await FakeSearch().start()
        ws = _ws(srv, {"tavily": TAVILY_KEY})
        ws.usage = websearch.Usage(tmp_path / "u.json")
        try:
            res = await ws.search("Pythagorean theorem proof", 3)
        finally:
            await ws.close()
            await srv.stop()
        r = srv.requests[0]
        assert r["method"] == "POST" and r["headers"]["Authorization"] == f"Bearer {TAVILY_KEY}"
        assert r["body"] == {"query": "Pythagorean theorem proof", "max_results": 3, "search_depth": "basic",
                             "include_answer": False}
        assert "Madalean/2.0" in r["headers"]["User-Agent"]
        assert res["provider"] == "tavily" and [x["url"] for x in res["results"]] == [
            "https://en.wikipedia.org/wiki/Pythagorean_theorem"]          # http:// result dropped
        assert res["results"][0]["n"] == 1 and res["results"][0]["source"] == "Tavily"
        assert ws.usage.of("tavily") == {"units": 1.0, "searches": 1}
        assert TAVILY_KEY not in (tmp_path / "u.json").read_text() and "Pythagorean" not in (tmp_path / "u.json").read_text()
    run(go())


@pytest.mark.parametrize("status,kind", [(401, "key_refused"), (432, "quota"), (433, "quota"), (429, "rate_limit")])
def test_tavily_errors_fall_back_to_exa(status, kind):
    async def go():
        srv = await FakeSearch().start()
        srv.status["tavily"] = status
        ws = _ws(srv, {"tavily": TAVILY_KEY, "exa": EXA_KEY})
        try:
            res = await ws.search("modular forms", 2)
        finally:
            await ws.close()
            await srv.stop()
        assert res["tried"] == [{"provider": "tavily", "error": kind}]
        assert res["provider"] == "exa" and res["results"][0]["url"] == "https://arxiv.org/abs/1234.5678"
        exa = [r for r in srv.requests if r["name"] == "exa"][0]
        assert exa["headers"]["x-api-key"] == EXA_KEY and "Authorization" not in exa["headers"]
        assert exa["body"]["type"] == "lite" and exa["body"]["numResults"] == 2
        assert TAVILY_KEY not in json.dumps(exa["headers"])                # one key, one host
        assert ws.usage.of("exa")["units"] == pytest.approx(0.005)       # costDollars counted
    run(go())


def test_exa_402_brave_then_wikipedia_keyless():
    async def go():
        srv = await FakeSearch().start()
        srv.status["exa"] = 402
        ws = _ws(srv, {"exa": EXA_KEY, "brave": BRAVE_KEY})
        try:
            res = await ws.search("Fermat", 2)
            srv.status["brave"] = 401
            res2 = await ws.search("Fermat", 2, lang="fr")
        finally:
            await ws.close()
            await srv.stop()
        assert res["provider"] == "brave" and res["tried"] == [{"provider": "exa", "error": "quota"}]
        b = [r for r in srv.requests if r["name"] == "brave"][0]
        assert b["method"] == "GET" and b["headers"]["X-Subscription-Token"] == BRAVE_KEY
        assert b["query"] == {"q": "Fermat", "count": "2"}
        assert res["results"][0]["title"] == "Brave hit" and res["results"][0]["snippet"] == "desc & more"
        assert res2["provider"] == "wikipedia"
        w = [r for r in srv.requests if r["name"] == "wiki"][0]
        assert "Authorization" not in w["headers"] and "X-Subscription-Token" not in w["headers"]
        assert w["query"]["list"] == "search" and w["query"]["srsearch"] == "Fermat"
        assert res2["results"][0]["url"] == "https://fr.wikipedia.org/wiki/Fermat's_Last_Theorem"
        assert res2["results"][0]["snippet"] == "Fermat …"
    run(go())


def test_local_mode_and_disabled_never_connect():
    async def go():
        srv = await FakeSearch().start()
        try:
            for st, kind in (({"mode": "local"}, "local_mode"), ({"web_search": False}, "disabled")):
                ws = _ws(srv, {"tavily": TAVILY_KEY}, **st)
                with pytest.raises(SearchError) as e:
                    await ws.search("anything")
                assert e.value.kind == kind
                await ws.close()
            ws = _ws(srv, {"tavily": TAVILY_KEY})
            with pytest.raises(SearchError) as e:
                await ws.search("anything", mode="local")         # the call's mode alone is enough
            assert e.value.kind == "local_mode"
            ws2 = _ws(srv, {"tavily": TAVILY_KEY}, providers_disabled=["tavily", "wikipedia"])
            assert ws2.order() == []
            await ws.close()
            await ws2.close()
        finally:
            await srv.stop()
        assert srv.requests == []
    run(go())


def test_key_is_never_sent_to_another_host():
    async def go():
        srv = await FakeSearch().start()
        ws = _ws(srv, {"tavily": TAVILY_KEY})
        ws.endpoints["tavily"] = f"http://localhost:{srv.port}/tavily"    # re-bound AFTER the key hosts were fixed
        try:
            res = await ws.search("x", 1)
        finally:
            await ws.close()
            await srv.stop()
        assert res["provider"] == "wikipedia" and res["tried"][0]["provider"] == "tavily"
        assert not any(TAVILY_KEY in json.dumps(r["headers"]) for r in srv.requests)
    run(go())


def test_search_tool_cites_urls_and_key_test():
    async def go():
        srv = await FakeSearch().start()
        ws = _ws(srv, {"tavily": TAVILY_KEY})
        try:
            tool = websearch.tool_spec(ws)
            text = await tool.run({"query": "Pythagoras"})
            t_ok = await ws.test("tavily")
            srv.status["tavily"] = 401
            t_bad = await ws.test("tavily")
            t_none = await ws.test("exa")
        finally:
            await ws.close()
            await srv.stop()
        assert tool.name == "web_search" and tool.parameters["required"] == ["query"]
        assert "[1] Pythagorean theorem — https://en.wikipedia.org/wiki/Pythagorean_theorem" in text
        assert t_ok["ok"] is True and t_bad == {"ok": False, "reason": "key_refused", "status": 401}
        assert t_none == {"ok": False, "reason": "no_key"}
    run(go())


# ---------------------------------------------------------------- catalogue: new providers, Leanstral, task hints
def test_new_keyed_providers_and_families():
    ids = {p.id: p for p in KEYED}
    assert ids["sambanova"].base_url == "https://api.sambanova.ai/v1" and not ids["sambanova"].paid
    assert ids["nvidia"].base_url == "https://integrate.api.nvidia.com/v1" and not ids["nvidia"].paid
    q, why = family_quality("labs-leanstral-1-5")
    leanstral = Model("mistral", "labs-leanstral-1-5", "Leanstral", quality=q)
    gpt = Model("groq", "openai/gpt-oss-120b", "gpt-oss", quality=family_quality("openai/gpt-oss-120b")[0])
    assert "Leanstral" in why and lean_quality(leanstral) >= 0.99 > lean_quality(gpt)
    coder = family_quality("@cf/qwen/qwen2.5-coder-32b-instruct")[0]
    assert coder["code"] > coder["writing"]


def test_hub_cards_are_complete_and_starter_has_keys():
    cards = {c["id"]: c for c in hub.cards()}
    groups = {g for g, _fr, _en in hub.GROUPS}
    assert list(cards)[0] == "leanstral" and cards["leanstral"]["group"] == "lean"
    for c in cards.values():
        assert c["group"] in groups and c["checked"] == hub.CHECKED
        for f in ("good_for", "free_tier", "privacy"):
            assert c[f]["fr"] and c[f]["en"], (c["id"], f)
        if c["key"]:
            assert c["key_url"].startswith("https://"), c["id"]
    for s in hub.STARTER:
        assert cards[s]["key"] and cards[s]["price"] in ("free", "free_tier")
    assert cards["github-models"]["integrated"] == "retired" and cards["aristotle"]["integrated"] == "no"


def _keyed(pid: str) -> dict:
    from dataclasses import asdict
    return asdict(next(p for p in KEYED if p.id == pid))


def _mistral_brain(tmp_path, srv, **kw):
    write_catalogue(tmp_path, [_keyed("mistral")], [model("mistral", "labs-leanstral-1-5"), model("mistral", "mistral-small-latest"),
                                   model("mistral", "codestral-latest")])
    return make_brain(tmp_path, keys={"mistral": "mistral-test-key-0123456789"}, endpoints={"mistral": srv.url}, **kw)


def test_leanstral_leads_prove_and_disabled_provider_vanishes(tmp_path):
    async def go():
        srv = await FakeServer([oa_stream("ok")]).start()
        b = _mistral_brain(tmp_path, srv)
        try:
            pool = [r.key for r in b.pool("prove", "online")]
            assert pool[0] == "mistral:labs-leanstral-1-5"
            with classify.task("sage"):
                code_first = b.ranking("explain", "online")[0].model.key
            assert code_first == "mistral:codestral-latest"
            b.update_settings({"providers_disabled": ["mistral"]})
            assert b.key("mistral") is None and not [r for r in b.pool("prove", "online") if r.provider == "mistral"]
        finally:
            await b.close()
            await srv.stop()
    run(go())


def test_keyless_switch_turns_off_every_keyless_provider(tmp_path):
    write_catalogue(tmp_path, [free_provider("llm7", "http://127.0.0.1:9/v1"), free_provider("kilo", "http://127.0.0.1:9/v1")],
                    [model("llm7", "a-70b"), model("kilo", "b-70b")])
    b = make_brain(tmp_path, providers_disabled=["keyless"])
    assert b.pool("explain", "online") == []
    b.update_settings({"providers_disabled": []})
    assert len(b.pool("explain", "online")) == 2


def test_leanstral_agent_uses_lean_run_code_alias(tmp_path):
    from madalean.brain.prover_agent import prove_with_agent
    stmt = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"
    code = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"
    checked: list[str] = []

    async def check(c: str) -> dict:
        checked.append(c)
        good = "Even.add" in c
        return {"ok": good, "feedback": "" if good else "error", "verdict": {"ok": good}}

    async def go():
        srv = await FakeServer([oa_stream(tool_calls=[("c1", "lean_run_code", {"code": code})]),
                                oa_stream(tool_calls=[("c2", "submit", {"code": code})])]).start()
        b = _mistral_brain(tmp_path, srv)
        try:
            out = await prove_with_agent(b, None, statement=stmt, workspace_key="demo", check=check, mode="online",
                                         only="mistral:labs-leanstral-1-5", max_steps=4, max_seconds=60)
        finally:
            await b.close()
            await srv.stop()
        first = srv.requests[0].body
        names = [t["function"]["name"] for t in first["tools"]]
        assert first["model"] == "labs-leanstral-1-5" and "lean_run_code" in names and "lean_check" in names
        assert srv.requests[0].headers["Authorization"] == "Bearer mistral-test-key-0123456789"
        assert out["finish"] == "proved" and "Even.add" in out["code"] and checked
    run(go())


@pytest.mark.parametrize("status,reason", [(401, "key_refused"), (429, "rate_limit"), (402, None)])
def test_sambanova_errors(tmp_path, status, reason):
    async def go():
        srv = await FakeServer([{"status": status, "body": {"error": {"message": "nope"}},
                                 "headers": {"Retry-After": "30"} if status == 429 else None}]).start()
        write_catalogue(tmp_path, [_keyed("sambanova")], [model("sambanova", "gpt-oss-120b")])
        b = make_brain(tmp_path, keys={"sambanova": "samba-key-0123456789"}, endpoints={"sambanova": srv.url})
        try:
            with pytest.raises(Exception):
                await b.complete("explain", [{"role": "user", "content": "hi"}], mode="online",
                                 prefer="sambanova:gpt-oss-120b")
            paused = b.states.pause_of("sambanova:gpt-oss-120b")
        finally:
            await b.close()
            await srv.stop()
        assert srv.requests[0].headers["Authorization"] == "Bearer samba-key-0123456789"
        assert paused, status
        if reason == "key_refused":
            assert b.last_error.get("sambanova") == "key_refused"
        if reason == "rate_limit":
            assert b.last_error.get("sambanova") == "rate_limit"
    run(go())


# ---------------------------------------------------------------- server routes
def test_providers_and_search_routes(tmp_path):
    async def go():
        srv = await FakeSearch().start()
        ctx = make_ctx(tmp_path)
        ctx._search_endpoints = {"tavily": srv.url("tavily"), "exa": srv.url("exa"), "brave": srv.url("brave"),
                                 "wikipedia": srv.url("wiki")}
        try:
            async with running(ctx) as (_srv, local, _remote):
                async with session() as s:
                    async with s.post(local + "/api/models/keys", json={"provider": "tavily", "key": TAVILY_KEY}) as r:
                        assert r.status == 200
                    async with s.get(local + "/api/providers") as r:
                        body = await r.json()
                    cards = {c["id"]: c for c in body["cards"]}
                    assert body["starter"] == hub.STARTER and body["checked"] == hub.CHECKED
                    assert cards["tavily"]["key_set"] is True and cards["exa"]["key_set"] is False
                    assert cards["tavily"]["usage"]["free_month"] == 1000 and TAVILY_KEY not in json.dumps(body)
                    async with s.patch(local + "/api/settings", json={"mode": "local"}) as r:
                        assert r.status == 200
                    async with s.post(local + "/api/search/web", json={"query": "Pythagoras"}) as r:
                        assert r.status == 409 and (await r.json())["error"] == "local_mode"
                    assert srv.requests == []
                    async with s.patch(local + "/api/settings", json={"mode": "auto"}) as r:
                        assert r.status == 200
                    async with s.post(local + "/api/search/web", json={"query": "Pythagoras", "k": 2}) as r:
                        res = await r.json()
                    assert r.status == 200 and res["provider"] == "tavily" and res["results"][0]["n"] == 1
                    async with s.post(local + "/api/search/test", json={"provider": "tavily"}) as r:
                        assert (await r.json())["ok"] is True
                    async with s.patch(local + "/api/settings", json={"providers_disabled": ["tavily"]}) as r:
                        assert r.status == 200
                    async with s.get(local + "/api/providers") as r:
                        assert {c["id"]: c for c in (await r.json())["cards"]}["tavily"]["disabled"] is True
                    async with s.post(local + "/api/search/web", json={"query": "Pythagoras"}) as r:
                        assert (await r.json())["provider"] == "wikipedia"
        finally:
            await srv.stop()
    run(go())
