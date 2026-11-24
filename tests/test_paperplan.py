"""« De l'article au plan formel » (TODO Stratégie 2.1 item 6, D60): structure of a small LaTeX paper (statements
verbatim, labels, exact dependency graph, nothing invented), closure of a selection, exports, and the formal plan
with a fake model and the REAL Lean (statements compiled, Mathlib-first, a top-level dossier with a sub-dossier,
conditional until Lean proves the lemma, budgeted and resumed)."""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import os
import re
import time
from pathlib import Path

from helpers import make_ctx, running, session, wait_idle
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import fulltext as ft
from madalean.research import paperplan as PP
from madalean.research import papers

DATA = Path(__file__).parent / "data" / "paperplan"
TEX = (DATA / "small.tex").read_text(encoding="utf-8")
SRC = {"id": "s-small00001", "key": "small2026"}


def blueprint() -> dict:
    bp = papers.blueprint_from_tex(ft.parse_tex(TEX), SRC)
    bp["shelf"] = ""
    return bp


def edges(bp) -> set[tuple[str, str, str]]:
    return {(n["id"], u["to"], u["via"]) for n in bp["nodes"] for u in n["uses"]}


# ---------------------------------------------------------------- structure (deterministic)
def test_tex_structure_is_extracted_with_numbers_labels_and_verbatim_text():
    bp = blueprint()
    got = [(n["id"], n["kind"], n["number"], n["label"]) for n in bp["nodes"]]
    assert got == [("n-def-double", "definition", "1.1", "def:double"), ("n-lem-assoc", "lemma", "1.2", "lem:assoc"),
                   ("n-lem-comm", "lemma", "1.3", "lem:comm"), ("n-lem-square", "lemma", "1.4", "lem:square"),
                   ("n-thm-main", "theorem", "2.1", "thm:main"), ("n-thm-late", "theorem", "2.2", "thm:late"),
                   ("n-prop-alone", "proposition", "2.3", "prop:alone")]          # the remark is not a result
    lines = TEX.split("\n")
    for n in bp["nodes"]:
        assert n["verbatim"] and n["verbatim"] in TEX, n["id"]              # quoted verbatim from the source
        assert n["label"] in lines[n["line"] - 1], (n["id"], n["line"])     # and located
    assert next(n for n in bp["nodes"] if n["id"] == "n-lem-comm")["title"] == "Commutativity"
    st = PP.plan_status(make_ctx_stub(), bp)["nodes"]["n-thm-main"]
    assert st["location"] == "Theorem 2.1, §2, l. 38" and st["verbatim"].startswith("\\label{thm:main}")


def make_ctx_stub():
    class Repo:
        def get(self, _did):
            return None
    return type("Ctx", (), {"repo": Repo()})()


def test_dependency_graph_is_exactly_the_references_and_nothing_is_invented():
    bp = blueprint()
    assert edges(bp) == {("n-lem-square", "n-lem-comm", "proof_ref"),              # a proof environment
                         ("n-thm-main", "n-lem-square", "proof_ref"),              # a proof citing two lemmas
                         ("n-thm-main", "n-lem-assoc", "proof_ref"),
                         ("n-thm-late", "n-def-double", "proof_ref")}              # a « Proof of Theorem » section
    nodes = {n["id"]: n for n in bp["nodes"]}
    assert nodes["n-prop-alone"]["uses"] == [] and nodes["n-lem-assoc"]["uses"] == []   # unknown stays unknown
    assert nodes["n-thm-main"]["cites"] == ["euclid"]
    # closure: dependencies first; mains: the selected results no other selected result uses
    assert PP.closure(bp, ["n-thm-main"]) == ["n-lem-assoc", "n-lem-comm", "n-lem-square", "n-thm-main"]
    assert PP.closure(bp, ["n-thm-late"]) == ["n-def-double", "n-thm-late"]
    assert PP.closure(bp, ["n-prop-alone"]) == ["n-prop-alone"]
    assert PP.mains(bp, ["n-thm-main", "n-lem-square", "n-prop-alone"]) == ["n-thm-main", "n-prop-alone"]
    # a model-proposed edge is shown but not followed until the user accepts it
    assert papers.apply_model_uses(bp, '[{"from": "n-prop-alone", "to": "n-lem-comm"}, {"from": "x", "to": "y"}]') == 1
    assert PP.closure(bp, ["n-prop-alone"]) == ["n-prop-alone"]
    next(u for u in nodes["n-prop-alone"]["uses"] if u["to"] == "n-lem-comm")["accepted"] = True
    assert PP.closure(bp, ["n-prop-alone"]) == ["n-lem-comm", "n-prop-alone"]
    # a cycle in the references is cut, never followed forever
    nodes["n-lem-assoc"]["uses"].append({"to": "n-thm-main", "via": "user", "proposed": False})
    assert sorted(PP.closure(bp, ["n-thm-main"])) == ["n-lem-assoc", "n-lem-comm", "n-lem-square", "n-thm-main"]


def test_pdf_statements_keep_the_text_layer_verbatim():
    blocks = [(1, "Lemma 1.1. Every prime p > 2 is odd."), (1, "Proof. Otherwise 2 divides p. □"),
              (2, "Theorem 1.2. There are infinitely many primes."), (2, "Proof. By Lemma 1.1 and Euclid. □")]
    bp = papers.blueprint_from_blocks(blocks, {"id": "s-pdf0000001", "key": "p"})
    assert [n["verbatim"] for n in bp["nodes"]] == ["Every prime p > 2 is odd.", "There are infinitely many primes."]
    assert edges(bp) == {("n-theorem-1-2", "n-lemma-1-1", "text_ref")}
    assert PP.location(bp, bp["nodes"][1]) == "Theorem 1.2, p. 2"


def test_exports_are_blueprint_style_and_escaped():
    bp = blueprint()
    nodes = {n["id"]: n for n in bp["nodes"]}
    nodes["n-lem-assoc"]["formal"] = {"status": "in_mathlib", "compiled": True, "name": "paper_lem_assoc",
                                      "lean": "theorem paper_lem_assoc (a b c : ℕ) : a + b + c = a + (b + c) := by sorry",
                                      "mathlib_name": "Nat.add_assoc"}
    nodes["n-thm-main"]["formal"] = {"status": "to_prove", "compiled": True, "name": "paper_thm_main",
                                     "lean": "theorem paper_thm_main : True := by sorry <script>", "dossier_id": ""}
    bp["plan"] = {"order": PP.closure(bp, ["n-thm-main"])}
    st = PP.plan_status(make_ctx_stub(), bp)
    assert st["progress"] == {"proved": 0, "in_mathlib": 1, "to_prove": 0, "formalised": 1, "unformalised": 2,
                              "total": 4, "done": 1}
    assert set(st["nodes"]["n-thm-main"]["rests_on"]) == {"n-lem-square", "n-lem-comm"}   # transitively, unproved
    tex = PP.export_tex(bp, st)
    assert "\\lean{paper_lem_assoc}\n\\mathlibok" in tex and "\\uses{lem:square,lem:assoc}" in tex
    assert nodes["n-thm-main"]["verbatim"] in tex and "n-thm-late" not in tex      # only the selection's closure
    page = PP.export_html(bp, st, "en")
    assert "<script>" not in page and "&lt;script&gt;" in page and "in Mathlib" in page and "1/4" in page


# ---------------------------------------------------------------- the formal plan (fake model, REAL Lean)
LEAN = {
    "+ c = a a": "(a b c : ℕ) : (a + b) * (a + b) + c = a * a + (b * (2 * a + b) + c)",
    "(a + b)(a + b) = a a": "(a b : ℕ) : (a + b) * (a + b) = a * a + b * (2 * a + b)",
    "a + b + c = a + (b + c)": "(a b c : ℕ) : a + b + c = a + (b + c)",
    "a + b = b + a": "(a b : ℕ) : a + b = b + a",
}


def paper_brain(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if first.startswith("Please autoformalize"):
        name = re.search(r"Use the following theorem name: (\S+)", first).group(1)
        brain.behaviour.setdefault("formalized", []).append(first)
        for key, sig in LEAN.items():
            if key in first:
                return f"```lean4\nimport Mathlib\n\ntheorem {name} {sig} := by sorry\n```"
        return "no idea"
    if "Complete the following Lean 4 code" in first:
        m = re.search(r"theorem (\w+)", first.split("```")[-2] if "```" in first else first)
        return f"```lean4\nimport Mathlib\n\ntheorem {m.group(1)} {LEAN['(a + b)(a + b) = a a']} := by\n  ring\n```"
    return demo_responder(role, messages, brain)


async def _wait_run(s, url, timeout=900):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        st = await (await s.get(url)).json()
        if st.get("run") and not st["run"]["running"]:
            return st
        await asyncio.sleep(0.2)
    raise TimeoutError(url)


async def test_formal_plan_real_lean_budget_resume_subdossier_and_conditional(tmp_path, ws):
    brain = FakeBrain(paper_brain, online=True)
    ctx = make_ctx(tmp_path, ws=ws, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        ctx.settings.statement_check = ctx.settings.mathlib_first = ctx.settings.certificates = False
        pid = (await (await s.post(L + "/api/projects", json={"title": "Papier", "workspace": ws.key})).json())[
            "project"]["id"]
        bp = blueprint()
        bp["shelf"] = pid
        papers.save(ctx, pid, bp)
        base = L + f"/api/research/projects/{pid}/blueprints/{SRC['id']}"
        bad = await s.post(base + "/plan", json={"nodes": ["n-nope"]})
        assert bad.status == 400
        # run 1: budget of 2 statements → the two first nodes of the closure only, no dossier yet
        r = await s.post(base + "/plan", json={"nodes": ["n-thm-main"], "statements": 2})
        assert r.status == 202, await r.text()
        assert (await r.json())["order"] == ["n-lem-assoc", "n-lem-comm", "n-lem-square", "n-thm-main"]
        st = await _wait_run(s, base + "/plan")
        assert st["run"]["reason"] == "budget" and st["run"]["done"] == 2
        n = st["nodes"]
        assert n["n-lem-assoc"]["status"] == "in_mathlib" and n["n-lem-comm"]["status"] == "in_mathlib", n
        assert n["n-lem-assoc"]["mathlib_name"] and n["n-lem-assoc"]["compiled"]
        assert "theorem paper_lem_assoc (a b c : ℕ)" in n["n-lem-assoc"]["lean"]
        assert n["n-lem-square"]["status"] == "unformalised" and not n["n-lem-square"]["tried"]
        assert not ctx.repo.list(pid)
        asked = list(brain.behaviour["formalized"])
        assert len(asked) == 2 and all("Result quoted verbatim from the paper small2026" in q for q in asked)
        # run 2 resumes: the done nodes are skipped (no model call for them), the rest is formalised
        r = await s.post(base + "/plan", json={"nodes": ["n-thm-main"], "statements": 4})
        st = await _wait_run(s, base + "/plan")
        assert st["run"]["reason"] == "complete" and st["run"]["skipped"] == 2 and st["run"]["done"] == 2, st["run"]
        assert len(brain.behaviour["formalized"]) == 4
        n = st["nodes"]
        assert n["n-lem-square"]["status"] == "to_prove" and n["n-thm-main"]["status"] == "to_prove", n
        assert n["n-thm-main"]["rests_on"] == ["n-lem-square"]                     # conditional
        assert st["progress"]["done"] == 2 and st["progress"]["total"] == 4
        # one top-level dossier for the main theorem, a sub-dossier for the lemma to prove; nothing started
        top = ctx.repo.get(n["n-thm-main"]["dossier_id"])
        sub = ctx.repo.get(n["n-lem-square"]["dossier_id"])
        assert top is not None and not top.parent_id and sub is not None and sub.parent_id == top.id
        assert top.statement and "(a + b) * (a + b) + c" in top.statement and top.source["original_text"]
        assert not ctx.orchestrator.active_for(top.id) and not ctx.orchestrator.active_for(sub.id)
        g = ctx.research.graphs.get(top.id)
        kinds = sorted((x["kind"], x["status"]) for x in g["nodes"].values())
        assert kinds == [("cited", "cited"), ("goal", "open"), ("mathlib", "mathlib"), ("mathlib", "mathlib")], kinds
        cited = next(x for x in g["nodes"].values() if x["kind"] == "cited")
        assert cited["dossier_id"] == sub.id and cited["claimed"] == "proved" and cited["source"]["kind"] == "paper"
        assert [g["root"], "uses", cited["id"]] in g["edges"]
        # a third run changes nothing (idempotent): no new dossier, no model call
        r = await s.post(base + "/plan", json={"nodes": ["n-thm-main"]})
        st = await _wait_run(s, base + "/plan")
        assert len(ctx.repo.list(pid)) == 2 and len(brain.behaviour["formalized"]) == 4
        # Lean proves the lemma (normal pipeline job on the sub-dossier) → « prouvé », the main no longer rests on it
        job = ctx.orchestrator.submit(sub.id, [{"stage": "proof"}])
        await wait_idle(ctx, 600)
        assert ctx.repo.get(sub.id).proof_is_current, job.to_dict()
        st = await (await s.get(base + "/plan")).json()
        assert st["nodes"]["n-lem-square"]["status"] == "proved" and st["nodes"]["n-thm-main"]["rests_on"] == []
        assert st["progress"]["done"] == 3
        g = ctx.research.graphs.ensure(top.id)
        cited = next(x for x in g["nodes"].values() if x.get("dossier_id") == sub.id)
        assert cited["status"] == "proved"                                       # rolled up by the graph service
        # exports
        tex = await (await s.get(base + "/export?format=tex")).text()
        assert "\\lean{paper_lem_square}\n\\leanok" in tex and "\\mathlibok" in tex
        page = await s.get(base + "/export?format=html&lang=en")
        assert page.status == 200 and "attachment" in page.headers["Content-Disposition"]


# ---------------------------------------------------------------- arXiv LaTeX source path
ARXIV = json.loads((DATA / "arxiv-1907.00847.json").read_text(encoding="utf-8"))


async def _eprint_blueprint(data: bytes, key: str, tmp_path) -> tuple[dict, str, list]:
    from madalean.research import litsearch, safety
    from madalean.research.fetch import Fetcher, ReplayTransport
    t = ReplayTransport(tmp_path / "none", strict=True)
    t.add(ARXIV["url"], data, content_type=ARXIV["content_type"])
    body, ctype = await litsearch.arxiv_source(Fetcher(t), "1907.00847", "online")
    assert t.requests == [ARXIV["url"]] and ctype == ARXIV["content_type"]
    root = tmp_path / "x"
    ex = safety.extract_archive(body, root)
    tex = ft.find_main_tex(root).read_text(encoding="utf-8", errors="replace")
    return papers.blueprint_from_tex(ft.parse_tex(tex, root), {"id": "s-arxiv000001", "key": key}), tex, ex.files


async def test_arxiv_eprint_path_gives_the_tex_structure(tmp_path):
    """The path of a real arXiv e-print (a gzipped single TeX file, as recorded on 2026-11-24) end to end, on our own
    fixture paper; the real answer is re-checked against the recorded structure when a local copy is given
    (MADALEAN_ARXIV_EPRINT: its source is not redistributed here)."""
    bp, _tex, files = await _eprint_blueprint(gzip.compress(TEX.encode()), "small2026", tmp_path)
    assert files == ["main.tex"] and len(bp["nodes"]) == 7
    assert edges(bp) == edges(blueprint())
    real = os.environ.get("MADALEAN_ARXIV_EPRINT")
    if real and Path(real).is_file():
        data = Path(real).read_bytes()
        assert hashlib.sha256(data).hexdigest() == ARXIV["sha256"] and len(data) == ARXIV["bytes"]
        bp, tex, files = await _eprint_blueprint(data, "huang2019", tmp_path / "real")
        assert files == ARXIV["extracted"] and bp["title"] == ARXIV["title"]
        assert [[n["id"], n["kind"], n["number"], n["label"], n["line"]] for n in bp["nodes"]] == ARXIV["nodes"]
        assert sorted(list(e) for e in edges(bp)) == sorted(ARXIV["edges"])
        assert all(n["verbatim"] in tex for n in bp["nodes"])
