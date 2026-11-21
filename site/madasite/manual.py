"""docs/manual -> site pages (fr/, en/), docs/manual/index.json (in-app help) and assets/search-<lang>.json."""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import layout
from .leanhl import code_block
from .mathrender import MathBatch
from .mdrender import Hooks, Renderer, plain_text, split_front_matter, strip_comments

LANGS = ("fr", "en")
AUDIENCES = ("learner", "researcher", "all")
REQUIRED = ("id", "title", "order", "section", "audience", "summary")
SITE_LINKS = {"install": "download.html", "download": "download.html", "updates": "../updates/index.html",
              "search": "search.html"}
E = html.escape


@dataclass
class Page:
    lang: str
    meta: dict
    body_md: str            # comments removed
    verify: list[str]
    source: str             # fr/pairing.md
    html: str = ""
    headings: list = field(default_factory=list)
    links: list = field(default_factory=list)
    images: list = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.meta["id"]


class ManualError(Exception):
    pass


def load(manual_dir: Path) -> dict[str, dict[str, Page]]:
    pages: dict[str, dict[str, Page]] = {lg: {} for lg in LANGS}
    errors = []
    for lg in LANGS:
        for f in sorted((manual_dir / lg).glob("*.md")):
            meta, body = split_front_matter(f.read_text(encoding="utf-8"))
            miss = [k for k in REQUIRED if k not in meta]
            if miss:
                errors.append(f"{lg}/{f.name}: missing front matter {miss}")
                continue
            if meta["id"] != f.stem:
                errors.append(f"{lg}/{f.name}: id {meta['id']!r} must equal the file name")
            if meta["audience"] not in AUDIENCES:
                errors.append(f"{lg}/{f.name}: audience must be one of {AUDIENCES}")
            if meta["section"] not in dict(layout.SECTIONS[lg]):
                errors.append(f"{lg}/{f.name}: unknown section {meta['section']!r}")
            body, notes = strip_comments(body)
            pages[lg][meta["id"]] = Page(lg, meta, body, notes, f"{lg}/{f.name}")
    fr, en = set(pages["fr"]), set(pages["en"])
    if fr != en:
        errors.append(f"pages missing in en: {sorted(fr - en)}; missing in fr: {sorted(en - fr)}")
    for pid in fr & en:
        a, b = pages["fr"][pid].meta, pages["en"][pid].meta
        for k in ("order", "section", "audience"):
            if a[k] != b[k]:
                errors.append(f"{pid}: {k} differs between fr and en")
    if errors:
        raise ManualError("\n".join(errors))
    return pages


def ordered(pages: dict[str, Page], lang: str) -> list[Page]:
    sec_rank = {k: i for i, (k, _) in enumerate(layout.SECTIONS[lang])}
    return sorted(pages.values(), key=lambda p: (sec_rank[p.meta["section"]], p.meta["order"], p.id))


def render_all(pages, manual_dir: Path, math: MathBatch, problems: list[str]) -> None:
    img_root = manual_dir / "img"
    for lg in LANGS:
        for p in pages[lg].values():
            def link(href: str, p=p) -> str | None:
                p.links.append(href)
                if href.startswith(("http://", "https://", "mailto:")):
                    return href
                if href.startswith("site:"):
                    name, _, frag = href[5:].partition("#")
                    if name not in SITE_LINKS:
                        return None
                    return SITE_LINKS[name] + (f"#{frag}" if frag else "")
                if href.startswith("#"):
                    return href
                m = re.fullmatch(r"([a-z0-9-]+)\.md(#[a-z0-9-]+)?", href)
                if not m:
                    return None
                return f"{m.group(1)}.html{m.group(2) or ''}"

            def image(src: str, alt: str, p=p) -> str:
                p.images.append(src)
                name = src.split("img/", 1)[-1]
                if (img_root / name).is_file():
                    return (f'<figure><img src="../img/{E(name)}" alt="{E(alt)}" loading="lazy" decoding="async">'
                            f"<figcaption>{E(alt)}</figcaption></figure>")
                problems.append(f"placeholder image {src} in {p.source}")
                return (f'<figure class="img-placeholder" role="img" aria-label="{E(alt)}"><div>'
                        f'{E(layout.STR[p.lang]["image_missing"])}<br><code>{E(name)}</code></div>'
                        f"<figcaption>{E(alt)}</figcaption></figure>")
            hooks = Hooks(link=link, image=image, math=math.add,
                          code=lambda lang, code: code_block(lang, code))
            r = Renderer(hooks).render(p.body_md)
            p.html, p.headings = r.html, r.headings
            for b in r.broken_links:
                problems.append(f"bad link {b!r} in {p.source}")
    # anchors
    for lg in LANGS:
        for p in pages[lg].values():
            for href in p.links:
                m = re.fullmatch(r"([a-z0-9-]+)\.md(?:#([a-z0-9-]+))?", href)
                if not m:
                    continue
                tgt = pages[lg].get(m.group(1))
                if tgt is None:
                    problems.append(f"link to missing page {href} in {p.source}")
                elif m.group(2) and m.group(2) not in {h["id"] for h in tgt.headings}:
                    problems.append(f"link to missing anchor {href} in {p.source}")
                if href.startswith("#") and href[1:] not in {h["id"] for h in p.headings}:
                    problems.append(f"bad in-page anchor {href} in {p.source}")


def build_pages(pages, out: Path, repo_url: str) -> None:
    for lg in LANGS:
        other = "en" if lg == "fr" else "fr"
        s = layout.STR[lg]
        seq = ordered(pages[lg], lg)
        nav = [f'<nav class="side-nav" aria-label="{E(s["menu"])}"><details class="side-details" open>'
               f'<summary>{E(s["menu"])}</summary>']
        for sk, stitle in layout.SECTIONS[lg]:
            items = [p for p in seq if p.meta["section"] == sk]
            if not items:
                continue
            nav.append(f'<h2 class="side-h">{E(stitle)}</h2><ul>')
            for p in items:
                nav.append(f'<li><a href="{p.id}.html"%CUR_{p.id}%>{E(p.meta["title"])}</a></li>')
            nav.append("</ul>")
        nav.append("</details></nav>")
        nav_html = "".join(nav)
        for k, p in enumerate(seq):
            sidebar = re.sub(r"%CUR_([a-z0-9-]+)%", lambda m: ' aria-current="page"' if m.group(1) == p.id else "",
                             nav_html)
            toc = [h for h in p.headings if h["level"] == 2]
            toc_html = ""
            if len(toc) >= 3:
                toc_html = (f'<nav class="toc" aria-label="{E(s["on_page"])}"><h2>{E(s["on_page"])}</h2><ul>'
                            + "".join(f'<li><a href="#{h["id"]}">{E(h["text"])}</a></li>' for h in toc)
                            + "</ul></nav>")
            aud = p.meta["audience"]
            badge = f'<p class="audience aud-{aud}">{E(s[aud])}</p>' if aud != "all" else ""
            prev_next = [f'<nav class="pager" aria-label="{E(s["prev"])} / {E(s["next"])}">']
            if k > 0:
                q = seq[k - 1]
                prev_next.append(f'<a rel="prev" href="{q.id}.html"><span>{E(s["prev"])}</span>{E(q.meta["title"])}</a>')
            if k + 1 < len(seq):
                q = seq[k + 1]
                prev_next.append(f'<a rel="next" href="{q.id}.html"><span>{E(s["next"])}</span>{E(q.meta["title"])}</a>')
            prev_next.append("</nav>")
            src = f'<p class="page-source"><a href="{E(repo_url)}/blob/main/docs/manual/{p.source}" rel="noopener noreferrer">{E(s["source"])}</a></p>'
            body = (f'<div class="manual-layout">{sidebar}<main id="main" class="manual-main" tabindex="-1">'
                    f'<article class="prose">{badge}{p.html}</article>{"".join(prev_next)}{src}</main>{toc_html}</div>')
            doc = layout.page(lang=lg, title=f'{p.meta["title"]} — Madalean', body=body, root="../",
                              description=p.meta["summary"], alt_href=f"../{other}/{p.id}.html", active="manual")
            (out / lg).mkdir(parents=True, exist_ok=True)
            (out / lg / f"{p.id}.html").write_text(doc, encoding="utf-8")


def _plain(md: str) -> str:
    t = re.sub(r"```.*?```", " ", md, flags=re.S)
    t = re.sub(r"^#+\s*", "", t, flags=re.M)
    t = re.sub(r"^\|?[\s:|-]+\|?$", " ", t, flags=re.M)
    t = plain_text(t).replace("|", " ")
    return re.sub(r"\s+", " ", t).strip()


def index_json(pages, manual_dir: Path, site_url: str) -> dict:
    out = {"schema": "madalean-manual/1", "source": "docs/manual", "site_url": site_url,
           "languages": list(LANGS),
           "sections": {lg: [{"id": k, "title": t} for k, t in layout.SECTIONS[lg]] for lg in LANGS},
           "site_links": {k: v for k, v in SITE_LINKS.items()},
           "pages": []}
    for lg in LANGS:
        for p in ordered(pages[lg], lg):
            body = re.sub(r"\]\(\.\./img/", "](img/", p.body_md).strip() + "\n"
            imgs = []
            for src in p.images:
                name = src.split("img/", 1)[-1]
                imgs.append({"src": f"img/{name}", "exists": (manual_dir / "img" / name).is_file()})
            out["pages"].append({
                "id": p.id, "lang": lg, "title": p.meta["title"], "order": p.meta["order"],
                "section": p.meta["section"], "audience": p.meta["audience"], "summary": p.meta["summary"],
                "source": p.source, "site_path": f"{lg}/{p.id}.html",
                "headings": p.headings, "images": imgs, "verify": p.verify,
                "body": body, "text": _plain(p.body_md),
            })
    return out


def search_index(pages, lang: str) -> list[dict]:
    """One entry per page section (h1 intro + each h2), text cut to 600 characters."""
    entries = []
    for p in ordered(pages[lang], lang):
        chunks = re.split(r"^(##\s+.*)$", p.body_md, flags=re.M)
        head = chunks[0]
        h2s = [h for h in p.headings if h["level"] == 2]
        entries.append({"u": f"{p.id}.html", "t": p.meta["title"], "h": "", "x": _plain(head)[:600],
                        "s": p.meta["summary"]})
        for j in range(1, len(chunks), 2):
            idx = j // 2
            h = h2s[idx] if idx < len(h2s) else {"id": "", "text": plain_text(chunks[j][2:])}
            entries.append({"u": f'{p.id}.html#{h["id"]}', "t": p.meta["title"], "h": h["text"],
                            "x": _plain(chunks[j + 1])[:600]})
    return entries


def search_page(lang: str, out: Path) -> None:
    s = layout.STR[lang]
    other = "en" if lang == "fr" else "fr"
    body = (f'<main id="main" class="narrow" tabindex="-1"><h1>{E(s["search"])}</h1>'
            f'<div class="search" id="search" data-index="../assets/search-{lang}.json" '
            f'data-none="{E(s["search_none"])}" data-hint="{E(s["search_hint"])}" data-results="{E(s["search_results"])}">'
            f'<label for="q">{E(s["search_label"])}</label>'
            f'<input id="q" type="search" autocomplete="off" spellcheck="false" disabled>'
            f'<p class="search-status" id="search-status" role="status" aria-live="polite">{E(s["nojs_search"])}</p>'
            f'<ol class="search-results" id="search-results"></ol></div></main>')
    doc = layout.page(lang=lang, title=f'{s["search"]} — Madalean', body=body, root="../",
                      alt_href=f"../{other}/search.html", active="search")
    (out / lang / "search.html").write_text(doc, encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
