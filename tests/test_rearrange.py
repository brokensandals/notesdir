from pathlib import Path
from urllib.parse import urlparse

import pytest

from notesdir.conf import DirectRepoConf
from notesdir.rearrange import href_path, path_as_href, edits_for_rearrange


def test_ref_path_same_file():
    src = Path('foo/bar')
    dest = Path('foo/bar')
    assert href_path(src, dest) == Path('bar')


def test_ref_path_same_dir():
    src = Path('foo/bar')
    dest = Path('foo/baz')
    assert href_path(src, dest) == Path('baz')


def test_ref_path_sibling_descendant():
    src = Path('foo/bar')
    dest = Path('foo/baz/meh')
    assert href_path(src, dest) == Path('baz/meh')


def test_ref_path_common_ancestor():
    src = Path('foo/bar/baz')
    dest = Path('foo/meh')
    assert href_path(src, dest) == Path('../meh')


def test_ref_path_root_is_only_common_ancestor():
    src = Path('/foo/bar')
    dest = Path('/baz/meh')
    assert href_path(src, dest) == Path('../baz/meh')


def test_ref_path_root_is_only_common_ancestor_relative(fs):
    src = Path('foo/bar')
    dest = Path('baz/meh')
    fs.cwd = '/'
    assert href_path(src, dest) == Path('../baz/meh')


def test_ref_path_child():
    src = Path('foo')
    dest = Path('foo/bar')
    assert href_path(src, dest) == Path('foo/bar')


def test_ref_path_parent():
    src = Path('foo/bar')
    dest = Path('foo')
    assert href_path(src, dest) == Path('.')


def test_ref_path_relative_to_absolute(fs):
    src = Path('foo/bar')
    dest = Path('/somewhere/beta/file')
    fs.cwd = '/somewhere/alpha'
    assert href_path(src, dest) == Path('../../beta/file')


def test_ref_path_absolute_to_relative(fs):
    src = Path('/somewhere/beta/file')
    dest = Path('foo/bar')
    fs.cwd = '/somewhere/alpha'
    assert href_path(src, dest) == Path('../alpha/foo/bar')


def test_ref_path_symlinks(fs):
    src = Path('/foo/bar/baz')
    dest = Path('/whatever/hello')
    fs.create_symlink('/whatever', '/foo/meh')
    assert href_path(src, dest) == Path('../meh/hello')


def test_ref_path_symlinks_relative(fs):
    src = Path('foo/bar/baz')
    dest = Path('whatever/hello')
    fs.create_symlink('/cwd/whatever', '/cwd/foo/meh')
    fs.cwd = '/cwd'
    assert href_path(src, dest) == Path('../meh/hello')


def test_path_as_ref_absolute():
    assert path_as_href(Path('/foo/bar/baz')) == '/foo/bar/baz'


def test_path_as_ref_relative():
    assert path_as_href(Path('../bar/baz')) == '../bar/baz'


def test_path_as_ref_absolute_into_url():
    parts = urlparse('/foo/bar/baz#f?k=v')
    assert path_as_href(Path('/meh/ok'), parts) == '/meh/ok#f?k=v'


def test_path_as_ref_relative_into_url():
    parts = urlparse('/foo/bar/baz#f?k=v')
    assert path_as_href(Path('../meh/ok'), parts) == '../meh/ok#f?k=v'


def test_path_as_ref_absolute_into_url_with_scheme():
    parts = urlparse('file://localhost/foo/bar/baz')
    assert path_as_href(Path('/meh/ok'), parts) == 'file://localhost/meh/ok'


def test_path_as_ref_relative_into_url_with_scheme():
    parts = urlparse('file://localhost/foo/bar/baz')
    with pytest.raises(ValueError):
        path_as_href(Path('../meh/ok'), parts)


def test_path_as_ref_special_characters():
    assert path_as_href(Path('/a dir/a file!.md')) == '/a%20dir/a%20file%21.md'


def test_path_as_ref_special_characters_into_url():
    parts = urlparse('/foo/bar/baz#f?k=v')
    assert path_as_href(Path('/a dir/a file!.md'), parts) == '/a%20dir/a%20file%21.md#f?k=v'


def test_rearrange_selfreference(fs):
    doc = 'I link to [myself](one.md).'
    fs.create_file('/notes/one.md', contents=doc)
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits_for_rearrange(repo, {Path('/notes/one.md'): Path('/notes/two.md')}))
    assert not Path('/notes/one.md').exists()
    assert Path('/notes/two.md').exists()
    assert Path('/notes/two.md').read_text() == 'I link to [myself](two.md).'


def test_rearrange_mutual(fs):
    doc1 = 'I link to [two](two.md).'
    doc2 = 'I link to [one](one.md).'
    fs.create_file('/notes/one.md', contents=doc1)
    fs.create_file('/notes/two.md', contents=doc2)
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits_for_rearrange(repo, {
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
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits_for_rearrange(repo, {
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
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits_for_rearrange(repo, {
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
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits_for_rearrange(repo, {
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
    doc3 = 'I link to [one](../../one.md) and [the web](https://example.com).'
    fs.create_file('/notes/one.md', contents=doc1)
    fs.create_file('/notes/dir/two.md', contents=doc2)
    fs.create_file('/notes/dir/subdir/three.md', contents=doc3)
    Path('/notes/wrapper').mkdir()
    repo = DirectRepoConf(root_paths={'/notes'}).instantiate()
    repo.change(edits_for_rearrange(repo, {
        Path('/notes/dir'): Path('/notes/wrapper/newdir')}))
    assert not Path('/notes/dir').exists()
    assert Path('/notes/one.md').read_text() == 'I link to [two](wrapper/newdir/two.md).'
    assert Path('/notes/wrapper/newdir/two.md').read_text() == 'I link to [three](subdir/three.md).'
    assert (Path('/notes/wrapper/newdir/subdir/three.md').read_text()
            == 'I link to [one](../../../one.md) and [the web](https://example.com).')
