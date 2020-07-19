from datetime import datetime
from typing import Optional, Set

from PyPDF4 import PdfFileReader, PdfFileMerger
from PyPDF4.generic import IndirectObject

from notesdir.accessors.base import Accessor, ParseError
from notesdir.models import AddTagCmd, DelTagCmd, FileInfo, SetTitleCmd, SetCreatedCmd


def _pdf_strptime(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("'", '').replace('Z0000', 'Z')
    if len(s) < 17:
        return datetime.strptime(s, 'D:%Y%m%d%H%M%S')
    else:
        return datetime.strptime(s, 'D:%Y%m%d%H%M%S%z')


def _pdf_strftime(d: Optional[datetime]) -> Optional[str]:
    if not d:
        return None
    s = datetime.strftime(d, 'D:%Y%m%d%H%M%S')
    tz = datetime.strftime(d, '%z')
    if tz == '+0000':
        return f"{s}Z00'00'"
    else:
        return f"{s}{tz[:3]}'{tz[3:]}'"


def _resolve_object(o):
    if isinstance(o, IndirectObject):
        return o.getObject()
    return o


class PDFAccessor(Accessor):
    """Responsible for parsing and updating PDF files.

    Current support:

    * Metadata is stored in the PDF's "document info":
        * ``/Title``
        * ``/CreationDate``
        * ``/Keywords`` (comma-separated)
    * Links are *not* currently supported, so although notesdir can update links to PDF files from other files,
      it will not currently update links from PDF files to other files.

    PyPDF4 is used for parsing and updating.

    Note: when updating a PDF containing the metadata key ``/AAPL:Keywords`` (which is often included on PDFs
    generated on Mac), that field will be removed. It appears to violate version 1.7 of the PDF spec, and PyPDF4
    cannot serialize it.
    """
    def _load(self):
        with open(self.path, 'rb') as file:
            try:
                pdf = PdfFileReader(file)
                if pdf.isEncrypted:
                    # See https://github.com/mstamy2/PyPDF2/issues/51
                    # Some PDFs that open fine without a password in many apps, apparently
                    # have a password of an empty string
                    pdf.decrypt('')
                self._meta = {k: _resolve_object(v) for k, v in (pdf.getDocumentInfo() or {}).items()}
            except Exception as e:
                raise ParseError('Cannot parse PDF', self.path, e)

    def _tags(self):
        split = (t.strip() for t in self._meta.get('/Keywords', '').lower().split(','))
        return {t for t in split if t}

    def _info(self, info: FileInfo):
        info.title = self._meta.get('/Title')
        info.created = _pdf_strptime(self._meta.get('/CreationDate'))
        info.tags.update(self._tags())

    def _save(self):
        merger = PdfFileMerger()
        with open(self.path, 'rb') as file:
            merger.append(file)
        if '/AAPL:Keywords' in self._meta:
            # HACK: Some Apple software includes this field when producing PDFs.
            # The value is an array. However, at least as of version 1.7, the PDF spec
            # forbids custom document info fields from having anything but string values.
            # PyPDF will crash if we try to have it write an array to a document info field.
            del self._meta['/AAPL:Keywords']
        merger.addMetadata(self._meta)
        with open(self.path, 'wb') as file:
            merger.write(file)

    def _add_tag(self, edit: AddTagCmd):
        lower = edit.value.lower()
        tags = self._tags()
        if lower in tags:
            return
        tags.add(lower)
        self._set_tags(tags)

    def _del_tag(self, edit: DelTagCmd):
        lower = edit.value.lower()
        tags = self._tags()
        if lower not in tags:
            return
        tags.remove(lower)
        self._set_tags(tags)

    def _set_tags(self, tags: Set[str]):
        self._meta['/Keywords'] = ', '.join(sorted(tags))
        self.edited = True

    def _set_title(self, edit: SetTitleCmd):
        self.edited = self.edited or not self._meta.get('/Title') == edit.value
        self._meta['/Title'] = edit.value

    def _set_created(self, edit: SetCreatedCmd):
        self.edited = self.edited or not _pdf_strptime(self._meta.get('/CreationDate')) == edit.value
        self._meta['/CreationDate'] = _pdf_strftime(edit.value)
