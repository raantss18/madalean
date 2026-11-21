"""`deps` update checker (ARCHITECTURE §16, §18), plugged into `madalean.updates` like S-G's checkers.

Two kinds of candidates, kind "deps":
- **pin newer than installed** (a Madalean update brought a new manifest): installable → `scripts/updater.py
  deps-install <component>` (download, verify SHA-256, new versioned directory, check, switch, keep previous) —
  automatic at a quiet moment when the user left « automatic » on, like Lean/Mathlib;
- **upstream newer than the pin** (new micromamba / elan / llama.cpp / Tailscale / conda-forge package): notify only.
  A new pin needs new hashes, so it arrives with a signed Madalean release; nothing unpinned is ever installed.
In `mode = local` nothing is queried on the network."""
from __future__ import annotations

import json
import re
import urllib.request

from .. import updates
from ..i18n import _
from . import health, manifest

UA = {"User-Agent": "madalean-update-check"}
GITHUB_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
ANACONDA = "https://api.anaconda.org/package/conda-forge/{name}"
TAILSCALE_TAGS = "https://api.github.com/repos/tailscale/tailscale/releases/latest"


def _get_json(url: str, timeout: float = 20) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read(2_000_000))


def _head_ok(url: str, timeout: float = 15) -> bool:
    """True when `url` exists (status < 400, redirects followed), False on 404 / 410; raises otherwise."""
    import urllib.error
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=timeout) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return False
        raise


BUNDLE_RE = re.compile(r"_v(\d+)\.tar$")
BUNDLE_PROBES = 3                  # at most 3 HEAD requests per check (usually 1: the next version is missing)


def bundle_latest(url: str, head=_head_ok) -> str:
    """Newest tectonic bundle published on the relay, probing v<N+1>, v<N+2>… from the pinned URL
    (relay.fullyjustified.net answers 302 for a published bundle, 404 otherwise — checked 2026-11-22: v33 302, v34
    404). Returns "v<N>" or "" when the URL has no version."""
    m = BUNDLE_RE.search(url or "")
    if not m:
        return ""
    n = int(m.group(1))
    for k in range(n + 1, n + 1 + BUNDLE_PROBES):
        if not head(BUNDLE_RE.sub(f"_v{k}.tar", url)):
            break
        n = k
    return f"v{n}"


def vkey(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4])


def newer(a: str, b: str) -> bool:
    return bool(a) and bool(b) and vkey(a) > vkey(b)


def upstream_versions(comps: dict, get=_get_json, head=_head_ok) -> dict[str, dict[str, str]]:
    """component -> {item: latest upstream version}. Errors are reported per item, never raised."""
    out: dict[str, dict[str, str]] = {}
    for name, c in comps.items():
        up = str(c.get("upstream", ""))
        items: dict[str, str] = {}
        try:
            if up.startswith("github-release:") and "," not in up:
                tag = get(GITHUB_LATEST.format(repo=up.split(":", 1)[1]))["tag_name"]
                items[name] = tag.lstrip("v")
            elif up == "go-module:tailscale.com":
                items["tailscale"] = get(TAILSCALE_TAGS)["tag_name"].lstrip("v")
            elif up == "tectonic-bundle":
                items[name] = bundle_latest(str(c.get("url", "")), head)
            elif up == "conda-forge" and c.get("watch"):
                for pkg in c["watch"]:
                    items[pkg] = str(get(ANACONDA.format(name=pkg)).get("latest_version", ""))
        except Exception as e:  # noqa: BLE001 (network: report, never crash)
            items["_error"] = str(e)[:200]
        out[name] = items
    return out


def pinned_versions(name: str, c: dict) -> dict[str, str]:
    if c.get("kind") == "conda-env":
        try:
            lv = manifest.lock_versions(c)
        except OSError:
            return {}
        return {p: lv.get(p, "") for p in c.get("watch", [])}
    if name == "madalean-net":
        return {"tailscale": c.get("tailscale", "")}
    if name == "llama.cpp":
        return {name: c.get("version", "").lstrip("b")}
    return {name: c.get("version", "")}


def candidates(get=_get_json, online: bool = True, head=_head_ok) -> list[updates.Candidate]:
    comps = manifest.components()
    out: list[updates.Candidate] = []
    for h in health.components():
        name = h["component"]
        if h["state"] == "outdated":
            out.append(updates.Candidate("deps", f"deps:{name}", f"{h['title']} {h['pinned']}", h["version"],
                                         h["pinned"], True, _("Nouvelle version fournie par la mise à jour de "
                                                              "Madalean : vérifiée (SHA-256) puis installée à côté de "
                                                              "l'ancienne, qui reste disponible."), 0,
                                         {"component": name}))
    if not online:
        return out
    ups = upstream_versions(comps, get, head)
    for name, items in ups.items():
        pins = pinned_versions(name, comps[name])
        for item, latest in items.items():
            if item == "_error":
                continue
            cur = pins.get(item, "")
            if name == "llama.cpp":
                latest = latest.lstrip("b")
            if newer(latest, cur):
                out.append(updates.Candidate(
                    "deps-upstream", f"deps-upstream:{name}:{item}", f"{item} {latest}", cur, latest, False,
                    _("Version plus récente publiée en amont. Madalean n'installe que des versions épinglées avec "
                      "leur empreinte : elle arrivera avec une prochaine version de Madalean."), 0,
                    {"component": name, "item": item}))
    return out


def install_args(c: updates.Candidate) -> list[str]:
    comp = c.spec.get("component", "")
    if not re.fullmatch(r"[a-z0-9.-]{1,40}", comp):
        raise ValueError("bad component")
    return ["deps-install", comp]


def register(ctx=None) -> None:
    updates.INSTALL_ARGS["deps"] = install_args

    def check() -> list[updates.Candidate]:
        local = ctx is not None and getattr(getattr(ctx, "settings", None), "mode", "") == "local"
        return candidates(online=not local)
    check.__name__ = "check_deps"
    updates.register_checker("Composants", check)
