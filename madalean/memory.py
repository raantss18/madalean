"""« Mémoire qui grossit » (TODO « Stratégie 2.1 » item 9, DECISIONS D62): one portable, verifiable memory bundle.

A `.madalean-memory` file is a zip:

    manifest.json              format, schema, Madalean version, created, the Lean / Mathlib versions of each
                               workspace the library rows come from, per part {path, sha256, count, bytes},
                               the original files {path, sha256}, what was left out and why, and `integrity`
                               (SHA-256 of the canonical manifest without that field — corruption / tampering
                               evidence, NOT a signature: anybody can rebuild a consistent bundle)
    parts/library.json         Lean results: statement, proof (no header), deps, verification stamp, provenance
    parts/lessons.json         lessons (D57b) with their evidence
    parts/recipes.json         Calcul recipes (D39): the best version per intent, Sage / Python
    parts/graphs.json          problem graphs (D57) of the selected projects
    parts/digests.json         attachment digests (D56): text only; © sources left out unless asked
    files/<sha256>             original attachment files, only when the user ticked it

Nothing imported is trusted (docs/MEMORY.md §3, SECURITY.md « Memory bundles »): the archive is read with size /
count / ratio limits and a fixed name set; every hash is checked before anything is parsed; each Lean proof is
re-checked by a fresh strict Lean in a workspace with the same Lean / Mathlib versions before it enters the library
(otherwise it waits in « importées, non vérifiées » with the reason); recipes are re-validated (preparser / compile,
names of the installed Sage) and statically screened; lessons keep their evidence with neutral counters; graphs are
read-only references; text that reads like instructions to a model is refused. Import is host-only.

Also here: scheduled local backups (never uploaded) and the training-dataset export (JSONL of verified pairs only)
for a future, optional, off-by-default fine-tune (docs/MEMORY.md §6)."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
import secrets
import time
import zipfile
from pathlib import Path

from . import __version__, config, leancheck
from .logs import get

log = get("memory")

FORMAT = "madalean-memory"
SCHEMA = 1
EXT = ".madalean-memory"
PARTS = ("library", "lessons", "recipes", "graphs", "digests")
MAX_BUNDLE = 200 * 1024 * 1024
MAX_PART = 64 * 1024 * 1024
MAX_FILE = 40 * 1024 * 1024
MAX_MEMBERS = 2000
MAX_RATIO = 200
MAX_ROWS = 20000
MAX_GRAPH = 2 * 1024 * 1024
_NAME_RE = re.compile(r"^(manifest\.json|parts/(" + "|".join(PARTS) + r")\.json|files/[0-9a-f]{64})$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_'.]{0,200}$")
BACKUP_RE = re.compile(r"^madalean-memory-\d{8}-\d{6}" + re.escape(EXT) + "$")
# Sage / Python code that reaches the system: never stored from someone else's bundle (it would be served again
# without a model as « the best version » of a request)
_CODE_RISK = re.compile(r"\b(import\s+(os|sys|subprocess|socket|shutil|ctypes|requests|urllib|http|pathlib|pickle|"
                        r"multiprocessing|signal|pty|importlib)\b|from\s+(os|sys|subprocess|socket|shutil|ctypes|"
                        r"requests|urllib|http|pathlib|pickle|importlib)\b|__import__|__builtins__|__subclasses__|"
                        r"\beval\s*\(|\bexec\s*\(|\bopen\s*\(|\bcompile\s*\(|\bglobals\s*\(|\bgetattr\s*\(|"
                        r"os\.system|load_session|attach\s*\(|\bload\s*\()")


class BundleError(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind, self.detail = kind, detail


# ---------------------------------------------------------------- small helpers
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def integrity_of(manifest: dict) -> str:
    return sha256(_canon({k: v for k, v in manifest.items() if k != "integrity"}))


def clean(text, limit: int = 4000) -> str:
    from .mcp.schema import clean_text
    return clean_text(text if isinstance(text, str) else ("" if text is None else str(text)), limit)


def suspect(text: str) -> bool:
    """Text that addresses a model rather than a reader (same heuristic as the news summaries)."""
    from .news.summarize import looks_like_injection
    return looks_like_injection(text or "")


def redistributable(licence: str) -> bool:
    from .research.publish import REDISTRIBUTABLE
    return bool(REDISTRIBUTABLE.search(licence or ""))


def memory_dir(ctx) -> Path:
    return ctx.paths.config / "memory"


def _ws_info(ws) -> dict:
    from .runtime.lean import workspace_info
    info = workspace_info(ws)
    return {"lean": info.get("lean", ""), "mathlib": info.get("mathlib", "")}


def _lessons_store(ctx):
    from .research.lessons import Lessons, store_of
    return store_of(ctx) or Lessons(ctx.paths.config / "research" / "lessons.json")


def _recipes_store(ctx):
    wb = getattr(ctx, "workbench", None)
    if wb is not None and getattr(wb, "recipes", None) is not None:
        return wb.recipes
    from .research.recipes import RecipeStore
    return RecipeStore(ctx.paths.config / "research" / "recipes.json")


def _sources(ctx):
    from .research.sources import library
    return library(ctx)


def _shelves(ctx, projects: list[str] | None) -> list[tuple[str, str]]:
    """(shelf id, project title) of the selected projects (+ the global shelf when no selection)."""
    from .research.sources import GLOBAL
    out = [(p.id, p.title) for p in ctx.projects.list() if projects is None or p.id in projects]
    if projects is None or GLOBAL in projects:
        out.append((GLOBAL, ""))
    return out


# ---------------------------------------------------------------- export
def default_options() -> dict:
    return {"parts": list(PARTS), "projects": None, "include_copyrighted": False, "include_files": False}


def normalize_options(data: dict | None) -> dict:
    o = default_options()
    data = data if isinstance(data, dict) else {}
    if isinstance(data.get("parts"), list):
        o["parts"] = [p for p in PARTS if p in data["parts"]]
    if isinstance(data.get("projects"), list):
        o["projects"] = [str(p)[:80] for p in data["projects"]][:500]
    o["include_copyrighted"] = data.get("include_copyrighted") is True
    o["include_files"] = data.get("include_files") is True
    return o


def collect(ctx, opts: dict) -> tuple[dict[str, list], dict[str, bytes], list[dict], dict]:
    """→ (parts {name: rows}, files {sha: bytes}, excluded [{what, why}], workspaces {key: {lean, mathlib}})."""
    parts: dict[str, list] = {}
    files: dict[str, bytes] = {}
    excluded: list[dict] = []
    wss: dict[str, dict] = {}
    projects = opts.get("projects")
    if "library" in opts["parts"]:
        parts["library"] = _collect_library(ctx, projects, wss)
    if "lessons" in opts["parts"]:
        parts["lessons"] = _lessons_store(ctx).list()
    if "recipes" in opts["parts"]:
        parts["recipes"] = _collect_recipes(ctx)
    if "graphs" in opts["parts"]:
        parts["graphs"] = _collect_graphs(ctx, projects)
    if "digests" in opts["parts"]:
        parts["digests"] = _collect_digests(ctx, projects, opts, files, excluded)
    return parts, files, excluded, wss


def _collect_library(ctx, projects: list[str] | None, wss: dict) -> list[dict]:
    from .dossiers import closure
    lib = ctx.library
    chosen = []
    for e in lib.entries:
        d = ctx.repo.get(e.dossier) if e.dossier else None
        pid = (d.project_id if d is not None else "") or "global"     # « Hors projet » = the global shelf's id
        if projects is not None and pid not in projects:
            continue
        chosen.append(e)
    rows = []
    for e in closure(lib, chosen):                   # a result travels with what it uses
        d = ctx.repo.get(e.dossier) if e.dossier else None
        pv = d.proofs[d.cur_proof] if d is not None and 0 <= d.cur_proof < len(d.proofs) else None
        meta = (pv.meta if pv is not None else {}) or {}
        if e.workspace not in wss:
            wss[e.workspace] = _ws_info(ctx.workspace(e.workspace))
        origin = dict(getattr(e, "origin", {}) or {})
        nl = (d.understood_display or d.understood or d.problem) if d is not None else origin.get("nl", "")
        rows.append({"name": e.name, "title": e.title, "statement": e.statement, "code": e.code,
                     "workspace": e.workspace, "deps": list(e.deps), "t": e.t, "nl": (nl or "")[:4000],
                     "stamp": {"workspace": e.workspace, "lean": meta.get("lean") or wss[e.workspace]["lean"],
                               "mathlib": meta.get("mathlib") or wss[e.workspace]["mathlib"],
                               "axioms": meta.get("axioms"), "checked": meta.get("checked") or e.t,
                               "verdict": "strict"},
                     "provenance": {"model": (pv.model if pv is not None else "") or origin.get("model", ""),
                                    "by_user": bool(pv is not None and pv.source == "user"),
                                    "imported": bool(origin.get("bundle"))}})
    return rows


def _collect_recipes(ctx) -> list[dict]:
    rows = []
    for r in _recipes_store(ctx).list():
        if not r.get("code"):
            continue
        best = next((v for v in r.get("versions") or [] if v.get("vid") == r.get("best")), {})
        rows.append({"request": r.get("request", ""), "requests": list(r.get("requests") or [])[:5],
                     "summary": r.get("summary", ""), "language": r.get("language", ""),
                     "version": r.get("version", ""), "uses": list(r.get("uses") or []), "code": r["code"],
                     "runs_ok": int(best.get("runs_ok") or 0), "approved": int(best.get("approved") or 0),
                     "origin": best.get("origin", "")})
    return rows


def _plans_dir(ctx) -> Path:
    return ctx.paths.config / "research" / "plans"


def _collect_graphs(ctx, projects: list[str] | None) -> list[dict]:
    titles = {p.id: p.title for p in ctx.projects.list()}
    rows = []
    for d in ctx.repo.list():
        if projects is not None and d.project_id not in projects:
            continue
        try:
            data = json.loads((_plans_dir(ctx) / f"{d.id}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        g = data.get("graph") if isinstance(data, dict) else None
        if isinstance(g, dict) and g.get("nodes"):
            rows.append({"dossier_id": d.id, "project_id": d.project_id, "project": titles.get(d.project_id, ""),
                         "title": d.title, "graph": g})
    return rows


def _collect_digests(ctx, projects, opts, files: dict, excluded: list) -> list[dict]:
    lib = _sources(ctx)
    rows = []
    for shelf, ptitle in _shelves(ctx, projects):
        try:
            sh = lib.shelf(shelf)
        except Exception:  # noqa: BLE001
            continue
        for p in sorted((sh.root / "digests").glob("*.json"))[:500]:
            try:
                dig = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(dig, dict) or not dig.get("sha"):
                continue
            src = sh.get(str(dig.get("source_id") or "")) or {}
            lic = str(src.get("license") or (src.get("csl") or {}).get("license") or "")
            name = dig.get("name") or src.get("key") or dig["sha"][:12]
            if not redistributable(lic) and not opts.get("include_copyrighted"):
                excluded.append({"what": f"digest:{name}", "why": "license_not_redistributable", "license": lic})
                continue
            row = {"shelf": shelf, "project": ptitle, "license": lic, "digest": dig, "files": []}
            if opts.get("include_files"):
                for f in src.get("files") or []:
                    try:
                        data = sh.blob(f["sha256"]).read_bytes()
                    except Exception:  # noqa: BLE001
                        continue
                    if len(data) <= MAX_FILE:
                        files[f["sha256"]] = data
                        row["files"].append({"sha256": f["sha256"], "name": str(f.get("name") or "")[:200]})
            rows.append(row)
    return rows


def build_bundle(parts: dict[str, list], files: dict[str, bytes], excluded: list[dict], workspaces: dict,
                 created: float | None = None) -> bytes:
    created = created or time.time()
    man = {"format": FORMAT, "schema": SCHEMA, "madalean": __version__,
           "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created)), "workspaces": workspaces,
           "parts": {}, "files": [], "excluded": excluded[:2000]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in PARTS:
            if name not in parts:
                continue
            raw = json.dumps(parts[name], ensure_ascii=False, indent=0).encode("utf-8")
            path = f"parts/{name}.json"
            z.writestr(path, raw)
            man["parts"][name] = {"path": path, "sha256": sha256(raw), "count": len(parts[name]), "bytes": len(raw)}
        for sha, data in sorted(files.items()):
            z.writestr(f"files/{sha}", data)
            man["files"].append({"path": f"files/{sha}", "sha256": sha256(data), "bytes": len(data)})
        man["integrity"] = integrity_of(man)
        z.writestr("manifest.json", json.dumps(man, ensure_ascii=False, indent=1))
    return buf.getvalue()


def export_bundle(ctx, opts: dict | None = None) -> tuple[bytes, dict]:
    o = normalize_options(opts)
    parts, files, excluded, wss = collect(ctx, o)
    data = build_bundle(parts, files, excluded, wss)
    return data, {"counts": {k: len(v) for k, v in parts.items()}, "files": len(files), "excluded": excluded,
                  "bytes": len(data)}


# ---------------------------------------------------------------- reading (untrusted)
class Bundle:
    def __init__(self, manifest: dict, parts: dict[str, list], files: dict[str, bytes]):
        self.manifest, self.parts, self.files = manifest, parts, files


def read_bundle(data: bytes) -> Bundle:
    """Parse and check a bundle. Raises BundleError(kind) — nothing is parsed before its hash matched."""
    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_BUNDLE:
        raise BundleError("too_large")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        raise BundleError("not_a_bundle", str(e)[:200])
    if len(infos) > MAX_MEMBERS:
        raise BundleError("too_many_files")
    names, total = set(), 0
    for i in infos:
        if i.filename in names or not _NAME_RE.match(i.filename) or i.is_dir():
            raise BundleError("unexpected_member", i.filename[:120])
        names.add(i.filename)
        if i.file_size > (MAX_FILE if i.filename.startswith("files/") else MAX_PART):
            raise BundleError("too_large", i.filename[:120])
        if i.compress_size and i.file_size / max(1, i.compress_size) > MAX_RATIO:
            raise BundleError("ratio", i.filename[:120])
        total += i.file_size
    if total > MAX_BUNDLE:
        raise BundleError("too_large")

    def read(name: str, limit: int) -> bytes:
        with z.open(name) as f:
            out = f.read(limit + 1)
        if len(out) > limit:
            raise BundleError("too_large", name)
        return out

    if "manifest.json" not in names:
        raise BundleError("no_manifest")
    try:
        man = json.loads(read("manifest.json", 4 * 1024 * 1024).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise BundleError("bad_manifest", str(e)[:200])
    if not isinstance(man, dict) or man.get("format") != FORMAT:
        raise BundleError("not_a_bundle")
    if not isinstance(man.get("schema"), int) or man["schema"] > SCHEMA:
        raise BundleError("newer_schema", str(man.get("schema")))
    if man.get("integrity") != integrity_of(man):
        raise BundleError("manifest_tampered")
    parts: dict[str, list] = {}
    declared = man.get("parts") if isinstance(man.get("parts"), dict) else {}
    for name, info in declared.items():
        if name not in PARTS or not isinstance(info, dict) or info.get("path") != f"parts/{name}.json":
            raise BundleError("bad_manifest", f"part {str(name)[:40]}")
        if info["path"] not in names:
            raise BundleError("missing_part", name)
        raw = read(info["path"], MAX_PART)
        if sha256(raw) != info.get("sha256"):
            raise BundleError("hash_mismatch", info["path"])
        try:
            rows = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise BundleError("bad_part", f"{name}: {str(e)[:120]}")
        if not isinstance(rows, list) or len(rows) > MAX_ROWS or len(rows) != info.get("count"):
            raise BundleError("bad_part", name)
        parts[name] = [r for r in rows if isinstance(r, dict)]
    files: dict[str, bytes] = {}
    for f in man.get("files") or []:
        if not isinstance(f, dict) or f.get("path") not in names:
            raise BundleError("missing_file", str((f or {}).get("path"))[:120] if isinstance(f, dict) else "")
        raw = read(f["path"], MAX_FILE)
        sha = f["path"].split("/", 1)[1]
        if sha256(raw) != sha or f.get("sha256") != sha:
            raise BundleError("hash_mismatch", f["path"])
        files[sha] = raw
    undeclared = {n for n in names if n != "manifest.json"} - {i["path"] for i in declared.values()} - \
        {f"files/{s}" for s in files}
    if undeclared:
        raise BundleError("unexpected_member", sorted(undeclared)[0][:120])
    return Bundle(man, parts, files)


# ---------------------------------------------------------------- workspaces
def match_workspace(ctx, src: dict, key: str):
    """The local workspace with the same Lean and Mathlib versions as the exporting one (any key), else None."""
    lean, mathlib = str((src or {}).get("lean") or ""), str((src or {}).get("mathlib") or "")
    cands = [w for w in ctx.workspaces if not getattr(w, "problems", None)]
    same_key = next((w for w in cands if w.key == key), None)
    for w in ([same_key] if same_key else []) + [w for w in cands if w is not same_key]:
        info = _ws_info(w)
        if lean and info["lean"] == lean and (mathlib and info["mathlib"] == mathlib):
            return w
    if same_key is not None and lean and _ws_info(same_key)["lean"] == lean and not mathlib:
        return same_key
    return None


# ---------------------------------------------------------------- unverified (pending) library entries
class Pending:
    """Imported library results that Lean has not accepted here (yet), with the reason. Never used by a prover."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def list(self) -> list[dict]:
        data, _bad = config.read_json(self.path)
        rows = data.get("entries") if isinstance(data, dict) else None
        return [r for r in rows or [] if isinstance(r, dict) and r.get("name")]

    def save(self, rows: list[dict]) -> None:
        config.atomic_write_text(self.path, json.dumps({"entries": rows[-2000:]}, ensure_ascii=False, indent=1))

    def put(self, row: dict, reason: str, detail: str = "") -> None:
        rows = [r for r in self.list() if not (r["name"] == row["name"] and r.get("workspace") == row.get("workspace"))]
        rows.append({**row, "reason": reason, "detail": detail[:600], "t_import": time.time()})
        self.save(rows)

    def drop(self, name: str, workspace: str | None = None) -> bool:
        rows = self.list()
        keep = [r for r in rows if not (r["name"] == name and (workspace is None or r.get("workspace") == workspace))]
        if len(keep) != len(rows):
            self.save(keep)
            return True
        return False


def pending_of(ctx) -> Pending:
    return Pending(memory_dir(ctx) / "unverified.json")


# ---------------------------------------------------------------- import plan (dry run)
def _lib_row(r: dict) -> dict | None:
    """A library row reduced to plain, bounded fields; None when malformed."""
    name, code = str(r.get("name") or ""), r.get("code")
    if not _IDENT.match(name) or not isinstance(code, str) or not code.strip() or len(code) > 200000:
        return None
    deps = [str(x) for x in r.get("deps") or [] if isinstance(x, str) and _IDENT.match(x)][:50]
    stamp = r.get("stamp") if isinstance(r.get("stamp"), dict) else {}
    prov = r.get("provenance") if isinstance(r.get("provenance"), dict) else {}
    return {"name": name, "title": clean(r.get("title"), 300) or name, "code": code,
            "statement": clean(r.get("statement"), 4000), "workspace": clean(r.get("workspace"), 80),
            "deps": deps, "nl": clean(r.get("nl"), 4000),
            "stamp": {k: clean(stamp.get(k), 200) for k in ("workspace", "lean", "mathlib")},
            "model": clean(prov.get("model"), 120)}


def _statement_key(sig: str) -> str:
    from .research.proofgraph import statement_key
    try:
        return statement_key(sig or "")
    except Exception:  # noqa: BLE001
        return ""


def _local_graph_keys(ctx) -> set[str]:
    keys: set[str] = set()
    for p in sorted(_plans_dir(ctx).glob("*.json"))[:5000]:
        try:
            g = (json.loads(p.read_text(encoding="utf-8")) or {}).get("graph") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for n in (g.get("nodes") or {}).values():
            if isinstance(n, dict) and n.get("key"):
                keys.add(n["key"])
    return keys


def plan_import(ctx, b: Bundle) -> dict:
    """What an import would do, item by item: add / update / skip / unverified, with the reason. No side effect."""
    man = b.manifest
    wss = man.get("workspaces") if isinstance(man.get("workspaces"), dict) else {}
    out: dict = {"bundle": {"madalean": clean(man.get("madalean"), 40), "created": clean(man.get("created"), 40),
                            "schema": man.get("schema"), "workspaces": {clean(k, 80): {
                                "lean": clean((v or {}).get("lean"), 80), "mathlib": clean((v or {}).get("mathlib"), 120)}
                                for k, v in list(wss.items())[:20] if isinstance(v, dict)},
                            "excluded": len(man.get("excluded") or [])},
                 "items": {}, "summary": {}}
    # library
    items = []
    local_keys = {(e.workspace, _statement_key(e.statement)) for e in ctx.library.entries}
    local_names = {e.name: e for e in ctx.library.entries}
    for raw in b.parts.get("library", []):
        r = _lib_row(raw)
        if r is None:
            items.append({"name": str(raw.get("name"))[:80], "action": "skip", "reason": "bad_entry"})
            continue
        ws = match_workspace(ctx, wss.get(r["workspace"]) or r["stamp"], r["workspace"])
        it = {"name": r["name"], "title": r["title"], "workspace": ws.key if ws else r["workspace"]}
        if suspect(r["title"] + "\n" + r["nl"] + "\n" + r["code"]):
            it.update(action="skip", reason="suspect_text")
        elif ws is None:
            it.update(action="unverified", reason="no_matching_workspace")
        elif _statement_key(r["statement"]) and (ws.key, _statement_key(r["statement"])) in local_keys:
            it.update(action="skip", reason="duplicate")
        elif r["name"] in local_names:
            it.update(action="skip", reason="name_taken")
        else:
            it.update(action="verify", reason="lean_check")
        items.append(it)
    out["items"]["library"] = items
    # lessons
    store = _lessons_store(ctx)
    items = []
    for raw in b.parts.get("lessons", []):
        x, why = _lesson_row(raw)
        lid = (x or {}).get("id") or str(raw.get("id"))[:40]
        if x is None:
            items.append({"id": lid, "action": "skip", "reason": why})
        elif lid in store.items:
            items.append({"id": lid, "kind": x["kind"], "action": "skip", "reason": "duplicate"})
        else:
            items.append({"id": lid, "kind": x["kind"], "action": "add", "reason": "neutral_counters"})
    out["items"]["lessons"] = items
    # recipes
    items = []
    for raw in b.parts.get("recipes", []):
        r, why = _recipe_row(raw)
        name = clean((r or raw).get("request"), 120)
        if r is None:
            items.append({"request": name, "action": "skip", "reason": why})
        else:
            items.append({"request": name, "language": r["language"], "action": "validate",
                          "reason": "preparse_and_names" if r["language"] == "sage" else "compile"})
    out["items"]["recipes"] = items
    # graphs
    items = []
    local = _local_graph_keys(ctx) if b.parts.get("graphs") else set()
    have = _reference_hashes(ctx, "graphs")
    for raw in b.parts.get("graphs", []):
        g = raw.get("graph")
        if not isinstance(g, dict) or not isinstance(g.get("nodes"), dict) or len(_canon(g)) > MAX_GRAPH:
            items.append({"title": clean(raw.get("title"), 120), "action": "skip", "reason": "bad_graph"})
            continue
        h = sha256(_canon(g))[:24]
        keys = {n.get("key") for n in g["nodes"].values() if isinstance(n, dict) and n.get("key")}
        items.append({"title": clean(raw.get("title"), 120), "project": clean(raw.get("project"), 120),
                      "nodes": len(g["nodes"]), "same_statements": len(keys & local),
                      "action": "skip" if h in have else "reference", "reason": "duplicate" if h in have
                      else "read_only"})
    out["items"]["graphs"] = items
    # digests
    items = []
    for raw in b.parts.get("digests", []):
        dig = raw.get("digest") if isinstance(raw.get("digest"), dict) else {}
        sha = str(dig.get("sha") or "")
        it = {"name": clean(dig.get("name"), 120), "license": clean(raw.get("license"), 120)}
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            it.update(action="skip", reason="bad_digest")
        elif _digest_exists(ctx, raw.get("shelf"), sha):
            it.update(action="skip", reason="duplicate")
        else:
            it.update(action="add", reason="project" if _project_exists(ctx, raw.get("shelf")) else "reference")
        items.append(it)
    out["items"]["digests"] = items
    for k, v in out["items"].items():
        s: dict[str, int] = {}
        for it in v:
            s[it["action"]] = s.get(it["action"], 0) + 1
        out["summary"][k] = s
    return out


def _lesson_row(raw: dict) -> tuple[dict | None, str]:
    from .research.lessons import KINDS, _id
    if raw.get("kind") not in KINDS:
        return None, "bad_entry"
    x: dict = {}
    for k, v in raw.items():
        if k in ("ok", "bad", "used", "imported", "unconfirmed") or not isinstance(k, str) or len(k) > 40:
            continue
        if isinstance(v, str):
            x[k] = clean(v, 400)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            x[k] = v
        elif isinstance(v, list) and k in ("tactics", "domain"):
            x[k] = [clean(t, 80) for t in v if isinstance(t, str)][:12]
        elif isinstance(v, list) and k == "evidence":
            x[k] = [{kk: clean(vv, 120) for kk, vv in e.items() if isinstance(kk, str) and len(kk) < 30}
                    for e in v if isinstance(e, dict)][:5]
    text = " ".join(str(v) for k, v in x.items() if isinstance(v, str)) + " ".join(x.get("tactics") or [])
    if suspect(text):
        return None, "suspect_text"
    if x["kind"] == "rename" and not (_IDENT.match(str(x.get("old", ""))) and _IDENT.match(str(x.get("new", "")))):
        return None, "bad_entry"
    if x["kind"] in ("fix", "strategy") and any(not re.fullmatch(r"[A-Za-z_][\w.?!']{0,40}", t)
                                               for t in x.get("tactics") or []):
        return None, "bad_entry"
    if not re.fullmatch(r"ls-[0-9a-f]{6,40}", str(x.get("id") or "")):
        x["id"] = _id(json.dumps(x, sort_keys=True))
    return x, ""


def _recipe_row(raw: dict) -> tuple[dict | None, str]:
    lang = raw.get("language")
    code, request = raw.get("code"), raw.get("request")
    if lang not in ("sage", "python") or not isinstance(code, str) or not code.strip() or len(code) > 20000 or \
            not isinstance(request, str) or not request.strip():
        return None, "bad_entry"
    if _CODE_RISK.search(code):
        return None, "unsafe_code"
    if suspect(code + "\n" + request + "\n" + str(raw.get("summary") or "")):
        return None, "suspect_text"
    uses = [u for u in raw.get("uses") or [] if isinstance(u, str) and re.fullmatch(r"[A-Za-z_]\w{0,60}", u)][:40]
    return {"language": lang, "code": code.strip(), "request": clean(request, 4000),
            "summary": clean(raw.get("summary"), 300), "uses": uses}, ""


def _project_exists(ctx, shelf) -> bool:
    from .research.sources import GLOBAL
    return shelf == GLOBAL or (isinstance(shelf, str) and ctx.projects.get(shelf) is not None)


def _digest_exists(ctx, shelf, sha: str) -> bool:
    if (memory_dir(ctx) / "references" / "digests" / f"{sha}.json").exists():
        return True
    if not _project_exists(ctx, shelf):
        return False
    try:
        return (_sources(ctx).shelf(shelf).root / "digests" / f"{sha}.json").exists()
    except Exception:  # noqa: BLE001
        return False


def _reference_hashes(ctx, kind: str) -> set[str]:
    d = memory_dir(ctx) / "references" / kind
    return {p.stem for p in d.glob("*.json")} if d.exists() else set()


# ---------------------------------------------------------------- import (apply)
async def verify_entry(ctx, r: dict, ws, extra_deps: dict[str, str] | None = None) -> tuple[bool, str, str]:
    """A fresh strict Lean check of an imported result (its dependencies above it). → (ok, reason, detail)."""
    code = leancheck.remove_comments(r["code"]).strip()      # comments never travel into a prover prompt
    try:
        name = leancheck.theorem_name(code)
    except leancheck.StatementError:
        return False, "bad_entry", "no theorem"
    if name != r["name"]:
        return False, "statement_mismatch", f"last theorem is {name}"
    from .dossiers import main_signature
    if r["statement"] and re.sub(r"\s+", " ", r["statement"]).strip() != main_signature(code, name):
        return False, "statement_mismatch", "the statement shown is not the one proved"
    deps = []
    for dn in r["deps"]:
        e = ctx.library.get(dn)
        if e is not None and e.workspace == ws.key:
            deps.append(e.code)
        elif extra_deps and dn in extra_deps:
            deps.append(extra_deps[dn])
        else:
            return False, "missing_dependency", dn
    full = leancheck.GOEDEL_HEADER + "\n\n".join(deps + [code]) + "\n"
    res = await ctx.lean.check(leancheck.with_axiom_probe(full, name), ws,
                               min(int(getattr(ctx.settings, "compile_timeout_s", 300)), 900), name,
                               owner="memory-import")
    if res.infra_error:
        return False, "lean_unavailable", res.infra_error[:300]
    if getattr(res, "timed_out", False):
        return False, "lean_timeout", ""
    if not res.verdict.ok:
        return False, "lean_rejected", res.verdict.summary[:300]
    r["code"], r["axioms"] = code, res.verdict.axioms
    return True, "", ""


def _order(rows: list[dict]) -> list[dict]:
    by = {r["name"]: r for r in rows}
    out, seen = [], set()

    def visit(r, depth=0):
        if r["name"] in seen or depth > 30:
            return
        seen.add(r["name"])
        for d in r["deps"]:
            if d in by:
                visit(by[d], depth + 1)
        out.append(r)
    for r in rows:
        visit(r)
    return out


async def apply_import(ctx, b: Bundle, progress=None) -> dict:
    """Import what the plan allows. Library results enter the library only after a fresh strict Lean check."""
    plan = plan_import(ctx, b)
    report: dict = {"library": {"verified": [], "unverified": [], "skipped": []}, "lessons": {}, "recipes": {},
                    "graphs": {}, "digests": {}, "t": time.time()}
    stamp = {"bundle": plan["bundle"]["created"], "from": plan["bundle"]["madalean"]}
    # ---- library
    acts = {it["name"]: it for it in plan["items"].get("library", [])}
    rows = [r for r in (_lib_row(x) for x in b.parts.get("library", [])) if r is not None]
    verified_code: dict[str, str] = {}
    pend = pending_of(ctx)
    todo = _order(rows)
    for i, r in enumerate(todo):
        it = acts.get(r["name"], {})
        if progress:
            progress({"stage": "library", "done": i, "total": len(todo), "name": r["name"]})
        if it.get("action") == "skip":
            report["library"]["skipped"].append({"name": r["name"], "reason": it.get("reason")})
            continue
        if it.get("action") == "unverified":
            pend.put({**r, "origin": stamp}, it["reason"])
            report["library"]["unverified"].append({"name": r["name"], "reason": it["reason"]})
            continue
        ws = ctx.workspace(it["workspace"])
        ok, reason, detail = await verify_entry(ctx, r, ws, verified_code)
        if not ok:
            pend.put({**r, "workspace": ws.key, "origin": stamp}, reason, detail)
            report["library"]["unverified"].append({"name": r["name"], "reason": reason, "detail": detail})
            continue
        e = _add_verified(ctx, r, ws, stamp)
        if e is None:
            report["library"]["skipped"].append({"name": r["name"], "reason": "duplicate"})
        else:
            verified_code[r["name"]] = e.code
            pend.drop(r["name"])
            report["library"]["verified"].append({"name": r["name"], "workspace": ws.key})
    # ---- lessons (neutral counters: they must prove themselves here)
    store = _lessons_store(ctx)
    added = 0
    skipped: dict[str, int] = {}
    for raw in b.parts.get("lessons", []):
        x, why = _lesson_row(raw)
        if x is None or x["id"] in store.items:
            why = why or "duplicate"
            skipped[why] = skipped.get(why, 0) + 1
            continue
        x.update(ok=0, bad=0, used=0, imported=time.time(), updated=time.time(), unconfirmed=True)
        x.setdefault("created", time.time())
        x.setdefault("evidence", [])
        store.items[x["id"]] = x
        added += 1
    if added:
        store.save()
    report["lessons"] = {"added": added, "skipped": skipped}
    # ---- recipes
    report["recipes"] = await asyncio.to_thread(_import_recipes, ctx, b.parts.get("recipes", []))
    # ---- graphs: read-only references
    gp = [it for it in plan["items"].get("graphs", [])]
    ref = memory_dir(ctx) / "references" / "graphs"
    n = 0
    for raw, it in zip(b.parts.get("graphs", []), gp):
        if it["action"] != "reference":
            continue
        g = raw["graph"]
        h = sha256(_canon(g))[:24]
        config.atomic_write_text(ref / f"{h}.json", json.dumps({
            "title": clean(raw.get("title"), 300), "project": clean(raw.get("project"), 300),
            "dossier_id": clean(raw.get("dossier_id"), 80), "imported": time.time(), "bundle": stamp,
            "same_statements": it["same_statements"], "graph": g}, ensure_ascii=False))
        n += 1
    report["graphs"] = {"referenced": n, "skipped": sum(1 for it in gp if it["action"] == "skip")}
    # ---- digests
    report["digests"] = await _import_digests(ctx, b)
    if progress:
        progress({"stage": "done"})
    return report


def _add_verified(ctx, r: dict, ws, stamp: dict):
    from .dossiers import LibEntry, main_signature
    lib = ctx.library
    sig = main_signature(r["code"], r["name"])
    key = _statement_key(sig)
    for e in lib.entries:
        if e.workspace == ws.key and (e.name == r["name"] or (key and _statement_key(e.statement) == key)):
            return None
    origin = {**stamp, "checked": time.time(), "lean": _ws_info(ws)["lean"], "mathlib": _ws_info(ws)["mathlib"],
              "axioms": r.get("axioms"), "nl": r["nl"], "model": r["model"]}
    kw = {"name": r["name"], "title": r["title"] if not suspect(r["title"]) else r["name"], "statement": sig,
          "code": r["code"], "workspace": ws.key, "dossier": "", "deps": r["deps"]}
    e = LibEntry(**kw, origin=origin)
    lib.entries.append(e)
    lib.save()
    ctx.publish("library.updated", {"added": e.name})
    return e


def _import_recipes(ctx, rows: list[dict]) -> dict:
    from . import syntaxcards
    from .research import codecat
    from .research.recipes import norm_code, request_key
    store = _recipes_store(ctx)
    out: dict = {"added": 0, "skipped": {}}

    def skip(why):
        out["skipped"][why] = out["skipped"].get(why, 0) + 1
    sage_v = None
    existing = {(r.get("key"), r["language"], r.get("version")): {norm_code(v["code"]) for v in r.get("versions") or []}
                for r in store.list()}
    for raw in rows:
        r, why = _recipe_row(raw)
        if r is None:
            skip(why)
            continue
        if r["language"] == "sage":
            if sage_v is None:
                sage_v = codecat.tool_version("sage") or ""
            chk = syntaxcards.validate_sage(r["code"], set(r["uses"]), sage_v)
            if not chk.get("checked"):
                skip("sage_unavailable")
                continue
            version = sage_v
        else:
            chk = syntaxcards.validate_python(r["code"])
            version = ""
        if not chk.get("ok"):
            skip("invalid_code")
            continue
        key = request_key(r["request"], set(r["uses"]))
        if norm_code(r["code"]) in existing.get((key, r["language"], version), set()):
            skip("duplicate")
            continue
        store.record(key, r["request"], r["code"], r["language"], version, origin="import", uses=r["uses"],
                     summary=r["summary"])
        out["added"] += 1
    return out


async def _import_digests(ctx, b: Bundle) -> dict:
    from .literature.attach import save_digest
    out = {"project": 0, "reference": 0, "files": 0, "skipped": {}}

    def skip(why):
        out["skipped"][why] = out["skipped"].get(why, 0) + 1
    for raw in b.parts.get("digests", []):
        dig = raw.get("digest") if isinstance(raw.get("digest"), dict) else {}
        sha = str(dig.get("sha") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            skip("bad_digest")
            continue
        if _digest_exists(ctx, raw.get("shelf"), sha):
            skip("duplicate")
            continue
        items = []
        for itm in dig.get("items") or []:
            if not isinstance(itm, dict):
                continue
            txt = json.dumps(itm, ensure_ascii=False)
            if len(txt) > 20000 or suspect(txt):
                continue                                 # a statement that talks to the model is dropped
            items.append(itm)
        safe = {"sha": sha, "version": clean(dig.get("version"), 40), "state": "imported",
                "name": clean(dig.get("name"), 200), "kind": clean(dig.get("kind"), 20),
                "record": dig.get("record") if isinstance(dig.get("record"), dict) and
                not suspect(json.dumps(dig.get("record"), ensure_ascii=False)) else {},
                "items": items[:30], "license": clean(raw.get("license"), 200), "imported": time.time(),
                "t": time.time()}
        shelf = raw.get("shelf")
        if _project_exists(ctx, shelf):
            save_digest(ctx, shelf, safe)
            out["project"] += 1
            for f in raw.get("files") or []:
                data = b.files.get(str((f or {}).get("sha256") or ""))
                if data is None:
                    continue
                try:
                    await _sources(ctx).add_upload(shelf, clean(f.get("name"), 200) or "file", data, mode="local")
                    out["files"] += 1
                except Exception as e:  # noqa: BLE001 (refused by the Sources import: type, size, archive…)
                    skip("file_" + str(getattr(e, "kind", "refused"))[:30])
        else:
            config.atomic_write_text(memory_dir(ctx) / "references" / "digests" / f"{sha}.json",
                                     json.dumps({**safe, "project": clean(raw.get("project"), 200)},
                                                ensure_ascii=False))
            out["reference"] += 1
    return out


async def reverify_pending(ctx, progress=None) -> dict:
    """Retry every « importée, non vérifiée » result (after installing the matching workspace, say)."""
    pend = pending_of(ctx)
    rows = pend.list()
    out = {"verified": [], "unverified": []}
    verified_code: dict[str, str] = {}
    for i, r0 in enumerate(_order([x for x in (_lib_row(r) for r in rows) if x])):
        src = next((r for r in rows if r["name"] == r0["name"]), {})
        if progress:
            progress({"stage": "library", "done": i, "total": len(rows), "name": r0["name"]})
        ws = match_workspace(ctx, r0["stamp"], r0["stamp"].get("workspace") or r0["workspace"])
        if ws is None:
            pend.put(src, "no_matching_workspace")
            out["unverified"].append({"name": r0["name"], "reason": "no_matching_workspace"})
            continue
        ok, reason, detail = await verify_entry(ctx, r0, ws, verified_code)
        if not ok:
            pend.put(src, reason, detail)
            out["unverified"].append({"name": r0["name"], "reason": reason})
            continue
        e = _add_verified(ctx, r0, ws, dict(src.get("origin") or {}))
        pend.drop(r0["name"])
        if e is not None:
            verified_code[e.name] = e.code
            out["verified"].append({"name": e.name, "workspace": ws.key})
    return out


def references(ctx) -> dict:
    out: dict = {"graphs": [], "digests": []}
    for kind in ("graphs", "digests"):
        d = memory_dir(ctx) / "references" / kind
        for p in sorted(d.glob("*.json"))[:500] if d.exists() else []:
            try:
                x = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            row = {"id": p.stem, "title": x.get("title") or x.get("name") or p.stem[:12],
                   "project": x.get("project", ""), "imported": x.get("imported")}
            if kind == "graphs":
                row.update(nodes=len((x.get("graph") or {}).get("nodes") or {}),
                           same_statements=x.get("same_statements", 0))
            else:
                row.update(statements=len(x.get("items") or []), license=x.get("license", ""))
            out[kind].append(row)
    return out


def delete_reference(ctx, kind: str, rid: str) -> bool:
    if kind not in ("graphs", "digests") or not re.fullmatch(r"[0-9a-f]{12,64}", rid or ""):
        return False
    p = memory_dir(ctx) / "references" / kind / f"{rid}.json"
    try:
        p.unlink()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- scheduled local backups
BACKUP_DEFAULTS = {"enabled": False, "every_days": 7, "keep": 5, "folder": "", "last": 0.0, "last_error": "",
                   "include_copyrighted": False, "include_files": False}


def backup_settings(ctx) -> dict:
    data, _bad = config.read_json(memory_dir(ctx) / "backups.json")
    s = dict(BACKUP_DEFAULTS)
    if isinstance(data, dict):
        s.update({k: data[k] for k in BACKUP_DEFAULTS if k in data and isinstance(data[k], type(BACKUP_DEFAULTS[k]))
                  or (k == "last" and isinstance(data.get(k), (int, float)))})
    return s


def backup_folder(ctx, s: dict | None = None) -> Path:
    s = s or backup_settings(ctx)
    return Path(s["folder"]).expanduser() if s.get("folder") else ctx.paths.config / "backups"


def set_backup_settings(ctx, patch: dict) -> dict:
    s = backup_settings(ctx)
    for k, v in (patch or {}).items():
        if k == "enabled" or k in ("include_copyrighted", "include_files"):
            if not isinstance(v, bool):
                raise BundleError("bad_value", k)
            s[k] = v
        elif k == "every_days":
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 90:
                raise BundleError("bad_value", k)
            s[k] = v
        elif k == "keep":
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 100:
                raise BundleError("bad_value", k)
            s[k] = v
        elif k == "folder":
            if not isinstance(v, str) or len(v) > 1000 or "\x00" in v:
                raise BundleError("bad_value", k)
            v = v.strip()
            if v and not Path(v).expanduser().is_absolute():
                raise BundleError("folder_not_absolute", k)
            s[k] = v
        else:
            raise BundleError("bad_value", str(k)[:40])
    config.atomic_write_text(memory_dir(ctx) / "backups.json", json.dumps(s, indent=1))
    return s


def list_backups(ctx, s: dict | None = None) -> list[dict]:
    folder = backup_folder(ctx, s)
    out = []
    try:
        for p in folder.iterdir():
            if BACKUP_RE.match(p.name) and p.is_file() and not p.is_symlink():
                st = p.stat()
                out.append({"name": p.name, "bytes": st.st_size, "t": st.st_mtime})
    except OSError:
        pass
    return sorted(out, key=lambda x: x["name"], reverse=True)


def run_backup(ctx, now: float | None = None) -> dict:
    """Write one backup now and rotate (only our own file names are ever deleted)."""
    s = backup_settings(ctx)
    folder = backup_folder(ctx, s)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    now = now or time.time()
    data, info = export_bundle(ctx, {"include_copyrighted": s["include_copyrighted"],
                                     "include_files": s["include_files"]})
    name = "madalean-memory-" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + EXT
    tmp = folder / (name + ".tmp")
    tmp.write_bytes(data)
    tmp.chmod(0o600)
    tmp.replace(folder / name)
    removed = []
    for old in list_backups(ctx, s)[s["keep"]:]:
        try:
            (folder / old["name"]).unlink()
            removed.append(old["name"])
        except OSError:
            pass
    s["last"], s["last_error"] = now, ""
    config.atomic_write_text(memory_dir(ctx) / "backups.json", json.dumps(s, indent=1))
    return {"name": name, "bytes": len(data), "removed": removed, **info}


def backup_due(ctx, now: float | None = None) -> bool:
    s = backup_settings(ctx)
    return bool(s["enabled"]) and (now or time.time()) - float(s["last"] or 0) >= s["every_days"] * 86400


# ---------------------------------------------------------------- training dataset (no training here)
DATASET_SCHEMA = "madalean-train/1"


def dataset_rows(ctx) -> list[dict]:
    """Verified pairs only: (statement → proof) from the library (strict Lean verdict), (error → fix) from lessons
    learned here from a verified success (imported lessons that did not prove themselves are left out)."""
    rows = []
    for r in _collect_library(ctx, None, {}):
        rows.append({"schema": DATASET_SCHEMA, "type": "statement_proof", "statement": r["statement"],
                     "nl": r["nl"], "proof": r["code"], "deps": r["deps"], "lean": r["stamp"]["lean"],
                     "mathlib": r["stamp"]["mathlib"], "workspace": r["workspace"], "verified": "lean-strict",
                     "license": "user (own work, not redistributed without the user's consent)",
                     "provenance": {"source": "imported+reverified" if r["provenance"]["imported"] else "madalean",
                                    "model": r["provenance"]["model"], "by_user": r["provenance"]["by_user"]}})
    for x in _lessons_store(ctx).list():
        # an imported lesson starts at ok = 0: it is in only once it helped a proof Lean accepted HERE
        if int(x.get("ok", 0)) < 1 or x.get("kind") not in ("rename", "fix"):
            continue
        ev = (x.get("evidence") or [{}])[-1]
        if x["kind"] == "rename":
            err, fix = f"unknown identifier '{x.get('old', '')}'", f"use `{x.get('new', '')}`"
        else:
            err, fix = x.get("pattern", ""), "tactics: " + ", ".join(x.get("tactics") or [])
        rows.append({"schema": DATASET_SCHEMA, "type": "error_fix", "error": err, "fix": fix,
                     "shape": x.get("shape", ""), "lean": ev.get("lean", x.get("lean", "")),
                     "mathlib": ev.get("mathlib", x.get("mathlib", "")), "verified": "lean-strict (learned from a "
                     "verified proof)", "license": "user (own work)", "provenance": {
                         "source": "lessons", "lesson": x["id"], "ok": x.get("ok", 0), "bad": x.get("bad", 0)}})
    return rows


def dataset_jsonl(ctx) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in dataset_rows(ctx))


def status(ctx) -> dict:
    lib = ctx.library.entries
    return {"counts": {"library": len(lib), "lessons": len(_lessons_store(ctx).items),
                       "recipes": len(_recipes_store(ctx).list()), "unverified": len(pending_of(ctx).list())},
            "projects": [{"id": p.id, "title": p.title} for p in ctx.projects.list() if not p.archived],
            "backups": {**backup_settings(ctx), "folder_effective": config.tilde(backup_folder(ctx)),
                        "files": list_backups(ctx)}}


def new_token() -> str:
    return secrets.token_hex(8)


__all__ = ["Bundle", "BundleError", "export_bundle", "read_bundle", "plan_import", "apply_import", "run_backup",
           "dataset_rows"]
