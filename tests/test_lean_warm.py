"""Warm Lean checker (TODO B10, DECISIONS D37).

Unit tests drive the real LSP client and pool against `fake_lean_server.py` (no Lean needed); the real-Lean tests
(fixture `ws`, skipped without a built workspace) check that a warm check gives exactly the messages, verdict and
model feedback of a fresh `lean --json` on tests/data/warm_attempts.json, attempt after attempt."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest

from madalean import leancheck, leansandbox
from madalean.runtime import lean as leanmod
from madalean.runtime import leanwarm
from madalean.runtime.lean import LeanRunner
from madalean.slots import Slots

HERE = Path(__file__).resolve().parent
FAKE = HERE / "fake_lean_server.py"
HDR = "import Mathlib\nimport Aesop\n\nset_option maxHeartbeats 400000\n\n"


class FakeWS:
    def __init__(self, tmp: Path, key: str = "fakews"):
        self.key, self.path, self.toolchain, self.sysroot = key, tmp, "leanprover/lean4:v4.9.0-rc1", None
        self.lean_bin = FAKE
        self.log = tmp / f"{key}.starts"
        self.problems: list = []

    def lean_path(self):
        return []

    def env(self):
        return {"LEAN_FAKE_LOG": str(self.log)}

    def check(self):
        return []

    def starts(self, mode: str = "server") -> int:
        try:
            return self.log.read_text().split().count(mode)
        except OSError:
            return 0


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(leansandbox, "wrap", lambda ws, argv, files: [sys.executable, str(FAKE), *argv[1:]])
    monkeypatch.setenv("MADALEAN_LEAN_WARM", "1")
    return FakeWS(tmp_path)


class S:
    lean_warm = True
    lean_warm_idle_minutes = 10


def runner(tmp: Path, settings=None, caps=None) -> LeanRunner:
    return LeanRunner(Slots(caps), tmp / "lean-tmp", lambda: settings or S())


async def ready(r: LeanRunner, ws, code: str = HDR + "theorem t : True := trivial\n", timeout: float = 20):
    """A warm-eligible check (fresh when no worker runs yet: it starts one); then wait until the worker is ready."""
    await r.check(code, ws, 900, None, warm=True)
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        w = r.warm.workers.get(ws.key)
        if w is not None and w.state == "ready":
            return w
        await asyncio.sleep(0.05)
    raise AssertionError(f"warm worker not ready: {r.warm.status()}")


# ---------------------------------------------------------------- pure helpers
def test_header_and_prefix():
    code = HDR + "theorem t : True := trivial\n"
    assert leanwarm.split_header(code) == "import Mathlib\nimport Aesop\n\n"
    assert leanwarm.warm_prefix(code) == "import Mathlib\nimport Aesop\n\ns"
    assert leanwarm.split_header("-- c\n/- block /- nested -/ -/\nimport Mathlib -- x\ntheorem a : True := trivial") \
        == "-- c\n/- block /- nested -/ -/\nimport Mathlib -- x\n"
    assert leanwarm.split_header("theorem t : True := trivial\n") is None          # no import
    assert leanwarm.split_header("import Mathlib\n") is None                         # nothing after the header
    assert leanwarm.split_header("prelude\nimport Init\ntheorem x : True := trivial") is None
    assert leanwarm.split_header("import Mathlib\n/-- doc -/\ntheorem x : True := trivial") == "import Mathlib\n"


def test_utf16_columns_and_json_roundtrip():
    line = "  exact (𝓝 l) bad"
    assert leanwarm.utf16_to_cp(line, 0) == 0
    assert leanwarm.utf16_to_cp(line, 9) == 9 and leanwarm.utf16_to_cp(line, 11) == 10   # 𝓝: 2 units, 1 code point
    assert leanwarm.utf16_to_cp(line, len(line) + 1) == len(line)
    code = "x\n" + line + "\n"
    diags = [{"range": {"start": {"line": 1, "character": 15}, "end": {"line": 1, "character": 18}},
              "fullRange": {"start": {"line": 1, "character": 15}, "end": {"line": 1, "character": 18}},
              "severity": 1, "message": "unknown identifier 'bad'"},
             {"range": {"start": {"line": 1, "character": 2}, "end": {"line": 1, "character": 2}},
              "severity": 3, "message": "info"},
             {"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
              "severity": 2, "message": "silent", "isSilent": True}]
    msgs = leanwarm.diagnostics_to_messages(code, diags)
    assert [(m.severity, m.line, m.col, m.end_line, m.end_col) for m in msgs] == \
        [("error", 2, 14, 2, 17), ("information", 2, 2, None, None)]
    back = leancheck.parse_lean_json(leanwarm.messages_to_json(msgs))
    assert [(m.severity, m.line, m.col, m.end_line, m.end_col, m.text) for m in back] == \
        [(m.severity, m.line, m.col, m.end_line, m.end_col, m.text) for m in msgs]


# ---------------------------------------------------------------- pool behaviour (fake LSP)
async def test_first_check_fresh_then_warm_with_identical_messages(fake, tmp_path):
    r = runner(tmp_path)
    first = await r.check(HDR + "theorem t : True := trivial\n", fake, 30, None, warm=True)
    assert first.via == "fresh"                              # nothing warm yet: fresh, and a worker starts
    await ready(r, fake)
    code = HDR + "theorem t (x : ℕ) : x = x := by\n  exact (𝓝 bad)\n"
    warm = await r.check(code, fake, 30, None, warm=True)
    assert warm.via in ("warm", "warm+fresh")
    fresh = await r.check(code, fake, 30, None)            # default: always fresh
    assert fresh.via == "fresh"
    sig = lambda res: [(m.severity, m.line, m.col, m.end_line, m.end_col, m.text)  # noqa: E731
                       for m in leancheck.parse_lean_json(res.stdout)]
    assert sig(warm) == sig(fresh) and sig(warm)[0][2] == 11      # code-point column after 𝓝
    assert leancheck.errors_for_feedback(code, warm.verdict) == leancheck.errors_for_feedback(code, fresh.verdict)
    assert fake.starts("server") == 1
    r.kill_all()


async def test_strict_acceptance_is_always_confirmed_fresh(fake, tmp_path):
    r = runner(tmp_path)
    await ready(r, fake)
    code = leancheck.with_axiom_probe(HDR + "theorem good : True := trivial\n", "good")
    n_json = fake.starts("json")
    res = await r.check(code, fake, 30, "good", warm=True)
    assert res.verdict.ok and res.via == "warm+fresh" and res.verdict.axioms == ["propext"]
    assert fake.starts("json") == n_json + 1              # the verdict that counts came from a fresh run
    r.kill_all()


async def test_disagreement_keeps_fresh_verdict_and_sets_warm_aside(fake, tmp_path):
    r = runner(tmp_path)
    await ready(r, fake)
    code = leancheck.with_axiom_probe(HDR + "theorem good : True := trivial -- DISAGREE\n", "good")
    res = await r.check(code, fake, 30, "good", warm=True)
    assert not res.verdict.ok and res.via == "warm+fresh"
    assert "fakews" in r.warm.distrusted and not r.warm.workers
    again = await r.check(HDR + "theorem t : True := bad\n", fake, 30, None, warm=True)
    assert again.via == "fresh"
    from madalean.server.routes_core import _warm_check
    row = _warm_check(r.warm.status())
    assert not row["ok"] and row["repair"] == "lean_warm"
    r.warm.reset()
    assert not r.warm.distrusted
    r.kill_all()


async def test_rejections_are_audited_first_then_every_n(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(leanwarm, "AUDIT_EVERY", 3)
    r = runner(tmp_path)
    await ready(r, fake)
    vias = []
    for i in range(5):
        res = await r.check(HDR + f"theorem t{i} : True := bad\n", fake, 30, None, warm=True)
        assert not res.verdict.ok and res.verdict.errors[0].text == "unknown identifier 'bad'"
        vias.append(res.via)
    assert vias == ["warm+fresh", "warm", "warm", "warm+fresh", "warm"]
    assert not r.warm.distrusted
    r.kill_all()


async def test_no_state_leaks_between_attempts(fake, tmp_path):
    r = runner(tmp_path)
    w = await ready(r, fake)
    await r.check(HDR + "theorem a : True := bad\n-- LATEPUB\n", fake, 30, None, warm=True)
    res = await r.check(HDR + "theorem b : True := trivial\n", fake, 30, None, warm=True)
    assert res.verdict.ok and res.via in ("warm", "warm+fresh") and not res.stdout.strip()
    # every attempt is preceded by a reset of the document to the prefix alone
    assert w.version >= 5
    r.kill_all()


async def test_other_header_runs_fresh_and_restarts_after_repeats(fake, tmp_path):
    r = runner(tmp_path)
    await ready(r, fake)
    other = "import Mathlib\nimport Mathlib.Tactic\n\ntheorem t : True := trivial\n"
    for _ in range(leanwarm.MISMATCH_RESTART - 1):
        assert (await r.check(other, fake, 30, None, warm=True)).via == "fresh"
    assert r.warm.workers["fakews"].prefix.startswith("import Mathlib\nimport Aesop")
    assert (await r.check(other, fake, 30, None, warm=True)).via == "fresh"        # restart on the new header
    t0 = time.monotonic()
    while r.warm.workers.get("fakews") is None or r.warm.workers["fakews"].state != "ready":
        assert time.monotonic() - t0 < 20
        await asyncio.sleep(0.05)
    assert r.warm.workers["fakews"].prefix == leanwarm.warm_prefix(other)
    assert (await r.check(other, fake, 30, None, warm=True)).via in ("warm", "warm+fresh")
    r.kill_all()


async def test_timeout_does_not_poison_the_next_attempt(fake, tmp_path):
    r = runner(tmp_path)
    await ready(r, fake)
    slow = HDR + "theorem t : True := trivial -- SLEEP=30\n"
    t0 = time.monotonic()
    res = await r.check(slow, fake, 1, None, warm=True)      # warm wait is at least 5 s
    assert res.timed_out and res.via == "warm" and time.monotonic() - t0 < 15
    assert "fakews" not in r.warm.workers                     # killed, never reused
    nxt = await r.check(HDR + "theorem u : True := bad\n", fake, 30, None, warm=True)
    assert not nxt.timed_out and nxt.verdict.errors        # fresh while the new worker loads
    await ready(r, fake)
    assert fake.starts("server") == 2
    r.kill_all()


async def test_cancel_kills_the_worker_and_leaves_no_stuck_lock(fake, tmp_path):
    r = runner(tmp_path)
    await ready(r, fake)
    t = asyncio.create_task(r.check(HDR + "theorem t : True := trivial -- SLEEP=30\n", fake, 60, None, warm=True))
    await asyncio.sleep(1.0)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    assert "fakews" not in r.warm.workers and not r.running
    assert r.slots.usage()["lean"]["used"] == 0
    res = await asyncio.wait_for(r.check(HDR + "theorem u : True := bad\n", fake, 30, None, warm=True), 20)
    assert res.via == "fresh" and res.verdict.errors
    r.kill_all()


async def test_crash_during_a_check_falls_back_to_fresh(fake, tmp_path):
    r = runner(tmp_path)
    await ready(r, fake)
    res = await r.check(HDR + "theorem t : True := bad -- CRASH\n", fake, 30, None, warm=True)
    assert res.via == "fresh" and res.verdict.errors and r.warm.stats["fresh_fallback"] >= 1
    assert "fakews" not in r.warm.workers
    r.kill_all()


async def test_broken_header_never_judges_and_is_not_retried_at_once(fake, tmp_path):
    r = runner(tmp_path)
    code = "import Mathlib.Broken\n\ntheorem t : True := trivial\n"
    assert (await r.check(code, fake, 30, None, warm=True)).via == "fresh"
    t0 = time.monotonic()
    while "fakews" not in r.warm.failures:
        assert time.monotonic() - t0 < 20
        await asyncio.sleep(0.05)
    assert (await r.check(code, fake, 30, None, warm=True)).via == "fresh"
    assert fake.starts("server") == 1                       # RETRY_AFTER_FAILURE
    r.kill_all()


async def test_gate_runs_before_any_lean(fake, tmp_path):
    r = runner(tmp_path)
    res = await r.check(HDR + '#eval IO.println "x"\n', fake, 30, None, warm=True)
    assert not res.verdict.ok and res.verdict.reasons
    assert fake.starts("server") == 0 and fake.starts("json") == 0


async def test_disabled_idle_and_workspace_change(fake, tmp_path):
    s = S()
    r = runner(tmp_path, s)
    await ready(r, fake)
    w = r.warm.workers["fakews"]
    w.last_used -= 11 * 60                                    # idle for longer than the setting
    r.warm.reap_once()
    assert "fakews" not in r.warm.workers
    await asyncio.wait_for(w.proc.wait(), 10)                 # the process is really gone
    await ready(r, fake)
    s.lean_warm = False
    res = await r.check(HDR + "theorem t : True := trivial\n", fake, 30, None, warm=True)
    assert res.via == "fresh" and not r.warm.workers
    s.lean_warm = True
    await ready(r, fake)
    fake.toolchain = "leanprover/lean4:v4.10.0"             # the workspace changed (update / switch)
    r.warm.forget_changed([fake])
    assert not r.warm.workers
    r.kill_all()


async def test_worker_above_the_memory_cap_is_recycled_when_idle(fake, tmp_path, monkeypatch):
    r = runner(tmp_path)
    w = await ready(r, fake)
    assert w.status()["rss_mb"] > 0
    monkeypatch.setattr(leanwarm, "MAX_MEMORY_MB", 0)
    r.warm.reap_once()
    assert "fakews" not in r.warm.workers
    r.kill_all()


async def test_warm_checks_hold_a_lean_slot(fake, tmp_path):
    r = runner(tmp_path, caps={"gpu": 1, "online": 1, "lean": 1})
    await ready(r, fake)
    codes = [HDR + f"theorem t{i} : True := trivial\n" for i in range(4)]
    res = await asyncio.gather(*(r.check(c, fake, 30, None, warm=True) for c in codes))
    assert all(x.verdict.ok for x in res) and r.slots.max_seen["lean"] == 1
    st = r.warm.status()
    assert st["enabled"] and st["workers"][0]["workspace"] == "fakews" and st["stats"]["warm"] >= 1
    r.kill_all()
    assert not r.warm.workers


# ---------------------------------------------------------------- real Lean
def _attempts() -> list[tuple[dict, str, str | None]]:
    data = json.loads((HERE / "data" / "warm_attempts.json").read_text(encoding="utf-8"))["attempts"]
    out = []
    for a in data:
        code = leancheck.GOEDEL_HEADER + a["body"]
        name = leancheck.theorem_name(code) if a["strict"] else None
        out.append((a, leancheck.with_axiom_probe(code, name) if name else code, name))
    return out


async def test_real_lean_warm_equals_fresh_attempt_after_attempt(ws, tmp_path):
    """The reliability contract: for every attempt, in sequence on one warm Lean, the warm check gives the
    messages (positions included), verdict, axioms and model feedback of a fresh `lean --json`."""
    r = runner(tmp_path)
    attempts = _attempts()
    await ready(r, ws, attempts[0][1], timeout=900)
    w = r.warm.workers[ws.key]
    try:
        for a, code, name in attempts:
            fresh = await r._run(0, code, ws, 300, name)
            async with w.lock:
                out = await w.check(code, 300)
            warm = r._warm_result(0, code, out, name)
            assert not out.timed_out, a["id"]
            assert leanmod._sig(warm) == leanmod._sig(fresh), a["id"]
            allm = lambda res: [(m.severity, m.line, m.col, m.end_line, m.end_col, m.text)  # noqa: E731
                                for m in leancheck.parse_lean_json(res.stdout)]
            assert allm(warm) == allm(fresh), a["id"]
            assert leancheck.errors_for_feedback(code, warm.verdict) == \
                leancheck.errors_for_feedback(code, fresh.verdict), a["id"]
            if ws.key == "lean-prover49":
                assert fresh.verdict.ok == a["expect"], a["id"]
    finally:
        r.kill_all()


async def test_real_lean_runner_contract(ws, tmp_path):
    """Through LeanRunner.check(warm=True): a good strict proof is warm-checked then confirmed fresh (axioms
    recorded from the fresh run); a wrong attempt is answered by the warm Lean in well under a second."""
    r = runner(tmp_path)
    good = leancheck.with_axiom_probe(leancheck.GOEDEL_HEADER + "theorem w_ok (a b : ℕ) : a + b = b + a := by\n"
                                      "  omega\n", "w_ok")
    await ready(r, ws, good, timeout=900)
    try:
        bad1 = leancheck.with_axiom_probe(leancheck.GOEDEL_HEADER + "theorem w_ko (a : ℕ) : a + 1 = a := by\n"
                                          "  omega\n", "w_ko")
        first = await r.check(bad1, ws, 120, "w_ko", warm=True)          # first rejection: audited
        assert not first.verdict.ok and first.via == "warm+fresh"
        bad2 = bad1.replace("w_ko", "w_ko2")
        t0 = time.monotonic()
        second = await r.check(bad2, ws, 120, "w_ko2", warm=True)
        assert not second.verdict.ok and second.via == "warm" and time.monotonic() - t0 < 2.0
        ok = await r.check(good, ws, 120, "w_ok", warm=True)
        assert ok.verdict.ok and ok.via == "warm+fresh" and set(ok.verdict.axioms or []) <= leancheck.ALLOWED_AXIOMS
        assert not r.warm.distrusted
    finally:
        r.kill_all()
