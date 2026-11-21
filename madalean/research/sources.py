"""Sources library (ARCHITECTURE §14): per project, plus a global shelf and Mathlib's read-only shelf.

A Source = bibliographic record (CSL-JSON, `research.biblio`) + a stable unique BibTeX key + optional files (PDF,
TeX / arXiv source archive, EPUB) + tags, collections, reading status, notes, annotations anchored to (page, quads)
or (chunk, text range), and full-text state.

Storage (single writer: the server):
    <config>/projects/<pid>/sources/          one shelf per project
    <config>/sources/                          the global shelf (shelf id "global")
        items/<sid>.json                       one record per source (atomic writes)
        files/<sha256>                         content-addressed blobs (0600), shared by the records of the shelf
        unpacked/<sha256>/                     safely extracted source archives (parsed, NEVER compiled)
        .trash/<sid>.json                      deleted records (undo)
        index.sqlite                           full-text index (research.fulltext)
Shelf "mathlib": Mathlib's `docs/references.bib` (read-only, records only)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from .. import config
from ..logs import get
from . import biblio
from .safety import MAX_UPLOAD, UnsafeInput, extract_archive, safe_rel, sniff

log = get("research.sources")
STATUSES = ("unread", "reading", "read", "to_read", "skimmed")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SID_RE = re.compile(r"^s-[0-9a-z]{6,24}$")
COLORS = ("yellow", "green", "blue", "pink", "purple", "red", "orange", "grey")
FILE_KINDS = ("pdf", "tex", "archive", "epub", "other")


class SourceError(Exception):
    def __init__(self, kind: str, status: int = 400, **info):
        super().__init__(kind)
        self.kind, self.status, self.info = kind, status, info


def new_id() -> str:
    return "s-" + uuid.uuid4().hex[:10]


def blank(item: dict, key: str) -> dict:
    now = time.time()
    return {"id": new_id(), "key": key, "csl": item, "files": [], "tags": [], "collections": [], "status": "unread",
            "notes": "", "annotations": [], "verified": True, "proposed": None, "origin": {}, "oa": {},
            "fulltext": {"state": "none"}, "added": now, "updated": now}


def summary(src: dict) -> dict:
    """What lists show (no annotations / notes body)."""
    it = src.get("csl") or {}
    return {"id": src["id"], "key": src["key"], "title": it.get("title", ""),
            "authors": biblio.format_names(it.get("author") or it.get("editor") or []), "year": biblio.year_of(it),
            "type": it.get("type", ""), "venue": it.get("container-title", ""), "doi": it.get("DOI", ""),
            "arxiv": it.get("arxiv", ""), "tags": src.get("tags", []), "collections": src.get("collections", []),
            "status": src.get("status", "unread"), "verified": src.get("verified", True),
            "has_pdf": any(f.get("kind") == "pdf" for f in src.get("files", [])),
            "has_tex": any(f.get("kind") in ("tex", "archive") for f in src.get("files", [])),
            "fulltext": (src.get("fulltext") or {}).get("state", "none"), "oa": src.get("oa") or {},
            "annotations": len(src.get("annotations", [])), "updated": src.get("updated", 0),
            "readonly": bool(src.get("readonly"))}


class Shelf:
    """One directory of sources (a project's, or the global one)."""

    def __init__(self, shelf_id: str, root: Path):
        self.id = shelf_id
        self.root = Path(root)
        self.items_dir = self.root / "items"
        self.files_dir = self.root / "files"
        self.unpacked_dir = self.root / "unpacked"
        self.trash = self.root / ".trash"
        self.cache: dict[str, dict] = {}
        self.loaded = False
        self.lock = asyncio.Lock()

    @property
    def index_path(self) -> Path:
        return self.root / "index.sqlite"

    def load(self) -> None:
        self.cache = {}
        if self.items_dir.is_dir():
            for p in self.items_dir.glob("s-*.json"):
                try:
                    src = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(src, dict) and SID_RE.match(str(src.get("id", ""))):
                        self.cache[src["id"]] = src
                except (OSError, ValueError):
                    log.warning("unreadable source record %s", p)
        self.loaded = True

    def list(self) -> list[dict]:
        return sorted(self.cache.values(), key=lambda s: -float(s.get("updated", 0)))

    def get(self, sid: str) -> dict | None:
        return self.cache.get(sid)

    def by_key(self, key: str) -> dict | None:
        return next((s for s in self.cache.values() if s.get("key") == key), None)

    def keys(self) -> set[str]:
        return {s["key"] for s in self.cache.values()}

    def save_sync(self, src: dict) -> None:
        if not SID_RE.match(src["id"]):
            raise SourceError("bad_id")
        src["updated"] = time.time()
        config.atomic_write_text(self.items_dir / f"{src['id']}.json", json.dumps(src, ensure_ascii=False, indent=1))
        self.cache[src["id"]] = src

    def put_blob(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        path = self.files_dir / sha
        if not path.exists():
            self.files_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.files_dir / f".{sha}.{uuid.uuid4().hex[:6]}.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        return sha

    def blob(self, sha: str) -> Path:
        if not SHA_RE.match(sha or ""):
            raise SourceError("bad_file")
        p = self.files_dir / sha
        if not p.is_file():
            raise SourceError("not_found", 404)
        return p

    def unpacked(self, sha: str) -> Path:
        """Extracted copy of an archive blob (extracted once, safely)."""
        if not SHA_RE.match(sha or ""):
            raise SourceError("bad_file")
        dest = self.unpacked_dir / sha
        if (dest / ".complete").exists():
            return dest
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        tmp = self.unpacked_dir / f".{sha}.{uuid.uuid4().hex[:6]}"
        extract_archive(self.blob(sha).read_bytes(), tmp)
        (tmp / ".complete").write_text("ok")
        os.replace(tmp, dest)
        return dest

    def delete_sync(self, sid: str) -> bool:
        p = self.items_dir / f"{sid}.json"
        if not p.exists():
            return False
        self.trash.mkdir(parents=True, exist_ok=True)
        os.replace(p, self.trash / f"{sid}.json")
        self.cache.pop(sid, None)
        return True

    def restore_sync(self, sid: str) -> dict | None:
        p = self.trash / f"{sid}.json"
        if not p.exists() or (self.items_dir / f"{sid}.json").exists():
            return None
        src = json.loads(p.read_text(encoding="utf-8"))
        self.items_dir.mkdir(parents=True, exist_ok=True)
        os.replace(p, self.items_dir / f"{sid}.json")
        self.cache[sid] = src
        return src

    def find_duplicate(self, item: dict, exclude: str = "") -> tuple[dict | None, str]:
        for s in self.cache.values():
            if s["id"] == exclude:
                continue
            why = biblio.same_work(s.get("csl") or {}, item)
            if why:
                return s, why
        return None, ""


# ================================================================ annotations / patches
def clean_annotation(a: dict, old: dict | None = None) -> dict:
    """Validated annotation: {id, page?, quads?: [[x0,y0,x1,y1,x2,y2,x3,y3]…], range?: {chunk, start, end},
    text, note, color, created, updated}. Coordinates are PDF points (page space), as pdf.js gives them."""
    if not isinstance(a, dict):
        raise SourceError("bad_annotation")
    out = dict(old or {})
    out.setdefault("id", "a-" + uuid.uuid4().hex[:10])
    out.setdefault("created", time.time())
    if "page" in a:
        if a["page"] is None:
            out["page"] = None
        elif isinstance(a["page"], int) and 1 <= a["page"] <= 100000:
            out["page"] = a["page"]
        else:
            raise SourceError("bad_annotation", field="page")
    if "quads" in a:
        q = a["quads"]
        if not isinstance(q, list) or len(q) > 400 or not all(
                isinstance(x, list) and len(x) in (4, 8) and all(isinstance(v, (int, float)) and abs(v) < 1e6
                                                                 for v in x) for x in q):
            raise SourceError("bad_annotation", field="quads")
        out["quads"] = [[round(float(v), 2) for v in x] for x in q]
    if "range" in a:
        r = a["range"]
        if r is None:
            out["range"] = None
        elif isinstance(r, dict) and isinstance(r.get("chunk"), str) and re.match(r"^c-[0-9a-f]{6,40}$", r["chunk"]) \
                and isinstance(r.get("start"), int) and isinstance(r.get("end"), int) and 0 <= r["start"] <= r["end"]:
            out["range"] = {"chunk": r["chunk"], "start": r["start"], "end": r["end"]}
        else:
            raise SourceError("bad_annotation", field="range")
    for k, lim in (("text", 5000), ("note", 20000)):
        if k in a:
            if not isinstance(a[k], str):
                raise SourceError("bad_annotation", field=k)
            out[k] = a[k][:lim]
    if "color" in a:
        if a["color"] not in COLORS:
            raise SourceError("bad_annotation", field="color")
        out["color"] = a["color"]
    out.setdefault("color", "yellow")
    out.setdefault("text", "")
    out.setdefault("note", "")
    if out.get("page") is None and not out.get("range"):
        raise SourceError("bad_annotation", field="anchor")
    out["updated"] = time.time()
    return out


def _str_list(v, limit: int = 50) -> list[str]:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise SourceError("bad_fields")
    return list(dict.fromkeys(x.strip()[:80] for x in v if x.strip()))[:limit]


def apply_patch(src: dict, data: dict, taken_keys: set[str]) -> list[str]:
    """PATCH of a source. Returns refused field names (nothing applied when not empty)."""
    bad = []
    new = json.loads(json.dumps(src))
    for k, v in data.items():
        try:
            if k == "tags":
                new["tags"] = _str_list(v)
            elif k == "collections":
                new["collections"] = _str_list(v)
            elif k == "status":
                if v not in STATUSES:
                    raise SourceError("bad")
                new["status"] = v
            elif k == "notes":
                if not isinstance(v, str):
                    raise SourceError("bad")
                new["notes"] = v[:200000]
            elif k == "csl":
                if not isinstance(v, dict):
                    raise SourceError("bad")
                item = biblio.clean_csl(v)
                if not item.get("title"):
                    raise SourceError("bad")
                new["csl"] = item
                new["verified"] = True                     # the user wrote / confirmed it
                new["proposed"] = None
            elif k == "key":
                if not isinstance(v, str) or not biblio.KEY_RE.match(v) or (v != src["key"] and v.lower() in
                                                                            {x.lower() for x in taken_keys}):
                    raise SourceError("bad")
                new["key"] = v
            elif k == "verified":
                if v is not True:
                    raise SourceError("bad")
                if src.get("proposed"):
                    new["csl"] = biblio.clean_csl({**(src.get("csl") or {}), **src["proposed"]})
                new["verified"], new["proposed"] = True, None
            else:
                raise SourceError("bad")
        except SourceError:
            bad.append(k)
    if not bad:
        src.clear()
        src.update(new)
    return bad


# ================================================================ files
def file_kind(data: bytes) -> str:
    k = sniff(data)
    if k == "pdf":
        return "pdf"
    if k in ("gzip", "tar", "zip"):
        return "archive"
    if k == "epub":
        return "epub"
    if k == "tex":
        return "tex"
    return "other"


def check_upload(data: bytes, name: str) -> str:
    if len(data) > MAX_UPLOAD:
        raise SourceError("too_large", 413)
    if not data:
        raise SourceError("empty")
    kind = file_kind(data)
    if kind == "other" and sniff(data) not in ("bib", "ris", "csljson", "text"):
        raise SourceError("bad_type", 415, detected=sniff(data))
    return kind


def safe_name(name: str, fallback: str) -> str:
    from urllib.parse import unquote
    base = os.path.basename(unquote(str(name or "")).replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._ +-]", "_", base).strip(" .")[:120]
    return base or fallback


def attach_file(shelf: Shelf, src: dict, data: bytes, name: str, role: str = "main") -> dict:
    kind = check_upload(data, name)
    if kind == "other":
        raise SourceError("bad_type", 415)
    sha = shelf.put_blob(data)
    for f in src["files"]:
        if f["sha256"] == sha:
            return f
    if kind == "archive":
        try:
            shelf.unpacked(sha)                  # validate now: a hostile archive is refused at upload time
        except UnsafeInput as e:
            raise SourceError("bad_archive", 422, reason=e.kind)
    ext = {"pdf": ".pdf", "tex": ".tex", "archive": ".tar.gz", "epub": ".epub"}[kind]
    f = {"sha256": sha, "name": safe_name(name, f"{src['key']}{ext}"), "kind": kind, "size": len(data),
         "role": role, "added": time.time()}
    src["files"].append(f)
    return f


def tex_main_text(shelf: Shelf, f: dict) -> tuple[str, Path | None]:
    """(TeX of the main file, directory of the extracted archive or None)."""
    if f["kind"] == "tex":
        return shelf.blob(f["sha256"]).read_text(encoding="utf-8", errors="replace"), None
    root = shelf.unpacked(f["sha256"])
    from .fulltext import find_main_tex
    main = find_main_tex(root)
    if main is None:
        return "", root
    return main.read_text(encoding="utf-8", errors="replace"), root


# ================================================================ metadata from files (fallback)
def pdfinfo(path: Path) -> dict:
    from .safety import run_tool
    r = run_tool(["pdfinfo", "-enc", "UTF-8", str(path)], timeout=30)
    out = {}
    if r.rc == 0:
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            k, _, v = line.partition(":")
            if k.strip() and v.strip():
                out[k.strip().lower()] = v.strip()
    return out


def first_page_text(path: Path, pages: int = 1) -> str:
    from .safety import run_tool
    r = run_tool(["pdftotext", "-f", "1", "-l", str(pages), "-enc", "UTF-8", "-layout", str(path), "-"], timeout=30)
    return r.stdout.decode("utf-8", "replace") if r.rc == 0 else ""


def guess_from_pdf(path: Path) -> dict:
    """Heuristics only: identifiers in the first pages (→ resolved online later), else pdfinfo + first lines.
    Returns {identifiers: [(kind, id)], proposed: csl | None}."""
    info = pdfinfo(path)
    text = first_page_text(path, 2)
    ids: list[tuple[str, str]] = []
    m = re.search(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", text)
    if m:
        ids.append(("arxiv", m.group(1)))
    for m in biblio.DOI_RE.finditer(text[:6000]):
        d = biblio.norm_doi(m.group(1))
        if ("doi", d) not in ids:
            ids.append(("doi", d))
    title = info.get("title", "")
    if not title or re.match(r"(?i)^(untitled|microsoft word|.*\.(dvi|tex|pdf|docx?))", title):
        lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 8]
        cand = [ln for ln in lines[:15] if not re.search(r"(?i)arxiv|doi|journal|vol\.|http|abstract|©|page|\d{4}-\d{4}",
                                                             ln)]
        title = re.sub(r"\s{2,}", " ", cand[0]) if cand else ""
    proposed = None
    if title:
        proposed = {"type": "article", "title": title[:300]}
        if info.get("author"):
            proposed["author"] = [{"literal": a.strip()} for a in re.split(r",|;| and ", info["author"]) if a.strip()][:20]
        y = re.search(r"(19|20)\d\d", info.get("creationdate", ""))
        if y:
            proposed["issued"] = {"date-parts": [[int(y.group(0))]]}
    return {"identifiers": ids, "proposed": proposed, "pages": int(info.get("pages", "0") or 0),
            "first_text": text[:4000]}


def guess_from_tex(tex: str) -> dict | None:
    from .fulltext import strip_comments, braced_after
    t = strip_comments(tex)
    title = braced_after(t, r"\title")
    if not title:
        return None
    item: dict = {"type": "article", "title": biblio.latex_to_unicode(re.sub(r"\\\\|\\thanks\{[^}]*\}", " ",
                                                                             title))[:300]}
    authors = re.findall(r"\\author(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}", t)
    names = []
    for a in authors:
        a = re.sub(r"\\(thanks|footnote|address|email|inst)\{[^}]*\}", "", a)
        for part in re.split(r"\\and|,|\\\\", a):
            p = biblio.latex_to_unicode(part).strip()
            if 2 < len(p) < 80:
                names.append({"literal": p})
    if names:
        item["author"] = names[:20]
    return item


METADATA_PROMPT = (
    "Below is the first page of a mathematical document, given as data. Extract its bibliographic metadata. "
    "{rule}\nAnswer ONLY with JSON: {{\"title\": \"…\", \"authors\": [\"Given Family\", …], \"year\": 2020 or null, "
    "\"journal\": \"…\" or \"\", \"doi\": \"…\" or \"\", \"arxiv\": \"…\" or \"\"}}. Use only what is written on "
    "the page; leave a field empty when it is not there.\n\n{page}")


def metadata_messages(first_text: str) -> list[dict]:
    from .safety import UNTRUSTED_RULE, wrap_untrusted
    return [{"role": "user", "content": METADATA_PROMPT.format(rule=UNTRUSTED_RULE,
                                                               page=wrap_untrusted(first_text[:5000], "first page"))}]


def parse_metadata_answer(text: str, page_text: str) -> dict | None:
    """Model proposal → CSL (unverified). Identifiers are kept only if they literally occur on the page."""
    from .litsearch import parse_json_block
    data = parse_json_block(text)
    if not isinstance(data, dict) or not str(data.get("title", "")).strip():
        return None
    item: dict = {"type": "article-journal" if data.get("journal") else "article",
                  "title": str(data["title"]).strip()[:300]}
    authors = [str(a).strip() for a in data.get("authors") or [] if str(a).strip()][:30]
    if authors:
        item["author"] = [{"family": a.split()[-1], "given": " ".join(a.split()[:-1])} for a in authors]
    try:
        if data.get("year") and 1500 < int(data["year"]) < 2100:
            item["issued"] = {"date-parts": [[int(data["year"])]]}
    except (TypeError, ValueError):
        pass
    if data.get("journal"):
        item["container-title"] = str(data["journal"])[:300]
    flat = re.sub(r"\s+", "", page_text).lower()
    doi = biblio.norm_doi(str(data.get("doi") or ""))
    if doi and doi in flat:
        item["DOI"] = doi
    ax = biblio.norm_arxiv(str(data.get("arxiv") or ""))
    if ax and ax.lower() in flat:
        item["arxiv"] = ax
    return biblio.clean_csl(item)


# ================================================================ the library (all shelves of one server)
GLOBAL = "global"
MATHLIB = "mathlib"


class Library:
    """Shelves of the server: `global`, one per project, and the read-only `mathlib`. Publishes `sources.updated`."""

    def __init__(self, ctx, fetcher=None):
        from .fetch import Fetcher
        self.ctx = ctx
        self.fetcher = fetcher or Fetcher()
        self.shelves: dict[str, Shelf] = {}
        self.busy: dict[str, str] = {}            # source id -> what runs on it (extract / propose)
        self.embeddings = True

    # ------------------------------------------------------------ shelves
    def shelf(self, shelf_id: str) -> Shelf:
        if shelf_id == MATHLIB:
            raise SourceError("readonly", 403)
        if shelf_id != GLOBAL:
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$", shelf_id or "") or \
                    self.ctx.projects.get(shelf_id) is None:
                raise SourceError("not_found", 404)
        sh = self.shelves.get(shelf_id)
        if sh is None:
            root = (self.ctx.paths.config / "sources") if shelf_id == GLOBAL else \
                (self.ctx.projects.store.dir(shelf_id) / "sources")
            sh = Shelf(shelf_id, root)
            sh.load()
            self.shelves[shelf_id] = sh
        return sh

    def mathlib(self) -> list[dict]:
        items = biblio.mathlib_shelf(self.ctx.workspaces)
        out = []
        for it in items:
            key = it.get("_key", "")
            out.append({"id": "m-" + hashlib.sha1(key.encode()).hexdigest()[:10], "key": key,
                        "csl": {k: v for k, v in it.items() if not k.startswith("_")}, "files": [], "tags": ["mathlib"],
                        "collections": [], "status": "unread", "notes": "", "annotations": [], "verified": True,
                        "readonly": True, "origin": {"via": "mathlib", "workspace": it.get("_workspace", "")},
                        "fulltext": {"state": "none"}, "updated": 0})
        return out

    def project_entries(self, pid: str | None) -> list[tuple[str, dict]]:
        """Keys a project can cite: its own shelf, then the global shelf, then Mathlib (first key wins)."""
        out: dict[str, dict] = {}
        shelves = []
        if pid and self.ctx.projects.get(pid) is not None:
            shelves.append(self.shelf(pid).list())
        shelves.append(self.shelf(GLOBAL).list())
        for lst in shelves:
            for s in lst:
                out.setdefault(s["key"], s.get("csl") or {})
        return list(out.items())

    def all_entries(self, pid: str | None) -> dict[str, dict]:
        """project + global + Mathlib keys (for validating citations and building .bib files)."""
        out = dict(self.project_entries(pid))
        for s in self.mathlib():
            out.setdefault(s["key"], s["csl"])
        return out

    def taken_keys(self, shelf_id: str) -> set[str]:
        keys = set(self.shelf(shelf_id).keys())
        if shelf_id != GLOBAL:
            keys |= self.shelf(GLOBAL).keys()
        return keys

    def publish(self, shelf_id: str, src: dict | None = None, removed: str = "") -> None:
        payload: dict = {"shelf": shelf_id}
        if src is not None:
            payload["source"] = src
        if removed:
            payload["removed"] = removed
        self.ctx.publish("sources.updated", payload)

    # ------------------------------------------------------------ adding
    async def add_record(self, shelf_id: str, item: dict, *, via: str, verified: bool = True,
                         proposed: dict | None = None, oa: dict | None = None,
                         files: list[tuple[str, bytes]] | None = None, force: bool = False, tags=None,
                         collections=None, extract: bool = True) -> tuple[dict, dict | None]:
        """Returns (source, duplicate) — when a duplicate exists and not `force`, nothing is added and
        (existing, {"of": id, "reason": …}) is returned."""
        sh = self.shelf(shelf_id)
        clean = biblio.clean_csl({k: v for k, v in item.items() if not k.startswith("_")})
        if not clean.get("title"):
            clean["title"] = "(sans titre)"
        async with sh.lock:
            if not force:
                dup, why = sh.find_duplicate(clean)
                if dup is not None:
                    return dup, {"of": dup["id"], "reason": why}
            wanted = item.get("_key", "")
            taken = self.taken_keys(shelf_id)
            key = wanted if wanted and biblio.KEY_RE.match(wanted) and wanted.lower() not in {k.lower() for k in taken} \
                else biblio.make_key(clean, taken)
            src = blank(clean, key)
            src["verified"] = bool(verified)
            src["proposed"] = proposed
            src["oa"] = oa or {}
            src["origin"] = {"via": via, "at": time.time()}
            if tags:
                src["tags"] = _str_list(list(tags))
            if collections:
                src["collections"] = _str_list(list(collections))
            for name, data in files or []:
                try:
                    await asyncio.to_thread(attach_file, sh, src, data, name)
                except SourceError as e:
                    src.setdefault("warnings", []).append(f"file:{e.kind}")
            await asyncio.to_thread(sh.save_sync, src)
        self.publish(shelf_id, src)
        if extract and src["files"]:
            self.schedule_extract(shelf_id, src["id"])
        return src, None

    async def add_identifier(self, shelf_id: str, text: str, *, mode: str, files: bool = True,
                             force: bool = False) -> tuple[dict, dict | None]:
        from . import litsearch
        self.shelf(shelf_id)
        found = await litsearch.resolve(self.fetcher, text, mode)
        sh = self.shelf(shelf_id)
        if not force:
            dup, why = sh.find_duplicate(found.item)
            if dup is not None:
                return dup, {"of": dup["id"], "reason": why}
        blobs: list[tuple[str, bytes]] = []
        warnings = []
        if files and found.item.get("arxiv"):
            aid = found.item["arxiv"]
            try:
                data, _ct = await litsearch.arxiv_source(self.fetcher, aid, mode)
                blobs.append((f"arXiv-{aid}" + (".pdf" if data.startswith(b"%PDF") else ".tar.gz"), data))
            except Exception as e:  # noqa: BLE001
                warnings.append(f"eprint:{getattr(e, 'kind', type(e).__name__)}")
            if not any(b[1].startswith(b"%PDF") for b in blobs):
                try:
                    blobs.append((f"arXiv-{aid}.pdf", await litsearch.arxiv_pdf(self.fetcher, aid, mode)))
                except Exception as e:  # noqa: BLE001
                    warnings.append(f"pdf:{getattr(e, 'kind', type(e).__name__)}")
        elif files and found.oa.get("is_oa") and found.oa.get("url"):
            try:
                blobs.append((f"{found.via}.pdf", await litsearch.download_oa_pdf(self.fetcher, found.oa, mode)))
            except Exception as e:  # noqa: BLE001
                warnings.append(f"oa_pdf:{getattr(e, 'kind', type(e).__name__)}")
        src, dup = await self.add_record(shelf_id, found.item, via=found.via, oa=found.oa, files=blobs, force=force)
        if warnings and dup is None:
            src["warnings"] = src.get("warnings", []) + warnings
            await asyncio.to_thread(sh.save_sync, src)
        return src, dup

    async def import_text(self, shelf_id: str, data: bytes, fmt: str = "", files_root: Path | None = None,
                          force: bool = False) -> dict:
        """BibTeX / RIS / CSL-JSON / Zotero RDF. Attached file paths are only read from `files_root` (an uploaded
        Zotero export archive, safely extracted) — never from an arbitrary path written in the file."""
        text = data.decode("utf-8", "replace")
        kind = fmt or sniff(data)
        errors: list[str] = []
        if kind == "bib":
            items, errors = biblio.bibtex_to_items(text)
        elif kind == "ris":
            items = biblio.ris_to_items(text)
        elif kind == "csljson":
            try:
                items = biblio.csljson_to_items(text)
            except ValueError as e:
                raise SourceError("bad_json", detail=str(e)[:200])
        elif kind in ("rdf", "text") and "zotero.org/namespaces" in text[:5000]:
            try:
                items = biblio.rdf_to_items(data)
            except UnsafeInput as e:
                raise SourceError("bad_xml", detail=e.kind)
        else:
            raise SourceError("bad_format", detected=kind)
        added, dups, unattached = [], [], []
        for it in items[:5000]:
            blobs = []
            for path in it.get("_files") or []:
                if files_root is None:
                    unattached.append(path)
                    continue
                rel = safe_rel(path.replace("\\", "/").lstrip("./")) if not path.startswith("/") else None
                cand = None
                if rel:
                    try:
                        from .safety import safe_join
                        cand = safe_join(files_root, rel)
                    except ValueError:
                        cand = None
                if cand is None or not cand.is_file() or cand.is_symlink():
                    # Zotero absolute paths: match by file name inside the uploaded archive only
                    base = os.path.basename(path)
                    hits = [p for p in files_root.rglob(base) if p.is_file() and not p.is_symlink()] if base else []
                    cand = hits[0] if hits else None
                if cand is None:
                    unattached.append(path)
                    continue
                blobs.append((cand.name, cand.read_bytes()))
            src, dup = await self.add_record(shelf_id, it, via="import", files=blobs, force=force)
            (dups if dup else added).append({"id": src["id"], "key": src["key"], **({"duplicate": dup} if dup else {})})
        return {"added": added, "duplicates": dups, "errors": errors[:50], "unattached_files": unattached[:200]}

    async def add_upload(self, shelf_id: str, name: str, data: bytes, *, mode: str, force: bool = False) -> dict:
        """A file dropped in the library: bibliography file, Zotero export (zip), PDF, TeX or a source archive."""
        self.shelf(shelf_id)
        kind = sniff(data)
        if len(data) > MAX_UPLOAD:
            raise SourceError("too_large", 413)
        if kind in ("bib", "ris", "csljson") or (kind == "text" and "zotero.org/namespaces" in
                                                 data[:5000].decode("utf-8", "replace")):
            return await self.import_text(shelf_id, data, "" if kind != "text" else "rdf", force=force)
        if kind == "zip":
            res = await self._zip_import(shelf_id, data, force)
            if res is not None:
                return res
        fkind = check_upload(data, name)
        if fkind == "other":
            raise SourceError("bad_type", 415, detected=kind)
        sh = self.shelf(shelf_id)
        proposed, ids, first_text = None, [], ""
        if fkind == "pdf":
            tmp = sh.files_dir / sh.put_blob(data)
            g = await asyncio.to_thread(guess_from_pdf, tmp)
            ids, proposed, first_text = g["identifiers"], g["proposed"], g["first_text"]
        elif fkind in ("tex", "archive"):
            try:
                text = data.decode("utf-8", "replace") if fkind == "tex" else ""
                if fkind == "archive":
                    sha = await asyncio.to_thread(sh.put_blob, data)
                    root = await asyncio.to_thread(sh.unpacked, sha)
                    from .fulltext import find_main_tex, read_tex
                    main = find_main_tex(root)
                    text = read_tex(main) if main else ""
                proposed = guess_from_tex(text)
                m = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})", text)
                if m:
                    ids.append(("arxiv", m.group(1)))
            except UnsafeInput as e:
                raise SourceError("bad_archive", 422, reason=e.kind)
        # an identifier found in the file → verified metadata from the API (when the network is allowed)
        if mode != "local":
            from . import litsearch
            for k, ident in ids[:3]:
                try:
                    found = await litsearch.resolve(self.fetcher, ident if k != "doi" else f"doi:{ident}", mode)
                except Exception:  # noqa: BLE001
                    continue
                src, dup = await self.add_record(shelf_id, found.item, via=f"file+{found.via}", oa=found.oa,
                                                 files=[(name, data)], force=force)
                return {"added": [] if dup else [{"id": src["id"], "key": src["key"]}],
                        "duplicates": [{"id": src["id"], "key": src["key"], "duplicate": dup}] if dup else [],
                        "source": src}
        item = dict(proposed or {"type": "document", "title": os.path.splitext(safe_name(name, "document"))[0]})
        src, dup = await self.add_record(shelf_id, item, via="file", verified=False, proposed=None,
                                         files=[(name, data)], force=force)
        if dup is None and first_text and self.ctx.brain is not None:
            self.schedule_propose(shelf_id, src["id"], mode, first_text)
        return {"added": [] if dup else [{"id": src["id"], "key": src["key"]}],
                "duplicates": [{"id": src["id"], "key": src["key"], "duplicate": dup}] if dup else [], "source": src}

    async def _zip_import(self, shelf_id: str, data: bytes, force: bool) -> dict | None:
        """A Zotero export folder zipped (the .bib / .json / .rdf plus its `files/` directory)."""
        import tempfile
        with tempfile.TemporaryDirectory(prefix="madalean-import-", dir=str(self.ctx.paths.tmp)) as tmp:
            try:
                ex = await asyncio.to_thread(extract_archive, data, Path(tmp))
            except UnsafeInput as e:
                raise SourceError("bad_archive", 422, reason=e.kind)
            metas = [f for f in ex.files if f.lower().endswith((".bib", ".json", ".rdf", ".ris"))]
            if not metas:
                return None                         # not an export: treat as a source archive
            total: dict = {"added": [], "duplicates": [], "errors": [], "unattached_files": []}
            for rel in metas[:5]:
                raw = (Path(tmp) / rel).read_bytes()
                fmt = "rdf" if rel.lower().endswith(".rdf") else ""
                res = await self.import_text(shelf_id, raw, fmt, files_root=Path(tmp), force=force)
                for k in total:
                    total[k] += res.get(k, [])
            return total

    # ------------------------------------------------------------ edits
    async def save(self, shelf_id: str, src: dict) -> None:
        sh = self.shelf(shelf_id)
        await asyncio.to_thread(sh.save_sync, src)
        self.publish(shelf_id, src)

    def get(self, shelf_id: str, sid: str) -> dict:
        if shelf_id == MATHLIB:
            s = next((x for x in self.mathlib() if x["id"] == sid), None)
        else:
            s = self.shelf(shelf_id).get(sid)
        if s is None:
            raise SourceError("not_found", 404)
        return s

    async def patch(self, shelf_id: str, sid: str, data: dict) -> dict:
        sh = self.shelf(shelf_id)
        async with sh.lock:
            src = self.get(shelf_id, sid)
            bad = apply_patch(src, data, self.taken_keys(shelf_id))
            if bad:
                raise SourceError("bad_fields", fields=bad)
            await asyncio.to_thread(sh.save_sync, src)
        self.publish(shelf_id, src)
        return src

    async def delete(self, shelf_id: str, sid: str) -> None:
        sh = self.shelf(shelf_id)
        if sid in self.busy or "p:" + sid in self.busy:
            raise SourceError("busy", 409, running=self.busy.get(sid) or "propose")
        async with sh.lock:
            if not await asyncio.to_thread(sh.delete_sync, sid):
                raise SourceError("not_found", 404)
        from .fulltext import Index
        await asyncio.to_thread(Index(sh.index_path).remove, sid)
        self.publish(shelf_id, removed=sid)

    async def restore(self, shelf_id: str, sid: str) -> dict:
        sh = self.shelf(shelf_id)
        async with sh.lock:
            src = await asyncio.to_thread(sh.restore_sync, sid)
        if src is None:
            raise SourceError("not_found", 404)
        self.publish(shelf_id, src)
        if src.get("files"):
            self.schedule_extract(shelf_id, sid)
        return src

    async def copy_to(self, src_shelf: str, sid: str, dst_shelf: str) -> tuple[dict, dict | None]:
        """Copy a source (record + files) to another shelf — e.g. from the global shelf or Mathlib to a project."""
        src = self.get(src_shelf, sid)
        files = []
        if src_shelf != MATHLIB:
            sh = self.shelf(src_shelf)
            for f in src.get("files", []):
                files.append((f["name"], await asyncio.to_thread(sh.blob(f["sha256"]).read_bytes)))
        item = {**src["csl"], "_key": src["key"]}
        new, dup = await self.add_record(dst_shelf, item, via=f"copy:{src_shelf}", verified=src.get("verified", True),
                                         oa=src.get("oa"), files=files, tags=src.get("tags"))
        return new, dup

    async def attach(self, shelf_id: str, sid: str, name: str, data: bytes) -> dict:
        sh = self.shelf(shelf_id)
        async with sh.lock:
            src = self.get(shelf_id, sid)
            await asyncio.to_thread(attach_file, sh, src, data, name)
            await asyncio.to_thread(sh.save_sync, src)
        self.publish(shelf_id, src)
        self.schedule_extract(shelf_id, sid)
        return src

    async def annotate(self, shelf_id: str, sid: str, data: dict, ann_id: str = "", delete: bool = False) -> dict:
        sh = self.shelf(shelf_id)
        async with sh.lock:
            src = self.get(shelf_id, sid)
            anns = src.setdefault("annotations", [])
            if ann_id:
                cur = next((a for a in anns if a.get("id") == ann_id), None)
                if cur is None:
                    raise SourceError("not_found", 404)
                if delete:
                    anns.remove(cur)
                    src.setdefault("annotations_trash", []).append(cur)
                    src["annotations_trash"] = src["annotations_trash"][-50:]
                else:
                    anns[anns.index(cur)] = clean_annotation(data, cur)
            else:
                if len(anns) >= 5000:
                    raise SourceError("too_many", 413)
                anns.append(clean_annotation(data))
            await asyncio.to_thread(sh.save_sync, src)
        self.publish(shelf_id, src)
        return src

    # ------------------------------------------------------------ full text
    def schedule_extract(self, shelf_id: str, sid: str) -> bool:
        if sid in self.busy:
            return False
        self.busy[sid] = "extract"

        async def run():
            try:
                await self.extract(shelf_id, sid)
            except Exception:  # noqa: BLE001
                log.exception("extraction failed for %s", sid)
            finally:
                self.busy.pop(sid, None)
        spawn = getattr(self.ctx, "spawn", None)
        (spawn or asyncio.ensure_future)(run())
        return True

    async def extract(self, shelf_id: str, sid: str) -> dict:
        from . import fulltext as ft
        sh = self.shelf(shelf_id)
        src = self.get(shelf_id, sid)
        files = src.get("files", [])
        tex = next((f for f in files if f["kind"] in ("archive", "tex")), None)
        pdf = next((f for f in files if f["kind"] == "pdf"), None)
        epub = next((f for f in files if f["kind"] == "epub"), None)
        state: dict = {"state": "none", "at": time.time(), "warnings": []}
        chunks: list = []

        def work():
            nonlocal chunks
            if tex is not None:
                try:
                    text, root = tex_main_text(sh, tex)
                    if text.strip():
                        doc = ft.parse_tex(text, root)
                        chunks = ft.tex_chunks(sid, doc)
                        state.update({"state": "ok", "method": "tex", "nodes": len(doc.nodes),
                                      "sections": len(doc.sections)})
                        state["warnings"] += doc.warnings
                        return
                    state["warnings"].append("tex_main_not_found")
                except (UnsafeInput, SourceError, OSError) as e:
                    state["warnings"].append(f"tex:{getattr(e, 'kind', type(e).__name__)}")
            if pdf is not None:
                r = ft.extract_pdf(sid, sh.blob(pdf["sha256"]))
                chunks = r.chunks
                state.update({"state": r.state, "method": "pdf", "pages": r.pages, "two_columns": r.two_columns,
                              "headers_removed": r.removed_lines})
                state["warnings"] += r.warnings
                return
            if epub is not None:
                try:
                    chunks = ft.extract_epub(sid, sh.unpacked(epub["sha256"]))
                    state.update({"state": "ok" if chunks else "error", "method": "epub"})
                except (UnsafeInput, SourceError) as e:
                    state.update({"state": "error", "method": "epub"})
                    state["warnings"].append(f"epub:{getattr(e, 'kind', '')}")
        await asyncio.to_thread(work)
        state["chunks"] = len(chunks)
        await asyncio.to_thread(ft.Index(sh.index_path).replace, sid, chunks)
        async with sh.lock:
            cur = sh.get(sid)
            if cur is not None:
                cur["fulltext"] = state
                await asyncio.to_thread(sh.save_sync, cur)
                self.publish(shelf_id, cur)
        return state

    async def search(self, shelf_ids: list[str], query: str, k: int = 12, source_ids: list[str] | None = None,
                     semantic: bool | None = None) -> list[dict]:
        from . import fulltext as ft
        hits = []
        for shid in shelf_ids:
            sh = self.shelf(shid)
            for h in await asyncio.to_thread(ft.Index(sh.index_path).search, query, k * 2 if semantic else k,
                                             source_ids):
                s = sh.get(h["source_id"])
                if s is None:
                    continue
                h["shelf"] = shid
                h["source_key"] = s["key"]
                hits.append(h)
        hits.sort(key=lambda h: -h["score"])
        hits = hits[: k * 2]
        use_sem = self.embeddings if semantic is None else semantic
        if use_sem:
            hits = await ft.semantic_rerank(query, hits, True)
        return hits[:k]

    def chunks_of(self, shelf_id: str, sid: str, page: int | None = None) -> list[dict]:
        from . import fulltext as ft
        sh = self.shelf(shelf_id)
        self.get(shelf_id, sid)
        return ft.Index(sh.index_path).chunks(sid, page)

    # ------------------------------------------------------------ metadata proposal (brain)
    def schedule_propose(self, shelf_id: str, sid: str, mode: str, first_text: str) -> bool:
        if "p:" + sid in self.busy:
            return False
        self.busy["p:" + sid] = "propose"

        async def run():
            try:
                await self.propose(shelf_id, sid, mode, first_text)
            except Exception:  # noqa: BLE001
                log.exception("metadata proposal failed for %s", sid)
            finally:
                self.busy.pop("p:" + sid, None)
        (getattr(self.ctx, "spawn", None) or asyncio.ensure_future)(run())
        return True

    async def propose(self, shelf_id: str, sid: str, mode: str, first_text: str) -> dict | None:
        """Brain role « understand » reads the first page and proposes metadata — stored as `proposed`
        (unverified) until the user confirms (PATCH verified=true or csl=…)."""
        from ..server.helpers import complete_once
        c = await complete_once(self.ctx, "understand", metadata_messages(first_text), mode,
                                owner=f"meta-{sid}", max_tokens=600, temperature=0.1)
        prop = parse_metadata_answer(c.text, first_text)
        if prop is None:
            return None
        sh = self.shelf(shelf_id)
        async with sh.lock:
            src = sh.get(sid)
            if src is None or src.get("verified"):
                return None
            src["proposed"] = prop
            src["proposed_by"] = c.model.key
            await asyncio.to_thread(sh.save_sync, src)
        self.publish(shelf_id, src)
        return prop

    # ------------------------------------------------------------ export
    def export(self, shelf_id: str, fmt: str, ids: list[str] | None = None) -> tuple[str, str]:
        if shelf_id == MATHLIB:
            lst = self.mathlib()
        else:
            lst = self.shelf(shelf_id).list()
        if ids:
            lst = [s for s in lst if s["id"] in ids or s["key"] in ids]
        pairs = [(s["key"], s.get("csl") or {}) for s in lst]
        if fmt == "bib":
            return "".join(biblio.item_to_bibtex(it, k) + "\n" for k, it in pairs), "application/x-bibtex"
        if fmt == "ris":
            return biblio.items_to_ris(pairs), "application/x-research-info-systems"
        if fmt == "csljson":
            return biblio.items_to_csljson(pairs), "application/vnd.citationstyles.csl+json"
        raise SourceError("bad_format")


def library(ctx) -> Library:
    """The server's Library (created on first use, attached to the context)."""
    lib = getattr(ctx, "_research_library", None)
    if lib is None:
        from .fetch import Fetcher, ReplayTransport
        fetcher = None
        if getattr(ctx, "demo", False):
            fetcher = Fetcher(ReplayTransport(Path(__file__).resolve().parent / "demo_http", loose=True))
        lib = Library(ctx, fetcher)
        ctx._research_library = lib
    return lib
