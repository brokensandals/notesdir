from pathlib import Path
import pytest
from notesdir.accessors.base import BaseAccessor, FileEdit, FileInfo


def test_refs_to_path_skips_invalid_urls():
    info = FileInfo(Path('foo'), refs={'file://no['})
    assert info.refs_to_path(Path('bar')) == set()


def test_refs_to_path_skips_non_file_schemes():
    info = FileInfo(Path('foo'), refs={'http:///bar'})
    assert info.refs_to_path(Path('/bar')) == set()


def test_refs_to_path_skips_non_local_hosts():
    info = FileInfo(Path('foo'), refs={'file://example.com/bar'})
    assert info.refs_to_path(Path('/bar')) == set()


def test_refs_to_path_matches_absolute_paths():
    info = FileInfo(Path('foo'), refs={'/bar', 'file:///bar', 'file://localhost/bar'})
    assert info.refs_to_path(Path('/bar')) == {'/bar', 'file:///bar', 'file://localhost/bar'}


def test_refs_to_path_matches_relative_paths():
    info = FileInfo(Path('foo'), refs={'bar'})
    assert info.refs_to_path(Path('bar')) == {'bar'}


def test_refs_to_path_resolves_symlinks(fs):
    fs.cwd = '/cwd'
    fs.create_symlink('/cwd/bar', '/cwd/target')
    info = FileInfo(Path('foo'), refs={'bar/baz'})
    assert info.refs_to_path(Path('/cwd/target/baz')) == {'bar/baz'}


def test_refs_to_path_only_returns_matches():
    info = FileInfo(Path('foo'), refs={'bar', 'http://example.com/bar', 'baz'})
    assert info.refs_to_path(Path('bar')) == {'bar'}


def test_refs_to_path_ignores_query_and_fragment():
    info = FileInfo(Path('foo'), refs={'bar#baz', 'bar?baz'})
    assert info.refs_to_path(Path('bar')) == {'bar#baz', 'bar?baz'}


def test_refs_to_path_resolves_src_relative_to_self(fs):
    fs.cwd = '/meh'
    info = FileInfo(Path('/foo/bar'), refs={'baz'})
    assert info.refs_to_path(Path('../foo/baz')) == {'baz'}


def test_refs_to_path_handles_special_characters():
    info = FileInfo(Path('foo'), refs={'hi%20there%21', 'hi+there%21'})
    assert info.refs_to_path(Path('hi there!')) == {'hi%20there%21', 'hi+there%21'}


def test_change_empty():
    assert not BaseAccessor().change([])


def test_change_multiple_paths():
    with pytest.raises(ValueError):
        BaseAccessor().change([FileEdit(Path('a')), FileEdit(Path('b'))])
