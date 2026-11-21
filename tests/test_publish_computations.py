"""Calcul notebook → « Calculs » page of the published site (S-W, TODO P1 10): cells, outputs, figures as static SVG,
maths rendered with KaTeX at build time, notebooks downloadable; bad input refused."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from madalean.research import calcul as cal
from madalean.research import notebook as nbm
from madalean.research.sagebridge import ExecResult

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
from madasite import computations, figure  # noqa: E402

PNG_RAW = cal.PNG_MAGIC + b"\x00" * 40
PNG = base64.b64encode(PNG_RAW).decode()
SAMPLE = ROOT / "site" / "publication" / "sample"


def _store(tmp_path):
    st = nbm.NotebookStore(tmp_path / "nb", tmp_path / "meta")
    st.docs("p1")
    st.add("p1", "On calcule $\\sqrt{2}$ :", kind="markdown")
    c = st.add("p1", "sqrt(2)")
    st.record_run("p1", c["id"], ExecResult("ok", execution_count=1, outputs=[
        {"output_type": "display_data", "metadata": {}, "data": {"image/png": PNG, "text/plain": "Graphics"}},
        {"output_type": "execute_result", "execution_count": 1, "metadata": {},
         "data": {"text/latex": "\\sqrt{2} \\in \\Bold{R}", "text/plain": "sqrt(2)"}}]), "host", c["code_hash"],
        upstream=st.upstream_of("p1", "calcul", c["id"]), approx="1.41421356237310")
    f = st.add("p1", "fig(sin(x)/x, x^2 + y^2 == 4)")
    st.record_run("p1", f["id"], ExecResult("ok", execution_count=2, outputs=[
        {"output_type": "display_data", "metadata": {}, "data": {
            nbm.FIGURE_MIME: {"v": 1, "view": {"xmin": -5, "xmax": 5, "ymin": -3, "ymax": 3}, "objects": [],
                              "curves": [{"id": "c0", "expr": "sin(x)/x"}, {"id": "c1", "expr": "x^2+y^2=4"}],
                              "points": [{"x": 1, "y": 2, "label": "A"}]},
            "text/plain": "Figure: 2 curve(s), 1 point(s)"}}]), "host", f["code_hash"],
        upstream=st.upstream_of("p1", "calcul", f["id"]))
    e = st.add("p1", "1/0")
    st.record_run("p1", e["id"], ExecResult("error", execution_count=3, outputs=[
        {"output_type": "error", "ename": "ZeroDivisionError", "evalue": "rational division by zero",
         "traceback": []}]), "host", e["code_hash"], upstream=st.upstream_of("p1", "calcul", e["id"]))
    st.add("p1", "", kind="figure", figure={"v": 1, "curves": [{"id": "f1", "expr": "x^3"}], "objects": []})
    st.set_engine("p1", "calcul", {"name": "SageMath", "version": "10.10"})
    return st


def test_figure_renderer_draws_every_kind_of_curve():
    for expr, kind in (("sin(x)/x", "explicit"), ("y = 1/x", "explicit"), ("x^2+y^2=4", "implicit"),
                       ("r = 1 + cos(θ)", "polar"), ("(cos(t), sin(2t))", "parametric"), ("2x+1", "explicit"),
                       ("xy = 1", "implicit")):
        assert figure.parse_curve(expr)[0] == kind, expr
    svg, desc = figure.render({"view": {"xmin": -5, "xmax": 5, "ymin": -3, "ymax": 3},
                               "curves": [{"id": "a", "expr": "sin(x)/x"}, {"id": "b", "expr": "x^2+y^2=4"},
                                          {"id": "c", "expr": "__import__('os')"}],
                               "graph": {"vertices": ["0", "1"], "edges": [["0", "1"]], "pos": {"0": [0, 0], "1": [1, 1]}}})
    assert svg.startswith("<svg") and svg.count("<path") >= 4 and "<script" not in svg and "style=" not in svg
    assert "sin(x)/x" in desc and "non dessinée" in desc and "2 sommets" in desc
    # a curve never evaluates Python: names other than the grammar's are refused
    with pytest.raises(figure.ExprError):
        figure.compile_expr("__import__('os').system('x')")
    assert figure.render({"view": "nonsense", "curves": "x"})[0].startswith("<svg")


def test_validation_keeps_paths_inside_files_calcul():
    ok = {"documents": [{"id": "calcul", "notebook": "files/calcul/calcul.ipynb", "cells": [
        {"kind": "code", "outputs": [{"kind": "image", "path": "files/calcul/abc.png"}]}]}]}
    assert computations.validate(ok) == []
    bad = json.loads(json.dumps(ok))
    bad["documents"][0]["cells"][0]["outputs"][0]["path"] = "files/calcul/../../etc/passwd"
    assert computations.validate(bad)
    bad["documents"][0]["notebook"] = "/etc/passwd"
    assert len(computations.validate(bad)) == 2
    assert computations.katex_tex("$$\\Bold{Z} \\to \\QQ$$") == "\\mathbb{Z} \\to \\mathbb{Q}"


@pytest.mark.skipif(not shutil.which("node"), reason="node (KaTeX) not installed")
def test_published_site_has_the_computations_page(tmp_path):
    st = _store(tmp_path)
    inp = tmp_path / "input"
    shutil.copytree(SAMPLE, inp)
    comp = nbm.publication_computations(st, "p1", inp / "files")
    latex = next(o for c in comp["documents"][0]["cells"] for o in c.get("outputs") or [] if o["kind"] == "latex")
    assert latex["text"] == "sqrt(2)"
    pub = json.loads((inp / "publication.json").read_text(encoding="utf-8"))
    pub["computations"] = comp
    (inp / "publication.json").write_text(json.dumps(pub, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "site" / "build.py"), "publication", "--input", str(inp),
                        "--out", str(out)], capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    page = (out / "computations.html").read_text(encoding="utf-8")
    lg = pub["lang"]
    assert computations.T[lg]["title"] in page
    assert 'href="computations.html"' in (out / "index.html").read_text(encoding="utf-8")       # in the menu
    assert 'class="katex' in page and "\\Bold" not in page                                    # maths by KaTeX
    assert "sqrt(2)" in page and "1.41421356237310" in page                                    # code + approx value
    assert "ZeroDivisionError" in page
    assert (out / "files" / "calcul" / "calcul.ipynb").is_file() and 'href="files/calcul/calcul.ipynb"' in page
    figs = sorted((out / "files" / "calcul").glob("fig-*.svg"))
    assert len(figs) == 2                                                    # fig() output + Figure cell without SVG
    assert all(f.read_text().startswith("<svg") for f in figs)
    assert any(p.suffix == ".png" and p.read_bytes() == PNG_RAW for p in (out / "files" / "calcul").iterdir())


async def test_plan_adds_the_computations_and_lists_their_files(tmp_path):
    """POST …/publish/{pid}/plan: the notebooks of the project go into publication.json and every file appears in
    the list of what leaves the machine; `computations: false` leaves them out."""
    from test_article_publish import fake_workspace, setup_project
    from helpers import make_ctx, running, session
    from madalean.research import publish
    from madalean.server.plugins import workbench as wbm
    ctx = make_ctx(tmp_path, ws=fake_workspace(tmp_path), fake_lean=True)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            pid, _ds, _paper, _lib = await setup_project(s, local, ctx)
            st = srv.app[wbm.WB].calc
            st.docs(pid)
            st.add(pid, "Une note de calcul : $x^2$.", kind="markdown")
            st.add(pid, "", kind="figure", figure={"v": 1, "curves": [{"id": "f", "expr": "x^2"}], "objects": []})
            async with s.post(local + f"/api/research/publish/{pid}/plan", json={}) as r:
                assert r.status == 200, await r.text()
                man = (await r.json())["manifest"]
            assert any(i["path"].startswith("files/calcul/") and i["kind"] == "calcul" for i in man["items"])
            pub = json.loads((publish.pub_dir(ctx, pid) / "input" / "publication.json").read_text(encoding="utf-8"))
            assert [c["kind"] for c in pub["computations"]["documents"][0]["cells"]] == ["markdown", "figure"]
            async with s.post(local + f"/api/research/publish/{pid}/plan", json={"computations": False}) as r:
                man = (await r.json())["manifest"]
            assert not any(i["path"].startswith("files/calcul/") for i in man["items"])
            async with s.post(local + f"/api/research/publish/{pid}/plan", json={"computations": "yes"}) as r:
                assert r.status == 400
