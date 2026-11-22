---
id: components
title: Ce qu'installe Madalean, composant par composant
order: 12
section: start
audience: all
summary: Lean, SageMath, JupyterLab, modèles locaux, LaTeX, Python, Tailscale, Ollama, bubblewrap — à quoi sert chacun, s'il est obligatoire, sa taille, où il se trouve, s'il vaut mieux réutiliser ce qui est déjà installé, et comment le réparer ou le retirer.
---

# Ce qu'installe Madalean, composant par composant

Madalean s'appuie sur plusieurs programmes : Lean pour vérifier les preuves, SageMath pour calculer, LaTeX pour
composer les PDF, des modèles d'IA… Cette page dit, pour chacun, **à quoi il sert**, s'il est **obligatoire**, **la
place qu'il prend**, **où il se trouve**, et s'il vaut mieux **réutiliser** une version déjà installée sur votre
machine ou laisser Madalean installer **sa propre copie**.

Un principe vaut pour tous : Madalean installe ses composants dans **son propre dossier**,
`~/.local/share/madalean` (appelé ci-dessous « le dossier de Madalean »). Il ne modifie jamais les programmes de
votre système, ne lance jamais `sudo` ni le gestionnaire de paquets de votre distribution. Quand il réutilise un
programme déjà installé, c'est **en lecture seule**.

## Vue d'ensemble

| Composant | Sert à | Obligatoire | Place | Où |
|---|---|---|---|---|
| [Lean, elan, espaces Mathlib](#lean-elan-et-les-espaces-mathlib) | vérifier chaque preuve | oui | ≈ 5 Go par espace construit | dossier de Madalean |
| [SageMath](#sagemath) | l'écran « Calcul », les expériences | non | ≈ 5 Go (copie de Madalean) | dossier de Madalean, ou celui du système |
| [JupyterLab](#jupyterlab) | les carnets | oui (inclus) | compris dans l'environnement principal | dossier de Madalean |
| [Modèles locaux](#modeles-locaux) | travailler sans Internet | non | ≈ 5 Go par modèle | `~/models` |
| [LaTeX](#latex) | l'export PDF | oui (inclus) | ≈ 50 Mo pour le paquet TeX | dossier de Madalean, ou TeX Live du système |
| [Python](#python) | faire tourner Madalean | oui (inclus) | compris dans l'environnement principal | dossier de Madalean |
| [Tailscale](#tailscale) | joindre l'hôte depuis vos appareils | oui (inclus) | ≈ 25 Mo | dossier de Madalean |
| [Ollama](#ollama) | — (facultatif, déjà chez vous) | non | — | celui du système |
| [bubblewrap](#bubblewrap-le-bac-a-sable) | isoler compilations et calculs | conseillé | < 1 Mo | paquet du système |

L'environnement principal (Python, JupyterLab, tectonic, poppler, git…) occupe ≈ 1,3 Go une fois installé.

## Réparer, installer plus tard, retirer

**Dans l'application.** « Réglages › Système », partie « État de santé », vérifie chaque composant (espaces Lean,
serveur de modèles local, modèles, LaTeX, polices, Jupyter, SageMath, bac à sable, disque). Une ligne en problème
porte un bouton « Réparer » quand une réparation existe ; « Revérifier » relance le contrôle. Les réparations se
lancent depuis l'ordinateur hôte. « Réglages › Mises à jour », partie « Composants suivis », montre la version
installée de Lean, Mathlib, SageMath et LaTeX, et la partie « Composants du système » les programmes que vous
installez vous-même (comme bubblewrap), avec la commande exacte et le bouton « Ouvrir un terminal avec la commande ».

L'étape « Outils » de l'assistant [« Premiers pas »](first-config.md#lassistant-premiers-pas) (menu du logo ›
« Premiers pas ») liste les mêmes composants, chacun avec son état (installé, installé à la première utilisation,
absent, nouvelle version prête) et un bouton « Installer », « Installer maintenant » ou « Mettre à jour » qui montre
l'étape et le pourcentage pendant l'installation.

**En terminal**, sur l'hôte, le même outil que celui qu'utilise `install.sh` :

```bash
cd ~/.local/share/madalean/current
~/.local/share/madalean/env/bin/python -m madalean.deps health           # état de chaque composant
~/.local/share/madalean/env/bin/python -m madalean.deps install sage     # installer ou réparer un composant
~/.local/share/madalean/env/bin/python -m madalean.deps list             # composants connus, versions
```

Les noms de composants sont `micromamba`, `env` (l'environnement principal), `sage`, `fonts`, `tex-bundle`, `elan`,
`llama.cpp` et `madalean-net`. `rollback <composant>` revient à la version précédente d'un composant.
Relancer `./install.sh` répare aussi tout ce qui manque, sans refaire ce qui est en ordre.

**Retirer** un composant obligatoire n'a pas de sens ; tout disparaît avec la [désinstallation](install.md#desinstaller).
Les composants facultatifs se retirent comme indiqué dans leur partie.

## Lean, elan et les espaces Mathlib

**À quoi ça sert.** Lean est le vérificateur de preuves : c'est lui qui tranche, rien n'est déclaré prouvé sans son
accord. Mathlib est la grande bibliothèque de mathématiques écrite en Lean. Un **espace de travail** (ou espace Lean)
est une version de Lean accompagnée d'une Mathlib déjà compilée, prête à l'emploi. **elan** est le petit programme
qui installe et choisit les versions de Lean.

**Obligatoire** : oui.

**Les espaces.**

| Espace | Contenu | Rôle |
|---|---|---|
| « Lean actuel » (`lean-current`) | une version récente de Lean (v4.34.1 à l'écriture de cette page) et la Mathlib correspondante | l'espace par défaut, suivi par les mises à jour |
| « Prouveur » (`lean-prover49`) | Lean 4.9 et la Mathlib de l'époque | celle sur laquelle les modèles Goedel ont été entraînés ; jamais mis à jour |

**Place** : ≈ 5 Go par espace construit ; elan lui-même pèse ≈ 5 Mo.

**Où** : `~/.local/share/madalean/workspaces/` et `~/.local/share/madalean/elan/`.

**Réutiliser ou non.** Si des espaces Lean sont déjà construits sur la machine (par exemple ceux de Lean AI
Station 1.x), `install.sh` les **reprend par liens physiques** : les fichiers ne sont pas copiés, aucune place en
plus. Les versions de Lean déjà présentes dans votre `~/.elan` sont lues pour cet import, **sans jamais être
modifiées**. C'est la solution conseillée quand elle est possible. Sinon, `./install.sh --build-workspace`
construit l'espace « Lean actuel » (≈ 5 Go, réseau nécessaire, comptez de longues minutes). L'espace « Prouveur »
n'est pas construit par le script : il est repris s'il existe.

**Installer plus tard, réparer** : « Réglages › Espaces Lean » donne l'état de chaque espace ; relancez
`./install.sh --build-workspace` si aucun n'est installé. Les nouvelles versions de Lean et de Mathlib s'installent
depuis « Réglages › Mises à jour » (voir [Mises à jour](updates.md)).

## SageMath

**À quoi ça sert.** SageMath est un logiciel libre de calcul mathématique (algèbre, théorie des nombres,
combinatoire, graphiques…). Madalean l'utilise dans l'écran « Calcul », pour les expériences de l'atelier de
conjectures et pour les exemples et figures d'un article. Voir [Calcul](calcul.md).

**Obligatoire** : non. Sans SageMath, les carnets Python fonctionnent et le reste de Madalean aussi.

**Deux possibilités.**

| | Copie de Madalean | SageMath de votre système |
|---|---|---|
| Version | SageMath 10.10 | la vôtre, **10.0 ou plus récente** |
| Place | ≈ 1,4 Go à télécharger, ≈ 5 Go sur le disque | aucune en plus |
| Mise à jour | par Madalean (« Composants suivis ») | par votre distribution |
| Condition | aucune | le noyau Jupyter `sagemath` doit être installé (par exemple dans `/usr/share/jupyter/kernels/sagemath`) |

**Ce qui est conseillé.** Si votre système a déjà un SageMath compatible (version ≥ 10.0 **et** son noyau Jupyter
`sagemath`), réutilisez-le : vous économisez 5 Go et votre distribution le tient à jour. Sinon, laissez Madalean
installer sa propre copie. Dans les deux cas, le calcul tourne dans **le même bac à sable** : sans réseau, sans accès
à votre dossier personnel (voir [bubblewrap](#bubblewrap-le-bac-a-sable)).

**Le réglage `sage_source`** fixe ce choix :

| Valeur | Effet |
|---|---|
| `auto` (défaut) | la copie de Madalean si elle est installée, sinon celui du système |
| `own` | toujours la copie de Madalean |
| `system` | toujours celui du système |

Il est écrit à l'installation (`--sage`, ou le choix fait dans l'installateur graphique) et se change ensuite dans
l'application, dans l'étape « Outils » de l'assistant « Premiers pas » (menu du logo, ou « Réglages », lien
« Premiers pas »), qui indique le choix conseillé avec sa raison et la copie utilisée en ce moment. « Celui du
système » n'y est proposé que si un SageMath compatible est présent.

**Installer plus tard.** Par défaut (`--sage later`), la copie de Madalean s'installe **à la première utilisation** :
dans un carnet SageMath de l'écran « Calcul », bouton « Installer SageMath », sur l'ordinateur hôte ; l'écran
affiche l'étape et le pourcentage. Pour l'installer tout de suite : `./install.sh --sage now`, ou
`python -m madalean.deps install sage` (voir [plus haut](#reparer-installer-plus-tard-retirer)).

**Retirer la copie de Madalean** : arrêtez Madalean (`systemctl --user stop madalean`), supprimez
`~/.local/share/madalean/envs/sage` et les dossiers `~/.local/share/madalean/envs/sage-…`, puis redémarrez.
L'application n'a pas de bouton pour cela. Ensuite, SageMath apparaît de nouveau comme « installé à la première
utilisation », et avec `sage_source` sur `auto` le SageMath du système est utilisé s'il existe.

## JupyterLab

**À quoi ça sert.** JupyterLab est l'environnement de carnets (« notebooks ») : des cellules de code et leurs
résultats. Madalean l'utilise pour les carnets de l'écran « Calcul » et pour l'écran « Carnet » (voir
[Jupyter et Sage](jupyter.md)).

**Obligatoire** : oui, il fait partie de l'environnement principal de Madalean ; il n'y a rien à choisir.

**Où** : dans l'environnement principal, `~/.local/share/madalean/env/`. Les carnets eux-mêmes sont rangés dans
`~/Documents/Madalean/notebooks/`.

**Accès depuis vos autres appareils** : désactivé par défaut. Le réglage `remote_jupyter` (« Réglages › Carnet et
accès » › « Ouvrir le carnet aux appareils reliés », sur l'hôte seulement) l'ouvre aux appareils reliés. Un carnet
exécute du code sur l'hôte : ne l'activez que si vous faites confiance à vos appareils.

**Réparer** : ligne « Jupyter » de l'« État de santé », bouton « Réparer ».

## Modèles locaux

**À quoi ça sert.** Des modèles d'IA qui tournent **sur l'ordinateur hôte**, sans rien envoyer sur Internet. Ils
servent en mode *Local* (rien ne quitte la machine) et, en mode *Automatique*, quand Internet manque. Voir
[Modèles et clés](models-keys.md).

**Obligatoire** : non. Sans modèle local, Madalean utilise les modèles en ligne (gratuits, ou avec vos clés).

**Le moteur, llama.cpp.** C'est le programme qui fait tourner les modèles. `install.sh` choisit la version adaptée
à votre machine d'après le pilote NVIDIA : une version pour la carte graphique (CUDA) si le pilote convient, sinon
une version pour le processeur (`--cpu` / `--gpu` forcent le choix). Il est installé dans le dossier de Madalean
(≈ 25 Mo pour le processeur, ≈ 650 Mo avec les bibliothèques CUDA), même si vous ne prenez aucun modèle.

**Les trois modèles** (fichiers GGUF, quantification Q4_K_M), dans `~/models` :

| Fichier | Rôle | Taille |
|---|---|---|
| `Goedel-Prover-V2-8B.Q4_K_M.gguf` | le **prouveur** : écrit les preuves Lean | ≈ 5 Go |
| `Goedel-Formalizer-V2-8B.Q4_K_M.gguf` | le **traducteur** : met les énoncés en Lean | ≈ 5 Go |
| `Qwen3-8B-Q4_K_M.gguf` | l'**explicateur** : explications et preuves rédigées | ≈ 5 Go |

**Quand cela vaut la peine.** Un modèle local n'est utile que s'il tourne sur une carte graphique assez grande. Le
plan recommandé suit cette règle :

| Votre machine | Conseil |
|---|---|
| carte NVIDIA avec 10 Go de mémoire graphique ou plus, et 16 Go de mémoire vive ou plus | les trois modèles (`--models all`) |
| carte NVIDIA avec 8 à 10 Go de mémoire graphique | le prouveur seulement (`--models prover`) |
| moins de 8 Go, ou pas de carte NVIDIA | **pas de modèle local conseillé** (`--models none`) |

Sans carte adaptée, un modèle local tourne sur le processeur : une seule réponse peut prendre de nombreuses
minutes, alors que les modèles en ligne sont à la fois plus rapides et meilleurs. Pour donner un ordre de grandeur,
le prouveur est réglé pour un contexte de 24 000 jetons, ce qui occupe environ 7 Go de mémoire graphique.

**Réutiliser ou non.** Des fichiers déjà présents dans `~/models` (avec leur empreinte `.sha256`) sont réutilisés et
jamais déplacés.

**Ajouter un modèle plus tard** : relancez `./install.sh --models all` (seuls les fichiers manquants sont
téléchargés), ou téléchargez un modèle précis depuis le dossier des sources :

```bash
./scripts/download_model.sh Q4_K_M formalizer explainer   # prouveur, traducteur, explicateur
```

(n'importe quel sous-ensemble ; `Q4_K_M` désigne le prouveur). Chaque fichier est vérifié par son empreinte.

**Libérer la carte graphique.** Le modèle local est arrêté après 10 minutes sans travail, pour rendre la mémoire
graphique aux autres programmes (réglage `local_idle_unload_minutes`, 0 = jamais ; voir
[Première configuration](first-config.md#comportements-automatiques-et-manuels)).

**Retirer un modèle** : supprimez son fichier (et le `.sha256` qui l'accompagne) dans `~/models`. Madalean cesse de
le proposer ; la désinstallation, elle, garde `~/models`.

## LaTeX

**À quoi ça sert.** LaTeX compose les documents PDF : export d'un dossier, d'une preuve rédigée, d'un article.

**Obligatoire** : oui, et inclus. Sans LaTeX, Madalean ouvre une version HTML à imprimer depuis le navigateur.

**Deux possibilités.**

| | LaTeX de Madalean (conseillé) | TeX Live de votre système |
|---|---|---|
| Programme | **tectonic**, dans l'environnement principal | `xelatex` ou `lualatex`, avec `latexmk` |
| Paquets LaTeX | un paquet TeX figé (version v33, ≈ 50 Mo), téléchargé une fois à l'installation | tous ceux de votre installation |
| Réseau | aucun après l'installation | aucun |
| Bac à sable | oui | oui |

**Ce qui est conseillé.** Le LaTeX de Madalean : il donne **le même résultat sur toutes les machines** (le paquet TeX
est figé et vérifié), fonctionne **hors ligne** et tourne dans le bac à sable. Un TeX Live déjà installé est de toute
façon utilisé **en secours** si tectonic échoue. Choisissez de l'utiliser **en premier** si vous avez besoin de
paquets LaTeX absents du paquet TeX de Madalean ; il faut alors TeX Live 2022 ou plus récent, avec `fontspec`.

**Le réglage `tex_engine`** :

| Valeur | Effet |
|---|---|
| `auto` (défaut) | tectonic d'abord, TeX Live du système en secours |
| `tectonic` | tectonic seulement |
| `system` | TeX Live du système d'abord |

Il est écrit à l'installation (`--tex own` ou `--tex system`, ou le choix fait dans l'installateur graphique), et se
change dans l'étape « Outils » de l'assistant « Premiers pas ». Avec `system`, l'export essaie XeLaTeX puis
LuaLaTeX du système, et tectonic en dernier ; avec `tectonic`, seulement tectonic (ce choix est refusé tant que le
tectonic de Madalean n'est pas installé).

**Réparer** : ligne « LaTeX (export PDF) » de l'« État de santé », bouton « Réparer », ou
`python -m madalean.deps install tex-bundle`. Les polices utilisées dans les PDF (DejaVu Sans Mono, Noto Sans Math)
sont installées avec Madalean et vérifiées au même endroit.

## Python

Madalean a **son propre Python** (3.13), dans son environnement principal (`~/.local/share/madalean/env/`). Le
Python de votre système n'est **jamais modifié**, et le serveur ne s'en sert pas. Seul le lanceur des noyaux
d'expériences peut le trouver sur votre système, s'il y en a un, pour démarrer un noyau Python dans le bac à sable.
Rien à choisir, rien à installer.

## Tailscale

**À quoi ça sert.** Tailscale crée un réseau privé chiffré entre vos appareils (votre « tailnet »). Madalean s'en
sert pour que votre téléphone, votre tablette ou un autre PC joignent l'ordinateur hôte, sans rien ouvrir sur
Internet.

**Inclus** : Madalean fournit **son propre nœud Tailscale**, `madalean-net` (≈ 25 Mo, dans le dossier de Madalean).
Il apparaît sous le nom « madalean » dans votre tailnet. Il ne demande ni `sudo` ni service système.

**Un Tailscale déjà installé** sur l'hôte peut rester en place : aucun conflit, les deux coexistent.

**Configurer** : il faut approuver le nœud une fois dans votre compte Tailscale, puis relier chaque appareil. Voir
[Relier un appareil](pairing.md) et [Tailscale](tailscale.md).

## Ollama

Ollama est un autre programme qui fait tourner des modèles en local. Madalean **ne l'installe pas** et n'en a pas
besoin. S'il est déjà installé et en marche sur l'hôte, ses modèles apparaissent parmi les modèles locaux disponibles
et peuvent être choisis ; les deux programmes coexistent sans conflit.

**Partage de la carte graphique avec Ollama** (« Réglages › Modèles », partie « Modèles locaux » ; activé par
défaut, utile seulement quand Ollama est lancé). Les deux programmes ne tiennent pas ensemble sur une carte de 8 Go.
Quand le modèle local de Madalean ne tient pas, Madalean demande à Ollama de décharger ses modèles (la demande prévue
par Ollama : rien n'est arrêté, Ollama les recharge seul à sa prochaine demande, en 3 secondes environ), charge le
sien, puis rend la carte après `local_idle_unload_minutes` sans travail. **Jamais pendant qu'Ollama répond à une autre
application** : Madalean attend qu'il ait fini (30 s au plus, réglable), puis, selon le réglage, charge son modèle
avec la mémoire libre (en partie sur le processeur, plus lent) ou passe au modèle suivant (en ligne). Le panneau
d'état (bouton en haut à droite) et « Réglages › Système › État de santé » disent en clair qui tient la carte.

## bubblewrap, le bac à sable

**À quoi ça sert.** bubblewrap est un petit outil de Linux qui enferme un programme dans un **bac à sable** : sans
réseau, sans accès à votre dossier personnel, avec Lean et Mathlib en lecture seule. Madalean l'utilise pour chaque
compilation Lean, chaque compilation LaTeX et chaque calcul (SageMath, Python). C'est une protection importante, car
le code compilé ou exécuté peut venir d'un modèle d'IA. Voir [Sécurité](security.md).

**Obligatoire** : non, mais **fortement conseillé**. Sans bubblewrap, compilations et calculs tournent sans cette
isolation ; « Réglages › Système » indique si le bac à sable est actif.

**Installer** : c'est un paquet de votre distribution, que Madalean ne peut pas installer à votre place (il faudrait
`sudo`). Lancez vous-même la commande correspondant à votre système :

| Distribution | Commande |
|---|---|
| Arch Linux, Manjaro | `sudo pacman -S bubblewrap` |
| Debian, Ubuntu, Linux Mint | `sudo apt install bubblewrap` |
| Fedora | `sudo dnf install bubblewrap` |
| openSUSE | `sudo zypper install bubblewrap` |

Puis « Revérifier » dans « Réglages › Système » : la ligne du bac à sable doit passer en ordre.
