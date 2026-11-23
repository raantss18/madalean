"""« Mesurer » (D53): the benchmark runner with a scripted brain and a Lean stand-in — strict verdict, statements
that do not compile, budgets (time, money), resume, cost accounting, problem sets (pinning, safe extraction)."""
from __future__ import annotations

import io
import json
import re
import tarfile

import pytest

from helpers import make_ctx
from madalean import leancheck
from madalean.bench import cli as bcli
from madalean.bench import runner as R
from madalean.bench import sets as S
from madalean.brain import usage
from madalean.brain.fake import FakeBrain, FakeLean

HEAD = leancheck.GOEDEL_HEADER


def problem(name: str, concl: str = "Even (a + b)") -> S.Problem:
    st = f"theorem {name} (a b : ℕ) (ha : Even a) (hb : Even b) : {concl} := by sorry\n"
    return S.Problem(name, "unit", HEAD + st, informal=f"statement {name}")


def responder(role, messages, brain):
    """A prover scripted by the theorem's name: *_hard never finds, *_slow answers late, *_paid costs money."""
    first = next(m["content"] for m in messages if m["role"] == "user")
    stmt = re.search(r"```lean4\n(.*?)```", first, re.DOTALL).group(1)
    sig = stmt[stmt.rindex("theorem"):].replace(":= by sorry", ":= by")
    name = leancheck.theorem_name(stmt)
    brain.seen.append(name)
    if "paid" in name:
        usage.record("anthropic", "claude-haiku-5-5", 100_000, 1_000_000)        # 0.01 + 0.50 USD at list price
    tactic = "exact no_such_lemma ha hb" if "hard" in name else "exact Even.add ha hb"
    out = {"text": f"```lean4\n{sig}\n  {tactic}\n```"}
    if "slow" in name and brain.behaviour.get("slow", True):
        out["delay"] = 30
    return out


class PickyLean(FakeLean):
    """FakeLean, except that the benchmark's own fresh check refuses the theorems named *_flaky (what a warm or
    cached acceptance that a fresh Lean does not confirm would look like)."""

    async def check(self, code, ws, timeout_s=180, strict_name=None, owner=None, warm=False):
        if strict_name and "flaky" in strict_name and str(owner or "").startswith(R.VERIFY_OWNER):
            from madalean.runtime.lean import CompileResult
            m = leancheck.LeanMessage("error", 9, 2, 9, 20, "unsolved goals")
            return CompileResult(leancheck.judge(code, [m], strict_name, 1), code, 0.01, "")
        return await super().check(code, ws, timeout_s, strict_name, owner, warm)


def factory(tmp_path, brains: list):
    def make(state_dir, cfg):
        ctx = make_ctx(state_dir, brain=FakeBrain(responder), lean_seconds=0.01)
        ctx.lean = PickyLean(ctx.slots, 0.01)
        ctx.brain.seen = []
        brains.append(ctx.brain)
        s = R.settings_for(cfg)
        s.update(workspace="demo", mode="local")
        ctx.paths.ensure()
        ctx.paths.settings.write_text(json.dumps(s))
        return ctx
    return make


def cfg(**kw) -> R.BenchConfig:
    base = dict(strategy="goedel-local", workspace="demo", attempts=2, time_per_problem=20, jobs=2, compile_timeout=10)
    base.update(kw)
    return R.BenchConfig(**base)


def in_order(problems) -> dict:
    """A selection whose seeded schedule is the order the problems are listed in (tests that depend on order)."""
    import random
    for seed in range(1000):
        q = list(problems)
        random.Random(seed).shuffle(q)
        if q == list(problems):
            return {"count": len(problems), "set_size": len(problems), "seed": seed}
    raise AssertionError("no seed found")


async def run(tmp_path, problems, brains=None, **kw):
    brains = brains if brains is not None else []
    out = tmp_path / "run"
    s = await R.run_bench(cfg(**kw), "unit", problems, out, source={"content_sha256": "x"},
                          selection=in_order(problems), context_factory=factory(tmp_path, brains))
    return s, R.final_rows(R.read_rows(out / "rows.jsonl")), out


async def test_only_a_fresh_strict_verdict_counts(tmp_path):
    ps = [problem("t_a"), problem("t_b"), problem("t_hard"), problem("t_flaky"),
          problem("t_broken", "no_such_thing (a + b)")]
    s, rows, out = await run(tmp_path, ps)
    assert {k: r["status"] for k, r in rows.items()} == {
        "t_a": "verified", "t_b": "verified", "t_hard": "failed", "t_flaky": "rejected", "t_broken": "statement_error"}
    # a statement Lean does not accept is reported apart: not attempted, not a failure
    assert (s["selected"], s["attempted"], s["statement_errors"], s["solved"]) == (5, 4, 1, 2)
    assert s["statement_error_ids"] == ["t_broken"] and s["rate"] == 0.5 and s["complete"] and s["stop"] == "done"
    assert rows["t_flaky"]["verified"] is False and "bench verdict" in rows["t_flaky"]["error"]
    assert rows["t_broken"]["attempts"] == 0
    assert rows["t_hard"]["attempts"] == 2 and rows["t_a"]["attempts"] == 1
    assert sorted(f.name for f in (out / "proofs").iterdir()) == ["t_a.lean", "t_b.lean"]     # verified proofs only
    assert "sorry" not in (out / "proofs" / "t_a.lean").read_text()
    assert rows["t_a"]["tokens_out"] > 0 and rows["t_a"]["model"] and s["cost_usd"] == 0
    assert s["cost_per_verified_usd"] == 0 and s["median_wall_s_solved"] is not None
    assert json.loads((out / "summary.json").read_text())["solved_ids"] == ["t_a", "t_b"]


async def test_resume_redoes_only_what_is_not_final(tmp_path):
    ps = [problem("t_1"), problem("t_2_slow"), problem("t_3")]
    brains: list = []
    s, rows, out = await run(tmp_path, ps, brains, jobs=1, time_budget=1.5)
    assert s["stop"] == "time_budget" and not s["complete"]
    assert rows["t_1"]["status"] == "verified" and rows["t_2_slow"]["status"] == "unfinished" and "t_3" not in rows
    assert s["attempted"] == 1                      # a problem cut by the run's budget is not a failure

    def make(state_dir, c):
        ctx = factory(tmp_path, brains)(state_dir, c)
        ctx.brain.behaviour["slow"] = False
        return ctx
    s2 = await R.run_bench(cfg(jobs=1), "unit", ps, out, source={"content_sha256": "x"},
                           selection=in_order(ps), context_factory=make)
    assert "t_1" not in brains[-1].seen and set(brains[-1].seen) == {"t_2_slow", "t_3"}
    assert s2["solved"] == 3 and s2["complete"] and s2["stop"] == "done"
    with pytest.raises(R.BenchError):               # another configuration never continues this run directory
        await R.run_bench(cfg(attempts=5), "unit", ps, out, source={"content_sha256": "x"},
                          selection=in_order(ps), context_factory=make)


async def test_problem_timeout_is_a_failure_of_that_problem(tmp_path):
    s, rows, _ = await run(tmp_path, [problem("t_ok"), problem("t_slow")], time_per_problem=5.0)
    assert rows["t_slow"]["status"] == "timeout" and rows["t_ok"]["status"] == "verified"
    assert s["attempted"] == 2 and s["solved"] == 1 and s["complete"]


async def test_paid_budget_is_a_hard_stop_and_cost_is_counted(tmp_path):
    ps = [problem("t_paid_1"), problem("t_paid_2"), problem("t_paid_3"), problem("t_paid_4")]
    s, rows, _ = await run(tmp_path, ps, jobs=1, paid_budget=1.0)
    assert s["stop"] == "paid_budget" and list(rows) == ["t_paid_1", "t_paid_2"]      # 0.51 + 0.51 ≥ 1.00: stop
    assert rows["t_paid_1"]["cost_usd"] == pytest.approx(0.51) and s["cost_usd"] == pytest.approx(1.02)
    assert s["cost_per_verified_usd"] == pytest.approx(0.51) and s["paid"] is True
    assert "anthropic:claude-haiku-5-5" in rows["t_paid_1"]["models"]


async def test_a_paid_call_without_budget_stops_the_run(tmp_path):
    s, rows, _ = await run(tmp_path, [problem("t_paid_1"), problem("t_x"), problem("t_y")], jobs=1)
    assert s["stop"] == "paid_call_without_budget" and list(rows) == ["t_paid_1"]
    assert "paid call without a paid budget" in rows["t_paid_1"]["error"]


def test_free_by_default_paid_only_with_a_budget():
    free, paid = R.BenchConfig(strategy="tournament"), R.BenchConfig(strategy="tournament", paid_budget=2.0)
    assert not {"anthropic", "huggingface", "openai", "deepseek"} & R.allowed_providers(free)
    assert {"gemini", "groq", "mistral"} <= R.allowed_providers(free)
    assert "anthropic" in R.allowed_providers(paid)
    assert R.allowed_providers(R.BenchConfig(strategy="tournament", providers=["groq", "anthropic"])) == {"groq"}
    s = R.settings_for(free)
    assert (s["claude_reinforce"], s["hf_goedel"], s["conductor"]) == (False, False, False)
    assert s["claude_cap_month_usd"] == 0 and s["claude_cap_proof_usd"] == 0 and s["statement_check"] is False
    assert R.settings_for(paid)["claude_cap_month_usd"] == 2.0
    assert R.settings_for(R.BenchConfig(strategy="conductor"))["conductor"] is True
    with pytest.raises(R.BenchError):
        R.settings_for(R.BenchConfig(strategy="single"))
    with pytest.raises(R.BenchError):
        R.settings_for(R.BenchConfig(strategy="certificate"))

    class Store:
        def get(self, p):
            return "k-" + p

        def providers(self):
            return ["anthropic", "gemini"]
    keys = R.ReadOnlyKeys(Store(), R.allowed_providers(free))
    assert keys.get("anthropic") is None and keys.get("gemini") == "k-gemini" and keys.providers() == ["gemini"]
    with pytest.raises(R.BenchError):
        keys.set("gemini", "x")


async def test_no_model_brain_answers_nothing():
    b = R.NoModelBrain()
    assert b.candidates("prove", "online") == [] and await b.internet() is False
    with pytest.raises(Exception):
        await b.complete("prove", [{"role": "user", "content": "x"}])


def test_the_given_statement_is_pinned():
    p = problem("t_pin")
    good = p.statement.replace(":= by sorry", ":= by\n  exact Even.add ha hb")
    assert R.pinned(p.statement, good)
    assert not R.pinned(p.statement, good.replace("Even (a + b)", "True"))          # another conclusion
    assert not R.pinned(p.statement, good.replace("(hb : Even b)", "(hb : Even b) (h : False)"))
    assert not R.pinned(p.statement, "theorem t_pin : True := by trivial")
    assert R.pinned(p.statement, good.replace("theorem t_pin", "-- a comment\ntheorem t_pin"))


def test_batch_file_keeps_each_statement_in_its_section():
    ps = [problem("t_a"), problem("t_b")]
    code, ranges = R.batch_file(ps)
    lines = code.split("\n")
    assert lines[:2] == ["import Mathlib", "import Aesop"] and code.count("import Mathlib") == 1
    for pid, (a, b) in ranges.items():
        block = lines[a - 1:b]
        assert block[0] == "section" and block[-2] == "end" and any(f"theorem {pid} " in ln for ln in block)
    assert ranges["t_a"][1] < ranges["t_b"][0]


# ---------------------------------------------------------------- problem sets
def archive(files: dict[str, bytes], extra=()) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            ti = tarfile.TarInfo("repo-abc/" + name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        for ti in extra:
            tf.addfile(ti)
    return buf.getvalue()


def test_fetch_pins_the_content_and_extracts_only_problem_files(tmp_path, monkeypatch):
    src = S.Source("mini", "o/r", "c" * 40, "MIT", "LICENSE", "lean", r"^P/(Valid|Test)/[\w']+\.lean$", "",
                   ("valid", "test"))
    monkeypatch.setitem(S.SOURCES, "mini", src)
    files = {"P/Valid/p1.lean": "import Mathlib\ntheorem p1 : 1 + 1 = 2 := by sorry\n".encode(),
             "P/Test/p2.lean": "import Mathlib\n/-- doc text -/\ntheorem p2 (n : ℕ) : n = n :=\n  sorry\n".encode(),
             "LICENSE": b"MIT", "README.md": b"x", "P/Valid/evil.sh": b"rm", "../../outside.lean": b"theorem x"}
    link = tarfile.TarInfo("repo-abc/P/Valid/link.lean")
    link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
    calls = []

    def download(url):
        calls.append(url)
        return archive(files, [link])
    meta = S.fetch("mini", tmp_path, download=download)
    assert calls == ["https://codeload.github.com/o/r/tar.gz/" + "c" * 40]
    root = S.set_dir("mini", tmp_path) / "files"
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == [
        "LICENSE", "P/Test/p2.lean", "P/Valid/p1.lean"]
    assert not (tmp_path / "outside.lean").exists() and meta["problems"] == 2 and meta["licence"] == "MIT"
    assert S.fetch("mini", tmp_path, download=download) == meta and len(calls) == 1          # cached
    ps = S.load("mini", tmp_path)
    assert [(p.id, p.split) for p in ps] == [("p1", "valid"), ("p2", "test")]
    assert ps[1].statement.rstrip().endswith(":= by sorry") and ps[1].informal == "doc text"
    assert [p.id for p in S.load("mini", tmp_path, split="test")] == ["p2"]
    # a changed upstream (or a tampered cache) is refused
    (root / "P/Valid/p1.lean").write_text("theorem p1 : False := by sorry\n")
    with pytest.raises(S.SetError):
        S.load("mini", tmp_path)
    monkeypatch.setitem(S.SOURCES, "mini", S.Source(**{**src.__dict__, "content_sha256": "0" * 64}))
    with pytest.raises(S.SetError):
        S.fetch("mini", tmp_path, download=download, force=True)
    with pytest.raises(S.SetError):
        S.source_meta("mini", tmp_path / "elsewhere")


def test_putnam_answers_are_filled_in_and_selection_is_deterministic():
    text = ("import Mathlib\n\nabbrev putnam_x_solution : ℕ → ℕ := sorry\n-- fun n => 2 ^ n\n/--\nCount them.\n-/\n"
            "theorem putnam_x (n : ℕ) : putnam_x_solution n = 2 ^ n :=\nsorry\n")
    st, informal, note = S.normalise(text)
    assert "putnam_x_solution : ℕ → ℕ := fun n => 2 ^ n" in st and st.rstrip().endswith(":= by sorry")
    assert st.count("sorry") == 1 and informal == "Count them." and "answer" in note
    ps = S.smoke()
    assert len(ps) == 20 and len({p.id for p in ps}) == 20 and len({p.branch for p in ps}) >= 8
    assert all(p.theorem == p.id and p.statement.startswith("import Mathlib") for p in ps)
    a, b = S.select(ps, sample=7, seed=3), S.select(list(reversed(ps)), sample=7, seed=3)
    assert [p.id for p in a] == [p.id for p in b] == sorted(p.id for p in a) and len(a) == 7
    assert [p.id for p in S.select(ps, sample=7, seed=4)] != [p.id for p in a]
    assert [p.id for p in S.select(ps, ids=["smoke_alg_square"])] == ["smoke_alg_square"]
    assert len(S.select(ps, limit=3)) == 3 and S.source_meta("smoke")["problems"] == 20
    assert all(S.SOURCES[n].content_sha256 and len(S.SOURCES[n].commit) == 40 for n in S.SOURCES)   # pinned


def test_site_page_is_generated_from_the_committed_summaries(tmp_path):
    import sys
    from pathlib import Path
    site = Path(__file__).resolve().parent.parent / "site"
    if str(site) not in sys.path:
        sys.path.insert(0, str(site))
    from madasite import measures
    res = tmp_path / "bench" / "results"
    s = {"format": 1, "set": "minif2f", "config": "tournament", "strategy": "tournament", "workspace": "lean-prover49",
         "lean": "v4.9.0-rc1", "mathlib": "2f65", "date": "2026-11-22", "madalean": "2.0.3", "selected": 50,
         "attempted": 48, "statement_errors": 2, "solved": 12, "complete": False, "median_wall_s_solved": 41.5,
         "cost_usd": 0.0, "cost_per_verified_usd": 0.0, "model_calls": 30, "paid": False,
         "found_by": {"mathlib:a": 2, "mathlib:b": 1, "groq:meta/llama-x:free": 9},
         "budgets": {"time_per_problem_s": 150, "attempts": 3},
         "selection": {"split": "valid", "set_size": 244, "seed": 1, "count": 50},
         "source": {"repo": "yangky11/miniF2F-lean4", "commit": "5746b7d6c47855ce", "licence": "MIT"}}
    bcli.publish(s, res)
    (res / "broken.json").write_text("{not json")
    (res / "other.json").write_text(json.dumps({"format": 99}))
    for lg in ("fr", "en"):
        (tmp_path / "out" / lg).mkdir(parents=True)
    assert measures.build(tmp_path / "out", tmp_path, "https://github.com/raantss18/madalean") == 1
    fr = (tmp_path / "out" / "fr" / "measures.html").read_text()
    en = (tmp_path / "out" / "en" / "measures.html").read_text()
    assert "<strong>12 / 48</strong> (25 %)" in fr and "50 sur 244, graine 1" in fr and "41,5 s" in fr
    assert "2 énoncés non compilés" in fr and "passage incomplet" in fr and "0 $ (gratuit)" in fr
    assert "Mathlib (sans modèle) × 3" in fr and "llama-x × 9" in fr and 'lang="fr"' in fr
    assert "50 of 244, seed 1" in en and "41.5 s" in en and "$0 (free)" in en and "incomplete run" in en
    assert "yangky11/miniF2F-lean4/tree/5746b7d6c47855ce" in en and "licence MIT" in en
    assert "No measurement published yet." in measures.page("en", [], "https://github.com/raantss18/madalean")


def test_cli_and_published_summary(tmp_path, monkeypatch, capsys):
    from madalean import cli
    monkeypatch.setenv("MADALEAN_BENCH_CACHE", str(tmp_path / "cache"))
    assert cli.main(["bench", "sets"]) == 0
    out = capsys.readouterr().out
    assert "smoke" in out and "yangky11/miniF2F-lean4@5746b7d6c478" in out and "not fetched" in out
    assert cli.main(["bench", "run", "minif2f", "--sample", "3"]) == 2                 # not fetched: says how
    assert "madalean bench fetch minif2f" in capsys.readouterr().err
    assert cli.main(["bench", "run", "smoke", "--strategy", "certificate"]) == 2
    s = {"set": "minif2f", "config": "single:groq:llama/x", "workspace": "lean-prover49", "solved": 1, "attempted": 2,
         "selected": 2, "statement_errors": 0, "stop": "done",
         "selection": {"split": "valid", "count": 2, "set_size": 244, "seed": 1}}
    f = bcli.publish(s, tmp_path / "results")
    assert f.name == "minif2f-valid-n2-seed1__single-groq-llama-x__lean-prover49.json"
    assert json.loads(f.read_text())["solved"] == 1 and "1/2" in bcli.line(s)


def test_a_let_inside_the_statement_is_not_its_end():
    text = ("import Mathlib\n\ntheorem putnam_y (f : ℕ → ℕ × ℕ) :\n    let ⟨p, q⟩ := f 0\n    p + q = q + p :=\n  sorry\n")
    st, _, _ = S.normalise(text)
    assert "let ⟨p, q⟩ := f 0" in st and "p + q = q + p := by sorry" in st


def test_who_found_it_separates_mathlib_alone_from_a_model_adapted_lemma():
    assert R.winner_of({"model": "mathlib:exact rfl", "model_calls": 0, "models": []}) == R.NO_MODEL
    assert R.winner_of({"model": "mathlib:norm_num", "model_calls": 2, "models": ["groq:x"]}) == R.ADAPTED
    assert R.winner_of({"model": "groq:x", "model_calls": 2}) == "groq:x"
