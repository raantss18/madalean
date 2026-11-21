"""« Publier »: publication.json + Lake project from a project, privacy manifest, local preview, push to a FAKE GitHub
API and a LOCAL bare git remote (nothing leaves the machine). A slow test builds a generated project with real Lean."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from aiohttp import web

from madalean.research import publish
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.sources import Library
from madalean.workspaces import Workspace
from helpers import make_ctx, running, session

ROOT = Path(__file__).resolve().parents[1]
LEAN_CURRENT = ROOT / "workspaces" / "lean-current"
DATA = ROOT / "madalean" / "research" / "demo_data"
HEAD = "import Mathlib\n\nset_option maxHeartbeats 400000\n\nopen BigOperators Real Nat Topology Rat\n\n"


def fake_workspace(tmp: Path) -> Workspace:
    w = tmp / "ws"
    w.mkdir()
    (w / "lean-toolchain").write_text("leanprover/lean4:v4.34.1\n")
    man = {"version": "1.1.0", "packagesDir": ".lake/packages", "name": "LeanCurrent", "lakeDir": ".lake",
           "packages": [{"type": "git", "url": "https://github.com/leanprover-community/mathlib4", "name": "mathlib",
                         "rev": "d13f23b723b8a846827a245b89c10fc7d3f11612", "inputRev": "v4.34.1", "inherited": False,
                         "scope": "", "manifestFile": "lake-manifest.json", "configFile": "lakefile.lean"}]}
    (w / "lake-manifest.json").write_text(json.dumps(man))
    return Workspace("cur", "Current", w, "leanprover/lean4:v4.34.1", True)


def dossier(ctx, pid, title, statement, proof=None, axioms=("propext",), uses=(), ok=True):
    d = ctx.repo.new(title, "cur", title)
    d.project_id = pid
    st = HEAD + statement.format(name=d.theorem) + " := by sorry\n"
    d.add_statement(st, ok=ok)
    if proof is not None:
        d.add_proof(HEAD + statement.format(name=d.theorem) + " := by\n  " + proof + "\n",
                    meta={"axioms": list(axioms) if axioms is not None else None})
        d.add_informal_proof("Écrivons $a = 2k$, $b = 2l$ [@hw79, Ch. 1].")
    d.uses = list(uses)
    d.problem = f"{title} [@hw79]."
    ctx.repo.cache[d.id] = d
    return d


async def setup_project(s, local, ctx):
    async with s.post(local + "/api/projects", json={"title": "Parité publiée"}) as r:
        pid = (await r.json())["project"]["id"]
    lib = Library(ctx, Fetcher(ReplayTransport(Path("/nonexistent"))))
    lib.embeddings = False
    ctx._research_library = lib
    book = {"type": "book", "title": "An introduction to the theory of numbers", "_key": "hw79",
            "author": [{"family": "Hardy", "given": "G. H."}, {"family": "Wright", "given": "E. M."}],
            "issued": {"date-parts": [[1979]]}}
    await lib.add_record(pid, book, via="form", extract=False)
    paper, _ = await lib.add_record(pid, {"type": "article", "title": "A note on parity", "_key": "note"},
                                    via="form", files=[("note.pdf", (DATA / "parity-note.pdf").read_bytes())],
                                    extract=False)
    base = dossier(ctx, pid, "Base", "theorem {name} : (0 : ℕ) + 0 = 0", "simp")
    hidden = dossier(ctx, pid, "Hidden", "theorem {name} (n : ℕ) : n * 0 = 0")            # statement only
    a = dossier(ctx, pid, "Sum even", "theorem {name} (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)",
                "exact Even.add ha hb", uses=[base.id])
    b = dossier(ctx, pid, "Uses hidden", "theorem {name} : (2 : ℕ) * 0 = 0", "simp", uses=[hidden.id])
    c = dossier(ctx, pid, "Sorry proof", "theorem {name} : (1 : ℕ) = 1", "rfl", axioms=["propext", "sorryAx"])
    for d in (base, hidden, a, b, c):
        await ctx.repo.save(d)
    # the article shows base, a, b, c — not `hidden` (it is added as a dependency)
    async with s.get(local + f"/api/research/projects/{pid}/article") as r:
        art = (await r.json())["article"]
    keep = [x["id"] for x in art["blocks"] if x["kind"] != "dossier" or x["dossier_id"] != hidden.id]
    for x in art["blocks"]:
        if x["id"] not in keep:
            async with s.delete(local + f"/api/research/projects/{pid}/article/blocks/{x['id']}") as r:
                assert r.status == 200
    return pid, {"base": base, "hidden": hidden, "a": a, "b": b, "c": c}, paper, lib


# ---------------------------------------------------------------- fake GitHub
def fake_github(state: dict) -> web.Application:
    app = web.Application()

    def auth(request):
        state.setdefault("auth", []).append(request.headers.get("Authorization", ""))
        return request.headers.get("Authorization") == "Bearer tok-123"

    async def user(request):
        return web.json_response({"login": "alice"} if auth(request) else {}, status=200 if auth(request) else 401)

    async def repo(request):
        auth(request)
        name = f"{request.match_info['o']}/{request.match_info['r']}"
        return web.json_response({"full_name": name}) if name in state["repos"] else \
            web.json_response({"message": "Not Found"}, status=404)

    async def create(request):
        auth(request)
        data = await request.json()
        state["repos"].add(f"alice/{data['name']}")
        state.setdefault("created", []).append(data)
        return web.json_response({"full_name": f"alice/{data['name']}"}, status=201)

    async def pages(request):
        auth(request)
        name = f"{request.match_info['o']}/{request.match_info['r']}"
        state.setdefault("pages_calls", []).append(request.method)
        if request.method == "GET":
            p = state["pages"].get(name)
            return web.json_response(p) if p else web.json_response({"message": "Not Found"}, status=404)
        data = await request.json()
        state["pages"][name] = {"build_type": data["build_type"], "html_url": f"https://alice.github.io/{name[6:]}/"}
        return web.json_response(state["pages"][name], status=201 if request.method == "POST" else 204)
    app.router.add_get("/user", user)
    app.router.add_get("/repos/{o}/{r}", repo)
    app.router.add_post("/user/repos", create)
    app.router.add_route("*", "/repos/{o}/{r}/pages", pages)
    return app


async def wait_event(ws, rid, timeout=120):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    steps = []
    while True:
        ev = json.loads((await asyncio.wait_for(ws.receive(), end - loop.time())).data)
        if ev.get("request_id") != rid:
            continue
        if ev["type"] == "publish.progress":
            steps.append(ev["step"])
        if ev["type"] in ("publish.done", "publish.error"):
            return ev, steps


async def test_plan_preview_push_against_fake_github_and_bare_remote(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, ws=fake_workspace(tmp_path), fake_lean=True)
    gh_state = {"repos": set(), "pages": {}}
    runner = web.AppRunner(fake_github(gh_state))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    monkeypatch.setattr(publish, "GITHUB_API", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(publish, "git_url", lambda repo: str(bare))
    git_calls = []
    real_git = publish._git

    def spy(args, cwd, token="", timeout=300):
        git_calls.append(list(args))
        return real_git(args, cwd, token, timeout)
    monkeypatch.setattr(publish, "_git", spy)
    try:
        async with running(ctx) as (srv, local, remote):
            ctx.settings.mode = "auto"
            async with session() as s, s.ws_connect(local + "/api/ws") as ws:
                await ws.receive_json()
                pid, ds, paper, lib = await setup_project(s, local, ctx)
                # ---- plan: the manifest lists everything that would leave the machine
                async with s.post(local + f"/api/research/publish/{pid}/plan",
                                  json={"source_files": [{"shelf": pid, "id": paper["id"],
                                                          "sha256": paper["files"][0]["sha256"]}],
                                        "notes": ["n-missing"], "lang": "en"}) as r:
                    assert r.status == 200, await r.text()
                    man = (await r.json())["manifest"]
                paths = [i["path"] for i in man["items"]]
                assert paths[0] == "publication.json" and any(p.endswith("-lake.zip") for p in paths)
                assert ".github/workflows/verify-and-publish.yml" in paths and "lean/Verify.lean" in paths
                assert all(len(i["sha256"]) == 64 and i["size"] > 0 for i in man["items"])
                assert {"what": "source:note/note.pdf", "why": "license_not_redistributable", "license": ""} in \
                    man["excluded"]
                assert {"what": "note:n-missing", "why": "not_found"} in man["excluded"]
                assert f"dependency_added:{ds['hidden'].id}" in man["warnings"]
                st = man["statuses"]
                assert st[ds["base"].id] == "verified" and st[ds["a"].id] == "verified"
                assert st[ds["b"].id] == "proved"                      # its dependency is only stated
                assert st[ds["hidden"].id] == "statement" and st[ds["c"].id] == "statement"   # sorryAx → no proof
                base_dir = publish.pub_dir(ctx, pid)
                pub = json.loads((base_dir / "input" / "publication.json").read_text())
                assert pub["schema"] == "madalean-publication/1" and pub["lang"] == "en"
                assert pub["lean"]["mathlib"] == "d13f23b723b8a846827a245b89c10fc7d3f11612"
                assert [b["key"] for b in pub["bibliography"]] == ["hw79"]
                lean_dir = base_dir / "lean"
                lakefile = (lean_dir / "lakefile.lean").read_text()
                assert '@ "d13f23b723b8a846827a245b89c10fc7d3f11612"' in lakefile and "package ParitePubliee" in lakefile
                assert json.loads((lean_dir / "lake-manifest.json").read_text())["name"] == "ParitePubliee"
                verify = (lean_dir / "Verify.lean").read_text()
                assert verify.startswith("import ParitePubliee") and verify.count("#print axioms") == 2
                rootmod = (lean_dir / "ParitePubliee.lean").read_text()
                assert rootmod.count("import ParitePubliee.M") == 5
                # the licence ticks a source file in
                async with s.patch(local + f"/api/research/shelves/{pid}/sources/{paper['id']}",
                                   json={"license": "CC-BY-4.0"}) as r:
                    assert r.status == 200
                async with s.post(local + f"/api/research/publish/{pid}/plan",
                                  json={"source_files": [{"shelf": pid, "id": paper["id"],
                                                          "sha256": paper["files"][0]["sha256"]}]}) as r:
                    man2 = (await r.json())["manifest"]
                assert "files/note.pdf" in [i["path"] for i in man2["items"]] and man2["id"] != man["id"]
                # ---- preview: only for the manifest the user confirmed
                async with s.post(local + f"/api/research/publish/{pid}/preview", json={"manifest_id": man["id"]}) as r:
                    assert r.status == 409 and (await r.json())["error"] == "manifest_changed"
                async with s.post(local + f"/api/research/publish/{pid}/preview",
                                  json={"manifest_id": man2["id"]}) as r:
                    assert r.status == 200, await r.text()
                    url = (await r.json())["url"]
                async with s.get(local + url) as r:
                    html = await r.text()
                    assert r.status == 200 and "sandbox" in r.headers["Content-Security-Policy"]
                assert "Parité publiée" in html
                for bad in ("..%2F..%2Fproject.json", "../../project.json", "%2e%2e/manifest.json"):
                    async with s.get(local + f"/api/research/publish/{pid}/preview/{bad}") as r:
                        assert r.status in (400, 404), bad
                async with s.get(remote + url) as r:
                    assert r.status == 401
                async with s.post(remote + f"/api/research/publish/{pid}/push", json={}) as r:
                    assert r.status in (401, 403)
                # ---- push: no credentials → clear error
                monkeypatch.setattr(publish, "_gh_path", lambda: None)
                async with s.post(local + f"/api/research/publish/{pid}/push",
                                  json={"manifest_id": man2["id"], "repo": "alice/parity", "create": True}) as r:
                    rid = (await r.json())["request_id"]
                ev, _ = await wait_event(ws, rid)
                assert ev["type"] == "publish.error" and ev["error"] == "no_github_credentials" and ev["message"]
                await asyncio.to_thread(ctx.keys.set, "github", "tok-123")
                async with s.post(local + f"/api/research/publish/{pid}/push",
                                  json={"manifest_id": man2["id"], "repo": "alice/parity"}) as r:
                    rid = (await r.json())["request_id"]
                ev, _ = await wait_event(ws, rid)
                assert ev["type"] == "publish.error" and ev["error"] == "repo_not_found"
                async with s.post(local + f"/api/research/publish/{pid}/push",
                                  json={"manifest_id": man2["id"], "repo": "alice/parity", "create": True}) as r:
                    rid = (await r.json())["request_id"]
                ev, steps = await wait_event(ws, rid)
                assert ev["type"] == "publish.done", ev
                stt = ev["state"]
                assert stt["created"] and stt["changed"] and stt["pages"] and stt["commit"]
                assert steps[:3] == ["repository", "created", "fetch"] and "push" in steps and steps[-1] == "pages"
                assert gh_state["created"][0]["name"] == "parity" and gh_state["pages"]["alice/parity"]["build_type"] \
                    == "workflow"
                assert all(a == "Bearer tok-123" for a in gh_state["auth"])
                tree = subprocess.run(["git", "-C", str(bare), "ls-tree", "-r", "--name-only", "main"],
                                      capture_output=True, text=True).stdout.split()
                assert "site/index.html" in tree and "lean/lakefile.lean" in tree and "lean/Verify.lean" in tree
                assert ".github/workflows/verify-and-publish.yml" in tree and ".github/madalean/make_badge.py" in tree
                assert "site/files/note.pdf" in tree
                # ---- idempotent: same content → no new commit, Pages not re-created
                n_pages = gh_state["pages_calls"].count("POST")
                async with s.post(local + f"/api/research/publish/{pid}/push",
                                  json={"manifest_id": man2["id"], "repo": "alice/parity"}) as r:
                    rid = (await r.json())["request_id"]
                ev, _ = await wait_event(ws, rid)
                assert ev["type"] == "publish.done" and ev["state"]["changed"] is False
                assert ev["state"]["commit"] == stt["commit"] and gh_state["pages_calls"].count("POST") == n_pages
                # ---- a remote that refuses: reported, never forced
                hook = bare / "hooks" / "pre-receive"
                hook.write_text("#!/bin/sh\nexit 1\n")
                hook.chmod(0o755)
                (base_dir / "preview" / "extra.txt").write_text("change")
                async with s.post(local + f"/api/research/publish/{pid}/push",
                                  json={"manifest_id": man2["id"], "repo": "alice/parity"}) as r:
                    rid = (await r.json())["request_id"]
                ev, _ = await wait_event(ws, rid)
                assert ev["type"] == "publish.error" and ev["error"] == "git_push_rejected"
                pushes = [a for a in git_calls if a and a[0] == "push"]
                assert pushes and not any(x in ("--force", "-f", "--force-with-lease") or x.startswith("+")
                                          for a in pushes for x in a)
                assert not any("tok-123" in " ".join(a) for a in git_calls)          # never in a command line
    finally:
        await runner.cleanup()


def test_namespaced_modules_and_pins():
    src, name = publish.namespaced(HEAD + "theorem t (a : ℕ) : a = a := by\n  rfl\n", "Root.M01X")
    assert src.startswith("import Mathlib\n\nnamespace Root.M01X") and src.rstrip().endswith("end Root.M01X")
    assert name == "t" and "set_option" in src
    assert publish.ident("Parité publiée !") == "ParitePubliee" and publish.ident("2 notes")[0].isalpha()
    lf = publish.lakefile("Pkg", "a" * 40, "Pkg")
    assert '"https://github.com/leanprover-community/mathlib4.git" @ "' + "a" * 40 in lf


@pytest.mark.slow
@pytest.mark.skipif(not (LEAN_CURRENT / ".lake" / "packages" / "mathlib").is_dir(), reason="lean-current not built")
async def test_generated_lake_project_builds_with_real_lean(tmp_path):
    """Real `lake build` of a generated project (offline: the workspace's built packages are linked in)."""
    from madalean.workspaces import all_workspaces
    ws = next(w for w in all_workspaces(scan_user=False) if w.key == "lean-current")
    ctx = make_ctx(tmp_path, ws=ws, fake_lean=True)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            pid, ds, _paper, _lib = await setup_project(s, local, ctx)
            for d in ds.values():
                d.workspace = "lean-current"
            man = await asyncio.to_thread(publish.plan, ctx, pid, {})
    lean = publish.pub_dir(ctx, pid) / "lean"
    (lean / ".lake" / "packages").mkdir(parents=True)
    for p in (LEAN_CURRENT / ".lake" / "packages").iterdir():
        (lean / ".lake" / "packages" / p.name).symlink_to(p)
    tc = (lean / "lean-toolchain").read_text().strip().replace("/", "--").replace(":", "---")
    lake = Path.home() / ".elan" / "toolchains" / tc / "bin" / "lake"
    r = subprocess.run([str(lake), "build"], cwd=lean, capture_output=True, text=True, timeout=3000)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "manifest out of date" not in r.stdout + r.stderr
    v = subprocess.run([str(lake), "env", "lean", "Verify.lean"], cwd=lean, capture_output=True, text=True,
                       timeout=1200)
    assert v.returncode == 0 and v.stdout.count("depends on axioms") == 2 and "sorryAx" not in v.stdout
    assert man["statuses"]
