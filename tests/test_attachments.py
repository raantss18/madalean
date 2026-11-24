"""Attachments read once (S-AX, D56): content-addressed digests reused across the project, image transcription by a
(fake) vision model, Local mode, verbatim quotes, target vs provided results, mentions in follow-ups."""
from __future__ import annotations

import asyncio
import struct
import zlib

from madalean.brain.fake import FakeBrain
from madalean.literature import attach
from madalean.literature.types import LiteratureItem, Reference, SourceText
from madalean.pipeline import literature_hook
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.sources import Library
from helpers import make_ctx, running, session

TEX = rb"""\documentclass{article}
\newtheorem{theorem}{Theorem}
\newtheorem{lemma}[theorem]{Lemma}
\begin{document}
\title{A note on odd primes}
\section{Results}
\begin{lemma}\label{l1}
Every prime number $p > 2$ is odd.
\end{lemma}
\begin{theorem}\label{t1}
For every natural number $n \ge 1$ there is a prime $p$ with $n < p \le 2n$.
\end{theorem}
\end{document}
"""


def png() -> bytes:
    raw = b"\x00\xff\xff\xff"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class VisionBrain(FakeBrain):
    def __init__(self, text: str, **kw):
        super().__init__(lambda role, messages, brain: "[]", **kw)
        self.text, self.vision_calls = text, 0

    async def vision(self, data, mime, prompt, *, mode):
        self.vision_calls += 1
        assert mime == "image/png" and data.startswith(b"\x89PNG")
        return self.text, "fake:vision"


def att_ctx(tmp_path, brain=None):
    ctx = make_ctx(tmp_path, brain=brain or FakeBrain(lambda role, messages, brain: "[]", online=False))
    t = ReplayTransport(tmp_path / "none")
    lib = Library(ctx, Fetcher(t))
    lib.embeddings = False
    ctx._research_library = lib
    return ctx, t


async def _new(s, L, pid, title="D"):
    r = await s.post(L + "/api/dossiers", json={"problem": title, "start": False, "project_id": pid,
                                                "statement": "theorem t (n : ℕ) (h : 1 ≤ n) : ∃ p, Nat.Prime p ∧ n < p "
                                                             "∧ p ≤ 2 * n := by sorry"})
    return (await r.json())["dossier"]["id"]


async def _wait_read(s, L, did, n, timeout=60):
    for _ in range(int(timeout / 0.05)):
        atts = (await (await s.get(L + f"/api/dossiers/{did}/attachments")).json())["attachments"]
        a = next(x for x in atts if x["n"] == n)
        if a["state"] != "reading":
            return a
        await asyncio.sleep(0.05)
    raise TimeoutError


async def test_same_file_is_read_once_per_project_and_reused(tmp_path):
    ctx, t = att_ctx(tmp_path)
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.mode = "local"
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        d1, d2 = await _new(s, L, pid, "un"), await _new(s, L, pid, "deux")
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("file", TEX, filename="note.tex", content_type="application/x-tex")
        r = await s.post(L + f"/api/dossiers/{d1}/attachments", data=form)
        assert r.status == 201, await r.text()
        out = await r.json()
        assert out["read"] is True and out["attachment"]["n"] == 1
        a = await _wait_read(s, L, d1, 1)
        assert a["state"] == "read" and not a["verified"]           # no identifier, Local mode: « non vérifiée »
        labels = [it["label"] for it in a["items"]]
        assert len(a["items"]) == 2, a["items"]
        for it in a["items"]:
            q, src = it["quotes"][0], it["texts"][0]["text"]
            assert src[q["start"]:q["end"]] == q["text"] and it["origin"] == "attachment"
        assert any("prime" in it["quotes"][0]["text"] for it in a["items"]) and labels
        n_req = len(ctx.brain.requests)
        form = aiohttp.FormData()
        form.add_field("file", TEX, filename="copie.tex", content_type="application/x-tex")
        r = await s.post(L + f"/api/dossiers/{d2}/attachments", data=form)
        out = await r.json()
        assert r.status == 201 and out["read"] is False and out["attachment"]["state"] == "read"
        assert out["attachment"]["source_id"] == a["source_id"]
        assert len(ctx.brain.requests) == n_req and t.requests == []   # no model, no network: Local mode
        # the second dossier sees the project's digest as « résultats fournis », typed like cited results
        dd = ctx.repo.get(d2)
        items = attach.provided_items(ctx, dd)
        assert items and all(isinstance(i, LiteratureItem) and i.origin == "attachment" for i in items)
        node = items[0].node()
        assert node["origin"] == "attachment" and node["quote"]["text"]
        # a follow-up that names « pièce jointe 1, lemme 1 » gets the verbatim quote, never the raw file
        ctx1 = ctx.repo.get(d1)
        txt = attach.with_mentions(ctx, ctx1, "d'après la pièce jointe 1, lemme 1, conclure")
        assert "Every prime number $p > 2$ is odd." in txt and "\\begin{lemma}" not in txt
        # URL in Local mode: refused before any request
        r = await s.post(L + f"/api/dossiers/{d1}/attachments", json={"url": "https://arxiv.org/abs/2101.00001"})
        assert r.status == 409 and (await r.json())["error"] == "local_mode" and t.requests == []
        # an unknown file type is refused by the Sources rules
        form = aiohttp.FormData()
        form.add_field("file", b"\x00\x01binary", filename="x.bin")
        r = await s.post(L + f"/api/dossiers/{d1}/attachments", data=form)
        assert r.status == 415


async def test_image_is_transcribed_once_by_a_vision_model_or_kept_unread(tmp_path):
    brain = VisionBrain("Theorem 1. For every prime $p > 2$, the number $p$ is odd. Proof: trivial.")
    ctx, _t = att_ctx(tmp_path, brain)
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.mode = "auto"
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        d1 = await _new(s, L, pid)
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("file", png(), filename="board.png", content_type="image/png")
        r = await s.post(L + f"/api/dossiers/{d1}/attachments", data=form)
        assert r.status == 201
        a = await _wait_read(s, L, d1, 1)
        assert a["state"] == "read" and a["transcription"]["note"] == "transcription"
        assert a["transcription"]["model"] == "fake:vision" and brain.vision_calls == 1
        q = a["items"][0]["quotes"][0]
        assert "prime $p > 2$" in q["text"] and "transcription" in q["location"]
        # attached again elsewhere: no second vision call
        d2 = await _new(s, L, pid, "autre")
        form = aiohttp.FormData()
        form.add_field("file", png(), filename="same.png", content_type="image/png")
        out = await (await s.post(L + f"/api/dossiers/{d2}/attachments", data=form)).json()
        assert out["read"] is False and brain.vision_calls == 1
    # no vision model at all: the image is kept, marked « non lue »
    ctx2, _ = att_ctx(tmp_path / "b")
    async with running(ctx2) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        d = await _new(s, L, pid)
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("file", png(), filename="board.png", content_type="image/png")
        await s.post(L + f"/api/dossiers/{d}/attachments", data=form)
        a = await _wait_read(s, L, d, 1)
        assert a["state"] == "unread" and a["items"] == [] and a["transcription"] is None


def test_invented_quote_is_never_kept_in_a_digest():
    it = LiteratureItem(id="L0000000002", reference=Reference(id="source:p/s-1", title="T"),
                        texts=[SourceText("fulltext", "sources", "Every prime number $p > 2$ is odd.")])
    attach._quote(it, 0, "Every prime number is odd and greater than two.", "x")
    assert it.quotes == []
    attach._quote(it, 0, "Every prime number $p > 2$ is odd.", "Lemma 1")
    assert it.quotes and it.quotes[0].location == "Lemma 1"


def test_target_and_provided_results_are_kept_apart():
    from madalean.dossiers import Dossier
    d = Dossier(id="x", title="t", problem="Montrer le postulat de Bertrand", understood="Bertrand's postulate")
    it = LiteratureItem(id="L0000000003", reference=Reference(id="source:p/s-1", title="A note on odd primes"),
                        texts=[SourceText("fulltext", "sources", "Every prime number $p > 2$ is odd.")],
                        origin="attachment", label="Lemma 1")
    attach._quote(it, 0, "Every prime number $p > 2$ is odd.", "Lemma 1")
    m, detail = literature_hook.provided_event(d, [it])
    assert m["params"]["target"] == "Bertrand's postulate" and m["params"]["n"] == 1
    assert "Every prime number" in detail and "Every prime number" not in m["params"]["target"]
    h = literature_hook.hint([it])
    assert h == ""                                           # not formalized: nothing usable for the provers
    it.lean.statement, it.lean.compiled, it.lean.status, it.lean.name = (
        "theorem cited_odd (p : ℕ) (hp : p.Prime) (h : 2 < p) : Odd p := by sorry", True, "to_prove", "cited_odd")
    assert "NOT available in Lean" in literature_hook.hint([it])


async def test_calcul_demande_paperclip_project_attachment(tmp_path, monkeypatch):
    """D59: a Calcul « Demande » cell attaches a file to the PROJECT (read once, same digest as a dossier's), the cell
    is linked to it, and the request naming « pièce jointe 1 » sends the digest's verbatim quote to the model (never
    the raw file); the written code still needs approval."""
    import aiohttp
    from madalean.server.plugins import workbench as wbm
    from test_calcul_notebook import FakeKernels
    seen = []

    def responder(role, messages, brain):
        first = next((m["content"] for m in messages if m.get("role") == "user"), "")
        if "Translate the request into ONE short" in first:
            seen.append(first)
            return "```python\nprint(7 % 2)\n```"
        return "[]"
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: FakeKernels())
    ctx, t = att_ctx(tmp_path, FakeBrain(responder, online=False))
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.mode = "local"
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        D = L + f"/api/calcul/{pid}/docs/calcul"
        q = (await (await s.post(D + "/cells", json={"type": "ask", "prompt": "x"})).json())["cell"]
        form = aiohttp.FormData()
        form.add_field("file", TEX, filename="note.tex", content_type="application/x-tex")
        form.add_field("cell", q["id"])
        r = await s.post(L + f"/api/calcul/{pid}/attachments", data=form)
        assert r.status == 201, await r.text()
        out = await r.json()
        assert out["read"] is True and out["attachment"]["n"] == 1 and out["attachment"]["cells"] == [q["id"]]
        for _ in range(1200):
            a = (await (await s.get(L + f"/api/calcul/{pid}/attachments?cell={q['id']}")).json())["attachments"][0]
            if a["state"] != "reading":
                break
            await asyncio.sleep(0.05)
        assert a["state"] == "read" and len(a["items"]) == 2
        # the same file from another cell: linked, not read again
        n_req = len(ctx.brain.requests)
        form = aiohttp.FormData()
        form.add_field("file", TEX, filename="copie.tex", content_type="application/x-tex")
        form.add_field("cell", "c-other")
        out = await (await s.post(L + f"/api/calcul/{pid}/attachments", data=form)).json()
        assert out["read"] is False and out["attachment"]["cells"] == [q["id"], "c-other"]
        assert len(ctx.brain.requests) == n_req
        assert (await (await s.get(L + f"/api/calcul/{pid}/attachments?cell=nope")).json())["attachments"] == []
        # the request names the attachment: its quote (bounded) reaches the model, the cell keeps the user's words
        r = await s.post(D + f"/cells/{q['id']}/ask",
                         json={"prompt": "d'après la pièce jointe 1, lemme 1, vérifier pour p = 7"})
        assert r.status == 201, await r.text()
        cell = (await r.json())["cell"]
        assert seen and "Every prime number $p > 2$ is odd." in seen[-1] and "\\begin{lemma}" not in seen[-1]
        assert cell["prompt"] == "d'après la pièce jointe 1, lemme 1, vérifier pour p = 7"
        assert (await s.post(D + f"/cells/{q['id']}/run")).status == 403            # approval rule unchanged
        # unlink from a cell; a bad cell id is refused
        r = await s.delete(L + f"/api/calcul/{pid}/attachments/1?cell=c-other")
        assert (await r.json())["attachment"]["cells"] == [q["id"]]
        r = await s.post(L + f"/api/calcul/{pid}/attachments", json={"url": "https://x.org/a", "cell": "a/b"})
        assert r.status == 400
