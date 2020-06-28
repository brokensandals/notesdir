from datetime import datetime, timedelta, timezone
from pathlib import Path
from notesdir.accessors.base import ReplaceRef, SetAttr, FileInfo
from notesdir.accessors.html import HTMLAccessor


def test_parse_garbage(fs):
    # Ideally this test would trigger the try-except block in the parse method,
    # but I don't actually know how to construct a document that does that.
    doc = '<nonsense️'
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    info = HTMLAccessor().parse(path)
    assert info == FileInfo(path)


def test_parse(fs):
    doc = """<html>
    <head>
        <title>I Am A Strange Knot</title>
        <meta name="keywords" content="mind, Philosophy, cOnsciOusNess"/>
        <meta name="created" content="2019-10-03 23:31:14 -0800"/>
    </head>
    <body>
        Some #extra tags in the body! But <a href="#nope">this is not a tag.</a>
        Here's a <a href="../Another%20Note.md">link to another note</a>, and here's
        an image: <img src="me.html.resources/A%20Picture.png" />
    </body>
</html>"""
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    info = HTMLAccessor().parse(path)
    assert info.path == path
    assert info.title == 'I Am A Strange Knot'
    assert info.tags == {'mind', 'philosophy', 'consciousness', 'extra'}
    assert info.created == datetime(2019, 10, 3, 23, 31, 14, 0, timezone(timedelta(hours=-8)))
    assert info.refs == {'../Another%20Note.md', 'me.html.resources/A%20Picture.png', '#nope'}
