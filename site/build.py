#!/usr/bin/env python3
"""Madalean site generator (Python 3.10+ stdlib; node only to pre-render maths with the vendored KaTeX).

  python3 site/build.py [--out site/_site] [--sample-release] [--with-sample-publication] [--no-check]
      builds the GitHub Pages site: manual (fr/, en/), install page, updates/ channel, search indexes, and writes
      docs/manual/index.json (the in-app help index). Exit code 1 when a check fails.
  python3 site/build.py publication --input DIR --out DIR
      renders a project (DIR/publication.json + DIR/files/) with the publication template (used by « Publier »).

Formats: docs/SITE.md."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

from madasite import checks, install, layout, manual, publication  # noqa: E402
from madasite.mathrender import MathBatch  # noqa: E402

SITE_URL = "https://raantss18.github.io/madalean/"
REPO_URL = "https://github.com/raantss18/madalean"


def copy_assets(out: Path) -> None:
    a = out / "assets"
    (a / "fonts").mkdir(parents=True, exist_ok=True)
    (a / "katex" / "fonts").mkdir(parents=True, exist_ok=True)
    for f in ("style.css", "theme.js", "site.js"):
        shutil.copy2(HERE / "assets" / f, a / f)
    shutil.copy2(REPO / "shells" / "branding" / "madalean-icon.svg", a / "icon.svg")
    for f in (HERE / "vendor" / "fonts").iterdir():
        if f.suffix in (".woff2", ".txt"):
            shutil.copy2(f, a / "fonts" / f.name)
    k = HERE / "vendor" / "katex"
    shutil.copy2(k / "katex.min.css", a / "katex" / "katex.min.css")
    shutil.copy2(k / "LICENSE", a / "katex" / "LICENSE.txt")
    for f in (k / "fonts").glob("*.woff2"):
        shutil.copy2(f, a / "katex" / "fonts" / f.name)


def door(out: Path) -> None:
    fr, en = layout.STR["fr"], layout.STR["en"]
    body = ('<main id="main" class="door prose" tabindex="-1"><h1>Madalean</h1>'
            '<p class="lead">Assistant de démonstration pour Lean 4 et Mathlib : rien n’est déclaré prouvé sans le '
            'verdict de Lean. <span lang="en">Proof assistant companion for Lean 4 and Mathlib: nothing is declared '
            'proved without Lean’s verdict.</span></p><div class="door-grid">'
            f'<section class="door-card" aria-labelledby="d-fr"><h2 id="d-fr">Français</h2><ul>'
            f'<li><a href="fr/index.html">{fr["manual"]}</a></li><li><a href="fr/download.html">{fr["download"]}</a></li>'
            f'<li><a href="fr/search.html">{fr["search"]}</a></li></ul></section>'
            f'<section class="door-card" lang="en" aria-labelledby="d-en"><h2 id="d-en">English</h2><ul>'
            f'<li><a href="en/index.html">{en["manual"]}</a></li><li><a href="en/download.html">{en["download"]}</a></li>'
            f'<li><a href="en/search.html">{en["search"]}</a></li></ul></section>'
            '<section class="door-card" aria-labelledby="d-up"><h2 id="d-up">Mises à jour · <span lang="en">Updates</span></h2>'
            '<ul><li><a href="updates/index.html">updates/</a></li></ul></section></div></main>')
    (out / "index.html").write_text(layout.page(lang="fr", title="Madalean", body=body, root="",
                                                description="Manuel, installation et canal de mise à jour de Madalean."),
                                    encoding="utf-8")
    body404 = ('<main id="main" class="narrow prose" tabindex="-1"><h1>Page introuvable</h1>'
               '<p>Cette page n’existe pas. <a href="/madalean/index.html">Accueil du site</a>.</p>'
               '<p lang="en">This page does not exist. <a href="/madalean/index.html">Site home</a>.</p></main>')
    # 404.html is served for any missing path, so it uses absolute paths under the project site.
    (out / "404.html").write_text(layout.page(lang="fr", title="Page introuvable — Madalean", body=body404,
                                              root="/madalean/"), encoding="utf-8")


def build_site(args) -> int:
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    problems: list[str] = []
    copy_assets(out)
    (out / ".nojekyll").write_text("")
    math = MathBatch()
    mdir = REPO / "docs" / "manual"
    pages = manual.load(mdir)
    manual.render_all(pages, mdir, math, problems)
    manual.build_pages(pages, out, REPO_URL)
    for lg in manual.LANGS:
        manual.search_page(lg, out)
        manual.write_json(out / "assets" / f"search-{lg}.json", manual.search_index(pages, lg))
    idx = manual.index_json(pages, mdir, SITE_URL)
    manual.write_json(mdir / "index.json", idx)
    if (mdir / "img").is_dir():
        shutil.copytree(mdir / "img", out / "img", dirs_exist_ok=True)
    rel = install.build(out, REPO, Path(args.channel), problems,
                        sample=(HERE / "fixtures" / "stable.sample.json") if args.sample_release else None)
    door(out)
    pub = None
    if args.with_sample_publication:
        pdir = out / "publication-sample"
        pub = publication.build(HERE / "publication" / "sample", pdir, math, problems)
        copy_assets(pdir)
    math.finish()
    problems += math.errors
    css = math.css()
    (out / "assets" / "math.css").write_text(css)
    if pub is not None:
        (out / "publication-sample" / "assets" / "math.css").write_text(css)
    for f in out.rglob("*.html"):
        t = f.read_text(encoding="utf-8")
        if "\x01M" in t:
            f.write_text(math.apply(t), encoding="utf-8")
    # the manual pages need the maths stylesheets: add them after the main stylesheet
    for f in list((out / "fr").glob("*.html")) + list((out / "en").glob("*.html")):
        t = f.read_text(encoding="utf-8")
        if 'class="katex"' in t and "katex.min.css" not in t:
            t = t.replace('<link rel="stylesheet" href="../assets/style.css">',
                          '<link rel="stylesheet" href="../assets/style.css"><link rel="stylesheet" '
                          'href="../assets/katex/katex.min.css"><link rel="stylesheet" href="../assets/math.css">', 1)
            f.write_text(t, encoding="utf-8")
    verify_notes = sum(len(p["verify"]) for p in idx["pages"])
    print(f"manual: {len(idx['pages'])} pages ({', '.join(manual.LANGS)}), {verify_notes} 'verify after integration' notes")
    print(f"index:  docs/manual/index.json ({(mdir / 'index.json').stat().st_size // 1024} KiB)")
    print(f"maths:  {len(math.items)} expressions, {len(math.styles)} generated style classes"
          + ("" if math.node else " (node missing: TeX shown as source)"))
    print(f"release channel: {'stable.json published' if rel['published_manifest'] else 'no stable.json yet'}"
          + (" (install page built with SAMPLE data)" if rel["sample"] else ""))
    if pub:
        print(f"publication sample: {pub['nodes']} nodes, {pub['verified']} verified -> publication-sample/")
    status = 0
    for p in problems:
        level = "warn" if p.startswith("placeholder image") else "ERROR"
        print(f"{level}: {p}")
        if level == "ERROR":
            status = 1
    if not args.no_check:
        rep = checks.check_site(out)
        print(f"checks: {rep['pages']} HTML pages, {rep['qr_checked']} QR codes decoded")
        for cat, urls in rep["external"].items():
            print(f"  external links ({cat}): {len(urls)}")
            for u in urls:
                print(f"    {u}")
        for e in rep["errors"]:
            print(f"ERROR: {e}")
        if rep["errors"]:
            status = 1
        sz = checks.sizes(out)
        print(f"size: {sz['total'] / 1024:.0f} KiB total; " + ", ".join(f"{k} {v / 1024:.0f} KiB" for k, v in sz["by_dir"].items()))
        if args.report:
            Path(args.report).write_text(json.dumps({**rep, "sizes": sz}, indent=1, ensure_ascii=False))
    return status


def build_publication(args) -> int:
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"{out} is not empty (use --force)", file=sys.stderr)
        return 2
    if out.exists():
        shutil.rmtree(out)
    problems: list[str] = []
    math = MathBatch()
    res = publication.build(Path(args.input).resolve(), out, math, problems)
    copy_assets(out)
    math.finish()
    (out / "assets" / "math.css").write_text(math.css())
    for f in out.rglob("*.html"):
        f.write_text(math.apply(f.read_text(encoding="utf-8")), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    problems += math.errors
    for p in problems:
        print(f"ERROR: {p}")
    rep = checks.check_site(out)
    for e in rep["errors"]:
        print(f"ERROR: {e}")
    print(f"publication: {res['nodes']} nodes, {res['verified']} verified, {rep['pages']} pages -> {out}")
    return 1 if problems or rep["errors"] else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("publication", help="render a project with the publication template")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true")
    ap.add_argument("--out", default=str(HERE / "_site"))
    ap.add_argument("--channel", default=str(HERE / "updates"), help="directory holding stable.json(.sig)")
    ap.add_argument("--sample-release", action="store_true", help="preview the install page with fixture data")
    ap.add_argument("--with-sample-publication", action="store_true", help="also render site/publication/sample")
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--report", help="write the check report (JSON) here")
    args = ap.parse_args()
    if args.cmd == "publication":
        return build_publication(args)
    return build_site(args)


if __name__ == "__main__":
    sys.exit(main())
