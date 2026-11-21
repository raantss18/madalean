"""RAG: Lean source parser (docstrings, attributes, to_additive, aliases…) and retrieval on the REAL index of the
lean-prover49 workspace (built once into a temporary cache shared by the brain tests, ≈40 s)."""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from madalean.brain import rag
from madalean.brain.lean_parse import additive_name, parse_source

CACHE = Path(tempfile.gettempdir()) / f"madalean-brain-test-{os.getuid()}"

SRC = '''
/-! # Module doc
theorem not_real : True := trivial
-/
namespace Polynomial
variable {R : Type*} [Semiring R]

section Roots
/-- A root of a degree one polynomial. -/
theorem exists_root_of_degree_eq_one (h : degree p = 1) :
    ∃ x, IsRoot p x := by
  sorry
@[simp] lemma eval_add' {p q : R[X]} : (p + q).eval x = p.eval x + q.eval x := by simp
end Roots

protected theorem _root_.Nat.my_lemma (n : ℕ) : n ≤ n := le_rfl
alias exists_root_deg_one := exists_root_of_degree_eq_one
alias ⟨mp_name, _⟩ := some_iff
instance (priority := 100) instFoo : Inhabited R[X] := ⟨0⟩
instance : Inhabited R := ⟨0⟩
private theorem secret : True := trivial
end Polynomial

@[to_additive "Sum version."]
theorem Finset.prod_le_prod' (h : ∀ i ∈ s, f i ≤ g i) : s.prod f ≤ s.prod g := sorry

@[to_additive]
lemma IsSquare.mul [CommSemigroup α] {a b : α} : IsSquare a → IsSquare b → IsSquare (a * b) := by
  rintro ⟨a, rfl⟩ ⟨b, rfl⟩; exact ⟨a * b, mul_mul_mul_comm _ _ _ _⟩
#align is_square.mul IsSquare.mul
#align even.add Even.add

attribute [to_additive add_pos "**Alias** of `Left.add_pos`."] one_lt_mul'

-- theorem commented_out : True := trivial
def top_level (n : ℕ) : ℕ := n
'''


def test_parser():
    ds = {d.name: d for d in parse_source(SRC, "Mathlib.Test")}
    assert "not_real" not in ds and "commented_out" not in ds and "Polynomial.secret" not in ds
    d = ds["Polynomial.exists_root_of_degree_eq_one"]
    assert d.signature == "(h : degree p = 1) : ∃ x, IsRoot p x" and d.doc == "A root of a degree one polynomial."
    assert d.kind == "theorem" and d.module == "Mathlib.Test" and "[Semiring R]" in d.context
    assert ds["Polynomial.eval_add'"].attrs.startswith("@[simp]")
    assert "Nat.my_lemma" in ds and ds["Polynomial.exists_root_deg_one"].signature.startswith("alias of")
    assert "Polynomial.mp_name" in ds and "Polynomial.instFoo" in ds
    assert ds["Even.add"].origin == "IsSquare.mul" and "Even a → Even b → Even (a + b)" in ds["Even.add"].signature
    assert ds["Finset.sum_le_sum'"].doc == "Sum version." and ds["Finset.sum_le_sum'"].extra.get("guessed")
    assert ds["add_pos"].origin == "one_lt_mul'" and ds["top_level"].kind == "def"
    assert additive_name("Finset.prod_pow") == "Finset.sum_nsmul" and additive_name("isSquare_one") == "even_zero"


def test_query_expansion():
    g = rag.lean_groups("theorem t (s : Finset ℕ) (f g : ℕ → ℝ) (h : ∀ i ∈ s, f i ≤ g i) : ∑ i in s, f i ≤ ∑ i in s, g i := by sorry")
    flat = {w for alts, _ in g for w in alts}
    assert {"sum", "le", "finset"} <= flat and "f" not in flat and "s" not in flat
    weights = {tuple(a): w for a, w in g}
    assert weights[("sum", "finset")] == 2.0                                   # conclusion weighs more
    n = rag.nl_groups("the number of roots of a polynomial is at most its degree")
    assert (["card"], 1.0) in n and (["le"], 1.0) in n
    assert "nonneg" in rag.pattern_words("0 ≤ x ^ 2") and "sq" in rag.pattern_words("0 ≤ x ^ 2")
    assert rag.name_words("exists_linearIndependent_extension") == ["exists", "linear", "independent",
                                                                     "linearindependent", "extension"]


@pytest.fixture(scope="module")
def retr49():
    from madalean.brain.leanrun import workspace
    if workspace("lean-prover49") is None:
        pytest.skip("lean-prover49 workspace not installed")
    r = rag.LeanRetriever(CACHE, embeddings=False)
    assert asyncio.run(r.ensure("lean-prover49", timeout=900)), r.errors
    return r


def test_real_index_search(retr49):
    async def main():
        s = await retr49.search("lean-prover49", "sum of two even numbers is even", 8)
        assert "Even.add" in [x["name"] for x in s][:3]
        s = await retr49.search("lean-prover49", "intermediate value theorem", 8)
        assert "intermediate_value_Icc" in [x["name"] for x in s]
        s = await retr49.search("lean-prover49", "Finset.sum_le_sum", 3)
        assert s[0]["name"] == "Finset.sum_le_sum"
        p = await retr49.premises("lean-prover49", "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry", 5)
        assert "Even.add" in [x["name"] for x in p]
        d = await retr49.declaration("lean-prover49", "exists_linearIndependent_extension")
        assert d["kind"] == "theorem" and "LinearIndependent K" in d["signature"]
        assert d["module"] == "Mathlib.LinearAlgebra.LinearIndependent"
        e = await retr49.declaration("lean-prover49", "Even.add")
        assert e["generated_from"] == "IsSquare.mul" and "original_signature" in e
        assert await retr49.declaration("lean-prover49", "Polynomial.exists_root_of_odd_degree") is None
        sug = await retr49.suggest("lean-prover49", "Nat.even_add_even", 5)
        assert any(x["name"].startswith(("Nat.even_add", "Even.add")) for x in sug)
    asyncio.run(main())


def test_index_key_changes_with_manifest(tmp_path):
    from madalean.workspaces import Workspace
    ws = Workspace("x", "x", tmp_path, "tc", False)
    p1 = rag.index_path(tmp_path, ws)
    (tmp_path / "lake-manifest.json").write_text("{}")
    assert rag.index_path(tmp_path, ws) != p1


def test_embedding_rerank_with_fake_ollama():
    """Semantic re-ranking path, against a fake Ollama (no GPU, no real model)."""
    from aiohttp import web

    async def main():
        async def tags(_):
            return web.json_response({"models": [{"name": "qwen3:8b"}, {"name": "nomic-embed-text:latest"}]})

        async def embed(req):
            body = await req.json()
            assert body["model"] == "nomic-embed-text:latest"
            vecs = [[1.0, 0.0] if ("Even.add" in t or "search_query" in t) else [0.0, 1.0] for t in body["input"]]
            return web.json_response({"embeddings": vecs})
        app = web.Application()
        app.router.add_get("/api/tags", tags)
        app.router.add_post("/api/embed", embed)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        e = rag.Embedder(f"http://127.0.0.1:{port}")
        res = [{"name": "Odd.add_odd", "signature": "", "doc": "", "score": 2.0},
               {"name": "Nat.even_add", "signature": "", "doc": "", "score": 1.9},
               {"name": "Even.add", "signature": "", "doc": "", "score": 1.5}]
        out = await e.rerank("sum of two even numbers", res)
        await e.close()
        await runner.cleanup()
        assert out[0]["name"] == "Even.add" and out[0]["semantic"] == 1.0
        with pytest.raises(ValueError):
            rag.Embedder("http://10.0.0.1:11434")                  # never a non-local embedding server
    asyncio.run(main())
