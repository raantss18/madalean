"""Output checks: internal links and anchors, external URL allow-list, basic HTML validity, QR codes, sizes."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SVG_VOID_OK = {"path", "rect", "circle", "line", "polyline", "polygon", "stop", "use", "ellipse"}
# Links (never loaded resources) allowed to leave the site. Anything else is an error.
ALLOWED = {
    "github": re.compile(r"^https://github\.com/raantss18(/madalean(\.git|/.*)?)?/?$"),
    # « Mesures » (D53): the public repositories of the benchmark sets, linked at their pinned commit
    "benchmarks": re.compile(r"^https://github\.com/(yangky11/miniF2F-lean4|trishullab/PutnamBench)(/.*)?$"),
    "scholarly": re.compile(r"^https://(doi\.org|arxiv\.org|zbmath\.org|www\.ams\.org/mathscinet)/"),
    "instructions": re.compile(r"^https://(tailscale\.com|platform\.claude\.com|aistudio\.google\.com|"
                               r"console\.anthropic\.com|huggingface\.co|console\.mistral\.ai|console\.groq\.com|"
                               r"cloud\.cerebras\.ai|cloud\.sambanova\.ai|openrouter\.ai|build\.nvidia\.com|"
                               r"platform\.openai\.com|platform\.deepseek\.com|app\.tavily\.com|dashboard\.exa\.ai|"
                               r"api-dashboard\.search\.brave\.com)(/.*)?$"),
    # « Attaque » (D69): the site whose problems are attacked
    "attack": re.compile(r"^https://lefttosolve\.com/?$"),
}


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []
        self.ids: list[str] = []
        self.refs: list[tuple[str, str, str]] = []    # (tag, attr, value)
        self.lang = None
        self.h1 = 0
        self.in_svg = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if "id" in a:
            self.ids.append(a["id"])
        if "style" in a:
            self.errors.append(f"inline style attribute on <{tag}>")
        for k in a:
            if k.startswith("on"):
                self.errors.append(f"inline event handler {k} on <{tag}>")
        if tag == "img" and "alt" not in a:
            self.errors.append("img without alt")
        if tag == "script" and "src" not in a:
            self.errors.append("inline <script>")
        if tag == "style":
            self.errors.append("<style> element")
        for attr in ("href", "src", "action", "poster"):
            if attr in a and a[attr] is not None:
                self.refs.append((tag, attr, a[attr]))
        if tag == "svg":
            self.in_svg += 1
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if "style" in a:
            self.errors.append(f"inline style attribute on <{tag}>")
        for attr in ("href", "src"):
            if attr in a and a[attr] is not None:
                self.refs.append((tag, attr, a[attr]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag == "svg":
            self.in_svg -= 1
        if not self.stack:
            self.errors.append(f"stray </{tag}>")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"unclosed <{self.stack.pop()}> before </{tag}>")
            self.stack.pop()
        else:
            self.errors.append(f"stray </{tag}>")


def check_site(out: Path) -> dict:
    report = {"errors": [], "external": {}, "pages": 0, "qr_checked": 0, "text_urls": set()}
    docs: dict[Path, Doc] = {}
    for f in sorted(out.rglob("*.html")):
        d = Doc()
        txt = f.read_text(encoding="utf-8")
        d.feed(txt)
        d.close()
        docs[f] = d
        rel = f.relative_to(out)
        report["pages"] += 1
        if not txt.startswith("<!doctype html>"):
            report["errors"].append(f"{rel}: missing doctype")
        if not d.lang:
            report["errors"].append(f"{rel}: <html> without lang")
        if d.h1 != 1:
            report["errors"].append(f"{rel}: {d.h1} <h1> elements")
        for e in d.errors:
            report["errors"].append(f"{rel}: {e}")
        if d.stack:
            report["errors"].append(f"{rel}: unclosed {d.stack}")
        dup = {i for i in d.ids if d.ids.count(i) > 1}
        if dup:
            report["errors"].append(f"{rel}: duplicate ids {sorted(dup)}")
        if "Content-Security-Policy" not in txt:
            report["errors"].append(f"{rel}: no CSP meta")
        for u in re.findall(r"https?://[^\s\"'<>)]+", re.sub(r"<[^>]+>", " ", txt)):
            report["text_urls"].add(u.rstrip(".,;"))
    for f, d in docs.items():
        rel = f.relative_to(out)
        for tag, attr, val in d.refs:
            if val.startswith(("http://", "https://", "//")):
                if tag != "a" or attr != "href":
                    report["errors"].append(f"{rel}: external resource {val} ({tag} {attr})")
                    continue
                cat = next((k for k, rx in ALLOWED.items() if rx.match(val)), None)
                if cat is None:
                    report["errors"].append(f"{rel}: external link not allowed: {val}")
                else:
                    report["external"].setdefault(cat, set()).add(val)
                continue
            if val.startswith(("mailto:", "data:")):
                continue
            sp = urlsplit(val)
            if sp.scheme:
                report["errors"].append(f"{rel}: unexpected scheme {val}")
                continue
            if sp.path.startswith("/madalean/"):          # 404.html: absolute paths of the project site
                target = (out / unquote(sp.path[len("/madalean/"):])).resolve()
            else:
                target = f if not sp.path else (f.parent / unquote(sp.path)).resolve()
            if sp.path.endswith("/"):
                target = target / "index.html"
            try:
                target.relative_to(out.resolve())
            except ValueError:
                report["errors"].append(f"{rel}: link leaves the site: {val}")
                continue
            if not target.exists():
                report["errors"].append(f"{rel}: broken link {val}")
                continue
            if sp.fragment and target.suffix == ".html":
                td = docs.get(target) or docs.get(Path(target))
                if td is None:
                    td = next((dd for ff, dd in docs.items() if ff.resolve() == target), None)
                if td is not None and sp.fragment not in td.ids:
                    report["errors"].append(f"{rel}: missing anchor {val}")
    for css in out.rglob("*.css"):
        for u in re.findall(r"url\(([^)]+)\)", css.read_text(encoding="utf-8")):
            u = u.strip("'\"")
            if u.startswith(("http", "//")):
                report["errors"].append(f"{css.relative_to(out)}: external url() {u}")
            elif not u.startswith("data:") and not (css.parent / u).exists():
                report["errors"].append(f"{css.relative_to(out)}: missing {u}")
    report["qr_checked"] = check_qr(out, report["errors"])
    report["text_urls"] = sorted(report["text_urls"])
    report["external"] = {k: sorted(v) for k, v in report["external"].items()}
    return report


def check_qr(out: Path, errors: list[str]) -> int:
    """Decode every QR code of download pages with rsvg-convert + zbarimg (when installed) and compare with the link."""
    if not (shutil.which("rsvg-convert") and shutil.which("zbarimg")):
        return 0
    n = 0
    for f in out.rglob("download.html"):
        txt = f.read_text(encoding="utf-8")
        for item in re.findall(r'<li class="dl-item">(.*?)</li>', txt, re.S):
            href = re.search(r'class="button" href="([^"]+)"', item).group(1)
            svg = re.search(r"(<svg class=\"qr\".*?</svg>)", item, re.S).group(1)
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "q.svg").write_text(svg)
                subprocess.run(["rsvg-convert", "-w", "600", str(Path(d) / "q.svg"), "-o", str(Path(d) / "q.png")], check=True)
                got = subprocess.run(["zbarimg", "-q", "--raw", str(Path(d) / "q.png")], capture_output=True, text=True).stdout.strip()
            if got != href.replace("&amp;", "&"):
                errors.append(f"{f.relative_to(out)}: QR code decodes to {got!r}, expected {href!r}")
            n += 1
    return n


def sizes(out: Path) -> dict:
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    by: dict[str, int] = {}
    for p in out.rglob("*"):
        if p.is_file():
            top = p.relative_to(out).parts[0] if len(p.relative_to(out).parts) > 1 else "(root)"
            by[top] = by.get(top, 0) + p.stat().st_size
    return {"total": total, "by_dir": dict(sorted(by.items(), key=lambda kv: -kv[1]))}
