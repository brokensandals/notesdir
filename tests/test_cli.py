from datetime import datetime
import json
from pathlib import Path
import re
from freezegun import freeze_time
import pytest
from notesdir import cli
from notesdir.models import FileInfo


def nd_setup(fs):
    fs.cwd = '/notes/cwd'
    Path('~').expanduser().mkdir(parents=True)
    Path('~/.notesdir.toml').expanduser().write_text("""
        repo.roots = ["/notes"]
    """)


def test_help(capsys):
    """Writes usage info to the doc/ folder."""
    doc = Path('doc')
    with pytest.raises(SystemExit):
        cli.main(['-h'])
    cap = capsys.readouterr()
    doc.joinpath('usage.txt').write_text(
        re.sub(r'\S*pytest\S*', 'notesdir', cap.out))
    cmds = re.search('\\{(.+)\\}', cap.out).group(1)
    for cmd in cmds.split(','):
        with pytest.raises(SystemExit):
            cli.main([cmd, '-h'])
        cap = capsys.readouterr()
        doc.joinpath(f'usage-{cmd}.txt').write_text(
            re.sub(r'\S*pytest\S*', 'notesdir', cap.out))


def test_i(fs, capsys):
    nd_setup(fs)
    path1 = Path('/notes/cwd/one.md')
    path2 = Path('/notes/cwd/two.md')
    doc1 = """---
title: A Note
created: 2001-02-03 04:05:06
...
I have #some #boring-tags and [a link](two.md#heading)."""
    doc2 = """I link to [one](one.md)."""
    fs.create_file(path1, contents=doc1)
    fs.create_file(path2, contents=doc2)
    assert cli.main(['i', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert out == """path: one.md
title: A Note
created: 2001-02-03 04:05:06
tags: boring-tags, some
refs:
\ttwo.md#heading -> /notes/cwd/two.md
referrers:
\t/notes/cwd/two.md
"""
    assert cli.main(['i', '-f', 'title,tags', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert out == "title: A Note\ntags: boring-tags, some\n"
    assert cli.main(['i', '-j', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {
        'path': 'one.md',
        'title': 'A Note',
        'created': '2001-02-03T04:05:06',
        'tags': ['boring-tags', 'some'],
        'refs': ['two.md#heading'],
        'referrers': {
            '/notes/cwd/two.md': ['one.md']
        }
    }


def test_mv_file(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/subdir/old.md')
    fs.create_file('/notes/dir/referrer.md', contents='I have a [link](../cwd/subdir/old.md).')
    assert cli.main(['mv', 'subdir/old.md', '../dir/new.md']) == 0
    assert not Path('/notes/cwd/subdir/old.md').exists()
    assert Path('/notes/dir/new.md').exists()
    assert Path('/notes/dir/referrer.md').read_text() == 'I have a [link](new.md).'
    out, err = capsys.readouterr()
    assert not out


def test_mv_file_to_dir(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/subdir/old.md')
    fs.create_file('/notes/dir/referrer.md', contents='I have a [link](../cwd/subdir/old.md).')
    assert cli.main(['mv', 'subdir/old.md', '../dir']) == 0
    assert not Path('/notes/cwd/subdir/old.md').exists()
    assert Path('/notes/dir/old.md').exists()
    assert Path('/notes/dir/referrer.md').read_text() == 'I have a [link](old.md).'
    out, err = capsys.readouterr()
    assert 'Moved subdir/old.md to ../dir/old.md' in out


def test_mv_file_conflict(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/referrer.md', contents='I have a [link](foo.md).')
    fs.create_file('/notes/cwd/foo.md', contents='foo')
    fs.create_file('/notes/dir/bar.md', contents='bar')
    fs.create_file('/notes/dir/2-bar.md', contents='baz')
    assert cli.main(['mv', 'foo.md', '../dir/bar.md']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/bar.md').read_text() == 'bar'
    assert Path('/notes/dir/2-bar.md').read_text() == 'baz'
    assert Path('/notes/dir/3-bar.md').read_text() == 'foo'
    assert Path('/notes/cwd/referrer.md').read_text() == 'I have a [link](../dir/3-bar.md).'
    out, err = capsys.readouterr()
    assert 'Moved foo.md to ../dir/3-bar.md' in out


def test_mv_file_to_dir_conflict(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/referrer.md', contents='I have a [link](foo.md).')
    fs.create_file('/notes/cwd/foo.md', contents='foo')
    fs.create_file('/notes/dir/foo.md', contents='bar')
    assert cli.main(['mv', 'foo.md', '../dir']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/foo.md').read_text() == 'bar'
    assert Path('/notes/dir/2-foo.md').read_text() == 'foo'
    assert Path('/notes/cwd/referrer.md').read_text() == 'I have a [link](../dir/2-foo.md).'
    out, err = capsys.readouterr()
    assert 'Moved foo.md to ../dir/2-foo.md' in out


def test_mv_file_to_dir_startswith_conflict(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo.md')
    Path('/notes/dir/foo.md.resources').mkdir(exist_ok=True, parents=True)
    assert cli.main(['mv', 'foo.md', '../dir']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/2-foo.md').exists()
    assert Path('/notes/dir/foo.md.resources').is_dir()
    out, err = capsys.readouterr()
    assert 'Moved foo.md to ../dir/2-foo.md' in out


def test_mv_with_resources(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo.md', contents='I have an [attachment](foo.md.resources/blah.txt).')
    fs.create_file('/notes/cwd/foo.md.resources/blah.txt', contents='Yo')
    fs.create_file('/notes/cwd/bar.md', contents='This is a [bad idea](foo.md.resources/blah.txt).')
    fs.create_file('/notes/dir/foo.md', contents='I conflict!')
    Path('/notes/dir').mkdir(exist_ok=True, parents=True)
    assert cli.main(['mv', '-j', 'foo.md', '../dir']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert not Path('/notes/cwd/foo.md.resources').exists()
    assert Path('/notes/dir/foo.md').read_text() == 'I conflict!'
    assert Path('/notes/dir/2-foo.md').read_text() == 'I have an [attachment](2-foo.md.resources/blah.txt).'
    assert Path('/notes/dir/2-foo.md.resources/blah.txt').read_text() == 'Yo'
    assert Path('/notes/cwd/bar.md').read_text() == 'This is a [bad idea](../dir/2-foo.md.resources/blah.txt).'
    out, err = capsys.readouterr()
    assert json.loads(out) == {'foo.md': '../dir/2-foo.md', 'foo.md.resources': '../dir/2-foo.md.resources'}


def test_mv_creation_folders(fs, capsys):
    doc = '---\ncreated: 2013-04-05 06:07:08\n...\nsome text'
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo.md', contents=doc)
    assert cli.main(['mv', '-c', 'foo.md', '../blah.md']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/2013/04/blah.md').read_text() == doc
    out, err = capsys.readouterr()
    assert 'Moved foo.md to ../2013/04/blah.md' in out


@freeze_time('2012-03-04T05:06:07-0800')
def test_mv_c_unrecognized(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/garbage.garbage')
    assert cli.main(['mv', '-c', 'garbage.garbage', '..']) == 0
    assert not Path('/notes/cwd/garbage.garbage').exists()
    assert Path('/notes/2012/03/garbage.garbage').exists()
    out, err = capsys.readouterr()
    assert 'Moved garbage.garbage to ../2012/03/garbage.garbage' in out


def test_norm_nothing(fs, capsys):
    doc = """---
created: 2001-02-03T04:05:06Z
title: Foo Bar
...
some text"""
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo-bar.md', contents=doc)
    assert cli.main(['norm', 'foo-bar.md']) == 0
    assert Path('/notes/cwd/foo-bar.md').read_text() == doc
    out, err = capsys.readouterr()
    assert not out


@freeze_time('2012-03-04T05:06:07-0800')
def test_norm_missing_attrs(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo-bar.md', contents='some text')
    assert cli.main(['norm', 'foo-bar.md']) == 0
    assert Path('/notes/cwd/foo-bar.md').read_text() == """---
created: 2012-03-04 13:06:07
title: foo-bar
...
some text"""
    out, err = capsys.readouterr()
    assert not out


def test_norm_move(fs, capsys):
    doc = """---
created: 2012-03-04 05:06:07
title: Foo Bar! Hooray!
...
some text"""
    nd_setup(fs)
    fs.create_file('/notes/cwd/foobar.md', contents=doc)
    assert cli.main(['norm', '-j', 'foobar.md']) == 0
    assert not Path('/notes/cwd/foobar.md').exists()
    assert Path('/notes/cwd/foo-bar-hooray.md').read_text() == doc
    out, err = capsys.readouterr()
    assert json.loads(out) == {'foobar.md': 'foo-bar-hooray.md'}


def test_norm_move_and_set_title(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/+foo-Bar-.md', contents="""---
created: 2012-03-04 05:06:07
...
some text""")
    assert cli.main(['norm', '+foo-Bar-.md']) == 0
    assert not Path('/notes/cwd/+foo-Bar-.md').exists()
    assert Path('/notes/cwd/foo-bar.md').read_text() == """---
created: 2012-03-04 05:06:07
title: +foo-Bar-
...
some text"""
    out, err = capsys.readouterr()
    assert 'Moved +foo-Bar-.md to foo-bar.md' in out


def test_tags(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo.md')
    assert cli.main(['t+', 'One,two, , three', 'foo.md']) == 0
    assert Path('/notes/cwd/foo.md').read_text() == '---\nkeywords:\n- one\n- three\n- two\n...\n'
    assert cli.main(['t-', 'oNe,tWo', 'foo.md']) == 0
    assert Path('/notes/cwd/foo.md').read_text() == '---\nkeywords:\n- three\n...\n'


def test_tags_count(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    assert cli.main(['tc', '-j']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert cli.main(['tc']) == 0
    out, err = capsys.readouterr()
    assert out

    assert cli.main(['tc', '-j', 'tag:tag3']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {'tag1': 2, 'tag3': 2, 'tag4': 1}
    assert cli.main(['tc', 'tag:tag3']) == 0
    out, err = capsys.readouterr()
    assert out


def test_query(fs, capsys):
    nd_setup(fs)
    doc1 = """---
title: A Test File
created: 2012-03-04 05:06:07
keywords:
- has space
- cool
...
This is a test doc."""
    doc2 = 'Another #test doc.'
    path1 = '/notes/cwd/subdir/one.md'
    path2 = '/notes/two.md'
    fs.create_file(path1, contents=doc1)
    fs.create_file(path2, contents=doc2)
    assert cli.main(['q', '-j']) == 0
    out, err = capsys.readouterr()
    expected1 = FileInfo(path=path1,
                         title='A Test File',
                         created=datetime(2012, 3, 4, 5, 6, 7),
                         tags=['cool', 'has space']).as_json()
    assert json.loads(out) == [expected1, FileInfo(path=path2, tags=['test']).as_json()]
    assert cli.main(['q']) == 0
    out, err = capsys.readouterr()
    assert out

    assert cli.main(['q', '-j', 'tag:has+space']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == [expected1]
    assert cli.main(['q', 'tag:has+space']) == 0
    out, err = capsys.readouterr()
    assert out
