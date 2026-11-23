# « Actualités » — the permanent mathematical watch (session S-AV, DECISIONS D54)

User request (2026-11-22): « une source d'information en permanence sur les actualités et les nouveaux problèmes de
mathématiques ». TODO « Stratégie 2.1 », item 3.

**Résumé (FR).** L'écran « Actualités » (menu du logo) montre ce qui est nouveau en mathématiques : articles d'arXiv
par domaine, problèmes ouverts (problèmes d'Erdős, MathOverflow), Lean et Mathlib, IA pour les maths, annonces et
prix. Le serveur va chercher ces informations toutes les 6 heures à 13 adresses publiques, sans
compte ni clé, et les garde dans une petite base locale : tout se lit hors ligne. En mode Local, rien n'est demandé à
Internet. Chaque élément peut être envoyé vers un projet (Sources, conjecture, dossier, note). Un résumé court en
français, par un modèle gratuit en ligne, est proposé en option pour les sources dont la licence le permet ; le texte
d'origine reste toujours affiché à côté. Les règles de chaque site pour les robots (robots.txt) ont été lues : ce
qu'un site ferme aux robots n'est pas utilisé (c'est pourquoi l'OEIS n'y est pas).
Ce qui vient d'Internet est traité comme un texte à lire, jamais comme une consigne.

Code: `madalean/news/` (registry, parsers, branches, store, relevance, summarize, service),
`madalean/server/plugins/news.py` (routes and the periodic task), `web/src/screens/news/`,
`web/src/screens/settings/NewsSettings.svelte`, `web/src/lib/news.svelte.ts`, `web/src/lib/api/news.ts`.
Tests: `tests/test_news.py`, `web/e2e/news.spec.ts`. Real fetch check: `scripts/dev/news_check.py`.

## 1. What it does

- **Sources**: a registry (`news/registry.py`); each entry has its endpoint, the hosts allowed to answer, its parser,
  its licence, a note on its terms, its own minimum interval and how long its items are kept. The user turns each
  one on or off and adds RSS / Atom feeds of their own (https, public host).
- **Refresh**: `NewsService.tick` every 10 minutes from the plugin's own task (first one 90 s after the start);
  it fetches only the sources that are due. Default frequency 6 h (user: 6 h, 12 h, 1 day, 2 days); a source is never
  asked more often than its own interval (6 h for arXiv and MathOverflow, 12 h for the feeds and GitHub, 24 h for
  Polymath). Never in Local mode, never in the demo, never when `MADALEAN_NO_UPDATE_CHECK=1` (tests).
- **Store**: `<config>/news/news.sqlite` (SQLite, WAL, FTS5). Deduplicated on a key (`arxiv:<id>` whatever the
  version or the query that found the paper, `mo:<id>`, `erdos:<n>@<status date>`, else the URL).
  Bounded: 30 days by default for papers (3–365), longer for slow sources (45–400 days, see the table), and at most
  5 000 items (200–20 000); saved items are never removed. About 2 kB per item.
- **Tagging** (`news/branches.py`): 15 branches — algebra, number theory, geometry, topology, analysis, PDE,
  probability, statistics, combinatorics, logic, category theory, numerical analysis, optimisation, mathematical
  physics, history / education. Evidence: arXiv categories, MSC 2020 codes, MathOverflow tags (`nt.number-theory`
  → `math.NT`), then keyword rules in English and French (two hits or one in the title; at most two branches from
  keywords).
- **« Pour mes projets »** (`news/relevance.py`): an item matches a project when it shares several rare terms (inverse
  document frequency over the stored items; two-word expressions count double) with the project's own texts: title,
  description, dossier titles / problems, note titles and tags, source titles. The matching terms are shown.
  **Entirely local**: no model, no network.
- **French summary** (`news/summarize.py`), optional: on demand per item, and — setting off by default — for at
  most 8 new unread items of the followed fields per refresh. A free online model on the latency-first path (D35 /
  D38: `classify.short_stage`), never a paid model, never a local one, never in Local mode; cached in the store;
  shown above the original title and abstract, never instead of them. Only for sources whose licence allows giving
  the text to a model (`registry.Source.summaries`: arXiv metadata, MathOverflow, Mathlib commit messages) and for
  the user's own feeds; a © source (blogs, magazines, societies) keeps title, excerpt and link — 422 `rights`.
  Hostile text: §4.
- **Screen**: search, field, source, « Non lus », « Mes domaines », « Problèmes ouverts », « Pour mes projets »,
  « Enregistrés »; each item with source, date, authors, abstract, external link; actions « Ajouter aux Sources du
  projet » (arXiv → the existing Sources import), « Créer une conjecture », « Créer un dossier à partir de ce
  problème » (created, not started), « Envoyer dans une note ». Home card « Nouveautés » and a number in the logo
  menu: unread items of the followed fields. Quiet by design: a number, never a toast or a system notification.

## 2. Sources (checked by hand on 2026-11-22)

Every source below answered a real request from this machine on 2026-11-22 through the server's own code path
(`scripts/dev/news_check.py`: one GET each, generic client name) and its answer was parsed; a trimmed copy of each
answer is the test fixture and the demo data (`madalean/news/demo_data/`, feeds cut to excerpts).

**robots.txt** of every host was read the same day. Rule applied: a path that a site closes to *all* robots is not
used. Consequences: no OEIS (its robots.txt disallows `/search`, the only machine-readable listing of new
sequences); no `*.atom` feed of github.com (disallowed) — the GitHub REST API instead, whose host has no robots.txt
and whose terms allow keyless reads (60 an hour per address). One judgement call, stated plainly: `export.arxiv.org`
answers `Disallow: /` to every robot, yet it is the host of the **documented arXiv API**, offered for programs under
the arXiv API Terms of Use (one request per 3 s, which the fetcher enforces); Madalean's Sources screen already uses
it. It is kept as API access under those terms — turn the two arXiv sources off in Réglages › Actualités if you read
the rule more strictly. The feeds of the AMS, Quanta, Images des mathématiques, Polymath, Xena, Tao and the Lean
community blog are allowed for `*`; ams.org adds content signals (`search=yes, ai-train=no`): links and short
excerpts are what is kept, and no summary is made from © sources.

| Id | What | Endpoint (host) | Format | Validators | Licence / what is kept | Min. interval | Kept |
|---|---|---|---|---|---|---|---|
| `arxiv-math` | new papers, `math.*` + `cs.LO` | `export.arxiv.org/api/query` (150 newest) | Atom | none | metadata CC0 1.0; abstract as metadata | 6 h | user (30 d) |
| `arxiv-ai` | AI for maths: `cs.AI`, `cs.LG`, `cs.CL`, `cs.LO` whose abstract mentions proving / formalisation / Lean / mathematical reasoning, then a local filter | `export.arxiv.org/api/query` (40 newest) | Atom | none | as above | 6 h | user (30 d) |
| `erdos` | Erdős problems: status changes (open, solved, Lean) | `raw.githubusercontent.com/teorth/erdosproblems/…/data/problems.yaml` | YAML table | ETag | Apache-2.0; no statement in the table, none copied | 12 h | 120 d |
| `mo-open` | MathOverflow, tag `open-problems`, newest | `api.stackexchange.com/2.3/questions` | JSON | none | CC BY-SA 4.0, author and link shown | 6 h | 120 d |
| `polymath` | Polymath blog | `polymathprojects.org/feed/` | RSS | Last-Modified | © authors; title, excerpt, link | 24 h | 400 d |
| `lean-releases` | Lean 4 releases | `api.github.com/repos/leanprover/lean4/releases` | JSON | ETag | excerpt and link | 12 h | 200 d |
| `mathlib-feat` | Mathlib: the latest additions (commits marked `feat`, of the 40 newest) | `api.github.com/repos/leanprover-community/mathlib4/commits` | JSON | ETag, Last-Modified | Apache-2.0; title, description, link | 12 h | 45 d |
| `lean-blog` | Lean community blog | `leanprover-community.github.io/blog/rss.xml` | RSS | ETag, Last-Modified | © authors; title, excerpt, link | 12 h | 400 d |
| `xena` | Xena project blog | `xenaproject.wordpress.com/feed/` | RSS | Last-Modified | © authors; title, excerpt, link | 12 h | 400 d |
| `tao` | Terence Tao's blog | `terrytao.wordpress.com/feed/` | RSS | Last-Modified | © author; title, excerpt, link | 12 h | 200 d |
| `quanta` | Quanta Magazine, mathematics | `www.quantamagazine.org/mathematics/feed/` | RSS | ETag, Last-Modified | © Quanta; headline, excerpt, link | 12 h | 200 d |
| `ams` | AMS news and prizes | `www.ams.org/cgi-bin/content/news_items.cgi?rss=1` (advertised by the newsroom page) | RSS | none | © AMS; headline, excerpt, link | 12 h | 200 d |
| `idm` | Images des mathématiques (CNRS), in French | `images.math.cnrs.fr/feed/` | RSS | ETag, Last-Modified | © authors; title, excerpt, link | 12 h | 200 d |

Terms noted per source (shown in Réglages › Actualités, `registry.Source.terms`): arXiv API — one request every 3 s
at most, a single connection (the research layer's rate limit already enforces 3 s per arXiv host); Stack Exchange
API without a key — 300 requests a day per address and the `backoff` field must be obeyed (it is: the source is not
asked again before it expires, even by a manual refresh); GitHub REST API without a key — 60 requests an hour per
address, shared with Madalean's own update check (two requests per 12 h here, conditional).
A full cycle is 13 GETs; at the default frequency that is at most 4 × 13 = 52 small requests a day, fewer in
practice (12 h and 24 h sources, `304 Not Modified`).

**Looked at and left out** (`registry.LEFT_OUT`):

| Source | Why |
|---|---|
| OEIS, new sequences | the only listing of new sequences a program can read is the JSON search (`/search?q=keyword:new&fmt=json` — it answered and was parsed), but `oeis.org/robots.txt` disallows `/search` for every robot; `recent.txt` has not changed since 2018 |
| GitHub `*.atom` feeds (releases, commits) | `github.com/robots.txt` disallows `/*.atom$`; the REST API is used instead |
| arXiv RSS (`rss.arxiv.org`) | works, but the feed is empty at weekends and on holidays (it was on 2026-11-22, a Sunday); the API gives the same papers every day |
| Open Problem Garden | its RSS feed lists taxonomy pages (« cubic graphs », author names), not problems; no API |
| AIM problem lists (`aimpl.org`) | no feed or API, and the TLS certificate does not match the host name |
| lean-lang.org blog | no feed found (`/blog/rss.xml`, `/blog/feed.xml` are not served) |
| European Mathematical Society, IMU, SMF, Abel Prize | no RSS / Atom feed advertised on their news pages |
| Clay Mathematics Institute | the feed answers but is empty |
| CNRS Mathématiques (INSMI) | the feed answers but has not been updated since 2022 |
| erdosproblems.com pages, LMFDB, zbMATH Open | no listing of new items meant for automated reading (the Erdős *table* on GitHub is used instead) |

A user who wants one of these can still add any RSS / Atom address under « Vos flux ».

## 3. Privacy: what leaves the machine

- **Only anonymous GETs to the hosts of the table above** (and to the hosts of the feeds the user added), with the
  client name `Madalean/2.0 (math news reader)`: no account, no key, no cookie (`DummyCookieJar`), no `Referer`, no
  name or e-mail address, no proxy from the environment. The request carries nothing about the user: the queries
  are the same for everyone (they do not depend on the followed fields or on the projects).
- **Relevance to the projects is computed locally**; project texts never leave the machine for this feature.
- **Summaries** (optional): the item's public title and abstract are sent to the free online model the brain picks;
  nothing else (no project text, no profile). Off in Local mode; never for © sources.
- **Local mode**: `refresh`, `tick`, the feed test and the summaries all stop before any request
  (`NewsService._get` refuses; test `test_local_mode_makes_zero_requests`).
- Read / saved flags, settings and fetch state stay in `<config>/news/`. The e-mail addresses found in fetched text
  are masked before storage (`[e-mail]`).

## 4. Hostile content (docs/SECURITY.md « News feeds »)

Everything fetched is untrusted. In order:
1. **Transport**: `research/fetch.py` (`check_url`: https, port 443, no IP literal, no local name; `PublicResolver`:
   resolve-then-connect, public addresses only; redirects re-validated hop by hop). A built-in source may only be
   answered by the hosts of its registry entry (a redirect elsewhere is an error); size limit 4 MB (2 MB for user
   feeds), 25 s.
2. **Parsing**: XML through `research.safety.parse_xml` (DTDs and entities refused); JSON with `json`; the Erdős
   table with a small line reader (no YAML loader, nothing evaluated). At most 400 items per answer.
3. **Text**: `parsers.clean_text` — HTML reduced to its text (scripts, styles, iframes, SVG dropped), control,
   zero-width and bidirectional-override characters removed, lengths capped (title 300, abstract 4 000). Links must
   be `http(s)` without credentials, else the item is dropped.
4. **Display**: titles and abstracts go through the app's safe Markdown renderer (`lib/md.ts`: no raw HTML, no
   images, DOMPurify, KaTeX `trust: false`); links open outside with `rel="noopener noreferrer"`.
5. **Models**: an item whose text looks like instructions to a model (`summarize.looks_like_injection`) is marked
   (`extra.suspect`), shown with a warning and **never sent to a model**. Otherwise the summary prompt wraps the text
   in `safety.wrap_untrusted` under a system message carrying `UNTRUSTED_RULE`; the call has no tools; the answer is
   reduced to plain text without links (`clean_summary`) and refused if it reads like instructions itself.
6. **Projects**: an item reaches a project only when the user presses one of the four buttons; « Créer un dossier »
   creates the dossier without starting it, so the statement is read before any model sees it.

## 5. Data model

`items(id, key UNIQUE, source, grp, kind, url, title, summary, authors, published, fetched, open, branches, cats,
extra, read, saved, fr, fr_model, fr_t, rel, rel_max)` + `items_fts(title, summary, authors, fr)`.
`kind` ∈ paper | problem | question | release | change | post; `open` = an open problem (MathOverflow
`open-problems`, an Erdős problem whose status starts with « open »); `branches` = space-separated branch ids;
`extra` = small source-specific facts (`arxiv`, `primary`, `erdos`, `state`, `prize`, `oeis` (A-numbers linked by an
Erdős problem), `repo`, `tag`, `score`, `suspect`);
`rel` = `[{project, score, terms}]`. Settings: `<config>/news/settings.json` `{enabled, interval_hours, branches,
sources, feeds, summaries, badge, keep_days, max_items}`; state: `state.json` (per source: `etag`, `modified`,
`checked`, `ok`, `error`, `failures`, `next`). API: docs/API.md §6e.

## 6. Limits (not done, or not verified)

- The tagging is rule-based: a paper outside arXiv's categories gets its branch from keywords and can be untagged or
  mis-tagged; the relevance match is lexical (shared rare words), not semantic, and gets noisier for projects with
  very long texts.
- 150 arXiv papers per request: on a day with more than 150 new `math.*` + `cs.LO` papers between two refreshes
  (6 h), the oldest of that window are missed.
- The Erdős table has no statements; the item links to erdosproblems.com.
- No source of new integer sequences (OEIS left out, see §2); no source for the prizes of the EMS, IMU, SMF or the
  Abel Prize (no feed) — the AMS feed is the only « prizes » source.
- robots.txt was read once, by hand, on 2026-11-22; the server does not re-read it at each refresh.
- Read / saved flags are per server, not per device.
- Summaries were tested with scripted models only (no real provider call in the tests).
- The `If-None-Match` / `304` path is tested against recorded answers, not observed live on each host.
- Not verified on the user's real server (the live service was not touched).
