"""« Mesures » / « Measurements » page (D53): the committed benchmark summaries (`bench/results/*.json`, written by
`madalean bench … --publish`) as one table per problem set. Numbers are never typed by hand here."""
from __future__ import annotations

import json
from html import escape as E
from pathlib import Path

from . import layout

SETS = {
    "smoke": {"fr": "Jeu de contrôle (20 énoncés de Madalean)", "en": "Smoke set (20 statements written for Madalean)",
              "url": ""},
    "minif2f": {"fr": "miniF2F", "en": "miniF2F", "url": "https://github.com/yangky11/miniF2F-lean4"},
    "putnam": {"fr": "PutnamBench", "en": "PutnamBench", "url": "https://github.com/trishullab/PutnamBench"},
}
ORDER = ["minif2f", "putnam", "smoke"]
T = {
    "fr": {
        "title": "Mesures", "lead": "Ce que Madalean prouve réellement, en combien de temps et à quel coût — mesuré par "
        "le même programme que l'application, compté seulement quand un Lean neuf et strict accepte la preuve.",
        "how": "Comment lire ces tableaux",
        "how_items": [
            "Chaque ligne est un passage complet : un jeu de problèmes, une configuration, un espace Lean. L'énoncé "
            "formel est donné ; Madalean cherche la preuve ; la preuve trouvée est recompilée à part, sans « sorry », "
            "avec les seuls axiomes standards. Rien d'autre ne compte.",
            "« Échantillon » dit combien de problèmes ont été tirés du jeu, et avec quelle graine : un échantillon de "
            "50 problèmes donne une estimation à une dizaine de points près, pas un score officiel.",
            "Un énoncé que le Lean de l'espace de travail n'accepte pas (version de Mathlib différente de celle du "
            "jeu) est compté à part, jamais comme un échec.",
            "Le coût est celui des modèles payants, au prix public ; les modèles gratuits et la recherche dans Mathlib "
            "coûtent 0 $. Les passages publiés ici n'utilisent aucun modèle payant, sauf mention « payant ».",
            "Les limites de temps et d'essais sont courtes (quelques minutes par problème) : ces chiffres mesurent "
            "l'atelier tel qu'on l'utilise, pas le maximum atteignable avec des milliers d'essais.",
        ],
        "none": "Aucune mesure publiée pour l'instant.",
        "c_config": "Configuration", "c_sample": "Échantillon", "c_solved": "Prouvés", "c_time": "Temps médian",
        "c_cost": "Coût par preuve", "c_date": "Date", "c_versions": "Lean / Mathlib", "c_models": "Qui a trouvé",
        "of": "sur", "all": "tout le jeu", "seed": "graine", "split": "partie", "not_compiling": "énoncés non compilés",
        "partial": "passage incomplet", "paid": "payant", "free": "0 $ (gratuit)", "nomodel": "0 $ (sans modèle)",
        "no_proof": "—", "mathlib": "Mathlib (sans modèle)",
        "adapted": "Mathlib d'abord (courte preuve écrite par un modèle)", "limits": "limites",
        "per_problem": "s par problème", "attempts": "essais", "caption": "Résultats sur",
        "source": "Source", "licence": "licence", "commit": "version figée",
        "redo": "Refaire ces mesures",
        "redo_text": "Les jeux publics ne sont pas copiés dans Madalean : ils sont téléchargés à une version figée, "
        "avec leur licence, puis lus tels quels. Les commandes et les formats sont décrits dans",
        "redo_link": "docs/BENCH.md",
        "putnam_note": "PutnamBench demande de ne pas publier de preuves : seuls les comptes figurent ici.",
        "strategies": {"mathlib": "Recherche dans Mathlib seule, sans modèle",
                       "tournament": "Mathlib d'abord, puis tournoi de modèles gratuits",
                       "conductor": "Tournoi dirigé par le chef d'orchestre", "single": "Un seul modèle",
                       "goedel-local": "Goedel-Prover local (carte graphique)",
                       "certificate": "Certificats : Sage calcule, Lean vérifie"},
    },
    "en": {
        "title": "Measurements", "lead": "What Madalean actually proves, how fast and at what cost — measured by the "
        "same program as the application, counted only when a fresh strict Lean accepts the proof.",
        "how": "How to read these tables",
        "how_items": [
            "Each row is one complete run: a problem set, a configuration, a Lean workspace. The formal statement is "
            "given; Madalean searches for the proof; the proof found is compiled again on its own, without “sorry”, "
            "with the standard axioms only. Nothing else counts.",
            "“Sample” says how many problems were drawn from the set, and with which seed: a sample of 50 problems "
            "gives an estimate within about ten points, not an official score.",
            "A statement that the workspace's Lean does not accept (a Mathlib version other than the set's) is "
            "counted apart, never as a failure.",
            "The cost is that of paid models, at list price; free models and the Mathlib search cost $0. The runs "
            "published here use no paid model unless marked “paid”.",
            "Time and attempt limits are short (a few minutes per problem): these figures measure the workshop as it "
            "is used, not the maximum reachable with thousands of attempts.",
        ],
        "none": "No measurement published yet.",
        "c_config": "Configuration", "c_sample": "Sample", "c_solved": "Proved", "c_time": "Median time",
        "c_cost": "Cost per proof", "c_date": "Date", "c_versions": "Lean / Mathlib", "c_models": "Found by",
        "of": "of", "all": "whole set", "seed": "seed", "split": "split", "not_compiling": "statements not compiling",
        "partial": "incomplete run", "paid": "paid", "free": "$0 (free)", "nomodel": "$0 (no model)",
        "no_proof": "—", "mathlib": "Mathlib (no model)",
        "adapted": "Mathlib first (short proof written by a model)", "limits": "limits",
        "per_problem": "s per problem", "attempts": "attempts", "caption": "Results on",
        "source": "Source", "licence": "licence", "commit": "pinned version",
        "redo": "Reproducing these measurements",
        "redo_text": "The public sets are not copied into Madalean: they are downloaded at a pinned version, with "
        "their licence, and read as they are. Commands and formats are described in",
        "redo_link": "docs/BENCH.md",
        "putnam_note": "PutnamBench asks that proofs not be published: only counts appear here.",
        "strategies": {"mathlib": "Mathlib search only, no model",
                       "tournament": "Mathlib first, then a tournament of free models",
                       "conductor": "Tournament directed by the conductor", "single": "A single model",
                       "goedel-local": "Local Goedel-Prover (graphics card)",
                       "certificate": "Certificates: Sage computes, Lean checks"},
    },
}


def load(results: Path) -> list[dict]:
    out = []
    if results.is_dir():
        for f in sorted(results.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, dict) and d.get("format") == 1 and d.get("set") and "solved" in d:
                out.append(d)
    return out


def _num(x: float, lang: str, digits: int = 1) -> str:
    s = f"{x:.{digits}f}"
    return s.replace(".", ",") if lang == "fr" else s


def _cost(s: dict, t: dict, lang: str) -> str:
    cpv = s.get("cost_per_verified_usd")
    if cpv is None:
        return t["no_proof"]
    if not s.get("cost_usd"):
        return t["nomodel"] if not s.get("model_calls") else t["free"]
    return _num(cpv, lang, 4) + " $"


def _sample(s: dict, t: dict) -> str:
    sel = s.get("selection") or {}
    n, total = s.get("selected", 0), sel.get("set_size") or s.get("selected", 0)
    part = f'{t["split"]} « {E(str(sel["split"]))} », ' if sel.get("split") else ""
    if n >= total:
        return f'{part}{t["all"]} ({n})'
    seed = f', {t["seed"]} {sel["seed"]}' if sel.get("seed") is not None else ""
    return f'{part}{n} {t["of"]} {total}{seed}'


def _found(s: dict, t: dict) -> str:
    agg: dict[str, int] = {}
    for k, v in (s.get("found_by") or {}).items():
        name = (t["adapted"] if k.startswith("mathlib-first") else t["mathlib"] if k.startswith("mathlib")
                else k.split(":", 1)[-1].split("/")[-1].removesuffix(":free"))
        agg[name] = agg.get(name, 0) + int(v)
    return "<br>".join(f"{E(k)} × {v}" for k, v in sorted(agg.items(), key=lambda kv: -kv[1])) or "—"


def row(s: dict, lang: str) -> str:
    t = T[lang]
    b = s.get("budgets") or {}
    strat = t["strategies"].get(s.get("strategy", ""), s.get("strategy", ""))
    cfg = (f'<strong>{E(strat)}</strong><br><span class="muted"><code>{E(s["config"])}</code> · {t["limits"]} : '
           f'{int(b.get("time_per_problem_s", 0))} {t["per_problem"]}, {b.get("attempts", "?")} {t["attempts"]}'
           + (f' · <strong>{t["paid"]}</strong>' if s.get("paid") else "") + "</span>")
    solved = f'<strong>{s["solved"]} / {s["attempted"]}</strong>'
    if s.get("attempted"):
        solved += f' ({_num(100.0 * s["solved"] / s["attempted"], lang, 0)} %)'
    extra = []
    if s.get("statement_errors"):
        extra.append(f'{s["statement_errors"]} {t["not_compiling"]}')
    if not s.get("complete"):
        extra.append(t["partial"])
    if extra:
        solved += f'<br><span class="muted">{E(" · ".join(extra))}</span>'
    med = s.get("median_wall_s_solved")
    return (f'<tr><th scope="row">{cfg}</th><td>{_sample(s, t)}</td><td>{solved}</td>'
            f'<td>{(_num(med, lang) + " s") if med is not None else "—"}</td><td>{_cost(s, t, lang)}</td>'
            f'<td>{_found(s, t)}</td><td>{E(s.get("lean", ""))}<br><span class="muted">{E(s.get("mathlib", ""))}</span>'
            f'</td><td>{E(s.get("date", ""))}<br><span class="muted">Madalean {E(s.get("madalean", ""))}</span></td></tr>')


def table(name: str, rows: list[dict], lang: str) -> str:
    t = T[lang]
    info = SETS.get(name, {"fr": name, "en": name, "url": ""})
    src = next((r.get("source") or {} for r in rows if r.get("source")), {})
    meta = ""
    if src.get("repo"):
        url = f'https://github.com/{src["repo"]}/tree/{src.get("commit", "")}'
        meta = (f'<p class="muted">{t["source"]} : <a href="{E(url)}" rel="noopener noreferrer">{E(src["repo"])}</a> · '
                f'{t["commit"]} <code>{E(src.get("commit", "")[:12])}</code> · {t["licence"]} {E(src.get("licence", ""))}'
                + (f' · {t["putnam_note"]}' if name == "putnam" else "") + "</p>")
    elif src.get("licence"):
        meta = f'<p class="muted">{t["licence"]} {E(src["licence"])}</p>'
    rows = sorted(rows, key=lambda r: (r.get("workspace", ""), (r.get("selection") or {}).get("split", ""),
                                       r.get("config", "")))
    head = "".join(f'<th scope="col">{E(t[c])}</th>' for c in ("c_config", "c_sample", "c_solved", "c_time", "c_cost",
                                                               "c_models", "c_versions", "c_date"))
    return (f'<section aria-labelledby="set-{E(name)}"><h2 id="set-{E(name)}">{E(info[lang])}</h2>{meta}'
            f'<div class="table-wrap"><table><caption class="sr-only">{E(t["caption"])} {E(info[lang])}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(row(r, lang) for r in rows)}</tbody></table></div></section>')


def page(lang: str, results: list[dict], repo_url: str) -> str:
    t = T[lang]
    names = [n for n in ORDER if any(r["set"] == n for r in results)]
    names += sorted({r["set"] for r in results} - set(names))
    tables = "".join(table(n, [r for r in results if r["set"] == n], lang) for n in names) or f'<p>{E(t["none"])}</p>'
    how = "".join(f"<li>{E(x)}</li>" for x in t["how_items"])
    body = (f'<main id="main" class="narrow prose measures" tabindex="-1"><h1>{E(t["title"])}</h1>'
            f'<p class="lead">{E(t["lead"])}</p>{tables}'
            f'<section aria-labelledby="how"><h2 id="how">{E(t["how"])}</h2><ul>{how}</ul></section>'
            f'<section aria-labelledby="redo"><h2 id="redo">{E(t["redo"])}</h2><p>{E(t["redo_text"])} '
            f'<a href="{E(repo_url)}/blob/main/docs/BENCH.md" rel="noopener noreferrer">{E(t["redo_link"])}</a>.</p>'
            f'</section></main>')
    other = "en" if lang == "fr" else "fr"
    return layout.page(lang=lang, title=f'{t["title"]} — Madalean', body=body, root="../", description=t["lead"],
                       alt_href=f"../{other}/measures.html")


def build(out: Path, repo: Path, repo_url: str) -> int:
    results = load(repo / "bench" / "results")
    for lg in ("fr", "en"):
        (out / lg / "measures.html").write_text(page(lg, results, repo_url), encoding="utf-8")
    return len(results)
