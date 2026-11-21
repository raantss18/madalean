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
- ⚠️ Modèles locaux Goedel/Qwen et Ollama par le nouveau moteur : pas encore essayés en réel (carte graphique réservée)
- ✅ Mode agentique : prouveur qui compile avec Lean et cherche dans Mathlib
- ✅ Index Mathlib (179 000 déclarations Lean 4.9, 290 000 Lean récent) ; bon lemme dans les 8 premiers : 13/20 et 12/20 sur le jeu final

## 3. Applications (session S-C, Opus) — terminé, testé contre un serveur factice
- ✅ AppImage (Tauri, 104 Mo) : appairage, reconnexion, téléchargement PDF, révocation — 14 contrôles sur 14 dans une session graphique isolée
- ✅ APK Android signés (Flutter, 18 Mo en arm64) : appairage, envoi et téléchargement de fichiers sur émulateurs
- ✅ Icône Madalean (baobab formant ∀), script Tailscale (n'ajoute qu'une entrée, refuse de toucher celles de Sampana)
- 🔄 Deux points d'accès à ajouter au serveur pour l'ouverture de session depuis les applications
- ⚠️ Jamais essayé : vrai serveur, vrai Tailscale en HTTPS, vrai téléphone ou tablette, trousseau du bureau
- ⚠️ À faire par toi : sauvegarder `~/.config/madalean/release-keys/` (clé de signature des APK)

## 4. Interface web (session S-D, Opus) — terminé en mode démonstration
- ✅ Écran 1 : écrire l'énoncé (langage naturel / LaTeX avec aperçu, import .tex, exemples)
- ✅ Écran 2 : traduction Lean côte à côte avec le texte, lecture guidée ligne par ligne, survol des symboles
- ✅ Écran 3 : essais en direct, preuve vérifiée, preuve rédigée, explication, découpage en lemmes, versions, export
- ✅ Projets et dossiers en parallèle, centre d'activité, indicateur « qui reçoit quoi »
- ✅ Modes « Apprendre » (indices progressifs, explication à reformuler, exercices) et « Recherche »
- ✅ Réglages façon L Katta (clés, modèles, appareils avec QR code, mises à jour, santé) ; français / anglais ; clair / sombre ; téléphone et tablette
- ✅ Accessibilité AA (0 violation sur 14 écrans), 60 images/s sur 10 000 lignes, 1,3 s sur téléphone (cache chaud)
- 🔄 11 demandes au serveur (versions des corrections manuelles, test réel des clés, survol Mathlib…)
- ⬜ Écrans de l'atelier de recherche (sources, notes, graphe, conjectures, plans de preuve, articles) — session suivante
- ⚠️ Jamais essayé avec les vrais modèles, dans les applications, sur un vrai téléphone ou un lecteur d'écran

## 5. Recherche : bibliographie et articles (session S-E, Opus) — 🔄 en cours
- ⬜ Bibliographie par projet (DOI, arXiv, zbMATH, BibTeX), citations dans les preuves, jamais de référence inventée
- ⬜ Lean → article scientifique (LaTeX/PDF, bibliographie, tableau de vérification)
- ⬜ Article (arXiv / PDF) → énoncés structurés → dossiers Lean (« blueprint » avec dépendances)
- ⬜ Mises à jour systématiques : toutes les bibliothèques Lean des espaces, Sage et ses composants (notification)

## 5 bis. Atelier de recherche (session S-G, Opus) — 🔄 en cours (côté serveur ; écrans dans une session suivante)
- ⬜ Bibliothèque de sources intégrée (articles, livres ; ajout manuel, DOI, arXiv ; import/export BibTeX et Zotero)
- ⬜ Recherche d'articles et d'ouvrages du domaine (arXiv, zbMATH Open, Crossref, OpenAlex)
- ⬜ Lecteur avec surlignages et notes ; questions sur les sources avec citations cliquables (façon NotebookLM)
- ⬜ Notes liées internes (Markdown, LaTeX, Lean, liens, graphe)
- ⬜ Atelier de conjectures (expériences Sage, recherche de contre-exemples, journal des indices)
- ⬜ Conception de preuve guidée : plan → lemmes en parallèle → preuves ; chaque section corrigeable à la main

## 5 ter. Mises à jour internes et automatiques (comme L Katta)
- ⬜ Madalean lui-même : versions signées (Ed25519), installation automatique à un moment calme, retour arrière en un clic
- ⬜ AppImage : mise à jour automatique signée ; APK : téléchargement interne (Android impose un appui pour installer)
- ⬜ Lean, Mathlib, paquets Lean, modèles Goedel : installés automatiquement après vérification (réglable)
- ⬜ Sage, JupyterLab, TeX : détection + bouton qui ouvre un terminal avec la commande exacte (jamais de sudo automatique)

## 5 quater. Installation autonome (session S-I, Opus) — 🔄 en cours
- ⬜ Un seul dossier `~/.local/share/madalean` : Python, JupyterLab, LaTeX, outils PDF, Lean/Mathlib, llama.cpp, tout épinglé et vérifié
- ⬜ Sage installé par Madalean au premier usage, puis mis à jour par lui
- ⬜ Tailscale intégré : Madalean est son propre appareil `madalean` sur ton réseau, sans toucher au Tailscale du PC
- ⬜ Un seul service ; aucun processus ne survit à l'arrêt ; désinstallation complète
- ⬜ Audit des failles connues et liste des composants (SBOM)

## 6. Site GitHub Pages utile (session S-F) — pas de vitrine
- ⬜ « Publier » un projet : site statique (article, graphe blueprint, Lean, vérification, bibliographie) poussé sur un dépôt de ton choix, revérifié par une action GitHub
- ⬜ Canal de mises à jour signé (manifeste Ed25519, page d'installation avec QR code)
- ⬜ Manuel de référence : une seule source pour l'aide intégrée et le site (FR + EN)
- ⬜ README, CHANGELOG 2.0.0, DECISIONS, ACCEPTANCE

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
