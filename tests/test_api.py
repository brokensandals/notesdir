import os.path
from pathlib import Path
from freezegun import freeze_time
import pytest
from notesdir.api import Error, Notesdir


def test_for_user_no_file(fs):
    with pytest.raises(Error, match=r'No config file found at .*\.notesdir\.toml'):
        Notesdir.for_user()


def test_for_user(fs):
    fs.create_file(os.path.expanduser('~/.notesdir.toml'), contents='repo.roots = ["/foo"]')
    nd = Notesdir.for_user()
    assert nd.config == {'repo': {'roots': ['/foo']}}


def test_replace_path_refs(fs):
    nd = Notesdir({'repo': {'roots': ['/notes']}})
    fs.create_file('/notes/one.md', contents='I link to [two](two.md) [twice](two.md#section).')
    fs.create_file('/notes/subdir/three.md', contents='I link to [two](../two.md) and [four](four.md).')
    nd.replace_path_hrefs('/notes/two.md', '/notes/subdir/new.md')
    assert Path('/notes/one.md').read_text() == 'I link to [two](subdir/new.md) [twice](subdir/new.md#section).'
    assert (Path('/notes/subdir/three.md').read_text() ==
            'I link to [two](new.md) and [four](four.md).')


@freeze_time('2019-08-07T06:05:04')
def test_custom_filename_template(fs):
    # In reality you'd almost always want the template to end in ${info.path.suffix} but
    # this test doesn't, just to prove it is technically left up to the template.
    template = """${info.title} ${info.guess_created().strftime('%Y-%m-%d')}.md"""
    nd = Notesdir({'repo': {'roots': ['/notes']}, 'filename_template': template})
    path = Path('/notes/blah.html')
    fs.create_file(path)
    nd.normalize(path)
    assert not path.exists()
    assert Path('/notes/blah 2019-08-07.md').read_text() == """---
created: 2019-08-07 06:05:04
title: blah
...
"""

# Most of the Notesdir class is tested indirectly via the tests for the CLI.
