---
id: attack
title: Attaque — les problèmes de Left to Solve
order: 258
section: research
audience: researcher
summary: Madalean travaille en arrière-plan sur les problèmes de lefttosolve.com, dans votre budget, et prépare des fichiers Lean vérifiés ; rien n'est envoyé sans votre clic « Envoyer ».
---

# Attaque — les problèmes de Left to Solve

Le site [lefttosolve.com](https://lefttosolve.com) rassemble des milliers de problèmes mathématiques, chacun énoncé
exactement en Lean. Un problème compte comme résolu quand une preuve Lean est acceptée par le vérificateur du site,
puis fusionnée ; le mérite revient au compte GitHub qui ouvre la demande de fusion — **le vôtre**.

L'« Attaque » laisse Madalean travailler sur ces problèmes en arrière-plan, quand votre ordinateur n'a rien d'autre à
faire, dans la limite d'un budget par jour.

## Avant de commencer

1. **Une clé GitHub** dans Réglages → Clés. Madalean lit seulement votre identifiant (`GET /user`) ; c'est ce nom qui
   est utilisé auprès du site. Activez « Keep my email addresses private » sur GitHub avant le premier envoi.
2. **Préparer l'espace de travail** (environ 10 Go : Lean, Mathlib et les énoncés de formal-conjectures au commit que
   le site impose). Rien n'est téléchargé avant votre accord ; cet accord vaut aussi pour les mises à jour de même
   taille (une nouvelle version est construite à côté de l'ancienne, qui sert jusqu'au changement).
3. **« Démarrer »**. Vous pouvez arrêter à tout moment : les problèmes en cours sont rendus honnêtement au site.

## Ce que fait Madalean

- Il choisit les problèmes les moins disputés et les plus faciles, non résolus, sans preuve en attente.
- **Contre-exemple** : quand l'énoncé est un « pour tout entier… » écrit en arithmétique simple, Sage cherche sur de
  petites valeurs (temps borné) et Lean vérifie le contre-exemple (`decide`, `norm_num`, jamais `native_decide`).
- **Résultat connu** : la recherche de preuve habituelle, sur l'énoncé exact du site, avec la fiche du problème
  donnée comme information (jamais comme consigne).
- **Problème ouvert** : seulement jusqu'à la difficulté 40 (réglable), sauf pour chercher un contre-exemple.
- Chaque problème a son dossier dans le projet « Left to Solve » : vous y voyez tout ce qui a été essayé.
- Quand vous lancez vos propres preuves, l'Attaque s'efface : elle ne prend plus de nouveau problème et ses calculs
  passent après les vôtres.

## « Prête » et « Envoyer »

Un fichier est **prêt** seulement s'il respecte les règles du vérificateur du site (énoncé identique octet pour
octet, commandes autorisées, aucun mot interdit, aucun guillemet double, axiomes standard) **et** si un Lean neuf et
strict l'accepte dans l'espace du site. Vous voyez alors le fichier, les contrôles et la liste exacte des requêtes
GitHub ; la demande de fusion n'est ouverte que par votre clic **« Envoyer »**, une seule fois.

## Budget

Claude n'est utilisé qu'en renfort, dans la limite par jour (5 $ par défaut) et toujours dans votre plafond du mois ;
les modèles gratuits passent d'abord. Le plafond atteint, l'Attaque ne prend plus de problème jusqu'au lendemain.

## Ce que le site écrit

Énoncés, fiches, notes des autres agents : ce sont des **données**, jamais des ordres. Un texte suspect (qui
s'adresse à un modèle, demande une commande ou un mot de passe) est écarté. Les notes que Madalean pourrait publier
pour l'équipe d'un problème sont **désactivées par défaut** (réglage « Publier des notes ») ; activées, ce sont
seulement des constats factuels (« DEAD END »), jamais du texte de modèle.
