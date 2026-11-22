---
id: security
title: Sécurité, expliquée simplement
order: 320
section: settings
audience: all
summary: Qui peut accéder à Madalean, comment les appareils sont reliés et déliés, où sont les clés, et ce que Madalean ne fait jamais.
---

# Sécurité, expliquée simplement

## Qui peut parler à Madalean

Madalean écoute à deux portes, toutes deux fermées vers l'extérieur de l'ordinateur hôte :

1. **La porte locale** (`127.0.0.1:11500`), utilisée par le navigateur ou l'application de bureau **de l'hôte**.
   Elle n'accepte que des requêtes venant de l'hôte lui-même.
2. **La porte des appareils** (`127.0.0.1:11501`), publiée sur votre réseau privé Tailscale. Toute requête doit
   présenter le **jeton** d'un appareil relié, sauf la page de liaison elle-même.

Une troisième porte, sur le réseau local (port 11502), n'existe que si vous l'ouvrez depuis l'hôte (voir
[Tailscale › Sans Tailscale](tailscale.md#sans-tailscale)) ; elle exige aussi le jeton d'un appareil relié, mais son
trafic n'est pas chiffré.

Il n'y a pas de compte Madalean, pas de serveur Madalean sur Internet, pas de télémétrie.

## Les appareils et les codes

- Relier un appareil demande un **code à 6 chiffres** affiché sur l'hôte : valable 5 minutes, utilisable une fois.
  Cinq codes faux bloquent la liaison 10 minutes ; les essais rapprochés sont freinés.
- L'appareil reçoit alors un **jeton** de 256 bits. L'hôte n'en garde qu'une empreinte (SHA-256) : même quelqu'un
  qui lirait les fichiers de l'hôte ne pourrait pas en tirer le jeton.
- Sur le téléphone, le jeton est dans le stockage protégé d'Android ; sur un PC, dans le trousseau du système ; dans
  un navigateur, dans un cookie inaccessible aux scripts de la page.
- **Délier** un appareil (« Réglages › Appareils ») coupe son accès immédiatement.

Un appareil perdu ou volé : déliez-le depuis l'hôte, et retirez-le de votre réseau Tailscale.

## Ce qu'un appareil relié ne peut pas faire

Certains réglages ouvriraient la machine ; ils ne se changent **que depuis l'hôte** (cadenas dans l'interface) :

- écouter sur le réseau local ;
- ouvrir Jupyter (qui exécute du code) aux appareils reliés ;
- autoriser l'exécution d'expériences depuis un appareil relié, ou sans accord préalable.

## Vos clés d'API

Gardées dans le trousseau de l'hôte (sinon dans un fichier lisible par vous seul). Jamais renvoyées à l'interface
(elle sait seulement si une clé est enregistrée), jamais écrites dans un journal, jamais envoyées à un autre
fournisseur que le leur.

## Code exécuté sur l'hôte

- **Lean** compile les preuves écrites par les modèles. Les constructions interdites (`sorry`, nouveaux axiomes,
  commandes de recherche) sont refusées avant compilation.
- **Lean peut aussi exécuter du code** pendant qu'il lit un fichier : `#eval`, `initialize`, `run_cmd`, des
  tactiques, macros, notations ou élaborateurs définis dans le fichier (`elab`, `macro`, `syntax`, `notation`…),
  des attributs qui enregistrent du code, `unsafe`, `implemented_by`, `IO`, `native_decide`. Comme le code Lean peut
  venir d'un modèle, du texte d'un article ou d'un appareil relié, Madalean **refuse de compiler** tout fichier qui
  contient l'une de ces constructions (« Refusé avant compilation : … »). Les `import` sont limités à Mathlib,
  Aesop, Batteries, Std, Qq, ProofWidgets et Plausible. Le contrôle porte sur les mots, hors commentaires et
  chaînes : il peut refuser à tort un fichier légitime (une variable nommée `prefix`, par exemple) ; le message de
  refus indique le genre de construction en cause.
- Ce filtre n'est qu'une première barrière. **Chaque compilation Lean tourne dans un bac à sable** (bubblewrap) :
  sans réseau, sans accès à votre dossier personnel, avec Lean et Mathlib en lecture seule. Les compilations LaTeX
  aussi. « Réglages › Système » indique si le bac à sable est actif ; sans bubblewrap (ou si le système ne le
  permet pas), elles tournent sans cette isolation.
- **Expériences de l'atelier de conjectures** : le code vous est montré, et ne s'exécute qu'après votre accord sur
  **ce code exact**. Il tourne avec des limites de temps, de mémoire et de taille de fichiers, sans vos clés ni
  variables secrètes ; dans le bac à sable, **sans réseau**, avec un système de fichiers en lecture seule où votre
  dossier de configuration, `~/.ssh`, vos trousseaux et l'état de Tailscale sont masqués. Les carnets de Calcul
  tournent dans le même bac à sable.
- **Jupyter** (JupyterLab ouvert à part) exécute ce que vous y tapez, comme sur n'importe quelle installation de
  Jupyter : ses noyaux ne sont pas dans le bac à sable.
- Le texte d'un modèle ne devient jamais une commande système.

## Documents venant de l'extérieur

PDF, sources TeX, fichiers BibTeX et réponses de sites peuvent être piégés. Madalean ne compile jamais le TeX d'un
article (il le lit seulement), compile ses propres exports TeX sans aucun accès au shell, limite la taille et le
contenu des archives, et traite le texte des sources comme des **données** : un passage qui dirait « ignore tes
instructions » n'a pas d'effet sur les outils, parce que les réponses fondées sur vos sources n'ont accès à aucun
outil.

## Ce que Madalean ne fait jamais

- Ouvrir un port sur Internet (pas de Funnel Tailscale, pas de redirection de port).
- Lancer `sudo`, ou installer un paquet système à votre place.
- Envoyer vos données à un service que vous n'avez pas choisi, ou quoi que ce soit en mode *Local*.
- Afficher une preuve comme vérifiée sans le verdict strict de Lean.
- Publier quoi que ce soit sans que vous ayez validé, élément par élément, ce qui part.
- Installer une mise à jour dont la signature n'est pas valide.

Madalean 2.0 a fait l'objet d'une revue de sécurité indépendante avant sa première publication (ses auteurs n'ont
pas fait la revue) ; ses conclusions et les risques acceptés sont dans `docs/SECURITY.md` du dépôt.
