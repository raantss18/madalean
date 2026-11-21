"""CycloneDX 1.5 SBOM of an installed prefix (ARCHITECTURE §15): every conda package of the locked envs (from
conda-meta: name, version, licence, SHA-256, URL), every pinned component of the manifest, and the Go modules
compiled into madalean-net (net/go.mod + go.sum)."""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from . import env_dir, home, manifest, sage_env_dir

ROOT = Path(__file__).resolve().parents[2]


def _conda_components(env: Path, group: str) -> list[dict]:
    out = []
    for f in sorted((env / "conda-meta").glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        c = {"type": "library", "bom-ref": f"conda:{group}:{m.get('name')}@{m.get('version')}",
             "group": group, "name": m.get("name", ""), "version": str(m.get("version", "")),
             "purl": f"pkg:conda/conda-forge/{m.get('name')}@{m.get('version')}?build={m.get('build', '')}"
                     f"&subdir={m.get('subdir', '')}",
             "externalReferences": [{"type": "distribution", "url": m.get("url", "")}]}
        if m.get("sha256"):
            c["hashes"] = [{"alg": "SHA-256", "content": m["sha256"]}]
        if m.get("license"):
            c["licenses"] = [{"expression": m["license"]}] if re.fullmatch(r"[A-Za-z0-9.+\-() ]+", m["license"]) \
                else [{"license": {"name": m["license"][:200]}}]
        out.append(c)
    return out


def _go_components() -> list[dict]:
    gomod, gosum = ROOT / "net" / "go.mod", ROOT / "net" / "go.sum"
    if not gomod.exists():
        return []
    sums = {}
    if gosum.exists():
        for ln in gosum.read_text().splitlines():
            parts = ln.split()
            if len(parts) == 3 and not parts[1].endswith("/go.mod"):
                sums[(parts[0], parts[1])] = parts[2]
    out = []
    for m in re.finditer(r"^\s*([\w./~-]+\.[\w./~-]+)\s+(v[\w.+-]+)", gomod.read_text(), re.M):
        name, ver = m.group(1), m.group(2)
        c = {"type": "library", "bom-ref": f"go:{name}@{ver}", "group": "madalean-net", "name": name,
             "version": ver, "purl": f"pkg:golang/{name}@{ver}"}
        if (name, ver) in sums:
            c["properties"] = [{"name": "go.sum:h1", "value": sums[(name, ver)]}]
        out.append(c)
    return out


def _manifest_components() -> list[dict]:
    out = []
    for name, c in manifest.components().items():
        urls = [c.get("url")] + [v.get("url") for v in c.get("variants", {}).values()] + \
               [a.get("url") for a in c.get("assets", [])]
        item = {"type": "application" if c.get("kind") in ("binary", "archive") else "data",
                "bom-ref": f"madalean-component:{name}@{c.get('version')}", "name": name,
                "version": str(c.get("version", "")), "description": c.get("title", ""),
                "licenses": [{"license": {"name": c.get("license", "")}}],
                "externalReferences": [{"type": "distribution", "url": u} for u in urls if u]}
        if re.fullmatch(r"[0-9a-f]{64}", c.get("sha256", "")):
            item["hashes"] = [{"alg": "SHA-256", "content": c["sha256"]}]
        out.append(item)
    return out


def build_sbom() -> dict:
    from .. import __version__
    comps = _manifest_components()
    if (env_dir() / "conda-meta").is_dir():
        comps += _conda_components(env_dir(), "env")
    if (sage_env_dir() / "conda-meta").is_dir():
        comps += _conda_components(sage_env_dir(), "sage")
    comps += _go_components()
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
            "metadata": {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         "tools": [{"vendor": "Madalean", "name": "madalean.deps.sbom", "version": __version__}],
                         "component": {"type": "application", "name": "madalean", "version": __version__,
                                       "bom-ref": "madalean"},
                         "properties": [{"name": "madalean:prefix", "value": str(home())}]},
            "components": comps}


def write_sbom(out: Path) -> int:
    d = build_sbom()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return len(d["components"])
