"""Linked research notes, internal to Madalean (ARCHITECTURE §14) — session S-G.

A note belongs to a project and is Markdown with LaTeX maths (`$…$`) and fenced ```lean blocks. Links:

    [[Title]]  [[Title|shown text]]  [[note:ID]]          another note of the project (by title or id)
    [[dossier:ID]]  [[dossier:Title]]                    a dossier (theorem, conjecture…)
    [[@key]]  [[@key#p12]]  [[@key#chunk-3f2a]]          a source of the sources library (BibTeX key + locator)
    [[lib:Name]]                                         a result of the library (Lean name)

Links inside code (fenced blocks, `inline code`) are ignored. Link targets are stored raw and resolved when read,
so backlinks and the graph stay right after a rename, a delete (link becomes dangling) or a restore.

Storage: one SQLite database `<config>/research/notes.sqlite` (WAL): notes, every revision (full text), links, FTS5
index, attachments metadata; attachment bytes in `<config>/research/attachments/`. Single writer: the server.

Concurrency (several devices edit live): each note has a revision number `rev`. A write carries `base_rev`; when the
note moved on meanwhile, the server three-way merges (base = revision `base_rev`, theirs = current, mine = the
request) line by line; non-overlapping edits merge silently, overlapping ones are refused with a conflict payload
(409) that carries the current note and the conflicting hunks."""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

LINK_RE = re.compile(r"\[\[([^\[\]\n]{1,300})\]\]")
FENCE_RE = re.compile(r"(?ms)^[ \t]*(```|~~~)([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
TAG_RE = re.compile(r"(?<![\w#&/])#([A-Za-zÀ-ÿ][\w\-/À-ÿ]{0,40})")
MAX_BODY = 1_000_000
MAX_TITLE = 200


class NoteError(Exception):
    def __init__(self, kind: str, status: int = 400, **data):
        super().__init__(kind)
        self.kind, self.status, self.data = kind, status, data


# ---------------------------------------------------------------- parsing
@dataclass
class Link:
    kind: str          # note | dossier | source | lib | passage
    ref: str           # note id or title, dossier id or title, bib key, lean name, chunk id
    label: str = ""
    locator: str = ""  # sources: p12, chunk id, "Thm 2.1"…

    def as_dict(self) -> dict:
        return {"kind": self.kind, "ref": self.ref, "label": self.label, "locator": self.locator}


def strip_code(body: str) -> str:
    """Body with fenced blocks and inline code blanked (same length, so offsets stay valid)."""
    out = FENCE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), body)
    return INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), out)


def parse_link(inner: str) -> Link | None:
    target, _, label = inner.partition("|")
    target, label = target.strip(), label.strip()
    if not target:
        return None
    if target.startswith("@"):
        key, _, loc = target[1:].partition("#")
        key = key.strip()
        return Link("source", key, label, loc.strip()) if re.fullmatch(r"[\w:.\-+/]{1,120}", key) else None
    low = target.lower()
    for prefix, kind in (("dossier:", "dossier"), ("note:", "note"), ("lib:", "lib"), ("passage:", "passage")):
        if low.startswith(prefix):
            ref = target[len(prefix):].strip()
            return Link(kind, ref, label) if ref else None
    return Link("note", target, label)


def parse_links(body: str) -> list[Link]:
    out, seen = [], set()
    for m in LINK_RE.finditer(strip_code(body)):
        ln = parse_link(m.group(1))
        if ln is None:
            continue
        k = (ln.kind, ln.ref.lower(), ln.locator)
        if k not in seen:
            seen.add(k)
            out.append(ln)
    return out


def parse_tags(body: str) -> list[str]:
    text = strip_code(body)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s", " ", text)          # headings are not tags
    return sorted({t.lower() for t in TAG_RE.findall(text)})


@dataclass
class LeanBlock:
    index: int
    code: str
    start_line: int     # 1-based line of the first code line in the body
    hash: str


def lean_blocks(body: str) -> list[LeanBlock]:
    out = []
    for m in FENCE_RE.finditer(body):
        lang = m.group(2).strip().lower().split()[:1]
        if lang and lang[0] in ("lean", "lean4"):
            code = m.group(3)
            line = body.count("\n", 0, m.start(3)) + 1
            out.append(LeanBlock(len(out), code, line, hashlib.sha256(code.encode()).hexdigest()[:16]))
    return out


def paragraphs(body: str) -> list[str]:
    text = FENCE_RE.sub("\n\n", body)
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


# ---------------------------------------------------------------- three-way merge
def _hunks(base: list[str], other: list[str]) -> list[tuple[int, int, list[str]]]:
    sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
    return [(i1, i2, other[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def merge3(base: str, mine: str, theirs: str) -> tuple[str | None, list[dict]]:
    """Line-based three-way merge. Returns (merged, []) or (None, conflicts). Identical edits are not conflicts;
    edits of adjacent (but distinct) lines merge; overlapping edits, or two insertions at the same place, conflict."""
    if mine == theirs:
        return mine, []
    if base == theirs:
        return mine, []
    if base == mine:
        return theirs, []
    b, a, c = base.splitlines(True), mine.splitlines(True), theirs.splitlines(True)
    if b and not b[-1].endswith("\n"):
        b[-1] += "\n"
    if a and not a[-1].endswith("\n"):
        a[-1] += "\n"
    if c and not c[-1].endswith("\n"):
        c[-1] += "\n"
    ha = [(s, e, r, "mine") for s, e, r in _hunks(b, a)]
    hc = [(s, e, r, "theirs") for s, e, r in _hunks(b, c)]
    allh = sorted(ha + hc, key=lambda h: (h[0], h[1]))
    conflicts: list[dict] = []
    merged_h: list[tuple[int, int, list[str]]] = []
    i = 0
    while i < len(allh):
        s, e, r, who = allh[i]
        group = [allh[i]]
        j = i + 1
        while j < len(allh):
            s2, e2, r2, who2 = allh[j]
            ge = max(h[1] for h in group)
            gs = min(h[0] for h in group)
            touch = s2 < ge or s2 == gs or (s2 == ge and (s2 == e2 or any(h[0] == h[1] for h in group)))
            if not touch:
                break
            group.append(allh[j])
            j += 1
        owners = {h[3] for h in group}
        gs, ge = min(h[0] for h in group), max(h[1] for h in group)
        if len(owners) == 1:
            merged_h += [(h[0], h[1], h[2]) for h in group]
        else:
            # both sides edited this region: fine only when they produced the very same text
            def side(name: str) -> list[str]:
                out, pos = [], gs
                for h in sorted((h for h in group if h[3] == name), key=lambda h: h[0]):
                    out += b[pos:h[0]] + h[2]
                    pos = h[1]
                return out + b[pos:ge]
            ma, mc = side("mine"), side("theirs")
            if ma == mc:
                merged_h.append((gs, ge, ma))
            else:
                conflicts.append({"base_start": gs + 1, "base_end": ge, "base": "".join(b[gs:ge]),
                                  "mine": "".join(ma), "theirs": "".join(mc)})
        i = j
    if conflicts:
        return None, conflicts
    out, pos = [], 0
    for s, e, r in sorted(merged_h, key=lambda h: (h[0], h[1])):
        out += b[pos:s] + r
        pos = max(pos, e)
    out += b[pos:]
    text = "".join(out)
    if not (mine.endswith("\n") or theirs.endswith("\n")) and text.endswith("\n"):
        text = text[:-1]
    return text, []


def diff_text(old: str, new: str, old_label: str = "a", new_label: str = "b") -> str:
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), old_label, new_label, n=3))


# ---------------------------------------------------------------- attachments (safe types only)
SAFE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp",
              "application/pdf": ".pdf"}
MAX_ATTACHMENT = 10 * 1024 * 1024


def sniff(data: bytes) -> str | None:
    """Content type from the magic bytes (never from the file name or the client's header). SVG, HTML and anything
    else that a browser could execute are refused."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    return None


def validate_image(data: bytes, ctype: str) -> bool:
    """Decode the image fully when Pillow is available (polyglot / truncated files are refused)."""
    if not ctype.startswith("image/"):
        return True
    try:
        import io

        from PIL import Image
    except ImportError:  # pragma: no cover
        return True
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = (im.format or "").lower()
            im.verify()
        return {"png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}.get(fmt) == ctype
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- store
SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]', kind TEXT NOT NULL DEFAULT 'note', rev INTEGER NOT NULL DEFAULT 1,
  created REAL NOT NULL, updated REAL NOT NULL, deleted REAL, device TEXT NOT NULL DEFAULT '',
  lean TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS notes_project ON notes(project_id);
CREATE TABLE IF NOT EXISTS versions (
  note_id TEXT NOT NULL, rev INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, tags TEXT NOT NULL,
  t REAL NOT NULL, device TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', PRIMARY KEY(note_id, rev));
CREATE TABLE IF NOT EXISTS links (
  src TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
  locator TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS links_src ON links(src);
CREATE INDEX IF NOT EXISTS links_ref ON links(kind, ref);
CREATE TABLE IF NOT EXISTS attachments (
  id TEXT PRIMARY KEY, note_id TEXT NOT NULL, project_id TEXT NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL,
  size INTEGER NOT NULL, sha256 TEXT NOT NULL, t REAL NOT NULL, deleted REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(note_id UNINDEXED, title, body, tags,
  tokenize = 'unicode61 remove_diacritics 2');
"""


def _now() -> float:
    return time.time()


def new_id() -> str:
    return "n-" + time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8]


def fts_query(q: str) -> str:
    """User text → a safe FTS5 query (every word quoted, prefix match on the last one)."""
    words = re.findall(r"[\w\-']+", q, re.UNICODE)[:12]
    if not words:
        return ""
    parts = ['"' + w.replace('"', "") + '"' for w in words]
    parts[-1] += "*"
    return " AND ".join(parts)


@dataclass
class Note:
    id: str
    project_id: str
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
    kind: str = "note"
    rev: int = 1
    created: float = 0.0
    updated: float = 0.0
    deleted: float | None = None
    device: str = ""
    lean: dict = field(default_factory=dict)     # block hash -> stored Lean result

    @property
    def all_tags(self) -> list[str]:
        return sorted(set(self.tags) | set(parse_tags(self.body)))

    def summary(self) -> dict:
        return {"id": self.id, "project_id": self.project_id, "title": self.title, "tags": self.all_tags,
                "kind": self.kind, "rev": self.rev, "created": self.created, "updated": self.updated,
                "deleted": self.deleted, "size": len(self.body),
                "excerpt": re.sub(r"\s+", " ", strip_code(self.body))[:200].strip()}

    def to_dict(self) -> dict:
        blocks = lean_blocks(self.body)
        return {**self.summary(), "body": self.body, "user_tags": self.tags, "device": self.device,
                "lean_blocks": [{"index": b.index, "hash": b.hash, "start_line": b.start_line,
                                 "result": self.lean.get(b.hash)} for b in blocks],
                "links": [ln.as_dict() for ln in parse_links(self.body)]}


class NoteStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.att_dir = self.root / "attachments"
        self.att_dir.mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(self.root / "notes.sqlite"), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self.db.close()

    # ------------------------------------------------------------ rows
    def _row(self, r) -> Note:
        return Note(id=r[0], project_id=r[1], title=r[2], body=r[3], tags=json.loads(r[4] or "[]"), kind=r[5],
                    rev=r[6], created=r[7], updated=r[8], deleted=r[9], device=r[10], lean=json.loads(r[11] or "{}"))

    COLS = "id, project_id, title, body, tags, kind, rev, created, updated, deleted, device, lean"

    def get(self, nid: str, include_deleted: bool = True) -> Note | None:
        with self._lock:
            r = self.db.execute(f"SELECT {self.COLS} FROM notes WHERE id=?", (nid,)).fetchone()
        if r is None:
            return None
        n = self._row(r)
        return n if include_deleted or n.deleted is None else None

    def list(self, project_id: str | None = None, trash: bool = False, tag: str | None = None) -> list[Note]:
        q = f"SELECT {self.COLS} FROM notes WHERE " + ("deleted IS NOT NULL" if trash else "deleted IS NULL")
        args: list = []
        if project_id is not None:
            q += " AND project_id=?"
            args.append(project_id)
        with self._lock:
            rows = self.db.execute(q + " ORDER BY updated DESC", args).fetchall()
        notes = [self._row(r) for r in rows]
        if tag:
            notes = [n for n in notes if tag.lower() in n.all_tags]
        return notes

    def by_title(self, project_id: str, title: str) -> Note | None:
        with self._lock:
            r = self.db.execute(f"SELECT {self.COLS} FROM notes WHERE project_id=? AND deleted IS NULL AND "
                                "lower(title)=lower(?) ORDER BY created LIMIT 1", (project_id, title.strip())).fetchone()
        return self._row(r) if r else None

    # ------------------------------------------------------------ writes
    def _index(self, n: Note) -> None:
        self.db.execute("DELETE FROM links WHERE src=?", (n.id,))
        self.db.executemany("INSERT INTO links(src, kind, ref, label, locator) VALUES (?,?,?,?,?)",
                            [(n.id, ln.kind, ln.ref, ln.label, ln.locator) for ln in parse_links(n.body)])
        self.db.execute("DELETE FROM notes_fts WHERE note_id=?", (n.id,))
        if n.deleted is None:
            self.db.execute("INSERT INTO notes_fts(note_id, title, body, tags) VALUES (?,?,?,?)",
                            (n.id, n.title, n.body, " ".join(n.all_tags)))

    def _write(self, n: Note, reason: str) -> None:
        self.db.execute(f"INSERT OR REPLACE INTO notes({self.COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (n.id, n.project_id, n.title, n.body, json.dumps(n.tags), n.kind, n.rev, n.created, n.updated,
                         n.deleted, n.device, json.dumps(n.lean)))
        self.db.execute("INSERT OR REPLACE INTO versions(note_id, rev, title, body, tags, t, device, reason) "
                        "VALUES (?,?,?,?,?,?,?,?)", (n.id, n.rev, n.title, n.body, json.dumps(n.tags), n.updated,
                                                     n.device, reason))
        self._index(n)

    @staticmethod
    def _clean_title(title: str) -> str:
        t = re.sub(r"\s+", " ", str(title or "")).strip()[:MAX_TITLE]
        t = t.replace("[[", "").replace("]]", "").replace("|", "/")
        if not t:
            raise NoteError("title_required")
        return t

    @staticmethod
    def _clean_tags(tags) -> list[str]:
        if tags is None:
            return []
        if not isinstance(tags, list):
            raise NoteError("bad_fields", fields="tags")
        return sorted({re.sub(r"\s+", "-", str(t).strip().lstrip("#").lower())[:40] for t in tags if str(t).strip()})

    def create(self, project_id: str, title: str, body: str = "", tags=None, kind: str = "note",
               device: str = "") -> Note:
        title = self._clean_title(title)
        if len(body) > MAX_BODY:
            raise NoteError("too_large", 413)
        with self._lock:
            if self.by_title(project_id, title) is not None:
                raise NoteError("title_exists", 409, title=title)
            t = _now()
            n = Note(new_id(), project_id, title, body, self._clean_tags(tags), kind, 1, t, t, None, device, {})
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self._write(n, "create")
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
        return n

    def version(self, nid: str, rev: int) -> dict | None:
        with self._lock:
            r = self.db.execute("SELECT rev, title, body, tags, t, device, reason FROM versions WHERE note_id=? AND rev=?",
                                (nid, rev)).fetchone()
        if r is None:
            return None
        return {"rev": r[0], "title": r[1], "body": r[2], "tags": json.loads(r[3]), "t": r[4], "device": r[5],
                "reason": r[6]}

    def versions(self, nid: str) -> list[dict]:
        with self._lock:
            rows = self.db.execute("SELECT rev, title, length(body), t, device, reason FROM versions WHERE note_id=? "
                                   "ORDER BY rev DESC", (nid,)).fetchall()
        return [{"rev": r[0], "title": r[1], "size": r[2], "t": r[3], "device": r[4], "reason": r[5]} for r in rows]

    def update(self, nid: str, base_rev: int | None, *, title=None, body=None, tags=None, device: str = "",
               reason: str = "edit") -> tuple[Note, bool, Note | None]:
        """Apply an edit made on top of `base_rev`. Returns (note, merged, old_note_before). Raises NoteError
        conflict (409) with the conflict payload when the edit overlaps a concurrent one."""
        with self._lock:
            cur = self.get(nid)
            if cur is None:
                raise NoteError("not_found", 404)
            if cur.deleted is not None:
                raise NoteError("deleted", 409)
            if base_rev is None:
                raise NoteError("base_rev_required")
            if not isinstance(base_rev, int) or base_rev < 1 or base_rev > cur.rev:
                raise NoteError("bad_rev")
            new_title = cur.title if title is None else self._clean_title(title)
            new_tags = cur.tags if tags is None else self._clean_tags(tags)
            new_body = cur.body if body is None else str(body)
            if len(new_body) > MAX_BODY:
                raise NoteError("too_large", 413)
            merged = False
            if base_rev != cur.rev:
                base = self.version(nid, base_rev)
                if base is None:
                    raise NoteError("bad_rev")
                conflicts: list[dict] = []
                if body is not None:
                    m, conflicts = merge3(base["body"], new_body, cur.body)
                    if m is not None:
                        new_body = m
                fields = []
                if title is not None and new_title != base["title"] and cur.title != base["title"] \
                        and new_title != cur.title:
                    fields.append("title")
                elif title is not None and new_title == base["title"]:
                    new_title = cur.title                     # untouched on our side: keep theirs
                if tags is not None and sorted(new_tags) != sorted(base["tags"]) and sorted(cur.tags) != \
                        sorted(base["tags"]) and sorted(new_tags) != sorted(cur.tags):
                    fields.append("tags")
                elif tags is not None and sorted(new_tags) == sorted(base["tags"]):
                    new_tags = cur.tags
                if conflicts or fields:
                    raise NoteError("conflict", 409, current=cur.to_dict(), base_rev=base_rev, conflicts=conflicts,
                                    fields=fields)
                merged = True
            if new_title != cur.title:
                other = self.by_title(cur.project_id, new_title)
                if other is not None and other.id != nid:
                    raise NoteError("title_exists", 409, title=new_title)
            if new_title == cur.title and new_body == cur.body and new_tags == cur.tags:
                return cur, merged, None
            old = Note(**{**cur.__dict__})
            n = Note(**{**cur.__dict__})
            n.title, n.body, n.tags = new_title, new_body, new_tags
            n.rev, n.updated, n.device = cur.rev + 1, _now(), device
            live = {b.hash for b in lean_blocks(n.body)}
            n.lean = {h: r for h, r in cur.lean.items() if h in live}
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self._write(n, reason)
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            return n, merged, old

    def set_lean_result(self, nid: str, block_hash: str, result: dict) -> Note | None:
        """Lean results are metadata of the current text (no new revision)."""
        with self._lock:
            n = self.get(nid)
            if n is None:
                return None
            if block_hash in {b.hash for b in lean_blocks(n.body)}:
                n.lean[block_hash] = result
                self.db.execute("UPDATE notes SET lean=? WHERE id=?", (json.dumps(n.lean), nid))
            return n

    def delete(self, nid: str) -> Note | None:
        with self._lock:
            n = self.get(nid)
            if n is None or n.deleted is not None:
                return None
            n.deleted = _now()
            self.db.execute("UPDATE notes SET deleted=? WHERE id=?", (n.deleted, nid))
            self._index(n)
            return n

    def restore(self, nid: str) -> Note | None:
        with self._lock:
            n = self.get(nid)
            if n is None or n.deleted is None:
                return None
            if self.by_title(n.project_id, n.title) is not None:
                n.title = f"{n.title} ({time.strftime('%Y-%m-%d %H%M%S')})"[:MAX_TITLE]
                self.db.execute("UPDATE notes SET title=? WHERE id=?", (n.title, nid))
            n.deleted = None
            self.db.execute("UPDATE notes SET deleted=NULL WHERE id=?", (nid,))
            self._index(n)
            return n

    def purge_project_links(self) -> None:  # pragma: no cover (maintenance)
        with self._lock:
            self.db.execute("DELETE FROM links WHERE src NOT IN (SELECT id FROM notes)")

    # ------------------------------------------------------------ links
    def raw_links(self, project_id: str | None = None) -> list[tuple[str, Link]]:
        q = "SELECT l.src, l.kind, l.ref, l.label, l.locator FROM links l JOIN notes n ON n.id=l.src WHERE " \
            "n.deleted IS NULL"
        args: list = []
        if project_id is not None:
            q += " AND n.project_id=?"
            args.append(project_id)
        with self._lock:
            rows = self.db.execute(q, args).fetchall()
        return [(r[0], Link(r[1], r[2], r[3], r[4])) for r in rows]

    def resolve_note(self, project_id: str, ref: str) -> Note | None:
        n = self.get(ref, include_deleted=False)
        if n is not None and n.project_id == project_id:
            return n
        return self.by_title(project_id, ref)

    def backlinks(self, n: Note) -> list[dict]:
        out = []
        for src, ln in self.raw_links(n.project_id):
            if ln.kind == "note" and src != n.id and (ln.ref == n.id or ln.ref.strip().lower() == n.title.lower()):
                s = self.get(src)
                if s is not None:
                    out.append({"id": s.id, "title": s.title, "label": ln.label, "context": _context(s.body, ln)})
        return out

    def referencing(self, kind: str, ref: str) -> list[Note]:
        """Notes (any project) whose body links to a dossier / source / library result."""
        with self._lock:
            rows = self.db.execute("SELECT DISTINCT src FROM links WHERE kind=? AND lower(ref)=lower(?)",
                                   (kind, ref)).fetchall()
        return [n for n in (self.get(r[0], include_deleted=False) for r in rows) if n is not None]

    def rename_links(self, project_id: str, old_title: str, new_title: str, skip: str) -> list[tuple[str, str]]:
        """Bodies of the project's notes rewritten so that [[old title]] points to the new title. Returns
        [(note id, new body)] (the caller saves them as new revisions)."""
        pat = re.compile(r"\[\[\s*(?:note:)?" + re.escape(old_title.strip()) + r"\s*(\|[^\[\]\n]*)?\]\]", re.I)
        out = []
        for n in self.list(project_id):
            if n.id == skip:
                continue
            code = strip_code(n.body)
            spans = [m.span() for m in pat.finditer(code)]
            if not spans:
                continue
            body = n.body
            for s, e in reversed(spans):
                m = pat.match(body, s)
                if m is None:
                    continue
                label = m.group(1) or ""
                body = body[:s] + f"[[{new_title}{label}]]" + body[e:]
            if body != n.body:
                out.append((n.id, body))
        return out

    # ------------------------------------------------------------ search
    def search(self, q: str, project_id: str | None = None, limit: int = 30) -> list[dict]:
        fq = fts_query(q)
        if not fq:
            return []
        sql = ("SELECT f.note_id, snippet(notes_fts, 2, '[', ']', '…', 12), bm25(notes_fts, 0, 5.0, 1.0, 2.0) AS s "
               "FROM notes_fts f JOIN notes n ON n.id=f.note_id WHERE notes_fts MATCH ? AND n.deleted IS NULL")
        args: list = [fq]
        if project_id is not None:
            sql += " AND n.project_id=?"
            args.append(project_id)
        sql += " ORDER BY s LIMIT ?"
        args.append(limit)
        with self._lock:
            try:
                rows = self.db.execute(sql, args).fetchall()
            except sqlite3.OperationalError:
                return []
        out = []
        for nid, snip, score in rows:
            n = self.get(nid)
            if n is not None:
                out.append({**n.summary(), "snippet": snip, "score": round(-score, 3)})
        return out

    # ------------------------------------------------------------ attachments
    def add_attachment(self, nid: str, name: str, data: bytes) -> dict:
        n = self.get(nid, include_deleted=False)
        if n is None:
            raise NoteError("not_found", 404)
        if len(data) > MAX_ATTACHMENT:
            raise NoteError("too_large", 413)
        ctype = sniff(data)
        if ctype is None or not validate_image(data, ctype):
            raise NoteError("bad_type", 415)
        aid = "a-" + uuid.uuid4().hex[:16]
        safe = re.sub(r"[^\w.\- ]", "_", Path(str(name or "file")).name)[:80] or "file"
        stem = safe.rsplit(".", 1)[0] if "." in safe else safe
        safe = stem + SAFE_TYPES[ctype]
        path = self.att_dir / aid
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        meta = {"id": aid, "note_id": nid, "project_id": n.project_id, "name": safe, "mime": ctype, "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "t": _now()}
        with self._lock:
            self.db.execute("INSERT INTO attachments(id, note_id, project_id, name, mime, size, sha256, t) "
                            "VALUES (?,?,?,?,?,?,?,?)", tuple(meta.values()))
        return {**meta, "url": f"/api/attachments/{aid}", "markdown": (f"![{stem}](/api/attachments/{aid})"
                                                                         if ctype.startswith("image/") else
                                                                         f"[{safe}](/api/attachments/{aid})")}

    def attachment(self, aid: str) -> tuple[dict, Path] | None:
        if not re.fullmatch(r"a-[0-9a-f]{16}", aid or ""):
            return None
        with self._lock:
            r = self.db.execute("SELECT id, note_id, project_id, name, mime, size, sha256, t FROM attachments "
                                "WHERE id=? AND deleted IS NULL", (aid,)).fetchone()
        if r is None:
            return None
        p = self.att_dir / r[0]
        if not p.is_file():
            return None
        return dict(zip(("id", "note_id", "project_id", "name", "mime", "size", "sha256", "t"), r)), p

    def attachments(self, nid: str) -> list[dict]:
        with self._lock:
            rows = self.db.execute("SELECT id, name, mime, size, t FROM attachments WHERE note_id=? AND deleted IS NULL",
                                   (nid,)).fetchall()
        return [{"id": r[0], "name": r[1], "mime": r[2], "size": r[3], "t": r[4], "url": f"/api/attachments/{r[0]}"}
                for r in rows]

    def delete_attachment(self, aid: str) -> bool:
        with self._lock:
            cur = self.db.execute("UPDATE attachments SET deleted=? WHERE id=? AND deleted IS NULL", (_now(), aid))
            return cur.rowcount > 0

    def restore_attachment(self, aid: str) -> bool:
        with self._lock:
            cur = self.db.execute("UPDATE attachments SET deleted=NULL WHERE id=? AND deleted IS NOT NULL", (aid,))
            return cur.rowcount > 0


def _context(body: str, ln: Link, width: int = 90) -> str:
    m = re.search(r"\[\[\s*(?:note:)?" + re.escape(ln.ref) + r"\s*(\|[^\]]*)?\]\]", body, re.I)
    if not m:
        return ""
    s, e = max(0, m.start() - width // 2), min(len(body), m.end() + width // 2)
    return re.sub(r"\s+", " ", body[s:e]).strip()


# ---------------------------------------------------------------- graph
def build_graph(store: NoteStore, project_id: str, dossiers: list, sources: list[dict] | None = None,
                library=None, kinds: set[str] | None = None, edges: set[str] | None = None,
                tag: str | None = None, include_orphans: bool = True) -> dict:
    """Nodes: notes, dossiers, sources (+ unresolved targets marked `missing`). Edges: `link` (note → note /
    dossier / library result), `uses` (dossier → dossier: `uses` and `parent_id`), `cites` (note → source,
    dossier → source through `refs`)."""
    kinds = kinds or {"note", "dossier", "source"}
    edges = edges or {"link", "uses", "cites"}
    nodes: dict[str, dict] = {}
    out_edges: list[dict] = []
    notes = store.list(project_id, tag=tag)
    note_ids = {n.id for n in notes}
    if "note" in kinds:
        for n in notes:
            nodes[f"note:{n.id}"] = {"id": f"note:{n.id}", "kind": "note", "ref": n.id, "title": n.title,
                                     "tags": n.all_tags, "updated": n.updated}
    dmap = {d.id: d for d in dossiers}
    dtitle = {d.title.strip().lower(): d for d in dossiers}
    if "dossier" in kinds:
        for d in dossiers:
            nodes[f"dossier:{d.id}"] = {"id": f"dossier:{d.id}", "kind": "dossier", "ref": d.id, "title": d.title,
                                        "status": d.status, "dossier_kind": d.kind, "proved": d.proof_is_current}
    skeys = {s.get("key"): s for s in (sources or []) if s.get("key")}
    if "source" in kinds:
        for k, s in skeys.items():
            nodes[f"source:{k}"] = {"id": f"source:{k}", "kind": "source", "ref": k,
                                    "title": s.get("title") or k, "missing": False}

    def add_edge(src: str, dst: str, kind: str, **extra) -> None:
        if kind in edges and src in nodes and dst in nodes:
            out_edges.append({"source": src, "target": dst, "kind": kind, **extra})

    def ensure_source(key: str) -> str:
        nid = f"source:{key}"
        if nid not in nodes and "source" in kinds:
            nodes[nid] = {"id": nid, "kind": "source", "ref": key, "title": key, "missing": True}
        return nid

    for src, ln in store.raw_links(project_id):
        if src not in note_ids:
            continue
        s = f"note:{src}"
        if ln.kind == "note":
            t = store.resolve_note(project_id, ln.ref)
            if t is not None and t.id in note_ids:
                add_edge(s, f"note:{t.id}", "link", label=ln.label)
            elif "note" in kinds and t is None:
                nid = f"missing:{ln.ref.lower()}"
                nodes.setdefault(nid, {"id": nid, "kind": "note", "ref": ln.ref, "title": ln.ref, "missing": True})
                add_edge(s, nid, "link", label=ln.label)
        elif ln.kind == "dossier":
            d = dmap.get(ln.ref) or dtitle.get(ln.ref.strip().lower())
            if d is not None:
                add_edge(s, f"dossier:{d.id}", "link", label=ln.label)
        elif ln.kind == "lib" and library is not None:
            e = library.get(ln.ref)
            if e is not None and e.dossier in dmap:
                add_edge(s, f"dossier:{e.dossier}", "link", label=ln.label or ln.ref)
        elif ln.kind == "source":
            add_edge(s, ensure_source(ln.ref), "cites", locator=ln.locator)
    for d in dossiers:
        for u in list(d.uses or []) + ([d.parent_id] if d.parent_id else []):
            if u in dmap:
                add_edge(f"dossier:{d.id}", f"dossier:{u}", "uses")
        for r in d.refs or []:
            if isinstance(r, dict) and r.get("key"):
                add_edge(f"dossier:{d.id}", ensure_source(str(r["key"])), "cites", locator=r.get("locator", ""))
    if not include_orphans:
        used = {e["source"] for e in out_edges} | {e["target"] for e in out_edges}
        nodes = {k: v for k, v in nodes.items() if k in used}
    return {"nodes": list(nodes.values()), "edges": out_edges}


# ---------------------------------------------------------------- export
def note_markdown(n: Note) -> str:
    tags = " ".join(f"#{t}" for t in n.all_tags)
    head = f"# {n.title}\n\n" + (f"*{tags}*\n\n" if tags and not set(n.tags) <= set(parse_tags(n.body)) else "")
    return head + n.body.strip() + "\n"


def notebook_markdown(notes: list[Note], title: str) -> str:
    parts = [f"# {title}\n"]
    for n in sorted(notes, key=lambda n: n.title.lower()):
        parts.append("#" + note_markdown(n))                 # each note becomes a section
    return "\n\n".join(parts)


def markdown_to_tex_body(md: str, f) -> str:
    """Prose through texio.sanitize_markdown, Lean blocks as numbered listings, other code verbatim."""
    from .. import texio
    out, pos = [], 0
    for m in FENCE_RE.finditer(md):
        prose = md[pos:m.start()]
        if prose.strip():
            out.append(_tex_prose(prose, f))
        lang = (m.group(2).strip().lower().split() or [""])[0]
        out.append(texio.lean_listing(m.group(3), f=f) if lang in ("lean", "lean4") else
                   texio.lean_listing(m.group(3), numbers=False, f=f))
        pos = m.end()
    if md[pos:].strip():
        out.append(_tex_prose(md[pos:], f))
    return "\n\n".join(out)


def _tex_prose(text: str, f) -> str:
    from .. import texio
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)                       # images are not embedded
    text = LINK_RE.sub(lambda m: (parse_link(m.group(1)).label or parse_link(m.group(1)).ref)
                       if parse_link(m.group(1)) else m.group(0), text)
    out = []
    for block in re.split(r"(?m)^(#{1,6}\s+.*)$", text):
        h = re.match(r"(#{1,6})\s+(.*)", block.strip()) if block.strip().startswith("#") else None
        if h:
            cmd = "section*" if len(h.group(1)) <= 2 else "subsection*"
            out.append("\\" + cmd + "{" + texio.sanitize_markdown(h.group(2), f) + "}")
        elif block.strip():
            out.append(texio.sanitize_markdown(block.strip(), f))
    return "\n\n".join(out)


async def export_notes(notes: list[Note], title: str, fmt: str, lang: str, tmp_root: Path):
    """Markdown, HTML (self-contained) or PDF (XeLaTeX through the export code; HTML fallback)."""
    md = note_markdown(notes[0]) if len(notes) == 1 else notebook_markdown(notes, title)
    return await export_markdown(md, title, fmt, lang, tmp_root)


async def export_markdown(md: str, title: str, fmt: str, lang: str, tmp_root: Path):
    """The same for any Markdown (also the worksheets of `teaching`, D63); `tex`: the source of the PDF."""
    import asyncio
    import datetime as _dt
    import html as _html

    from .. import export as ex
    from .. import texio
    from ..dossiers import slugify
    name = slugify(title) or "notes"
    if fmt == "md":
        return ex.Export(f"{name}.md", ex.CONTENT_TYPES["md"], md.encode("utf-8"))

    def html_page() -> str:
        katex = ex._katex()
        body = texio.markdown_to_html(LINK_RE.sub(lambda m: (parse_link(m.group(1)).label or parse_link(m.group(1)).ref)
                                                  if parse_link(m.group(1)) else m.group(0), md), keep_tex=bool(katex))
        return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" '
                f'content="width=device-width,initial-scale=1"><title>{_html.escape(title)}</title>'
                f"<style>{ex._HTML_CSS}</style>{katex}</head><body>{body}</body></html>")
    if fmt == "html":
        return ex.Export(f"{name}.html", ex.CONTENT_TYPES["html"], (await asyncio.to_thread(html_page)).encode())
    if fmt not in ("pdf", "tex"):
        raise ValueError(fmt)
    f = await asyncio.to_thread(texio.fonts)
    c = ex.Content(title=title, kind="theorem", theorem="", nl_statement="", lean_statement="", notes="", informal="",
                   informal_is_explanation=False, proof="", proved=False, stamp=None, explanation="",
                   date=_dt.date.today(), lang=lang if lang in ex.T else "fr")

    def tex() -> str:
        body = markdown_to_tex_body(md.split("\n", 1)[1] if md.startswith("# ") else md, f)
        return "\n".join([ex._preamble(c, f), r"\begin{document}", r"\begin{center}{\LARGE\bfseries " +
                          ex._esc(title, f) + r"\par}\end{center}", body, r"\end{document}", ""])
    if fmt == "tex":
        return ex.Export(f"{name}.tex", "application/x-tex", (await asyncio.to_thread(tex)).encode("utf-8"))
    log = ""
    engines = ex._engines()
    if engines:
        pdf, log, _to = await ex.compile_pdf(await asyncio.to_thread(tex), Path(tmp_root), 120.0, engines)
        if pdf:
            return ex.Export(f"{name}.pdf", ex.CONTENT_TYPES["pdf"], pdf, "", "")
    return ex.Export(f"{name}.html", ex.CONTENT_TYPES["html"], (await asyncio.to_thread(html_page)).encode(), "html",
                     log)
