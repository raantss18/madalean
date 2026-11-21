"""« Publier » → GitHub (session S-Q): the token is read from Réglages → Clés (provider "github"), tested read-only
(« Tester la connexion GitHub »), and every refusal names what is missing. Against a FAKE GitHub API: good classic
token, classic token without `workflow`, fine-grained token without the Pages permission, expired token, an organisation
behind SAML SSO and one requiring 2FA. git gets the token through GIT_ASKPASS (never argv, never a URL)."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import subprocess
from pathlib import Path

import pytest
from aiohttp import web

from madalean.research import publish
from helpers import make_ctx, running, session

TOKENS = {
    "ghp_good": {"kind": "classic", "scopes": "repo, workflow", "login": "alice"},
    "ghp_noworkflow": {"kind": "classic", "scopes": "repo", "login": "alice"},
    "github_pat_nopages": {"kind": "fine", "login": "alice", "perms": {"contents", "workflows", "administration"}},
    "ghp_expired": None,
}


def fake_github(state: dict) -> web.Application:
    app = web.Application()

    def who(request):
        tok = request.headers.get("Authorization", "").removeprefix("Bearer ")
        state.setdefault("methods", []).append(request.method)
        return tok, TOKENS.get(tok)

    def base_headers(t):
        h = {"X-RateLimit-Remaining": "4999", "GitHub-Authentication-Token-Expiration": "2027-01-31 10:00:00 UTC"}
        if t and t["kind"] == "classic":
            h["X-OAuth-Scopes"] = t["scopes"]
        return h

    def unauth():
        return web.json_response({"message": "Bad credentials"}, status=401)

    async def user(request):
        tok, t = who(request)
        if not t:
            return unauth()
        return web.json_response({"login": t["login"], "name": "Alice"}, headers=base_headers(t))

    async def org(request):
        tok, t = who(request)
        if not t:
            return unauth()
        o = request.match_info["o"]
        if o == "samlorg":
            return web.json_response({"message": "Resource protected by organization SAML enforcement. You must grant "
                                                 "your Personal Access token access to this organization."},
                                     status=403, headers={**base_headers(t), "X-GitHub-SSO":
                                                          "required; url=https://github.com/orgs/samlorg/sso?"
                                                          "authorization_request=XYZ"})
        if o == "tfaorg":
            return web.json_response({"message": "You must enable two-factor authentication to access this "
                                                 "organization."}, status=403, headers=base_headers(t))
        if o == "goodorg":
            return web.json_response({"login": o}, headers=base_headers(t))
        return web.json_response({"message": "Not Found"}, status=404)

    async def repo(request):
        tok, t = who(request)
        if not t:
            return unauth()
        name = f"{request.match_info['o']}/{request.match_info['r']}"
        if request.match_info["o"] == "samlorg":
            return web.json_response({"message": "Resource protected by organization SAML enforcement."}, status=403,
                                     headers={"X-GitHub-SSO": "required; url=https://github.com/orgs/samlorg/sso"})
        if name in state["repos"]:
            return web.json_response({"full_name": name, "permissions": {"admin": True, "push": True, "pull": True}},
                                     headers=base_headers(t))
        return web.json_response({"message": "Not Found"}, status=404, headers=base_headers(t))

    async def create(request):
        tok, t = who(request)
        if not t:
            return unauth()
        data = await request.json()
        if t["kind"] == "fine" and "administration" not in t["perms"]:
            return web.json_response({"message": "Resource not accessible by personal access token"}, status=403,
                                     headers={"X-Accepted-GitHub-Permissions": "administration=write"})
        state["repos"].add(f"alice/{data['name']}")
        return web.json_response({"full_name": f"alice/{data['name']}"}, status=201)

    async def pages(request):
        tok, t = who(request)
        if not t:
            return unauth()
        name = f"{request.match_info['o']}/{request.match_info['r']}"
        if request.method == "GET":
            p = state["pages"].get(name)
            if t["kind"] == "fine" and "pages" not in t["perms"]:
                return web.json_response({"message": "Resource not accessible by personal access token"}, status=403,
                                         headers={"X-Accepted-GitHub-Permissions": "pages=read"})
            return web.json_response(p) if p else web.json_response({"message": "Not Found"}, status=404)
        if t["kind"] == "fine" and "pages" not in t["perms"]:
            return web.json_response({"message": "Resource not accessible by personal access token"}, status=403,
                                     headers={"X-Accepted-GitHub-Permissions": "pages=write; administration=write"})
        data = await request.json()
        state["pages"][name] = {"build_type": data["build_type"], "html_url": f"https://alice.github.io/{name[6:]}/"}
        return web.json_response(state["pages"][name], status=201)
    app.router.add_get("/user", user)
    app.router.add_get("/orgs/{o}", org)
    app.router.add_get("/repos/{o}/{r}", repo)
    app.router.add_post("/user/repos", create)
    app.router.add_route("*", "/repos/{o}/{r}/pages", pages)
    return app


@contextlib.asynccontextmanager
async def fake_gh(monkeypatch):
    state = {"repos": {"alice/existing"}, "pages": {}}
    runner = web.AppRunner(fake_github(state))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    monkeypatch.setattr(publish, "GITHUB_API", f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}")
    monkeypatch.setattr(publish, "_gh_path", lambda: None)
    yield state
    await runner.cleanup()


def ctx_with(tmp_path, token):
    ctx = make_ctx(tmp_path)
    if token:
        ctx.keys.set("github", token)
    return ctx


async def test_token_source_and_kinds(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "_gh_path", lambda: None)
    ctx = make_ctx(tmp_path)
    with pytest.raises(publish.PublishError) as e:
        publish.github_token(ctx)
    assert e.value.kind == "no_github_credentials"
    ctx.keys.set("github", "  ghp_abc\n")                    # copy-paste whitespace
    assert publish.github_token(ctx) == ("ghp_abc", "keyring")
    assert [publish.token_kind(t) for t in ("ghp_x", "github_pat_x", "gho_x", "zzz")] == \
        ["classic", "fine_grained", "oauth", "unknown"]


async def test_check_good_classic_token(tmp_path, monkeypatch):
    async with fake_gh(monkeypatch) as gh:
        ctx = ctx_with(tmp_path, "ghp_good")
        res = await publish.check(ctx, "alice/existing")
        assert res["ok"] is True and res["login"] == "alice" and res["token_kind"] == "classic"
        by = {c["id"]: c for c in res["checks"]}
        assert by["workflow"]["ok"] and by["create"]["ok"] and by["pages"]["ok"] and by["repo"]["code"] == "repo_ok"
        assert by["expiry"]["params"]["date"].startswith("2027-01-31")
        assert set(gh["methods"]) == {"GET"}                       # read-only: nothing created
        res = await publish.check(ctx, "alice/newone")
        assert {c["id"]: c for c in res["checks"]}["repo"]["code"] == "repo_absent" and res["ok"] is True


async def test_check_reports_missing_scope_expired_sso_2fa(tmp_path, monkeypatch):
    async with fake_gh(monkeypatch) as gh:
        res = await publish.check(ctx_with(tmp_path / "a", "ghp_noworkflow"))
        wf = next(c for c in res["checks"] if c["id"] == "workflow")
        assert res["ok"] is False and wf["ok"] is False and wf["code"] == "scope_missing" and wf["params"]["scope"] == \
            "workflow"
        res = await publish.check(ctx_with(tmp_path / "b", "ghp_expired"))
        assert res["ok"] is False and res["checks"][0]["code"] == "github_token_invalid"
        ctx = ctx_with(tmp_path / "c", "ghp_good")
        res = await publish.check(ctx, "samlorg/site")
        org = next(c for c in res["checks"] if c["id"] == "org")
        assert org["code"] == "github_sso_required" and "samlorg/sso" in org["params"]["url"]
        res = await publish.check(ctx, "tfaorg/site")
        assert next(c for c in res["checks"] if c["id"] == "org")["code"] == "github_2fa_required"
        res = await publish.check(ctx_with(tmp_path / "d", "github_pat_nopages"))
        assert res["token_kind"] == "fine_grained" and res["ok"] is True
        assert all(c["ok"] is None for c in res["checks"] if c["id"] in ("create", "push", "workflow", "pages"))
        res = await publish.check(ctx_with(tmp_path / "e", None))
        assert res["ok"] is False and res["checks"][0]["code"] == "no_token"


def _prepared(ctx, pid="p1"):
    base = publish.pub_dir(ctx, pid)
    (base / "preview").mkdir(parents=True)
    (base / "preview" / "index.html").write_text("<p>site</p>")
    (base / "lean").mkdir()
    (base / "lean" / "lakefile.lean").write_text("-- lake\n")
    return pid


@pytest.fixture
def bare(tmp_path, monkeypatch):
    b = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(b)], check=True)
    monkeypatch.setattr(publish, "git_url", lambda repo: str(b))
    return b


async def test_push_errors_name_what_is_missing(tmp_path, bare, monkeypatch):
    async with fake_gh(monkeypatch) as gh:
        monkeypatch.setattr(publish, "pub_dir", lambda ctx, pid: tmp_path / "pub" / pid)
        # expired token: said so (not « repository not found »)
        ctx = ctx_with(tmp_path / "x", "ghp_expired")
        pid = _prepared(ctx)
        with pytest.raises(publish.PublishError) as e:
            await publish.push(ctx, pid, "alice/site", create=True)
        assert e.value.kind == "github_token_invalid"
        # classic token without `workflow`: refused BEFORE anything is created or pushed
        ctx.keys.set("github", "ghp_noworkflow")
        gh["methods"].clear()
        with pytest.raises(publish.PublishError) as e:
            await publish.push(ctx, pid, "alice/site", create=True)
        assert e.value.kind == "github_scope_missing" and e.value.info["scope"] == "workflow"
        assert "settings/tokens" in e.value.info["settings"] and "POST" not in gh["methods"]
        # SAML organisation
        ctx.keys.set("github", "ghp_good")
        with pytest.raises(publish.PublishError) as e:
            await publish.push(ctx, pid, "samlorg/site", create=True)
        assert e.value.kind == "github_sso_required" and e.value.info["url"].startswith("https://github.com/orgs/samlorg")
        # fine-grained without Pages: the code is pushed, Pages is reported with the permission to add
        ctx.keys.set("github", "github_pat_nopages")
        st = await publish.push(ctx, pid, "alice/site", create=True)
        assert st["created"] and st["changed"] and st["pages"] is False
        assert st["pages_error"]["error"] == "github_permission_missing"
        assert "Pages (Read and write)" in st["pages_error"]["permission"] and st["pages_settings"].endswith(
            "/alice/site/settings/pages")
        # good classic token: Pages enabled
        ctx.keys.set("github", "ghp_good")
        (tmp_path / "pub" / pid / "preview" / "more.html").write_text("x")
        st = await publish.push(ctx, pid, "alice/site")
        assert st["pages"] is True and "pages_error" not in st and st["login"] == "alice"


def test_git_failures_are_classified():
    f = publish._git_failure
    wf = ("remote: refusing to allow a Personal Access Token to create or update workflow "
          "`.github/workflows/verify-and-publish.yml` without `workflow` scope")
    e = f(wf, "push", "classic")
    assert e.kind == "github_scope_missing" and e.info["scope"] == "workflow"
    e = f(wf.replace("without `workflow` scope", "without `workflows` permission"), "push", "fine_grained")
    assert e.kind == "github_permission_missing" and "Workflows" in e.info["permission"]
    assert f("remote: Permission to alice/site.git denied to alice.\nfatal: unable to access: The requested URL "
             "returned error: 403", "push", "fine_grained").info["permission"].startswith("Contents")
    assert f("fatal: Authentication failed for 'https://github.com/a/b.git/'", "fetch", "classic").kind == \
        "github_token_invalid"
    assert f(" ! [rejected]        main -> main (fetch first)", "push", "classic").kind == "git_push_rejected"
    assert f("fatal: something odd", "fetch", "classic").kind == "git_clone_failed"


async def test_git_gets_token_through_askpass_never_argv(tmp_path):
    """A local HTTP server asks for Basic auth: git answers through GIT_ASKPASS with the token from the environment."""
    seen = []

    async def handler(request):
        auth = request.headers.get("Authorization", "")
        seen.append(auth)
        if not auth:
            return web.Response(status=401, headers={"WWW-Authenticate": 'Basic realm="GitHub"'})
        return web.Response(status=404)
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        r = await asyncio.to_thread(publish._git, ["ls-remote", f"http://127.0.0.1:{port}/alice/site.git"],
                                    tmp_path, "ghp_secret_token_123")
    finally:
        await runner.cleanup()
    sent = [base64.b64decode(a.split(" ", 1)[1]).decode() for a in seen if a.startswith("Basic ")]
    assert sent and sent[0] == "x-access-token:ghp_secret_token_123"
    assert "ghp_secret_token_123" not in " ".join(r.args) and "ghp_secret_token_123" not in r.stderr
    assert not list(Path("/tmp").glob("madalean-askpass-*")) or all(
        not (p / "askpass.sh").exists() for p in Path("/tmp").glob("madalean-askpass-*") if os.access(p, os.R_OK))


async def test_github_check_route_and_key_test(tmp_path, monkeypatch):
    async with fake_gh(monkeypatch) as gh:
        ctx = ctx_with(tmp_path, "ghp_good")
        async with running(ctx) as (srv, local, remote):
            async with session() as s:
                async with s.get(local + "/api/research/github/check?repo=alice/existing") as r:
                    assert r.status == 200
                    res = await r.json()
                assert res["ok"] and res["login"] == "alice"
                async with s.get(local + "/api/research/github/check?repo=bad%20name") as r:
                    assert r.status == 400
                # Réglages → Clés « tester » for github: an identity check, never « no model » (the reported bug)
                async with s.post(local + "/api/models/test", json={"provider": "github"}) as r:
                    t = await r.json()
                assert t["ok"] is True and t["login"] == "alice" and t["reason"] == ""
                ctx.keys.set("github", "ghp_expired")
                async with s.post(local + "/api/models/test", json={"provider": "github"}) as r:
                    t = await r.json()
                assert t["ok"] is False and t["reason"] == "github:github_token_invalid"
