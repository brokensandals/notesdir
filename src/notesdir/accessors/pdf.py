from datetime import datetime
from pathlib import Path
from typing import List, Optional
from PyPDF4 import PdfFileReader, PdfFileMerger
from PyPDF4.generic import IndirectObject
from notesdir.accessors.base import BaseAccessor
from notesdir.models import FileInfo, FileEditCmd, SetTitleCmd, SetCreatedCmd


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


class PDFAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        info = FileInfo(path)
        with path.open('rb') as file:
            try:
                pdf = PdfFileReader(file)
                pdfinfo = pdf.getDocumentInfo()
                info.title = resolve_object(pdfinfo.get('/Title'))
                info.created = pdf_strptime(resolve_object(pdfinfo.get('/CreationDate')))
                for tag in resolve_object(pdfinfo.get('/Keywords')).split(','):
                    tag = tag.strip()
                    if tag:
                        info.managed_tags.add(tag)
            except:
                # TODO
                pass
        return info

    def _change(self, edits: List[FileEditCmd]) -> bool:
        path = edits[0].path
        merger = PdfFileMerger()

        with path.open('rb') as file:
            pdf = PdfFileReader(file)
            oldmeta = {k: resolve_object(v) for k, v in pdf.getDocumentInfo().items()}
            newmeta = oldmeta.copy()

            for edit in edits:
                if isinstance(edit, SetTitleCmd):
                    newmeta['/Title'] = edit.value
                elif isinstance(edit, SetCreatedCmd):
                    newmeta['/CreationDate'] = pdf_strftime(edit.value)

            if oldmeta == newmeta:
                return False

            merger.append(file)

        merger.addMetadata(newmeta)
        with path.open('wb') as file:
            merger.write(file)

        return True
