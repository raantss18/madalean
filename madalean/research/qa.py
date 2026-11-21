"""Grounded answers over the sources (NotebookLM-style), summaries and comparisons.

1. Retrieve chunks (FTS5 + optional local embeddings) in the chosen scope.
2. Nothing relevant → the answer SAYS SO; the model is not asked to answer from memory (unless the user enabled
   « also use general knowledge », and then that part is generated separately and marked `general`).
3. The model sees the passages as labelled DATA (`<<<SOURCE_DATA …>>>`, see safety.wrap_untrusted) and must end
   every sentence with citations `[P2: "exact quote"]`.
4. Post-check in code: each cited passage must exist and each quote must really occur in that chunk (normalised,
   fuzzy ≥ 0.85 around the longest common block). Unsupported citations are dropped; a sentence left without any
   valid citation is flagged `supported: false`. Every kept citation carries its anchor (source key, chunk id,
   page, bbox, locator, character span of the quote in the chunk) so the UI opens the page at the passage.

The model is only ever called through `complete` (no tools): retrieved text cannot make anything run."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .safety import UNTRUSTED_RULE, wrap_untrusted

MIN_SCORE = 0.0
CITE_RE = re.compile(r"\[(P\d{1,3})(?::\s*[\"“«]\s*(.*?)\s*[\"”»])?((?:\s*;\s*P\d{1,3}(?::\s*[\"“«].*?[\"”»])?)*)\]",
                     re.S)
ONE_CITE = re.compile(r"(P\d{1,3})(?::\s*[\"“«]\s*(.*?)\s*[\"”»])?", re.S)

ANSWER_PROMPT = {
    "en": ("Answer the question using ONLY the passages below (they come from the user's sources). {rule}\n\n"
           "Rules:\n- Write in English, precise and concise; formulas in LaTeX between $...$.\n"
           "- End EVERY sentence with its citations in the form [P2: \"exact words copied from passage P2\"] — the "
           "quote must be copied verbatim from that passage (5 to 30 words). Several: [P2: \"…\"; P5: \"…\"].\n"
           "- Never cite a passage that does not say it. Never use outside knowledge.\n"
           "- If the passages do not contain the answer, answer exactly: NOT IN SOURCES.\n\n"
           "Question: {q}\n\n{passages}"),
    "fr": ("Réponds à la question en utilisant UNIQUEMENT les passages ci-dessous (ils viennent des sources de "
           "l'utilisateur). {rule}\n\nRègles :\n- Écris en français, précis et concis ; formules en LaTeX entre $...$.\n"
           "- Termine CHAQUE phrase par ses citations sous la forme [P2: \"mots exacts copiés du passage P2\"] — la "
           "citation est copiée mot pour mot de ce passage (5 à 30 mots), dans la langue du passage. Plusieurs : "
           "[P2: \"…\"; P5: \"…\"].\n- Ne cite jamais un passage qui ne le dit pas. N'utilise aucune connaissance "
           "extérieure.\n- Si les passages ne contiennent pas la réponse, réponds exactement : NOT IN SOURCES.\n\n"
           "Question : {q}\n\n{passages}"),
}
GENERAL_PROMPT = {
    "en": "Answer briefly from general mathematical knowledge (no citations, no references): {q}",
    "fr": "Réponds brièvement à partir de connaissances mathématiques générales (sans citation ni référence) : {q}",
}
TASKS = {
    "summary": {"en": "Summarise this source: what it proves (main results, precisely), its main definitions, and "
                      "what it depends on (results or works it uses).",
                "fr": "Résume cette source : ce qu'elle démontre (résultats principaux, précisément), ses définitions "
                      "principales, et ce dont elle dépend (résultats ou travaux utilisés)."},
    "compare": {"en": "Compare these sources: what each proves, how their results and methods relate, where they "
                      "agree or differ.",
                "fr": "Compare ces sources : ce que chacune démontre, comment leurs résultats et méthodes se "
                      "rattachent, où elles s'accordent ou diffèrent."},
}


# ================================================================ quote verification
def _norm_map(text: str) -> tuple[str, list[int]]:
    """Normalised text (lower case, no TeX punctuation, single spaces) + index map back to the original."""
    out, idx = [], []
    prev_space = True
    for i, ch in enumerate(text):
        c = ch.lower()
        if c in "$\\{}~*_`" or c.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
                prev_space = True
            continue
        if c in "’‘":
            c = "'"
        if c in "“”«»":
            c = '"'
        out.append(c)
        idx.append(i)
        prev_space = False
    return "".join(out), idx


def find_quote(quote: str, text: str, threshold: float = 0.85) -> tuple[int, int, float] | None:
    """(start, end, ratio) of `quote` inside `text` (original indices), or None."""
    q, _ = _norm_map(quote)
    q = q.strip().strip('"').strip()
    t, idx = _norm_map(text)
    if len(q) < 8 or not t:
        return None
    k = t.find(q)
    if k >= 0:
        return idx[k], idx[min(k + len(q), len(idx)) - 1] + 1, 1.0
    sm = difflib.SequenceMatcher(None, t, q, autojunk=False)
    m = sm.find_longest_match(0, len(t), 0, len(q))
    if m.size < min(12, len(q) // 3):
        return None
    best = None
    start0 = m.a - m.b
    for shift in range(-6, 7):
        s = max(0, start0 + shift)
        for ln in (len(q) - 4, len(q), len(q) + 4):
            e = min(len(t), s + max(ln, 1))
            r = difflib.SequenceMatcher(None, t[s:e], q, autojunk=False).ratio()
            if best is None or r > best[2]:
                best = (s, e, r)
    if best and best[2] >= threshold:
        s, e, r = best
        return idx[s], idx[max(s, e - 1)] + 1, round(r, 3)
    return None


# ================================================================ answer parsing
@dataclass
class Passage:
    pid: str
    chunk: dict


def split_sentences(text: str) -> list[str]:
    """Sentences, keeping their trailing citation groups attached (a citation follows the period)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    # protect math so that "$a.b$" never splits
    parts = re.split(r"(\$\$.+?\$\$|\$[^$]+\$)", text)
    shield = []
    for i, p in enumerate(parts):
        shield.append(p.replace(".", "\x00") if i % 2 else p)
    t = "".join(shield)
    out = []
    # split after a citation group or after . ! ? when followed by a capital / quote / list marker
    for s in re.split(r"(?<=\])\s+(?=[A-ZÀ-Ý0-9$(\"«*-])|(?<=[.!?])\s+(?=[A-ZÀ-Ý$(\"«*-])", t):
        s = s.replace("\x00", ".").strip()
        if s:
            out.append(s)
    # a citation group alone (model put it after the period with a space) joins the previous sentence
    merged: list[str] = []
    for s in out:
        if merged and re.fullmatch(r"(\[[^\]]*\]\s*)+[.]?", s):
            merged[-1] += " " + s
        else:
            merged.append(s)
    return merged


def check_answer(text: str, passages: dict[str, Passage]) -> tuple[list[dict], int]:
    """Sentences with verified citations. Returns (sentences, number of dropped citations)."""
    sentences, dropped = [], 0
    for sent in split_sentences(text):
        cites, seen = [], set()
        for grp in CITE_RE.finditer(sent):
            for m in ONE_CITE.finditer(grp.group(0)[1:-1]):
                pid, quote = m.group(1), (m.group(2) or "").strip()
                p = passages.get(pid)
                if p is None or not quote:
                    dropped += 1
                    continue
                hit = find_quote(quote, p.chunk["text"])
                if hit is None:
                    dropped += 1
                    continue
                key = (pid, hit[0])
                if key in seen:
                    continue
                seen.add(key)
                c = p.chunk
                cites.append({"passage": pid, "chunk_id": c["id"], "source_id": c["source_id"],
                              "source_key": c.get("source_key", ""), "shelf": c.get("shelf", ""),
                              "page": c.get("page"), "bbox": c.get("bbox"), "locator": c.get("locator", ""),
                              "quote": c["text"][hit[0]:hit[1]], "span": [hit[0], hit[1]], "match": hit[2]})
        clean = CITE_RE.sub("", sent).strip()
        from .biblio import CITE_GROUP
        clean = CITE_GROUP.sub("", clean).strip()        # answers cite passages, never bibliography keys
        clean = re.sub(r"\s+([.,;:!?])", r"\1", clean)
        if not clean or re.fullmatch(r"[.\s]*", clean):
            continue
        sentences.append({"text": clean, "citations": cites, "supported": bool(cites), "general": False})
    return sentences, dropped


def passages_block(hits: list[dict]) -> tuple[str, dict[str, Passage]]:
    table: dict[str, Passage] = {}
    blocks = []
    for i, h in enumerate(hits, 1):
        pid = f"P{i}"
        table[pid] = Passage(pid, h)
        where = ", ".join(x for x in (h.get("source_key", ""), h.get("locator", ""),
                                      f"p. {h['page']}" if h.get("page") and "p. " not in (h.get("locator") or "")
                                      else "") if x)
        blocks.append(wrap_untrusted(f"[{pid}] ({where})\n{h['text'][:2400]}", pid))
    return "\n\n".join(blocks), table


def answer_messages(question: str, hits: list[dict], lang: str = "fr") -> tuple[list[dict], dict[str, Passage]]:
    block, table = passages_block(hits)
    p = ANSWER_PROMPT["en" if lang == "en" else "fr"]
    return [{"role": "user", "content": p.format(rule=UNTRUSTED_RULE, q=question[:2000], passages=block)}], table


NO_PASSAGE = {"fr": "Aucun passage de vos sources ne traite de cette question : je ne réponds pas de mémoire.",
              "en": "No passage of your sources addresses this question: I do not answer from memory."}
NOT_IN = {"fr": "Les passages trouvés ne contiennent pas la réponse.",
          "en": "The passages found do not contain the answer."}


async def grounded(complete, question: str, hits: list[dict], *, lang: str = "fr", general: bool = False,
                   task: str = "") -> dict:
    """`complete(role, messages, on_chunk_kind)` → Completion. Returns the checked answer."""
    out: dict = {"question": question, "passages": [_public_hit(h, i) for i, h in enumerate(hits, 1)],
                 "sentences": [], "dropped": 0, "model": "", "status": "ok", "general": []}
    if not hits:
        out["status"] = "no_passages"
        out["sentences"] = [{"text": NO_PASSAGE["en" if lang == "en" else "fr"], "citations": [], "supported": True,
                             "general": False, "notice": True}]
    else:
        msgs, table = answer_messages(task or question, hits, lang)
        c = await complete("explain", msgs, "answer")
        out["model"] = c.model.key
        text = re.sub(r"<think>.*?(</think>|$)", "", c.text or "", flags=re.S).strip()
        if "NOT IN SOURCES" in text.upper() and len(text) < 60:
            out["status"] = "not_in_sources"
            out["sentences"] = [{"text": NOT_IN["en" if lang == "en" else "fr"], "citations": [], "supported": True,
                                 "general": False, "notice": True}]
        else:
            out["sentences"], out["dropped"] = check_answer(text, table)
            if not any(s["supported"] for s in out["sentences"]):
                out["status"] = "unsupported"
    if general:
        g = await complete("explain", [{"role": "user", "content":
                                        GENERAL_PROMPT["en" if lang == "en" else "fr"].format(q=question[:2000])}],
                           "general")
        gtext = re.sub(r"<think>.*?(</think>|$)", "", g.text or "", flags=re.S).strip()
        from .biblio import CITE_GROUP
        gtext = CITE_GROUP.sub("", gtext)               # no reference can come from memory
        out["general"] = [{"text": s, "citations": [], "supported": False, "general": True}
                          for s in split_sentences(gtext)]
        out["general_model"] = g.model.key
    return out


def _public_hit(h: dict, i: int) -> dict:
    return {"passage": f"P{i}", "chunk_id": h["id"], "source_id": h["source_id"], "source_key": h.get("source_key", ""),
            "shelf": h.get("shelf", ""), "page": h.get("page"), "bbox": h.get("bbox"), "locator": h.get("locator", ""),
            "kind": h.get("kind", ""), "text": h["text"][:2400], "score": h.get("score")}


def source_overview_hits(chunks: list[dict], budget: int = 12000) -> list[dict]:
    """Chunks for a summary: abstract, statements (theorem-like), then the first paragraphs, within a budget."""
    order = {"abstract": 0, "theorem": 1, "proposition": 1, "corollary": 1, "lemma": 2, "definition": 2,
             "conjecture": 2, "claim": 3, "paragraph": 4, "proof": 6, "remark": 5}
    ranked = sorted(chunks, key=lambda c: (order.get(c.get("kind", ""), 4), c.get("ord", 0)))
    out, used = [], 0
    for c in ranked:
        if used + len(c["text"]) > budget and out:
            continue
        out.append(c)
        used += len(c["text"])
        if len(out) >= 24:
            break
    return sorted(out, key=lambda c: c.get("ord", 0))
