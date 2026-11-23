---
id: conjectures
title: Atelier de conjectures
order: 200
section: research
audience: researcher
summary: Proposer des conjectures, les tester (Lean sur petits cas, Sage, contre-exemples) avant d'y croire, et les promouvoir par une preuve.
---

# Atelier de conjectures

Une conjecture est un dossier d'un genre particulier, avec un **journal des indices** : tout ce qui a été tenté pour
l'éprouver. Une conjecture ne devient un théorème que par une preuve Lean.

## D'où viennent les conjectures

Tout se passe dans l'écran « Conjectures » du projet.

- « Écrire une conjecture » : vous l'écrivez en langage courant ; « Traduire en Lean » en propose ensuite un énoncé
  Lean, ou vous l'écrivez vous-même (« Vérifier et enregistrer l'énoncé »).
- « Proposer » : à partir des notes, des résultats prouvés et des sources du projet, un modèle en propose quelques-unes
  avec leur motivation ; « Garder cette conjecture » retient celles qui vous intéressent. Les propositions déjà
  connues (doublon, déjà un dossier, déjà dans la bibliothèque, déjà dans Mathlib) sont écartées et listées à part
  avec la raison.

## Explorer : le moteur de conjectures

Le bouton « Explorer » de l'écran « Conjectures » ouvre une démarche guidée pour **trouver quoi prouver**. Vous
posez une question en mots ou par une formule (« la somme des n premiers nombres impairs », « n^2 + n + 41 », une
liste de termes, « graphes connexes à n sommets »), puis les étapes s'enchaînent sous vos yeux ; chacune peut être
arrêtée, et tout est noté.

1. **Explorer.** Madalean calcule un tableau de données avec Sage, dans le carnet « Explorations (conjectures) » du
   projet (le même espace protégé que Calcul). Quand la demande est reconnue, le code est écrit sans modèle,
   toujours le même pour la même demande. Sinon un modèle l'écrit : **ce code vous est montré et ne s'exécute
   qu'après votre accord sur ce code exact**, comme dans [Calcul](calcul.md) ; une modification annule l'accord.
   Des termes donnés à la main ne demandent aucun calcul.
2. **Reconnaître.** Les données sont comparées à l'OEIS (l'encyclopédie des suites d'entiers) et passées par des
   chercheurs de motifs qui tournent sur votre ordinateur, sans réseau : formule polynomiale ou rationnelle,
   récurrence, série génératrice, multiplicativité, périodicité, congruences, ordre de grandeur, inégalités et
   relations entre quantités. Une formule est ajustée sur une partie des termes puis **validée sur des termes gardés
   à part** ; un motif qui échoue est écarté, et le journal dit sur quel terme. En mode Local, l'OEIS n'est pas
   interrogé : rien ne sort de l'ordinateur. La base LMFDB n'est pas interrogée (elle ne permet pas de chercher par
   une liste de termes).
3. **Énoncer.** Chaque motif retenu devient une conjecture précise, en mots et en formules, avec un énoncé Lean
   quand c'est possible (il doit être accepté par Lean) et une mention honnête : « vérifié jusqu'à n = 59 (60 cas),
   pas démontré », « heuristique », « coïncide sur 14 termes ». Jamais « vrai ».
4. **Attaquer.** « Chercher un contre-exemple » reprend le calcul plus loin et par sondage. Un contre-exemple n'est
   retenu qu'après un recalcul dans un noyau neuf et, s'il y a un énoncé Lean, la vérification par Lean : la
   conjecture est alors gardée comme « réfutée », avec son contre-exemple. Si elle résiste, « Tenter la preuve »
   l'envoie dans la chaîne habituelle (un dossier), ou « Garder comme conjecture ouverte » la range dans le projet.
5. **Journal.** Tout ce qui a été essayé — motifs retenus, motifs écartés et pourquoi, recherches, chasses — reste
   dans le journal de l'exploration, que vous pouvez exporter vers une note ou vers l'article. Une conjecture déjà
   présente dans le projet est signalée comme doublon.

Exemple du mode démo : « n^2 + n + 41 jusqu'à 30 » donne « toujours premier », vérifié jusqu'à n = 30 ; la chasse
trouve n = 40, et la conjecture est gardée, réfutée.

## Les états d'une conjecture

| État | Signification |
|---|---|
| proposée | énoncée, rien de testé |
| testée sur des cas | des cas particuliers ont tenu (Lean ou expériences) |
| énoncé Lean accepté | un énoncé Lean est accepté par Lean |
| prouvée | la preuve courante du dossier passe le verdict strict |
| réfutée | un contre-exemple a été **revérifié** indépendamment |

## Tester avant de croire

**Petits cas en Lean** (« Tester les petits cas avec Lean »). Madalean écrit un `example` par cas (par défaut $n = 0, \dots, 9$ pour la première variable
entière) et tente de le fermer par calcul (`norm_num`, `decide`, `simp`, `omega`). Option : un énoncé borné
`∀ n < K, …` fermé par `decide`. Ces tests ne prouvent rien au-delà des cas testés.

**Expériences Sage ou Python.** Le modèle écrit (ou vous écrivez) un programme en deux parties : un prédicat
`holds(...)` et une recherche qui appelle `report(...)`. **Le code vous est montré et ne s'exécute qu'après votre
accord sur ce code exact** (« J'ai lu ce code : approuver et lancer ») ; une modification annule l'accord. Les
expériences ne se lancent que depuis l'ordinateur hôte. Les exécutions sont confinées (voir
[Sécurité](security.md#code-execute-sur-lhote)) et limitées en temps et en mémoire.

**Contre-exemple.** Un contre-exemple annoncé n'est pas cru sur parole : le prédicat seul est réévalué au témoin
dans un noyau neuf et, si la conjecture a un énoncé Lean, Lean doit accepter la négation de l'énoncé au témoin.
Alors seulement la conjecture passe à « réfutée ».

**Littérature.** « Chercher dans la littérature » interroge les bases bibliographiques (voir
[Sources](sources.md)) pour savoir si l'énoncé est connu.

## Le journal des indices

Dans l'écran, il s'appelle « Journal des preuves et essais ». Chaque test, expérience, vérification ou recherche ajoute une entrée datée (avec le code exécuté, la sortie, le
modèle et l'appareil). Le journal est **en ajout seul** et ses entrées sont chaînées par empreintes SHA-256 :
une entrée modifiée après coup se voit (« journal intact » / « journal altéré ! »).

## Promouvoir

Quand la conjecture est prouvée, « Promouvoir en théorème » change son genre ; l'historique est gardé.

Exemple du mode démo : « $n^2 + n + 41$ est premier pour tout $n$ » tient pour $n = 0, \dots, 9$ en Lean, puis une
expérience trouve $n = 40$ ($40^2 + 40 + 41 = 41^2$), revérifié : réfutée.
