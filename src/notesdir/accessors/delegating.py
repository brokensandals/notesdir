from pathlib import Path

from notesdir.accessors.base import Accessor, MiscAccessor
from notesdir.models import FileInfo, FileEditCmd
from notesdir.accessors.html import HTMLAccessor
from notesdir.accessors.markdown import MarkdownAccessor
from notesdir.accessors.pdf import PDFAccessor


class DelegatingAccessor(Accessor):
    def __init__(self, path: Path):
        super().__init__(path)
        if path.suffix == '.md':
            self.accessor = MarkdownAccessor(path)
        elif path.suffix == '.html':
            self.accessor = HTMLAccessor(path)
        elif path.suffix == '.pdf':
            self.accessor = PDFAccessor(path)
        else:
            self.accessor = MiscAccessor(path)

    def load(self):
        self.accessor.load()

    def info(self) -> FileInfo:
        return self.accessor.info()

    def edit(self, edit: FileEditCmd):
        self.accessor.edit(edit)

    def save(self) -> bool:
        return self.accessor.save()
