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
| Système | Linux (Arch/EndeavourOS, Fedora, Debian, Ubuntu, openSUSE) | Arch ou Fedora récents |
| Carte graphique | aucune (modèles locaux sur le processeur, très lents) | NVIDIA ≥ 8 Go de mémoire |
| Mémoire vive | 16 Go | 32 Go |
| Disque | ≈ 40 Go libres | SSD |

Sans carte NVIDIA, tout fonctionne, mais une preuve par un modèle local peut prendre plusieurs dizaines de minutes.
Les modèles en ligne (gratuits ou avec une clé) ne dépendent pas de votre carte graphique.

Le pilote NVIDIA et le CUDA Toolkit (`nvcc`) sont à installer **vous-même** avant : le script ne touche jamais aux
pilotes.

| Distribution | Pilote + CUDA |
|---|---|
| Arch / EndeavourOS | `sudo pacman -S nvidia-open nvidia-utils cuda` |
| Fedora | pilote par RPM Fusion (`akmod-nvidia`, `xorg-x11-drv-nvidia-cuda`), CUDA par le dépôt NVIDIA |
| Debian / Ubuntu | `sudo apt install nvidia-driver-XXX nvidia-cuda-toolkit` (ou le dépôt NVIDIA) |
| openSUSE | dépôt NVIDIA |

## Installer

```bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh --install-deps
```

`--install-deps` installe une fois les outils de compilation avec `sudo` (vous tapez votre mot de passe). Le script
est relançable sans risque : il reprend où il s'était arrêté et ne refait pas ce qui est déjà fait.

Il installe, au niveau de l'utilisateur :

- le gestionnaire de versions Lean **elan** et deux **espaces de travail** Lean : « Prouveur » (Lean 4.9 et la
  Mathlib sur laquelle les modèles Goedel ont été entraînés ; compilation de Mathlib depuis les sources, ≈ 1 h 30 une
  seule fois) et « Lean récent » (dernière Mathlib) ;
- le moteur **llama.cpp** compilé pour votre carte (version épinglée) ;
- trois modèles locaux (≈ 5 Go chacun, empreintes SHA-256 vérifiées) : Goedel-Prover-V2-8B (preuves),
  Goedel-Formalizer-V2-8B (traduction en Lean), Qwen3-8B (explications) ;
- le serveur Madalean et son service systemd utilisateur `madalean.service`.

Options utiles (`./install.sh --help`) :

| Option | Effet |
|---|---|
| `--backend cpu` | pas de carte graphique : moteur pour le processeur |
| `--no-models` | ne télécharge pas les modèles locaux (≈ 15 Go) : seuls les modèles en ligne serviront |
| `--no-prover49` | saute l'espace Lean 4.9 (la longue compilation de Mathlib) |
| `--no-current` | saute l'espace « Lean récent » |
| `--no-service` | n'installe pas le service systemd |

## Où sont les choses

| Quoi | Où |
|---|---|
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

Ouvrez ensuite l'interface sur l'hôte : `http://127.0.0.1:11500`, ou l'application de bureau Madalean (AppImage),
qui reconnaît l'hôte toute seule. Suite : [Premier démarrage](first-run.md).
<!-- verify after integration: final repository name raantss18/madalean, install.sh installs the 2.0 server and unit, menu entry name -->

## Désinstaller

`./uninstall.sh` liste exactement ce qui sera supprimé avant de le faire. Vos dossiers ne sont pas supprimés sans
votre accord.
<!-- verify after integration: uninstall.sh covers ~/.config/madalean and the systemd unit in 2.0 -->
