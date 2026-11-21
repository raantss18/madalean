# Madalean 2.0 — liste des tâches

État : ⬜ à faire · 🔄 en cours · ✅ fait et vérifié · ⚠️ fait, non vérifié en réel

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
- 🔄 « Publier » ne marche pas avec ta clé GitHub : cause, message clair, bouton « Tester la connexion GitHub » (session S-Q)
- 🔄 Calcul = vrai carnet Sage façon JupyterLab : cellules qui se suivent (un seul noyau partagé avec JupyterLab, fichier .ipynb), demandes en langage naturel → code Sage, graphes, courbes et géométrie dynamique inspirés de Fikajiana, export vers Publier (S-P)
- 🔄 Consigne de recherche sur un article : vérifications Lean, exemples et figures Sage, améliorations et généralisations proposées une par une, tu valides chaque changement (S-Q)
- 🔄 Mémoire : noyaux gardés chauds (~1,5–2 Go au repos), aucun doublon de processus, d'index ou de tâche (S-Q)
- 🔄 Défauts vus sur tes vrais dossiers : Riesz manqué par la recherche Mathlib, modèle Gemini « Live » choisi, doublon dans une course, Gemini qui se bloque, PDF (S-O)
- ⬜ Relancer Cayley-Hamilton et Riesz après mise à jour

### P1 — à faire avant la publication
- 🔄 Outil à part « fitantanana » (`~/GitHub/fitantanana`) : inventaire des services, ports, carte graphique, modèles, Lean, environnements Python, Jupyter, TeX ; doublons proposés (liens physiques de préférence, rien sans ton accord) ; prêt automatique de la carte graphique entre Ollama et Madalean (Madalean rend la carte après 10 min d'inactivité)
9. 🔄 Glossaire par catégories et niveaux ; bibliothèque des résultats par domaine, projet, étiquette
10. 🔄 Écran « Calcul » Sage intégré : calculs et conjectures, reliés aux notes, dossiers Lean et articles (objectif : publier)
11. ⬜ Défauts du PDF : version de Mathlib « — », « Théorème. » répété, numérotation de l'annexe
12. ⬜ Interfaces téléphone et tablette pour l'APK et l'AppImage (épuré, complet, sans chevauchement)
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
