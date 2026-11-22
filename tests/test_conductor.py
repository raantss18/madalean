"""S-AI (DECISIONS D41): the conductor — tool rule cards and prompt compaction, the Claude request shape (structured
output, thinking off, cache breakpoint), plan validation, data-driven choice of the conductor and of the worker
models, the fallback chain (429 / timeout / refusal / invalid JSON / no key), the request's cap and the « continue
with Claude? » question (yes / no), coherence with the monthly cap, the hook in the pipeline (plan, corrections,
final check, conductor off = pipeline unchanged, cancellation). Fakes only: no network."""
from __future__ import annotations

import asyncio
import json

import pytest

from madalean.brain import conductor as C
from madalean.brain import spend, toolcards
from madalean.brain.fake import FakeBrain
from madalean.brain.fake_conductor import ConductedFakeBrain, demo_conductor
from madalean.brain.providers import anthropic as A
from madalean.brain.providers.openai_compat import merge_stable
from madalean.pipeline import conductor_hook
from madalean.server.routes_work import create_dossier
from test_brain_fakes import FakeServer, an_stream, free_provider, make_brain, model, oa_stream, write_catalogue
from helpers import make_ctx, running, session, wait_idle

PROBLEM = "Montrer que la somme de deux entiers pairs est paire."
ANTHROPIC_KEY = "sk-ant-test-0123456789"


# ---------------------------------------------------------------- tool cards and compaction
def test_features_and_card_selection_per_task():
    f = toolcards.features_of("Montrer par récurrence que ∑ i ∈ Finset.range n, i = n*(n-1)/2")
    assert {"sum", "induction"} <= f and "plot" not in f
    c = toolcards.compact("formalize", f)
    assert "lean-induction" in c.selected and "lean-bigop" in c.selected and "lean-real" not in c.selected
    assert "sorry" in c.stable and "Tool rules" in c.stable           # Madalean conventions are core
    e = toolcards.compact("explain", f)
    assert "Lean 4 only" not in e.stable + e.request                    # the explainer gets no Lean syntax
    assert "induction" in e.request.lower()
    assert toolcards.compact("route", f).stable == ""                   # routing has no tool
    s = toolcards.compact("sage", toolcards.features_of("trace la courbe de sin"))
    assert "sage-plot" in s.selected and "sage-integral" not in s.selected


def test_stable_prefix_is_byte_identical_and_compaction_saves_tokens():
    a = toolcards.compact("formalize", toolcards.features_of("somme de deux entiers pairs"))
    b = toolcards.compact("formalize", toolcards.features_of("limite d'une suite réelle, dérivée de exp"))
    assert a.stable == b.stable and a.stable_hash == b.stable_hash and a.request != b.request
    for role in ("formalize", "explain", "plan", "fix_proof", "final"):
        c = toolcards.compact(role, toolcards.features_of(PROBLEM))
        assert c.tokens < c.tokens_all_cards and c.tokens <= c.tokens_full
        assert c.tokens_request <= toolcards.ROLE_BUDGET[role]
    # no volatile content (dates, times, ids) in the stable block
    import re
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}|[0-9a-f]{12}", a.stable)
    msgs, comp = toolcards.worker_messages([{"role": "user", "content": "x"}], "formalize", frozenset({"sum"}))
    assert msgs[0]["stable"] is True and msgs[0]["content"] == comp.stable and msgs[-1]["content"] == "x"


def test_dedup_across_cards():
    c = toolcards.compact("plan", frozenset({"induction", "ineq", "sum"}))
    texts = (c.stable + "\n" + c.request).split("\n- ")
    assert len(texts) == len(set(texts))


# ---------------------------------------------------------------- the Claude request
def test_request_shape_structured_output_thinking_and_cache():
    system, msgs = A.split_system([{"role": "system", "content": "STABLE", "stable": True},
                                   {"role": "system", "content": "VARIABLE"}, {"role": "user", "content": "q"}])
    assert system == [("STABLE", True), ("VARIABLE", False)]
    body, _h = A.build_body("claude-sonnet-5-5", system, msgs, max_tokens=100, tools=None, effort="low",
                            thinking=True, fallbacks=True, cache=True, output_format={"type": "json_schema",
                                                                                      "schema": C.FINAL_SCHEMA},
                            thinking_off=True)
    assert body["system"][0] == {"type": "text", "text": "STABLE", "cache_control": {"type": "ephemeral"}}
    assert "cache_control" not in body["system"][1]
    assert body["thinking"] == {"type": "between_tools"}                # never {type: disabled} (400)
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": C.FINAL_SCHEMA}}
    assert not {"temperature", "top_p", "top_k", "tool_choice"} & set(body)
    body, _h = A.build_body("claude-opus-5-5", "S", msgs, max_tokens=100, tools=None, effort="low",
                            thinking=True, fallbacks=True, cache=True, thinking_off=True)
    assert "thinking" not in body                                       # Opus 5.5: omit + low effort
    body, _h = A.build_body("claude-sonnet-5-5", "S", msgs, max_tokens=100, tools=None, effort="max",
                            thinking=True, fallbacks=True, cache=True, thinking_off=True)
    assert "thinking" not in body                                       # between_tools only at effort ≤ high
    # plain system (every other caller): unchanged
    assert A.split_system([{"role": "system", "content": "a"}, {"role": "user", "content": "b"}])[0] == "a"


def test_openai_compat_merges_the_stable_block():
    m = merge_stable([{"role": "system", "content": "S", "stable": True}, {"role": "system", "content": "V"},
                      {"role": "user", "content": "u"}])
    assert m == [{"role": "system", "content": "S\n\nV"}, {"role": "user", "content": "u"}]
    plain = [{"role": "user", "content": "u"}]
    assert merge_stable(plain) is plain


# ---------------------------------------------------------------- plan validation
def test_plan_validation_drops_junk_breaks_cycles_and_waves():
    raw = {"difficulty": "hard", "summary": "s", "tasks": [
        {"id": "a", "kind": "formalize", "goal": "", "depends_on": ["c"], "model": "fake:ok", "why": "", "hint": "h"},
        {"id": "b", "kind": "prove", "goal": "", "depends_on": ["a"], "model": "anthropic:evil", "why": "", "hint": ""},
        {"id": "c", "kind": "explain", "goal": "", "depends_on": ["b"], "model": "", "why": "", "hint": ""},
        {"id": "d", "kind": "rm -rf", "goal": "", "depends_on": [], "model": "", "why": "", "hint": ""},
        {"id": "a", "kind": "lemmas", "goal": "", "depends_on": ["zz"], "model": "", "why": "", "hint": ""}]}
    diff, summary, tasks = C.validate_plan(raw, {"formalize": ["fake:ok"], "prove": ["fake:p"]})
    assert diff == "hard" and [t.kind for t in tasks] == ["formalize", "prove", "explain", "lemmas"]
    by = {t.id: t for t in tasks}
    assert by["a"].model == "fake:ok" and by["b"].model == ""           # a model outside the candidates is dropped
    assert by["ab"].advisory and by["ab"].depends_on == []              # duplicate id renamed, unknown dep dropped
    waves = sorted(t.wave for t in tasks)
    assert waves[0] == 0 and max(waves) <= 3                             # the cycle a→c→b→a was cut
    assert C.validate_plan({"tasks": "x"}, {}) is None and C.validate_plan(None, {}) is None
    assert C.parse_json('blabla ```json\n{"a": 1}\n``` fin') == {"a": 1}
    assert C.parse_json('Voici : {"consistent": true, "x": "}"} merci') == {"consistent": True, "x": "}"}


# ---------------------------------------------------------------- choosing the conductor (data-driven)
def _brain(tmp_path, **kw):
    return ConductedFakeBrain(tmp_path / "cfg", **kw)


def test_choice_follows_difficulty_budget_and_measurements(tmp_path):
    b = _brain(tmp_path)
    c = C.Conductor(b)
    pick = lambda d, **kw: c.choose("plan", d, mode="auto", scope="s1", prompt_tokens=3000, **kw)[0].tier  # noqa
    b.ledger.scope_caps["s1"] = 1.0
    assert pick("easy") == "haiku" and pick("medium") == "sonnet" and pick("hard") == "opus"
    final = c.choose("final", "medium", mode="auto", scope="s1", prompt_tokens=2500)
    assert final[0].tier == "sonnet"
    # a measured success at its usual speed keeps Sonnet (real run: an unmeasured Opus must not win on latency)
    c.stats.record("anthropic:claude-sonnet-5-5", "plan", True, 10.4, 0.015)
    assert pick("medium") == "sonnet"
    # a model measured as very slow here loses its place
    for _ in range(6):
        c.stats.record("anthropic:claude-haiku-5-5", "plan", True, 55.0, 0.001)
    assert pick("easy") != "haiku"
    # measured: Sonnet's plans keep failing here → another model takes over for medium plans
    for _ in range(8):
        c.stats.record("anthropic:claude-sonnet-5-5", "plan", False, 4.0, 0.01)
    assert pick("medium") != "sonnet"
    # little budget left: the cheap model
    b.ledger.scope_caps["s1"] = 0.02
    assert pick("hard") == "haiku"
    # a correction Sonnet failed twice goes to Opus first
    b.ledger.scope_caps["s1"] = 1.0
    fix = [x.tier for x in c.choose("fix", "medium", mode="auto", scope="s1", prompt_tokens=4000, attempt=0)]
    assert fix[0] == "sonnet" and fix.index("opus") > fix.index("sonnet")
    assert c.choose("fix", "medium", mode="auto", scope="s1", prompt_tokens=4000, attempt=2)[0].tier == "opus"
    # free conductors come after Claude; without the key only them; local mode: nobody
    assert c.choose("plan", "easy", mode="auto", scope="s1", prompt_tokens=3000)[-1].tier == "free"
    nokey = C.Conductor(_brain(tmp_path / "n", claude_key=False))
    assert {x.tier for x in nokey.choose("plan", "hard", mode="auto", scope=None, prompt_tokens=3000)} == {"free"}
    assert nokey.choose("plan", "hard", mode="local", scope=None, prompt_tokens=3000) == []
    weak = C.Conductor(_brain(tmp_path / "w", claude_key=False, free=False))
    assert weak.free_conductors("auto") == []                           # no capable conductor at all


def test_worker_candidates_use_latency_cost_and_paid_rules(tmp_path):
    b = _brain(tmp_path)
    c = C.Conductor(b)
    b.ledger.scope_caps["s"] = 1.0
    ex = c.worker_candidates("explain", "auto", domain=None, scope="s")
    keys = [r["key"] for r in ex]
    assert keys and not ex[0]["paid"]            # a paid writer must beat the free ones by a clear margin
    b.ledger.scope_caps["s"] = 0.1
    assert "anthropic:claude-opus-5-5" not in [r["key"] for r in c.worker_candidates(
        "explain", "auto", domain=None, scope="s", k=10)]                 # more than half of what is left: out
    pr = c.worker_candidates("prove", "auto", domain=None, scope="s")
    assert pr and not any(r["paid"] for r in pr)                          # paid provers: the tournament only
    # a slow measured model drops below a fast one
    b.states.record_latency("fake:fake-explain", 0.5)
    b.states.record_latency("fake:fake-understand", 25.0)
    free = [r for r in c.worker_candidates("explain", "auto", domain=None, scope="s", claude=False, k=10)]
    order = [r["key"] for r in free]
    assert order.index("fake:fake-explain") < order.index("fake:fake-understand")
    assert all(not r["paid"] for r in free)


# ---------------------------------------------------------------- the fallback chain (real engine, fake servers)
def _claude_and_free(tmp_path, anth: FakeServer, free: FakeServer, **kw):
    write_catalogue(tmp_path, [free_provider("free", free.url)],
                    [model("free", "free-reasoner", 0.8), model("free", "free-tiny-1b", 0.9)])
    return make_brain(tmp_path, keys={"anthropic": ANTHROPIC_KEY}, endpoints={"anthropic": anth.url}, **kw)


FINAL_OK = json.dumps({"consistent": True, "issues": [], "summary": "ok"})


def test_fallback_on_429_refusal_timeout_invalid_then_free(tmp_path):
    async def main():
        anth = await FakeServer([
            {"status": 429, "headers": {"retry-after": "30"}, "body": {"type": "error", "error": {
                "type": "rate_limit_error", "message": "rate limited"}}},
            an_stream([("text", "")], stop="refusal"),
            {"events": [], "hang": 30},
            an_stream([("text", "pas du json")]),
        ]).start()
        free = await FakeServer([oa_stream("Voici: " + FINAL_OK)]).start()
        b = _claude_and_free(tmp_path, anth, free)
        try:
            c = C.Conductor(b)
            r = await c.ask("final", kind="final", user="check", schema=C.FINAL_SCHEMA, difficulty="medium",
                            mode="auto", scope=None)
            assert r.tier == "free" and r.data["consistent"] is True and r.key == "free:free-reasoner"
            assert len(r.tried) >= 3 and any("refused" in t for t in r.tried)
            assert any("429" in t or "rate" in t for t in r.tried)
            first = anth.requests[0].body
            assert first["output_config"]["format"]["type"] == "json_schema"
            assert first["system"][0]["cache_control"] == {"type": "ephemeral"} and "temperature" not in first
            assert b.states.pause_of(first and f"anthropic:{first['model']}")      # the 429 paused that model
            assert "free-tiny-1b" not in json.dumps([x.body for x in free.requests])   # unfit: never a conductor
        finally:
            await b.close()
            await anth.stop()
            await free.stop()
    asyncio.run(main())


def test_no_key_and_nothing_capable(tmp_path):
    async def main():
        free = await FakeServer([oa_stream(FINAL_OK)]).start()
        write_catalogue(tmp_path, [free_provider("free", free.url)], [model("free", "weak", 0.3)])
        b = make_brain(tmp_path)
        try:
            c = C.Conductor(b)
            assert c.claude_models("auto") == [] and c.free_conductors("auto") == []
            with pytest.raises(C.NoConductor):
                await c.ask("final", kind="final", user="x", schema=C.FINAL_SCHEMA, difficulty="easy", mode="auto",
                            scope=None)
            assert not free.requests
        finally:
            await b.close()
            await free.stop()
    asyncio.run(main())


def test_real_engine_records_cost_and_cache_reads(tmp_path):
    async def main():
        ev = an_stream([("text", FINAL_OK)], model="claude-haiku-5-5", usage=(1200, 40))
        ev["events"][0] = ev["events"][0].replace('"cache_read_input_tokens": 0', '"cache_read_input_tokens": 900')
        anth = await FakeServer([ev]).start()
        free = await FakeServer([oa_stream(FINAL_OK)]).start()
        b = _claude_and_free(tmp_path, anth, free)
        try:
            c = C.Conductor(b)
            tok = spend.SPEND_SCOPE.set("d:j")
            try:
                r = await c.ask("final", kind="final", user="x", schema=C.FINAL_SCHEMA, difficulty="easy",
                                mode="auto", scope="d:j")
            finally:
                spend.SPEND_SCOPE.reset(tok)
            assert r.tier == "haiku" and r.cache_read == 900
            row = b.ledger.rows[-1]
            assert row.scope == "d:j" and row.cache_read == 900 and r.usd == pytest.approx(row.usd)
        finally:
            await b.close()
            await anth.stop()
            await free.stop()
    asyncio.run(main())


# ---------------------------------------------------------------- the cap question
def test_cap_question_yes_raises_cap_no_goes_without_claude(tmp_path):
    async def main():
        b = _brain(tmp_path)
        c = C.Conductor(b)
        b.ledger.scope_caps["s"] = 0.0001                  # the request's cap is used up
        answers = [True]
        asked = []

        async def on_cap(est):
            asked.append(est)
            if answers.pop(0):
                b.ledger.scope_caps["s"] += 0.5
                return True
            return False
        r = await c.ask("plan", kind="plan", user="x", schema=C.PLAN_SCHEMA, difficulty="medium", mode="auto",
                        scope="s", on_cap=on_cap)
        assert asked and r.tier in ("sonnet", "haiku", "opus")
        b.ledger.scope_caps["s"] = 0.0001
        answers.append(False)
        r = await c.ask("plan", kind="plan", user="x", schema=C.PLAN_SCHEMA, difficulty="medium", mode="auto",
                        scope="s", on_cap=on_cap)
        assert r.tier == "free" and len(asked) == 2
    asyncio.run(main())


def test_request_cap_replaces_proof_cap_and_month_cap_wins(tmp_path):
    led = spend.Ledger(tmp_path / "s.json")
    led.scope_caps["d:j"] = 1.5
    led.record("claude-sonnet-5-5", "d:j", 50_000, 80_000)                # 0.90 $
    assert led.proof_room("d:j", 1.0) == pytest.approx(0.6)
    led.check("d:j", 0.5, cap_proof=1.0, cap_month=20.0)                   # fits the raised request cap
    led.release("d:j", 0.5)
    with pytest.raises(spend.BudgetExceeded) as e:
        led.check("d:j", 0.5, cap_proof=1.0, cap_month=1.0)
    assert e.value.which == "month"
    assert led.proof_room("other:job", 1.0) == pytest.approx(1.0)         # other scopes: the per-proof cap


# ---------------------------------------------------------------- the hook in the pipeline
async def _ctx(tmp_path, brain):
    ctx = make_ctx(tmp_path, brain=brain)
    ctx.settings.mode = "auto"
    return ctx


async def test_pipeline_directed_plan_cards_final_check(tmp_path):
    b = _brain(tmp_path)
    ctx = await _ctx(tmp_path, b)
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    assert job.state == "done", (job.error, job.summary)
    cd = job.conductor
    assert cd["by"].startswith("anthropic:") and cd["plan"] and cd["state"] == "done"
    assert {t["kind"] for t in cd["plan"]} >= {"formalize", "prove", "explain"}
    assert cd["usd"] > 0 and cd["usd"] < 1.0 and cd["final"]["consistent"]
    kinds = [x["kind"] for x in b.calls]
    assert kinds[0] == "plan" and kinds[-1] == "final" and "fix_proof" not in kinds
    texts = [e.text for e in d.events]
    assert any(t.startswith("Dirigé par Claude") for t in texts)
    assert any("Vérification finale (Claude" in t for t in texts)
    # workers got their tool cards (formalizer: Lean + conventions), in a stable block first
    form = [r for r in b.requests if r["role"] == "formalize"]
    assert form and form[0]["messages"][0].get("stable") and "Madalean conventions" in form[0]["messages"][0]["content"]
    # the conductor's hint reached the formalizer
    assert "Advice from the conductor" in json.dumps(form[0]["messages"], ensure_ascii=False)
    # the stable prefix of the conductor's calls is identical: the second call to a model reads the cache
    assert d.proof_is_current
    await ctx.stop()


async def test_pipeline_conductor_fixes_rejected_statement_and_failed_proof(tmp_path):
    b = _brain(tmp_path)
    b.behaviour["bad_statement"] = True
    ctx = await _ctx(tmp_path, b)
    ctx.settings.prove_strategy = "goedel"
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    kinds = [x["kind"] for x in b.calls]
    assert "fix_statement" in kinds, kinds
    assert d.statements[-1].ok and d.statements[-1].model.startswith("anthropic:")
    assert any("a corrigé l'erreur Lean" in e.text for e in d.events)
    assert job.state == "done" and d.proof_is_current, (job.error, job.summary)
    await ctx.stop()

    def no_hints(kind, messages, brain):           # a plan without advice: the provers fail on their own
        ans = demo_conductor(kind, messages, brain)
        if kind == "plan":
            p = json.loads(ans["text"])
            for t in p["tasks"]:
                t["hint"] = ""
            ans = {"text": json.dumps(p)}
        return ans
    b2 = _brain(tmp_path / "p", conductor=no_hints)
    b2.behaviour["fail_unless_hint"] = True
    ctx = await _ctx(tmp_path / "p", b2)
    ctx.settings.prove_strategy = "goedel"
    ctx.settings.prove_attempts = 1
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    kinds = [x["kind"] for x in b2.calls]
    assert "fix_proof" in kinds, (kinds, job.error)
    assert job.state == "done" and d.proof_is_current and d.proofs[-1].meta.get("strategy") == "conductor"
    assert "Even.add" in d.proof and d.proofs[-1].model.startswith("anthropic:")
    await ctx.stop()


async def test_pipeline_cap_question_over_http_yes_and_no(tmp_path):
    for approve in (True, False):
        b = _brain(tmp_path / str(approve), settings={"conductor_cap_usd": 0.0})
        ctx = await _ctx(tmp_path / str(approve), b)
        async with running(ctx) as (_srv, local, _remote):
            ctx.settings.conductor_cap_usd = 0.0           # (the server start reloads the settings)
            ctx.settings.mode = "auto"
            d, job = await create_dossier(ctx, {"problem": PROBLEM})
            for _ in range(200):
                if (job.conductor or {}).get("ask"):
                    break
                await asyncio.sleep(0.02)
            assert job.conductor["ask"]["step"] == 0.5
            assert any("Plafond atteint" in e.text for e in d.events)
            async with session() as s:
                async with s.post(f"{local}/api/jobs/{job.id}/conductor", json={"approve": approve}) as r:
                    assert r.status == 200
                async with s.post(f"{local}/api/jobs/{job.id}/conductor", json={"approve": approve}) as r:
                    assert r.status == 409                         # nothing is waiting any more
                async with s.post(f"{local}/api/jobs/{job.id}/conductor", json={"approve": "yes"}) as r:
                    assert r.status == 400
            await wait_idle(ctx, 60)
        assert job.state == "done", (job.error, job.summary)
        if approve:
            assert job.conductor["cap"] == 0.5 and job.conductor["by"].startswith("anthropic:")
            assert any("relevé à 0.50 $" in e.text for e in d.events)
        else:
            assert not job.conductor["claude"] and job.conductor["by"].startswith("fake:")   # the next best
            assert not [x for x in b.calls if x["model"].startswith("anthropic:")]
            assert any("Suite sans Claude" in e.text for e in d.events)
        assert b.ledger.scope_caps == {}                             # the request's cap is dropped at the end
        await ctx.stop()


async def test_conductor_off_or_fake_brain_changes_nothing(tmp_path):
    # FakeBrain (no conductor interface) and the setting off: no conductor, the same calls as before
    plain = FakeBrain()
    ctx = await _ctx(tmp_path / "a", plain)
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    assert job.state == "done" and job.conductor == {}
    base = [r["role"] for r in plain.requests]
    await ctx.stop()
    b = _brain(tmp_path / "b")
    ctx = await _ctx(tmp_path / "b", b)
    ctx.settings.conductor = False
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    assert job.state == "done" and job.conductor == {} and b.calls == []
    assert [r["role"] for r in b.requests] == base
    assert all(not m.get("stable") for r in b.requests for m in r["messages"])
    await ctx.stop()
    # local mode: never
    b = _brain(tmp_path / "c")
    ctx = make_ctx(tmp_path / "c", brain=b)
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    assert job.conductor == {} and b.calls == []
    await ctx.stop()


async def test_free_conductor_when_claude_has_no_key(tmp_path):
    b = _brain(tmp_path, claude_key=False)
    ctx = await _ctx(tmp_path, b)
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    await wait_idle(ctx, 60)
    assert job.state == "done" and job.conductor["by"].startswith("fake:") and job.conductor["usd"] == 0
    assert all(x["usd"] == 0 for x in b.calls)
    await ctx.stop()


async def test_cancel_stops_conductor_and_tasks(tmp_path):
    async def slow(kind, messages, brain):
        await asyncio.sleep(30)
        return demo_conductor(kind, messages, brain)
    b = _brain(tmp_path, conductor=slow)
    ctx = await _ctx(tmp_path, b)
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    for _ in range(100):
        if job.state == "running" and getattr(job, "conductor_hook", None) is not None:
            break
        await asyncio.sleep(0.02)
    hook = job.conductor_hook
    await asyncio.sleep(0.1)
    assert await ctx.orchestrator.cancel(job.id)
    await wait_idle(ctx, 20)
    assert job.state == "cancelled" and hook.plan_task.done()
    assert b.ledger.scope_caps == {} and not conductor_hook.ASKS
    await ctx.stop()
