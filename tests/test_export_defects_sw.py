"""PDF export defects seen on the real dossiers (TODO P1 11, S-W): Mathlib version printed « — », « Théorème. »
repeated, numbering of the annex, glosses cut after one sentence."""
import asyncio
import shutil
import subprocess
import time

import pytest

from madalean import export, texio
from madalean.dossiers import Dossier

HAS_TEX = bool(shutil.which("xelatex") or shutil.which("lualatex") or export.tectonic_cmd())
needs_tex = pytest.mark.skipif(not HAS_TEX or not shutil.which("pdftotext"), reason="TeX / pdftotext not installed")

STMT = "import Mathlib\n\ntheorem compact_demo (K : Set ℝ) (hK : IsCompact K) : True := by sorry\n"
PROOF = STMT.replace("by sorry", "by\n  trivial")

# the explanation shape that Gemini / Mistral produce for the prompt « 1. énonce… 2. idée… 3. étapes »
EXPL_BOLD = ("1. **Énoncé du théorème en langage mathématique courant :**  \n"
             "Soit $f$ continue sur un compact $K$. Alors $f$ est bornée.\n\n"
             "2. **Idée de la preuve :**  \nOn utilise la compacité.\n\n"
             "3. **Commentaires sur les étapes de la preuve :**\n\n"
             "- **`refine ⟨a, b⟩`**  \n  Cette tactique découpe le but :\n  - `a` : borne supérieure.\n"
             "  - `b` : borne inférieure.\n")
EXPL_HEADINGS = ("Voici l'explication.\n\n### 1. Énoncé en langage mathématique courant\n\nSoit $X$ un espace de "
                 "Banach.\n\n### 2. Idée de la preuve\n\nOn applique Mathlib.\n\n### 3. Explication des étapes\n\n"
                 "1. **`norm_num`** : calcul.\n2. **`apply foo`** : on applique foo.\n3. **`exact h`** : fin.")
INFORMAL = ("**Théorème.** Soit $K$ un compact non vide.\n\n**Démonstration.** Puisque $K$ est compact, "
            "l'image est bornée. □")


def make(meta_mathlib="", explanation=EXPL_BOLD, informal=INFORMAL) -> Dossier:
    d = Dossier(id="20261122-120000-abcd", title="Fonction continue sur un compact", theorem="compact_demo",
                problem="Montre que toute fonction continue sur un compact est bornée.",
                understood_display="Toute fonction continue sur un compact de $\\mathbb{R}$ est bornée.")
    d.add_statement(STMT)
    d.add_proof(PROOF, model="gemini:gemini-3-flash-preview",
                meta={"axioms": ["propext"], "lean": "v4.9.0-rc1", "mathlib": meta_mathlib,
                      "workspace": "lean-prover49", "checked": time.time(), "strategy": "agent"})
    d.add_explanation(explanation)
    if informal:
        d.add_informal_proof(informal)
    return d


# ---------------------------------------------------------------- Mathlib version
def test_stamp_takes_the_workspace_mathlib_when_the_proof_did_not_record_it():
    # proofs checked before the checkout detection carry « mathlib: "" »: the stamp must not print « — »
    c = export.collect(make(meta_mathlib=""), "fr", {"workspace": "lean-prover49", "lean": "v4.9.0-rc1",
                                                     "mathlib": "2f65ba7f1a91 (checkout)"})
    rows = dict(export._stamp_rows(c))
    assert rows["Mathlib"] == "2f65ba7f1a91 (checkout)"
    tex = export.build_tex(c)
    assert "2f65ba7f1a91" in tex
    # the version recorded with the proof wins over the current workspace
    c2 = export.collect(make(meta_mathlib="v4.9.0 @ abcdef012345"), "fr", {"mathlib": "other"})
    assert dict(export._stamp_rows(c2))["Mathlib"] == "v4.9.0 @ abcdef012345"


# ---------------------------------------------------------------- « Théorème. » repeated
def test_annex_drops_the_restated_statement_and_numbers_only_the_steps():
    out = export.document_explanation(EXPL_BOLD)
    assert "Énoncé" not in out and "Soit $f$ continue" not in out
    assert "### Idée de la preuve" in out and "### Commentaires sur les étapes de la preuve" in out
    assert not any(ln.startswith(("1. **", "2. **", "3. **")) for ln in out.split("\n"))
    out2 = export.document_explanation(EXPL_HEADINGS)
    assert "Banach" not in out2 and out2.startswith("Voici l'explication.")
    assert "### Idée de la preuve" in out2 and "### Explication des étapes" in out2
    assert "1. **`norm_num`** : calcul." in out2                          # the steps keep their numbers
    tex = texio.sanitize_markdown(out2)
    assert tex.count("\\begin{enumerate}") == 1 and tex.count("\\item") == 3 and "setcounter" not in tex


def test_annex_without_sections_or_with_tactic_steps_in_bold_is_untouched():
    plain = "On applique le lemme.\n\n1. **intro x**\n   on introduit x.\n2. **simp**\n   on simplifie."
    assert export.document_explanation(plain) == plain                   # bold tactic steps are not section titles
    assert export.document_explanation("") == ""
    only = "### Énoncé\n\nSoit x."                                          # nothing else: kept
    assert "Soit x." in export.document_explanation(only)


def test_proof_body_for_the_article_proof_environment():
    assert export.proof_body(INFORMAL) == "Puisque $K$ est compact, l'image est bornée."
    assert export.proof_body("Démonstration. Soit ε > 0. ∎") == "Soit ε > 0."
    assert export.proof_body("Proof of the claim uses x.") == "Proof of the claim uses x."
    assert export.proof_body("Preuve : évident.") == "évident."


def test_article_statement_label_is_removed():
    from madalean.research.article import statement_text

    class D:
        extra, problem, source, title = {}, "", {}, "t"
        understood_display = ""
    for raw in ("**Théorème.** Soit x.", "Théorème 1.2. Soit x.", "Lemme (Riesz) : Soit x."):
        d = D()
        d.understood_display = raw
        assert statement_text(d) == "Soit x."
    d = D()
    d.understood_display = "Théorème de Riesz : soit X."              # a name, not a label: kept
    assert statement_text(d).startswith("Théorème de Riesz")


def test_tex_document_has_one_statement_and_a_clean_annex():
    tex = export.build_tex(export.collect(make(), "fr", {}))
    assert tex.count("\\begin{MLstatement}") == 1
    body = tex.split("\\begin{document}", 1)[1]
    assert "Théorème." not in body and "Démonstration." not in body
    annex = body.split("Annexe", 1)[1]
    assert "Énoncé du théorème" not in annex and "Soit $f$ continue" not in annex
    assert "\\begin{enumerate}" not in annex                               # the three sections are titles now


def test_double_backtick_code_is_code():
    tex = texio.sanitize_markdown("* ``theorem foo_bar`` : le nom `foo_bar`.")
    assert "``" not in tex and "`" not in tex
    assert tex.count("\\texttt{") == 2
    html = texio.markdown_to_html("``theorem x`` et `y`")
    assert "<code>theorem x</code>" in html and "<code>y</code>" in html


# ---------------------------------------------------------------- cut glosses
def test_a_cut_gloss_is_not_saved(tmp_path):
    from madalean.pipeline import runner as rn

    class C:
        def __init__(self, text, finish):
            self.text, self.finish = text, finish
            self.model = type("M", (), {"key": "gemini:gemini-3.5-flash"})()

    class R:
        has_model = staticmethod(lambda role, mode: True)
        calls = []

        async def _short(self, io, role, messages, temperature, max_tokens=700):
            R.calls.append(max_tokens)
            return R.answer

        async def event(self, *a, **k):
            pass
    d = make()
    job = type("J", (), {"mode": "auto"})()
    R.answer = C("Voici l'explication :\n\n* `theorem x` : C'est le mot-clé, suivi du nom qui lui a", "length")
    asyncio.run(rn.DossierPipeline._notes(R(), job, d, None, ""))
    assert d.notes == "" and R.calls[-1] >= 4000
    R.answer = C("Voici l'explication complète.", "stop")
    asyncio.run(rn.DossierPipeline._notes(R(), job, d, None, ""))
    assert d.notes == "Voici l'explication complète."


# ---------------------------------------------------------------- real PDF
@needs_tex
def test_real_pdf_has_mathlib_one_theorem_and_a_clean_annex(tmp_path):
    ex = asyncio.run(export.export_dossier(make(), "pdf", lang="fr", tmp_root=tmp_path,
                                           ws_info={"mathlib": "2f65ba7f1a91 (checkout)", "lean": "v4.9.0-rc1"}))
    assert ex.content_type == "application/pdf", ex.log[-2000:]
    p = tmp_path / "out.pdf"
    p.write_bytes(ex.data)
    text = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
    assert "2f65ba7f1a91" in text
    assert text.count("Théorème") == 1                                     # the statement box title only
    annex = text.split("Annexe", 1)[1]
    assert "Idée de la preuve" in annex and "Énoncé du théorème" not in annex
    assert "1." not in annex.split("Commentaires", 1)[0]
