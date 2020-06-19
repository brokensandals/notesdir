from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Set


@dataclass
class FileInfo:
    path: Path
    refs: Set[str]
    tags: Set[str]
    title: Optional[str]


@dataclass
class FileEdit:
    replace_refs: Dict[str, str] = field(default_factory=dict)
    pass


class BaseAccessor:
    def parse(self, path: Path) -> FileInfo:
        raise NotImplementedError()

    def change(self, path: Path, edit: FileEdit):
        raise NotImplementedError()
