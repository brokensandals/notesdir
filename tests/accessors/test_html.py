from datetime import datetime, timedelta, timezone
from pathlib import Path
from bs4 import BeautifulSoup
from notesdir.models import AddTagCmd, DelTagCmd, FileInfo, SetTitleCmd, SetCreatedCmd, ReplaceRefCmd
from notesdir.accessors.html import HTMLAccessor


def test_info_garbage(fs):
    # Ideally this test would trigger the try-except block in the load method,
    # but I don't actually know how to construct a document that does that.
    doc = '<nonsense️'
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    info = HTMLAccessor(path).info()
    assert info == FileInfo(path)


def test_info(fs):
    doc = """<html>
    <head>
        <title>I Am A Strange Knot</title>
        <meta name="keywords" content="mind, Philosophy, cOnsciOusNess"/>
        <meta name="created" content="2019-10-03 23:31:14 -0800"/>
    </head>
    <body>
        No #extra tags in the body for now! And <a href="#nope">this will never be a tag.</a>
        Here's a <a href="../Another%20Note.md">link to another note</a>, and here's
        an image: <img src="me.html.resources/A%20Picture.png" />
    </body>
</html>"""
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    info = HTMLAccessor(path).info()
    assert info.path == path
    assert info.title == 'I Am A Strange Knot'
    assert info.tags == {'mind', 'philosophy', 'consciousness'}
    assert info.created == datetime(2019, 10, 3, 23, 31, 14, 0, timezone(timedelta(hours=-8)))
    assert info.refs == {'../Another%20Note.md', 'me.html.resources/A%20Picture.png', '#nope'}


def test_change_from_missing_attributes(fs):
    doc = """<html>
    <body>Hi!</body>
</html>"""
    expected = """<html><head><title>A Delightful Note</title><meta name="created" content="2019-06-04 10:12:13 -0800"/></head>
    <body>Hi!</body>
</html>"""
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    acc = HTMLAccessor(path)
    acc.edit(SetTitleCmd(path, 'A Delightful Note'))
    acc.edit(SetCreatedCmd(path, datetime(2019, 6, 4, 10, 12, 13, 0, timezone(timedelta(hours=-8)))))
    assert acc.save()
    assert BeautifulSoup(path.read_text(), 'lxml') == BeautifulSoup(expected, 'lxml')


def test_change(fs):
    doc = """<html>
    <head>
        <title>fdsalkhflsdakjsdhfaslkjdhfalkj</title>
        <meta name="created" content="2001-01-01 02:02:02 +0000" />
    </head>
    <body>
        <p>Hi! Here's a <a href="../Mediocre%20Note.md">link</a> and a <img src="http://example.com/foo.png" title="picture"/>.</p>

        <video controls src="media/something.weird">a video element</video>
        <audio controls src="media/something.weird">an audio element</audio>
        <audio controls><source src="media/something.weird">another audio element</audio>

        <p>Here's an <a href="../Mediocre%20Note.html">unaffected link</a>.</p>
    </body>
</html>"""
    expected = """<html>
    <head>
        <title>A Delightful Note</title>
        <meta name="created" content="2019-06-04 10:12:13 -0800" />
    </head>
    <body>
        <p>Hi! Here's a <a href="../archive/Mediocre%20Note.md">link</a> and a <img src="http://example.com/bar.png" title="picture"/>.</p>

        <video controls src="content/something.cool">a video element</video>
        <audio controls src="content/something.cool">an audio element</audio>
        <audio controls><source src="content/something.cool">another audio element</audio>

        <p>Here's an <a href="../Mediocre%20Note.html">unaffected link</a>.</p>
    </body>
</html>"""
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    acc = HTMLAccessor(path)
    acc.edit(SetTitleCmd(path, 'A Delightful Note'))
    acc.edit(SetCreatedCmd(path, datetime(2019, 6, 4, 10, 12, 13, 0, timezone(timedelta(hours=-8)))))
    acc.edit(ReplaceRefCmd(path, '../Mediocre%20Note.md', '../archive/Mediocre%20Note.md'))
    acc.edit(ReplaceRefCmd(path, 'http://example.com/foo.png', 'http://example.com/bar.png'))
    acc.edit(ReplaceRefCmd(path, 'media/something.weird', 'content/something.cool'))
    assert acc.save()
    assert BeautifulSoup(path.read_text(), 'lxml',) == BeautifulSoup(expected, 'lxml')


def test_change_tags(fs):
    doc = """<html>
    <head>
        <meta name="keywords" content="one, two"/>
    </head>
    <body>
        text
    </body>
</html>"""
    expected = """<html>
    <head>
        <meta name="keywords" content="three, two"/>
    </head>
    <body>
        text
    </body>
</html>"""
    path = Path('/fakenotes/test.html')
    fs.create_file(path, contents=doc)
    acc = HTMLAccessor(path)
    acc.edit(AddTagCmd(path, 'THREE'))
    acc.edit(DelTagCmd(path, 'ONE'))
    assert acc.save()
    assert BeautifulSoup(path.read_text(), 'lxml', ) == BeautifulSoup(expected, 'lxml')
