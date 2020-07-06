from datetime import datetime
from pathlib import Path
from notesdir.models import FileInfo
from notesdir.repos.sqlite import SqliteRepo


CONFIG = {'roots': ['/notes'], 'cache': ':memory:'}


def test_init(fs):
    repo = SqliteRepo(CONFIG)
    repo.close()


def test_info_unknown(fs):
    fs.create_file('/notes/one.md', contents='Hello')
    repo = SqliteRepo(CONFIG)
    assert repo.info(Path('/notes/two.md')) is None


def test_info_and_referrers(fs):
    doc = """---
title: A Note
created: 2012-01-02 03:04:05
...
I link to [two](two.md) and [three](../otherdir/three.md#heading) and have #two #tags."""
    path1 = Path('/notes/dir/one.md')
    path2 = Path('/notes/otherdir/three.md')
    path3 = Path('/notes/dir/two.md')
    fs.create_file(path1, contents=doc)
    fs.create_file(path2, contents='---\ntitle: Note 3\n...\n')
    repo = SqliteRepo(CONFIG)
    assert repo.info(path1) == FileInfo(
        path1,
        title='A Note',
        created=datetime(2012, 1, 2, 3, 4, 5),
        tags={'tags', 'two'},
        refs={'two.md', '../otherdir/three.md#heading'})
    assert repo.info(path2) == FileInfo(path2, title='Note 3')
    assert repo.info(path3) is None

    assert repo.referrers(path1) == set()
    assert repo.referrers(path2) == {path1}
    assert repo.referrers(path3) == {path1}


def test_refresh(fs):
    repo = SqliteRepo(CONFIG)
    path = Path('/notes/one.md')
    fs.create_file(path, contents='#hello')
    assert repo.info(path) is None
    repo.refresh()
    assert repo.info(path) == FileInfo(path, tags={'hello'})
