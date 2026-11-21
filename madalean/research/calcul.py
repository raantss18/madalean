"""« Calcul » — the integrated Sage / Python compute workspace (session S-M, user decision 2026-11-21).

One worksheet per project: an ordered list of cells (Sage or Python), each with its versions and its last runs
(text, LaTeX, plots). Cells run in the existing sandboxed, offline experiment kernel (sagebridge: allow-listed
environment, bubblewrap, no network, timeouts, output caps), one kernel per project so variables persist between
cells.

Approval rule (the same boundary as the conjecture workshop, docs/RESEARCH_WORKSHOP.md §Security):
- a cell the user typed (origin « user ») runs when the user asks;
- a cell written or changed by the assistant (origin « assistant ») runs only once the user approved that exact code
  (sha256 of the code), or when the host enabled `experiments_auto`. Editing an assistant cell keeps its origin and
  withdraws the approval: the user's edit of model code is reviewed like the code itself;
- from a paired device, execution needs the host-only setting `experiments_remote` (checked by the plugin).

Rich outputs: LaTeX is kept as text (rendered by KaTeX in the browser, never as HTML); PNG and SVG plots are stored
as files next to the worksheet and served by the plugin with a restrictive CSP; SVG is sanitised here (no script,
no event handler, no foreignObject, no external reference) and shown through <img>, where scripts never run."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
import uuid
from pathlib import Path

from .. import config

MAX_CELLS = 300
MAX_CODE = 100_000
MAX_VERSIONS = 20
MAX_RUNS = 8
LANGS = ("sage", "python")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class CalcError(Exception):
    def __init__(self, kind: str, status: int = 400):
        super().__init__(kind)
        self.kind, self.status = kind, status


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- SVG sanitising
_SVG_BAD_TAGS = "script|foreignObject|iframe|object|embed|audio|video|image|animate|set|handler|listener"
_SVG_PAIRED = re.compile(rf"<\s*({_SVG_BAD_TAGS})\b[^>]*>[\s\S]*?<\s*/\s*\1\s*>", re.I)
_SVG_SINGLE = re.compile(rf"<\s*/?\s*({_SVG_BAD_TAGS})\b[^>]*>", re.I)
_SVG_ON = re.compile(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_SVG_HREF = re.compile(r"\s+(xlink:)?href\s*=\s*(\"(?!#)[^\"]*\"|'(?!#)[^']*')", re.I)
_SVG_PI = re.compile(r"<!DOCTYPE[^\[>]*(\[[\s\S]*?\])?\s*>|<!ENTITY[\s\S]*?>|<\?xml-stylesheet[\s\S]*?\?>", re.I)
_SVG_CSS_URL = re.compile(r"url\(\s*['\"]?(?!#)[^)]*\)|@import[^;]*;|expression\s*\(", re.I)


def sanitize_svg(svg: str) -> str:
    """Remove everything active or external from an SVG (defence in depth: it is shown through <img> anyway)."""
    out = _SVG_PI.sub("", svg)
    prev = None
    while prev != out:
        prev = out
        out = _SVG_SINGLE.sub("", _SVG_PAIRED.sub("", out))
    out = _SVG_ON.sub("", out)
    out = _SVG_HREF.sub("", out)
    out = _SVG_CSS_URL.sub("none", out)
    out = re.sub(r"javascript\s*:", "", out, flags=re.I)
    if not re.search(r"<svg\b", out, re.I):
        raise CalcError("bad_svg")
    return out


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class CalcStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.assets = self.root / "assets"
        self._lock = threading.Lock()

    # ------------------------------------------------------------ files
    def _file(self, pid: str) -> Path:
        if not ID_RE.match(pid or ""):
            raise CalcError("bad_project")
        return self.root / f"{pid}.json"

    def load(self, pid: str) -> dict:
        try:
            data = json.loads(self._file(pid).read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("cells"), list):
                return data
        except (OSError, ValueError):
            pass
        return {"project_id": pid, "cells": [], "rev": 0}

    def _save(self, pid: str, sheet: dict) -> None:
        sheet["rev"] = int(sheet.get("rev", 0)) + 1
        self.root.mkdir(parents=True, exist_ok=True)
        config.atomic_write_text(self._file(pid), json.dumps(sheet, ensure_ascii=False))

    @staticmethod
    def _cell(sheet: dict, cid: str) -> dict:
        c = next((c for c in sheet["cells"] if c["id"] == cid), None)
        if c is None:
            raise CalcError("not_found", 404)
        return c

    # ------------------------------------------------------------ cells
    def add(self, pid: str, code: str, language: str, origin: str, *, after: str = "", note: str = "",
            model: str = "") -> dict:
        if language not in LANGS:
            raise CalcError("bad_language")
        if len(code) > MAX_CODE:
            raise CalcError("too_large", 413)
        now = time.time()
        cell = {"id": "c-" + uuid.uuid4().hex[:10], "language": language, "code": code, "code_hash": code_hash(code),
                "origin": "assistant" if origin == "assistant" else "user", "approved": None, "created": now,
                "updated": now, "model": model if origin == "assistant" else "", "note": note[:2000],
                "versions": [{"code": code, "t": now, "origin": origin}], "runs": []}
        with self._lock:
            sheet = self.load(pid)
            if len(sheet["cells"]) >= MAX_CELLS:
                raise CalcError("too_many", 413)
            idx = next((i + 1 for i, c in enumerate(sheet["cells"]) if c["id"] == after), len(sheet["cells"]))
            sheet["cells"].insert(idx, cell)
            self._save(pid, sheet)
        return cell

    def edit(self, pid: str, cid: str, *, code: str | None = None, language: str | None = None,
             by: str = "user", model: str = "", note: str | None = None) -> dict:
        with self._lock:
            sheet = self.load(pid)
            c = self._cell(sheet, cid)
            if language is not None:
                if language not in LANGS:
                    raise CalcError("bad_language")
                c["language"] = language
            if code is not None and code != c["code"]:
                if len(code) > MAX_CODE:
                    raise CalcError("too_large", 413)
                c["code"], c["code_hash"] = code, code_hash(code)
                if by == "assistant":
                    c["origin"], c["model"] = "assistant", model
                # a model's code stays « assistant » after a user edit, and any approval is for the old code
                c["approved"] = None
                c["versions"] = (c.get("versions") or [])[-(MAX_VERSIONS - 1):] + [
                    {"code": code, "t": time.time(), "origin": by}]
            if note is not None:
                c["note"] = note[:2000]
            c["updated"] = time.time()
            self._save(pid, sheet)
            return c

    def delete(self, pid: str, cid: str) -> dict:
        with self._lock:
            sheet = self.load(pid)
            c = self._cell(sheet, cid)
            sheet["cells"] = [x for x in sheet["cells"] if x["id"] != cid]
            sheet.setdefault("trash", []).append(c)
            sheet["trash"] = sheet["trash"][-20:]
            self._save(pid, sheet)
            return c

    def restore(self, pid: str, cid: str) -> dict:
        with self._lock:
            sheet = self.load(pid)
            c = next((x for x in sheet.get("trash", []) if x["id"] == cid), None)
            if c is None:
                raise CalcError("not_found", 404)
            sheet["trash"] = [x for x in sheet["trash"] if x["id"] != cid]
            sheet["cells"].append(c)
            self._save(pid, sheet)
            return c

    def move(self, pid: str, cid: str, to: int) -> dict:
        with self._lock:
            sheet = self.load(pid)
            c = self._cell(sheet, cid)
            sheet["cells"].remove(c)
            sheet["cells"].insert(max(0, min(int(to), len(sheet["cells"]))), c)
            self._save(pid, sheet)
            return sheet

    def approve(self, pid: str, cid: str, h: str, device: str) -> dict:
        with self._lock:
            sheet = self.load(pid)
            c = self._cell(sheet, cid)
            if h != c["code_hash"]:
                raise CalcError("stale_code", 409)       # the code changed since the user read it
            c["approved"] = {"hash": h, "t": time.time(), "device": device}
            self._save(pid, sheet)
            return c

    @staticmethod
    def may_run(cell: dict, auto: bool) -> bool:
        if cell.get("origin") != "assistant":
            return True
        return (cell.get("approved") or {}).get("hash") == cell["code_hash"] or auto

    # ------------------------------------------------------------ runs
    def _asset(self, mime: str, data: str) -> str | None:
        aid = uuid.uuid4().hex
        self.assets.mkdir(parents=True, exist_ok=True)
        try:
            if mime == "image/png":
                raw = base64.b64decode(data, validate=False)
                if not raw.startswith(PNG_MAGIC):
                    return None
                (self.assets / f"{aid}.png").write_bytes(raw)
            elif mime == "image/svg+xml":
                (self.assets / f"{aid}.svg").write_text(sanitize_svg(data), encoding="utf-8")
            else:
                return None
        except (ValueError, CalcError, OSError):
            return None
        return aid

    def asset_path(self, aid: str) -> tuple[Path, str] | None:
        if not re.fullmatch(r"[0-9a-f]{32}", aid or ""):
            return None
        for ext, mime in (("png", "image/png"), ("svg", "image/svg+xml")):
            p = self.assets / f"{aid}.{ext}"
            if p.is_file():
                return p, mime
        return None

    def record_run(self, pid: str, cid: str, res, device: str, ran_hash: str) -> dict:
        """Store an ExecResult (sagebridge) as the cell's latest run; plots become asset files."""
        rich = []
        for r in getattr(res, "rich", []) or []:
            if r.get("mime") == "text/latex":
                rich.append({"mime": "text/latex", "data": str(r.get("data", ""))[:200_000]})
            else:
                aid = self._asset(r.get("mime", ""), str(r.get("data", "")))
                if aid:
                    rich.append({"mime": r["mime"], "asset": aid})
        run = {"id": "r-" + uuid.uuid4().hex[:8], "t": time.time(), "status": res.status, "seconds": round(res.seconds, 2),
               "stdout": res.stdout, "stderr": res.stderr, "result": res.result, "error": res.error, "rich": rich,
               "device": device, "code_hash": ran_hash, "sandbox": res.sandbox, "language": res.language}
        with self._lock:
            sheet = self.load(pid)
            c = self._cell(sheet, cid)
            c["runs"] = (c.get("runs") or [])[-(MAX_RUNS - 1):] + [run]
            self._save(pid, sheet)
        return run


# ---------------------------------------------------------------- assistant prompts
SYSTEM = {
    "fr": "Tu aides un mathématicien dans un carnet de calcul {lang}. Réponds en français.",
    "en": "You help a mathematician in a {lang} computation notebook. Answer in English.",
}
TASK = {
    "write": "Write one code cell for this request. Return ONLY one fenced code block (```{tag}). Keep it short, "
             "deterministic, no network, no files outside the working directory, no infinite loops; print the "
             "result; use latex(...) only through the helper tex(x) when a formula is useful.\n\nRequest: {prompt}",
    "fix": "This cell failed. Return ONLY one fenced code block (```{tag}) with the corrected cell, same intent, "
           "no network.\n\nCell:\n```{tag}\n{code}\n```\n\nError:\n{error}\n\nUser note: {prompt}",
    "explain": "Explain what this cell computes and what its output means, in a few short paragraphs (Markdown, "
               "formulas in $…$). Say plainly what the computation does NOT prove.\n\nCell:\n```{tag}\n{code}\n"
               "```\n\nOutput:\n{output}\n\nQuestion: {prompt}",
}
FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n([\s\S]*?)```")


def assist_messages(action: str, language: str, lang: str, prompt: str = "", code: str = "", error: str = "",
                    output: str = "") -> list[dict]:
    name = "SageMath" if language == "sage" else "Python 3"
    tag = "sage" if language == "sage" else "python"
    return [{"role": "system", "content": SYSTEM.get(lang, SYSTEM["en"]).format(lang=name)},
            {"role": "user", "content": TASK[action].format(tag=tag, prompt=prompt[:4000] or "-", code=code[:20000],
                                                            error=error[:4000], output=output[:6000])}]


def extract_code(text: str) -> str:
    m = FENCE.search(text or "")
    return (m.group(2) if m else "").strip()


# helper available in every Calcul cell (after sagebridge's PREAMBLE)
CALC_PREAMBLE = r'''
def tex(x):
    """Madalean Calcul: show x as a formula (LaTeX rendered by KaTeX)."""
    try:
        from IPython.display import display as _d
        try:
            s = latex(x)            # Sage
        except NameError:
            s = str(x)
        _d({"text/latex": "$$" + str(s) + "$$", "text/plain": str(x)}, raw=True)
    except Exception:
        print(x)
'''


def output_text(run: dict) -> str:
    parts = [run.get("stdout", ""), run.get("result", "")]
    parts += [r["data"] for r in run.get("rich", []) if r.get("mime") == "text/latex"]
    if run.get("error"):
        parts.append(run["error"])
    return "\n".join(p for p in parts if p).strip()
