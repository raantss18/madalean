---
id: tailscale
title: Tailscale, le réseau privé de vos appareils
order: 40
section: start
audience: all
summary: Ce qu'est Tailscale, pourquoi Madalean l'utilise, comment l'installer, et ce qu'il ne fait pas.
---

# Tailscale, le réseau privé de vos appareils

## Ce que c'est

[Tailscale](https://tailscale.com/) relie **vos** appareils entre eux par des liaisons chiffrées (protocole
WireGuard), où qu'ils soient : même Wi-Fi, 4G, autre ville. L'ensemble forme un réseau privé, le *tailnet*. Chaque
appareil y reçoit un nom stable, par exemple `nitro.tail1234.ts.net`. Seuls les appareils connectés à **votre**
compte Tailscale font partie de ce réseau.

Madalean l'utilise pour une seule chose : que vos appareils joignent l'ordinateur hôte. Il ne se sert d'aucun
serveur de Madalean sur Internet (il n'y en a pas) et le site web de Madalean ne joue aucun rôle dans la
synchronisation.

## Ce que Madalean fait, et ne fait pas, avec Tailscale

- Il publie **un seul** port du serveur sur votre tailnet, en HTTPS : `https://<hôte>.<tailnet>.ts.net:10500`.
- Il n'active **jamais Funnel**, la fonction de Tailscale qui ouvrirait ce port à tout Internet.
- Il ne modifie aucune autre règle `tailscale serve` de la machine (d'autres logiciels peuvent en avoir).
- Être sur le tailnet **ne suffit pas** : chaque appareil doit en plus être relié par un code
  ([Relier un appareil](pairing.md)).

## Installer Tailscale

Sur l'ordinateur hôte (Linux) :

| Distribution | Commande |
|---|---|
| Arch / EndeavourOS | `sudo pacman -S tailscale` |
| Fedora, Debian, Ubuntu, openSUSE | voir <https://tailscale.com/download/linux> (dépôt officiel) |

puis :

```bash
sudo systemctl enable --now tailscaled
sudo tailscale up                       # ouvre une page de connexion à votre compte
sudo tailscale set --operator=$USER     # une fois : permet à Madalean de gérer sa règle sans sudo
```

Sur un téléphone ou une tablette : l'application Tailscale de l'App Store ou du Play Store, connectée au même compte.

Le compte Tailscale se crée avec un fournisseur d'identité (Google, Microsoft, GitHub, Apple…). L'offre
personnelle gratuite suffit pour un usage individuel.
<!-- verify after integration: Tailscale personal plan wording at release time -->

## Activer HTTPS

Les appareils joignent l'hôte en HTTPS, avec un certificat que Tailscale obtient pour le nom `*.ts.net`. Il faut, une
fois, dans la console d'administration Tailscale (page **DNS**) :

1. activer **MagicDNS** ;
2. activer **HTTPS Certificates**.

Ensuite `scripts/tailscale_setup.sh` (voir [Relier un appareil](pairing.md)) fonctionne. La première connexion
HTTPS peut prendre quelques secondes, le temps que le certificat soit émis.

## Sans Tailscale

Un réglage de l'ordinateur hôte permet d'écouter aussi sur le réseau local (port 11502, désactivé par défaut). Le
jeton d'appareil reste exigé, mais le trafic n'est alors **pas chiffré** par Madalean : à réserver à un réseau de
confiance. Ce réglage ne se change que depuis l'hôte et prend effet au redémarrage du serveur.
<!-- verify after integration: LAN listener toggle location in Réglages, plain HTTP on LAN -->
