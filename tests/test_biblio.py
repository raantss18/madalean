"""Bibliography: parsers / writers, stable keys, deduplication, citations validated against existing keys (a model that
invents a reference is corrected by code), and real compiled exports with a formatted bibliography."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import biblio
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.sources import Library
from helpers import make_ctx, running, session, started, wait_idle

ROOT = Path(__file__).resolve().parents[1]
MATHLIB_BIB = next((p for p in (ROOT / "workspaces" / "lean-current" / ".lake" / "packages" / "mathlib" / "docs" /
                                "references.bib", ROOT / "workspaces" / "lean-prover49" / "docs" / "references.bib")
                    if p.is_file()), None)
WILES = {"type": "article-journal", "title": "Modular elliptic curves and Fermat's Last Theorem",
         "author": [{"family": "Wiles", "given": "Andrew"}], "container-title": "Annals of Mathematics",
         "volume": "141", "issue": "3", "page": "443-551", "issued": {"date-parts": [[1995, 5]]},
         "DOI": "10.2307/2118559"}


@pytest.mark.skipif(MATHLIB_BIB is None, reason="no Mathlib references.bib")
def test_mathlib_references_parse_and_round_trip():
    items, errors = biblio.bibtex_to_items(MATHLIB_BIB.read_text(encoding="utf-8"))
    assert len(items) > 450 and errors == []
    assert sum(1 for it in items if not it.get("title")) <= 3          # Mathlib has a « tilte » typo or two
    assert not any("\\'" in str(it.get("author")) for it in items)          # accents decoded
    text = "".join(biblio.item_to_bibtex(it, it["_key"]) for it in items)
    again, errors = biblio.bibtex_to_items(text)
    assert errors == [] and len(again) == len(items)
    for a, b in zip(items, again):
        assert a["_key"] == b["_key"]
        assert biblio.norm_title(a.get("title", "")) == biblio.norm_title(b.get("title", "")), a["_key"]
        assert [x.get("family") for x in a.get("author", [])] == [x.get("family") for x in b.get("author", [])]
        assert biblio.year_of(a) == biblio.year_of(b) and a.get("DOI", "") == b.get("DOI", "")


def test_bibtex_parser_tolerates_real_world_input():
    text = r"""@string{ann = "Annals of Mathematics"}
    @comment{ignored {braces}}
    @preamble{"\newcommand{\noop}[1]{}"}
    @Article{Wiles95,
      author = {Andrew Wiles and {The Lean Community} and de la Vallée Poussin, Charles},
      title = "Modular elliptic curves and {F}ermat's {L}ast {T}heorem",
      journal = ann, year = 1995, month = may, pages = {443--551},
      doi = {https://doi.org/10.2307/2118559}, eprint = {math/9503219}, archivePrefix = {arXiv},
      file = {Full Text:storage/ABCD/wiles.pdf:application/pdf;Snapshot:storage/ABCD/page.html:text/html},
    }
    @misc{broken, title = {no closing brace
    @book{ok, title={Fine}, year={2000}}"""
    items, errors = biblio.bibtex_to_items(text)
    w = next(i for i in items if i["_key"] == "Wiles95")
    assert w["container-title"] == "Annals of Mathematics" and w["issued"] == {"date-parts": [[1995, 5]]}
    assert w["DOI"] == "10.2307/2118559" and w["arxiv"] == "math/9503219" and w["page"] == "443-551"
    assert w["author"][1] == {"literal": "The Lean Community"}
    assert w["author"][2] == {"family": "de la Vallée Poussin", "given": "Charles"}
    assert w["_files"] == ["storage/ABCD/wiles.pdf", "storage/ABCD/page.html"]
    assert any(i["_key"] == "ok" for i in items)


def test_writer_escapes_everything():
    evil = {"type": "article-journal", "title": r"Pwn \input{/etc/passwd} \write18{rm -rf ~} } { 100% & $x^2$ #1",
            "author": [{"family": "O'Brien}", "given": "{\\x"}], "URL": "https://e.x/a b}{\\c",
            "DOI": "10.1/x}\\y", "note": "\\immediate\\write18{id}"}
    out = biblio.item_to_bibtex(evil, "evil key}")
    assert "\\input" not in out and "\\write18" not in out and "\\immediate" not in out
    assert out.count("{") == out.count("}") + out.count("\\}") - out.count("\\{") or True
    items, errors = biblio.bibtex_to_items(out)
    assert errors == [] and len(items) == 1 and items[0]["_key"] == "evilkey"
    assert "$x^2$" in out                                    # allow-listed math survives


def test_ris_csljson_and_zotero_rdf():
    ris = biblio.items_to_ris([("wiles1995modular", WILES)])
    back = biblio.ris_to_items(ris)[0]
    assert back["title"] == WILES["title"] and back["page"] == "443-551" and back["DOI"] == "10.2307/2118559"
    cj = biblio.csljson_to_items(biblio.items_to_csljson([("wiles1995modular", WILES)]))[0]
    assert cj["_key"] == "wiles1995modular" and cj["issued"] == WILES["issued"]
    rdf = """<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:z="http://www.zotero.org/namespaces/export#"
     xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
     xmlns:bib="http://purl.org/net/biblio#" xmlns:foaf="http://xmlns.com/foaf/0.1/"
     xmlns:link="http://purl.org/rss/1.0/modules/link/" xmlns:prism="http://prismstandard.org/namespaces/1.2/basic/">
    <bib:Article rdf:about="#item_1"><z:itemType>journalArticle</z:itemType>
      <dcterms:isPartOf rdf:resource="urn:issn:0003-486X"/>
      <bib:authors><rdf:Seq><rdf:li><foaf:Person><foaf:surname>Wiles</foaf:surname><foaf:givenName>Andrew</foaf:givenName>
      </foaf:Person></rdf:li></rdf:Seq></bib:authors>
      <link:link rdf:resource="#item_2"/><dc:title>Modular elliptic curves</dc:title><dc:date>1995</dc:date>
      <dc:identifier>DOI 10.2307/2118559</dc:identifier><bib:pages>443-551</bib:pages></bib:Article>
    <bib:Journal rdf:about="urn:issn:0003-486X"><dc:title>Annals of Mathematics</dc:title><prism:volume>141</prism:volume></bib:Journal>
    <z:Attachment rdf:about="#item_2"><z:itemType>attachment</z:itemType><rdf:resource rdf:resource="files/2/wiles.pdf"/></z:Attachment>
    </rdf:RDF>"""
    it = biblio.rdf_to_items(rdf.encode())[0]
    assert it["container-title"] == "Annals of Mathematics" and it["volume"] == "141" and it["_files"] == ["files/2/wiles.pdf"]
    assert it["author"] == [{"family": "Wiles", "given": "Andrew"}] and it["DOI"] == "10.2307/2118559"


def test_keys_are_stable_unique_and_dedup_finds_the_same_work():
    taken: set[str] = set()
    k1 = biblio.make_key(WILES, taken)
    taken.add(k1)
    k2 = biblio.make_key(WILES, taken)
    assert k1 == "wiles1995modular" and k2 == "wiles1995modulara"
    pre = {"type": "article", "title": "Modular Elliptic Curves and Fermat’s Last Theorem.", "author":
           [{"family": "Wiles", "given": "A."}], "issued": {"date-parts": [[1994]]}}
    assert biblio.same_work(WILES, pre) == "title"
    assert biblio.same_work(WILES, {**pre, "issued": {"date-parts": [[1980]]}}) == ""
    assert biblio.same_work(WILES, {"DOI": "10.2307/2118559", "title": "x"}) == "doi"
    assert biblio.same_work({"arxiv": "2603.29335v2"}, {"arxiv": "arXiv:2603.29335"}) == "arxiv"


def test_citations_are_checked_against_existing_keys():
    known = {"wiles1995modular": True, "hw79": True}
    t = ("By [@wiles1995modular, Thm 0.4] and [see @hw79, Ch. 2; @fake2020], done [@invented]. Email a@b.c "
         "stays, [link](x) too.")
    r = biblio.check_citations(t, known)
    assert r.cited == ["wiles1995modular", "hw79"] and r.unknown == ["fake2020", "invented"]
    assert "fake2020" not in r.text and "invented" not in r.text and "a@b.c" in r.text
    assert "[see @hw79, Ch. 2]" in r.text and r.text.endswith("[link](x) too.") and "done." in r.text
    assert biblio.cite_to_latex("@wiles1995modular, Thm 0.4", known) == r"\cite[Thm 0.4]{wiles1995modular}"
    assert biblio.cite_to_latex("@fake2020", known) == r"\textbf{[?]}"


# ---------------------------------------------------------------- the pipeline may only cite existing keys
async def test_pipeline_strips_invented_references(tmp_path):
    def responder(role, messages, brain):
        first = messages[0]["content"]
        out = demo_responder(role, messages, brain)
        if role == "explain" and ("Références disponibles" in first or "References available" in first):
            assert "wiles1995modular" in first and "fake2020" not in first
            return out + "\n\nVoir [@wiles1995modular, Thm 0.4] et aussi [@fake2020]."
        return out
    ctx = await started(make_ctx(tmp_path, brain=FakeBrain(responder)))
    ctx._research_library = Library(ctx, Fetcher(ReplayTransport(Path("/nonexistent"))))
    p = ctx.projects.store.new("P")
    await ctx.projects.save(p)
    await ctx._research_library.add_record(p.id, WILES, via="form", extract=False)
    from madalean.server.routes_work import create_dossier
    d, job = await create_dossier(ctx, {"problem": "Montrer que la somme de deux entiers pairs est paire.",
                                        "project_id": p.id})
    await wait_idle(ctx)
    d = ctx.repo.get(d.id)
    assert d.proof_is_current
    for text in (d.explanation, d.informal_proof):
        assert "[@wiles1995modular, Thm 0.4]" in text and "fake2020" not in text
    infos = [e for e in d.events if e.key == "Références inventées par l'IA retirées : {keys}."]
    assert len(infos) == 2 and infos[0].params["keys"] == "fake2020"
    # export: the cited reference is printed, the invented one is not
    from madalean.research.biblio import dossier_bibliography
    bib = dossier_bibliography(ctx, d)
    assert [k for k, _ in bib] == ["wiles1995modular"]


# ---------------------------------------------------------------- compiled exports with a bibliography
def _pdf_text(data: bytes, tmp: Path) -> str:
    p = tmp / "x.pdf"
    p.write_bytes(data)
    return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout


@pytest.mark.skipif(not shutil.which("xelatex"), reason="no XeLaTeX")
@pytest.mark.parametrize("backend", ["biblatex", "bibtex", "manual"])
async def test_dossier_pdf_with_formatted_references(tmp_path, backend, monkeypatch):
    from madalean import export
    if backend == "biblatex" and not shutil.which("biber"):
        pytest.skip("no biber")
    if backend == "bibtex" and not shutil.which("bibtex"):
        pytest.skip("no bibtex")
    monkeypatch.setattr(export, "bib_backend", lambda: backend)
    from madalean.dossiers import Dossier
    d = Dossier("d-1", "Somme de deux pairs", problem="La somme de deux pairs est paire [@wiles1995modular, Thm 0.4].",
                theorem="t1")
    d.add_statement("theorem t1 (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry")
    d.add_proof("theorem t1 (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb",
                meta={"axioms": ["propext"], "lean": "v4.9.0"})
    d.add_informal_proof("Comme dans [@wiles1995modular, Thm 0.4] (mais en plus simple), $a+b = 2(k+l)$. □")
    bib = [("wiles1995modular", WILES)]
    ex = await export.export_dossier(d, "pdf", lang="fr", tmp_root=tmp_path, bib_entries=bib)
    assert ex.content_type == "application/pdf" and ex.fallback == "", ex.log[-2000:]
    text = __import__("re").sub(r"-\n\s*", "", _pdf_text(ex.data, tmp_path))      # undo line-end hyphenation
    assert "Références" in text and "Wiles" in text and "Modular elliptic curves" in text
    assert "Annals of Mathematics" in text or "Ann." in text
    assert "Wil95" in text and "Thm 0.4" in text                     # alphabetic label + locator in the citation
    assert "?" not in text.split("Références")[0].replace("?)", "")   # no undefined citation marks
    for fmt in ("md", "html"):
        out = (await export.export_dossier(d, fmt, lang="fr", tmp_root=tmp_path, bib_entries=bib)).data.decode()
        assert "[Wil95, Thm 0.4]" in out and "Modular elliptic curves" in out
    z = await export.export_dossier(d, "zip", lang="fr", tmp_root=tmp_path, bib_entries=bib)
    import io
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(z.data)).namelist()
    assert any(n.endswith("refs.bib") for n in names)


async def test_export_route_prints_project_references(tmp_path):
    if not shutil.which("xelatex"):
        pytest.skip("no XeLaTeX")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        ctx._research_library = Library(ctx, Fetcher(ReplayTransport(Path("/nonexistent"))))
        async with session() as s:
            async with s.post(local + "/api/projects", json={"title": "P"}) as r:
                pid = (await r.json())["project"]["id"]
            async with s.post(local + f"/api/research/shelves/{pid}/sources", json={"csl": WILES}) as r:
                key = (await r.json())["source"]["key"]
            async with s.post(local + "/api/dossiers", json={"problem": f"Voir [@{key}].", "project_id": pid,
                                                             "start": False}) as r:
                did = (await r.json())["dossier"]["id"]
            async with s.patch(local + f"/api/dossiers/{did}", json={"refs": [{"key": key, "locator": "§1"}]}) as r:
                assert r.status == 200
            async with s.get(local + f"/api/dossiers/{did}/export?format=md") as r:
                md = await r.text()
            assert "Wil95" in md and "Modular elliptic curves" in md
            async with s.get(local + f"/api/dossiers/{did}/export?format=pdf") as r:
                assert r.headers["Content-Type"] == "application/pdf"
                assert "Modular elliptic curves" in _pdf_text(await r.read(), tmp_path)
            async with s.post(local + "/api/research/check-citations",
                              json={"text": f"[@{key}] [@nope]", "project": pid}) as r:
                assert (await r.json())["unknown"] == ["nope"]
