# Madalean 2.0 — liste des tâches

État : ⬜ à faire · 🔄 en cours · ✅ fait et vérifié · ⚠️ fait, non vérifié en réel

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
