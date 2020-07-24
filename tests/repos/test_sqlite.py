from datetime import datetime
from pathlib import Path
from notesdir.models import FileInfo, FileQuery, SetTitleCmd, ReplaceHrefCmd, MoveCmd, FileInfoReq, LinkInfo
from notesdir.conf import SqliteRepoConf


def config():
    return SqliteRepoConf(root_paths={'/notes'}, cache_path=':memory:')


def test_init():
    config().instantiate().close()


def test_info_unknown(fs):
    fs.create_file('/notes/one.md', contents='Hello')
    repo = config().instantiate()
    assert repo.info('/notes/two.md') == FileInfo('/notes/two.md')


def test_info_and_referrers(fs):
    doc = """---
title: A Note
created: 2012-01-02 03:04:05
...
I link to [two](two.md) and [three](../otherdir/three.md#heading) and have #two #tags."""
    path1 = '/notes/dir/one.md'
    path2 = '/notes/dir/two.md'
    path3 = '/notes/otherdir/three.md'
    fs.create_file(path1, contents=doc)
    fs.create_file(path2, contents='---\ntitle: Note 2\n...\n')
    repo = config().instantiate()
    assert repo.info(path1, FileInfoReq.full()) == FileInfo(
        path1,
        title='A Note',
        created=datetime(2012, 1, 2, 3, 4, 5),
        tags={'tags', 'two'},
        links=[LinkInfo(path1, h) for h in ['../otherdir/three.md#heading', 'two.md']])
    assert repo.info(path2, FileInfoReq.full()) == FileInfo(
        path2,
        title='Note 2',
        backlinks=[LinkInfo(path1, 'two.md')])
    assert repo.info(path3, FileInfoReq.full()) == FileInfo(path3,
                                                            backlinks=[LinkInfo(path1, '../otherdir/three.md#heading')])


def test_duplicate_links(fs):
    doc = """I link to [two](two.md) [two](two.md) times."""
    path1 = '/notes/one.md'
    path2 = '/notes/two.md'
    fs.create_file(path1, contents=doc)
    repo = config().instantiate()
    assert repo.info(path1).links == [LinkInfo(path1, 'two.md'), LinkInfo(path1, 'two.md')]
    assert repo.info(path2, 'backlinks').backlinks == [LinkInfo(path1, 'two.md'), LinkInfo(path1, 'two.md')]


def test_invalidate(fs):
    repo = config().instantiate()
    path = '/notes/one.md'
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path)
    fs.create_file(path, contents='#hello [link](foo.md)')
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path)
    repo.invalidate()
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path, tags={'hello'}, links=[LinkInfo(path, 'foo.md')])
    repo.invalidate()
    Path(path).write_text('#goodbye')
    repo.invalidate()
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path, tags={'goodbye'})


def test_query(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2 #tag4')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = config().instantiate()
    paths = {i.path for i in repo.query(FileQuery())}
    assert paths == {'/notes/one.md', '/notes/two.md', '/notes/three.md'}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3'))}
    assert paths == {'/notes/two.md', '/notes/three.md'}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag1,tag4'))}
    assert paths == {'/notes/one.md', '/notes/three.md'}
    assert not list(repo.query(FileQuery.parse('tag:bogus')))
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2'))}
    assert paths == {'/notes/two.md', '/notes/three.md'}
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2,tag4'))}
    assert paths == {'/notes/two.md'}
    assert not list(repo.query(FileQuery.parse('-tag:tag1')))
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3 -tag:tag4'))}
    assert paths == {'/notes/two.md'}

    assert [Path(i.path).name for i in repo.query('sort:filename')] == ['one.md', 'three.md', 'two.md']


def test_tag_counts(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = config().instantiate()
    assert repo.tag_counts(FileQuery()) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert repo.tag_counts(FileQuery.parse('tag:tag3')) == {'tag1': 2, 'tag3': 2, 'tag4': 1}


def test_change(fs):
    fs.cwd = '/notes'
    path1 = '/notes/one.md'
    path2 = '/notes/two.md'
    path3 = '/notes/moved.md'
    fs.create_file(path1, contents='[1](old)')
    fs.create_file(path2, contents='[2](foo)')
    edits = [SetTitleCmd(path1, 'New Title'),
             ReplaceHrefCmd(path1, 'old', 'new'),
             MoveCmd(path1, path3),
             ReplaceHrefCmd(path2, 'foo', 'bar')]
    repo = config().instantiate()
    repo.change(edits)
    assert not Path(path1).exists()
    assert Path(path3).read_text() == '---\ntitle: New Title\n...\n[1](new)'
    assert Path(path2).read_text() == '[2](bar)'
    assert repo.info(path1, FileInfoReq.full()) == FileInfo(path1)
    assert repo.info(path3, FileInfoReq.full()) == FileInfo(path3, title='New Title', links=[LinkInfo(path3, 'new')])
    assert repo.info(path2, FileInfoReq.full()) == FileInfo(path2, links=[LinkInfo(path2, 'bar')])
    assert repo.info('old', FileInfoReq.full()) == FileInfo('/notes/old')
    assert repo.info('foo', FileInfoReq.full()) == FileInfo('/notes/foo')
    assert repo.info('new', FileInfoReq.full()) == FileInfo('/notes/new', backlinks=[LinkInfo(path3, 'new')])
    assert repo.info('bar', FileInfoReq.full()) == FileInfo('/notes/bar', backlinks=[LinkInfo(path2, 'bar')])
    # regression test for bug where invalidate removed entries for files that were referred to
    # only by files that had not been changed
    repo.invalidate()
    assert repo.info('new', FileInfoReq.full()) == FileInfo('/notes/new', backlinks=[LinkInfo(path3, 'new')])
    assert repo.info('bar', FileInfoReq.full()) == FileInfo('/notes/bar', backlinks=[LinkInfo(path2, 'bar')])


def test_ignore(fs):
    path1 = '/notes/one.md'
    path2 = '/notes/.two.md'
    fs.create_file(path1, contents='I link to [two](.two.md)')
    fs.create_file(path2, contents='I link to [one](one.md)')
    with config().instantiate() as repo:
        assert list(repo.query()) == [repo.info(path1)]
        assert not repo.info(path1, FileInfoReq.full()).backlinks
        assert repo.info(path2, FileInfoReq.full()).backlinks == [LinkInfo(path1, '.two.md')]
    conf = config()
    conf.ignore = lambda _1, _2: False
    with conf.instantiate() as repo:
        assert list(repo.query()) == [repo.info(path1), repo.info(path2)]
        assert repo.info(path1, FileInfoReq.full()).backlinks == [LinkInfo(path2, 'one.md')]
        assert repo.info(path2, FileInfoReq.full()).backlinks == [LinkInfo(path1, '.two.md')]


def test_skip_parse(fs):
    path1 = '/notes/one.md'
    path2 = '/notes/one.md.resources/two.md'
    path3 = '/notes/skip.md'
    fs.create_file(path1, contents='---\ntitle: Note One\n...\n')
    fs.create_file(path2, contents='---\ntitle: Note Two\n...\n')
    fs.create_file(path3, contents='---\ntitle: Note Skip\n...\n')

    def fn(parentpath, filename):
        return filename.endswith('.resources') or filename == 'skip.md'

    conf = config()
    conf.skip_parse = fn
    with conf.instantiate() as repo:
        assert list(repo.query('sort:path')) == [
            FileInfo(path1, title='Note One'),
            FileInfo(path2),
            FileInfo(path3)
        ]
        assert repo.info(path1) == FileInfo(path1, title='Note One')
        assert repo.info(path2) == FileInfo(path2)
        assert repo.info(path3) == FileInfo(path3)
