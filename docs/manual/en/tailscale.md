---
id: tailscale
title: Tailscale, the private network of your devices
order: 40
section: start
audience: all
summary: What Tailscale is, why Madalean uses it, how to install it, and what it does not do.
---

# Tailscale, the private network of your devices

## What it is

[Tailscale](https://tailscale.com/) connects **your** devices to each other through encrypted links (WireGuard
protocol), wherever they are: same Wi-Fi, 4G, another city. Together they form a private network, the *tailnet*.
Each device gets a stable name there, for example `nitro.tail1234.ts.net`. Only the devices signed in to **your**
Tailscale account belong to this network.

Madalean uses it for one thing only: letting your devices reach the host computer. It uses no Madalean server on the
Internet (there is none), and the Madalean website plays no part in synchronisation.

## What Madalean does, and does not do, with Tailscale

- It publishes **one** server port on your tailnet, over HTTPS: `https://<host>.<tailnet>.ts.net:10500`.
- It **never enables Funnel**, the Tailscale feature that would open this port to the whole Internet.
- It changes no other `tailscale serve` rule of the machine (other software may have some).
- Being on the tailnet is **not enough**: each device must also be linked with a code
  ([Link a device](pairing.md)).

## Installing Tailscale

On the host computer (Linux):

| Distribution | Command |
|---|---|
| Arch / EndeavourOS | `sudo pacman -S tailscale` |
| Fedora, Debian, Ubuntu, openSUSE | see <https://tailscale.com/download/linux> (official repository) |

then:

```bash
sudo systemctl enable --now tailscaled
sudo tailscale up                       # opens a sign-in page for your account
sudo tailscale set --operator=$USER     # once: lets Madalean manage its rule without sudo
```

On a phone or tablet: the Tailscale app from the App Store or the Play Store, signed in to the same account.

The Tailscale account is created with an identity provider (Google, Microsoft, GitHub, Apple…). The free personal
plan is enough for individual use.
<!-- verify after integration: Tailscale personal plan wording at release time -->

## Enable HTTPS

Devices reach the host over HTTPS, with a certificate that Tailscale obtains for the `*.ts.net` name. Once, in the
Tailscale admin console (**DNS** page):

1. enable **MagicDNS**;
2. enable **HTTPS Certificates**.

After that, `scripts/tailscale_setup.sh` (see [Link a device](pairing.md)) works. The first HTTPS connection may take
a few seconds while the certificate is issued.

## Without Tailscale

A setting of the host computer also makes Madalean listen on the local network (port 11502, off by default). The
device token is still required, but the traffic is then **not encrypted** by Madalean: keep this for a trusted
network. This setting can only be changed from the host and takes effect when the server restarts.
<!-- verify after integration: LAN listener toggle location in Réglages, plain HTTP on LAN -->
