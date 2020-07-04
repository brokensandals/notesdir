from datetime import datetime
from typing import Optional

from PyPDF4 import PdfFileReader, PdfFileMerger
from PyPDF4.generic import IndirectObject

from notesdir.accessors.base import Accessor, ParseError
from notesdir.models import FileInfo, SetTitleCmd, SetCreatedCmd


def pdf_strptime(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("'", '').replace('Z0000', 'Z')
    if len(s) < 17:
        return datetime.strptime(s, 'D:%Y%m%d%H%M%S')
    else:
        return datetime.strptime(s, 'D:%Y%m%d%H%M%S%z')


def pdf_strftime(d: Optional[datetime]) -> Optional[str]:
    if not d:
        return None
    s = datetime.strftime(d, 'D:%Y%m%d%H%M%S')
    tz = datetime.strftime(d, '%z')
    if tz == '+0000':
        return f"{s}Z00'00'"
    else:
        return f"{s}{tz[:3]}'{tz[3:]}'"


def resolve_object(o):
    if isinstance(o, IndirectObject):
        return o.getObject()
    return o


class PDFAccessor(Accessor):
    def _load(self):
        with self.path.open('rb') as file:
            try:
                pdf = PdfFileReader(file)
                self._meta = {k: resolve_object(v) for k, v in pdf.getDocumentInfo().items()}
            except Exception as e:
                raise ParseError('Cannot parse PDF', self.path, e)

    def _info(self, info: FileInfo):
        info.title = self._meta.get('/Title')
        info.created = pdf_strptime(self._meta.get('/CreationDate'))
        for tag in self._meta.get('/Keywords').split(','):
            tag = tag.strip()
            if tag:
                info.managed_tags.add(tag)

    def _save(self):
        merger = PdfFileMerger()
        with self.path.open('rb') as file:
            merger.append(file)
        merger.addMetadata(self._meta)
        with self.path.open('wb') as file:
            merger.write(file)

    def _set_title(self, edit: SetTitleCmd):
        self.edited = self.edited or not self._meta.get('/Title') == edit.value
        self._meta['/Title'] = edit.value

    def _set_created(self, edit: SetCreatedCmd):
        self.edited = self.edited or not pdf_strptime(self._meta.get('/CreationDate')) == edit.value
        self._meta['/CreationDate'] = pdf_strftime(edit.value)
