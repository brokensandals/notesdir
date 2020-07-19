import os.path
from pathlib import Path
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
    assert nd.conf == config().standardize()


def test_replace_path_refs(fs):
    nd = config().instantiate()
    fs.create_file('/notes/one.md', contents='I link to [two](two.md) [twice](two.md#section).')
    fs.create_file('/notes/subdir/three.md', contents='I link to [two](../two.md) and [four](four.md).')
    nd.replace_path_hrefs('/notes/two.md', '/notes/subdir/new.md')
    assert Path('/notes/one.md').read_text() == 'I link to [two](subdir/new.md) [twice](subdir/new.md#section).'
    assert (Path('/notes/subdir/three.md').read_text() ==
            'I link to [two](new.md) and [four](four.md).')


# Most of the Notesdir class is tested indirectly via the tests for the CLI.
