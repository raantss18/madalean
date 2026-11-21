"""Optional Overleaf round trip (session S-R, docs/ARTICLE.md §7). Madalean is the main editor; a local Overleaf
(Community Edition, docker container `sharelatex`) is used only when the user asks, and its data is never modified:

- detection is read-only (`docker ps`, `GET <url>/status`);
- « Ouvrir dans Overleaf » = an Overleaf-ready zip (the user uploads it with « New project → Upload project »;
  CE has no project API and no git bridge);
- « Reprendre depuis Overleaf » = import of the zip Overleaf gives (Menu → Source): .tex / .bib / images only,
  guarded like any source, history snapshot first."""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile
from pathlib import PurePosixPath

from . import texbuild, texproject as tp

LATEXMKRC = "# Madalean: compile with XeLaTeX (fontspec / unicode-math)\n$pdf_mode = 5;\n"
_DETECT: dict = {"t": 0.0, "v": None}


def detect(force: bool = False) -> dict:
    """{found, url, container, image, source: docker|http|none, alive}. Cached 60 s. Never writes anything."""
    if not force and _DETECT["v"] is not None and time.time() - _DETECT["t"] < 60:
        return _DETECT["v"]
    res = {"found": False, "url": "", "container": "", "image": "", "source": "none", "alive": False}
    docker = shutil.which("docker")
    if docker:
        try:
            out = subprocess.run([docker, "ps", "--format", "{{json .}}"], capture_output=True, text=True,
                                 timeout=5, stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        for ln in out.splitlines():
            try:
                c = json.loads(ln)
            except ValueError:
                continue
            name, image = c.get("Names", ""), c.get("Image", "")
            if re.search(r"sharelatex|overleaf", name + " " + image, re.I):
                m = re.search(r"(?:(\d+\.\d+\.\d+\.\d+|\[::\]|::):)?(\d+)->80/tcp", c.get("Ports", ""))
                host = m.group(1) if m and m.group(1) and m.group(1) not in ("0.0.0.0", "[::]", "::") else "127.0.0.1"
                port = m.group(2) if m else "80"
                res.update(found=True, container=name, image=image, source="docker",
                           url=f"http://{host}" + ("" if port == "80" else f":{port}"))
                break
    if not res["found"]:
        res["url"] = "http://127.0.0.1"
    try:
        with urllib.request.urlopen(res["url"] + "/status", timeout=2) as r:          # noqa: S310 (loopback)
            body = r.read(200).decode("utf-8", "replace")
            res["alive"] = r.status == 200 and "alive" in body
            if res["alive"] and not res["found"]:
                res.update(found=True, source="http")
    except Exception:  # noqa: BLE001
        pass
    _DETECT.update(t=time.time(), v=res)
    return res


def export_zip(ctx, pid: str) -> bytes:
    """Overleaf-ready project: sources, figures, refs.bib and madalean-generated.tex (derived, snapshot),
    latexmkrc (XeLaTeX). The truth rule is applied (unverified theorems are claims) as in every export."""
    build, _s, _a, _h = tp_build(ctx, pid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, v in sorted(build.items()):
            if isinstance(v, str):
                z.writestr(rel, v)
            else:
                z.write(v, rel)
        z.writestr("latexmkrc", LATEXMKRC)
        try:
            z.writestr("madalean.toml", (tp.root(ctx, pid) / "madalean.toml").read_text(encoding="utf-8"))
        except OSError:
            pass
    return buf.getvalue()


def tp_build(ctx, pid: str):
    return texbuild.prepare(ctx, pid, for_export=True)


IMPORT_OK = re.compile(r"^(main\.tex|sections/[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.tex|refs\.bib|madalean\.toml|"
                       r"figures/[^/]{1,120}\.(png|jpe?g|pdf))$", re.I)
SKIP_QUIET = {"latexmkrc", "madalean-generated.tex", "madalean.lock"}


def import_zip(ctx, pid: str, data: bytes, by: str = "") -> dict:
    """Overleaf zip → project files. Returns {changed:[paths], skipped:[{name, why}], refs_bib: text|None,
    preamble_manual: bool}. Raises TexProjectError."""
    if len(data) > 60 * 1024 * 1024:
        raise tp.TexProjectError("too_large", 413)
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise tp.TexProjectError("bad_archive", 422)
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > 500 or sum(i.file_size for i in infos) > 200 * 1024 * 1024:
        raise tp.TexProjectError("bad_archive", 422)
    names = [i.filename for i in infos]
    # Overleaf zips are flat; strip one common top-level folder if there is one
    prefix = ""
    tops = {n.split("/", 1)[0] for n in names}
    if len(tops) == 1 and all("/" in n for n in names):
        prefix = next(iter(tops)) + "/"
    files: dict[str, bytes] = {}
    skipped = []
    for i in infos:
        n = i.filename[len(prefix):] if i.filename.startswith(prefix) else i.filename
        pp = PurePosixPath(n)
        if n.startswith("/") or ".." in pp.parts or n in SKIP_QUIET:
            continue
        if not IMPORT_OK.match(n):
            why = "third_party_tex" if re.search(r"\.(sty|cls|lua|def|fd|bst|bbx|cbx|dtx|ins)$", n, re.I) \
                else "not_supported"
            skipped.append({"name": n[:200], "why": why})
            continue
        files[n] = z.read(i)
    if "main.tex" not in files:
        raise tp.TexProjectError("no_main", 422)
    texts = {}
    for n, b in files.items():
        if n.endswith((".tex", ".bib", ".toml")):
            try:
                texts[n] = b.decode("utf-8")
            except UnicodeDecodeError:
                raise tp.TexProjectError("bad_encoding", 422, file=n)
    texts = {n: texbuild.untruth(t) if n.endswith(".tex") else t for n, t in texts.items()}
    bad = [(n, g) for n, t in texts.items() if n.endswith(".tex") for g in texbuild.guard(t)]
    if bad:
        n, g = bad[0]
        raise tp.TexProjectError("unsafe_tex", 422, file=n, line=g["line"], found=g["what"])
    with tp.lock(pid):
        tp.snapshot(ctx, pid, "before-overleaf-import", auto=False, by=by)
        cur = tp.read_files(ctx, pid)
        s = tp.read_settings(ctx, pid)
        changed = []
        if "madalean.toml" in texts:
            try:
                import tomllib
                s2 = tp.normalize_settings(tomllib.loads(texts["madalean.toml"]))
                if not tp.validate_settings(s2):
                    s = s2
            except Exception:  # noqa: BLE001
                pass
        main = texts["main.tex"]
        manual = tp.get_region(main, "preamble") is None or \
            tp.get_region(main, "preamble").strip() != tp.gen_preamble(s).strip()
        if manual:
            s["madalean"]["preamble"] = "manual"
        tp.write_settings(ctx, pid, s)
        for n, t in texts.items():
            if n.endswith(".tex") and cur.get(n) != t:
                tp.write_file(ctx, pid, n, t)
                changed.append(n)
        for n in cur:
            if n.startswith("sections/") and n not in texts:
                tp.delete_file(ctx, pid, n)
                changed.append(n)
        for n, b in files.items():
            if n.startswith("figures/"):
                try:
                    tp.add_figure(ctx, pid, b)
                except tp.TexProjectError:
                    skipped.append({"name": n, "why": "bad_type"})
        return {"changed": changed, "skipped": skipped, "refs_bib": texts.get("refs.bib"),
                "preamble_manual": manual}
