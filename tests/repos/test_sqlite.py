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
    assert repo.info(Path('/notes/two.md')) == FileInfo(Path('/notes/two.md'))


def test_info_and_referrers(fs):
    doc = """---
title: A Note
created: 2012-01-02 03:04:05
...
I link to [two](two.md) and [three](../otherdir/three.md#heading) and have #two #tags."""
    path1 = Path('/notes/dir/one.md')
    path2 = Path('/notes/dir/two.md')
    path3 = Path('/notes/otherdir/three.md')
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
    path1 = Path('/notes/one.md')
    path2 = Path('/notes/two.md')
    fs.create_file(path1, contents=doc)
    repo = config().instantiate()
    assert repo.info(path1).links == [LinkInfo(path1, 'two.md'), LinkInfo(path1, 'two.md')]
    assert repo.info(path2, 'backlinks').backlinks == [LinkInfo(path1, 'two.md'), LinkInfo(path1, 'two.md')]


def test_refresh(fs):
    repo = config().instantiate()
    path = Path('/notes/one.md')
    fs.create_file(path, contents='#hello [link](foo.md)')
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path)
    repo.refresh()
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path, tags={'hello'}, links=[LinkInfo(path, 'foo.md')])
    repo.refresh()
    path.write_text('#goodbye')
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path, tags={'hello'}, links=[LinkInfo(path, 'foo.md')])
    repo.refresh()
    assert repo.info(path, FileInfoReq.full()) == FileInfo(path, tags={'goodbye'})


def test_query(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2 #tag4')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = config().instantiate()
    paths = {i.path for i in repo.query(FileQuery())}
    assert paths == {Path('/notes/one.md'), Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag1,tag4'))}
    assert paths == {Path('/notes/one.md'), Path('/notes/three.md')}
    assert not list(repo.query(FileQuery.parse('tag:bogus')))
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2'))}
    assert paths == {Path('/notes/two.md'), Path('/notes/three.md')}
    paths = {i.path for i in repo.query(FileQuery.parse('-tag:tag2,tag4'))}
    assert paths == {Path('/notes/two.md')}
    assert not list(repo.query(FileQuery.parse('-tag:tag1')))
    paths = {i.path for i in repo.query(FileQuery.parse('tag:tag3 -tag:tag4'))}
    assert paths == {Path('/notes/two.md')}


def test_tag_counts(fs):
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    repo = config().instantiate()
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
             ReplaceHrefCmd(path1, 'old', 'new'),
             MoveCmd(path1, path3),
             ReplaceHrefCmd(path2, 'foo', 'bar')]
    repo = config().instantiate()
    repo.change(edits)
    assert not path1.exists()
    assert path3.read_text() == '---\ntitle: New Title\n...\n[1](new)'
    assert path2.read_text() == '[2](bar)'
    assert repo.info(path1, FileInfoReq.full()) == FileInfo(path1)
    assert repo.info(path3, FileInfoReq.full()) == FileInfo(path3, title='New Title', links=[LinkInfo(path3, 'new')])
    assert repo.info(path2, FileInfoReq.full()) == FileInfo(path2, links=[LinkInfo(path2, 'bar')])
    assert repo.info(Path('old'), FileInfoReq.full()) == FileInfo(Path('/notes/old'))
    assert repo.info(Path('foo'), FileInfoReq.full()) == FileInfo(Path('/notes/foo'))
    assert repo.info(Path('new'), FileInfoReq.full()) == FileInfo(Path('/notes/new'),
                                                                  backlinks=[LinkInfo(path3, 'new')])
    assert repo.info(Path('bar'), FileInfoReq.full()) == FileInfo(Path('/notes/bar'),
                                                                  backlinks=[LinkInfo(path2, 'bar')])
    # regression test for bug where refresh removed entries for files that were referred to
    # only by files that had not been changed
    repo.refresh()
    assert repo.info(Path('new'), FileInfoReq.full()) == FileInfo(Path('/notes/new'),
                                                                  backlinks=[LinkInfo(path3, 'new')])
    assert repo.info(Path('bar'), FileInfoReq.full()) == FileInfo(Path('/notes/bar'),
                                                                  backlinks=[LinkInfo(path2, 'bar')])


def test_skip_parse(fs):
    path1 = Path('/notes/one.md')
    path2 = Path('/notes/skip.md')
    path3 = Path('/notes/moved.md')
    fs.create_file(path1, contents='I have #tags and a [link](skip.md).')
    fs.create_file(path2, contents='I #also have #tags.')
    conf = config()
    conf.skip_parse = lambda p: p.stem == 'skip'
    repo = conf.instantiate()
    assert repo.info(path1, FileInfoReq.full()) == FileInfo(path1, tags={'tags'}, links=[LinkInfo(path1, 'skip.md')])
    assert repo.info(path2, FileInfoReq.full()) == FileInfo(path2, backlinks=[LinkInfo(path1, 'skip.md')])
    assert repo.info(path3, FileInfoReq.full()) == FileInfo(path3)
    assert not list(repo.query(FileQuery(include_tags={'also'})))
    repo.change([ReplaceHrefCmd(path1, original='skip.md', replacement='moved.md'), MoveCmd(path2, path3)])
    assert repo.info(path1, FileInfoReq.full()) == FileInfo(path1, tags={'tags'}, links=[LinkInfo(path1, 'moved.md')])
    assert repo.info(path2, FileInfoReq.full()) == FileInfo(path2)
    assert repo.info(path3, FileInfoReq.full()) == FileInfo(
        path3, tags={'also', 'tags'}, backlinks=[LinkInfo(path1, 'moved.md')])
    assert list(repo.query(FileQuery(include_tags={'also'}))) == [repo.info(path3)]
