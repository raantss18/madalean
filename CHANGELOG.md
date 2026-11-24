# Changelog

## 2.2.0 — 2026-11-24

**Littérature d'abord**
- Pour chaque énoncé, Madalean cherche en parallèle des résultats liés dans zbMATH Open, OpenAlex et arXiv (DOI
  confirmés par Crossref), dans tes Sources et dans Mathlib, sans jamais bloquer la preuve.
- Une référence n'est montrée que si elle existe vraiment ; chaque théorème cité est recopié mot pour mot depuis le
  texte récupéré, avec sa place ; « relu par des pairs » ou « prépublication » est indiqué.
- Un résultat cité est formalisé en Lean et peut servir de lemme ; tant qu'il n'est pas prouvé en Lean, la preuve qui
  l'utilise est « conditionnelle » — jamais « vérifiée ». Panneau « Littérature » dans le dossier.

**Pièces jointes lues une seule fois** — image, PDF, LaTeX, BibTeX ou adresse web, sur un nouvel énoncé, dans le fil
d'un dossier ou dans une cellule Calcul ; lues une fois pour tout le projet, transformées en mémoire (référence,
énoncés cités, énoncés Lean), puis seule cette mémoire sert. La cible à prouver est énoncée à part des résultats
fournis.

**Graphe de lemmes raisonné**
- Chaque dossier a son graphe : cible, lemmes, résultats de Mathlib, certificats, résultats cités, chacun avec son
  statut ; un sous-lemme partagé n'est prouvé qu'une fois ; un même lemme est reconnu à un renommage des variables
  près (confirmé par Lean).
- « Recherche raisonnée » : une estimation écrite avant chaque piste, un contre-exemple cherché sur de petites valeurs
  (confirmé par Lean), des budgets stricts contre les boucles, un résumé à l'arrêt ; une piste abandonnée garde sa
  raison.
- « Expliquer la démonstration » : chemin choisi et pourquoi, lemmes, tactiques, échecs, bibliographie — construit
  seulement à partir de ce qui a été enregistré. Vue en liste ou en dessin.

**Sous-dossiers** — un lemme s'ouvre comme un dossier complet (preuve, sous-graphe, calculs), rangé sous son parent,
avec le fil d'Ariane « Projet › Dossier › Lemme » ; son statut remonte au parent.

**Ce que Madalean a appris** — des leçons tirées de preuves vérifiées par Lean (noms Mathlib renommés, corrections
d'erreurs, pistes sans issue, stratégies qui marchent), données à n'importe quel modèle ; visibles et supprimables
dans Réglages.

**De l'article au plan formel** — onglet « Plan formel » du Blueprint : les résultats d'un article (LaTeX d'arXiv ou
PDF) avec leur texte exact et leurs dépendances réelles, formalisés par étapes, Mathlib d'abord ; un dossier principal
et des sous-dossiers ; export LaTeX (style leanblueprint) et HTML.

**MCP** — Madalean peut servir d'outils à Claude Code ou Claude Desktop sur ton ordinateur (chercher dans Mathlib,
vérifier avec Lean, certifier, expliquer, chercher dans la littérature), et ses modèles peuvent utiliser des outils
externes que tu autorises un à un. Éteint par défaut.

## 2.1.0 — 2026-11-23

**Certificats : Sage calcule, Lean vérifie**
- Pour les énoncés qui s'y prêtent, Madalean ne demande rien à un modèle : Sage cherche un témoin (facteur,
  certificat de primalité de Pratt, inverse, cofacteurs d'une base de Gröbner, somme de carrés, combinaison de Farkas,
  contre-exemple, encadrement numérique) et Lean se contente de le vérifier. Un témoin faux est refusé par Lean.
- 12 familles : primalité, nombres composés, arithmétique, puissances modulaires, identités, idéaux, arithmétique
  linéaire, sommes de carrés, existence, contre-exemples, bornes numériques, cas finis — 60 énoncés sur 60 du banc
  d'essai sur les deux versions de Lean, en 2 à 7 s.
- Nouvelle stratégie de preuve « certificat » (sans coût), outil « témoin Sage » pour les modèles, et « Certifier
  avec Lean » dans le menu d'une cellule Calcul.

**Actualités** — veille mathématique permanente : nouveautés arXiv, IA pour les maths, problèmes ouverts (Erdős,
MathOverflow, Polymath), Lean et Mathlib, annonces (AMS, Quanta, Images des maths, blog de Tao), tes propres flux ;
tri par branche (15) et par pertinence pour tes projets, recherche, lecture hors ligne, « Ajouter aux Sources »,
« Créer une conjecture », « Créer un dossier ». Les textes du web sont traités comme des données, jamais comme des
consignes.

**Moteur de conjectures** — Conjectures › « Explorer » : expérience Sage, reconnaissance (polynômes, récurrences,
séries génératrices, multiplicativité, congruences, OEIS), énoncé précis en Lean avec une étiquette honnête
(« vérifié jusqu'à n = … »), chasse au contre-exemple confirmée par Lean, puis « Tenter la preuve » ; tout est noté
dans un journal.

**Mesures** — `madalean bench` : miniF2F, PutnamBench et un jeu de contrôle avec la vraie chaîne de Madalean ; seule
compte une preuve qu'un Lean neuf et strict accepte ; temps et coût par preuve vérifiée ; page « Mesures » du site.

**Corrigé** — le noyau Sage ne démarrait plus sur les machines à beaucoup de cœurs (16 fils de calcul dépassaient la
limite de mémoire du bac à sable) : 4 fils au plus et une marge pour la mémoire réservée mais inutilisée.

## 2.0.2 — 2026-11-22

**« Madalean Server », l'application de l'ordinateur hôte**
- Sur l'ordinateur qui fait tourner Madalean, le menu des applications propose maintenant **une seule** entrée,
  « Madalean Server » : Madalean dans sa propre fenêtre (plus besoin du navigateur), avec un menu « Serveur » pour
  voir l'état du serveur, le démarrer, l'arrêter, le redémarrer, lire ses journaux ou l'ouvrir dans le navigateur, et
  une icône près de l'horloge (KDE ; GNOME avec l'extension AppIndicator). Si le service n'est pas installé, la
  fenêtre le dit et donne la commande pour le réinstaller.
- Son icône est celle de Madalean avec un petit badge serveur dans le coin ; l'application « Madalean » des autres
  ordinateurs (AppImage), du téléphone (APK) et du navigateur garde l'icône sans badge.
- Installée par `install.sh`, l'installateur graphique et la mise à jour automatique, déjà construite (rien à
  compiler). Sans la bibliothèque système webkit2gtk-4.1, l'entrée ouvre une fenêtre de Chromium (ou Chrome, Brave,
  Edge, Vivaldi), sinon le navigateur ; l'installateur le dit. Elle remplace l'ancienne entrée « Madalean » qui
  ouvrait le navigateur avec une icône générique, et l'icône s'affiche tout de suite dans le menu.

**Carte graphique**
- Partage avec Ollama : quand Madalean a besoin de la carte pour un modèle local et qu'Ollama ne fait rien, il lui
  demande de libérer la place (0,3 s) ; si Ollama est en train de répondre, Madalean attend au plus 30 s puis passe
  au processeur ou à un modèle en ligne (réglable) — il ne coupe jamais Ollama. Ligne « Partage avec Ollama » dans le
  panneau ☁ et l'état de santé ; réglages dans Réglages › Modèles.
- L'état de santé signale quand le moteur des modèles locaux tourne sur le processeur alors qu'une carte NVIDIA est
  utilisable, avec un bouton pour réparer (cas vu après une mise à jour du pilote).

## 2.0.1 — 2026-11-22

**Interface repensée**
- Le logo est le menu (Accueil en premier) ; plus de barre du bas ni de boutons en double. « Projet › Dossier » en
  texte complet, seul endroit pour changer de projet ou de dossier.
- Le bouton ☁ montre le modèle utilisé, le processeur, la mémoire, la carte graphique, les jetons et le coût (cette
  demande, aujourd'hui, ce mois).
- Entrée envoie, Maj+Entrée va à la ligne (dans une cellule de code Calcul, Entrée exécute) ; cliquer à côté ferme
  un menu ou un panneau ; tout s'enregistre automatiquement, et ce qui est tapé sans être envoyé est gardé.
- Écrans plus rapides sur téléphone (accueil 2,4 → 1,6 s sur un téléphone lent simulé).

**Premiers pas** — un assistant à la première ouverture : outils (réutiliser SageMath ou LaTeX déjà installés, ou la
copie de Madalean), modèle local conseillé pour votre machine, clés, Claude et ses plafonds, modes, choix
automatiques ou manuels, appareils. Il reprend où vous l'avez laissé.

**Installation guidée**
- Nouvel installateur graphique `Madalean-installer.run` : rendez-le exécutable (clic droit › Propriétés ›
  « Autoriser l'exécution », ou `chmod +x Madalean-installer.run`), double-cliquez. Il vérifie son intégrité, examine
  votre machine, propose le meilleur plan et montre l'installation en direct dans votre navigateur.
- Le même assistant dans le terminal : `./install.sh` ; sans question : `./install.sh --yes`.

**Preuves et calculs**
- « Expliquer » pour Lean : l'erreur (avec une correction proposée seulement si Lean l'accepte) et la preuve ligne
  par ligne, avec les buts donnés par Lean.
- Le chef d'orchestre corrige aussi les cellules Calcul qui échouent et les compilations d'article (correction
  vérifiée, proposée en suggestion) ; une preuve trouvée avant un verdict « douteux » est gardée pour « Prouver
  quand même ».
- Calcul prêt d'avance : première intégrale en 0,1 s au lieu de 8 s.
- Historique des dossiers relancés très souvent compacté, sans rien perdre de ce qui est affiché.
- Enregistrer une nouvelle clé relance aussitôt le fournisseur mis en pause.

**Site et applications** — nouveau site (accueil, guide complet d'installation et de première configuration, page
« À propos ») ; téléchargements classés serveur / clients, toujours vers la dernière version ; coordonnées de
l'auteur dans les applications.

Fichiers (noms stables) : `Madalean-installer.run`, `madalean-server.tar.gz`, `Madalean-x86_64.AppImage`,
`Madalean-android.apk` (+ par processeur), `SHA256SUMS`, `SHA256SUMS.sig`.

## 2.0.0 — 2026-11-22

**Une nouvelle application.** « Lean AI Station » devient **Madalean** : un serveur sur l'ordinateur hôte, une
interface web, une application Android et une AppImage qui s'y relient par Tailscale. Les données de la 1.x sont
reprises au premier démarrage.

**Preuves**
- Modèles en ligne d'abord : tournoi des meilleurs modèles gratuits, Goedel-Prover-V2-32B (Hugging Face) en tête,
  modèles payants en renfort avec plafonds par preuve et par mois ; modèles locaux hors connexion.
- Vérification de l'énoncé avant la preuve (fidèle / douteux / faux, contre-exemple prouvé par Lean), correction en
  un clic.
- Recherche dans Mathlib d'abord : un résultat qui existe déjà est prouvé directement.
- Plan de preuve en carte mentale : découpage en lemmes validé par vous, preuves automatiques, recombinaison.
- Classement automatique des modèles par domaine (résultats ici, LMArena, nouveautés).
- Plus rapide : les étapes (lecture guidée, vérification de l'énoncé, recherche Mathlib, essais de preuve) partent
  ensemble ; Lean reste prêt d'avance (un essai refusé est jugé en 0,01 s au lieu de 2 à 3 s), le verdict « vérifiée »
  restant donné par un Lean neuf et strict ; rien n'est recalculé pour un énoncé déjà vérifié.
- Chef d'orchestre Claude (avec une clé Claude) : découpe la demande, choisit pour chaque tâche le modèle mesuré le
  plus adapté, corrige les échecs et vérifie la cohérence finale ; plafond de 1 $ par demande, sur votre accord au-delà ;
  sans Claude, le meilleur modèle gratuit dirige.

**Recherche**
- Calcul : vrai carnet SageMath partagé avec JupyterLab, demandes en langage naturel, courbes, géométrie dynamique.
- Code de calcul reproductible : la demande est analysée (F_125, GF(5^3), 𝔽₁₂₅… reconnus comme le même corps), un
  catalogue vérifié donne une écriture unique en Sage, Python et Lean, le meilleur code qui a marché est retenu ;
  explication de l'erreur, du code ligne par ligne et des étapes du calcul.
- Notes avec blocs Lean vérifiables, conjectures, sources (PDF, arXiv, questions sur un article), bibliographie.
- Article : éditeur LaTeX visuel, aperçu PDF, assistant en suggestions, échange avec Overleaf.
- Publier : site statique du projet (preuves revérifiables, calculs, article) sur GitHub Pages.
- Bibliothèque filtrée par domaine, projet, étiquette et état ; glossaire par catégories et niveaux.

**Appareils**
- Application Android : scan du QR code dans l'application, adresses de secours (IP Tailscale, réseau local),
  messages clairs quand Tailscale n'est pas connecté.
- Écrans adaptés au téléphone et à la tablette ; nouvelle identité visuelle « Madal∃an ».

**Installation, mises à jour, sécurité**
- Installation autonome en un dossier, sans `sudo` (Lean, Mathlib, SageMath à la demande, LaTeX, moteur des modèles,
  nœud Tailscale).
- Mises à jour signées de Madalean ; Lean, Mathlib, SageMath et LaTeX suivis et mis à jour avec revérification des
  preuves.
- Revue de sécurité indépendante ; Lean, LaTeX et calculs isolés ; appareils reliés par code ; clés gardées sur l'hôte.

## 1.1.4 — 2026-10-04

**Corrections** (signalées : « il fait toujours la réciproque », « unknown constant qui se répète »)
- **Sens de l'implication** : « un carré pair est issu d'un entier pair » était compris à l'envers (« le carré d'un
  entier pair est pair »). La consigne de l'étape « comprendre » impose maintenant de repérer ce qui est supposé et ce
  qui est à conclure, et l'énoncé compris est **affiché en français** dans le fil (l'anglais reste pour le traducteur).
- **Les demandes de suivi sont lues par l'IA** (Qwen3) au lieu d'un tri par mots-clés : « et la réciproque », « j'ai
  dit : si n² est pair alors n est pair » produisent un **nouvel énoncé** (affiché, retraduit, prouvé, expliqué) au lieu
  de reprouver le même théorème. « Preuve plus courte », « réessaie avec… » relancent la preuve ; « explique… »
  l'explication. Les mots-clés restent en secours (réponse inutilisable ou modèle absent).
- **Noms inventés qui reviennent à chaque essai** : les noms refusés par Lean pendant une recherche sont maintenant
  rappelés dans chaque nouvel essai (« ces noms n'existent pas… », avec les vrais noms proches), au lieu d'être oubliés
  à chaque nouveau départ ; si le modèle réutilise quand même un nom refusé, l'outil abandonne cette piste et repart
  de zéro avec l'avertissement. Le message du Lean récent (`Unknown identifier` avec des accents graves) est aussi reconnu.

## 1.1.3 — 2026-10-04

**Amélioration** (demandée après la 1.1.2)
- **Lemmes inventés** : quand Lean répond qu'un nom n'existe pas (`unknown constant`, `unknown identifier`, ou
  « invalid field notation » pour `Real.…`, `Nat.…` en Lean 4.9), l'outil cherche dans la Mathlib de l'espace de
  travail les déclarations aux noms proches et les donne au prouveur avec leur énoncé, dans le message de correction.
  Exemple réel : `Polynomial.exists_root_of_odd_degree` → `Polynomial.exists_root_of_degree_eq_one`,
  `Polynomial.exists_root_of_splits`… L'index (≈ 164 000 déclarations pour Lean 4.9, ≈ 275 000 pour le Lean actuel)
  se construit en arrière-plan en 5 à 10 s la première fois, puis se recharge en 1 à 2 s.

## 1.1.2 — 2026-10-04

**Corrections** (signalées : « les 8 essais reproduisent la même erreur », sur deux dossiers)
- **Les essais s'enlisaient sur la même piste** : chaque essai corrigeait le précédent, jusqu'à 7 corrections d'affilée
  de la même idée, et la conversation grossissait au point de ne laisser que ≈ 1 500 tokens de réponse (preuve coupée,
  `sorry`, même erreur à chaque essai). Désormais : au plus 2 corrections par piste puis un nouvel essai depuis zéro
  (comme Goedel-Prover-V2), nouveau départ immédiat si Lean renvoie exactement la même erreur, et au moins
  8 192 tokens garantis par réponse.
- **Les demandes après un échec n'atteignaient pas le prouveur** : « réessaie la preuve », « en utilisant les
  propriétés algébriques… » étaient envoyées au traducteur (énoncé retraduit à l'identique) et le prouveur ne voyait
  jamais l'indication. Elles relancent maintenant la recherche de preuve, avec la demande transmise au prouveur comme
  indice ; seules les demandes qui portent sur l'énoncé (« ajoute l'hypothèse… ») le font retraduire.

## 1.1.1 — 2026-10-04

**Corrections** (signalées avec une vidéo : « théorème de la base incomplète »)
- **Mauvaise traduction d'un théorème cité par son nom** : le traducteur ne recevait que le nom et a formalisé un
  autre résultat (« une famille de plus de dim V vecteurs est liée »). Nouvelle étape **« comprendre »** avant la
  traduction : l'IA généraliste reformule la demande en un énoncé mathématique précis et complet (affiché dans le fil :
  « Problème compris ainsi »), et c'est ce texte que le traducteur met en Lean. Si la demande ne désigne aucun résultat
  connu, l'outil s'arrête et demande l'énoncé au lieu d'en inventer un.
- **Le prouveur tournait en rond sans être arrêté** : il recyclait les mêmes paragraphes avec de petites variations
  (le détecteur ne voyait que les répétitions exactes), jusqu'à la limite de 16 384 tokens (≈ 6 min par essai).
  Nouveau détecteur de raisonnement circulaire, réglé sur de vraies réponses du modèle : il laisse au modèle le temps
  de sortir seul d'une hésitation (cas observé qui finit par une preuve correcte) et coupe au-delà (≈ 6 000 tokens),
  puis passe à l'essai suivant.
- Le détecteur de répétitions exactes (depuis la 1.0) pouvait arrêter une **preuve correcte** qui répète plusieurs
  fois le même bloc de tactiques (cas réel accepté par Lean) : il est désormais plus exigeant à l'intérieur du code.

## 1.1.0 — 2026-10-04

**Nouveautés**
- **Dossiers et fil de discussion** : chaque preuve devient un dossier. Après le résultat, on écrit simplement une demande
  (« ajoute l'hypothèse n > 0 », « preuve plus courte », « explique l'étape 2 ») ; l'outil devine l'étape à refaire
  (énoncé, preuve ou explication), modifiable à la main, et garde toutes les versions (« Revenir à cette version »).
  Les dossiers sont listés, renommables, supprimables (annulable) et rouverts plus tard.
- **Enchaînement entièrement automatique** traduire → prouver → expliquer, avec changement automatique du modèle
  (traducteur, prouveur, explicateur). Option « Pause pour relire l'énoncé ».
- **Mémoire** : profil personnel lu par le traducteur et l'explicateur ; historique du dossier pour les corrections ;
  **bibliothèque** des résultats prouvés, réutilisés comme lemmes quand un nouveau problème leur ressemble (onglet dédié).
- **Interface en anglais** (bouton 🌐 ou Système) : interface, aide, exemples et langue des explications.
- **Mises à jour de Lean/Mathlib et des modèles Goedel** : vérification chaque semaine au démarrage (GitHub et
  Hugging Face uniquement, désactivable), notification (bandeau + notification du bureau), installation en un clic.
  La nouvelle version est installée à côté de l'ancienne et vérifiée (théorème test pour Mathlib, chargement et réponse
  pour un modèle), puis l'ancienne est **supprimée automatiquement** ; une version de Lean encore utilisée par un de vos
  projets est conservée. En cas d'échec, rien n'est changé. Aussi en ligne de commande : `scripts/updater.py check`.
- Onglet Chat retiré (le prouveur n'est pas un modèle de discussion).

**Corrections**
- Une vérification Lean relancée juste après « Arrêter » pouvait planter ou reprendre un résultat périmé (numéros de tâche).
- Les signaux d'une génération annulée pouvaient perturber la suivante.


## 1.0.0 — 2026-10-04 (première version)

**Fonctions**
- Décrire un problème en français/anglais (LaTeX accepté) ou importer un `.tex` → traduction en énoncé Lean
  (Goedel-Formalizer-V2-8B) contrôlée par Lean, relecture obligatoire, puis recherche de preuve avec auto-correction
  (Goedel-Prover-V2-8B). Une preuve n'est acceptée que si Lean l'accepte sans `sorry`/`admit`, avec les axiomes
  standard seulement, pour l'énoncé exact relu.
- Explication d'une preuve Lean en français (Qwen3-8B) ; marche aussi sur une preuve collée.
- Export LaTeX (XeLaTeX, compatible Overleaf) avec énoncé, version Lean, explication et preuve ; import `.tex`.
- Vérification d'un fichier `.lean` (glisser-déposer). Assistant de premier démarrage, aide « Lean pour débutants ».
- Garde-fous : détection de boucles de génération, repli automatique en cas de mémoire graphique insuffisante,
  récupération après arrêt brutal, aucun processus orphelin, mode hors-ligne qui bloque le réseau de l'application.
- Deux espaces Lean : Lean 4.9 + Mathlib de Goedel (compilé depuis les sources) et Lean récent.

**Installation**
- `install.sh` multi-distributions (Arch, Fedora, Debian/Ubuntu, openSUSE), moteur CUDA ou processeur seul,
  versions et modèles épinglés avec SHA-256 ; `export_offline.sh` / `uninstall.sh`.

**Limites connues** : voir `ACCEPTANCE.md` (section « Not verified / known limits ») et le README.
