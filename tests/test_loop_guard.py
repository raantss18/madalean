"""Loop guard of the pipeline (S-K, coordinator report 2026-11-21: Cayley-Hamilton correction failed 3/3 with
finish « loop », 0 tokens). Real cause, reproduced on a test server with kilo:nvidia/nemotron-3-ultra: the model
wrote a complete statement, then degenerated into endless `import Mathlib.…` lines; the guard stopped it (right) and
the formalizer threw the whole answer away (wrong), recording 0 tokens / 0 s. Also: the guard was not reset when the
engine restarted with another model, so two partial answers could be judged as one loop."""
from __future__ import annotations

import re

from madalean.brain.api import Chunk, Completion
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.server.routes_work import create_dossier
from helpers import make_ctx, started, wait_idle

STMT = "(a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"


def looping_formalizer(role, messages, brain):
    first = messages[0]["content"]
    if first.startswith("Please autoformalize"):
        name = re.search(r"Use the following theorem name: (\S+)", first).group(1)
        imports = "".join(f"import Mathlib.LinearAlgebra.M{i % 3}\n" for i in range(400))
        return {"text": f"Plan.\n```lean4\ntheorem {name} {STMT}\n```\n\n```lean4\n" + imports}
    return demo_responder(role, messages, brain)


async def test_formalizer_keeps_the_statement_written_before_a_loop(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws, brain=FakeBrain(looping_formalizer)))
    ctx.settings.statement_notes = False
    d, job = await create_dossier(ctx, {"problem": "La somme de deux pairs est paire."})
    await wait_idle(ctx)
    j = ctx.orchestrator.jobs[job.id]
    tr = [a for a in j.attempts if a.stage == "statement"]
    assert tr[0].finish == "loop", [(a.finish, a.summary) for a in tr]
    assert tr[0].status == "accepted" and d.statement.rstrip().endswith("Even (a + b) := by sorry")
    assert tr[0].tokens > 0 and tr[0].gen_seconds >= 0      # what was streamed is counted, not 0
    assert d.proof_is_current
    await ctx.stop()


class RestartingBrain(FakeBrain):
    """Streams half an answer, restarts (as the engine does on a fallback), streams the same half again."""

    async def complete(self, role, messages, *, mode="auto", temperature=None, max_tokens=None, on_chunk=None,
                       prefer=None, extra=None):
        if not messages[0]["content"].startswith("Please autoformalize"):
            return await super().complete(role, messages, mode=mode, temperature=temperature, max_tokens=max_tokens,
                                          on_chunk=on_chunk, prefer=prefer, extra=extra)
        name = re.search(r"Use the following theorem name: (\S+)", messages[0]["content"]).group(1)
        block = "We think about the parity of a and b, and about the sum of two even numbers, once more. " * 2
        for _ in range(3):
            for i in range(0, len(block), 9):
                on_chunk(Chunk("text", block[i:i + 9]))
        on_chunk(Chunk("info", "", {"event": "restart", "model": "fake:a", "reason": "HTTP 429"}))
        on_chunk(Chunk("info", "→ B", {"event": "switch", "model": "fake:b"}))
        text = block * 3 + f"```lean4\ntheorem {name} {STMT}\n```"
        for i in range(0, len(text), 9):
            on_chunk(Chunk("text", text[i:i + 9]))
        return Completion(text, self._model("formalize", mode), "stop", tokens_out=len(text) // 4)


async def test_guard_is_reset_when_another_model_restarts(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws, brain=RestartingBrain()))
    ctx.settings.statement_notes = False
    d, job = await create_dossier(ctx, {"problem": "La somme de deux pairs est paire."})
    await wait_idle(ctx)
    tr = [a for a in ctx.orchestrator.jobs[job.id].attempts if a.stage == "statement"]
    assert tr[0].finish == "stop" and tr[0].status == "accepted", [(a.finish, a.summary) for a in tr]
    await ctx.stop()
