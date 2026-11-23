"""Showcase home page (index.html in French, en/home.html in English) and the About page (fr/about.html,
en/about.html) — session S-AL, DECISIONS D44. Static HTML, no script needed: the demo « énoncé → Lean → preuve
vérifiée » is a CSS animation (still frames under prefers-reduced-motion). No version number is shown anywhere:
download links go to GitHub's « latest » release."""
from __future__ import annotations

import html

from . import layout
from .install import LATEST

E = html.escape

T = {
    "fr": {
        "title": "Madalean — de l'énoncé à la preuve vérifiée par Lean",
        "desc": "Madalean traduit vos énoncés en Lean 4, cherche la preuve avec les meilleurs modèles et ne déclare "
                "rien prouvé sans le verdict de Lean. Libre, installé chez vous, sur tous vos appareils.",
        "eyebrow": "Assistant de preuve pour Lean 4 et Mathlib",
        "h1": "Vos énoncés, prouvés pour de vrai.",
        "promise": "Écrivez un énoncé comme au tableau : Madalean le traduit en Lean, cherche la preuve avec les "
                   "meilleurs modèles d'IA et n'affirme rien que Lean n'ait vérifié.",
        "b_install": "Installer", "b_guide": "Guide d'installation", "b_manual": "Manuel", "b_dl": "Télécharger",
        "hero_note": "Logiciel libre · installé sur votre ordinateur · sans traceur",
        "demo_label": "Démonstration animée : un énoncé en français devient un énoncé Lean, puis une preuve vérifiée.",
        "d1": "Énoncé", "d2": "Lean", "d3": "Preuve vérifiée",
        "d1_text": "La somme de deux entiers pairs est paire.",
        "d3_badge": "Vérifiée par Lean", "d3_axioms": "axiomes standard seulement",
        "features_h": "Tout le travail mathématique, au même endroit",
        "f": [
            ("proof", "Preuves", "Énoncé vérifié avant la preuve, recherche dans Mathlib d'abord, tournoi des "
             "meilleurs modèles, plans de preuve en lemmes. « Prouvé » veut toujours dire : accepté par Lean.",
             "workflow.html", "De l'énoncé à la preuve"),
            ("calc", "Calcul", "Carnets SageMath et Python en langage naturel, courbes et géométrie, dans un bac à "
             "sable hors ligne. Un résultat devient une conjecture ou un dossier Lean en un clic.",
             "calcul.html", "Calcul"),
            ("article", "Article", "Éditeur LaTeX visuel, aperçu PDF, bibliographie, échange avec Overleaf ; "
             "chaque résultat cité garde son lien vers sa preuve Lean.", "articles.html", "Article et bibliographie"),
            ("publish", "Publier", "Un site statique de votre projet sur GitHub Pages, revérifié indépendamment par "
             "lake build : les lecteurs voient ce qui est prouvé, et par quoi.", "publish.html", "Publier un projet"),
            ("devices", "Appareils", "L'ordinateur hôte calcule ; téléphone, tablette et autres PC s'y relient par "
             "votre réseau privé Tailscale, avec l'application ou un simple navigateur.", "pairing.html",
             "Relier un appareil"),
            ("cert", "Certificats", "Sage cherche un témoin — facteur, certificat de primalité, somme de carrés, "
             "contre-exemple — et Lean ne fait que le vérifier : sans modèle, sans coût, en quelques secondes.",
             "certificates.html", "Certificats"),
            ("conj", "Conjectures", "« Explorer » : une expérience Sage, des motifs reconnus (OEIS, récurrences, "
             "séries génératrices), un énoncé Lean précis, la chasse au contre-exemple, puis la preuve.",
             "conjectures.html", "Le moteur de conjectures"),
            ("news", "Actualités", "Veille permanente : nouveautés arXiv, problèmes ouverts (Erdős, MathOverflow), "
             "Lean et Mathlib, annonces ; triées par branche et par vos projets, lisibles hors ligne.",
             "news.html", "Actualités"),
            ("bench", "Mesures", "Madalean se mesure lui-même sur miniF2F et PutnamBench : seules comptent les "
             "preuves qu'un Lean neuf et strict accepte, avec le temps et le coût de chacune.",
             "measures.html", "Mesures"),
        ],
        "shots_h": "Un aperçu",
        "shots": [("home.png", "L'accueil : vos dossiers, leur état et ce qui tourne."),
                  ("lean-statement.png", "Un énoncé et sa traduction Lean, expliquée pas à pas."),
                  ("proof-learn.png", "Une preuve vérifiée, lue ligne par ligne en mode Apprendre.")],
        "how_h": "Comment ça marche",
        "how_p": "Un seul ordinateur fait le travail lourd : Lean et Mathlib, les modèles, SageMath, LaTeX. Vos autres "
                 "appareils s'y relient par Tailscale, un réseau privé chiffré entre vos appareils : rien n'est ouvert "
                 "sur Internet.",
        "how": ["L'hôte (Linux) garde vos projets, vos clés et toute la vérification.",
                "Chaque appareil est relié une fois, par un code à 6 chiffres ; vous pouvez le délier à tout moment.",
                "Les modèles en ligne sont appelés depuis l'hôte, avec vos clés et dans vos plafonds de dépense."],
        "svg_host": "Ordinateur hôte", "svg_host2": "Lean · Mathlib · modèles", "svg_host3": "SageMath · LaTeX",
        "svg_net": "Tailscale (privé, chiffré)", "svg_phone": "Téléphone", "svg_tablet": "Tablette",
        "svg_pc": "Autre PC", "svg_browser": "Navigateur",
        "svg_label": "Schéma : l'ordinateur hôte au centre du travail, relié par Tailscale au téléphone, à la "
                     "tablette, à un autre PC et à un navigateur.",
        "steps_h": "Installer en 3 étapes",
        "steps": [("Téléchargez l'installateur", "Un seul fichier, <code>Madalean-installer.run</code>, toujours la "
                   "dernière version."),
                  ("Rendez-le exécutable, ouvrez-le", "Clic droit › Propriétés › « Autoriser l'exécution », ou "
                   "<code>chmod +x Madalean-installer.run</code>, puis double-clic."),
                  ("Suivez l'assistant", "Il regarde votre machine, conseille quoi installer ou réutiliser "
                   "(SageMath, LaTeX, modèles locaux) et vous guide jusqu'à la première configuration.")],
        "steps_more": "Toutes les façons d'installer, pas à pas",
        "faq_h": "Questions fréquentes",
        "faq": [
            ("Faut-il une carte graphique ?", "Non. Sans carte NVIDIA, Madalean utilise les modèles en ligne (plusieurs "
             "sont gratuits avec une clé). Avec une carte d'au moins 8 Go, il peut aussi travailler hors connexion avec "
             "des modèles locaux ; l'installateur vous dit ce qui convient à votre machine."),
            ("Est-ce gratuit ?", "Madalean est un logiciel libre (licence Apache-2.0). Les modèles en ligne gratuits "
             "suffisent pour commencer ; les modèles payants sont facultatifs et toujours plafonnés."),
            ("Faut-il connaître Lean ?", "Non. Vous écrivez en français ou en anglais ; Madalean traduit, explique "
             "l'énoncé Lean et la preuve, et le mode Apprendre vous guide pas à pas."),
            ("Mes données quittent-elles mon ordinateur ?", "Vos projets restent sur l'hôte. Seul le texte envoyé "
             "aux modèles en ligne que vous choisissez sort ; en mode local, rien ne sort."),
            ("Et Windows, macOS, iPhone ?", "L'hôte s'installe sous Linux. Tous les autres appareils peuvent s'y "
             "relier : application Android, application de bureau Linux, ou n'importe quel navigateur."),
            ("Pourquoi ferais-je confiance au résultat ?", "Parce que ce n'est pas l'IA qui décide : chaque preuve "
             "est revérifiée par un Lean neuf et strict, et la liste des axiomes utilisés est contrôlée."),
        ],
        "author_h": "Conçu par un mathématicien, pour les mathématiciens",
        "author_p": "Madalean est développé par RANIRIAMANJAKA Antsa. Questions, idées, problèmes : écrivez-moi.",
        "author_more": "À propos et contact",
        # about page
        "a_title": "À propos de Madalean", "a_lead": "Madalean est un assistant de démonstration pour Lean 4 et "
                   "Mathlib : il aide à énoncer, formaliser, prouver, calculer et rédiger, et ne déclare rien prouvé "
                   "sans le verdict de Lean.",
        "a_author": "Auteur et contact", "a_mail": "Courriel", "a_github": "GitHub",
        "a_issue": "Signaler un problème ou proposer une idée", "a_issue_text": "Sur GitHub (tickets publics), ou par "
                   "courriel si vous préférez.",
        "a_licence": "Licence", "a_licence_text": "Madalean est un logiciel libre distribué sous licence Apache-2.0. "
                     "Vous pouvez l'utiliser, l'étudier, le modifier et le redistribuer.",
        "a_licence_link": "Texte de la licence",
        "a_source": "Code source", "a_credits": "Remerciements",
        "a_credits_text": "Madalean s'appuie sur Lean 4 et Mathlib, les modèles Goedel-Prover, SageMath, JupyterLab, "
                          "tectonic, llama.cpp, Tailscale, KaTeX et les polices Source Serif / Source Sans. Merci à "
                          "leurs communautés.",
        "a_site": "Ce site", "a_site_text": "Aucun traceur, aucun cookie, aucune ressource externe ; tout est servi "
                  "par GitHub Pages. Les liens de téléchargement mènent toujours à la dernière version publiée.",
    },
    "en": {
        "title": "Madalean — from the statement to a proof checked by Lean",
        "desc": "Madalean translates your statements into Lean 4, searches for the proof with the best models and "
                "declares nothing proved without Lean's verdict. Free software, installed at home, on all your devices.",
        "eyebrow": "Proof assistant companion for Lean 4 and Mathlib",
        "h1": "Your statements, proved for real.",
        "promise": "Write a statement as you would on the blackboard: Madalean translates it into Lean, searches for "
                   "the proof with the best AI models and claims nothing that Lean has not checked.",
        "b_install": "Install", "b_guide": "Installation guide", "b_manual": "Manual", "b_dl": "Download",
        "hero_note": "Free software · installed on your computer · no tracker",
        "demo_label": "Animated demo: a statement in plain words becomes a Lean statement, then a checked proof.",
        "d1": "Statement", "d2": "Lean", "d3": "Checked proof",
        "d1_text": "The sum of two even integers is even.",
        "d3_badge": "Checked by Lean", "d3_axioms": "standard axioms only",
        "features_h": "All your mathematical work, in one place",
        "f": [
            ("proof", "Proofs", "Statement checked before the proof, Mathlib searched first, a tournament of the best "
             "models, proof plans split into lemmas. “Proved” always means: accepted by Lean.",
             "workflow.html", "From statement to proof"),
            ("calc", "Computations", "SageMath and Python notebooks in plain language, curves and geometry, in an "
             "offline sandbox. A result becomes a conjecture or a Lean file in one click.",
             "calcul.html", "Computations"),
            ("article", "Article", "Visual LaTeX editor, PDF preview, bibliography, exchange with Overleaf; every "
             "cited result keeps its link to its Lean proof.", "articles.html", "Article and bibliography"),
            ("publish", "Publish", "A static site of your project on GitHub Pages, independently re-checked by lake "
             "build: readers see what is proved, and by what.", "publish.html", "Publishing a project"),
            ("devices", "Devices", "The host computer computes; phone, tablet and other PCs link to it over your "
             "private Tailscale network, with the app or just a browser.", "pairing.html", "Linking a device"),
            ("cert", "Certificates", "Sage finds a witness — a factor, a primality certificate, a sum of squares, a "
             "counterexample — and Lean only checks it: no model, no cost, in a few seconds.",
             "certificates.html", "Certificates"),
            ("conj", "Conjectures", "« Explore »: a Sage experiment, recognised patterns (OEIS, recurrences, "
             "generating functions), a precise Lean statement, a counterexample hunt, then the proof.",
             "conjectures.html", "The conjecture engine"),
            ("news", "News", "A permanent watch: new arXiv papers, open problems (Erdős, MathOverflow), Lean and "
             "Mathlib, announcements; sorted by branch and by your projects, readable offline.",
             "news.html", "News"),
            ("bench", "Measurements", "Madalean measures itself on miniF2F and PutnamBench: only proofs accepted by a "
             "fresh strict Lean count, with the time and cost of each.", "measures.html", "Measurements"),
        ],
        "shots_h": "A glimpse",
        "shots": [("home.png", "Home: your files, their state and what is running."),
                  ("lean-statement.png", "A statement and its Lean translation, explained step by step."),
                  ("proof-learn.png", "A checked proof, read line by line in Learn mode.")],
        "how_h": "How it works",
        "how_p": "One computer does the heavy work: Lean and Mathlib, the models, SageMath, LaTeX. Your other devices "
                 "link to it through Tailscale, an encrypted private network between your devices: nothing is opened "
                 "to the Internet.",
        "how": ["The host (Linux) keeps your projects, your keys and all the checking.",
                "Each device is linked once, with a 6-digit code; you can unlink it at any time.",
                "Online models are called from the host, with your keys and within your spending caps."],
        "svg_host": "Host computer", "svg_host2": "Lean · Mathlib · models", "svg_host3": "SageMath · LaTeX",
        "svg_net": "Tailscale (private, encrypted)", "svg_phone": "Phone", "svg_tablet": "Tablet",
        "svg_pc": "Another PC", "svg_browser": "Browser",
        "svg_label": "Diagram: the host computer at the centre of the work, linked through Tailscale to a phone, a "
                     "tablet, another PC and a browser.",
        "steps_h": "Install in 3 steps",
        "steps": [("Download the installer", "One file, <code>Madalean-installer.run</code>, always the latest "
                   "version."),
                  ("Make it executable, open it", "Right-click › Properties › “Allow executing”, or "
                   "<code>chmod +x Madalean-installer.run</code>, then double-click."),
                  ("Follow the assistant", "It looks at your machine, advises what to install or reuse (SageMath, "
                   "LaTeX, local models) and guides you up to the first configuration.")],
        "steps_more": "Every way to install, step by step",
        "faq_h": "Frequently asked questions",
        "faq": [
            ("Do I need a graphics card?", "No. Without an NVIDIA card, Madalean uses online models (several are free "
             "with a key). With a card of at least 8 GB it can also work offline with local models; the installer "
             "tells you what suits your machine."),
            ("Is it free?", "Madalean is free software (Apache-2.0 licence). Free online models are enough to start; "
             "paid models are optional and always capped."),
            ("Do I need to know Lean?", "No. You write in English or French; Madalean translates, explains the Lean "
             "statement and the proof, and Learn mode guides you step by step."),
            ("Does my data leave my computer?", "Your projects stay on the host. Only the text sent to the online "
             "models you choose leaves it; in local mode, nothing does."),
            ("What about Windows, macOS, iPhone?", "The host is installed on Linux. Every other device can link to "
             "it: Android app, Linux desktop app, or any browser."),
            ("Why should I trust the result?", "Because the AI does not decide: every proof is re-checked by a fresh, "
             "strict Lean, and the list of axioms used is checked."),
        ],
        "author_h": "Designed by a mathematician, for mathematicians",
        "author_p": "Madalean is developed by RANIRIAMANJAKA Antsa. Questions, ideas, problems: write to me.",
        "author_more": "About and contact",
        "a_title": "About Madalean", "a_lead": "Madalean is a proof assistant companion for Lean 4 and Mathlib: it helps "
                   "you state, formalise, prove, compute and write, and declares nothing proved without Lean's "
                   "verdict.",
        "a_author": "Author and contact", "a_mail": "E-mail", "a_github": "GitHub",
        "a_issue": "Report a problem or suggest an idea", "a_issue_text": "On GitHub (public issues), or by e-mail if "
                   "you prefer.",
        "a_licence": "Licence", "a_licence_text": "Madalean is free software released under the Apache-2.0 licence. "
                     "You may use, study, modify and redistribute it.",
        "a_licence_link": "Licence text",
        "a_source": "Source code", "a_credits": "Acknowledgements",
        "a_credits_text": "Madalean builds on Lean 4 and Mathlib, the Goedel-Prover models, SageMath, JupyterLab, "
                          "tectonic, llama.cpp, Tailscale, KaTeX and the Source Serif / Source Sans fonts. Thanks to "
                          "their communities.",
        "a_site": "This site", "a_site_text": "No tracker, no cookie, no external resource; everything is served by "
                  "GitHub Pages. Download links always lead to the latest published version.",
    },
}

ICONS = {   # 24×24 line icons (currentColor)
    "proof": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "calc": '<path d="M4 19h16M6 16l3.5-5 3 3L18 6"/><circle cx="18" cy="6" r="1.4"/>',
    "article": '<path d="M7 3.5h7l4 4V20.5H7z"/><path d="M14 3.5v4h4M9.5 12h6M9.5 15.5h6"/>',
    "publish": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 2.6 14.6 0 17M12 3.5c-2.6 2.4-2.6 14.6 0 17"/>',
    "devices": '<rect x="3" y="5" width="13" height="10" rx="1.5"/><path d="M1.5 18.5h16"/><rect x="17.5" y="9" width="5" height="10" rx="1.2"/>',
    "cert": '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "conj": '<path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1 1-1 1.7v.5"/><circle cx="12" cy="17" r=".6"/><circle cx="12" cy="12" r="9"/>',
    "news": '<rect x="3.5" y="5" width="13" height="14" rx="1.5"/><path d="M16.5 9h3v8.5a1.5 1.5 0 0 1-3 0M7 9h6M7 12.5h6M7 16h4"/>',
    "bench": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
}


def icon(name: str) -> str:
    return (f'<svg class="f-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def demo(t: dict) -> str:
    lean = ('<span class="hl-kw">theorem</span> even_add_even (a b : <span class="hl-ty">ℤ</span>)\n'
            '    (ha : Even a) (hb : Even b) :\n    Even (a + b) := <span class="hl-kw">by</span>\n  '
            '<span class="hl-sorry">sorry</span>')
    proof = ('<span class="hl-kw">theorem</span> even_add_even (a b : <span class="hl-ty">ℤ</span>)\n'
             '    (ha : Even a) (hb : Even b) :\n    Even (a + b) := <span class="hl-kw">by</span>\n  '
             '<span class="hl-tac">exact</span> ha.add hb')
    return (f'<figure class="demo" aria-label="{E(t["demo_label"])}"><div class="demo-bar" aria-hidden="true">'
            '<span></span><span></span><span></span>'
            f'<ol class="demo-steps"><li class="ds ds1">{E(t["d1"])}</li><li class="ds ds2">{E(t["d2"])}</li>'
            f'<li class="ds ds3">{E(t["d3"])}</li></ol></div><div class="demo-stage">'
            f'<div class="frame f1"><p class="frame-k">{E(t["d1"])}</p><p class="frame-nl">« {E(t["d1_text"])} »</p></div>'
            f'<div class="frame f2"><p class="frame-k">{E(t["d2"])}</p><pre><code>{lean}</code></pre></div>'
            f'<div class="frame f3"><p class="frame-k">{E(t["d3"])}</p><pre><code>{proof}</code></pre>'
            f'<p class="verified"><span class="tick" aria-hidden="true">✓</span> {E(t["d3_badge"])} '
            f'<span class="ax">· {E(t["d3_axioms"])}</span></p></div></div></figure>')


def diagram(t: dict) -> str:
    def dev(y: int, label: str, shape: str) -> str:      # one device per row, label on the right
        return (f'<g class="hw-dev" transform="translate(640 {y})">{shape}'
                f'<text x="44" y="26">{E(label)}</text></g>')
    phone = '<rect x="-12" y="4" width="24" height="44" rx="5"/><path d="M-5 42h10"/>'
    tablet = '<rect x="-22" y="6" width="44" height="40" rx="5"/>'
    pc = '<rect x="-26" y="8" width="52" height="30" rx="3"/><path d="M-32 44h64"/>'
    browser = '<rect x="-26" y="6" width="52" height="40" rx="4"/><path d="M-26 16h52"/><circle cx="-20" cy="11" r="1.6"/>'
    links = "".join(f'<path class="hw-link" d="M480 150 C 560 150, 560 {y + 26}, 606 {y + 26}"/>' for y in (2, 76, 150, 224))
    devs = (dev(2, t["svg_phone"], phone) + dev(76, t["svg_tablet"], tablet) + dev(150, t["svg_pc"], pc)
            + dev(224, t["svg_browser"], browser))
    return (f'<svg class="how-svg" viewBox="0 0 800 300" role="img" aria-label="{E(t["svg_label"])}">'
            '<defs><linearGradient id="hw-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#002b5c"/>'
            '<stop offset="1" stop-color="#0b4f9c"/></linearGradient></defs>'
            '<g class="hw-host"><rect x="24" y="70" width="230" height="160" rx="18" fill="url(#hw-g)"/>'
            '<rect x="24" y="70" width="230" height="6" rx="3" class="hw-accent"/>'
            f'<text x="139" y="130" text-anchor="middle" class="hw-t1">{E(t["svg_host"])}</text>'
            f'<text x="139" y="160" text-anchor="middle" class="hw-t2">{E(t["svg_host2"])}</text>'
            f'<text x="139" y="184" text-anchor="middle" class="hw-t2">{E(t["svg_host3"])}</text></g>'
            '<path class="hw-link" d="M254 150 C 330 150, 330 150, 400 150"/>'
            '<g class="hw-net"><rect x="320" y="118" width="160" height="64" rx="32"/>'
            f'<text x="400" y="146" text-anchor="middle" class="hw-t3">Tailscale</text>'
            f'<text x="400" y="166" text-anchor="middle" class="hw-t4">{E(t["svg_net"].split("(")[1].rstrip(")"))}</text></g>'
            + links + devs + '</svg>')


def home_page(lang: str, root: str) -> str:
    t = T[lang]
    L = lambda p: f"{root}{lang}/{p}"   # noqa: E731
    shots = "".join(f'<figure class="shot"><img src="{root}img/{n}" alt="{E(a)}" loading="lazy" decoding="async" '
                    f'width="1440" height="900"><figcaption>{E(a)}</figcaption></figure>' for n, a in t["shots"])
    feats = "".join(f'<article class="feature">{icon(k)}<h3>{E(h)}</h3><p>{E(p)}</p>'
                    f'<p><a href="{L(href)}">{E(more)}<span class="sr-only"> — {E(h)}</span></a></p></article>'
                    for k, h, p, href, more in t["f"])
    steps = "".join(f'<li><span class="step-n" aria-hidden="true">{i}</span><h3>{E(h)}</h3><p>{p}</p></li>'
                    for i, (h, p) in enumerate(t["steps"], 1))
    faq = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in t["faq"])
    body = (
        '<main id="main" class="home" tabindex="-1">'
        '<section class="hero"><div class="hero-in"><div class="hero-text">'
        f'<img class="hero-mark" src="{root}assets/wordmark-dark.svg" alt="Madalean" width="244" height="72">'
        f'<p class="eyebrow">{E(t["eyebrow"])}</p><h1>{E(t["h1"])}</h1><p class="promise">{E(t["promise"])}</p>'
        f'<div class="cta"><a class="btn btn-primary" href="{L("download.html")}">{E(t["b_install"])}</a>'
        f'<a class="btn btn-ghost" href="{L("install.html")}">{E(t["b_guide"])}</a>'
        f'<a class="btn btn-ghost" href="{L("index.html")}">{E(t["b_manual"])}</a>'
        f'<a class="btn btn-ghost" href="{LATEST}" rel="noopener noreferrer">{E(t["b_dl"])}</a></div>'
        f'<p class="hero-note">{E(t["hero_note"])}</p></div>{demo(t)}</div></section>'
        f'<section class="band" aria-labelledby="features"><div class="band-in"><h2 id="features">{E(t["features_h"])}</h2>'
        f'<div class="features">{feats}</div></div></section>'
        f'<section class="band band-alt" aria-labelledby="shots"><div class="band-in"><h2 id="shots">{E(t["shots_h"])}</h2>'
        f'<div class="shots">{shots}</div></div></section>'
        f'<section class="band" aria-labelledby="how"><div class="band-in how"><div><h2 id="how">{E(t["how_h"])}</h2>'
        f'<p>{E(t["how_p"])}</p><ul class="checks">' + "".join(f"<li>{E(x)}</li>" for x in t["how"]) +
        f'</ul><p><a href="{L("tailscale.html")}">Tailscale</a> · <a href="{L("pairing.html")}">'
        f'{E(t["f"][4][4])}</a></p></div>{diagram(t)}</div></section>'
        f'<section class="band band-ink" aria-labelledby="steps"><div class="band-in"><h2 id="steps">{E(t["steps_h"])}</h2>'
        f'<ol class="steps3">{steps}</ol><p class="cta"><a class="btn btn-primary" href="{L("download.html")}">'
        f'{E(t["b_install"])}</a><a class="btn btn-ghost" href="{L("install.html")}">{E(t["steps_more"])}</a></p>'
        f'</div></section>'
        f'<section class="band" aria-labelledby="faq"><div class="band-in narrow-in"><h2 id="faq">{E(t["faq_h"])}</h2>'
        f'{faq}</div></section>'
        f'<section class="band band-alt" aria-labelledby="author"><div class="band-in author">'
        f'<h2 id="author">{E(t["author_h"])}</h2><p>{E(t["author_p"])}</p>'
        f'<p class="author-card"><strong>{E(layout.AUTHOR["name"])}</strong><br>'
        f'<a href="mailto:{layout.AUTHOR["email"]}">{E(layout.AUTHOR["email"])}</a> · '
        f'<a href="{layout.AUTHOR["github"]}" rel="noopener noreferrer">github.com/raantss18</a></p>'
        f'<p><a href="{L("about.html")}">{E(t["author_more"])}</a></p></div></section></main>')
    alt = f"{root}en/home.html" if lang == "fr" else f"{root}index.html"
    return layout.page(lang=lang, title=t["title"], body=body, root=root, description=t["desc"], alt_href=alt,
                       active="home")


def about_page(lang: str) -> str:
    t = T[lang]
    a = layout.AUTHOR
    repo = a["repo"]
    body = (f'<main id="main" class="narrow prose about" tabindex="-1"><h1>{E(t["a_title"])}</h1>'
            f'<p class="lead">{E(t["a_lead"])}</p>'
            f'<section aria-labelledby="contact"><h2 id="contact">{E(t["a_author"])}</h2>'
            f'<div class="contact-card"><img src="../assets/icon.svg" alt="" width="56" height="56">'
            f'<div><p class="contact-name">{E(a["name"])}</p><dl class="contact-list">'
            f'<dt>{E(t["a_mail"])}</dt><dd><a href="mailto:{a["email"]}">{E(a["email"])}</a></dd>'
            f'<dt>{E(t["a_github"])}</dt><dd><a href="{a["github"]}" rel="noopener noreferrer">github.com/raantss18</a></dd>'
            f'</dl></div></div></section>'
            f'<section aria-labelledby="issues"><h2 id="issues">{E(t["a_issue"])}</h2><p>{E(t["a_issue_text"])}</p>'
            f'<p><a href="{repo}/issues" rel="noopener noreferrer">{repo.replace("https://", "")}/issues</a></p></section>'
            f'<section aria-labelledby="licence"><h2 id="licence">{E(t["a_licence"])}</h2><p>{E(t["a_licence_text"])}</p>'
            f'<p><a href="{repo}/blob/main/LICENSE" rel="noopener noreferrer">{E(t["a_licence_link"])}</a> · '
            f'<a href="{repo}" rel="noopener noreferrer">{E(t["a_source"])}</a></p></section>'
            f'<section aria-labelledby="credits"><h2 id="credits">{E(t["a_credits"])}</h2><p>{E(t["a_credits_text"])}</p></section>'
            f'<section aria-labelledby="site"><h2 id="site">{E(t["a_site"])}</h2><p>{E(t["a_site_text"])}</p></section>'
            '</main>')
    other = "en" if lang == "fr" else "fr"
    return layout.page(lang=lang, title=f'{t["a_title"]} — Madalean', body=body, root="../",
                       description=t["a_lead"], alt_href=f"../{other}/about.html", active="about")
