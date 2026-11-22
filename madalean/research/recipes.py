"""The best code of each Calcul request, kept by INTENT (sessions S-AB, D35, and S-AG, D39).

A recipe is one request intent (`intent.py`: « F_125 », « F_{5^3} », « GF(125) » share one key) in one tool
(sage | python) and tool version, with every code VERSION written for it and what happened to it:

    {id, key, request, requests: [texts seen], summary, language, version, uses, t, hits, template, params,
     versions: [{vid, code, origin: catalogue|model|variant|fix|recipe|user, model, t, runs_ok, runs_fail,
                 approved, seconds, error}], best: vid}

« Retenir le meilleur »:
- the first valid version becomes the best; a later request with the same key gets the best version **as is** (no
  model call), and « Réécrire » too: the user asked for one syntax per request;
- ranking: ran OK > approved by the user > faster run (≥ 30 % faster: no flapping on timing noise) > older; a
  version that only ever failed is never preferred again (and is shown to the model as « do not repeat »);
- a variant (« Autre version ») is stored as a version; it replaces the best only when it ranks strictly higher.

Older shortcuts (S-AB) stay: an exact template match with safe parameter substitution answers without a model; a
close request (word overlap) is a proven example for the model. Tied to the tool version: after an update every
recipe is re-checked (preparser + names) and dropped when it fails. Local only: `<config>/research/recipes.json`
(0600). Schema 1 files (S-AB) are migrated on first read (keys computed from the stored request, a backup kept as
`recipes.v1.json`)."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
import unicodedata
from pathlib import Path

from .. import config
from . import intent as I

SCHEMA = 2
MAX_RECIPES = 300
MAX_VERSIONS = 8
EXAMPLE_MIN = 0.5            # word overlap (Jaccard) for « give it to the model as an example »
FASTER = 0.7                 # a version must run ≥ 30 % faster to replace a best that also ran OK
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


def request_key(request: str, known: set[str] | None = None, it: I.Intent | None = None) -> str:
    """The key under which a request's best code is kept: its intent when recognized, else its folded words."""
    it = it if it is not None else I.analyze(request, known)
    if it.recognized:
        return "i:" + it.key()
    norm = re.sub(r"\s+", " ", _fold(request)).strip(" .?!")
    return "t:" + hashlib.sha256(norm.encode()).hexdigest()[:20]


def norm_code(code: str) -> str:
    """Two codes that differ only by trailing spaces / blank lines are the same version."""
    return "\n".join(l.rstrip() for l in (code or "").strip().split("\n") if l.strip())


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


def _failed(v: dict) -> bool:
    return bool(v.get("runs_fail")) and not v.get("runs_ok")


def _rank(v: dict) -> tuple:
    return (1 if v.get("runs_ok") else 0, 1 if v.get("approved") else 0)


def better(new: dict, old: dict | None) -> bool:
    """Does `new` replace the best `old`? Strictly higher rank, or both ran OK and `new` is clearly faster."""
    if _failed(new):
        return False
    if old is None or _failed(old):
        return True
    if _rank(new) != _rank(old):
        return _rank(new) > _rank(old)
    if new.get("runs_ok") and old.get("runs_ok") and new.get("seconds") and old.get("seconds"):
        return new["seconds"] < FASTER * old["seconds"]
    return False


class RecipeStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    # ------------------------------------------------------------ storage + migration
    def _load(self) -> list[dict]:
        data, _bad = config.read_json(self.path)
        items = (data or {}).get("recipes") if isinstance(data, dict) else None
        items = [r for r in items or [] if isinstance(r, dict) and (r.get("code") or r.get("versions"))]
        if isinstance(data, dict) and data.get("schema") != SCHEMA and items:
            items = migrate(items)
            try:
                bak = self.path.with_name(self.path.stem + ".v1.json")
                if not bak.exists():
                    config.atomic_write_text(bak, json.dumps(data, ensure_ascii=False))
                    bak.chmod(0o600)
            except OSError:
                pass
            self._save(items)
        return items

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        config.atomic_write_text(self.path, json.dumps({"schema": SCHEMA, "recipes": items[-MAX_RECIPES:]},
                                                       ensure_ascii=False))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def best_version(r: dict) -> dict | None:
        vs = r.get("versions") or []
        v = next((x for x in vs if x.get("vid") == r.get("best")), None)
        return v if v is not None and not _failed(v) else None

    @staticmethod
    def _view(r: dict) -> dict:
        b = RecipeStore.best_version(r)
        return {**r, "code": b["code"] if b else ""}

    def list(self) -> list[dict]:
        with self._lock:
            return sorted((self._view(r) for r in self._load()), key=lambda r: -r.get("t", 0))

    def delete(self, rid: str) -> bool:
        with self._lock:
            items = self._load()
            keep = [r for r in items if r.get("id") != rid]
            if len(keep) == len(items):
                return False
            self._save(keep)
            return True

    # ------------------------------------------------------------ intent-keyed best versions (S-AG)
    def _find(self, items: list[dict], key: str, language: str, version: str) -> dict | None:
        return next((r for r in items if r.get("key") == key and r["language"] == language
                     and r.get("version") == version), None)

    def best(self, key: str, language: str, version: str, known: set[str] | None = None) -> dict | None:
        """→ {code, recipe, vid, origin, model} — the best version of this request, or None."""
        with self._lock:
            r = self._find(self._load(), key, language, version)
        if r is None:
            return None
        v = self.best_version(r)
        if v is None:
            return None
        if not set(r.get("uses") or []) <= set(known or ()):
            return None                       # it relied on earlier cells that are not here
        return {"code": v["code"], "recipe": r["id"], "vid": v["vid"], "origin": v.get("origin", ""),
                "model": v.get("model", "")}

    def failed_codes(self, key: str, language: str, version: str) -> list[dict]:
        """Versions that only ever failed (given to the model: « do not write these again »)."""
        with self._lock:
            r = self._find(self._load(), key, language, version)
        return [{"code": v["code"], "error": v.get("error", "")} for v in (r or {}).get("versions") or []
                if _failed(v)][-3:]

    def versions_count(self, key: str, language: str, version: str) -> int:
        with self._lock:
            r = self._find(self._load(), key, language, version)
        return len((r or {}).get("versions") or [])

    def record(self, key: str, request: str, code: str, language: str, version: str, *, origin: str = "model",
               model: str = "", uses: list[str] | None = None, summary: str = "") -> dict:
        """A version written for this request (catalogue, model, variant…). The first valid one becomes the best.
        → {recipe, vid, best: bool}."""
        code = (code or "").strip()[:20000]
        request = (request or "").strip()[:4000]
        with self._lock:
            items = self._load()
            r = self._find(items, key, language, version)
            if r is None:
                r = {"id": secrets.token_hex(5), "key": key, "request": request, "requests": [request],
                     "summary": summary, "template": template(request), "params": params_of(request),
                     "language": language, "version": version, "uses": sorted(set(uses or [])), "t": time.time(),
                     "hits": 0, "versions": [], "best": ""}
            else:
                items.remove(r)
                if request and request not in r.setdefault("requests", []):
                    r["requests"] = (r["requests"] + [request])[-5:]
            items.append(r)
            nc = norm_code(code)
            v = next((x for x in r["versions"] if norm_code(x["code"]) == nc), None)
            if v is None:
                v = {"vid": secrets.token_hex(4), "code": code, "origin": origin, "model": model, "t": time.time(),
                     "runs_ok": 0, "runs_fail": 0, "approved": 0, "seconds": None, "error": ""}
                r["versions"].append(v)
                if len(r["versions"]) > MAX_VERSIONS:
                    keep_ids = {r.get("best")}
                    drop = next((x for x in r["versions"] if x["vid"] not in keep_ids), None)
                    if drop is not None:
                        r["versions"].remove(drop)
            cur = self.best_version(r)
            if cur is None and not _failed(v):
                r["best"] = v["vid"]
            if summary:
                r["summary"] = summary
            if uses is not None and r.get("best") == v["vid"]:
                r["uses"] = sorted(set(uses))
            r["t"] = time.time()
            self._save(items)
            return {"recipe": r["id"], "vid": v["vid"], "best": r.get("best") == v["vid"]}

    def outcome(self, key: str, code: str, language: str, version: str, *, ok: bool, seconds: float | None = None,
                error: str = "", request: str = "", uses: list[str] | None = None, model: str = "",
                origin: str = "model") -> dict | None:
        """A run of `code` for this request: ran OK / failed. Updates the ranking (and records the version when the
        user's edit or an automatic fix produced a new code)."""
        if ok:
            self.record(key, request, code, language, version, origin=origin, model=model, uses=uses)
        nc = norm_code(code)
        with self._lock:
            items = self._load()
            r = self._find(items, key, language, version)
            if r is None:
                return None
            v = next((x for x in r["versions"] if norm_code(x["code"]) == nc), None)
            if v is None:
                return None
            if ok:
                v["runs_ok"] = int(v.get("runs_ok", 0)) + 1
                if seconds is not None:
                    v["seconds"] = round(min(seconds, v["seconds"] or seconds), 3)
                v["error"] = ""
            else:
                v["runs_fail"] = int(v.get("runs_fail", 0)) + 1
                v["error"] = (error or "")[-300:]
            self._rebest(r, v)
            self._save(items)
            return {"recipe": r["id"], "vid": v["vid"], "best": r.get("best") == v["vid"]}

    def approve(self, key: str, code: str, language: str, version: str) -> None:
        nc = norm_code(code)
        with self._lock:
            items = self._load()
            r = self._find(items, key, language, version)
            v = next((x for x in (r or {}).get("versions") or [] if norm_code(x["code"]) == nc), None)
            if v is None:
                return
            v["approved"] = int(v.get("approved", 0)) + 1
            self._rebest(r, v)
            self._save(items)

    def _rebest(self, r: dict, changed: dict) -> None:
        cur = self.best_version(r)
        if cur is None:
            cands = [x for x in r["versions"] if not _failed(x)]
            if cands:
                top = max(cands, key=lambda x: (_rank(x), -(x.get("seconds") or 1e9), -x.get("t", 0)))
                r["best"] = top["vid"]
            else:
                r["best"] = ""
            return
        if changed is not cur and better(changed, cur):
            r["best"] = changed["vid"]

    # ------------------------------------------------------------ S-AB compatibility
    def add(self, request: str, code: str, language: str, version: str, uses: list[str] | None = None) -> dict:
        """A request whose code ran successfully (the corrected code after an automatic fix)."""
        key = request_key(request, set(uses or ()))
        self.outcome(key, code, language, version, ok=True, request=request, uses=uses)
        with self._lock:
            r = self._find(self._load(), key, language, version)
        return self._view(r) if r else {}

    def match(self, request: str, language: str, version: str, known: set[str]) -> dict | None:
        """→ {kind: "shortcut", code, recipe} | {kind: "example", recipe} | None (S-AB: templates and words)."""
        with self._lock:
            items = [self._view(r) for r in self._load() if r["language"] == language and r.get("version") == version]
        items = [r for r in items if r["code"]]
        if not items:
            return None
        tpl, ps, ws = template(request), params_of(request), words(request)
        for r in reversed(items):
            if r.get("template") != tpl or len(r.get("params") or []) != len(ps):
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
        version's preparser + names, on the best code); keep (and re-tag) those that pass, drop the others."""
        with self._lock:
            items = self._load()
            kept, dropped = [], 0
            for r in items:
                if r["language"] == language and r.get("version") != version:
                    view = self._view(r)
                    if view["code"] and check(view):
                        r["version"] = version
                        r["versions"] = [v for v in r["versions"] if v["vid"] == r.get("best")]
                    else:
                        dropped += 1
                        continue
                kept.append(r)
            if dropped or any(r["language"] == language for r in items):
                self._save(kept)
            return {"kept": len(kept), "dropped": dropped}


def migrate(items: list[dict]) -> list[dict]:
    """Schema 1 (S-AB: one code per request, ran OK) → schema 2 (intent key, versions, best). Two old recipes with
    the same intent merge (the most recent code is the best; the others stay as versions)."""
    out: dict[tuple, dict] = {}
    for r in sorted(items, key=lambda r: r.get("t", 0)):
        if r.get("versions"):
            out[(r.get("key"), r["language"], r.get("version"))] = r
            continue
        req = r.get("request", "")
        key = request_key(req, set(r.get("uses") or ()))
        k = (key, r.get("language", "sage"), r.get("version", ""))
        v = {"vid": secrets.token_hex(4), "code": r["code"], "origin": "model", "model": "", "t": r.get("t", 0),
             "runs_ok": 1, "runs_fail": 0, "approved": 0, "seconds": None, "error": ""}
        if k in out:
            n = out[k]
            if norm_code(r["code"]) not in {norm_code(x["code"]) for x in n["versions"]}:
                n["versions"].append(v)
                n["best"] = v["vid"]
            n["requests"] = (n.get("requests", []) + [req])[-5:]
            n["hits"] = int(n.get("hits", 0)) + int(r.get("hits", 0))
            n["t"] = max(n.get("t", 0), r.get("t", 0))
            continue
        it = I.analyze(req, set(r.get("uses") or ()))
        out[k] = {"id": r.get("id") or secrets.token_hex(5), "key": key, "request": req, "requests": [req],
                  "summary": I.summary(it, "fr") if it.recognized else "", "template": r.get("template") or
                  template(req), "params": r.get("params") or params_of(req), "language": k[1], "version": k[2],
                  "uses": r.get("uses") or [], "t": r.get("t", 0), "hits": r.get("hits", 0), "versions": [v],
                  "best": v["vid"]}
    return sorted(out.values(), key=lambda r: r.get("t", 0))
