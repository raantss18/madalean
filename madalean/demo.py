"""`madalean serve --demo`: scripted fake brain + fake Lean with realistic timings, and a seeded example project,
so that the web UI and the shells can be developed without GPU, models or Lean."""
from __future__ import annotations

from pathlib import Path

from .brain.fake import FakeBrain, FakeLean, FakeLocal, FakeRetriever
from .context import ServerContext
from .paths import Paths
from .workspaces import Workspace

PROVED_STATEMENT = ("import Mathlib\nimport Aesop\n\nset_option maxHeartbeats 400000\n\nopen BigOperators Real Nat "
                    "Topology Rat\n\ntheorem {name} (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry\n")


def demo_context(paths: Paths, delay: float = 0.03, lean_seconds: float = 1.5, swap_seconds: float = 1.5) -> ServerContext:
    ws = Workspace("demo", "Démo (Lean simulé)", Path("/nonexistent/madalean-demo"), "leanprover/lean4:v4.9.0-rc1",
                   True, "Espace simulé du mode démo : aucune vérification réelle.")
    ctx = ServerContext(paths, demo=True, workspaces=[ws])
    ctx.local = FakeLocal(ctx.slots, swap_seconds)
    ctx.lean = FakeLean(ctx.slots, lean_seconds)
    ctx.brain = FakeBrain(local=ctx.local, delay=delay)
    ctx.retriever = FakeRetriever()
    ctx.brain_kind = "fake"
    ctx.settings.workspace = "demo"
    orig = ctx.start

    async def start():
        await orig()
        ctx.settings.workspace = "demo"
        if not ctx.repo.cache:
            await seed(ctx)
    ctx.start = start
    return ctx


async def seed(ctx: ServerContext) -> None:
    p = ctx.projects.store.new("Exemples (démo)", "Projet de démonstration : modèles et Lean simulés.", "demo")
    await ctx.projects.save(p)
    d = ctx.repo.new("Montrer que la somme de deux entiers pairs est paire.", "demo")
    d.project_id = p.id
    d.add_event("user", d.problem, stage="auto")
    d.understood = "Let $a$ and $b$ be even natural numbers. Prove that $a + b$ is even."
    d.understood_display = "Soient $a$ et $b$ deux entiers naturels pairs. Montrer que $a + b$ est pair."
    d.add_event("understood", "Problème compris ainsi (c'est ce texte que l'IA traduit en Lean) :\n"
                + d.understood_display, model="local:Qwen3-8B-Q4_K_M.gguf")
    st = PROVED_STATEMENT.format(name=d.theorem)
    i = d.add_statement(st, model="local:Goedel-Formalizer-V2-8B.Q4_K_M.gguf")
    d.add_event("statement", "L'IA a traduit le problème en Lean. Lean comprend le code (cela ne dit pas qu'il est fidèle). Relisez-le : la preuve "
                "portera exactement sur ce texte.", ref=i, model="local:Goedel-Formalizer-V2-8B.Q4_K_M.gguf")
    d.add_notes("- `(a b : ℕ)` : $a$ et $b$ sont des entiers naturels.\n- `(ha : Even a)` : $a$ est pair.\n"
                "- `(hb : Even b)` : $b$ est pair.\n- `: Even (a + b)` : la conclusion.\n\nEn résumé : la somme de "
                "deux pairs est paire.", "local:Qwen3-8B-Q4_K_M.gguf")
    proof = st.replace(":= by sorry", ":= by\n  exact Even.add ha hb")
    j = d.add_proof(proof, model="local:Goedel-Prover-V2-8B.Q4_K_M.gguf",
                    meta={"axioms": ["propext"], "lean": "v4.9.0-rc1", "mathlib": "demo", "workspace": "demo",
                          "seconds": 12.0, "strategy": "goedel", "attempts": 1})
    d.add_event("proof", "Preuve trouvée et vérifiée par Lean (essai 1, 12 s).", ref=j,
                model="local:Goedel-Prover-V2-8B.Q4_K_M.gguf")
    k = d.add_explanation("**Énoncé.** La somme de deux entiers pairs est paire.\n\n1. On utilise `Even.add`.",
                          model="local:Qwen3-8B-Q4_K_M.gguf")
    d.add_event("explanation", "Explication rédigée par l'IA (la preuve Lean fait foi).", ref=k,
                model="local:Qwen3-8B-Q4_K_M.gguf")
    d.add_informal_proof("**Théorème.** Si $a$ et $b$ sont pairs, $a + b$ est pair.\n\n**Démonstration.** "
                         "$a = 2k$, $b = 2l$, donc $a + b = 2(k + l)$. □", "local:Qwen3-8B-Q4_K_M.gguf")
    d.status = "proved"
    await ctx.repo.save(d, publish=False)
    await __import__("asyncio").to_thread(ctx.library.add_proof, proof, d.title, "demo", d.id)
    d2 = ctx.repo.new("Montrer que le carré d'un entier pair est pair.", "demo")
    d2.project_id = p.id
    d2.add_event("user", d2.problem, stage="auto")
    await ctx.repo.save(d2, publish=False)
