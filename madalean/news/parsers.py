"""Parsers of the news sources → normalised items. Everything fetched is untrusted
(docs/SECURITY.md « News feeds »).

An item is a plain dict:
    {key, url, title, summary, authors, published, kind, open, cats, extra}
`title` / `summary` / `authors` are plain text: HTML is reduced to its text (scripts and styles dropped), control,
zero-width and bidirectional-override characters are removed, e-mail addresses are masked, lengths are capped.
`url` is http(s) only. `key` is the deduplication key (an arXiv paper has one key whatever its version or the
feed it came from). XML goes through `research.safety.parse_xml` (DTDs and entity declarations are refused)."""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from ..research.safety import UnsafeInput, parse_xml

MAX_TITLE = 300
MAX_SUMMARY = 4000
MAX_AUTHORS = 12
MAX_ITEMS = 400                    # per answer, whatever the source sends


class ParseError(Exception):
    pass


# ---------------------------------------------------------------- text hygiene
_CTRL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁠-⁩﻿]")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_WS = re.compile(r"[ \t\r\f\v]*\n[ \t\r\f\v\n]*")
_SP = re.compile(r"[ \t\r\f\v]+")
_BLOCK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "figure", "ul", "ol"}
_SKIP = {"script", "style", "noscript", "template", "iframe", "object", "svg", "math", "figure", "figcaption"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def clean_text(value, limit: int = MAX_SUMMARY, one_line: bool = False) -> str:
    """Untrusted text or HTML → plain text."""
    s = value if isinstance(value, str) else ""
    if not s:
        return ""
    s = s[: limit * 12]                       # bound the work before parsing
    if "<" in s or "&" in s:
        p = _Text()
        try:
            p.feed(s)
            p.close()
            s = "".join(p.out)
        except Exception:  # noqa: BLE001 (broken markup: drop every tag the blunt way)
            s = html.unescape(re.sub(r"<[^>]*>", " ", s))
        if "&" in s and re.search(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);", s):
            s = html.unescape(s)              # doubly escaped feeds (« Sp&amp;#x00e4;th »)
            s = re.sub(r"<[^>]{0,400}>", " ", s)
    s = _CTRL.sub("", s).replace("\xa0", " ")
    s = _EMAIL.sub("[e-mail]", s)
    s = _SP.sub(" ", s)
    s = " ".join(s.split()) if one_line else _WS.sub("\n", s).strip()
    if len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def safe_url(value, base: str = "") -> str:
    """http(s) URL without credentials, else ''. (Shown as a link the user opens in the browser.)"""
    s = _CTRL.sub("", value if isinstance(value, str) else "").strip()
    if not s or len(s) > 2000:
        return ""
    try:
        u = urlsplit(s)
    except ValueError:
        return ""
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        return ""
    return urlunsplit(u)


def parse_date(value) -> float:
    """RFC 822, ISO 8601 or epoch seconds → epoch (0.0 when unreadable); never in the future."""
    t = 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        t = float(value)
    elif isinstance(value, str) and value.strip():
        s = value.strip()
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            t = (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
        except ValueError:
            try:
                d = parsedate_to_datetime(s)
                t = (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
            except (TypeError, ValueError, IndexError):
                t = 0.0
    return max(0.0, min(t, time.time()))


def _item(key: str, url: str, title: str, summary: str = "", authors=None, published: float = 0.0,
          kind: str = "post", open_: bool = False, cats=None, extra: dict | None = None) -> dict | None:
    title = clean_text(title, MAX_TITLE, one_line=True)
    url = safe_url(url)
    if not title or not url or not key:
        return None
    names = [clean_text(a, 80, one_line=True) for a in (authors or [])][:MAX_AUTHORS]
    tags = [clean_text(str(c), 60, one_line=True) for c in (cats or [])][:20]
    return {"key": key[:200], "url": url, "title": title, "summary": clean_text(summary, MAX_SUMMARY),
            "authors": [n for n in names if n], "published": float(published or 0.0), "kind": kind,
            "open": bool(open_), "cats": [c for c in tags if c], "extra": extra or {}}


def _url_key(url: str) -> str:
    u = urlsplit(url)
    return "url:" + (u.hostname or "").lower().removeprefix("www.") + u.path.rstrip("/") + ("?" + u.query if u.query else "")


# ---------------------------------------------------------------- XML helpers
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _child(el, *names: str):
    for c in el:
        if _local(c.tag) in names:
            return c
    return None


def _children(el, name: str):
    return [c for c in el if _local(c.tag) == name]


def _text(el) -> str:
    return "".join(el.itertext()) if el is not None else ""


_END = re.compile(rb"</(rss|feed|rdf:RDF)\s*>", re.I)


def _root(data: bytes | str):
    raw = data.encode("utf-8") if isinstance(data, str) else data
    try:
        return parse_xml(raw)
    except UnsafeInput as e:
        # some servers (a CDN in front of a feed served as text/html) append a script after the document: keep
        # the document only, and never look at what follows it
        ends = list(_END.finditer(raw))
        if e.kind == "bad_xml" and ends and raw[ends[-1].end():].strip():
            try:
                return parse_xml(raw[:ends[-1].end()])
            except UnsafeInput as e2:
                raise ParseError(f"xml: {e2}") from e2
        raise ParseError(f"xml: {e}") from e


# ---------------------------------------------------------------- RSS 2.0 / Atom
def parse_feed(data: bytes | str, *, kind: str = "post", open_: bool = False) -> list[dict]:
    """Any RSS 2.0 or Atom feed (blogs, GitHub releases, societies, the user's own feeds)."""
    root = _root(data)
    out: list[dict] = []
    name = _local(root.tag)
    if name == "feed":                                            # Atom
        for e in _children(root, "entry")[:MAX_ITEMS]:
            link = ""
            for ln in _children(e, "link"):
                if ln.get("rel", "alternate") == "alternate" and ln.get("href"):
                    link = ln.get("href", "")
                    break
            ident = _text(_child(e, "id")).strip()
            link = link or (ident if ident.startswith("http") else "")
            body = _child(e, "summary")
            if body is None or not _text(body).strip():
                body = _child(e, "content") if _child(e, "content") is not None else body
            authors = [_text(_child(a, "name")) for a in _children(e, "author")]
            cats = [c.get("term", "") for c in _children(e, "category")]
            when = _text(_child(e, "published")) or _text(_child(e, "updated"))
            it = _item(_url_key(safe_url(link)) if safe_url(link) else "", link, _text(_child(e, "title")),
                       _text(body), authors, parse_date(when), kind, open_, cats)
            if it:
                out.append(it)
        return out
    channel = _child(root, "channel") if name == "rss" else (root if name == "channel" else None)
    if channel is None and name == "rdf":                         # RSS 1.0: items beside the channel
        channel = root
    if channel is None:
        raise ParseError("not an RSS or Atom feed")
    for e in _children(channel, "item")[:MAX_ITEMS]:
        link = _text(_child(e, "link")).strip()
        guid = _text(_child(e, "guid")).strip()
        link = link or (guid if guid.startswith("http") else "")
        body, full = _child(e, "description"), _child(e, "encoded")
        if (body is None or not _text(body).strip()) and full is not None:
            body = full                                             # no excerpt: the full text, cut to MAX_SUMMARY
        authors = [_text(c) for c in e if _local(c.tag) in ("creator", "author")]
        cats = [_text(c) for c in _children(e, "category")]
        when = _text(_child(e, "pubdate")) or _text(_child(e, "date"))
        it = _item(_url_key(safe_url(link)) if safe_url(link) else "", link, _text(_child(e, "title")), _text(body),
                   authors, parse_date(when), kind, open_, cats)
        if it:
            out.append(it)
    return out


# ---------------------------------------------------------------- arXiv API (Atom)
_ARXIV_ID = re.compile(r"arxiv\.org/abs/([a-z-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5})(v\d+)?", re.I)


def parse_arxiv(data: bytes | str) -> list[dict]:
    """export.arxiv.org/api/query answer. The key ignores the version; `extra.arxiv` is the identifier that the
    Sources screen imports (« Ajouter aux Sources du projet »)."""
    root = _root(data)
    if _local(root.tag) != "feed":
        raise ParseError("not an arXiv Atom answer")
    out: list[dict] = []
    for e in _children(root, "entry")[:MAX_ITEMS]:
        m = _ARXIV_ID.search(_text(_child(e, "id")))
        if not m:
            continue
        aid = m.group(1)
        cats = [c.get("term", "") for c in _children(e, "category")]
        prim = _child(e, "primary_category")
        primary = prim.get("term", "") if prim is not None else (cats[0] if cats else "")
        if primary and primary in cats:
            cats = [primary] + [c for c in cats if c != primary]
        authors = [_text(_child(a, "name")) for a in _children(e, "author")]
        extra = {"arxiv": aid, "primary": clean_text(primary, 30, True)}
        comment = clean_text(_text(_child(e, "comment")), 200, True)
        if comment:
            extra["comment"] = comment
        it = _item(f"arxiv:{aid}", f"https://arxiv.org/abs/{aid}", _text(_child(e, "title")),
                   _text(_child(e, "summary")), authors, parse_date(_text(_child(e, "published"))), "paper", False,
                   cats, extra)
        if it:
            it["summary"] = " ".join(it["summary"].split())       # arXiv wraps abstracts at 80 columns
            out.append(it)
    return out


# ---------------------------------------------------------------- GitHub REST API (releases, commits)
_GH = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/")
_TRAILER = re.compile(r"(?im)^(co-authored-by|signed-off-by|reviewed-by)\s*:.*$")


def _json_list(data: bytes | str) -> list:
    try:
        v = json.loads(data)
    except ValueError as e:
        raise ParseError(f"json: {e}") from e
    if not isinstance(v, list):
        msg = v.get("message") if isinstance(v, dict) else ""
        raise ParseError(str(msg or "unexpected answer")[:200])
    return v


def parse_github_releases(data: bytes | str) -> list[dict]:
    """api.github.com/repos/<owner>/<repo>/releases: published releases (drafts skipped)."""
    out = []
    for r in _json_list(data)[:MAX_ITEMS]:
        if not isinstance(r, dict) or r.get("draft"):
            continue
        url = safe_url(r.get("html_url"))
        m = _GH.match(url)
        tag = clean_text(str(r.get("name") or r.get("tag_name") or ""), 80, True)
        if not m or not tag:
            continue
        repo = m.group(2)
        title = f"{repo} {tag}" + (" (pre-release)" if r.get("prerelease") else "")
        it = _item(_url_key(url), url, title, str(r.get("body") or ""), [],
                   parse_date(r.get("published_at") or r.get("created_at")), "release", False, [],
                   {"repo": f"{m.group(1)}/{repo}", "tag": clean_text(str(r.get("tag_name") or ""), 60, True),
                    "prerelease": bool(r.get("prerelease"))})
        if it:
            out.append(it)
    return out


def parse_github_commits(data: bytes | str) -> list[dict]:
    """api.github.com/repos/<owner>/<repo>/commits: one item per commit — the first line is the title, the rest
    the description (trailers such as « Co-authored-by » dropped; e-mail addresses are never kept)."""
    out = []
    for r in _json_list(data)[:MAX_ITEMS]:
        c = r.get("commit") if isinstance(r, dict) else None
        if not isinstance(c, dict) or not isinstance(c.get("message"), str):
            continue
        url = safe_url(r.get("html_url"))
        m = _GH.match(url)
        if not m:
            continue
        head, _, rest = c["message"].partition("\n")
        who = c.get("author") if isinstance(c.get("author"), dict) else {}
        it = _item(_url_key(url), url, head, _TRAILER.sub("", rest), [str(who.get("name") or "")],
                   parse_date(who.get("date")), "change", False, [], {"repo": f"{m.group(1)}/{m.group(2)}"})
        if it:
            out.append(it)
    return out


# ---------------------------------------------------------------- Stack Exchange API (MathOverflow)
def parse_stackexchange(data: bytes | str) -> list[dict]:
    """api.stackexchange.com/2.3/questions answer (filter `withbody`). `extra.backoff` carries the API's own
    request to slow down, when it sends one."""
    try:
        v = json.loads(data)
    except ValueError as e:
        raise ParseError(f"json: {e}") from e
    if not isinstance(v, dict) or not isinstance(v.get("items"), list):
        raise ParseError(str(v.get("error_message") if isinstance(v, dict) else "unexpected answer")[:200])
    out = []
    for q in v["items"][:MAX_ITEMS]:
        if not isinstance(q, dict) or not isinstance(q.get("question_id"), int):
            continue
        tags = [str(t) for t in q.get("tags") or [] if isinstance(t, str)]
        owner = q.get("owner") if isinstance(q.get("owner"), dict) else {}
        qid = q["question_id"]
        it = _item(f"mo:{qid}", f"https://mathoverflow.net/questions/{qid}", html.unescape(str(q.get("title") or "")),
                   str(q.get("body") or ""), [html.unescape(str(owner.get("display_name") or ""))],
                   parse_date(q.get("creation_date")), "question", "open-problems" in tags or "open-problem" in tags,
                   tags, {"score": int(q.get("score") or 0), "answers": int(q.get("answer_count") or 0),
                          "licence": clean_text(str(q.get("content_license") or ""), 30, True)})
        if it:
            out.append(it)
    return out


def stackexchange_backoff(data: bytes | str) -> int:
    try:
        v = json.loads(data)
        return max(0, int(v.get("backoff") or 0)) if isinstance(v, dict) else 0
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------- Erdős problems (YAML table of the community database)
_ERDOS_TOP = re.compile(r'^  ([a-z_]+):\s*(.*)$')
_ERDOS_SUB = re.compile(r'^    ([a-z_]+):\s*(.*)$')


def _scalar(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    return s


def _inline_list(s: str) -> list[str]:
    s = s.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return []
    return [x for x in (_scalar(p) for p in s[1:-1].split(",")) if x]


def parse_erdos(data: bytes | str, *, limit: int = 60) -> list[dict]:
    """`data/problems.yaml` of github.com/teorth/erdosproblems (Apache-2.0): number, prize, status, tags — no
    statement (the statements live on erdosproblems.com, linked). A small reader of that regular layout (no YAML
    dependency, nothing is evaluated). One item per problem and status date, the `limit` most recent changes."""
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    if not re.search(r'(?m)^- number:\s*"?\d+', text):
        raise ParseError("not the Erdős problems table")
    probs: list[dict] = []
    for block in re.split(r"(?m)^(?=- number:)", text):
        m = re.match(r'- number:\s*"?(\d+)"?', block)
        if not m:
            continue
        p: dict = {"number": int(m.group(1))}
        top = ""
        for line in block.splitlines()[1:]:
            if (t := _ERDOS_TOP.match(line)) is not None:
                top = t.group(1)
                val = t.group(2)
                if val.startswith("["):
                    p[top] = _inline_list(val)
                elif val:
                    p[top] = _scalar(val)
                else:
                    p[top] = {}
            elif (s := _ERDOS_SUB.match(line)) is not None and isinstance(p.get(top), dict):
                p[top][s.group(1)] = _scalar(s.group(2))
        probs.append(p)

    def when(p: dict) -> str:
        st = p.get("status")
        return str(st.get("last_update") or "") if isinstance(st, dict) else ""
    probs = [p for p in probs if when(p)]
    probs.sort(key=lambda p: (when(p), p["number"]), reverse=True)
    out = []
    for p in probs[:limit]:
        n, st = p["number"], p["status"]
        state = clean_text(str(st.get("state") or "unknown"), 60, True)
        tags = [str(t) for t in p.get("tags") or []] if isinstance(p.get("tags"), list) else []
        prize = clean_text(str(p.get("prize") or ""), 20, True)
        oeis = [str(x) for x in p.get("oeis") or [] if re.fullmatch(r"A\d{6}", str(x))] \
            if isinstance(p.get("oeis"), list) else []
        formal = p.get("formalized").get("state") if isinstance(p.get("formalized"), dict) else ""
        lines = [f"Status: {state} (updated {when(p)})."]
        if prize and prize.lower() != "no":
            lines.append(f"Prize: {prize}.")
        if tags:
            lines.append("Topics: " + ", ".join(tags) + ".")
        if formal == "yes":
            lines.append("A Lean statement exists.")
        if oeis:
            lines.append("OEIS: " + ", ".join(oeis) + ".")
        it = _item(f"erdos:{n}@{when(p)}", f"https://www.erdosproblems.com/{n}", f"Erdős Problem #{n} — {state}",
                   "\n".join(lines), [], parse_date(when(p)), "problem", state.lower().startswith("open"), tags,
                   {"erdos": n, "state": state, "prize": prize, "oeis": oeis[:6]})
        if it:
            out.append(it)
    return out


PARSERS = {"feed": parse_feed, "arxiv": parse_arxiv, "stackexchange": parse_stackexchange, "erdos": parse_erdos,
           "github_releases": parse_github_releases, "github_commits": parse_github_commits}
