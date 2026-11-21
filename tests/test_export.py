"""Export of a dossier: real PDFs compiled with XeLaTeX (checked with pdftotext), every format, fallbacks."""
import asyncio
import io
import shutil
import subprocess
import time
import zipfile

import pytest

from madalean import export, texio
from madalean.dossiers import Dossier

HAS_TEX = bool(shutil.which("xelatex") or shutil.which("lualatex"))
needs_tex = pytest.mark.skipif(not HAS_TEX or not shutil.which("pdftotext"), reason="TeX / pdftotext not installed")

UNICODE = "ℝ ∀ ∃ → ≤ ⟨⟩ ∑ ↑ ₀ ᶜ ∘ ⁻¹ 𝓝 ∈ ⊆ λ ↦ ≠ ×"
STMT = ("import Mathlib\nimport Aesop\n\nset_option maxHeartbeats 400000\n\nopen BigOperators Real Nat Topology Rat\n\n"
        "theorem uni_demo (f : ℕ → ℝ) (s : Set ℝ) (hf : ∀ n, 0 ≤ f n) (h : ∃ x ∈ s, ∀ y ∈ s, y ≤ x) :\n"
        "    ∑ i in Finset.range 3, f i ≥ 0 ∧ (sᶜ ⊆ sᶜ) := by sorry\n")
PROOF = STMT.replace(":= by sorry", ":= by\n  obtain ⟨x, hx, hmax⟩ := h\n"
                     "  refine ⟨Finset.sum_nonneg (fun i _ => hf i), subset_refl _⟩\n"
                     f"  -- {UNICODE}\n  -- {{braces}} and \\backslash \\end{{Verbatim}} \\input{{/etc/passwd}}")
NASTY = r"""### Plan **audacieux**
Voici 50% de l'idée & le #1 du_jour, avec \foo{x} et $\unknownmacro{y}$ et $\frac{1}{2$ (accolade manquante).
$$\begin{align*} a &= b \\ c &= d \end{align*}$$
$x & y$ puis un $ seul et <b>html</b> <script>alert(1)</script> ~ ^ \\ fin.
| a | b |
|---|---|
| $x_1$ | `code_1` |
```python
print("{}")  # \end{Verbatim}
```
> une citation avec $\R$ et $\N$
1. étape $\mathbb{R}^n$
- puce ✓ ⚠ 🙂 ∎
***
**gras non fermé et *italique
"""


def make(proved=True, explanation="", informal="", notes="", title="Somme positive") -> Dossier:
    d = Dossier(id="20261121-120000-abcd", title=title, theorem="uni_demo",
                problem="Montrer que $\\sum_{i<3} f(i) \\ge 0$.", understood_display="Soit $f \\geq 0$ ; alors la somme est positive.")
    d.add_statement(STMT)
    if notes:
        d.add_notes(notes)
    if proved:
        d.add_proof(PROOF, model="local:Goedel-Prover-V2-8B.Q4_K_M.gguf",
                    meta={"axioms": ["propext", "Classical.choice", "Quot.sound"], "lean": "v4.9.0-rc1",
                          "mathlib": "2f65ba7f1a91", "workspace": "lean-prover49", "checked": time.time(),
                          "strategy": "goedel"})
        if explanation:
            d.add_explanation(explanation)
        if informal:
            d.add_informal_proof(informal)
    return d


def run(coro):
    return asyncio.run(coro)


def pdftext(data: bytes, tmp_path) -> str:
    p = tmp_path / "out.pdf"
    p.write_bytes(data)
    return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, timeout=60).stdout


@needs_tex
def test_pdf_has_structure_stamp_and_every_unicode_symbol(tmp_path):
    d = make(explanation="1. On utilise `Finset.sum_nonneg`.", informal="**Démonstration.** Chaque terme est $\\ge 0$. □",
             notes="- `(f : ℕ → ℝ)` : une suite réelle.")
    e = run(export.export_dossier(d, "pdf", tmp_root=tmp_path / "t"))
    assert e.data.startswith(b"%PDF") and e.fallback == "" and e.filename == "somme_positive.pdf"
    text = pdftext(e.data, tmp_path)
    for sym in UNICODE.split():
        assert sym in text, sym
    order = [text.index(s) for s in ("Énoncé", "Énoncé formalisé en Lean 4", "Lecture guidée", "Démonstration",
                                      "Preuve formelle en Lean 4", "Vérification", "Annexe")]
    assert order == sorted(order)
    assert "v4.9.0-rc1" in text and "2f65ba7f1a91" in text and "Classical.choice" in text and "Goedel-Prover" in text
    assert "/etc/passwd" in text                     # printed literally, never executed / never closes the listing
    assert not list((tmp_path / "t").iterdir())      # temp directories cleaned


@needs_tex
def test_unproved_dossier_has_no_stamp(tmp_path):
    d = make(proved=False)
    e = run(export.export_dossier(d, "pdf", tmp_root=tmp_path, lang="en"))
    text = pdftext(e.data, tmp_path)
    assert "Not proved" in text and "No proof of this statement has been verified" in text
    assert "Verification" not in text and "Axioms used" not in text and "Formal proof" not in text
    lean = run(export.export_dossier(d, "lean", tmp_root=tmp_path)).data.decode()
    assert "Non prouvé" in lean and lean.rstrip().endswith("by sorry")
    # a proof of an older statement is not a proof of the current one
    d2 = make()
    d2.add_statement(STMT.replace("≥ 0", "≥ 1"))
    assert not export.collect(d2).proved and export.collect(d2).stamp is None


@needs_tex
def test_nasty_model_markdown_never_breaks_the_pdf(tmp_path):
    d = make(explanation=NASTY, informal=NASTY, notes=NASTY)
    e = run(export.export_dossier(d, "pdf", tmp_root=tmp_path))
    assert e.data.startswith(b"%PDF") and e.fallback in ("", "verbatim"), e.log
    text = pdftext(e.data, tmp_path)
    assert "unknownmacro" in text and "alert(1)" not in text or e.fallback == "verbatim"
    assert "50%" in text


@needs_tex
def test_compile_failure_falls_back_to_verbatim_then_html(tmp_path, monkeypatch):
    d = make(explanation="Texte $x^2$ normal.", informal="ok")
    real = export.build_tex

    def broken(c, verbatim=False, f=None):
        src = real(c, verbatim, f)
        return src if verbatim else src.replace(r"\end{document}", r"\undefinedcommandxyz\end{document}")
    monkeypatch.setattr(export, "build_tex", broken)
    e = run(export.export_dossier(d, "pdf", tmp_root=tmp_path))
    assert e.fallback == "verbatim" and e.data.startswith(b"%PDF")
    assert "x^2" in pdftext(e.data, tmp_path)                  # the model text, printed as is
    monkeypatch.setattr(export, "build_tex", lambda c, verbatim=False, f=None: r"\documentclass{article}\bad")
    e = run(export.export_dossier(d, "pdf", tmp_root=tmp_path))
    assert e.fallback == "html" and e.content_type.startswith("text/html") and b"uni_demo" in e.data and e.log


def test_no_tex_engine_gives_self_contained_html(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "_engines", lambda: [])
    d = make(informal="Soit $x \\in \\mathbb{R}$ et $a \\le b$.", explanation="<script>x</script>1. `rcases`")
    e = run(export.export_dossier(d, "pdf", tmp_root=tmp_path))
    page = e.data.decode()
    assert e.fallback == "html" and e.filename.endswith(".html") and "no TeX" in e.log
    assert "x ∈ ℝ" in page and "a ≤ b" in page and "<script>x" not in page
    assert "http" not in page.split("<body>")[0].replace("http-equiv", "")     # nothing loaded from the network
    assert "Vérifié par Lean" in page and "Classical.choice" in page and 'class="lean"' in page


def test_timeout_kills_tex_and_returns_html(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "_engines", lambda: [["sh", "-c", "sleep 30", "\x00twice"]])
    t0 = time.monotonic()
    e = run(export.export_dossier(make(), "pdf", tmp_root=tmp_path, timeout=1))
    assert e.fallback == "html" and "timeout" in e.log and time.monotonic() - t0 < 10


def test_text_formats(tmp_path):
    d = make(explanation="1. `simp`", informal="Preuve : évident.", notes="- `f` : une suite")
    md = run(export.export_dossier(d, "md", tmp_root=tmp_path)).data.decode()
    assert md.startswith("# Somme positive") and "```lean4" in md and "Preuve : évident." in md and "propext" in md
    lean = run(export.export_dossier(d, "lean", tmp_root=tmp_path)).data.decode()
    assert lean.startswith("/-!") and "exact" not in lean.split("-/")[0] and "obtain ⟨x, hx, hmax⟩ := h" in lean
    assert "v4.9.0-rc1" in lean.split("-/\n")[0]
    tex = run(export.export_dossier(d, "tex", tmp_root=tmp_path)).data.decode()
    assert tex.startswith("% !TEX program = xelatex") and r"\begin{Verbatim}" in tex and r"\end{document}" in tex
    assert r"\input{/etc/passwd}" not in tex and r"\end{Verbatim} \input" not in tex
    html = run(export.export_dossier(d, "html", tmp_root=tmp_path, lang="en")).data.decode()
    assert "<!doctype html>" in html and "Verified by Lean" in html
    with pytest.raises(ValueError):
        run(export.export_dossier(d, "exe", tmp_root=tmp_path))


@needs_tex
def test_zip_contains_every_format(tmp_path):
    e = run(export.export_dossier(make(informal="ok"), "zip", tmp_root=tmp_path))
    z = zipfile.ZipFile(io.BytesIO(e.data))
    names = sorted(z.namelist())
    assert names == ["somme_positive/somme_positive.lean", "somme_positive/somme_positive.md",
                     "somme_positive/somme_positive.pdf", "somme_positive/somme_positive.tex"]
    assert z.read("somme_positive/somme_positive.pdf").startswith(b"%PDF")


def test_math_sanitiser():
    f = texio.fonts()
    assert texio.sanitize_math(r"$\R \to x_1$", f) == r"$\mathbb{R} \to x_1$"
    assert texio.sanitize_math(r"$\foo{x}$", f).startswith(r"\texttt{")          # unknown macro: literal
    assert texio.sanitize_math(r"$\frac{1}{2$", f).startswith(r"\texttt{")       # unbalanced
    assert texio.sanitize_math(r"$x & y$", f).startswith(r"\texttt{")            # & outside an alignment
    assert texio.sanitize_math(r"$$\begin{align*} a &= b \\ c &= d \end{align*}$$", f) == \
        r"\[\begin{aligned} a &= b \\ c &= d \end{aligned}\]"
    assert texio.sanitize_math(r"$50%$", f) == r"$50\%$"


def test_lean_listing_cannot_escape_and_wraps_missing_glyphs():
    f = texio.fonts()
    src = texio.lean_listing("x\n\\end{Verbatim}\n\\input{/etc/passwd} 𝓝", f=f)
    assert src.count(r"\end{Verbatim}") == 1 and r"\input" not in src
    if f.mono and f.fallbacks and ord("𝓝") not in f.mono:
        assert "{\\MLfb" in src
