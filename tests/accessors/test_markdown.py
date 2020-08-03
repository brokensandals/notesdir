from datetime import datetime, timedelta, timezone
from pathlib import Path
from notesdir.models import AddTagCmd, DelTagCmd, SetTitleCmd, SetCreatedCmd, ReplaceHrefCmd, LinkInfo
from notesdir.accessors.markdown import _extract_meta, _extract_hrefs, _extract_hashtags, _replace_href,\
    MarkdownAccessor


def test_extract_meta_none():
    # The correctness of this is questionable - I think Pandoc accepts meta blocks anywhere in the document.
    # But that doesn't sound like something I'd use.
    assert _extract_meta('Hi!\n---\nnope\n...') == ({}, 'Hi!\n---\nnope\n...')


def test_extract_meta():
    doc = """---\n
title: foo bar
otherVal: 19
...
text: regular
"""
    expected = {'title': 'foo bar', 'otherVal': 19}
    assert _extract_meta(doc) == (expected, 'text: regular\n')


def test_extract_tags():
    doc = """#beginning-of-line #123excluded-because-of-leading-numbers #end-of-line
# Heading #in-heading # whatever
You can have #numbers1234 just not at the beginning.
Everything gets #DownCased. #hyphens-and_underscores work.
The pound#sign must be preceded by whitespace if it's not at the beginning of the line.
"""
    expected = set(['beginning-of-line', 'end-of-line', 'in-heading', 'numbers1234',
                    'downcased', 'hyphens-and_underscores'])
    assert _extract_hashtags(doc) == expected


def test_extract_hrefs():
    doc = """A link to [some file](some-file). A link from [a ref].
[a ref]: foo/bar/baz%20blah.txt whatever
An ![image link](/foo/my.png)"""
    expected = ['some-file', '/foo/my.png', 'foo/bar/baz%20blah.txt']
    assert _extract_hrefs(doc) == expected


def test_replace_href_inline():
    doc = """A link to [some file](some-file) followed by
a link to [another file](another-file) and
[the first file again](some-file)."""
    expected = """A link to [some file](new-ref) followed by
a link to [another file](another-file) and
[the first file again](new-ref)."""
    assert _replace_href(doc, 'some-file', 'new-ref') == expected


def test_replace_href_refstyle():
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
    assert _replace_href(doc, 'file-1', 'new-ref') == expected


def test_replace_href_image():
    doc = "An ![image link](http://example.com/foo.png) should work too."
    expected = "An ![image link](http://example.com/bar.png) should work too."
    assert _replace_href(doc, 'http://example.com/foo.png', 'http://example.com/bar.png') == expected


def test_replace_href_replacement_string_special_characters():
    doc = """A [link](foo.md).
[refstyle]: foo.md"""
    expected = """A [link](2-foo\\3.md).
[refstyle]: 2-foo\\3.md"""
    assert _replace_href(doc, 'foo.md', '2-foo\\3.md') == expected


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
    path = '/fakenotes/test.md'
    fs.create_file(path, contents=doc)
    info = MarkdownAccessor(path).info()
    assert info.path == path
    assert info.links == [LinkInfo(path, r) for r in sorted(['../Another%20Note.md', 'http://example.com/blah'])]
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
    path = '/fakenotes/test.md'
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    acc.edit(ReplaceHrefCmd(path, '../Another%20Note.md', 'moved/another-note.md'))
    acc.edit(ReplaceHrefCmd(path, 'http://example.com/blah', 'https://example.com/meh'))
    acc.edit(SetTitleCmd(path, 'A Close Examination of the Navel'))
    acc.edit(SetCreatedCmd(path, datetime(2019, 6, 4, 10, 12, 13, 0, timezone(timedelta(hours=-8)))))
    assert acc.save()
    assert Path(path).read_text() == expected


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
    path = '/fakenotes/test.md'
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    acc.edit(AddTagCmd(path, 'THREE'))
    acc.edit(DelTagCmd(path, 'ONE'))
    assert acc.save()
    assert Path(path).read_text() == expected


def test_remove_hashtag(fs):
    doc = '#Tag1 tag1 #tag1. tag1#tag1 #tag1 #tag2 #tag1'
    # TODO Currently none of the whitespace around a tag is removed when the tag is, which can leave things
    #      pretty ugly. But I'm not sure what the best approach is.
    expected = ' tag1 . tag1#tag1  #tag2 '
    path = '/fakenotes/test.md'
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    assert acc.info().tags == {'tag1', 'tag2'}
    acc.edit(DelTagCmd(path, 'tag1'))
    assert acc.save()
    assert Path(path).read_text() == expected


def test_ignore_fenced_code_blocks(fs):
    doc = """#tag1 [link](link1.md)
```foo
#tag2 #tag3
text [link](link1.md)
```
  #tag3 [link](link2.md)

   ```
   [link](link3.md)
   ```"""
    path = '/fakenotes/text.md'
    fs.create_file(path, contents=doc)
    acc = MarkdownAccessor(path)
    info = acc.info()
    assert info.tags == {'tag1', 'tag3'}
    assert info.links == [LinkInfo(path, 'link1.md'), LinkInfo(path, 'link2.md')]
    acc.edit(ReplaceHrefCmd(path, 'link1.md', 'CHANGED1'))
    acc.edit(ReplaceHrefCmd(path, 'link2.md', 'CHANGED2'))
    acc.edit(ReplaceHrefCmd(path, 'link3.md', 'CHANGED3'))
    acc.edit(DelTagCmd(path, 'tag3'))
    acc.edit(DelTagCmd(path, 'tag2'))
    acc.save()
    assert Path(path).read_text() == """#tag1 [link](CHANGED1)
```foo
#tag2 #tag3
text [link](link1.md)
```
   [link](CHANGED2)

   ```
   [link](link3.md)
   ```"""

def test_meta_boundaries_in_body(fs):
    doc1 = """---
title: Hi
...

keywords:
- foo
...
whatever
"""
    doc2 = """---
title: Hi
---

keywords:
- foo
---
whatever
"""
    Path('/fakenotes').mkdir()
    for doc in [doc1, doc2]:
        path = '/fakenotes/doc.md'
        Path(path).write_text(doc)
        acc = MarkdownAccessor(path)
        info = acc.info()
        assert info.title == 'Hi'
        assert info.tags == set()
        acc.edit(AddTagCmd(path, 'testing'))
        acc.save()
        if doc == doc2:
            doc = doc.replace('\n---', '\n...', 1)
        doc = doc.replace('title', 'keywords:\n- testing\ntitle', 1)
        doc = doc.replace('...\n', '...', 1)  # FIXME it's a bug that the accessor removes this newline
        assert Path(path).read_text() == doc
