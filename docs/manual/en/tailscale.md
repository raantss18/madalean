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

- Madalean installs and runs **its own Tailscale node**. On your tailnet, the host appears as a separate machine,
  `madalean`, reachable over HTTPS at `https://madalean.<tailnet>.ts.net` (normal HTTPS port, no port number). This
  node stops with Madalean and sends no logs to Tailscale.
- The host needs neither the system's Tailscale nor `tailscale serve`. If there is one, Madalean does not touch it:
  both coexist.
- Madalean **never enables Funnel**, the Tailscale feature that would open access to the whole Internet.
- Being on the tailnet is **not enough**: each device must also be linked with a code ([Link a device](pairing.md)).

## Installing Tailscale

**On the host computer**, nothing to install: Madalean's node is installed by `./install.sh`. The first time, it must
be approved in your Tailscale account (see [Link a device › Step 1](pairing.md)).

**On a phone, a tablet or another computer**: the Tailscale app (App Store, Play Store, or Tailscale's site for a
computer), signed in to **the same account**.

The Tailscale account is created with an identity provider (Google, Microsoft, GitHub, Apple…). The plans and their
limits are described on Tailscale's site; personal use with a few devices usually fits in the free plan, but check
it on that site.

## Enable HTTPS

Devices reach the host over HTTPS, with a certificate that Tailscale issues for the name `madalean.<tailnet>.ts.net`.
Once, in Tailscale's admin console, turn on **MagicDNS** and **HTTPS certificates** (the exact menus are described in
Tailscale's help). The first HTTPS connection may take a few seconds, while the certificate is issued.

## Alternative: the system's Tailscale

If you prefer to use the Tailscale already installed on the host (the `tailscaled` service, signed in to your
account), the script `scripts/tailscale_setup.sh` publishes Madalean through it, on port 10500:
`https://pc-name.<tailnet>.ts.net:10500`. It adds **a single** `tailscale serve` rule, touches no other rule of the
machine and never enables Funnel. It needs `sudo tailscale set --operator=$USER` once to work without `sudo`.
`--status` shows the state, `--print` shows the commands without changing anything, `--remove` removes the rule. In
that case, type this address (without `https://`) in the “Address of this computer as seen from other devices”
field of “Settings › Devices”.

## Without Tailscale

“Settings › Notebook and access › Access from the local network (without Tailscale)” also makes Madalean listen on
the local network (“Local network port”, 11502 by default; off by default). Devices must still be linked with a code,
but traffic then goes over plain HTTP, **not encrypted**: keep this for a trusted network. This setting can only be
changed from the host and takes effect at the next start of Madalean.
