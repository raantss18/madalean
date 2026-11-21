"""Learning support (S-G): leak detector, hint ladder (gates, lazy cache, regenerate-then-redact), token
explanations (never invented), explain-it-back grading, per-device progress, and exercises checked by real Lean
(faded proof, erroneous example) in lean-prover49."""
import json

import pytest

from helpers import make_ctx, running, session
from madalean import leancheck
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import learn as L_

PROOF = ("theorem sum_even (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n"
         "  obtain ⟨k, hk⟩ := ha\n  obtain ⟨l, hl⟩ := hb\n  exact ⟨k + l, by omega⟩\n")


def _seed(ctx, proof=PROOF):
    d = ctx.repo.new("La somme de deux pairs est paire.", ctx.settings.workspace, "Somme paire")
    st = leancheck.prepare_statement(proof.split(":= by")[0] + ":= by sorry")
    d.add_statement(st)
    d.add_proof(leancheck.GOEDEL_HEADER + proof, model="local:x", meta={"axioms": ["propext"]})
    d.status = "proved"
    d.add_informal_proof("a = 2k, b = 2l, donc a + b = 2(k + l).")
    return d


def test_answer_key_and_leaks():
    key = L_.answer_key(leancheck.GOEDEL_HEADER + PROOF)
    assert key["tactics"] == ["exact", "obtain", "omega"] and key["lemmas"] == []
    assert key["lines"][0] == "obtain ⟨k, hk⟩ := ha" and len(key["lines"]) == 3
    assert L_.leaks(1, "Utilisez `obtain` sur ha.", key) == ["tactic:obtain"]
    assert L_.leaks(2, "On écrit a comme un double : obtain ⟨k, hk⟩ := ha", key) == ["line:obtain ⟨k, hk⟩ := ha"]
    assert L_.leaks(4, "obtain ⟨k, hk⟩ := ha\nobtain ⟨l, hl⟩ := hb", key) == []          # 2 of 3 lines allowed
    assert L_.leaks(4, PROOF, key)                                                     # but not the whole proof
    k2 = L_.answer_key(leancheck.GOEDEL_HEADER + "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n"
                                                 "  exact Even.add ha hb\n")
    assert k2["lemmas"] == ["Even.add"]
    assert L_.leaks(2, "Le lemme Even.add fait tout.", k2) == ["lemma:Even.add"]
    assert L_.leaks(3, "Le lemme clé est Even.add.", k2) == []
    assert L_.leaks(2, "Even.add", k2, allowed="j'ai pensé à Even.add") == []         # the learner's own words
    assert L_.redact("Voici : obtain ⟨k, hk⟩ := ha !", ["line:obtain ⟨k, hk⟩ := ha"]) == "Voici : … !"


def leaky(role, messages, brain):
    first = messages[0]["content"]
    if first.startswith(L_.MARK) and "task=hint" in first:
        lv = int(first.split("level=")[1][0])
        retry = len(messages) > 1
        brain.behaviour.setdefault("calls", []).append(lv)
        if lv == 1:
            return "Pensez à la définition de pair." if retry else "Utilisez `obtain` sur ha."
        if lv == 2:
            return "Décomposez : obtain ⟨k, hk⟩ := ha puis regroupez."          # leaks twice → redacted
        if lv == 3:
            return "Quel lien entre $a = k + k$ et un double ?"
        if lv == 4:
            return "Première ligne : obtain ⟨k, hk⟩ := ha"
    if first.startswith(L_.MARK) and "task=explain_back" in first:
        return json.dumps({"criteria": [{"criterion": "a, b doubles", "met": True, "evidence": "a = 2k"},
                                        {"criterion": "somme double", "met": False, "evidence": ""}],
                           "gap": "Il manque : exact ⟨k + l, by omega⟩", "question": "Que vaut a + b ?"})
    return demo_responder(role, messages, brain)


async def test_hint_ladder_gates_cache_and_leaks(tmp_path):
    brain = FakeBrain(leaky)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (_s, L, Rm), session() as s:
        d = _seed(ctx)
        await ctx.repo.save(d)
        u = L + f"/api/learn/{d.id}"
        r = await s.post(u + "/hint", json={"level": 1})
        assert r.status == 409 and (await r.json())["error"] == "attempt_first"
        assert (await s.post(u + "/attempt", json={"text": "", "confidence": 50})).status == 400
        assert (await s.post(u + "/attempt", json={"text": "J'ai essayé simp", "confidence": 30})).status == 200
        r = await s.post(u + "/hint", json={"level": 2})
        assert r.status == 409 and (await r.json())["error"] == "in_order"
        h1 = await (await s.post(u + "/hint", json={"level": 1})).json()
        assert h1["text"] == "Pensez à la définition de pair." and not h1["redacted"]          # regenerated once
        h2 = await (await s.post(u + "/hint", json={"level": 2})).json()
        assert h2["redacted"] and "obtain ⟨k, hk⟩ := ha" not in h2["text"]
        r = await s.post(u + "/hint", json={"level": 3})
        assert r.status == 409 and (await r.json())["error"] == "reflect_first"
        h3 = await (await s.post(u + "/hint", json={"level": 3, "reflection": "il faut écrire a comme double"})).json()
        h4 = await (await s.post(u + "/hint", json={"level": 4, "reflection": "compris"})).json()
        assert not h4["redacted"]
        h5 = await (await s.post(u + "/hint", json={"level": 5, "reflection": "vu le lien"})).json()
        assert h5["source"] == "lean" and PROOF.strip() in h5["text"] and h5["model"] == ""
        calls = list(brain.behaviour["calls"])
        again = await (await s.post(u + "/hint", json={"level": 3})).json()      # cached, re-reveal allowed
        assert again["text"] == h3["text"] and brain.behaviour["calls"] == calls
        st = await (await s.get(u + "/ladder")).json()
        assert st["revealed"] == [1, 2, 3, 4, 5] and st["next"] is None
        # another device has its own progress (and its own gate)
        dev, token = ctx.devices.add("tablet")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await s.post(Rm + f"/api/learn/{d.id}/hint", json={"level": 1}, headers=hdr)
        assert r.status == 409
        prog = await (await s.get(Rm + "/api/learn/progress", headers=hdr)).json()
        assert prog["device"] == dev.id and prog["entries"] == []
        prog = await (await s.get(L + f"/api/learn/progress?dossier={d.id}")).json()
        assert [e["kind"] for e in prog["entries"]].count("hint") == 5
        # explain it back: graded, the gap is leak-checked against the verified proof
        eb = await (await s.post(u + "/explain-back", json={"text": "a et b sont des doubles a = 2k, donc..."})).json()
        assert eb["met"] == 1 and eb["total"] == 2 and eb["redacted"] and "omega" not in eb["gap"]
        assert eb["graded_against"] == "lean_verified_proof"
        # tokens: curated tactic, retriever declaration, unknown name never invented
        t = await (await s.get(L + "/api/learn/token?name=omega")).json()
        assert t["kind"] == "tactic" and t["known"]
        t = await (await s.get(L + "/api/learn/token?name=Even.add")).json()
        assert t["kind"] == "declaration" and t["doc"] and t["source"] == "retriever"
        t = await (await s.get(L + "/api/learn/token?name=Nat.even_add_one_fake")).json()
        assert t["known"] is False and "doc" not in t and "signature" not in t and "inconnu" in t["text"]
        # unproved dossier: no learn mode
        d2 = ctx.repo.new("x", "demo", "x")
        await ctx.repo.save(d2)
        assert (await s.post(L + f"/api/learn/{d2.id}/attempt", json={"text": "abc"})).status == 409


async def test_faded_and_erroneous_exercises_real_lean(tmp_path, ws):
    ctx = make_ctx(tmp_path, ws=ws, brain=FakeBrain(leaky))
    async with running(ctx) as (_s, L, _R), session() as s:
        d = _seed(ctx)
        await ctx.repo.save(d)
        u = L + f"/api/learn/{d.id}"
        r = await s.post(u + "/exercises/faded", json={"k": 1})
        ex = await r.json()
        assert r.status == 200, ex
        assert ex["k"] == 1 and ex["verified"]["original_compiles"] and ex["verified"]["holes_compile"]
        assert ex["blanks"][0] in ex["verified"]["nontrivial"] and "solutions" not in ex
        assert ex["template"].count("sorry") == 1
        doc = ctx.research.tutor.store.doc(d.id)["exercises"][ex["id"]]
        good = doc["solutions"][str(ex["blanks"][0])]
        r = await s.post(u + f"/exercises/{ex['id']}/submit", json={"fills": [good]})
        j = await r.json()
        assert j["checked"] and j["ok"] is True, j
        r = await s.post(u + f"/exercises/{ex['id']}/submit", json={"fills": ["exact ⟨k, by omega⟩"]})
        j = await r.json()
        assert j["ok"] is False and j["check"]["errors"]
        r = await s.post(u + f"/exercises/{ex['id']}/submit", json={"fills": ["sorry"]})
        assert (await r.json())["ok"] is False
        # erroneous example: Lean really rejects it; its error is revealed after the diagnosis
        r = await s.post(u + "/exercises/erroneous")
        er = await r.json()
        assert r.status == 200, er and "lean_error" not in er
        assert er["wrong_proof"] != PROOF and len(er["prompts"]) == 3
        r = await s.post(u + f"/exercises/{er['id']}/submit", json={})
        assert r.status == 409
        r = await s.post(u + f"/exercises/{er['id']}/submit", json={"diagnosis": "la dernière étape manque"})
        j = await r.json()
        assert j["checked"] is False and j["lean_error"]
        fixed = PROOF.split(":= by\n", 1)[1]
        r = await s.post(u + f"/exercises/{er['id']}/submit", json={"code": fixed, "diagnosis": "x"})
        assert (await r.json())["ok"] is True
        prog = (await (await s.get(L + f"/api/learn/progress?dossier={d.id}")).json())["entries"]
        assert [e["ok"] for e in prog if e["kind"] == "exercise_submit"] == [True, False, False, True]


def test_tactic_blocks():
    head, sig, lines = L_.split_proof(leancheck.GOEDEL_HEADER + PROOF)
    assert sig.startswith("theorem sum_even") and len(lines) == 3
    assert L_.tactic_blocks(lines) == [[0], [1], [2]]
    _h, _s, l2 = L_.split_proof("theorem t : True := by\n  constructor\n  · simp\n    rfl\n  · exact x\n")
    assert L_.tactic_blocks(l2) == [[0], [1, 2], [3]]
    _h, _s, l3 = L_.split_proof("theorem t : True := by trivial\n")
    assert l3 == ["  trivial"]
    with pytest.raises(L_.LearnError):
        L_.split_proof("theorem t : True := trivial\n")


async def test_ui_shaped_endpoints(tmp_path):
    """The web UI's Tutor interface (web/src/lib/learn/tutor.ts) maps onto POST /dossiers/{id}/hint and
    /dossiers/{id}/explain-back; progress follows the device on the server."""
    ctx = make_ctx(tmp_path, brain=FakeBrain(leaky))
    async with running(ctx) as (_s, L, _R), session() as s:
        d = _seed(ctx)
        await ctx.repo.save(d)
        u = L + f"/api/dossiers/{d.id}"
        r = await s.post(u + "/hint", json={"level": "nudge", "tried": "", "help": "concept", "reflections": []})
        assert r.status == 409 and (await r.json())["error"] == "attempt_first"
        h = await (await s.post(u + "/hint", json={"level": "nudge", "tried": "simp ne marche pas", "help": "concept",
                                                  "reflections": []})).json()
        assert h["level"] == 1 and h["level_name"] == "nudge" and h["text"]
        await s.post(u + "/hint", json={"level": "strategy", "tried": "x", "reflections": ["la parité"]})
        h3 = await (await s.post(u + "/hint", json={"level": "lemma", "reflections": ["la parité", "écrire a = 2k"]})).json()
        assert h3["level"] == 3
        r = await s.post(u + "/explain-back", json={"target": "proof", "text": "a et b sont des doubles a = 2k donc",
                                                    "previous": ["Q: ?", "A: !"]})
        j = await r.json()
        assert r.status == 200 and j["text"] and j["target"] == "proof" and "Previous exchanges" in \
            ctx.brain.requests[-1]["messages"][0]["content"]
        d2 = ctx.repo.new("x", ctx.settings.workspace, "énoncé seul")
        d2.add_statement(leancheck.prepare_statement("theorem z (n : ℕ) : n + 0 = n := by sorry"))
        await ctx.repo.save(d2)
        r = await s.post(L + f"/api/dossiers/{d2.id}/explain-back", json={"target": "statement",
                                                                         "text": "pour tout entier n, n + 0 = n"})
        assert r.status == 200 and (await r.json())["graded_against"] == "lean_statement"
        kinds = [e["kind"] for e in (await (await s.get(L + "/api/learn/progress")).json())["entries"]]
        assert kinds.count("hint") == 3 and kinds.count("attempt") == 1 and kinds.count("explain_back") == 2
