from datetime import datetime
from pathlib import Path
from notesdir.models import FileInfo, FileQuery, SetTitleCmd, ReplaceRefCmd, MoveCmd
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


def test_change(fs):
    fs.cwd = '/notes'
    path1 = Path('/notes/one.md')
    path2 = Path('/notes/two.md')
    path3 = Path('/notes/moved.md')
    fs.create_file(path1, contents='[1](old)')
    fs.create_file(path2, contents='[2](foo)')
    edits = [SetTitleCmd(path1, 'New Title'),
             ReplaceRefCmd(path1, 'old', 'new'),
             MoveCmd(path1, path3),
             ReplaceRefCmd(path2, 'foo', 'bar')]
    repo = SqliteRepo(CONFIG)
    repo.change(edits)
    assert not path1.exists()
    assert path3.read_text() == '---\ntitle: New Title\n...\n[1](new)'
    assert path2.read_text() == '[2](bar)'
    assert repo.info(path1) is None
    assert repo.info(path3) == FileInfo(path3, title='New Title', refs={'new'})
    assert repo.info(path2) == FileInfo(path2, refs={'bar'})
    assert repo.info(Path('old')) is None
    assert repo.info(Path('foo')) is None
    assert repo.info(Path('new')) is None
    assert repo.info(Path('bar')) is None
    assert repo.referrers(Path('old')) == set()
    assert repo.referrers(Path('foo')) == set()
    assert repo.referrers(Path('new')) == {path3}
    assert repo.referrers(Path('bar')) == {path2}
    # regression test for bug where refresh removed entries for files that were referred to
    # only by files that had not been changed
    repo.refresh()
    assert repo.referrers(Path('new')) == {path3}
    assert repo.referrers(Path('bar')) == {path2}


def test_noparse(fs):
    path1 = Path('/notes/one.md')
    path2 = Path('/notes/skip.md')
    path3 = Path('/notes/moved.md')
    fs.create_file(path1, contents='I have #tags and a [link](skip.md).')
    fs.create_file(path2, contents='I #also have #tags.')
    repo = SqliteRepo({**CONFIG, 'noparse': ['skip']})
    assert repo.info(path1) == FileInfo(path1, tags={'tags'}, refs={'skip.md'})
    assert repo.info(path2) == FileInfo(path2)
    assert repo.info(path3) is None
    assert repo.referrers(path2) == {path1}
    assert repo.query(FileQuery(include_tags={'also'})) == []
    repo.change([ReplaceRefCmd(path1, original='skip.md', replacement='moved.md'), MoveCmd(path2, path3)])
    assert repo.info(path1) == FileInfo(path1, tags={'tags'}, refs={'moved.md'})
    assert repo.info(path2) is None
    assert repo.info(path3) == FileInfo(path3, tags={'also', 'tags'})
    assert repo.referrers(path3) == {path1}
    assert repo.query(FileQuery(include_tags={'also'})) == [repo.info(path3)]
