from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Set


@dataclass
class FileInfo:
    path: Path
    refs: Set[str]
    tags: Set[str]
    title: Optional[str]


@dataclass
class FileEdit:
    ACTION = 'unknown'


@dataclass
class ReplaceRef(FileEdit):
    ACTION = 'replace_ref'
    original: str
    replacement: str


class BaseAccessor:
    def parse(self, path: Path) -> FileInfo:
        raise NotImplementedError()

    def change(self, path: Path, edits: List[FileEdit]):
        raise NotImplementedError()
