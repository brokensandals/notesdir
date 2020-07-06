from datetime import datetime, timedelta, timezone
from pathlib import Path
from notesdir.models import AddTagCmd, DelTagCmd, SetTitleCmd, SetCreatedCmd, ReplaceRefCmd
from notesdir.accessors.markdown import extract_meta, extract_refs, extract_hashtags, replace_ref,\
    MarkdownAccessor


def test_extract_meta_none():
    # The correctness of this is questionable - I think Pandoc accepts meta blocks anywhere in the document.
    # But that doesn't sound like something I'd use.
    assert extract_meta('Hi!\n---\nnope\n...') == ({}, 'Hi!\n---\nnope\n...')


def test_extract_meta():
    doc = """---\n
title: foo bar
otherVal: 19
...
text: regular
"""
    expected = {'title': 'foo bar', 'otherVal': 19}
    assert extract_meta(doc) == (expected, 'text: regular\n')


def test_extract_tags():
    doc = """#beginning-of-line #123excluded-because-of-leading-numbers #end-of-line
# Heading #in-heading # whatever
You can have #numbers1234 just not at the beginning.
Everything gets #DownCased. #hyphens-and_underscores work.
The pound#sign must be preceded by whitespace if it's not at the beginning of the line.
"""
    expected = set(['beginning-of-line', 'end-of-line', 'in-heading', 'numbers1234',
                    'downcased', 'hyphens-and_underscores'])
    assert extract_hashtags(doc) == expected


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


def test_info(fs):
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
    info = MarkdownAccessor(path).info()
    assert info.path == path
    assert info.refs == {'../Another%20Note.md', 'http://example.com/blah'}
    assert info.tags == {'trulyprofound', 'personal', 'book-draft', 'journaling'}
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
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    acc.edit(ReplaceRefCmd(path, '../Another%20Note.md', 'moved/another-note.md'))
    acc.edit(ReplaceRefCmd(path, 'http://example.com/blah', 'https://example.com/meh'))
    acc.edit(SetTitleCmd(path, 'A Close Examination of the Navel'))
    acc.edit(SetCreatedCmd(path, datetime(2019, 6, 4, 10, 12, 13, 0, timezone(timedelta(hours=-8)))))
    assert acc.save()
    assert path.read_text() == expected


def test_change_metadata_tags(fs):
    doc = """---
keywords:
- one
- two
...
text"""
    expected = """---
keywords:
- three
- two
...
text"""
    path = Path('/fakenotes/test.md')
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    acc.edit(AddTagCmd(path, 'THREE'))
    acc.edit(DelTagCmd(path, 'ONE'))
    assert acc.save()
    assert path.read_text() == expected


def test_remove_hashtag(fs):
    doc = '#Tag1 tag1 #tag1. tag1#tag1 #tag1 #tag2 #tag1'
    # TODO Currently none of the whitespace around a tag is removed when the tag is, which can leave things
    #      pretty ugly. But I'm not sure what the best approach is.
    expected = ' tag1 . tag1#tag1  #tag2 '
    path = Path('/fakenotes/test.md')
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    assert acc.info().tags == {'tag1', 'tag2'}
    acc.edit(DelTagCmd(path, 'tag1'))
    assert acc.save()
    assert path.read_text() == expected
