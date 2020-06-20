from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List, Set


@dataclass
class FileInfo:
    path: Path
    refs: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    title: Optional[str] = None


@dataclass
class FileEdit:
    ACTION = 'unknown'


@dataclass
class SetAttr:
    ACTION = 'set_attr'
    key: str
    value: Any


@dataclass
class ReplaceRef(FileEdit):
    ACTION = 'replace_ref'
    original: str
    replacement: str


class BaseAccessor:
    def parse(self, path: Path) -> FileInfo:
        raise NotImplementedError()

    def change(self, path: Path, edits: List[FileEdit]) -> bool:
        raise NotImplementedError()


class MiscAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        return FileInfo(path)

    def change(self, path: Path, edits: List[FileEdit]) -> bool:
        raise NotImplementedError()
