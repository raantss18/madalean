---
id: install
title: Installer Madalean
order: 10
section: start
audience: all
summary: Ce qu'il faut comme machine, les trois façons d'installer (installateur graphique, assistant en terminal, installation automatique), ce que fait install.sh, ses options, la mise à jour et la désinstallation.
---

# Installer Madalean

Madalean s'installe sur **un seul ordinateur**, l'**ordinateur hôte** : c'est lui qui fait tourner le serveur, Lean,
les modèles locaux et qui garde vos données. Vos autres appareils (un autre PC, une tablette, un téléphone)
n'installent qu'une application légère, ou rien du tout : un navigateur suffit. Voir [Relier un appareil](pairing.md).

Cette page décrit l'installation elle-même. Deux pages la complètent :

- [Ce qu'installe Madalean, composant par composant](components.md) : à quoi sert chaque pièce (Lean, SageMath,
  LaTeX, modèles locaux…), sa taille, et s'il vaut mieux réutiliser ce qui est déjà sur votre machine ;
- [Première configuration](first-config.md) : les clés des fournisseurs en ligne, le mode de travail des modèles et
  les comportements automatiques, à régler une fois l'installation terminée.

## Ce qu'il faut avant de commencer

| | Minimum | Conseillé |
|---|---|---|
| Système | Linux 64 bits (x86_64), n'importe quelle distribution récente | — |
| Mémoire vive | 8 Go | 16 Go ou plus |
| Carte graphique | aucune | NVIDIA avec au moins 8 Go de mémoire graphique, pour faire tourner le prouveur local |
| Disque | ≈ 6 Go libres sans modèles locaux ni SageMath | un SSD, avec la place indiquée ci-dessous |

Place sur le disque, selon ce que vous installez :

| Élément | Place |
|---|---|
| Madalean et ses composants de base (Python, JupyterLab, LaTeX, polices, Lean, moteur des modèles) | ≈ 6 Go |
| Les trois modèles locaux (dans `~/models`) | ≈ 15 Go de plus, soit ≈ 25 Go en tout avec la base et une marge |
| SageMath (écran « Calcul ») | ≈ 5 Go de plus |
| Chaque espace de travail Lean/Mathlib construit sur la machine | ≈ 5 Go |

**Sans carte NVIDIA**, tout fonctionne : les modèles en ligne (gratuits, ou avec une clé) ne dépendent pas de votre
carte graphique, et ce sont eux que Madalean utilise par défaut. Seuls les modèles locaux seraient trop lents sur le
processeur ; l'installation ne les propose alors pas (voir [Les modèles locaux](components.md#modeles-locaux)).

**Avec une carte NVIDIA**, seul le **pilote NVIDIA** doit être installé, par vous, avec les outils de votre
distribution. Madalean ne touche jamais aux pilotes et n'a pas besoin du « CUDA Toolkit ». Si le pilote est trop
ancien, il installe le moteur des modèles pour le processeur.

Il faut enfin une connexion Internet pendant l'installation (sauf [installation hors ligne](#installer-sans-reseau)),
et les commandes de base `bash`, `curl`, `tar` et `sha256sum`, présentes sur toutes les distributions courantes.

## Trois façons d'installer

| Façon | Pour qui | Questions posées |
|---|---|---|
| [Installateur graphique](#avec-linstallateur-graphique-conseille) (conseillée) | tout le monde | dans une page de votre navigateur, avec un plan recommandé |
| [Depuis les sources, assistant en terminal](#depuis-les-sources-avec-lassistant-en-terminal) | qui préfère le terminal ou veut suivre le code | dans le terminal, avec le même plan recommandé |
| [Installation automatique](#sans-question-installation-automatique) | installation répétée, script, machine distante | aucune : les choix par défaut |

Les trois aboutissent à la même installation, faite par le même programme (`install.sh`). Aucune ne demande votre
mot de passe : rien n'est installé hors de votre dossier personnel.

### Avec l'installateur graphique (conseillé)

1. **Téléchargez** le fichier `Madalean-installer.run` : le lien
   <https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run> mène toujours à la
   dernière version. La
   [page de téléchargement](site:install) du site donne aussi ce lien.
2. **Rendez-le exécutable.** Un fichier téléchargé par un navigateur ne peut pas être lancé tel quel : c'est une
   protection de Linux. Au choix :
   - dans le gestionnaire de fichiers : clic droit sur le fichier › « Propriétés » › onglet « Permissions » › cochez
     « Autoriser l'exécution du fichier comme un programme » (le libellé varie selon le bureau : « Exécutable »,
     « Est exécutable »…) ;
   - ou dans un terminal, dans le dossier du fichier :

     ```bash
     chmod +x Madalean-installer.run
     ```
3. **Lancez-le** : double-clic sur le fichier, ou dans le terminal :

   ```bash
   ./Madalean-installer.run
   ```

Ce qui se passe ensuite :

- Le fichier **vérifie d'abord sa propre intégrité** (empreinte SHA-256) avant de décompresser quoi que ce soit. Un
  fichier abîmé pendant le téléchargement est refusé avec un message clair : téléchargez-le de nouveau.
- Il ouvre ensuite un **assistant d'installation dans votre navigateur**. Cette page est servie par l'installateur
  lui-même, sur votre machine seulement (adresse `127.0.0.1`, protégée par une clé à usage unique) : elle n'est
  joignable par aucun autre ordinateur.
- L'assistant vous mène en six écrans :
  1. **Bienvenue** : ce qui va être installé et où.
  2. **Examen de la machine** : système, mémoire, carte graphique, place libre, et les outils déjà présents (Lean,
     SageMath, TeX Live, Tailscale, Ollama, bubblewrap…).
  3. **Plan recommandé** : pour chaque élément (modèles locaux, SageMath, LaTeX, espaces Lean…), le choix conseillé
     pour votre machine et la raison ; vous pouvez changer chaque choix.
  4. **Installation** : la progression en direct, étape par étape.
  5. **Première configuration** : ce qu'il reste à régler dans Madalean (clé de modèle en ligne, mode de travail,
     comportements automatiques, appareils) et un bouton « Ouvrir Madalean » (`http://127.0.0.1:11500`), où
     l'assistant de premier démarrage prend le relais (voir [Première configuration](first-config.md)).
  6. **Terminé** : l'adresse de Madalean ; « Fermer l'assistant » arrête la petite page locale (elle s'arrête
     aussi d'elle-même après 30 minutes sans activité, jamais pendant une installation).
- En cas d'erreur, l'écran d'installation montre les dernières lignes, « Voir le détail » le journal complet, et
  « Réessayer » reprend là où l'installation s'est arrêtée.
- **Sans session graphique** (par exemple sur une machine à laquelle vous êtes connecté par `ssh`), l'installateur
  passe tout seul à l'assistant en terminal décrit ci-dessous.


### Depuis les sources, avec l'assistant en terminal

Si vous préférez le terminal, ou si vous voulez installer la version de développement :

```bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh
```

Lancé dans un terminal, `install.sh` :

1. examine la machine (système, mémoire, carte graphique, place libre, outils déjà installés) ;
2. affiche un **tableau récapitulatif** de ce qu'il a trouvé ;
3. propose un **plan recommandé** (le même que l'installateur graphique) ;
4. vous laisse l'**accepter** tel quel ou **changer chaque élément**, puis installe.

Pour seulement voir ce plan sans rien installer : `./install.sh --dry-run`.

### Sans question (installation automatique)

```bash
./install.sh --yes
```

`--yes` (ou `-y`) installe avec les choix par défaut, sans poser de question. C'est aussi ce qui se passe quand
`install.sh` n'est pas lancé dans un terminal (depuis un autre script, par exemple). Vous pouvez y ajouter les
options du [tableau ci-dessous](#options-de-installsh), ou réutiliser un plan enregistré avec `--plan FICHIER`.

## Ce que fait install.sh, étape par étape

Le script affiche neuf étapes, numérotées de `1/9` à `9/9`. Il est **relançable sans risque** : s'il est interrompu
(coupure de réseau, machine éteinte), relancez-le ; il reprend où il s'était arrêté, sans refaire ce qui est déjà
fait. Chaque fichier téléchargé est vérifié par son **empreinte SHA-256** (une sorte de signature numérique du
contenu) : un fichier altéré est refusé.

| Étape | Ce qui est fait |
|---|---|
| 1. Vérifications | Linux x86_64 ? outils de base présents ? place libre sur le disque |
| 2. Madalean | le code de Madalean et son interface web sont copiés dans `~/.local/share/madalean/versions/<version>` ; un lien `current` désigne la version en service |
| 3. Environnement | le petit gestionnaire de paquets **micromamba** est téléchargé, puis il installe l'environnement principal, figé à l'avance : Python 3.13, JupyterLab, le moteur LaTeX tectonic, poppler (lecture des PDF), git… Chaque paquet est vérifié par son empreinte SHA-256 |
| 4. Composants vérifiés | polices (DejaVu Sans Mono, Noto Sans Math), paquet TeX (pour composer les PDF sans réseau), **elan** (le gestionnaire de versions de Lean), **llama.cpp** (moteur des modèles locaux, pour votre carte NVIDIA ou pour le processeur), **madalean-net** (le nœud Tailscale intégré, qui permet à vos appareils de joindre l'hôte) |
| 5. Espaces Lean | les espaces Lean déjà construits sur la machine sont repris (par liens physiques : aucune place en plus) ; sinon, avec `--build-workspace`, l'espace « Lean actuel » est construit |
| 6. Modèles locaux | les modèles retenus par le plan sont téléchargés dans `~/models` ; ceux qui y sont déjà sont réutilisés, jamais déplacés |
| 7. Service | le service utilisateur systemd `madalean` est installé et démarré : Madalean tourne en arrière-plan dès l'ouverture de votre session |
| 8. Menu | une entrée « Madalean » est ajoutée au menu des applications |
| 9. Contrôle | un bilan de santé de chaque composant, puis un essai de connexion au serveur |

À la fin, le script affiche la durée, la place occupée et l'adresse à ouvrir : `http://127.0.0.1:11500`. Le journal
complet est dans `~/.local/share/madalean/install.log`.

## Ce qui est déjà sur votre machine

Madalean **n'utilise jamais `sudo`** et **ne lance jamais le gestionnaire de paquets de votre distribution**
(`pacman`, `apt`, `dnf`, `zypper`…). Il ne modifie aucun programme du système. Pour ce qu'il trouve déjà installé :

| Déjà présent | Ce que fait Madalean |
|---|---|
| Des espaces Lean construits, des versions de Lean dans `~/.elan` | repris **en lecture seule** pour l'import ; `~/.elan` n'est jamais modifié |
| Des modèles dans `~/models` | réutilisés (vérifiés par empreinte), jamais déplacés |
| SageMath du système | réutilisé s'il est compatible et si vous le choisissez ; sinon Madalean installe sa propre copie à la demande |
| TeX Live | utilisé en secours, ou en premier si vous le choisissez |
| Python du système | jamais modifié ; le serveur utilise son propre Python |
| Tailscale, Ollama | laissés en place ; aucun conflit |

Le détail, et ce qu'il vaut mieux choisir dans chaque cas : [Ce qu'installe Madalean](components.md).

Quand quelque chose ne peut venir que de votre distribution — c'est le cas de **bubblewrap**, qui isole les
compilations et les calculs dans un « bac à sable » —, le script **affiche la commande exacte** à lancer vous-même,
par exemple `sudo pacman -S bubblewrap` sur Arch Linux ou `sudo apt install bubblewrap` sur Debian et Ubuntu. Les
commandes pour chaque distribution sont dans [Ce qu'installe Madalean › bubblewrap](components.md#bubblewrap-le-bac-a-sable).

## Options de install.sh

`./install.sh --help` les affiche toutes.

| Option | Effet |
|---|---|
| `--yes`, `-y` | aucune question : les choix par défaut |
| `--assistant` | force l'assistant en terminal (même quand il ne serait pas proposé) |
| `--plan FICHIER` | installe selon un plan enregistré par l'assistant ou par l'installateur graphique |
| `--dry-run` | examine la machine et affiche le plan, sans rien installer |
| `--models all\|prover\|none` | modèles locaux : les trois, seulement le prouveur, ou aucun (sans question : les trois ; l'assistant conseille selon la carte graphique) |
| `--sage later\|now\|system` | SageMath : à la première utilisation de « Calcul » (défaut), tout de suite, ou celui du système |
| `--tex own\|system` | LaTeX : celui de Madalean (défaut) ou le TeX Live du système en premier |
| `--cpu` \| `--gpu` | moteur des modèles pour le processeur, ou pour la carte NVIDIA (défaut : la carte si le pilote convient) |
| `--no-models` | ne télécharge aucun modèle local (les fichiers déjà dans `~/models` restent utilisés) |
| `--no-workspaces` | n'installe aucun espace Lean |
| `--build-workspace` | construit l'espace « Lean actuel » si aucun n'est trouvé (≈ 5 Go, réseau nécessaire) |
| `--build-net` | construit le nœud Tailscale `madalean-net` à partir des sources (il doit donner exactement l'empreinte attendue) |
| `--offline DOSSIER` | installe sans réseau, depuis un export fait avec `./export_offline.sh` |
| `--prefix DOSSIER` | dossier d'installation (défaut `~/.local/share/madalean`) |
| `--config-dir DOSSIER` | dossier des réglages et des données (défaut `~/.config/madalean`) |
| `--cache-dir DOSSIER` | dossier des caches (défaut `~/.cache/madalean`) |
| `--no-systemd` | n'installe pas le service systemd (lancez alors Madalean vous-même) |
| `--no-desktop` | n'ajoute pas d'entrée au menu des applications |
| `--port N`, `--remote-port N` | ports du serveur : interface locale (défaut 11500) et accès des appareils reliés (défaut 11501) |


## Où sont enregistrés vos choix

Les choix faits à l'installation (modèles locaux, SageMath, LaTeX…) sont écrits dans
`~/.config/madalean/setup.json`. Madalean lit ce fichier au premier démarrage et applique les réglages qui en
découlent, par exemple `sage_source` (quel SageMath utiliser) et `tex_engine` (quel LaTeX utiliser) ; vous pouvez
les changer à tout moment (l'application les lit aussi par `GET /api/setup`). Voir
[Première configuration › Choix faits à l'installation](first-config.md#choix-faits-a-linstallation).

Au premier démarrage dans le navigateur de l'hôte, l'assistant [« Premiers pas »](first-config.md#lassistant-premiers-pas)
montre de nouveau ces choix (choix conseillé et raison pour cette machine) et permet de les changer.

## Où sont les choses

| Quoi | Où |
|---|---|
| Madalean et tous ses composants | `~/.local/share/madalean/` |
| Journal d'installation | `~/.local/share/madalean/install.log` |
| Réglages, choix d'installation, projets, dossiers, appareils reliés, clés (si pas de trousseau) | `~/.config/madalean/` |
| Index de recherche, caches | `~/.cache/madalean/` |
| Modèles locaux | `~/models/` |
| Carnets Jupyter | `~/Documents/Madalean/notebooks/` |
| Service systemd | `~/.config/systemd/user/madalean.service` |

Au premier démarrage, si vous aviez Lean AI Station 1.x, le serveur **copie** (sans jamais les déplacer) vos
réglages, dossiers et bibliothèque depuis `~/.config/lean-ai-station/`.

## Démarrer et arrêter

Le service démarre avec votre session. Ouvrez l'interface sur l'hôte : « Madalean » dans le menu des applications,
ou `http://127.0.0.1:11500` dans un navigateur. En terminal, si besoin :

```bash
systemctl --user status madalean      # état
systemctl --user restart madalean     # redémarrer
journalctl --user -u madalean -e      # journal
```

Ensuite : [Première configuration](first-config.md), puis [Premier démarrage](first-run.md) pour un premier énoncé.

## Installer sans réseau

Pour un ordinateur sans accès à Internet : sur une machine connectée où Madalean est installé, `./export_offline.sh`
prépare un dossier contenant tout ce qu'il faut (paquets, composants, espaces Lean, modèles). Copiez ce dossier sur
l'autre machine (clé USB, disque), puis :

```bash
./install.sh --offline /chemin/vers/l-export
```

Les empreintes SHA-256 sont vérifiées comme pour une installation en ligne.

## Mettre à jour

Madalean se met à jour **depuis l'application**, dans « Réglages › Mises à jour » : chaque nouvelle version est
**signée**, vérifiée, installée à côté de l'ancienne, puis mise en service ; la version précédente est gardée pour
revenir en arrière. Il n'est pas nécessaire de relancer `install.sh`. Le détail : [Mises à jour](updates.md).

## Désinstaller

Depuis le dossier des sources (ou `~/.local/share/madalean/current`) :

```bash
./uninstall.sh
```

Le script **liste d'abord** exactement ce qui sera supprimé, avec la taille de chaque élément, puis **demande
confirmation**. Il arrête d'abord le service et tous ses processus.

| Supprimé | Conservé |
|---|---|
| `~/.local/share/madalean` (environnement, composants, espaces Lean installés par Madalean, paquet TeX, état du nœud Tailscale, versions de Madalean) | `~/.config/madalean` : vos réglages, projets, dossiers, appareils reliés et clés |
| `~/.cache/madalean` | `~/models` : vos modèles |
| le service systemd et l'entrée du menu | `~/Documents/Madalean` : vos carnets |
| | jamais touchés : `~/.elan`, les paquets du système, le Tailscale du système |

Options :

| Option | Effet |
|---|---|
| `--purge` | propose en plus, avec une question pour chacun, de supprimer `~/.config/madalean` et `~/models` |
| `--yes` | ne demande pas la confirmation générale (les questions de `--purge` restent posées) |
| `--prefix`, `--config-dir`, `--cache-dir` | à donner si vous les aviez changés à l'installation |

Les clés enregistrées dans le trousseau du système restent dans le trousseau : supprimez-les d'abord dans
« Réglages › Fournisseurs » (« Retirer la clé ») si vous voulez les effacer.
