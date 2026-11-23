"""The local store of « Actualités »: one SQLite file (`<config>/news/news.sqlite`, WAL), bounded.

- deduplication: `key` is unique (an arXiv paper seen by two sources, or again in a later answer, is one row; its
  read / saved flags and its French summary survive a re-fetch);
- retention: an item leaves when it is older than its source's window (the user's `keep_days`, longer for slow
  sources) or when the store holds more than `max_items` (oldest first) — unless the user saved it;
- full-text search: FTS5 over title, abstract, authors and the French summary, accents ignored;
- everything is read back offline; nothing here touches the network."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, source TEXT NOT NULL, grp TEXT NOT NULL, kind TEXT NOT NULL,
  url TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', authors TEXT NOT NULL DEFAULT '[]',
  published REAL NOT NULL, fetched REAL NOT NULL, open INTEGER NOT NULL DEFAULT 0,
  branches TEXT NOT NULL DEFAULT '', cats TEXT NOT NULL DEFAULT '[]', extra TEXT NOT NULL DEFAULT '{}',
  read INTEGER NOT NULL DEFAULT 0, saved INTEGER NOT NULL DEFAULT 0,
  fr TEXT NOT NULL DEFAULT '', fr_model TEXT NOT NULL DEFAULT '', fr_t REAL NOT NULL DEFAULT 0,
  rel TEXT NOT NULL DEFAULT '[]', rel_max REAL NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS items_published ON items(published DESC);
CREATE INDEX IF NOT EXISTS items_source ON items(source);
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(title, summary, authors, fr,
  tokenize = 'unicode61 remove_diacritics 2');
"""
COLS = ("id, key, source, grp, kind, url, title, summary, authors, published, fetched, open, branches, cats, extra, "
        "read, saved, fr, fr_model, fr_t, rel, rel_max")
MAX_PAGE = 100


def fts_query(q: str) -> str:
    """User text → a safe FTS5 query (every word quoted, prefix match on the last one)."""
    words = re.findall(r"[\w\-']+", q or "", re.UNICODE)[:12]
    if not words:
        return ""
    parts = ['"' + w.replace('"', "") + '"' for w in words]
    parts[-1] += "*"
    return " AND ".join(parts)


def _row(r) -> dict:
    return {"id": r[0], "key": r[1], "source": r[2], "group": r[3], "kind": r[4], "url": r[5], "title": r[6],
            "summary": r[7], "authors": json.loads(r[8] or "[]"), "published": r[9], "fetched": r[10],
            "open": bool(r[11]), "branches": r[12].split(), "cats": json.loads(r[13] or "[]"),
            "extra": json.loads(r[14] or "{}"), "read": bool(r[15]), "saved": bool(r[16]), "fr": r[17],
            "fr_model": r[18], "fr_t": r[19], "projects": json.loads(r[20] or "[]"), "relevance": r[21]}


class NewsStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(self.root / "news.sqlite"), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self.db.close()

    # ------------------------------------------------------------ writes
    def _index(self, rid: int, title: str, summary: str, authors: list[str], fr: str) -> None:
        self.db.execute("DELETE FROM items_fts WHERE rowid = ?", (rid,))
        self.db.execute("INSERT INTO items_fts(rowid, title, summary, authors, fr) VALUES (?,?,?,?,?)",
                        (rid, title, summary, " ; ".join(authors), fr))

    def upsert(self, source: str, group: str, items: list[dict], *, now: float | None = None,
               min_published: float = 0.0) -> dict:
        """Insert the new items, refresh the changed ones (flags kept). Items published before `min_published`
        are not stored. Returns {"new": n, "updated": n, "seen": n}."""
        t = now or time.time()
        new = upd = 0
        with self._lock:
            self.db.execute("BEGIN")
            try:
                for it in items:
                    pub = float(it.get("published") or 0.0) or t
                    if pub < min_published:
                        continue
                    branches = " ".join(it.get("branches") or [])
                    row = self.db.execute("SELECT id, title, summary, source, fr FROM items WHERE key = ?",
                                          (it["key"],)).fetchone()
                    vals = (it["kind"], it["url"], it["title"], it.get("summary", ""),
                            json.dumps(it.get("authors") or [], ensure_ascii=False), int(bool(it.get("open"))),
                            branches, json.dumps(it.get("cats") or [], ensure_ascii=False),
                            json.dumps(it.get("extra") or {}, ensure_ascii=False))
                    if row is None:
                        cur = self.db.execute(
                            "INSERT INTO items(key, source, grp, kind, url, title, summary, authors, open, branches, "
                            "cats, extra, published, fetched) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (it["key"], source, group, *vals, pub, t))
                        self._index(cur.lastrowid, it["title"], it.get("summary", ""), it.get("authors") or [], "")
                        new += 1
                        continue
                    # a paper found by the « AI for maths » query belongs to that source, whoever saw it first
                    takeover = source == "arxiv-ai" and row[3] != source
                    if row[1] != it["title"] or row[2] != it.get("summary", "") or takeover:
                        self.db.execute(
                            "UPDATE items SET kind=?, url=?, title=?, summary=?, authors=?, open=?, branches=?, cats=?, "
                            "extra=?" + (", source=?, grp=?" if takeover else "") + " WHERE id=?",
                            (*vals, *((source, group) if takeover else ()), row[0]))
                        self._index(row[0], it["title"], it.get("summary", ""), it.get("authors") or [], row[4])
                        upd += 1
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
        return {"new": new, "updated": upd, "seen": len(items)}

    def purge(self, *, keep_days: float, max_items: int, source_days: dict[str, float] | None = None,
              now: float | None = None) -> int:
        """Retention (see the module docstring). Returns the number of items removed."""
        t = now or time.time()
        n = 0
        with self._lock:
            srcs = [r[0] for r in self.db.execute("SELECT DISTINCT source FROM items")]
            for s in srcs:
                days = float((source_days or {}).get(s) or keep_days)
                cur = self.db.execute("DELETE FROM items WHERE saved = 0 AND source = ? AND published < ?",
                                      (s, t - days * 86400))
                n += cur.rowcount
            total = self.db.execute("SELECT COUNT(*) FROM items WHERE saved = 0").fetchone()[0]
            if total > max_items:
                cur = self.db.execute(
                    "DELETE FROM items WHERE id IN (SELECT id FROM items WHERE saved = 0 "
                    "ORDER BY published ASC, id ASC LIMIT ?)", (total - max_items,))
                n += cur.rowcount
            if n:
                self.db.execute("DELETE FROM items_fts WHERE rowid NOT IN (SELECT id FROM items)")
        return n

    def drop_source(self, source: str) -> int:
        """Forget a removed user feed (its saved items stay)."""
        with self._lock:
            n = self.db.execute("DELETE FROM items WHERE source = ? AND saved = 0", (source,)).rowcount
            self.db.execute("DELETE FROM items_fts WHERE rowid NOT IN (SELECT id FROM items)")
        return n

    def set_flags(self, item_id: int, *, read: bool | None = None, saved: bool | None = None) -> dict | None:
        with self._lock:
            if read is not None:
                self.db.execute("UPDATE items SET read = ? WHERE id = ?", (int(read), item_id))
            if saved is not None:
                self.db.execute("UPDATE items SET saved = ? WHERE id = ?", (int(saved), item_id))
        return self.get(item_id)

    def set_summary(self, item_id: int, text: str, model: str, now: float | None = None) -> dict | None:
        with self._lock:
            self.db.execute("UPDATE items SET fr = ?, fr_model = ?, fr_t = ? WHERE id = ?",
                            (text, model, now or time.time(), item_id))
            it = self.get(item_id)
            if it is not None:
                self._index(item_id, it["title"], it["summary"], it["authors"], text)
        return it

    def set_relevance(self, rows: list[tuple[int, list[dict], float]]) -> None:
        """rows: (item id, [{project, score, terms}], best score)."""
        with self._lock:
            self.db.execute("BEGIN")
            try:
                self.db.execute("UPDATE items SET rel = '[]', rel_max = 0 WHERE rel_max > 0")
                self.db.executemany("UPDATE items SET rel = ?, rel_max = ? WHERE id = ?",
                                    [(json.dumps(m, ensure_ascii=False), mx, i) for i, m, mx in rows])
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------ reads
    def get(self, item_id: int) -> dict | None:
        with self._lock:
            r = self.db.execute(f"SELECT {COLS} FROM items WHERE id = ?", (item_id,)).fetchone()
        return _row(r) if r else None

    def by_key(self, key: str) -> dict | None:
        with self._lock:
            r = self.db.execute(f"SELECT {COLS} FROM items WHERE key = ?", (key,)).fetchone()
        return _row(r) if r else None

    @staticmethod
    def _where(*, branches=None, source=None, group=None, open_=None, projects=None, unread=None, saved=None,
               followed=None, sources_on=None) -> tuple[str, list]:
        w, a = [], []
        if branches:
            w.append("(" + " OR ".join("(' ' || branches || ' ') LIKE ?" for _ in branches) + ")")
            a += [f"% {b} %" for b in branches]
        if followed:                       # the user's domains: tagged with one of them, or not tagged at all
            w.append("(branches = '' OR " + " OR ".join("(' ' || branches || ' ') LIKE ?" for _ in followed) + ")")
            a += [f"% {b} %" for b in followed]
        if source:
            w.append("source = ?")
            a.append(source)
        if group:
            w.append("grp = ?")
            a.append(group)
        if sources_on is not None:         # sources the user turned off are hidden (saved items stay visible)
            w.append("(saved = 1 OR source IN (" + ",".join("?" for _ in sources_on) + "))" if sources_on
                     else "saved = 1")
            a += list(sources_on)
        if open_:
            w.append("open = 1")
        if projects is True:
            w.append("rel_max > 0")
        elif isinstance(projects, str) and projects:
            w.append("rel LIKE ?")
            a.append('%"project": ' + json.dumps(projects) + "%")
        if unread:
            w.append("read = 0")
        if saved:
            w.append("saved = 1")
        return (" WHERE " + " AND ".join(w)) if w else "", a

    def query(self, *, q: str = "", limit: int = 40, offset: int = 0, order: str = "date", **filters) -> dict:
        """→ {"items": [...], "total": n}. `order`: date | relevance."""
        where, args = self._where(**filters)
        limit = max(1, min(int(limit), MAX_PAGE))
        offset = max(0, int(offset))
        fq = fts_query(q)
        by = "rel_max DESC, published DESC, id DESC" if order == "relevance" else "published DESC, id DESC"
        with self._lock:
            if fq:
                base = f"FROM items JOIN items_fts ON items_fts.rowid = items.id{where}" \
                       f"{' AND' if where else ' WHERE'} items_fts MATCH ?"
                args = args + [fq]
                cols = ", ".join("items." + c.strip() for c in COLS.split(","))
                try:
                    total = self.db.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
                    rows = self.db.execute(f"SELECT {cols} {base} ORDER BY {by} LIMIT ? OFFSET ?",
                                           args + [limit, offset]).fetchall()
                except sqlite3.OperationalError:
                    total, rows = 0, []
            else:
                total = self.db.execute(f"SELECT COUNT(*) FROM items{where}", args).fetchone()[0]
                rows = self.db.execute(f"SELECT {COLS} FROM items{where} ORDER BY {by} LIMIT ? OFFSET ?",
                                       args + [limit, offset]).fetchall()
        return {"items": [_row(r) for r in rows], "total": total}

    def count(self, **filters) -> int:
        where, args = self._where(**filters)
        with self._lock:
            return self.db.execute(f"SELECT COUNT(*) FROM items{where}", args).fetchone()[0]

    def mark_read(self, **filters) -> int:
        where, args = self._where(**filters)
        with self._lock:
            return self.db.execute(f"UPDATE items SET read = 1{where}{' AND' if where else ' WHERE'} read = 0",
                                   args).rowcount

    def stats(self) -> dict:
        with self._lock:
            total, unread, saved = self.db.execute(
                "SELECT COUNT(*), COALESCE(SUM(read = 0), 0), COALESCE(SUM(saved), 0) FROM items").fetchone()
            per = {r[0]: {"items": r[1], "unread": r[2], "newest": r[3]} for r in self.db.execute(
                "SELECT source, COUNT(*), SUM(read = 0), MAX(published) FROM items GROUP BY source")}
        return {"items": total, "unread": unread, "saved": saved, "sources": per}

    def corpus(self) -> list[tuple[int, str, str]]:
        """(id, title, abstract) of every item, for the local relevance pass."""
        with self._lock:
            return list(self.db.execute("SELECT id, title, summary FROM items"))

    def pending_summaries(self, limit: int, *, followed=None, sources_on=None) -> list[dict]:
        """Unread items without a French summary, the ones matching a project first, then the newest."""
        where, args = self._where(unread=True, followed=followed, sources_on=sources_on)
        with self._lock:
            rows = self.db.execute(
                f"SELECT {COLS} FROM items{where} AND fr = '' AND length(summary) >= 200 "
                "ORDER BY (rel_max > 0) DESC, published DESC LIMIT ?", args + [limit]).fetchall()
        return [_row(r) for r in rows]
