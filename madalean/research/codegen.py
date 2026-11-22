"""Code transcription for the Calcul screen: a request in natural language → one Sage / Python cell, in seconds,
written against the INSTALLED version — and the SAME code every time (sessions S-AB, DECISIONS D35, and S-AG, D39).

Pipeline (`transcribe`):
1. **Analysis** (`intent.py`, no model): objects with canonical parameters (F_125 = F_{5^3} = GF(125)), operation,
   formulas in one spelling, variables; a wrong request (F_12) is explained at once, no code.
2. **The best version** of this intent (`recipes.py`, keyed by intent, not by words): returned as is — also by
   « Réécrire » (the user wants one syntax per request). Only « Autre version » (`variant=True`) asks for another.
3. **Catalogue** (`codecat.py`): a fully covered intent is assembled from the verified canonical constructions —
   no model, byte-identical every time.
4. **Model** (partially covered or not recognized): the catalogue's constructions are a MANDATORY prefix (enforced
   afterwards: `codefix.enforce_prefix`), temperature 0 + seed, ONE pinned model per language chosen by measured
   success on Calcul (`ModelStats`); the staggered race of D35 is only the fallback when that model fails or times
   out. Earlier failing versions of the same request are shown as « do not repeat ».
5. **Canonical output** (`codefix.py`): imports at the top, deduplicated, ordered; missing imports / library loads /
   earlier definitions added from a static analysis of the names, before any model repair.
6. Validation before showing (installed Sage's preparser + compile + undefined names); the deterministic fixer first,
   then the model (≤ 2 times). Streaming: `on_code(partial)`.
One generation per cell (`Generations`): a new request for a cell cancels the one still running for it."""
from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Callable

from .. import config, syntaxcards
from ..brain import classify
from ..logs import get
from ..slots import CURRENT_JOB
from . import codecat, codefix
from . import intent as I
from .calcul import extract_code
from .notebook import ask_messages
from .recipes import request_key

log = get("codegen")
CACHE_MAX = 64
MAX_TOKENS = 1500
TEMPERATURE = 0.0              # reproducible: the same request gives the same code
VARIANT_TEMPERATURE = 0.7      # « Autre version »: the user explicitly asked for a different one
SEED = 7
PIN_TIMEOUT = 45.0             # the pinned model has this long before the race of D35 takes over
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


class MemoryBest:
    """The best-version store when no recipe file is given (tests, other callers): same contract as
    `RecipeStore.best / record / failed_codes`, in memory, bounded."""

    def __init__(self):
        self.items: OrderedDict[tuple, dict] = OrderedDict()

    def best(self, key, language, version, known=None):
        r = self.items.get((key, language, version))
        if r is None or not set(r["uses"]) <= set(known or ()):
            return None
        return {"code": r["code"], "recipe": "", "vid": "", "origin": r["origin"], "model": r["model"]}

    def record(self, key, request, code, language, version, *, origin="model", model="", uses=None, summary=""):
        k = (key, language, version)
        if k not in self.items:
            self.items[k] = {"code": code, "origin": origin, "model": model, "uses": list(uses or [])}
            while len(self.items) > CACHE_MAX:
                self.items.popitem(last=False)
        return {"recipe": "", "vid": "", "best": self.items[k]["code"] == code}

    def failed_codes(self, key, language, version):
        return []

    def versions_count(self, key, language, version):
        return 1 if (key, language, version) in self.items else 0


_MEMORY = MemoryBest()


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


async def _complete(ctx, msgs: list[dict], owner: str, on_chunk, max_tokens: int = MAX_TOKENS, *,
                    temperature: float | None = TEMPERATURE, seed: int | None = None, only: str | None = None):
    """The fast code role: `classify.task("transcribe")`, no job-scheduler slot (see the module docstring).
    `only`: this model alone (the pinned model of the language); otherwise the staggered race of D35."""
    token = CURRENT_JOB.set(owner)
    try:
        with classify.task("transcribe"):
            kw = {}
            if seed is not None:
                kw["extra"] = {"seed": seed}
            if only:
                kw["only"] = only
            return await ctx.brain.complete("assistant", msgs, mode=ctx.settings.mode, temperature=temperature,
                                            max_tokens=max_tokens, on_chunk=on_chunk,
                                            prefer=(ctx.settings.prefer or {}).get("calcul") or None, **kw)
    finally:
        try:
            ctx.local.release_owner(owner)
        except Exception:  # noqa: BLE001
            pass
        CURRENT_JOB.reset(token)


# ================================================================ one pinned model per language (D39)
class ModelStats:
    """Measured success of the models on Calcul (per language): code shown, code valid, runs OK / failed. The pinned
    model is the one with the best smoothed run success (≥ MIN_RUNS runs); it stays pinned until another model is
    clearly better (MARGIN, ≥ MIN_RUNS + 2 runs) or it fails twice in a row (unavailable, timeout). Without data:
    the first model of the transcription ranking, pinned at first use (never « whichever answers first »).
    Local file `<config>/research/codegen-models.json` (0600)."""
    MIN_RUNS = 3
    MARGIN = 0.15

    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._mem: dict = {}

    def _load(self) -> dict:
        if self.path is None:
            return self._mem
        data, _bad = config.read_json(self.path)
        return data if isinstance(data, dict) else {}

    def _save(self, d: dict) -> None:
        if self.path is None:
            self._mem = d
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        config.atomic_write_text(self.path, json.dumps(d, ensure_ascii=False))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _score(s: dict) -> float:
        ok, fail = s.get("ok", 0), s.get("fail", 0)
        return (ok + 1) / (ok + fail + 2)

    def _bump(self, language: str, model: str, **inc) -> None:
        if not model or model in ("catalogue", "best", "recipe", "fix"):
            return
        with self._lock:
            d = self._load()
            s = d.setdefault(language, {}).setdefault("models", {}).setdefault(model, {})
            for k, v in inc.items():
                s[k] = s.get(k, 0) + v
            self._save(d)

    def generated(self, language: str, model: str, valid: bool) -> None:
        self._bump(language, model, gen=1, valid=int(valid))

    def ran(self, language: str, model: str, ok: bool) -> None:
        self._bump(language, model, ok=int(ok), fail=int(not ok))

    def failure(self, language: str, model: str) -> None:
        """The pinned model did not answer (error, timeout): twice in a row → unpinned."""
        with self._lock:
            d = self._load()
            L = d.setdefault(language, {})
            L["misses"] = L.get("misses", 0) + 1
            if L["misses"] >= 2 and L.get("pinned") == model:
                L["pinned"] = ""
                L["misses"] = 0
                L.setdefault("skip", [])
                L["skip"] = (L["skip"] + [model])[-5:]
            self._save(d)

    def success(self, language: str, model: str) -> None:
        with self._lock:
            d = self._load()
            L = d.setdefault(language, {})
            if L.get("misses"):
                L["misses"] = 0
                self._save(d)

    def pinned(self, language: str, ranked: list[str], forced: str = "") -> str:
        """The model to ask first for this language (sticky). `ranked`: available models, best first."""
        if forced:
            return forced
        with self._lock:
            d = self._load()
            L = d.setdefault(language, {})
            models = L.get("models") or {}
            cur = L.get("pinned") or ""
            avail = [m for m in ranked if m not in (L.get("skip") or [])] or list(ranked)
            measured = sorted(((self._score(s), s.get("ok", 0) + s.get("fail", 0), m) for m, s in models.items()
                               if s.get("ok", 0) + s.get("fail", 0) >= self.MIN_RUNS and m in avail), reverse=True)
            choice = cur if cur in avail else ""
            if measured:
                top_score, top_n, top = measured[0]
                if not choice:
                    choice = top
                elif top != choice:
                    cs = models.get(choice) or {}
                    if top_n >= self.MIN_RUNS + 2 and top_score >= self._score(cs) + self.MARGIN:
                        choice = top
            if not choice and avail:
                choice = avail[0]
            if choice != cur:
                L["pinned"] = choice
                L["since"] = time.time()
                self._save(d)
            return choice

    def view(self) -> dict:
        with self._lock:
            return self._load()


def _ranked_models(ctx) -> list[str]:
    """Online models of the transcription ranking, best first (empty when the brain cannot say)."""
    rank = getattr(ctx.brain, "ranking", None)
    if rank is None:
        return []
    try:
        with classify.task("transcribe"):
            chain = rank("assistant", ctx.settings.mode)
        return [c.model.key for c in chain if not getattr(c.model, "local", False)]
    except Exception:  # noqa: BLE001
        return []


async def _model_call(ctx, msgs, owner, on_chunk, language: str, stats: ModelStats | None, *,
                      temperature: float, seed: int):
    """The pinned model first (temperature 0, seed), the race of D35 when it fails or is too slow."""
    forced = (ctx.settings.prefer or {}).get("calcul") or ""
    ranked = await asyncio.to_thread(_ranked_models, ctx) if stats is not None else []
    pin = stats.pinned(language, ranked, forced) if stats is not None and (ranked or forced) else ""
    if pin:
        try:
            r = await asyncio.wait_for(_complete(ctx, msgs, owner, on_chunk, temperature=temperature, seed=seed,
                                                 only=pin), PIN_TIMEOUT)
            stats.success(language, pin)
            return r, pin, False
        except asyncio.CancelledError:
            raise
        except TypeError:
            pass                                   # a brain without `only` (tests): the normal path
        except Exception as e:  # noqa: BLE001 (BrainError, timeout): the race takes over
            log.info("pinned model %s failed for Calcul (%s): race", pin, type(e).__name__)
            stats.failure(language, pin)
            if on_chunk is not None:
                from ..brain.api import Chunk
                try:
                    on_chunk(Chunk("info", "", data={"event": "restart"}))
                except TypeError:
                    pass
    r = await _complete(ctx, msgs, owner, on_chunk, temperature=temperature, seed=seed)
    return r, pin, True


def card_for(language: str) -> tuple[str, str, bool]:
    """(card, version, verified) — blocking (reads the installed version once per 10 min)."""
    if language != "sage":
        return "", "", True                  # Python recipes are not tied to a version (as in S-AB)
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


def _sage_names(version: str) -> set[str]:
    d = syntaxcards.sage_card_data(version) if version else None
    return set((d or {}).get("names") or ())


def canonical(code: str, language: str, known: set[str], prev: dict[str, str] | None, version: str) -> str:
    """Imports at the top, missing imports / loads / earlier definitions added (codefix.py). Blocking."""
    names = _sage_names(version) if language == "sage" else None
    if language == "sage" and not names:            # no name index yet: never guess « missing » Sage names
        return codefix.canonicalize(code, language, known, prev, None, check_missing=False)["code"]
    return codefix.canonicalize(code, language, known, prev, names)["code"]


def _analysis(it: I.Intent) -> dict:
    return {"recognized": {"fr": I.summary(it, "fr"), "en": I.summary(it, "en")} if it.recognized else None,
            "intent": it.to_dict() if it.recognized else None}


async def transcribe(ctx, *, language: str, prompt: str, names: list, context: str, owner: str, lang: str = "fr",
                     use_cache: bool = True, on_code: Callable[[str], None] | None = None,
                     fix_code: str = "", fix_error: str = "", recipes=None, variant: bool = False,
                     stats: ModelStats | None = None, prev: dict[str, str] | None = None) -> dict:
    """→ {code, model, origin, seconds, first_s, valid, error, fixed, cached, attempts, uses, recipe, fallbacks,
    key, recognized, intent, coverage, request_error}. Raises BrainError when a model is needed and none answers.

    `fix_code` + `fix_error`: repair a cell that failed when run (deterministic fixer first, then the model).
    `variant`: « Autre version » — a different version on purpose (never the stored best, never the catalogue).
    `use_cache` False: kept for older callers; the best version is still returned (D39: same request, same code).
    `prev`: single-line definitions of earlier cells (name → line) the fixer may copy."""
    t0 = time.monotonic()
    card, version, verified = await asyncio.to_thread(card_for, language)
    if language == "sage" and not verified:
        syntaxcards.schedule(ctx)                     # first use of this Sage version: build its verified card
    known = {n for n, _t, _r in names or []}
    fixing = bool(fix_code)
    store = recipes if recipes is not None else _MEMORY
    it = I.analyze(prompt, known)
    key = request_key(prompt, known, it)
    base = {"model": "", "origin": "", "valid": True, "error": "", "fixed": False, "cached": False, "attempts": [],
            "recipe": "", "fallbacks": [], "key": key, "coverage": "none", "request_error": None, **_analysis(it)}

    def done(code: str, **kw) -> dict:
        out = {**base, "code": code, **kw}
        out.update(seconds=round(time.monotonic() - t0, 2), uses=uses_of(code, known) if code else [])
        out.setdefault("first_s", 0.0)
        return out

    if it.errors and not fixing:
        return done("", request_error=it.errors[0], valid=False, error=it.errors[0]["en"])
    lang_ = "sage" if language == "sage" else "python"
    cat_version = version if lang_ == "sage" else await asyncio.to_thread(codecat.tool_version, "python")
    cat_status = await asyncio.to_thread(codecat.status, lang_, cat_version) if cat_version else None
    asm = codecat.assemble(it, lang_, cat_status) if it.recognized else None
    if asm is not None:
        base["coverage"] = "full" if asm.full else ("partial" if asm.prefix else "none")
    if fixing:
        fx = await asyncio.to_thread(codefix.fix_error, fix_code, fix_error, lang_, known, prev,
                                     _sage_names(version) if lang_ == "sage" else None)
        if fx is not None:
            chk = await asyncio.to_thread(validate, fx["code"], language, known)
            if chk["ok"]:
                if on_code:
                    on_code(fx["code"])
                return done(fx["code"], model="fix", origin="fix", fixed=True)
    if not fixing and not variant:
        # 1. the best version of this request (by intent): the same code every time, « Réécrire » included
        b = await asyncio.to_thread(store.best, key, language, version, known)
        if b is not None and asm is not None and asm.full and b["origin"] == "catalogue" and b["code"] != asm.code:
            b = None                                  # the catalogue changed (new version): its new code wins
        if b is not None:
            chk = await asyncio.to_thread(validate, b["code"], language, known)
            if chk["ok"]:
                if recipes is not None and b.get("recipe"):
                    await asyncio.to_thread(recipes.hit, b["recipe"])
                if on_code:
                    on_code(b["code"])
                return done(b["code"], model=b["model"] or b["origin"] or "best", origin="best", cached=True,
                            recipe=b.get("recipe", ""))
        # 2. fully covered by the catalogue: assembled, no model
        if asm is not None and asm.full:
            code = asm.code
            await asyncio.to_thread(store.record, key, prompt, code, language, version, origin="catalogue",
                                    model="catalogue", uses=uses_of(code, known), summary=I.summary(it, "fr"))
            if on_code:
                on_code(code)
            return done(code, model="catalogue", origin="catalogue", cached=True)
        # 3. S-AB shortcut: same template, safe parameter substitution
        if recipes is not None:
            m = await asyncio.to_thread(recipes.match, prompt, language, version, known)
            if m and m["kind"] == "shortcut" and not (asm is not None and asm.prefix):
                chk = await asyncio.to_thread(validate, m["code"], language, known)
                if chk["ok"]:
                    await asyncio.to_thread(recipes.hit, m["recipe"]["id"])
                    await asyncio.to_thread(store.record, key, prompt, m["code"], language, version, origin="recipe",
                                            model="recipe", uses=uses_of(m["code"], known))
                    if on_code:
                        on_code(m["code"])
                    return done(m["code"], model="recipe", origin="recipe", cached=True, recipe=m["recipe"]["id"])
    # 4. the model, with the canonical structure fixed
    example, recipe_id = "", ""
    if recipes is not None and not fixing and not (asm is not None and asm.prefix):
        m = await asyncio.to_thread(recipes.match, prompt, language, version, known)
        if m and m["kind"] == "example":
            r = m["recipe"]
            example = f"Request: {r['request'][:500]}\n```{lang_}\n{r['code'][:3000]}\n```"
            recipe_id = r["id"]
    prefix = asm.prefix if asm is not None else ""
    avoid = [] if fixing else await asyncio.to_thread(store.failed_codes, key, language, version)
    other = ""
    if variant:
        b = await asyncio.to_thread(store.best, key, language, version, known)
        other = (b or {}).get("code", "") or (asm.code if asm is not None and asm.full else "")
    sigs = syntaxcards.sage_signatures(prompt, fix_code, version) if language == "sage" else ""
    msgs = ask_messages(lang, language, prompt, names, context, fix=fixing, code=fix_code, error=fix_error,
                        card=card, sigs=sigs, example=example, prefix=prefix, avoid=avoid, other=other)
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
    seed = SEED
    if variant:                                # each « Autre version » asks with another seed
        seed += 1 + await asyncio.to_thread(store.versions_count, key, language, version)
    temp = VARIANT_TEMPERATURE if variant else TEMPERATURE
    r, pin, raced = await _model_call(ctx, msgs, owner, on_chunk, lang_, stats, temperature=temp, seed=seed)
    code = extract_code(r.text)
    if code and first[0] is None:
        first[0] = time.monotonic() - t0
    model = getattr(r.model, "key", "") or ""
    if code:
        code = codefix.enforce_prefix(code, prefix) if prefix else code
        code = await asyncio.to_thread(canonical, code, language, known, prev, version)
    if on_code and code:
        on_code(code)
    out = done(code, model=model, origin="variant" if variant else ("fix" if fixing else "model"),
               recipe=recipe_id, fallbacks=list(getattr(r, "fallbacks", None) or []), first_s=round(first[0] or 0, 2),
               pinned=pin, raced=raced)
    if code:
        chk = await asyncio.to_thread(validate, code, language, known)
        tries = 0
        while not chk["ok"] and tries < VALIDATE_FIXES:
            # deterministic first (a missing import / load / definition), then the model with the exact error
            tries += 1
            out["attempts"].append({"code": code, "error": chk["error"][:500]})
            fx = await asyncio.to_thread(codefix.fix_error, code,
                                         "NameError: name '%s' is not defined" % (chk.get("unknown") or ["?"])[0],
                                         lang_, known, prev, _sage_names(version) if lang_ == "sage" else None) \
                if chk.get("unknown") else None
            if fx is not None:
                code = fx["code"]
            else:
                sigs2 = syntaxcards.sage_signatures(prompt, code, version) if language == "sage" else ""
                msgs2 = ask_messages(lang, language, prompt, names, "", fix=True, code=code,
                                     error=f"{chk['error']}\n(found before running: the code does not compile)",
                                     card=card, sigs=sigs2, prefix=prefix)
                try:
                    r2, _p, _r = await _model_call(ctx, msgs2, owner, None, lang_, stats, temperature=TEMPERATURE,
                                                   seed=SEED)
                    code2 = extract_code(r2.text)
                except Exception:  # noqa: BLE001 (keep the last proposal)
                    break
                if not code2:
                    break
                code2 = codefix.enforce_prefix(code2, prefix) if prefix else code2
                code = await asyncio.to_thread(canonical, code2, language, known, prev, version)
                model = getattr(r2.model, "key", "") or model
            chk = await asyncio.to_thread(validate, code, language, known)
            if on_code:
                on_code(code)
        out.update(code=code, model=model, fixed=tries > 0 and chk["ok"], valid=chk["ok"],
                   error="" if chk["ok"] else chk["error"], uses=uses_of(code, known))
        if stats is not None:
            await asyncio.to_thread(stats.generated, lang_, model, chk["ok"])
    if code and out["valid"] and not fixing:
        rec = await asyncio.to_thread(store.record, key, prompt, code, language, version,
                                      origin="variant" if variant else "model", model=model, uses=out["uses"],
                                      summary=I.summary(it, "fr") if it.recognized else "")
        out["best"] = bool(rec.get("best"))
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
