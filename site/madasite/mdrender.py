"""Markdown subset used by docs/manual and by publication texts -> HTML (stdlib only).

Supported (documented in docs/SITE.md, the in-app help must accept the same): YAML-like front matter (handled by
`split_front_matter`), ATX headings, paragraphs, `---` rules, block quotes, ordered/unordered nested lists, fenced code
(```lean highlighted at build time), GFM pipe tables (`\\|` = literal pipe), `$…$` / `$$…$$` maths, inline code,
**strong**, *em* / _em_, links, images (alone in a paragraph -> <figure>), <https://autolinks>, HTML comments (removed;
`<!-- verify … -->` comments are collected). Raw HTML is escaped (never passed through).

Hooks given by the caller: `link(href) -> href | None` (None = broken: rendered as text and reported),
`image(src, alt) -> html`, `math(tex, display) -> html`, `cite(keys_and_locators) -> html | None`, `code(lang, text)`.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def split_front_matter(text: str) -> tuple[dict, str]:
    """Front matter of the manual: `key: value` lines (strings; `order` is int). No nesting, no lists."""
    text = text.replace("\r\n", "\n")
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for ln in m.group(1).splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        k, sep, v = ln.partition(":")
        if not sep:
            raise ValueError(f"bad front matter line: {ln!r}")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        meta[k.strip()] = int(v) if k.strip() == "order" else v
    return meta, text[m.end():]


COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)


def strip_comments(text: str) -> tuple[str, list[str]]:
    """Remove HTML comments outside fenced code; return (text, verify notes). A comment alone on its line removes
    the line."""
    notes: list[str] = []
    out, fence = [], None
    lines = text.split("\n")
    buf = "\n".join(lines)
    # comments may span lines: process outside fences only
    parts = re.split(r"(^```.*?^```[ \t]*$)", buf, flags=re.S | re.M)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(part)
            continue

        def repl(m: re.Match) -> str:
            body = m.group(1).strip()
            if body.lower().startswith("verify"):
                notes.append(body)
            return "\x00COMMENT\x00"
        part = COMMENT_RE.sub(repl, part)
        part = re.sub(r"^[ \t]*\x00COMMENT\x00[ \t]*\n", "", part, flags=re.M)
        part = part.replace("\x00COMMENT\x00", "")
        out.append(part)
    del fence
    return "".join(out), notes


def slugify(text: str) -> str:
    """Heading anchor: NFKD, drop combining marks, lowercase, keep [a-z0-9 -], spaces -> '-', collapse."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9 \-]", "", t)
    t = re.sub(r"[ ]+", "-", t.strip())
    t = re.sub(r"-{2,}", "-", t).strip("-")
    return t or "section"


def plain_text(md_inline: str) -> str:
    """Rough plain text of inline Markdown (headings in the index, search)."""
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", md_inline)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_`]", "", t)
    t = t.replace("\\|", "|")
    return t.strip()


@dataclass
class Hooks:
    link: Callable[[str], str | None] = lambda h: h
    image: Callable[[str, str], str] | None = None
    math: Callable[[str, bool], str] = lambda t, d: f'<code class="tex">{html.escape(t)}</code>'
    code: Callable[[str, str], str] | None = None
    cite: Callable[[list[tuple[str, str]]], str | None] | None = None
    heading_offset: int = 0          # add to heading levels (publication texts inside a page)


@dataclass
class Result:
    html: str
    headings: list[dict] = field(default_factory=list)   # {level, text, id}
    title: str = ""
    broken_links: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)


class Renderer:
    def __init__(self, hooks: Hooks | None = None):
        self.h = hooks or Hooks()

    # ------------------------------------------------------------------ public
    def render(self, text: str) -> Result:
        self.res = Result(html="")
        self._ids: dict[str, int] = {}
        lines = text.replace("\r\n", "\n").replace("\t", "    ").split("\n")
        self.res.html = self._blocks(lines)
        return self.res

    def inline(self, text: str) -> str:
        if not hasattr(self, "res"):
            self.res = Result(html="")
            self._ids = {}
        return self._inline(text)

    # ------------------------------------------------------------------ blocks
    def _blocks(self, lines: list[str]) -> str:
        out: list[str] = []
        i, n = 0, len(lines)
        while i < n:
            ln = lines[i]
            s = ln.strip()
            if not s:
                i += 1
                continue
            m = re.match(r"^(\s*)(`{3,}|~{3,})\s*([\w+-]*)\s*$", ln)
            if m:
                fence, lang = m.group(2), m.group(3).lower()
                ind = len(m.group(1))
                body, i = [], i + 1
                while i < n and not re.match(r"^\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$", lines[i]):
                    body.append(lines[i][ind:] if lines[i][:ind].strip() == "" else lines[i])
                    i += 1
                i += 1
                code = "\n".join(body)
                if self.h.code:
                    out.append(self.h.code(lang, code))
                else:
                    cls = f' class="language-{html.escape(lang)}"' if lang else ""
                    out.append(f"<pre><code{cls}>{html.escape(code)}</code></pre>")
                continue
            m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", s)
            if m and not ln.startswith("    "):
                lvl = len(m.group(1))
                text = m.group(2)
                hid = self._unique(slugify(plain_text(text)))
                lv = min(6, lvl + self.h.heading_offset)
                if lvl == 1 and not self.res.title:
                    self.res.title = plain_text(text)
                self.res.headings.append({"level": lvl, "text": plain_text(text), "id": hid})
                out.append(f'<h{lv} id="{hid}">{self._inline(text)}</h{lv}>')
                i += 1
                continue
            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
                out.append("<hr>")
                i += 1
                continue
            if s.startswith("$$"):
                rest = s[2:]
                if rest.rstrip().endswith("$$") and len(rest.strip()) >= 2:
                    out.append(self._math_block(rest.rstrip()[:-2]))
                    i += 1
                    continue
                body, i = [rest], i + 1
                while i < n and not lines[i].rstrip().endswith("$$"):
                    body.append(lines[i])
                    i += 1
                if i < n:
                    body.append(lines[i].rstrip()[:-2])
                i += 1
                out.append(self._math_block("\n".join(body)))
                continue
            if s.startswith(">"):
                body = []
                while i < n and lines[i].strip().startswith(">"):
                    body.append(re.sub(r"^\s*> ?", "", lines[i]))
                    i += 1
                out.append(f"<blockquote>{self._blocks(body)}</blockquote>")
                continue
            if "|" in s and i + 1 < n and re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", lines[i + 1]):
                rows = [s]
                aligns = self._cells(lines[i + 1])
                i += 2
                while i < n and lines[i].strip() and "|" in lines[i]:
                    rows.append(lines[i].strip())
                    i += 1
                out.append(self._table(rows[0], aligns, rows[1:]))
                continue
            if self._list_marker(ln):
                html_list, i = self._list(lines, i)
                out.append(html_list)
                continue
            # paragraph
            para = [s]
            i += 1
            while i < n and lines[i].strip() and not self._starts_block(lines, i):
                para.append(lines[i].strip())
                i += 1
            out.append(self._paragraph("\n".join(para)))
        return "\n".join(out)

    def _starts_block(self, lines: list[str], i: int) -> bool:
        s = lines[i].strip()
        return bool(re.match(r"^(#{1,6}\s|```|~~~|>|\$\$)", s) or re.match(r"^(-{3,}|\*{3,})$", s)
                    or self._list_marker(lines[i]))

    @staticmethod
    def _list_marker(ln: str):
        return re.match(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$", ln)

    def _list(self, lines: list[str], i: int) -> tuple[str, int]:
        m = self._list_marker(lines[i])
        base = len(m.group(1))
        ordered = m.group(2)[0].isdigit()
        start = int(m.group(2)[:-1]) if ordered else 1
        items: list[list[str]] = []
        loose = False
        n = len(lines)
        while i < n:
            m = self._list_marker(lines[i])
            if not m or len(m.group(1)) != base or m.group(2)[0].isdigit() != ordered:
                break
            content_ind = len(m.group(1)) + len(m.group(2)) + 1
            item = [m.group(3)]
            i += 1
            blank = False
            while i < n:
                ln = lines[i]
                if not ln.strip():
                    blank = True
                    i += 1
                    continue
                ind = len(ln) - len(ln.lstrip())
                mm = self._list_marker(ln)
                if ind >= content_ind or (mm and ind > base):
                    if blank:
                        item.append("")
                        loose = loose or not mm
                    item.append(ln[min(ind, content_ind):] if ind >= content_ind else ln[base + 2:] if ind > base else ln)
                    blank = False
                    i += 1
                    continue
                if blank:
                    break
                if mm and ind <= base:
                    break
                if self._starts_block(lines, i):
                    break
                item.append(ln.strip())       # lazy continuation
                i += 1
            nm = self._list_marker(lines[i]) if i < n else None
            if blank and nm and len(nm.group(1)) == base and nm.group(2)[0].isdigit() == ordered:
                loose = True
            items.append(item)
        tag = "ol" if ordered else "ul"
        attr = f' start="{start}"' if ordered and start != 1 else ""
        parts = []
        for item in items:
            body = self._blocks(item)
            if not loose:
                body = re.sub(r"^<p>(.*?)</p>", r"\1", body, count=1, flags=re.S)
            parts.append(f"<li>{body}</li>")
        return f"<{tag}{attr}>" + "".join(parts) + f"</{tag}>", i

    def _paragraph(self, text: str) -> str:
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", text.strip())
        if m:
            alt, src = m.group(1), m.group(2)
            self.res.images.append(src)
            if self.h.image:
                return self.h.image(src, alt)
            return (f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy">'
                    f"<figcaption>{html.escape(alt)}</figcaption></figure>")
        return f"<p>{self._inline(text)}</p>"

    def _math_block(self, tex: str) -> str:
        return f'<div class="math-display">{self.h.math(tex.strip(), True)}</div>'

    @staticmethod
    def _cells(row: str) -> list[str]:
        r = row.strip()
        if r.startswith("|"):
            r = r[1:]
        if r.endswith("|") and not r.endswith("\\|"):
            r = r[:-1]
        cells, cur, k = [], "", 0
        while k < len(r):
            c = r[k]
            if c == "\\" and k + 1 < len(r) and r[k + 1] == "|":
                cur += "\\|"
                k += 2
                continue
            if c == "|":
                cells.append(cur.strip())
                cur = ""
            else:
                cur += c
            k += 1
        cells.append(cur.strip())
        return cells

    def _table(self, head: str, aligns: list[str], rows: list[str]) -> str:
        al = []
        for a in aligns:
            a = a.strip()
            al.append("center" if a.startswith(":") and a.endswith(":") else "right" if a.endswith(":") else
                      "left" if a.startswith(":") else "")
        hc = self._cells(head)

        def cell(tag: str, txt: str, j: int) -> str:
            cls = f' class="al-{al[j]}"' if j < len(al) and al[j] else ""
            return f"<{tag}{cls}>{self._inline(txt)}</{tag}>"
        out = ['<div class="table-wrap"><table><thead><tr>']
        out += [cell("th", c, j) for j, c in enumerate(hc)]
        out.append("</tr></thead><tbody>")
        for r in rows:
            cs = self._cells(r)
            cs += [""] * (len(hc) - len(cs))
            out.append("<tr>" + "".join(cell("td", c, j) for j, c in enumerate(cs[:len(hc)])) + "</tr>")
        out.append("</tbody></table></div>")
        return "".join(out)

    def _unique(self, base: str) -> str:
        k = self._ids.get(base, 0)
        self._ids[base] = k + 1
        return base if k == 0 else f"{base}-{k}"

    # ------------------------------------------------------------------ inline
    def _inline(self, text: str) -> str:
        store: list[str] = []

        def keep(h: str) -> str:
            store.append(h)
            return f"\x02{len(store) - 1}\x03"

        t = text
        # code spans
        def code_span(m: re.Match) -> str:
            body = m.group(2)
            if body.startswith(" ") and body.endswith(" ") and body.strip():
                body = body[1:-1]
            body = body.replace("\\|", "|")
            return keep(f"<code>{html.escape(body)}</code>")
        t = re.sub(r"(`+)(.+?)\1", code_span, t, flags=re.S)
        # display maths inline $$…$$ then $…$
        t = re.sub(r"\$\$(.+?)\$\$", lambda m: keep(self.h.math(m.group(1).strip(), True)), t, flags=re.S)

        def inline_math(m: re.Match) -> str:
            return keep(self.h.math(m.group(1), False))
        t = re.sub(r"(?<![\\$\w])\$(?![\s\d$])((?:\\.|[^$\\])+?)(?<!\s)\$(?!\d)", inline_math, t, flags=re.S)
        # escapes
        t = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|$<>~\"'])", lambda m: keep(html.escape(m.group(1))), t)
        # citations [@key, loc; @key2]
        if self.h.cite:
            def cite(m: re.Match) -> str:
                items = []
                for part in m.group(1).split(";"):
                    mm = re.match(r"\s*(?:[^@]*?)@([A-Za-z0-9_:.+/\-]+)\s*,?\s*(.*)$", part)
                    if not mm:
                        return m.group(0)
                    items.append((mm.group(1), mm.group(2).strip()))
                r = self.h.cite(items)
                return keep(r) if r is not None else m.group(0)
            t = re.sub(r"\[((?:[^\[\]]*?@[A-Za-z0-9_:.+/\-]+[^\[\]]*?))\](?!\()", cite, t)
        # images
        def img(m: re.Match) -> str:
            alt, src = m.group(1), m.group(2)
            self.res.images.append(src)
            if self.h.image:
                return keep(self.h.image(src, alt))
            return keep(f'<img src="{html.escape(src)}" alt="{html.escape(alt)}">')
        t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", img, t)

        # links
        def link(m: re.Match) -> str:
            label, href = m.group(1), m.group(2)
            self.res.links.append(href)
            target = self.h.link(href)
            inner = self._inline(label)
            if target is None:
                self.res.broken_links.append(href)
                return keep(inner)
            ext = target.startswith(("http://", "https://"))
            rel = ' rel="noopener noreferrer"' if ext else ""
            return keep(f'<a href="{html.escape(target, quote=True)}"{rel}>{inner}</a>')
        t = re.sub(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)\s]+)\)", link, t)

        def autolink(m: re.Match) -> str:
            href = m.group(1)
            self.res.links.append(href)
            target = self.h.link(href) or href
            return keep(f'<a href="{html.escape(target, quote=True)}" rel="noopener noreferrer">{html.escape(href)}</a>')
        t = re.sub(r"<(https?://[^>\s]+)>", autolink, t)
        t = html.escape(t, quote=False)
        t = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", t, flags=re.S)
        t = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", t, flags=re.S)
        t = re.sub(r"(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])", r"<em>\1</em>", t, flags=re.S)
        t = t.replace("\n", " ")
        while "\x02" in t:
            nt = re.sub(r"\x02(\d+)\x03", lambda m: store[int(m.group(1))], t)
            if nt == t:
                break
            t = nt
        return t
