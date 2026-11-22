# Changelog

## 2.0.1 — à venir

Travail en cours (branches non encore publiées) :

**Installation guidée**
- Installateur graphique `Madalean-installer.run` : il vérifie sa propre intégrité, examine la machine (carte
  graphique, mémoire, disque, SageMath, TeX Live, Python, Lean, Ollama, Tailscale déjà présents), propose un plan
  adapté (réutiliser un outil déjà installé ou installer la copie de Madalean, modèle local conseillé ou non) et
  montre l'installation en direct dans le navigateur, avec « Réessayer » en cas d'erreur.
- Le même assistant dans le terminal (`./install.sh`) ; `./install.sh --yes` garde les choix par défaut, sans
  question ; `--dry-run` montre le plan sans rien installer ; nouvelles options `--models`, `--sage`, `--tex`, `--plan`.
- SageMath et TeX Live déjà installés sur l'ordinateur peuvent être réutilisés (même bac à sable).
- Les choix d'installation sont gardés et appliqués au premier démarrage ; l'application peut les lire.

**Site**
- Nouvel accueil (démonstration animée, fonctions, fonctionnement, installation en 3 étapes, questions
  fréquentes), page « À propos » avec les coordonnées de l'auteur, guide complet d'installation et de première
  configuration ; téléchargements classés serveur / clients, toujours vers la dernière version.

**Applications**
- « À propos » avec les coordonnées de l'auteur dans l'application Android et l'application de bureau ; licence
  indiquée dans l'application web.

**Interface** — nouvelle présentation de l'application web : en cours (session S-AK).

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
