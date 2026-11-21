"""Projects: a body of work (a course chapter, a paper) that groups dossiers.

Storage: one directory per project, `projects/<id>/project.json` (+ `refs.bib` and other per-project files added by
later sessions, ARCHITECTURE §11). Unknown fields are kept and written back untouched (forward compatibility)."""
from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config


@dataclass
class Project:
    id: str
    title: str
    description: str = ""
    workspace: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    archived: bool = False
    refs_file: str = ""                       # path of the project's refs.bib (inside its directory), "" = none yet
    sources: list = field(default_factory=list)   # papers / documents attached to the project (S-E)
    extra: dict = field(default_factory=dict)     # unknown fields, round-tripped

    def to_dict(self) -> dict:
        d = asdict(self)
        extra = d.pop("extra") or {}
        return {**extra, **d}

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        names = set(cls.__dataclass_fields__) - {"extra"}
        p = cls(**{k: v for k, v in d.items() if k in names})
        p.extra = {k: v for k, v in d.items() if k not in names and k != "extra"}
        return p


class ProjectStore:
    """Atomic writes; deletion moves the directory to `.trash` (restorable)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.trash = self.root / ".trash"

    def dir(self, pid: str) -> Path:
        return self.root / pid

    def new(self, title: str, description: str = "", workspace: str = "") -> Project:
        pid = "p-" + time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6]
        return Project(pid, title.strip() or "Projet", description, workspace)

    def save(self, p: Project, touch: bool = True) -> None:
        if touch:
            p.updated = time.time()
        config.atomic_write_text(self.dir(p.id) / "project.json",
                                 json.dumps(p.to_dict(), ensure_ascii=False, indent=1))

    def load(self, pid: str) -> Project | None:
        if not pid or "/" in pid or pid.startswith("."):
            return None
        try:
            return Project.from_dict(json.loads((self.dir(pid) / "project.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    def list(self) -> list[Project]:
        out = []
        if self.root.is_dir():
            for d in self.root.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    p = self.load(d.name)
                    if p is not None:
                        out.append(p)
        return sorted(out, key=lambda p: p.updated, reverse=True)

    def delete(self, pid: str) -> bool:
        src = self.dir(pid)
        if not (src / "project.json").exists():
            return False
        self.trash.mkdir(parents=True, exist_ok=True)
        dst = self.trash / pid
        if dst.exists():
            shutil.rmtree(dst)
        src.replace(dst)
        return True

    def undelete(self, pid: str) -> bool:
        src = self.trash / pid
        if not (src / "project.json").exists() or self.dir(pid).exists():
            return False
        src.replace(self.dir(pid))
        return True
