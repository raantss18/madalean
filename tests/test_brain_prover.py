"""prove_with_agent end to end: a scripted fake model drives the tools, and every check runs the REAL Lean 4.9
compiler of the lean-prover49 workspace (strict verdict). ≈1 min."""
import asyncio

import pytest

from madalean.brain import rag
from madalean.brain.leanrun import check_with_lean, workspace
from madalean.brain.prover_agent import prove_with_agent
from test_brain_fakes import FakeServer, free_provider, make_brain, model, oa_stream, run, write_catalogue
from test_brain_rag import CACHE

STATEMENT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"


@pytest.fixture(scope="module")
def ws49():
    w = workspace("lean-prover49")
    if w is None:
        pytest.skip("lean-prover49 workspace not installed")
    return w


def test_prove_with_agent_real_lean(tmp_path, ws49):
    script = [
        # tries to weaken the statement: the statement is pinned, so Lean sees the original theorem
        oa_stream("Plan: Even.add.", tool_calls=[("c0", "lean_check", {"code": "theorem t (a b : ℕ) : True := by\n  trivial"})]),
        oa_stream("", tool_calls=[("c1", "lean_check", {"proof": "sorry"})]),
        oa_stream("", tool_calls=[("c2", "lean_check", {"proof": "exact Even.add_even ha hb"})]),
        oa_stream("", tool_calls=[("c3", "search_mathlib", {"query": "sum of two even numbers is even"}),
                                  ("c4", "read_declaration", {"name": "Even.add"})]),
        oa_stream("", tool_calls=[("c5", "lean_check", {"proof": "exact Even.add ha hb"})]),
        oa_stream("", tool_calls=[("c6", "submit", {"proof": "exact Even.add ha hb"})]),
        oa_stream("should not be reached"),
    ]
    checked = []

    async def check(code):
        checked.append(code)
        return await check_with_lean(ws49, code)

    async def main():
        srv = await FakeServer(script).start()
        write_catalogue(tmp_path, [free_provider("f", srv.url)], [model("f", "prover", 0.9)])
        b = make_brain(tmp_path)
        r = rag.LeanRetriever(CACHE, embeddings=False)
        try:
            res = await prove_with_agent(b, r, statement=STATEMENT, workspace_key="lean-prover49", check=check,
                                         mode="auto", max_steps=10, max_seconds=600)
        finally:
            await b.close(); await srv.stop()
        return res, srv.requests
    res, reqs = run(main())
    assert res["finish"] == "proved" and res["steps"] == 6 and res["checks"] == 3
    assert "exact Even.add ha hb" in res["code"] and "(ha : Even a) (hb : Even b) : Even (a + b)" in res["code"]
    assert all("theorem t (a b : ℕ) (ha : Even a)" in c for c in checked)           # statement pinned
    sys_prompt = reqs[0].body["messages"][0]["content"]
    assert "lean-prover49" in sys_prompt and "submit" in sys_prompt and "Lean 4.9" in sys_prompt
    assert "Even.add" in reqs[0].body["messages"][1]["content"]                     # premises given up front
    tools = {t["function"]["name"] for t in reqs[0].body["tools"]}
    assert {"lean_check", "search_mathlib", "read_declaration", "library_search", "submit"} <= tools
    results = [m["content"] for m in reqs[-1].body["messages"] if m["role"] == "tool"]
    assert "Lean rejected" in results[0]
    assert "Rejected before compiling" in results[1] and "sorry" in results[1]
    assert "`Even.add_even` does not exist here" in results[2] and "Even.add" in results[2]
    assert "`Even.add`" in results[3] and "signature: [AddCommSemigroup α]" in results[4]
    assert "ACCEPTED" in results[5]


def test_prove_with_agent_failure_is_reported(tmp_path, ws49):
    async def check(code):
        return {"ok": False, "feedback": "Error: nope", "summary": "Lean found 1 error."}

    async def main():
        srv = await FakeServer([oa_stream("", tool_calls=[("c", "lean_check", {"proof": "simp"})])]).start()
        write_catalogue(tmp_path, [free_provider("f", srv.url)], [model("f", "prover", 0.9)])
        b = make_brain(tmp_path)
        try:
            return await prove_with_agent(b, None, statement=STATEMENT, workspace_key="lean-prover49", check=check,
                                          max_steps=3)
        finally:
            await b.close(); await srv.stop()
    res = run(main())
    assert res["code"] is None and res["finish"] == "max_steps" and res["checks"] == 1     # identical code cached


def test_attempt_assembly_and_reindent():
    from madalean.brain.prover_agent import _Session, dedent_tactics
    assert dedent_tactics("have h : P := by\n    simp\n  \n  exact h") == "  have h : P := by\n    simp\n\n  exact h"
    assert dedent_tactics("intro x\nsimp") == "  intro x\n  simp"
    s = _Session(STATEMENT, None, None, "lean-prover49", None)
    whole = s.assemble({"proof": "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"})
    assert whole.count("theorem t") == 1 and whole.rstrip().endswith("exact Even.add ha hb")
    cheat = s.assemble({"code": "lemma helper : 1 = 1 := rfl\n\ntheorem t : True := by\n  trivial"})
    assert "theorem helper" in cheat or "lemma helper" in cheat
    assert "(ha : Even a) (hb : Even b) : Even (a + b) := by" in cheat and "True" not in cheat.split("theorem t")[1].split(":= by")[0]
