"""Maths rendered at build time with the vendored KaTeX (node), inline `style` attributes moved to a generated
stylesheet so that pages need neither scripts nor `style-src 'unsafe-inline'`.

Usage: placeholders are emitted while rendering (`MathBatch.add`), then `MathBatch.finish()` renders everything in
one node process and `MathBatch.apply(text)` substitutes them. Without node the TeX source is shown in <code>."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"


class MathBatch:
    def __init__(self, node: str | None = None):
        self.node = node or shutil.which("node")
        self.items: dict[str, tuple[str, bool]] = {}
        self.rendered: dict[str, str] = {}
        self.styles: dict[str, str] = {}      # style text -> class
        self.errors: list[str] = []

    def add(self, tex: str, display: bool) -> str:
        key = hashlib.sha1(f"{int(display)}{tex}".encode()).hexdigest()[:16]
        self.items[key] = (tex, display)
        return f"\x01M{key}\x01"

    def finish(self) -> None:
        todo = [k for k in self.items if k not in self.rendered]
        if not todo:
            return
        results = None
        if self.node:
            payload = json.dumps([{"tex": self.items[k][0], "display": self.items[k][1]} for k in todo])
            p = subprocess.run([self.node, str(TOOLS / "katex_render.cjs")], input=payload, capture_output=True,
                               text=True, timeout=300)
            if p.returncode == 0:
                results = json.loads(p.stdout)
            else:
                self.errors.append("node/katex failed: " + p.stderr[-500:])
        else:
            self.errors.append("node not found: maths left as TeX source")
        for idx, k in enumerate(todo):
            tex, display = self.items[k]
            r = results[idx] if results else {"html": None, "error": "no renderer"}
            if r["html"] is None:
                if results:
                    self.errors.append(f"KaTeX error in {tex!r}: {r['error']}")
                self.rendered[k] = f'<code class="tex">{html.escape(tex)}</code>'
            else:
                self.rendered[k] = self._unstyle(r["html"])

    def _unstyle(self, h: str) -> str:
        def tag(m: re.Match) -> str:
            t = m.group(0)
            sm = re.search(r'\sstyle="([^"]*)"', t)
            if not sm:
                return t
            style = sm.group(1).strip()
            t = t[:sm.start()] + t[sm.end():]
            if not style:
                return t
            cls = self.styles.get(style)
            if cls is None:
                cls = f"ks{len(self.styles)}"
                self.styles[style] = cls
            cm = re.search(r'\sclass="([^"]*)"', t)
            if cm:
                return t[:cm.start()] + f' class="{cm.group(1)} {cls}"' + t[cm.end():]
            return re.sub(r"^<([\w:-]+)", lambda x: f'<{x.group(1)} class="{cls}"', t)
        return re.sub(r"<[\w:-]+\s[^>]*>", tag, h)

    def apply(self, text: str) -> str:
        return re.sub(r"\x01M([0-9a-f]{16})\x01", lambda m: self.rendered.get(m.group(1), ""), text)

    def css(self) -> str:
        out = ["/* generated: KaTeX inline styles as classes (strict CSP, no style attributes) */"]
        for style, cls in self.styles.items():
            decl = ";".join(d.strip() + " !important" for d in style.split(";") if d.strip())
            out.append(f".katex .{cls},.{cls}{{{decl}}}")
        return "\n".join(out) + "\n"
