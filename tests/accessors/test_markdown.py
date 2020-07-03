from datetime import datetime, timedelta, timezone
from pathlib import Path
from notesdir.models import SetTitleCmd, SetCreatedCmd, ReplaceRefCmd
from notesdir.accessors.markdown import extract_meta, extract_refs, extract_tags, replace_ref,\
    MarkdownAccessor, set_meta


def test_extract_meta_none():
    assert extract_meta('Hi!\n---\nnope\n...') == {}


def test_extract_meta():
    doc = """---\n
title: foo bar
otherVal: 19
...
text: regular
"""
    expected = {'title': 'foo bar', 'otherVal': 19}
    assert extract_meta(doc) == expected


def test_extract_tags():
    doc = """#beginning-of-line #123excluded-because-of-leading-numbers #end-of-line
# Heading #in-heading # whatever
You can have #numbers1234 just not at the beginning.
Everything gets #DownCased. #hyphens-and_underscores work.
The pound#sign must be preceded by whitespace if it's not at the beginning of the line.
"""
    expected = set(['beginning-of-line', 'end-of-line', 'in-heading', 'numbers1234',
                    'downcased', 'hyphens-and_underscores'])
    assert extract_tags(doc) == expected


def test_extract_refs():
    doc = """A link to [some file](some-file). A link from [a ref].
[a ref]: foo/bar/baz%20blah.txt whatever
An ![image link](/foo/my.png)"""
    expected = set(['some-file', 'foo/bar/baz%20blah.txt', '/foo/my.png'])
    assert extract_refs(doc) == expected


def test_replace_ref_inline():
    doc = """A link to [some file](some-file) followed by
a link to [another file](another-file) and
[the first file again](some-file)."""
    expected = """A link to [some file](new-ref) followed by
a link to [another file](another-file) and
[the first file again](new-ref)."""
    assert replace_ref(doc, 'some-file', 'new-ref') == expected


def test_replace_ref_refstyle():
    doc = """Here we see the ref style syntax:
[some id]: file-1 "Some Text"
[other id]: file-1
[third id]: file-2
Ignored in the middle of a line: [some id]: file-1"""
    expected = """Here we see the ref style syntax:
[some id]: new-ref "Some Text"
[other id]: new-ref
[third id]: file-2
Ignored in the middle of a line: [some id]: file-1"""
    assert replace_ref(doc, 'file-1', 'new-ref') == expected


def test_replace_ref_image():
    doc = "An ![image link](http://example.com/foo.png) should work too."
    expected = "An ![image link](http://example.com/bar.png) should work too."
    assert replace_ref(doc, 'http://example.com/foo.png', 'http://example.com/bar.png') == expected


def test_replace_ref_replacement_string_special_characters():
    doc = """A [link](foo.md).
[refstyle]: foo.md"""
    expected = """A [link](2-foo\\3.md).
[refstyle]: 2-foo\\3.md"""
    assert replace_ref(doc, 'foo.md', '2-foo\\3.md') == expected


def test_set_meta_none_exists():
    doc = "This is a document.\nWith text."
    expected = "---\ntitle: My Document\n...\nThis is a document.\nWith text."
    meta = {'title': 'My Document'}
    assert set_meta(doc, meta) == expected


def test_set_meta_replace():
    doc = "---\ntitle: My Document\n...\nThis is a document.\nWith text."
    expected = "---\ntitle: Improved Document\n...\nThis is a document.\nWith text."
    meta = {'title': 'Improved Document'}
    assert set_meta(doc, meta) == expected


def test_parse(fs):
    doc = """---
title: An Examination of the Navel
created: 2019-06-04 10:12:13-08:00
keywords:
  - TrulyProfound
...
#personal #book-draft
# Preface: Reasons for #journaling

As I have explained at length in [another note](../Another%20Note.md) and also
published about online (see [this article](http://example.com/blah) among many others), ...
"""
    path = Path('/fakenotes/test.md')
    fs.create_file(path, contents=doc)
    info = MarkdownAccessor().parse(path)
    assert info.path == path
    assert info.refs == {'../Another%20Note.md', 'http://example.com/blah'}
    assert info.managed_tags == {'trulyprofound'}
    assert info.unmanaged_tags == {'personal', 'book-draft', 'journaling'}
    assert info.title == 'An Examination of the Navel'
    assert info.created == datetime(2019, 6, 4, 10, 12, 13, 0, timezone(timedelta(hours=-8)))


def test_change(fs):
    doc = """---
title: An Examination of the Navel
...
#personal #book-draft
# Preface: Reasons for #journaling

As I have explained at length in [another note](../Another%20Note.md) and also
published about online (see [this article](http://example.com/blahblah) and
[this one](http://example.com/blah) among many others), ...
"""
    expected = """---
created: 2019-06-04 10:12:13-08:00
title: A Close Examination of the Navel
...
#personal #book-draft
# Preface: Reasons for #journaling

As I have explained at length in [another note](moved/another-note.md) and also
published about online (see [this article](http://example.com/blahblah) and
[this one](https://example.com/meh) among many others), ...
"""
    path = Path('/fakenotes/test.md')
    edits = [
        ReplaceRefCmd(path, '../Another%20Note.md', 'moved/another-note.md'),
        ReplaceRefCmd(path, 'http://example.com/blah', 'https://example.com/meh'),
        SetTitleCmd(path, 'A Close Examination of the Navel'),
        SetCreatedCmd(path, datetime(2019, 6, 4, 10, 12, 13, 0, timezone(timedelta(hours=-8))))
    ]
    fs.create_file(path, contents=doc)
    assert MarkdownAccessor().change(edits)
    assert path.read_text() == expected
