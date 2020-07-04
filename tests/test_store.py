import json
from pathlib import Path
from unittest.mock import call, Mock
from urllib.parse import urlparse
from freezegun import freeze_time
import pytest
from notesdir.accessors.base import Accessor
from notesdir.models import FileInfo, SetTitleCmd, ReplaceRefCmd, MoveCmd
from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.accessors.markdown import MarkdownAccessor
from notesdir.store import ref_path, path_as_ref, edits_for_rearrange, FSStore


def test_ref_path_same_file():
    src = Path('foo/bar')
    dest = Path('foo/bar')
    assert ref_path(src, dest) == Path('bar')


def test_ref_path_same_dir():
    src = Path('foo/bar')
    dest = Path('foo/baz')
    assert ref_path(src, dest) == Path('baz')


def test_ref_path_sibling_descendant():
    src = Path('foo/bar')
    dest = Path('foo/baz/meh')
    assert ref_path(src, dest) == Path('baz/meh')


def test_ref_path_common_ancestor():
    src = Path('foo/bar/baz')
    dest = Path('foo/meh')
    assert ref_path(src, dest) == Path('../meh')


def test_ref_path_root_is_only_common_ancestor():
    src = Path('/foo/bar')
    dest = Path('/baz/meh')
    assert ref_path(src, dest) == Path('../baz/meh')


def test_ref_path_root_is_only_common_ancestor_relative(fs):
    src = Path('foo/bar')
    dest = Path('baz/meh')
    fs.cwd = '/'
    assert ref_path(src, dest) == Path('../baz/meh')


# Not sure if this is a real use case for this function
def test_ref_path_child():
    src = Path('foo')
    dest = Path('foo/bar')
    assert ref_path(src, dest) == Path('foo/bar')


# Not sure if this is a real use case for this function
def test_ref_path_parent():
    src = Path('foo/bar')
    dest = Path('foo')
    assert ref_path(src, dest) == Path('.')


def test_ref_path_relative_to_absolute(fs):
    src = Path('foo/bar')
    dest = Path('/somewhere/beta/file')
    fs.cwd = '/somewhere/alpha'
    assert ref_path(src, dest) == Path('../../beta/file')


def test_ref_path_absolute_to_relative(fs):
    src = Path('/somewhere/beta/file')
    dest = Path('foo/bar')
    fs.cwd = '/somewhere/alpha'
    assert ref_path(src, dest) == Path('../alpha/foo/bar')


def test_ref_path_symlinks(fs):
    src = Path('/foo/bar/baz')
    dest = Path('/whatever/hello')
    fs.create_symlink('/whatever', '/foo/meh')
    assert ref_path(src, dest) == Path('../meh/hello')


def test_ref_path_symlinks_relative(fs):
    src = Path('foo/bar/baz')
    dest = Path('whatever/hello')
    fs.create_symlink('/cwd/whatever', '/cwd/foo/meh')
    fs.cwd = '/cwd'
    assert ref_path(src, dest) == Path('../meh/hello')


def test_path_as_ref_absolute():
    assert path_as_ref(Path('/foo/bar/baz')) == '/foo/bar/baz'


def test_path_as_ref_relative():
    assert path_as_ref(Path('../bar/baz')) == '../bar/baz'


def test_path_as_ref_absolute_into_url():
    parts = urlparse('/foo/bar/baz#f?k=v')
    assert path_as_ref(Path('/meh/ok'), parts) == '/meh/ok#f?k=v'


def test_path_as_ref_relative_into_url():
    parts = urlparse('/foo/bar/baz#f?k=v')
    assert path_as_ref(Path('../meh/ok'), parts) == '../meh/ok#f?k=v'


def test_path_as_ref_absolute_into_url_with_scheme():
    parts = urlparse('file://localhost/foo/bar/baz')
    assert path_as_ref(Path('/meh/ok'), parts) == 'file://localhost/meh/ok'


def test_path_as_ref_relative_into_url_with_scheme():
    parts = urlparse('file://localhost/foo/bar/baz')
    with pytest.raises(ValueError):
        path_as_ref(Path('../meh/ok'), parts)


def test_path_as_ref_special_characters():
    assert path_as_ref(Path('/a dir/a file!.md')) == '/a%20dir/a%20file%21.md'


def test_path_as_ref_special_characters_into_url():
    parts = urlparse('/foo/bar/baz#f?k=v')
    assert path_as_ref(Path('/a dir/a file!.md'), parts) == '/a%20dir/a%20file%21.md#f?k=v'


def test_referrers(fs):
    fs.cwd = '/notes/foo'
    fs.create_file('/notes/foo/subject.md')
    fs.create_file('/notes/bar/baz/r1.md', contents='[1](no) [2](../../foo/subject.md)')
    fs.create_file('/notes/bar/baz/no.md', contents='[3](../../foo/bogus')
    fs.create_file('/notes/r2.md', contents='[4](foo/subject.md) [5](foo/bogus)')
    fs.create_file('/notes/foo/r3.md', contents='[6](subject.md)')
    store = FSStore(Path('/notes'), MarkdownAccessor)
    expected = {Path(p) for p in {'/notes/bar/baz/r1.md', '/notes/r2.md', '/notes/foo/r3.md'}}
    assert store.referrers(Path('subject.md')) == expected


def test_referrers_self(fs):
    fs.create_file('/notes/subject.md', contents='[1](subject.md)')
    store = FSStore(Path('/notes'), MarkdownAccessor)
    expected = {Path('/notes/subject.md')}
    assert store.referrers(Path('/notes/subject.md')) == expected


def test_change(fs):
    fs.create_file('/notes/one.md', contents='[1](old)')
    fs.create_file('/notes/two.md', contents='[2](foo)')
    edits = [SetTitleCmd(Path('/notes/one.md'), 'New Title'),
             ReplaceRefCmd(Path('/notes/one.md'), 'old', 'new'),
             MoveCmd(Path('/notes/one.md'), Path('/notes/moved.md')),
             ReplaceRefCmd(Path('/notes/two.md'), 'foo', 'bar')]
    store = FSStore(Path('/notes'), MarkdownAccessor)
    store.change(edits)
    assert not Path('/notes/one.md').exists()
    assert Path('/notes/moved.md').read_text() == '---\ntitle: New Title\n...\n[1](new)'
    assert Path('/notes/two.md').read_text() == '[2](bar)'


def test_rearrange_selfreference(fs):
    doc = 'I link to [myself](one.md).'
    fs.create_file('/notes/one.md', contents=doc)
    store = FSStore(Path('/notes'), MarkdownAccessor)
    store.change(edits_for_rearrange(store, {Path('/notes/one.md'): Path('/notes/two.md')}))
    assert not Path('/notes/one.md').exists()
    assert Path('/notes/two.md').exists()
    assert Path('/notes/two.md').read_text() == 'I link to [myself](two.md).'


def test_rearrange_mutual(fs):
    doc1 = 'I link to [two](two.md).'
    doc2 = 'I link to [one](one.md).'
    fs.create_file('/notes/one.md', contents=doc1)
    fs.create_file('/notes/two.md', contents=doc2)
    store = FSStore(Path('/notes'), MarkdownAccessor)
    store.change(edits_for_rearrange(store, {
        Path('/notes/one.md'): Path('/notes/three.md'),
        Path('/notes/two.md'): Path('/notes/four.md')
    }))
    assert not Path('/notes/one.md').exists()
    assert not Path('/notes/two.md').exists()
    assert Path('/notes/three.md').exists()
    assert Path('/notes/four.md').exists()
    assert Path('/notes/three.md').read_text() == 'I link to [two](four.md).'
    assert Path('/notes/four.md').read_text() == 'I link to [one](three.md).'


def test_rearrange_mutual_subdirs(fs):
    doc1 = 'I link to [two](../two.md).'
    doc2 = 'I link to [one](subdir1/one.md).'
    fs.create_file('/notes/subdir1/one.md', contents=doc1)
    fs.create_file('/notes/two.md', contents=doc2)
    Path('/notes/subdir2').mkdir()
    store = FSStore(Path('/notes'), MarkdownAccessor)
    store.change(edits_for_rearrange(store, {
        Path('/notes/subdir1/one.md'): Path('/notes/one.md'),
        Path('/notes/two.md'): Path('/notes/subdir2/two.md')
    }))
    assert not Path('/notes/subdir1/one.md').exists()
    assert not Path('/notes/two.md').exists()
    assert Path('/notes/one.md').exists()
    assert Path('/notes/subdir2/two.md').exists()
    assert Path('/notes/one.md').read_text() == 'I link to [two](subdir2/two.md).'
    assert Path('/notes/subdir2/two.md').read_text() == 'I link to [one](../one.md).'


def test_rearrange_swap(fs):
    doc1 = 'I link to [two](two.md).'
    doc2 = 'I link to [one](one.md).'
    fs.create_file('/notes/one.md', contents=doc1)
    fs.create_file('/notes/two.md', contents=doc2)
    store = FSStore(Path('/notes'), MarkdownAccessor)
    store.change(edits_for_rearrange(store, {
        Path('/notes/one.md'): Path('/notes/two.md'),
        Path('/notes/two.md'): Path('/notes/one.md')
    }))
    assert Path('/notes/one.md').exists()
    assert Path('/notes/two.md').exists()
    assert Path('/notes/one.md').read_text() == 'I link to [one](two.md).'
    assert Path('/notes/two.md').read_text() == 'I link to [two](one.md).'


def test_rearrange_special_characters(fs):
    doc1 = 'I link to [two](second%20doc%21.md).'
    doc2 = 'I link to [one](first%20doc%21.md).'
    fs.create_file('/notes/first doc!.md', contents=doc1)
    fs.create_file('/notes/second doc!.md', contents=doc2)
    Path('/notes/subdir').mkdir()
    store = FSStore(Path('/notes'), MarkdownAccessor)
    store.change(edits_for_rearrange(store, {
        Path('/notes/first doc!.md'): Path('/notes/subdir/new loc!.md')}))
    assert not Path('/notes/first doc!.md').exists()
    assert Path('/notes/second doc!.md').exists()
    assert Path('/notes/subdir/new loc!.md').exists()
    assert Path('/notes/second doc!.md').read_text() == 'I link to [one](subdir/new%20loc%21.md).'
    assert (Path('/notes/subdir/new loc!.md').read_text()
            == 'I link to [two](../second%20doc%21.md).')


def test_rearrange_folder(fs):
    doc1 = 'I link to [two](dir/two.md).'
    doc2 = 'I link to [three](subdir/three.md).'
    doc3 = 'I link to [one](../../one.md).'
    fs.create_file('/notes/one.md', contents=doc1)
    fs.create_file('/notes/dir/two.md', contents=doc2)
    fs.create_file('/notes/dir/subdir/three.md', contents=doc3)
    Path('/notes/wrapper').mkdir()
    store = FSStore(Path('/notes'), DelegatingAccessor)
    store.change(edits_for_rearrange(store, {
        Path('/notes/dir'): Path('/notes/wrapper/newdir')}))
    assert not Path('/notes/dir').exists()
    assert Path('/notes/one.md').read_text() == 'I link to [two](wrapper/newdir/two.md).'
    assert Path('/notes/wrapper/newdir/two.md').read_text() == 'I link to [three](subdir/three.md).'
    assert (Path('/notes/wrapper/newdir/subdir/three.md').read_text()
            == 'I link to [one](../../../one.md).')


@freeze_time('2020-02-03T04:05:06-0800')
def test_log_edits(fs):
    doc1 = 'I have [a link](doc2.md).'
    doc2 = bytes([0xfe, 0xfe, 0xff, 0xff])
    fs.create_file('doc1.md', contents=doc1)
    fs.create_file('doc2.bin', contents=doc2)
    edits = [
        ReplaceRefCmd(Path('doc1.md'), 'doc2.md', 'garbage.md'),
        MoveCmd(Path('doc2.bin'), Path('new-doc2.bin')),
    ]
    store = FSStore(Path('/notes'), DelegatingAccessor, edit_log_path=Path('edits'))
    store.change(edits)
    log = Path('edits').read_text().splitlines()
    assert len(log) == 2
    entry1 = json.loads(log[0])
    # FIXME these dates should have time zone indicators!
    assert entry1 == {
        'datetime': '2020-02-03T12:05:06',
        'path': 'doc1.md',
        'edits': [{
            'class': 'ReplaceRefCmd',
            'original': 'doc2.md',
            'replacement': 'garbage.md',
        }],
        'prior_text': 'I have [a link](doc2.md).'
    }
    entry2 = json.loads(log[1])
    assert entry2 == {
        'datetime': '2020-02-03T12:05:06',
        'path': 'doc2.bin',
        'edits': [{
            'class': 'MoveCmd',
            'dest': 'new-doc2.bin',
        }],
        'prior_base64': '/v7//w=='
    }
