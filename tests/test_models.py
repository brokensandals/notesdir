from pathlib import Path

from notesdir.models import FileInfo, FileQuery, FileInfoReq, LinkInfo


def test_referent_skips_invalid_urls():
    assert LinkInfo(Path('foo'), 'file://no[').referent() is None


def test_referent_skips_non_file_schemes():
    assert LinkInfo(Path('foo'), 'http:///bar').referent() is None


def test_referent_skips_non_local_hosts():
    assert LinkInfo(Path('foo'), 'file://example.com/bar').referent() is None


def test_referent_matches_absolute_paths():
    assert LinkInfo(Path('foo'), '/bar').referent() == Path('/bar')
    assert LinkInfo(Path('foo'), 'file:///bar').referent() == Path('/bar')
    assert LinkInfo(Path('foo'), 'file://localhost/bar').referent() == Path('/bar')


def test_referent_matches_relative_paths():
    assert LinkInfo(Path('/baz/foo'), 'bar').referent() == Path('/baz/bar')


def test_referent_resolves_symlinks(fs):
    fs.cwd = '/cwd'
    fs.create_symlink('/cwd/bar', '/cwd/target')
    assert LinkInfo(Path('foo'), 'bar/baz').referent() == Path('/cwd/target/baz')


def test_referent_ignores_query_and_fragment():
    assert LinkInfo(Path('/foo'), 'bar#baz').referent() == Path('/bar')
    assert LinkInfo(Path('/foo'), 'bar?baz').referent() == Path('/bar')


def test_referent_resolves_relative_to_referrer(fs):
    fs.cwd = '/meh'
    assert LinkInfo(Path('/foo/bar'), 'baz').referent() == Path('../foo/baz').resolve()


def test_referent_handles_special_characters():
    assert LinkInfo(Path('/foo'), 'hi%20there%21').referent() == Path('/hi there!')
    assert LinkInfo(Path('/foo'), 'hi+there%21').referent() == Path('/hi there!')


def test_parse_query():
    strquery = 'tag:first+tag,second -tag:third,fourth+tag tag:fifth'
    expected = FileQuery(
        include_tags={'first tag', 'second', 'fifth'},
        exclude_tags={'third', 'fourth tag'})
    assert FileQuery.parse(strquery) == expected


def test_parse_info_req():
    expected = FileInfoReq(path=True, backlinks=True)
    assert FileInfoReq.parse('path,backlinks') == expected
    assert FileInfoReq.parse(['path', 'backlinks']) == expected
    assert FileInfoReq.parse(expected) == expected
