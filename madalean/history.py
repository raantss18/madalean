"""History compaction of dossiers relaunched many times (session S-AO, TODO B16 bis, DECISIONS D47).

A dossier re-run hundreds of times grew without bound (soak: ≈ 1.7 MB per dossier after ~550 relaunches; every save
rewrote it whole). Most of it was repetition: the same notes / proof / explanation / natural-language proof written
again at each run (identical text), and the thread's machine events (« Preuve trouvée… », « Résultats de votre
bibliothèque proposés… »).

`compact(d)` keeps, in full:
- every verified version (statement accepted by Lean, proof accepted by Lean), every version written by the user,
  every current version (statement, proof, explanation, the notes of the current statement, the natural-language
  proof of the current proof) and the parents of everything kept;
- the latest TEXT_KEEP model texts per kind (explanations, notes, natural-language proofs) and the latest FAILED_KEEP
  unverified statements / proofs;
- every user event (messages, manual edits, « Retour à la version … ») and the latest EVENTS_KEEP events;
and removes:
- exact duplicates of a kept version (same text, same parent, same verdict, same author): the latest one stays, so
  « current » and « latest for this statement / proof » are unchanged;
- the older events, summarised in `d.history` as compact records (one per job: counts per kind, models, error keys,
  times; beyond HISTORY_RECORDS jobs they are merged into one record) and one « Historique compacté » event in the
  thread.
Nothing is lost: every removed version and event is appended, whole, to `<dossiers>/.history/<id>.jsonl.gz`
(append-only gzip members, never read by the server). Indices are remapped everywhere (current pointers, parents,
event refs). The library, the article and the proof meta only read the current proof / statement (kept).

Compaction runs when a dossier is over EVENTS_MAX events or VERSIONS_MAX versions: at the end of each job (no job
holds a version index then), and on load for existing big dossiers (migration). It is idempotent."""
from __future__ import annotations

import time
from collections import Counter

from .dossiers import Dossier, Event, Version

EVENTS_MAX = 300           # compaction starts above this many events …
VERSIONS_MAX = 120         # … or this many versions (all kinds together)
EVENTS_KEEP = 120          # most recent events kept in full
TEXT_KEEP = 10             # model texts kept per kind (explanations, notes, natural-language proofs), besides current
FAILED_KEEP = 6            # unverified statements / proofs kept, besides current
HISTORY_RECORDS = 40       # per-job summary records; older ones merged into one
SUMMARY_KEY = "Historique compacté : {events} événements plus anciens ({jobs} travaux) résumés ; le détail est conservé à part."
USER_KEYS = ("Retour à la version {n} de la {what}.", "Preuve modifiée à la main : Lean l'accepte.",
             "Preuve modifiée à la main : pas vérifiée par Lean ({why}).", "Explication modifiée à la main.",
             "Preuve en langage naturel modifiée à la main.", "Lecture de l'énoncé modifiée à la main.",
             "Énoncé modifié à la main.")
KINDS = ("statements", "proofs", "statement_notes", "explanations", "informal_proofs")
# which version list an event's `ref` points into
EVENT_REF = {"statement": "statements", "check": "statements", "understood": "statements", "notes": "statement_notes",
             "proof": "proofs", "explanation": "explanations", "informal": "informal_proofs"}


def versions_count(d: Dossier) -> int:
    return sum(len(getattr(d, k)) for k in KINDS)


def needs(d: Dossier) -> bool:
    return len(d.events) > EVENTS_MAX or versions_count(d) > VERSIONS_MAX


def _ref_kind(e: Event) -> str:
    if e.kind in EVENT_REF:
        return EVENT_REF[e.kind]
    if e.kind == "error" and e.ref is not None:
        return "proofs" if (e.key or "").startswith("Preuve") else "statements"
    return ""


def _latest(seq: list[Version], parent: int) -> int:
    for i in range(len(seq) - 1, -1, -1):
        if seq[i].parent == parent:
            return i
    return -1


def _select(d: Dossier) -> dict[str, set[int]]:
    """Indices kept per kind before deduplication (with the parents of everything kept)."""
    def last(seq, pred, n):
        idx = [i for i, v in enumerate(seq) if pred(v)]
        return set(idx[-n:]) if n else set()
    keep: dict[str, set[int]] = {}
    keep["statements"] = {i for i, v in enumerate(d.statements) if v.ok or v.source == "user"} | last(
        d.statements, lambda v: not v.ok and v.source != "user", FAILED_KEEP)
    keep["proofs"] = {i for i, v in enumerate(d.proofs) if v.ok or v.source == "user"} | last(
        d.proofs, lambda v: not v.ok and v.source != "user", FAILED_KEEP)
    for k in ("statement_notes", "explanations", "informal_proofs"):
        seq = getattr(d, k)
        keep[k] = {i for i, v in enumerate(seq) if v.source == "user"} | set(range(max(0, len(seq) - TEXT_KEEP),
                                                                                   len(seq)))
    for k, cur in (("statements", d.cur_statement), ("proofs", d.cur_proof), ("explanations", d.cur_explanation),
                   ("statement_notes", _latest(d.statement_notes, d.cur_statement)),
                   ("informal_proofs", _latest(d.informal_proofs, d.cur_proof))):
        if 0 <= cur < len(getattr(d, k)):
            keep[k].add(cur)
    for k in ("explanations", "informal_proofs"):                  # parents: proofs, then their statements
        keep["proofs"] |= {v.parent for i, v in enumerate(getattr(d, k))
                           if i in keep[k] and v.parent is not None and 0 <= v.parent < len(d.proofs)}
    for k in ("proofs", "statement_notes"):
        keep["statements"] |= {v.parent for i, v in enumerate(getattr(d, k))
                               if i in keep[k] and v.parent is not None and 0 <= v.parent < len(d.statements)}
    return keep


def _remap(seq: list[Version], keep: set[int], parent_map: dict[int, int] | None) -> tuple[list[Version], dict[int, int], list[dict]]:
    """Kept versions in order, duplicates folded into their latest occurrence. Returns (new list, old -> new index,
    removed versions as dicts with their old index)."""
    from dataclasses import asdict
    rep: dict[int, int] = {}                  # old index -> old index of its representative
    seen: dict[tuple, int] = {}
    for i in range(len(seq) - 1, -1, -1):
        if i not in keep:
            continue
        v = seq[i]
        parent = parent_map.get(v.parent, v.parent) if parent_map is not None and v.parent is not None else v.parent
        key = (v.code, parent, v.ok, v.source)
        if key in seen:
            rep[i] = seen[key]
        else:
            seen[key] = i
            rep[i] = i
    order = sorted(i for i in rep if rep[i] == i)
    new_of = {old: n for n, old in enumerate(order)}
    mapping = {i: new_of[rep[i]] for i in rep}
    out = []
    for old in order:
        v = seq[old]
        if parent_map is not None and v.parent is not None:
            v.parent = parent_map.get(v.parent, v.parent)
        out.append(v)
    removed = [{"index": i, **asdict(v)} for i, v in enumerate(seq) if i not in rep or rep[i] != i]
    return out, mapping, removed


def _is_user_event(e: Event, d: Dossier) -> bool:
    if e.kind == "user" or (e.key or "") in USER_KEYS:
        return True
    k = _ref_kind(e)
    seq = getattr(d, k, None) if k else None
    return bool(seq is not None and e.ref is not None and 0 <= e.ref < len(seq) and seq[e.ref].source == "user")


def _record(events: list[Event]) -> dict:
    kinds = Counter(e.kind for e in events)
    models = Counter(e.model for e in events if e.model)
    errors = Counter((e.key or e.text)[:120] for e in events if e.kind == "error")
    secs = 0.0
    for e in events:
        s = (e.params or {}).get("seconds") if isinstance(e.params, dict) else None
        if isinstance(s, (int, float)):
            secs += float(s)
    return {"job": events[0].job if events else "", "t0": min(e.t for e in events), "t1": max(e.t for e in events),
            "events": len(events), "kinds": dict(kinds), "models": dict(models), "errors": dict(errors),
            "proofs": kinds.get("proof", 0), "seconds": round(secs, 1), "jobs": 1}


def _merge(records: list[dict]) -> dict:
    out = {"job": "", "t0": min(r["t0"] for r in records), "t1": max(r["t1"] for r in records), "events": 0,
           "kinds": Counter(), "models": Counter(), "errors": Counter(), "proofs": 0, "seconds": 0.0, "jobs": 0,
           "merged": True}
    for r in records:
        out["events"] += r.get("events", 0)
        out["proofs"] += r.get("proofs", 0)
        out["seconds"] += r.get("seconds", 0.0)
        out["jobs"] += r.get("jobs", 1)
        for k in ("kinds", "models", "errors"):
            out[k].update(r.get(k) or {})
    errors = Counter(dict(out["errors"].most_common(30)))
    out.update(kinds=dict(out["kinds"]), models=dict(out["models"].most_common(30)), errors=dict(errors),
               seconds=round(out["seconds"], 1))
    return out


def history_of(d: Dossier) -> list[dict]:
    h = d.extra.get("history")
    return h if isinstance(h, list) else []


def compact(d: Dossier, force: bool = False) -> dict | None:
    """Compact `d` in place. Returns the archive record (removed versions and events, whole) or None when nothing
    changed. Call only when no job works on the dossier (version indices move)."""
    from dataclasses import asdict
    if not force and not needs(d):
        return None
    keep = _select(d)
    removed: dict[str, list[dict]] = {}
    maps: dict[str, dict[int, int]] = {}
    new_s, maps["statements"], removed["statements"] = _remap(d.statements, keep["statements"], None)
    new_p, maps["proofs"], removed["proofs"] = _remap(d.proofs, keep["proofs"], maps["statements"])
    new_n, maps["statement_notes"], removed["statement_notes"] = _remap(d.statement_notes, keep["statement_notes"],
                                                                        maps["statements"])
    new_e, maps["explanations"], removed["explanations"] = _remap(d.explanations, keep["explanations"],
                                                                  maps["proofs"])
    new_i, maps["informal_proofs"], removed["informal_proofs"] = _remap(d.informal_proofs, keep["informal_proofs"],
                                                                        maps["proofs"])
    # events: user ones and the latest EVENTS_KEEP in full, the older ones summarised (decided on the old indices)
    old_summary = [e for e in d.events if e.key == SUMMARY_KEY]
    events = [e for e in d.events if e.key != SUMMARY_KEY]
    cut = max(0, len(events) - EVENTS_KEEP)
    kept_events, gone = [], []
    for i, e in enumerate(events):
        (kept_events if i >= cut or _is_user_event(e, d) else gone).append(e)
    if not gone and not any(removed.values()):
        return None                           # nothing to remove: the dossier is left exactly as it was
    d.statements, d.proofs, d.statement_notes, d.explanations, d.informal_proofs = new_s, new_p, new_n, new_e, new_i
    d.cur_statement = maps["statements"].get(d.cur_statement, -1) if d.cur_statement >= 0 else d.cur_statement
    d.cur_proof = maps["proofs"].get(d.cur_proof, -1) if d.cur_proof >= 0 else d.cur_proof
    d.cur_explanation = maps["explanations"].get(d.cur_explanation, -1) if d.cur_explanation >= 0 else \
        d.cur_explanation
    for e in kept_events:
        k = _ref_kind(e)
        if k and e.ref is not None:
            e.ref = maps[k].get(e.ref)
    history = history_of(d)
    if gone:
        by_job: dict[str, list[Event]] = {}
        for e in gone:
            by_job.setdefault(e.job or f"t{int(e.t) // 3600}", []).append(e)
        history += [_record(es) for es in by_job.values()]
        history.sort(key=lambda r: r["t0"])
        if len(history) > HISTORY_RECORDS:
            n = len(history) - HISTORY_RECORDS + 1
            history[:n] = [_merge(history[:n])]
    d.extra["history"] = history
    total = sum(r.get("events", 0) for r in history)
    jobs = sum(r.get("jobs", 1) for r in history)
    if history:
        t = max(r["t1"] for r in history)
        summary = Event("info", "", t=t, key=SUMMARY_KEY, params={"events": total, "jobs": jobs})
        from .i18n import msg
        summary.text = msg(SUMMARY_KEY, events=total, jobs=jobs)["text"]
        pos = next((i for i, e in enumerate(kept_events) if e.t > t), len(kept_events))
        kept_events.insert(pos, summary)
    d.events = kept_events
    return {"t": time.time(), "id": d.id, "events": [asdict(e) for e in gone + old_summary],
            "versions": {k: v for k, v in removed.items() if v}}
