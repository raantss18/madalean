"""Submissions to Left to Solve: PREPARED here, sent only by the host's explicit « Envoyer » (D69, D61's GitHub code).

A submission = one Lean file (`proofs/<id>.lean`, `reductions/<id>.R<n>.lean` or `statements/<id>.lean`), its check
(the checker's rules + a fresh strict Lean in the pinned workspace) and the exact plan of GitHub requests:

    POST /repos/lefttosolve2/open-math-agents/forks           (or reuse the fork <login>/open-math-agents)
    GET  /repos/lefttosolve2/open-math-agents/git/ref/heads/main
    POST /repos/<login>/open-math-agents/git/refs             branch oma/<id>
    PUT  /repos/<login>/open-math-agents/contents/<file>      the file, nothing else
    POST /repos/lefttosolve2/open-math-agents/pulls           title <id>, body exactly « Lease / Agent / Model »

The login comes from the saved GitHub key (`GET /user`), never from a page; at send time it is read again and must
be the login the plan was made for. Only a « ready » submission (both checks passed) can be sent, once."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
import threading
import time
from pathlib import Path

from ..brain._util import read_json, write_private
from . import screen

UPSTREAM = "lefttosolve2/open-math-agents"
UPSTREAM_BRANCH = "main"
AGENT = "madalean"
STATES = ("ready", "sent", "merged", "rejected", "expired", "discarded", "failed")
MAX_KEEP = 300


class SubmitError(Exception):
    def __init__(self, code: str, status: int = 409, **params):
        super().__init__(code)
        self.code, self.status, self.params = code, status, params


def file_path(problem_id: str, kind: str, n: int = 1) -> str:
    if kind == "reduction":
        return f"reductions/{problem_id}.R{n}.lean"
    if kind == "statement":
        return f"statements/{problem_id}.lean"
    return f"proofs/{problem_id}.lean"


def branch_name(problem_id: str) -> str:
    return "oma/" + re.sub(r"[^A-Za-z0-9._-]+", "-", problem_id).strip("-.")[:80]


def pr_body(lease: str, model: str) -> str:
    """Exactly three lines (join.txt « Pull request »)."""
    model = re.sub(r"[\r\n]+", " ", model or "unknown").strip()[:120] or "unknown"
    return f"Lease: {lease}\nAgent: {AGENT}\nModel: {model}"


def plan_for(sub: dict, login: str) -> dict:
    if not screen.HANDLE_RE.match(login or ""):
        raise SubmitError("github_login", 409)
    fork, branch = f"{login}/{UPSTREAM.split('/')[1]}", branch_name(sub["problem"])
    return {"id": secrets.token_urlsafe(12), "login": login, "fork": fork, "branch": branch,
            "sha256": hashlib.sha256(sub["file"]["text"].encode()).hexdigest(),
            "requests": [
                {"method": "POST", "url": f"/repos/{UPSTREAM}/forks", "body": {"default_branch_only": True}},
                {"method": "GET", "url": f"/repos/{UPSTREAM}/git/ref/heads/{UPSTREAM_BRANCH}"},
                {"method": "POST", "url": f"/repos/{fork}/git/refs",
                 "body": {"ref": f"refs/heads/{branch}", "sha": "<main de lefttosolve2/open-math-agents>"}},
                {"method": "PUT", "url": f"/repos/{fork}/contents/{sub['file']['path']}",
                 "body": {"message": f"{sub['problem']}", "branch": branch, "content": "<le fichier ci-dessus, base64>"}},
                {"method": "POST", "url": f"/repos/{UPSTREAM}/pulls",
                 "body": {"title": sub["problem"], "head": f"{login}:{branch}", "base": UPSTREAM_BRANCH,
                          "body": pr_body(sub["lease"], sub["model"]), "maintainer_can_modify": True}},
            ]}


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        raw = read_json(path)
        self.items: list[dict] = [x for x in (raw or {}).get("items", []) if isinstance(x, dict)] \
            if isinstance(raw, dict) else []

    def save(self) -> None:
        with self._lock:
            self.items = self.items[-MAX_KEEP:]
            write_private(self.path, json.dumps({"items": self.items}, ensure_ascii=False))

    def get(self, sid: str) -> dict | None:
        return next((x for x in self.items if x["id"] == sid), None)

    def add(self, *, problem: dict, kind: str, text: str, lease: str, model: str, check: dict, dossier_id: str = "",
            login: str = "") -> dict:
        sub = {"id": "s-" + time.strftime("%Y%m%d") + "-" + secrets.token_hex(4), "problem": problem["id"],
               "title": problem.get("title", ""), "kind": kind, "lease": lease, "model": model,
               "file": {"path": file_path(problem["id"], kind), "text": text},
               "check": check_view(check),
               "state": "ready" if check.get("ready") else "failed", "pr_url": "", "created": time.time(),
               "dossier_id": dossier_id, "plan": None}
        if sub["state"] == "ready" and login:
            sub["plan"] = plan_for(sub, login)
        self.items.append(sub)
        self.save()
        return sub

    @staticmethod
    def item(x: dict) -> dict:
        """One submission as the interface reads it (`file = {path, text}`, `plan` with its login)."""
        return dict(x)

    def public(self) -> list[dict]:
        return [self.item(x) for x in reversed(self.items)]


def check_view(check: dict) -> dict:
    """{local, rules, axioms}: each {ok, detail} (axioms: the list in `detail`); `review`: a person must reread
    (the OMA.answer case); `failures`: the failed rules [{rule, ok, detail}]."""
    fails = check.get("rules") or []
    ax = check.get("axioms")
    local = check.get("local") or "not_run"
    summary = str(check.get("summary", ""))
    return {"local": {"ok": local == "ok", "detail": summary if local == "ok" else f"{local} : {summary}"},
            "rules": {"ok": not fails, "detail": "; ".join(f["detail"] for f in fails)},
            "axioms": {"ok": local == "ok" and ax is not None,
                       "detail": ", ".join(ax) if ax else ("aucun" if ax == [] else "non contrôlés")},
            "review": bool(check.get("review")), "failures": fails}


async def github_login(gh) -> str:
    from ..research.publish import gh_failure
    status, data = await gh.call("GET", "/user")
    login = str((data or {}).get("login") or "")
    if status != 200 or not screen.HANDLE_RE.match(login):
        raise gh_failure(gh, status, data, "identity", "")
    return login


async def send(gh, sub: dict, plan_id: str) -> dict:
    """Execute the confirmed plan once. Raises SubmitError / PublishError; the caller stores the result."""
    from ..research.publish import gh_failure
    plan = sub.get("plan") or {}
    if sub.get("state") != "ready" or not plan:
        raise SubmitError("not_ready")
    if not plan_id or plan_id != plan.get("id"):
        raise SubmitError("plan_mismatch")
    if hashlib.sha256(sub["file"]["text"].encode()).hexdigest() != plan["sha256"]:
        raise SubmitError("file_changed")
    login = await github_login(gh)
    if login != plan["login"]:
        raise SubmitError("github_login_changed", 409, login=login, planned=plan["login"])
    fork, branch = plan["fork"], plan["branch"]
    status, data = await gh.call("POST", f"/repos/{UPSTREAM}/forks", {"default_branch_only": True})
    if status not in (200, 202):
        raise gh_failure(gh, status, data, "fork", "")
    if data.get("full_name") and data["full_name"] != fork:
        raise SubmitError("github_fork_name", 409, fork=str(data["full_name"])[:200])
    for _ in range(10):
        status, _d = await gh.call("GET", f"/repos/{fork}")
        if status == 200:
            break
        await asyncio.sleep(2)
    else:
        raise SubmitError("github_fork_pending", 504)
    status, data = await gh.call("GET", f"/repos/{UPSTREAM}/git/ref/heads/{UPSTREAM_BRANCH}")
    sha = ((data or {}).get("object") or {}).get("sha", "")
    if status != 200 or not sha:
        raise gh_failure(gh, status, data, "ref", "")
    status, data = await gh.call("POST", f"/repos/{fork}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})
    if status == 422:
        raise SubmitError("github_branch_exists", 409, branch=branch)
    if status != 201:
        raise gh_failure(gh, status, data, "branch", "")
    content = base64.b64encode(sub["file"]["text"].encode()).decode()
    put = plan["requests"][3]
    status, data = await gh.call("PUT", put["url"], {"message": put["body"]["message"], "content": content,
                                                     "branch": branch})
    if status not in (200, 201):
        raise gh_failure(gh, status, data, "commit", "")
    pr = plan["requests"][4]["body"]
    status, data = await gh.call("POST", f"/repos/{UPSTREAM}/pulls", pr)
    if status != 201:
        raise gh_failure(gh, status, data, "pr", "")
    return {"number": data.get("number"), "url": str(data.get("html_url") or "")[:300]}
