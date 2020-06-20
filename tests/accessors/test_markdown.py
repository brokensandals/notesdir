from pathlib import Path
from notesdir.accessors.base import FileEdit
from notesdir.accessors.markdown import extract_meta, extract_refs, extract_tags, replace_refs, MarkdownAccessor


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


def test_replace_refs():
    doc = """A link to [some file](some-file). A link from [a ref].
[a ref]: foo/bar/baz%20blah.txt whatever
An ![image link](/foo/my.png)"""
    expected = """A link to [some file](../new/1). A link from [a ref].
[a ref]: baz%20new/2 whatever
An ![image link](/foo/your.png)"""
    replacements = {
        '/foo/my.png': '/foo/your.png',
        'nonexistent': 'irrelevant',
        'foo/bar/baz%20blah.txt': 'baz%20new/2',
        'some-file': '../new/1'
    }
    assert replace_refs(doc, replacements) == expected


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
    assert info.refs == set(['../Another%20Note.md', 'http://example.com/blah'])
    assert info.tags == set(['personal', 'book-draft', 'journaling'])
    assert info.title == 'An Examination of the Navel'


def test_change(fs):
    doc = """---\n
title: An Examination of the Navel
...
#personal #book-draft
# Preface: Reasons for #journaling

As I have explained at length in [another note](../Another%20Note.md) and also
published about online (see [this article](http://example.com/blah) among many others), ...
"""
    expected = """---\n
title: An Examination of the Navel
...
#personal #book-draft
# Preface: Reasons for #journaling

As I have explained at length in [another note](moved/another-note.md) and also
published about online (see [this article](http://example.com/blah) among many others), ...
"""
    edit = FileEdit(
        replace_refs={
            '../Another%20Note.md': 'moved/another-note.md'
        }
    )
    path = Path('/fakenotes/test.md')
    fs.create_file(path, contents=doc)
    assert MarkdownAccessor().change(path, edit)
    assert path.read_text() == expected
