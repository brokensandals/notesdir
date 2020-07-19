from datetime import datetime
import os.path

from notesdir.models import FileQuery, FileInfoReq, LinkInfo, FileQuerySort, FileQuerySortField, FileInfo


def test_referent_skips_invalid_urls():
    assert LinkInfo('foo', 'file://no[').referent() is None


def test_referent_skips_non_file_schemes():
    assert LinkInfo('foo', 'http:///bar').referent() is None


def test_referent_skips_non_local_hosts():
    assert LinkInfo('foo', 'file://example.com/bar').referent() is None


def test_referent_matches_absolute_paths():
    assert LinkInfo('foo', '/bar').referent() == '/bar'
    assert LinkInfo('foo', 'file:///bar').referent() == '/bar'
    assert LinkInfo('foo', 'file://localhost/bar').referent() == '/bar'


def test_referent_matches_relative_paths():
    assert LinkInfo('/baz/foo', 'bar').referent() == '/baz/bar'


def test_referent_resolves_symlinks(fs):
    fs.cwd = '/cwd'
    fs.create_symlink('/cwd/bar', '/cwd/target')
    assert LinkInfo('foo', 'bar/baz').referent() == '/cwd/target/baz'


def test_referent_ignores_query_and_fragment():
    assert LinkInfo('/foo', 'bar#baz').referent() == '/bar'
    assert LinkInfo('/foo', 'bar?baz').referent() == '/bar'


def test_referent_resolves_relative_to_referrer(fs):
    fs.cwd = '/meh'
    assert LinkInfo('/foo/bar', 'baz').referent() == os.path.realpath('../foo/baz')


def test_referent_handles_special_characters():
    assert LinkInfo('/foo', 'hi%20there%21').referent() == '/hi there!'
    assert LinkInfo('/foo', 'hi+there%21').referent() == '/hi there!'


def test_parse_query():
    strquery = 'tag:first+tag,second -tag:third,fourth+tag tag:fifth sort:created,-backlinks'
    expected = FileQuery(
        include_tags={'first tag', 'second', 'fifth'},
        exclude_tags={'third', 'fourth tag'},
        sort_by=[FileQuerySort(FileQuerySortField.CREATED),
                 FileQuerySort(FileQuerySortField.BACKLINKS_COUNT, reverse=True)])
    assert FileQuery.parse(strquery) == expected


def test_apply_sorting():
    data = [
        FileInfo('/a/one', tags={'baz'},
                 backlinks=[LinkInfo(referrer='whatever', href='whatever')]),
        FileInfo('/b/two', title='Beta', created=datetime(2010, 1, 15)),
        FileInfo('/c/Three', title='Gamma', created=datetime(2012, 1, 9),
                 backlinks=[LinkInfo(referrer='whatever', href='whatever'),
                            LinkInfo(referrer='whatever', href='whatever')]),
        FileInfo('/d/four', title='delta', created=datetime(2012, 1, 9), tags={'foo', 'bar'})
    ]

    assert FileQuery.parse('sort:path').apply_sorting(data) == data
    assert FileQuery.parse('sort:-path').apply_sorting(data) == list(reversed(data))
    assert FileQuery.parse('sort:filename').apply_sorting(data) == [data[3], data[0], data[2], data[1]]
    assert FileQuery(sort_by=[FileQuerySort(FileQuerySortField.FILENAME, ignore_case=False)]).apply_sorting(data) == [
        data[2], data[3], data[0], data[1]]

    assert FileQuery.parse('sort:title').apply_sorting(data) == [data[1], data[3], data[2], data[0]]
    assert FileQuery(sort_by=[FileQuerySort(FileQuerySortField.TITLE, ignore_case=False)]).apply_sorting(data) == [
        data[1], data[2], data[3], data[0]]
    assert FileQuery(sort_by=[FileQuerySort(FileQuerySortField.TITLE, missing_first=True)]).apply_sorting(data) == [
        data[0], data[1], data[3], data[2]]
    assert FileQuery(sort_by=[FileQuerySort(FileQuerySortField.TITLE,
                                            missing_first=True,
                                            reverse=True)]).apply_sorting(data) == [
        data[2], data[3], data[1], data[0]]

    assert FileQuery.parse('sort:created').apply_sorting(data) == [data[1], data[2], data[3], data[0]]
    assert FileQuery.parse('sort:-created').apply_sorting(data) == [data[0], data[2], data[3], data[1]]
    assert FileQuery(sort_by=[FileQuerySort(FileQuerySortField.CREATED, missing_first=True)]).apply_sorting(data) == [
        data[0], data[1], data[2], data[3]]

    assert FileQuery.parse('sort:-tags').apply_sorting(data) == [data[3], data[0], data[1], data[2]]

    assert FileQuery.parse('sort:-backlinks').apply_sorting(data) == [data[2], data[0], data[1], data[3]]

    assert FileQuery.parse('sort:created,title').apply_sorting(data) == [data[1], data[3], data[2], data[0]]
    assert FileQuery.parse('sort:created,-title').apply_sorting(data) == [data[1], data[2], data[3], data[0]]


def test_parse_info_req():
    expected = FileInfoReq(path=True, backlinks=True)
    assert FileInfoReq.parse('path,backlinks') == expected
    assert FileInfoReq.parse(['path', 'backlinks']) == expected
    assert FileInfoReq.parse(expected) == expected
