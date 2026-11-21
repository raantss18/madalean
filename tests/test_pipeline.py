"""Dossier pipeline on asyncio (understand → statement (+notes) → proof → explanation (+informal), follow-ups,
versions, library) with the scripted fake brain and the REAL Lean compiler. Port of the 1.1.4 tests."""
from __future__ import annotations

from madalean import i18n
from madalean.pipeline.runner import plan_for_message
from madalean.server.routes_work import create_dossier
from helpers import make_ctx, started, wait_idle

PROBLEM = "Montrer que la somme de deux entiers pairs est paire."


async def new(ctx, problem=PROBLEM, **kw):
    d, job = await create_dossier(ctx, {"problem": problem, **kw})
    await wait_idle(ctx)
    return d


async def request(ctx, d, text, stage="auto"):
    plan, shown = plan_for_message(d, text, stage, bool(ctx.brain.candidates("route", ctx.settings.mode)))
    d.add_event("user", text, stage=shown)
    await ctx.repo.save(d)
    ctx.orchestrator.submit(d.id, plan)
    await wait_idle(ctx)
    return shown


def kinds(d):
    return [e.kind for e in d.events]


def roles(ctx):
    return [r["role"] for r in ctx.brain.requests]


async def test_full_automatic_chain(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d = await new(ctx)
    assert kinds(d) == ["user", "understood", "statement", "notes", "proof", "info", "explanation", "informal"], \
        [(e.kind, e.text) for e in d.events]
    assert d.understood.startswith("Let $a$ and $b$ be even") and "Soient $a$ et $b$" in d.events[1].text
    assert d.understood_display.startswith("Soient")
    assert d.statement.rstrip().endswith("Even (a + b) := by sorry") and d.theorem in d.statement
    assert "exact Even.add ha hb" in d.proof and d.proof_is_current and d.status == "proved"
    assert d.explanation.startswith("**Énoncé.**") and d.notes.startswith("- `(a b : ℕ)`")
    assert d.informal_proof.startswith("**Théorème.**")
    assert roles(ctx) == ["understand", "formalize", "explain", "prove", "explain", "explain"]
    assert "Let $a$ and $b$ be even natural numbers" in ctx.brain.requests[1]["messages"][0]["content"]
    assert all(e.model.startswith("local:") for e in d.events if e.kind in ("understood", "statement", "proof",
                                                                           "explanation", "notes", "informal"))
    meta = d.proofs[d.cur_proof].meta
    assert meta["axioms"] is not None and meta["workspace"] == ws.key and meta["lean"]
    assert ctx.repo.store.load(d.id).to_json() == d.to_json()
    assert [e.name for e in ctx.library.entries] == [d.theorem]
    assert d.statement_notes[0].parent == d.cur_statement and d.informal_proofs[0].parent == d.cur_proof
    await ctx.stop()


async def test_follow_up_on_the_proof_uses_history(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d = await new(ctx)
    ctx.brain.requests.clear()
    await request(ctx, d, "Donne une preuve plus courte avec simpa")
    reqs = ctx.brain.requests
    assert reqs[0]["messages"][0]["content"].startswith("You assist a user")
    assert [e.stage for e in d.events if e.kind == "user"][-1] == "proof"
    prover = reqs[1]["messages"]
    assert len(prover) == 3 and "The user now asks: Donne une preuve plus courte" in prover[2]["content"]
    assert "exact Even.add ha hb" in prover[1]["content"]
    assert len(d.proofs) == 2 and "simpa using" in d.proof and len(d.explanations) == 2
    assert len(d.informal_proofs) == 2                            # new proof → new informal proof
    await ctx.stop()


async def test_follow_up_on_the_statement_reruns_everything(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d = await new(ctx)
    ctx.brain.requests.clear()
    await request(ctx, d, "ajoute + 0 à la conclusion de l'énoncé")
    f = ctx.brain.requests[1]["messages"][0]["content"]
    assert f.startswith("Please autoformalize") and "a + b + 0" in f
    assert "Even (a + b + 0)" in d.statement and d.proof_is_current and len(d.statements) == 2
    assert kinds(d)[-7:] == ["user", "understood", "statement", "notes", "proof", "explanation", "informal"]
    assert d.notes and d.statement_notes[-1].parent == 1
    await ctx.stop()


async def test_explanation_follow_up_and_language(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d = await new(ctx)
    ctx.brain.requests.clear()
    i18n.set_language("en")
    try:
        await request(ctx, d, "explain step 1 in more detail")
    finally:
        i18n.set_language("fr")
    m = ctx.brain.requests[1]["messages"]
    assert len(ctx.brain.requests) == 2 and m[0]["content"].startswith("You are a mathematics teacher") and len(m) == 3
    assert "explain step 1" in m[2]["content"]
    await ctx.stop()


async def test_library_result_is_offered_in_the_next_dossier(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d1 = await new(ctx)
    ctx.brain.requests.clear()
    d2 = await new(ctx, "Montrer encore que la somme de deux pairs est paire.")
    prompt = next(r for r in ctx.brain.requests if r["role"] == "prove")["messages"][0]["content"]
    assert f"theorem {d1.theorem}" in prompt
    assert d2.lemmas_used == [d1.theorem] and d2.proof_is_current
    await ctx.stop()


async def test_pause_option_and_failed_translation(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    ctx.settings.pause_after_translation = True
    d = await new(ctx)
    assert kinds(d) == ["user", "understood", "statement", "info", "notes"] and not d.proof
    ctx.settings.pause_after_translation = False
    ctx.brain.behaviour["bad_statement"] = True
    d2 = await new(ctx, "Problème qui se traduit mal")
    assert kinds(d2)[-1] == "error" and not d2.proof and d2.statements and not d2.statements[-1].ok
    assert not any(r["role"] == "prove" for r in ctx.brain.requests[-3:])
    await ctx.stop()


async def test_cancel_and_restore(tmp_path, ws):
    import asyncio
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d, job = await create_dossier(ctx, {"problem": PROBLEM})
    for _i in range(3000):
        if job.stage == "proof":
            break
        await asyncio.sleep(0.02)
    assert await ctx.orchestrator.cancel(job.id)
    assert job.state == "cancelled" and kinds(d)[-1] == "info" and d.status == "stopped"
    ctx.orchestrator.submit(d.id, [{"stage": "proof"}, {"stage": "explanation"}])
    await wait_idle(ctx)
    assert d.proof_is_current
    await request(ctx, d, "ajoute + 0 à la conclusion de l'énoncé")
    d.restore("statement", 0)
    assert d.statement.rstrip().endswith("Even (a + b) := by sorry") and not d.proof_is_current
    d.restore("proof", 0)
    assert d.proof_is_current
    await ctx.stop()


async def test_unknown_request_stops_and_asks_for_the_statement(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    ctx.brain.behaviour["unknown"] = True
    d = await new(ctx, "lemme des bergers")
    assert kinds(d) == ["user", "error"] and not d.statement
    assert roles(ctx) == ["understand"]
    ctx.brain.behaviour.clear()
    ctx.brain.requests.clear()
    await request(ctx, d, "Pour tous entiers pairs a et b, a + b est pair.")
    assert d.statement and "lemme des bergers" in ctx.brain.requests[0]["messages"][0]["content"]
    assert "a + b est pair" in ctx.brain.requests[0]["messages"][0]["content"]
    await ctx.stop()


async def test_follow_up_after_a_failed_search_reaches_the_prover(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    ctx.settings.prove_attempts = 2
    ctx.brain.behaviour["fail_unless_hint"] = True
    d = await new(ctx)
    assert not d.proof and kinds(d)[-1] == "error" and d.status == "failed"
    ctx.brain.requests.clear()
    await request(ctx, d, "Réessaie la preuve en utilisant Even.add")
    prompts = [r["messages"][0]["content"] for r in ctx.brain.requests]
    assert prompts[1].startswith("Complete the following Lean 4 code")
    assert ("The user gives this hint for the proof (follow it if it helps): Réessaie la preuve en utilisant "
            "Even.add") in prompts[1]
    assert d.proof_is_current and len(d.statements) == 1
    await ctx.stop()


async def test_converse_request_changes_the_theorem(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d = await new(ctx)
    ctx.brain.requests.clear()
    await request(ctx, d, "et la réciproque")
    assert roles(ctx) == ["route", "formalize", "explain", "prove", "explain", "explain"]
    assert "previous formalization" not in ctx.brain.requests[1]["messages"][0]["content"]
    assert "(hab : Even (a + b)) : Even b" in d.statement and d.proof_is_current and len(d.statements) == 2
    und = [e for e in d.events if e.kind == "understood"][-1]
    assert "Montrer que $b$ est pair" in und.text
    assert [e.stage for e in d.events if e.kind == "user"][-1] == "statement"
    expl = [r for r in ctx.brain.requests if r["messages"][0]["content"].startswith("Tu es un professeur")][0]
    assert "Prove that $b$ is even" in expl["messages"][0]["content"]
    await ctx.stop()


async def test_unusable_routing_answer_falls_back_to_keywords(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    d = await new(ctx)
    ctx.brain.behaviour["route_garbage"] = True
    ctx.brain.requests.clear()
    await request(ctx, d, "une preuve plus courte")
    assert roles(ctx)[:2] == ["route", "prove"]
    # without a routing model, the keyword router is used directly
    assert plan_for_message(d, "une preuve plus courte", "auto", False)[1] == "proof"
    await ctx.stop()


async def test_split_into_lemmas_retries_the_parent(tmp_path, ws):
    """Sub-dossiers: children proved in parallel, then the parent retried with them as library lemmas."""
    from madalean.pipeline.runner import parse_split
    ctx = await started(make_ctx(tmp_path, ws=ws))
    ctx.settings.prove_attempts = 1
    ctx.brain.behaviour["fail_unless_hint"] = True
    parent = await new(ctx)
    assert not parent.proof_is_current
    ctx.brain.behaviour.clear()
    lemmas = parse_split(ctx.brain.responder("prove", [{"role": "user", "content":
                         "Here is a Lean 4 theorem that has not been proved yet:"}], ctx.brain))
    assert [lm["statement"].split()[1] for lm in lemmas] == ["split_even_add", "split_even_zero"]
    from madalean.server.routes_work import create_dossier as cd
    kids = []
    for lm in lemmas[:1]:
        k, _j = await cd(ctx, {**lm, "parent_id": parent.id, "kind": "lemma", "workspace": parent.workspace})
        kids.append(k)
    parent.retry_parent = True
    await wait_idle(ctx)
    import asyncio
    await asyncio.sleep(0.2)
    await wait_idle(ctx)
    assert kids[0].proof_is_current and kids[0].parent_id == parent.id
    assert parent.proof_is_current, [(e.kind, e.text[:80]) for e in parent.events[-6:]]
    assert any(k.theorem in parent.lemmas_used for k in kids)
    await ctx.stop()
