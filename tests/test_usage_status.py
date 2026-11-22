"""S-AK (D43): token tally of every model call and the status panel endpoint GET /api/usage."""
from __future__ import annotations

import json
import time

from madalean.brain import usage
from madalean.slots import CURRENT_JOB
from helpers import make_ctx, running, session, wait_idle

PROBLEM = "La somme de deux entiers pairs est paire."


def test_tally_days_scopes_and_persistence(tmp_path):
    t = usage.Tally()
    t.attach(tmp_path / "u.json")
    now = time.time()
    tok = CURRENT_JOB.set("job_a")
    try:
        t.record("groq", "llama", 100, 20, when=now)
        t.record("anthropic", "claude-sonnet-4-5", 1000, 200, usd=0.01, when=now)
    finally:
        CURRENT_JOB.reset(tok)
    t.record("local", "qwen.gguf", 50, 5, when=now)                   # outside any request
    t.record("groq", "llama", 7, 7, when=now - 40 * 86400)            # an older month: not in today / month
    s = t.summary(["job_a", "nope"], now=now)
    assert s["today"] == {"tokens_in": 1150, "tokens_out": 225, "calls": 3, "usd": 0.01}
    assert s["month"]["calls"] == 3
    assert set(s["by_provider_today"]) == {"groq", "anthropic", "local"}
    assert s["requests"]["job_a"]["tokens_in"] == 1100 and s["requests"]["job_a"]["calls"] == 2
    assert s["requests"]["job_a"]["models"] == ["groq:llama", "anthropic:claude-sonnet-4-5"]
    assert "nope" not in s["requests"]
    t.flush()
    days = json.loads((tmp_path / "u.json").read_text())["days"]
    assert len(days) == 2
    t2 = usage.Tally()
    t2.attach(tmp_path / "u.json")
    assert t2.summary(now=now)["today"]["calls"] == 3
    usage.record("x", "y", "not a number", 1)                       # never raises


async def test_usage_endpoint_counts_a_request(tmp_path):
    ctx = make_ctx(tmp_path, delay=0.001)
    async with running(ctx) as (_srv, local, _remote):
        async with session() as s:
            async with s.get(local + "/api/usage") as r:
                assert r.status == 200
                first = await r.json()
            assert first["mode"] == ctx.settings.mode
            assert set(first["resources"]) >= {"cpu_percent", "memory", "gpu", "cpus"}
            assert first["tokens"]["today"]["calls"] == 0
            assert set(first["spend"]) == {"today_usd", "month_usd", "cap_month_usd", "cap_request_usd"}
            async with s.post(local + "/api/dossiers", json={"problem": PROBLEM}) as r:
                jid = (await r.json())["job"]["id"]
            await wait_idle(ctx)
            async with s.get(local + f"/api/usage?requests={jid},bad id,../x") as r:
                after = await r.json()
            assert after["tokens"]["today"]["calls"] > 0
            assert after["tokens"]["today"]["tokens_out"] > 0
            assert list(after["requests"]) == [jid]
            assert after["requests"][jid]["calls"] > 0
            mem = after["resources"]["memory"]
            assert mem is None or 0 < mem["used_mb"] <= mem["total_mb"]
            cpu = after["resources"]["cpu_percent"]
            assert cpu is None or 0 <= cpu <= 100
    assert (tmp_path / "config" / "model-usage.json").exists()
