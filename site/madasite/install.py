"""Install page (fr/download.html, en/download.html) and the signed update channel directory (updates/).

The channel files are produced by the release process (scripts/sign_release.sh, session S-G): `stable.json` and
`stable.json.sig` (base64 Ed25519 signature of the exact bytes of stable.json). This module only CONSUMES them: it
verifies the signature against the public key embedded in madalean/update_checkers/selfupdate.py, copies both files
byte for byte, and refuses to publish a manifest whose signature does not verify."""
from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import layout
from .qr import qr_svg

E = html.escape
DER_PREFIX = bytes.fromhex("302a300506032b6570032100")
ARCH_ORDER = ["arm64-v8a", "armeabi-v7a", "x86_64", "universal"]

RELEASES = "https://github.com/raantss18/madalean/releases"
LATEST = RELEASES + "/latest"
LATEST_DL = LATEST + "/download/"
# Stable release asset names (DECISIONS D44, scripts/stage_release.sh). The site never shows a version: links go to
# releases/latest/download/<name>, which GitHub resolves to the newest release. Until a release publishes a name
# (v2.0.0 used versioned names), the link points to the latest release page instead, so nothing breaks.
ASSETS = {"installer": "Madalean-installer.run", "server": "madalean-server.tar.gz",
          "appimage": "Madalean-x86_64.AppImage", "apk": "Madalean-android.apk"}
APK_ABIS = ["arm64-v8a", "armeabi-v7a", "x86_64"]

T = {
    "fr": {
        "title": "Installer et télécharger",
        "lead": "Madalean s'installe sur <strong>un ordinateur hôte</strong> sous Linux, qui fait tout le calcul (le "
                "<em>serveur</em>). Vos autres appareils — téléphone, tablette, autre PC — sont des <em>clients</em> : "
                "ils se relient à l'hôte par votre réseau privé Tailscale. Les liens ci-dessous mènent toujours à la "
                "dernière version publiée.",
        "sample": "Aperçu avec des données d'exemple : ces fichiers n'existent pas.",
        "server": "Serveur — l'ordinateur hôte (Linux x86_64)",
        "server_text": "À installer une seule fois, sur l'ordinateur qui fera le calcul. Environ 6 Go sans modèle local, "
                       "25 Go avec ; une carte NVIDIA est utile mais pas nécessaire.",
        "run": "Installateur graphique", "recommended": "conseillé",
        "run_text": "Un seul fichier. Il vérifie sa propre intégrité, regarde ce qui est déjà sur votre machine, vous "
                    "propose le meilleur plan et installe tout en vous montrant l'avancement, dans votre navigateur.",
        "run_dl": "Télécharger l'installateur",
        "run_exec": "Un fichier téléchargé n'est pas exécutable. Deux façons de l'autoriser :",
        "run_gui": "dans le gestionnaire de fichiers : clic droit › <em>Propriétés</em> › <em>Permissions</em> › "
                   "cocher « Autoriser l'exécution du fichier comme un programme » (le libellé varie selon le bureau), "
                   "puis double-cliquer sur le fichier ;",
        "run_term": "ou dans un terminal, dans le dossier du fichier :",
        "src": "Depuis les sources, dans un terminal", "src_text": "Le même installateur, sans fenêtre : "
               "<code>install.sh</code> vérifie la machine, affiche un tableau et un plan conseillé, puis vous laisse "
               "accepter ou changer chaque élément. Avec <code>--yes</code>, il installe les choix par défaut sans "
               "question.",
        "src_tar": "Ou l'archive du serveur, sans git :",
        "guide": "Guide complet d'installation", "guide2": "Ce qu'installe Madalean, composant par composant",
        "guide3": "Première configuration (clés, modes, réglages)",
        "clients": "Clients — les appareils qui se connectent à l'hôte",
        "clients_text": "Rien à calculer sur ces appareils : ils affichent Madalean et parlent à l'hôte. Reliez-les avec "
                        "le code affiché par l'hôte (Réglages › Appareils).",
        "android": "Téléphone et tablette Android", "android_text": "Scannez le QR code avec l'appareil photo du "
                   "téléphone, ou touchez le lien depuis le téléphone. Android demande une fois d'autoriser "
                   "l'installation depuis le navigateur.",
        "apk_dl": "Télécharger l'application Android", "apk_small": "Fichiers plus petits, par type de processeur",
        "arch_help": {"arm64-v8a": "presque tous les téléphones et tablettes depuis 2017",
                      "armeabi-v7a": "appareils 32 bits plus anciens",
                      "x86_64": "émulateurs, quelques tablettes et Chromebooks"},
        "qr": "QR code du lien de l'application Android",
        "desktop": "Autre ordinateur Linux", "desktop_text": "Application de bureau (AppImage) : rendez le fichier "
                   "exécutable, puis lancez-le. Elle se relie à l'hôte comme un téléphone.",
        "appimage_dl": "Télécharger l'AppImage",
        "browser": "iPhone, iPad, Mac, Windows… : un navigateur suffit",
        "browser_text": "Pas d'application à installer : ouvrez l'adresse de l'hôte sur votre réseau Tailscale (par "
                        "exemple <code>https://madalean.tailXXXX.ts.net</code>) et reliez l'appareil avec le code "
                        "affiché par l'hôte.", "pairing": "Relier un appareil",
        "all": "Toutes les versions et leurs notes", "pending": "Le lien direct sera actif avec la prochaine version ; "
               "en attendant, il ouvre la page de la dernière version.",
        "verify": "Vérifier un téléchargement",
        "verify_text": "Chaque version publie <code>SHA256SUMS</code> (empreintes de tous les fichiers) et "
                       "<code>SHA256SUMS.sig</code>, sa signature Ed25519. La clé publique est inscrite dans Madalean, "
                       "qui refuse toute mise à jour mal signée ; l'installateur graphique vérifie lui-même son contenu. "
                       "Pour vérifier vous-même, dans le dossier des fichiers téléchargés :",
        "verify_key": "Clé publique de publication (Ed25519, hexadécimal)",
        "verify_apk": "Certificat de signature des APK (SHA-256) — vérifiable avec <code>apksigner verify --print-certs</code> :",
        "channel": "Canal de mise à jour", "channel_text": "Lu par Madalean et ses applications pour savoir qu'une "
                   "version existe :",
        "step_sums": "les empreintes correspondent (chaque ligne doit finir par « OK ») :",
        "step_sig": "la signature est valide (doit afficher « Signature Verified Successfully ») :",
    },
    "en": {
        "title": "Install and download",
        "lead": "Madalean is installed on <strong>one host computer</strong> running Linux, which does all the "
                "computing (the <em>server</em>). Your other devices — phone, tablet, another PC — are <em>clients</em>: "
                "they link to the host over your private Tailscale network. The links below always lead to the latest "
                "published version.",
        "sample": "Preview with sample data: these files do not exist.",
        "server": "Server — the host computer (Linux x86_64)",
        "server_text": "Installed once, on the computer that will do the computing. About 6 GB without a local model, "
                       "25 GB with; an NVIDIA card helps but is not required.",
        "run": "Graphical installer", "recommended": "recommended",
        "run_text": "One file. It checks its own integrity, looks at what is already on your machine, proposes the "
                    "best plan and installs everything while showing the progress, in your browser.",
        "run_dl": "Download the installer",
        "run_exec": "A downloaded file is not executable. Two ways to allow it:",
        "run_gui": "in the file manager: right-click › <em>Properties</em> › <em>Permissions</em> › tick “Allow "
                   "executing file as program” (the wording depends on the desktop), then double-click the file;",
        "run_term": "or in a terminal, in the file's folder:",
        "src": "From source, in a terminal", "src_text": "The same installer without a window: <code>install.sh</code> "
               "checks the machine, shows a table and a recommended plan, then lets you accept or change each item. "
               "With <code>--yes</code> it installs the defaults without any question.",
        "src_tar": "Or the server archive, without git:",
        "guide": "Complete installation guide", "guide2": "What Madalean installs, component by component",
        "guide3": "First configuration (keys, modes, settings)",
        "clients": "Clients — the devices that connect to the host",
        "clients_text": "Nothing is computed on these devices: they show Madalean and talk to the host. Link them with "
                        "the code shown by the host (Settings › Devices).",
        "android": "Android phone and tablet", "android_text": "Scan the QR code with the phone's camera, or tap the "
                   "link on the phone. Android asks once to allow installing from the browser.",
        "apk_dl": "Download the Android app", "apk_small": "Smaller files, per processor type",
        "arch_help": {"arm64-v8a": "almost every phone and tablet since 2017",
                      "armeabi-v7a": "older 32-bit devices",
                      "x86_64": "emulators, a few tablets and Chromebooks"},
        "qr": "QR code of the Android app link",
        "desktop": "Another Linux computer", "desktop_text": "Desktop app (AppImage): make the file executable, then "
                   "run it. It links to the host like a phone.",
        "appimage_dl": "Download the AppImage",
        "browser": "iPhone, iPad, Mac, Windows…: a browser is enough",
        "browser_text": "No app to install: open the host's address on your Tailscale network (for example "
                        "<code>https://madalean.tailXXXX.ts.net</code>) and link the device with the code shown by the "
                        "host.", "pairing": "Linking a device",
        "all": "Every version and its notes", "pending": "The direct link becomes active with the next release; "
               "meanwhile it opens the latest release page.",
        "verify": "Verify a download",
        "verify_text": "Each release publishes <code>SHA256SUMS</code> (hashes of every file) and "
                       "<code>SHA256SUMS.sig</code>, its Ed25519 signature. The public key is built into Madalean, which "
                       "refuses any badly signed update; the graphical installer checks its own content. To check "
                       "yourself, in the folder of the downloaded files:",
        "verify_key": "Release public key (Ed25519, hexadecimal)",
        "verify_apk": "APK signing certificate (SHA-256) — check with <code>apksigner verify --print-certs</code>:",
        "channel": "Update channel", "channel_text": "Read by Madalean and its apps to learn that a version exists:",
        "step_sums": "the hashes match (every line must end with “OK”):",
        "step_sig": "the signature is valid (must print “Signature Verified Successfully”):",
    },
}


def public_key(repo: Path) -> bytes:
    src = (repo / "madalean" / "update_checkers" / "selfupdate.py").read_text(encoding="utf-8")
    m = re.search(r'PUBLIC_KEY\s*=\s*bytes\.fromhex\("([0-9a-f]{64})"\)', src)
    if not m:
        raise RuntimeError("PUBLIC_KEY not found in madalean/update_checkers/selfupdate.py")
    return bytes.fromhex(m.group(1))


def pem(pub: bytes) -> str:
    b = base64.b64encode(DER_PREFIX + pub).decode()
    return f"-----BEGIN PUBLIC KEY-----\n{b}\n-----END PUBLIC KEY-----\n"


def verify_sig(pub: bytes, data: bytes, sig_b64: str) -> bool:
    """Ed25519 check with openssl (the same command the install page tells users to run)."""
    try:
        sig = base64.b64decode("".join(sig_b64.split()), validate=True)
    except ValueError:
        return False
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        (dp / "k.pem").write_text(pem(pub))
        (dp / "m").write_bytes(data)
        (dp / "s").write_bytes(sig)
        p = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(dp / "k.pem"), "-rawin",
                            "-in", str(dp / "m"), "-sigfile", str(dp / "s")], capture_output=True, text=True)
        return p.returncode == 0


def load_channel(src: Path, pub: bytes, problems: list[str]) -> tuple[dict | None, bytes | None, str | None]:
    j, s = src / "stable.json", src / "stable.json.sig"
    if not j.is_file():
        return None, None, None
    raw = j.read_bytes()
    if not s.is_file():
        raise RuntimeError(f"{j} has no {s.name}: refusing to publish an unsigned update manifest")
    sig = s.read_text()
    if not verify_sig(pub, raw, sig):
        raise RuntimeError(f"{s} does not verify against the embedded public key: refusing to publish")
    data = json.loads(raw)
    validate_channel(data, problems)
    return data, raw, sig


def validate_channel(d: dict, problems: list[str]) -> None:
    if d.get("schema") != "madalean-updates/1":
        problems.append("stable.json: schema must be 'madalean-updates/1'")
    for k in ("version", "date", "files"):
        if k not in d:
            problems.append(f"stable.json: missing {k}")
    for f in d.get("files", []):
        if not re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256", ""))):
            problems.append(f"stable.json: bad sha256 for {f.get('name')}")
        if not str(f.get("url", "")).startswith("https://github.com/"):
            problems.append(f"stable.json: file URL must be a GitHub release URL: {f.get('url')}")


def _size(n: int, lang: str) -> str:
    v = n / 1e6
    s = f"{v:.0f}" if v >= 10 else f"{v:.1f}"
    return (s.replace(".", ",") + " Mo") if lang == "fr" else (s + " MB")


def build(out: Path, repo: Path, channel_src: Path, problems: list[str], sample: Path | None = None) -> dict:
    pub = public_key(repo)
    data, raw, sig = load_channel(channel_src, pub, problems)
    is_sample = False
    if data is None and sample is not None:
        data = json.loads(sample.read_text())
        is_sample = True
    up = out / "updates"
    up.mkdir(parents=True, exist_ok=True)
    (up / "madalean-release.pub.pem").write_text(pem(pub))
    if raw is not None:
        (up / "stable.json").write_bytes(raw)
        (up / "stable.json.sig").write_text(sig)
    for lg in ("fr", "en"):
        (out / lg).mkdir(parents=True, exist_ok=True)
        (out / lg / "download.html").write_text(_page(lg, data, is_sample, pub), encoding="utf-8")
    (up / "index.html").write_text(_channel_page(raw is not None, pub), encoding="utf-8")
    return {"published_manifest": raw is not None, "sample": is_sample}


def asset_url(name: str, files: list[dict]) -> tuple[str, bool]:
    """(URL, direct): releases/latest/download/<name> when the published release has that stable name, else the
    latest release page. Never a versioned URL (the site shows no version)."""
    if any(f.get("name") == name for f in files):
        return LATEST_DL + name, True
    return LATEST, False


def _page(lg: str, d: dict | None, is_sample: bool, pub: bytes) -> str:
    t = T[lg]
    other = "en" if lg == "fr" else "fr"
    colon = " :" if lg == "fr" else ":"
    files = (d or {}).get("files", [])
    parts = [f'<main id="main" class="wide dl-page" tabindex="-1"><div class="prose"><h1>{t["title"]}</h1>'
             f'<p class="lead">{t["lead"]}</p></div>']
    if is_sample:
        parts.append(f'<p class="notice notice-warn" role="note"><strong>{E(t["sample"])}</strong></p>')
    pending = False

    def link(key: str, label: str, cls: str = "button") -> str:
        nonlocal pending
        url, direct = asset_url(ASSETS[key], files)
        pending = pending or not direct
        c = f' class="{cls}"' if cls else ""
        return f'<a{c} href="{E(url)}" rel="noopener noreferrer">{E(label)}</a>'

    # ---------------------------------------------------------------- server
    run = ASSETS["installer"]
    parts.append(f'<section class="dl-group" aria-labelledby="server"><h2 id="server">{t["server"]}</h2>'
                 f'<p>{t["server_text"]}</p><div class="dl-cards">'
                 f'<article class="dl-card dl-card-main" aria-labelledby="run"><p class="badge-rec">{t["recommended"]}</p>'
                 f'<h3 id="run">{t["run"]}</h3><p><code>{run}</code></p><p>{t["run_text"]}</p>'
                 f'<p>{link("installer", t["run_dl"])}</p>'
                 f'<p>{t["run_exec"]}</p><ol><li>{t["run_gui"]}</li><li>{t["run_term"]}'
                 f'<pre class="code" tabindex="0"><code>chmod +x {run}\n./{run}</code></pre></li></ol></article>'
                 f'<article class="dl-card" aria-labelledby="source"><h3 id="source">{t["src"]}</h3><p>{t["src_text"]}</p>'
                 '<pre class="code" tabindex="0"><code>git clone https://github.com/raantss18/madalean.git ~/madalean\n'
                 'cd ~/madalean\n./install.sh</code></pre>'
                 f'<p>{t["src_tar"]} {link("server", ASSETS["server"], "")}</p>'
                 f'<pre class="code" tabindex="0"><code>tar -xzf {ASSETS["server"]}\ncd madalean\n./install.sh</code></pre>'
                 f'</article></div>'
                 f'<ul class="dl-guides"><li><a href="install.html">{t["guide"]}</a></li>'
                 f'<li><a href="components.html">{t["guide2"]}</a></li>'
                 f'<li><a href="first-config.html">{t["guide3"]}</a></li></ul></section>')

    # ---------------------------------------------------------------- clients
    apk_url, apk_direct = asset_url(ASSETS["apk"], files)
    pending = pending or not apk_direct
    q = qr_svg(apk_url, t["qr"], 168)
    abis = [a for a in APK_ABIS if any(f.get("name") == f"Madalean-android-{a}.apk" for f in files)]
    parts.append(f'<section class="dl-group" aria-labelledby="clients"><h2 id="clients">{t["clients"]}</h2>'
                 f'<p>{t["clients_text"]}</p><div class="dl-cards">'
                 f'<article class="dl-card" aria-labelledby="android"><h3 id="android">{t["android"]}</h3>'
                 f'<p>{t["android_text"]}</p><ul class="dl-list"><li class="dl-item"><div class="dl-text">'
                 f'<p><code>{ASSETS["apk"]}</code></p>'
                 f'<p><a class="button" href="{E(apk_url)}" rel="noopener noreferrer">{E(t["apk_dl"])}</a></p></div>'
                 f'<div class="dl-qr">{q}</div></li></ul>')
    if abis:
        parts.append(f'<details><summary>{t["apk_small"]}</summary><ul>' + "".join(
            f'<li><a href="{E(LATEST_DL)}Madalean-android-{a}.apk" rel="noopener noreferrer">'
            f'Madalean-android-{a}.apk</a> — {E(t["arch_help"][a])}</li>' for a in abis) + "</ul></details>")
    parts.append("</article>")
    parts.append(f'<article class="dl-card" aria-labelledby="desktop"><h3 id="desktop">{t["desktop"]}</h3>'
                 f'<p>{t["desktop_text"]}</p><p><code>{ASSETS["appimage"]}</code></p>'
                 f'<p>{link("appimage", t["appimage_dl"])}</p>'
                 f'<pre class="code" tabindex="0"><code>chmod +x {ASSETS["appimage"]}\n./{ASSETS["appimage"]}</code></pre>'
                 f'</article>'
                 f'<article class="dl-card" aria-labelledby="browser"><h3 id="browser">{t["browser"]}</h3>'
                 f'<p>{t["browser_text"]}</p><p><a href="pairing.html">{E(t["pairing"])}</a></p>'
                 f'</article></div></section>')
    parts.append(f'<p class="dl-all"><a href="{RELEASES}" rel="noopener noreferrer">{t["all"]}</a>'
                 + (f' <span class="muted">— {t["pending"]}</span>' if pending else "") + "</p>")

    # ---------------------------------------------------------------- verification + channel
    sums = LATEST_DL + "SHA256SUMS"
    parts.append(f'<div class="prose"><section aria-labelledby="verify"><h2 id="verify">{t["verify"]}</h2>'
                 f'<p>{t["verify_text"]}</p>'
                 f'<ol><li>{t["step_sums"]}<pre class="code" tabindex="0"><code>sha256sum -c --ignore-missing SHA256SUMS</code></pre></li>'
                 f'<li>{t["step_sig"]}<pre class="code" tabindex="0"><code>base64 -d SHA256SUMS.sig &gt; SHA256SUMS.sig.bin\n'
                 'openssl pkeyutl -verify -pubin -inkey madalean-release.pub.pem -rawin \\\n'
                 '  -in SHA256SUMS -sigfile SHA256SUMS.sig.bin</code></pre></li></ol>'
                 f'<p><a href="../updates/madalean-release.pub.pem" download>madalean-release.pub.pem</a> · '
                 f'<a href="{E(sums)}" rel="noopener noreferrer">SHA256SUMS</a> · '
                 f'<a href="{E(sums)}.sig" rel="noopener noreferrer">SHA256SUMS.sig</a></p>'
                 f'<p>{t["verify_key"]}{colon}</p><p class="hash"><code>{pub.hex()}</code></p>')
    cert = (d or {}).get("apk_certificate_sha256", "0d43426ba9682f791707ee3233361c369c8ebec3f1209c6e000d7322936fc544")
    parts.append(f'<p>{t["verify_apk"]}</p><p class="hash"><code>{E(cert)}</code></p></section>')
    if d and not is_sample:
        parts.append(f'<section aria-labelledby="channel"><h2 id="channel">{t["channel"]}</h2><p>{t["channel_text"]}</p>'
                     '<ul><li><a href="../updates/stable.json"><code>updates/stable.json</code></a></li>'
                     '<li><a href="../updates/stable.json.sig"><code>updates/stable.json.sig</code></a></li></ul></section>')
    parts.append("</div></main>")
    return layout.page(lang=lg, title=f'{t["title"]} — Madalean', body="".join(parts), root="../",
                       alt_href=f"../{other}/download.html", active="download",
                       description=T[lg]["title"])


def _channel_page(published: bool, pub: bytes) -> str:
    files = ("<li><a href=\"stable.json\"><code>stable.json</code></a></li>"
             "<li><a href=\"stable.json.sig\"><code>stable.json.sig</code></a></li>") if published else ""
    body = (f'<main id="main" class="narrow prose" tabindex="-1"><h1>Madalean — canal de mise à jour</h1>'
            f'<p>Fichiers lus par Madalean, l\'application de bureau et l\'application Android pour savoir qu\'une version '
            f'existe. <code>stable.json.sig</code> est la signature Ed25519 (base64) des octets exacts de '
            f'<code>stable.json</code> ; tout fichier mal signé est refusé. Les fichiers eux-mêmes sont sur GitHub Releases.</p>'
            f'<ul>{files}<li><a href="madalean-release.pub.pem"><code>madalean-release.pub.pem</code></a></li></ul>'
            f'{"" if published else "<p>Aucune version publiée pour l’instant.</p>"}'
            f'<p><a href="../fr/download.html">Installer</a></p>'
            f'<section lang="en"><h2>Update channel</h2><p>Files read by Madalean, the desktop app and the Android app '
            f'to learn that a version exists. <code>stable.json.sig</code> is the Ed25519 signature (base64) of the exact '
            f'bytes of <code>stable.json</code>; anything badly signed is refused. Release files live on GitHub Releases.</p>'
            f'{"" if published else "<p>No version published yet.</p>"}<p><a href="../en/download.html">Install</a></p>'
            f'<p>Public key (hex): <code>{pub.hex()}</code></p></section></main>')
    return layout.page(lang="fr", title="Canal de mise à jour — Madalean", body=body, root="../",
                       alt_href=None, header_nav=True)
