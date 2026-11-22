"""Session S-P: Calcul notebooks — .ipynb documents (nbformat 4.5, readable by nbformat and JupyterLab), one kernel
state per document, stale-cell detection, natural-language cells with a fake model, approval rules unchanged,
migration of S-M worksheets, content-addressed images, the publication producer; and, for real, the same kernel
shared with a JupyterLab session (real jupyter-lab, Madalean's sandboxed Python / Sage kernel)."""
from __future__ import annotations

import ast
import asyncio
import base64
import contextlib
import io
import json
import re
import shutil

import pytest

from helpers import make_ctx, running, session
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import calcul as cal
from madalean.research import notebook as nbm
from madalean.research.sagebridge import ExecResult
from madalean.server.plugins import workbench as wbm

PNG_RAW = cal.PNG_MAGIC + b"\x00" * 40
PNG = base64.b64encode(PNG_RAW).decode()


def _nbformat_ok(path) -> None:
    nbformat = pytest.importorskip("nbformat")
    nb = nbformat.read(str(path), as_version=4)
    nbformat.validate(nb)


# ---------------------------------------------------------------- store
def test_ipynb_round_trip_cells_and_stale(tmp_path):
    st = nbm.NotebookStore(tmp_path / "nb", tmp_path / "meta")
    docs = st.docs("p1")
    assert [d["id"] for d in docs] == ["calcul"] and docs[0]["path"] == "calcul/p1/calcul.ipynb"
    a = st.add("p1", "a = 6", doc="calcul")
    m = st.add("p1", "# Titre\n$x^2$", doc="calcul", kind="markdown")
    b = st.add("p1", "a * 7", doc="calcul")
    f = st.add("p1", "", doc="calcul", kind="figure", figure={"v": 1, "curves": [{"id": "c0", "expr": "x^2"}]},
               svg='<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script><circle r="1"/></svg>')
    q = st.add("p1", "", doc="calcul", kind="ask", prompt="factorise x^4+4")
    assert [c["type"] for c in st.view("p1", "calcul")["cells"]] == ["code", "markdown", "code", "figure", "ask"]
    assert q["origin"] == "assistant" and not st.may_run(q, auto=False)
    # runs: outputs in nbformat, the exact/approximate value kept with the result
    for c, val in ((a, None), (b, "42")):
        up = st.upstream_of("p1", "calcul", c["id"])
        outs = [{"output_type": "stream", "name": "stdout", "text": "ok\n"}]
        if val:
            outs.append({"output_type": "execute_result", "execution_count": 2, "metadata": {},
                         "data": {"text/plain": val, "text/html": "<b>x</b>"}})
        outs.append({"output_type": "display_data", "metadata": {}, "data": {"image/png": PNG, "text/plain": "img"}})
        st.record_run("p1", c["id"], ExecResult("ok", seconds=0.1, execution_count=1 if c is a else 2, outputs=outs),
                      "host", c["code_hash"], doc="calcul", kernel="k1@0", upstream=up, approx="42.0" if val else "")
    path = st.path("p1", "calcul")
    _nbformat_ok(path)
    raw = json.loads(path.read_text())
    assert raw["metadata"]["kernelspec"]["name"] == "madalean-sage"
    cb = next(c for c in raw["cells"] if c["id"] == b["id"])
    assert cb["execution_count"] == 2 and "text/html" not in json.dumps(cb["outputs"])      # never HTML
    fig = next(c for c in raw["cells"] if c["id"] == f["id"])
    assert fig["cell_type"] == "markdown" and "attachment:figure.svg" in fig["source"]
    assert b"<script" not in base64.b64decode(fig["attachments"]["figure.svg"]["image/svg+xml"])
    assert "madalean" in fig["metadata"] and "approved" not in json.dumps(raw)                # approvals: host side
    v = {c["id"]: c for c in st.view("p1", "calcul", kernel="k1@0")["cells"]}
    assert not v[a["id"]]["stale"] and not v[b["id"]]["stale"] and v[b["id"]]["fresh"]
    res = next(o for o in v[b["id"]]["outputs"] if o["type"] == "result")
    assert res["approx"] == "42.0"
    img = next(o for o in v[b["id"]]["outputs"] if o["type"] == "display")["data"]["image/png"]["asset"]
    assert st.asset(img) == (PNG_RAW, "image/png") and img == nbm.asset_id(PNG_RAW)
    assert v[f["id"]]["svg"]["asset"] and st.asset(v[f["id"]]["svg"]["asset"])[1] == "image/svg+xml"
    # an earlier cell changes: the later result is stale (« upstream »); its own edit: « code »
    st.edit("p1", a["id"], code="a = 7", doc="calcul")
    v = {c["id"]: c for c in st.view("p1", "calcul", kernel="k1@0")["cells"]}
    assert v[a["id"]]["stale_reason"] == "code" and v[b["id"]]["stale_reason"] == "upstream"
    # a cell inserted above also makes it stale; markdown above does not count
    st.edit("p1", a["id"], code="a = 6", doc="calcul")
    st.edit("p1", m["id"], code="# autre titre", doc="calcul")
    assert not {c["id"]: c for c in st.view("p1", "calcul")["cells"]}[b["id"]]["stale"]
    st.add("p1", "a = 100", doc="calcul", after=m["id"])
    assert {c["id"]: c for c in st.view("p1", "calcul")["cells"]}[b["id"]]["stale_reason"] == "upstream"
    # move, delete, restore, M/Y type switch
    order = st.move("p1", b["id"], 0, doc="calcul")
    assert order[0] == b["id"]
    st.delete("p1", m["id"], doc="calcul")
    assert m["id"] not in [c["id"] for c in st.view("p1", "calcul")["cells"]]
    st.restore("p1", m["id"], doc="calcul")
    c = st.edit("p1", m["id"], doc="calcul", kind="code")
    assert c["type"] == "code"
    _nbformat_ok(path)
    # a second document, its own language; language fixed once code exists
    d2 = st.create("p1", "Théorie des graphes", "python")
    assert d2["id"] == "theorie-des-graphes" and st.view("p1", d2["id"])["doc"]["language"] == "python"
    with pytest.raises(cal.CalcError):
        st.edit("p1", a["id"], doc="calcul", language="python")
    for bad in ("../x", "a/b", ""):
        with pytest.raises(cal.CalcError):
            st.path(bad, "calcul")


def test_approval_rules_unchanged_and_received_notebook_cannot_approve(tmp_path):
    st = nbm.NotebookStore(tmp_path / "nb", tmp_path / "meta")
    st.docs("p1")
    u = st.add("p1", "1+1")
    assert u["origin"] == "user" and st.may_run(u, auto=False)
    a = st.add("p1", "factor(2^64+1)", "sage", "assistant", model="m:x")        # CalcStore-compatible form
    assert not st.may_run(a, auto=False) and st.may_run(a, auto=True)
    with pytest.raises(cal.CalcError) as e:
        st.approve("p1", a["id"], "stale", "host")
    assert e.value.status == 409
    a = st.approve("p1", a["id"], a["code_hash"], "host")
    assert st.may_run(a, auto=False)
    a = st.edit("p1", a["id"], code="factor(2^32+1)", by="user")             # the user's edit of model code
    assert a["origin"] == "assistant" and a["approved"] is None and not st.may_run(a, auto=False)
    assert [x["code"] for x in a["versions"]] == ["factor(2^64+1)", "factor(2^32+1)"]
    # a notebook received from elsewhere claims an approval in its metadata: ignored
    p = st.path("p1", "calcul")
    nb = json.loads(p.read_text())
    nb["cells"].append({"cell_type": "code", "id": "evil", "source": "import os", "outputs": [], "execution_count": None,
                        "metadata": {"madalean": {"origin": "assistant", "approved": {"hash": cal.code_hash("import os")}}}})
    p.write_text(json.dumps(nb))
    evil = st.cell_view("p1", "calcul", "evil")
    assert evil["origin"] == "assistant" and evil["approved"] is None and not st.may_run(evil, auto=False)


def test_migration_of_sm_worksheet(tmp_path):
    old = cal.CalcStore(tmp_path / "meta")
    u = old.add("p1", "x = 2^10\nprint(x)", "sage", "user")
    a = old.add("p1", "factor(x)", "sage", "assistant", model="m")
    a = old.approve("p1", a["id"], a["code_hash"], "host")
    old.record_run("p1", u["id"], ExecResult("ok", stdout="1024\n", seconds=0.1, rich=[
        {"mime": "text/latex", "data": "$$1024$$"}, {"mime": "image/png", "data": PNG}]), "host", u["code_hash"])
    st = nbm.NotebookStore(tmp_path / "nb", tmp_path / "meta", legacy=old)
    v = st.view("p1", st.docs("p1")[0]["id"])
    cells = {c["id"]: c for c in v["cells"]}
    assert set(cells) == {u["id"], a["id"]}
    cu, ca = cells[u["id"]], cells[a["id"]]
    assert cu["outputs"][0]["text"] == "1024\n" and any("image/png" in o.get("data", {}) for o in cu["outputs"])
    assert ca["origin"] == "assistant" and ca["approved"]["hash"] == a["code_hash"] and st.may_run(ca, auto=False)
    assert (tmp_path / "meta" / "p1.json.migrated").exists() and not (tmp_path / "meta" / "p1.json").exists()
    _nbformat_ok(st.path("p1", "calcul"))


def test_static_names_and_ask_messages():
    names = dict((n, t) for n, t, _ in nbm.static_names(["R.<x> = PolynomialRing(QQ)\np = x^4 + 4", "def f(n):\n  return n",
                                                         "G = graphs.PetersenGraph()"]))
    assert {"R", "p", "f", "G"} <= set(names) and names["f"] == "function"
    msgs = nbm.ask_messages("fr", "sage", "factorise p sur Z[i]", [["p", "Polynomial", "x^4 + 4"]], "In [1]: p = x^4+4")
    assert "français" not in msgs[1]["content"] and "- p : Polynomial = x^4 + 4" in msgs[1]["content"]
    assert "factorise p sur Z[i]" in msgs[1]["content"] and "fig(" in msgs[0]["content"]
    # S-AB: the system prompt is fixed for a tool version (cacheable): the card goes there, the signatures to the user
    m2 = nbm.ask_messages("en", "sage", "x", [], "", card="SageMath 10.10 — CARD", sigs="- integral(x, *args)")
    assert m2[0]["content"].endswith("SageMath 10.10 — CARD") and "integral(x, *args)" in m2[1]["content"]
    assert nbm.ask_messages("fr", "sage", "a", [], "")[0] == nbm.ask_messages("en", "sage", "b", [], "c")[0]
    assert len(nbm.ask_messages("fr", "sage", "a", [], "z" * 9000)[1]["content"]) < 3000
    assert len(nbm.outputs_text([{"output_type": "stream", "name": "stdout", "text": "y" * 5000}], 100)) < 200


def test_publication_producer(tmp_path):
    st = nbm.NotebookStore(tmp_path / "nb", tmp_path / "meta")
    st.docs("p1")
    st.add("p1", "Le calcul :", kind="markdown")
    c = st.add("p1", "plot(x^2)")
    st.record_run("p1", c["id"], ExecResult("ok", execution_count=1, outputs=[
        {"output_type": "display_data", "metadata": {}, "data": {"image/png": PNG, "text/plain": "Graphics"}},
        {"output_type": "execute_result", "execution_count": 1, "metadata": {},
         "data": {"text/latex": "\\sqrt{2}", "text/plain": "sqrt(2)"}}]), "host", c["code_hash"],
        upstream=st.upstream_of("p1", "calcul", c["id"]), approx="1.41421356237310")
    st.add("p1", "", kind="figure", figure={"v": 1, "curves": []}, svg='<svg xmlns="http://www.w3.org/2000/svg"/>')
    st.set_engine("p1", "calcul", {"name": "SageMath", "version": "10.10"})
    files = tmp_path / "pub" / "files"
    comp = nbm.publication_computations(st, "p1", files)
    assert comp["engine"] == {"name": "SageMath", "version": "10.10"}
    d = comp["documents"][0]
    assert d["notebook"] == "files/calcul/calcul.ipynb" and (files / "calcul" / "calcul.ipynb").is_file()
    kinds = [x["kind"] for x in d["cells"]]
    assert kinds == ["markdown", "code", "figure"]
    outs = d["cells"][1]["outputs"]
    img = next(o for o in outs if o["kind"] == "image")
    assert (tmp_path / "pub" / img["path"]).read_bytes() == PNG_RAW
    assert next(o for o in outs if o["kind"] == "latex")["approx"] == "1.41421356237310"
    assert d["cells"][2]["figure"]["svg"].startswith("files/calcul/")
    assert nbm.publication_computations(nbm.NotebookStore(tmp_path / "e", tmp_path / "e2"), "p2") is None


# ---------------------------------------------------------------- API with a fake kernel (a real Python namespace)
class FakeKernels:
    """One namespace per document path, like one kernel per document."""

    def __init__(self):
        self.ns: dict[str, dict] = {}
        self.docs: dict[str, dict] = {}
        self.calls: list[str] = []
        self.count: dict[str, int] = {}

    def known(self, path):
        return "k" if path in self.ns else ""

    def epoch(self, path):
        return f"k-{path}" if path in self.ns else ""

    async def status(self, path):
        return {"kernel": "k" if path in self.ns else "", "state": "idle" if path in self.ns else "none"}

    async def execute(self, path, language, code, *, timeout, on_output=None, approx=True):
        self.calls.append(code)
        ns = self.ns.setdefault(path, {})
        self.docs[path] = {"engine": {"name": "Python", "version": "3"}}
        n = self.count[path] = self.count.get(path, 0) + 1
        res = ExecResult("ok", language=language, sandbox="bwrap", execution_count=n, kernel=self.epoch(path))
        buf = io.StringIO()
        try:
            tree = ast.parse(code)
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            with contextlib.redirect_stdout(buf):
                exec(compile(tree, "<cell>", "exec"), ns)                       # noqa: S102 (test double)
                val = eval(compile(ast.Expression(last.value), "<cell>", "eval"), ns) if last else None
            if buf.getvalue():
                res.outputs.append({"output_type": "stream", "name": "stdout", "text": buf.getvalue()})
                if on_output:
                    on_output("stdout", buf.getvalue())
            if val is not None:
                res.outputs.append({"output_type": "execute_result", "execution_count": n, "metadata": {},
                                    "data": {"text/plain": repr(val)}})
                if isinstance(val, float):
                    res.user_expressions["approx"] = repr(repr(val))
        except Exception as e:  # noqa: BLE001
            res.status, res.error = "error", f"{type(e).__name__}: {e}"
            res.outputs.append({"output_type": "error", "ename": type(e).__name__, "evalue": str(e), "traceback": []})
        return res

    async def variables(self, path, language):
        ns = self.ns.get(path)
        return None if ns is None else [[k, type(v).__name__, repr(v)[:80]] for k, v in ns.items() if not k.startswith("_")]

    async def interrupt(self, path):
        return True

    async def restart(self, path, language):
        self.ns.pop(path, None)
        self.count.pop(path, None)
        return "k"

    async def shutdown(self, path):
        self.ns.pop(path, None)


def responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if "The cell you wrote failed" in first:
        assert "NameError" in first
        return "```python\nprint(total)\n```"
    if "Translate the request into ONE short" in first:
        assert "- total : int = 45" in first, first                  # the kernel's names reach the model
        assert "Out: " in first and "45" in first
        if "fail" in first:
            return "```python\nprint(undefined_name)\n```"
        return "Voici :\n```python\ntotal * 2\n```"
    if "Explain what this cell computes" in first:
        return "It doubles the total. It does not prove anything."
    return demo_responder(role, messages, brain)


async def test_notebook_api_sequential_state_nl_cells_and_connections(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    events = []
    async with running(ctx) as (_s, L, Rm), session() as s:
        orig = ctx.bus.publish
        ctx.bus.publish = lambda t, p=None: (events.append((t, p)), orig(t, p))[1]
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        docs = (await (await s.get(L + f"/api/calcul/{pid}/docs")).json())["docs"]
        assert [d["id"] for d in docs] == ["calcul"]
        r = await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "Essai", "language": "python"})
        doc = (await r.json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        j = await (await s.get(D)).json()
        assert j["cells"] == [] and j["status"]["kernel"]["state"] == "none" and fake.calls == []   # GET starts nothing
        add = lambda body: s.post(D + "/cells", json=body)                                         # noqa: E731
        c1 = (await (await add({"type": "markdown", "source": "# Somme"})).json())["cell"]
        c2 = (await (await add({"source": "total = sum(range(10))\nprint(total)"})).json())["cell"]
        c3 = (await (await add({"source": "total + 0.5"})).json())["cell"]
        # run all: sequential, one state
        r = await s.post(D + "/run", json={"all": True})
        j = await r.json()
        assert r.status == 200 and j["stopped"] is None and set(j["runs"]) == {c2["id"], c3["id"]}
        assert j["runs"][c2["id"]]["stdout"] == "45\n" and "45.5" in j["runs"][c3["id"]]["result"]
        v = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}
        assert [v[c2["id"]]["exec_count"], v[c3["id"]]["exec_count"]] == [1, 2]
        assert v[c3["id"]]["outputs"][0]["approx"] == "45.5" and v[c3["id"]]["fresh"]
        # edit an earlier cell: the later one is stale; « run until here » refreshes it
        await s.patch(D + f"/cells/{c2['id']}", json={"source": "total = sum(range(11))"})
        v = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}
        assert v[c3["id"]]["stale"] and v[c3["id"]]["stale_reason"] == "upstream"
        j = await (await s.post(D + "/run", json={"until": c3["id"]})).json()
        assert "55.5" in j["runs"][c3["id"]]["result"]
        assert not {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}[c3["id"]]["stale"]
        # ask cell: natural language → code with the kernel's names, approval required
        await s.patch(D + f"/cells/{c2['id']}", json={"source": "total = sum(range(10))\nprint(total)"})
        await s.post(D + "/run", json={"until": c2["id"]})
        q = (await (await add({"type": "ask", "prompt": "double the total"})).json())["cell"]
        r = await s.post(D + f"/cells/{q['id']}/ask", json={})
        q = (await r.json())["cell"]
        assert r.status == 201 and q["code"] == "total * 2" and q["origin"] == "assistant" and q["prompt"] == "double the total"
        n = len(fake.calls)
        r = await s.post(D + f"/cells/{q['id']}/run")
        assert r.status == 403 and (await r.json())["error"] == "not_approved" and len(fake.calls) == n
        j = await (await s.post(D + "/run", json={"all": True})).json()
        assert j["stopped"] == {"cell_id": q["id"], "reason": "not_approved"}             # run-all stops there
        # paired device: may read, may not approve nor run (experiments_remote off)
        _dev, token = ctx.devices.add("phone")
        hdr = {"Authorization": f"Bearer {token}"}
        R = Rm + f"/api/calcul/{pid}/docs/{doc}"
        assert (await s.get(R, headers=hdr)).status == 200
        assert (await s.post(R + f"/cells/{q['id']}/approve", json={"code_hash": q["code_hash"]}, headers=hdr)).status == 403
        assert (await s.post(R + "/run", json={"all": True}, headers=hdr)).status == 403
        assert (await s.post(D + f"/cells/{q['id']}/approve", json={"code_hash": q["code_hash"]})).status == 200
        run = (await (await s.post(D + f"/cells/{q['id']}/run")).json())["run"]
        assert run["result"].strip() == "90"
        # an ask cell that fails: the error goes back to the model once, the fix needs approval again
        q2 = (await (await add({"type": "ask", "prompt": "fail please"})).json())["cell"]
        q2 = (await (await s.post(D + f"/cells/{q2['id']}/ask", json={})).json())["cell"]
        await s.post(D + f"/cells/{q2['id']}/approve", json={"code_hash": q2["code_hash"]})
        j = await (await s.post(D + f"/cells/{q2['id']}/run")).json()
        assert j["run"]["status"] == "error" and j["autofix"]["code"] == "print(total)" and j["autofix"]["approved"] is None
        j = await (await s.post(D + f"/cells/{q2['id']}/run")).json()
        assert j.get("error") == "not_approved"
        # variables
        names = (await (await s.get(D + "/variables")).json())["names"]
        assert {"name": "total", "type": "int", "value": "45"} in names
        # restart: fresh state, outputs kept but not « fresh »
        assert (await s.post(D + "/restart")).status == 200
        v = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}
        assert not v[c3["id"]]["fresh"]
        # connections: note, conjecture, Lean dossier, article (formula + code in the computations section)
        r = await s.post(D + f"/cells/{c3['id']}/to", json={"target": "note", "title": "Somme"})
        assert r.status == 201 and "total + 0.5" in (await r.json())["note"]["body"]
        r = await s.post(D + f"/cells/{c2['id']}/to", json={"target": "dossier", "text": "∑_{k<10} k = 45"})
        assert r.status == 201 and ctx.repo.get((await r.json())["dossier"]["id"]).problem == "∑_{k<10} k = 45"
        r = await s.post(D + f"/cells/{c2['id']}/to", json={"target": "conjecture", "text": "∑_{k<n} k = n(n-1)/2"})
        assert r.status == 201
        r = await s.post(D + f"/cells/{c2['id']}/to", json={"target": "article", "title": "Somme"})
        assert r.status == 201
        from madalean.research import article as art_mod
        art = art_mod.load(ctx, pid)
        texts = [b.get("text", "") for b in art["blocks"]]
        assert any("45" in t for t in texts) and any("sum(range(10))" in t for t in texts)
        assert any(b["kind"] == "section" and "SageMath" in b.get("title", "") for b in art["blocks"])
        r = await s.post(D + f"/cells/{c1['id']}/to", json={"target": "article"})
        assert r.status == 400                                     # a text cell needs an image to become a figure
        # the .ipynb download is the file itself; nbformat reads it
        r = await s.get(D + "/ipynb")
        assert r.status == 200 and json.loads(await r.read())["nbformat"] == 4
        _nbformat_ok(ctx.jupyter.root_dir / "calcul" / pid / f"{doc}.ipynb")
        # the S-M routes still work on the default document
        j = await (await s.get(L + f"/api/calcul/{pid}")).json()
        assert j["sheet"]["cells"] == [] and j["doc"]["id"] == "calcul"
        r = await s.post(L + f"/api/calcul/{pid}/assist", json={"action": "write", "prompt": "double the total"})
        assert r.status in (201, 400, 502, 503)
        assert any(t == "calcul.updated" and p.get("doc") == doc for t, p in events)


# ---------------------------------------------------------------- real JupyterLab + real sandboxed kernel
needs_lab = pytest.mark.skipif(not shutil.which("jupyter-lab"), reason="jupyter-lab not installed")


@needs_lab
@pytest.mark.parametrize("language", ["python", pytest.param("sage", marks=pytest.mark.skipif(
    not shutil.which("sage"), reason="sage not installed"))])
async def test_real_kernel_shared_with_jupyterlab_session(tmp_path, language, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TEST-SECRET-123")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_s, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "Réel", "language": language}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        path = f"calcul/{pid}/{doc}.ipynb"
        # JupyterLab opens the notebook first (the way its UI does: a session for the path, the notebook's kernel)
        await ctx.jupyter.start()
        spec = "madalean-sage" if language == "sage" else "madalean-python"
        ctx.research.bridge.install_specs()
        async with s.post(L + "/jupyter/api/sessions", json={"path": path, "type": "notebook", "name": f"{doc}.ipynb",
                                                             "kernel": {"name": spec}}) as r:
            assert r.status == 201, await r.text()
            lab_kid = (await r.json())["kernel"]["id"]
        add = lambda src: s.post(D + "/cells", json={"source": src})                               # noqa: E731
        c1 = (await (await add("a = 6\nimport os\nprint('KEY' in str(os.environ.get('ANTHROPIC_API_KEY')))")).json())["cell"]
        c2 = (await (await add("a * 7")).json())["cell"]
        c3 = (await (await add("fig([(0, 0), (1, 2)], title='t')")).json())["cell"]
        j = await (await s.post(D + "/run", json={"all": True, "timeout": 300})).json()
        assert j["stopped"] is None, j
        assert j["runs"][c1["id"]]["stdout"].strip() == "False"                    # no secret in the kernel
        assert j["runs"][c2["id"]]["result"].strip() == "42"                       # state shared between cells
        v = await (await s.get(D)).json()
        assert v["status"]["kernel"]["kernel"] == lab_kid                           # Madalean attached to Lab's kernel
        figs = [o for o in v["cells"][2]["outputs"] if nbm.FIGURE_MIME in o.get("data", {})]
        assert figs and figs[0]["data"][nbm.FIGURE_MIME]["points"][1] == {"x": 1.0, "y": 2.0}
        assert v["doc"]["engine"]["name"] == ("SageMath" if language == "sage" else "Python")
        async with s.get(L + "/jupyter/api/sessions") as r:
            mine = [x for x in await r.json() if x["path"] == path]
        assert len(mine) == 1 and mine[0]["kernel"]["id"] == lab_kid               # never a second kernel
        if language == "sage":
            c4 = (await (await add("sqrt(2) * pi")).json())["cell"]
            run = (await (await s.post(D + f"/cells/{c4['id']}/run", json={"timeout": 120})).json())["run"]
            out = next(o for o in run["outputs"] if o["type"] == "result")
            assert out["approx"].startswith("4.44288") and "pi" in out["data"]["text/latex"]
            # Maxima (integrals) writes its cache inside the experiments dir, never under HOME (read-only sandbox)
            c6 = (await (await add("n = var('n'); assume(n, 'integer'); assume(n > 0)\n"
                                   "integral(x^2*cos(n*x), x, 0, 2*pi).simplify_full()")).json())["cell"]
            run = (await (await s.post(D + f"/cells/{c6['id']}/run", json={"timeout": 300})).json())["run"]
            assert run["status"] == "ok", run
            out = next(o for o in run["outputs"] if o["type"] == "result")
            assert "pi" in out["data"]["text/plain"] and "n^2" in out["data"]["text/plain"]
        # restart from Madalean: the same session, state gone, then the shutdown removes the session
        assert (await s.post(D + "/restart")).status == 200
        c5 = (await (await add("print(a)")).json())["cell"]
        run = (await (await s.post(D + f"/cells/{c5['id']}/run")).json())["run"]
        assert run["status"] == "error" and "NameError" in run["error"]
        _nbformat_ok(ctx.jupyter.root_dir / path)
        assert (await s.post(D + "/shutdown")).status == 200
        async with s.get(L + "/jupyter/api/sessions") as r:
            assert not [x for x in await r.json() if x["path"] == path]
        # Madalean first, JupyterLab later: Lab finds Madalean's session (one kernel for the document)
        await s.post(D + f"/cells/{c2['id']}/run")
        async with s.get(L + "/jupyter/api/sessions") as r:
            mine = [x for x in await r.json() if x["path"] == path]
        assert len(mine) == 1 and mine[0]["kernel"]["name"] == spec
        # idle reaper: everything under calcul/ that is idle stops
        wb = _s.app[wbm.WB]
        await asyncio.sleep(1.2)
        assert path in await wb.kernels().reap(1)
        # a session switched to a non-sandboxed kernel is refused
        async with s.post(L + "/jupyter/api/sessions", json={"path": path, "type": "notebook", "name": f"{doc}.ipynb",
                                                             "kernel": {"name": "python3"}}) as r:
            assert r.status == 201, await r.text()
        run = (await (await s.post(D + f"/cells/{c2['id']}/run")).json())["run"]
        assert run["status"] == "unavailable" and "kernel_not_sandboxed" in run["error"]


# ---------------------------------------------------------------- S-AB: fast transcription, « Réécrire », no busy
def fast_responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    req = first.split("Request: ", 1)[-1].split("\n", 1)[0]
    if "The cell you wrote failed" in first:
        if "found before running" in first:                       # the validation loop (code did not compile)
            assert "SyntaxError" in first
            return "```python\nprint('repaired')\n```"
        return {"text": "```python\nprint('auto')\n```", "delay": 1.5}
    if req.startswith("slow"):
        return {"text": "```python\n'slow'\n```", "delay": 3.0}
    if req.startswith("broken"):
        return "```python\nprint(\n```"
    if req.startswith("fail"):
        return "```python\nundefined_name\n```"
    return "```python\n'" + req.replace("'", "") + "'\n```"


async def test_rewrite_replaces_generation_autofix_never_blocks_and_fast_loop(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    brain = FakeBrain(fast_responder)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (srv, L, _R), session() as s:
        events = []
        orig = ctx.bus.publish
        ctx.bus.publish = lambda t, p=None: (events.append((t, p)), orig(t, p))[1]
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "python"}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        add = lambda body: s.post(D + "/cells", json=body)                                         # noqa: E731
        q = (await (await add({"type": "ask", "prompt": "slow"})).json())["cell"]
        # « Réécrire » while the first generation is still running: the new one replaces it, never « busy »
        first = asyncio.ensure_future(s.post(D + f"/cells/{q['id']}/ask", json={"prompt": "slow request"}))
        await asyncio.sleep(0.4)
        r = await s.post(D + f"/cells/{q['id']}/ask", json={"prompt": "quick one"})
        j = await r.json()
        assert r.status == 201 and j["cell"]["code"] == "'quick one'", j
        r1 = await first
        assert r1.status == 409 and (await r1.json())["error"] == "replaced"
        await asyncio.sleep(3.2)                                  # the replaced generation never writes afterwards
        cell = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}[q["id"]]
        assert cell["code"] == "'quick one'" and cell["prompt"] == "quick one"
        drafts = [p for t, p in events if t == "calcul.draft" and p["cell_id"] == q["id"]]
        assert any(p["state"] == "writing" and p["code"] for p in drafts) and drafts[-1]["state"] == "done"
        # the model's code is checked before it is shown: a syntax error goes back to the model once
        q2 = (await (await add({"type": "ask", "prompt": "broken"})).json())["cell"]
        j = await (await s.post(D + f"/cells/{q2['id']}/ask", json={})).json()
        assert j["cell"]["code"] == "print('repaired')" and j["checked"] == {"valid": True, "fixed": True, "error": ""}
        # identical request on a new cell: its best version, no model; S-AG (D39): « Réécrire » too (one syntax
        # per request); only « Autre version » (variant) asks the model for a different one
        n = len(brain.requests)
        q3 = (await (await add({"type": "ask", "prompt": "quick one", "at": 0})).json())["cell"]   # same place
        j = await (await s.post(D + f"/cells/{q3['id']}/ask", json={})).json()
        assert j["timing"]["cached"] is True and len(brain.requests) == n and j["cell"]["code"] == "'quick one'"
        j = await (await s.post(D + f"/cells/{q3['id']}/ask", json={})).json()
        assert j["timing"]["cached"] is True and len(brain.requests) == n and j["origin"] == "best"
        j = await (await s.post(D + f"/cells/{q3['id']}/ask", json={"variant": True})).json()
        assert j["timing"]["cached"] is False and len(brain.requests) == n + 1 and j["origin"] == "variant"
        assert "ANOTHER version" in brain.requests[-1]["messages"][-1]["content"]
        # a failed ask cell: the automatic fix runs AFTER the kernel lock is released — other cells may run
        c1 = (await (await add({"source": "40 + 2"})).json())["cell"]
        q4 = (await (await add({"type": "ask", "prompt": "fail"})).json())["cell"]
        q4 = (await (await s.post(D + f"/cells/{q4['id']}/ask", json={})).json())["cell"]
        await s.post(D + f"/cells/{q4['id']}/approve", json={"code_hash": q4["code_hash"]})
        run4 = asyncio.ensure_future(s.post(D + f"/cells/{q4['id']}/run"))
        await asyncio.sleep(0.5)                                  # the run failed; the fix is being written
        r = await s.post(D + f"/cells/{c1['id']}/run")
        assert r.status == 200 and "42" in (await r.json())["run"]["result"]
        # « Réécrire » during the automatic fix: the fix is cancelled, the user's request wins
        r = await s.post(D + f"/cells/{q4['id']}/ask", json={"prompt": "quick two"})
        assert r.status == 201
        j = await (await run4).json()
        assert j["run"]["status"] == "error" and j["autofix"] is None
        cell = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}[q4["id"]]
        assert cell["code"] == "'quick two'"
        # cells running: the notebook's own message, not the dossier one
        wb = srv.app[wbm.WB]
        async with wb.lock(f"{pid}/{doc}"):
            r = await s.post(D + f"/cells/{c1['id']}/run")
            assert r.status == 409 and (await r.json())["error"] == "calcul_busy"
            # …but a request can still be written (names read from the code, not from the busy kernel)
            r = await s.post(D + f"/cells/{q['id']}/ask", json={"prompt": "while busy"})
            assert r.status == 201


def fix_loop_responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if "Cette cellule a échoué" in first:
        return "Le nom « totl » n'existe pas : c'est « total ».\n\n```python\nprint(total)\n```"
    if "ligne par ligne" in first:
        return "1: On additionne.\n2: On affiche le total."
    if "The cell you wrote failed" in first:
        return "```python\nundefined_again\n```" if "undefined_once" in first else "```python\n6 * 7\n```"
    req = first.split("Request: ", 1)[-1].split("\n", 1)[0]
    if req.startswith("fail"):
        return "```python\nundefined_once\n```"
    return "```python\nsum([" + ", ".join(str(int(t)) for t in re.findall(r"\d+", req)) + "])\n```"


async def test_auto_fix_policy_recipes_detect_explain_and_kinds(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    brain = FakeBrain(fix_loop_responder)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "python"}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        add = lambda body: s.post(D + "/cells", json=body)                                         # noqa: E731
        # 1. approval required (default): a failed run → ONE corrected proposal, not run, to approve
        q = (await (await add({"type": "ask", "prompt": "fail"})).json())["cell"]
        q = (await (await s.post(D + f"/cells/{q['id']}/ask", json={})).json())["cell"]
        await s.post(D + f"/cells/{q['id']}/approve", json={"code_hash": q["code_hash"]})
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["autofix"]["code"] == "undefined_again" and j["autofix"]["autofix"]["n"] == 1
        assert "reran" not in j["autofix"] and j["autofix"]["approved"] is None
        n_calls = len(fake.calls)
        # 2. « experiments_auto » (model code runs without approval): fix → run again by itself, bounded
        ctx.settings.experiments_auto = True
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["run"]["status"] == "ok" and "42" in j["run"]["result"]  # undefined_again failed, then fixed
        cell = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}[q["id"]]
        assert cell["code"] == "6 * 7" and cell["autofix"]["n"] == 2   # …corrected (2/3) and run again: 42
        assert any(c == "6 * 7" for c in fake.calls[n_calls:])
        assert [v["code"] for v in cell["versions"]][-3:] == ["undefined_once", "undefined_again", "6 * 7"]
        ctx.settings.experiments_auto = False
        # 3. a request whose code ran is learned; the same request with other numbers → instant code, no model
        r1 = (await (await add({"type": "ask", "prompt": "somme de 3 et 4"})).json())["cell"]
        r1 = (await (await s.post(D + f"/cells/{r1['id']}/ask", json={})).json())["cell"]
        await s.post(D + f"/cells/{r1['id']}/approve", json={"code_hash": r1["code_hash"]})
        assert (await (await s.post(D + f"/cells/{r1['id']}/run")).json())["run"]["status"] == "ok"
        rec = (await (await s.get(L + "/api/calcul/recipes")).json())["recipes"]
        assert len(rec) == 2 and {x["request"] for x in rec} == {"fail", "somme de 3 et 4"}
        before = len(brain.requests)
        r2 = (await (await add({"type": "ask", "prompt": "somme de 5 et 8"})).json())["cell"]
        j = await (await s.post(D + f"/cells/{r2['id']}/ask", json={})).json()
        assert j["recipe"] and j["model"] == "recipe" and j["cell"]["code"] == "sum([5, 8])"
        assert len(brain.requests) == before and j["approval_required"]   # still model code: approval rule
        rid = next(x["id"] for x in rec if x["request"] == "somme de 3 et 4")
        assert (await s.delete(L + f"/api/calcul/recipes/{rid}")).status == 200
        rec = (await (await s.get(L + "/api/calcul/recipes")).json())["recipes"]
        # S-AG: the shortcut's code is now the best version of « somme de 5 et 8 » (kept by intent)
        assert {x["request"] for x in rec} == {"fail", "somme de 5 et 8"}
        # 4. code or request?
        j = await (await s.post(D + "/detect", json={"text": "la somme des carrés de 1 à 10"})).json()
        assert j["kind"] == "ask"
        j = await (await s.post(D + "/detect", json={"text": "sum(k**2 for k in range(11))"})).json()
        assert j["kind"] == "code"
        # a typed request becomes a request cell (and back)
        c = (await (await add({"source": "la somme de 1 et 2"})).json())["cell"]
        c = (await (await s.patch(D + f"/cells/{c['id']}", json={"type": "ask"})).json())["cell"]
        assert c["type"] == "ask" and c["prompt"] == "la somme de 1 et 2" and c["source"] == ""
        c = (await (await s.patch(D + f"/cells/{c['id']}", json={"type": "code"})).json())["cell"]
        assert c["type"] == "code"
        # 5. « Expliquer l'erreur »: explanation + a proposed fix that is NOT applied; applying it = model code
        e = (await (await add({"source": "total = 1\nprint(totl)"})).json())["cell"]
        await s.post(D + f"/cells/{e['id']}/run")
        j = await (await s.post(D + f"/cells/{e['id']}/explain", json={"mode": "error"})).json()
        assert "totl" in j["explanation"] and j["fix"] == "print(total)" and j["fix_valid"]
        cell = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}[e["id"]]
        assert cell["code"] == "total = 1\nprint(totl)"                   # never applied by itself
        j = await (await s.post(D + f"/cells/{e['id']}/suggestion", json={"code": j["fix"], "model": j["model"]})).json()
        assert j["cell"]["origin"] == "assistant" and j["approval_required"]
        r = await s.post(D + f"/cells/{e['id']}/run")
        assert r.status == 403                                            # model code: approval first
        # « Expliquer ligne par ligne » and the generic endpoint (Lean too, for the proofs screen)
        j = await (await s.post(L + "/api/code/explain", json={
            "language": "python", "code": "a = 1 + 2\n\nprint(a)", "mode": "lines"})).json()
        assert [x["text"] for x in j["lines"]] == ["On additionne.", "", ""]   # blank line: nothing
        j = await (await s.post(D + f"/cells/{e['id']}/explain", json={"mode": "lines"})).json()
        assert [x["line"] for x in j["lines"]] == [1] and j["lines"][0]["text"] == "On additionne."
        r = await s.post(L + "/api/code/explain", json={"language": "cobol", "code": "x", "mode": "lines"})
        assert r.status == 400
        r = await s.post(L + "/api/code/explain", json={"language": "lean", "code": "theorem t : 1 = 1 := rfl",
                                                         "mode": "error"})
        assert r.status == 400                                            # mode error needs an error
