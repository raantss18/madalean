# Malagasy (`mg`)

Interface catalogue: `web/src/lib/i18n/mg.ts` (partial), screen strings `lib/exercises/strings.ts` and
`lib/calcul/strings.ts` (`MG`), server messages `madalean/i18n_mg.py`, exercise texts `madalean/teaching/seed.json`
(source: `scripts/dev/exercise_seed.py`).

**Fallback**: mg → French → key. Never English. Contents that exist in French and English only (manual, glossary
entries, examples, model prompts, exports) are shown in French: client `i18n.base`, server `i18n.language()`
(`i18n.ui_language()` is the language of the interface). A model's remarks on an exercise are asked in Malagasy; its
quality depends on the model.

Every string was machine-assisted: **« à relire »**. To correct a term: change it here and in the files above, then
`npx vitest run` (placeholders are checked).

## Terminology

| Français | Malagasy used | Status |
|---|---|---|
| preuve / prouver | porofo / porofoy | à relire |
| théorème, lemme | teorema, lemma | à relire |
| énoncé (d'un exercice, d'un dossier) | laza adina | à relire — **doubtful**: natural for an exercise; for a theorem, « fehezan-teny » or « fanambarana »? |
| exercice | fanazaran-tena | à relire |
| indice | toro-hevitra | à relire — **doubtful**: also « advice »; « famantarana »? |
| solution | vahaolana | à relire |
| calcul | kajy | à relire |
| vérifier | hamarino, fanamarinana | à relire |
| accepté / refusé par Lean | neken'i / nolavin'i Lean | à relire |
| niveau | ambaratonga | à relire |
| domaine | sehatra | à relire |
| nombre, entier naturel | isa, isa natoraly | **doubtful** (« isa voajanahary »?) |
| nombre premier | isa voalohany | given by the user (note: « premier » also means « first ») |
| pair / impair | (tsy) azo zaraina amin'ny 2 | described on purpose: no term chosen |
| divisible par | azo zaraina amin'ny | à relire |
| reste (division) | ambiny | à relire |
| somme | fitambarana | **doubtful** (« tambatra »? also used for « union ») |
| produit | vokatra | **doubtful** (means « result / product » in general) |
| carré | kare | à relire |
| différence | elanelana | **doubtful** (« distance, gap »; « sisa » for a subtraction?) |
| inégalité | tsy fitoviana | à relire |
| continu / continuité | mitohy / fitohizana | **doubtful** as a mathematical term |
| croissante, majorée, converge, limite | French words kept | no term chosen |
| réel, rationnel, fonction, injective, composée, groupe, commutatif, cyclique, ordre, noyau, compact, image, application linéaire, récurrence, fraction, inverse, ensemble | French words kept | no term chosen: to decide |
| aritmetika, aljebra, aljebra lineera, analizy, topolojia | spelling adapted | **doubtful** spellings |
| raisonnement | fanjohian-kevitra | à relire |
| raisonnement par l'absurde | described (« tadiavo ny mifanohitra ») | **doubtful** |
| si et seulement si | raha …, ary raha izany ihany | **doubtful** |
| axiome, tactique, LaTeX, Lean | kept | à relire |
| formule | formule | to decide (« raikipohy »?) |
| Apprendre / Recherche | Mianatra / Fikarohana | à relire |
| accueil, réglages, projet, dossier, carnet | fandraisana, fikirana, tetikasa, dosie, kahie | **doubtful**: « dosie » (loan) |
| bibliothèque, glossaire | tranomboky, rakiteny | **doubtful**: « rakiteny » (« rakibolana » is a dictionary) |
| appareil, outils | fitaovana (both) | **doubtful**: same word |
| ordinateur hôte | solosaina mpampiantrano | **doubtful** |
| modèle (IA), clé, fournisseur | modely, lakile, mpamatsy | à relire |
| en ligne / local | an-tserasera / eto an-toerana | à relire |
| espace Lean | toerana Lean | **doubtful** |
| tuteur | mpanabe | **doubtful** (« educator »; « mpanampy »?) |
| feuille d'exercices, banque d'exercices | taratasy fanazaran-tena, fitehirizana fanazaran-tena | **doubtful** |
| lycée, licence, master, olympiade | lisea, lisansa, master, olimpiada | à relire (« lisansa » is also used here for a copyright licence) |

## Not translated yet (shown in French)

Article, Blueprint, Sources, Notes, Graph, Publish, Conjectures, News, wizard, keys / providers, updates, devices,
the glossary's entries, the manual (its generator handles `fr` / `en` only), most of Calcul, most server messages.
