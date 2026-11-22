"""Small helpers shared by the brain modules (private files, time)."""
from __future__ import annotations

import re
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def now() -> float:
    return time.time()


def write_private(path: Path, text: str) -> None:
    """Atomic write with mode 0600 (state and catalogue may reveal which providers the user has keys for)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def short(text: str, n: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------- mojibake (S-AI follow-up, 2026-11-22)
# Seen on real conductor answers: French accents arriving as UTF-8 bytes re-read in a legacy code page
# (« l'Ă©quivalence », « l'Î“Â©quivalence », « Â« … Â» », « â‰  »), a different code page from one answer to the
# next. Each run of non-ASCII characters is re-encoded in the usual suspects and kept when the bytes are valid UTF-8
# and shorter (the repaired text); a run that is not mojibake never re-decodes (strict UTF-8), so text is unchanged.
_MOJI_CODEPAGES = ("cp1252", "cp1250", "iso8859_16", "iso8859_2", "cp1253", "cp1251", "latin-1", "cp1254", "cp1257",
                   "mac_roman")
# characters a repaired French/maths text is made of: a candidate made only of these wins over another one
_MOJI_GOOD = set("àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ«»’‘“”…–—≠≤≥∀∃∈∉⊂⊆∪∩ℕℤℚℝℂ→↦⇒⇔×·°±√∞αβγδεζηθλμνπρστφχψωΓΔΘΛΠΣΦΨΩ\u00a0")
_MOJI_RUN = re.compile(r"([^\x00-\x7f]+)( ?)")      # a following space may be a lost NBSP byte (≠ → â‰\xa0)
_MOJI_HINT = re.compile(r"[ÂÃĂÎΓâ][\u0080-˿Ͱ-Ͽ -⃿℀-⅟]")


def fix_mojibake(text: str) -> str:
    if not text or not _MOJI_HINT.search(text):
        return text

    def decode(run: str) -> str | None:
        best, score = None, None
        for cp in _MOJI_CODEPAGES:
            try:
                cand = run.encode(cp).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if len(cand) >= len(run):
                continue
            s = (sum(ch in _MOJI_GOOD or ch.isascii() for ch in cand) / len(cand), -len(cand))
            if score is None or s > score:
                best, score = cand, s
        return best

    def fix_run(run: str) -> str | None:
        out = None
        for _ in range(2):                         # double-encoded text: two passes at most
            fixed = decode(run)
            if fixed is None:
                break
            run = out = fixed
        return out

    def one(m: re.Match) -> str:
        run, space = m.group(1), m.group(2)
        fixed = fix_run(run)
        if fixed is not None:
            return fixed + space
        if space:                                  # the NBSP of a 3-byte character became a plain space
            fixed = fix_run(run + "\u00a0")
            if fixed is not None:
                return fixed
        return run + space
    return _MOJI_RUN.sub(one, text)


def looks_mojibake(text: str) -> bool:
    return bool(text and _MOJI_HINT.search(text))


def fix_mojibake_deep(v):
    """`fix_mojibake` on every string of a JSON-like value."""
    if isinstance(v, str):
        return fix_mojibake(v)
    if isinstance(v, list):
        return [fix_mojibake_deep(x) for x in v]
    if isinstance(v, dict):
        return {k: fix_mojibake_deep(x) for k, x in v.items()}
    return v
