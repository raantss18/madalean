"""« Calcul » notebooks (session S-P, docs/CALCUL.md): a Calcul document is a standard Jupyter notebook (.ipynb,
nbformat 4.5) — an ordered sequence of cells sharing ONE kernel state — stored in the integrated JupyterLab's tree
(`<notebooks>/calcul/<project id>/<doc>.ipynb`), so the very same file opens in JupyterLab with Madalean's
sandboxed Sage kernel and nothing is stored or started twice.

Cells (nbformat ↔ Madalean):
- code (Sage or Python, the document's kernel language)            → nbformat code cell
- ask: a request in natural language + the code the model wrote     → code cell, metadata.madalean {kind: ask, prompt}
- markdown text with $LaTeX$                                         → markdown cell
- figure (interactive curves / dynamic geometry, web/src/lib/figure) → markdown cell showing the figure as an SVG
  attachment (what JupyterLab displays), metadata.madalean {kind: figure, figure: FigureSpec}

What must not live in a file the user can share or receive — who wrote a cell (the assistant or the user), the
approval of model code, the version history and the run history — lives in a small sidecar on the host
(`<config>/research/calcul/<pid>/<doc>.json`). A notebook received from elsewhere therefore never carries an
approval: model code is approved by hash, on this host (docs/SECURITY.md). Images are stored once, inside the
.ipynb (standard, readable by JupyterLab, nbviewer, nbconvert); the server addresses them by content hash
(sha-256, 32 hex) without copying them.

Older `<config>/research/calcul/<pid>.json` worksheets (session S-M) are migrated once into `<doc>=calcul`, with
their versions, approvals and last outputs; the JSON is kept as `<pid>.json.migrated`."""
from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
import re
import secrets
import threading
import time
from pathlib import Path

from .. import config
from .calcul import PNG_MAGIC, CalcError, code_hash, sanitize_svg

KINDS = ("code", "ask", "markdown", "figure")
LANGS = ("sage", "python")
SPECS = {"sage": ("madalean-sage", "SageMath (Madalean)", "sage"),
         "python": ("madalean-python", "Python 3 (Madalean)", "python")}
DOC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
CELL_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DEFAULT_DOC = "calcul"
FIGURE_MIME = "application/vnd.madalean.figure+json"
MAX_CELLS = 400
MAX_SOURCE = 100_000
MAX_VERSIONS = 20
MAX_RUNS = 8
MAX_DOCS = 60
MAX_FIGURE = 1_000_000
MAX_TRASH = 20
CONTEXT_OUTPUT = 1_500          # characters of an output sent to a model (large outputs are cut)


def _now() -> float:
    return time.time()


def _text(src) -> str:
    return "".join(src) if isinstance(src, list) else str(src or "")


def asset_id(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:32]


def slugify(title: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48]
    return s or "calcul"


def upstream_hash(hashes: list[str]) -> str:
    return hashlib.sha256("|".join(hashes).encode()).hexdigest()[:16]


def new_nb(language: str, title: str) -> dict:
    name, display, lang = SPECS[language]
    return {"cells": [], "nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"name": name, "display_name": display, "language": lang},
                         "language_info": {"name": lang},
                         "madalean": {"title": title[:200], "language": language, "created": _now()}}}


def cell_kind(c: dict) -> str:
    m = (c.get("metadata") or {}).get("madalean") or {}
    k = m.get("kind")
    if c.get("cell_type") == "code":
        return "ask" if k == "ask" else "code"
    if c.get("cell_type") == "markdown":
        return "figure" if k == "figure" and isinstance(m.get("figure"), dict) else "markdown"
    return "markdown"                              # raw cells are shown as text


def nb_language(nb: dict) -> str:
    m = (nb.get("metadata") or {})
    lang = (m.get("madalean") or {}).get("language")
    if lang in LANGS:
        return lang
    ks = (m.get("kernelspec") or {})
    return "sage" if "sage" in str(ks.get("name", "")) + str(ks.get("language", "")) else "python"


# ================================================================ outputs
def _png(data: str) -> bytes | None:
    try:
        raw = base64.b64decode(data, validate=False)
    except ValueError:
        return None
    return raw if raw.startswith(PNG_MAGIC) else None


def clean_outputs(outputs: list[dict]) -> list[dict]:
    """Outputs as stored in the .ipynb: PNG checked by magic number, SVG sanitised, never HTML or scripts."""
    out = []
    for o in outputs or []:
        t = o.get("output_type")
        if t == "stream":
            out.append({"output_type": "stream", "name": "stderr" if o.get("name") == "stderr" else "stdout",
                        "text": _text(o.get("text"))[:200_000]})
        elif t == "error":
            out.append({"output_type": "error", "ename": str(o.get("ename", ""))[:200],
                        "evalue": str(o.get("evalue", ""))[:4000],
                        "traceback": [str(x)[:4000] for x in (o.get("traceback") or [])[-20:]]})
        elif t in ("execute_result", "display_data"):
            data = {}
            for mime, v in (o.get("data") or {}).items():
                if mime == FIGURE_MIME:
                    if isinstance(v, dict) and len(json.dumps(v)) <= MAX_FIGURE:
                        data[mime] = v
                    continue
                v = _text(v)
                if mime == "image/png":
                    if _png(v) is not None:
                        data[mime] = v.replace("\n", "")
                elif mime == "image/svg+xml":
                    try:
                        data[mime] = sanitize_svg(v)
                    except CalcError:
                        pass
                elif mime in ("text/plain", "text/latex", "text/markdown"):
                    data[mime] = v[:200_000]
            if not data:
                continue
            x = {"output_type": t, "data": data, "metadata": dict(o.get("metadata") or {})}
            if t == "execute_result":
                x["execution_count"] = o.get("execution_count")
            out.append(x)
    return out


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def view_outputs(outputs: list[dict], index: dict | None = None, where: tuple | None = None) -> list[dict]:
    """Outputs for the UI: images replaced by their content address (fetched from /api/calcul/…/assets/<id>)."""
    out = []
    for o in outputs or []:
        t = o.get("output_type")
        if t == "stream":
            out.append({"type": "stream", "name": o.get("name", "stdout"), "text": _text(o.get("text"))})
        elif t == "error":
            out.append({"type": "error", "ename": o.get("ename", ""), "evalue": o.get("evalue", ""),
                        "traceback": _ANSI.sub("", "\n".join(_text(x) for x in o.get("traceback") or []))[-6000:]})
        elif t in ("execute_result", "display_data"):
            data = {}
            for mime, v in (o.get("data") or {}).items():
                if mime in ("image/png", "image/svg+xml"):
                    raw = _png(_text(v)) if mime == "image/png" else _text(v).encode()
                    if raw:
                        aid = asset_id(raw)
                        data[mime] = {"asset": aid}
                        if index is not None and where is not None:
                            index[aid] = where
                elif mime == FIGURE_MIME:
                    data[mime] = v
                elif mime in ("text/plain", "text/latex", "text/markdown"):
                    data[mime] = _text(v)
            m = (o.get("metadata") or {}).get("madalean") or {}
            x = {"type": "result" if t == "execute_result" else "display", "data": data}
            if m.get("approx"):
                x["approx"] = str(m["approx"])
            out.append(x)
    return out


def outputs_text(outputs: list[dict], limit: int = CONTEXT_OUTPUT) -> str:
    parts = []
    for o in outputs or []:
        t = o.get("output_type")
        if t == "stream":
            parts.append(_text(o.get("text")))
        elif t == "error":
            parts.append(f"{o.get('ename')}: {o.get('evalue')}")
        elif t in ("execute_result", "display_data"):
            d = o.get("data") or {}
            if "text/latex" in d:
                parts.append(_text(d["text/latex"]))
            elif "text/plain" in d:
                parts.append(_text(d["text/plain"]))
            elif any(k.startswith("image/") for k in d):
                parts.append("[image]")
    s = "\n".join(p.rstrip("\n") for p in parts if p).strip()
    return s if len(s) <= limit else s[:limit] + f"\n[… {len(s) - limit} characters cut]"


def run_summary(outputs: list[dict]) -> dict:
    """The S-M run shape (stdout, stderr, result, error, rich) derived from nbformat outputs (older clients)."""
    s = {"stdout": "", "stderr": "", "result": "", "error": "", "rich": []}
    for o in view_outputs(outputs):
        if o["type"] == "stream":
            s["stderr" if o["name"] == "stderr" else "stdout"] += o["text"]
        elif o["type"] == "error":
            s["error"] = f"{o['ename']}: {o['evalue']}\n{o['traceback']}"[-4000:]
        else:
            d = o["data"]
            if "text/plain" in d:
                s["result"] += d["text/plain"] + "\n"
            if "text/latex" in d:
                s["rich"].append({"mime": "text/latex", "data": d["text/latex"]})
            for mime in ("image/png", "image/svg+xml"):
                if mime in d:
                    s["rich"].append({"mime": mime, "asset": d[mime]["asset"]})
    return s


# ================================================================ store
class NotebookStore:
    """Documents of a project. All methods are blocking (call them through asyncio.to_thread)."""

    def __init__(self, nb_root: Path, meta_root: Path, legacy=None):
        self.nb_root = Path(nb_root)
        self.meta_root = Path(meta_root)
        self.legacy = legacy                       # calcul.CalcStore of the S-M worksheets (migration, old assets)
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()
        self._cache: dict[Path, tuple[int, dict]] = {}
        self.assets: dict[str, tuple[str, str]] = {}    # content address -> (pid, doc)

    # ------------------------------------------------------------ paths
    @staticmethod
    def _pid(pid: str) -> str:
        if not PID_RE.match(pid or "") or ".." in pid:
            raise CalcError("bad_project")
        return pid

    @staticmethod
    def _doc(doc: str) -> str:
        if not DOC_RE.match(doc or ""):
            raise CalcError("bad_document")
        return doc

    def rel_path(self, pid: str, doc: str) -> str:
        return f"calcul/{self._pid(pid)}/{self._doc(doc)}.ipynb"

    def path(self, pid: str, doc: str) -> Path:
        return self.nb_root / self.rel_path(pid, doc)

    def side_path(self, pid: str, doc: str) -> Path:
        return self.meta_root / self._pid(pid) / f"{self._doc(doc)}.json"

    def lock(self, pid: str, doc: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(f"{pid}/{doc}", threading.RLock())

    # ------------------------------------------------------------ files
    def read(self, pid: str, doc: str) -> dict:
        p = self.path(pid, doc)
        try:
            st = p.stat()
        except FileNotFoundError:
            raise CalcError("not_found", 404) from None
        hit = self._cache.get(p)
        if hit and hit[0] == st.st_mtime_ns:
            return copy.deepcopy(hit[1])
        try:
            nb = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise CalcError("bad_notebook", 422) from None
        if not isinstance(nb, dict) or not isinstance(nb.get("cells"), list):
            raise CalcError("bad_notebook", 422)
        changed = False
        for c in nb["cells"]:                       # nbformat < 4.5 or cells written by hand: give them ids
            if not isinstance(c, dict):
                continue
            if not CELL_RE.match(str(c.get("id", ""))):
                c["id"] = secrets.token_hex(4)
                changed = True
        nb["cells"] = [c for c in nb["cells"] if isinstance(c, dict)]
        if len(self._cache) > 16:
            self._cache.clear()
        self._cache[p] = (st.st_mtime_ns, nb)
        if changed:
            self.write(pid, doc, nb)
        return copy.deepcopy(nb)

    def write(self, pid: str, doc: str, nb: dict) -> None:
        nb["nbformat"], nb["nbformat_minor"] = 4, max(5, int(nb.get("nbformat_minor") or 5))
        p = self.path(pid, doc)
        config.atomic_write_text(p, json.dumps(nb, ensure_ascii=False, indent=1) + "\n")
        try:
            self._cache[p] = (p.stat().st_mtime_ns, copy.deepcopy(nb))
        except OSError:
            self._cache.pop(p, None)

    def side(self, pid: str, doc: str) -> dict:
        data, _bad = config.read_json(self.side_path(pid, doc))
        if not isinstance(data, dict):
            data = {}
        data.setdefault("cells", {})
        data.setdefault("trash", [])
        return data

    def save_side(self, pid: str, doc: str, side: dict) -> None:
        config.atomic_write_text(self.side_path(pid, doc), json.dumps(side, ensure_ascii=False))

    # ------------------------------------------------------------ documents
    def docs(self, pid: str) -> list[dict]:
        self._pid(pid)
        self.migrate(pid)
        d = self.nb_root / "calcul" / pid
        out = []
        for p in sorted(d.glob("*.ipynb")) if d.is_dir() else []:
            if not DOC_RE.match(p.stem):
                continue
            try:
                nb = self.read(pid, p.stem)
            except CalcError:
                continue
            m = (nb.get("metadata") or {}).get("madalean") or {}
            out.append({"id": p.stem, "title": m.get("title") or p.stem, "language": nb_language(nb),
                        "path": self.rel_path(pid, p.stem), "cells": len(nb["cells"]),
                        "updated": p.stat().st_mtime, "created": m.get("created")})
        if not out:
            self.create(pid, "Calcul", "sage", doc=DEFAULT_DOC)
            return self.docs(pid)
        out.sort(key=lambda x: (x["id"] != DEFAULT_DOC, -(x["updated"] or 0)))
        return out

    def create(self, pid: str, title: str, language: str = "sage", doc: str = "") -> dict:
        self._pid(pid)
        if language not in LANGS:
            raise CalcError("bad_language")
        d = self.nb_root / "calcul" / pid
        if d.is_dir() and len(list(d.glob("*.ipynb"))) >= MAX_DOCS:
            raise CalcError("too_many", 413)
        base = self._doc(doc) if doc else slugify(title)
        name, n = base, 2
        while self.path(pid, name).exists():
            name, n = f"{base[:55]}-{n}", n + 1
        self.write(pid, name, new_nb(language, title.strip() or "Calcul"))
        return {"id": name, "title": title.strip() or "Calcul", "language": language, "path": self.rel_path(pid, name)}

    def rename(self, pid: str, doc: str, title: str) -> dict:
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            nb.setdefault("metadata", {}).setdefault("madalean", {})["title"] = title.strip()[:200] or doc
            self.write(pid, doc, nb)
        return {"id": doc, "title": nb["metadata"]["madalean"]["title"]}

    def delete_doc(self, pid: str, doc: str) -> None:
        """Moved to `<notebooks>/calcul/<pid>/.trash/` (hidden from JupyterLab's tree, restorable by hand)."""
        p = self.path(pid, doc)
        if not p.exists():
            raise CalcError("not_found", 404)
        t = p.parent / ".trash"
        t.mkdir(exist_ok=True)
        p.rename(t / f"{doc}-{int(_now())}.ipynb")
        self._cache.pop(p, None)

    # ------------------------------------------------------------ migration of S-M worksheets
    def migrate(self, pid: str) -> bool:
        old = self.meta_root / f"{pid}.json"
        if not old.is_file() or self.path(pid, DEFAULT_DOC).exists():
            return False
        try:
            sheet = json.loads(old.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        cells = [c for c in sheet.get("cells") or [] if isinstance(c, dict)]
        langs = [c.get("language") for c in cells]
        language = "python" if langs and all(x == "python" for x in langs) else "sage"
        nb = new_nb(language, "Calcul")
        side = {"cells": {}, "trash": [], "migrated_from": old.name}
        for c in cells:
            cid = re.sub(r"[^A-Za-z0-9_-]", "-", str(c.get("id") or secrets.token_hex(4)))[:64]
            runs = c.get("runs") or []
            last = runs[-1] if runs else None
            outputs = []
            if last:
                if last.get("stdout"):
                    outputs.append({"output_type": "stream", "name": "stdout", "text": last["stdout"]})
                for r in last.get("rich") or []:
                    if r.get("mime") == "text/latex":
                        outputs.append({"output_type": "display_data", "metadata": {},
                                        "data": {"text/latex": r.get("data", ""), "text/plain": r.get("data", "")}})
                    elif r.get("asset") and self.legacy is not None:
                        found = self.legacy.asset_path(r["asset"])
                        if found:
                            raw = found[0].read_bytes()
                            v = base64.b64encode(raw).decode() if found[1] == "image/png" else raw.decode("utf-8", "replace")
                            outputs.append({"output_type": "display_data", "metadata": {},
                                            "data": {found[1]: v, "text/plain": "<image>"}})
                if last.get("result") and not any(r.get("mime") == "text/latex" for r in last.get("rich") or []):
                    outputs.append({"output_type": "execute_result", "execution_count": None, "metadata": {},
                                    "data": {"text/plain": last["result"].rstrip("\n")}})
                if last.get("error"):
                    e = str(last["error"])
                    outputs.append({"output_type": "error", "ename": e.split(":", 1)[0][:200],
                                    "evalue": e.split(":", 1)[-1].strip()[:4000], "traceback": []})
            code = str(c.get("code", ""))
            meta = {"kind": "code"}
            if c.get("language") and c.get("language") != language:
                meta["language_was"] = c["language"]
            if last:
                meta["run"] = {"status": last.get("status", "ok"), "seconds": last.get("seconds", 0),
                               "t": last.get("t", 0), "code_hash": last.get("code_hash", ""), "upstream": "",
                               "kernel": ""}
            nb["cells"].append({"cell_type": "code", "id": cid, "metadata": {"madalean": meta}, "source": code,
                                "outputs": clean_outputs(outputs), "execution_count": None})
            side["cells"][cid] = {"origin": "assistant" if c.get("origin") == "assistant" else "user",
                                  "model": c.get("model", ""), "approved": c.get("approved"),
                                  "note": c.get("note", ""),
                                  "versions": (c.get("versions") or [])[-MAX_VERSIONS:],
                                  "runs": [{k: r.get(k) for k in ("id", "t", "status", "seconds", "device",
                                                                  "code_hash")} for r in runs][-MAX_RUNS:]}
        self.write(pid, DEFAULT_DOC, nb)
        self.save_side(pid, DEFAULT_DOC, side)
        old.rename(old.with_name(old.name + ".migrated"))
        return True

    # ------------------------------------------------------------ view
    def view(self, pid: str, doc: str, kernel: str = "") -> dict:
        nb = self.read(pid, doc)
        side = self.side(pid, doc)
        language = nb_language(nb)
        cells, hashes = [], []
        execs: list[tuple[int, int]] = []        # (index in cells, execution count) of cells run in this kernel
        for c in nb["cells"]:
            kind = cell_kind(c)
            m = (c.get("metadata") or {}).get("madalean") or {}
            s = side["cells"].get(c["id"], {})
            src = _text(c.get("source"))
            v = {"id": c["id"], "type": kind, "language": language, "source": src, "collapsed":
                 bool(m.get("collapsed") or (c.get("metadata") or {}).get("collapsed")),
                 "outputs_hidden": bool((c.get("metadata") or {}).get("jupyter", {}).get("outputs_hidden"))}
            if kind in ("code", "ask"):
                h = code_hash(src)
                origin = "assistant" if (s.get("origin") == "assistant" or m.get("origin") == "assistant"
                                         or kind == "ask") else "user"
                run = m.get("run") or None
                up = upstream_hash(hashes)
                stale, reason = False, ""
                if run and c.get("outputs") is not None:
                    if run.get("code_hash") and run["code_hash"] != h:
                        stale, reason = True, "code"
                    elif run.get("upstream") and run["upstream"] != up:
                        stale, reason = True, "upstream"
                ec = c.get("execution_count")
                if run and kernel and run.get("kernel") == kernel and isinstance(ec, int):
                    if any(e > ec for _i, e in execs) and not stale:
                        stale, reason = True, "order"
                    execs.append((len(cells), ec))
                v.update({"code": src, "code_hash": h, "origin": origin, "model": s.get("model", ""),
                          "approved": s.get("approved"), "prompt": m.get("prompt", "") or s.get("note", ""),
                          "note": s.get("note", "") or m.get("prompt", ""),
                          "versions": s.get("versions") or [{"code": src, "t": 0, "origin": origin}],
                          "runs": s.get("runs") or [], "exec_count": ec,
                          "outputs": view_outputs(c.get("outputs") or [], self.assets, (pid, doc)),
                          "last": run, "stale": stale, "stale_reason": reason,
                          "fresh": bool(run and kernel and run.get("kernel") == kernel),
                          "autofix": s.get("autofix"), "uses": s.get("uses") or [],
                          # S-AG (D39): what the request was recognized as, its intent key, where the code came from
                          "intent_key": s.get("intent_key") or "", "recognized": s.get("recognized"),
                          "gen": s.get("gen") or ""})
                hashes.append(h)
            elif kind == "figure":
                v["figure"] = m.get("figure")
                svg = ((c.get("attachments") or {}).get("figure.svg") or {}).get("image/svg+xml")
                if svg:
                    try:
                        raw = base64.b64decode(_text(svg))
                        aid = asset_id(raw)
                        self.assets[aid] = (pid, doc)
                        v["svg"] = {"asset": aid}
                    except ValueError:
                        pass
            cells.append(v)
        m = (nb.get("metadata") or {}).get("madalean") or {}
        p = self.path(pid, doc)
        return {"doc": {"id": doc, "title": m.get("title") or doc, "language": language,
                        "path": self.rel_path(pid, doc), "rev": p.stat().st_mtime_ns,
                        "engine": m.get("engine")},
                "cells": cells, "trash": [{"id": t["cell"]["id"], "source": _text(t["cell"].get("source"))[:200]}
                                          for t in side["trash"]][-5:]}

    def cell_view(self, pid: str, doc: str, cid: str, kernel: str = "") -> dict:
        v = self.view(pid, doc, kernel)
        c = next((x for x in v["cells"] if x["id"] == cid), None)
        if c is None:
            raise CalcError("not_found", 404)
        return c

    # ------------------------------------------------------------ cells
    @staticmethod
    def _find(nb: dict, cid: str) -> dict:
        c = next((c for c in nb["cells"] if c.get("id") == cid), None)
        if c is None:
            raise CalcError("not_found", 404)
        return c

    def _figure_cell(self, cell: dict, figure: dict, svg: str, title: str = "") -> None:
        if not isinstance(figure, dict) or len(json.dumps(figure)) > MAX_FIGURE:
            raise CalcError("bad_figure")
        cell["metadata"].setdefault("madalean", {}).update({"kind": "figure", "figure": figure})
        label = re.sub(r"[\[\]\n]", " ", title or str(figure.get("title") or "Figure"))[:120]
        cell["source"] = f"![{label}](attachment:figure.svg)"
        if svg:
            try:
                clean = sanitize_svg(svg)
            except CalcError:
                clean = ""
            if clean and len(clean) <= 3_000_000:
                cell["attachments"] = {"figure.svg": {"image/svg+xml": base64.b64encode(clean.encode()).decode()}}

    def add(self, pid: str, code: str = "", language: str = "", origin: str = "user", *, after: str = "",
            note: str = "", model: str = "", doc: str = DEFAULT_DOC, kind: str = "code", prompt: str = "",
            figure: dict | None = None, svg: str = "", at: int | None = None) -> dict:
        """A new cell. `CalcStore.add`-compatible positional form (pid, code, language, origin) adds a code cell to
        the project's default document (used by the article editor's « Exemple avec Sage »)."""
        if kind not in KINDS:
            raise CalcError("bad_kind")
        if len(code) > MAX_SOURCE or len(prompt) > 4000:
            raise CalcError("too_large", 413)
        if doc == DEFAULT_DOC:
            self.docs(pid)                         # creates / migrates the default document
        origin = "assistant" if origin == "assistant" else "user"
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            if language and language in LANGS and language != nb_language(nb) and not nb["cells"]:
                nb = new_nb(language, ((nb.get("metadata") or {}).get("madalean") or {}).get("title", "Calcul"))
            if len(nb["cells"]) >= MAX_CELLS:
                raise CalcError("too_many", 413)
            cid = secrets.token_hex(4)
            meta: dict = {"kind": kind}
            if kind == "ask":
                meta["prompt"] = prompt[:4000]
                origin = "assistant"
            if origin == "assistant":
                meta["origin"] = "assistant"
            if kind in ("code", "ask"):
                cell = {"cell_type": "code", "id": cid, "metadata": {"madalean": meta}, "source": code,
                        "outputs": [], "execution_count": None}
            else:
                cell = {"cell_type": "markdown", "id": cid, "metadata": {"madalean": meta}, "source": code}
                if kind == "figure":
                    self._figure_cell(cell, figure or {"v": 1, "view": {"xmin": -10, "xmax": 10, "ymin": -6,
                                                                         "ymax": 6}, "curves": [], "objects": []},
                                      svg)
            if at is not None:
                idx = max(0, min(int(at), len(nb["cells"])))
            else:
                idx = next((i + 1 for i, c in enumerate(nb["cells"]) if c["id"] == after), len(nb["cells"]))
            nb["cells"].insert(idx, cell)
            self.write(pid, doc, nb)
            if kind in ("code", "ask"):
                side = self.side(pid, doc)
                side["cells"][cid] = {"origin": origin, "model": model if origin == "assistant" else "",
                                      "approved": None, "note": (note or prompt)[:2000],
                                      "versions": [{"code": code, "t": _now(), "origin": origin}] if code else [],
                                      "runs": []}
                self.save_side(pid, doc, side)
        return self.cell_view(pid, doc, cid)

    def edit(self, pid: str, cid: str, *, code: str | None = None, language: str | None = None, by: str = "user",
             model: str = "", note: str | None = None, doc: str = DEFAULT_DOC, prompt: str | None = None,
             figure: dict | None = None, svg: str = "", kind: str | None = None,
             collapsed: bool | None = None, outputs_hidden: bool | None = None, vinfo: dict | None = None) -> dict:
        """`vinfo`: shown with the new version in the cell's history (S-AN: who corrected it and what it cost)."""
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            c = self._find(nb, cid)
            c.setdefault("metadata", {})
            m = c["metadata"].setdefault("madalean", {})
            cur = cell_kind(c)
            side = self.side(pid, doc)
            s = side["cells"].setdefault(cid, {"origin": "assistant" if m.get("origin") == "assistant" else "user",
                                               "model": "", "approved": None, "note": "", "versions": [],
                                               "runs": []})
            if kind is not None and kind != cur:          # M / Y in the UI: code <-> markdown; S-AB: <-> request
                if kind == "markdown" and cur in ("code", "ask"):
                    c["cell_type"] = "markdown"
                    c.pop("outputs", None)
                    c.pop("execution_count", None)
                    m["kind"] = "markdown"
                    m.pop("prompt", None)
                elif kind == "code" and cur in ("markdown", "ask"):
                    if cur == "markdown":
                        c.update(cell_type="code", outputs=[], execution_count=None)
                    m["kind"] = "code"                # code a model wrote stays « assistant » (approval unchanged)
                    m.pop("prompt", None)
                elif kind == "ask" and cur in ("code", "markdown"):
                    # what was typed becomes the request (unless one is given); the code is written by the model
                    text = _text(c.get("source"))
                    c.update(cell_type="code", source="", outputs=c.get("outputs") if cur == "code" else [],
                             execution_count=c.get("execution_count"))
                    m["kind"] = "ask"
                    m["prompt"] = (prompt if prompt is not None else text)[:4000]
                    s["autofix"] = None
                else:
                    raise CalcError("bad_kind")
                cur = kind
            if code is not None and code != _text(c.get("source")):
                if len(code) > MAX_SOURCE:
                    raise CalcError("too_large", 413)
                c["source"] = code
                if cur in ("code", "ask"):
                    if by == "assistant":
                        s["origin"], s["model"], m["origin"] = "assistant", model, "assistant"
                    # a model's code stays « assistant » after a user edit; any approval was for the old code
                    s["approved"] = None
                    s["versions"] = (s.get("versions") or [])[-(MAX_VERSIONS - 1):] + [
                        {"code": code, "t": _now(), "origin": by, **({"fix": dict(vinfo)} if vinfo else {})}]
            if prompt is not None and cur == "ask":
                m["prompt"] = prompt[:4000]
                s["autofix"] = None
            if note is not None:
                s["note"] = note[:2000]
            if figure is not None and cur == "figure":
                self._figure_cell(c, figure, svg)
            if collapsed is not None:
                m["collapsed"] = bool(collapsed)
            if outputs_hidden is not None:
                c["metadata"].setdefault("jupyter", {})["outputs_hidden"] = bool(outputs_hidden)
            if language is not None and language in LANGS and language != nb_language(nb):
                if any(cell_kind(x) in ("code", "ask") and _text(x.get("source")).strip() for x in nb["cells"]):
                    raise CalcError("language_fixed", 409)    # one kernel per document
                nb["metadata"].update({k: v for k, v in new_nb(language, "")["metadata"].items()
                                       if k in ("kernelspec", "language_info")})
                nb["metadata"].setdefault("madalean", {})["language"] = language
            self.write(pid, doc, nb)
            self.save_side(pid, doc, side)
        return self.cell_view(pid, doc, cid)

    def delete(self, pid: str, cid: str, doc: str = DEFAULT_DOC) -> dict:
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            c = self._find(nb, cid)
            nb["cells"] = [x for x in nb["cells"] if x["id"] != cid]
            side = self.side(pid, doc)
            side["trash"] = (side["trash"] + [{"cell": c, "meta": side["cells"].pop(cid, None), "t": _now()}])[-MAX_TRASH:]
            self.write(pid, doc, nb)
            self.save_side(pid, doc, side)
        return {"id": cid}

    def restore(self, pid: str, cid: str, doc: str = DEFAULT_DOC) -> dict:
        with self.lock(pid, doc):
            side = self.side(pid, doc)
            t = next((x for x in side["trash"] if x["cell"].get("id") == cid), None)
            if t is None:
                raise CalcError("not_found", 404)
            nb = self.read(pid, doc)
            nb["cells"].append(t["cell"])
            side["trash"] = [x for x in side["trash"] if x is not t]
            if t.get("meta"):
                side["cells"][cid] = t["meta"]
            self.write(pid, doc, nb)
            self.save_side(pid, doc, side)
        return self.cell_view(pid, doc, cid)

    def move(self, pid: str, cid: str, to: int, doc: str = DEFAULT_DOC) -> list[str]:
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            c = self._find(nb, cid)
            nb["cells"].remove(c)
            nb["cells"].insert(max(0, min(int(to), len(nb["cells"]))), c)
            self.write(pid, doc, nb)
            return [x["id"] for x in nb["cells"]]

    def approve(self, pid: str, cid: str, h: str, device: str, doc: str = DEFAULT_DOC) -> dict:
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            c = self._find(nb, cid)
            if h != code_hash(_text(c.get("source"))):
                raise CalcError("stale_code", 409)       # the code changed since the user read it
            side = self.side(pid, doc)
            s = side["cells"].setdefault(cid, {"origin": "assistant", "versions": [], "runs": []})
            s["approved"] = {"hash": h, "t": _now(), "device": device}
            self.save_side(pid, doc, side)
        return self.cell_view(pid, doc, cid)

    @staticmethod
    def may_run(cell: dict, auto: bool) -> bool:
        """The approval boundary (unchanged from S-M): user code runs; model code only once this exact code was
        approved on this host, or when the host enabled `experiments_auto`."""
        if cell.get("origin") != "assistant":
            return True
        return (cell.get("approved") or {}).get("hash") == cell["code_hash"] or auto

    def set_autofix(self, pid: str, doc: str, cid: str, value: dict | None) -> None:
        with self.lock(pid, doc):
            side = self.side(pid, doc)
            side["cells"].setdefault(cid, {"origin": "assistant", "versions": [], "runs": []})["autofix"] = value
            self.save_side(pid, doc, side)

    def set_side(self, pid: str, doc: str, cid: str, **values) -> None:
        """Host-only facts of a cell (S-AB: `uses` — names of earlier cells the model's code relies on)."""
        with self.lock(pid, doc):
            side = self.side(pid, doc)
            side["cells"].setdefault(cid, {"origin": "assistant", "versions": [], "runs": []}).update(values)
            self.save_side(pid, doc, side)

    def set_engine(self, pid: str, doc: str, engine: dict) -> None:
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            m = nb.setdefault("metadata", {}).setdefault("madalean", {})
            if m.get("engine") != engine:
                m["engine"] = engine
                self.write(pid, doc, nb)

    def upstream_of(self, pid: str, doc: str, cid: str) -> str:
        nb = self.read(pid, doc)
        hashes = []
        for c in nb["cells"]:
            if c["id"] == cid:
                return upstream_hash(hashes)
            if cell_kind(c) in ("code", "ask"):
                hashes.append(code_hash(_text(c.get("source"))))
        raise CalcError("not_found", 404)

    # ------------------------------------------------------------ runs
    def record_run(self, pid: str, cid: str, res, device: str, ran_hash: str, *, doc: str = DEFAULT_DOC,
                   kernel: str = "", upstream: str = "", approx: str = "") -> dict:
        outputs = clean_outputs(getattr(res, "outputs", None) or [])
        if res.status != "ok" and not any(o["output_type"] == "error" for o in outputs):
            # timeout, output limit, kernel unavailable or dead: said in the notebook like any error
            outputs.append({"output_type": "error", "ename": res.status,
                            "evalue": (getattr(res, "error", "") or res.status)[:4000], "traceback": []})
        if approx:
            for o in outputs:
                if o["output_type"] == "execute_result":
                    o["metadata"]["madalean"] = {"approx": approx[:400]}
        meta = {"status": res.status, "seconds": round(res.seconds, 2), "t": _now(), "code_hash": ran_hash,
                "upstream": upstream, "kernel": kernel, "device": device}
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            c = self._find(nb, cid)
            c["outputs"] = outputs
            c["execution_count"] = res.execution_count if isinstance(res.execution_count, int) else None
            c.setdefault("metadata", {}).setdefault("madalean", {})["run"] = {k: v for k, v in meta.items()
                                                                              if k != "device"}
            self.write(pid, doc, nb)
            side = self.side(pid, doc)
            s = side["cells"].setdefault(cid, {"origin": "user", "versions": [], "runs": []})
            run = {"id": "r-" + secrets.token_hex(4), **meta, "exec": c["execution_count"]}
            s["runs"] = (s.get("runs") or [])[-(MAX_RUNS - 1):] + [run]
            self.save_side(pid, doc, side)
        return {**run, **run_summary(outputs), "sandbox": getattr(res, "sandbox", ""),
                "language": getattr(res, "language", ""), "outputs": view_outputs(outputs, self.assets, (pid, doc))}

    def clear_outputs(self, pid: str, doc: str) -> None:
        with self.lock(pid, doc):
            nb = self.read(pid, doc)
            for c in nb["cells"]:
                if c.get("cell_type") == "code":
                    c["outputs"], c["execution_count"] = [], None
                    (c.get("metadata") or {}).get("madalean", {}).pop("run", None)
            self.write(pid, doc, nb)

    # ------------------------------------------------------------ assets (content-addressed, inside the .ipynb)
    def _scan(self, pid: str, doc: str, aid: str) -> tuple[bytes, str] | None:
        try:
            nb = self.read(pid, doc)
        except CalcError:
            return None
        for c in nb["cells"]:
            for o in c.get("outputs") or []:
                for mime in ("image/png", "image/svg+xml"):
                    v = (o.get("data") or {}).get(mime)
                    if v is None:
                        continue
                    raw = _png(_text(v)) if mime == "image/png" else _text(v).encode()
                    if raw and asset_id(raw) == aid:
                        return raw, mime
            svg = ((c.get("attachments") or {}).get("figure.svg") or {}).get("image/svg+xml")
            if svg:
                try:
                    raw = base64.b64decode(_text(svg))
                except ValueError:
                    continue
                if asset_id(raw) == aid:
                    return raw, "image/svg+xml"
        return None

    def asset(self, aid: str) -> tuple[bytes, str] | None:
        if not re.fullmatch(r"[0-9a-f]{32}", aid or ""):
            return None
        where = self.assets.get(aid)
        if where:
            hit = self._scan(where[0], where[1], aid)
            if hit:
                return hit
        root = self.nb_root / "calcul"
        for p in sorted(root.glob("*/*.ipynb")) if root.is_dir() else []:
            if not (PID_RE.match(p.parent.name) and DOC_RE.match(p.stem)):
                continue
            hit = self._scan(p.parent.name, p.stem, aid)
            if hit:
                self.assets[aid] = (p.parent.name, p.stem)
                return hit
        if self.legacy is not None:                       # S-M worksheets not migrated yet
            found = self.legacy.asset_path(aid)
            if found:
                return found[0].read_bytes(), found[1]
        return None

    def asset_path(self, aid: str, cache: Path | None = None) -> tuple[Path, str] | None:
        """`CalcStore.asset_path` compatibility (article editor: insert a Calcul plot as a figure): the image bytes
        are written to a cache file named by their content address."""
        if self.legacy is not None:
            found = self.legacy.asset_path(aid)
            if found:
                return found
        hit = self.asset(aid)
        if hit is None:
            return None
        raw, mime = hit
        d = Path(cache or (self.meta_root / ".export-cache"))
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{aid}.{'png' if mime == 'image/png' else 'svg'}"
        if not p.exists():
            p.write_bytes(raw)
        return p, mime

    # ------------------------------------------------------------ S-M worksheet shape (other plugins)
    def load(self, pid: str) -> dict:
        """The default document in the S-M worksheet shape {project_id, cells, rev}: each cell's last run carries
        stdout / result / error / rich (assets) derived from the notebook outputs."""
        self.docs(pid)
        v = self.view(pid, DEFAULT_DOC)
        nb = self.read(pid, DEFAULT_DOC)
        raw = {c["id"]: c for c in nb["cells"]}
        cells = []
        for c in v["cells"]:
            if c["type"] not in ("code", "ask"):
                continue
            runs = list(c.get("runs") or [])
            if runs:
                runs[-1] = {**runs[-1], **run_summary(raw[c["id"]].get("outputs") or [])}
            cells.append({**c, "runs": runs})
        return {"project_id": pid, "cells": cells, "rev": v["doc"]["rev"]}

    # ------------------------------------------------------------ context for the model
    def context(self, pid: str, doc: str, upto: str = "", limit: int = 12) -> str:
        """A compact summary of the cells above `upto` (code + cut outputs) for the natural-language cell."""
        nb = self.read(pid, doc)
        parts = []
        for c in nb["cells"]:
            if c["id"] == upto:
                break
            k = cell_kind(c)
            if k in ("code", "ask"):
                src = _text(c.get("source")).strip()
                if src:
                    out = outputs_text(c.get("outputs") or [], 300)
                    parts.append(f"In [{c.get('execution_count') or ' '}]: {src[:800]}" + (f"\nOut: {out}" if out else ""))
            elif k == "markdown":
                t = _text(c.get("source")).strip()
                if t:
                    parts.append("# " + t[:300].replace("\n", " "))
        return "\n\n".join(parts[-limit:])


def static_names(sources: list[str]) -> list[list[str]]:
    """Names assigned by earlier cells when no kernel is running (Sage preparsing aside: best effort)."""
    names: dict[str, str] = {}
    for src in sources:
        s = re.sub(r"\^", "**", src)
        s = re.sub(r"(?m)^\s*([A-Za-z_]\w*)\.<([\w, ]+)>\s*=", r"\1 =", s)   # Sage: R.<x> = PolynomialRing(QQ)
        try:
            tree = ast.parse(s)
        except SyntaxError:
            for m in re.finditer(r"(?m)^\s*([A-Za-z_]\w*)\s*=(?!=)", src):
                names[m.group(1)] = "?"
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names[node.name] = "function"
            elif isinstance(node, ast.ClassDef):
                names[node.name] = "class"
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            val = getattr(node, "value", None)
                            names[n.id] = type(val).__name__ if val is not None else "?"
    return [[k, v, ""] for k, v in names.items() if not k.startswith("_")][:60]


# ================================================================ helpers run once per kernel (Madalean's own code)
NB_PREAMBLE = r'''
import json as _mjson
_MADALEAN_BASE = None
def _madalean_vars(limit=40):
    """Madalean: compact summary of the names defined by the notebook (for the natural-language cell)."""
    import types as _t
    out = []
    for k, v in list(globals().items()):
        if k.startswith('_') or k in (_MADALEAN_BASE or ()) or k in ('In', 'Out', 'exit', 'quit', 'get_ipython'):
            continue
        if isinstance(v, _t.ModuleType):
            continue
        try:
            r = repr(v)
        except Exception:
            r = '?'
        out.append([k, type(v).__name__, r[:80]])
        if len(out) >= limit:
            break
    print('MADALEAN_VARS ' + _mjson.dumps(out))

def _madalean_approx(v):
    """Madalean: decimal value of an exact result ('' when there is none) — the « exact / approché » toggle."""
    import sys as _s
    if 'sage.all' not in _s.modules:              # a Python kernel never loads Sage just for this
        import fractions
        return repr(float(v)) if isinstance(v, fractions.Fraction) else ''
    from sage.all import N
    if isinstance(v, (bool, str)) or v is None:
        return ''
    try:
        a = N(v, digits=15)
    except Exception:
        return ''
    s = str(a)
    return '' if s == str(v) else s

def _madalean_latex(v):
    """Madalean: LaTeX of a Sage result, rendered by KaTeX in Madalean and MathJax in JupyterLab ('' = none)."""
    import sys as _s
    if 'sage.all' not in _s.modules or v is None or isinstance(v, (bool, str)):
        return ''
    if type(v).__module__.startswith(('sage.plot', 'sage.graphs', 'sage.repl')):
        return ''
    try:
        from sage.all import latex
        t = str(latex(v))
    except Exception:
        return ''
    return t if t and t != str(v) and len(t) < 20000 else ''

def fig(*objs, xmin=None, xmax=None, ymin=None, ymax=None, title=''):
    """Madalean: draw in an interactive figure (curves, equations, points, graphs). Examples:
    fig(sin(x)/x) · fig(x^2 + y^2 == 4) · fig('r=1+cos(θ)') · fig([(0,0), (1,2)]) · fig(graphs.PetersenGraph())"""
    import re as _re
    spec = {"v": 1, "curves": [], "objects": [], "points": [], "title": str(title)[:200]}
    def _s(e):
        s = str(e).replace('**', '^')
        return _re.sub(r'\barc(sin|cos|tan)\b', r'a\1', s)
    def _pt(p, label=None):
        d = {"x": float(p[0]), "y": float(p[1])}
        if label is not None:
            d["label"] = str(label)[:40]
        spec["points"].append(d)
    for o in objs:
        if isinstance(o, str):
            spec["curves"].append({"id": "c%d" % len(spec["curves"]), "expr": o[:2000]})
        elif hasattr(o, 'vertices') and hasattr(o, 'edges') and hasattr(o, 'layout'):
            pos = o.layout()
            spec["graph"] = {"vertices": [str(v) for v in o.vertices(sort=False)][:500],
                             "edges": [[str(a), str(b)] + ([w] if isinstance(w, (int, float)) else
                                                           ([str(w)] if w is not None else []))
                                       for a, b, w in o.edges(sort=False)][:3000],
                             "pos": {str(k): [float(p[0]), float(p[1])] for k, p in pos.items()},
                             "directed": bool(o.is_directed())}
        elif hasattr(o, 'is_relational') and o.is_relational():
            spec["curves"].append({"id": "c%d" % len(spec["curves"]), "expr": _s(o.lhs()) + "=" + _s(o.rhs())})
        elif isinstance(o, (tuple, list)) and len(o) == 2 and all(hasattr(t, '__float__') for t in o) \
                and not any(isinstance(t, (tuple, list)) for t in o):
            _pt(o)
        elif isinstance(o, (tuple, list)):
            for p in o:
                _pt(p)
        elif hasattr(o, 'variables') or hasattr(o, '__call__'):
            spec["curves"].append({"id": "c%d" % len(spec["curves"]), "expr": _s(o)})
        else:
            raise TypeError("fig(): cannot draw %s" % type(o).__name__)
    xs = [p["x"] for p in spec["points"]] + [p[0] for p in (spec.get("graph") or {}).get("pos", {}).values()]
    ys = [p["y"] for p in spec["points"]] + [p[1] for p in (spec.get("graph") or {}).get("pos", {}).values()]
    if xs and not spec["curves"]:
        w = max(max(xs) - min(xs), max(ys) - min(ys), 1) * 0.15
        v = {"xmin": min(xs) - w, "xmax": max(xs) + w, "ymin": min(ys) - w, "ymax": max(ys) + w}
    else:
        v = {"xmin": -10, "xmax": 10, "ymin": -6, "ymax": 6}
    for k, val in (("xmin", xmin), ("xmax", xmax), ("ymin", ymin), ("ymax", ymax)):
        if val is not None:
            v[k] = float(val)
    spec["view"] = v
    from IPython.display import display as _d
    _d({"application/vnd.madalean.figure+json": spec,
        "text/plain": "Figure: %d curve(s), %d point(s)%s" % (len(spec["curves"]), len(spec["points"]),
                                                              ", 1 graph" if "graph" in spec else "")}, raw=True)

import sys as _msys
if 'sage.all' in _msys.modules:                   # the Sage kernel (a Python kernel never imports Sage here)
    import sage.plot.plot3d.base as _mb3
    _mb3.SHOW_DEFAULTS['viewer'] = 'tachyon'      # 3D as a static image (never the three.js page)
    from sage.version import version as _mver
    print('MADALEAN_ENGINE ' + _mjson.dumps({"name": "SageMath", "version": _mver}))
else:
    print('MADALEAN_ENGINE ' + _mjson.dumps({"name": "Python", "version": _msys.version.split()[0]}))
_MADALEAN_BASE = set(globals())
'''
ENGINE_RE = re.compile(r"^MADALEAN_ENGINE (\{.*\})\s*$", re.M)
VARS_RE = re.compile(r"^MADALEAN_VARS (\[.*\])\s*$", re.M)


# ================================================================ natural language → Sage
# S-AB (DECISIONS D35): the system prompt is FIXED for a language + tool version (rules + the verified syntax card,
# madalean/syntaxcards.py) so providers can cache it; everything that changes (names, earlier cells, request,
# signatures) is in the user message, kept short (≈ 1–2 k characters): the transcription must start in seconds.
ASK_SYSTEM = (
    "You translate a mathematician's request into ONE short {lang} code cell of a computation notebook (earlier "
    "cells already ran in the SAME kernel: reuse their variables). Answer with ONLY one fenced code block "
    "(```{tag}), no prose before or after.\n"
    "Rules: deterministic; no network, no files outside the working directory, no infinite loops; the last line is "
    "an expression whose value is the answer (it is displayed), or print it; plots: return the Graphics object "
    "(plot(...), implicit_plot(...), parametric_plot(...), polar_plot(...), G.plot(...)); 3D: plot3d(...); an "
    "interactive figure the user can edit: fig(expr_or_equation_or_graph, ...); a formula: tex(x).{card}")
ASK_TASK = (
    "Translate the request into ONE short {lang} code cell (```{tag} block only).\n"
    "Defined names (name, type, value excerpt):\n{names}\n\nEarlier cells (most recent last):\n{context}\n"
    "{sigs}{example}\nRequest: {prompt}")
ASK_FIX = (
    "The cell you wrote failed. Return ONLY one fenced code block (```{tag}) with a corrected cell, same intent.\n\n"
    "Request: {prompt}\n\nCell:\n```{tag}\n{code}\n```\n\nError:\n{error}\n\nDefined names:\n{names}\n{sigs}")
ASK_CONTEXT = 2500


def ask_messages(lang: str, language: str, prompt: str, names: list, context: str, *, fix: bool = False,
                 code: str = "", error: str = "", card: str = "", sigs: str = "", example: str = "",
                 prefix: str = "", avoid: list[dict] | None = None, other: str = "") -> list[dict]:
    """`card`: the syntax card of the installed tool version (system prompt, cacheable); `sigs`: exact signatures
    of the functions this request needs (installed Sage). `lang` (UI language) does not change the prompt: the
    code is the same in French and English, and one system prompt per tool version caches better.
    S-AG (D39): `prefix` — the canonical constructions of the recognized objects (catalogue), the cell MUST start
    with them; `avoid` — earlier versions of this request that failed when run; `other` — the current best version
    (« Autre version »: write a different one)."""
    name = "SageMath" if language == "sage" else "Python 3"
    tag = "sage" if language == "sage" else "python"
    ns = "\n".join(f"- {n} : {t}" + (f" = {r}" if r else "") for n, t, r in (names or [])[:40]) or "- (none)"
    sg = f"\nExact signatures in the installed version:\n{sigs}\n" if sigs else ""
    ex = (f"\nA recipe that already worked on this installation for a similar request (adapt it):\n{example}\n"
          if example else "")
    body = (ASK_FIX if fix else ASK_TASK).format(lang=name, tag=tag, names=ns,
                                                 context=context[-ASK_CONTEXT:] or "(none)", prompt=prompt[:4000],
                                                 code=code[:20000], error=error[-3000:], sigs=sg, example=ex)
    if prefix:
        body += (f"\n\nThe cell MUST start with exactly these lines (canonical constructions of the objects of the "
                 f"request, already checked on this installation; keep these names, do not redefine them):\n"
                 f"```{tag}\n{prefix}\n```")
    for a in (avoid or [])[:3]:
        body += (f"\n\nThis earlier version FAILED when run; do not write it again:\n```{tag}\n{a['code'][:1500]}\n```"
                 + (f"\nError: {a['error'][-300:]}" if a.get("error") else ""))
    if other:
        body += (f"\n\nThe user asked for ANOTHER version: write a different correct cell than this one (another "
                 f"method or presentation), same result:\n```{tag}\n{other[:3000]}\n```")
    system = ASK_SYSTEM.format(lang=name, tag=tag, card=f"\n\n{card}" if card else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": body}]


# ================================================================ publication.json « computations » (for S-Q)
def publication_computations(store: NotebookStore, pid: str, files_dir: Path | None = None,
                             docs: list[str] | None = None) -> dict | None:
    """The `computations` section of publication.json (docs/SITE.md §4): every Calcul document of the project with
    its cells in order — code (and the natural-language request), outputs (text, LaTeX, images, figures), whether a
    result is out of date — and the engine version. Images are written once, content-addressed, as
    `files/calcul/<id>.png|svg` (written into `files_dir`, the publication's `DIR/files`), with the .ipynb itself
    (`files/calcul/<doc>.ipynb`, downloadable and re-runnable). Returns None when the project has no computation."""
    out_docs = []
    engine = None
    for d in store.docs(pid):
        if docs is not None and d["id"] not in docs:
            continue
        v = store.view(pid, d["id"])
        if not any((c.get("source") or "").strip() for c in v["cells"]):
            continue
        engine = engine or v["doc"].get("engine")
        nb_rel = f"files/calcul/{d['id']}.ipynb"
        if files_dir is not None:
            dst = Path(files_dir) / "calcul"
            dst.mkdir(parents=True, exist_ok=True)
            (dst / f"{d['id']}.ipynb").write_bytes(store.path(pid, d["id"]).read_bytes())
        cells = []
        for c in v["cells"]:
            x: dict = {"id": c["id"], "kind": c["type"]}
            if c["type"] in ("code", "ask"):
                x.update(code=c["code"], language=d["language"], execution_count=c.get("exec_count"),
                         origin=c["origin"], stale=bool(c.get("stale")),
                         status=(c.get("last") or {}).get("status", "not_run"))
                if c["type"] == "ask":
                    x["prompt"] = c.get("prompt", "")
                outs = []
                for o in c.get("outputs") or []:
                    if o["type"] == "stream":
                        outs.append({"kind": "text", "text": o["text"][:20000]})
                    elif o["type"] == "error":
                        outs.append({"kind": "error", "text": f"{o['ename']}: {o['evalue']}"[:4000]})
                    else:
                        dd = o["data"]
                        img = next((m for m in ("image/svg+xml", "image/png") if m in dd), None)
                        if img:
                            path = _export_asset(store, dd[img]["asset"], files_dir)
                            if path:
                                outs.append({"kind": "image", "path": path, "mime": img,
                                             "alt": dd.get("text/plain", "")[:300]})
                        elif FIGURE_MIME in dd:
                            outs.append({"kind": "figure", "spec": dd[FIGURE_MIME]})
                        elif "text/latex" in dd:
                            outs.append({"kind": "latex", "latex": dd["text/latex"][:20000],
                                         **({"text": dd["text/plain"][:20000]} if dd.get("text/plain") else {}),
                                         **({"approx": o["approx"]} if o.get("approx") else {})})
                        elif "text/plain" in dd:
                            outs.append({"kind": "text", "text": dd["text/plain"][:20000],
                                         **({"approx": o["approx"]} if o.get("approx") else {})})
                x["outputs"] = outs
            elif c["type"] == "figure":
                x["figure"] = {"spec": c.get("figure")}
                if c.get("svg"):
                    p = _export_asset(store, c["svg"]["asset"], files_dir)
                    if p:
                        x["figure"]["svg"] = p
            else:
                x["markdown"] = c["source"]
            cells.append(x)
        out_docs.append({"id": d["id"], "title": d["title"], "language": d["language"], "notebook": nb_rel,
                         "cells": cells})
    if not out_docs:
        return None
    return {"engine": engine or {"name": "SageMath", "version": ""}, "documents": out_docs}


def _export_asset(store: NotebookStore, aid: str, files_dir: Path | None) -> str | None:
    hit = store.asset(aid)
    if hit is None:
        return None
    raw, mime = hit
    rel = f"files/calcul/{aid}.{'png' if mime == 'image/png' else 'svg'}"
    if files_dir is not None:
        p = Path(files_dir) / "calcul" / rel.rsplit("/", 1)[1]
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(raw)
    return rel
