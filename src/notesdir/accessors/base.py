from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set


@dataclass
class FileInfo:
    path: Path
    refs: Set[str]
    tags: Set[str]
    title: Optional[str]


@dataclass
class FileEdit:
    pass


class BaseAccessor:
    def parse(self, path: Path) -> FileInfo:
        raise NotImplementedError()

    def change(self, path: Path, edit: FileEdit):
        raise NotImplementedError()