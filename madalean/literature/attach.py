"""Attachments: an image, a PDF, a LaTeX / BibTeX file or a URL attached to a dossier, read ONCE into a digest.

- **Storage**: the attachment becomes a Source of the PROJECT (its shelf; the global shelf for a dossier outside a
  project) through the existing Sources import (`research/sources.py`: size / type limits from the magic bytes,
  hostile archives refused, SSRF-safe fetch of URLs, Local mode refused for URLs). The dossier keeps a link
  (`extra.attachments`, numbered « pièce jointe 1, 2 … »).
- **Read once**: the digest is content-addressed by SHA-256 (of the file, or of the normalised URL) in
  `<shelf>/digests/<sha>.json` and versioned by `EXTRACTOR_VERSION`; the same file attached again — in this dossier
  or any other of the project — is linked to the existing digest, never read again (no extraction, no model, no
  vision call). « Relire » (`read(..., force=True)`) is the only way to read it again.
- **Digest** = the bibliographic record (verified when an identifier resolved through the scholarly APIs, else
  « référence non vérifiée »), the statements found (theorem-like blocks of the extracted text, or sentences of an
  image transcription), each a `LiteratureItem` with `origin="attachment"` and a verbatim quote string-matched
  against the extracted text (same rule as the literature search), and an optional Lean statement (formalizer,
  Lean-checked; free online models only). An image is read by a vision model (a free online one; a local one in
  Local mode); its transcription is marked as such and the original stays in the Sources. Without a vision model
  the image is kept and marked « non lue ».
Later requests read the digest (bounded), never the document."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
from pathlib import Path

from .. import config
from ..logs import get
from . import formal, quotes as Q, retrieve as R
from .types import Budget, LiteratureItem, Quote, SourceText, item_id

log = get("literature.attach")

EXTRACTOR_VERSION = "attach-1"
MAX_ATTACHMENTS = 20                  # per dossier
MAX_STATEMENTS = 30                   # per digest
MAX_TRANSCRIPTION = 12000
THEOREM_KINDS = ("theorem", "lemma", "proposition", "corollary", "definition", "conjecture", "claim")
VISION_PROMPT = (
    "Transcribe the mathematical content of this image exactly: plain text, formulas in LaTeX between $…$. Keep "
    "numbering and labels (Theorem 2.1, Lemma 3…). Do not solve, comment or add anything. If the image contains no "
    "mathematics, answer NONE.")
_MENTION = re.compile(r"\b(?:pi[eè]ce\s+jointe|pj|attachment|fichier)\s*(?:n[°o]\s*)?(\d{1,2})\b"
                      r"(?:[^.\n]{0,40}?\b(th[ée]or[eè]me|theorem|lemme|lemma|proposition|corollaire|corollary|"
                      r"d[ée]finition|definition|conjecture)\s*(\d+(?:\.\d+)*))?", re.I)
LABEL_EN = {"théorème": "theorem", "theoreme": "theorem", "lemme": "lemma", "corollaire": "corollary",
            "définition": "definition", "definition": "definition"}


class AttachError(Exception):
    def __init__(self, kind: str, status: int = 400):
        super().__init__(kind)
        self.kind, self.status = kind, status


def sha_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def url_sha(url: str) -> str:
    return hashlib.sha256(("url:" + url.strip().rstrip("/").lower()).encode()).hexdigest()


def _lib(ctx):
    from ..research.sources import library
    return library(ctx)


def shelf_of(ctx, d) -> str:
    from ..research.sources import GLOBAL
    return d.project_id if d.project_id and ctx.projects.get(d.project_id) is not None else GLOBAL


def _digest_path(ctx, shelf: str, sha: str) -> Path:
    return _lib(ctx).shelf(shelf).root / "digests" / f"{sha}.json"


def load_digest(ctx, shelf: str, sha: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f]{64}", sha or ""):
        return None
    try:
        data = json.loads(_digest_path(ctx, shelf, sha).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_digest(ctx, shelf: str, digest: dict) -> None:
    p = _digest_path(ctx, shelf, digest["sha"])
    p.parent.mkdir(parents=True, exist_ok=True)
    config.atomic_write_text(p, json.dumps(digest, ensure_ascii=False))


def items_of(digest: dict | None) -> list[LiteratureItem]:
    """The digest's statements as typed items (origin « attachment »), for the pipeline and the lemma graph."""
    from .types import LiteratureResult
    if not digest:
        return []
    try:
        return LiteratureResult.from_dict({"items": digest.get("items") or []}).items
    except Exception:  # noqa: BLE001
        return []


def link(d, entry: dict) -> dict:
    atts = d.extra.setdefault("attachments", [])
    for a in atts:
        if a.get("sha") == entry["sha"]:
            return a
    if len(atts) >= MAX_ATTACHMENTS:
        raise AttachError("too_many", 409)
    entry = {**entry, "n": len(atts) + 1, "t": time.time()}
    atts.append(entry)
    return entry


# ---------------------------------------------------------------- attach
async def attach_file(ctx, d, name: str, data: bytes, *, mode: str, cell: str = "") -> tuple[dict, bool]:
    """Store + link + read once. Returns (attachment entry, read_now). A file already digested in the project is
    linked without being read again."""
    from ..research.safety import MAX_UPLOAD, image_type, sniff
    from ..research.sources import SourceError
    if not data:
        raise AttachError("empty")
    if len(data) > MAX_UPLOAD:
        raise AttachError("too_large", 413)
    kind = "image" if image_type(data) else sniff(data, name)
    if kind not in ("image", "pdf", "tex", "bib", "gzip", "tar", "zip"):
        raise AttachError("bad_type", 415)
    shelf, sha = shelf_of(ctx, d), sha_of(data)
    dig = load_digest(ctx, shelf, sha)
    if dig is not None and dig.get("version") == EXTRACTOR_VERSION and dig.get("source_id"):
        entry = link(d, {"sha": sha, "shelf": shelf, "source_id": dig["source_id"], "name": dig.get("name", name),
                         "kind": dig.get("kind", kind), **({"cell": cell} if cell else {})})
        return entry, False
    lib = _lib(ctx)
    try:
        if kind == "image":
            src, _dup = await lib.add_record(shelf, {"type": "graphic", "title": _title(name)}, via="attachment",
                                             verified=False, files=[(name, data)], extract=False)
        else:
            res = await lib.add_upload(shelf, name, data, mode=mode)
            src = res.get("source") or _first_added(lib, shelf, res)
    except SourceError as e:
        raise AttachError(e.kind, getattr(e, "status", 400)) from e
    if src is None:
        raise AttachError("nothing_imported", 422)
    entry = link(d, {"sha": sha, "shelf": shelf, "source_id": src["id"], "name": name[:200],
                     "kind": "bib" if kind == "bib" else "image" if kind == "image" else
                     ("pdf" if kind == "pdf" else "tex"), **({"cell": cell} if cell else {})})
    save_digest(ctx, shelf, {"sha": sha, "version": EXTRACTOR_VERSION, "state": "reading", "source_id": src["id"],
                             "name": name[:200], "kind": entry["kind"], "t": time.time()})
    return entry, True


async def attach_url(ctx, d, url: str, *, mode: str, cell: str = "") -> tuple[dict, bool]:
    """A URL (DOI page, arXiv, publisher page): the Sources' identifier import (SSRF-safe fetcher)."""
    from ..research.sources import SourceError
    if mode == "local":
        raise AttachError("local_mode", 409)
    url = url.strip()[:2000]
    shelf, sha = shelf_of(ctx, d), url_sha(url)
    dig = load_digest(ctx, shelf, sha)
    if dig is not None and dig.get("version") == EXTRACTOR_VERSION and dig.get("source_id"):
        return link(d, {"sha": sha, "shelf": shelf, "source_id": dig["source_id"], "name": url, "kind": "url",
                        **({"cell": cell} if cell else {})}), False
    try:
        src, _dup = await _lib(ctx).add_identifier(shelf, url, mode=mode)
    except SourceError as e:
        raise AttachError(e.kind, getattr(e, "status", 400)) from e
    except Exception as e:  # noqa: BLE001 (network / not found)
        raise AttachError(getattr(e, "kind", "network"), 502) from e
    entry = link(d, {"sha": sha, "shelf": shelf, "source_id": src["id"], "name": url, "kind": "url",
                     **({"cell": cell} if cell else {})})
    save_digest(ctx, shelf, {"sha": sha, "version": EXTRACTOR_VERSION, "state": "reading", "source_id": src["id"],
                             "name": url, "kind": "url", "t": time.time()})
    return entry, True


def _title(name: str) -> str:
    return re.sub(r"\.[A-Za-z0-9]{1,5}$", "", name or "image")[:200] or "image"


def _first_added(lib, shelf: str, res: dict):
    for a in (res.get("added") or []) + [x for x in (res.get("duplicates") or [])]:
        try:
            return lib.get(shelf, a["id"])
        except Exception:  # noqa: BLE001
            continue
    return None


# ---------------------------------------------------------------- read once
async def read(ctx, shelf: str, sha: str, *, mode: str, budget: Budget | None = None, force: bool = False,
               lang: str = "fr") -> dict:
    """Build the digest of one attachment (once). `force` = « relire »."""
    dig = load_digest(ctx, shelf, sha) or {}
    if dig.get("state") in ("read", "unread") and dig.get("version") == EXTRACTOR_VERSION and not force:
        return dig
    sid = dig.get("source_id")
    lib = _lib(ctx)
    try:
        src = lib.get(shelf, sid)
    except Exception:  # noqa: BLE001
        raise AttachError("not_found", 404)
    budget = (budget or Budget(seconds=180, requests=4, model_calls=4, lean_checks=8, formalize=2)).start()
    t0 = time.monotonic()
    texts: list[SourceText] = []
    labels: list[str] = []
    transcription: dict | None = None
    state = "read"
    kind = dig.get("kind", "")
    if kind == "image":
        f = next((x for x in src.get("files", []) if x.get("kind") == "image"), None)
        text, model = "", ""
        if f is not None:
            data = await asyncio.to_thread(lib.shelf(shelf).blob(f["sha256"]).read_bytes)
            text, model = await transcribe_image(ctx, data, mode, budget)
        if text:
            transcription = {"text": text, "model": model, "note": "transcription"}
            st = SourceText("transcription", "attachment", text, licence="your own file (Sources)")
            st.suspect = Q.suspect(text)
            texts.append(st)
        else:
            state = "unread"
    else:
        chunks = await _chunks(lib, shelf, sid, src)
        for c in chunks:
            if c.get("kind") not in THEOREM_KINDS:
                continue
            t = Q.clean(c.get("text", ""), 4000)
            if len(t) < Q.MIN_QUOTE:
                continue
            loc = str(c.get("locator") or c.get("label") or "")[:80]
            texts.append(SourceText("fulltext", "sources", t, locator=loc,
                                    page=c.get("page") if isinstance(c.get("page"), int) else None,
                                    licence="your own file (Sources)", suspect=Q.suspect(t)))
            labels.append(str(c.get("kind")))
            if len(texts) >= MAX_STATEMENTS:
                break
    record = await _record(ctx, lib, shelf, src, texts, mode)
    ref = record["reference"]
    items: list[LiteratureItem] = []
    if kind == "image" and texts:
        t = texts[0].text
        for i, (a, b) in enumerate(Q.sentences(t)):
            s = t[a:b]
            if len(s) >= Q.MIN_QUOTE and Q.RESULT_MARKERS.search(s) and len(items) < MAX_STATEMENTS:
                it = LiteratureItem(id=item_id(f"att:{sha}:{i}"), reference=ref, texts=texts, origin="attachment",
                                    label="")
                _quote(it, 0, s, Q.location("transcription", i + 1, lang=lang) if lang != "en" else
                       f"image transcription, sentence {i + 1}")
                if it.quotes:
                    items.append(it)
    else:
        for i, t in enumerate(texts):
            it = LiteratureItem(id=item_id(f"att:{sha}:{i}"), reference=ref, texts=[t], origin="attachment",
                                label=t.locator or labels[i])
            body = t.text if len(t.text) <= Q.MAX_QUOTE else t.text[: t.text.rfind(". ", 0, Q.MAX_QUOTE) + 1]
            _quote(it, 0, body, Q.location("fulltext", 0, t.locator, t.page, lang))
            if it.quotes:
                items.append(it)
    # optional Lean statements (free online models, Lean-checked), within the budget
    ws = ctx.workspace(getattr(ctx.settings, "workspace", ""))
    if ws is not None and mode != "local":
        io = formal.LitIO(ctx, mode, budget, owner=f"attach-{sha[:8]}")
        n = 0
        for it in items:
            if n >= budget.formalize or budget.over:
                break
            n += 1
            await formal.formalize(io, it, ws, getattr(ctx.settings, "compile_timeout_s", 180))
            if it.lean.compiled:
                await formal.mathlib_status(ctx, io, it, ws, getattr(ctx.settings, "compile_timeout_s", 180))
    for it in items:
        if not it.lean.name:
            it.lean.name = formal.cited_name(it)
    out = {"sha": sha, "version": EXTRACTOR_VERSION, "state": state, "source_id": sid, "name": dig.get("name", ""),
           "kind": kind, "record": {k: v for k, v in record.items() if k != "reference"},
           "reference": _asdict(ref), "transcription": transcription,
           "items": [_asdict(it) for it in items], "t": time.time(), "seconds": round(time.monotonic() - t0, 2),
           "usage": budget.usage()}
    save_digest(ctx, shelf, out)
    return out


def _asdict(x) -> dict:
    from dataclasses import asdict
    return asdict(x)


def _quote(it: LiteratureItem, ti: int, text: str, location: str) -> None:
    src = it.texts[ti].text
    span = Q.verify(text, src)
    if span is None:
        return
    a, b = span
    it.quotes.append(Quote(text=src[a:b], text_index=ti, start=a, end=b, location=location))


async def _chunks(lib, shelf: str, sid: str, src: dict) -> list[dict]:
    """The Sources' extracted full text (waits for the extraction the import scheduled, ≤ 120 s)."""
    for _ in range(240):
        if sid not in lib.busy:
            break
        await asyncio.sleep(0.5)
    cur = lib.get(shelf, sid)
    if (cur.get("fulltext") or {}).get("state") in (None, "none") and any(
            f.get("kind") in ("pdf", "tex", "archive", "epub") for f in cur.get("files", [])):
        try:
            await lib.extract(shelf, sid)
        except Exception as e:  # noqa: BLE001
            log.info("extraction of %s failed: %s", sid, e)
    try:
        return await asyncio.to_thread(lib.chunks_of, shelf, sid)
    except Exception:  # noqa: BLE001
        return []


async def _record(ctx, lib, shelf: str, src: dict, texts: list[SourceText], mode: str) -> dict:
    """The bibliographic record: the Source's own when verified, else an identifier found in the text resolved
    through the scholarly APIs (verified), else « référence non vérifiée »."""
    from ..research import biblio, litsearch
    csl, verified, via = dict(src.get("csl") or {}), bool(src.get("verified")), "source"
    if not verified and mode != "local":
        blob = " ".join(t.text for t in texts)[:20000]
        m = biblio.DOI_RE.search(blob) or re.search(r"arXiv:\s*(\d{4}\.\d{4,5})", blob)
        if m:
            ident = m.group(0) if m.re is biblio.DOI_RE else f"arXiv:{m.group(1)}"
            try:
                found = await asyncio.wait_for(litsearch.resolve(lib.fetcher, ident, mode), 30)
                csl, verified, via = dict(found.item), True, found.via
            except Exception:  # noqa: BLE001
                pass
    rec = R.Record(csl, {"sources": 0} if not verified else {via if via in ("zbmath", "openalex", "arxiv",
                                                                           "crossref") else "crossref": 0},
                   shelf=shelf, source_id=src["id"], source_verified=verified)
    ref = R.reference_of(rec)
    if not ref.title:
        ref.title = csl.get("title") or src.get("key", "")
    return {"verified": verified, "via": via, "reference": ref}


# ---------------------------------------------------------------- vision
async def transcribe_image(ctx, data: bytes, mode: str, budget: Budget) -> tuple[str, str]:
    """One vision call (free online model; a local one in Local mode). ('', '') when none can read it."""
    from ..research.safety import image_type
    if not budget.take("model"):
        return "", ""
    brain = ctx.brain
    mime = image_type(data) or "image/png"
    hook = getattr(brain, "vision", None)          # a brain that reads images directly (tests, future adapters)
    try:
        if hook is not None:
            text, model = await asyncio.wait_for(hook(data, mime, VISION_PROMPT, mode=mode), budget.left() + 1)
        else:
            text, model = await _vision_via_chat(brain, data, mime, mode, budget)
    except Exception as e:  # noqa: BLE001 (no vision model, provider refused the image…)
        log.info("image not read: %s", e)
        return "", ""
    text = (text or "").strip()
    if not text or text.upper().startswith("NONE"):
        return "", model or ""
    return text[:MAX_TRANSCRIPTION], model or ""


async def _vision_via_chat(brain, data: bytes, mime: str, mode: str, budget: Budget) -> tuple[str, str]:
    cands = []
    try:
        for c in brain.candidates("understand", mode):
            if not getattr(c, "vision", False):
                continue
            if mode == "local" and c.local or mode != "local" and not c.local and not c.paid:
                cands.append(c)
    except Exception:  # noqa: BLE001
        return "", ""
    url = f"data:{mime};base64," + base64.b64encode(data).decode()
    content = [{"type": "text", "text": VISION_PROMPT}, {"type": "image_url", "image_url": {"url": url}}]
    for c in cands[:2]:
        try:
            res = await asyncio.wait_for(brain.complete("understand", [{"role": "user", "content": content}],
                                                        mode=mode, temperature=0.0, max_tokens=3000, only=c.key),
                                         max(5.0, budget.left()))
        except Exception:  # noqa: BLE001
            continue
        if getattr(res.model, "paid", False):
            continue
        return res.text, res.model.key
    return "", ""


# ---------------------------------------------------------------- use
def digests(ctx, d) -> list[dict]:
    """The dossier's attachments first, then the other digests of the project (read once, reused everywhere)."""
    shelf = shelf_of(ctx, d)
    out, seen = [], set()
    for a in d.extra.get("attachments") or []:
        dig = load_digest(ctx, a.get("shelf", shelf), a.get("sha", ""))
        if dig is not None:
            out.append({**dig, "n": a.get("n"), "here": True})
            seen.add(dig["sha"])
    try:
        folder = _lib(ctx).shelf(shelf).root / "digests"
        for p in sorted(folder.glob("*.json"))[:200]:
            if p.stem in seen:
                continue
            dig = load_digest(ctx, shelf, p.stem)
            if dig is not None and dig.get("items"):
                out.append({**dig, "here": False})
    except Exception:  # noqa: BLE001
        pass
    return out


def provided_items(ctx, d) -> list[LiteratureItem]:
    """« Résultats fournis »: the statements of the attachments / project digests, typed like cited results."""
    items: list[LiteratureItem] = []
    for dig in digests(ctx, d):
        items.extend(items_of(dig))
    return items


def mentions(ctx, d, text: str) -> list[dict]:
    """« d'après la pièce jointe 2, lemme 3.1 » → the digest items meant, with their verbatim quotes."""
    out = []
    atts = {a.get("n"): a for a in d.extra.get("attachments") or []}
    for m in _MENTION.finditer(text or ""):
        a = atts.get(int(m.group(1)))
        if a is None:
            continue
        dig = load_digest(ctx, a.get("shelf", ""), a.get("sha", ""))
        its = items_of(dig)
        if m.group(2):
            word = LABEL_EN.get(m.group(2).lower(), m.group(2).lower())
            word = {"théorème": "theorem", "théoreme": "theorem"}.get(word, word)
            num = m.group(3)
            its = [it for it in its if re.search(rf"\b{word[:4]}\w*\s*{re.escape(num)}\b", it.label or
                                                 (it.quotes[0].location if it.quotes else ""), re.I)]
        for it in its[:3]:
            if it.quotes:
                out.append({"n": a.get("n"), "name": a.get("name"), "item": it.id, "label": it.label,
                            "quote": it.quotes[0].text, "location": it.quotes[0].location,
                            "lean": it.lean.statement if it.lean.compiled else ""})
    return out


def with_mentions(ctx, d, text: str) -> str:
    """The request text with the attachments it names quoted from their digests (never the raw document)."""
    try:
        found = mentions(ctx, d, text)
    except Exception:  # noqa: BLE001
        return text
    if not found:
        return text
    lines = [text, "", "Referenced attachments (quoted verbatim from their digests):"]
    for f in found[:4]:
        lines.append(f"- attachment {f['n']} ({f['location']}): \"{f['quote'][:800]}\"")
        if f["lean"]:
            lines.append(f"  Lean: {f['lean'].split('theorem', 1)[-1][:400]}")
    return "\n".join(lines)
