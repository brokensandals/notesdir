from datetime import datetime
from pathlib import Path
from notesdir.models import FileInfo, FileQuery
from notesdir.repos.sqlite import SqliteRepo


CONFIG = {'roots': ['/notes'], 'cache': ':memory:'}


def test_init():
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
    fs.create_file(path, contents='#hello [link](foo.md)')
    assert repo.info(path) is None
    repo.refresh()
    assert repo.info(path) == FileInfo(path, tags={'hello'}, refs={'foo.md'})
    repo.refresh()
    path.write_text('#goodbye')
    assert repo.info(path) == FileInfo(path, tags={'hello'}, refs={'foo.md'})
    repo.refresh()
    assert repo.info(path) == FileInfo(path, tags={'goodbye'})


def test_query(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2 #tag4')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = SqliteRepo(CONFIG)
    paths = {i.path for i in repo.query(FileQuery())}
    assert paths == {Path('/notes/one.md'), Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag1,tag4'))}
    assert paths == {Path('/notes/one.md'), Path('/notes/three.md')}
    assert not repo.query(FileQuery.parse('tag:bogus'))
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2,tag4'))}
    assert paths == {Path('/notes/two.md')}
    assert not repo.query(FileQuery.parse('-tag:tag1'))
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3 -tag:tag4'))}
    assert paths == {Path('/notes/two.md')}


def test_tag_counts(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = SqliteRepo(CONFIG)
    assert repo.tag_counts(FileQuery()) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert repo.tag_counts(FileQuery.parse('tag:tag3')) == {'tag1': 2, 'tag3': 2, 'tag4': 1}
