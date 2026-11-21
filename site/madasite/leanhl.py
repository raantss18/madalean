"""Build-time Lean 4 syntax highlighting -> HTML spans (no client script). Classes: hl-kw, hl-tac, hl-com, hl-str,
hl-num, hl-ty, hl-sym, hl-sorry, hl-attr. Lines are wrapped in <span class="ln"> so CSS can number them."""
from __future__ import annotations

import html
import re

KEYWORDS = set("""theorem lemma def example abbrev instance structure class inductive where extends deriving
namespace section end open variable universe import noncomputable private protected partial unsafe mutual
fun λ let in have show from by at with match if then else do return calc suffices obtain using termination_by
decreasing_by axiom opaque set_option attribute local scoped macro syntax notation infix infixl infixr prefix
postfix elab""".split())
TACTICS = set("""intro intros exact apply refine constructor use obtain rcases cases induction rw rewrite simp
simp_all norm_num ring ring_nf linarith nlinarith positivity omega decide field_simp gcongr unfold ext funext congr
exfalso by_contra by_cases push_neg contradiction specialize left right exists trivial rfl assumption aesop tauto
interval_cases norm_cast push_cast exact_mod_cast split_ifs nth_rewrite nth_rw symm trans subst rintro refine'
apply_fun conv first try repeat all_goals any_goals focus done skip exact? apply? polyrith bound zify qify lift
change show_term choose filter_upwards""".split())
TYPES = set("ℕ ℤ ℚ ℝ ℂ Prop Type Sort Nat Int Rat Real Complex Bool True False Finset Set List Fin".split())

TOKEN = re.compile(r"""
 (?P<com>--[^\n]*|/-(?:[^-]|-(?!/))*-/)
|(?P<str>"(?:\\.|[^"\\])*")
|(?P<attr>@\[[^\]]*\])
|(?P<num>\b\d+(?:\.\d+)?\b)
|(?P<id>[A-Za-z_À-ɏͰ-Ͽἀ-῿][\w'!?.À-ɏͰ-Ͽ₀-ₜ₀-₉]*|[ℕℤℚℝℂ])
|(?P<sym>:=|->|<-|=>|[∀∃→←↔∧∨¬≤≥≠∣∑∏⟨⟩⊢∘•·×∈∉⊆∩∪⁻¹√π∞λ↑]|<;>)
""", re.X)


def highlight(code: str) -> str:
    out: list[str] = []
    pos = 0
    for m in TOKEN.finditer(code):
        if m.start() > pos:
            out.append(html.escape(code[pos:m.start()]))
        kind = m.lastgroup
        tok = m.group(0)
        cls = None
        if kind == "com":
            cls = "hl-com"
        elif kind == "str":
            cls = "hl-str"
        elif kind == "attr":
            cls = "hl-attr"
        elif kind == "num":
            cls = "hl-num"
        elif kind == "sym":
            cls = "hl-sym"
        elif kind == "id":
            if tok in ("sorry", "admit"):
                cls = "hl-sorry"
            elif tok in KEYWORDS:
                cls = "hl-kw"
            elif tok in TACTICS:
                cls = "hl-tac"
            elif tok in TYPES:
                cls = "hl-ty"
        esc = html.escape(tok)
        if cls:
            # a multi-line comment must not swallow the line wrappers: close/reopen per line
            esc = esc.replace("\n", f"</span>\n<span class=\"{cls}\">")
            out.append(f'<span class="{cls}">{esc}</span>')
        else:
            out.append(esc)
        pos = m.end()
    out.append(html.escape(code[pos:]))
    body = "".join(out)
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return "".join(f'<span class="ln">{ln}</span>\n' for ln in lines)


def code_block(lang: str, code: str, numbered: bool = False, label: str = "") -> str:
    lang = (lang or "").lower()
    cls = "code" + (" numbered" if numbered else "")
    aria = f' aria-label="{html.escape(label)}"' if label else ""
    if lang == "lean" or lang == "lean4":
        return f'<pre class="{cls} lean" tabindex="0"{aria}><code>{highlight(code)}</code></pre>'
    tag = f' data-lang="{html.escape(lang)}"' if lang else ""
    return f'<pre class="{cls}"{tag} tabindex="0"{aria}><code>{html.escape(code)}</code></pre>'
