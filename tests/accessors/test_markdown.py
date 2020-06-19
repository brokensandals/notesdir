from pathlib import Path
from notesdir.accessors.markdown import extract_meta, MarkdownAccessor


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


def test_parse(fs):
    doc = """---\n
title: An Examination of the Navel
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
    assert info.title == 'An Examination of the Navel'
