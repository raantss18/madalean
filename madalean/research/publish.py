"""« Publier » (ARCHITECTURE §17, role 1): a project → a static site (template of session S-F, `site/build.py
publication`) + a Lake project that a GitHub Action re-verifies, pushed to a GitHub repository chosen by the user.

1. `plan()` builds `publication.json` (schema madalean-publication/1, docs/SITE.md §4) from the project's article
   order (dossier blocks, sections, abstract), the transitive dependencies of what is published (added automatically:
   a result is never shown without what it relies on), the cited bibliography (CSL), the Lean code assembled into a
   Lake project (the workspace's `lean-toolchain`, Mathlib pinned to the workspace's exact commit, its
   `lake-manifest.json`, one module per result inside its own namespace, a root module importing all, `Verify.lean`),
   and the facts behind the statuses (`statement_ok`, `proof_ok` = current proof accepted by the strict verdict AND
   only standard axioms; optional fresh Lean re-check). The template recomputes the statuses from these facts.
2. Privacy: the plan is an explicit manifest of every file that would leave the machine (path, size, SHA-256,
   origin). Notes are excluded unless selected; a source's files (PDF/TeX) only when its `license` says
   redistributable AND the user ticked them. Building / pushing needs the manifest id the user confirmed.
3. Preview: `python3 site/build.py publication --input … --out …` into `<project>/publish/preview/`.
4. Push (host only): `git` (never `--force`) to `https://github.com/<owner>/<repo>.git` with a token from the keyring
   (provider "github") or `gh auth token`, passed in an `http.extraHeader` (never in a URL, never logged);
   repository created on request, GitHub Pages enabled with `build_type: workflow`; updates are new commits on top of
   the remote branch, and nothing is committed when nothing changed."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from .. import config, leancheck
from ..logs import get
from . import article as art_mod
from . import biblio

log = get("research.publish")
SCHEMA = "madalean-publication/1"
REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = REPO_ROOT / "site"
CI_DIR = SITE_DIR / "publication" / "ci"
GITHUB_API = "https://api.github.com"
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
MATHLIB_GIT = "https://github.com/leanprover-community/mathlib4.git"
REDISTRIBUTABLE = re.compile(r"(?i)\b(cc[- _]?(by|0|zero)|creative\s*commons|creativecommons\.org/(licenses|publicdomain)"
                             r"|public[- ]domain|pd)\b")
MANAGED = ("site", "lean", ".github/workflows/verify-and-publish.yml", ".github/madalean")


class PublishError(Exception):
    def __init__(self, kind: str, status: int = 400, **info):
        super().__init__(kind)
        self.kind, self.status, self.info = kind, status, info


def git_url(repo: str) -> str:
    """Where `git push` goes (tests point it to a local bare repository)."""
    return f"https://github.com/{repo}.git"


def pub_dir(ctx, pid: str) -> Path:
    return ctx.projects.store.dir(pid) / "publish"


def ident(text: str, fallback: str = "Pub") -> str:
    """A Lean identifier (CamelCase ASCII) from a title."""
    words = re.findall(r"[A-Za-z0-9]+", biblio.ascii_fold(text or ""))
    s = "".join(w[:1].upper() + w[1:] for w in words)[:40]
    if not s or not s[0].isalpha():
        s = fallback + s
    return s


# ================================================================ workspace pins
def workspace_pins(ws) -> dict:
    """{toolchain, mathlib_rev, mathlib_input, manifest} of a workspace (exact commit, never a moving branch)."""
    if ws is None:
        raise PublishError("no_workspace", 409)
    root = Path(ws.path)
    toolchain = (root / "lean-toolchain").read_text().strip() if (root / "lean-toolchain").exists() else ws.toolchain
    rev, inp, manifest, url = "", "", None, ""
    try:
        man = json.loads((root / "lake-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        man = None
    if man is not None:
        mp = next((p for p in man.get("packages", []) if p.get("name") == "mathlib"), None)
        if mp is not None:
            rev, inp, manifest = mp.get("rev", ""), mp.get("inputRev", ""), man
            url = mp.get("url") or ""
    if not rev and (root / "Mathlib.lean").exists():          # the workspace IS Mathlib (lean-prover49)
        try:
            rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                                 timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            rev = ""
    if not re.fullmatch(r"[0-9a-f]{40}", rev or ""):
        raise PublishError("no_mathlib_pin", 409, workspace=ws.key)
    return {"toolchain": toolchain, "mathlib_rev": rev, "mathlib_input": inp, "manifest": manifest,
            "mathlib_url": url if url.startswith("https://github.com/") else MATHLIB_GIT}


def lakefile(package: str, rev: str, lib: str, url: str = MATHLIB_GIT) -> str:
    # the URL must be the one of lake-manifest.json, else lake reports the manifest out of date
    return (f'import Lake\nopen Lake DSL\n\npackage {package} where\n\nrequire mathlib from git\n  "{url}" @ "{rev}"\n\n'
            f"@[default_target]\nlean_lib {lib} where\n")


def manifest_for(pins: dict, package: str) -> str | None:
    """The workspace's lake-manifest.json re-targeted at the published package: every dependency stays pinned to the
    exact commit the results were checked with."""
    man = pins.get("manifest")
    if not man:
        return None
    m = json.loads(json.dumps(man))
    m["name"] = package
    m["packagesDir"] = ".lake/packages"
    for p in m.get("packages", []):
        if p.get("name") == "mathlib":
            p["inputRev"] = pins["mathlib_rev"]
    return json.dumps(m, indent=1) + "\n"


def namespaced(code: str, ns: str) -> tuple[str, str]:
    """(module source, last theorem name) — the dossier's code inside `namespace ns`; imports stay on top."""
    lines = code.replace("\r\n", "\n").strip("\n").split("\n")
    head = [ln for ln in lines if re.match(r"\s*import\s", ln)]
    body = [ln for ln in lines if not re.match(r"\s*import\s", ln)]
    text = "\n".join(head or ["import Mathlib"]) + f"\n\nnamespace {ns}\n\n" + "\n".join(body).strip("\n") + \
        f"\n\nend {ns}\n"
    try:
        name = leancheck.theorem_name(code)
    except leancheck.StatementError:
        name = ""
    return text, name


# ================================================================ plan
def _dossier_facts(d) -> dict:
    stmt_ok = bool(d.statement) and d.statements[d.cur_statement].ok
    proof_ok = False
    axioms = None
    if d.proof_is_current:
        meta = d.proofs[d.cur_proof].meta or {}
        axioms = meta.get("axioms")
        proof_ok = axioms is not None and set(axioms) <= STANDARD_AXIOMS and not leancheck.forbidden_reasons(d.proof)
    return {"statement_ok": stmt_ok, "proof_ok": proof_ok and stmt_ok, "axioms": axioms}


NODE_KIND = {"theorem": "theorem", "lemma": "lemma", "definition": "definition", "claim": "claim",
             "conjecture": "conjecture", "proposition": "proposition", "corollary": "corollary", "question": "claim"}


def _published_ids(ctx, art: dict, selected: list[str] | None) -> tuple[list[str], list[str]]:
    """Dossiers in article order (+ selection), then their missing transitive dependencies (appended)."""
    order = [b["dossier_id"] for b in art["blocks"] if b["kind"] == "dossier" and ctx.repo.get(b.get("dossier_id") or "")]
    if selected is not None:
        order = [x for x in order if x in selected] + [x for x in selected if x not in order and ctx.repo.get(x)]
    added: list[str] = []
    stack = list(order)
    seen = set(order)
    while stack:
        d = ctx.repo.get(stack.pop())
        for u in d.uses or []:
            if isinstance(u, str) and u not in seen and ctx.repo.get(u) is not None:
                seen.add(u)
                added.append(u)
                stack.append(u)
    return order + added, added


def _md_cites(text: str, keys: set) -> str:
    return biblio.check_citations(text or "", keys).text


def plan(ctx, pid: str, opts: dict) -> dict:
    """Build the publication input (in `<project>/publish/input/`) and the manifest of what would leave the machine.
    opts: {dossiers?: [ids], notes?: [note ids], source_files?: [{shelf, id, sha256}], include_pdf?: bool,
    lang?, license?, authors?, title?} + `_notes` (callable id → note dict) and `_pdf` (bytes) given by the route."""
    from .sources import library
    p = ctx.projects.get(pid)
    if p is None:
        raise PublishError("not_found", 404)
    art = art_mod.load(ctx, pid)
    lang = opts.get("lang") if opts.get("lang") in ("fr", "en") else art["options"].get("lang", "fr")
    ids, auto = _published_ids(ctx, art, opts.get("dossiers"))
    if not ids:
        raise PublishError("nothing_to_publish", 409)
    dossiers = [ctx.repo.get(i) for i in ids]
    # one workspace for the whole Lake project
    wss = [d.workspace or ctx.settings.workspace for d in dossiers]
    ws_key = max(set(wss), key=wss.count)
    ws = ctx.workspace(ws_key)
    pins = workspace_pins(ws)
    warnings = [f"dependency_added:{i}" for i in auto]
    root = ident(p.title, "Pub")
    lib = library(ctx)
    known = lib.all_entries(pid)
    # ---- bibliography: everything cited by the article, the published dossiers and their refs
    cited: list[str] = []
    texts = [art["abstract"].get("text", "")] + [b.get("text", "") for b in art["blocks"]]
    for d in dossiers:
        texts += biblio.dossier_texts(d)
        cited += [r["key"] for r in d.refs or [] if isinstance(r, dict) and r.get("key") in known]
        if isinstance(d.source, dict) and d.source.get("paper_key") in known:
            cited.append(d.source["paper_key"])
    for t in texts:
        cited += [c.key for c in biblio.find_citations(t) if c.key in known]
    cited = list(dict.fromkeys(cited))
    entries = [(k, known[k]) for k in cited]
    labels = biblio.labels_for(entries)
    keys = set(cited)
    # ---- nodes + Lean modules
    nodes, modules, pub_ids = [], {}, set(ids)
    for i, d in enumerate(dossiers, 1):
        facts = _dossier_facts(d)
        bp = (d.extra or {}).get("blueprint") or {}
        kind = NODE_KIND.get(bp.get("paper_kind") or d.kind, "claim")
        node: dict = {"id": d.id, "kind": kind, "number": str(i), "title": re.sub(r"\s*\[[^\]]*\]$", "", d.title)[:200],
                      "statement": _md_cites(art_mod.statement_text(d), keys) or d.title,
                      "uses": [u for u in d.uses or [] if u in pub_ids and u != d.id]}
        if facts["proof_ok"] and (d.informal_proof or d.explanation):
            node["informal_proof"] = _md_cites(d.informal_proof or d.explanation, keys)
        refs = [{"key": r["key"], "locator": r.get("locator", ""), "note": r.get("note", "")} for r in d.refs or []
                if isinstance(r, dict) and r.get("key") in keys]
        if refs:
            node["refs"] = refs
        if isinstance(d.source, dict) and d.source.get("paper_key") in keys:
            node["source"] = {"paper_key": d.source["paper_key"], "locator": d.source.get("locator", "")}
        if d.workspace and d.workspace != ws_key and d.statement:
            warnings.append(f"other_workspace:{d.id}")
        elif d.statement and facts["statement_ok"]:
            code = d.proof if facts["proof_ok"] else d.statement
            mod = f"M{i:02d}" + ident(d.title, "R")[:30]
            ns = f"{root}.{mod}"
            src, name = namespaced(code, ns)
            modules[mod] = src
            node["lean"] = {"name": f"{ns}.{name}" if name else ns, "code": code.strip(),
                            "statement_ok": True, "proof_ok": facts["proof_ok"], "axioms": facts["axioms"]}
        elif d.statement:
            node["lean"] = {"name": "", "code": d.statement.strip(), "statement_ok": False, "proof_ok": False,
                            "axioms": None}
        nodes.append(node)
    # ---- sections from the article blocks
    sections, cur = [], None
    for b in art["blocks"]:
        if b["kind"] in ("intro", "section", "conclusion") or cur is None:
            cur = {"id": f"s{len(sections) + 1}", "title": b.get("title") or (art.get("title") or p.title),
                   "body": "", "nodes": []}
            sections.append(cur)
        if b.get("text", "").strip():
            cur["body"] = (cur["body"] + "\n\n" + _md_cites(b["text"], keys)).strip()
        if b["kind"] == "dossier" and b.get("dossier_id") in pub_ids:
            cur["nodes"].append(b["dossier_id"])
    placed = {n for s in sections for n in s["nodes"]}
    if auto or any(i not in placed for i in ids):
        sections.append({"id": f"s{len(sections) + 1}", "title": "Dépendances" if lang == "fr" else "Dependencies",
                         "body": "", "nodes": [i for i in ids if i not in placed]})
    sections = [s for s in sections if s["body"] or s["nodes"]]
    info = {}
    try:
        from ..runtime.lean import workspace_info
        info = workspace_info(ws)
    except Exception:  # noqa: BLE001
        pass
    pub = {"schema": SCHEMA, "lang": lang,
           "project": {"title": (opts.get("title") or art.get("title") or p.title)[:300],
                       "authors": [{"name": a["name"], **({"affiliation": a["affiliation"]} if a.get("affiliation")
                                                         else {})} for a in (opts.get("authors") or art.get("authors")
                                                                             or [])],
                       "date": time.strftime("%Y-%m-%d"), "license": str(opts.get("license") or "CC-BY-4.0")[:60],
                       **({"abstract": _md_cites(art["abstract"]["text"], keys)} if art["abstract"].get("text") else {})},
           "lean": {"toolchain": pins["toolchain"], "mathlib": pins["mathlib_rev"],
                    "checked_at": time.strftime("%Y-%m-%d"),
                    "checker": f"Madalean {ctx.version}, verdict strict" + (f" ({info.get('lean')})" if info.get("lean")
                                                                             else ""),
                    "root_module": root, "lake_project": f"files/{root}-lake.zip"},
           "article": {"sections": sections},
           "nodes": nodes,
           "bibliography": [{"key": k, "label": labels[k], "csl": {x: v for x, v in it.items() if not x.startswith("_")}}
                            for k, it in entries],
           "files": [{"path": f"files/{root}-lake.zip", "title": "Lean (Lake)", "kind": "lake"}]}
    # ---- write the input directory and the Lake project
    base = pub_dir(ctx, pid)
    inp, lean_dir = base / "input", base / "lean"
    for d_ in (inp, lean_dir):
        if d_.exists():
            shutil.rmtree(d_)
    (inp / "files").mkdir(parents=True)
    lean_dir.mkdir(parents=True)
    sys.path.insert(0, str(SITE_DIR)) if str(SITE_DIR) not in sys.path else None
    from madasite import publication as tpl                    # S-F's template (validation, Verify.lean)
    files: dict[str, bytes] = {}
    files["lean-toolchain"] = (pins["toolchain"] + "\n").encode()
    files["lakefile.lean"] = lakefile(root, pins["mathlib_rev"], root, pins["mathlib_url"]).encode()
    man = manifest_for(pins, root)
    if man:
        files["lake-manifest.json"] = man.encode()
    for mod, src in modules.items():
        files[f"{root}/{mod}.lean"] = src.encode()
    files[f"{root}.lean"] = ("".join(f"import {root}.{m}\n" for m in modules) or "import Mathlib\n").encode()
    files["Verify.lean"] = tpl.verify_file(pub).encode()
    for rel, data in files.items():
        (lean_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (lean_dir / rel).write_bytes(data)
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, data in sorted(files.items()):
            z.writestr(f"{root}/{rel}", data)
    items = []

    def put(rel: str, data: bytes, origin: str, kind: str = "file", note: str = "") -> None:
        (inp / rel).parent.mkdir(parents=True, exist_ok=True)
        (inp / rel).write_bytes(data)
        items.append({"path": rel, "kind": kind, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "origin": origin, "note": note})
    put(f"files/{root}-lake.zip", zbuf.getvalue(), "lean", "lake",
        f"{len(modules)} module(s) Lean, Mathlib {pins['mathlib_rev'][:12]}")
    if opts.get("_pdf"):
        put("files/article.pdf", opts["_pdf"], "article", "pdf")
        pub["article"]["pdf"] = "files/article.pdf"
        pub["files"].append({"path": "files/article.pdf", "title": "PDF", "kind": "pdf"})
    excluded = []
    get_note = opts.get("_notes")
    for nid in opts.get("notes") or []:
        note = get_note(nid) if get_note else None
        if not note or note.get("project_id") not in (pid, "", None):
            excluded.append({"what": f"note:{nid}", "why": "not_found"})
            continue
        name = f"files/note-{re.sub(r'[^A-Za-z0-9._-]', '_', nid)[:60]}.md"
        put(name, (f"# {note.get('title', '')}\n\n" + note.get("body", "")).encode(), f"note:{nid}", "other")
        pub["files"].append({"path": name, "title": note.get("title") or nid, "kind": "other"})
    for sel in opts.get("source_files") or []:
        try:
            src = lib.get(str(sel.get("shelf")), str(sel.get("id")))
        except Exception:  # noqa: BLE001
            excluded.append({"what": f"source:{sel.get('id')}", "why": "not_found"})
            continue
        lic = str(src.get("license") or (src.get("csl") or {}).get("license") or "")
        f = next((x for x in src.get("files", []) if x["sha256"] == sel.get("sha256")), None)
        if f is None:
            excluded.append({"what": f"source:{src['key']}", "why": "no_such_file"})
            continue
        if not REDISTRIBUTABLE.search(lic):
            excluded.append({"what": f"source:{src['key']}/{f['name']}", "why": "license_not_redistributable",
                             "license": lic})
            continue
        ext = {"pdf": "pdf", "tex": "tex", "archive": "tar.gz", "epub": "epub"}.get(f["kind"], "bin")
        name = f"files/{re.sub(r'[^A-Za-z0-9._-]', '_', src['key'])[:60]}.{ext}"
        put(name, lib.shelf(str(sel.get("shelf"))).blob(f["sha256"]).read_bytes(), f"source:{src['key']}",
            "pdf" if f["kind"] == "pdf" else "other", lic)
        pub["files"].append({"path": name, "title": f"{src['key']} ({lic})", "kind": "pdf" if f["kind"] == "pdf"
                             else ("tex" if f["kind"] in ("tex", "archive") else "other")})
    errs = tpl.validate(pub)
    if errs:
        raise PublishError("invalid_publication", 422, errors=errs[:20])
    text = json.dumps(pub, ensure_ascii=False, indent=1)
    (inp / "publication.json").write_text(text, encoding="utf-8")
    items.insert(0, {"path": "publication.json", "kind": "metadata", "size": len(text.encode()),
                     "sha256": hashlib.sha256(text.encode()).hexdigest(), "origin": "project",
                     "note": f"{len(nodes)} résultats / results, {len(entries)} références / references"})
    for rel, data in sorted(files.items()):
        items.append({"path": f"lean/{rel}", "kind": "lean", "size": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(), "origin": "lean", "note": ""})
    for rel in ("verify-and-publish.yml", "make_badge.py"):
        data = (CI_DIR / rel).read_bytes()
        items.append({"path": (".github/workflows/" if rel.endswith(".yml") else ".github/madalean/") + rel,
                      "kind": "ci", "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "origin": "template",
                      "note": ""})
    st = tpl.statuses(nodes)
    mid = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {"id": mid, "project": pid, "created": time.time(), "items": items, "excluded": excluded,
                "warnings": warnings, "statuses": st,
                "counts": {s: list(st.values()).count(s) for s in set(st.values())},
                "not_included": ["sources_full_text", "unselected_notes", "dossier_threads", "model_transcripts",
                                 "settings", "keys"],
                "workspace": ws_key, "mathlib": pins["mathlib_rev"], "toolchain": pins["toolchain"]}
    config.atomic_write_text(base / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


def confirmed(ctx, pid: str, manifest_id: str) -> dict:
    try:
        man = json.loads((pub_dir(ctx, pid) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PublishError("no_plan", 409)
    if man.get("id") != manifest_id:
        raise PublishError("manifest_changed", 409, current=man.get("id"))
    return man


# ================================================================ preview
def render(ctx, pid: str, timeout: float = 300) -> dict:
    """site/build.py publication → <project>/publish/preview/ (static)."""
    base = pub_dir(ctx, pid)
    out = base / "preview"
    r = subprocess.run([sys.executable, str(SITE_DIR / "build.py"), "publication", "--input", str(base / "input"),
                        "--out", str(out), "--force"], capture_output=True, text=True, timeout=timeout,
                       cwd=str(REPO_ROOT), env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if r.returncode != 0 or not (out / "index.html").exists():
        raise PublishError("build_failed", 422, log=(r.stdout + r.stderr)[-3000:])
    return {"pages": len(list(out.rglob("*.html"))), "log": r.stdout[-1000:]}


# ================================================================ GitHub
def _gh_path() -> str | None:
    return shutil.which("gh")


def github_token(ctx) -> tuple[str, str]:
    tok = ctx.keys.get("github") if hasattr(ctx, "keys") else None
    if tok:
        return tok, "keyring"
    gh = _gh_path()
    if gh:
        try:
            r = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip(), "gh"
        except (OSError, subprocess.SubprocessError):
            pass
    raise PublishError("no_github_credentials", 409)


class GitHub:
    def __init__(self, token: str, api: str | None = None):
        self.token, self.api = token, (api or GITHUB_API).rstrip("/")

    async def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import aiohttp
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Madalean/2.0 (publish)"}
        async with aiohttp.ClientSession(trust_env=False, cookie_jar=aiohttp.DummyCookieJar()) as s:
            async with s.request(method, self.api + path, json=body, headers=headers, allow_redirects=False,
                                 timeout=aiohttp.ClientTimeout(total=60)) as r:
                try:
                    data = await r.json(content_type=None)
                except ValueError:
                    data = {}
                return r.status, data if isinstance(data, dict) else {"items": data}


def _git(args: list[str], cwd: Path, token: str = "", timeout: float = 300) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd), "GIT_TERMINAL_PROMPT": "0",
           "GIT_CONFIG_NOSYSTEM": "1", "LANG": "C.UTF-8"}
    if token:                                   # Authorization header through git's config env: never in a URL / log
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                    "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}"})
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    if token:
        r = subprocess.CompletedProcess(r.args, r.returncode, r.stdout.replace(token, "***"),
                                        r.stderr.replace(token, "***"))
    return r


def _sync_tree(work: Path, base: Path) -> None:
    """Replace the managed paths of the working copy by the new site / Lake project / CI files."""
    for rel in MANAGED:
        p = work / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    shutil.copytree(base / "preview", work / "site")
    shutil.copytree(base / "lean", work / "lean")
    (work / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (work / ".github" / "madalean").mkdir(parents=True, exist_ok=True)
    shutil.copy(CI_DIR / "verify-and-publish.yml", work / ".github" / "workflows" / "verify-and-publish.yml")
    shutil.copy(CI_DIR / "make_badge.py", work / ".github" / "madalean" / "make_badge.py")
    gi = work / ".gitignore"
    if not gi.exists():
        gi.write_text("lean/.lake/\n")
    rd = work / "README.md"
    if not rd.exists():
        rd.write_text("Published with Madalean: `site/` is the website (GitHub Pages), `lean/` the Lake project that "
                      "the workflow re-verifies with Lean.\n")


async def push(ctx, pid: str, repo: str, *, create: bool = False, private: bool = False, branch: str = "main",
               progress=lambda step, **kw: None) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,39}/[A-Za-z0-9_.-]{1,100}", repo or "") or ".." in repo:
        raise PublishError("bad_repo")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", branch) or ".." in branch:
        raise PublishError("bad_branch")
    base = pub_dir(ctx, pid)
    if not (base / "preview" / "index.html").exists():
        raise PublishError("no_preview", 409)
    token, how = await asyncio.to_thread(github_token, ctx)
    gh = GitHub(token)
    owner, name = repo.split("/", 1)
    progress("repository", repo=repo, credentials=how)
    st, info = await gh.call("GET", f"/repos/{owner}/{name}")
    created = False
    if st == 404:
        if not create:
            raise PublishError("repo_not_found", 404, repo=repo)
        st_u, me = await gh.call("GET", "/user")
        if st_u != 200:
            raise PublishError("github_auth", 401)
        path = "/user/repos" if me.get("login", "").lower() == owner.lower() else f"/orgs/{owner}/repos"
        st, info = await gh.call("POST", path, {"name": name, "private": bool(private), "auto_init": False,
                                                "description": "Published with Madalean (Lean-verified)"})
        if st not in (200, 201):
            raise PublishError("repo_create_failed", 502, status=st, message=str(info.get("message", ""))[:200])
        created = True
        progress("created", repo=repo)
    elif st in (401, 403):
        raise PublishError("github_auth", 401)
    elif st != 200:
        raise PublishError("github_error", 502, status=st)
    url = git_url(repo)
    with tempfile.TemporaryDirectory(prefix="madalean-publish-") as tmp:
        work = Path(tmp) / "repo"
        progress("fetch")
        r = await asyncio.to_thread(_git, ["clone", "--quiet", url, str(work)], Path(tmp), token)
        if r.returncode != 0:
            raise PublishError("git_clone_failed", 502, log=r.stderr[-500:])
        await asyncio.to_thread(_git, ["checkout", "-q", "-B", branch] + ([f"origin/{branch}"] if (
            await asyncio.to_thread(_git, ["rev-parse", "--verify", "-q", f"origin/{branch}"], work)).returncode == 0
            else []), work)
        await asyncio.to_thread(_sync_tree, work, base)
        await asyncio.to_thread(_git, ["add", "-A", "."], work)
        diff = await asyncio.to_thread(_git, ["status", "--porcelain"], work)
        commit = ""
        if diff.stdout.strip():
            progress("commit", files=len(diff.stdout.strip().splitlines()))
            r = await asyncio.to_thread(_git, ["-c", "user.name=Madalean", "-c", "user.email=madalean@localhost",
                                               "commit", "-q", "-m", f"Publish {time.strftime('%Y-%m-%d %H:%M')} "
                                               "(Madalean)"], work)
            if r.returncode != 0:
                raise PublishError("git_commit_failed", 500, log=r.stderr[-500:])
            progress("push")
            r = await asyncio.to_thread(_git, ["push", "--quiet", "origin", f"HEAD:refs/heads/{branch}"], work, token)
            if r.returncode != 0:                        # never --force: a diverged remote is reported
                raise PublishError("git_push_rejected", 409, log=r.stderr[-500:])
        commit = (await asyncio.to_thread(_git, ["rev-parse", "HEAD"], work)).stdout.strip()
        changed = bool(diff.stdout.strip())
    progress("pages")
    st, pages = await gh.call("GET", f"/repos/{owner}/{name}/pages")
    if st == 404:
        st, pages = await gh.call("POST", f"/repos/{owner}/{name}/pages", {"build_type": "workflow"})
    elif st == 200 and pages.get("build_type") != "workflow":
        st, pages = await gh.call("PUT", f"/repos/{owner}/{name}/pages", {"build_type": "workflow"})
        st = 200 if st == 204 else st
    pages_ok = st in (200, 201, 204)
    state = {"repo": repo, "branch": branch, "commit": commit, "changed": changed, "created": created,
             "pages": pages_ok, "pages_url": pages.get("html_url") or f"https://{owner.lower()}.github.io/{name}/",
             "pushed_at": time.time()}
    config.atomic_write_text(base / "state.json", json.dumps(state, indent=1))
    return state


def state(ctx, pid: str) -> dict:
    try:
        return json.loads((pub_dir(ctx, pid) / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
