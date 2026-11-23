"""The sources of « Actualités ». Each one is a public, keyless, machine-readable endpoint whose terms allow a
polite automated read; the endpoint, the fields and the terms were checked by hand on VERIFIED (docs/NEWS.md has
the table, with the sources that were left out and why).

Rules common to all sources (service.py): one GET per source and per refresh, a generic contact-less client name,
robots.txt of every host read on VERIFIED (a path it closes to all robots is not used — see LEFT_OUT),
conditional requests (ETag / Last-Modified) where the server supports them, exponential backoff on failure, never
in Local mode, redirects only to the hosts listed here. Only the title, an excerpt, the authors, the date and the
link are kept; the user reads the full text on the source's own site."""
from __future__ import annotations

import re
from dataclasses import dataclass

VERIFIED = "2026-11-22"
GROUPS: list[tuple[str, str, str]] = [
    ("papers", "Nouveaux articles", "New papers"),
    ("problems", "Problèmes ouverts", "Open problems"),
    ("lean", "Lean et Mathlib", "Lean and Mathlib"),
    ("ai", "IA pour les maths", "AI for mathematics"),
    ("community", "Annonces, prix et vulgarisation", "Announcements, prizes and outreach"),
    ("custom", "Vos flux", "Your feeds"),
]

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_MATH_N = 150
ARXIV_AI_N = 40
ARXIV_AI_QUERY = ("%28cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.LO%29+AND+%28abs:%22theorem+proving%22+OR+"
                  "abs:autoformalization+OR+abs:Mathlib+OR+abs:%22Lean+4%22+OR+abs:miniF2F+OR+"
                  "abs:%22proof+assistant%22+OR+abs:%22mathematical+reasoning%22%29")
# cs.AI & co. are kept only when the paper is about mathematics or proving (the API query is broad)
AI_MATH = re.compile(r"\b(theorem\w*|proofs?|provers?|proving|lean|mathlib|coq|isabelle|autoformali[sz]\w*|"
                     r"formali[sz]\w*|mathematic\w*|conjecture\w*|olympiad|minif2f|putnam\w*)\b", re.I)


@dataclass(frozen=True)
class Source:
    id: str
    group: str
    fr: str
    en: str
    about_fr: str
    about_en: str
    url: str
    hosts: frozenset
    parser: str                       # key of parsers.PARSERS
    home: str                         # the site, shown as a link
    licence: str
    terms: str                        # what the site asks of automated readers, and what we keep
    kind: str = "post"
    open: bool = False                # every item is an open problem (feeds only; other parsers decide per item)
    interval_h: float = 6.0           # never fetched more often than this, whatever the user's frequency
    keep_days: int = 0                # 0 = the user's retention; slow sources keep their items longer
    conditional: bool = True          # the server answers ETag / Last-Modified
    require: re.Pattern | None = None
    default_on: bool = True
    fixture: str = ""                 # recorded answer (demo mode and tests), in news/demo_data
    summaries: bool = False           # the licence allows giving the text to a model for a summary
    max_bytes: int = 4 * 1024 * 1024


_s = Source

SOURCES: list[Source] = [
    _s("arxiv-math", "papers", "arXiv — mathématiques", "arXiv — mathematics",
       "Les nouveaux articles de toutes les catégories de mathématiques (math.*) et de logique informatique (cs.LO).",
       "New papers of every mathematics category (math.*) and of logic in computer science (cs.LO).",
       f"{ARXIV_API}?search_query=cat:math.*+OR+cat:cs.LO&sortBy=submittedDate&sortOrder=descending"
       f"&max_results={ARXIV_MATH_N}",
       frozenset({"export.arxiv.org"}), "arxiv", "https://arxiv.org/archive/math",
       "metadata CC0 1.0 (abstracts under their authors' licences)",
       "arXiv API terms of use: at most one request every 3 s, a single connection; metadata may be stored and "
       "shown with a link to arxiv.org. One request per refresh here. (The API host's robots.txt closes it to "
       "crawlers; the API itself is the documented programmatic access and is used under its own terms.)",
       kind="paper", conditional=False, summaries=True, fixture="arxiv-math.xml"),
    _s("arxiv-ai", "ai", "arXiv — IA pour les maths", "arXiv — AI for mathematics",
       "Articles d'informatique (cs.AI, cs.LG, cs.CL, cs.LO) qui parlent de preuve automatique, de formalisation, "
       "de Lean ou de raisonnement mathématique.",
       "Computer-science papers (cs.AI, cs.LG, cs.CL, cs.LO) about automated proving, formalisation, Lean or "
       "mathematical reasoning.",
       f"{ARXIV_API}?search_query={ARXIV_AI_QUERY}&sortBy=submittedDate&sortOrder=descending"
       f"&max_results={ARXIV_AI_N}",
       frozenset({"export.arxiv.org"}), "arxiv", "https://arxiv.org/list/cs.AI/recent",
       "metadata CC0 1.0 (abstracts under their authors' licences)",
       "Same arXiv API terms as above; one request per refresh, 3 s after the previous arXiv request.",
       kind="paper", conditional=False, require=AI_MATH, summaries=True, fixture="arxiv-ai.xml"),
    _s("erdos", "problems", "Problèmes d'Erdős", "Erdős problems",
       "Les changements d'état des problèmes d'Erdős (ouvert, résolu, formalisé en Lean), d'après la table tenue "
       "par la communauté. L'énoncé se lit sur erdosproblems.com.",
       "Status changes of the Erdős problems (open, solved, formalised in Lean), from the community-maintained "
       "table. The statement is read on erdosproblems.com.",
       "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/problems.yaml",
       frozenset({"raw.githubusercontent.com"}), "erdos", "https://www.erdosproblems.com/",
       "Apache-2.0 (github.com/teorth/erdosproblems)",
       "A public repository file read through GitHub's raw host with a conditional request (ETag); the table has "
       "no statements, so none is copied. erdosproblems.com itself is not crawled.",
       kind="problem", interval_h=12, keep_days=120, fixture="erdos.yaml"),
    _s("mo-open", "problems", "MathOverflow — problèmes ouverts", "MathOverflow — open problems",
       "Les nouvelles questions de MathOverflow marquées « open-problems ».",
       "New MathOverflow questions tagged “open-problems”.",
       "https://api.stackexchange.com/2.3/questions?site=mathoverflow&tagged=open-problems&sort=creation"
       "&order=desc&pagesize=30&filter=withbody",
       frozenset({"api.stackexchange.com"}), "stackexchange",
       "https://mathoverflow.net/questions/tagged/open-problems",
       "CC BY-SA 4.0 (user contributions; attribution = author and link, both shown)",
       "Stack Exchange API without a key: 300 requests a day per address, and the answer's `backoff` field must "
       "be obeyed (it is). One request per refresh.",
       kind="question", conditional=False, keep_days=120, summaries=True, fixture="mo-open.json"),
    _s("polymath", "problems", "Polymath", "Polymath",
       "Le blog des projets Polymath : propositions de problèmes à résoudre à plusieurs.",
       "The blog of the Polymath projects: proposals of problems to solve together.",
       "https://polymathprojects.org/feed/",
       frozenset({"polymathprojects.org"}), "feed", "https://polymathprojects.org/",
       "© the authors; title, excerpt and link only",
       "Public RSS feed of the blog, read with a conditional request.",
       interval_h=24, keep_days=400, fixture="polymath.xml"),
    _s("lean-releases", "lean", "Lean — versions", "Lean — releases",
       "Les nouvelles versions de Lean 4.", "New releases of Lean 4.",
       "https://api.github.com/repos/leanprover/lean4/releases?per_page=10",
       frozenset({"api.github.com"}), "github_releases", "https://github.com/leanprover/lean4/releases",
       "Apache-2.0 project; release notes © their authors, excerpt and link only",
       "GitHub REST API without a key (60 requests an hour per address), conditional request (ETag: an unchanged "
       "answer does not count). The site's *.atom feeds are not used: github.com/robots.txt disallows them.",
       kind="release", interval_h=12, keep_days=200, fixture="lean-releases.json"),
    _s("mathlib-feat", "lean", "Mathlib — ajouts récents", "Mathlib — recent additions",
       "Les derniers ajouts intégrés à Mathlib (changements marqués « feat »), avec leur description.",
       "The latest additions merged into Mathlib (changes marked “feat”), with their description.",
       "https://api.github.com/repos/leanprover-community/mathlib4/commits?per_page=40",
       frozenset({"api.github.com"}), "github_commits", "https://github.com/leanprover-community/mathlib4/commits/master",
       "Apache-2.0 (Mathlib and its commit messages); title, excerpt and link",
       "GitHub REST API without a key, conditional request (ETag); one request per refresh, the 40 latest "
       "commits, of which only the additions are kept.",
       kind="change", interval_h=12, keep_days=45, require=re.compile(r"\Afeat\b"), summaries=True,
       fixture="mathlib-feat.json"),
    _s("lean-blog", "lean", "Blog de la communauté Lean", "Lean community blog",
       "Les articles du blog de la communauté Lean et Mathlib.", "Posts of the Lean and Mathlib community blog.",
       "https://leanprover-community.github.io/blog/rss.xml",
       frozenset({"leanprover-community.github.io"}), "feed", "https://leanprover-community.github.io/blog/",
       "© the authors; title, excerpt and link only",
       "Public RSS feed, conditional request.",
       interval_h=12, keep_days=400, fixture="lean-blog.xml"),
    _s("xena", "lean", "Xena (Kevin Buzzard)", "Xena (Kevin Buzzard)",
       "Le blog du projet Xena : formaliser les mathématiques en Lean.",
       "The Xena project's blog: formalising mathematics in Lean.",
       "https://xenaproject.wordpress.com/feed/",
       frozenset({"xenaproject.wordpress.com"}), "feed", "https://xenaproject.wordpress.com/",
       "© the authors; title, excerpt and link only",
       "Public RSS feed of the blog, conditional request.",
       interval_h=12, keep_days=400, fixture="xena.xml"),
    _s("tao", "community", "What's new (Terence Tao)", "What's new (Terence Tao)",
       "Le blog de Terence Tao : résultats récents, problèmes ouverts, IA et mathématiques.",
       "Terence Tao's blog: recent results, open problems, AI and mathematics.",
       "https://terrytao.wordpress.com/feed/",
       frozenset({"terrytao.wordpress.com"}), "feed", "https://terrytao.wordpress.com/",
       "© the author; title, excerpt and link only",
       "Public RSS feed of the blog, conditional request.",
       interval_h=12, keep_days=200, fixture="tao.xml"),
    _s("quanta", "community", "Quanta Magazine — mathématiques", "Quanta Magazine — mathematics",
       "Les articles de vulgarisation de Quanta Magazine sur les mathématiques (en anglais).",
       "Quanta Magazine's articles about mathematics.",
       "https://www.quantamagazine.org/mathematics/feed/",
       frozenset({"www.quantamagazine.org", "quantamagazine.org"}), "feed",
       "https://www.quantamagazine.org/mathematics/",
       "© Quanta Magazine; headline, excerpt and link only",
       "Public RSS feed offered by the magazine, conditional request (ETag).",
       interval_h=12, keep_days=200, fixture="quanta.xml"),
    _s("ams", "community", "AMS — annonces et prix", "AMS — news and prizes",
       "Les annonces de l'American Mathematical Society : prix, nominations, vie de la communauté.",
       "News of the American Mathematical Society: prizes, appointments, community life.",
       "https://www.ams.org/cgi-bin/content/news_items.cgi?rss=1",
       frozenset({"www.ams.org", "ams.org"}), "feed", "https://www.ams.org/news",
       "© American Mathematical Society; headline, excerpt and link only",
       "The RSS feed the AMS newsroom page advertises (`<link rel=alternate>`). No ETag: one request per refresh. "
       "ams.org/robots.txt allows indexing with links and short excerpts and reserves AI training: no summary.",
       conditional=False, interval_h=12, keep_days=200, fixture="ams.xml"),
    _s("idm", "community", "Images des mathématiques (CNRS)", "Images des mathématiques (CNRS)",
       "Des articles en français sur la recherche mathématique, écrits par des mathématiciens.",
       "Articles in French about mathematical research, written by mathematicians.",
       "https://images.math.cnrs.fr/feed/",
       frozenset({"images.math.cnrs.fr"}), "feed", "https://images.math.cnrs.fr/",
       "© the authors (each article states its licence); title, excerpt and link only",
       "Public RSS feed of the site, conditional request (ETag).",
       interval_h=12, keep_days=200, fixture="idm.xml"),
]
BY_ID = {s.id: s for s in SOURCES}
GROUP_IDS = [g[0] for g in GROUPS]

# Looked at on VERIFIED and left out (docs/NEWS.md §2 gives the detail)
LEFT_OUT: list[tuple[str, str]] = [
    ("OEIS new sequences", "the only listing of new sequences a program can read is the JSON search, and "
     "oeis.org/robots.txt disallows /search for automated clients; recent.txt has not changed since 2018"),
    ("GitHub *.atom feeds (releases, commits)", "github.com/robots.txt disallows *.atom; the REST API is used instead"),
    ("arXiv RSS (rss.arxiv.org)", "works, but is empty at weekends and on holidays; the API gives the same papers"),
    ("Open Problem Garden", "its RSS feed lists taxonomy pages, not problems; no API"),
    ("AIM problem lists (aimpl.org)", "no feed or API, and the TLS certificate does not match the host name"),
    ("lean-lang.org blog", "no feed found (the guessed feed addresses are not served)"),
    ("European Mathematical Society, IMU, SMF, Abel Prize", "no RSS / Atom feed advertised on their news pages"),
    ("Clay Mathematics Institute", "the feed answers but is empty"),
    ("CNRS Mathématiques (INSMI)", "the feed answers but has not been updated since 2022"),
    ("erdosproblems.com pages, LMFDB, zbMATH Open", "no listing of new items meant for automated reading"),
]
