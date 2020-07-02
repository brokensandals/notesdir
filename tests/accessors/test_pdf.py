from datetime import datetime
from pathlib import Path
from notesdir.accessors.pdf import PDFAccessor


def test_parse(fs):
    path = Path(__file__).parent.joinpath('test.pdf')
    fs.add_real_file(path)
    info = PDFAccessor().parse(path)
    assert info.path == path
    assert info.title == 'Test PDF'
    assert info.created == datetime.fromisoformat('2020-07-02T17:43:40+00:00')
    assert info.tags == {'tag1', 'tag2'}
