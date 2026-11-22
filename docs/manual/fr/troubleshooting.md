---
id: troubleshooting
title: Dépannage
order: 400
section: help
audience: all
summary: Les messages d'erreur en clair, leur cause et quoi faire.
---

# Dépannage

« Réglages › Système », partie « État de santé », montre l'état de chaque composant (espaces Lean, modèles, TeX,
polices, Jupyter, bac à sable, disque) avec un bouton « Réparer » quand il en existe un. Commencez par là.

## Installation

Le journal complet de l'installation est dans `~/.local/share/madalean/install.log`. `install.sh` peut être relancé
sans risque : il reprend où il s'était arrêté. Voir [Installer Madalean](install.md).

### L'installateur .run ne démarre pas

- **Rien ne se passe au double-clic, ou « Permission non accordée »** : le fichier n'est pas exécutable. Clic droit ›
  « Propriétés » › « Permissions » › « Autoriser l'exécution du fichier comme un programme », ou dans un terminal
  `chmod +x Madalean-installer.run`, puis relancez-le.
- **Le double-clic ouvre le fichier dans un éditeur de texte** : lancez-le depuis un terminal,
  `./Madalean-installer.run`.
- **« Fichier abîmé ou modifié (empreinte SHA-256 incorrecte) »** : le fichier a été abîmé pendant le
  téléchargement, ou il est incomplet. Supprimez-le et **téléchargez-le de nouveau** depuis la page des versions ;
  ne contournez jamais ce contrôle.


### Aucun navigateur ne s'ouvre

Sans session graphique, l'installateur passe tout seul à l'assistant en terminal. S'il y a bien un bureau mais
qu'aucun navigateur ne s'ouvre, l'installateur affiche dans le terminal l'adresse de sa page
(`http://127.0.0.1:…`, avec sa clé à usage unique) : copiez-la dans un navigateur de la **même** machine. Vous pouvez
aussi forcer l'assistant en terminal : `./Madalean-installer.run --terminal` (ou, depuis les sources,
`./install.sh --assistant`).

### Le disque est plein

L'étape 1 affiche la place libre. Prévoyez ≈ 6 Go sans modèle local ni SageMath, ≈ 25 Go avec les modèles locaux,
5 Go de plus pour SageMath (voir [Installer Madalean](install.md#ce-quil-faut-avant-de-commencer)). Libérez de la
place, ou réduisez le plan : `--models none` (ou `--models prover`), `--sage later`. Relancez ensuite
`install.sh` : ce qui est déjà installé n'est pas refait. Les téléchargements en cours sont gardés dans
`~/.local/share/madalean/downloads/` et repris.

### « Échec de micromamba »

L'installation de l'environnement principal (étape 3) a échoué, le plus souvent à cause d'une coupure de réseau ou
d'un disque plein. Les dernières lignes du journal sont affichées ; le détail est dans
`~/.local/share/madalean/install.log`. Vérifiez la connexion et la place libre, puis relancez `install.sh`.

### « Empreinte SHA-256 incorrecte : … »

Un fichier téléchargé ne correspond pas à l'empreinte attendue : il a été tronqué ou altéré en route. Le fichier
fautif est supprimé ; relancez `install.sh`, qui le télécharge de nouveau. Si l'erreur se répète, un proxy ou un
filtre de votre réseau modifie peut-être les téléchargements.

### Pas de carte NVIDIA, ou pilote trop ancien

Ce n'est pas une erreur : Madalean installe alors le moteur des modèles pour le processeur et ne conseille aucun
modèle local. Les modèles en ligne fonctionnent normalement. Si vous avez bien une carte NVIDIA, vérifiez que le
pilote est installé (`nvidia-smi` doit répondre), puis relancez `./install.sh --gpu`. Voir
[Modèles locaux](components.md#modeles-locaux).

### Le SageMath du système n'est pas retenu

Pour être réutilisé, le SageMath de votre système doit être en version 10.0 ou plus récente **et** fournir son noyau
Jupyter `sagemath` (par exemple `/usr/share/jupyter/kernels/sagemath`). Sinon, Madalean utilise sa propre copie
(≈ 5 Go). Installez le noyau Jupyter avec votre distribution, ou laissez Madalean installer sa copie. Voir
[SageMath](components.md#sagemath).

### L'export LaTeX échoue

« Réglages › Système », partie « État de santé », ligne « LaTeX (export PDF) » : « Réparer » réinstalle le paquet
TeX. Si vous utilisez le TeX Live du système en premier (`tex_engine = system`), il doit être en version 2022 ou plus
récente, avec `fontspec`. Voir aussi [Export](#export) plus bas et [LaTeX](components.md#latex).

### Le service ne démarre pas

À la fin de l'installation, « Le serveur ne répond pas encore » signifie que le service n'a pas démarré à temps.
Regardez son journal :

```bash
systemctl --user status madalean
journalctl --user -u madalean -e
```

Le journal donne la cause (port 11500 déjà pris par un autre programme, composant manquant…). Si `systemctl --user`
n'est pas disponible (certains conteneurs ou sessions sans systemd), lancez Madalean à la main :
`~/.local/share/madalean/current/bin/madalean serve`.

### Le bac à sable est signalé inactif

bubblewrap n'est pas installé : c'est un paquet de votre distribution, à installer vous-même (par exemple
`sudo apt install bubblewrap`). Voir [bubblewrap](components.md#bubblewrap-le-bac-a-sable).

## Connexion et appareils

### L'appareil ne joint pas l'hôte

1. L'ordinateur hôte est-il allumé, et pas en veille ?
2. Tailscale est-il **connecté** sur l'appareil, avec le même compte que l'hôte ? (application Tailscale :
   interrupteur actif.)
3. Le serveur tourne-t-il ? Sur l'hôte : `systemctl --user status madalean`.
4. Le nœud Tailscale de Madalean est-il approuvé et en marche ? Sur l'hôte : `curl -s http://127.0.0.1:11500/api/net`
   doit indiquer `"state": "running"` (sinon, voir [Relier un appareil › Étape 1](pairing.md)). Si vous utilisez le
   Tailscale du système à la place : `scripts/tailscale_setup.sh --status`.
5. L'adresse tapée est-elle complète, `madalean.tailXXXX.ts.net` (ou `nom-du-pc.tailXXXX.ts.net:10500` avec le
   Tailscale du système) ?

### « Cet appareil n'est pas (ou plus) relié »

L'appareil a été délié, ou ses données ont été effacées. Demandez un nouveau code sur l'hôte et reliez-le de nouveau.

### Le certificat HTTPS est refusé, ou la première connexion est très lente

HTTPS n'est pas activé sur votre tailnet : voir [Tailscale › Activer HTTPS](tailscale.md#activer-https). La toute
première connexion peut prendre quelques secondes, le temps d'émettre le certificat.

### « Réservé à l'ordinateur hôte »

Ce réglage ouvre la machine à d'autres appareils ; il ne se change que sur l'hôte. Voir [Sécurité](security.md).

## Modèles

### « Aucun modèle disponible »

- Mode *Local* : aucun modèle local n'est installé ou chargeable. « Réglages › Système » indique lequel manque ;
  `./install.sh` télécharge les modèles.
- Mode *En ligne* : pas de réseau, ou tous les fournisseurs sont en pause (quotas). Passez en *Automatique* pour
  utiliser les modèles locaux en secours.

### « Le fournisseur refuse la clé »

La clé a été mal copiée (espace en trop), révoquée, ou le compte n'a plus de crédit. Recréez-la sur le site du
fournisseur et collez-la de nouveau (« Réglages › Fournisseurs ») : Madalean la teste aussitôt. Après un refus de
clé, Madalean met le fournisseur en pause 12 h (« En pause pour l'instant (clé refusée (vérifiez-la)) »). Pour
Hugging Face, un nouveau jeton qui passe le test lève la pause tout de suite ; pour les autres fournisseurs, la pause
va à son terme, puis la nouvelle clé sert normalement.

### Le modèle local est lent, ou « mémoire graphique insuffisante »

Un autre programme occupe la carte graphique (jeu, autre IA). « Réglages › Système » montre la mémoire utilisée par
application. Sans carte NVIDIA, les modèles locaux tournent sur le processeur : comptez des minutes par réponse.

### « Pause : quota atteint » sur un fournisseur gratuit

Normal : Madalean passe au modèle suivant et réessaie le fournisseur plus tard (après l'heure indiquée par le
fournisseur, ou le lendemain pour un quota journalier).

## Lean

### « Lean refuse l'énoncé »

La traduction n'est pas du Lean valide pour cet espace (nom inconnu, notation d'une autre version de Mathlib). Le
message de Lean est affiché sous l'énoncé. « Corriger l'énoncé… » relance la traduction avec l'erreur ; ou
« Modifier à la main ».

### « Refusé avant compilation : … »

Le code contient une construction qui pourrait exécuter du code sur l'hôte (`#eval`, `macro`, `elab`, `unsafe`,
`native_decide`…) ou un `import` hors de Mathlib et de ses dépendances : Madalean refuse de le compiler (voir
[Sécurité](security.md#code-execute-sur-lhote)). Le message donne le genre de construction trouvée, par exemple
« méta-programmation (élaborateur, macro, syntaxe) », « accès au système (IO, unsafe) » ou « import d'un module non
autorisé ». Retirez-la. Si le mot en cause est un simple nom de variable (`prefix`, `syntax`, `IO`…), renommez la
variable.

### « Pas de preuve trouvée »

Les essais sont épuisés. Ce n'est pas une preuve que l'énoncé est faux. Essayez : relire l'énoncé (hypothèse
manquante ?), « Autre méthode », un modèle plus fort (une clé), « Découper en lemmes », ou un indice dans une demande
de suivi (« utilise une récurrence sur $n$ »).

### « Preuve refusée : contient sorry » ou « axiome non standard »

Le verdict strict refuse une preuve incomplète ou qui ajoute un axiome. Seuls `propext`, `Classical.choice` et
`Quot.sound` sont admis.

### « Délai de compilation dépassé »

La compilation a dépassé le temps maximal (« Réglages › Modèles », 10 à 1800 s). Une tactique comme `simp` ou
`nlinarith` peut chercher longtemps ; une preuve plus explicite compile plus vite.

### « Espace Lean introuvable » ou « espace non prêt »

L'espace de travail n'est pas installé ou sa compilation n'est pas terminée. « Réglages › Espaces Lean » donne son
état ; relancez `./install.sh` si besoin.

### « Ce dossier a déjà un travail en cours »

Un dossier n'a qu'un travail actif. Attendez la fin, ou « Arrêter ».

## Export

### « Pas de LaTeX sur l'ordinateur hôte : la version HTML s'ouvre »

Le moteur LaTeX de Madalean (installé par `./install.sh`) est absent ou n'a pas pu composer le document, et aucun
LaTeX du système ne l'a remplacé. Le HTML s'imprime en PDF depuis le navigateur. Pour le vrai PDF : « Réglages ›
Système », partie « État de santé », ligne LaTeX, bouton « Réparer » (ou relancez `./install.sh`).

### Des symboles manquent dans le PDF

Les polices DejaVu Sans Mono et Noto Sans Math sont installées avec Madalean ; « Réglages › Système » vérifie
qu'elles sont présentes. Relancez `./install.sh` si l'une manque.

## Jupyter

### « Jupyter n'est pas disponible »

JupyterLab (installé avec Madalean) est absent ou n'a pas démarré. « Réglages › Système » donne la cause, avec un
bouton « Réparer ».

### « Jupyter n'est accessible que depuis l'hôte »

L'hôte n'a pas ouvert Jupyter aux appareils reliés (« Réglages › Carnet et accès », sur l'hôte).

## Quand rien ne va

```bash
systemctl --user restart madalean
journalctl --user -u madalean -e
```

Le journal ne contient ni clé, ni jeton : vous pouvez le joindre à un signalement de problème.
