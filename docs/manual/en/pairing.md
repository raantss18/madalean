---
id: pairing
title: Link a phone, a tablet or another PC
order: 30
section: start
audience: all
summary: Step by step, linking a device to the host computer with a 6-digit code, and unlinking it.
---

# Link a phone, a tablet or another PC

A linked device shows the same interface as the host computer and stays synchronised with it: what you start on the
phone appears on the PC, and vice versa. All computation stays on the host.

Three things are needed:

1. the host computer switched on, Madalean running;
2. the host and the device on **your Tailscale network** (see [Tailscale](tailscale.md));
3. a **6-digit code** shown by the host.

On the host computer itself, no code is needed.

## Step 1 — Publish Madalean on your Tailscale network (once)

On the host, in the Madalean folder:

```bash
scripts/tailscale_setup.sh
```

The script adds **a single** rule, `tailscale serve --bg --https=10500 http://127.0.0.1:11501`, and prints the
host's address as seen from other devices, of the form `https://pc-name.tailXXXX.ts.net:10500`. It touches no other
`tailscale serve` rule of the machine and never enables *Funnel* (opening to the Internet).
`scripts/tailscale_setup.sh --print` shows the commands without changing anything; `--remove` removes the rule.

If the script reports that HTTPS is not enabled, follow [Tailscale › Enable HTTPS](tailscale.md#enable-https).
<!-- verify after integration: tailscale_setup.sh applied for real on the host; printed URL format -->

## Step 2 — Show a code on the host

On the host computer: “Settings › Devices › Add a device”. A 6-digit code appears, valid for **5 minutes**, usable
**once**, with a QR code for the Android app.

![Settings › Devices: code and QR code](../img/devices-add.png)

Check the field “Address of this computer as seen from other devices”: it is the address printed by the script in
step 1, without `https://` (for example `nitro.tail1234.ts.net:10500`). It is used to build the QR code.

## Step 3 — On the device

### Android phone or tablet

1. Install the **Tailscale** app (Play Store) and sign in with **the same account** as on the host.
2. Install the **Madalean** app from the [install page](site:install) (APK file; Android asks you to allow
   installation from your browser, once).
3. Scan the host's QR code with the camera: the app opens with the address and the code already filled in.
   Otherwise, type the address and the code by hand.
4. Give the device a name (“Marie's Pixel”) and tap “Link”.

![Linking screen on a phone](../img/pair-phone.png)

### iPhone, iPad, or any device with a browser

There is no iOS app. Install Tailscale (App Store), then open the address `https://pc-name.tailXXXX.ts.net:10500` in
the browser. The linking page asks for the code and a device name. Tip: “Share › Add to Home Screen” gives an icon
that opens Madalean directly.
<!-- verify after integration: browser pairing over the tailnet from Safari; cookie persists -->

### Another Linux computer

Install Tailscale, then either a browser (as above) or the **Madalean** desktop app (AppImage,
[install page](site:install)), which keeps the token in the system keyring and reconnects by itself.

## What happens when linking

The device sends the code; the host gives it a secret **token** (256 bits) that identifies it from then on. The host
keeps only a fingerprint of this token, never the token itself. Five wrong codes in a row lock linking for 10
minutes. Details: [Security](security.md).

## Unlinking a device

- From the host: “Settings › Devices”, the “Unlink” button next to the device. Access is cut **immediately**,
  including for a page that is already open.
- From the device itself: “Settings › Devices › Unlink this device”.

Unlinking a lost phone is the first thing to do; your Tailscale account also lets you remove the device from the
private network.

## If it does not work

| Message | What to do |
|---|---|
| “Wrong code” | Type again the 6 digits shown on the host. |
| “This code has expired” | “New code” on the host (valid for 5 minutes). |
| “Too many tries: linking is locked for N min” | Wait, then ask for a new code. |
| The address does not answer | Is Tailscale connected on both devices? See [Troubleshooting](troubleshooting.md#the-device-cannot-reach-the-host). |
