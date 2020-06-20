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
    path: Path


@dataclass
class SetAttr(FileEdit):
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

    def change(self, edits: List[FileEdit]) -> bool:
        if len(edits) == 0:
            return False
        if len({e.path for e in edits}) > 1:
            raise ValueError(f"change() received edits for multiple paths, which is unsupported: {edits}")
        return self._change(edits)

    def _change(self, edits: List[FileEdit]) -> bool:
        raise NotImplementedError()


class MiscAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        return FileInfo(path)

    def _change(self, edits: List[FileEdit]) -> bool:
        raise NotImplementedError()
