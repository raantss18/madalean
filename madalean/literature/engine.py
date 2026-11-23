"""`search(statement, ctx, budget)`: the literature-first search (DECISIONS D56, docs/LITERATURE.md).

Phases, each run ONCE (no loop, no recursion — a cited lemma's own dossier never searches the literature again):
1. query plan (deterministic; + a few keywords from a free model when the budget allows);
2. retrieval in parallel: zbMATH Open, OpenAlex, arXiv (network, never in Local mode), the user's Sources and the
   Mathlib index (local), merged by work;
3. confirmation of DOIs by Crossref (venue → peer-reviewed / preprint), dropping what does not resolve;
4. verbatim quotes: candidate passages cut from the retrieved texts by rules, optionally picked by a model among
   numbered ids, every quote string-matched against its text;
5. formalization of the best quotes (free models, Lean-checked), Mathlib / library status.
A failing provider is reported, never fatal. The budget (time, requests, model calls, Lean checks) is checked before
each step; `budget.cancel()` stops at the next step and returns what was found so far."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Callable

from ..logs import get
from ..research import biblio
from ..research.fetch import FetchError
from . import formal, query as QP, quotes as Q, retrieve as R
from .types import Budget, LiteratureItem, LiteratureResult, Quote, item_id

log = get("literature")

PER_QUERY = 6
MIN_SCORE = 1.0                   # a quote must state a result AND share a keyword, or share two keywords
CACHE_KIND = "literature"
CACHE_DAYS = 30
PICK_PROMPT = (
    "You help a mathematician find, in published texts, the passages that state a result related to the statement "
    "below. Candidate passages are given as data, each with an id P1, P2, …\n{rule}\n\nStatement (Lean 4):\n{lean}\n"
    "\nIn words: {text}\n\n{cands}\n\nAnswer ONLY with a JSON list of the ids of at most {k} passages that STATE a "
    "result directly useful for this statement (a theorem, a lemma, a bound), most useful first. Use only the ids "
    "above; never write a passage yourself. Answer [] when none fits.")


def _emit(on_event: Callable | None, step: str, **kw) -> None:
    if on_event is not None:
        try:
            on_event(step, kw)
        except Exception:  # noqa: BLE001
            log.exception("literature progress callback")


async def _extra_keywords(io: formal.LitIO, plan, statement: str, text: str) -> list[str]:
    if io.budget.over or not io.free_models("understand"):
        return []
    from ..brain import classify
    prompt = QP.KEYWORDS_PROMPT.format(n=QP.MAX_EXTRA, lean=formal._decl_only(statement)[:1500] or statement[:1500],
                                       text=(text or "")[:800])
    try:
        with classify.short_stage():
            c = await io.complete("understand", [{"role": "user", "content": prompt}], temperature=0.2,
                                  max_tokens=200)
    except Exception as e:  # noqa: BLE001 (no free model / budget: the deterministic keywords are enough)
        log.info("extra keywords: %s", e)
        return []
    return QP.parse_extra(c.text, plan.keywords)


async def _retrieve(ctx, fetcher, plan, mode: str, budget: Budget, project_id: str, ws_key: str, n: int,
                    providers: dict) -> tuple[list[R.Record], list[dict]]:
    tasks: dict[str, asyncio.Future] = {}
    queries = plan.queries or [" ".join(plan.keywords[:4])]
    if mode != "local" and fetcher is not None and queries and queries[0].strip():
        for name in ("zbmath", "openalex", "arxiv"):
            g = R.Guarded(fetcher, budget, name)
            # zbMATH and OpenAlex get the two most specific queries, arXiv the first (3 s between arXiv calls)
            qs = queries[:1] if name == "arxiv" else queries[:2]
            tasks[name] = asyncio.ensure_future(_provider(name, g, qs, mode, n, providers))
    local_q = " ".join((plan.keywords + plan.extra_keywords)[:6])
    tasks["sources"] = asyncio.ensure_future(R.local_sources(ctx, project_id, local_q, k=4)) if local_q else None
    ml = asyncio.ensure_future(R.mathlib_related(ctx, ws_key, queries + [local_q])) if ws_key else None
    lists: list[list[R.Record]] = []
    for name, t in tasks.items():
        if t is None:
            continue
        try:
            recs = await asyncio.wait_for(t, max(1.0, budget.left()))
        except asyncio.TimeoutError:
            providers[name] = {"ok": False, "count": 0, "error": "timeout"}
            continue
        if name == "sources":
            providers["sources"] = {"ok": True, "count": len(recs), "error": ""}
        lists.append(recs)
    mathlib = []
    if ml is not None:
        try:
            mathlib = await asyncio.wait_for(ml, max(1.0, min(20.0, budget.left())))
        except asyncio.TimeoutError:
            mathlib = []
    return R.merge(lists), mathlib


async def _provider(name: str, g: R.Guarded, qs: list[str], mode: str, n: int, providers: dict) -> list[R.Record]:
    out: list[R.Record] = []
    err = ""
    for q in qs:
        try:
            out.extend(await R.SEARCHERS[name](g, q, mode, n))
        except FetchError as e:
            if e.kind == "local_mode":
                raise
            err = e.kind if not e.status else f"{e.kind}:{e.status}"
            if e.kind == "budget":
                break
        except asyncio.TimeoutError:
            err = "timeout"
        except Exception as e:  # noqa: BLE001 (a provider changing its format must not break the others)
            err = f"parse:{type(e).__name__}"
    providers[name] = {"ok": bool(out) or not err, "count": len(out), "error": err, "requests": len(g.urls)}
    return out


def _same_title(a: R.Record, b: R.Record) -> bool:
    ta, tb = biblio.norm_title(a.csl.get("title", "")), biblio.norm_title(b.csl.get("title", ""))
    return len(ta) >= 12 and ta == tb and biblio.first_family(a.csl) == biblio.first_family(b.csl)


def _dedupe(top: list) -> list:
    """After the DOI confirmation: a preprint and its journal version (other DOI, same title and first author) are
    one work; the published record leads, the arXiv id and every retrieved text are kept."""
    out: list = []
    for score, matched, rec in top:
        tgt = next((x for x in out if biblio.same_work(x[2].csl, rec.csl) or _same_title(x[2], rec)), None)
        if tgt is None:
            out.append([score, matched, rec])
            continue
        lead, other = tgt[2], rec
        if R.classify(other)[1] and not R.classify(lead)[1]:
            lead, other = other, lead
        lead.csl = litsearch_merge(lead.csl, other.csl)
        for p, rank in other.providers.items():
            lead.providers.setdefault(p, rank)
        for t in other.texts:
            if not any(t.text == x.text for x in lead.texts):
                lead.texts.append(t)
        lead.crossref_type = lead.crossref_type or other.crossref_type
        lead.zb_type = lead.zb_type or other.zb_type
        tgt[0], tgt[1], tgt[2] = max(tgt[0], score), list(dict.fromkeys(tgt[1] + matched)), lead
    return [tuple(x) for x in out]


def litsearch_merge(a: dict, b: dict) -> dict:
    from ..research.litsearch import _merge_item
    out = _merge_item(a, b)
    if a.get("DOI"):
        out["DOI"] = a["DOI"]
    return out


def _score(rec: R.Record, keywords: list[str]) -> tuple[float, list[str]]:
    title = biblio.norm_title(rec.csl.get("title", ""))
    body = " ".join(t.text.lower() for t in rec.texts)[:8000]
    matched = []
    for k in keywords:
        words = [w for w in biblio.norm_title(k).split() if len(w) > 2]
        if words and all(w in title or w in body for w in words):
            matched.append(k)
    rrf = sum(1.0 / (10 + r) for r in rec.providers.values())
    title_hits = sum(1 for k in matched if all(w in title for w in biblio.norm_title(k).split()))
    return len(matched) + 0.5 * title_hits + 3 * rrf, matched


def _quotes(item: LiteratureItem, keywords: list[str], lang: str) -> list[dict]:
    """Candidate passages of every text of an item (not yet verified)."""
    out = []
    for ti, t in enumerate(item.texts):
        for c in Q.candidates(t.text, keywords, limit=4):
            c["text_index"] = ti
            c["location"] = Q.location(t.kind, c["sentence"] if t.kind != "fulltext" else 0, t.locator, t.page, lang)
            if t.kind == "fulltext":
                c["score"] += 1.0                      # a theorem of the paper itself beats a summary of it
            out.append(c)
    out.sort(key=lambda c: -c["score"])
    return out


def _accept_quote(item: LiteratureItem, cand: dict, picked_by: str, rejected: dict) -> bool:
    """The ONLY way a quote enters a result: string-matched against the text it claims to come from."""
    t = item.texts[cand["text_index"]].text
    if any(Q.verify(cand["text"], q.text) for q in item.quotes):
        return False                              # the same passage from another provider: shown once
    span = Q.verify(cand["text"], t)
    if span is None:
        rejected["invented_passages"] = rejected.get("invented_passages", 0) + 1
        return False
    a, b = span
    item.quotes.append(Quote(text=t[a:b], text_index=cand["text_index"], start=a, end=b,
                             location=cand["location"], picked_by=picked_by, score=float(cand.get("score", 0))))
    return True


async def _pick(io: formal.LitIO, statement: str, text: str, pool: list[tuple[LiteratureItem, dict]], k: int,
                rejected: dict) -> list[tuple[LiteratureItem, dict]] | None:
    """A free model chooses among numbered passages (never writes one). None when no model could answer."""
    from ..brain import classify
    from ..research.safety import UNTRUSTED_RULE, wrap_untrusted
    table = {f"P{i + 1}": x for i, x in enumerate(pool) if not x[0].texts[x[1]["text_index"]].suspect}
    if not table or io.budget.over:
        return None
    cands = "\n\n".join(wrap_untrusted(f"{pid}. ({it.reference.short()}) {c['text']}", f"passage {pid}")
                        for pid, (it, c) in table.items())
    prompt = PICK_PROMPT.format(rule=UNTRUSTED_RULE, lean=formal._decl_only(statement)[:1500], text=(text or "")[:600],
                                cands=cands, k=k)
    try:
        with classify.short_stage():
            c = await io.complete("understand", [{"role": "user", "content": prompt}], temperature=0.1,
                                  max_tokens=150)
    except Exception as e:  # noqa: BLE001
        log.info("passage pick: %s", e)
        return None
    ids, unknown = Q.picked_ids(c.text, table)
    if unknown:
        rejected["unknown_passage_ids"] = rejected.get("unknown_passage_ids", 0) + unknown
    return [table[i] for i in ids][:k] + [("model", c.model.key)]  # type: ignore[list-item]


async def _confirm(fetcher, recs: list[R.Record], mode: str, budget: Budget, rejected: dict, providers: dict) -> None:
    """Crossref record of each DOI: venue/type for the label; a DOI Crossref does not know is removed."""
    if mode == "local" or fetcher is None:
        return
    g = R.Guarded(fetcher, budget, "crossref")
    reg = R.Guarded(fetcher, budget, "doi")
    n_ok = 0
    err = ""
    for rec in recs:
        doi = rec.csl.get("DOI")
        if not doi:
            continue
        if biblio.norm_doi(doi).startswith("10.48550/arxiv.") and rec.csl.get("arxiv"):
            continue                              # the DOI of an arXiv record: that record was retrieved already
        try:
            cr = await R.confirm_doi(g, doi, mode)
            if cr is None and await R.doi_exists(reg, doi, mode):
                continue                          # a registered non-Crossref DOI (DataCite): kept, venue unknown
        except FetchError as e:
            err = e.kind
            if e.kind in ("budget", "local_mode"):
                break
            continue
        except asyncio.TimeoutError:
            err = "timeout"
            break
        if cr is None or not R.title_matches(cr["title"], rec.csl.get("title", "")):
            rejected["unresolved_dois"] = rejected.get("unresolved_dois", 0) + 1
            rec.csl.pop("DOI", None)              # the work stays (another identifier resolved), its DOI does not
            continue
        n_ok += 1
        rec.providers.setdefault("crossref", 99)
        rec.crossref_type = cr["type"]
        if cr["venue"] and not rec.csl.get("container-title"):
            rec.csl["container-title"] = cr["venue"]
        if cr["abstract"] and not any(t.provider == "crossref" for t in rec.texts):
            st = R._text("abstract", "crossref", cr["abstract"])
            if st:
                rec.texts.append(st)
    providers["crossref"] = {"ok": not err or n_ok > 0, "count": n_ok, "error": err,
                             "requests": len(g.urls) + len(reg.urls)}


async def search(statement: str, ctx, budget: Budget | None = None, *, text: str = "", depth: str = "quick",
                 mode: str | None = None, project_id: str = "", ws=None, fetcher=None, lang: str = "fr",
                 formalize: bool = True, owner: str = "literature", on_event: Callable | None = None,
                 use_cache: bool = True) -> LiteratureResult:
    """Search the literature for results related to a Lean statement (+ the user's words). Plain async function
    (also exposed to MCP); never raises for a provider or model failure; Local mode → zero network requests."""
    budget = (budget or Budget.for_depth(depth)).start()
    mode = mode or getattr(getattr(ctx, "settings", None), "mode", "auto")
    if ws is None and ctx is not None:
        ws = ctx.workspace(getattr(ctx.settings, "workspace", "")) if hasattr(ctx, "workspace") else None
    t0 = time.monotonic()
    res = LiteratureResult(statement=statement, depth=depth if depth in ("quick", "deep") else "quick",
                           local_mode=(mode == "local"), versions=_versions(ws))
    key = cache_key(statement, ws, res.depth, text) if use_cache else ""
    if key:
        hit = await _cache_get(ctx, key)
        if hit is not None:
            hit.cached = True
            _emit(on_event, "cached", items=len(hit.items))
            return hit
    if fetcher is None and mode != "local":
        try:
            from ..research.sources import library
            fetcher = library(ctx).fetcher
        except Exception:  # noqa: BLE001
            fetcher = None
    io = formal.LitIO(ctx, mode, budget, owner=owner, warm=owner != "literature")
    plan = QP.build(statement, text)
    res.query = plan
    try:
        if mode != "local" and plan.keywords:
            QP.with_extra(plan, await _extra_keywords(io, plan, statement, text))
        _emit(on_event, "queries", queries=plan.queries, keywords=plan.keywords)
        if not plan.queries:
            res.message = "no_query"
            return _finish(res, budget, t0)
        recs, res.mathlib = await _retrieve(ctx, fetcher, plan, mode, budget, project_id, getattr(ws, "key", ""),
                                            PER_QUERY, res.providers)
        _emit(on_event, "retrieved", records=len(recs))
        kws = plan.keywords + plan.extra_keywords
        scored = sorted(((*_score(r, kws), r) for r in recs), key=lambda x: -x[0])
        top = [x for x in scored if x[0] >= MIN_SCORE][: budget.items * 2]
        await _confirm(fetcher, [r for _s, _m, r in top], mode, budget, res.rejected, res.providers)
        top = _dedupe(top)
        items: list[LiteratureItem] = []
        for score, matched, rec in top:
            ref = R.reference_of(rec)
            if not ref.title:
                res.rejected["no_title"] = res.rejected.get("no_title", 0) + 1
                continue
            if re.match(r"\s*(withdrawn|retracted|retraction( note)?)\b", ref.title, re.I):
                res.rejected["withdrawn"] = res.rejected.get("withdrawn", 0) + 1
                continue                          # a withdrawn / retracted work is never offered as a result
            if ref.id.startswith("t:"):
                res.rejected["no_identifier"] = res.rejected.get("no_identifier", 0) + 1
                continue                          # no identifier that resolves: never shown
            it = LiteratureItem(id=item_id(ref.id), reference=ref, texts=rec.texts, score=round(score, 3),
                                matched=matched)
            if any(t.suspect for t in it.texts):
                res.rejected["suspect_texts"] = res.rejected.get("suspect_texts", 0) + sum(t.suspect for t in it.texts)
            items.append(it)
            if len(items) >= budget.items:
                break
        # passages: rules first; in deep mode a free model may choose among the numbered candidates
        pool = [(it, c) for it in items for c in _quotes(it, kws, lang)[:3]]
        picked = await _pick(io, statement, text, pool[:16], 4, res.rejected) if depth == "deep" and pool else None
        if picked:
            who = picked.pop()[1]
            for it, c in picked:
                _accept_quote(it, c, f"model:{who}", res.rejected)
        for it, c in pool:
            if len(it.quotes) < 2 and c["score"] >= MIN_SCORE and \
                    not any(q.start == c["start"] and q.text_index == c["text_index"] for q in it.quotes):
                _accept_quote(it, c, "rules", res.rejected)
        for it in items:
            it.quotes.sort(key=lambda q: -q.score)
            it.key, it.bibtex = _bibtex(it)
        items.sort(key=lambda it: (-(it.quotes[0].score if it.quotes else -1), -it.score))
        res.items = items
        _emit(on_event, "quoted", items=len(items), quotes=sum(len(i.quotes) for i in items))
        if formalize and ws is not None and mode != "local":
            n = 0
            for it in items:
                if n >= budget.formalize or budget.over:
                    break
                if not it.quotes:
                    continue
                n += 1
                await formal.formalize(io, it, ws, getattr(ctx.settings, "compile_timeout_s", 180))
                if it.lean.compiled:
                    await formal.mathlib_status(ctx, io, it, ws, getattr(ctx.settings, "compile_timeout_s", 180))
                _emit(on_event, "formalized", item=it.id, status=it.lean.status)
        for it in items:
            if not it.lean.name:
                it.lean.name = formal.cited_name(it)
            if not it.lean.statement and not it.lean.note:
                it.lean.note = "not_tried" if formalize else "off"
        res.message = "found" if res.found else ("nothing_reliable" if mode != "local" or recs else "local_nothing")
    except asyncio.CancelledError:
        res.cancelled = True
        res.message = "cancelled"
        raise
    finally:
        _finish(res, budget, t0)
    if key and not res.cancelled and not budget.cancelled and _complete_enough(res):
        await _cache_put(ctx, key, res)
    return res


def _complete_enough(res: LiteratureResult) -> bool:
    """Cache only an answer that is not an accident: at least one network provider answered (or Local mode)."""
    if res.local_mode:
        return False                               # the next online search must still run
    return any(v.get("ok") and k != "sources" for k, v in res.providers.items())


def _finish(res: LiteratureResult, budget: Budget, t0: float) -> LiteratureResult:
    res.seconds = round(time.monotonic() - t0, 2)
    res.usage = budget.usage()
    if budget.cancelled:
        res.cancelled = True
        res.message = res.message or "cancelled"
    return res


def _bibtex(it: LiteratureItem) -> tuple[str, str]:
    csl = dict(it.reference.csl)
    if not csl.get("title"):
        csl["title"] = it.reference.title
    key = biblio.make_key(csl, set())
    try:
        return key, biblio.item_to_bibtex(csl, key)
    except Exception:  # noqa: BLE001
        return key, ""


# ---------------------------------------------------------------- cache (D38 stage cache, kind « literature »)
def _versions(ws) -> dict:
    if ws is None:
        return {}
    try:
        from ..runtime.lean import workspace_info
        return workspace_info(ws)
    except Exception:  # noqa: BLE001
        return {"workspace": getattr(ws, "key", "")}


def cache_key(statement: str, ws, depth: str, text: str = "") -> str:
    from ..pipeline.stagecache import make_key, normalize_text
    return make_key(statement, _versions(ws), "literature-v1", depth, normalize_text(text)[:400])


def _cache(ctx):
    if ctx is None or not hasattr(ctx, "paths"):
        return None
    from ..pipeline.stagecache import shared
    try:
        return shared(ctx)
    except Exception:  # noqa: BLE001
        return None


async def _cache_get(ctx, key: str) -> LiteratureResult | None:
    c = _cache(ctx)
    v = c.get(CACHE_KIND, key) if c is not None else None
    if not v or time.time() - float(v.get("_t", 0)) > CACHE_DAYS * 86400:
        return None
    try:
        return LiteratureResult.from_dict(v.get("result") or {})
    except Exception:  # noqa: BLE001
        return None


async def _cache_put(ctx, key: str, res: LiteratureResult) -> None:
    c = _cache(ctx)
    if c is not None:
        await c.put(CACHE_KIND, key, {"_t": time.time(), "result": res.to_dict()})
