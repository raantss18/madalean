# Madalean 2.0 — liste des tâches

État : ⬜ à faire · 🔄 en cours · ✅ fait et vérifié · ⚠️ fait, non vérifié en réel

## 🚀 Ordre de travail à partir du 22/11/2026 (demandes du 22/11)

⚠️ = installé le 22/11, à essayer par toi.

Règle commune : **plus rapide sans perdre la fiabilité**. Une preuve n'est « vérifiée » que par un Lean neuf et
strict ; les accélérations servent aux essais intermédiaires, jamais au verdict final. Chaque gain est mesuré
(avant/après, consigné dans docs/PERFORMANCE.md).

### A — Calcul fiable et rapide (en cours)
1. ✅ Intégrales Sage en panne dans l'espace protégé (Maxima écrivait dans un dossier personnel absent) — corrigé et installé
2. ⚠️ Correction de fond de l'espace protégé (S-AC) : vrai dossier personnel privé et court pour chaque projet, tous
   les caches dedans (Sage, Maxima, GAP, PARI, matplotlib…), suite d'essais de tous les sous-systèmes de Sage dans le
   vrai noyau, même contrôle pour Lean et LaTeX ; essai rapide dans « État de santé » après chaque mise à jour, pour
   attraper une régression avant toi
3. ⚠️ Transcription en code beaucoup plus rapide (S-AB) : rôle « code » vers les modèles mesurés les plus rapides,
   réflexion coupée pour cette tâche, code affiché au fil de l'écriture, jamais d'attente derrière une preuve.
   Objectif : premier code visible en 2 à 5 s
4. ⚠️ « Réécrire » toujours possible (S-AB) : plus de « le dossier travaille », la nouvelle demande remplace l'ancienne
5. ⚠️ Catalogue de syntaxe permanent selon les versions installées (S-AB) : fiche Sage et fiche Lean/Mathlib testées
   sur les vraies versions, gardées en consigne permanente du modèle, signatures exactes des fonctions Sage lues dans
   la version installée, contrôle du code avant affichage (une correction automatique si erreur), fiches refaites à
   chaque mise à jour de Sage, Lean ou Mathlib
6. ⚠️ Cellules plus simples (S-AB) : « Réécrire » sous le texte de la demande, « Approuver et exécuter » sous le code
   produit, un seul « + » en bas et une nouvelle cellule ajoutée après l'exécution ; la cellule reconnaît seule
   code ou demande (choix corrigeable d'un clic) ; Texte et Figure dans une petite liste
6 bis. ⚠️ Correction automatique du code qui échoue (quelques essais, versions gardées, retour arrière possible) et
   **recettes apprises** : chaque demande dont le code a marché est retenue (code, version de Sage/Lean) et resservie
   comme raccourci pour une demande semblable ; recettes revérifiées à chaque mise à jour, visibles et supprimables (S-AB)
6 ter. ⚠️ Résultat mathématique coupé à droite sur téléphone : retour à la ligne ou défilement dans la case (S-AB)
7. ⚠️ « Expliquer l'erreur » et « Expliquer ligne par ligne » à la demande sur les cellules Sage (S-AB)
7 bis. ⚠️ Éditeur d'article plus aéré (S-AD) : panneaux latéraux repliables (mode « pleine largeur »,
   choix retenu), calculs Sage et autres éléments du projet dans la liste avec chacun son logo et son nom bien
   distincts, arborescence des fichiers de l'article affichable au choix
8. ⬜ Même chose pour Lean : « Expliquer l'erreur » (avec correction proposée) et « Expliquer ligne par ligne » sur un
   énoncé ou une preuve Lean, dans les dossiers et les notes (réutilise le service d'explication de l'étape 7)

### B — Accélération de toute l'application (après A)
9. ✅ **Mesurer d'abord** (22/11 : docs/PERFORMANCE.md « Proof time baseline », scripts/perf_report.py) : chronométrage de bout en bout d'une preuve réelle (compréhension, vérification de
   l'énoncé, recherche Mathlib, traduction, chaque essai, chaque vérification Lean, explication) et de chaque écran ;
   tableau des temps dans docs/PERFORMANCE.md, refait à chaque version
10. ✅ **Lean toujours chaud** (22/11, S-AE, DECISIONS D37, docs/BRAIN.md §17, docs/PERFORMANCE.md « Lean chaud ») :
    un `lean --server` par espace utilisé garde Mathlib chargé ; un essai refusé est vérifié en 0,01–0,2 s au lieu de
    2–3 s (10–34 s à froid). Toute preuve acceptée est revérifiée par un Lean neuf et strict ; un verdict sur 20 est
    contrôlé ; au moindre désaccord, le Lean chaud est mis de côté. Réglage « Garder Lean prêt d'avance », ligne
    « Lean prêt d'avance » dans l'état du système
11. ⏸ **Arrêt précoce des essais** : conçu, pas construit (docs/BRAIN.md §17 : une coupure n'est presque jamais
    sûre — le modèle corrige souvent son bloc avant la fin — et une coupure fausse perdrait une preuve)
12. 🔄 **Course des modèles plus intelligente** (S-AF, D38 : les étapes courtes — compréhension, lecture guidée,
    vérification, explication, preuve rédigée — prennent le modèle en ligne le plus rapide mesuré, réflexion
    minimale, jamais le modèle local de la carte graphique tant qu'un modèle en ligne répond ; reste : les preuves) : choix selon le temps mesuré ici et le taux de réussite par domaine,
    la première preuve vérifiée arrête les autres ; réflexion réglée selon la difficulté ; mise en cache des
    consignes chez les fournisseurs qui le permettent
13. ✅ **Travail en parallèle** (S-AF, D38) : lecture guidée, vérification de l'énoncé, recherche Mathlib et premiers
    essais lancés ensemble au lieu de l'un après l'autre (on annule ce qui devient inutile) ; explication et preuve
    rédigée ensemble ; « faux » / « douteux » arrête la preuve comme avant — à essayer sur tes dossiers
14. 🔄 **Ne jamais refaire deux fois** (S-AF, D38 : vérification de l'énoncé et recherche Mathlib gardées par énoncé
    et version de Mathlib, preuve Mathlib revérifiée par Lean ; lemmes de la bibliothèque déjà proposés d'abord ;
    reste : réponses identiques des modèles) : résultats déjà prouvés et réponses identiques gardés (par version de
    Mathlib), lemmes de la bibliothèque proposés d'abord
15. ⬜ **Noyau Sage prêt d'avance** : noyau démarré à l'ouverture d'un carnet, Maxima préparé une fois par version
    (le premier calcul d'intégrale prend aujourd'hui ≈ 10 s)
16 bis. ⬜ **Dossiers relancés des centaines de fois** : historique compacté (versions vérifiées et tes messages gardés, essais ratés résumés) et écriture plus légère — vu à l'essai prolongé (≈ 1,7 Mo par dossier après 550 relances)
16. ⬜ **Interface** : temps d'ouverture des écrans sur téléphone, mises à jour regroupées, rien de lourd chargé
    tant qu'on ne l'ouvre pas

### C — Avant la publication 2.0.0 (sur ton accord)
17. ✅ Essai continu de 2 h (0 erreur) + 1 h sur les mêmes dossiers ; ✅ suite de tests ; ✅ manuel (23 points) ; ✅ README et notes de version
18. ⬜ Tes essais : APK 2.0.1 (scan dans l'app), Calcul, une vraie preuve (coût Hugging Face), GitHub « Tester la connexion »
19. ⬜ Publication : fusion v2 → main, tag v2.0.0, release signée, site GitHub Pages — **seulement sur ton accord**

### D — Plus tard
- Lever la pause d'un fournisseur quand on enregistre une nouvelle clé (aujourd'hui seulement pour Hugging Face)
- Partage de la carte graphique avec Ollama ; fitantanana (doublons, sur ton accord)

## ⭐ Priorités avant la release 2.0.0 (mis à jour le 21/11/2026)

### P0 — bloquant
1. ✅ Revue de sécurité : publiable sous conditions — ✅ clés chiffrées (copies : dépôt `release-keys/` ignoré par git, `~/Documents/madalean-cles`, NAS `Cles-Signature-Releases/madalean`) ; ✅ llama.cpp b12608 (failles corrigées, testé sur la carte graphique) — à installer sur ton PC
2. ✅ Vérification de l'énoncé avant la preuve (S-K) : « fidèle / douteux / faux », preuve Lean du contraire (K = ∅ trouvé tout seul ; contre-exemple (-1)ⁿ des sous-suites), « Corriger l'énoncé avec : … » / « Prouver quand même » — essai réel : sous-suites signalé douteux → correction en un clic → prouvé
3. ✅ Recherche Mathlib d'abord (S-K) + énoncé Mathlib donné au traducteur — essai réel : Cayley-Hamilton (LinearMap.aeval_self_charpoly) et E/ker f ≅ Im f (LinearMap.quotKerEquivRange) prouvés par Mathlib ; ⚠️ Banach : énoncé traduit sans `CompleteSpace 𝕜`, pas prouvé
4. ✅ « L'IA tourne en rond » pendant la traduction (S-K) : vrai bouclage du modèle (lignes `import` sans fin) après un énoncé complet — l'énoncé est maintenant gardé, jetons comptés, garde remise à zéro au changement de modèle
5. ✅ Découpage en lemmes en carte mentale : analyse → lemmes indépendants → tu valides le plan → preuves automatiques → combinaison ; autre piste ou nouveau découpage si échec ; limites (profondeur 3, 6 lemmes, 30 nœuds), arrêt sur les évidences, « sorry » en dernier recours (résultat conditionnel, jamais « vérifié ») — fait (S-L) : vrai essai « fonction continue sur un compact » prouvé de bout en bout (2 lemmes évidents, 1 par Mathlib, combinaison vérifiée par Lean) ; ⚠️ polynôme de degré 3 : plans refusés par Lean avec les modèles gratuits du moment
6. ⚠️ Modèles à clé réellement utilisés : Gemini (clé OK, mais modèles mal classés), Mistral ; Claude en renfort après échec des gratuits, avec plafond par preuve (1 $) et par mois (20 $) réglables — fait par S-M (classement par famille, test sur Flash-Lite, renfort + registre des dépenses), à vérifier avec tes clés
7. ⬜ (4 sur 5 prouvés en test : compact, sous-suites corrigées, Cayley-Hamilton, E/ker f ; Riesz non) Relancer tes dossiers échoués avec ces corrections : Cayley-Hamilton, Banach, compact, sous-suites, E/ker f ≅ Im f
8. ✅ Énoncé refusé compté valide ; carte graphique non détectée ; un seul essai en ligne → tournoi (corrigés, installés)

### P0 bis — demandes du 21/11 au soir
- ⚠️ « Publier » ne marche pas avec ta clé GitHub (S-Q) : cause trouvée — le test de la clé dans Réglages → Clés traitait GitHub comme un fournisseur de modèles (« aucun modèle trouvé : la clé est-elle valide ? ») ; l'envoi demandait aussi le droit « workflow », signalé à tort comme « historique différent ». Corrigé : test d'identité GitHub, bouton « Tester la connexion GitHub », message précis pour chaque droit manquant (classique ou à accès précis, SSO, 2FA, jeton expiré), aperçu construit automatiquement. Testé contre un faux GitHub ; à vérifier avec ta vraie clé après mise à jour (bouton « Tester »)
- 🔄 Calcul = vrai carnet Sage façon JupyterLab : cellules qui se suivent (un seul noyau partagé avec JupyterLab, fichier .ipynb), demandes en langage naturel → code Sage, graphes, courbes et géométrie dynamique inspirés de Fikajiana, export vers Publier (S-P)
- ⚠️ Consigne de recherche sur un article (S-Q) : panneau « Consigne » du projet (plan affiché avant de lancer, limites, arrêt/reprise, journal), « Suggestions » dans Article (avant/après, preuves Lean, calculs Sage, citations, accepter/refuser une par une), recherche unique dans le projet (→ Article, → Publier). Essai réel sur arXiv 1504.02718 avec modèles gratuits
- ✅ Mémoire (S-Q, docs/PERFORMANCE.md) : au repos 63 Mo sans processus inutile (avant : nvidia-smi lancé 40 fois/min et un événement toutes les 3 s même sans écran ouvert) ; noyaux Sage gardés chauds 2 h, 3 au plus ; caches bornés (réseau, vecteurs, file d'événements) ; un seul moteur d'embeddings ; actualisation du catalogue sans doublon
- 🔄 Défauts vus sur tes vrais dossiers : Riesz manqué par la recherche Mathlib, modèle Gemini « Live » choisi, doublon dans une course, Gemini qui se bloque, PDF (S-O)
- 🔄 Écriture d'articles : éditeur visuel (formules, théorèmes, figures, citations) avec source LaTeX à un clic, aperçu PDF, assistant en suggestions, paquets gérés par le moteur interne sans doublon, Overleaf en option, interface épurée + options avancées et personnalisation (S-R)
- ✅ Tes 5 théorèmes prouvés sur ton installation (Cayley-Hamilton, Riesz, compact, sous-suites, E/ker f)
- 🔄 Appairage de la tablette : port 443 au lieu de 10500, QR code en lien https avec bouton « Ouvrir dans l'application », nouvel APK à réinstaller (S-C)
- 🔄 APK 2.0.1 (S-Y) : scan du QR code dans l'application, adresses de secours dans le QR (IP Tailscale, réseau local 11502), messages clairs (« Tailscale n'est pas connecté… » + bouton), langue suivie (français) — à installer et essayer sur le Poco F8 Pro
- 🔄 Écran « Fournisseurs » : spécialistes Lean (Aristotle de Harmonic, Goedel 32B…), code Sage, rédaction LaTeX, recherche Internet (Tavily, Exa…), modèles gratuits (Gemini, Mistral, Groq, Cerebras, GitHub Models, NVIDIA, OpenRouter…), clés à créer par toi, le moins cher d'abord (S-U)
- 🔄 Goedel-Prover-V2-32B en ligne (Hugging Face, ta clé à ajouter) en tête du tournoi ; modèles locaux seulement hors connexion (S-T)
- ⚠️ Classement automatique des meilleurs modèles (S-V) : Réglages → Modèles, par domaine (preuves Lean, formalisation, LaTeX, Sage/code, raisonnement), résultats mesurés ici + classement public LMArena (source et date affichées) + estimation ; badge « Nouveau » et journal des nouveautés ; catalogue toutes les 12 h, LMArena chaque semaine. « Composants suivis » dans Mises à jour (Lean, Mathlib, Sage, LaTeX : installé, plus récent, prochaine vérification) ; les versions de Sage/LaTeX validées s'installent seules comme Mathlib. Testé contre de faux serveurs ; à voir sur ton installation

### P1 — à faire avant la publication
- 🔄 Outil à part « fitantanana » (`~/GitHub/fitantanana`) : inventaire des services, ports, carte graphique, modèles, Lean, environnements Python, Jupyter, TeX ; doublons proposés (liens physiques de préférence, rien sans ton accord) ; prêt automatique de la carte graphique entre Ollama et Madalean (Madalean rend la carte après 10 min d'inactivité)
9. ✅ Glossaire par catégories et niveaux (ordre A–Z ou « Par catégorie », du plus simple au plus avancé ; filtres catégorie et niveau) ; bibliothèque des résultats rangée et filtrée par domaine, projet, étiquette, statut (S-W, une seule liste de domaines côté serveur, tests unitaires)
10. ⚠️ Écran « Calcul » = vrai carnet Sage (S-P, docs/CALCUL.md) : cellules qui s'enchaînent dans un seul noyau partagé avec JupyterLab (même fichier .ipynb), « Demander » en langage naturel, courbes et géométrie dynamique (outils de Fikajiana), exact/approché, reliés aux conjectures, notes, dossiers Lean, article et Publier — testé avec de vrais noyaux Sage et Python ; section « Calculs » du site publié faite (S-W) : cellules, demandes, résultats, formules rendues par KaTeX, images, figures en SVG fixe, carnets téléchargeables, case « Joindre les calculs » dans Publier ; message clair quand le noyau ne démarre pas ou que SageMath manque (bouton Redémarrer / Installer SageMath) ; reste : essai par toi
11. ✅ Défauts du PDF (S-O puis S-W, vérifié sur tes vrais dossiers) : version de Mathlib affichée ; énoncé une seule fois (l'annexe ne le répète plus, l'article non plus dans ses preuves) ; annexe : titres sans numéro, seules les étapes sont numérotées ; « Lecture guidée » coupée après une phrase (Gemini) : plus enregistrée — à refaire sur Riesz, compact, E/ker f (relancer la lecture guidée)
12. ✅ Interfaces téléphone et tablette pour l'APK et l'AppImage (S-X, docs/UI.md §12) : vérifiées écran par écran à 360, 412, 768, 1024 et 1366 px, clair et sombre — plus aucun défilement de côté ni chevauchement, boutons d'au moins 44 px au doigt, menus et fenêtres en volets du bas sur téléphone, « ⋯ » pour les boutons secondaires du Calcul, Notes et Conjectures en liste puis détail, barre du bas masquée quand le clavier est ouvert et texte saisi gardé visible ; reste : essai sur ton téléphone et ta tablette
13. ⬜ Suite de tests complète verte ; 44 points du manuel ; README et notes de version 2.0.0 ; essai prolongé de 2 h
14. ✅ Clé Gemini présente et acceptée par Google (le modèle de test était surchargé : 503)

### P2 — publication (sur ton accord)
13. ⬜ Fusion `v2` → `main`, tag `v2.0.0`, release signée (AppImage, APK, canal de mises à jour), site GitHub Pages
14. ⬜ Tests de l'AppImage et de l'APK après la release (toi), puis retrait de l'ancienne application 1.1.4

### Après la 2.0.0
- Ollama occupe 4,8 Go de la carte graphique : partage à prévoir avec les modèles locaux
- Lignes par domaine et badge de tour dans l'écran du tournoi
- ⚠️ Claude (clé payante) en renfort final du tournoi, plafonds 1 $/preuve et 20 $/mois (S-M) — à vérifier avec ta clé

## 0. Préparation
- ✅ Dépôt renommé `madalean`, dossier `~/madalean`, branche `v2`
- ✅ Architecture et contrat des sessions (`docs/ARCHITECTURE.md`), interface du moteur (`madalean/brain/api.py`)

## 1. Serveur (session S-A, Opus) — terminé, 180 tests sans carte graphique
- ✅ Serveur asyncio, API + WebSocket (synchronisation de tous les appareils), référence dans `docs/API.md`
- ✅ Sécurité : appairage par code, appareils révocables, clés d'API au trousseau (tests de contournement)
- ✅ Projets, dossiers, sous-dossiers en parallèle, historique par dossier
- ✅ Chaîne comprendre → traduire (+ lecture guidée de l'énoncé Lean) → prouver → expliquer, avec le vrai Lean
- ✅ Export PDF par XeLaTeX (symboles Lean vérifiés), repli HTML
- ✅ JupyterLab derrière la même connexion (noyau réel testé à travers le proxy)
- ⚠️ Pas encore essayé : vrais modèles locaux sous le nouveau serveur, `tailscale serve`, installation réelle d'une mise à jour, migration de tes vrais dossiers
- ⚠️ Pas de noyau Jupyter Lean 4 : aucun n'est fiable aujourd'hui (documenté)

## 2. Moteur de modèles (session S-B, Opus) — terminé, 35 tests
- ✅ Routeur de L Katta (meilleur modèle gratuit, pauses, quotas), repli hors ligne automatique
- ✅ Fournisseurs gratuits sans clé : preuve réelle trouvée et vérifiée par Lean 4.9 (2 essais sur 2)
- ⚠️ Claude (API native, outils), Gemini, OpenRouter : testés contre de faux serveurs seulement (clés à fournir)
- ✅ Modèles locaux Goedel/Qwen sous le nouveau serveur, en réel (2026-11-21) : 3 preuves de bout en bout, dont une relance « et la réciproque » et deux dossiers en parallèle, 0 erreur
- ⚠️ Ollama pas essayé
- ✅ Mode agentique : prouveur qui compile avec Lean et cherche dans Mathlib
- ✅ Index Mathlib (179 000 déclarations Lean 4.9, 290 000 Lean récent) ; bon lemme dans les 8 premiers : 13/20 et 12/20 sur le jeu final

## 3. Applications (session S-C, Opus) — ✅ terminé
- ✅ AppImage (Tauri) : appairage, reconnexion, révocation — 12/12 contre le vrai serveur en démonstration
- ✅ APK Android signés (Flutter) : appairage, fichiers, sur émulateurs
- ✅ Mises à jour signées automatiques (AppImage 13/13 scénarios ; APK sur émulateur, Android impose un appui)
- ✅ Icône Madalean (baobab formant ∀) ; ouverture de session sans jeton dans les adresses
- ⚠️ Jamais essayé : vrai Tailscale en HTTPS, vrai téléphone ou tablette, trousseau du bureau, Android 8–9
- ⚠️ À faire par toi : sauvegarder `~/.config/madalean/release-keys/` (clés de signature)

## 4. Interface web (session S-D, Opus) — ✅ terminé en démonstration
- ✅ Énoncé → Traduction Lean (lecture guidée) → Preuve, projets et dossiers parallèles, réglages façon L Katta
- ✅ Modes Apprendre / Recherche, aide intégrée (manuel), recherche globale Ctrl+K
- ✅ Écrans de recherche : sources + lecteur + questions sourcées, notes + graphe, blueprint, article, conjectures, plans de preuve, publier, mises à jour
- ✅ AA sans violation (42 vues), 60 images/s, 1,26 s sur téléphone (cache chaud)
- 🔄 8 petites demandes au serveur (refus Lean de sécurité comme donnée, recherche unifiée, réflexions d'apprentissage…)
- ⚠️ Jamais essayé avec les vrais modèles, sur un vrai téléphone, avec un lecteur d'écran, hors Chromium

## 5. Sources, bibliographie, articles (session S-E, Opus) — ✅ serveur fait
- ✅ Bibliothèque (DOI, arXiv, ISBN, zbMATH, BibTeX/RIS/CSL/Zotero), recherche d'ouvrages, questions sourcées vérifiées
- ✅ Bibliographie dans preuves et exports, références inventées retirées
- ✅ Article → blueprint (12/12 énoncés sur 3 vrais articles ; dépendances : point faible), Lean → article PDF
- 🔄 « Publier » : génération du site, liste de ce qui sort, aperçu, envoi vers GitHub
- ⚠️ Qualité avec un vrai modèle non mesurée (clé nécessaire)

## 5 bis. Atelier de recherche (session S-G, Opus) — ✅ serveur fait
- ✅ Notes liées avec fusion multi-appareils, conjectures testées par Sage (bac à sable) et Lean, plans de preuve, « conditionnel » jamais vérifié
- ✅ Apprentissage (indices sans fuite, exercices vérifiés par Lean), progression synchronisée
- ⚠️ Générations avec un vrai modèle non essayées

## 5 ter. Mises à jour internes et automatiques — ✅ fait
- ✅ Madalean signé (Ed25519), retour arrière ; Lean/bibliothèques avec revérification des preuves ; Sage/TeX par terminal
- ✅ Un seul format de canal signé pour serveur, AppImage et APK
- ⚠️ Jamais déclenché en réel (aucune version publiée)

## 5 quater. Installation autonome (session S-I, Opus) — ✅ fait
- ✅ Un seul dossier (1,9 Go, 6,6 Go avec Sage), installation réelle de bout en bout, hors ligne, désinstallation sans trace
- ✅ Sage à la demande, LaTeX interne, Tailscale intégré (journaux Tailscale désactivés), un seul service
- ✅ 0 faille connue (Python, Go) ; SBOM ; exception : pillow dans Sage (documentée)
- ⚠️ Vraie connexion Tailscale et moteur CUDA avec un vrai modèle non essayés

## 6. Site GitHub Pages (session S-F, Opus) — ✅ prêt, pas en ligne
- ✅ Manuel FR/EN (23 pages), page d'installation avec QR codes, canal de mises à jour, modèle de publication
- ⬜ Mise en ligne après ton accord ; 44 points du manuel à vérifier à l'intégration
- ⬜ README, CHANGELOG 2.0.0, DECISIONS, ACCEPTANCE à finaliser

## 6 bis. Sécurité et robustesse (session S-H, Opus, indépendante des auteurs) — avant publication
- ⬜ Revue de sécurité de la synchronisation (appareil compromis, page web malveillante, fichiers hostiles, injection par les sources)
- ⬜ Audit des dépendances et des CVE (Python, npm, Rust, Flutter), versions épinglées, liste des composants publiée
- ⬜ Tests de robustesse : coupures, redémarrages, 2 h de travaux en parallèle, 5 appareils connectés
- ⬜ Fluidité mesurée sur téléphone ; facilité d'usage au niveau de L Katta (ajout de clé testé automatiquement, aucun terminal)

## 7. Intégration et publication (intégrateur)
- ⬜ Assemblage, tests complets sans carte graphique
- ⬜ Tests réels : modèles locaux (carte graphique), fournisseurs gratuits, Claude et Gemini avec tes clés
- ⬜ Appairage réel par Tailscale (téléphone, tablette, autre PC)
- ⬜ Migration de tes dossiers, retrait de l'ancienne application PySide6
- ⬜ Version 2.0.0 : tag, release (AppImage, APK), site en ligne
