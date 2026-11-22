"""S-AO (TODO B16 bis, DECISIONS D47): dossiers relaunched hundreds of times keep a bounded history — every verified
version, every user message / edit, the current versions and the latest attempts in full; older events summarised
(compact records + one thread event); exact duplicates folded; everything removed appended whole to an archive;
indices remapped; idempotent; existing big dossiers migrated on load; coalesced saves."""
from __future__ import annotations

import asyncio
import json
import time

import pytest

from helpers import make_ctx, running, session, wait_idle
from madalean import history
from madalean.dossiers import Dossier, DossierStore
from madalean.repo import DossierRepo

STMT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"
PROOF = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"


def relaunched(runs: int = 300) -> Dossier:
    """A dossier as the soak leaves it: the same notes / proof / explanation written at every run, a failed run now
    and then, user messages, a manual proof, a restore, a second statement."""
    d = Dossier(id="20261122-000000-abcd", title="Somme de deux pairs", problem="Montrer que …")
    t = 1_700_000_000.0
    d.add_event("user", "Montrer que la somme de deux pairs est paire")
    s0 = d.add_statement(STMT, ok=True, model="m:a")
    d.add_event("statement", "Énoncé accepté", ref=s0, key="L'IA a traduit…", job="j-0")
    for r in range(runs):
        job = f"j-{r + 1}"
        if r % 50 == 25:
            d.add_event("user", f"message {r}", stage="proof")
        if r == 120:                                       # the user changes the statement (a new verified version)
            s1 = d.add_statement(STMT.replace("ℕ", "ℤ"), ok=True, source="user")
            d.add_event("statement", "Énoncé modifié", ref=s1, key="Énoncé modifié à la main.")
        if r == 121:
            s2 = d.add_statement("theorem bad : False := by sorry", ok=False, model="m:a")
            d.add_event("error", "Lean refuse", ref=s2, key="Lean refuse la traduction.", job=job)
            d.restore("statement", 1)
        i = d.add_notes(f"notes for statement {d.cur_statement}", model="m:b")
        d.add_event("notes", "Lecture guidée", ref=i, key="Lecture guidée…", job=job, model="m:b")
        d.add_event("info", "Résultats de votre bibliothèque proposés à l'IA : …", key="Résultats…", job=job)
        if r % 7 == 3:
            d.add_proof(f"{PROOF}\n-- attempt {r}", ok=False, model="m:c", meta={"attempts": 3})
            d.add_event("error", "Lean refuse la preuve", key="Pas de preuve vérifiée", job=job, model="m:c",
                        params={"seconds": 12.5})
            continue
        p = d.add_proof(PROOF.replace("ℕ", "ℤ") if d.cur_statement == 1 else PROOF, model="m:c",
                        meta={"axioms": ["propext"], "seconds": 2.0, "attempts": 5})
        d.add_event("proof", "Preuve trouvée et vérifiée par Lean", ref=p, key="Preuve trouvée…", job=job,
                    model="m:c", params={"seconds": 2.0})
        e = d.add_explanation("Explanation of the proof.", model="m:d")
        d.add_event("explanation", "Explication", ref=e, key="Explication…", job=job, model="m:d")
        f = d.add_informal_proof(f"Informal proof {r % 2}.", model="m:d")
        d.add_event("informal", "Preuve rédigée", ref=f, key="Preuve rédigée…", job=job, model="m:d")
        if r == 200:
            up = d.add_proof(PROOF + "  -- by hand", source="user", ok=True)
            d.add_event("proof", "Preuve modifiée à la main : Lean l'accepte.", ref=up,
                        key="Preuve modifiée à la main : Lean l'accepte.")
            d.restore("proof", up - 1)
            d.add_event("info", "Retour à la version", key="Retour à la version {n} de la {what}.",
                        params={"n": up, "what": "preuve"})
    for i, e in enumerate(d.events):                     # chronological times
        e.t = t + i
    d.status = "proved"
    return d


def snapshot(d: Dossier) -> dict:
    return {"statement": d.statement, "proof": d.proof, "explanation": d.explanation, "notes": d.notes,
            "informal": d.informal_proof, "proved": d.proof_is_current,
            "proof_meta": d.proofs[d.cur_proof].meta if d.cur_proof >= 0 else None,
            "verified": {(v.code, d.statements[v.parent].code if v.parent is not None else None)
                         for v in d.proofs if v.ok},
            "statements_ok": {v.code for v in d.statements if v.ok},
            "user_versions": {(k, v.code) for k in history.KINDS for v in getattr(d, k) if v.source == "user"},
            "user_events": [(e.kind, e.text) for e in d.events if e.kind == "user" or e.key in history.USER_KEYS]}


def referenced(d: Dossier) -> list[tuple]:
    """(event identity, referenced version code) for every event with a ref."""
    out = []
    for e in d.events:
        k = history._ref_kind(e)
        if k and e.ref is not None:
            seq = getattr(d, k)
            assert 0 <= e.ref < len(seq), (e.kind, e.ref, len(seq))
            out.append((id(e), seq[e.ref].code))
    return out


def test_compaction_keeps_what_matters_and_bounds_the_dossier():
    d = relaunched(300)
    before = snapshot(d)
    size0, n_events = len(d.to_json()), len(d.events)
    refs0 = dict(referenced(d))
    assert history.needs(d)
    rec = history.compact(d)
    assert rec is not None
    after = snapshot(d)
    assert after == before                                         # current, verified, user: all unchanged
    for eid, code in referenced(d):                                # every kept ref still points to the same text
        if eid in refs0:
            assert code == refs0[eid]
    for k in ("proofs", "statement_notes"):                        # parents valid
        assert all(v.parent is None or 0 <= v.parent < len(d.statements) for v in getattr(d, k))
    for k in ("explanations", "informal_proofs"):
        assert all(v.parent is None or 0 <= v.parent < len(d.proofs) for v in getattr(d, k))
    users = sum(1 for e in d.events if e.kind == "user" or e.key in history.USER_KEYS)
    assert len(d.events) <= history.EVENTS_KEEP + users + 1
    assert sum(1 for e in d.events if e.key == history.SUMMARY_KEY) == 1
    assert [e.t for e in d.events] == sorted(e.t for e in d.events)
    assert len(d.explanations) <= history.TEXT_KEEP + 1 and len(d.statement_notes) <= history.TEXT_KEEP + 1
    assert len(d.proofs) <= 3 + history.FAILED_KEEP                 # 3 distinct verified proofs + recent failures
    assert not history.needs(d)
    # the archive holds every removed event, whole
    summarised = sum(r["events"] for r in history.history_of(d))
    assert len(rec["events"]) == summarised == n_events - (len(d.events) - 1)
    assert sum(r.get("jobs", 1) for r in history.history_of(d)) > 200
    assert len(history.history_of(d)) <= history.HISTORY_RECORDS
    rec_all = history.history_of(d)
    assert sum(r["kinds"].get("error", 0) for r in rec_all) > 0 and any("m:c" in r["models"] for r in rec_all)
    size1 = len(d.to_json())
    assert size1 < size0 / 4 and size1 < 120_000, (size0, size1)
    # round trip through the file format, then idempotent (even forced)
    d2 = Dossier.from_dict(json.loads(d.to_json()))
    assert history.history_of(d2) == history.history_of(d)
    assert history.compact(d2, force=True) is None and d2.to_json() == d.to_json()


def test_compaction_growth_stays_bounded_over_many_rounds():
    d = relaunched(40)
    sizes = []
    for _round in range(15):                                       # 15 × 40 more relaunches, compacted as at job end
        more = relaunched(40)
        base = len(d.events)
        for e in more.events[3:]:
            e.t = time.time() + base
            e.ref = None if e.ref is not None and e.kind != "user" else e.ref
            d.events.append(e)
        for v in more.proofs[1:]:
            d.proofs.append(v)
        d.cur_proof = len(d.proofs) - 1 if d.proofs[-1].ok else d.cur_proof
        history.compact(d)
        sizes.append(len(d.to_json()))
    assert max(sizes) < 150_000 and sizes[-1] <= max(sizes)


def test_restore_route_numbers_still_resolve_after_compaction():
    d = relaunched(300)
    history.compact(d)
    for kind, seq in (("statement", d.statements), ("proof", d.proofs), ("explanation", d.explanations)):
        for i in range(len(seq)):
            d.restore(kind, i)                                     # every listed version is restorable


async def test_repo_migrates_on_load_archives_and_is_idempotent(tmp_path):
    store = DossierStore(tmp_path / "dossiers")
    store.root.mkdir(parents=True)
    big = relaunched(300)
    small = relaunched(3)
    small.id = "20261122-000001-beef"
    store.save(big)
    store.save(small)
    small_bytes = (store.root / f"{small.id}.json").read_bytes()
    size0 = (store.root / f"{big.id}.json").stat().st_size
    events = []
    repo = DossierRepo(store, lambda k, p: events.append(k))
    await repo.load_all()
    size1 = (store.root / f"{big.id}.json").stat().st_size
    assert size1 < size0 / 4 and repo.compactions == 1
    assert (store.root / f"{small.id}.json").read_bytes() == small_bytes      # small dossiers untouched
    arc = store.archive_read(big.id)
    assert len(arc) == 1 and arc[0]["id"] == big.id and arc[0]["events"] and arc[0]["versions"]
    assert not events                                                       # nothing published at start
    file1 = (store.root / f"{big.id}.json").read_bytes()
    repo2 = DossierRepo(store, lambda k, p: None)
    await repo2.load_all()                                                  # a second start: nothing to do
    assert (store.root / f"{big.id}.json").read_bytes() == file1 and len(store.archive_read(big.id)) == 1
    assert repo2.get(big.id).proof == relaunched(300).proof
    assert [d.id for d in store.list()] and not list(store.root.glob(".history/*.json"))
    # the archive follows the dossier to the trash and back
    assert await repo2.delete(big.id)
    assert not store.archive_path(big.id).exists()
    assert await repo2.restore(big.id) is not None and len(store.archive_read(big.id)) == 1


def test_archive_survives_a_truncated_last_member(tmp_path):
    store = DossierStore(tmp_path)
    store.archive_append("x", {"n": 1})
    store.archive_append("x", {"n": 2})
    p = store.archive_path("x")
    p.write_bytes(p.read_bytes() + b"\x1f\x8b\x08garbage")
    assert [r["n"] for r in store.archive_read("x")] == [1, 2]


async def test_saves_queued_behind_a_write_are_coalesced(tmp_path, monkeypatch):
    store = DossierStore(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    repo = DossierRepo(store, lambda k, p: None)
    d = relaunched(2)
    slow = repo._write

    def write(did, text):
        time.sleep(0.05)
        slow(did, text)
    monkeypatch.setattr(repo, "_write", write)
    saves = []
    for i in range(20):
        d.add_event("info", f"event {i}")
        saves.append(asyncio.create_task(repo.save(d)))
    await asyncio.gather(*saves)
    assert repo.writes + repo.coalesced == 20 and repo.writes <= 3
    on_disk = store.load(d.id)
    assert on_disk.events[-1].text == "event 19" and len(on_disk.events) == len(d.events)


async def test_jobs_compact_at_their_end_and_the_dossier_stays_proved(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "EVENTS_MAX", 30)
    monkeypatch.setattr(history, "EVENTS_KEEP", 12)
    monkeypatch.setattr(history, "VERSIONS_MAX", 20)
    monkeypatch.setattr(history, "TEXT_KEEP", 2)
    ctx = make_ctx(tmp_path, delay=0.001)
    async with running(ctx) as (_srv, L, _R), session() as s:
        r = await (await s.post(L + "/api/dossiers", json={"problem": "Montrer que la somme de deux pairs est "
                                                                      "paire."})).json()
        did = r["dossier"]["id"]
        await wait_idle(ctx)
        for _ in range(10):
            assert (await s.post(L + f"/api/dossiers/{did}/run", json={"plan": ["notes", "proof", "explanation"]})
                    ).status == 202
            await wait_idle(ctx)
        d = ctx.repo.get(did)
        assert ctx.repo.compactions >= 1 and d.proof_is_current and d.status == "proved"
        assert any(e.key == history.SUMMARY_KEY for e in d.events)
        assert len(d.events) <= history.EVENTS_MAX
        assert ctx.repo.store.archive_read(did)
        j = await (await s.get(L + f"/api/dossiers/{did}")).json()
        assert j["dossier"]["current"]["proof_is_current"] and j["dossier"]["history"]
        assert any(x["dossier"] == did for x in (await (await s.get(L + "/api/library")).json())["entries"])
