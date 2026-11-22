"""Fast code transcription for the Calcul screen (session S-AB, DECISIONS D35): a request in natural language → one
Sage / Python cell, in seconds, written against the INSTALLED version.

- Model: `classify.task("transcribe")` — code models ranked with their measured latency, thinking capped, a
  staggered parallel start when the first model is slow (brain/engine.py `_race`). No online slot of the job
  scheduler: a transcription never waits behind a dossier's long proof calls (the brain keeps its own small pool).
- Prompt: fixed system prompt (rules + verified syntax card, syntaxcards.py: cacheable) + a short user message
  (names, last cells, exact signatures of the functions the request needs).
- Validation before showing: the installed Sage's preparser + compile + undefined names (never executes); on an
  error the error goes back to the model ONCE for a quick fix.
- Streaming: `on_code(partial)` receives the code as it arrives (the cell fills while the model writes).
- Cache: an identical first request (same text, names, context, version) is answered from memory (1 h); « Réécrire »
  never uses it.
- One generation per cell (`Generations`): a new request for a cell cancels the one still running for it."""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import OrderedDict
from typing import Callable

from .. import syntaxcards
from ..brain import classify
from ..slots import CURRENT_JOB
from .calcul import extract_code
from .notebook import ask_messages

CACHE_TTL = 3600.0
CACHE_MAX = 64
MAX_TOKENS = 1500
_OPEN = re.compile(r"```[ \t]*([\w+-]*)[ \t]*\n")


class Replaced(Exception):
    """This generation was replaced by a newer request for the same cell."""


class Generations:
    """At most one running generation (ask, automatic fix, explanation) per cell key; a new one cancels the old."""

    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}
        self._replaced: set[asyncio.Task] = set()

    def running(self, key: str) -> bool:
        t = self.tasks.get(key)
        return t is not None and not t.done()

    async def cancel(self, key: str) -> None:
        t = self.tasks.get(key)
        if t is not None and not t.done():
            self._replaced.add(t)
            t.cancel()
            await asyncio.wait([t])

    async def run(self, key: str, coro):
        await self.cancel(key)
        task = asyncio.ensure_future(coro)
        self.tasks[key] = task
        try:
            return await task
        except asyncio.CancelledError:
            if task in self._replaced and task.cancelled():
                raise Replaced() from None
            task.cancel()                     # the caller itself was cancelled: stop its generation too
            raise
        finally:
            self._replaced.discard(task)
            if self.tasks.get(key) is task:
                del self.tasks[key]


_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()


def _cache_key(*parts) -> str:
    return hashlib.sha256("\x00".join(str(p) for p in parts).encode()).hexdigest()


def partial_code(text: str) -> str:
    """The code written so far inside the first fenced block (for streaming into the cell)."""
    m = _OPEN.search(text or "")
    if not m:
        return ""
    body = text[m.end():]
    end = body.find("```")
    return (body[:end] if end >= 0 else body.rstrip("`")).rstrip()


def validate(code: str, language: str, known: set[str]) -> dict:
    if language == "sage":
        return syntaxcards.validate_sage(code, known)
    return syntaxcards.validate_python(code)


async def _complete(ctx, msgs: list[dict], owner: str, on_chunk, max_tokens: int = MAX_TOKENS):
    """The fast code role: `classify.task("transcribe")`, no job-scheduler slot (see the module docstring)."""
    token = CURRENT_JOB.set(owner)
    try:
        with classify.task("transcribe"):
            return await ctx.brain.complete("assistant", msgs, mode=ctx.settings.mode, temperature=0.2,
                                            max_tokens=max_tokens, on_chunk=on_chunk,
                                            prefer=(ctx.settings.prefer or {}).get("calcul") or None)
    finally:
        try:
            ctx.local.release_owner(owner)
        except Exception:  # noqa: BLE001
            pass
        CURRENT_JOB.reset(token)


def card_for(language: str) -> tuple[str, str, bool]:
    """(card, version, verified) — blocking (reads the installed version once per 10 min)."""
    if language != "sage":
        return "", "", True
    v = syntaxcards.sage_version()
    card, ok = syntaxcards.sage_card(v)
    return card, v, ok


VALIDATE_FIXES = 2            # repairs before showing (the code did not compile): each attempt is a cell version


def uses_of(code: str, known: set[str]) -> list[str]:
    """Names of earlier cells the code relies on (shown « utilise F, f des cellules précédentes »)."""
    bare = re.sub(r"([\x27\"]).*?\1", "", code)
    assigned: set[str] = set()
    for m in re.finditer(r"^\s*([A-Za-z_][\w\s,]*?)(?:\.<([^>]*)>)?\s*=(?!=)", bare, re.M):
        assigned |= {x.strip() for x in m.group(1).split(",") if x.strip()}
        assigned |= {x.strip() for x in (m.group(2) or "").split(",") if x.strip()}
    assigned |= set(re.findall(r"\bdef\s+(\w+)", bare)) | set(re.findall(r"\bfor\s+(\w+)\s+in\b", bare))
    found = set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)\b", bare))
    return sorted((found & set(known)) - assigned)


async def transcribe(ctx, *, language: str, prompt: str, names: list, context: str, owner: str, lang: str = "fr",
                     use_cache: bool = False, on_code: Callable[[str], None] | None = None,
                     fix_code: str = "", fix_error: str = "", recipes=None) -> dict:
    """→ {code, model, seconds, first_s, valid, error, fixed, cached, attempts, uses, recipe, fallbacks}. Raises
    BrainError when no model answers. `fix_code` + `fix_error`: repair a cell that failed when run (automatic fix).
    `recipes` (research/recipes.py): a learned recipe answers at once (shortcut) or is given as an example; never
    for « Réécrire » (`use_cache` False: the user wants another answer)."""
    t0 = time.monotonic()
    card, version, verified = await asyncio.to_thread(card_for, language)
    if language == "sage" and not verified:
        syntaxcards.schedule(ctx)                     # first use of this Sage version: build its verified card
    known = {n for n, _t, _r in names or []}
    fixing = bool(fix_code)
    example = ""
    recipe_id = ""
    if recipes is not None and not fixing:
        m = await asyncio.to_thread(recipes.match, prompt, language, version, known)
        if m and m["kind"] == "shortcut" and use_cache:
            chk = await asyncio.to_thread(validate, m["code"], language, known)
            if chk["ok"]:
                await asyncio.to_thread(recipes.hit, m["recipe"]["id"])
                if on_code:
                    on_code(m["code"])
                return {"code": m["code"], "model": "recipe", "valid": True, "error": "", "fixed": False,
                        "cached": True, "attempts": [], "uses": uses_of(m["code"], known), "fallbacks": [],
                        "recipe": m["recipe"]["id"], "seconds": round(time.monotonic() - t0, 2), "first_s": 0.0}
        if m:
            r = m["recipe"]
            example = f"Request: {r['request'][:500]}\n```{'sage' if language == 'sage' else 'python'}\n{r['code'][:3000]}\n```"
            recipe_id = r["id"]
    sigs = syntaxcards.sage_signatures(prompt, fix_code, version) if language == "sage" else ""
    msgs = ask_messages(lang, language, prompt, names, context, fix=fixing, code=fix_code, error=fix_error,
                        card=card, sigs=sigs, example=example)
    key = _cache_key(language, version, prompt.strip(), names, context[-2500:])
    if use_cache and not fixing:
        hit = _CACHE.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            _CACHE.move_to_end(key)
            if on_code:
                on_code(hit[1]["code"])
            return {**hit[1], "seconds": round(time.monotonic() - t0, 2), "first_s": 0.0, "cached": True,
                    "attempts": [], "fallbacks": [], "recipe": ""}
    first: list = [None]                      # seconds to the first visible code
    buf: list[str] = []
    last = [0.0]

    def on_chunk(ch) -> None:
        if ch.kind == "info" and (ch.data or {}).get("event") == "restart":
            buf.clear()
            return
        if ch.kind != "text" or not ch.text:
            return
        buf.append(ch.text)
        now = time.monotonic()
        if on_code and now - last[0] > 0.12:
            part = partial_code("".join(buf))
            if part:
                last[0] = now
                if first[0] is None:
                    first[0] = now - t0
                on_code(part)
    r = await _complete(ctx, msgs, owner, on_chunk)
    code = extract_code(r.text)
    if code and first[0] is None:
        first[0] = time.monotonic() - t0
    if on_code and code:
        on_code(code)
    model = getattr(r.model, "key", "") or ""
    out = {"code": code, "model": model, "valid": True, "error": "", "fixed": False, "cached": False,
           "attempts": [], "recipe": recipe_id, "fallbacks": list(getattr(r, "fallbacks", None) or [])}
    if code:
        chk = await asyncio.to_thread(validate, code, language, known)
        tries = 0
        while not chk["ok"] and tries < VALIDATE_FIXES:
            # automatic repair with the exact error (and the signatures of what the code calls): nothing ran yet
            tries += 1
            out["attempts"].append({"code": code, "error": chk["error"][:500]})
            sigs2 = syntaxcards.sage_signatures(prompt, code, version) if language == "sage" else ""
            msgs2 = ask_messages(lang, language, prompt, names, "", fix=True, code=code,
                                 error=f"{chk['error']}\n(found before running: the code does not compile)",
                                 card=card, sigs=sigs2)
            try:
                r2 = await _complete(ctx, msgs2, owner, None)
                code2 = extract_code(r2.text)
            except Exception:  # noqa: BLE001 (keep the last proposal)
                break
            if not code2:
                break
            code, model = code2, getattr(r2.model, "key", "") or model
            chk = await asyncio.to_thread(validate, code, language, known)
            if on_code:
                on_code(code)
        out.update(code=code, model=model, fixed=tries > 0 and chk["ok"], valid=chk["ok"],
                   error="" if chk["ok"] else chk["error"])
    out.update(seconds=round(time.monotonic() - t0, 2), first_s=round(first[0] or 0.0, 2),
               uses=uses_of(code, known) if code else [])
    if code and out["valid"] and not fixing:
        _CACHE[key] = (time.monotonic(), {k: out[k] for k in ("code", "model", "valid", "error", "fixed", "uses")})
        while len(_CACHE) > CACHE_MAX:
            _CACHE.popitem(last=False)
    return out


# ================================================================ code or request? (S-AB, the « + » cell)
_NL_START = re.compile(
    r"^(trace|tracer|dessine|calcule|calculer|factorise|factoriser|r[ée]sou[st]|r[ée]soudre|montre|donne|"
    r"trouve|cherche|d[ée]veloppe|simplifie|d[ée]rive|int[èe]gre|quel(le)?s?|combien|comment|pourquoi|est-ce|"
    r"peux-tu|affiche|v[ée]rifie|compare|liste|[ée]cris|fais|construis|repr[ée]sente|d[ée]termine|cr[ée]e|"
    r"plot|draw|compute|calculate|factor|solve|show|give|find|list|what|which|how|why|is|are|does|can|"
    r"simplify|expand|integrate|differentiate|check|verify|write|make|build|create|determine|graph)\b(?![ \t]*[(=.\[])",
    re.I)
_FR_WORDS = re.compile(r"\b(le|la|les|des|du|de|un|une|sur|pour|avec|dans|et|entre|son|sa|ses|of|the|and|for|"
                       r"with|between|its|from|on)\b", re.I)
_CODE_MARK = re.compile(r"[=()\[\]{}]|\b(def|for|import|return|lambda|print)\b|\.\w+\(|^\s*#|\^|\*\*|:\s*$", re.M)


def detect(text: str, language: str = "sage", known: set[str] | None = None) -> dict:
    """Is what was typed code (run it) or a request in words (the model writes the code)? → {kind, why}.
    Code that the installed Sage / Python compiles and whose names all exist wins; natural-language markers (a
    request verb or question word at the start, French / English function words, a question mark, accents
    outside strings) win otherwise. The UI shows the guess as a one-click chip the user can switch."""
    t = (text or "").strip()
    if not t:
        return {"kind": "code", "why": "empty"}
    chk = validate(t, language, known or set()) if language in ("sage", "python") else {"ok": False}
    words = re.findall(r"[^\W\d_]{2,}", t)
    nl = 0
    why = []
    if _NL_START.match(t):
        nl += 2
        why.append("request verb")
    fw = len(_FR_WORDS.findall(re.sub(r"(['\"]).*?\1", "", t)))
    if fw >= 2 or (fw == 1 and len(words) >= 3):
        nl += 2 if fw >= 2 else 1
        why.append("sentence words")
    if t.endswith("?"):
        nl += 2
        why.append("question")
    stripped = re.sub(r"(['\"]).*?\1", "", t)
    if re.search(r"[À-ÿ²³]", stripped):
        nl += 1
        why.append("accents")
    code = 0
    if chk.get("ok"):
        code += 3
        why.append("compiles")
    elif chk.get("unknown"):
        code += 1                                  # compiles, but uses names defined nowhere: words?
        nl += 1 if len(chk["unknown"]) >= 2 else 0
    if _CODE_MARK.search(stripped):
        code += 1
    if "\n" in t and chk.get("ok"):
        code += 1
    return {"kind": "ask" if nl > code else "code", "why": ", ".join(why) or "default", "nl": nl, "code": code}


fast_complete = _complete                       # for research/explain.py (and the Lean explanations to come)
