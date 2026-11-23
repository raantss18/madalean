"""Verbatim quotations: candidate passages of a retrieved text, and the string match that every shown quote passes.

Rules (docs/LITERATURE.md §2):
- the text a quote comes from is the retrieved text after a fixed, deterministic cleaning (`clean`): tags removed,
  entities decoded, Unicode NFKC, runs of white space → one space; nothing else (no case change, no rewording);
- `verify(quote, text)` finds the quote in that text after the same white-space normalisation only; anything else
  (a paraphrase, a « corrected » formula, an invented sentence) is rejected;
- a model may *pick* among numbered candidate passages (`P1`, `P2`…) that this module cut from the text; it never
  writes the passage itself; an unknown id is dropped and counted.
Retrieved text is data: it is stored as inert plain text, and a text that addresses a model (`suspect`) is never
sent to one (`looks_like_injection`, shared with the news watch)."""
from __future__ import annotations

import html
import re
import unicodedata

from ..news.summarize import looks_like_injection

MAX_TEXT = 6000
MAX_QUOTE = 700
MIN_QUOTE = 25

_TAG = re.compile(r"</?[A-Za-z][\w:.-]{0,40}(?:\s[^<>]{0,300})?/?>")
_CTRL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​-‏‪-‮⁦-⁩]")
# a sentence end: . ! ? followed by space + capital / $ / digit — but not after usual abbreviations or inside $…$
_ABBR = r"(?<!\be\.g)(?<!\bi\.e)(?<!\bet al)(?<!\bcf)(?<!\bresp)(?<!\bThm)(?<!\bLem)(?<!\bProp)(?<!\bSec)(?<!\bEq)" \
        r"(?<!\bvs)(?<!\bp)(?<!\bpp)(?<!\bno)(?<!\bVol)(?<!\bFig)"
RESULT_MARKERS = re.compile(
    r"\b(we (prove|show|establish|obtain|give|determine|characteri[sz]e|deduce|derive|confirm|disprove)|"
    r"it is (proved|shown)|is proved|is shown|main (result|theorem)|theorem|lemma|proposition|corollary|"
    r"conjecture|if and only if|iff|for (all|every|each|any)|there (exist|is|are)|every|at least|at most|"
    r"infinitely many|is (irrational|transcendental|prime|bounded|finite|equal)|holds|nous (montrons|prouvons|"
    r"démontrons|établissons)|théorème|pour tout|il existe)\b", re.I)


def clean(text: str, limit: int = MAX_TEXT) -> str:
    """The deterministic cleaning of a retrieved text (JATS / HTML tags, entities, controls, spaces)."""
    s = _TAG.sub(" ", str(text or ""))
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    s = _CTRL.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.lower().startswith("abstract "):
        s = s[9:].lstrip(" :.")
    return s[:limit]


def _norm(s: str) -> tuple[str, list[int]]:
    """White space collapsed, with the map back to positions in `s`."""
    out, pos = [], []
    prev_space = True
    for i, ch in enumerate(s):
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                pos.append(i)
            prev_space = True
        else:
            out.append(ch)
            pos.append(i)
            prev_space = False
    if out and out[-1] == " ":
        out.pop()
        pos.pop()
    return "".join(out), pos


def verify(quote: str, text: str) -> tuple[int, int] | None:
    """(start, end) of `quote` in `text` — verbatim up to white space — or None. Empty / too short quotes never
    match (a three-word « quote » proves nothing)."""
    q = unicodedata.normalize("NFKC", str(quote or ""))
    q, _ = _norm(q.strip())
    if len(q) < MIN_QUOTE or len(q) > MAX_QUOTE * 2:
        return None
    t, pos = _norm(str(text or ""))
    i = t.find(q)
    if i < 0:
        return None
    return pos[i], pos[i + len(q) - 1] + 1


def sentences(text: str) -> list[tuple[int, int]]:
    """Sentence spans of a cleaned text; `$…$` math is never cut."""
    spans: list[tuple[int, int]] = []
    start, i, n, in_math = 0, 0, len(text), False
    while i < n:
        ch = text[i]
        if ch == "$":
            in_math = not in_math
        elif ch in ".!?" and not in_math and i + 2 <= n:
            nxt = text[i + 1:i + 3]
            if (i + 1 == n or (nxt[:1] == " " and (nxt[1:2].isupper() or nxt[1:2] in "$(" or nxt[1:2].isdigit()))) \
                    and re.search(_ABBR + r"$", text[max(0, i - 6):i]):
                spans.append((start, i + 1))
                start = i + 2
                i += 1
        i += 1
    if start < n:
        spans.append((start, n))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def candidates(text: str, keywords: list[str], limit: int = 8) -> list[dict]:
    """Passages that state a result: one or two sentences with a result marker, scored by the query keywords they
    contain. Returns [{start, end, text, sentence, score, matched}] best first; every `text` is `text[start:end]`."""
    spans = sentences(text)
    kws = [k.lower() for k in keywords if k]
    out = []
    for idx, (a, b) in enumerate(spans):
        s = text[a:b]
        if len(s) < MIN_QUOTE:
            continue
        if len(s) > MAX_QUOTE:              # one very long sentence: not a quotable statement
            continue
        if not s.rstrip().endswith((".", "!", "?", ".)", ".$")):
            continue                        # a text cut in the middle of a sentence
        if not _balanced(s):                # a sentence cut inside a citation / a formula: not quotable
            continue
        marker = bool(RESULT_MARKERS.search(s))
        low = s.lower()
        matched = [k for k in kws if _has(low, k)]
        score = len(matched) + (1.5 if marker else 0.0) - (0.4 if idx > 6 else 0.0)
        if not matched or (not marker and len(matched) < 2):
            continue
        # a sentence that only announces (« In this paper we study … ») is weaker than one that states
        if re.search(r"\b(we study|we consider|this paper|in this note|we discuss|we survey)\b", low) and \
                not re.search(r"\b(prove|show|establish)\b", low):
            score -= 1.0
        out.append({"start": a, "end": b, "text": s, "sentence": idx + 1, "score": round(score, 3),
                    "matched": matched})
    out.sort(key=lambda c: (-c["score"], c["start"]))
    return out[:limit]


def _has(low: str, keyword: str) -> bool:
    """Every word of the keyword (singular or plural; « Bertrand's » for « Bertrand ») is in the text."""
    words = [w for w in re.findall(r"\w+", keyword.lower()) if len(w) > 2]
    stems = [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words]
    return bool(stems) and all(re.search(r"\b" + re.escape(w), low) for w in stems)


def _balanced(s: str) -> bool:
    if s.count("(") + s.count("[") != s.count(")") + s.count("]") or s.count("{") != s.count("}"):
        return False            # ( and [ counted together: half-open intervals « (x, 2x] » are fine
    return s.count("$") % 2 == 0 and s.count("\\(") == s.count("\\)")


def location(kind: str, sentence: int = 0, locator: str = "", page: int | None = None, lang: str = "fr") -> str:
    """Human locator of a quote (FR / EN)."""
    fr = lang != "en"
    if kind == "fulltext":
        parts = [locator] if locator else []
        if page:
            parts.append(f"p. {page}")
        return ", ".join(parts) or ("texte intégral" if fr else "full text")
    name = {"abstract": ("résumé", "abstract"), "review": ("recension zbMATH", "zbMATH review"),
            "summary": ("résumé (zbMATH)", "summary (zbMATH)"),
            "transcription": ("transcription de l’image (pièce jointe)", "image transcription (attachment)")}.get(kind, (kind, kind))[0 if fr else 1]
    if sentence:
        return f"{name}, {'phrase' if fr else 'sentence'} {sentence}"
    return name


def suspect(*texts: str) -> bool:
    return any(looks_like_injection(t or "") for t in texts)


def picked_ids(answer: str, table: dict) -> tuple[list[str], int]:
    """Model answer (JSON list of `P…` ids) → known ids in order, and the number of unknown ones."""
    from ..research.litsearch import parse_json_block
    data = parse_json_block(answer or "")
    ids, unknown = [], 0
    for x in data if isinstance(data, list) else []:
        pid = str(x.get("id", "") if isinstance(x, dict) else x).strip()
        if pid in table and pid not in ids:
            ids.append(pid)
        else:
            unknown += 1
    return ids, unknown
