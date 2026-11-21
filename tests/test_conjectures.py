"""Conjecture workshop (S-G): statement analysis, evidence log, generation + filtering, approval boundary, and real
experiments: a Sage kernel refutes « n² + n + 41 is prime for all n » (n = 40), re-verified independently in a fresh
kernel and by Lean; kernel timeout kill; API keys invisible inside the kernel."""
import asyncio
import json
import os
import shutil

import pytest

from helpers import make_ctx, running, session, started
from madalean import leancheck
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import conjectures as cj

EULER = "theorem euler_poly (n : ℕ) : Nat.Prime (n ^ 2 + n + 41) := by sorry"
EULER_CODE = cj.demo_answer(cj.MARK + " task=experiment").split("```python\n")[1].split("```")[0]


def responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    ans = cj.demo_answer(first)
    if ans is not None and "task=generate" in first:
        return json.dumps([
            {"statement": "For every natural number n, n^2 + n + 41 is prime.", "motivation": "Euler.",
             "lean": EULER},
            {"statement": "The sum of two even numbers is even.", "motivation": "obvious"},     # Mathlib: Even.add
            {"statement": "For every natural number n, n^2 + n + 41 is a prime.", "motivation": "dup"},
            {"statement": "For all n, n^2+n is even.", "motivation": "consecutive"}])
    return ans if ans is not None else demo_responder(role, messages, brain)


def test_signature_prop_instances_negation():
    st = leancheck.prepare_statement("theorem t {α : Type} [Fintype α] (n m : ℕ) (h : 0 < n) : n * m ≥ m := by sorry")
    binders, concl = cj.split_signature(st)
    assert [(b["name"], b["kind"]) for b in binders] == [("α", "implicit"), ("", "inst"), ("n", "explicit"),
                                                          ("m", "explicit"), ("h", "explicit")]
    assert concl == "n * m ≥ m"
    assert cj.as_prop(st).startswith("∀ {α : Type} [Fintype α] (n m : ℕ) (h : 0 < n), n * m ≥ m")
    code, spans = cj.instance_file(st, [{"n": 2, "m": 3}, {"x": 1}])
    assert len(spans) == 1 and "(fun (n : ℕ) (m : ℕ) => ∀ {α : Type} [Fintype α] (h : 0 < n), n * m ≥ m) 2 3" in code
    neg = cj.negation_file(st, {"n": 2, "m": -1})
    assert "have hw := h 2 (-1) (by first | norm_num | decide | omega)" in neg
    with pytest.raises(cj.ConjectureError):
        cj.lean_value("1; #exit")


def test_evidence_chain_is_tamper_evident():
    from madalean.dossiers import Dossier
    d = Dossier(id="x", title="t", kind="conjecture")
    cj.add_evidence(d, "created", {"key": "a", "params": {}, "text": "a"})
    cj.add_evidence(d, "experiment", {"key": "b", "params": {}, "text": "b"}, verdict="holds", data={"cases": 5})
    assert cj.chain_ok(d) and cj.status(d) == "tested-n-cases" and cj.cases_tested(d) == 5
    d2 = Dossier.from_dict(json.loads(d.to_json()))          # round-trips through the dossier store
    assert cj.chain_ok(d2) and d2.kind == "conjecture"
    d2.extra["conjecture"]["evidence"][0]["output"] = "edited"
    assert not cj.chain_ok(d2)


def test_parse_experiment_requires_predicate_and_search():
    assert cj.parse_experiment("```python\nprint(1)\n```") is None
    pred, full = cj.parse_experiment(f"```python\n{EULER_CODE}```")
    assert "def holds" in pred and "# SEARCH" not in pred and "report(" in full


async def test_generation_filters_duplicates_and_known(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    async with running(ctx) as (_s, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "Euler", "body": "n²+n+41"})).json())["note"]
        r = await s.post(L + f"/api/projects/{pid}/conjectures/generate", json={"note_ids": [n["id"]], "n": 4})
        j = await r.json()
        assert r.status == 200, j
        assert [p["statement"][:24] for p in j["proposals"]] == ["For every natural number", "For all n, n^2+n is even"]
        reasons = {f["reason"] for f in j["filtered"]}
        assert reasons == {"known_mathlib", "duplicate_proposal"}
        assert j["proposals"][0]["origin"]["notes"] == [n["id"]]
        prompt = ctx.brain.requests[-1]["messages"][0]["content"]
        assert "n²+n+41" in prompt and "## Note: Euler" in prompt
        # accept a proposal → conjecture dossier (kind conjecture), evidence log started
        r = await s.post(L + "/api/conjectures", json={"project_id": pid, **j["proposals"][0]})
        c = (await r.json())["conjecture"]
        assert r.status == 201 and c["kind"] == "conjecture" and c["status"] == "lean-statement"
        assert [e["kind"] for e in c["evidence"]] == ["created", "lean_statement"] and c["chain_ok"]
        # duplicate of an existing dossier is now filtered
        j2 = await (await s.post(L + f"/api/projects/{pid}/conjectures/generate", json={"n": 4})).json()
        assert any(f["reason"] == "duplicate_dossier" for f in j2["filtered"])
        assert (await s.post(L + f"/api/conjectures/{c['id']}/promote")).status == 409    # not proved


async def test_approval_boundary(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    async with running(ctx) as (_s, L, Rm), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        c = (await (await s.post(L + "/api/conjectures", json={"project_id": pid, "statement": "n^2+n+41 prime"})).json())["conjecture"]
        r = await s.post(L + f"/api/conjectures/{c['id']}/experiments", json={"language": "python"})
        exp = (await r.json())["experiment"]
        assert r.status == 201 and exp["status"] == "awaiting_approval" and (await r.json())["approval_required"]
        run_url = L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/run"
        r = await s.post(run_url)
        assert r.status == 403 and (await r.json())["error"] == "not_approved"
        dev, token = ctx.devices.add("phone")
        hdr = {"Authorization": f"Bearer {token}"}
        rurl = Rm + f"/api/conjectures/{c['id']}/experiments/{exp['id']}"
        r = await s.post(rurl + "/approve", json={"code_hash": exp["code_hash"]}, headers=hdr)
        assert r.status == 403 and (await r.json())["error"] == "experiments_host_only"
        assert (await s.post(rurl + "/run", headers=hdr)).status == 403
        # remote devices may not flip the host-only switches
        r = await s.patch(Rm + "/api/settings", json={"experiments_remote": True}, headers=hdr)
        assert r.status == 403
        # a stale approval (code changed after reading) is refused
        r = await s.post(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/approve", json={"code_hash": "x"})
        assert r.status == 409
        r = await s.patch(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}", json={"code": "print(1)"})
        assert r.status == 422
        r = await s.post(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/approve",
                         json={"code_hash": exp["code_hash"]})
        assert r.status == 200 and (await r.json())["experiment"]["approved"]["device"] == "host"
        # editing the code drops the approval
        r = await s.patch(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}", json={"code": EULER_CODE + "\n# x\n"})
        e2 = (await r.json())["experiment"]
        assert e2["approved"] is None and e2["status"] == "awaiting_approval"
        assert (await s.post(run_url)).status == 403
        assert (await s.get(L + "/api/experiments/status")).status == 200


needs_kernel = pytest.mark.skipif(not (shutil.which("jupyter-lab") and shutil.which("sage")),
                                  reason="jupyter-lab / sage not installed")


@needs_kernel
async def test_sage_refutes_euler_and_reverifies_independently(tmp_path, ws, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TEST-SECRET-123")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_TEST_SECRET")
    ctx = make_ctx(tmp_path, ws=ws, brain=FakeBrain(responder))
    events = []
    async with running(ctx) as (_s, L, _R), session() as s:
        (ctx.paths.config / "keys.json").write_text('{"anthropic": "sk-ant-FILE-SECRET"}')
        orig = ctx.bus.publish
        ctx.bus.publish = lambda t, p=None: (events.append((t, p)), orig(t, p))[1]
        pid = (await (await s.post(L + "/api/projects", json={"title": "P", "workspace": ws.key})).json())["project"]["id"]
        c = (await (await s.post(L + "/api/conjectures", json={"project_id": pid, "lean": EULER, "statement":
                                                             "Pour tout n, n^2+n+41 est premier."})).json())["conjecture"]
        assert c["status"] == "lean-statement"
        # (b) small cases in Lean: n = 0..9 proved by norm_num
        r = await s.post(L + f"/api/conjectures/{c['id']}/lean-cases", json={"cases": [{"n": i} for i in range(6)] +
                                                                              [{"n": 40}]})
        e = (await r.json())["entry"]
        assert r.status == 200 and e["data"]["proved"] == 6 and e["data"]["cases"][-1]["proved"] is False
        # (a)+(c) Sage experiment (sage kernel), approved, finds n = 40
        r = await s.post(L + f"/api/conjectures/{c['id']}/experiments", json={"language": "sage"})
        exp = (await r.json())["experiment"]
        await s.post(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/approve",
                     json={"code_hash": exp["code_hash"]})
        r = await s.post(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/run", json={"timeout": 120})
        assert r.status == 202
        for _ in range(900):
            c = (await (await s.get(L + f"/api/conjectures/{c['id']}")).json())["conjecture"]
            if any(x["kind"] == "counterexample_check" for x in c["evidence"]):
                break
            await asyncio.sleep(0.2)
        kinds = [x["kind"] for x in c["evidence"]]
        assert kinds[-2:] == ["experiment", "counterexample_check"], (kinds, c["evidence"][-1]["output"], c["evidence"][-1]["data"])
        ex, chk = c["evidence"][-2], c["evidence"][-1]
        assert ex["verdict"] == "counterexample" and ex["data"]["witness"] == {"n": 40} and ex["data"]["approved"]
        assert chk["data"]["kernel"]["fresh"] and chk["data"]["kernel"]["predicate_false"]
        assert chk["data"]["lean"]["ok"] is True and "¬" in chk["data"]["lean"]["code"]
        assert c["status"] == "refuted" and c["counterexample"]["witness"] == {"n": 40} and c["counterexample"]["lean"]
        assert c["chain_ok"]
        assert any(t == "experiment.output" for t, _p in events)
        assert any(t == "conjecture.updated" and p["conjecture"]["status"] == "refuted" for t, p in events)
        # a wrong witness is NOT confirmed by Lean
        r = await s.post(L + f"/api/conjectures/{c['id']}/refute-lean", json={"witness": {"n": 3}})
        assert (await r.json())["ok"] is False
        # the kernel environment: no API key, no token; Madalean's config dir is hidden; cwd confined
        code = ("# PREDICATE\ndef holds(n):\n    return True\n# SEARCH\nimport os\n"
                "print('ENV', sorted(k for k in os.environ if any(w in k for w in ('KEY','TOKEN','SECRET'))))\n"
                "print('VALS', any('SECRET' in v for v in os.environ.values()))\n"
                f"try:\n    print('KEYS', open({str(ctx.paths.config / 'keys.json')!r}).read())\n"
                "except Exception as e:\n    print('KEYS blocked', type(e).__name__)\n"
                "print('CWD', os.getcwd())\nreport('holds', cases=0)\n")
        r = await s.post(L + f"/api/conjectures/{c['id']}/experiments", json={"language": "python", "code": code})
        exp = (await r.json())["experiment"]
        await s.post(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/approve",
                     json={"code_hash": exp["code_hash"]})
        await s.post(L + f"/api/conjectures/{c['id']}/experiments/{exp['id']}/run")
        for _ in range(600):
            c = (await (await s.get(L + f"/api/conjectures/{c['id']}")).json())["conjecture"]
            if c["evidence"][-1]["data"].get("experiment_id") == exp["id"]:
                break
            await asyncio.sleep(0.2)
        out = c["evidence"][-1]["output"]
        assert "ENV []" in out and "VALS False" in out and "FILE-SECRET" not in out and "KEYS blocked" in out, out
        assert f"CWD {ctx.paths.cache / 'experiments' / c['id']}" in out
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-TEST-SECRET-123"      # the server itself is unchanged


@needs_kernel
async def test_kernel_timeout_is_killed(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    await started(ctx)
    from madalean.research.sagebridge import SageBridge
    b = SageBridge(ctx)
    try:
        r = await b.run("c", "sage", "while True:\n    pass\n", timeout=3)
        assert r.status == "timeout" and r.killed and 2.5 < r.seconds < 30, (r.status, r.error[-3000:], r.stdout[-500:])
        assert b.kernels == {}
        r = await b.run("c", "python", "print(6*7)\nreport('holds', cases=1)\n", timeout=30)
        assert r.status == "ok" and "42" in r.stdout and r.reports == [{"verdict": "holds", "witness": None,
                                                                         "cases": 1, "note": ""}]
        r = await b.run("c", "python", "print('x' * 10000)", max_output=500)
        assert r.status == "output_limit" and r.killed and len(r.stdout) < 700
    finally:
        await b.close()
        await ctx.stop()
