"""Learned recipes of the Calcul screen (session S-AB, DECISIONS D35): every request whose model-written code RAN
successfully on this host is kept as a recipe — normalised request, working code, tool version, the names of earlier
cells it relied on. A later similar request gets it:

- **shortcut** (no model call): same request once its parameters (numbers, formulas, intervals, fields like F_16)
  are abstracted, every old parameter found verbatim in the code, the names it relied on defined again → the code
  with the new parameters, checked by the installed Sage's preparser before it is shown;
- otherwise, when close enough (word overlap), the recipe goes to the model as a proven example.

Tied to the tool version: on a Sage update every recipe is re-checked (preparser + names of the new version) and
dropped when it no longer compiles. Local only: `<config>/research/recipes.json` (0600), never sent anywhere but to
the model as an example; the user lists and deletes them (« Recettes apprises »)."""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
import unicodedata
from pathlib import Path

from .. import config

MAX_RECIPES = 300
EXAMPLE_MIN = 0.5            # word overlap (Jaccard) for « give it to the model as an example »
_PARAM = re.compile(r"\[[^\]]{1,40}\]|\b[A-Za-z]{1,3}_\{?\d+\}?|[\w.]*\d[\w.^+\-*/()]*|\b[a-z]\^\d+[\w^+\-*/]*")
_WORD = re.compile(r"[a-z]{2,}")
STOP = {"le", "la", "les", "de", "des", "du", "un", "une", "et", "sur", "pour", "dans", "avec", "en", "au", "aux",
        "the", "of", "and", "on", "for", "in", "with", "to", "a", "an", "its", "son", "sa", "ses"}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("²", "^2").replace("³", "^3").replace("π", "pi"))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()


def params_of(request: str) -> list[str]:
    """The concrete values of a request: numbers, small formulas, intervals, finite fields (F_16)."""
    return [m.group(0) for m in _PARAM.finditer(_fold(request)) if m.group(0)]


def template(request: str) -> str:
    """The request with its parameters abstracted: « racines dans F_16 de x^5+x^3+x+1 » → « racines dans # de # »."""
    t = _PARAM.sub("#", _fold(request))
    t = re.sub(r"[^\w#]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def words(request: str) -> set[str]:
    return {w for w in _WORD.findall(_PARAM.sub(" ", _fold(request))) if w not in STOP}


def _variants(p: str) -> list[str]:
    """How a request's parameter may appear in code: as typed, with `**` for `^`, F_16 → GF(16)."""
    out = [p, p.replace("^", "**")]
    m = re.fullmatch(r"(?:f|gf|fq)_\{?(\d+)\}?", p)
    if m:
        out += [f"GF({m.group(1)}", f"GF({m.group(1)},"]
    return out


def _spots(code: str, v: str) -> list[int]:
    """Positions of `v` in `code` as a whole token (not inside a longer number or name)."""
    return [m.start() for m in re.finditer(r"(?<![\w.])" + re.escape(v) + (r"(?![\w.])" if v[-1:].isalnum() else ""),
                                           code)]


class RecipeStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _load(self) -> list[dict]:
        data, _bad = config.read_json(self.path)
        items = (data or {}).get("recipes") if isinstance(data, dict) else None
        return [r for r in items or [] if isinstance(r, dict) and r.get("code")]

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        config.atomic_write_text(self.path, json.dumps({"recipes": items[-MAX_RECIPES:]}, ensure_ascii=False))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def list(self) -> list[dict]:
        with self._lock:
            return sorted(self._load(), key=lambda r: -r.get("t", 0))

    def delete(self, rid: str) -> bool:
        with self._lock:
            items = self._load()
            keep = [r for r in items if r.get("id") != rid]
            if len(keep) == len(items):
                return False
            self._save(keep)
            return True

    def add(self, request: str, code: str, language: str, version: str, uses: list[str] | None = None) -> dict:
        """A request whose code ran successfully (the corrected code after an automatic fix)."""
        request, code = request.strip()[:4000], code.strip()[:20000]
        with self._lock:
            items = self._load()
            tpl = template(request)
            old = next((r for r in items if r["template"] == tpl and r["language"] == language
                        and r.get("params") == params_of(request)), None)
            if old is not None:
                old.update(code=code, version=version, uses=sorted(set(uses or [])), t=time.time(),
                           request=request)
                items.remove(old)
                items.append(old)
                self._save(items)
                return old
            r = {"id": secrets.token_hex(5), "request": request, "template": tpl, "params": params_of(request),
                 "code": code, "language": language, "version": version, "uses": sorted(set(uses or [])),
                 "t": time.time(), "hits": 0}
            items.append(r)
            self._save(items)
            return r

    def match(self, request: str, language: str, version: str, known: set[str]) -> dict | None:
        """→ {kind: "shortcut", code, recipe} | {kind: "example", recipe} | None."""
        with self._lock:
            items = [r for r in self._load() if r["language"] == language and r.get("version") == version]
        if not items:
            return None
        tpl, ps, ws = template(request), params_of(request), words(request)
        for r in reversed(items):
            if r["template"] != tpl or len(r.get("params") or []) != len(ps):
                continue
            if not set(r.get("uses") or []) <= known:
                continue                       # it relied on earlier cells that are not here
            code = r["code"]
            ok = True
            for old, new in zip(r["params"], ps):
                if old == new:
                    continue
                hit = next((v for v in _variants(old) if len(_spots(code, v)) == 1), None)
                if hit is None:            # absent, or ambiguous (« 5 » appears twice): not a safe substitution
                    ok = False
                    break
                rep = _variants(new)[_variants(old).index(hit)]
                a = _spots(code, hit)[0]
                code = code[:a] + rep + code[a + len(hit):]
            if ok:
                return {"kind": "shortcut", "code": code, "recipe": r}
        best, score = None, 0.0
        for r in items:
            rw = words(r["request"])
            if not rw or not ws:
                continue
            j = len(rw & ws) / len(rw | ws)
            if j > score:
                best, score = r, j
        if best is not None and score >= EXAMPLE_MIN:
            return {"kind": "example", "recipe": best, "score": round(score, 2)}
        return None

    def hit(self, rid: str) -> None:
        with self._lock:
            items = self._load()
            for r in items:
                if r.get("id") == rid:
                    r["hits"] = int(r.get("hits", 0)) + 1
                    self._save(items)
                    return

    def revalidate(self, language: str, version: str, check) -> dict:
        """After a version change: re-check each recipe of another version with `check(recipe) -> bool` (the new
        version's preparser + names); keep (and re-tag) those that pass, drop the others."""
        with self._lock:
            items = self._load()
            kept, dropped = [], 0
            for r in items:
                if r["language"] == language and r.get("version") != version:
                    if check(r):
                        r["version"] = version
                    else:
                        dropped += 1
                        continue
                kept.append(r)
            if dropped or any(r["language"] == language for r in items):
                self._save(kept)
            return {"kept": len(kept), "dropped": dropped}
