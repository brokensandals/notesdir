from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileInfo:
    path: Path
    title: str


@dataclass
class FileEdit:
    pass


class FileAccessor:
    def parse(self, path: Path) -> FileInfo:
        raise NotImplementedError()

    def change(self, path: Path, edit: FileEdit):
        raise NotImplementedError()


class MarkdownAccessor(FileAccessor):
    def parse(self, path: Path) -> FileInfo:
        pass

    def change(self, path: Path, edit: FileEdit):
        raise NotImplementedError()
