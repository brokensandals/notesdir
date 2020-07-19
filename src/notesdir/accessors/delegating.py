"""Provides the :class:`DelegatingAccessor` class."""

from notesdir.accessors.base import Accessor, MiscAccessor
from notesdir.models import FileInfo, FileEditCmd
from notesdir.accessors.html import HTMLAccessor
from notesdir.accessors.markdown import MarkdownAccessor
from notesdir.accessors.pdf import PDFAccessor


class DelegatingAccessor(Accessor):
    """Responsible for choosing what :class:`notesdir.accessors.base.Accessor` subclass to use for a given file.

    This selects an accessor based on the path's file extension, and delegates method calls to that accessor.

    Currently, the mapping is hardcoded:

    * ``.md`` -> :class:`MarkdownAccessor`
    * ``.html`` -> :class:`HTMLAccessor`
    * ``.pdf`` -> :class:`PDFAccessor`
    * anything else -> :class:`MiscAccessor`
    """
    def __init__(self, path: str):
        super().__init__(path)
        if path.endswith('.md'):
            self.accessor = MarkdownAccessor(path)
        elif path.endswith('.html'):
            self.accessor = HTMLAccessor(path)
        elif path.endswith('.pdf'):
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
