"""HTTP client of the Left to Solve desk (join.txt « WITHOUT tools/oma.sh », read 2026-11-28).

- One request at a time and at least `MIN_INTERVAL` (3 s) between two requests (« BE GENTLE WITH THE DESK »).
- Handle = the GitHub login of the key saved in Réglages → Clés (`GET /user`), never a value read from a page.
- Every answer is data: screened (screen.py) and bounded before anyone reads it.
- Statuses: 409 proof_pending (take another problem), 410 on beat (stop: settled), 503 busy (retry later; a
  proof that passes the checker never depends on the desk), `degraded: true` (beat / note / release store nothing:
  notes go into the pull request body), 501 not_enabled_yet for the board."""
from __future__ import annotations

import asyncio
import time
from urllib.parse import quote, urlencode

from . import screen

BASE = "https://lefttosolve.com"
MIN_INTERVAL = 3.0
TIMEOUT = 45
MAX_BYTES = 2_000_000
AGENT = "madalean"
RELEASE_REASONS = ("submitted", "out_of_time", "statement_seems_false", "missing_lemma", "does_not_elaborate",
                   "too_hard", "other", "reduced")
NOTE_PREFIXES = ("PLAN:", "TAKING:", "DONE:", "DEAD END:")
KINDS = ("known", "open", "warmup", "any", "step", "formalize", "impact")


class DeskError(Exception):
    """code: proof_pending | settled | busy | not_enabled | bad_answer | unreachable | refused | http_<n>"""

    def __init__(self, code: str, status: int = 0, detail: str = ""):
        super().__init__(f"{code} ({status}) {detail}".strip())
        self.code, self.status, self.detail = code, status, detail[:300]


class Desk:
    def __init__(self, handle: str, base: str = BASE, min_interval: float = MIN_INTERVAL, agent: str = AGENT):
        if not screen.HANDLE_RE.match(handle or ""):
            raise DeskError("refused", 0, "no valid GitHub handle")
        self.handle, self.base, self.min_interval, self.agent = handle, base.rstrip("/"), min_interval, agent
        self._lock = asyncio.Lock()
        self._last = 0.0
        self.requests = 0

    async def _req(self, method: str, path: str, params: dict | None = None, body: str | None = None,
                   want: str = "json"):
        import aiohttp
        q = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        url = self.base + path + ("?" + urlencode(q) if q else "")
        async with self._lock:                                   # one at a time, ≥ min_interval apart
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                async with aiohttp.ClientSession(trust_env=False, cookie_jar=aiohttp.DummyCookieJar()) as s:
                    async with s.request(method, url, data=body.encode() if body is not None else None,
                                         headers={"User-Agent": "Madalean (attack)",
                                                  **({"Content-Type": "text/plain; charset=utf-8"} if body else {})},
                                         allow_redirects=False, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
                        # read to the end: one read() returns one network chunk, not the whole answer (live run
                        # 2026-11-28: problem records cut in the middle → « bad_answer »)
                        raw = b""
                        async for part in r.content.iter_chunked(65536):
                            raw += part
                            if len(raw) > MAX_BYTES:
                                break
                        status = r.status
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                raise DeskError("unreachable", 0, type(e).__name__) from None
            finally:
                self._last = time.monotonic()
                self.requests += 1
        if len(raw) > MAX_BYTES:
            raise DeskError("bad_answer", status, "too large")
        text = raw.decode("utf-8", "replace")
        if want == "text":
            return status, text
        import json
        try:
            data = json.loads(text) if text.strip() else {}
        except ValueError:
            data = {"text": text[:500]}
        return status, data if isinstance(data, dict) else {"items": data}

    @staticmethod
    def _raise(status: int, data: dict, op: str) -> None:
        err = str((data or {}).get("error") or (data or {}).get("code") or "")
        if status == 409:
            raise DeskError("proof_pending" if "pending" in err or op == "next" else "conflict", 409, err)
        if status == 410:
            raise DeskError("settled", 410, err)
        if status == 503:
            raise DeskError("busy", 503, err)
        if status == 501:
            raise DeskError("not_enabled", 501, err)
        if status >= 400:
            raise DeskError(f"http_{status}", status, err)

    # ---------------------------------------------------------------- the desk
    async def next(self, *, problem: str = "", kind: str = "", level: str = "", exact: bool = True) -> dict:
        """Take a lease. The live event is opted out (event=0): Madalean chooses its own problems."""
        if problem and not screen.valid_id(problem):
            raise DeskError("refused", 0, "bad problem id")
        params = {"handle": self.handle, "agent": self.agent, "kind": kind if kind in KINDS else "",
                  "level": level if level in ("warmup", "solid", "hard", "legendary") else "",
                  "problem": problem, "exact": "1" if problem and exact else "", "event": "0"}
        status, data = await self._req("GET", "/api/desk/next", params)
        self._raise(status, data, "next")
        lease = str(data.get("lease") or "")
        if not screen.LEASE_RE.match(lease):
            raise DeskError("bad_answer", status, "no lease")
        prob = data.get("problem")
        if isinstance(prob, str):
            prob = {"id": prob}
        prob = dict(prob or {})
        for k in ("skeleton", "disproofSkeleton", "reductionSkeleton", "file"):
            if k in data and k not in prob:
                prob[k] = data[k]
        if "proofFile" not in prob and isinstance(data.get("file"), str):
            prob["proofFile"] = data["file"]
        p = screen.problem(prob)
        if p is None:
            raise DeskError("bad_answer", status, "no problem")
        notes = [n for n in (screen.note(x) for x in (data.get("teamNotes") or [])[:40]) if n]
        return {"lease": lease, "problem": p, "role": screen.clean(data.get("role"), 20, True),
                "roleTask": screen.clean(data.get("roleTask"), 600), "notes": notes,
                "last_note": screen.clean(data.get("lastNote") or data.get("last_note"), 40, True),
                "degraded": bool(data.get("degraded")) or lease.startswith("offline-")}

    async def beat(self, lease: str, since: str = "") -> dict:
        status, data = await self._req("POST", "/api/desk/beat", {"lease": lease, "since": since})
        self._raise(status, data, "beat")
        notes = [n for n in (screen.note(x) for x in (data.get("notes") or [])[:40]) if n]
        stop = str(data.get("stop") or data.get("action") or "").upper() == "STOP" or data.get("stop") is True
        return {"role": screen.clean(data.get("role"), 20, True), "notes": notes, "stop": stop,
                "last_note": screen.clean(data.get("last_note") or data.get("lastNote") or since, 40, True)}

    async def release(self, lease: str, reason: str) -> None:
        if reason not in RELEASE_REASONS:
            reason = "other"
        status, data = await self._req("POST", "/api/desk/release", {"lease": lease, "reason": reason})
        if status not in (404, 410):              # already gone: nothing to hand back
            self._raise(status, data, "release")

    async def note(self, lease: str, text: str) -> None:
        if not text.startswith(NOTE_PREFIXES) or not 20 <= len(text) <= 4000:
            raise DeskError("refused", 0, "note shape")
        status, data = await self._req("POST", "/api/desk/note", {"lease": lease}, body=text)
        self._raise(status, data, "note")

    async def board(self, problem: str, since: str = "") -> dict:
        status, data = await self._req("GET", "/api/desk/board", {"problem": problem, "since": since})
        self._raise(status, data, "board")
        items = []
        for it in (data.get("items") or data.get("board") or [])[:60]:
            if isinstance(it, dict):
                items.append({"k": it.get("k") if isinstance(it.get("k"), int) else None,
                              "state": screen.clean(it.get("state"), 10, True),
                              "text": screen.clean(it.get("text") or it.get("lemma"), 1000),
                              "suspect": screen.suspect(str(it.get("text") or ""))})
        return {"items": items, "notes": [n for n in (screen.note(x) for x in (data.get("notes") or [])[:40]) if n]}

    # ---------------------------------------------------------------- public pages (no lease)
    async def problems(self, *, kind: str = "", sort: str = "easiest", limit: int = 50, offset: int = 0,
                       q: str = "") -> dict:
        status, data = await self._req("GET", "/api/problems", {
            "kind": kind if kind in KINDS else "", "sort": sort if sort in ("hardest", "easiest", "prize", "active") else "",
            "limit": max(1, min(int(limit), 100)), "offset": max(0, int(offset)), "q": q[:100]})
        self._raise(status, data, "problems")
        up = data.get("upstream") if isinstance(data.get("upstream"), dict) else {}
        commit = str(up.get("commit") or "")
        return {"total": data.get("total") if isinstance(data.get("total"), int) else 0,
                "commit": commit if len(commit) == 40 and all(c in "0123456789abcdef" for c in commit) else "",
                "items": [p for p in (screen.problem(x) for x in (data.get("items") or [])[:100]) if p]}

    async def problem(self, pid: str) -> dict:
        if not screen.valid_id(pid):
            raise DeskError("refused", 0, "bad problem id")
        status, data = await self._req("GET", "/api/problems/" + quote(pid, safe="._-"))
        self._raise(status, data, "problem")
        p = screen.problem(data)
        if p is None:
            raise DeskError("bad_answer", status, "problem")
        return p

    async def brief(self, pid: str) -> str:
        if not screen.valid_id(pid):
            raise DeskError("refused", 0, "bad problem id")
        status, text = await self._req("GET", "/p/" + quote(pid, safe="._-") + "/agent.txt", want="text")
        if status != 200:
            raise DeskError(f"http_{status}", status, "brief")
        return screen.clean(text, screen.LIMITS["brief"])
