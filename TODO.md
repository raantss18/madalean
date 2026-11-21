# Madalean 2.0 — liste des tâches

État : ⬜ à faire · 🔄 en cours · ✅ fait et vérifié · ⚠️ fait, non vérifié en réel

## 0. Préparation
- ✅ Dépôt renommé `madalean`, dossier `~/madalean`, branche `v2`
- ✅ Architecture et contrat des sessions (`docs/ARCHITECTURE.md`), interface du moteur (`madalean/brain/api.py`)

## 1. Serveur (session S-A, Opus)
- 🔄 Serveur asyncio, API + WebSocket (synchronisation de tous les appareils)
- 🔄 Sécurité : appairage par code, appareils révocables, clés d'API au trousseau
- 🔄 Projets, dossiers, sous-dossiers en parallèle, historique par dossier
- 🔄 Chaîne comprendre → traduire (+ explication de l'énoncé Lean) → prouver → expliquer
- 🔄 Export PDF/LaTeX très lisible (énoncé, Lean, preuve en langage naturel, tampon de vérification)
- 🔄 JupyterLab + Sage derrière la même connexion, même assistant
- 🔄 Migration des dossiers 1.x, mode démonstration, tests

## 2. Moteur de modèles (session S-B, Opus)
- 🔄 Routeur de L Katta (meilleur modèle gratuit, pauses, quotas), repli hors ligne automatique
- 🔄 Claude (API native, outils), Gemini, OpenRouter, Ollama, modèles locaux Goedel/Qwen
- 🔄 Mode agentique : prouveur qui compile avec Lean et cherche dans Mathlib
- 🔄 RAG : index plein texte des déclarations Mathlib (+ recherche par le sens si possible)

## 3. Applications (session S-C, Opus)
- 🔄 AppImage (ce PC et autres ordinateurs), APK Android (téléphone, tablette)
- 🔄 Icône et identité Madalean
- 🔄 Script Tailscale (une seule entrée ajoutée, celles de Sampana intactes)

## 4. Interface web (session S-D, Opus) — après S-A
- ⬜ Écran 1 : écrire l'énoncé (langage naturel / LaTeX, import .tex)
- ⬜ Écran 2 : traduction Lean avec explication ligne par ligne (apprendre)
- ⬜ Écran 3 : prouver, vérifier, expliquer, exporter en PDF
- ⬜ Projets et dossiers en parallèle, historique clair, bibliothèque de résultats
- ⬜ Modes « Apprendre » (indices progressifs, exercices) et « Recherche »
- ⬜ Réglages : modèles, clés, appareils, mises à jour ; français / anglais ; clair / sombre ; téléphone

## 5. Recherche : bibliographie et articles (session S-E, Opus) — après S-A
- ⬜ Bibliographie par projet (DOI, arXiv, zbMATH, BibTeX), citations dans les preuves, jamais de référence inventée
- ⬜ Lean → article scientifique (LaTeX/PDF, bibliographie, tableau de vérification)
- ⬜ Article (arXiv / PDF) → énoncés structurés → dossiers Lean (« blueprint » avec dépendances)
- ⬜ Mises à jour systématiques : toutes les bibliothèques Lean des espaces, Sage et ses composants (notification)

## 5 bis. Atelier de recherche (session S-G, Opus) — après S-A et S-E
- ⬜ Bibliothèque de sources intégrée (articles, livres ; ajout manuel, DOI, arXiv ; import/export BibTeX et Zotero)
- ⬜ Recherche d'articles et d'ouvrages du domaine (arXiv, zbMATH Open, Crossref, OpenAlex)
- ⬜ Lecteur avec surlignages et notes ; questions sur les sources avec citations cliquables (façon NotebookLM)
- ⬜ Notes liées internes (Markdown, LaTeX, Lean, liens, graphe)
- ⬜ Atelier de conjectures (expériences Sage, recherche de contre-exemples, journal des indices)
- ⬜ Conception de preuve guidée : plan → lemmes en parallèle → preuves ; chaque section corrigeable à la main

## 6. Site et documentation (session S-F) — après S-D
- ⬜ Site GitHub Pages (FR + EN), captures, guide d'installation, guide d'appairage
- ⬜ README, CHANGELOG 2.0.0, DECISIONS, ACCEPTANCE

## 7. Intégration et publication (intégrateur)
- ⬜ Assemblage, tests complets sans carte graphique
- ⬜ Tests réels : modèles locaux (carte graphique), fournisseurs gratuits, Claude et Gemini avec tes clés
- ⬜ Appairage réel par Tailscale (téléphone, tablette, autre PC)
- ⬜ Migration de tes dossiers, retrait de l'ancienne application PySide6
- ⬜ Version 2.0.0 : tag, release (AppImage, APK), site en ligne
