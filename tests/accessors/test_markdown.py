from notesdir.accessors.markdown import extract_meta


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
