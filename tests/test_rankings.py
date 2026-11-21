"""Session S-V: « Classement » of the models (measured here + LMArena public signal + catalogue estimate), model news
(« Nouveau », disappeared, provider added), router bonus for new models, the cadence and local mode; plus the
« Composants suivis » overview (Lean, Mathlib, Sage, LaTeX). A fake datasets-server on loopback; no network."""
from __future__ import annotations

import json
import time

from aiohttp import web

from madalean import updates
from madalean.brain import rankings as rk
from madalean.brain.catalogue import Model
from madalean.brain.leaderboard import Leaderboard
from test_brain_fakes import free_provider, make_brain, model, run, write_catalogue


def _row(name, rating, rank, cat="math", org="x"):
    return {"row_idx": rank, "row": {"model_name": name, "organization": org, "rating": rating, "rank": float(rank),
                                     "category": cat, "leaderboard_publish_date": "2026-11-19"}, "truncated_cells": []}


# answers shaped like datasets-server.huggingface.co/filter on 2026-11-22
SLICES = {
    "math": [_row("Claude Opus 5.5 (High)", 1530.0, 1), _row("GLM-5.1", 1490.0, 2), _row("Claude Opus 5.5", 1500.0, 3),
             _row("Qwen3-Next-80B-A3B-Instruct", 1400.0, 4), _row("Other Model", 1300.0, 5)],
    "coding": [_row("GLM-5.1", 1450.0, 1, "coding"), _row("Other Model", 1350.0, 2, "coding")],
    "overall": [_row("GLM-5.1", 1480.0, 1, "overall")],
}


class FakeArena:
    def __init__(self, fail: bool = False):
        self.requests: list[dict] = []
        self.fail = fail
        self.port = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/filter"

    async def start(self):
        app = web.Application()
        app.router.add_get("/filter", self.handle)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        await self.runner.cleanup()

    async def handle(self, req):
        q = dict(req.query)
        self.requests.append(q)
        if self.fail:
            return web.Response(status=502, text="bad gateway")
        cat = q["where"].split("'")[1]
        rows = SLICES.get(cat, [])
        return web.json_response({"features": [], "rows": rows, "num_rows_total": 408, "partial": False})


# ---------------------------------------------------------------- pure functions
def test_slug_matches_catalogue_ids_exactly():
    assert rk.slug("Claude Opus 5.5 (High)") == rk.slug("claude-opus-5-5") == "claude-opus-5-5"
    assert rk.slug("GLM-5.1") == rk.slug("z-ai/glm-5.1:free") == "glm-5-1"
    assert rk.slug("Qwen3-Next-80B-A3B-Instruct") == rk.slug("qwen/qwen3-next-80b-a3b-instruct:free")
    assert rk.slug("Gemma 4 31B") == rk.slug("google/gemma-4-31b-it")
    # a preview or another size is another model: never merged
    assert rk.slug("Gemini 3.1 Pro Preview") != rk.slug("gemini-3.1-pro")
    assert rk.slug("Qwen3.8-27B") != rk.slug("qwen3.8-235b")


def test_parse_and_fold_conservative():
    rows = rk.parse_lmarena({"rows": SLICES["math"], "num_rows_total": 408})
    assert rows[0] == {"slug": "claude-opus-5-5", "name": "Claude Opus 5.5 (High)", "org": "x", "rating": 1530.0,
                       "rank": 1, "total": 408, "published": "2026-11-19"}
    f = rk.fold(rows)
    assert f["claude-opus-5-5"]["name"] == "Claude Opus 5.5"         # plain name preferred over the effort variant
    assert f["glm-5-1"]["pct"] == 0.5 and f["other-model"]["pct"] == 0.0
    assert rk.parse_lmarena(None) == [] and rk.parse_lmarena({"error": "x"}) == []
    assert rk.parse_lmarena({"rows": [{"row": {"model_name": "x", "rating": True}}]}) == []


def test_news_new_gone_provider_added(tmp_path):
    r = rk.Rankings(tmp_path / "r.json")
    a, b, c = Model("p", "a", "A"), Model("p", "b", "B"), Model("q", "c", "C")
    assert r.update_news([a, b]) == []                               # first snapshot: no artificial news
    assert not r.is_new("p:a")
    ev = r.update_news([a, Model("p", "d", "D"), c])
    kinds = {(e["kind"], e.get("key") or e.get("provider")) for e in ev}
    assert kinds == {("new", "p:d"), ("gone", "p:b"), ("provider_added", "q")}
    assert r.is_new("p:d") and not r.is_new("q:c")                   # a new key's models are not « new » one by one
    assert not r.is_new("p:d", at=time.time() + 15 * 86400)          # badge for NEW_DAYS days
    ev = r.update_news([a])                                          # provider q entirely missing: key removed / down
    assert [(e["kind"], e["key"]) for e in ev] == [("gone", "p:d")]
    r2 = rk.Rankings(tmp_path / "r.json")                            # persisted
    assert r2.events() and r2.news["snapshot"] == ["p:a"]
    assert len(json.loads((tmp_path / "r.json").read_text())["news"]["events"]) <= rk.MAX_EVENTS


def test_table_evidence_and_router_bonus(tmp_path):
    r = rk.Rankings(tmp_path / "r.json")
    r.public = {"fetched": time.time(), "slices": {k: rk.parse_lmarena({"rows": v, "num_rows_total": 408})
                                                   for k, v in SLICES.items()}}
    lb = Leaderboard(tmp_path / "lb.json")
    glm = Model("kilo", "z-ai/glm-5.1:free", "GLM 5.1", quality={"chat": 0.6, "math": 0.6})
    other = Model("kilo", "unknown-x", "X", quality={"chat": 0.5, "math": 0.5}, est="family Y")
    solid = Model("llm7", "solid", "Solid", quality={"chat": 0.4})
    for _ in range(8):
        lb.record("llm7:solid", "prove", ok=True)
    doms = {d["domain"]: d for d in rk.table(r, [glm, other, solid], lb)}
    assert set(doms) == set(rk.DOMAINS)
    lean = doms["lean"]["rows"]
    assert lean[0]["key"] == "llm7:solid" and lean[0]["evidence"] == "measured"
    g = next(x for x in lean if x["key"] == glm.key)
    pub = next(s for s in g["sources"] if s["kind"] == "public")
    assert g["evidence"] == "public" and pub["source"] == "LMArena" and pub["license"] == "CC BY 4.0"
    assert pub["rows"][0]["published"] == "2026-11-19" and pub["rows"][0]["rank"] == 2
    x = next(x for x in lean if x["key"] == other.key)
    assert x["evidence"] == "estimate" and not any(s["kind"] == "public" for s in x["sources"])
    # router: public percentile while nothing is measured here; nothing once measured
    b, why = r.router_bonus(glm, "formalize", lb)                     # math 50th pct, coding 1st → above the middle
    assert b > 0 and "LMArena math/coding" in why
    assert r.router_bonus(solid, "prove", lb) == (0.0, "")
    r.news = {"first_seen": {other.key: time.time()}}
    b, why = r.router_bonus(other, "prove", lb)
    assert b == rk.NEW_BONUS and "new model" in why


# ---------------------------------------------------------------- through the brain
def test_public_fetch_cadence_local_mode_and_view(tmp_path):
    async def main():
        arena = await FakeArena().start()
        cfg = tmp_path / "cfg"
        write_catalogue(cfg, [free_provider("kilo", "http://127.0.0.1:9/v1")],
                        [model("kilo", "z-ai/glm-5.1:free"), model("kilo", "plain-model")])
        b = make_brain(cfg, endpoints={"lmarena": arena.url})
        try:
            assert await b.refresh_public() is True
            assert len(arena.requests) == len(rk.SLICES)
            q = arena.requests[0]
            assert q["dataset"] == rk.LMARENA_DATASET and q["split"] == "latest" and q["length"] == "100"
            assert await b.refresh_public() is False                 # weekly: not due again
            assert await b.refresh_public(force=True) is True        # manual refresh
            assert await b.refresh_public(force=True) is False       # at most once an hour
            assert len(arena.requests) == 2 * len(rk.SLICES)
            v = b.rankings_view()
            assert v["public"]["published"] == "2026-11-19" and v["public"]["verified"] == rk.VERIFIED
            lean = next(d for d in v["domains"] if d["domain"] == "lean")
            assert lean["rows"][0]["key"] == "kilo:z-ai/glm-5.1:free"
            assert v["auto"] is False and v["next"]["public"] is None    # refresh_catalogue off in tests
            await b.tick()                                            # auto off: contacts nothing
            assert len(arena.requests) == 2 * len(rk.SLICES)
            b.update_settings({"mode": "local"})
            b.rankings.public["fetched"] = 0
            b.rankings.last_force = 0
            assert await b.refresh_public() is False and await b.refresh_public(force=True) is False
            assert len(arena.requests) == 2 * len(rk.SLICES)          # local mode never leaves the machine
        finally:
            await b.close()
            await arena.stop()
    run(main())


def test_public_fetch_failure_keeps_previous_data(tmp_path):
    async def main():
        arena = await FakeArena(fail=True).start()
        b = make_brain(tmp_path / "cfg", endpoints={"lmarena": arena.url})
        b.rankings.public = {"fetched": 1.0, "published": "2026-10-01", "slices": {"math": [{"slug": "a"}]}}
        try:
            assert await b.refresh_public() is False
            assert b.rankings.public["published"] == "2026-10-01" and b.rankings.public["error"] == "unreachable"
            assert b.rankings.public["slices"] == {"math": [{"slug": "a"}]}
        finally:
            await b.close()
            await arena.stop()
    run(main())


def test_router_tries_new_model(tmp_path):
    cfg = tmp_path / "cfg"
    write_catalogue(cfg, [free_provider("kilo", "http://127.0.0.1:9/v1")],
                    [model("kilo", "old-model", 0.6), model("kilo", "fresh-model", 0.58)])
    b = make_brain(cfg)
    try:
        b.rankings.news = {"first_seen": {"kilo:fresh-model": time.time()}}
        ranked = b._rank("prove", "auto", None, None, False, None)
        top = ranked[0]
        assert top.model.key == "kilo:fresh-model" and "new model" in top.why
    finally:
        run(b.close())


def test_rankings_api(tmp_path):
    from helpers import make_ctx, running, session, started

    async def main():
        ctx = await started(make_ctx(tmp_path))
        try:
            async with running(ctx) as (_srv, local, remote):
                async with session() as s:
                    async with s.get(local + "/api/models/rankings") as r:
                        assert r.status == 200
                        data = await r.json()
                    assert "domains" in data and "news" in data and "next" in data
                    async with s.post(local + "/api/models/rankings/refresh", json={}) as r:
                        assert r.status == 200
                    async with s.get(remote + "/api/models/rankings") as r:
                        assert r.status in (401, 403)                 # unpaired device
                    async with s.get(local + "/api/updates") as r:
                        body = await r.json()
                    tracked = (body.get("updates") or body).get("tracked")
                    assert tracked is None or {c["id"] for c in tracked["components"]} >= {"lean", "mathlib"}
        finally:
            await ctx.stop()
    run(main())


# ---------------------------------------------------------------- tracked components (Lean, Mathlib, Sage, LaTeX)
def test_tracked_overview(tmp_path):
    from madalean.update_checkers.overview import overview
    ws = tmp_path / "ws" / "lean-current"
    ws.mkdir(parents=True)
    (ws / "lean-toolchain").write_text("leanprover/lean4:v4.36.0\n")
    (ws / "lakefile.toml").write_text('[[require]]\nname = "mathlib"\nrev = "v4.36.0"\n')
    cands = [updates.Candidate("mathlib", "mathlib", "Lean + Mathlib v4.37.0", "v4.36.0", "v4.37.0"),
             updates.Candidate("lean-toolchain", "lean-toolchain", "Lean v4.37.0", "v4.36.0", "v4.37.0", False),
             updates.Candidate("deps-upstream", "deps-upstream:tex-bundle:tex-bundle", "tex-bundle v34", "v33",
                               "v34", False)]
    health = {"sage": {"version": "", "state": "on_demand", "pinned": "10.10"},
              "tex-bundle": {"version": "v33", "state": "ok", "pinned": "v33"}}
    t = time.time()
    o = overview({"t": t}, cands, ws_root=tmp_path / "ws", health_rows=health)
    by = {r["id"]: r for r in o["components"]}
    assert set(by) == {"lean", "mathlib", "sage", "latex", "tex-bundle"}
    assert by["lean"]["current"] == "v4.36.0" and by["lean"]["latest"] == "v4.37.0" and not by["lean"]["installable"]
    assert by["mathlib"] == {**by["mathlib"], "current": "v4.36.0", "latest": "v4.37.0", "pending": True,
                             "installable": True, "policy": "auto"}
    assert by["sage"]["state"] == "on_demand" and not by["sage"]["pending"] and by["sage"]["pinned"] == "10.10"
    assert by["tex-bundle"]["latest"] == "v34" and by["tex-bundle"]["policy"] == "auto_pin"
    assert o["last_check"] == t and o["next_check"] == t + updates.CHECK_EVERY_S
    assert overview({}, [], ws_root=tmp_path / "none", health_rows={})["next_check"] is None


def test_deps_are_installed_automatically_like_mathlib():
    from madalean.server.plugins import research_workshop as rw
    assert "deps" in rw.AUTO_KINDS and "deps-upstream" not in rw.AUTO_KINDS
