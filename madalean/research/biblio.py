"""Bibliographic records: CSL-JSON is the internal model; BibTeX, RIS, CSL-JSON and Zotero RDF in and out; stable
unique BibTeX keys; deduplication; citations `[@key, Thm 2.1]` in model/user text (validated against the keys that
really exist — an invented reference is removed by code, never printed); reference formatting for exports;
Mathlib's own `docs/references.bib` as a read-only shelf.

A record (`item`) is a CSL-JSON dict plus a few extra keys that CSL processors ignore: `arxiv`, `zbl`, `mrnumber`,
`msc` (list), `zbmath` (document id), `openalex`."""
from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ================================================================ LaTeX ⇄ Unicode (BibTeX field values)
_ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304", ".": "\u0307",
            "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a", "d": "\u0323",
            "b": "\u0331"}
_SYMBOLS = {"ss": "ß", "o": "ø", "O": "Ø", "aa": "å", "AA": "Å", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ",
            "l": "ł", "L": "Ł", "i": "ı", "j": "ȷ", "dh": "ð", "DH": "Ð", "th": "þ", "TH": "Þ", "dj": "đ", "DJ": "Đ",
            "textendash": "–", "textemdash": "—", "&": "&", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{",
            "}": "}", "ldots": "…", "dots": "…", "textquoteright": "’", "textquoteleft": "‘", "S": "§",
            "cprime": "ʹ", "cdprime": "ʺ", "textbackslash": "\\"}
_MATH_SEG = re.compile(r"(\$\$.+?\$\$|\$[^$]+\$|\\\(.+?\\\))", re.S)


def latex_to_unicode(s: str) -> str:
    """BibTeX value → readable Unicode (accents, ligatures, dashes, protective braces). Math segments are kept."""
    if not s:
        return ""
    parts = _MATH_SEG.split(s)
    out = []
    for i, p in enumerate(parts):
        if i % 2:
            out.append(p)
            continue
        p = re.sub(r"\\([" + re.escape("'`^\"~=.") + r"])\s*\{?\\?([A-Za-z])\}?",
                   lambda m: unicodedata.normalize("NFC", m.group(2) + _ACCENTS[m.group(1)]), p)
        p = re.sub(r"\\([uvHckrdb])\s*\{\\?([A-Za-z])\}|\\([uvHckrdb])\s+([A-Za-z])",
                   lambda m: unicodedata.normalize("NFC", (m.group(2) or m.group(4)) +
                                                   _ACCENTS[m.group(1) or m.group(3)]), p)
        p = re.sub(r"\\(ss|aa|AA|ae|AE|oe|OE|dh|DH|th|TH|dj|DJ|o|O|l|L|i|j|textendash|textemdash|ldots|dots|"
                   r"textquoteright|textquoteleft|S|cprime|cdprime)(?![A-Za-z])\s?(\{\})?",
                   lambda m: _SYMBOLS[m.group(1)], p)
        p = re.sub(r"\\([&%$#_{}])", lambda m: _SYMBOLS[m.group(1)], p)
        p = re.sub(r"\\(?:emph|textit|textbf|textsc|textrm|textsf|texttt|mbox|url|bf|it|em|sc|rm)\s*", "", p)
        p = re.sub(r"\\[A-Za-z]+\s*", "", p)            # any other command: formatting, dropped
        p = p.replace("---", "—").replace("--", "–").replace("~", "\u00a0").replace("``", "“").replace("''", "”")
        p = p.replace("{", "").replace("}", "")
        out.append(p)
    return re.sub(r"[ \t\r\n]+", " ", "".join(out)).strip()


def unicode_to_bibtex(s: str, protect_case: bool = False) -> str:
    """Unicode value → safe BibTeX field content. Every TeX special outside math is escaped; math survives only if
    texio's sanitiser accepts it (allow-listed commands), else it is escaped too. Braces always balance."""
    from .. import texio
    if not s:
        return ""
    parts = _MATH_SEG.split(str(s))
    out = []
    for i, p in enumerate(parts):
        if i % 2:
            inner = p
            sane = texio.sanitize_math(inner)
            if not sane.startswith("\\texttt"):
                out.append(sane if sane.startswith("$") else "$" + sane[2:-2] + "$")
                continue
        esc = "".join({"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$",
                       "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}.get(c, c)
                      for c in p)
        if protect_case:                 # keep the capitals of names / acronyms (BibTeX styles lower-case titles)
            esc = re.sub(r"(?<![\\\w{])([A-Za-z]*[A-Z][A-Za-z]*(?:[-'’][A-Za-z]+)*)",
                         lambda m: m.group(1) if (i == 0 and m.start() == 0 and not any(c.isupper() for c in
                                                                                       m.group(1)[1:]))
                         else "{" + m.group(1) + "}", esc)
        out.append(esc)
    res = "".join(out).replace("\n", " ")
    return res


# ================================================================ BibTeX parser
@dataclass
class BibEntry:
    type: str
    key: str
    fields: dict = field(default_factory=dict)     # lower-case name -> raw value (braces stripped one level)


class _Scanner:
    def __init__(self, text: str):
        self.s, self.i, self.n = text, 0, len(text)

    def ws(self):
        while self.i < self.n and self.s[self.i].isspace():
            self.i += 1

    def peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def braced(self) -> str:
        """At '{': returns the content up to the matching '}' (nested braces kept)."""
        depth, start = 0, self.i
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                self.i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    self.i += 1
                    return self.s[start + 1:self.i - 1]
            self.i += 1
        raise ValueError("unbalanced braces")

    def quoted(self) -> str:
        self.i += 1
        start, depth = self.i, 0
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                self.i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == '"' and depth == 0:
                self.i += 1
                return self.s[start:self.i - 1]
            self.i += 1
        raise ValueError("unterminated string")

    def ident(self) -> str:
        m = re.compile(r"[^\s,={}()\"#%']+").match(self.s, self.i)
        if not m:
            return ""
        self.i = m.end()
        return m.group(0)


def parse_bibtex_entries(text: str, max_entries: int = 20000) -> tuple[list[BibEntry], list[str]]:
    """Tolerant BibTeX parser: @string macros, # concatenation, @comment/@preamble, both delimiters, errors
    skipped (reported in the second list)."""
    sc = _Scanner(text)
    strings = {m: m.capitalize() for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                            "nov", "dec")}
    out: list[BibEntry] = []
    errors: list[str] = []
    while sc.i < sc.n and len(out) < max_entries:
        at = sc.s.find("@", sc.i)
        if at < 0:
            break
        sc.i = at + 1
        typ = sc.ident().lower()
        sc.ws()
        if sc.peek() not in "{(":
            continue
        close = "}" if sc.peek() == "{" else ")"
        if typ in ("comment",):
            try:
                sc.braced() if close == "}" else None
            except ValueError:
                pass
            continue
        sc.i += 1
        try:
            if typ in ("preamble",):
                depth = 1
                while sc.i < sc.n and depth:
                    depth += {"{": 1, "}": -1, "(": 0, ")": 0}.get(sc.s[sc.i], 0)
                    sc.i += 1
                continue
            sc.ws()
            if typ == "string":
                name = sc.ident().lower()
                sc.ws()
                if sc.peek() == "=":
                    sc.i += 1
                    strings[name] = _value(sc, strings)
                sc.ws()
                if sc.peek() == close:
                    sc.i += 1
                continue
            key = sc.ident()
            sc.ws()
            if sc.peek() == ",":
                sc.i += 1
            fields: dict = {}
            while sc.i < sc.n:
                sc.ws()
                if sc.peek() == close:
                    sc.i += 1
                    break
                name = sc.ident().lower()
                sc.ws()
                if not name or sc.peek() != "=":
                    # garbage: skip to the next comma or the end of the entry
                    nxt = min([p for p in (sc.s.find(",", sc.i), sc.s.find("\n@", sc.i)) if p >= 0] or [sc.n])
                    sc.i = nxt + 1
                    if sc.s[nxt:nxt + 2] == "\n@":
                        sc.i = nxt + 1
                        break
                    continue
                sc.i += 1
                fields[name] = _value(sc, strings)
                sc.ws()
                if sc.peek() == ",":
                    sc.i += 1
            if key:
                out.append(BibEntry(typ, key, fields))
        except ValueError as e:
            errors.append(f"{typ} near offset {at}: {e}")
            nxt = re.compile(r"\n[ \t]*@").search(sc.s, at + 1)
            sc.i = nxt.end() - 1 if nxt else sc.n
    return out, errors


def _value(sc: _Scanner, strings: dict) -> str:
    parts = []
    while True:
        sc.ws()
        c = sc.peek()
        if c == "{":
            parts.append(sc.braced())
        elif c == '"':
            parts.append(sc.quoted())
        else:
            word = sc.ident()
            if not word:
                raise ValueError("empty value")
            parts.append(word if word.isdigit() else strings.get(word.lower(), word))
        sc.ws()
        if sc.peek() == "#":
            sc.i += 1
            continue
        return "".join(parts)


# ================================================================ BibTeX ⇄ CSL
BIB2CSL = {"article": "article-journal", "book": "book", "booklet": "book", "inbook": "chapter",
           "incollection": "chapter", "inproceedings": "paper-conference", "conference": "paper-conference",
           "proceedings": "book", "phdthesis": "thesis", "mastersthesis": "thesis", "thesis": "thesis",
           "techreport": "report", "report": "report", "manual": "report", "unpublished": "manuscript",
           "online": "webpage", "misc": "document", "collection": "book"}
CSL2BIB = {"article-journal": "article", "article": "misc", "book": "book", "chapter": "incollection",
           "paper-conference": "inproceedings", "thesis": "phdthesis", "report": "techreport",
           "manuscript": "unpublished", "webpage": "online", "document": "misc", "article-magazine": "article",
           "article-newspaper": "article", "entry-encyclopedia": "incollection", "dataset": "misc", "software": "misc",
           "post": "online", "post-weblog": "online", "speech": "misc", "standard": "techreport"}


def split_names(value: str) -> list[dict]:
    names = []
    for raw in re.split(r"\s+and\s+(?![^{]*\})", value.strip()):
        raw = raw.strip()
        if not raw:
            continue
        if raw.lower() == "others":
            names.append({"literal": "others"})
            continue
        if raw.startswith("{") and raw.endswith("}") and raw.count("{") == 1:
            names.append({"literal": latex_to_unicode(raw)})
            continue
        if "," in raw:
            fam, _, given = raw.partition(",")
            names.append({"family": latex_to_unicode(fam), "given": latex_to_unicode(given.strip(" ,"))})
        else:
            words = raw.split()
            # « von » particles stay with the family name
            k = len(words) - 1
            while k > 0 and words[k - 1][:1].islower():
                k -= 1
            names.append({"family": latex_to_unicode(" ".join(words[k:])),
                          "given": latex_to_unicode(" ".join(words[:k]))})
    return names


def _year_month(fields: dict) -> list:
    y = re.search(r"\d{4}", fields.get("year", "") or fields.get("date", ""))
    if not y:
        return []
    parts = [int(y.group(0))]
    m = (fields.get("month") or "").strip().lower()[:3]
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    if m in months:
        parts.append(months.index(m) + 1)
    elif m.isdigit() and 1 <= int(m) <= 12:
        parts.append(int(m))
    else:
        d = re.match(r"\d{4}-(\d{2})", fields.get("date", ""))
        if d:
            parts.append(int(d.group(1)))
    return parts


ARXIV_RE = re.compile(r"(?:arxiv[:/ ]\s*)?(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>{}]+[^\s\"<>{}.,;)\]])")


def norm_doi(doi: str) -> str:
    d = (doi or "").strip()
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", d, flags=re.I)
    return d.lower()


def norm_arxiv(aid: str) -> str:
    m = ARXIV_RE.search((aid or "").strip())
    return m.group(1) if m else ""


def bibtex_to_items(text: str) -> tuple[list[dict], list[str]]:
    """BibTeX (incl. Better BibTeX / Zotero exports) → [CSL item with `_key` and `_files`], errors."""
    entries, errors = parse_bibtex_entries(text)
    return [entry_to_csl(e) for e in entries], errors


def entry_to_csl(e: BibEntry) -> dict:
    f = e.fields
    g = lambda k: latex_to_unicode(f.get(k, ""))  # noqa: E731
    typ = BIB2CSL.get(e.type, "document")
    item: dict = {"type": typ, "_key": e.key}
    if f.get("eprint") and (f.get("archiveprefix", "").lower() == "arxiv" or ARXIV_RE.fullmatch(f["eprint"].strip())):
        item["arxiv"] = norm_arxiv(f["eprint"])
        if e.type in ("misc", "unpublished", "online", "article") and not f.get("journal"):
            item["type"] = "article"
    for bk, ck in (("title", "title"), ("journal", "container-title"), ("journaltitle", "container-title"),
                   ("booktitle", "container-title"), ("volume", "volume"), ("number", "issue"),
                   ("publisher", "publisher"), ("address", "publisher-place"), ("location", "publisher-place"),
                   ("series", "collection-title"), ("edition", "edition"), ("note", "note"),
                   ("abstract", "abstract"), ("language", "language"), ("institution", "publisher"),
                   ("school", "publisher"), ("organization", "publisher"), ("howpublished", "note")):
        if f.get(bk) and ck not in item:
            item[ck] = g(bk)
    if e.type in ("techreport", "report") and f.get("number"):
        item["number"] = g("number")
        item.pop("issue", None)
    if e.type == "mastersthesis":
        item["genre"] = "Master's thesis"
    if f.get("pages"):
        item["page"] = latex_to_unicode(f["pages"]).replace("–", "-").replace("--", "-")
    if f.get("doi"):
        item["DOI"] = norm_doi(f["doi"])
    if f.get("url"):
        item["URL"] = f["url"].strip()
    if f.get("isbn"):
        item["ISBN"] = f["isbn"].strip()
    if f.get("keywords"):
        item["keyword"] = latex_to_unicode(f["keywords"])
    for k in ("zbl", "mrnumber", "zbmath"):
        if f.get(k):
            item[k] = f[k].strip()
    if f.get("mrclass"):
        item["msc"] = re.findall(r"\d\d[A-Z-][0-9x]{2}", f["mrclass"])
    if f.get("author"):
        item["author"] = split_names(f["author"])
    if f.get("editor"):
        item["editor"] = split_names(f["editor"])
    ym = _year_month(f)
    if ym:
        item["issued"] = {"date-parts": [ym]}
    files = _bib_files(f.get("file", ""))
    if files:
        item["_files"] = files
    return item


def _bib_files(value: str) -> list[str]:
    """Zotero `file = {Title:path/to.pdf:application/pdf;…}` or Better BibTeX `{/abs/path.pdf}` → paths."""
    out = []
    for part in re.split(r"(?<!\\);", value or ""):
        part = part.strip()
        if not part:
            continue
        bits = re.split(r"(?<!\\):", part)
        path = bits[1] if len(bits) >= 3 else part
        path = path.replace("\\:", ":").replace("\\;", ";").strip()
        if path:
            out.append(path)
    return out


def item_to_bibtex(item: dict, key: str) -> str:
    """One BibTeX entry (fields escaped: nothing in a record can inject TeX into our documents)."""
    typ = item.get("type", "document")
    btype = CSL2BIB.get(typ, "misc")
    if item.get("genre", "").lower().startswith("master"):
        btype = "mastersthesis"
    fields: list[tuple[str, str]] = []

    def add(name: str, value, protect: bool = False):
        if value in (None, "", []):
            return
        fields.append((name, unicode_to_bibtex(str(value), protect)))
    names = lambda lst: " and ".join(_bib_name(n) for n in lst)  # noqa: E731
    if item.get("author"):
        fields.append(("author", names(item["author"])))
    if item.get("editor"):
        fields.append(("editor", names(item["editor"])))
    add("title", item.get("title"), True)
    ct = item.get("container-title")
    if isinstance(ct, list):
        ct = ct[0] if ct else ""
    if btype == "article":
        add("journal", ct)
    elif btype in ("incollection", "inproceedings"):
        add("booktitle", ct)
    year = _year(item)
    if year:
        fields.append(("year", str(year)))
    add("volume", item.get("volume"))
    add("number", item.get("issue") or item.get("number"))
    if item.get("page"):
        fields.append(("pages", unicode_to_bibtex(str(item["page"]).replace("–", "-")).replace("-", "--", 1)
                       if "--" not in str(item["page"]) else unicode_to_bibtex(str(item["page"]))))
    add("publisher" if btype not in ("phdthesis", "mastersthesis", "techreport") else
        ("school" if "thesis" in btype else "institution"), item.get("publisher"))
    add("address", item.get("publisher-place"))
    add("series", item.get("collection-title"))
    add("edition", item.get("edition"))
    if item.get("DOI"):
        fields.append(("doi", _safe_ident(item["DOI"])))
    if item.get("arxiv"):
        fields += [("eprint", _safe_ident(item["arxiv"])), ("archiveprefix", "arXiv")]
    if item.get("URL"):
        fields.append(("url", _safe_url(item["URL"])))
    if item.get("ISBN"):
        fields.append(("isbn", _safe_ident(str(item["ISBN"]))))
    add("note", item.get("note"))
    for k in ("zbl", "mrnumber"):
        if item.get(k):
            fields.append((k, _safe_ident(str(item[k]))))
    body = ",\n".join(f"  {k:<10} = {{{v}}}" for k, v in fields)
    return f"@{btype}{{{safe_key(key)},\n{body}\n}}\n"


def _safe_ident(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._:/()\-;<>+]", "", s)


def _safe_url(s: str) -> str:
    s = s.strip()
    return re.sub(r"[\s{}\\%#^~$&]", lambda m: "%" + format(ord(m.group(0)), "02X"), s) if re.match(r"https?://", s) else ""


def _bib_name(n: dict) -> str:
    if n.get("literal"):
        return "{" + unicode_to_bibtex(n["literal"]) + "}"
    fam = unicode_to_bibtex(n.get("family", ""))
    given = unicode_to_bibtex(n.get("given", ""))
    if " " in fam.strip():
        fam = "{" + fam + "}"
    return f"{fam}, {given}" if given else fam


KEY_RE = re.compile(r"^[A-Za-z0-9_:.\-+/]{1,80}$")


def safe_key(key: str) -> str:
    k = re.sub(r"[^A-Za-z0-9_:.\-+/]", "", key or "")[:80]
    return k or "ref"


# ================================================================ keys, years, titles
def _year(item: dict) -> int | None:
    for k in ("issued", "published-print", "published-online", "created"):
        dp = (item.get(k) or {}).get("date-parts") if isinstance(item.get(k), dict) else None
        if dp and dp[0] and dp[0][0]:
            try:
                return int(dp[0][0])
            except (TypeError, ValueError):
                continue
    return None


year_of = _year


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


STOP = {"a", "an", "the", "on", "of", "in", "and", "for", "to", "with", "sur", "le", "la", "les", "un", "une", "des",
        "du", "de", "et", "über", "uber", "die", "der", "das", "ein", "eine", "some", "note", "remarks", "remark"}


def make_key(item: dict, existing: set[str]) -> str:
    """`familyYEARword` (ASCII, lower case), unique in `existing` (suffix a, b, c…). Never changes afterwards."""
    authors = item.get("author") or item.get("editor") or []
    fam = ""
    if authors:
        a = authors[0]
        fam = a.get("family") or a.get("literal") or ""
    fam = re.sub(r"[^a-z]", "", ascii_fold(fam.split()[-1] if fam.split() else "").lower()) or "anon"
    year = str(_year(item) or "")
    words = [w for w in re.findall(r"[a-z]+", ascii_fold(str(item.get("title", ""))).lower()) if w not in STOP]
    base = f"{fam}{year}{words[0] if words else ''}"[:60] or "ref"
    key, n = base, 0
    low = {k.lower() for k in existing}
    while key.lower() in low:
        key = base + _suffix(n)
        n += 1
    return key


def _suffix(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


def norm_title(t: str) -> str:
    t = ascii_fold(latex_to_unicode(t or "")).lower()
    t = re.sub(r"\$[^$]*\$|\\\(.*?\\\)", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def first_family(item: dict) -> str:
    a = (item.get("author") or item.get("editor") or [{}])[0]
    return ascii_fold(a.get("family") or a.get("literal") or "").lower().strip()


def same_work(a: dict, b: dict) -> str:
    """'' or the reason two records are the same work: doi | arxiv | title."""
    da, db = norm_doi(a.get("DOI", "")), norm_doi(b.get("DOI", ""))
    if da and db:
        return "doi" if da == db else ""
    xa, xb = norm_arxiv(a.get("arxiv", "")), norm_arxiv(b.get("arxiv", ""))
    if xa and xb and xa == xb:
        return "arxiv"
    ta, tb = norm_title(a.get("title", "")), norm_title(b.get("title", ""))
    if len(ta) < 8 or len(tb) < 8:
        return ""
    ya, yb = _year(a), _year(b)
    if ya and yb and abs(ya - yb) > 1:          # preprint and journal version can differ by a year
        return ""
    fa, fb = first_family(a), first_family(b)
    if fa and fb and fa.split()[-1:] != fb.split()[-1:]:
        return ""
    if difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.93:
        return "title"
    return ""


# ================================================================ RIS
RIS2CSL = {"JOUR": "article-journal", "BOOK": "book", "CHAP": "chapter", "CONF": "paper-conference",
           "CPAPER": "paper-conference", "THES": "thesis", "RPRT": "report", "UNPB": "manuscript", "ELEC": "webpage",
           "GEN": "document", "EJOUR": "article-journal", "PREPRINT": "article", "MANSCPT": "manuscript"}
CSL2RIS = {v: k for k, v in reversed(list(RIS2CSL.items()))}


def ris_to_items(text: str) -> list[dict]:
    items, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  -\s?(.*)$", line.rstrip())
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"type": RIS2CSL.get(val, "document"), "author": []}
            continue
        if cur is None:
            continue
        if tag == "ER":
            if not cur["author"]:
                cur.pop("author")
            items.append(cur)
            cur = None
        elif tag in ("AU", "A1", "A2", "ED"):
            fam, _, given = val.partition(",")
            name = {"family": fam.strip(), "given": given.strip()} if given else {"literal": val}
            cur.setdefault("editor" if tag in ("ED", "A2") else "author", []).append(name)
        elif tag in ("TI", "T1"):
            cur["title"] = val
        elif tag in ("JO", "JF", "T2", "BT", "J2") and "container-title" not in cur:
            cur["container-title"] = val
        elif tag in ("PY", "Y1", "DA"):
            y = re.search(r"\d{4}", val)
            if y and "issued" not in cur:
                cur["issued"] = {"date-parts": [[int(y.group(0))]]}
        elif tag == "VL":
            cur["volume"] = val
        elif tag == "IS":
            cur["issue"] = val
        elif tag == "SP":
            cur["page"] = val + cur.get("page", "")
        elif tag == "EP":
            cur["page"] = cur.get("page", "") + "-" + val
        elif tag == "DO":
            cur["DOI"] = norm_doi(val)
        elif tag == "UR":
            cur.setdefault("URL", val)
        elif tag == "SN":
            cur["ISBN"] = val
        elif tag == "PB":
            cur["publisher"] = val
        elif tag == "CY":
            cur["publisher-place"] = val
        elif tag in ("AB", "N2"):
            cur["abstract"] = val
        elif tag == "KW":
            cur["keyword"] = (cur.get("keyword", "") + ", " + val).strip(", ")
        elif tag in ("L1", "L4"):
            cur.setdefault("_files", []).append(re.sub(r"^file://", "", val))
        elif tag == "N1":
            cur["note"] = val
    return items


def items_to_ris(items: list[tuple[str, dict]]) -> str:
    out = []
    for key, it in items:
        out.append(f"TY  - {CSL2RIS.get(it.get('type', ''), 'GEN')}")
        out.append(f"ID  - {key}")
        for a in it.get("author") or []:
            out.append("AU  - " + (a.get("literal") or f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")))
        for a in it.get("editor") or []:
            out.append("ED  - " + (a.get("literal") or f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")))
        if it.get("title"):
            out.append("TI  - " + _one_line(it["title"]))
        ct = it.get("container-title")
        if ct:
            out.append("T2  - " + _one_line(ct if isinstance(ct, str) else ct[0]))
        if _year(it):
            out.append(f"PY  - {_year(it)}")
        for tag, k in (("VL", "volume"), ("IS", "issue"), ("DO", "DOI"), ("UR", "URL"), ("SN", "ISBN"),
                       ("PB", "publisher"), ("CY", "publisher-place"), ("AB", "abstract"), ("N1", "note")):
            if it.get(k):
                out.append(f"{tag}  - {_one_line(str(it[k]))}")
        if it.get("page"):
            sp, _, ep = str(it["page"]).partition("-")
            out.append(f"SP  - {sp}")
            if ep:
                out.append(f"EP  - {ep.lstrip('-')}")
        out.append("ER  - ")
        out.append("")
    return "\n".join(out)


def _one_line(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


# ================================================================ CSL-JSON in/out
CSL_KEEP = {"type", "title", "author", "editor", "issued", "container-title", "volume", "issue", "page", "DOI", "URL",
            "ISBN", "publisher", "publisher-place", "abstract", "note", "keyword", "collection-title", "edition",
            "number", "genre", "language", "arxiv", "zbl", "mrnumber", "msc", "zbmath", "openalex", "accessed",
            "container-title-short", "event", "event-place", "title-short", "subtitle"}


def clean_csl(raw: dict) -> dict:
    """Keep the known fields with sane types (CSL-JSON from Crossref / DataCite / a user file)."""
    item: dict = {}
    for k, v in raw.items():
        if k not in CSL_KEEP:
            continue
        if k in ("author", "editor"):
            if isinstance(v, list):
                names = []
                for n in v[:500]:
                    if isinstance(n, dict):
                        nn = {x: str(n[x])[:200] for x in ("family", "given", "literal") if n.get(x)}
                        if nn:
                            names.append(nn)
                item[k] = names
        elif k in ("issued", "accessed"):
            if isinstance(v, dict) and isinstance(v.get("date-parts"), list):
                try:
                    dp = [[int(x) for x in v["date-parts"][0][:3] if x is not None]]
                    if dp[0]:
                        item[k] = {"date-parts": dp}
                except (TypeError, ValueError, IndexError):
                    pass
        elif k == "msc":
            if isinstance(v, list):
                item[k] = [str(x)[:12] for x in v[:20]]
        elif k in ("container-title", "title", "subtitle") and isinstance(v, list):
            if v:
                item[k] = re.sub(r"\s+", " ", str(v[0]))[:2000]
        elif isinstance(v, (str, int, float)):
            item[k] = re.sub(r"[ \t]+", " ", str(v))[:20000 if k == "abstract" else 2000].strip()
    if "DOI" in item:
        item["DOI"] = norm_doi(item["DOI"])
    if "title" in item:
        item["title"] = re.sub(r"<[^>]+>", "", item["title"])          # Crossref titles carry <i>, <sub>…
    if "abstract" in item:
        item["abstract"] = re.sub(r"<[^>]+>", " ", item["abstract"]).strip()
    item.setdefault("type", "document")
    return item


def csljson_to_items(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("items", [data])
    out = []
    for raw in data if isinstance(data, list) else []:
        if isinstance(raw, dict):
            it = clean_csl(raw)
            if raw.get("id"):
                it["_key"] = safe_key(str(raw["id"]))
            files = raw.get("_files") or raw.get("file") or []
            if isinstance(files, str):
                files = [files]
            if files:
                it["_files"] = [str(x) for x in files][:20]
            out.append(it)
    return out


def items_to_csljson(items: list[tuple[str, dict]]) -> str:
    return json.dumps([{"id": k, **{x: v for x, v in it.items() if not x.startswith("_")}} for k, it in items],
                      ensure_ascii=False, indent=1)


# ================================================================ Zotero RDF (basic)
NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "dc": "http://purl.org/dc/elements/1.1/",
      "dcterms": "http://purl.org/dc/terms/", "bib": "http://purl.org/net/biblio#", "foaf": "http://xmlns.com/foaf/0.1/",
      "z": "http://www.zotero.org/namespaces/export#", "link": "http://purl.org/rss/1.0/modules/link/",
      "prism": "http://prismstandard.org/namespaces/1.2/basic/"}
RDF_TYPES = {"Article": "article-journal", "Book": "book", "BookSection": "chapter", "Thesis": "thesis",
             "Report": "report", "Manuscript": "manuscript", "Document": "document", "Data": "dataset"}


def rdf_to_items(data: bytes | str) -> list[dict]:
    from .safety import parse_xml
    root = parse_xml(data)
    about = {}
    for el in root:
        a = el.get(f"{{{NS['rdf']}}}about")
        if a:
            about[a] = el
    items = []
    for el in root:
        tag = el.tag.split("}")[-1]
        ztype = el.findtext("z:itemType", default="", namespaces=NS)
        if tag in ("Attachment", "Memo") or ztype in ("attachment", "note"):
            continue
        if tag not in RDF_TYPES and not ztype:
            continue
        title = el.findtext("dc:title", default="", namespaces=NS)
        if not title:
            continue
        it: dict = {"type": RDF_TYPES.get(tag, "document"), "title": title.strip()}
        if ztype == "conferencePaper":
            it["type"] = "paper-conference"
        if ztype == "preprint":
            it["type"] = "article"
        for role, key in (("authors", "author"), ("editors", "editor")):
            people = []
            for p in el.findall(f"bib:{role}/rdf:Seq/rdf:li/foaf:Person", NS):
                fam = p.findtext("foaf:surname", default="", namespaces=NS)
                giv = p.findtext("foaf:givenName", default="", namespaces=NS)
                if fam or giv:
                    people.append({"family": fam.strip(), "given": giv.strip()})
            if people:
                it[key] = people
        date = el.findtext("dc:date", default="", namespaces=NS)
        y = re.search(r"\d{4}", date)
        if y:
            it["issued"] = {"date-parts": [[int(y.group(0))]]}
        for ident in el.findall("dc:identifier", NS):
            txt = "".join(ident.itertext()).strip()
            if txt.upper().startswith("DOI"):
                it["DOI"] = norm_doi(txt[3:].strip(" :"))
            elif txt.upper().startswith("ISBN"):
                it["ISBN"] = txt[4:].strip(" :")
            uri = ident.find("dcterms:URI/rdf:value", NS)
            if uri is not None and uri.text:
                it["URL"] = uri.text.strip()
        for k, path in (("volume", "prism:volume"), ("issue", "prism:number"), ("page", "bib:pages"),
                        ("abstract", "dcterms:abstract")):
            v = el.findtext(path, default="", namespaces=NS)
            if v:
                it[k] = v.strip()
        part = el.find("dcterms:isPartOf", NS)
        if part is not None:
            ref = part.get(f"{{{NS['rdf']}}}resource")
            node = about.get(ref) if ref else (part[0] if len(part) else None)
            if node is not None:
                jt = node.findtext("dc:title", default="", namespaces=NS)
                if jt:
                    it["container-title"] = jt.strip()
                for k, path in (("volume", "prism:volume"), ("issue", "prism:number")):
                    v = node.findtext(path, default="", namespaces=NS)
                    if v and k not in it:
                        it[k] = v.strip()
        files = []
        for ln in el.findall("link:link", NS):
            ref = ln.get(f"{{{NS['rdf']}}}resource")
            att = about.get(ref)
            if att is not None:
                res = att.find("rdf:resource", NS)
                if res is not None and res.get(f"{{{NS['rdf']}}}resource"):
                    files.append(res.get(f"{{{NS['rdf']}}}resource"))
        if files:
            it["_files"] = files
        items.append(it)
    return items


# ================================================================ citations in text
CITE_GROUP = re.compile(r"\[([^\[\]\n]{0,400}?@[^\[\]\n]{0,400})\]")
CITE_ITEM = re.compile(r"^\s*(?:(see|cf\.|voir)\s+)?@([A-Za-z0-9_:.\-+/]+)\s*(?:,\s*(.*?))?\s*$", re.I)


@dataclass
class Cite:
    key: str
    locator: str = ""
    prefix: str = ""


def parse_group(inner: str) -> list[Cite] | None:
    out = []
    for part in inner.split(";"):
        m = CITE_ITEM.match(part)
        if not m:
            return None
        out.append(Cite(m.group(2).rstrip(".:"), (m.group(3) or "").strip()[:80], m.group(1) or ""))
    return out


def find_citations(text: str) -> list[Cite]:
    out = []
    for m in CITE_GROUP.finditer(text or ""):
        g = parse_group(m.group(1))
        if g:
            out.extend(g)
    return out


@dataclass
class CiteCheck:
    text: str
    cited: list[str]
    unknown: list[str]


def check_citations(text: str, known: set[str] | dict) -> CiteCheck:
    """Remove every citation of a key that is not in `known` (an invented reference never reaches a document)."""
    cited, unknown = [], []

    def repl(m: re.Match) -> str:
        g = parse_group(m.group(1))
        if g is None:
            return m.group(0)
        keep = []
        for c in g:
            if c.key in known:
                keep.append(c)
                if c.key not in cited:
                    cited.append(c.key)
            elif c.key not in unknown:
                unknown.append(c.key)
        if not keep:
            return "\x00DROP\x00"
        return "[" + "; ".join((c.prefix + " " if c.prefix else "") + "@" + c.key + (", " + c.locator if c.locator
                                                                                      else "") for c in keep) + "]"
    out = CITE_GROUP.sub(repl, text or "")
    out = re.sub(r"[ \t]*\x00DROP\x00", "", out)
    return CiteCheck(out, cited, unknown)


def cite_to_latex(inner: str, known: set[str] | dict) -> str | None:
    """`@a, Thm 2; @b` → `\\cite[Thm 2]{a}\\cite{b}` (only known keys; None when the group is not a citation)."""
    from .. import texio
    g = parse_group(inner)
    if g is None:
        return None
    parts = []
    for c in g:
        if c.key not in known or not KEY_RE.match(c.key):
            parts.append(r"\textbf{[?]}")
            continue
        pre = texio.escape_plain(c.prefix) + "~" if c.prefix else ""
        loc = "[" + texio.escape_plain(c.locator).replace("]", "") + "]" if c.locator else ""
        parts.append(f"{pre}\\cite{loc}{{{c.key}}}")
    return ", ".join(parts)


def cite_to_text(inner: str, labels: dict) -> str | None:
    """`@a, Thm 2` → `[Wil95, Thm 2]` for Markdown / HTML (labels: key → label)."""
    g = parse_group(inner)
    if g is None:
        return None
    parts = []
    for c in g:
        lab = labels.get(c.key)
        if not lab:
            parts.append("?")
            continue
        parts.append((c.prefix + " " if c.prefix else "") + lab + (", " + c.locator if c.locator else ""))
    return "[" + "; ".join(parts) + "]"


def known_keys_prompt(entries: list[tuple[str, dict]], lang: str = "fr", limit: int = 60) -> str:
    """Block appended to the explanation / informal-proof prompts: the only keys a model may cite."""
    if not entries:
        return ""
    lines = []
    for key, it in entries[:limit]:
        y = _year(it) or ""
        lines.append(f"- {key}: {short_author(it)} {y}, « {str(it.get('title', ''))[:140]} »")
    head = ("\n\nRéférences disponibles dans ce projet (vous POUVEZ en citer une avec la syntaxe [@clé] ou "
            "[@clé, Thm 2.1] — UNIQUEMENT ces clés ; n'inventez jamais de référence, n'en citez aucune si rien ne "
            "convient) :\n" if lang != "en" else
            "\n\nReferences available in this project (you MAY cite one with the syntax [@key] or [@key, Thm 2.1] — "
            "ONLY these keys; never invent a reference, cite none if nothing fits):\n")
    return head + "\n".join(lines)


# ================================================================ formatting (exports)
def short_author(it: dict) -> str:
    names = it.get("author") or it.get("editor") or []
    fams = [n.get("family") or n.get("literal") or "" for n in names if n.get("literal") != "others"]
    if not fams:
        return ""
    if len(fams) == 1:
        return fams[0]
    if len(fams) == 2:
        return f"{fams[0]} & {fams[1]}"
    return f"{fams[0]} et al."


def alpha_label(it: dict) -> str:
    """amsalpha-like label: [Wil95], [HW79], [ABCD+20]."""
    names = [n for n in (it.get("author") or it.get("editor") or []) if n.get("literal") != "others"]
    fams = [ascii_fold(n.get("family") or n.get("literal") or "") for n in names]
    fams = [re.sub(r"[^A-Za-z]", "", f) for f in fams if f]
    y = _year(it)
    yy = f"{y % 100:02d}" if y else ""
    if not fams:
        base = re.sub(r"[^A-Za-z]", "", ascii_fold(str(it.get("title", "")))[:3]) or "Ano"
    elif len(fams) == 1:
        base = fams[0][:3]
    else:
        base = "".join(f[:1] for f in fams[:4]) + ("+" if len(fams) > 4 else "")
    return base + yy


def labels_for(entries: list[tuple[str, dict]]) -> dict:
    out, seen = {}, {}
    for key, it in entries:
        lab = alpha_label(it)
        n = seen.get(lab, 0)
        seen[lab] = n + 1
        out[key] = lab + (_suffix(n - 1) if n else "")
    return out


def _initials(given: str) -> str:
    def one(word: str) -> str:
        return "-".join((w[0] + ".") if w and w[0].isalpha() else w for w in word.split("-"))
    return " ".join(one(p) for p in re.split(r"\s+", given.strip()) if p)


def format_names(names: list[dict]) -> str:
    out = []
    for n in names:
        if n.get("literal"):
            out.append("et al." if n["literal"] == "others" else n["literal"])
        else:
            out.append((_initials(n.get("given", "")) + " " + n.get("family", "")).strip())
    if len(out) <= 2:
        return " and ".join(out)
    return ", ".join(out[:-1]) + ", and " + out[-1]


def format_reference(it: dict) -> list[tuple[str, str]]:
    """Reference as styled pieces [(style, text)] with style in plain | italic | bold — rendered by each format."""
    p: list[tuple[str, str]] = []
    who = format_names(it.get("author") or [])
    if not who and it.get("editor"):
        who = format_names(it["editor"]) + " (ed.)"
    if who:
        p.append(("plain", who + ", "))
    title = str(it.get("title") or "Untitled").strip().rstrip(".")
    typ = it.get("type", "")
    p.append(("italic", title))
    ct = it.get("container-title")
    ct = ct[0] if isinstance(ct, list) and ct else ct
    y = _year(it)
    if typ in ("article-journal", "article-magazine") and ct:
        p.append(("plain", f", {ct}"))
        if it.get("volume"):
            p += [("plain", " "), ("bold", str(it["volume"]))]
        if y:
            p.append(("plain", f" ({y})"))
        if it.get("issue"):
            p.append(("plain", f", no. {it['issue']}"))
        if it.get("page"):
            p.append(("plain", ", " + str(it["page"]).replace("--", "–").replace("-", "–")))
    elif typ in ("chapter", "paper-conference") and ct:
        p.append(("plain", f", {ct}"))
        if it.get("publisher"):
            p.append(("plain", f", {it['publisher']}"))
        if y:
            p.append(("plain", f", {y}"))
        if it.get("page"):
            p.append(("plain", ", pp. " + str(it["page"]).replace("--", "–").replace("-", "–")))
    else:
        if it.get("collection-title"):
            p.append(("plain", f", {it['collection-title']}"))
            if it.get("volume"):
                p.append(("plain", f", vol. {it['volume']}"))
        if typ == "thesis":
            p.append(("plain", ", " + (it.get("genre") or "Ph.D. thesis")))
        if it.get("publisher"):
            p.append(("plain", f", {it['publisher']}"))
        if it.get("publisher-place"):
            p.append(("plain", f", {it['publisher-place']}"))
        if y:
            p.append(("plain", f", {y}"))
    if it.get("arxiv"):
        p.append(("plain", f", arXiv:{it['arxiv']}"))
    if it.get("DOI"):
        p.append(("plain", f", doi:{it['DOI']}"))
    elif it.get("URL") and not it.get("arxiv"):
        p.append(("plain", f", {it['URL']}"))
    p.append(("plain", "."))
    return p


def reference_latex(it: dict, esc) -> str:
    out = []
    for style, txt in format_reference(it):
        e = esc(txt)
        out.append(r"\emph{" + e + "}" if style == "italic" else r"\textbf{" + e + "}" if style == "bold" else e)
    return "".join(out)


def reference_text(it: dict, md: bool = True) -> str:
    out = []
    for style, txt in format_reference(it):
        if md and style == "italic":
            out.append(f"*{txt}*")
        elif md and style == "bold":
            out.append(f"**{txt}**")
        else:
            out.append(txt)
    return "".join(out)


def reference_html(it: dict) -> str:
    import html
    out = []
    for style, txt in format_reference(it):
        t = html.escape(txt)
        out.append(f"<em>{t}</em>" if style == "italic" else f"<strong>{t}</strong>" if style == "bold" else t)
    return "".join(out)


# ================================================================ Mathlib shelf
_MATHLIB_CACHE: dict[str, tuple[float, list[dict]]] = {}


def mathlib_bib_paths(workspaces) -> list[tuple[str, Path]]:
    out = []
    for w in workspaces or []:
        root = Path(getattr(w, "path", ""))
        for cand in (root / "docs" / "references.bib",
                     root / ".lake" / "packages" / "mathlib" / "docs" / "references.bib"):
            if cand.is_file():
                out.append((getattr(w, "key", root.name), cand))
                break
    return out


def mathlib_shelf(workspaces) -> list[dict]:
    """Read-only records of Mathlib's `docs/references.bib` (first workspace that has it; cached by mtime)."""
    for key, path in mathlib_bib_paths(workspaces):
        try:
            mt = path.stat().st_mtime
        except OSError:
            continue
        hit = _MATHLIB_CACHE.get(str(path))
        if hit and hit[0] == mt:
            return hit[1]
        items, _err = bibtex_to_items(path.read_text(encoding="utf-8", errors="replace"))
        for it in items:
            it["_workspace"] = key
        _MATHLIB_CACHE[str(path)] = (mt, items)
        return items
    return []


# ================================================================ hooks used by the pipeline and the exports
def _library(ctx):
    from .sources import library
    return library(ctx)


def dossier_texts(d) -> list[str]:
    return [d.problem or "", d.understood_display or "", d.notes or "", d.informal_proof or "", d.explanation or "",
            str((d.source or {}).get("original_text", "")) if isinstance(d.source, dict) else ""]


def citation_support(ctx, d, lang: str = "fr") -> dict | None:
    """For the explanation / informal-proof prompts: {prompt, keys}. None when the project has no reference."""
    try:
        lib = _library(ctx)
        entries = lib.project_entries(d.project_id or None)
        known = lib.all_entries(d.project_id or None)
    except Exception:  # noqa: BLE001 (no research layer: the pipeline runs as before)
        return None
    for r in d.refs or []:                       # keys attached to the dossier first (Mathlib ones included)
        k = r.get("key") if isinstance(r, dict) else None
        if k and k in known and all(k != e[0] for e in entries):
            entries.insert(0, (k, known[k]))
    if not entries:
        return None
    return {"prompt": known_keys_prompt(entries, lang), "keys": set(known)}


def dossier_bibliography(ctx, d) -> list[tuple[str, dict]]:
    """Entries a dossier's export prints: its `refs` plus every valid `[@key]` of its texts (first-cited order)."""
    try:
        known = _library(ctx).all_entries(d.project_id or None)
    except Exception:  # noqa: BLE001
        return []
    order: list[str] = []
    for r in d.refs or []:
        k = r.get("key") if isinstance(r, dict) else None
        if k and k in known and k not in order:
            order.append(k)
    for t in dossier_texts(d):
        for c in find_citations(t):
            if c.key in known and c.key not in order:
                order.append(c.key)
    return [(k, known[k]) for k in order]
