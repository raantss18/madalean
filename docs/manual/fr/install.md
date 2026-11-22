---
id: install
title: Installer sur l'ordinateur hôte
order: 10
section: start
audience: all
summary: Matériel conseillé, installation par install.sh, ce qui est installé et où.
---

# Installer sur l'ordinateur hôte

L'**ordinateur hôte** est la machine qui fait tourner Madalean : le serveur, Lean, les modèles locaux et vos
données. Les autres appareils n'installent qu'une application légère (ou rien du tout : un navigateur suffit), voir
[Relier un appareil](pairing.md).

## Matériel et système

| | Minimum | Conseillé |
|---|---|---|
| Système | Linux 64 bits (x86_64), n'importe quelle distribution récente | — |
| Carte graphique | aucune (modèles locaux sur le processeur, très lents) | NVIDIA ≥ 8 Go de mémoire |
| Mémoire vive | 16 Go | 32 Go |
| Disque | ≈ 40 Go libres | SSD |

Sans carte NVIDIA, tout fonctionne, mais une preuve par un modèle local peut prendre plusieurs dizaines de minutes.
Les modèles en ligne (gratuits ou avec une clé) ne dépendent pas de votre carte graphique.

Avec une carte NVIDIA, seul le **pilote NVIDIA** doit être installé (par vous, avec les outils de votre
distribution) : le script ne touche jamais aux pilotes et n'a pas besoin du CUDA Toolkit. Si le pilote est trop
ancien, le script installe le moteur pour le processeur.

## Installer

```bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh
```

Pas de `sudo`, pas de paquet système : tout va dans un seul dossier, `~/.local/share/madalean`. Il suffit de
`bash`, `curl` et `tar`. Le script est relançable sans risque : il reprend où il s'était arrêté et ne refait pas ce
qui est déjà fait. Chaque téléchargement est vérifié par son empreinte SHA-256.

Il installe :

- Madalean lui-même (serveur et interface) ;
- un environnement Python avec JupyterLab, le moteur LaTeX et ses polices (l'export PDF marche ensuite sans
  réseau) ;
- le gestionnaire de versions Lean **elan** et les **espaces de travail** Lean (voir ci-dessous) ;
- le moteur **llama.cpp** (version épinglée, pour votre carte ou pour le processeur) ;
- le nœud Tailscale intégré de Madalean, pour joindre l'hôte depuis vos autres appareils (voir
  [Tailscale](tailscale.md)) ;
- trois modèles locaux (≈ 5 Go chacun) dans `~/models` : Goedel-Prover-V2-8B (preuves), Goedel-Formalizer-V2-8B
  (traduction en Lean), Qwen3-8B (explications). Des modèles déjà présents dans `~/models` sont réutilisés ;
- le service systemd utilisateur `madalean.service` et l'entrée « Madalean » du menu des applications.

SageMath (pour l'écran « Calcul ») n'est pas installé d'avance : il s'installe à la demande, voir
[Calcul](calcul.md).

**Espaces Lean.** Le script reprend les espaces Lean déjà construits sur la machine (par exemple ceux de Lean AI
Station 1.x), sans prendre de place en plus. S'il n'en trouve aucun, relancez-le avec `--build-workspace` : il
construit l'espace « Lean actuel » (dernière Mathlib, ≈ 5 Go, réseau nécessaire). L'espace « Prouveur » (Lean 4.9,
la Mathlib sur laquelle les modèles Goedel ont été entraînés) n'est pas construit par le script : il est repris s'il
existe déjà.

Options utiles (`./install.sh --help`) :

| Option | Effet |
|---|---|
| `--cpu` | moteur des modèles pour le processeur (pas de carte graphique) |
| `--no-models` | ne télécharge pas les modèles locaux (≈ 15 Go) : seuls les modèles en ligne serviront |
| `--no-workspaces` | n'installe pas d'espace Lean |
| `--build-workspace` | construit l'espace « Lean actuel » s'il n'en existe aucun |
| `--no-systemd` | n'installe pas le service systemd |
| `--no-desktop` | n'ajoute pas d'entrée au menu des applications |
| `--offline DOSSIER` | installe sans réseau, depuis un export fait avec `./export_offline.sh` |

## Où sont les choses

| Quoi | Où |
|---|---|
| Madalean et tous ses composants | `~/.local/share/madalean/` |
| Réglages, projets, dossiers, appareils reliés | `~/.config/madalean/` |
| Index de recherche, caches | `~/.cache/madalean/` |
| Modèles locaux | `~/models/` |
| Carnets Jupyter | `~/Documents/Madalean/notebooks/` |

Au premier démarrage, si vous aviez Lean AI Station 1.x, le serveur **copie** (sans jamais les déplacer) vos
réglages, dossiers et bibliothèque depuis `~/.config/lean-ai-station/`.

## Démarrer et arrêter

Le service démarre avec votre session. En terminal, si besoin :

```bash
systemctl --user status madalean      # état
systemctl --user restart madalean     # redémarrer
journalctl --user -u madalean -e      # journal
```

Ouvrez ensuite l'interface sur l'hôte : « Madalean » dans le menu des applications, ou `http://127.0.0.1:11500`
dans un navigateur. Suite : [Premier démarrage](first-run.md).

## Désinstaller

`./uninstall.sh` liste exactement ce qui sera supprimé et demande confirmation avant de le faire. Il supprime
`~/.local/share/madalean`, `~/.cache/madalean`, le service systemd et l'entrée du menu. Il **garde** vos réglages,
projets et dossiers (`~/.config/madalean`), vos modèles (`~/models`) et vos carnets (`~/Documents/Madalean`).
`./uninstall.sh --purge` propose en plus, avec une question pour chacun, de supprimer `~/.config/madalean` et
`~/models`.
