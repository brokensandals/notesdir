from pathlib import Path
from notesdir.store import ref_path


def test_ref_path_same_file():
    src = Path('foo/bar')
    dest = Path('foo/bar')
    assert ref_path(src, dest) == Path('.')


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
    assert ref_path(src, dest) == Path('bar')


# Not sure if this is a real use case for this function
def test_ref_path_parent():
    src = Path('foo/bar')
    dest = Path('foo')
    assert ref_path(src, dest) == Path('..')


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
