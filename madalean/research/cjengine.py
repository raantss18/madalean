"""« Moteur de conjectures » — the guided loop Explore → Recognise → State → Attack → Journal (S-AW, DECISIONS D55,
docs/CONJECTURES.md).

An exploration belongs to a project and is one JSON file (`<config>/research/explore/<project>/<id>.json`): the
question, what was recognised, the experiment (a cell of the project's Calcul notebook « explorations », so the
same kernel, sandbox, approval rule and file as any Calcul cell), the table of data, every pattern tried (kept and
discarded, with the reason), the candidate conjectures with their evidence, and the journal.

Execution boundary (unchanged, docs/SECURITY.md): code reaches a kernel only through the Calcul workbench
(`Workbench.run_cell`, which applies `NotebookStore.may_run`: user code runs; model code only once this exact code
was approved on this host, or with `experiments_auto`) from a device allowed to execute. The engine's own programs
are fixed (`cjcatalog.driver`, `GUESS`): only integers enter them, and they call the experiment's `cj_rows_for`
only after the same `may_run` check. Catalogue experiments are Madalean's deterministic code built from a parsed
request (no free text reaches the code); they are stored as ordinary (non-model) cells.

Nothing here says « true »: a candidate carries the range it was tested on; `proved` only comes from the normal
pipeline (a fresh strict Lean), `refuted` from a counter-example recomputed in a fresh kernel and, when the
candidate has a Lean statement, closed by Lean (`conjectures.negation_file`)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import time
from fractions import Fraction as Fr
from pathlib import Path

from .. import config, leancheck
from ..i18n import language as ui_language, pick
from ..logs import get
from . import cjcatalog as C
from . import cjpatterns as P
from . import cjstate as S
from . import conjectures as cj
from .calcul import CalcError
from .codecat import lean_flavor
from .fetch import effective_mode
from .oeis import Oeis

log = get("explore")
DOC = "explorations"
STEPS = ("explore", "recognise", "state", "attack")
RUN_TIMEOUT = 120.0
PROBE_TIMEOUT = 60.0
HUNT_BUDGET_S = 20.0
MAX_EXPLORATIONS = 200
MAX_TABLE_ROWS = 4000
MAX_JOURNAL = 400
ID_RE = re.compile(r"^x-[0-9a-f]{8}$")

GUESS = r'''
def _madalean_cj_guess(_terms, _num, _den):
    import json as _json
    _out = {"ogf": "", "agrees": None, "ore_algebra": False, "error": ""}
    try:
        from sage.all import CFiniteSequences, QQ, PolynomialRing
        _C = CFiniteSequences(QQ)
        _g = _C.guess([QQ(t) for t in _terms])
        _R = PolynomialRing(QQ, "x")
        _own = _R([QQ(c) for c in _num]) / _R([QQ(c) for c in _den])
        _out["ogf"] = str(_g.ogf())[:400]
        _out["agrees"] = bool(_g.ogf() == _own)
    except Exception as _e:
        _out["error"] = type(_e).__name__ + ": " + str(_e)[:200]
    try:
        import ore_algebra as _oa
        _out["ore_algebra"] = True
    except Exception:
        pass
    print("MADALEAN_CJG " + _json.dumps(_out))
_madalean_cj_guess(%s, %s, %s)
del _madalean_cj_guess
'''


class ExploreError(Exception):
    def __init__(self, kind: str, status: int = 400, **data):
        super().__init__(kind)
        self.kind, self.status, self.data = kind, status, data


def _now() -> float:
    return time.time()


def _text(fr: str, en: str) -> dict:
    return {"fr": fr, "en": en}


# ================================================================ store
class ExploreStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _file(self, pid: str, xid: str) -> Path:
        if not ID_RE.match(xid) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", pid):
            raise ExploreError("not_found", 404)
        return self.root / pid / f"{xid}.json"

    def find(self, xid: str) -> dict | None:
        if not ID_RE.match(xid or ""):
            return None
        for f in self.root.glob(f"*/{xid}.json"):
            data, _bad = config.read_json(f)
            if isinstance(data, dict) and data.get("id") == xid:
                return data
        return None

    def list(self, pid: str) -> list[dict]:
        out = []
        d = self.root / pid
        for f in sorted(d.glob("x-*.json")) if d.is_dir() else []:
            data, _bad = config.read_json(f)
            if isinstance(data, dict) and data.get("id"):
                out.append(data)
        out.sort(key=lambda x: -float(x.get("created", 0)))
        return out

    def save(self, x: dict) -> None:
        x["updated"] = _now()
        f = self._file(x["project_id"], x["id"])
        f.parent.mkdir(parents=True, exist_ok=True)
        config.atomic_write_text(f, json.dumps(x, ensure_ascii=False, indent=1, default=str))

    def delete(self, x: dict) -> None:
        try:
            self._file(x["project_id"], x["id"]).unlink()
        except OSError:
            pass


def new_exploration(pid: str, question: str) -> dict:
    return {"id": "x-" + secrets.token_hex(4), "project_id": pid, "question": question[:4000], "created": _now(),
            "updated": _now(), "language": "", "origin": "", "intent": {}, "cell": None, "code": "", "model": "",
            "steps": {s: {"state": "todo", "error": "", "seconds": 0.0} for s in STEPS},
            "table": None, "oeis": {}, "findings": [], "candidates": [], "journal": [], "lmfdb": "not_queried"}


def journal(x: dict, step: str, kind: str, fr: str, en: str, **data) -> None:
    x["journal"].append({"t": _now(), "step": step, "kind": kind, "fr": fr, "en": en, "data": data})
    del x["journal"][:-MAX_JOURNAL]


def public(x: dict, brief: bool = False) -> dict:
    if brief:
        return {"id": x["id"], "project_id": x["project_id"], "question": x["question"], "created": x["created"],
                "updated": x["updated"], "origin": x["origin"], "steps": {k: v["state"] for k, v in x["steps"].items()},
                "candidates": len([c for c in x["candidates"] if c["status"] != "discarded"]),
                "refuted": len([c for c in x["candidates"] if c["status"] == "refuted"]),
                "summary": (x.get("intent") or {}).get("summary", "")}
    out = dict(x)
    t = x.get("table")
    if t:
        out["table"] = {**t, "rows": t["rows"][:200], "total": len(t["rows"])}
    return out


def table_markdown(table: dict, limit: int = 30) -> str:
    cols = table["columns"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in table["rows"][:limit]:
        lines.append("| " + " | ".join(str(v)[:60] for v in r) + " |")
    if len(table["rows"]) > limit:
        lines.append("| " + " | ".join("…" for _ in cols) + " |")
    return "\n".join(lines)


def journal_markdown(x: dict, lang: str) -> str:
    """The whole exploration as a note: question, data, conjectures with their strength, everything tried."""
    fr = lang == "fr"
    out = [f"# {'Exploration' if fr else 'Exploration'} : {x['question'][:120]}", ""]
    summ = (x.get("intent") or {}).get("summary")
    if summ:
        out += [("Reconnu : " if fr else "Recognised: ") + summ, ""]
    if x.get("table"):
        out += ["## " + ("Données" if fr else "Data"), "", table_markdown(x["table"], 20), ""]
    cands = [c for c in x["candidates"] if c["status"] != "discarded"]
    if cands:
        out += ["## " + ("Conjectures" if fr else "Conjectures"), ""]
        for c in cands:
            out.append(f"- {c['text'][lang]}  \n  *{c['strength'][lang]}*" + (
                f"  \n  **{'Réfutée' if fr else 'Refuted'}** : " + json.dumps(c["counterexample"]["witness"])
                if c.get("counterexample") else ""))
            if c.get("lean") and c.get("lean_ok"):
                out += ["", "  ```lean", *("  " + ln for ln in c["lean"].split("\n")), "  ```"]
        out.append("")
    if x.get("code"):
        out += ["## " + ("Code de l'expérience" if fr else "Experiment code"), "",
                f"```{x.get('language') or 'python'}", x["code"].rstrip(), "```", ""]
    out += ["## " + ("Journal" if fr else "Journal"), ""]
    for e in x["journal"]:
        out.append(f"- {time.strftime('%Y-%m-%d %H:%M', time.localtime(e['t']))} — {e[lang]}")
    return "\n".join(out) + "\n"


# ================================================================ engine
class Engine:
    def __init__(self, ctx, workbench=None, research=None, oeis: Oeis | None = None):
        self.ctx = ctx
        self.store = ExploreStore(ctx.paths.config / "research" / "explore")
        self._wb, self._rs = workbench, research
        self.oeis = oeis or Oeis(cache_dir=ctx.paths.cache / "oeis")
        self.tasks: dict[str, asyncio.Task] = {}
        self.live: dict[str, dict] = {}       # one object per exploration in use (requests and its task share it)

    # the Calcul workbench and the research workshop are other plugins: resolved when used
    def bind(self, workbench, research) -> None:
        self._wb, self._rs = workbench, research

    @property
    def wb(self):
        if self._wb is None:
            raise ExploreError("no_workbench", 503)
        return self._wb

    @property
    def rs(self):
        if self._rs is None:
            raise ExploreError("no_workshop", 503)
        return self._rs

    def get(self, xid: str) -> dict:
        x = self.live.get(xid) or self.store.find(xid)
        if x is None:
            raise ExploreError("not_found", 404)
        self.live[xid] = x
        while len(self.live) > 40:
            old = next(k for k in self.live if not self.running(k) or k == xid)
            if old == xid:
                break
            self.live.pop(old)
        return x

    def delete(self, x: dict) -> None:
        self.live.pop(x["id"], None)
        self.store.delete(x)

    def running(self, xid: str) -> bool:
        t = self.tasks.get(xid)
        return t is not None and not t.done()

    def publish(self, x: dict) -> None:
        self.ctx.publish("explore.updated", {"exploration": public(x), "running": self.running(x["id"])})

    def save(self, x: dict) -> None:
        self.store.save(x)
        self.publish(x)

    def _step(self, x: dict, step: str, state: str, error: str = "", **more) -> None:
        x["steps"][step].update({"state": state, "error": error, **more})
        self.save(x)

    def _flavor(self, pid: str) -> tuple[object, str]:
        p = self.ctx.projects.get(pid)
        ws = self.ctx.workspace((p.workspace if p is not None else "") or self.ctx.settings.workspace)
        return ws, lean_flavor(getattr(ws, "toolchain", "") or "")

    def _mode(self, pid: str) -> str:
        return effective_mode(self.ctx, self.ctx.projects.get(pid))

    async def status(self, pid: str = "") -> dict:
        try:
            avail = await asyncio.to_thread(self.wb.bridge().available)
        except Exception:  # noqa: BLE001
            avail = {}
        mode = self._mode(pid) if pid else getattr(self.ctx.settings, "mode", "auto")
        return {"available": avail, "auto": bool(self.ctx.settings.experiments_auto),
                "remote_allowed": bool(self.ctx.settings.experiments_remote), "demo": bool(self.ctx.demo),
                "oeis": "off" if mode == "local" else "on", "lmfdb": "not_queried", "mode": mode,
                "examples": EXAMPLES}

    # ------------------------------------------------------------ create
    async def _language(self, it: C.Intent, wanted: str) -> str:
        if self.ctx.demo:
            return wanted if wanted in ("sage", "python") else "sage"
        try:
            avail = await asyncio.to_thread(self.wb.bridge().available)
        except Exception:  # noqa: BLE001
            avail = {}
        if wanted in ("sage", "python") and (avail.get(wanted) or not any(avail.values())):
            return wanted
        if avail.get("sage") or not avail.get("python"):
            return "sage"
        return "python"

    async def _doc(self, pid: str, language: str) -> str:
        """The project's notebook of explorations for this language (created on first use)."""
        calc = self.wb.calc
        name = DOC if language == "sage" else f"{DOC}-python"
        docs = await asyncio.to_thread(calc.docs, pid)
        hit = next((d for d in docs if d["id"] == name), None)
        if hit is None:
            title = pick("Explorations (conjectures)", "Explorations (conjectures)") + (
                "" if language == "sage" else " — Python")
            await asyncio.to_thread(calc.create, pid, title, language, name)
        return name

    async def create(self, pid: str, question: str, *, language: str = "", device: str = "") -> dict:
        question = (question or "").strip()
        if not question:
            raise ExploreError("empty")
        if len(self.store.list(pid)) >= MAX_EXPLORATIONS:
            raise ExploreError("too_many", 413)
        lang = ui_language()
        it = await asyncio.to_thread(C.recognise, question)
        x = new_exploration(pid, question)
        x["intent"] = it.to_dict(lang)
        x["language"] = await self._language(it, language)
        if it.kind == "family":
            x["language"] = "sage"
        if it.kind == "data":
            x["origin"] = "data"
            journal(x, "explore", "recognised", f"Suite donnée : {len(it.table['rows'])} termes.",
                    f"Given sequence: {len(it.table['rows'])} terms.")
        elif it.recognised:
            x["origin"] = "catalogue"
            x["code"] = C.experiment_code(it, x["language"], lang)
            journal(x, "explore", "recognised", f"Demande reconnue sans modèle : {it.summary('fr')}.",
                    f"Request recognised without a model: {it.summary('en')}.")
        else:
            x["origin"] = "model"
            journal(x, "explore", "unrecognised", "Demande non reconnue par le catalogue : un modèle écrit le code "
                    "de l'expérience ; il ne s'exécute qu'après votre approbation.",
                    "Request not recognised by the catalogue: a model writes the experiment's code; it runs only "
                    "after your approval.")
            try:
                await self._draft(x)
            except ExploreError as e:
                x["steps"]["explore"].update({"state": "failed", "error": e.kind})
        if x["code"]:
            await self._put_cell(x, device)
        self.live[x["id"]] = x
        self.save(x)
        return x

    async def _draft(self, x: dict) -> None:
        """Model-written experiment (unrecognised request). The code is only stored; nothing runs here."""
        from ..server.helpers import complete_once
        try:
            ans = await complete_once(self.ctx, "assistant", C.model_messages(x["question"], x["language"]),
                                      self.ctx.settings.mode, owner=f"explore-{x['id']}", max_tokens=1500,
                                      temperature=0.0)
        except Exception as e:  # noqa: BLE001
            log.info("explore draft failed: %s", e)
            raise ExploreError("no_model", 503) from e
        from .calcul import extract_code
        code = extract_code(leancheck.clean_model_text(ans.text))
        if not C.contract_ok(code):
            raise ExploreError("no_code", 502)
        x["code"], x["model"] = code.strip() + "\n", ans.model.key
        x["steps"]["explore"].update({"state": "awaiting_approval", "error": ""})

    async def _put_cell(self, x: dict, device: str, by_user: bool = False) -> None:
        """The experiment as a cell of the project's « explorations » notebook: model code keeps the model origin
        (approval needed, by hash, on this host); catalogue and user code are ordinary cells. Calcul's rule for
        edits applies as it is: a model's cell edited by the user stays model code, and its approval is dropped."""
        calc = self.wb.calc
        doc = await self._doc(x["project_id"], x["language"])
        origin = "assistant" if x["origin"] == "model" else "user"
        if x.get("cell"):
            c = await asyncio.to_thread(lambda: calc.edit(x["project_id"], x["cell"]["id"], code=x["code"], doc=doc,
                                                          by="user" if by_user else origin,
                                                          model=x.get("model", "")))
        else:
            title = "## " + x["question"][:200].replace("\n", " ")
            await asyncio.to_thread(lambda: calc.add(x["project_id"], title, "", "user", doc=doc, kind="markdown"))
            c = await asyncio.to_thread(lambda: calc.add(x["project_id"], x["code"], x["language"], origin, doc=doc,
                                                         model=x.get("model", ""), note=x["question"][:500]))
        x["cell"] = {"doc": doc, "id": c["id"], "code_hash": c["code_hash"], "origin": c["origin"]}
        self.ctx.publish("calcul.updated", {"project_id": x["project_id"], "doc": doc, "cell": c})

    async def set_code(self, x: dict, code: str, device: str) -> dict:
        """The user rewrote the experiment. A catalogue experiment becomes the user's code; a model's experiment
        stays model code (Calcul's rule) and needs a new approval of the edited code."""
        if self.running(x["id"]):
            raise ExploreError("busy", 409)
        if not code.strip() or len(code) > 100_000:
            raise ExploreError("bad_code", 422)
        if not C.contract_ok(code):
            raise ExploreError("bad_contract", 422)
        model_cell = x["origin"] == "model" and bool(x.get("cell"))
        x["code"] = code
        if not model_cell:
            x["origin"], x["model"] = "user", ""
        x["intent"] = {**(x.get("intent") or {}), "recognised": False, "kind": "unknown", "sequences": []}
        await self._put_cell(x, device, by_user=True)
        x["steps"]["explore"].update({"state": "awaiting_approval" if model_cell and not await self.may_run(x)
                                      else "todo", "error": ""})
        journal(x, "explore", "edited", "Code de l'expérience modifié à la main.", "Experiment code edited by hand.")
        self.save(x)
        return x

    async def cell_view(self, x: dict) -> dict | None:
        if not x.get("cell"):
            return None
        try:
            return await asyncio.to_thread(self.wb.calc.cell_view, x["project_id"], x["cell"]["doc"], x["cell"]["id"])
        except CalcError:
            return None

    async def may_run(self, x: dict) -> bool:
        """The approval boundary of Calcul, applied to the experiment's cell as it is NOW in the notebook."""
        if x["origin"] == "data":
            return True
        c = await self.cell_view(x)
        return bool(c) and self.wb.calc.may_run(c, bool(self.ctx.settings.experiments_auto))

    # ------------------------------------------------------------ run: explore → recognise → state
    def start(self, x: dict, coro) -> None:
        if self.running(x["id"]):
            raise ExploreError("busy", 409)

        async def guarded():
            try:
                await coro
            except asyncio.CancelledError:
                y = x
                for s in STEPS:
                    if y["steps"][s]["state"] == "running":
                        y["steps"][s]["state"] = "stopped"
                for c in y["candidates"]:
                    if c.get("hunting"):
                        c["hunting"] = False
                journal(y, "run", "stopped", "Arrêté à votre demande.", "Stopped at your request.")
                self.store.save(y)
                raise
            except Exception:  # noqa: BLE001
                log.exception("exploration %s failed", x["id"])
                y = x
                for s in STEPS:
                    if y["steps"][s]["state"] == "running":
                        y["steps"][s].update({"state": "failed", "error": "internal"})
                self.store.save(y)
            finally:
                self.tasks.pop(x["id"], None)
                self.publish(x)
        self.tasks[x["id"]] = self.ctx.spawn(guarded())

    async def stop(self, x: dict) -> None:
        t = self.tasks.get(x["id"])
        if t is not None and not t.done():
            t.cancel()
            if x.get("cell") and not self.ctx.demo:
                try:
                    await self.wb.kernels().interrupt(self.wb.calc.rel_path(x["project_id"], x["cell"]["doc"]))
                except Exception:  # noqa: BLE001
                    pass

    async def run(self, x: dict, device: str) -> None:
        """Explore (data) → Recognise (patterns, OEIS) → State (conjectures + Lean statements). Each step is saved
        and published; a step that cannot go on says why and the loop stops there."""
        t0 = time.monotonic()
        self._step(x, "explore", "running")
        for s in ("recognise", "state", "attack"):
            x["steps"][s].update({"state": "todo", "error": ""})
        try:
            table = await self._explore(x, device)
        except ExploreError as e:
            state = "awaiting_approval" if e.kind == "not_approved" else "failed"
            self._step(x, "explore", state, e.kind, detail=e.data.get("detail", ""))
            return
        x["table"] = table
        n = len(table["rows"])
        journal(x, "explore", "data", f"Données calculées : {n} lignes ({', '.join(table['columns'])}).",
                f"Data computed: {n} rows ({', '.join(table['columns'])}).")
        self._step(x, "explore", "done", seconds=round(time.monotonic() - t0, 2))
        await self._recognise(x)
        await self._state(x)

    async def _explore(self, x: dict, device: str) -> dict:
        it = C.recognise(x["question"]) if x["origin"] in ("catalogue", "data") else None
        if x["origin"] == "data":
            table = dict(it.table)                                            # type: ignore[union-attr]
            await self._data_cell(x, table)
            return table
        if not x.get("cell"):
            raise ExploreError("no_code")
        if not await self.may_run(x):
            raise ExploreError("not_approved", 403)
        pid, doc, cid = x["project_id"], x["cell"]["doc"], x["cell"]["id"]
        if self.ctx.demo:
            # the demo has no kernel: a recognised sequence is computed here by the catalogue's own reference
            # implementation (exact, bounded); anything else needs a real kernel
            if it is None or it.kind != "sequence":
                raise ExploreError("demo_no_kernel", 409)
            d = await asyncio.to_thread(C.local_rows, it, list(range(it.first, it.last + 1)))
            await self._demo_output(x, d)
        else:
            run = await self.wb.run_cell(pid, cid, device, doc, RUN_TIMEOUT)
            if run is None:
                raise ExploreError("calcul_busy", 409)
            if run.get("status") != "ok":
                raise ExploreError("run_failed", 422, detail=str(run.get("error") or run.get("status"))[:1500])
            d = await self._driver(x, None)
        if d is None or d.get("error") or not d.get("rows"):
            raise ExploreError("no_table", 422, detail=(d or {}).get("error", ""))
        table = {"columns": [str(c) for c in d["columns"]][:12], "rows": d["rows"][:MAX_TABLE_ROWS]}
        if it is not None and it.kind == "family":
            table["labels"] = True
        return table

    async def _driver(self, x: dict, indices: list[int] | None, budget: float = HUNT_BUDGET_S) -> dict | None:
        """Read the experiment's table through Madalean's fixed driver, outside the notebook's history. The caller
        checked `may_run`; the notebook's run lock is held here."""
        pid, doc = x["project_id"], x["cell"]["doc"]
        km = self.wb.kernels()
        if not hasattr(km, "probe"):
            return None
        lock = self.wb.lock(f"{pid}/{doc}")
        async with lock:
            res = await km.probe(self.wb.calc.rel_path(pid, doc), x["language"], C.driver(indices, budget),
                                 timeout=PROBE_TIMEOUT + budget)
        if res.status != "ok":
            return {"columns": [], "rows": [], "done": [], "error": res.error or res.status}
        return C.parse_driver(res.stdout)

    async def _demo_output(self, x: dict, d: dict) -> None:
        from .sagebridge import ExecResult
        text = " ".join(d["columns"]) + "\n" + "\n".join(" ".join(r) for r in d["rows"][:30]) + "\n"
        res = ExecResult("ok", language=x["language"], sandbox="demo", execution_count=1,
                         outputs=[{"output_type": "stream", "name": "stdout", "text": text}])
        calc = self.wb.calc
        pid, doc, cid = x["project_id"], x["cell"]["doc"], x["cell"]["id"]
        try:
            up = await asyncio.to_thread(calc.upstream_of, pid, doc, cid)
            run = await asyncio.to_thread(lambda: calc.record_run(pid, cid, res, "host", x["cell"]["code_hash"],
                                                                  doc=doc, upstream=up))
            self.ctx.publish("calcul.updated", {"project_id": pid, "doc": doc, "cell_id": cid, "run": run})
        except CalcError:
            pass

    async def _data_cell(self, x: dict, table: dict) -> None:
        """Given terms: stored as a table in the notebook too (a text cell), nothing to run."""
        if x.get("cell"):
            return
        try:
            lang = "sage"
            doc = await self._doc(x["project_id"], lang)
            calc = self.wb.calc
            body = "## " + x["question"][:200].replace("\n", " ") + "\n\n" + table_markdown(table, 40)
            c = await asyncio.to_thread(lambda: calc.add(x["project_id"], body, "", "user", doc=doc, kind="markdown"))
            x["cell"] = {"doc": doc, "id": c["id"], "code_hash": "", "origin": "user"}
        except (CalcError, ExploreError):
            pass

    def _ctx(self, x: dict) -> S.Ctx:
        _ws, flavor = self._flavor(x["project_id"])
        it = C.recognise(x["question"]) if x["origin"] in ("catalogue", "data") else None
        table = x.get("table") or {"columns": [], "rows": []}
        terms = {c: [str(r[i]) for r in table["rows"][:24] if i < len(r)] for i, c in enumerate(table["columns"])}
        return S.Ctx(it if (it and it.kind in ("sequence", "family")) else None, table["columns"], flavor,
                     x["origin"], terms)

    async def _recognise(self, x: dict) -> None:
        t0 = time.monotonic()
        self._step(x, "recognise", "running")
        table = x["table"]
        findings = await asyncio.to_thread(P.analyze, table)
        ctx = self._ctx(x)
        S.mark_trivial(findings, ctx)
        # Sage's own guesser as a second opinion on a rational generating function (fixed program, numbers only)
        for f in findings:
            if f["kind"] == "recurrence" and f["status"] == "kept" and x["language"] == "sage" and x.get("cell") \
                    and x["cell"].get("code_hash") and not self.ctx.demo:
                f["detail"]["sage"] = await self._sage_guess(x, f)
        x["findings"] = findings
        for f in findings:
            cols = ", ".join(f["columns"])
            nfr, nen = f"{S.kind_name(f['kind'], 'fr')} ({cols})", f"{S.kind_name(f['kind'], 'en')} ({cols})"
            if f["status"] == "kept":
                journal(x, "recognise", "kept", f"Motif retenu : {nfr}.", f"Pattern kept: {nen}.", finding=f)
            else:
                journal(x, "recognise", "discarded",
                        f"Motif écarté : {nfr} — {S.discarded_text(f, 'fr')}.",
                        f"Pattern discarded: {nen} — {S.discarded_text(f, 'en')}.", finding=f)
        x["oeis"] = {}
        mode = self._mode(x["project_id"])
        for seq in P.sequences(table)[:2]:
            if not seq.integral():
                continue
            terms = [int(v) for v in seq.vals]
            r = await self.oeis.lookup(terms, mode=mode, n0=seq.n0)
            if self.ctx.demo and r["status"] == "error":
                r["status"] = "unrecorded"
            x["oeis"][seq.name] = r
            if r["status"] == "off":
                journal(x, "recognise", "oeis_off", "OEIS non interrogé : mode Local (rien ne sort de cet ordinateur).",
                        "OEIS not queried: Local mode (nothing leaves this computer).")
            elif r["status"] == "ok":
                names = ", ".join(m["number"] for m in r["matches"])
                journal(x, "recognise", "oeis", f"OEIS : {seq.name}(n) coïncide avec {names} sur les termes calculés.",
                        f"OEIS: {seq.name}(n) agrees with {names} on the computed terms.")
            elif r["status"] == "none":
                journal(x, "recognise", "oeis_none", f"OEIS : aucune suite ne coïncide avec {seq.name}(n) sur tous "
                        "les termes calculés.", f"OEIS: no sequence agrees with {seq.name}(n) on every computed term.")
            elif r["status"] == "unrecorded":
                journal(x, "recognise", "oeis_demo", "OEIS : démonstration, seule la recherche enregistrée "
                        "(nombres de Catalan) répond.", "OEIS: demo, only the recorded look-up (Catalan numbers) "
                        "answers.")
            elif r["status"] == "error":
                journal(x, "recognise", "oeis_error", "OEIS injoignable : recherche non faite.",
                        "OEIS unreachable: look-up not done.", error=r.get("error", ""))
            for rej in r.get("rejected", [])[:3]:
                journal(x, "recognise", "discarded",
                        f"Suite OEIS écartée : {rej['number']} — diffère au terme n = {rej['differs_at']}.",
                        f"OEIS sequence discarded: {rej['number']} — differs at term n = {rej['differs_at']}.")
        journal(x, "recognise", "lmfdb", "LMFDB non interrogée (pas de recherche par liste de termes dans son API).",
                "LMFDB not queried (its API has no look-up by a list of terms).")
        self._step(x, "recognise", "done", seconds=round(time.monotonic() - t0, 2))

    async def _sage_guess(self, x: dict, f: dict) -> dict:
        seq = next((s for s in P.sequences(x["table"]) if s.name == f["columns"][0]), None)
        if seq is None or not await self.may_run(x):
            return {}
        gf = f["params"]["gf"]
        prog = GUESS % (json.dumps([P.show(v) for v in seq.vals]), json.dumps(gf["num"]), json.dumps(gf["den"]))
        km = self.wb.kernels()
        if not hasattr(km, "probe"):
            return {}
        pid, doc = x["project_id"], x["cell"]["doc"]
        async with self.wb.lock(f"{pid}/{doc}"):
            res = await km.probe(self.wb.calc.rel_path(pid, doc), "sage", prog, timeout=PROBE_TIMEOUT)
        m = re.search(r"MADALEAN_CJG (\{.*\})", res.stdout or "")
        try:
            return json.loads(m.group(1)) if m else {}
        except ValueError:
            return {}

    async def _state(self, x: dict) -> None:
        t0 = time.monotonic()
        self._step(x, "state", "running")
        ctx = self._ctx(x)
        old = {c["norm"]: c for c in x.get("candidates") or []}
        cands = []
        for f in x["findings"]:
            c = S.candidate(f, ctx)
            if c is not None:
                cands.append(c)
        for col, r in (x.get("oeis") or {}).items():
            seq = next((s for s in P.sequences(x["table"]) if s.name == col), None)
            for m in (r.get("matches") or [])[:2]:
                if seq is not None:
                    cands.append(S.oeis_candidate(m, ctx, col, seq.n0, len(seq.vals)))
        seen: set[str] = set()
        cands = [c for c in cands if not (c["norm"] in seen or seen.add(c["norm"]))]
        # the Lean statements must compile (one compilation for all of them); a refused one is shown as such and
        # is never attached to a conjecture
        ws, _flavor = self._flavor(x["project_id"])
        with_lean = [c for c in cands if c["lean"]]
        if with_lean and ws is not None:
            code, spans = S.lean_batch(with_lean, leancheck.GOEDEL_HEADER)
            try:
                r = (await self.ctx.lean.check(code, ws, self.ctx.settings.compile_timeout_s, None,
                                               owner=f"explore-{x['id']}")).to_dict()
            except Exception as e:  # noqa: BLE001
                r = {"errors": [], "timed_out": False, "infra_error": str(e)[:200]}
            byid = {c["id"]: c for c in with_lean}
            for cid, a, b in spans:
                errs = [e for e in r.get("errors", []) if a <= e["line"] <= b]
                c = byid[cid]
                if r.get("timed_out") or r.get("infra_error"):
                    c["lean_ok"], c["lean_error"] = None, "lean_unavailable"
                else:
                    c["lean_ok"] = not errs
                    c["lean_error"] = "\n".join(e["text"][:400] for e in errs[:3])
        self._duplicates(x, cands)
        for c in cands:
            prev = old.get(c["norm"])
            if prev:                                    # a re-run keeps what was done with the candidate
                for k in ("status", "conjecture_id", "counterexample", "hunt"):
                    c[k] = prev.get(k, c[k])
                if c["hunt"]:
                    c["strength"] = S.strength(c["finding"], bool(ctx.family), c["hunt"]) \
                        if c["kind"] != "oeis" else c["strength"]
            else:
                dup = c.get("duplicate_of")
                journal(x, "state", "candidate" if not dup else "duplicate",
                        f"Conjecture candidate : {c['text']['fr']} ({c['strength']['fr']})" +
                        (f" — déjà dans le projet : « {dup['title']} »." if dup else ""),
                        f"Candidate conjecture: {c['text']['en']} ({c['strength']['en']})" +
                        (f" — already in the project: “{dup['title']}”." if dup else ""), candidate=c["id"])
        x["candidates"] = cands
        self._step(x, "state", "done", seconds=round(time.monotonic() - t0, 2))

    def _duplicates(self, x: dict, cands: list[dict]) -> None:
        """Same normalised statement as a conjecture of the project: same engine key, same Lean statement (name
        and spacing aside), or the same words."""
        known = []
        for d in self.ctx.repo.list(x["project_id"]):
            if not cj.is_conjecture(d):
                continue
            c = cj.data_of(d)
            eng = (c.get("origin") or {}).get("engine") or {}
            known.append((d, eng.get("norm", ""), S.norm_lean(d.statement), c.get("statement_nl", "")))
        for c in cands:
            c["duplicate_of"] = None
            nl = S.norm_lean(leancheck.prepare_statement(c["lean"])) if c.get("lean") else ""
            for d, norm, lean, text in known:
                same_text = any(" ".join(text.split()) == " ".join(c["text"][k].split()) for k in ("fr", "en"))
                if (norm and norm == c["norm"]) or (nl and nl == lean) or same_text:
                    c["duplicate_of"] = {"id": d.id, "title": d.title}
                    if not c.get("conjecture_id"):
                        c["conjecture_id"] = d.id
                    break

    # ------------------------------------------------------------ candidates
    def _cand(self, x: dict, cid: str) -> dict:
        c = next((c for c in x["candidates"] if c["id"] == cid), None)
        if c is None:
            raise ExploreError("not_found", 404)
        return c

    async def keep(self, x: dict, cid: str, device: str = "") -> object:
        """Keep a candidate as a conjecture of the project (a dossier of kind `conjecture`, created through the
        conjecture workshop like any other), with its evidence attached. A duplicate returns the existing one."""
        c = self._cand(x, cid)
        if c.get("conjecture_id"):
            d = self.ctx.repo.get(c["conjecture_id"])
            if d is not None:
                return d
        lang = ui_language()
        title = _title(x, c, lang)
        lean = c["lean"] if (c.get("lean") and c.get("lean_ok")) else ""
        st = c["strength"]
        d = await self.rs.workshop.create(
            x["project_id"], c["text"][lang], motivation=pick("Trouvée par le moteur de conjectures", "Found by the "
                                                              "conjecture engine") + f" — {st[lang]}.",
            lean=lean, title=title, device=device,
            origin={"engine": {"exploration": x["id"], "candidate": c["id"], "norm": c["norm"], "kind": c["kind"],
                               "question": x["question"][:500]}})
        t = x.get("table") or {"columns": [], "rows": []}
        cj.add_evidence(
            d, "exploration", {"key": "", "params": {}, "text": pick(
                f"Expérience du moteur de conjectures : {st['fr']}.", f"Conjecture engine experiment: {st['en']}.")},
            verdict="holds", code=x.get("code", ""), language=x.get("language", ""),
            output=table_markdown(t, 40),
            data={"cases": int(st.get("cases", 0)), "range": [st.get("from"), st.get("to")], "strength": st,
                  "finding": c["finding"], "exploration": x["id"], "origin": x["origin"],
                  "heuristic": st.get("kind") == "heuristic"}, model=x.get("model", ""), device=device)
        if c.get("hunt"):
            self._hunt_evidence(d, c, device)
        if c.get("counterexample"):
            self._refute_evidence(d, c, device)
        await self.rs.workshop.save(d)
        c["conjecture_id"] = d.id
        if c["status"] == "candidate":
            c["status"] = "kept"
        journal(x, "state", "kept_conjecture", f"Gardée comme conjecture du projet : « {title} ».",
                f"Kept as a conjecture of the project: “{title}”.", candidate=c["id"], conjecture=d.id)
        self.save(x)
        return d

    def _hunt_evidence(self, d, c: dict, device: str) -> None:
        h = c["hunt"]
        cj.add_evidence(d, "hunt", {"key": "", "params": {}, "text": pick(
            f"Chasse au contre-exemple : aucun trouvé ({h['cases']} cas de plus, jusqu'à n = {h['max']}).",
            f"Counter-example hunt: none found ({h['cases']} more cases, up to n = {h['max']}).")},
            verdict="holds", data={"cases": 0, "hunt": h}, device=device)

    def _refute_evidence(self, d, c: dict, device: str) -> None:
        ce = c["counterexample"]
        w = json.dumps(ce["witness"], ensure_ascii=False)
        verdict = "refuted" if ce["verified"] else "unconfirmed"
        e = cj.add_evidence(d, "counterexample_check", {"key": "", "params": {}, "text": pick(
            f"Contre-exemple {w} : {'vérifié indépendamment' if ce['verified'] else 'non confirmé'}.",
            f"Counter-example {w}: {'independently verified' if ce['verified'] else 'not confirmed'}.")},
            verdict=verdict, code=(ce.get("lean_check") or {}).get("code", ""), language="lean",
            data={"witness": ce["witness"], "kernel": {"fresh": True, "predicate_false": ce["sage"]},
                  "lean": ce.get("lean_check"), "detail": ce.get("detail")}, device=device)
        if ce["verified"]:
            cj.data_of(d)["counterexample"] = {"witness": ce["witness"], "verified": True, "sage": ce["sage"],
                                               "lean": bool(ce["lean"]), "evidence": e["id"], "t": _now()}

    async def discard(self, x: dict, cid: str, reason: str = "") -> dict:
        c = self._cand(x, cid)
        c["status"] = "discarded"
        journal(x, "state", "discarded_by_user", "Candidate écartée par vous" + (f" : {reason[:300]}" if reason else "")
                + f" — {c['text']['fr']}", "Candidate discarded by you" + (f": {reason[:300]}" if reason else "")
                + f" — {c['text']['en']}", candidate=cid)
        self.save(x)
        return x

    async def prove(self, x: dict, cid: str, device: str = "", mode: str = "") -> dict:
        """« Tenter la preuve »: the candidate becomes a conjecture dossier and goes through the normal pipeline
        (formalisation first when it has no accepted Lean statement)."""
        from ..orchestrator import DossierBusy
        c = self._cand(x, cid)
        if c["status"] == "refuted":
            raise ExploreError("refuted", 409)
        d = await self.keep(x, cid, device)
        ok_stmt = bool(d.statement) and d.statements[d.cur_statement].ok
        plan = ([] if ok_stmt else [{"stage": "understand"}, {"stage": "statement"}]) + \
            [{"stage": "proof"}, {"stage": "explanation"}]
        if not ok_stmt and not d.problem:
            d.problem = cj.data_of(d)["statement_nl"]
        opts = {"mode": mode} if mode in ("local", "auto", "online") else {}
        try:
            job = self.ctx.orchestrator.submit(d.id, plan, **opts)
        except DossierBusy as e:
            raise ExploreError("busy", 409, job=e.job.to_dict()) from e
        journal(x, "attack", "prove", f"Preuve tentée par la chaîne normale (dossier « {d.title} »).",
                f"Proof attempted through the normal pipeline (dossier “{d.title}”).", candidate=cid, dossier=d.id)
        self.save(x)
        return {"job": job.to_dict(), "conjecture_id": d.id}

    # ------------------------------------------------------------ attack: the counter-example hunt
    async def attack(self, x: dict, cid: str, device: str) -> None:
        c = self._cand(x, cid)
        t0 = time.monotonic()
        c["hunting"] = True
        self._step(x, "attack", "running", candidate=cid)
        try:
            res = await self._hunt(x, c)
        except ExploreError as e:
            c["hunting"] = False
            self._step(x, "attack", "awaiting_approval" if e.kind == "not_approved" else "failed", e.kind,
                       candidate=cid)
            return
        c["hunting"] = False
        if res.get("skipped"):
            journal(x, "attack", "skipped", f"Chasse impossible : {res['fr']}", f"Hunt not possible: {res['en']}",
                    candidate=cid)
            self._step(x, "attack", "done", res["skipped"], candidate=cid, seconds=round(time.monotonic() - t0, 2))
            return
        if res.get("violation") is None:
            prev = c.get("hunt") or {"cases": 0, "max": 0, "to": 0}
            c["hunt"] = {"cases": prev["cases"] + res["cases"], "to": max(prev.get("to", 0), res["to"]),
                         "max": max(prev.get("max", 0), res["max"]), "sparse": res["sparse"],
                         "seconds": round(time.monotonic() - t0, 2), "t": _now()}
            if c["kind"] != "oeis":
                c["strength"] = S.strength(c["finding"], bool(self._ctx(x).family), c["hunt"])
            else:
                c["strength"]["cases"] += res["cases"]
                c["strength"]["fr"] = f"coïncide sur {c['strength']['cases']} termes, pas démontré"
                c["strength"]["en"] = f"agrees on {c['strength']['cases']} terms, not proved"
            if c["status"] in ("candidate",):
                c["status"] = "survived"
            journal(x, "attack", "survived",
                    f"Chasse au contre-exemple : aucun trouvé ({res['cases']} cas de plus, jusqu'à n = {res['max']}) — "
                    f"{c['text']['fr']}",
                    f"Counter-example hunt: none found ({res['cases']} more cases, up to n = {res['max']}) — "
                    f"{c['text']['en']}", candidate=cid)
            if c.get("conjecture_id"):
                d = self.ctx.repo.get(c["conjecture_id"])
                if d is not None:
                    self._hunt_evidence(d, c, device)
                    await self.rs.workshop.save(d)
        else:
            await self._refute(x, c, res["violation"], device)
        self._step(x, "attack", "done", candidate=cid, seconds=round(time.monotonic() - t0, 2))

    async def _rows(self, x: dict, indices: list[int]) -> dict | None:
        """More rows of the experiment (the same approved code, at other indices)."""
        if self.ctx.demo:
            it = C.recognise(x["question"])
            if it.kind != "sequence":
                return None
            return await asyncio.to_thread(C.local_rows, it, indices)
        if not await self.may_run(x):
            raise ExploreError("not_approved", 403)
        return await self._driver(x, indices)

    async def _hunt(self, x: dict, c: dict) -> dict:
        f, kind = c["finding"], c["kind"]
        table = x.get("table") or {"columns": [], "rows": []}
        if x["origin"] == "data" or not x.get("cell") or not x["cell"].get("code_hash"):
            return {"skipped": "no_code", "fr": "la suite a été donnée terme par terme : ajoutez des termes.",
                    "en": "the sequence was given term by term: add more terms."}
        if f.get("heuristic") or kind in ("algebraic_gf", "growth"):
            return {"skipped": "not_checkable", "fr": "ce motif ne se teste pas terme à terme.",
                    "en": "this pattern cannot be tested term by term."}
        if table.get("labels"):                          # a family of objects: the next sizes, then random samples
            done = sorted({int(r[0]) for r in table["rows"] if str(r[0]).lstrip("-").isdigit()})
            start = max((c.get("hunt") or {}).get("max", 0), done[-1] if done else 1) + 1
            d = await self._rows(x, list(range(start, start + 4)))
            if d is None or d.get("error") or not d.get("rows"):
                raise ExploreError("no_table", 422, detail=(d or {}).get("error", ""))
            more = {"columns": table["columns"], "rows": d["rows"], "labels": True}
            cases, bad = P.check_rows(f, more)
            top = max(d.get("done") or [start])
            return {"cases": cases, "violation": bad, "to": top, "max": top, "sparse": top > start}
        t = f.get("tested") or {}
        lo = max(int(t.get("to", 0)), int((c.get("hunt") or {}).get("to", 0))) + 1
        span = max(200, 4 * (int(t.get("to", 0)) - int(t.get("from", 0)) + 1))
        hi = min(lo + span, 200_000)
        seed = int(hashlib.sha256((c["norm"] + str(lo)).encode()).hexdigest()[:8], 16)
        if kind == "oeis":
            data = self._oeis_data(x, c)
            back = int(f["params"].get("shift", 0)) - int(data["offset"])
            idx = [n for n in range(lo, lo + 400) if 0 <= n + back < len(data["data"])]
            if not idx:
                return {"skipped": "no_more_terms", "fr": "l'OEIS ne liste pas d'autres termes à comparer.",
                        "en": "the OEIS lists no further terms to compare."}
        elif kind == "multiplicative":
            idx = P.hunt_indices(kind, f.get("params") or {}, lo, min(hi, 20_000), seed)
        else:
            idx = P.hunt_indices(kind, f.get("params") or {}, lo, hi, seed)
        d = await self._rows(x, idx)
        if d is None or d.get("error") or not d.get("rows"):
            raise ExploreError("no_table", 422, detail=(d or {}).get("error", ""))
        cols = [str(k) for k in d["columns"]]
        values: dict[str, dict[int, Fr]] = {k: {} for k in cols[1:]}
        for r in d["rows"]:
            n = P.parse_value(r[0])
            if n is None:
                continue
            for i, k in enumerate(cols[1:], 1):
                v = P.parse_value(r[i]) if i < len(r) else None
                if v is not None:
                    values[k][int(n)] = v
        if kind == "multiplicative":                    # needs a(m), a(n) below the new range too
            for s in P.sequences(table):
                for i, v in enumerate(s.vals):
                    values.setdefault(s.name, {}).setdefault(s.n0 + i, v)
        done = sorted(d.get("done") or [])
        contiguous = lo - 1
        for n in done:
            if n == contiguous + 1:
                contiguous = n
        if kind == "oeis":
            col, data = f["columns"][0], self._oeis_data(x, c)
            cases, bad = 0, None
            for n in sorted(values.get(col, {})):
                p = n + int(f["params"].get("shift", 0)) - int(data["offset"])
                if 0 <= p < len(data["data"]):
                    cases += 1
                    if values[col][n] != data["data"][p]:
                        bad = {"n": n, "expected": str(data["data"][p]), "got": P.show(values[col][n])}
                        break
        else:
            cases, bad = P.check(f, values)
        return {"cases": cases, "violation": bad, "to": contiguous, "max": max(done or [lo]),
                "sparse": bool(done) and max(done) > contiguous}

    def _oeis_data(self, x: dict, c: dict) -> dict:
        """The full listed terms of the matched OEIS entry (from the cache; no new request)."""
        num = c["finding"]["params"]["number"]
        for r in (x.get("oeis") or {}).values():
            url = r.get("url", "")
            for e in self.oeis._cached(url) or []:
                if e["number"] == num:
                    return e
        return {"offset": 0, "data": []}

    async def _refute(self, x: dict, c: dict, bad: dict, device: str) -> None:
        """A violation found by the hunt is believed only once recomputed independently (a FRESH kernel, the same
        approved code) and — when the candidate has a Lean statement — closed by Lean at the witness."""
        f, kind = c["finding"], c["kind"]
        witness = {"m": bad["m"], "n": bad["n"]} if kind == "multiplicative" else (
            {"n": int(bad["n"]) - int(c.get("shift", 0))} if "n" in bad else {})
        need = sorted({int(v) for v in bad.values() if isinstance(v, int)} | (
            {bad["m"] * bad["n"]} if kind == "multiplicative" else set()))
        if "n" in bad and kind in ("recurrence", "holonomic", "increasing", "periodic", "residue_periodic"):
            w = int(f.get("params", {}).get("order") or f.get("params", {}).get("period") or 1)
            need = list(range(int(bad["n"]) - w, int(bad["n"]) + w + 1))
        sage_ok = False
        if x.get("table", {}).get("labels"):
            sage_ok = True                                 # objects are listed with their invariants (graph6 kept)
        elif self.ctx.demo:
            d = await self._rows(x, [n for n in need if n >= 0])
            sage_ok = self._still_false(x, c, d)
        else:
            code = x["code"] + "\n" + C.driver([n for n in need if n >= 0], 30.0)
            res = await self.rs.bridge.run(f"explore-{x['id']}", x["language"], code, timeout=180, fresh=True)
            sage_ok = self._still_false(x, c, C.parse_driver(res.stdout))
        lean_check, lean_ok = None, None
        if c.get("lean") and c.get("lean_ok") and witness:
            ws, _fl = self._flavor(x["project_id"])
            if ws is not None:
                try:
                    code = cj.negation_file(leancheck.prepare_statement(c["lean"]), witness)
                    r = (await self.ctx.lean.check(code, ws, self.ctx.settings.compile_timeout_s, None,
                                                   owner=f"explore-{x['id']}")).to_dict()
                    lean_ok = bool(r["statement_ok"] and not r["has_sorry"])
                    lean_check = {"ok": lean_ok, "code": code, "errors": [e["text"][:300] for e in r["errors"][:3]]}
                except cj.ConjectureError as e:
                    lean_check = {"ok": False, "unsupported": True, "error": e.kind}
        verified = sage_ok and (lean_ok is True or lean_check is None or bool(lean_check.get("unsupported")))
        c["counterexample"] = {"witness": witness or bad, "detail": bad, "sage": sage_ok, "lean": lean_ok,
                               "lean_check": lean_check, "verified": verified, "t": _now()}
        c["status"] = "refuted" if verified else "disputed"
        w = json.dumps(witness or bad, ensure_ascii=False)
        if verified:
            journal(x, "attack", "refuted", f"Réfutée : contre-exemple {w} recalculé dans un noyau neuf" +
                    (" et vérifié par Lean" if lean_ok else "") + f" — {c['text']['fr']}",
                    f"Refuted: counter-example {w} recomputed in a fresh kernel" +
                    (" and checked by Lean" if lean_ok else "") + f" — {c['text']['en']}", candidate=c["id"])
        else:
            journal(x, "attack", "disputed", f"Contre-exemple {w} trouvé mais non confirmé (" +
                    ("recalcul différent" if not sage_ok else "Lean n'a pas pu le vérifier") + ").",
                    f"Counter-example {w} found but not confirmed (" +
                    ("the recomputation differs" if not sage_ok else "Lean could not check it") + ").",
                    candidate=c["id"])
        # a refuted conjecture is kept, with its counter-example
        try:
            d = await self.keep(x, c["id"], device)
            if not any(e["kind"] == "counterexample_check" and e["data"].get("witness") == (witness or bad)
                       for e in cj.data_of(d)["evidence"]):
                self._refute_evidence(d, c, device)
            await self.rs.workshop.save(d)
        except (ExploreError, cj.ConjectureError, leancheck.StatementError) as e:
            log.info("refuted candidate not stored as a conjecture: %s", e)

    def _still_false(self, x: dict, c: dict, d: dict | None) -> bool:
        if not d or d.get("error") or not d.get("rows"):
            return False
        cols = [str(k) for k in d["columns"]]
        values: dict[str, dict[int, Fr]] = {k: {} for k in cols[1:]}
        for r in d["rows"]:
            n = P.parse_value(r[0])
            for i, k in enumerate(cols[1:], 1):
                v = P.parse_value(r[i]) if i < len(r) else None
                if n is not None and v is not None:
                    values[k][int(n)] = v
        if c["kind"] == "oeis":
            data = self._oeis_data(x, c)
            col = c["finding"]["columns"][0]
            for n, v in values.get(col, {}).items():
                p = n + int(c["finding"]["params"].get("shift", 0)) - int(data["offset"])
                if 0 <= p < len(data["data"]) and v != data["data"][p]:
                    return True
            return False
        _cases, bad = P.check(c["finding"], values)
        return bad is not None

    # ------------------------------------------------------------ export
    async def export(self, x: dict, to: str, device: str = "") -> dict:
        lang = ui_language()
        md = journal_markdown(x, lang)
        title = pick("Exploration : ", "Exploration: ") + x["question"][:80]
        if to == "note":
            n = await asyncio.to_thread(lambda: self.rs.notes.create(x["project_id"], title, md, ["conjectures"],
                                                                      device=device))
            journal(x, "journal", "exported", "Journal exporté vers une note.", "Journal exported to a note.",
                    note=n.id)
            self.save(x)
            return {"note_id": n.id}
        if to == "article":
            from . import article as art_mod
            from . import texproject as tp
            cands = [c for c in x["candidates"] if c["status"] in ("kept", "survived", "candidate", "refuted")]
            if not cands:
                raise ExploreError("nothing_to_export", 409)
            if await asyncio.to_thread(tp.exists, self.ctx, x["project_id"]):
                body = "\n\n".join("\\paragraph{" + ("Conjecture réfutée" if c["status"] == "refuted" else
                                                    "Conjecture") + ".} " + c["text"][lang] + " \\emph{(" +
                                   tp.texio_plain(c["strength"][lang]) + ")}" for c in cands)
            else:
                body = "\n\n".join(f"**{'Conjecture réfutée' if c['status'] == 'refuted' else 'Conjecture'}.** "
                                   f"{c['text'][lang]} *({c['strength'][lang]})*" for c in cands)
            art = await asyncio.to_thread(art_mod.load, self.ctx, x["project_id"])
            art["blocks"].append(art_mod.new_block("prose", title, body, "user"))
            await asyncio.to_thread(art_mod.save, self.ctx, x["project_id"], art)
            self.ctx.publish("article.updated", {"project_id": x["project_id"]})
            journal(x, "journal", "exported", "Conjectures exportées vers l'article.",
                    "Conjectures exported to the article.")
            self.save(x)
            return {"article": True}
        raise ExploreError("bad_fields")

    async def close(self) -> None:
        for t in list(self.tasks.values()):
            t.cancel()
        try:
            await self.oeis.close()
        except Exception:  # noqa: BLE001
            pass


def _title(x: dict, c: dict, lang: str) -> str:
    name = S.kind_name(c["kind"], lang)
    return f"{name[:1].upper()}{name[1:]} — {x['question'][:70]}"[:200]


EXAMPLES = [
    {"fr": "la somme des n premiers nombres impairs", "en": "the sum of the first n odd numbers"},
    {"fr": "1, 1, 2, 5, 14, 42, 132, 429, 1430, 4862, 16796, 58786, 208012, 742900",
     "en": "1, 1, 2, 5, 14, 42, 132, 429, 1430, 4862, 16796, 58786, 208012, 742900"},
    {"fr": "n^2 + n + 41 jusqu'à 30", "en": "n^2 + n + 41 up to 30"},
    {"fr": "les sommes des carrés des diviseurs", "en": "the sum of the squares of the divisors"},
    {"fr": "graphes connexes à n sommets", "en": "connected graphs on n vertices"},
]
