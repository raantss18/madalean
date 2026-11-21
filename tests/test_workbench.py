"""Session S-M: Calcul (approval boundary, sandboxed kernel through sagebridge, rich outputs, SVG sanitising, history,
one-click actions), the organised library catalogue (domain, tags, status, uses / used-by, export) and the glossary's
links to dossiers. Fake kernel for the API, a real Sage kernel when installed."""
from __future__ import annotations

import base64
import shutil

import pytest

from helpers import make_ctx, running, session
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import calcul as cal
from madalean.research.sagebridge import ExecResult
from madalean.server.plugins import workbench as wbm

PNG = base64.b64encode(cal.PNG_MAGIC + b"\x00" * 32).decode()
EVIL_SVG = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg" '
            'onload="alert(1)"><script>alert(2)</script><a href="javascript:alert(3)"><rect width="1" height="1" '
            'style="fill:url(https://evil/x)" onclick="x()"/></a><foreignObject><iframe src="https://evil"/>'
            '</foreignObject><image href="https://evil/p.png"/></svg>')


def test_svg_sanitiser_removes_everything_active():
    s = cal.sanitize_svg(EVIL_SVG)
    low = s.lower()
    for bad in ("<script", "onload", "onclick", "javascript", "foreignobject", "iframe", "https://evil", "<!entity",
                "<image"):
        assert bad not in low, bad
    assert "<rect" in s and "<svg" in s
    with pytest.raises(cal.CalcError):
        cal.sanitize_svg("<html>nope</html>")


def test_store_approval_rules_and_history(tmp_path):
    st = cal.CalcStore(tmp_path)
    u = st.add("p1", "1+1", "sage", "user")
    assert u["origin"] == "user" and cal.CalcStore.may_run(u, auto=False)
    a = st.add("p1", "factor(2^64+1)", "sage", "assistant", after=u["id"], model="m:x")
    assert not cal.CalcStore.may_run(a, auto=False) and cal.CalcStore.may_run(a, auto=True)
    with pytest.raises(cal.CalcError) as e:
        st.approve("p1", a["id"], "stale", "host")
    assert e.value.status == 409
    a = st.approve("p1", a["id"], a["code_hash"], "host")
    assert cal.CalcStore.may_run(a, auto=False)
    a = st.edit("p1", a["id"], code="factor(2^32+1)", by="user")       # the user's edit of model code
    assert a["origin"] == "assistant" and a["approved"] is None and not cal.CalcStore.may_run(a, auto=False)
    assert [v["code"] for v in a["versions"]] == ["factor(2^64+1)", "factor(2^32+1)"]
    res = ExecResult("ok", stdout="2\n", seconds=0.1, language="sage", sandbox="bwrap",
                     rich=[{"mime": "text/latex", "data": "$$2$$"}, {"mime": "image/png", "data": PNG},
                           {"mime": "image/svg+xml", "data": EVIL_SVG}, {"mime": "image/png", "data": "bm90LXBuZw=="}])
    run = st.record_run("p1", u["id"], res, "host", u["code_hash"])
    assert [r["mime"] for r in run["rich"]] == ["text/latex", "image/png", "image/svg+xml"]   # fake PNG dropped
    svg = st.asset_path(run["rich"][2]["asset"])
    assert svg and svg[1] == "image/svg+xml" and "<script" not in svg[0].read_text()
    assert st.asset_path("../../etc/passwd") is None
    assert [c["id"] for c in st.load("p1")["cells"]] == [u["id"], a["id"]]
    st.delete("p1", u["id"])
    st.restore("p1", u["id"])
    with pytest.raises(cal.CalcError):
        st.load("../x")
        st.add("../x", "1", "sage", "user")


class FakeKernels:
    """S-P: Calcul cells run in the document's kernel (research/nbkernels.py); this double answers like one."""

    def __init__(self):
        self.calls = []
        self.docs = {}

    def known(self, path):
        return ""

    def epoch(self, path):
        return "k@0"

    async def status(self, path):
        return {"kernel": "", "state": "none"}

    async def execute(self, path, language, code, *, timeout=60, on_output=None, approx=True):
        self.calls.append((path, language, code))
        if on_output:
            on_output("stdout", "42\n")
        return ExecResult("ok", stdout="42\n", seconds=0.01, language=language, sandbox="bwrap", execution_count=1,
                          outputs=[{"output_type": "stream", "name": "stdout", "text": "42\n"},
                                   {"output_type": "display_data", "metadata": {},
                                    "data": {"text/latex": "$$\\frac{1}{2}$$", "text/plain": "1/2"}},
                                   {"output_type": "display_data", "metadata": {}, "data": {"image/png": PNG}}])

    async def variables(self, path, language):
        return None


def responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if "Write one code cell" in first or "Translate the request into ONE short" in first:
        return "Here:\n```sage\nprint(sum(range(10)))\n```"
    if "This cell failed" in first:
        return "```sage\nprint(1)\n```"
    if "Explain what this cell computes" in first:
        return "It sums the integers below 10. It does not prove anything general."
    return demo_responder(role, messages, brain)


async def test_calcul_api_approval_actions_and_assets(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    async with running(ctx) as (_s, L, Rm), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        j = await (await s.get(L + f"/api/calcul/{pid}")).json()
        assert j["sheet"]["cells"] == [] and j["status"]["sandbox"] == "bwrap" and j["status"]["local"]
        assert (await s.get(L + "/api/calcul/nope")).status == 404
        # the user's own cell runs directly
        r = await s.post(L + f"/api/calcul/{pid}/cells", json={"code": "6*7", "language": "sage"})
        u = (await r.json())["cell"]
        assert r.status == 201 and u["origin"] == "user"
        r = await s.post(L + f"/api/calcul/{pid}/cells/{u['id']}/run")
        run = (await r.json())["run"]
        assert r.status == 200 and run["stdout"] == "42\n" and run["rich"][0]["data"] == "$$\\frac{1}{2}$$"
        assert fake.calls[-1][0] == f"calcul/{pid}/calcul.ipynb"          # the default document's kernel
        assert "def tex" in wbm.CALC_PREAMBLE
        a = await s.get(L + f"/api/calcul/assets/{run['rich'][1]['asset']}")
        assert a.status == 200 and a.headers["Content-Type"] == "image/png" and "sandbox" in a.headers["Content-Security-Policy"]
        # the assistant's cell needs the explicit approval of that exact code
        r = await s.post(L + f"/api/calcul/{pid}/assist", json={"action": "write", "prompt": "sum below 10"})
        c = (await r.json())["cell"]
        assert r.status == 201 and c["origin"] == "assistant" and c["code"] == "print(sum(range(10)))"
        assert (await r.json())["approval_required"]
        n = len(fake.calls)
        r = await s.post(L + f"/api/calcul/{pid}/cells/{c['id']}/run")
        assert r.status == 403 and (await r.json())["error"] == "not_approved" and len(fake.calls) == n
        # paired devices: no approval, no run (host-only setting experiments_remote)
        _dev, token = ctx.devices.add("phone")
        hdr = {"Authorization": f"Bearer {token}"}
        assert (await s.post(Rm + f"/api/calcul/{pid}/cells/{c['id']}/approve", json={"code_hash": c["code_hash"]},
                             headers=hdr)).status == 403
        assert (await s.post(Rm + f"/api/calcul/{pid}/cells/{u['id']}/run", headers=hdr)).status == 403
        assert (await s.get(Rm + f"/api/calcul/{pid}", headers=hdr)).status == 200      # reading is allowed
        r = await s.post(L + f"/api/calcul/{pid}/cells/{c['id']}/approve", json={"code_hash": c["code_hash"]})
        assert r.status == 200
        assert (await s.post(L + f"/api/calcul/{pid}/cells/{c['id']}/run")).status == 200
        # « fix » rewrites the cell as assistant code: approval withdrawn again
        r = await s.post(L + f"/api/calcul/{pid}/assist", json={"action": "fix", "cell_id": c["id"]})
        c2 = (await r.json())["cell"]
        assert c2["approved"] is None and (await s.post(L + f"/api/calcul/{pid}/cells/{c['id']}/run")).status == 403
        r = await s.post(L + f"/api/calcul/{pid}/assist", json={"action": "explain", "cell_id": u["id"]})
        assert "does not prove" in (await r.json())["text"]
        # one-click actions on a result
        r = await s.post(L + f"/api/calcul/{pid}/cells/{u['id']}/to", json={"target": "note", "title": "Six fois sept"})
        note = (await r.json())["note"]
        assert r.status == 201 and "6*7" in note["body"] and "calcul" in note["tags"]
        r = await s.post(L + f"/api/calcul/{pid}/cells/{u['id']}/to",
                         json={"target": "dossier", "text": "6 × 7 = 42", "title": "Produit"})
        did = (await r.json())["dossier"]["id"]
        assert r.status == 201 and ctx.repo.get(did).project_id == pid and ctx.repo.get(did).problem == "6 × 7 = 42"
        r = await s.post(L + f"/api/calcul/{pid}/cells/{u['id']}/to", json={"target": "article"})
        assert r.status == 201 and (await r.json())["block"]["text"].startswith("$$\\frac{1}{2}$$")
        r = await s.post(L + f"/api/calcul/{pid}/cells/{u['id']}/to",
                         json={"target": "conjecture", "text": "For every n, n^2 + n is even."})
        assert r.status == 201 and (await r.json())["conjecture"]["kind"] == "conjecture"
        assert (await s.post(L + f"/api/calcul/{pid}/cells/{u['id']}/to", json={"target": "x"})).status == 400
        # history: the sheet keeps runs and versions
        j = await (await s.get(L + f"/api/calcul/{pid}")).json()
        cells = {x["id"]: x for x in j["sheet"]["cells"]}
        assert len(cells[u["id"]]["runs"]) == 1 and len(cells[c["id"]]["versions"]) == 2


async def test_library_catalog_meta_export_and_glossary_uses(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_s, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "Arith"})).json())["project"]["id"]
        d, _ = await __import__("madalean.server.routes_work", fromlist=["x"]).create_dossier(
            ctx, {"statement": "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry",
                  "project_id": pid, "problem": "La somme de deux pairs est paire.", "start": False})
        code = d.statement.replace("sorry", "exact Even.add ha hb")
        d.add_proof(code, model="kilo:m", meta={"axioms": []})
        d.status = "proved"
        await ctx.repo.save(d)
        e1 = ctx.library.add_proof(code, d.title, "demo", d.id)
        e2 = ctx.library.add_proof(code.replace(f"theorem {d.theorem}", "theorem t2"), "Suite", "demo", "", [e1.name])
        j = await (await s.get(L + "/api/library/catalog")).json()
        by = {x["name"]: x for x in j["entries"]}
        a = by[e1.name]
        assert a["status"] == "verified" and a["model"] == "kilo:m" and a["project"] == "Arith"
        assert a["domain"] == "number_theory" and a["nl"].startswith("La somme") and a["used_by"] == [e2.name]
        assert by[e2.name]["uses"] == [e1.name]
        r = await s.patch(L + f"/api/library/meta/{e1.name}", json={"domain": "algebra", "tags": ["parité", "L1"]})
        assert r.status == 200
        assert (await s.patch(L + f"/api/library/meta/{e1.name}", json={"domain": "astrology"})).status == 400
        assert (await s.patch(L + "/api/library/meta/nope", json={"tags": []})).status == 404
        a = {x["name"]: x for x in (await (await s.get(L + "/api/library/catalog")).json())["entries"]}[e1.name]
        assert a["domain"] == "algebra" and a["domain_manual"] and a["domain_auto"] == "number_theory"
        assert a["tags"] == ["L1", "parité"]
        md = await (await s.get(L + "/api/library/catalog/export?format=md")).text()
        assert "## " in md and "```lean" in md
        lean = await (await s.get(L + f"/api/library/catalog/export?format=lean&name={e2.name}")).text()
        assert lean.startswith("import Mathlib") and lean.index(e1.name) < lean.index("theorem t2")
        # a conditional result of a proof plan shows up as conditional
        d2, _ = await __import__("madalean.server.routes_work", fromlist=["x"]).create_dossier(
            ctx, {"statement": "theorem c (n : ℕ) : n ≤ n ^ 2 := by sorry", "start": False})
        d2.extra["conditional_proof"] = {"verdict": "proved_modulo", "admitted": ["aux"], "strict_ok": False}
        await ctx.repo.save(d2)
        cond = [x for x in (await (await s.get(L + "/api/library/catalog")).json())["entries"]
                if x["status"] == "conditional"]
        assert [c["admitted"] for c in cond] == [["aux"]]
        g = await (await s.get(L + "/api/glossary/uses", params={"term": "Even"})).json()
        assert [x["id"] for x in g["dossiers"]] == [d.id]
        g = await (await s.get(L + "/api/glossary/uses", params={"term": "Ev"})).json()
        assert g["dossiers"] == []


needs_kernel = pytest.mark.skipif(not (shutil.which("jupyter-lab") and shutil.which("sage")),
                                  reason="jupyter-lab / sage not installed")


@needs_kernel
async def test_calcul_real_sage_kernel_latex_and_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TEST-SECRET-123")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_s, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        c1 = (await (await s.post(L + f"/api/calcul/{pid}/cells", json={"code": "x = factor(2^32 + 1); print(x)\ntex(x)\n"
                                                                     "import os; print('KEY' in str(os.environ.get('ANTHROPIC_API_KEY')))",
                                                                     "language": "sage"})).json())["cell"]
        r = await s.post(L + f"/api/calcul/{pid}/cells/{c1['id']}/run", json={"timeout": 300})
        run = (await r.json())["run"]
        assert run["status"] == "ok", run
        assert "641 * 6700417" in run["stdout"] and "False" in run["stdout"]
        assert any(x["mime"] == "text/latex" and "641" in x["data"] for x in run["rich"])
        c2 = (await (await s.post(L + f"/api/calcul/{pid}/cells", json={"code": "print(x.value())", "language": "sage"})).json())["cell"]
        run2 = (await (await s.post(L + f"/api/calcul/{pid}/cells/{c2['id']}/run", json={"timeout": 120})).json())["run"]
        assert run2["stdout"].strip() == "4294967297"                    # variables persist between cells
        await ctx.research.bridge.close()
