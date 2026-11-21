"""Article LaTeX project (S-R, docs/ARTICLE.md): one representation (files), v1 view round trip on real-world
snippets, migration with stable ids, managed regions, suggestions on stable ids (accept/reject/stale), security guard,
package analysis against the bundle, truth rule, real PDFs (system XeLaTeX in a dev checkout; the prefix's tectonic
from a temporary prefix), SyncTeX, Overleaf zip round trip, assistant suggestions through the HTTP API."""
from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import socket
import subprocess
import zipfile
from pathlib import Path

import pytest

from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import article as am
from madalean.research import overleaf, texbuild as tb, texproject as tp
from helpers import make_ctx, running, session, wait_idle

# Real-world snippets: theorem environments, align, TikZ, user macros, comments, verbatim-like text, nested braces.
CORPUS = [
    r"""\begin{theorem}[Cauchy--Schwarz]\label{thm:cs}
For all $u,v$ in an inner product space, $|\langle u,v\rangle| \le \|u\|\,\|v\|$.
\end{theorem}
\begin{proof}
Expand $\|u - tv\|^2 \ge 0$ % a comment with $ and { unbalanced
and take $t = \langle u, v\rangle / \|v\|^2$.
\end{proof}""",
    r"""\begin{align}
  f(x) &= \sum_{n\ge 0} a_n x^n \label{eq:f}\\
       &\le \frac{1}{1-x}, \qquad |x|<1. \nonumber
\end{align}""",
    r"""\begin{figure}[ht]
\centering
\begin{tikzpicture}[scale=1.2]
  \draw[->] (0,0) -- (2,0) node[right] {$x$};
  \foreach \i in {0,...,3} { \fill (\i/2, \i*\i/8) circle (1pt); }
\end{tikzpicture}
\caption{Points on a parabola.}\label{fig:p}
\end{figure}""",
    r"""\newcommand{\abs}[1]{\left|#1\right|}
Let $\abs{x} < \varepsilon$ and $\R^n \ni x$; see \cref{thm:cs} and \cite[Thm.~2.1]{knuth}.""",
    r"""\begin{enumerate}[label=(\roman*)]
  \item First, $\int_0^1 x\,dx = \tfrac12$.\footnote{Elementary.}
  \item Second: \verb|a_b| and 100\% sure.
\end{enumerate}""",
    "Texte en français : « guillemets », œuvre, ∀x ∈ ℕ, $x^{2}$.\n\n\\paragraph{Remarque.} Fin.",
]


def setup_project(ctx, pid: str) -> None:
    tp.ensure(ctx, pid)


async def _project(s, local, title="Parité") -> str:
    async with s.post(local + "/api/projects", json={"title": title}) as r:
        return (await r.json())["project"]["id"]


# ================================================================ model, view, round trip
async def test_view_round_trip_on_corpus_is_byte_identical(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local)
            async with s.get(local + f"/api/research/projects/{pid}/texproject") as r:
                st = await r.json()
                assert r.status == 200 and st["created"] is True
    paths = st["order"]
    assert paths == ["sections/01-introduction.tex"]
    # write the corpus by hand (source mode) into the section, between markers and outside them
    sec = tp.read_files(ctx, pid)[paths[0]]
    body = sec + "\n" + "\n\n".join(CORPUS) + "\n%% mdl:block b-0000abcd prose\nUn paragraphe {avec {accolades}}.\n"
    tp.write_file(ctx, pid, paths[0], body)
    before = tp.read_files(ctx, pid)
    view = am.load(ctx, pid)
    assert view["format"] == "latex" and view["blocks"][-1]["id"] == "b-0000abcd"
    am.save(ctx, pid, view)                                   # nothing changed → byte for byte
    assert tp.read_files(ctx, pid) == before
    # changing one block leaves every other byte alone
    view = am.load(ctx, pid)
    view["blocks"][-1]["text"] = "Nouveau texte $x$."
    am.save(ctx, pid, view)
    after = tp.read_files(ctx, pid)[paths[0]]
    assert after.startswith(before[paths[0]].split("%% mdl:block b-0000abcd")[0])
    assert all(c in after for c in CORPUS) and "Nouveau texte $x$." in after
    # Markdown from an older writer is converted (citations of known keys only, maths through the allow-list)
    view = am.load(ctx, pid)
    view["blocks"][-1]["text"] = "**Gras** et [@nokey] puis $\\frac{1}{2}$"
    am.save(ctx, pid, view)
    b = am.load(ctx, pid)["blocks"][-1]
    assert "\\textbf{Gras}" in b["text"] and "@nokey" not in b["text"] and "\\frac{1}{2}" in b["text"]
    assert "**Gras**" in b["md"]


def test_parse_markers_and_unmarked_text():
    text = "Intro sans marqueur\n%% mdl:block b-12345678 prose\nA\n%% mdl:end\nhors bloc\n" \
           "%% mdl:block b-87654321 dossier dossier=d-1\n\\begin{theorem}x\\end{theorem}"
    regs = tp.parse_file("sections/01-a.tex", text)
    assert [(r["id"], r["kind"], r["dossier_id"]) for r in regs] == [
        (regs[0]["id"], "prose", ""), ("b-12345678", "prose", ""), ("b-87654321", "dossier", "d-1")]
    assert regs[0]["marked"] is False and regs[0]["id"].startswith("b-")
    assert regs[1]["body"] == "A" and regs[2]["body"].startswith("\\begin{theorem}")
    assert tp.parse_file("sections/01-a.tex", text)[0]["id"] == regs[0]["id"]      # deterministic id


async def test_migration_from_v1_keeps_block_ids_and_marks_dossiers(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local)
            async with s.post(local + "/api/dossiers", json={"problem": "La somme de deux pairs est paire.",
                                                             "project_id": pid}) as r:
                did = (await r.json())["dossier"]["id"]
            await wait_idle(ctx)
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:      # v1 JSON
                v1 = (await r.json())["article"]
            async with s.patch(local + f"/api/research/projects/{pid}/article/blocks/{v1['blocks'][0]['id']}",
                               json={"text": "Mon *introduction* en Markdown."}) as r:
                assert r.status == 200
            assert (ctx.projects.store.dir(pid) / "article.json").exists()
            async with s.get(local + f"/api/research/projects/{pid}/texproject") as r:
                st = await r.json()
            assert (ctx.projects.store.dir(pid) / "article.v1.json").exists()
            assert not (ctx.projects.store.dir(pid) / "article.json").exists()
            sec = next(f["text"] for f in st["files"] if f["path"].startswith("sections/"))
            assert f"%% mdl:block {v1['blocks'][0]['id']} intro" in sec and "\\emph{introduction}" in sec
            assert f"dossier={did}" in sec and "\\begin{theorem}" in sec and "\\begin{proof}" in sec
            # the v1 routes keep working on the files (view)
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                view = (await r.json())["article"]
            assert [b["id"] for b in view["blocks"]] == [b["id"] for b in v1["blocks"]]
            assert view["blocks"][0]["source"] == "user" and view["blocks"][1]["dossier_id"] == did
            async with s.post(local + f"/api/research/projects/{pid}/article/blocks",
                              json={"kind": "section", "title": "Questions ouvertes",
                                    "after": view["blocks"][1]["id"]}) as r:
                sec_b = (await r.json())["block"]
            files = tp.read_files(ctx, pid)
            assert any(f"%% mdl:block {sec_b['id']} section" in t for t in files.values())
            assert len(tp.section_paths(files["main.tex"])) == 2
            async with s.delete(local + f"/api/research/projects/{pid}/article/blocks/{sec_b['id']}") as r:
                undo = (await r.json())["undo"]
            assert len(tp.section_paths(tp.read_files(ctx, pid)["main.tex"])) == 1
            async with s.post(local + undo) as r:
                assert sec_b["id"] in [b["id"] for b in (await r.json())["article"]["blocks"]]
            async with s.patch(local + f"/api/research/projects/{pid}/article",
                               json={"title": "Sommes paires", "authors": [{"name": "A. Auteur"}],
                                     "options": {"lang": "en"}}) as r:
                assert r.status == 200
            main = tp.read_files(ctx, pid)["main.tex"]
            assert "\\title{Sommes paires}" in main and "\\author{A. Auteur}" in main and "[english]{babel}" in main


# ================================================================ settings and managed regions
async def test_settings_regenerate_managed_regions_only(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local)
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                main = next(f for f in (await r.json())["files"] if f["path"] == "main.tex")
            mine = main["text"].replace("% Vos propres lignes", "\\newcommand{\\eps}{\\varepsilon}\n% Vos propres lignes")
            async with s.post(base + "/file", json={"path": "main.tex", "text": mine, "base": main["hash"]}) as r:
                h = (await r.json())["hash"]
            async with s.post(base + "/file", json={"path": "main.tex", "text": mine + "x", "base": "0" * 16}) as r:
                assert r.status == 409 and (await r.json())["current"]["hash"] == h
            async with s.patch(base + "/settings", json={"packages": {"extra": ["tikz"]},
                                                         "macros": {"eps": "\\varepsilon", "R": "\\mathbb{R}"},
                                                         "layout": {"font": "libertinus"}}) as r:
                assert r.status == 200, await r.text()
            main2 = tp.read_files(ctx, pid)["main.tex"]
            assert "\\usepackage{tikz}" in main2 and "\\newcommand{\\eps}{\\varepsilon}" in main2
            assert "Libertinus" in main2 and "\\providecommand{\\N}" not in main2
            for bad in ({"macros": {"x": "\\input{/etc/passwd}"}}, {"macros": {"y": "^^5cinput"}},
                        {"packages": {"extra": ["a b"]}}, {"document": {"class": "../x"}}, {"nope": 1}):
                async with s.patch(base + "/settings", json=bad) as r:
                    assert r.status == 400, bad
            async with s.post(base + "/template", json={"template": "beamer"}) as r:
                assert r.status == 200
            main3 = tp.read_files(ctx, pid)["main.tex"]
            assert "{beamer}" in main3 and "\\titlepage" in main3 and "\\newcommand{\\eps}" in main3
            assert "\\newtheorem{theorem}" not in main3                     # beamer defines it already
            assert "%% mdl:block abstract abstract" in main3 and "\\input{sections/01-introduction}" in main3


# ================================================================ suggestions
async def test_suggestions_accept_reject_stale_on_stable_ids(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local)
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                st = await r.json()
            path = st["order"][0]
            bid = tp.parse_file(path, tp.read_files(ctx, pid)[path])[0]["id"]
            text = tp.read_files(ctx, pid)[path] + "Le résultat est clair. Il est clair.\n"
            tp.write_file(ctx, pid, path, text)
            # S-Q's Python API
            s1 = tp.add_suggestion(ctx, pid, block_id=bid, find="clair", occurrence=1, replace="évident",
                                   kind="research", origin="research", rationale="style")
            assert s1["anchor"]["path"] == path and text[s1["anchor"]["from"]:s1["anchor"]["to"]] == "clair"
            with pytest.raises(tp.TexProjectError) as e:
                tp.add_suggestion(ctx, pid, block_id=bid, find="clair", replace="\\input{/etc/passwd}")
            assert e.value.kind == "unsafe_tex"
            with pytest.raises(tp.TexProjectError):
                tp.add_suggestion(ctx, pid, block_id=bid, find="clair", replace="^^5cinput x")
            async with s.post(base + "/suggestions", json={"block_id": bid, "find": "Le résultat",
                                                           "replace": "Ce résultat [@nokey]", "kind": "rewrite"}) as r:
                s2 = (await r.json())["suggestion"]
            assert "@nokey" not in s2["replace"]                          # invented citation removed
            async with s.post(base + "/suggestions", json={"block_id": bid, "find": "absent", "replace": "x"}) as r:
                assert r.status == 409
            async with s.post(base + f"/suggestions/{s1['id']}/accept", json={}) as r:
                assert r.status == 200
            new = tp.read_files(ctx, pid)[path]
            assert "Il est évident." in new and "Le résultat est clair." in new
            async with s.post(base + f"/suggestions/{s1['id']}/accept", json={}) as r:
                assert r.status == 409 and (await r.json())["error"] == "decided"
            async with s.post(base + f"/suggestions/{s2['id']}/reject", json={}) as r:
                assert (await r.json())["suggestion"]["state"] == "rejected"
            s3 = tp.add_suggestion(ctx, pid, block_id=bid, find="Le résultat est", replace="Ce fait est")
            tp.write_file(ctx, pid, path, new.replace("Le résultat est", "Le fait est"))      # edited meanwhile
            assert tp.list_suggestions(ctx, pid, "stale")[0]["id"] == s3["id"]
            # editor-applied acceptance: the server only records the decision
            s4 = tp.add_suggestion(ctx, pid, block_id=bid, find="évident", replace="trivial")
            async with s.post(base + f"/suggestions/{s4['id']}/accept", json={"applied": True}) as r:
                assert (await r.json())["files"] == []
            # blocks moved to another file keep their suggestions (anchors follow the block id)
            s5 = tp.add_suggestion(ctx, pid, block_id=bid, find="Le fait", replace="Ce fait")
            view = am.load(ctx, pid)
            am.save(ctx, pid, view)
            assert tp.list_suggestions(ctx, pid, "pending")[-1]["id"] == s5["id"]


# ================================================================ security
def test_guard_refuses_file_shell_and_rebuild_tricks():
    bad = [r"\input{/etc/passwd}", r"\include{../../x}", r"\immediate\write18{rm -rf}", r"\openout1=x",
           "^^5cinput{/etc/hostname}", r"\csname input\endcsname", r"\catcode`\~=0", r"\directlua{os.exit()}",
           r"\includegraphics{/home/x.png}", r"\input /etc/passwd", r"\read16 to \x", r"\scantokens{x}"]
    for b in bad:
        assert tb.guard("ok\n" + b), b
    assert tb.guard("% \\input{/etc/passwd} in a comment\n100\\% ok") == []
    assert tb.guard("\n".join(CORPUS)) == []
    assert tb.guard(r"\input{sections/01-a}") == []
    assert tb.guard_ai(r"\def\x{1}") and tb.guard_ai(r"\usepackage{x}") and not tb.guard_ai(r"$\frac{a}{b}$")


async def test_compile_refuses_unsafe_source_and_shell_packages(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local)
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                path = (await r.json())["order"][0]
            tp.write_file(ctx, pid, path, tp.read_files(ctx, pid)[path] + "\\input{/etc/hostname}\n")
            async with s.post(base + "/compile", json={}) as r:
                res = await r.json()
            assert res["ok"] is False and res["diagnostics"][0]["path"] == path
            assert "sécurité" in res["diagnostics"][0]["plain"]["text"]
            assert not (tb.build_dir(ctx, pid) / "work").exists()                    # never reached TeX


def test_package_analysis_needed_redundant_refused():
    files = {"main.tex": "\\documentclass{amsart}\n\\usepackage{amsmath}\n\\usepackage{mathtools,mathtools}\n"
                         "\\usepackage{cleveref}\n\\usepackage{hyperref}\n\\usepackage{minted}\n\\ifTUTeX\n\\else\n"
                         "\\usepackage{lmodern}\n\\fi\n\\begin{document}\\input{sections/a}\\end{document}",
             "sections/a.tex": "\\begin{tikzpicture}\\end{tikzpicture} \\SI{3}{m} \\includegraphics{x}"}
    a = tb.analyse(files)
    assert a["class"] == "amsart"
    red = {(r["name"], r["reason"].split(":")[0]) for r in a["redundant"]}
    assert ("amsmath", "class") in red and ("mathtools", "twice") in red and ("cleveref", "order") in red
    assert {n["name"] for n in a["needed"]} >= {"tikz", "siunitx", "graphicx"}
    assert a["refused"][0]["name"] == "minted"
    assert "lmodern" not in {p["name"] for p in a["packages"]}                # pdfTeX branch ignored


def test_log_diagnostics_font_and_missing_file():
    log = ("(./sections/01-a.tex\n! Font TU/lmr/bx/n/9=[lmroman9-bold]:mapping=tex-text; at 9.0pt not loadable: M\n"
           "etric (TFM) file or installed font not found.\n<to be read again> \n                   relax \n"
           "l.75 ...note \\cite{x}\n")
    b = {"engine": "tectonic", "index": frozenset({"lmroman9-bold.otf"}), "cached_dir": Path("/nonexistent"), "digest": ""}
    d = tb.parse_log("error: main.tex:75: Font ... not loadable\n", log, {"main.tex": ""}, tp.default_settings(), b)
    assert d[0]["fix"] == {"kind": "fetch", "files": ["lmroman9-bold.otf"]} and d[0]["line"] == 75
    log2 = "! LaTeX Error: File `nosuch.sty' not found.\n\nl.3 \\usepackage{nosuch}\n"
    d = tb.parse_log("", log2, {"main.tex": ""}, tp.default_settings(), b)
    assert d[0]["fix"]["kind"] == "remove_package" and d[0]["fix"]["name"] == "nosuch"


# ================================================================ truth rule
def test_truth_rule_in_build_copy_only():
    src = ("%% mdl:block b-11111111 dossier dossier=d-ok\n\\begin{theorem}[A]\\label{a}\nx\n\\end{theorem}\n"
           "%% mdl:block b-22222222 dossier dossier=d-no\n\\begin{lemma}\ny\n\\end{lemma}\n"
           "%% mdl:block b-33333333 prose\n\\begin{proposition}\n% mdl:lean d-no\nz\n\\end{proposition}\n"
           "\\begin{theorem}free\\end{theorem}\n")
    out = tb.truth_transform(src, {"d-ok": {"status": "verified"}, "d-no": {"status": "unverified"}})
    assert "\\begin{theorem}[A]" in out and "\\begin{lemma}" not in out and "\\begin{proposition}" not in out
    assert out.count("\\begin{claim}") == 2 and out.count("\\MLunverified") == 2 and out.count("\\end{claim}") == 2
    assert "\\begin{theorem}free" in out


# ================================================================ real PDFs
def _pdf_text(pdf: Path) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True,
                                                        text=True).stdout)


@pytest.mark.skipif(not (shutil.which("xelatex") and shutil.which("latexmk")), reason="no system XeLaTeX (dev)")
async def test_compile_real_pdf_dev_engine_diagnostics_and_synctex(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local, "Compilation réelle")
            async with s.post(local + "/api/dossiers", json={"problem": "Tout carré impair est congru à 1 modulo 8.",
                                                             "project_id": pid, "start": False}) as r:
                did = (await r.json())["dossier"]["id"]
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                st = await r.json()
            path = st["order"][0]
            text = tp.read_files(ctx, pid)[path]
            assert f"dossier={did}" in text
            tp.write_file(ctx, pid, path, text + "\n" + "\n\n".join(c for c in CORPUS if "tikz" not in c
                                                                     and "enumerate" not in c) + "\n")
            async with s.post(base + "/compile", json={}) as r:
                res = await r.json()
            assert res["ok"], res["diagnostics"]
            assert res["engine"] == "xelatex"
            pdf = tb.pdf_path(ctx, pid)
            txt = _pdf_text(pdf)
            assert "COMPILATION RÉELLE" in txt.upper() and "non vérifié par Lean" in txt      # truth rule
            assert "Affirmation" in txt and "Cauchy" in txt and "∀x ∈" in txt and "théorème 1.2" in txt, txt
            assert "\\begin{theorem}" in tp.read_files(ctx, pid)[path]                     # source untouched
            assert any(d["message"].startswith("Citation") or "knuth" in d["message"] for d in res["diagnostics"])
            async with s.get(base + "/pdf") as r:
                assert r.headers["Content-Type"] == "application/pdf" and (await r.read()).startswith(b"%PDF")
            # second compile of the same inputs reuses the PDF
            async with s.post(base + "/compile", json={}) as r:
                assert (await r.json())["cached"] is True
            # SyncTeX both ways
            line = next(i + 1 for i, ln in enumerate(tp.read_files(ctx, pid)[path].split("\n")) if "Expand" in ln)
            async with s.get(base + f"/synctex?path={path}&line={line}") as r:
                fw = (await r.json())["result"]
            assert fw and fw["page"] >= 1 and 50 < fw["x"] < 550 and 50 < fw["y"] < 800
            async with s.get(base + f"/synctex?page={fw['page']}&x={fw['x'] + 5}&y={fw['y'] + fw['h'] - 2}") as r:
                inv = (await r.json())["result"]
            assert inv["path"] == path and abs(inv["line"] - line) <= 2
            # an error with a one-click fix
            tp.write_file(ctx, pid, path, tp.read_files(ctx, pid)[path] + "\nVoir \\cref{thm:cs} et \\textcolr{red}{x}.\n")
            async with s.post(base + "/compile", json={}) as r:
                res = await r.json()
            assert not res["ok"]
            err = next(d for d in res["diagnostics"] if d["severity"] == "error")
            assert err["path"] == path and err["line"] > 1 and err["fix"]["kind"] == "replace"
            assert err["fix"]["replace"] == "\\textcolor"


def _temp_prefix(tmp: Path) -> Path | None:
    """A temporary MADALEAN_HOME: the live prefix's env linked read-only, a COPY of its tectonic cache (writes go
    to the copy), a fontconfig file with a private cache dir. None when there is no installed prefix."""
    live = Path.home() / ".local" / "share" / "madalean"
    if not (live / "env" / "bin" / "tectonic").exists() or not (live / "tectonic" / "files").is_dir():
        return None
    home = tmp / "prefix"
    home.mkdir()
    (home / "env").symlink_to((live / "env").resolve())
    shutil.copytree(live / "tectonic", home / "tectonic", symlinks=True)
    (home / "fontconfig").mkdir()
    conf = (live / "fontconfig" / "fonts.conf").read_text() if (live / "fontconfig" / "fonts.conf").exists() else \
        "<fontconfig></fontconfig>"
    conf = __import__("re").sub(r"<cachedir>.*?</cachedir>", f"<cachedir>{home}/cache/fontconfig</cachedir>", conf)
    (home / "fontconfig" / "fonts.conf").write_text(conf)
    return home


def _online() -> bool:
    try:
        socket.create_connection(("relay.fullyjustified.net", 443), timeout=3).close()
        return True
    except OSError:
        return False


async def test_tectonic_from_temp_prefix(tmp_path, monkeypatch):
    home = _temp_prefix(tmp_path)
    if home is None:
        pytest.skip("no installed prefix with tectonic")
    monkeypatch.setenv("MADALEAN_HOME", str(home))
    from madalean import deps
    assert deps.installed() and tb.engine_cmd()[1] == "tectonic"
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local, "Tectonic")
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                assert r.status == 200
            async with s.get(base + "/packages") as r:
                a = await r.json()
            assert a["engine"] == "tectonic" and a["digest"]
            states = {p["name"]: p["state"] for p in a["packages"]}
            assert states["hyperref"] == "cached" and all(v in ("cached", "bundle") for v in states.values())
            lock = json.loads((tp.root(ctx, pid) / "madalean.lock").read_text())
            assert lock["engine"] == "tectonic" and lock["files"]["hyperref.sty"] == "cached"
            async with s.post(base + "/compile", json={}) as r:
                res = await r.json()
            if not res["ok"]:
                fetch = [d for d in res["diagnostics"] if (d.get("fix") or {}).get("kind") == "fetch"]
                assert fetch, res["diagnostics"]                    # missing files are offered, never a 2nd TeX
                if os.environ.get("MADALEAN_ONLINE_TESTS") != "1" or not _online():
                    pytest.skip("files to fetch from the pinned bundle; online part disabled")
                ctx.settings.mode = "auto"
                async with s.post(base + "/compile", json={"fetch": True}) as r:
                    res = await r.json()
                assert res["ok"], res["diagnostics"]
                async with s.post(base + "/compile", json={"force": True}) as r:      # now offline (cache only)
                    res = await r.json()
            assert res["ok"] and res["engine"] == "tectonic", res["diagnostics"]
            txt = _pdf_text(tb.pdf_path(ctx, pid))
            assert "TECTONIC" in txt.upper() and "Introduction" in txt
            async with s.get(base + "/synctex?path=sections/01-introduction.tex&line=2") as r:
                assert (await r.json())["result"]["page"] == 1
    assert not (Path.home() / ".local" / "share" / "madalean" / "tectonic" / "bundles" / "x").exists()


# ================================================================ Overleaf and history
async def test_overleaf_zip_round_trip_and_history(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, _r):
        async with session() as s:
            pid = await _project(s, local, "Overleaf")
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                path = (await r.json())["order"][0]
            tp.add_figure(ctx, pid, b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            async with s.get(base + "/export?format=overleaf") as r:
                assert r.status == 200
                data = await r.read()
            z = zipfile.ZipFile(io.BytesIO(data))
            names = set(z.namelist())
            assert {"main.tex", path, "latexmkrc", "madalean-generated.tex", "madalean.toml"} <= names
            assert any(n.startswith("figures/") for n in names)
            # « edited in Overleaf »: a paragraph added, a third-party .sty, an unsafe file
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z2:
                for n in names:
                    content = z.read(n)
                    if n == path:
                        content += b"\nAjout depuis Overleaf.\n"
                    z2.writestr(n, content)
                z2.writestr("mystyle.sty", b"\\def\\x{1}")
            fd = __import__("aiohttp").FormData()
            fd.add_field("file", buf.getvalue(), filename="overleaf.zip", content_type="application/zip")
            async with s.post(base + "/import", data=fd) as r:
                res = await r.json()
                assert r.status == 200, res
            assert res["changed"] == [path] and res["skipped"][0]["why"] == "third_party_tex"
            assert "Ajout depuis Overleaf." in tp.read_files(ctx, pid)[path]
            bad = io.BytesIO()
            with zipfile.ZipFile(bad, "w") as z3:
                z3.writestr("main.tex", "\\documentclass{article}\\begin{document}\\input{/etc/passwd}\\end{document}")
            fd = __import__("aiohttp").FormData()
            fd.add_field("file", bad.getvalue(), filename="x.zip", content_type="application/zip")
            async with s.post(base + "/import", data=fd) as r:
                assert r.status == 422 and (await r.json())["error"] == "unsafe_tex"
            # history: the import left a snapshot to go back to
            async with s.get(base + "/versions") as r:
                vs = (await r.json())["versions"]
            before = next(v for v in vs if v["label"] == "before-overleaf-import")
            async with s.post(base + f"/versions/{before['id']}/restore") as r:
                assert path in (await r.json())["changed"]
            assert "Ajout depuis Overleaf." not in tp.read_files(ctx, pid)[path]
            objs = list((tp.root(ctx, pid) / ".madalean" / "history" / "objects").iterdir())
            assert len(objs) == len({o.name for o in objs})                 # content-addressed


def test_overleaf_detect_is_read_only_and_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(overleaf.shutil, "which", lambda n: None)
    monkeypatch.setattr(overleaf.urllib.request, "urlopen", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(OSError()))
    r = overleaf.detect(force=True)
    assert r["found"] is False and r["url"] == "http://127.0.0.1" and len(calls) == 1
    overleaf.detect()
    assert len(calls) == 1


# ================================================================ assistant: suggestions, never silent edits
def assist_responder(role, messages, brain):
    c = messages[0]["content"]
    if "Shorten" in c:
        return "Court."
    if "Rewrite the passage" in c:
        return "\\input{/etc/passwd} injected"
    if "SageMath" in c:
        return "```sage\nprint(factor(2^10-1))\n```"
    return demo_responder(role, messages, brain)


async def test_assistant_makes_suggestions_only(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(assist_responder))
    async with running(ctx) as (_srv, local, _r):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            pid = await _project(s, local, "Assistant")
            base = local + f"/api/research/projects/{pid}/texproject"
            async with s.get(base) as r:
                path = (await r.json())["order"][0]
            text = tp.read_files(ctx, pid)[path] + "Une phrase beaucoup trop longue à raccourcir.\n"
            tp.write_file(ctx, pid, path, text)
            sel = "Une phrase beaucoup trop longue à raccourcir."

            async def run(action):
                async with s.post(base + "/assist", json={"action": action, "path": path, "text": sel,
                                                          "from": text.find(sel)}) as r:
                    rid = (await r.json())["request_id"]
                while True:
                    ev = json.loads((await asyncio.wait_for(ws.receive(), 30)).data)
                    if ev["type"] in ("article.assist.done", "article.assist.error") and ev.get("request_id") == rid:
                        return ev
            ev = await run("shorten")
            assert ev["type"] == "article.assist.done" and ev["suggestion"]["replace"] == "Court."
            assert tp.read_files(ctx, pid)[path] == text                          # nothing written
            ev = await run("rewrite")
            assert ev["type"] == "article.assist.error" and ev["error"] == "unsafe_tex"
            ev = await run("sage")
            assert ev["type"] == "article.assist.done" and ev["cell"]["id"]
            from madalean.server.plugins.workbench import WB
            cell = _srv.app[WB].calc.load(pid)["cells"][-1]
            assert cell["origin"] == "assistant" and cell["approved"] is None      # runs only once approved
            # « Vérifier avec Lean »: a dossier + a link right after the statement's environment line
            thm = "\\begin{theorem}\\label{t}\nTout entier pair au carré est pair.\n\\end{theorem}\n"
            tp.write_file(ctx, pid, path, tp.read_files(ctx, pid)[path] + thm)
            async with s.post(base + "/lean", json={"path": path, "text": "Tout entier pair au carré est pair."}) as r:
                res = await r.json()
                assert r.status == 201 and res["linked"]
            assert f"\\begin{{theorem}}\\label{{t}}\n% mdl:lean {res['dossier']['id']}" in tp.read_files(ctx, pid)[path]
            assert ctx.repo.get(res["dossier"]["id"]).project_id == pid


async def test_remote_listener_needs_token(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, remote):
        async with session() as s:
            pid = await _project(s, local)
            for method, p in (("GET", ""), ("POST", "/compile"), ("GET", "/pdf"), ("POST", "/file"),
                              ("GET", "/export?format=overleaf"), ("POST", "/import")):
                async with s.request(method, remote + f"/api/research/projects/{pid}/texproject{p}") as r:
                    assert r.status == 401, p
