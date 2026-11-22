"""Scripted Brain + Retriever (+ a fake Lean for `--demo`): no GPU, no network, no model.

`FakeBrain(responder)` answers every request with `responder(role, messages, brain)` → str | dict(text, finish).
The default responder (`demo_responder`) recognises the prompts of the pipeline (understand, route, formalize, prove,
explain, notes, informal proof, split, assistant) and answers like the real models would on a simple theorem, so
the whole chain runs end to end — with the REAL Lean compiler in tests, or the fake one in `--demo`."""
from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Any, Callable

from .. import leancheck
from .api import AgentResult, BrainError, Chunk, Completion, ModelRef

Responder = Callable[[str, list, "FakeBrain"], "str | dict"]


def _first_user(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "user":
            return m.get("content", "")
    return messages[0].get("content", "") if messages else ""


def demo_responder(role: str, messages: list[dict], brain: "FakeBrain") -> str | dict:
    b = brain.behaviour
    first = _first_user(messages)
    if first.startswith("You prepare a mathematics problem"):
        if b.get("unknown"):
            return "EN: UNKNOWN"
        return ("EN: Let $a$ and $b$ be even natural numbers. Prove that $a + b$ is even.\n"
                "FR: Soient $a$ et $b$ deux entiers naturels pairs. Montrer que $a + b$ est pair.")
    if first.startswith("You assist a user who proves theorems"):
        msg = re.search(r"The user now writes: « (.*?) »", first, re.S).group(1).lower()
        if b.get("route_garbage"):
            return "Je ne sais pas."
        if "réciproque" in msg or "converse" in msg:
            return ("ACTION: STATEMENT\nEN: Let $a$ and $b$ be natural numbers such that $a$ is even and $a + b$ is "
                    "even. Prove that $b$ is even.\nFR: Soient $a$ et $b$ deux entiers naturels, $a$ pair et $a + b$ "
                    "pair. Montrer que $b$ est pair.")
        if "énoncé" in msg or "statement" in msg:
            return ("ACTION: STATEMENT\nEN: Let $a$ and $b$ be even natural numbers. Prove that $a + b + 0$ is even.\n"
                    "FR: Montrer que $a + b + 0$ est pair.")
        if "expli" in msg or "pourquoi" in msg:
            return "ACTION: EXPLANATION\nEN:\nFR:"
        return "ACTION: PROOF\nEN:\nFR:"
    if first.startswith("Please autoformalize"):
        name = re.search(r"Use the following theorem name: (\S+)", first).group(1)
        if b.get("bad_statement"):
            return f"```lean4\ntheorem {name} (a b : ℕ) (ha : Even a : Even (a + b) := by sorry\n```"
        if "Prove that $b$ is even" in first:
            return f"```lean4\ntheorem {name} (a b : ℕ) (ha : Even a) (hab : Even (a + b)) : Even b := by sorry\n```"
        concl = "Even (a + b + 0)" if ("previous formalization" in first or "a + b + 0" in first) else "Even (a + b)"
        return (f"<think>ok</think>\n```lean4\nimport Mathlib\n\ntheorem {name} (a b : ℕ) (ha : Even a) (hb : Even b) : "
                f"{concl} := by sorry\n```")
    if first.startswith("Complete the following Lean 4 code"):
        stmt = re.search(r"```lean4\n(.*?)```", first, re.DOTALL).group(1)
        sig = stmt[stmt.rindex("theorem"):].replace(":= by sorry", ":= by")
        tactic = "simpa using Even.add ha hb" if len(messages) > 1 else "exact Even.add ha hb"
        if b.get("fail_unless_hint") and "The user gives this hint" not in first:
            tactic = "exact no_such_lemma ha hb"
        if "+ 0" in sig:
            tactic = "simpa using Even.add ha hb"
        if "(hab : Even (a + b))" in sig:
            tactic = "exact (Nat.even_add.mp hab).mp ha"
        if "(ha : Even a)" not in sig:                        # anything else: an honest generic attempt
            tactic = "simp"
        return f"<think>plan</think>\n```lean4\n{sig}\n  {tactic}\n```"
    if first.startswith(("Tu aides un étudiant", "You help a student")):
        return ("- `(a b : ℕ)` : $a$ et $b$ sont des entiers naturels.\n- `(ha : Even a)` : hypothèse « $a$ est pair ».\n"
                "- `(hb : Even b)` : hypothèse « $b$ est pair ».\n- `: Even (a + b)` : la conclusion, $a + b$ est pair.\n\n"
                "En résumé : la somme de deux entiers naturels pairs est paire.")
    if first.startswith(("Tu es un professeur de mathématiques. Voici un théorème et une preuve",
                         "You are a mathematics teacher. Here is a theorem and a Lean 4 proof")):
        return ("**Théorème.** Si $a$ et $b$ sont pairs, alors $a + b$ est pair.\n\n**Démonstration.** Écrivons "
                "$a = 2k$ et $b = 2l$. Alors $a + b = 2(k + l)$, qui est pair. □")
    if first.startswith("Here is a Lean 4 theorem that has not been proved yet"):
        return ("```lean4\n-- the sum of two even numbers is even\n"
                "theorem split_even_add (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry\n"
                "-- zero is even\ntheorem split_even_zero : Even (0 : ℕ) := by sorry\n```")
    if messages and messages[0].get("role") == "system" and "assistant of Madalean" in messages[0]["content"] \
            or messages and messages[0].get("role") == "system" and "l'assistant de Madalean" in messages[0]["content"]:
        q = messages[-1]["content"] if messages else ""
        return f"Voici une piste : pour « {q[:80]} », commencez par `simp`, puis `omega` sur les entiers."
    # explanation (1.1.4 prompt) and anything else
    return "<think>\n\n</think>\n\n**Énoncé.** La somme de deux entiers pairs est paire.\n\n1. On utilise `Even.add`."


class FakeBrain:
    """Implements `madalean.brain.api.Brain`."""

    def __init__(self, responder: Responder | None = None, local=None, delay: float = 0.0, chunk: int = 9,
                 online: bool = True):
        self.responder = responder or demo_responder
        self.local = local
        self.delay = delay
        self.chunk = chunk
        self.online = online
        self.behaviour: dict[str, Any] = {}
        self.requests: list[dict] = []
        self.active = 0
        self.max_active = 0

    def _model(self, role: str, mode: str) -> ModelRef:
        if mode == "local" or not self.online:
            ref = self.local.model_for(role) if self.local is not None else None
            return ref or ModelRef("local", f"fake-{role}.gguf", f"Fake local {role}", local=True)
        return ModelRef("fake", f"fake-{role}", f"Fake online {role}")

    async def complete(self, role, messages, *, mode="auto", temperature=None, max_tokens=None, on_chunk=None,
                       prefer=None, extra=None, only=None) -> Completion:
        model = self._model(role, mode)
        if only and only != model.key:
            raise BrainError("no_model", f"{only} is not available")
        self.requests.append({"role": role, "mode": mode, "messages": [dict(m) for m in messages],
                              "temperature": temperature, "max_tokens": max_tokens, "extra": dict(extra or {}),
                              "model": model.key, "only": only})
        if len(self.requests) > 4000:          # S-H soak: `serve --demo` ran for hours → bounded record
            del self.requests[:-2000]
        t0 = time.monotonic()
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if model.local and self.local is not None:
                url = await self.local.ensure(role)
                if url is None and not getattr(self.local, "fake", False):
                    raise BrainError("no_model", f"no local model for {role}")
            ans = self.responder(role, messages, self)
            if asyncio.iscoroutine(ans):
                ans = await ans
            if isinstance(ans, BaseException):
                raise ans
            d = ans if isinstance(ans, dict) else {"text": ans}
            text, finish = d.get("text", ""), d.get("finish", "stop")
            if d.get("delay") is not None:
                await asyncio.sleep(d["delay"])
            sent = []
            for i in range(0, len(text), self.chunk):
                piece = text[i:i + self.chunk]
                sent.append(piece)
                if on_chunk:
                    on_chunk(Chunk("text", piece))
                await asyncio.sleep(self.delay * random.uniform(0.5, 1.5) if self.delay else 0)
            return Completion("".join(sent), model, finish, tokens_in=sum(len(m.get("content", "")) for m in messages) // 4,
                              tokens_out=len(text) // 4, seconds=time.monotonic() - t0)
        except asyncio.CancelledError:
            raise
        finally:
            self.active -= 1
            if model.local and self.local is not None:
                self.local.release()

    async def run_agent(self, role, system, task, tools, *, mode="auto", max_steps=24, max_seconds=900,
                        on_chunk=None, prefer=None) -> AgentResult:
        c = await self.complete(role, [{"role": "system", "content": system}, {"role": "user", "content": task}],
                                mode=mode, on_chunk=on_chunk)
        return AgentResult(c.text, c.model, 1, "done", [{"role": "assistant", "content": c.text}])

    def candidates(self, role, mode="auto") -> list[ModelRef]:
        out = []
        if mode != "local" and self.online:
            out.append(ModelRef("fake", f"fake-{role}", f"Fake online {role}"))
        out.append(self._model(role, "local"))
        return out

    async def status(self) -> dict:
        return {"online": self.online, "fake": True,
                "providers": [{"id": "fake", "name": "Fake (demo)", "keyed": False, "key_set": False, "ok": True,
                               "paused_until": None, "reason": ""}],
                "local": self.local.status() if self.local is not None and hasattr(self.local, "status") else {}}

    async def refresh(self) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeRetriever:
    DECLS = [
        {"name": "Even.add", "signature": "{m n : α} (hm : Even m) (hn : Even n) : Even (m + n)",
         "doc": "The sum of two even elements is even.", "module": "Mathlib.Algebra.Group.Even"},
        {"name": "Nat.even_add", "signature": "{m n : ℕ} : Even (m + n) ↔ (Even m ↔ Even n)",
         "doc": "", "module": "Mathlib.Algebra.Group.Nat.Even"},
        {"name": "Nat.even_mul", "signature": "{m n : ℕ} : Even (m * n) ↔ Even m ∨ Even n",
         "doc": "", "module": "Mathlib.Algebra.Group.Nat.Even"},
    ]

    async def search(self, workspace_key: str, query: str, k: int = 8) -> list[dict]:
        q = set(re.findall(r"\w+", query.lower()))
        scored = []
        for d in self.DECLS:
            words = set(re.findall(r"\w+", (d["name"] + " " + d["signature"] + " " + d["doc"]).lower()))
            s = len(q & words)
            if s:
                scored.append({**d, "score": float(s)})
        return sorted(scored, key=lambda d: -d["score"])[:k]

    async def premises(self, workspace_key: str, lean_statement: str, k: int = 8) -> list[dict]:
        return await self.search(workspace_key, lean_statement, k)

    async def declaration(self, workspace_key: str, name: str) -> dict | None:
        return next((d for d in self.DECLS if d["name"] == name), None)


class FakeLocal:
    """Stand-in for the local llama-server in `--demo`: same gpu-slot discipline, simulated model swaps."""
    fake = True

    def __init__(self, slots, swap_seconds: float = 0.0):
        from ..slots import current_owner
        self._owner = current_owner
        self.slots = slots
        self.swap_seconds = swap_seconds
        self.loaded: str | None = None
        self.loads = 0
        self._holder: str | None = None
        self._lock = asyncio.Lock()

    def model_for(self, role):
        from ..runtime.llama import ROLE_KIND
        kind = ROLE_KIND.get(role, "prover")
        name = {"prover": "Goedel-Prover-V2-8B.Q4_K_M.gguf", "formalizer": "Goedel-Formalizer-V2-8B.Q4_K_M.gguf",
                "explainer": "Qwen3-8B-Q4_K_M.gguf"}[kind]
        return ModelRef("local", name, name.rsplit(".gguf", 1)[0], local=True)

    async def ensure(self, role):
        owner = self._owner()
        if self._holder != owner:
            await self.slots.acquire("gpu", owner)
            self._holder = owner
        async with self._lock:
            want = self.model_for(role).model_id
            if self.loaded != want:
                self.loaded = None
                await asyncio.sleep(self.swap_seconds)
                self.loaded = want
                self.loads += 1
        return "http://127.0.0.1:0/v1"

    def release(self):
        owner = self._owner()
        if self._holder is not None and (self._holder == owner or self._holder not in self.slots.holders["gpu"]):
            self.slots.release("gpu", self._holder)
            self._holder = None

    def release_owner(self, owner):
        if self._holder == owner:
            self.slots.release("gpu", owner)
            self._holder = None

    def status(self):
        return {"state": "ready" if self.loaded else "stopped", "model": self.loaded, "fake": True,
                "holder": self._holder}


class FakeLean:
    """Lean stand-in for `--demo` only: same interface as `runtime.lean.LeanRunner`, accepts proofs that contain no
    `sorry` and no `no_such`, after a realistic delay. Never used by tests that check real proofs."""

    def __init__(self, slots, seconds: float = 1.5):
        self.slots = slots
        self.seconds = seconds
        self.running: dict = {}

    async def problems(self, ws) -> list[str]:
        return []

    async def check(self, code, ws, timeout_s=180, strict_name=None, owner=None):
        from ..runtime.lean import CompileResult
        from ..slots import current_owner
        async with self.slots.hold("lean", owner or current_owner()):
            await asyncio.sleep(self.seconds * random.uniform(0.6, 1.4))
        body = leancheck.remove_comments(code.rsplit("#print axioms", 1)[0])
        if "no_such" in body or re.search(r"\(ha : Even a : ", body):
            line = next((i + 1 for i, l in enumerate(code.split("\n")) if "no_such" in l or "(ha : Even a :" in l), 1)
            msg = leancheck.LeanMessage("error", line, 2, line, 20, "unknown identifier 'no_such_lemma'")
            v = leancheck.judge(code, [msg], strict_name, 1)
            return CompileResult(v, code, self.seconds, "")
        msgs = []
        if re.search(r"\bsorry\b", body):
            msgs.append(leancheck.LeanMessage("warning", 1, 0, None, None, "declaration uses 'sorry'"))
        if strict_name:
            msgs.append(leancheck.LeanMessage("info", 1, 0, None, None, f"'{strict_name}' depends on axioms: [propext]"))
        v = leancheck.judge(code, msgs, strict_name, 0)
        return CompileResult(v, code, self.seconds, "")

    def kill_all(self):
        pass
