"""Session S-AM (DECISIONS D45): « Expliquer » for Lean and the verified catalogue in the provers' prompts.

- Goal states: `trace_state` inserted after each complete tactic (never inside a calc chain, an alternative or a
  continued line), Lean's information messages mapped back; nothing when the insertion breaks the file.
- Explanations through the server with a fake brain and the demo Lean: the Lean prompt (version, Lean's messages
  with positions), streaming events, cache, the correction offered only when Lean accepts it (a proof pinned to the
  dossier's statement), one repair round, a correction Lean keeps refusing is never offered, header lines glossed
  without a model, notes' blocks, the generic endpoint.
- Real Lean (lean-prover49, skipped without a built workspace): a correction is checked by Lean before being
  offered, a wrong one is never offered, the applied one becomes « vérifiée » only through the fresh strict check of
  the manual edit; goal states from Lean.
- Catalogue: relevant entries per request, only those verified on the workspace (a failed or unbuilt one never),
  per Lean version, appended after the stable prefix (Goedel loop, agent, conductor); token counts measured."""
from __future__ import annotations

import asyncio
import json
import re

import pytest

from helpers import make_ctx, running, session
from madalean import leancheck, syntaxcards
from madalean.brain import toolcards
from madalean.brain.fake import FakeBrain
from madalean.pipeline import leancat
from madalean.research import codecat
from madalean.research import leanexplain as LX
from madalean.workspaces import Workspace

H = leancheck.GOEDEL_HEADER
STMT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"
GOOD = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"


# ---------------------------------------------------------------- goal states (pure)
def test_instrument_after_complete_tactics_only():
    code = ("theorem t (n : ℕ) (h : 0 < n) : n ^ 2 ≥ n := by\n"
            "  have h1 : 1 ≤ n := h\n"
            "  calc n = n * 1 := by ring\n"
            "    _ ≤ n * n := Nat.mul_le_mul_left n h1\n"
            "    _ = n ^ 2 := by ring\n")
    icode, mp = LX.instrument(code)
    lines = icode.split("\n")
    assert lines[1] == "  trace_state" and mp[2] == 1                 # the goal to prove, at the theorem's line
    assert lines[3] == "  trace_state" and mp[4] == 2                 # after the `have`
    assert lines[4].startswith("  calc") and lines[5].startswith("    _ ≤") and lines[6].startswith("    _ =")
    assert lines[7] == "  trace_state" and mp[8] == 3                 # after the whole calc chain, never inside
    assert icode.replace("\n  trace_state", "") == code
    # induction alternatives: nothing before `|`, the alternative's block gets its own states
    code = ("theorem u (a b : ℕ) : a + b = b + a := by\n  induction a with\n  | zero => simp\n"
            "  | succ k ih =>\n    rw [Nat.succ_add]\n    omega\n")
    icode, mp = LX.instrument(code)
    assert "  | zero => simp\n  | succ" in icode and "rw [Nat.succ_add]\n    trace_state\n    omega" in icode
    assert sorted(mp.values()) == [1, 2, 5, 6]
    # multi-line signature, bullets, nested `have … := by` block
    code = ("theorem v (p q : Prop) (hp : p) (hq : q) :\n    p ∧ q := by\n  constructor\n  · exact hp\n"
            "  · have h2 : q := by\n      exact hq\n    exact h2\n")
    icode, mp = LX.instrument(code)
    assert mp[3] == 1 and 3 in mp.values() and 4 in mp.values()
    # continued lines are never split
    code = "theorem w : 1 + 1 = 2 := by\n  simp only [Nat.add_comm,\n    Nat.one_add]\n"
    icode, mp = LX.instrument(code)
    assert "Nat.add_comm,\n    Nat.one_add]\n  trace_state" in icode
    # no tactic block: nothing; a one-line `by sorry` statement: the goal only
    assert LX.instrument("theorem z : True := trivial\n") is None
    icode, mp = LX.statement_probe(H + STMT)
    assert icode.endswith(":= by\n  trace_state\n  sorry") and list(mp.values()) == [H.count("\n") + 1]


def _json(*msgs) -> str:
    return "\n".join(json.dumps({"severity": s, "pos": {"line": l, "column": 2}, "data": t}) for s, l, t in msgs)


def test_goals_from_lean_messages_and_never_after_a_broken_insertion():
    mp = {2: 1, 4: 2}
    out = LX.goals_from(_json(("information", 2, "n : ℕ\n⊢ n = n"), ("information", 4, ""),
                              ("warning", 3, "unused")), mp)
    assert out == {1: "n : ℕ\n⊢ n = n", 2: "no goals"}
    assert LX.goals_from(_json(("information", 2, "x"), ("error", 4, "unknown tactic")), mp) is None
    # an error elsewhere (the user's own) keeps the states Lean printed before it
    assert LX.goals_from(_json(("information", 2, "x"), ("error", 3, "unknown identifier")), mp) == {1: "x"}
    # header prepended before compiling (a note's block): positions shifted back
    assert LX.goals_from(_json(("information", 12, "g")), mp, offset=10) == {1: "g"}


def test_header_lines_glossed_without_a_model():
    rows, fixed = LX.numbered(H + "theorem t : True := by\n  trivial", "fr")
    assert "import Mathlib" not in rows and "1: " not in rows and "theorem t" in rows
    assert fixed[1].startswith("Charge Mathlib") and "maxHeartbeats" not in rows
    assert any("espaces de noms" in v for v in fixed.values())


# ---------------------------------------------------------------- through the server (fake brain, demo Lean)
def responder_for(fix: str | list[str], expl: str = "Lean ne connaît pas `no_such_lemma`.", seen: list | None = None):
    fixes = [fix] if isinstance(fix, str) else list(fix)

    def responder(role, messages, brain):
        user = [m["content"] for m in messages if m["role"] == "user"]
        if seen is not None:
            seen.append([dict(m) for m in messages])
        if user[0].startswith(("Explique ce code Lean", "Explain this Lean code")):
            nums = re.findall(r"^(\d+): (.*)$", user[0], re.M)
            return "\n".join(f"{n}: étape {n}" for n, _c in nums)
        f = fixes[min(len(user) - 1, len(fixes) - 1)]
        return f"{expl}\n\n```lean\n{f}\n```" if f else expl
    return responder


async def _dossier(s, L, statement=STMT):
    async with s.post(L + "/api/dossiers", json={"statement": statement, "start": False}) as r:
        return (await r.json())["dossier"]


async def test_explain_error_statement_checked_fix_stream_and_cache(tmp_path):
    seen: list = []
    brain = FakeBrain(responder_for(H + STMT.replace("theorem t", "theorem t2"), seen=seen))
    ctx = make_ctx(tmp_path, brain=brain)
    events: list[dict] = []
    real = ctx.publish

    def publish(t, payload=None):
        if t == "lean.explain":
            events.append(dict(payload or {}))
        return real(t, payload)
    ctx.publish = publish
    checks: list[tuple[str, bool]] = []
    lean_check = ctx.lean.check

    async def spy(code, ws, timeout_s=180, strict_name=None, owner=None, warm=False):
        checks.append((code, warm))
        return await lean_check(code, ws, timeout_s, strict_name, owner, warm)
    ctx.lean.check = spy
    async with running(ctx) as (_srv, L, _R), session() as s:
        d = await _dossier(s, L)
        bad = d["current"]["statement"].replace("Even (a + b)", "Even (no_such_lemma a + b)")
        errs = [{"line": bad.split("\n").index(next(l for l in bad.split("\n") if "no_such" in l)) + 1, "col": 40,
                 "text": "unknown identifier 'no_such_lemma'", "severity": "error"}]
        body = {"mode": "error", "dossier": d["id"], "part": "statement", "code": bad, "errors": errs,
                "stream": "s1"}
        j = await (await s.post(L + "/api/lean/explain", json=body)).json()
        assert j["fix_status"] == "accepted" and "theorem t2" in j["fix"] and not j["cached"]
        assert j["explanation"].startswith("Lean ne connaît pas") and j["workspace"] == "demo"
        assert len(checks) == 1 and checks[0][1] is True and "theorem t2" in checks[0][0]   # warm path allowed
        sysm, user = seen[0][0]["content"], seen[0][1]["content"]
        assert "Lean v4.9.0-rc1" in sysm and "Fintype.card" in sysm                         # version-aware
        assert user.startswith("Lean refuse cet énoncé") and "<error>" in user and "no_such_lemma" in user
        assert [e["state"] for e in events][0] == "start" and events[-1]["state"] == "done"
        assert "checking" in [e["state"] for e in events] and all(e["stream"] == "s1" for e in events)
        # same request: cached (no model call, no Lean)
        n = len(brain.requests)
        j2 = await (await s.post(L + "/api/code/explain", json={**body, "language": "lean"})).json()
        assert j2["cached"] and j2["fix"] == j["fix"] and len(brain.requests) == n and len(checks) == 1
        # applying it = the manual edit: a new statement version (checked again by Lean)
        r = await (await s.post(L + f"/api/dossiers/{d['id']}/statement", json={"code": j["fix"]})).json()
        assert r["dossier"]["statements"][-1]["source"] == "user" and r["check"]["statement_ok"]


async def test_a_correction_lean_refuses_is_never_offered(tmp_path):
    seen: list = []
    still_bad = GOOD.replace("Even.add ha hb", "no_such_lemma ha hb")
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder_for([still_bad, still_bad], seen=seen)))
    async with running(ctx) as (_srv, L, _R), session() as s:
        d = await _dossier(s, L)
        await s.post(L + f"/api/dossiers/{d['id']}/versions/proof", json={"code": still_bad})
        # no errors given: the server compiles the current proof itself (pinned, strict)
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"],
                                                               "part": "proof"})).json()
        assert j["fix"] == "" and j["fix_status"] == "rejected" and j["fix_tries"] == 2
        assert len(seen) == 2 and "Lean refuse aussi ta correction" in seen[1][-1]["content"]   # one repair round
        assert "unknown identifier" in seen[0][1]["content"] and "<error>" in seen[0][1]["content"]
        # a repair that Lean accepts is offered; the statement is pinned (a changed signature is not taken)
        seen.clear()
        weaker = "theorem t : True := by\n  trivial"
        ctx.brain.responder = responder_for([still_bad, GOOD.replace("theorem t ", "theorem other ")], seen=seen)
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"], "part": "proof",
                                                               "error": "unknown identifier 'no_such_lemma'"})).json()
        assert j["fix_status"] == "accepted" and j["fix_tries"] == 2
        ctx.brain.responder = responder_for(weaker)
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"], "part": "proof",
                                                               "error": "x"})).json()
        assert j["fix_status"] == "accepted"       # the demo Lean accepts `trivial`… for the PINNED statement only:
        r = await (await s.post(L + f"/api/dossiers/{d['id']}/versions/proof", json={"code": j["fix"]})).json()
        assert f"theorem {d['theorem']} (a b : ℕ)" in r["dossier"]["current"]["proof"]
        # nothing wrong: said so, no model call
        await s.post(L + f"/api/dossiers/{d['id']}/versions/proof", json={"code": GOOD})
        n = len(ctx.brain.requests)
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"],
                                                               "part": "proof"})).json()
        assert j["no_error"] and len(ctx.brain.requests) == n


async def test_lines_mode_header_glossed_and_note_blocks(tmp_path):
    seen: list = []
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder_for(GOOD, seen=seen)))
    async with running(ctx) as (_srv, L, _R), session() as s:
        d = await _dossier(s, L)
        await s.post(L + f"/api/dossiers/{d['id']}/versions/proof", json={"code": GOOD})
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "lines", "dossier": d["id"],
                                                               "part": "proof"})).json()
        rows = {r["line"]: r for r in j["lines"]}
        assert rows[1]["text"].startswith("Charge Mathlib") and rows[1]["goal"] is None
        th = next(r for r in j["lines"] if r["code"].startswith("theorem"))
        assert th["text"] == f"étape {th['line']}" and j["goals"] == "none"      # the demo Lean prints no goal
        assert "import Mathlib" not in seen[-1][1]["content"] and "ne décris aucun but" in seen[-1][1]["content"]
        # a note's ```lean block: workspace of the project, the header it is checked with, the block's positions
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        block = "theorem nb (n : ℕ) : n ≤ n := by\n  exact no_such_lemma n"
        note = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "N",
                                                                    "body": f"Texte\n\n```lean\n{block}\n```\n"}))
                .json())["note"]
        ctx.brain.responder = responder_for(block.replace("no_such_lemma", "Nat.le_refl"), seen=seen)
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "note": note["id"],
                                                               "block": 0})).json()
        assert j["fix_status"] == "accepted" and "Nat.le_refl" in j["fix"] and "import" not in j["fix"]
        assert "2: " not in seen[-1][1]["content"] and "<error>" in seen[-1][1]["content"]
        assert ":= by\n  <error>exact no_such" in seen[-1][1]["content"]           # the block's own line 2
        # bad requests
        r = await s.post(L + "/api/lean/explain", json={"mode": "steps", "code": "x"})
        assert r.status == 400
        r = await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"], "part": "x"})
        assert r.status == 400


# ---------------------------------------------------------------- real Lean (lean-prover49)
async def test_real_lean_checks_the_correction_before_it_is_offered(tmp_path, ws):
    wrong = GOOD.replace("Even.add ha hb", "Even.add ha")               # Lean: type mismatch
    also_wrong = GOOD.replace("Even.add ha hb", "no_such_lemma ha hb")
    seen: list = []
    ctx = make_ctx(tmp_path, ws=ws, brain=FakeBrain(responder_for([also_wrong, also_wrong], seen=seen)))
    async with running(ctx) as (_srv, L, _R), session() as s:
        d = await _dossier(s, L)
        name = d["theorem"]
        await s.post(L + f"/api/dossiers/{d['id']}/versions/proof", json={"code": wrong})
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"],
                                                               "part": "proof"})).json()
        assert j["fix"] == "" and j["fix_status"] == "rejected"           # Lean refused it twice: never offered
        assert "<error>" in seen[0][1]["content"] and "Lean v4.9" in seen[0][0]["content"]
        ctx.brain.responder = responder_for(GOOD.replace("theorem t ", f"theorem {name} "))
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "error", "dossier": d["id"],
                                                               "part": "proof"})).json()
        assert j["fix_status"] == "accepted" and "Even.add ha hb" in j["fix"]
        assert j["fix_check"]["summary"].startswith("Preuve acceptée")
        # applied = a manual edit; « vérifiée » only from its fresh strict check
        r = await (await s.post(L + f"/api/dossiers/{d['id']}/versions/proof", json={"code": j["fix"]})).json()
        assert r["check"]["ok"] and r["check"]["via"] == "fresh" and r["dossier"]["status"] == "proved"
        # goal states printed by Lean, line by line
        j = await (await s.post(L + "/api/lean/explain", json={"mode": "lines", "dossier": d["id"],
                                                               "part": "proof"})).json()
        assert j["goals"] == "lean"
        th = next(r for r in j["lines"] if r["code"].startswith(f"theorem {name}"))
        assert "⊢ Even (a + b)" in th["goal"]
        ex = next(r for r in j["lines"] if "exact Even.add" in r["code"])
        assert ex["goal"] == "no goals"


# ---------------------------------------------------------------- catalogue in the provers' prompts
def _ws(tmp_path, key: str, toolchain: str) -> Workspace:
    return Workspace(key, key, tmp_path / key, toolchain, True)


def _built(ws, verified, failed=None, lean="v4.9.0-rc1"):
    f = codecat._lean_file(ws)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"tool": "lean", "workspace": ws.key, "flavor": codecat.lean_flavor(ws.toolchain),
                             "lean": lean, "catalogue_version": codecat.CATALOGUE_VERSION, "built": 1.0,
                             "verified": verified, "failed": failed or {}}), encoding="utf-8")


def test_catalogue_entries_by_intent_and_workspace(tmp_path):
    syntaxcards.configure(tmp_path / "cache")
    assert codecat.lean_relevant("Montrer que la somme des n premiers entiers impairs vaut n^2") == ["sum_range"]
    assert codecat.lean_relevant("F_125 a 125 éléments") == ["gf"]
    assert codecat.lean_relevant("theorem x (p : ℕ) (hp : Nat.Prime p) : 2 ≤ p := by sorry") == ["int_is_prime"]
    assert codecat.lean_relevant("Pour tout n, n^2 >= n") == []
    old, new = _ws(tmp_path, "lean-prover49", "leanprover/lean4:v4.9.0-rc1"), _ws(tmp_path, "lean-current",
                                                                                   "leanprover/lean4:v4.36.0")
    req = "la somme des carrés de 0 à 3 dans F_125"
    assert codecat.lean_prompt_block(old, req) == ("", [])               # catalogue not built here: nothing
    _built(old, sorted(codecat.LEAN_ENTRIES), {"gf": "unknown constant"})
    _built(new, sorted(codecat.LEAN_ENTRIES), lean="v4.36.0")
    txt, ids = codecat.lean_prompt_block(old, req)
    assert ids == ["sum_range"] and "∑ i in Finset.range" in txt and "GaloisField" not in txt   # failed: never
    txt, ids = codecat.lean_prompt_block(new, req)
    assert ids == ["gf", "sum_range"] and "∑ i ∈ Finset.range" in txt and "Nat.card F125" in txt
    _built(old, ["gf"], {})
    assert codecat.lean_prompt_block(old, "somme des k")[1] == []        # never checked there: not given


def test_catalogue_appended_after_the_stable_prefix_and_measured(tmp_path):
    syntaxcards.configure(tmp_path / "cache")
    ws = _ws(tmp_path, "lean-current", "leanprover/lean4:v4.36.0")
    _built(ws, sorted(codecat.LEAN_ENTRIES), lean="v4.36.0")
    problem = "Montrer que la somme des n premiers entiers impairs vaut n^2"
    stmt = H + "theorem odd_sum (n : ℕ) : ∑ i ∈ Finset.range n, (2 * i + 1) = n ^ 2 := by sorry"
    base = [{"role": "user", "content": leancheck.initial_prompt(stmt)}]
    block, ids = leancat.block_for(ws, "prove", problem, stmt)
    out = leancat.append_block(base, block)
    assert ids == ["sum_range"] and out[0]["content"].startswith(base[0]["content"].rstrip())
    assert out[0]["content"].endswith(block) and base[0]["content"] == leancheck.initial_prompt(stmt)   # a copy
    # a correction round: the first message is byte-identical (cached prefix), appended once only
    rounds = leancat.append_block(out + [{"role": "assistant", "content": "x"}, {"role": "user", "content": "e"}],
                                  block)
    assert rounds[0]["content"] == out[0]["content"] and rounds[2]["content"] == "e"
    before = toolcards.estimate_tokens(base[0]["content"])
    after = toolcards.estimate_tokens(out[0]["content"])
    assert 15 <= after - before <= 220
    # the conductor's corrections: in the request block, the stable block unchanged
    plain = toolcards.compact("fix_proof", toolcards.features_of(problem, stmt), ws)
    withc = toolcards.compact("fix_proof", toolcards.features_of(problem, stmt), ws, intent_text=problem + stmt)
    assert withc.stable == plain.stable and withc.stable_hash == plain.stable_hash
    assert "∑ i ∈ Finset.range" in withc.request and "cat-sum_range" in withc.selected
    assert withc.tokens_request > plain.tokens_request
    # roles that do not write Lean: unchanged
    assert leancat.append_block(base, "") is base
