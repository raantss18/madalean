"""Problem sets of the benchmark: the built-in smoke set, miniF2F and PutnamBench (docs/BENCH.md).

miniF2F and PutnamBench are NOT vendored: `fetch()` downloads the public repository at a pinned commit into a cache
directory outside the source tree (`~/.cache/madalean-bench/sets/<set>-<commit>/`), keeps only the Lean problem files
and the licence, and records the commit, the archive SHA-256 and a content hash of the kept files (`source.json`).
A cache whose content hash differs from the pinned one is refused (a changed upstream is a different benchmark).

A problem is a complete Lean file ending with `theorem NAME … := by sorry` (header included), exactly what the
application's statement editor holds once Lean accepted a statement."""
from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import tarfile
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import leancheck
from .smoke import SMOKE

CODELOAD = "https://codeload.github.com/{repo}/tar.gz/{commit}"
MAX_ARCHIVE = 80 * 1024 * 1024
MAX_FILE = 256 * 1024


@dataclass(frozen=True)
class Source:
    name: str
    repo: str                      # GitHub « owner/name » (public)
    commit: str                    # pinned commit (full SHA)
    licence: str                   # SPDX id of the Lean 4 part
    licence_file: str              # path of the licence in the repository
    lean: str                      # toolchain the upstream project is built with (informative)
    pattern: str                   # regex of the problem files inside the repository
    content_sha256: str = ""       # pinned hash of the kept problem files ("" = not pinned yet)
    splits: tuple = ()
    note: str = ""

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repo}/tree/{self.commit}"


SOURCES: dict[str, Source] = {
    "minif2f": Source(
        "minif2f", "yangky11/miniF2F-lean4", "5746b7d6c47855ce1294bed87329618ff7f1bc31", "MIT", "LICENSE",
        "leanprover/lean4:v4.24.0", r"^MiniF2F/(Valid|Test)/[\w']+\.lean$",
        "c5e5ab3da5028fec193f4b0e64aa1d0fbf40de7bea8227999b90a408b9b8ce73", ("valid", "test"),
        "488 olympiad / school statements (244 valid + 244 test), one file per problem."),
    "putnam": Source(
        "putnam", "trishullab/PutnamBench", "a635813f5edf297d928f9bd5ef8324a26bdde09c", "Apache-2.0", "lean4/LICENSE",
        "leanprover/lean4:v4.33.1", r"^lean4/src/putnam_\d{4}_[ab]\d+\.lean$",
        "597367f4927e76b26f5316193acb5b686c09a10090cdb0ad20be970b81bda9fb", (),
        "Putnam competition 1962–2025 (Lean 4 part). Upstream asks not to publish proofs: runs keep them out of the "
        "committed results."),
}
SET_NAMES = ("smoke", *SOURCES)


@dataclass
class Problem:
    id: str
    set: str
    statement: str                 # full Lean file, target theorem last, ends with `:= by sorry`
    split: str = ""
    branch: str = ""               # smoke set: the mathematical branch
    informal: str = ""
    note: str = ""                 # e.g. « answer filled in from the upstream comment »

    @property
    def theorem(self) -> str:
        return leancheck.theorem_name(self.statement)

    def to_dict(self) -> dict:
        return asdict(self)


class SetError(Exception):
    pass


def cache_root(cache_dir: Path | None = None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir)
    base = os.environ.get("MADALEAN_BENCH_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "madalean-bench")
    return Path(base)


def set_dir(name: str, cache_dir: Path | None = None) -> Path:
    s = SOURCES[name]
    return cache_root(cache_dir) / "sets" / f"{name}-{s.commit[:12]}"


# ---------------------------------------------------------------- fetch (network; never inside the source tree)
def content_hash(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.encode() + b"\0" + hashlib.sha256(files[path]).digest())
    return h.hexdigest()


def _download(url: str, timeout: float = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "madalean-bench"})
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 (fixed https host, pinned commit)
        data = r.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise SetError("archive larger than expected")
    return data


def extract(archive: bytes, src: Source) -> dict[str, bytes]:
    """The problem files and the licence of a repository archive, as {path inside the repository: bytes}. Only
    regular files whose path matches are read; nothing is written by tarfile itself (no path traversal)."""
    keep: dict[str, bytes] = {}
    pat = re.compile(src.pattern)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        for m in tf:
            if not m.isfile() or m.size > MAX_FILE:
                continue
            path = m.name.split("/", 1)[1] if "/" in m.name else m.name     # drop « repo-commit/ »
            if ".." in path.split("/") or path.startswith("/"):
                continue
            if pat.match(path) or path == src.licence_file:
                f = tf.extractfile(m)
                if f is not None:
                    keep[path] = f.read()
    return keep


def fetch(name: str, cache_dir: Path | None = None, *, force: bool = False, download=_download,
          allow_unpinned: bool = False) -> dict:
    """Download a set at its pinned commit into the cache. Returns the recorded `source.json`."""
    if name not in SOURCES:
        raise SetError(f"unknown downloadable set: {name}")
    src = SOURCES[name]
    out = set_dir(name, cache_dir)
    meta_file = out / "source.json"
    if meta_file.exists() and not force:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    archive = download(CODELOAD.format(repo=src.repo, commit=src.commit))
    files = extract(archive, src)
    problems = {p: b for p, b in files.items() if p != src.licence_file}
    if not problems:
        raise SetError(f"{name}: no problem file found in the archive of {src.repo}@{src.commit[:12]}")
    digest = content_hash(problems)
    if src.content_sha256 and digest != src.content_sha256 and not allow_unpinned:
        raise SetError(f"{name}: content hash {digest} differs from the pinned {src.content_sha256}")
    tmp = out.with_name(out.name + ".part")
    if tmp.exists():
        _rmtree(tmp)
    for path, data in files.items():
        f = tmp / "files" / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    meta = {"set": name, "repo": src.repo, "commit": src.commit, "url": src.url, "licence": src.licence,
            "licence_file": src.licence_file if src.licence_file in files else "",
            "upstream_lean": src.lean, "problems": len(problems),
            "archive_sha256": hashlib.sha256(archive).hexdigest(), "content_sha256": digest,
            "pinned": bool(src.content_sha256), "fetched": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (tmp / "source.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    if out.exists():
        _rmtree(out)
    tmp.rename(out)
    return meta


def _rmtree(p: Path) -> None:
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def source_meta(name: str, cache_dir: Path | None = None) -> dict:
    """What is recorded about a set (commit, hashes, licence); for the smoke set, its own identity."""
    if name == "smoke":
        return {"set": "smoke", "repo": "", "commit": "", "licence": "Apache-2.0 (Madalean)", "problems": len(SMOKE),
                "content_sha256": content_hash({p.id: p.statement.encode() for p in smoke()}), "pinned": True}
    f = set_dir(name, cache_dir) / "source.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SetError(f"{name} is not in the cache: run `madalean bench fetch {name}`") from None


# ---------------------------------------------------------------- loaders
def smoke() -> list[Problem]:
    return [Problem(k, "smoke", leancheck.GOEDEL_HEADER + st + "\n", branch=branch, informal=informal)
            for k, branch, informal, st in SMOKE]


HEADER_LINE = re.compile(r"^\s*(import|open|set_option|universe|variable|noncomputable section|section|namespace)\b")
ANSWER = re.compile(r"(?m)^((?:noncomputable\s+)?abbrev\s+\w+_solution\b[^\n]*?:=)\s*sorry[ \t]*\n[ \t]*--[ \t]*(\S[^\n]*)$")
DOC = re.compile(r"/--(.*?)-/", re.S)


def normalise(text: str) -> tuple[str, str, str]:
    """(statement ending with `:= by sorry`, informal text, note) of an upstream problem file. PutnamBench « answer »
    problems leave the answer as `abbrev …_solution : T := sorry` followed by the answer in a comment: it is filled
    in (the task « prove with the answer given »)."""
    src = text.replace("\r\n", "\n")
    note = ""
    if ANSWER.search(src):
        src = ANSWER.sub(lambda m: f"{m.group(1)} {m.group(2).strip()}", src)
        note = "answer filled in from the upstream comment"
    # the target ends with `:= sorry` upstream; made explicit here so that a `let … := …` inside the statement is
    # never mistaken for the end of the statement
    src = re.sub(r":=\s*(?:by\s+)?sorry\s*\Z", ":= by sorry\n", src.rstrip())
    docs = DOC.findall(src)
    informal = " ".join(docs[-1].split()) if docs else ""
    return leancheck.prepare_statement(src), informal, note


def _load_cached(name: str, cache_dir: Path | None = None) -> list[Problem]:
    src = SOURCES[name]
    root = set_dir(name, cache_dir) / "files"
    meta = source_meta(name, cache_dir)
    pat = re.compile(src.pattern)
    out = []
    files = {}
    for f in sorted(root.rglob("*.lean")):
        rel = f.relative_to(root).as_posix()
        if pat.match(rel):
            files[rel] = f.read_bytes()
    if content_hash(files) != meta.get("content_sha256"):
        raise SetError(f"{name}: the cached files do not match source.json (run `madalean bench fetch {name} --force`)")
    if src.content_sha256 and meta.get("content_sha256") != src.content_sha256:
        raise SetError(f"{name}: cached content differs from the pinned hash")
    for rel, data in files.items():
        pid = Path(rel).stem
        split = Path(rel).parent.name.lower() if src.splits else ""
        try:
            st, informal, note = normalise(data.decode("utf-8"))
        except (leancheck.StatementError, UnicodeDecodeError) as e:
            out.append(Problem(pid, name, "", split=split, note=f"unreadable: {e}"))
            continue
        out.append(Problem(pid, name, st, split=split, informal=informal, note=note))
    return out


def load(name: str, cache_dir: Path | None = None, *, split: str = "") -> list[Problem]:
    """All problems of a set, sorted by id (the order of every run)."""
    if name == "smoke":
        ps = smoke()
    elif name in SOURCES:
        ps = _load_cached(name, cache_dir)
    else:
        raise SetError(f"unknown set: {name} (known: {', '.join(SET_NAMES)})")
    if split:
        ps = [p for p in ps if p.split == split]
    return sorted(ps, key=lambda p: p.id)


def select(problems: list[Problem], *, sample: int = 0, seed: int = 0, ids: list[str] | None = None,
           limit: int = 0) -> list[Problem]:
    """Deterministic choice: explicit ids, else a seeded sample (`random.Random(seed)` over the sorted ids), else the
    first `limit`; always returned sorted by id."""
    ps = sorted(problems, key=lambda p: p.id)
    if ids:
        want = set(ids)
        ps = [p for p in ps if p.id in want]
    elif sample and sample < len(ps):
        ps = sorted(random.Random(seed).sample(ps, sample), key=lambda p: p.id)
    if limit:
        ps = ps[:limit]
    return ps


@dataclass
class Compiled:
    ok: list[str] = field(default_factory=list)
    bad: dict[str, str] = field(default_factory=dict)      # id -> first Lean error (statement does not compile)
