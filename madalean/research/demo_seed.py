"""`madalean serve --demo`: a small research project (2 sources, a blueprint with dossiers, an article) so that the
web UI can be built against realistic data. Network calls of the demo replay recorded answers (`demo_http/`)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from ..logs import get

log = get("research.demo")
DATA = Path(__file__).resolve().parent / "demo_data"
PAPER_KEY = "example2026parity"
NOTE = {"type": "article", "title": "A note on parity", "author": [{"family": "Example", "given": "Ada"}],
        "issued": {"date-parts": [[2026]]}, "abstract": "We recall why the sum of two even integers is even, prove "
        "that the square of an even integer is even, and state an open-looking conjecture about odd squares.",
        "note": "Demo paper written for Madalean (CC0)", "_key": PAPER_KEY}
BOOK = {"type": "book", "title": "An introduction to the theory of numbers",
        "author": [{"family": "Hardy", "given": "G. H."}, {"family": "Wright", "given": "E. M."}],
        "issued": {"date-parts": [[1979]]}, "publisher": "Clarendon Press", "publisher-place": "Oxford",
        "edition": "5", "ISBN": "9780198531715", "msc": ["11-01"], "_key": "hardy1979introduction"}


def install(ctx) -> None:
    marker = ctx.paths.config / ".research-demo-seeded"
    if marker.exists():
        return

    async def run():
        try:
            await seed(ctx)
            marker.write_text("ok")
        except Exception:  # noqa: BLE001
            log.exception("research demo seed failed")
    ctx.spawn(run())


async def seed(ctx) -> dict:
    from . import article as art_mod
    from . import papers
    from .sources import library
    lib = library(ctx)
    p = ctx.projects.store.new("Recherche (démo) — parité", "Projet de démonstration : sources, blueprint, article.",
                               ctx.settings.workspace or "demo")
    await ctx.projects.save(p)
    note, _ = await lib.add_record(p.id, NOTE, via="demo", files=[
        ("parity-note.tar.gz", (DATA / "parity-note.tar.gz").read_bytes()),
        ("parity-note.pdf", (DATA / "parity-note.pdf").read_bytes())], extract=False)
    book, _ = await lib.add_record(p.id, BOOK, via="demo", extract=False, tags=["manuel"])
    await lib.extract(p.id, note["id"])
    await lib.annotate(p.id, note["id"], {"page": 1, "quads": [[126, 341, 485, 341, 126, 364, 485, 364]],
                                          "text": "An integer n is even if there is an integer k such that n = 2k",
                                          "note": "Définition utilisée par tout le reste.", "color": "yellow"})
    await lib.patch(p.id, note["id"], {"status": "reading", "tags": ["parité", "démo"]})
    sh = lib.shelf(p.id)
    bp = await asyncio.to_thread(papers.extract, sh, lib.get(p.id, note["id"]))
    bp["shelf"] = p.id
    created = await papers.create_dossiers(ctx, p.id, bp, None, lib.all_entries(p.id))
    by_node = {n["id"]: n.get("dossier_id") for n in bp["nodes"]}
    from ..demo import PROVED_STATEMENT
    lem = ctx.repo.get(by_node.get("n-lem-sum", ""))
    if lem is not None:
        st = PROVED_STATEMENT.format(name=lem.theorem)
        lem.add_statement(st, model="local:Goedel-Formalizer-V2-8B.Q4_K_M.gguf")
        proof = st.replace(":= by sorry", ":= by\n  exact Even.add ha hb")
        lem.add_proof(proof, model="local:Goedel-Prover-V2-8B.Q4_K_M.gguf",
                      meta={"axioms": ["propext"], "lean": "v4.9.0-rc1", "mathlib": "demo", "workspace": "demo",
                            "seconds": 9.0, "strategy": "goedel", "attempts": 1})
        lem.add_informal_proof("Écrivons $a = 2k$ et $b = 2l$ ; alors $a + b = 2(k + l)$ est pair "
                               "[@example2026parity, Lemma 1.2]. □", "local:Qwen3-8B-Q4_K_M.gguf")
        lem.status = "proved"
        await ctx.repo.save(lem)
    dfn = ctx.repo.get(by_node.get("n-def-even", ""))
    if dfn is not None:
        dfn.add_statement("import Mathlib\n\n-- Even is Mathlib's `Even`: ∃ r, a = r + r\n"
                          f"theorem {dfn.theorem} (n : ℤ) : Even n ↔ ∃ k, n = 2 * k := by sorry\n",
                          model="local:Goedel-Formalizer-V2-8B.Q4_K_M.gguf")
        await ctx.repo.save(dfn)
    await asyncio.to_thread(papers.save, ctx, p.id, bp)
    art = art_mod.default_article(ctx, p.id)
    art["title"] = "Parité des carrés, vérifiée en Lean"
    art["authors"] = [{"name": "Ada Example", "affiliation": "Démo Madalean", "email": ""}]
    art_mod.set_text(art["abstract"], "Nous reprenons la note [@example2026parity] : la somme de deux entiers pairs "
                     "est paire (vérifié par Lean), et nous énonçons les résultats sur les carrés, qui restent à "
                     "vérifier.", "ai", "local:Qwen3-8B-Q4_K_M.gguf")
    intro = next(b for b in art["blocks"] if b["kind"] == "intro")
    art_mod.set_text(intro, "La parité est une notion élémentaire [@hardy1979introduction, Ch. 1]. Cet article "
                     "distingue ce qui est vérifié par Lean de ce qui est seulement énoncé.", "ai",
                     "local:Qwen3-8B-Q4_K_M.gguf")
    await asyncio.to_thread(art_mod.save, ctx, p.id, art)
    ctx.publish("project.updated", {"project": p.to_dict()})
    return {"project": p.id, "sources": [note["id"], book["id"]], "dossiers": [d.id for d in created]}
