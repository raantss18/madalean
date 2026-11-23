"""« Pour mes projets »: which news items speak about what the user works on. Entirely local.

A project's profile is the vocabulary of its own texts: title, description, the titles / problems / understood
statements of its dossiers, the titles and tags of its notes, the titles of its sources. An item matches a project
when it shares several *rare* terms with that profile: every shared term weighs its inverse document frequency in
the news corpus (a word present in every abstract is worth nothing), a shared two-word expression counts double,
and a match needs at least MIN_TERMS distinct terms (or one expression) and MIN_SCORE points. The matching terms
are kept, so the screen can say why an item is shown. No model, no network."""
from __future__ import annotations

import math
import re

from .branches import fold

MIN_TERMS = 2
MIN_SCORE = 6.0
MAX_PROFILE_CHARS = 200_000
TOP_TERMS = 5

STOP = frozenset("""
a about above after again all also although always among and another any are around because been before being
below between both but can cannot could does doing done during each either every few first for from further get
give given gives had has have having here how however into its itself just let like many may might more most much
must near need new non nor not now obtain obtained often one only onto other our out over paper per present
proof prove proved proves result results same second several shall should show shown shows since some such than
that the their them then there these they this those through thus too two under until upon use used using very
via was were what when where whether which while who whose will with within without work would yet you your
alors apres ainsi aucun aussi autre autres aux avec avoir bien car cas ceci cela celle celles celui ces cet cette
ceux chaque comme comment dans des deux donc dont elle elles encore entre est etant ete etre fait faire fois ici
ils leur leurs lors mais meme mes moins mon montre montrer montrons nos notre nous par parce pas peut peuvent plus
pour pourquoi quand que quel quelle quelles quels qui quoi sans ses soit son sont sous sur tous tout toute toutes
tres trois une vers voici voir vos votre vous
theorem theoreme lemma lemme proposition corollary corollaire definition remark remarque example exemple exercise
exercice problem probleme question conjecture demonstration preuve enonce statement note notes projet project
dossier demo recherche research introduction chapter chapitre section general study etude case some certain
""".split())
_WORD = re.compile(r"[a-z][a-z0-9'-]{2,}")
_TEX = re.compile(r"\\[a-zA-Z]+|[{}$^_\\]")


def tokens(text: str) -> list[str]:
    """Content words of a text (lower case, no accents, TeX commands dropped, stop words removed)."""
    s = fold(_TEX.sub(" ", text or ""))
    out = []
    for w in _WORD.findall(s):
        w = w.strip("'-").rsplit("'", 1)[-1]          # « d'un », « l'entier » → the word after the apostrophe
        if len(w) >= 4 and w not in STOP:
            out.append(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w)
    return out


def terms(text: str) -> set[str]:
    """Words and two-word expressions (« even integer », « nombre premier »)."""
    ws = tokens(text)
    return set(ws) | {f"{a} {b}" for a, b in zip(ws, ws[1:])}


def project_texts(ctx) -> dict[str, dict]:
    """project id → {"title", "text"}: the project's own words, gathered from the stores (never from the network)."""
    out: dict[str, dict] = {}
    try:
        projects = [p for p in ctx.projects.list() if not p.archived]
    except Exception:  # noqa: BLE001
        return out
    for p in projects:
        parts = [p.title, p.description]
        try:
            for d in ctx.repo.list(p.id, include_archived=False):
                parts += [d.title, d.problem, getattr(d, "understood", "")]
        except Exception:  # noqa: BLE001
            pass
        rs = getattr(ctx, "research", None)
        try:
            for n in (rs.notes.list(p.id) if rs is not None else []):
                parts += [n.title, " ".join(n.tags)]
        except Exception:  # noqa: BLE001
            pass
        try:
            from ..research.sources import library
            for e in library(ctx).all_entries(p.id).values():
                csl = e.get("csl") if isinstance(e.get("csl"), dict) else e
                parts.append(str(csl.get("title") or ""))
        except Exception:  # noqa: BLE001
            pass
        text = "\n".join(x for x in parts if isinstance(x, str) and x)[:MAX_PROFILE_CHARS]
        out[p.id] = {"title": p.title, "text": text}
    return out


def score_corpus(corpus: list[tuple[int, str, str]], profiles: dict[str, dict]) -> list[tuple[int, list[dict], float]]:
    """→ [(item id, [{project, score, terms}], best score)] for the items matching at least one project."""
    if not corpus or not profiles:
        return []
    docs = [(i, terms(f"{title}\n{summary}")) for i, title, summary in corpus]
    df: dict[str, int] = {}
    for _i, ts in docs:
        for t in ts:
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    prof = {pid: terms(p["text"]) for pid, p in profiles.items()}
    prof = {pid: ts for pid, ts in prof.items() if ts}
    out = []
    for i, ts in docs:
        matches = []
        for pid, pts in prof.items():
            common = ts & pts
            if not common:
                continue
            singles = [t for t in common if " " not in t]
            pairs = [t for t in common if " " in t]
            if len(singles) < MIN_TERMS and not pairs:
                continue
            weight = {t: (math.log((n + 1) / (df.get(t, 0) + 0.5)) + 0.5) * (2.0 if " " in t else 1.0) for t in common}
            score = sum(weight.values())
            if score < MIN_SCORE:
                continue
            # shown to the user: plain words, the rarest first (expressions only count in the score)
            shown = sorted(singles or {w for t in pairs for w in t.split()}, key=lambda t: (-weight.get(t, 0), t))
            shown = shown[:TOP_TERMS]
            matches.append({"project": pid, "score": round(score, 2), "terms": shown})
        if matches:
            matches.sort(key=lambda m: -m["score"])
            out.append((i, matches[:4], matches[0]["score"]))
    return out
