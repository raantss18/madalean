"""S-AB (DECISIONS D35): the interactive transcription path of the brain — latency-aware ranking, staggered
parallel start (« race »), minimal thinking, short timeouts, its own pool of simultaneous requests."""
import asyncio
import time

from madalean.brain import classify, engine
from madalean.brain.router import latency_bonus
from madalean.brain.catalogue import Model
from test_brain_fakes import FakeServer, free_provider, make_brain, model, oa_chunk, oa_stream, run, write_catalogue


def slow(text: str, delay: float) -> dict:
    s = oa_stream(text)
    return {"events": [delay] + s["events"]}


def test_latency_is_learned_and_ranks_fast_models_first_for_transcription(tmp_path):
    write_catalogue(tmp_path, [free_provider("a", "http://127.0.0.1:9/v1"), free_provider("b", "http://127.0.0.1:9/v1")],
                    [model("a", "big", 0.9), model("b", "quick", 0.7)])
    b = make_brain(tmp_path)
    try:
        with classify.task("transcribe"):
            assert [c.model.key for c in b.ranking("assistant", "online")][:2] == ["a:big", "b:quick"]
            for _ in range(3):
                b.states.record_latency("a:big", 9.0)
                b.states.record_latency("b:quick", 0.8)
            order = b.ranking("assistant", "online")
            assert [c.model.key for c in order][:2] == ["b:quick", "a:big"]
            assert "measured 0.8 s to first text +0.20" in order[0].why
        # other roles are unchanged by the latency (quality first)
        assert b.ranking("explain", "online")[0].model.key == "a:big"
        # moving average: a model that became slow drops within a few calls
        for _ in range(4):
            b.states.record_latency("b:quick", 20.0)
        assert b.states.latency("b:quick") > 10
    finally:
        run(b.close())
    assert latency_bonus(None, Model("g", "gemini-3.1-pro-preview", "x"))[0] < 0
    assert latency_bonus(None, Model("g", "gemini-3.5-flash-lite", "x"))[0] > 0
    assert latency_bonus(30.0, Model("g", "x", "x"))[0] == -0.30


def test_race_starts_the_next_model_when_the_first_is_slow_and_cancels_the_loser(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "HEDGE_AFTER", 0.3)

    async def main():
        s1 = await FakeServer([slow("```sage\nslow\n```", 3.0)]).start()
        s2 = await FakeServer([oa_stream("```sage\nfast\n```")]).start()
        write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                        [model("f1", "m-best", 0.9), model("f2", "m-second", 0.5)])
        b = make_brain(tmp_path)
        seen = []
        t0 = time.monotonic()
        try:
            with classify.task("transcribe"):
                c = await b.complete("assistant", [{"role": "user", "content": "x"}], on_chunk=seen.append)
            took = time.monotonic() - t0
        finally:
            await b.close()
            await s1.stop()
            await s2.stop()
        assert c.text == "```sage\nfast\n```" and c.model.key == "f2:m-second" and took < 2.5
        assert "".join(x.text for x in seen if x.kind == "text") == c.text          # only the winner was streamed
        assert len(s1.requests) == 1 and len(s2.requests) == 1
        assert b.states.latency("f2:m-second") is not None and b.states.latency("f1:m-best") is None
        assert b.states.pause_of("f1:m-best") is None              # a cancelled racer is not a failure
    run(main())


def test_race_failure_starts_next_immediately_and_brainerror_when_all_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "HEDGE_AFTER", 5.0)

    async def main():
        s1 = await FakeServer([{"status": 429, "body": {"error": {"message": "Rate limit"}}}]).start()
        s2 = await FakeServer([oa_stream("```sage\nok\n```")]).start()
        write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                        [model("f1", "m-best", 0.9), model("f2", "m-second", 0.5)])
        b = make_brain(tmp_path)
        t0 = time.monotonic()
        try:
            with classify.task("transcribe"):
                c = await b.complete("assistant", [{"role": "user", "content": "x"}])
                assert c.model.key == "f2:m-second" and time.monotonic() - t0 < 2.0
                assert c.fallbacks and c.fallbacks[0].startswith("f1:m-best: HTTP 429")
        finally:
            await b.close()
            await s1.stop()
            await s2.stop()
    run(main())


def test_transcription_sends_minimal_effort_short_timeouts_and_skips_the_shared_pool(tmp_path, monkeypatch):
    async def main():
        def answer(body):
            if body.get("reasoning_effort") == "minimal":
                return {"status": 400, "body": {"error": {"message": "Request contains an invalid argument."}}}
            return oa_stream("```sage\n1\n```")
        s = await FakeServer([answer]).start()
        b = make_brain(tmp_path, endpoints={"gemini": s.url}, keys={"gemini": "AIza-TEST"})
        seen = {}
        real = engine.openai_compat.stream_chat

        async def spy(*a, **kw):
            seen.update(first=kw["first_byte"], stall=kw["stall"], effort=(kw.get("extra") or {}).get("reasoning_effort"))
            return await real(*a, **kw)
        monkeypatch.setattr(engine.openai_compat, "stream_chat", spy)
        try:
            sem = b.sem()
            for _ in range(3):                       # the shared pool is full (a dossier's long calls)…
                await sem.acquire()
            with classify.task("transcribe"):
                res = await asyncio.wait_for(b._generate(Model("gemini", "gemini-3.5-flash-lite", "x"), "assistant",
                                                         mode="auto", messages=[{"role": "user", "content": "x"}]), 5)
        finally:
            await b.close()
            await s.stop()
        assert res.text == "```sage\n1\n```"                          # …the transcription did not wait for it
        assert seen == {"first": engine.FAST_FIRST_BYTE, "stall": min(5.0, engine.FAST_STALL), "effort": "minimal"}
        # « invalid argument » on minimal: retried once with « low »
        assert [r.body.get("reasoning_effort") for r in s.requests] == ["minimal", "low"]
    run(main())


def test_race_streams_the_leader_and_replaces_it_when_it_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "HEDGE_AFTER", 0.2)

    async def main():
        broken = {"events": [oa_chunk({"content": "```sage\npart"}), 0.6,
                             'data: {"error": {"message": "overloaded"}}\n\n']}
        s1 = await FakeServer([broken]).start()
        s2 = await FakeServer([slow("```sage\nwhole\n```", 1.0)]).start()
        write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                        [model("f1", "m-best", 0.9), model("f2", "m-second", 0.5)])
        b = make_brain(tmp_path)
        seen = []
        try:
            with classify.task("transcribe"):
                c = await b.complete("assistant", [{"role": "user", "content": "x"}], on_chunk=seen.append)
        finally:
            await b.close()
            await s1.stop()
            await s2.stop()
        assert c.model.key == "f2:m-second"
        events = [(x.kind, x.data.get("event")) for x in seen if x.kind == "info"]
        assert ("info", "restart") in events
        after = seen[[i for i, x in enumerate(seen) if x.data.get("event") == "restart"][-1]:]
        assert "".join(x.text for x in after if x.kind == "text") == "```sage\nwhole\n```"
    run(main())


# ---------------------------------------------------------------- S-AF (D38): short text stages of a dossier
class _Local:
    """A local GPU model for every role (stands for Qwen3-8B on the user's GPU)."""
    def model_for(self, role):
        from madalean.brain.api import ModelRef
        return ModelRef("local", "Qwen3-8B-Q4_K_M.gguf", "Qwen3 8B", local=True)

    async def ensure(self, role):
        raise AssertionError("the local GPU model must not be used while an online model answers")

    def release(self):
        pass


def test_short_stages_rank_by_measured_latency_keep_quality_and_put_the_gpu_model_last(tmp_path):
    write_catalogue(tmp_path, [free_provider("a", "http://127.0.0.1:9/v1"), free_provider("b", "http://127.0.0.1:9/v1")],
                    [model("a", "big", 0.95), model("b", "quick", 0.5)])
    b = make_brain(tmp_path, local=_Local())
    try:
        for _ in range(3):
            b.states.record_latency("a:big", 9.0)
            b.states.record_latency("b:quick", 0.8)
        assert b.ranking("understand", "auto")[0].model.key == "a:big"        # outside a short stage: as before
        with classify.short_stage():
            order = [c.model.key for c in b.ranking("understand", "auto")]
            assert order[:2] == ["b:quick", "a:big"] and order[-1] == "local:Qwen3-8B-Q4_K_M.gguf"
            # writing (explanation, informal proof): the latency counts half, a much better writer stays first
            ex = b.ranking("explain", "auto")
            assert ex[0].model.key == "a:big" and "measured" in ex[0].why
            assert ex[-1].model.local
            assert classify.fast_task()
        assert not classify.fast_task()
    finally:
        run(b.close())


def test_short_stage_falls_to_the_next_online_model_never_the_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "HEDGE_AFTER", 5.0)

    async def main():
        s1 = await FakeServer([{"status": 503, "body": {"error": {"message": "overloaded"}}}]).start()
        s2 = await FakeServer([oa_stream("Une explication en français.")]).start()
        write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                        [model("f1", "m-best", 0.9), model("f2", "m-second", 0.5)])
        b = make_brain(tmp_path, local=_Local())
        try:
            with classify.short_stage():
                c = await b.complete("explain", [{"role": "user", "content": "Explique"}], mode="auto")
        finally:
            await b.close()
            await s1.stop()
            await s2.stop()
        assert c.model.key == "f2:m-second" and c.text == "Une explication en français."
    run(main())
