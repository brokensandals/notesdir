from pathlib import Path
from notesdir.conf import default_ignore, resource_path_fn, rewrite_name_using_title
from notesdir.models import FileInfo


def test_default_ignore():
    assert default_ignore(None, '.git')
    assert default_ignore('/foo', '.git')
    assert default_ignore('/foo', 'bar.icloud')

    assert not default_ignore('/foo', 'bar')
    assert not default_ignore('/foo/baz.git', 'bar')
    assert not default_ignore('/foo', 'icloud.md')
    # The following path should be ignored, but default_ignore in isolation
    # will not detect it, for performance reasons. DirectRepo._paths will still
    # ignore the file, since default_ignore returns True for /foo/.git as a whole,
    # causing the directory to be skipped.
    assert not default_ignore('/foo/.git', 'bar')


def test_resource_path_fn():
    assert resource_path_fn('/foo/bar/baz') is None
    # the next case shouldn't really come up since we don't call path_organizer on directories
    assert resource_path_fn('/foo/bar/baz.resources') is None
    assert resource_path_fn('/foo/bar/baz') is None
    # the next case probably isn't good behavior, but it seems unimportant; leaving this
    # test case as documentation of the current behavior
    assert resource_path_fn('/foo/bar/.resources/baz')

    result = resource_path_fn('/foo/bar.resources/baz')
    assert result.determinant == '/foo/bar'
    assert result.fn(FileInfo('/somewhere/else')) == '/somewhere/else.resources/baz'
    assert result.fn(FileInfo('/foo/bar')) == '/foo/bar.resources/baz'
    assert result.fn(FileInfo('/foo/bar.md')) == '/foo/bar.md.resources/baz'

    result = resource_path_fn('/foo/My File.md.resources/subdir/My Picture.png')
    assert result.determinant == '/foo/My File.md'
    assert result.fn(FileInfo('/foo/My File.md')) == '/foo/My File.md.resources/subdir/My Picture.png'
    assert result.fn(FileInfo('/file.md')) == '/file.md.resources/subdir/My Picture.png'


def test_rewrite_name_using_title():
    def call(p, t):
        return rewrite_name_using_title(FileInfo(path=p, title=t))

    assert call('/notes/Foo Bar.md', None) == '/notes/Foo Bar.md'
    assert call('/notes/Foo Bar.md', 'Foo Bar') == '/notes/foo-bar.md'
    assert call('/notes/blah.html', '-+-+Awesome  Document#1000!!!') == '/notes/awesome-document-1000.html'
    assert (call('/notes/blah.md', '01234567890123456789012345678901234567890123456789012345678901234567')
            == '/notes/012345678901234567890123456789012345678901234567890123456789.md')
    assert call('/notes/blah.md', 'hi 😀 love you') == '/notes/hi-love-you.md'
