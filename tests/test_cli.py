from datetime import datetime
import json
import itertools
from pathlib import Path
from freezegun import freeze_time
from notesdir import cli
from notesdir.models import FileInfo, CreateCmd, ReplaceHrefCmd, MoveCmd, AddTagCmd, DelTagCmd, SetTitleCmd,\
    SetCreatedCmd


def nd_setup(fs, extra_conf=''):
    fs.cwd = '/notes/cwd'
    Path(fs.cwd).mkdir(parents=True)
    Path('~').expanduser().mkdir(parents=True)
    Path('~/.notesdir.conf.py').expanduser().write_text("""
from notesdir.conf import *
conf = NotesdirConf(
    repo_conf=SqliteRepoConf(
        root_paths={'/notes'},
        cache_path=':memory:'
    ),
    
    template_globs={'/notes/templates/*.mako'}
)
""" + extra_conf)


def test_info(fs, capsys):
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
    assert cli.main(['info', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert out == """path: /notes/cwd/one.md
title: A Note
created: 2001-02-03 04:05:06
tags: boring-tags, some
links:
\ttwo.md#heading -> /notes/cwd/two.md
backlinks:
\t/notes/cwd/two.md
"""
    assert cli.main(['info', '-f', 'title,tags', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert out == "title: A Note\ntags: boring-tags, some\n"
    assert cli.main(['info', '-j', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {
        'path': '/notes/cwd/one.md',
        'title': 'A Note',
        'created': '2001-02-03T04:05:06',
        'tags': ['boring-tags', 'some'],
        'links': [{'referrer': '/notes/cwd/one.md', 'href': 'two.md#heading', 'referent': '/notes/cwd/two.md'}],
        'backlinks': [{'referrer': '/notes/cwd/two.md', 'href': 'one.md', 'referent': '/notes/cwd/one.md'}]
    }


def test_path_rewrite(fs, capsys):
    nd_setup(fs, extra_conf="""
conf.cli_path_output_rewriter = lambda path: path.replace('/notes/cwd/', '/newbasepath/')
""")
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
    assert cli.main(['info', 'one.md']) == 0
    out, err = capsys.readouterr()
    assert out == """path: /newbasepath/one.md
title: A Note
created: 2001-02-03 04:05:06
tags: boring-tags, some
links:
\ttwo.md#heading -> /newbasepath/two.md
backlinks:
\t/newbasepath/two.md
"""

    template = "<% directives.dest = '/notes/cwd/created.md' %>"
    fs.create_file('/notes/templates/empty.md.mako', contents=template)
    assert cli.main(['new', 'empty']) == 0
    out, err = capsys.readouterr()
    assert out == 'Created /newbasepath/created.md\n'


@freeze_time('2012-05-02T03:04:05Z')
def test_new(fs, capsys, mocker):
    mocker.patch('shortuuid.uuid', side_effect=(f'uuid{i}' for i in itertools.count(1)))
    template = """<% from datetime import datetime %>\
---
title: Testing in ${datetime.now().strftime('%B %Y')}
...
Nothing to see here, move along."""
    simple_expected = """---
title: Testing in May 2012
...
Nothing to see here, move along."""
    nd_setup(fs)
    fs.create_file('/notes/templates/simple.md.mako', contents=template)
    assert cli.main(['new', 'simple']) == 0
    out, err = capsys.readouterr()
    assert out == 'Created /notes/cwd/simple.md\n'
    assert Path('/notes/cwd/simple.md').read_text() == simple_expected
    assert cli.main(['new', 'simple']) == 0
    out, err = capsys.readouterr()
    assert out == 'Created /notes/cwd/simple_uuid1.md\n'
    assert Path('/notes/cwd/simple_uuid1.md').exists()

    template2 = """All current tags: ${', '.join(sorted(nd.repo.tag_counts().keys()))}"""
    fs.create_file('/notes/other-template.md.mako', contents=template2)
    fs.create_file('/notes/one.md', contents='#happy #sad #melancholy')
    fs.create_file('/notes/two.md', contents='#green #bright-green #best-green')
    assert cli.main(['new', '../other-template.md.mako', 'tags.md']) == 0
    out, err = capsys.readouterr()
    assert out == 'Created /notes/cwd/tags.md\n'
    assert (Path('/notes/cwd/tags.md').read_text()
            == """All current tags: best-green, bright-green, green, happy, melancholy, sad""")

    template3 = """<%
    from pathlib import Path
    directives.dest = Path(template_path).parent.parent.joinpath('cool-note.md')
%>"""
    fs.create_file('/notes/templates/self-namer.md.mako', contents=template3)
    assert cli.main(['new', 'self-namer', 'unimportant.md']) == 0
    out, err = capsys.readouterr()
    assert out == 'Created /notes/cool-note.md\n'
    assert Path('/notes/cool-note.md').is_file()
    assert not Path('unimportant.md').exists()

    assert cli.main(['new', '-p', 'simple', 'no.md']) == 0
    assert not Path('no.md').exists()
    out, err = capsys.readouterr()
    assert out == str(CreateCmd('/notes/cwd/no.md', contents=simple_expected)) + '\n'


def test_mv_file(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/subdir/old.md')
    fs.create_file('/notes/dir/referrer.md', contents='I have a [link](../cwd/subdir/old.md).')
    assert cli.main(['mv', '-p', 'subdir/old.md', '../dir/new.md']) == 0
    assert Path('/notes/cwd/subdir/old.md').exists()
    assert Path('/notes/dir/referrer.md').read_text() == 'I have a [link](../cwd/subdir/old.md).'
    out, err = capsys.readouterr()
    assert out == (str(ReplaceHrefCmd('/notes/dir/referrer.md', '../cwd/subdir/old.md', 'new.md')) + '\n'
                   + str(MoveCmd('/notes/cwd/subdir/old.md', '/notes/dir/new.md')) + '\n')

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


def test_mv_file_conflict(fs, capsys, mocker):
    mocker.patch('shortuuid.uuid', side_effect=(f'uuid{i}' for i in itertools.count(1)))
    nd_setup(fs)
    fs.create_file('/notes/cwd/referrer.md', contents='I have a [link](foo.md).')
    fs.create_file('/notes/cwd/foo.md', contents='foo')
    fs.create_file('/notes/dir/bar.md', contents='bar')
    assert cli.main(['mv', 'foo.md', '../dir/bar.md']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/bar_uuid1.md').read_text() == 'foo'
    assert Path('/notes/dir/bar.md').read_text() == 'bar'
    assert Path('/notes/cwd/referrer.md').read_text() == 'I have a [link](../dir/bar_uuid1.md).'
    out, err = capsys.readouterr()
    assert 'Moved foo.md to ../dir/bar_uuid1.md' in out


def test_mv_file_to_dir_conflict(fs, capsys, mocker):
    mocker.patch('shortuuid.uuid', side_effect=(f'uuid{i}' for i in itertools.count(1)))
    nd_setup(fs)
    fs.create_file('/notes/cwd/referrer.md', contents='I have a [link](foo.md).')
    fs.create_file('/notes/cwd/foo.md', contents='foo')
    fs.create_file('/notes/dir/foo.md', contents='bar')
    assert cli.main(['mv', 'foo.md', '../dir']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/foo.md').read_text() == 'bar'
    assert Path('/notes/dir/foo_uuid1.md').read_text() == 'foo'
    assert Path('/notes/cwd/referrer.md').read_text() == 'I have a [link](../dir/foo_uuid1.md).'
    out, err = capsys.readouterr()
    assert 'Moved foo.md to ../dir/foo_uuid1.md' in out


def test_org_no_function(fs, capsys):
    nd_setup(fs)
    path1 = Path('/notes/cwd/one.md')
    path2 = Path('/notes/cwd/two.md')
    fs.create_file(path1)
    fs.create_file(path2)
    assert cli.main(['organize', '-j']) == 0
    assert path1.exists()
    assert path2.exists()
    out, err = capsys.readouterr()
    assert json.loads(out) == {}


def test_org_simple(fs, capsys, mocker):
    mocker.patch('shortuuid.uuid', side_effect=(f'uuid{i}' for i in itertools.count(1)))
    nd_setup(fs, extra_conf="""
conf.path_organizer = lambda info: info.path.replace('hi', 'hello')
""")
    path1 = Path('/notes/cwd/one.md')
    path2 = Path('/notes/cwd/two.md')
    fs.create_file(path1)
    fs.create_file(path2, contents='I link to [hi](hi.md).')
    assert cli.main(['organize', '-j']) == 0
    assert path1.is_file()
    assert path2.is_file()
    out, err = capsys.readouterr()
    assert json.loads(out) == {}

    path3 = Path('/notes/cwd/hi.md')
    path4 = Path('/notes/cwd/hello.md')
    fs.create_file(path3, contents='I link to [one](one.md).')
    assert cli.main(['organize', '-p']) == 0
    assert path3.exists()
    assert not path4.exists()
    out, err = capsys.readouterr()
    assert out == (str(ReplaceHrefCmd(str(path2), 'hi.md', 'hello.md')) + '\n'
                   + str(MoveCmd(str(path3), str(path4), create_parents=True, delete_empty_parents=True)) + '\n')
    assert cli.main(['organize', '-j']) == 0
    assert path1.is_file()
    assert path2.read_text() == 'I link to [hi](hello.md).'
    assert not path3.exists()
    assert path4.read_text() == 'I link to [one](one.md).'
    capsys.readouterr()

    path5 = Path('/notes/cwd/hello_uuid1.md')
    fs.create_file(path3, contents='I am a duplicate name')
    assert cli.main(['organize', '-j']) == 0
    assert not path3.exists()
    assert path4.read_text() == 'I link to [one](one.md).'
    assert path5.read_text() == 'I am a duplicate name'
    out, err = capsys.readouterr()
    assert json.loads(out) == {'/notes/cwd/hi.md': '/notes/cwd/hello_uuid1.md'}


def test_org_dirs(fs, capsys):
    nd_setup(fs, extra_conf="""
import os.path
conf.path_organizer =\
    lambda info: f'/notes/{sorted(info.tags)[0] if info.tags else "untagged"}/{os.path.split(info.path)[1]}'
""")
    path1 = Path('/notes/cwd/one.md')
    path2 = Path('/notes/cwd/two.md')
    fs.create_file(path1, contents='I link to [two](two.md).')
    fs.create_file(path2, contents='I link to [one](one.md).')
    assert cli.main(['organize']) == 0
    capsys.readouterr()
    assert not Path.cwd().exists()  # at one point I had a special case to prevent this, but... meh
    assert [p for p in [path1, path2] if p.exists()] == []
    path3 = Path('/notes/untagged/one.md')
    path4 = Path('/notes/untagged/two.md')
    assert path3.read_text() == 'I link to [two](two.md).'
    assert path4.read_text() == 'I link to [one](one.md).'

    path3.write_text('I link to [two](two.md) and am tagged #happy!')
    path4.write_text('I link to [one](one.md) and am tagged #sad:(')
    assert cli.main(['organize', '-j']) == 0
    assert not any(p for p in [Path('/notes/untagged'), path1, path2, path3, path4] if p.exists())
    path5 = Path('/notes/happy/one.md')
    path6 = Path('/notes/sad/two.md')
    assert path5.read_text() == 'I link to [two](../sad/two.md) and am tagged #happy!'
    assert path6.read_text() == 'I link to [one](../happy/one.md) and am tagged #sad:('
    out, err = capsys.readouterr()
    assert json.loads(out) == {str(path3): str(path5), str(path4): str(path6)}


def test_org_recommended(fs, capsys):
    nd_setup(fs, extra_conf="""
def path_organizer(info):
    path = rewrite_name_using_title(info)
    return resource_path_fn(path) or path
conf.path_organizer = path_organizer
""")
    paths1 = [Path('/notes/I Will Be Renamed.md'),
              Path('/notes/I Will Be Renamed.md.resources/I Will Not.png'),
              Path('/notes/I Will Be Renamed.md.resources/weird'),
              Path('/notes/I Will Be Renamed.md.resources/weird.resources/blah.txt')]
    for path in paths1:
        fs.create_file(path)
    paths1[0].write_text('---\ntitle: New Name\n...\n')
    assert cli.main(['organize', '-j']) == 0
    assert [p for p in paths1 if p.exists()] == []
    paths2 = [Path('/notes/new-name.md'), Path('/notes/new-name.md.resources/I Will Not.png'),
              Path('/notes/new-name.md.resources/weird'), Path('/notes/new-name.md.resources/weird.resources/blah.txt')]
    assert [p for p in paths2 if p.exists()] == paths2
    out, err = capsys.readouterr()
    assert json.loads(out) == {str(paths1[i]): str(paths2[i]) for i in range(4)}


def test_org_conflict(fs, capsys, mocker):
    mocker.patch('shortuuid.uuid', side_effect=(f'uuid{i}abcdefghijklmnopq' for i in itertools.count(1)))
    nd_setup(fs, extra_conf='conf.path_organizer = lambda x: "/notes/foo.md"')
    paths = [Path('/notes/one.md'), Path('/notes/two.md')]
    for path in paths:
        fs.create_file(path)
    assert cli.main(['organize', '-j']) == 0
    assert [p for p in paths if p.exists()] == []
    assert Path('/notes/foo.md').exists()
    assert Path('/notes/foo_uuid1abcdefghijklmnopq.md').exists()
    out, err = capsys.readouterr()
    assert json.loads(out) == {'/notes/one.md': '/notes/foo.md',
                               '/notes/two.md': '/notes/foo_uuid1abcdefghijklmnopq.md'}
    assert cli.main(['organize', '-j']) == 0
    assert Path('/notes/foo.md').exists()
    assert not Path('/notes/foo_uuid2abcdefghijklmnopq.md').exists()
    assert Path('/notes/foo_uuid1abcdefghijklmnopq.md').exists()
    out, err = capsys.readouterr()
    assert json.loads(out) == {}


def test_change(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/foo.md', contents='some text')
    assert cli.main(['change', '-p', '-a', 'tag1,tag2', '-c', '2012-02-03', '-t', 'A Bland Note', 'foo.md']) == 0
    assert Path('/notes/cwd/foo.md').read_text() == 'some text'
    out, err = capsys.readouterr()
    lines = set(out.splitlines())
    # It's a little weird that we generate Cmds with relative paths, when most of the time the repos deal with
    # fully resolved paths. I don't think it affects anything right now, but may need to change at some point.
    assert lines == {str(AddTagCmd('foo.md', 'tag1')),
                     str(AddTagCmd('foo.md', 'tag2')),
                     str(SetTitleCmd('foo.md', 'A Bland Note')),
                     str(SetCreatedCmd('foo.md', datetime(2012, 2, 3)))}

    assert cli.main(['change', '-a', 'tag1,tag2', '-c', '2012-02-03', '-t', 'A Bland Note', 'foo.md']) == 0
    assert Path('/notes/cwd/foo.md').read_text() == """---
created: 2012-02-03 00:00:00
keywords:
- tag1
- tag2
title: A Bland Note
...
some text"""
    assert cli.main(['change', '-d', 'tag1', '-t', 'A Better Note', 'foo.md']) == 0
    assert Path('/notes/cwd/foo.md').read_text() == """---
created: 2012-02-03 00:00:00
keywords:
- tag2
title: A Better Note
...
some text"""


def test_tags_count(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/one.md', contents='#tag1 #tag1 #tag2')
    fs.create_file('/notes/two.md', contents='#tag1 #tag3')
    fs.create_file('/notes/three.md', contents='#tag1 #tag3 #tag4')
    assert cli.main(['tags', '-j']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {'tag1': 3, 'tag2': 1, 'tag3': 2, 'tag4': 1}
    assert cli.main(['tags']) == 0
    out, err = capsys.readouterr()
    assert out

    assert cli.main(['tags', '-j', 'tag:tag3']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == {'tag1': 2, 'tag3': 2, 'tag4': 1}
    assert cli.main(['tags', 'tag:tag3']) == 0
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
    assert cli.main(['query', '-j']) == 0
    out, err = capsys.readouterr()
    expected1 = FileInfo(path=path1,
                         title='A Test File',
                         created=datetime(2012, 3, 4, 5, 6, 7),
                         tags=['cool', 'has space']).as_json()
    assert json.loads(out) == [expected1, FileInfo(path=path2, tags=['test']).as_json()]
    assert cli.main(['query']) == 0
    out, err = capsys.readouterr()
    assert out
    assert cli.main(['query', '-t']) == 0
    out, err = capsys.readouterr()
    assert out

    assert cli.main(['query', '-j', 'tag:has+space']) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == [expected1]
    assert cli.main(['query', 'tag:has+space']) == 0
    out, err = capsys.readouterr()
    assert out


def test_relink(fs, capsys):
    nd_setup(fs)
    path1 = Path('/notes/foo.md')
    fs.create_file(path1, contents='I link to [bar](/notes/subdir1/bar.md#section)')
    assert cli.main(['relink', '-p', '/notes/subdir1/bar.md', '/blah/baz.md']) == 0
    out, err = capsys.readouterr()
    assert out == str(ReplaceHrefCmd(str(path1), '/notes/subdir1/bar.md#section', '../blah/baz.md#section')) + '\n'
    assert cli.main(['relink', '/notes/subdir1/bar.md', '/blah/baz.md']) == 0
    assert path1.read_text() == 'I link to [bar](../blah/baz.md#section)'


@freeze_time('2010-09-08T07:06:05Z')
def test_backfill(fs, capsys):
    nd_setup(fs)
    good_path = '/notes/all-good.md'
    good_doc = """---
title: Good Note
created: 2001-02-03T04:05:06-07:00
...
Hi!"""
    no_title_doc = """---
created: 2002-03-04T05:06:07-08:00
...
Hello!"""
    no_created_doc = """---
title: Mediocre Note
...
Whatever"""
    nothing_doc = 'Boo.'
    unsupported_doc = 'Go away.'
    no_title_path = '/notes/no-title.md'
    no_created_path = '/notes/no-created.md'
    nothing_path = '/notes/nothing.md'
    unsupported_path = '/notes/unsupported'
    fs.create_file(good_path, contents=good_doc)
    fs.create_file(no_title_path, contents=no_title_doc)
    fs.create_file(no_created_path, contents=no_created_doc)
    fs.create_file(nothing_path, contents=nothing_doc)
    fs.create_file(unsupported_path, contents=unsupported_doc)
    assert cli.main(['backfill', '-p']) == 0
    out, err = capsys.readouterr()
    assert Path(good_path).read_text() == good_doc
    assert Path(no_title_path).read_text() == no_title_doc
    assert Path(no_created_path).read_text() == no_created_doc
    assert Path(nothing_path).read_text() == nothing_doc
    assert Path(unsupported_path).read_text() == unsupported_doc

    assert cli.main(['backfill']) == 0
    out, err = capsys.readouterr()
    assert good_path not in out
    assert good_path not in err
    assert no_title_path in out
    assert no_created_path in out
    assert nothing_path in out
    assert unsupported_path in err
    assert Path(good_path).read_text() == good_doc
    assert Path(no_title_path).read_text() == """---
created: 2002-03-04 05:06:07-08:00
title: no-title
...
Hello!"""
    assert Path(no_created_path).read_text() == """---
created: 2010-09-08 07:06:05+00:00
title: Mediocre Note
...
Whatever"""
    assert Path(nothing_path).read_text() == """---
created: 2010-09-08 07:06:05+00:00
title: nothing
...
Boo."""
    assert Path(unsupported_path).read_text() == unsupported_doc
