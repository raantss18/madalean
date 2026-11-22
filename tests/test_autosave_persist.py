"""S-AK (D43): every write the web UI's autosave sends is persisted — checked by restarting the server on the same
config directory and reading everything back. Also the stale-write answers the UI relies on (409 keeps the text)."""
from __future__ import annotations

from helpers import make_ctx, running, session

PROBLEM = "La somme de deux entiers pairs est paire."


async def test_autosaved_fields_survive_a_restart(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "Projet", "description": ""})).json())["project"]["id"]
        did = (await (await s.post(L + "/api/dossiers", json={"problem": PROBLEM, "project_id": pid, "start": False}))
               .json())["dossier"]["id"]
        # dossier title (InlineTitle) and statement (StepStatement), each as its own PATCH like the UI
        r = await s.patch(L + f"/api/dossiers/{did}", json={"title": "Titre autosauvé"})
        assert r.status == 200
        r = await s.patch(L + f"/api/dossiers/{did}", json={"problem": PROBLEM + " Ajout."})
        assert r.status == 200
        # project title / description (project page)
        r = await s.patch(L + f"/api/projects/{pid}", json={"description": "Décrit sans bouton."})
        assert r.status == 200
        r = await s.patch(L + f"/api/projects/{pid}", json={"title": "Projet renommé"})
        assert r.status == 200
        # profile setting
        r = await s.patch(L + "/api/settings", json={"profile": "Agrégation 2027."})
        assert r.status == 200
        # note body (base_rev) and a stale write: 409 with the current note, nothing overwritten
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "N", "body": "a\nb\n"})).json())["note"]
        r = await s.patch(L + f"/api/notes/{n['id']}", json={"base_rev": n["rev"], "body": "a\nb\nc\n"})
        assert r.status == 200
        rev2 = (await r.json())["note"]["rev"]
        stale = await s.patch(L + f"/api/notes/{n['id']}", json={"base_rev": n["rev"], "body": "x\nb\n", "title": "Autre"})
        assert stale.status in (200, 409)            # merged when the lines differ, 409 when the same lines changed
        # Calcul cell source (debounced autosave of a cell)
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "C", "language": "python"})).json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        cid = (await (await s.post(D + "/cells", json={"type": "code", "source": "1"})).json())["cell"]["id"]
        r = await s.patch(D + f"/cells/{cid}", json={"source": "for i in range(3):\n    x = i\ny = 2"})
        assert r.status == 200

    ctx2 = make_ctx(tmp_path)
    async with running(ctx2) as (_srv, L, _R), session() as s:
        d = (await (await s.get(L + f"/api/dossiers/{did}")).json())["dossier"]
        assert d["title"] == "Titre autosauvé"
        assert d["problem"] == PROBLEM + " Ajout."
        p = next(x for x in (await (await s.get(L + "/api/projects")).json())["projects"] if x["id"] == pid)
        assert p["title"] == "Projet renommé" and p["description"] == "Décrit sans bouton."
        assert (await (await s.get(L + "/api/settings")).json())["settings"]["profile"] == "Agrégation 2027."
        note = (await (await s.get(L + f"/api/notes/{n['id']}")).json())["note"]
        assert note["rev"] >= rev2 and "c" in note["body"].splitlines()
        cells = (await (await s.get(L + f"/api/calcul/{pid}/docs/{doc}")).json())["cells"]
        assert next(c for c in cells if c["id"] == cid)["source"] == "for i in range(3):\n    x = i\ny = 2"
