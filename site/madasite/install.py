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

T = {
    "fr": {
        "title": "Installer et télécharger",
        "lead": "Madalean s'installe sur <strong>un ordinateur hôte</strong> sous Linux, qui fait tout le calcul. Les "
                "autres appareils (téléphone, tablette, autre PC) se relient à lui par votre réseau privé Tailscale, avec "
                "une application légère ou un simple navigateur. Voir le <a href=\"install.html\">guide d'installation</a> "
                "et <a href=\"pairing.html\">relier un appareil</a>.",
        "latest": "Dernière version", "none": "Aucune version n'est encore publiée sur ce canal. En attendant, "
                  "installez depuis les sources (ci-dessous).",
        "sample": "Aperçu avec des données d'exemple : ces fichiers n'existent pas.",
        "released": "publiée le", "notes": "Notes de version",
        "host": "Ordinateur hôte (Linux)", "host_text": "Le serveur s'installe depuis les sources, avec le script "
                "d'installation (relançable sans risque). Il faut environ 40 Go de disque ; une carte NVIDIA est conseillée.",
        "android": "Téléphone et tablette Android", "android_text": "Scannez le QR code avec l'appareil photo du "
                   "téléphone, ou touchez le lien depuis le téléphone. Android demande une fois d'autoriser l'installation "
                   "depuis le navigateur.",
        "which": "Quel fichier choisir ?", "arch": "Architecture", "file": "Fichier", "size": "Taille",
        "qr": "QR code",
        "arch_help": {"arm64-v8a": "presque tous les téléphones et tablettes depuis 2017",
                      "armeabi-v7a": "appareils 32 bits plus anciens",
                      "x86_64": "émulateurs, quelques tablettes et Chromebooks",
                      "universal": "fonctionne partout, plus volumineux"},
        "desktop": "Autre ordinateur Linux (application de bureau)",
        "desktop_text": "Fichier AppImage : rendez-le exécutable, puis lancez-le. L'application se relie à l'hôte "
                        "comme un téléphone. Construite et testée sur Arch Linux ; elle peut ne pas démarrer sur une "
                        "distribution beaucoup plus ancienne.",
        "ios": "iPhone, iPad, autres appareils",
        "ios_text": "Pas d'application : ouvrez l'adresse de l'hôte sur votre réseau Tailscale dans le navigateur "
                    "(par exemple <code>https://madalean.tailXXXX.ts.net</code>) et reliez l'appareil avec le "
                    "code affiché par l'hôte.",
        "verify": "Vérifier un téléchargement",
        "verify_text": "Chaque version publie <code>SHA256SUMS</code> (empreintes de tous les fichiers) et "
                       "<code>SHA256SUMS.sig</code>, sa signature Ed25519. La clé publique est inscrite dans Madalean, "
                       "qui refuse toute mise à jour mal signée. Pour vérifier vous-même, dans le dossier des fichiers "
                       "téléchargés :",
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
                "computing. Other devices (phone, tablet, another PC) link to it over your private Tailscale network, "
                "with a light app or just a browser. See the <a href=\"install.html\">installation guide</a> and "
                "<a href=\"pairing.html\">linking a device</a>.",
        "latest": "Latest version", "none": "No version has been published on this channel yet. Meanwhile, install "
                  "from source (below).",
        "sample": "Preview with sample data: these files do not exist.",
        "released": "released on", "notes": "Release notes",
        "host": "Host computer (Linux)", "host_text": "The server is installed from source with the install script "
                "(safe to re-run). It needs about 40 GB of disk; an NVIDIA graphics card is recommended.",
        "android": "Android phone and tablet", "android_text": "Scan the QR code with the phone's camera, or tap the "
                   "link on the phone. Android asks once to allow installing from the browser.",
        "which": "Which file?", "arch": "Architecture", "file": "File", "size": "Size", "qr": "QR code",
        "arch_help": {"arm64-v8a": "almost every phone and tablet since 2017",
                      "armeabi-v7a": "older 32-bit devices",
                      "x86_64": "emulators, a few tablets and Chromebooks",
                      "universal": "works everywhere, larger"},
        "desktop": "Another Linux computer (desktop app)",
        "desktop_text": "AppImage file: make it executable, then run it. The app links to the host like a phone. "
                        "Built and tested on Arch Linux; it may not start on a much older distribution.",
        "ios": "iPhone, iPad, other devices",
        "ios_text": "No app: open the host's address on your Tailscale network in the browser (for example "
                    "<code>https://madalean.tailXXXX.ts.net</code>) and link the device with the code shown by "
                    "the host.",
        "verify": "Verify a download",
        "verify_text": "Each release publishes <code>SHA256SUMS</code> (hashes of every file) and "
                       "<code>SHA256SUMS.sig</code>, its Ed25519 signature. The public key is built into Madalean, which "
                       "refuses any badly signed update. To check yourself, in the folder of the downloaded files:",
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


def _page(lg: str, d: dict | None, is_sample: bool, pub: bytes) -> str:
    t = T[lg]
    other = "en" if lg == "fr" else "fr"
    parts = [f'<main id="main" class="narrow prose" tabindex="-1"><h1>{t["title"]}</h1><p class="lead">{t["lead"]}</p>']
    if is_sample:
        parts.append(f'<p class="notice notice-warn" role="note"><strong>{E(t["sample"])}</strong></p>')
    files = (d or {}).get("files", [])
    if d:
        notes = (d.get("notes") or {}).get(lg, "")
        url = d.get("notes_url", "")
        parts.append(f'<section aria-labelledby="latest"><h2 id="latest">{t["latest"]} : {E(d["version"])}</h2>'.replace(
            " : ", " : " if lg == "fr" else ": "))
        parts.append(f'<p>{E(t["released"])} {E(d["date"])}.'
                     + (f' <a href="{E(url)}" rel="noopener noreferrer">{t["notes"]}</a>' if url else "") + "</p>")
        if notes:
            parts.append(f"<p>{E(notes)}</p>")
        parts.append("</section>")
    else:
        parts.append(f'<p class="notice" role="note">{t["none"]}</p>')
    tag = (d or {}).get("tag", "")
    parts.append(f'<section aria-labelledby="host"><h2 id="host">{t["host"]}</h2><p>{t["host_text"]}</p>'
                 '<pre class="code" tabindex="0"><code>git clone https://github.com/raantss18/madalean.git ~/madalean\n'
                 'cd ~/madalean\n' + (f"git checkout {E(tag)}\n" if tag else "") +
                 './install.sh --install-deps</code></pre></section>')
    apks = sorted([f for f in files if f.get("kind") == "apk"],
                  key=lambda f: ARCH_ORDER.index(f.get("arch")) if f.get("arch") in ARCH_ORDER else 99)
    parts.append(f'<section aria-labelledby="android"><h2 id="android">{t["android"]}</h2><p>{t["android_text"]}</p>')
    if apks:
        parts.append(f'<h3>{t["which"]}</h3><ul class="dl-list">')
        for f in apks:
            arch = f.get("arch", "")
            q = qr_svg(f["url"], f'{t["qr"]} — {f["name"]}', 168)
            parts.append(f'<li class="dl-item"><div class="dl-text"><h4>{E(arch)}</h4>'
                         f'<p>{E(t["arch_help"].get(arch, ""))}</p>'
                         f'<p><a class="button" href="{E(f["url"])}">{E(f["name"])}</a> '
                         f'<span class="muted">{_size(int(f.get("size", 0)), lg)}</span></p>'
                         f'<p class="hash"><span class="sr-only">SHA-256 </span><code>{E(f["sha256"])}</code></p></div>'
                         f'<div class="dl-qr">{q}</div></li>')
        parts.append("</ul>")
    parts.append("</section>")
    imgs = [f for f in files if f.get("kind") == "appimage"]
    parts.append(f'<section aria-labelledby="desktop"><h2 id="desktop">{t["desktop"]}</h2><p>{t["desktop_text"]}</p>')
    for f in imgs:
        parts.append(f'<p><a class="button" href="{E(f["url"])}">{E(f["name"])}</a> '
                     f'<span class="muted">{_size(int(f.get("size", 0)), lg)}</span></p>'
                     f'<pre class="code" tabindex="0"><code>chmod +x {E(f["name"])}\n./{E(f["name"])}</code></pre>')
    parts.append("</section>")
    parts.append(f'<section aria-labelledby="ios"><h2 id="ios">{t["ios"]}</h2><p>{t["ios_text"]}</p></section>')
    sums = (d or {}).get("sums_url") or "https://github.com/raantss18/madalean/releases/latest/download/SHA256SUMS"
    sumsig = (d or {}).get("sums_sig_url") or sums + ".sig"
    parts.append(f'<section aria-labelledby="verify"><h2 id="verify">{t["verify"]}</h2><p>{t["verify_text"]}</p>'
                 f'<ol><li>{t["step_sums"]}<pre class="code" tabindex="0"><code>sha256sum -c --ignore-missing SHA256SUMS</code></pre></li>'
                 f'<li>{t["step_sig"]}<pre class="code" tabindex="0"><code>base64 -d SHA256SUMS.sig &gt; SHA256SUMS.sig.bin\n'
                 'openssl pkeyutl -verify -pubin -inkey madalean-release.pub.pem -rawin \\\n'
                 '  -in SHA256SUMS -sigfile SHA256SUMS.sig.bin</code></pre></li></ol>'
                 f'<p><a href="../updates/madalean-release.pub.pem" download>madalean-release.pub.pem</a> · '
                 f'<a href="{E(sums)}" rel="noopener noreferrer">SHA256SUMS</a> · '
                 f'<a href="{E(sumsig)}" rel="noopener noreferrer">SHA256SUMS.sig</a></p>'
                 f'<p>{t["verify_key"]} :</p><p class="hash"><code>{pub.hex()}</code></p>'.replace(" :</p>", ":</p>" if lg == "en" else " :</p>"))
    cert = (d or {}).get("apk_certificate_sha256", "0d43426ba9682f791707ee3233361c369c8ebec3f1209c6e000d7322936fc544")
    parts.append(f'<p>{t["verify_apk"]}</p><p class="hash"><code>{E(cert)}</code></p></section>')
    parts.append(f'<section aria-labelledby="channel"><h2 id="channel">{t["channel"]}</h2><p>{t["channel_text"]}</p>'
                 '<ul><li><a href="../updates/stable.json"><code>updates/stable.json</code></a></li>'
                 '<li><a href="../updates/stable.json.sig"><code>updates/stable.json.sig</code></a></li></ul></section>'
                 if not is_sample and d else "")
    parts.append("</main>")
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
