import os.path
from pathlib import Path
from freezegun import freeze_time
import pytest
from notesdir.api import Notesdir
from notesdir.conf import DirectRepoConf, NotesdirConf


def config():
    return NotesdirConf(repo_conf=DirectRepoConf(root_paths={'/notes'}))


def test_for_user_no_file(fs):
    with pytest.raises(Exception, match=r'You need to create the config file: .*\.notesdir\.conf\.py'):
        Notesdir.for_user()


def test_for_user(fs):
    confpy = """from notesdir.conf import *
conf = NotesdirConf(repo_conf=DirectRepoConf(root_paths={'/notes'}))"""
    fs.create_file(os.path.expanduser('~/.notesdir.conf.py'), contents=confpy)
    nd = Notesdir.for_user()
    assert nd.conf == config().normalize()


def test_replace_path_refs(fs):
    nd = config().instantiate()
    fs.create_file('/notes/one.md', contents='I link to [two](two.md) [twice](two.md#section).')
    fs.create_file('/notes/subdir/three.md', contents='I link to [two](../two.md) and [four](four.md).')
    nd.replace_path_hrefs('/notes/two.md', '/notes/subdir/new.md')
    assert Path('/notes/one.md').read_text() == 'I link to [two](subdir/new.md) [twice](subdir/new.md#section).'
    assert (Path('/notes/subdir/three.md').read_text() ==
            'I link to [two](new.md) and [four](four.md).')


@freeze_time('2019-08-07T06:05:04')
def test_custom_filename_template(fs):
    conf = config()
    # In reality you'd almost always want the template to end in ${info.path.suffix} but
    # this test doesn't, just to prove it is technically left up to the template.
    conf.filename_template = """${info.title} ${info.guess_created().strftime('%Y-%m-%d')}.md"""
    nd = conf.instantiate()
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
