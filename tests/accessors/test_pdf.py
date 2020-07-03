from datetime import datetime
from pathlib import Path
from PyPDF4 import PdfFileReader
from notesdir.accessors.base import SetTitle, SetCreated
from notesdir.accessors.pdf import PDFAccessor


def test_parse(fs):
    path = Path(__file__).parent.joinpath('test.pdf')
    fs.add_real_file(path)
    info = PDFAccessor().parse(path)
    assert info.path == path
    assert info.title == 'Test PDF'
    assert info.created == datetime.fromisoformat('2020-07-02T17:43:40+00:00')
    assert info.managed_tags == {'tag1', 'tag2'}


def test_change(fs):
    path = Path(__file__).parent.joinpath('test.pdf')
    fs.add_real_file(path, read_only=False)
    edits = [
        SetTitle(path, 'Why Donuts Are Great'),
        SetCreated(path, datetime.fromisoformat('1999-02-04T06:08:10+00:00'))
    ]
    assert PDFAccessor().change(edits)
    with path.open('rb') as file:
        pdf = PdfFileReader(file)
        assert 'I like donuts' in pdf.getPage(0).extractText()
        # Make sure we didn't destroy preexisting metadata
        assert pdf.getDocumentInfo()['/Creator'] == 'Pages'
    info = PDFAccessor().parse(path)
    assert info.title == 'Why Donuts Are Great'
    assert info.created == datetime.fromisoformat('1999-02-04T06:08:10+00:00')
    assert info.managed_tags == {'tag1', 'tag2'}
